import os
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from yahooquery import Ticker

# === CONFIGURACIÓN ===
CARPETA_DATOS = "./BacktestJL6-70-200"
CARPETA_CACHE = "./cache_yahoo"               # Carpeta para guardar históricos
ARCHIVO_UNIFICADO = "unificado_con_maximos.csv"
ARCHIVO_BACKTEST = "resultado_backtest.csv"

# === PARÁMETROS DE BACKTEST ===
STOP_LOSS = 0.09        # 8% de stop loss
TAKE_PROFIT = 0.40      # 25% de take profit
SALIDA_DIAS_MAX = 30    # salir después de N días si no se toca TP o SL
DIAS_ENFRIAMIENTO = 25   # días de espera antes de volver a operar el mismo ticker

# === TRAILING STOP ===
TRAIL_START = 0.2      # activación del trailing al 12%
TRAIL_DISTANCE = 0.1   # distancia del trailing stop al 6%

# === GESTIÓN DE RIESGO ===
RIESGO_POR_OPERACION = 0.01  # 1% de riesgo por operación
VOLUMEN_MINIMO = 100000      # Volumen mínimo diario promedio (ajustar según necesidad)

# === PARÁMETROS DE CACHÉ ===
DIAS_CACHE_VALIDO = 7     
FORCE_DOWNLOAD = False    
os.makedirs(CARPETA_CACHE, exist_ok=True)


