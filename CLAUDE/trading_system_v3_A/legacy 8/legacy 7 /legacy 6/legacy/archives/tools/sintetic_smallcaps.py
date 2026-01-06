import numpy as np
import pandas as pd
import os

def generar_ohlcv_minuto_volatil(n_dias=20, start_price=10, filename='synthetic_data/minuto_smallcaps.csv'):
    np.random.seed(42)

    minutos_por_dia = 390
    n = n_dias * minutos_por_dia + 1

    # Generar diferentes regímenes de mercado más realistas para smallcaps
    sigma = 0.01  # Volatilidad base alta
    returns = np.zeros(n)
    
    # Definir períodos de diferentes tendencias
    periodo_minutos = n // 4  # Dividir en 4 períodos aproximados
    
    # Tipos de tendencia: 0=lateral, 1=alcista, 2=bajista
    # Distribución más realista: más laterales y bajistas que alcistas
    tipos_tendencia = np.random.choice([0, 1, 2], 4, p=[0.5, 0.2, 0.3])  # 50% lateral, 20% alcista, 30% bajista
    
    for i in range(4):
        inicio = i * periodo_minutos
        fin = min((i + 1) * periodo_minutos, n)
        periodo_len = fin - inicio
        
        if tipos_tendencia[i] == 0:  # Tendencia lateral
            mu = np.random.uniform(-0.00005, 0.00005)  # Drift muy pequeño
            sigma_periodo = sigma * np.random.uniform(0.7, 1.0)  # Volatilidad moderada
        elif tipos_tendencia[i] == 1:  # Tendencia alcista
            mu = np.random.uniform(0.0001, 0.0003)  # Drift positivo
            sigma_periodo = sigma * np.random.uniform(0.8, 1.2)
        else:  # Tendencia bajista
            mu = np.random.uniform(-0.0003, -0.0001)  # Drift negativo
            sigma_periodo = sigma * np.random.uniform(1.0, 1.5)  # Más volatilidad en bajadas
            
        returns[inicio:fin] = np.random.normal(mu, sigma_periodo, periodo_len)

    # Saltos extremos más realistas - menos frecuentes pero más impactantes
    n_saltos = max(1, n_dias // 2)  # Menos saltos por día
    saltos_idx = np.random.choice(len(returns), n_saltos, replace=False)
    # Saltos más extremos y asimétricos (más bajadas bruscas que subidas)
    saltos_valores = np.random.choice(
        [0.02, -0.04, 0.03, -0.06, 0.01, -0.05], 
        n_saltos, 
        p=[0.15, 0.25, 0.10, 0.30, 0.10, 0.10]  # Más probabilidad de caídas
    )
    returns[saltos_idx] += saltos_valores

    price = start_price * np.exp(np.cumsum(returns))

    días = pd.date_range(start='2023-01-02', periods=n_dias, freq='B', tz='Europe/Madrid')
    fechas = []
    for d in días:
        rango_dia = pd.date_range(
            start=d + pd.Timedelta(hours=15, minutes=30),
            periods=minutos_por_dia,
            freq='T',  # Minuto
            tz='Europe/Madrid'
        )
        fechas.extend(rango_dia)
    idx = pd.DatetimeIndex(fechas)

    open_ = price[:-1]
    close_ = price[1:]
    high_ = np.maximum(open_, close_) + np.random.uniform(0, 0.08, len(open_))
    low_ = np.minimum(open_, close_) - np.random.uniform(0, 0.08, len(open_))
    low_ = np.where(low_ < 0, 0, low_)

    vol_base = 1000
    vol_var = 7000  # Más sensibilidad a movimientos
    volume_ = (
        vol_base +
        vol_var * np.abs(close_ - open_) / start_price +
        np.random.randint(3000, 10000, len(open_)) * (np.abs(close_ - open_) > 0.10)
    ).astype(int)

    open_ = np.round(open_, 2)
    high_ = np.round(high_, 2)
    low_ = np.round(low_, 2)
    close_ = np.round(close_, 2)

    df = pd.DataFrame({
        'Open': open_,
        'High': high_,
        'Low': low_,
        'Close': close_,
        'Volume': volume_
    }, index=idx)

    parent_dir = os.path.dirname(filename)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    df.index.name = 'Date'
    df.to_csv(filename)
    return df, filename

# Ejemplo de uso:
df, archivo = generar_ohlcv_minuto_volatil(n_dias=10, start_price=5.25, filename='synthetic_data/smallcaps_1m_10dias.csv')
print(f'Datos generados: {len(df)} velas en {archivo}')
print(df.head())