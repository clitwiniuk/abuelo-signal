"""
Modo demo con datos sintéticos realistas para cuando IBKR no está disponible
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import random

def generate_demo_data(symbol: str, timeframe: str = "5m", num_bars: int = 500) -> pd.DataFrame:
    """
    Generar datos de demo realistas basados en el símbolo y timeframe
    
    Args:
        symbol: Símbolo del stock
        timeframe: Timeframe ("1m", "5m", "15m", "1h", "1d")
        num_bars: Número de velas a generar
    
    Returns:
        DataFrame con datos OHLCV realistas
    """
    
    # Configuración base según símbolo
    symbol_configs = {
        "GME": {"base_price": 20.0, "volatility": 0.08, "trend": 0.001},
        "AMC": {"base_price": 4.5, "volatility": 0.06, "trend": 0.0005},
        "MARA": {"base_price": 15.0, "volatility": 0.07, "trend": 0.0008},
        "RIOT": {"base_price": 12.0, "volatility": 0.065, "trend": 0.0007},
        "PLTR": {"base_price": 18.0, "volatility": 0.055, "trend": 0.0006},
        "TSLA": {"base_price": 250.0, "volatility": 0.04, "trend": 0.0003},
        "AAPL": {"base_price": 180.0, "volatility": 0.025, "trend": 0.0002},
        "SPY": {"base_price": 450.0, "volatility": 0.015, "trend": 0.0001},
    }
    
    # Obtener configuración o usar defaults
    config = symbol_configs.get(symbol, {
        "base_price": 50.0,
        "volatility": 0.04,
        "trend": 0.0003
    })
    
    base_price = config["base_price"]
    volatility = config["volatility"]
    trend = config["trend"]
    
    # Ajustar volatilidad según timeframe
    timeframe_multipliers = {
        "1m": 1.0,
        "5m": 0.8,
        "15m": 0.6,
        "1h": 0.4,
        "1d": 0.2
    }
    volatility *= timeframe_multipliers.get(timeframe, 0.8)
    
    # Generar timestamps
    end_time = datetime.now()
    
    if timeframe == "1m":
        freq = "1min"
        start_time = end_time - timedelta(minutes=num_bars)
    elif timeframe == "5m":
        freq = "5min"
        start_time = end_time - timedelta(minutes=num_bars * 5)
    elif timeframe == "15m":
        freq = "15min"
        start_time = end_time - timedelta(minutes=num_bars * 15)
    elif timeframe == "1h":
        freq = "1H"
        start_time = end_time - timedelta(hours=num_bars)
    else:  # 1d
        freq = "1D"
        start_time = end_time - timedelta(days=num_bars)
    
    # Generar timestamps solo para horas de mercado (9:30 AM - 4:00 PM ET)
    timestamps = []
    current_time = start_time
    
    while len(timestamps) < num_bars and current_time < end_time:
        # Solo agregar si es hora de mercado y día de semana
        if (current_time.weekday() < 5 and 
            9 <= current_time.hour < 16 and 
            (current_time.hour > 9 or current_time.minute >= 30)):
            timestamps.append(current_time)
        
        # Avanzar según timeframe
        if timeframe == "1m":
            current_time += timedelta(minutes=1)
        elif timeframe == "5m":
            current_time += timedelta(minutes=5)
        elif timeframe == "15m":
            current_time += timedelta(minutes=15)
        elif timeframe == "1h":
            current_time += timedelta(hours=1)
        else:
            current_time += timedelta(days=1)
    
    # Generar precios con movimiento browniano geométrico
    np.random.seed(hash(symbol) % 2**32)  # Reproducible por símbolo
    
    returns = np.random.normal(trend, volatility, len(timestamps))
    
    # Agregar algunos patrones realistas
    if random.random() < 0.3:  # 30% de probabilidad de gap
        gap_pos = random.randint(len(returns) // 4, len(returns) // 2)
        returns[gap_pos] += random.choice([-0.05, 0.05])  # Gap up/down
    
    if random.random() < 0.2:  # 20% de probabilidad de tendencia fuerte
        trend_start = random.randint(len(returns) // 3, 2 * len(returns) // 3)
        trend_strength = random.uniform(0.002, 0.008)
        for i in range(trend_start, min(trend_start + 50, len(returns))):
            returns[i] += trend_strength * (1 if random.random() > 0.5 else -1)
    
    # Calcular precios
    prices = [base_price]
    for ret in returns:
        new_price = prices[-1] * (1 + ret)
        prices.append(max(new_price, base_price * 0.5))  # Evitar precios muy bajos
    
    # Generar OHLC realista
    data = []
    for i in range(len(timestamps)):
        timestamp = timestamps[i]
        open_price = prices[i]
        close_price = prices[i + 1]
        
        # High y Low realistas
        daily_range = abs(close_price - open_price)
        noise = np.random.normal(0, daily_range * 0.3)
        
        high = max(open_price, close_price) + abs(noise) + abs(np.random.normal(0, volatility * base_price * 0.5))
        low = min(open_price, close_price) - abs(noise) - abs(np.random.normal(0, volatility * base_price * 0.5))
        
        # Asegurar que high >= max(open, close) y low <= min(open, close)
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # Volumen realista
        base_volume = 1000000 if timeframe in ["1m", "5m"] else 500000
        volume_multiplier = 1 + abs(returns[i]) * 10  # Más volumen con más movimiento
        volume = int(base_volume * volume_multiplier * np.random.uniform(0.5, 2.0))
        
        data.append({
            'date': timestamp,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close_price, 2),
            'volume': volume
        })
    
    # Crear DataFrame
    df = pd.DataFrame(data)
    df.set_index('date', inplace=True)
    
    # Calcular indicadores
    df['vwap'] = calculate_vwap(df)
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    
    return df

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calcular VWAP"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def get_demo_data(symbol: str, timeframe: str = "5m") -> pd.DataFrame:
    """
    Obtener datos de demo para un símbolo y timeframe
    
    Args:
        symbol: Símbolo del stock
        timeframe: Timeframe deseado
    
    Returns:
        DataFrame con datos OHLCV de demo
    """
    st.info(f"🎭 Modo Demo: Generando datos realistas para {symbol}")
    
    # Generar datos
    df = generate_demo_data(symbol, timeframe)
    
    # Mostrar información del demo
    st.info(f"📊 Datos generados: {len(df)} velas | Precio actual: ${df['close'].iloc[-1]:.2f}")
    
    return df

def is_demo_mode() -> bool:
    """Verificar si estamos en modo demo"""
    return st.session_state.get('demo_mode', False)

def set_demo_mode(enabled: bool):
    """Establecer modo demo"""
    st.session_state.demo_mode = enabled
