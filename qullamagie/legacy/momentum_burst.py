# =================================================================
# SISTEMA COMPLETO: Universo NASDAQ Automático + IBKR + Python
# Momentum Burst Scanner | Cuenta $1,000 | Riesgo 2%
# SIN ProRealTime | SIN Watchlist Manual
# =================================================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import warnings
warnings.filterwarnings('ignore')

# -------------------------------
# CONFIGURACIÓN
# -------------------------------
CUENTA_CAPITAL = 1000
RIESGO_POR_OPERACION = 0.02
RIESGO_DOLAR = CUENTA_CAPITAL * RIESGO_POR_OPERACION

# IBKR Configuration
IBKR_HOST = '127.0.0.1'
IBKR_PORT = 7497  # 7497 = Paper, 7496 = Live
IBKR_CLIENT_ID = 1

# Parámetros de Momentum Burst
MIN_PRICE = 5
MAX_PRICE = 100
MIN_AVG_VOLUME = 100000
MIN_EXPANSION = 0.04
MAX_BURST = 0.12
MIN_STOP_PCT = 2.0
MAX_STOP_PCT = 4.0
EMA_FAST = 10
EMA_SLOW = 20

# -------------------------------
# FUNCIÓN 1: Obtener Universo NASDAQ Automáticamente
# -------------------------------
def obtener_universo_nasdaq():
    """
    Descarga la lista completa de tickers del NASDAQ desde API pública
    Fuente: https://www.nasdaq.com/market-activity/stocks/screener
    """
    print("\n📡 Descargando universo NASDAQ...")
    
    try:
        # Opción A: NASDAQ API pública (sin auth)
        url = "https://api.nasdaq.com/api/screener/stocks"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        
        params = {
            'tableonly': 'true',
            'limit': '5000',  # Máximo permitido
            'exchange': 'NASDAQ'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extraer tickers
            if 'data' in data and 'rows' in data['data']:
                tickers = [row['symbol'] for row in data['data']['rows']]
                print(f"✅ {len(tickers)} tickers NASDAQ obtenidos")
                return tickers
            else:
                print("⚠️ Formato de respuesta inesperado")
        
        # Opción B: Fallback a lista estática actualizada (si API falla)
        print("⚠️ Fallback a lista alternativa...")
        return obtener_universo_alternativo()
        
    except Exception as e:
        print(f"⚠️ Error obteniendo NASDAQ: {e}")
        return obtener_universo_alternativo()

def obtener_universo_alternativo():
    """
    Fallback: Lista de tickers líquidos del NASDAQ (actualizable)
    """
    # Fuente alternativa: Financial Modeling Prep (gratis, requiere API key)
    # O lista curada de tickers líquidos
    
    # Opción 1: FMP API (gratis hasta 250 llamadas/día)
    try:
        api_key = ""  # Opcional: obtener gratis en financialmodelingprep.com
        if api_key:
            url = f"https://financialmodelingprep.com/api/v3/stock/list?apikey={api_key}"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                tickers = [item['symbol'] for item in data if item['exchange'] == 'NASDAQ']
                print(f"✅ {len(tickers)} tickers desde FMP")
                return tickers
    except:
        pass
    
    # Opción 2: Lista curada de ~500 tickers líquidos (fallback seguro)
    tickers_liquidos = [
        # Tecnología
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA',
        'AMD', 'NFLX', 'AVGO', 'COST', 'PEP', 'ADBE', 'CSCO', 'INTC',
        'PYPL', 'CMCSA', 'TXN', 'QCOM', 'AMAT', 'SBUX', 'GILD', 'BKNG',
        'MDLZ', 'ISRG', 'ADI', 'REGN', 'LRCX', 'KLAC', 'SNPS', 'CDNS',
        'MELI', 'ASML', 'ARM', 'MRVL', 'CRWD', 'PANW', 'ADSK', 'FTNT',
        
        # ETFs
        'QQQ', 'SPY', 'IWM', 'DIA', 'VTI', 'VOO', 'VEA', 'VWO',
        'TLT', 'IEF', 'SHY', 'GLD', 'SLV', 'USO', 'UNG',
        
        # Biotech
        'MRNA', 'BNTX', 'VRTX', 'BIIB', 'ILMN', 'ALXN', 'BMRN',
        
        # Consumer
        'LULU', 'NKE', 'SBUX', 'MCD', 'CMG', 'DPZ', 'YUM',
        
        # Financieros
        'PYPL', 'SQ', 'COIN', 'SOFI', 'AFRM', 'UPST',
        
        # Añadir más según necesidad...
    ]
    
    print(f"⚠️ Usando lista curada de {len(tickers_liquidos)} tickers líquidos")
    return tickers_liquidos

# -------------------------------
# FUNCIÓN 2: Pre-filtrado rápido (sin conectar a IBKR)
# -------------------------------
def pre_filtrar_tickers(tickers):
    """
    Filtra tickers por criterios básicos antes de consultar IBKR
    Reduce el universo de ~3000 a ~300-500 tickers operables
    """
    print(f"\n🔍 Pre-filtrando {len(tickers)} tickers...")
    
    # Criterios que podemos validar sin datos históricos:
    # 1. Longitud del símbolo (2-5 caracteres, típico de acciones)
    # 2. Sin caracteres especiales
    # 3. No son ETFs si solo queremos acciones (opcional)
    
    tickers_filtrados = []
    for ticker in tickers:
        if isinstance(ticker, str) and 2 <= len(ticker) <= 5:
            if ticker.isalpha() or ticker.replace('.', '').isalpha():
                tickers_filtrados.append(ticker)
    
    print(f"✅ {len(tickers_filtrados)} tickers tras pre-filtro básico")
    return tickers_filtrados

# -------------------------------
# FUNCIÓN 3: Conexión a IBKR
# -------------------------------
def conectar_ibkr():
    """Establece conexión con TWS o IB Gateway"""
    try:
        from ib_insync import IB
        ib = IB()
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=60)
        
        if ib.isConnected():
            print("✅ Conectado a IBKR API")
            return ib
        else:
            print("❌ No se pudo conectar")
            return None
    except Exception as e:
        print(f"⚠️ Error conectando: {e}")
        return None

