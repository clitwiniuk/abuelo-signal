import yfinance as yf
import pandas as pd
import time

# Lista de tickers de prueba
tickers = ['AAPL', 'GOOGL', 'MSFT']

# Obtener datos del mercado
print("\nObteniendo datos del mercado...")
for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period='60d', interval='5m')
        
        if not df.empty:
            print(f"\n✅ Datos obtenidos para {ticker}")
            print(f"Período: {df.index[0]} a {df.index[-1]}")
            print(f"Número de registros: {len(df)}")
            print(f"Último precio de cierre: {df['Close'].iloc[-1]:.2f}")
            print(f"Último volumen: {df['Volume'].iloc[-1]:,}")
        else:
            print(f"❌ No se obtuvieron datos para {ticker}")
            
        # Esperar un poco entre tickers
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Error obteniendo datos para {ticker}: {str(e)}")
        # Esperar 60 segundos antes de continuar
        time.sleep(60)
