import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import streamlit as st
import time
from functools import wraps

# Importar conexión IBKR
try:
    from utils.ibkr_connection import get_stock_data_ibkr, initialize_ibkr, IBKR_AVAILABLE
    IBKR_INITIALIZED = False
except ImportError:
    IBKR_AVAILABLE = False
    IBKR_INITIALIZED = False

# Importar modo demo
try:
    from utils.demo_data import get_demo_data, is_demo_mode, set_demo_mode
    DEMO_AVAILABLE = True
except ImportError:
    DEMO_AVAILABLE = False

# Cache extendido para datos de mercado (30 minutos)
@st.cache_data(ttl=1800)
def get_stock_data(symbol, period="1d", interval="1m", max_retries=3, use_ibkr=True, use_demo=False):
    """
    Obtener datos históricos con múltiples fuentes: IBKR > Demo > Yahoo Finance
    
    Args:
        symbol: Símbolo de la acción (ej: AAPL)
        period: Período de datos (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Intervalo de velas (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        max_retries: Número máximo de reintentos
        use_ibkr: Usar IBKR como fuente principal
        use_demo: Forzar modo demo
    
    Returns:
        DataFrame con datos OHLCV
    """
    global IBKR_INITIALIZED
    
    # Modo demo forzado
    if use_demo or (DEMO_AVAILABLE and is_demo_mode()):
        return get_demo_data(symbol, interval)
    
    # Inicializar IBKR si no está hecho
    if use_ibkr and IBKR_AVAILABLE and not IBKR_INITIALIZED:
        IBKR_INITIALIZED = initialize_ibkr()
    
    # Intentar IBKR primero si está disponible
    if use_ibkr and IBKR_AVAILABLE and IBKR_INITIALIZED:
        try:
            df = get_stock_data_ibkr(symbol, interval)
            if df is not None and not df.empty:
                st.success(f"✅ Datos de {symbol} obtenidos via IBKR")
                return df
        except Exception as e:
            st.warning(f"⚠️ Error con IBKR para {symbol}: {str(e)}")
    
    # Fallback a modo demo si está disponible
    if DEMO_AVAILABLE:
        try:
            st.info("🎭 Usando modo demo (datos sintéticos realistas)")
            return get_demo_data(symbol, interval)
        except Exception as e:
            st.warning(f"⚠️ Error con modo demo: {str(e)}")
    
    # Último fallback: Yahoo Finance con rate limiting mejorado
    st.info(f"📊 Obteniendo datos de {symbol} via Yahoo Finance...")
    
    for attempt in range(max_retries):
        try:
            # Espera exponencial entre reintentos
            if attempt > 0:
                wait_time = min(2 ** attempt, 10)  # Máximo 10 segundos
                st.info(f"⏳ Intento {attempt + 1}/{max_retries} en {wait_time}s...")
                time.sleep(wait_time)
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, timeout=10)
            
            if df.empty:
                if attempt == max_retries - 1:
                    st.warning(f"No se encontraron datos para {symbol}")
                continue
            
            # Renombrar columnas
            df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
            # Calcular VWAP si es intradía
            if interval in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h']:
                df['vwap'] = calculate_vwap(df)
            
            # Calcular volumen promedio
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            
            st.success(f"✅ Datos de {symbol} obtenidos via Yahoo Finance")
            return df
        
        except Exception as e:
            error_msg = str(e).lower()
            
            # Si es rate limiting, esperar más tiempo
            if "rate limit" in error_msg or "too many requests" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = min(30 * (attempt + 1), 60)  # 30, 60 segundos
                    st.warning(f"🚦 Rate limit detectado. Esperando {wait_time} segundos...")
                    time.sleep(wait_time)
                    continue
            
            # Último intento - mostrar error
            if attempt == max_retries - 1:
                st.error(f"❌ Error al obtener datos de {symbol}: {str(e)}")
                
                # Último recurso: modo demo de emergencia
                if DEMO_AVAILABLE:
                    st.info("🆘 Usando modo demo de emergencia")
                    return get_demo_data(symbol, interval)
                
                return None
    
    return None

