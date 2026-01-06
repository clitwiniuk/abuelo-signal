import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# === CONFIGURACIÓN ===
ARCHIVO_BACKTEST = "resultado_backtest.csv"   # Ruta a tu CSV de resultados
CAPITAL_INICIAL = 10000                       # Capital inicial
RISK_PER_TRADE = 0.01                       # % riesgo fijo por operación (2%)

# === 1️⃣ Cargar datos ===
df = pd.read_csv(ARCHIVO_BACKTEST)
df["fecha_senal"] = pd.to_datetime(df["fecha_senal"])
df["entrada_fecha"] = pd.to_datetime(df["entrada_fecha"])
df["salida_fecha"] = pd.to_datetime(df["salida_fecha"])
df = df.sort_values("entrada_fecha")

# === 2️⃣ Métricas básicas ===
n_total = len(df)
n_ganadoras = (df["resultado_pct"] > 0).sum()
n_perdedoras = (df["resultado_pct"] <= 0).sum()
winrate = n_ganadoras / n_total * 100
profit_factor = df.loc[df["resultado_pct"] > 0, "resultado_pct"].sum() / abs(df.loc[df["resultado_pct"] <= 0, "resultado_pct"].sum())
media = df["resultado_pct"].mean()
std = df["resultado_pct"].std()
expectancy = (winrate/100) * df.loc[df["resultado_pct"]>0,"resultado_pct"].mean() + ((100-winrate)/100) * df.loc[df["resultado_pct"]<=0,"resultado_pct"].mean()

# === 3️⃣ Simular equity curve (capital acumulado) ===
# Crear un DataFrame con todas las fechas del backtest
fechas_unicas = pd.concat([df["entrada_fecha"], df["salida_fecha"]]).unique()
# Convertir a numpy array para ordenar si es necesario
if hasattr(fechas_unicas, 'sort'):
    fechas_unicas.sort()
else:
    fechas_unicas = np.sort(fechas_unicas)

# Crear un DataFrame con todas las fechas
fecha_inicio = df["entrada_fecha"].min()
fecha_fin = df["salida_fecha"].max()
rango_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
df_equity = pd.DataFrame(index=rango_fechas)
df_equity["capital"] = 0.0
df_equity.loc[df_equity.index[0], "capital"] = CAPITAL_INICIAL

# Inicializar diccionario para mantener el capital en cada operación activa
operaciones_activas = {}
capital_total = CAPITAL_INICIAL

# Procesar cada día
for fecha_actual in df_equity.index:
    # Inicializar el capital del día con el del día anterior (si existe)
    if fecha_actual > df_equity.index[0]:
        df_equity.loc[fecha_actual, "capital"] = df_equity.loc[df_equity.index[df_equity.index.get_loc(fecha_actual)-1], "capital"]
    
    # Procesar operaciones que se cierran hoy
    for ticker in list(operaciones_activas.keys()):
        if operaciones_activas[ticker]["fecha_salida"] == fecha_actual:
            # Obtener los datos de la operación
            capital_invertido = operaciones_activas[ticker]["capital_invertido"]
            resultado_pct = operaciones_activas[ticker]["resultado_pct"]
            
            # Calcular el resultado de la operación
            resultado = capital_invertido * resultado_pct
            
            # Actualizar el capital total
            df_equity.loc[fecha_actual, "capital"] += resultado
            
            # Eliminar la operación de las activas
            del operaciones_activas[ticker]
    
    # Procesar operaciones que empiezan hoy
    operaciones_dia = df[df["entrada_fecha"] == fecha_actual]
    for _, operacion in operaciones_dia.iterrows():
        # Calcular el capital a invertir en esta operación
        capital_invertido = df_equity.loc[fecha_actual, "capital"] * RISK_PER_TRADE
        
        # Registrar la operación activa
        operaciones_activas[operacion["ticker"]] = {
            "fecha_salida": operacion["salida_fecha"],
            "capital_invertido": capital_invertido,
            "resultado_pct": operacion["resultado_pct"]
        }
        
        # Restar el capital invertido del total (se sumará de nuevo al cerrar)
        df_equity.loc[fecha_actual, "capital"] -= capital_invertido

# Asegurarse de que el capital nunca sea negativo
df_equity["capital"] = df_equity["capital"].clip(lower=0)

# Calcular métricas de drawdown
df_equity["max_capital"] = df_equity["capital"].cummax()
df_equity["drawdown"] = (df_equity["capital"] - df_equity["max_capital"]) / df_equity["max_capital"]
max_drawdown = df_equity["drawdown"].min()

