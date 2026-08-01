# =================================================================
# SISTEMA COMPLETO: Universo NASDAQ Automático + IBKR + Python
# Momentum Burst Scanner | Cuenta $1,000 | Riesgo 2%
# Estilo: Qullamaggie & Stockbee
# SIN ProRealTime | SIN Watchlist Manual Pequeña
# =================================================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import os
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

# Parámetros de Momentum Burst (Qullamaggie / Stockbee)
MIN_PRICE = 5
MAX_PRICE = 100
MIN_AVG_VOLUME = 100000
MIN_EXPANSION = 0.04  # 4% mínimo
MAX_BURST = 0.12      # Máximo 12% (no perseguir)
MIN_STOP_PCT = 2.0
MAX_STOP_PCT = 4.0
EMA_FAST = 10
EMA_SLOW = 20
CONSOLIDATION_DAYS = 5

# Archivo de caché para el universo (para no descargar siempre)
CACHE_FILE = 'nasdaq_universe_cache.csv'

# -------------------------------
# FUNCIÓN 1: Obtener Universo NASDAQ (SISTEMA DE 3 CAPAS)
# -------------------------------
def obtener_universo_nasdaq():
    """
    Obtiene el universo NASDAQ usando 3 capas de fallback.
    Prioridad: 1. API Externa -> 2. Caché Local -> 3. Lista Expandida
    """
    print("\n📡 Obteniendo universo NASDAQ...")
    
    # CAPA 1: Intentar descargar de fuente externa (Financial Modeling Prep)
    # Es más estable que la API directa de NASDAQ
    try:
        # Nota: Si tienes una API Key de FMP, ponla aquí. Si no, intenta sin key (limitado)
        api_key = ""  # Opcional: obtener gratis en financialmodelingprep.com
        url = f"https://financialmodelingprep.com/api/v3/stock/list?apikey={api_key}" if api_key else "https://financialmodelingprep.com/api/v3/stock/list"
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            tickers = [
                item['symbol'] for item in data 
                if item.get('exchange') == 'NASDAQ' and 
                item.get('type') == 'stock' and
                len(item['symbol']) <= 5
            ]
            if len(tickers) > 500:
                print(f"✅ {len(tickers)} tickers NASDAQ obtenidos desde API externa")
                _guardar_cache(tickers)
                return tickers
    except Exception as e:
        print(f"⚠️ API externa no disponible: {e}")
    
    # CAPA 2: Cargar desde caché local (si existe)
    if os.path.exists(CACHE_FILE):
        try:
            df = pd.read_csv(CACHE_FILE)
            tickers = df['Ticker'].tolist()
            print(f"✅ {len(tickers)} tickers cargados desde caché local ({CACHE_FILE})")
            return tickers
        except:
            print("⚠️ Error leyendo caché local")
    
    # CAPA 3: Lista expandida de respaldo (~300 tickers líquidos)
    print("⚠️ Usando lista expandida de tickers líquidos (Fallback)")
    tickers = _get_lista_expandida()
    _guardar_cache(tickers)
    return tickers

def _guardar_cache(tickers):
    """Guarda la lista de tickers en CSV local"""
    try:
        pd.DataFrame(tickers, columns=['Ticker']).to_csv(CACHE_FILE, index=False)
    except:
        pass