# ---------------------------
# Utilidades I/O y limpieza
# ---------------------------
def detectar_separador(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first_line = f.readline()
    if first_line.count("\t") > 0:
        return "\t"
    elif first_line.count(";") > first_line.count(","):
        return ";"
    else:
        return ","

def limpiar_columnas(df):
    df.columns = [c.strip().lower().replace('"', '').replace("'", "") for c in df.columns]
    df.columns = [c.replace('último', 'ultimo') for c in df.columns]
    return df

def leer_archivos_csv(carpeta):
    archivos = [f for f in os.listdir(carpeta) if f.endswith('.csv')]
    df_total = pd.DataFrame()

    for archivo in archivos:
        fecha_str = re.findall(r'\d{1,2}-\d{1,2}-\d{2,4}', archivo)
        if not fecha_str:
            continue
        fecha = datetime.strptime(fecha_str[0], "%d-%m-%y").date()

        path = os.path.join(carpeta, archivo)
        sep = detectar_separador(path)
        df = pd.read_csv(path, sep=sep, encoding="utf-8", engine="python")
        df = limpiar_columnas(df)
        df["fecha_archivo"] = fecha
        df_total = pd.concat([df_total, df], ignore_index=True)

    print("\nColumnas detectadas:", df_total.columns.tolist())
    df_total = df_total.sort_values(by="fecha_archivo").reset_index(drop=True)
    return df_total


# ---------------------------
# Caché de históricos por ticker
# ---------------------------
def safe_filename(name: str) -> str:
    return re.sub(r'[^\w\-_\.]', '_', name)

def cargar_datos_ticker(ticker: str, force_download: bool = False) -> pd.DataFrame:
    fname = safe_filename(ticker) + ".csv"
    path_cache = os.path.join(CARPETA_CACHE, fname)
    
    if os.path.exists(path_cache) and not (force_download or FORCE_DOWNLOAD):
        fecha_mod = datetime.fromtimestamp(os.path.getmtime(path_cache))
        if datetime.now() - fecha_mod < timedelta(days=DIAS_CACHE_VALIDO):
            try:
                df_cache = pd.read_csv(path_cache, parse_dates=["date"])
                print(f"🟢 Usando caché de {ticker} ({path_cache})")
                if "date" in df_cache.columns:
                    if hasattr(df_cache["date"].dt, 'tz') and df_cache["date"].dt.tz is not None:
                        df_cache["date"] = df_cache["date"].dt.tz_localize(None)
                    df_cache = df_cache.sort_values("date").reset_index(drop=True)
                return df_cache
            except Exception as e:
                print(f"⚠️ Error leyendo caché {path_cache}: {e} → se volverá a descargar.")

    print(f"⬇️ Descargando histórico de {ticker} desde Yahoo...")
    try:
        t = Ticker(ticker)
        hist = t.history(interval="1d")
        if hist is None or (isinstance(hist, pd.DataFrame) and hist.empty):
            print(f"⚠️ No hay datos para {ticker}")
            return pd.DataFrame()

        if isinstance(hist.index, pd.MultiIndex) or (isinstance(hist.index, pd.Index) and hist.index.name is not None):
            hist = hist.reset_index()

        if "date" not in hist.columns:
            dt_col = None
            for c in hist.columns:
                if pd.api.types.is_datetime64_any_dtype(hist[c]):
                    dt_col = c
                    break
            if dt_col is not None:
                hist["date"] = pd.to_datetime(hist[dt_col])
            else:
                if len(hist.columns) >= 2:
                    try:
                        possible = pd.to_datetime(hist.iloc[:, 1], errors="coerce")
                        if possible.notnull().any():
                            hist["date"] = possible
                    except Exception:
                        pass

        if "date" not in hist.columns:
            if isinstance(hist.index, pd.DatetimeIndex):
                hist = hist.reset_index()
                hist.rename(columns={hist.columns[0]: "date"}, inplace=True)
            else:
                print(f"❌ No se ha podido inferir la columna 'date' para {ticker}.")
                return pd.DataFrame()

        hist["date"] = pd.to_datetime(hist["date"])
        if hasattr(hist["date"].dt, 'tz_localize') and hist["date"].dt.tz is not None:
            hist["date"] = hist["date"].dt.tz_localize(None)
        hist = hist.sort_values("date").reset_index(drop=True)

        try:
            hist.to_csv(path_cache, index=False)
            print(f"💾 Guardado en caché: {path_cache}")
        except Exception as e:
            print(f"⚠️ No se pudo guardar cache {path_cache}: {e}")

        return hist

    except Exception as e:
        print(f"❌ Error al descargar {ticker}: {e}")
        return pd.DataFrame()


# ---------------------------
# Cálculo de máximos posteriores
# ---------------------------
def calcular_maximos(df):
    if "ticker" not in df.columns:
        raise ValueError("❌ No se encontró la columna 'ticker' en los datos unificados. "
                         f"Columnas disponibles: {df.columns.tolist()}")

    resultados = []
    tickers = df["ticker"].unique()

    for ticker in tickers:
        hist = cargar_datos_ticker(ticker)
        if hist.empty:
            continue

        hist_dates = hist.copy()
        hist_dates["date_only"] = pd.to_datetime(hist_dates["date"]).dt.date

        df_ticker = df[df["ticker"] == ticker]

        for _, row in df_ticker.iterrows():
            fecha = row["fecha_archivo"]
            try:
                fecha_obj = pd.to_datetime(fecha).date() if not isinstance(fecha, datetime) else fecha
            except Exception:
                fecha_obj = fecha

            futuros = hist_dates[hist_dates["date_only"] >= fecha_obj].copy()
            if futuros.empty:
                max_price = None
                days_to_max = None
            else:
                col_high = "high" if "high" in futuros.columns else ("close" if "close" in futuros.columns else futuros.columns[0])
                max_price = futuros[col_high].max()
                idxmax = futuros[col_high].idxmax()
                fecha_max = futuros.loc[idxmax, "date_only"]
                days_to_max = (fecha_max - fecha_obj).days

            row_data = row.to_dict()
            row_data["max_price_after"] = max_price
            row_data["days_to_max"] = days_to_max
            resultados.append(row_data)

    return pd.DataFrame(resultados)


# ---------------------------
# Backtest: entrada siguiente vela + TP/SL + TRAILING
# ---------------------------
def validar_datos_entrada(df):
    """Valida que los datos de entrada sean correctos."""
    if df.empty:
        print("❌ Error: El DataFrame de entrada está vacío")
        return False
    
    columnas_requeridas = ["ticker", "fecha_archivo"]
    for col in columnas_requeridas:
        if col not in df.columns:
            print(f"❌ Error: Falta la columna requerida: {col}")
            return False
    
    # Convertir fechas si es necesario
    if not pd.api.types.is_datetime64_any_dtype(df["fecha_archivo"]):
        try:
            df["fecha_archivo"] = pd.to_datetime(df["fecha_archivo"], errors='coerce')
        except Exception as e:
            print(f"❌ Error al convertir fechas: {e}")
            return False
    
    return True

def calcular_volumen_promedio(hist, dias=20):
    """Calcula el volumen promedio de los últimos N días."""
    if "volume" not in hist.columns or len(hist) < dias:
        return float('inf')  # Si no hay datos de volumen o son insuficientes, retornar infinito
    return hist["volume"].tail(dias).mean()

def ejecutar_backtest(df):
    """Ejecuta el backtest con gestión de riesgo mejorada."""
    # Validar datos de entrada
    if not validar_datos_entrada(df):
        return pd.DataFrame()
    
    operaciones = []
    ultima_operacion_por_ticker = {}
    df = df.sort_values('fecha_archivo')
    capital_inicial = 10000  # Capital inicial para cálculo de posición
    capital = capital_inicial
    
    for ticker in df["ticker"].unique():
        print(f"Simulando {ticker}...")
        hist = cargar_datos_ticker(ticker)
        if hist.empty:
            continue
            
        # Verificar volumen mínimo
        volumen_promedio = calcular_volumen_promedio(hist)
        if volumen_promedio < VOLUMEN_MINIMO:
            print(f"⏭️  Saltando {ticker} - Volumen promedio insuficiente: {volumen_promedio:,.0f}")
            continue

        hist = hist.sort_values("date").reset_index(drop=True)
        hist["date"] = pd.to_datetime(hist["date"])
        if hasattr(hist["date"].dt, 'tz_localize') and hist["date"].dt.tz is not None:
            hist["date"] = hist["date"].dt.tz_localize(None)

        for _, row in df[df["ticker"] == ticker].iterrows():
            fecha_senal = pd.to_datetime(row["fecha_archivo"])
            if hasattr(fecha_senal, 'tz_localize') and fecha_senal.tzinfo is not None:
                fecha_senal = fecha_senal.tz_localize(None)
            
            # Verificar período de enfriamiento
            if ticker in ultima_operacion_por_ticker:
                dias_desde_ultima_op = (fecha_senal - ultima_operacion_por_ticker[ticker]).days
                if dias_desde_ultima_op < DIAS_ENFRIAMIENTO:
                    print(f"⏭️  Saltando {ticker} - Operado hace {dias_desde_ultima_op} días (período de enfriamiento: {DIAS_ENFRIAMIENTO} días)")
                    continue
            
            # Obtener datos de la vela de entrada
            entrada_fecha = fecha_senal + timedelta(days=1)
            futuros = hist[hist["date"] >= entrada_fecha].copy()
            if futuros.empty:
                continue

            # Precio de entrada (usar open si está disponible, si no close)
            precio_entrada = float(futuros.iloc[0].get("open", np.nan))
            if np.isnan(precio_entrada):
                precio_entrada = float(futuros.iloc[0].get("close", np.nan))
                
            # Calcular tamaño de posición basado en el riesgo
            riesgo_por_accion = precio_entrada * STOP_LOSS
            if riesgo_por_accion <= 0:
                continue
                
            tamano_posicion = (capital * RIESGO_POR_OPERACION) / riesgo_por_accion
            tamano_posicion = int(tamano_posicion)  # Solo posiciones enteras
            
            if tamano_posicion <= 0:
                print(f"⚠️  Tamaño de posición inválido para {ticker}: {tamano_posicion}")
                continue

            # Inicializar variables de salida
            salida_fecha, precio_salida, resultado_pct = None, None, None
            trailing_active = False
            trailing_stop = None
            razon_salida = "Ninguna"
            
            # Precios objetivo
            precio_tp = precio_entrada * (1 + TAKE_PROFIT)
            precio_sl = precio_entrada * (1 - STOP_LOSS)
            
            # Iterar sobre las velas futuras
            iter_velas = futuros.iloc[1:SALIDA_DIAS_MAX+1]
            triggered = False
            
            for _, vela in iter_velas.iterrows():
                high = float(vela.get("high", np.nan))
                low = float(vela.get("low", np.nan))
                close = float(vela.get("close", np.nan))
                fecha_vela = vela["date"]
                
                # 1. Verificar si se activa el trailing stop
                if not trailing_active and high >= precio_entrada * (1 + TRAIL_START):
                    trailing_active = True
                    trailing_stop = max(high * (1 - TRAIL_DISTANCE), precio_entrada)
                    print(f"  🔄 Trailing stop activado para {ticker} a {trailing_stop:.2f}")
                
                # 2. Actualizar trailing stop si está activo
                if trailing_active and high > precio_entrada * (1 + TRAIL_START):
                    nuevo_trailing = high * (1 - TRAIL_DISTANCE)
                    trailing_stop = max(trailing_stop, nuevo_trailing)
                
                # 3. Verificar condiciones de salida (en orden de prioridad)
                # 3.1 Verificar si tanto TP como SL se alcanzaron en la misma vela
                if high >= precio_tp and low <= precio_sl:
                    # Determinar cuál se alcanzó primero (simplificación)
                    if abs(precio_entrada - precio_sl) / (precio_tp - precio_entrada) < 0.5:
                        precio_salida = precio_sl
                        razon_salida = "Stop Loss (TP y SL en misma vela)"
                    else:
                        precio_salida = precio_tp
                        razon_salida = "Take Profit (TP y SL en misma vela)"
                    salida_fecha = fecha_vela
                    triggered = True
                    break
                
                # 3.2 TP alcanzado
                elif high >= precio_tp:
                    precio_salida = precio_tp
                    salida_fecha = fecha_vela
                    razon_salida = "Take Profit"
                    triggered = True
                    break
                
                # 3.3 SL alcanzado
                elif low <= precio_sl:
                    precio_salida = precio_sl
                    salida_fecha = fecha_vela
                    razon_salida = "Stop Loss"
                    triggered = True
                    break
                
                # 3.4 Trailing stop alcanzado
                elif trailing_active and low <= trailing_stop:
                    precio_salida = trailing_stop
                    salida_fecha = fecha_vela
                    razon_salida = "Trailing Stop"
                    triggered = True
                    break
            
            # Si no se disparó ninguna salida, salir al cierre del último día
            if not triggered:
                idx = min(SALIDA_DIAS_MAX, len(futuros)-1)
                precio_salida = float(futuros.iloc[idx].get("close", np.nan))
                salida_fecha = futuros.iloc[idx]["date"]
                razon_salida = f"Salida por tiempo ({SALIDA_DIAS_MAX} días)"
            
            # Validar precios
            if np.isnan(precio_entrada) or precio_salida is None or np.isnan(precio_salida):
                print(f"⚠️  Precios inválidos para {ticker}")
                continue
            
            # Calcular resultado
            resultado_pct = (precio_salida / precio_entrada) - 1
            ganancia_neta = tamano_posicion * (precio_salida - precio_entrada)
            capital += ganancia_neta  # Actualizar capital
            
            # Registrar la operación
            operacion = {
                "ticker": ticker,
                "fecha_senal": fecha_senal.date() if hasattr(fecha_senal, "date") else fecha_senal,
                "entrada_fecha": entrada_fecha.date() if hasattr(entrada_fecha, "date") else entrada_fecha,
                "precio_entrada": round(precio_entrada, 4),
                "salida_fecha": salida_fecha.date() if hasattr(salida_fecha, "date") else salida_fecha,
                "precio_salida": round(precio_salida, 4),
                "resultado_pct": round(resultado_pct, 6),
                "razon_salida": razon_salida,
                "tamano_posicion": tamano_posicion,
                "ganancia_neta": round(ganancia_neta, 2),
                "capital_despues": round(capital, 2)
            }
            operaciones.append(operacion)
            
            # Actualizar última operación para este ticker
            ultima_operacion_por_ticker[ticker] = fecha_senal
            
            # Imprimir resumen de la operación
            resultado_str = "🟢 GANANCIA" if resultado_pct > 0 else "🔴 PÉRDIDA"
            print(f"  {resultado_str} {ticker}: {resultado_pct*100:.2f}% | Razón: {razon_salida}")
            print(f"  Entrada: {precio_entrada:.2f} | Salida: {precio_salida:.2f} | Capital: {capital:,.2f}")
    
    # Crear DataFrame con los resultados
    if not operaciones:
        print("⚠️  No se generaron operaciones")
        return pd.DataFrame()
    
    df_resultados = pd.DataFrame(operaciones)
    
    # Calcular métricas finales
    total_operaciones = len(df_resultados)
    operaciones_ganadoras = (df_resultados["resultado_pct"] > 0).sum()
    win_rate = (operaciones_ganadoras / total_operaciones) * 100
    profit_factor = abs(df_resultados[df_resultados["resultado_pct"] > 0]["ganancia_neta"].sum() / 
                       df_resultados[df_resultados["resultado_pct"] <= 0]["ganancia_neta"].sum())
    
    print("\n📊 RESUMEN FINAL")
    print(f"Operaciones totales: {total_operaciones}")
    print(f"Operaciones ganadoras: {operaciones_ganadoras} ({win_rate:.1f}%)")
    print(f"Capital final: ${capital:,.2f} ({(capital/capital_inicial-1)*100:.2f}%)")
    print(f"Profit Factor: {profit_factor:.2f}")
    
    return df_resultados


# ---------------------------
# EJECUCIÓN GENERAL
# ---------------------------
if __name__ == "__main__":
    df_unificado = leer_archivos_csv(CARPETA_DATOS)
    print(f"\nArchivos leídos: {df_unificado.shape[0]} filas")

    df_resultado = calcular_maximos(df_unificado)
    df_resultado.to_csv(ARCHIVO_UNIFICADO, index=False)
    print(f"\n✅ Archivo unificado guardado en: {ARCHIVO_UNIFICADO}")

    df_backtest = ejecutar_backtest(df_resultado)
    df_backtest["resultado_%"] = df_backtest["resultado_pct"] * 100
    df_backtest.to_csv(ARCHIVO_BACKTEST, index=False)
    print(f"\n✅ Resultado del backtest guardado en: {ARCHIVO_BACKTEST}")

    total = len(df_backtest)
    ganadoras = (df_backtest["resultado_pct"] > 0).sum()
    media = df_backtest["resultado_pct"].mean() if total > 0 else 0.0

    print(f"\n📊 RESUMEN GLOBAL")
    print(f"Operaciones totales: {total}")
    print(f"Ganadoras: {ganadoras} ({(ganadoras/total if total>0 else 0):.1%})")
    print(f"Rentabilidad media por operación: {media:.2%}")
