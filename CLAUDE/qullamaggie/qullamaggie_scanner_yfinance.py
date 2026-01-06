"""
Stock Scanner basado en el método de Qullamaggie (Kristjan Kullamägi)
Conversión del código R original a Python
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
import warnings
warnings.filterwarnings('ignore')

def get_stock_data(tickers, days_back=400):
    """
    Descarga datos OHLC para una lista de tickers
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            if len(hist) > 0:
                data[ticker] = hist
            else:
                print(f"No se pudieron obtener datos para {ticker}")
        except Exception as e:
            print(f"Error descargando {ticker}: {e}")
    
    return data

def calculate_adr_20(ticker_data):
    """
    ADR20 - Average Daily Range para los últimos 20 días
    """
    if len(ticker_data) < 20:
        return np.nan
    
    highs = ticker_data['High']
    lows = ticker_data['Low']
    
    # Calcular el ratio high/low
    ratio_high_low = highs / lows
    
    # Calcular SMA de 20 períodos del ratio, convertir a ADR%
    adr_20 = 100 * (ratio_high_low.rolling(window=20).mean() - 1)
    
    return adr_20.iloc[-1] if not pd.isna(adr_20.iloc[-1]) else np.nan

def calculate_acf(ticker_data, window_size=252):
    """
    ACF - Autocorrelación de retornos
    """
    if len(ticker_data) < window_size:
        return np.nan
    
    # Calcular retornos logarítmicos diarios en precios ajustados
    adj_close = ticker_data['Close']  # yfinance ya da precios ajustados en 'Close'
    log_returns = np.log(adj_close / adj_close.shift(1)).dropna()
    
    if len(log_returns) < 2:
        return np.nan
    
    # Calcular autocorrelación
    try:
        from statsmodels.tsa.stattools import acf
        acf_result = acf(log_returns, nlags=min(window_size, len(log_returns)-1), fft=False)
        return acf_result[-1] if len(acf_result) > 0 else np.nan
    except:
        # Método alternativo si statsmodels no está disponible
        correlation = np.corrcoef(log_returns[:-1], log_returns[1:])[0, 1]
        return correlation if not np.isnan(correlation) else 0

def calculate_clenow_momentum(ticker_data):
    """
    Momentum de Clenow
    """
    if len(ticker_data) < 200:
        return np.nan
    
    # Precios de cierre ajustados
    adjusted_close = ticker_data['Close']
    
    # Logaritmo natural de los precios
    ln_price = np.log(adjusted_close)
    
    # Calcular pendiente de 100 días de los precios log
    def calculate_slope(x):
        if len(x) < 100:
            return np.nan
        days = np.arange(len(x))
        slope, _, _, _, _ = stats.linregress(days, x)
        return slope
    
    slope_100 = ln_price.rolling(window=100).apply(calculate_slope, raw=False)
    
    # Pendiente anualizada
    annualized_slope = (np.exp(slope_100) ** 250) - 1
    
    # R-cuadrado móvil sobre la pendiente anualizada
    def calculate_rsquared(x):
        if len(x) < 100 or x.isna().all():
            return np.nan
        days = np.arange(len(x))
        valid_data = ~np.isnan(x)
        if sum(valid_data) < 10:
            return np.nan
        try:
            _, _, r_value, _, _ = stats.linregress(days[valid_data], x[valid_data])
            return r_value ** 2
        except:
            return np.nan
    
    rolling_rsq = annualized_slope.rolling(window=100).apply(calculate_rsquared, raw=False)
    
    # Pendiente ajustada
    adjusted_slope = rolling_rsq * annualized_slope
    
    return adjusted_slope.iloc[-1] if not pd.isna(adjusted_slope.iloc[-1]) else np.nan

def calculate_dollar_volume(ticker_data):
    """
    Volumen en dólares (Volumen * Precio)
    """
    last_volume = ticker_data['Volume'].iloc[-1]
    last_price = ticker_data['Close'].iloc[-1]
    return last_volume * last_price