def calculate_vwap(df):
    """Calcular Volume Weighted Average Price (VWAP)"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def get_small_cap_scanner(min_market_cap=50, max_market_cap=300, min_volume=100000):
    """
    Obtener lista de small caps con alto volumen
    
    Args:
        min_market_cap: Market cap mínimo en millones
        max_market_cap: Market cap máximo en millones
        min_volume: Volumen mínimo promedio
    
    Returns:
        DataFrame con small caps filtrados
    """
    # Lista de small caps populares para trading
    small_caps = [
        'MARA', 'RIOT', 'SOFI', 'PLTR', 'NIO', 'LCID', 'FCEL', 'AMC', 'GME',
        'BBBY', 'BB', 'TLRY', 'ACB', 'CGC', 'SNDL', 'NOK', 'CLOV', 'WISH',
        'CLNE', 'WKHS', 'SPCE', 'ASTS', 'RKLB', 'ASTR', 'SATL', 'SIDU',
        'LUNR', 'VORB', 'RDW', 'MYNA', 'BKSY', 'LLAP', 'SPIR', 'MNTS'
    ]
    
    results = []
    
    for symbol in small_caps[:15]:  # Limitar para no sobrecargar
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            market_cap = info.get('marketCap', 0) / 1e6  # Convertir a millones
            volume = info.get('averageVolume', 0)
            
            if min_market_cap <= market_cap <= max_market_cap and volume >= min_volume:
                results.append({
                    'symbol': symbol,
                    'name': info.get('shortName', 'N/A'),
                    'market_cap': market_cap,
                    'volume': volume,
                    'price': info.get('currentPrice', info.get('previousClose', 0)),
                    'change_pct': info.get('regularMarketChangePercent', 0)
                })
        
        except Exception:
            continue
    
    return pd.DataFrame(results)

def get_gappers(min_gap=5):
    """
    Obtener acciones con gap significativo en la apertura
    
    Args:
        min_gap: Gap mínimo en porcentaje
    
    Returns:
        DataFrame con acciones que hicieron gap
    """
    # Simulación de gappers para demo
    # En producción, esto consultaría datos pre-market reales
    
    symbols = ['MARA', 'RIOT', 'SOFI', 'PLTR', 'NIO', 'AMC', 'GME', 'TLRY']
    gappers = []
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_open = hist['Open'].iloc[-1]
                gap_pct = ((curr_open - prev_close) / prev_close) * 100
                
                if abs(gap_pct) >= min_gap:
                    gappers.append({
                        'symbol': symbol,
                        'gap_pct': gap_pct,
                        'prev_close': prev_close,
                        'curr_open': curr_open,
                        'volume': hist['Volume'].iloc[-1]
                    })
        
        except Exception:
            continue
    
    return pd.DataFrame(gappers)

def simulate_price_movement(symbol, current_price, volatility=0.002):
    """
    Simular movimiento de precio para modo replay/práctica
    
    Args:
        symbol: Símbolo de la acción
        current_price: Precio actual
        volatility: Volatilidad para simulación
    
    Returns:
        Nuevo precio simulado
    """
    # Movimiento aleatorio basado en volatilidad
    change = np.random.normal(0, volatility)
    new_price = current_price * (1 + change)
    return round(new_price, 2)

def calculate_support_resistance(df, window=20):
    """
    Calcular niveles de soporte y resistencia
    
    Args:
        df: DataFrame con datos OHLC
        window: Ventana para cálculo
    
    Returns:
        Dict con niveles de soporte y resistencia
    """
    if df.empty or len(df) < window:
        return {'support': [], 'resistance': []}
    
    # Niveles basados en mínimos y máximos locales
    highs = df['high'].rolling(window=window, center=True).max()
    lows = df['low'].rolling(window=window, center=True).min()
    
    # Encontrar pivots
    resistance_levels = df[df['high'] == highs]['high'].unique()[-3:]
    support_levels = df[df['low'] == lows]['low'].unique()[:3]
    
    return {
        'support': sorted(support_levels),
        'resistance': sorted(resistance_levels, reverse=True)
    }

def get_stock_fundamentals(symbol):
    """
    Obtener información fundamental de una acción
    
    Args:
        symbol: Símbolo de la acción
    
    Returns:
        Dict con información fundamental
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            'symbol': symbol,
            'name': info.get('shortName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'market_cap': info.get('marketCap', 0),
            'float': info.get('floatShares', 0),
            'short_ratio': info.get('shortRatio', 0),
            'avg_volume': info.get('averageVolume', 0),
            'beta': info.get('beta', 0),
            'eps': info.get('trailingEps', 0),
            'pe_ratio': info.get('trailingPE', 0),
            'price': info.get('currentPrice', info.get('previousClose', 0))
        }
    
    except Exception as e:
        return {'error': str(e)}

def is_market_open():
    """Verificar si el mercado está abierto (horario NY)"""
    from datetime import datetime
    import pytz
    
    ny_time = datetime.now(pytz.timezone('US/Eastern'))
    
    # Verificar si es día de semana
    if ny_time.weekday() >= 5:  # Sábado o domingo
        return False
    
    # Horario de mercado: 9:30 AM - 4:00 PM ET
    market_open = ny_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = ny_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= ny_time <= market_close

def get_market_time_remaining():
    """Obtener tiempo restante hasta cierre de mercado"""
    from datetime import datetime
    import pytz
    
    ny_time = datetime.now(pytz.timezone('US/Eastern'))
    market_close = ny_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if ny_time > market_close:
        return "Mercado cerrado"
    
    remaining = market_close - ny_time
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{hours}h {minutes}m hasta cierre"

def format_large_number(num):
    """Formatear números grandes (millones, billones)"""
    if num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    elif num >= 1e3:
        return f"${num/1e3:.2f}K"
    else:
        return f"${num:.2f}"