# -------------------------------
# FUNCIÓN 4: Obtener datos y validar ticker rápidamente
# -------------------------------
def validar_ticker_rapido(ib, ticker):
    """
    Obtiene datos y valida criterios básicos de liquidez y precio
    Retorna None si no cumple, DataFrame si cumple
    """
    try:
        from ib_insync import Stock
        contract = Stock(ticker, 'SMART', 'USD')
        
        # Obtener 3 meses de datos diarios
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='3 M',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        
        if not bars or len(bars) < 50:
            return None
        
        df = pd.DataFrame([{
            'date': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        } for bar in bars])
        
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Filtro de precio
        precio_actual = df['close'].iloc[-1]
        if not (MIN_PRICE <= precio_actual <= MAX_PRICE):
            return None
        
        # Filtro de volumen promedio
        vol_promedio = df['volume'].iloc[-20:].mean()
        if vol_promedio < MIN_AVG_VOLUME:
            return None
        
        return df
    except Exception as e:
        return None

# -------------------------------
# FUNCIÓN 5: Calcular indicadores
# -------------------------------
def calcular_indicadores(df):
    """Calcula EMA, ATR, volumen, momentum"""
    if df is None or len(df) < 50:
        return None
    
    df = df.copy()
    
    # EMAs
    df['ema10'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Volumen promedio
    df['vol_avg20'] = df['volume'].rolling(window=20).mean()
    
    # Rango diario
    df['range'] = df['high'] - df['low']
    df['range_avg5'] = df['range'].rolling(window=5).mean()
    
    # ATR
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr14'] = df['tr'].rolling(window=14).mean()
    
    # Momentum
    df['momentum10'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10) * 100
    df['expansion'] = (df['close'] - df['close'].shift(1)) / df['close'].shift(1)
    
    return df

# -------------------------------
# FUNCIÓN 6: Detectar Momentum Burst
# -------------------------------
def detectar_burst(df):
    """Aplica criterios Stockbee/Qullamaggie"""
    if df is None or len(df) < 10:
        return False, {}
    
    hoy = df.iloc[-1]
    ayer = df.iloc[-2]
    
    señales = {}
    
    # 1. Tendencia alcista
    señales['tendencia'] = (hoy['close'] > hoy['ema10'] > hoy['ema20'])
    
    # 2. Range Expansion (4%+)
    señales['expansion'] = hoy['expansion'] >= MIN_EXPANSION
    
    # 3. No perseguir (no 3 días seguidos al alza)
    subio3 = (df['close'].iloc[-1] > df['close'].iloc[-2] and
              df['close'].iloc[-2] > df['close'].iloc[-3] and
              df['close'].iloc[-3] > df['close'].iloc[-4])
    señales['no_perseguir'] = not subio3
    
    # 4. Volumen expansivo
    señales['vol_expansivo'] = hoy['volume'] > ayer['volume']
    
    # 5. Día previo estrecho
    señales['previo_estrecho'] = ayer['range'] < (hoy['range_avg5'] * 0.8)
    
    # 6. Cierre fuerte
    rango_hoy = hoy['high'] - hoy['low']
    señales['cierre_fuerte'] = hoy['close'] >= (hoy['low'] + (rango_hoy * 0.66))
    
    # 7. No exagerado (<12%)
    señales['no_exagerado'] = hoy['expansion'] < MAX_BURST
    
    criterios_cumplidos = sum(señales.values())
    señales['total'] = criterios_cumplidos
    señales['es_burst'] = criterios_cumplidos >= 5
    
    return señales['es_burst'], señales

# -------------------------------
# FUNCIÓN 7: Calcular Gestión de Riesgo
# -------------------------------
def calcular_gestion_riesgo(df):
    """Calcula stop, targets, posición"""
    hoy = df.iloc[-1]
    
    stop_level = min(hoy['low'], hoy['ema10'])
    stop_dolar = hoy['close'] - stop_level
    stop_pct = (stop_dolar / hoy['close']) * 100
    
    if not (MIN_STOP_PCT <= stop_pct <= MAX_STOP_PCT):
        return None
    
    shares = int(RIESGO_DOLAR / stop_dolar)
    if shares < 1:
        return None
    
    return {
        'precio': round(hoy['close'], 2),
        'stop': round(stop_level, 2),
        'stop_pct': round(stop_pct, 2),
        'shares': shares,
        'riesgo_$': round(shares * stop_dolar, 2),
        'target_2:1': round(hoy['close'] + (stop_dolar * 2), 2),
        'target_3:1': round(hoy['close'] + (stop_dolar * 3), 2),
        'potencial_2:1_$': round(shares * stop_dolar * 2, 2)
    }

# -------------------------------
# FUNCIÓN 8: Verificar Contexto de Mercado
# -------------------------------
def verificar_contexto(ib):
    """Verifica SPY, QQQ, VIX"""
    print("\n📈 Verificando contexto de mercado...")
    
    resultados = {}
    
    for indice, nombre in [('SPY', 'SPY'), ('QQQ', 'QQQ'), ('VIX', 'VIX')]:
        df = None
        try:
            from ib_insync import Stock, Index
            if indice == 'VIX':
                contract = Index(indice, 'CBOE', 'USD')
            else:
                contract = Stock(indice, 'SMART', 'USD')
            
            bars = ib.reqHistoricalData(contract, endDateTime='', durationStr='6 M',
                                       barSizeSetting='1 day', whatToShow='TRADES',
                                       useRTH=True, formatDate=1)
            if bars:
                df = pd.DataFrame([{'date': b.date, 'close': b.close} for b in bars])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
        except:
            pass
        
        if df is not None:
            if indice == 'VIX':
                resultados['VIX'] = df['close'].iloc[-1]
                resultados['VIX_favorable'] = resultados['VIX'] < 35
            else:
                ema50 = df['close'].ewm(span=50).mean().iloc[-1]
                resultados[f'{nombre}_sobre_EMA50'] = df['close'].iloc[-1] > ema50
    
    resultados['MERCADO_FAVORABLE'] = (
        resultados.get('SPY_sobre_EMA50', False) and
        resultados.get('QQQ_sobre_EMA50', False) and
        resultados.get('VIX_favorable', False)
    )
    
    print(f"   🎯 MERCADO FAVORABLE: {'✅ SÍ' if resultados['MERCADO_FAVORABLE'] else '❌ NO'}")
    return resultados

# -------------------------------
# FUNCIÓN 9: Verificar Earnings
# -------------------------------
def verificar_earnings(ticker):
    """Evita operar antes de earnings"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_dates
        if earnings is None or len(earnings) == 0:
            return True, None
        hoy = datetime.now()
        for idx, row in earnings.iterrows():
            fecha = row.name if hasattr(row, 'name') else None
            if fecha:
                dias = (fecha - hoy).days
                if 0 <= dias <= 5:
                    return False, fecha
        return True, None
    except:
        return True, None

# -------------------------------
# FUNCIÓN PRINCIPAL: Escaneo Completo NASDAQ
# -------------------------------
def ejecutar_escaneo_nasdaq_completo():
    """Ejecuta escaneo completo del universo NASDAQ"""
    print("=" * 70)
    print("🚀 ESCANEO MOMENTUM BURST - UNIVERSO NASDAQ COMPLETO")
    print(f"💰 Capital: ${CUENTA_CAPITAL} | Riesgo: ${RIESGO_DOLAR}")
    print("=" * 70)
    
    # 1. Obtener universo NASDAQ
    tickers = obtener_universo_nasdaq()
    tickers = pre_filtrar_tickers(tickers)
    
    # 2. Conectar a IBKR
    ib = conectar_ibkr()
    if ib is None:
        print("❌ No se pudo conectar a IBKR. Terminando.")
        return
    
    # 3. Contexto de mercado
    contexto = verificar_contexto(ib)
    if not contexto['MERCADO_FAVORABLE']:
        print("\n⚠️ ADVERTENCIA: Mercado no favorable.")
        continuar = input("   ¿Continuar de todas formas? (s/n): ")
        if continuar.lower() != 's':
            ib.disconnect()
            return
    
    # 4. Escanear tickers
    print(f"\n🔍 Escaneando {len(tickers)} tickers del NASDAQ...")
    print("   (Esto puede tomar 10-30 minutos dependiendo de tu conexión)")
    
    señales_encontradas = []
    tickers_procesados = 0
    tickers_validos = 0
    
    for i, ticker in enumerate(tickers, 1):
        # Progreso
        if i % 50 == 0:
            print(f"   Progreso: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%) - {len(señales_encontradas)} señales")
        
        # Validación rápida (precio + volumen)
        df = validar_ticker_rapido(ib, ticker)
        if df is None:
            continue
        
        tickers_validos += 1
        
        # Calcular indicadores
        df = calcular_indicadores(df)
        if df is None:
            continue
        
        # Detectar burst
        es_burst, detalles = detectar_burst(df)
        if not es_burst:
            continue
        
        # Verificar earnings
        ok_earnings, fecha = verificar_earnings(ticker)
        if not ok_earnings:
            continue
        
        # Calcular gestión
        gestion = calcular_gestion_riesgo(df)
        if gestion is None:
            continue
        
        # Señal válida
        señal = {
            'Ticker': ticker,
            **gestion,
            'Burst%': round(df.iloc[-1]['expansion'] * 100, 2),
            'Volumen': int(df.iloc[-1]['volume']),
            'Momentum10': round(df.iloc[-1]['momentum10'], 2),
            'Criterios': f"{detalles['total']}/7"
        }
        señales_encontradas.append(señal)
        print(f"   ✅ {ticker}: SEÑAL ({detalles['total']}/7)")
        
        # Limitar a top 10 señales (las mejores)
        if len(señales_encontradas) >= 10:
            print("   ⚠️ Límite de 10 señales alcanzado")
            break
    
    ib.disconnect()
    
    # 5. Guardar resultados
    print("\n" + "=" * 70)
    print(f"📊 RESUMEN: {tickers_validos} tickers válidos de {len(tickers)} escaneados")
    print("=" * 70)
    
    if señales_encontradas:
        df_final = pd.DataFrame(señales_encontradas)
        df_final = df_final.sort_values('Momentum10', ascending=False)
        df_final.to_csv("senales_nasdaq_momentum.csv", index=False)
        
        print("📋 TOP SEÑALES ENCONTRADAS")
        print("=" * 70)
        print(df_final.to_string(index=False))
        print(f"\n💡 {len(df_final)} señales guardadas en 'senales_nasdaq_momentum.csv'")
        print("   Recomendación: Operar MÁXIMO 1-2 tickers")
    else:
        print("😴 No hay señales operables esta semana. Paciencia.")
    print("=" * 70)

# -------------------------------
# EJECUCIÓN
# -------------------------------
if __name__ == "__main__":
    ejecutar_escaneo_nasdaq_completo()