def get_float_metrics(ticker):
    """
    Obtiene métricas del float y capitalización
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        float_shares = info.get('floatShares', np.nan)
        shares_outstanding = info.get('sharesOutstanding', np.nan)
        market_cap = info.get('marketCap', np.nan)
        
        # Si no hay floatShares, usar sharesOutstanding como aproximación
        if pd.isna(float_shares) and not pd.isna(shares_outstanding):
            float_shares = shares_outstanding
        
        # Calcular ratio float/outstanding
        float_ratio = np.nan
        if not pd.isna(float_shares) and not pd.isna(shares_outstanding) and shares_outstanding > 0:
            float_ratio = float_shares / shares_outstanding
        
        return {
            'float_shares': float_shares / 1e6 if not pd.isna(float_shares) else np.nan,  # En millones
            'shares_outstanding': shares_outstanding / 1e6 if not pd.isna(shares_outstanding) else np.nan,  # En millones
            'float_ratio': float_ratio,
            'market_cap': market_cap / 1e9 if not pd.isna(market_cap) else np.nan  # En billones
        }
    except Exception as e:
        print(f"Error obteniendo float para {ticker}: {e}")
        return {
            'float_shares': np.nan,
            'shares_outstanding': np.nan,
            'float_ratio': np.nan,
            'market_cap': np.nan
        }

def get_last_price(ticker_data):
    """
    Último precio
    """
    return ticker_data['Close'].iloc[-1]

def calculate_return_period(ticker_data, days):
    """
    Calcula retorno para un período específico (desde el mínimo del período)
    """
    if len(ticker_data) < days:
        return np.nan
    
    end_price = ticker_data['Close'].iloc[-1]
    period_prices = ticker_data['Close'].tail(days)
    min_price = period_prices.min()
    
    return (end_price / min_price) - 1

def run_qullamaggie_scanner(tickers, min_price=5.0, max_price=500.0, 
                           min_float=10, max_float=200, max_float_ratio=0.95):
    """
    Ejecuta el escáner completo de Qullamaggie
    
    Parámetros:
    - min_price: Precio mínimo por acción (default: $5)
    - max_price: Precio máximo por acción (default: $500)
    - min_float: Float mínimo en millones (default: 10M)
    - max_float: Float máximo en millones (default: 200M)
    - max_float_ratio: Ratio máximo float/outstanding (default: 0.95)
    """
    print("Descargando datos de precios...")
    stock_data = get_stock_data(tickers)
    
    if not stock_data:
        print("No se pudieron obtener datos para ningún ticker")
        return pd.DataFrame()
    
    print("Calculando métricas técnicas...")
    results = []
    
    for ticker, data in stock_data.items():
        try:
            print(f"Procesando {ticker}...")
            
            # Métricas técnicas
            tech_metrics = {
                'ticker': ticker,
                'ADR_20': calculate_adr_20(data),
                'ACF_252': calculate_acf(data, 252),
                'clenow': calculate_clenow_momentum(data),
                'dollarVolume': calculate_dollar_volume(data) / 1e6,  # En millones
                'priceLast': get_last_price(data),
                'return1M': calculate_return_period(data, 22),   # ~1 mes
                'return3M': calculate_return_period(data, 67),   # ~3 meses
                'return6M': calculate_return_period(data, 126),  # ~6 meses
            }
            
            # Métricas del float
            float_metrics = get_float_metrics(ticker)
            
            # Combinar todas las métricas
            result = {**tech_metrics, **float_metrics}
            results.append(result)
            
        except Exception as e:
            print(f"Error procesando {ticker}: {e}")
    
    # Crear DataFrame
    df = pd.DataFrame(results)
    
    if df.empty:
        print("No se generaron resultados")
        return df
    
    print("\nResultados completos:")
    print(df.round(4))
    
    # Aplicar filtros de Qullamaggie
    print("\n" + "="*50)
    print("APLICANDO FILTROS DE QULLAMAGGIE")
    print("="*50)
    
    print(f"Filtros aplicados:")
    print(f"- Precio: ${min_price} - ${max_price}")
    print(f"- Float: {min_float}M - {max_float}M acciones")
    print(f"- Float Ratio: < {max_float_ratio}")
    print(f"- Volumen: > $5M")
    print(f"- ADR20: > 5%")
    print(f"- Performance: Top 10% en 1M, 3M o 6M")
    
    # Calcular percentiles del 90% para retornos
    top_decile_1M = df['return1M'].quantile(0.9)
    top_decile_3M = df['return3M'].quantile(0.9)
    top_decile_6M = df['return6M'].quantile(0.9)
    
    print(f"\nPercentiles 90% (Top Decile):")
    print(f"- 1M: {top_decile_1M:.2%}")
    print(f"- 3M: {top_decile_3M:.2%}")
    print(f"- 6M: {top_decile_6M:.2%}")
    
    # Aplicar todos los filtros
    qullamaggie_scan = df[
        # Filtros de precio
        (df['priceLast'] >= min_price) &
        (df['priceLast'] <= max_price) &
        
        # Filtros de float
        (df['float_shares'] >= min_float) &
        (df['float_shares'] <= max_float) &
        (df['float_ratio'] <= max_float_ratio) &
        
        # Filtros técnicos originales
        (df['dollarVolume'] > 5) &  # Más de 5 millones en volumen
        (df['ADR_20'] > 5) &       # Más de 5% ADR20
        
        # Filtros de performance (top decile en al menos uno)
        (
            (df['return1M'] >= top_decile_1M) |
            (df['return3M'] >= top_decile_3M) |
            (df['return6M'] >= top_decile_6M)
        )
    ].copy()
    
    # Ordenar por performance combinada
    if not qullamaggie_scan.empty:
        qullamaggie_scan['combined_score'] = (
            qullamaggie_scan['return1M'].fillna(0) * 0.4 +
            qullamaggie_scan['return3M'].fillna(0) * 0.4 +
            qullamaggie_scan['return6M'].fillna(0) * 0.2
        )
        qullamaggie_scan = qullamaggie_scan.sort_values('combined_score', ascending=False)
    
    print(f"\n" + "="*50)
    print(f"RESULTADOS FINALES: {len(qullamaggie_scan)} acciones encontradas")
    print("="*50)
    
    if not qullamaggie_scan.empty:
        # Mostrar resultados con formato mejorado
        display_cols = ['ticker', 'priceLast', 'float_shares', 'dollarVolume', 
                       'ADR_20', 'return1M', 'return3M', 'return6M', 'combined_score']
        
        display_df = qullamaggie_scan[display_cols].copy()
        
        # Formatear columnas para mejor visualización
        display_df['priceLast'] = display_df['priceLast'].apply(lambda x: f"${x:.2f}")
        display_df['float_shares'] = display_df['float_shares'].apply(lambda x: f"{x:.1f}M" if not pd.isna(x) else "N/A")
        display_df['dollarVolume'] = display_df['dollarVolume'].apply(lambda x: f"${x:.1f}M")
        display_df['ADR_20'] = display_df['ADR_20'].apply(lambda x: f"{x:.1f}%" if not pd.isna(x) else "N/A")
        display_df['return1M'] = display_df['return1M'].apply(lambda x: f"{x:.1%}" if not pd.isna(x) else "N/A")
        display_df['return3M'] = display_df['return3M'].apply(lambda x: f"{x:.1%}" if not pd.isna(x) else "N/A")
        display_df['return6M'] = display_df['return6M'].apply(lambda x: f"{x:.1%}" if not pd.isna(x) else "N/A")
        display_df['combined_score'] = display_df['combined_score'].apply(lambda x: f"{x:.1%}")
        
        print(display_df.to_string(index=False))
    else:
        print("❌ No se encontraron acciones que cumplan todos los criterios")
        
        # Mostrar estadísticas de filtros para debugging
        print("\n📊 Análisis de filtros:")
        print(f"- Acciones con precio ${min_price}-${max_price}: {len(df[(df['priceLast'] >= min_price) & (df['priceLast'] <= max_price)])}")
        print(f"- Acciones con float {min_float}-{max_float}M: {len(df[(df['float_shares'] >= min_float) & (df['float_shares'] <= max_float)])}")
        print(f"- Acciones con volumen >$5M: {len(df[df['dollarVolume'] > 5])}")
        print(f"- Acciones con ADR20 >5%: {len(df[df['ADR_20'] > 5])}")
        print(f"- Acciones top decile performance: {len(df[(df['return1M'] >= top_decile_1M) | (df['return3M'] >= top_decile_3M) | (df['return6M'] >= top_decile_6M)])}")
    
    return qullamaggie_scan

# Ejemplo de uso
if __name__ == "__main__":
    # Lista de tickers de ejemplo (más amplia para mejores resultados)
    tickers = [
        # Tech
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "TSLA",
        # Growth
        "SHOP", "SQ", "PYPL", "ROKU", "ZOOM", "DOCU", "SNOW", "PLTR",
        # Biotech
        "GILD", "MRNA", "BNTX", "REGN", "VRTX", "BIIB",
        # Other
        "NFLX", "DIS", "NKE", "ADBE", "CRM", "UBER", "LYFT", "TWLO"
    ]
    
    # Para usar tickers desde archivo CSV:
    # tickers_df = pd.read_csv("weeklyTickers.csv")
    # tickers = tickers_df['ticker'].tolist()  # Ajustar nombre de columna según CSV
    
    print("🚀 INICIANDO ESCÁNER QULLAMAGGIE")
    print("="*50)
    
    # Ejecutar escáner con filtros personalizables
    results = run_qullamaggie_scanner(
        tickers=tickers,
        min_price=10.0,      # Mínimo $10 (evita penny stocks)
        max_price=300.0,     # Máximo $300 (evita acciones muy caras)
        min_float=15,        # Mínimo 15M acciones float
        max_float=150,       # Máximo 150M acciones float
        max_float_ratio=0.90 # Máximo 90% float ratio (indica insider ownership)
    )
    
    # Guardar resultados si hay datos
    if not results.empty:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qullamaggie_scan_{timestamp}.csv"
        results.to_csv(filename, index=False)
        print(f"\n💾 Resultados guardados en: {filename}")
    
    print("\n✅ Escáner completado!")