def _get_lista_expandida():
    """Lista curada expandida de ~300 tickers líquidos del NASDAQ"""
    return [
        # === MEGA CAP TECH ===
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA',
        'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM', 'ACN', 'IBM', 'INTC',
        'AMD', 'QCOM', 'TXN', 'AMAT', 'LRCX', 'KLAC', 'MU', 'MRVL',
        'ADI', 'MCHP', 'NXPI', 'ON', 'MPWR', 'SWKS', 'QRVO', 'ENTG',
        
        # === SOFTWARE / CLOUD ===
        'NOW', 'INTU', 'WDAY', 'PANW', 'CRWD', 'ZS', 'DDOG', 'NET',
        'SNOW', 'PLTR', 'MDB', 'TEAM', 'HUBS', 'ZM', 'DOCU', 'VEEV',
        'ANET', 'FTNT', 'CHKP', 'S', 'PATH', 'UI', 'ESTC', 'CFLT',
        
        # === INTERNET / E-COMMERCE ===
        'NFLX', 'BKNG', 'ABNB', 'EBAY', 'ETSY', 'MELI', 'SE', 'CPNG',
        'DASH', 'UBER', 'LYFT', 'RBLX', 'U', 'HOOD', 'COIN', 'SOFI',
        'AFRM', 'UPST', 'LC', 'NU', 'PAGS', 'STNE', 'WISH', 'CLOV',
        
        # === BIOTECH / PHARMA ===
        'GILD', 'AMGN', 'VRTX', 'REGN', 'BIIB', 'MRNA', 'BNTX', 'ILMN',
        'ALXN', 'BMRN', 'INCY', 'TECH', 'SGEN', 'NBIX', 'ALNY', 'IONS',
        'RGEN', 'EXAS', 'NVTA', 'PACB', 'TWST', 'CDNA', 'FATE', 'BLUE',
        
        # === CONSUMER / RETAIL ===
        'COST', 'PEP', 'MDLZ', 'KHC', 'MNST', 'KDP', 'WBA', 'DLTR',
        'ROST', 'LULU', 'SBUX', 'CMG', 'DPZ', 'YUM', 'QSR', 'WING',
        'ULTA', 'ORLY', 'AZO', 'AAP', 'TSCO', 'CHWY', 'PETQ', 'WOOF',
        
        # === INDUSTRIALS / OTROS ===
        'HON', 'UNP', 'CAT', 'DE', 'MMM', 'GE', 'BA', 'LMT', 'RTX',
        'NOC', 'GD', 'LHX', 'TDG', 'CTAS', 'FAST', 'VRSK', 'EXPD',
        
        # === MOMENTUM / GROWTH (2024-2025) ===
        'SMCI', 'ARM', 'RDDT', 'IONQ', 'RGTI', 'RBRK', 'APP', 'DT',
        'FROG', 'AI', 'C3AI', 'SOUN', 'BBAI', 'BARK', 'FUBO', 'DKNG',
        'PENN', 'RSI', 'GENI', 'FLUT', 'BALY', 'MGM', 'LVS', 'WYNN',
        
        # === ETFs PRINCIPALES ===
        'QQQ', 'QQQM', 'SPY', 'IWM', 'DIA', 'VTI', 'VOO', 'VEA',
        'VWO', 'TLT', 'IEF', 'SHY', 'GLD', 'SLV', 'USO', 'UNG',
        'SOXL', 'SOXS', 'TQQQ', 'SQQQ', 'UPRO', 'SPXU', 'FNGU', 'FNGD',
    ]

# -------------------------------
# FUNCIÓN 2: Pre-filtrado rápido
# -------------------------------
def pre_filtrar_tickers(tickers):
    """Filtra tickers por criterios básicos antes de consultar IBKR"""
    print(f"\n🔍 Pre-filtrando {len(tickers)} tickers...")
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
        print("   Asegúrate de tener TWS o IB Gateway abierto y API habilitada.")
        return None

# -------------------------------
# FUNCIÓN 4: Obtener datos y validar ticker
# -------------------------------
def validar_ticker_rapido(ib, ticker):
    """Obtiene datos y valida criterios básicos de liquidez y precio"""
    try:
        from ib_insync import Stock
        contract = Stock(ticker, 'SMART', 'USD')
        
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
# FUNCIÓN 6: Detectar Momentum Burst (Qullamaggie / Stockbee)
# -------------------------------
def detectar_burst(df):
    """
    Aplica criterios estrictos de Momentum Burst:
    1. Tendencia alcista (EMA stack)
    2. Range Expansion (4%+)
    3. Volumen expansivo
    4. Día previo estrecho (NR)
    5. Cierre fuerte
    6. No perseguir (no 3+ días subiendo)
    """
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
    
    # 5. Día previo estrecho (consolidación antes del burst)
    señales['previo_estrecho'] = ayer['range'] < (hoy['range_avg5'] * 0.8)
    
    # 6. Cierre fuerte (tercio superior del rango)
    rango_hoy = hoy['high'] - hoy['low']
    señales['cierre_fuerte'] = hoy['close'] >= (hoy['low'] + (rango_hoy * 0.66))
    
    # 7. No exagerado (<12%)
    señales['no_exagerado'] = hoy['expansion'] < MAX_BURST
    
    criterios_cumplidos = sum(señales.values())
    señales['total'] = criterios_cumplidos
    señales['es_burst'] = criterios_cumplidos >= 5  # Mínimo 5 de 7 criterios
    
    return señales['es_burst'], señales

# -------------------------------
# FUNCIÓN 7: Calcular Gestión de Riesgo
# -------------------------------
def calcular_gestion_riesgo(df):
    """Calcula stop, targets, posición"""
    hoy = df.iloc[-1]
    
    # Stop: mínimo del día o EMA10 (lo que esté más cerca)
    stop_level = min(hoy['low'], hoy['ema10'])
    stop_dolar = hoy['close'] - stop_level
    stop_pct = (stop_dolar / hoy['close']) * 100
    
    # Validar stop entre 2-4%
    if not (MIN_STOP_PCT <= stop_pct <= MAX_STOP_PCT):
        return None
    
    # Tamaño de posición (riesgo fijo $20)
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