def serie_sintetica(data, n_candlesticks=5, n_bloques=6):
    """
    Generar una serie sintética de precios a partir de datos históricos.
    Utiliza un proceso que combina el cálculo de retornos porcentuales, 
    la mezcla aleatoria en bloques y la reconstrucción acumulativa de precios.
    
    Args:
        data: DataFrame con columnas Open, High, Low, Close y Volume
        n_candlesticks: Número de candlesticks por subbloque (por defecto 5)
        n_bloques: Número de subbloques por bloque (por defecto 6)
    
    Returns:
        DataFrame con la serie sintética reconstruida
    """
    if data is None or len(data) < n_candlesticks * n_bloques:
        return None
    
    df = data.copy()
    
    # 1. Recorte Inicial de la Serie - Mantener estacionalidad semanal
    if n_candlesticks == 5:  # Subbloques semanales
        # Buscar primer lunes en los datos
        for i in range(len(df)):
            if df.index[i].day_name() == 'Monday':
                df = df.iloc[i:]
                break
    
    # Asegurarse de tener suficientes datos
    if len(df) < n_candlesticks * n_bloques:
        return df.copy()  # Retornar original si no hay suficientes datos
    
    # 2. Cálculo de Retornos Porcentuales
    df_returns = df.copy()
    for col in ['open', 'high', 'low', 'close']:
        df_returns[col] = df[col].pct_change()
    
    # Eliminar primera fila (no tiene retorno)
    df_returns = df_returns.iloc[1:]
    df_returns['volume'] = df['volume'].iloc[1:]  # Mantener volume sin transformar
    
    # 3. Mezcla de Bloques
    total_candles = len(df_returns)
    block_size = n_bloques * n_candlesticks
    
    # Dividir en bloques
    n_full_blocks = total_candles // block_size
    remainder = total_candles % block_size
    
    blocks = []
    for i in range(n_full_blocks):
        start_idx = i * block_size
        end_idx = start_idx + block_size
        block = df_returns.iloc[start_idx:end_idx]
        
        # Subdividir en subbloques y mezclar
        subblocks = []
        for j in range(0, block_size, n_candlesticks):
            subblock = block.iloc[j:j+n_candlesticks]
            subblocks.append(subblock)
        
        # Mezclar subbloques aleatoriamente
        random.shuffle(subblocks)
        mixed_block = pd.concat(subblocks, ignore_index=True)
        blocks.append(mixed_block)
    
    # Agregar resto si existe
    if remainder > 0:
        blocks.append(df_returns.iloc[n_full_blocks * block_size:])
    
    # Concatenar bloques mezclados
    mixed_returns = pd.concat(blocks, ignore_index=True)
    
    # 4. Reconstrucción de la Serie de Precios
    # Extraer arrays de retornos
    open_returns = mixed_returns['open'].values
    high_returns = mixed_returns['high'].values
    low_returns = mixed_returns['low'].values
    close_returns = mixed_returns['close'].values
    volume_data = mixed_returns['volume'].values
    
    # Precio inicial (primer Close original)
    initial_close = df['close'].iloc[0]
    
    # Calcular factor acumulativo
    cumulative_factor = np.cumprod(1 + close_returns)
    
    # Reconstruir precios
    new_open = np.zeros(len(open_returns) + 1)
    new_high = np.zeros(len(high_returns) + 1)
    new_low = np.zeros(len(low_returns) + 1)
    new_close = np.zeros(len(close_returns) + 1)
    new_volume = np.zeros(len(volume_data) + 1)
    
    # 5. Inclusión de la Vela Inicial
    new_open[0] = df['open'].iloc[0]
    new_high[0] = df['high'].iloc[0]
    new_low[0] = df['low'].iloc[0]
    new_close[0] = initial_close
    new_volume[0] = df['volume'].iloc[0]
    
    # Reconstruir velas restantes
    for i in range(len(close_returns)):
        factor = cumulative_factor[i]
        new_open[i+1] = initial_close * factor * (1 + open_returns[i])
        new_high[i+1] = initial_close * factor * (1 + high_returns[i])
        new_low[i+1] = initial_close * factor * (1 + low_returns[i])
        new_close[i+1] = initial_close * factor * (1 + close_returns[i])
        new_volume[i+1] = volume_data[i]
    
    # 6. Crear DataFrame resultante
    result_df = pd.DataFrame({
        'open': new_open,
        'high': new_high,
        'low': new_low,
        'close': new_close,
        'volume': new_volume
    })
    
    # Asignar índice temporal (preservar referencia temporal)
    try:
        # Crear índice temporal basado en el original
        start_time = df.index[0]
        time_delta = df.index[1] - df.index[0] if len(df) > 1 else pd.Timedelta(minutes=1)
        new_index = [start_time + i * time_delta for i in range(len(result_df))]
        result_df.index = new_index
    except:
        # Si falla, usar índice numérico
        result_df.index = range(len(result_df))
    
    return result_df