# Calcular retorno total y anualizado
dias_totales = (df_equity.index[-1] - df_equity.index[0]).days
retorno_total = (df_equity["capital"].iloc[-1] / CAPITAL_INICIAL - 1) * 100
retorno_anualizado = ((1 + retorno_total/100) ** (365/dias_totales) - 1) * 100 if dias_totales > 0 else 0

# === 4️⃣ Métricas temporales ===
df["duracion_dias"] = (df["salida_fecha"] - df["entrada_fecha"]).dt.days
media_duracion = df["duracion_dias"].mean()

# === 5️⃣ Mostrar resultados ===
print("\n📊 ANÁLISIS DE BACKTEST")
print(f"Período: {df_equity.index[0].strftime('%Y-%m-%d')} a {df_equity.index[-1].strftime('%Y-%m-%d')} ({dias_totales} días)")
print(f"Capital inicial: ${CAPITAL_INICIAL:,.2f}")
print(f"Capital final: ${df_equity['capital'].iloc[-1]:,.2f}")
print(f"Retorno total: {retorno_total:.2f}%")
print(f"Retorno anualizado: {retorno_anualizado:.2f}%")
print(f"Operaciones totales: {n_total}")
print(f"Ganadoras: {n_ganadoras}  ({winrate:.1f}%)")
print(f"Perdedoras: {n_perdedoras}  ({100-winrate:.1f}%)")
print(f"Profit factor: {profit_factor:.2f}")
print(f"Expectancy: {expectancy*100:.2f}%")
print(f"Media por operación: {media*100:.2f}%  |  Desviación: {std*100:.2f}%")
print(f"Duración media (días): {media_duracion:.1f}")
print(f"Máx. Drawdown: {max_drawdown*100:.2f}%")
print(f"Riesgo por operación: {RISK_PER_TRADE*100:.1f}% del capital")

# === 6️⃣ Visualizaciones ===
plt.style.use('seaborn')

# Crear figura y ejes
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

# Gráfico de capital
ax1.plot(df_equity.index, df_equity["capital"], label='Capital', lw=2, color='#2ecc71')

# Líneas de referencia
ax1.axhline(y=CAPITAL_INICIAL, color='#7f8c8d', linestyle='--', alpha=0.7, label='Capital Inicial')

# Rellenar área bajo la curva
ax1.fill_between(df_equity.index, df_equity["capital"], CAPITAL_INICIAL, 
                where=(df_equity["capital"] > CAPITAL_INICIAL), 
                color='#2ecc71', alpha=0.2, interpolate=True, label='Ganancias')
ax1.fill_between(df_equity.index, df_equity["capital"], CAPITAL_INICIAL, 
                where=(df_equity["capital"] <= CAPITAL_INICIAL), 
                color='#e74c3c', alpha=0.2, interpolate=True, label='Pérdidas')

# Configurar el gráfico de capital
ax1.set_title(f'Curva de Capital | Retorno: {retorno_total:.1f}% | Max DD: {max_drawdown*100:.1f}%', 
              fontsize=14, fontweight='bold', pad=20)
ax1.set_ylabel('Capital ($)', fontsize=12)
ax1.grid(True, linestyle='--', alpha=0.6)
ax1.legend(loc='upper left', frameon=True, framealpha=0.9)

# Gráfico de drawdown
ax2.fill_between(df_equity.index, df_equity["drawdown"]*100, 0, 
                where=(df_equity["drawdown"] < 0), 
                color='#e74c3c', alpha=0.3, label='Drawdown')
ax2.axhline(y=0, color='#7f8c8d', linestyle='-', alpha=0.5)

# Configurar el gráfico de drawdown
ax2.set_title('Drawdown', fontsize=12, pad=10)
ax2.set_ylabel('DD (%)', fontsize=10)
ax2.set_xlabel('Fecha', fontsize=12)
ax2.grid(True, linestyle='--', alpha=0.6)

# Formatear fechas
ax2.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d'))
ax2.xaxis.set_major_locator(plt.MaxNLocator(8))
plt.xticks(rotation=45)

# Ajustar diseño y guardar
plt.tight_layout()
plt.savefig('equity_curve.png', dpi=300, bbox_inches='tight')
plt.show()

plt.figure(figsize=(8,5))
plt.hist(df["resultado_pct"]*100, bins=20, edgecolor="black")
plt.title("Distribución de resultados (%)")
plt.xlabel("Rentabilidad por trade (%)")
plt.ylabel("Frecuencia")
plt.grid(True)
plt.tight_layout()
plt.show()

# === 7️⃣ Ranking de rendimiento por ticker ===
ranking = df.groupby("ticker")["resultado_pct"].agg(["count", "mean", "sum"]).sort_values("sum", ascending=False)
print("\n🏆 RENDIMIENTO POR TICKER:")
print(ranking)
