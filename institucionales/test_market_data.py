from machine_learning.strategies.base_strategy import BaseStrategy

# Crear una instancia de la estrategia
strategy = BaseStrategy()

# Lista de tickers de prueba
tickers = ['AAPL', 'GOOGL', 'MSFT']

try:
    # Obtener datos del mercado
    market_data = strategy.get_market_data(tickers)
    
    # Imprimir resumen de los datos obtenidos
    print("\nResumen de datos obtenidos:")
    for ticker, df in market_data.items():
        print(f"\nDatos para {ticker}:")
        print(f"Período: {df.index[0]} a {df.index[-1]}")
        print(f"Número de registros: {len(df)}")
        print(f"Último precio de cierre: {df['Close'].iloc[-1]:.2f}")
        print(f"Último volumen: {df['Volume'].iloc[-1]:,}")
        
except Exception as e:
    print(f"Error al obtener datos: {str(e)}")
