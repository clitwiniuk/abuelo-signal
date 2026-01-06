import yfinance as yf
import pandas as pd
import numpy as np
from ib_insync import *
import requests
from datetime import datetime

class SmallCapScanner:
    def __init__(self):
        self.nasdaq_url = "https://old.nasdaq.com/screening/companies-by-name.aspx?letter=0&exchange=nasdaq&render=download"
        
    def get_nasdaq_list(self):
        """Carga el listado de acciones NASDAQ solo desde CSV local (más rápido y confiable)."""
        try:
            df = pd.read_csv("nasdaq_list.csv")
            df = df[df['Symbol'].str.len() <= 4]
            return df[['Symbol', 'Name', 'MarketCap', 'Sector']]
        except Exception as e:
            print(f"[ERROR] No se pudo cargar el archivo local 'nasdaq_list.csv': {e}")
            return pd.DataFrame(columns=['Symbol', 'Name', 'MarketCap', 'Sector'])

    def filter_small_caps(self, df):
        """Filtra por capitalización y liquidez"""
        # Convertir MarketCap a numérico (ej. "1.2B" → 1.2e9)
        df['MarketCap'] = df['MarketCap'].replace(r'[\$,]', '', regex=True).replace(
            {'B': '*1e9', 'M': '*1e6'}, regex=True).apply(pd.eval).astype(float)
            
        return df[
            (df['MarketCap'] >= 300e6) & 
            (df['MarketCap'] <= 2e9) &
            (df['Symbol'].str.len() <= 4)  # Evitar warrants (ej. 'AAPLW')
        ]

    def enhance_with_yfinance(self, symbols):
        """Añade datos técnicos desde Yahoo Finance"""
        data = []
        for symbol in symbols[:100]:  # Limitar para pruebas
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo")
                if len(hist) < 20: continue
                
                # Calcular métricas clave
                close = hist['Close'].iloc[-1]
                atr = self.calculate_atr(hist)
                volume_avg = hist['Volume'].rolling(20).mean().iloc[-1]
                
                data.append({
                    'Symbol': symbol,
                    'Price': close,
                    'ATR%': (atr / close) * 100,
                    'VolumeAvg': volume_avg,
                    'SMA50': hist['Close'].rolling(50).mean().iloc[-1],
                    'RSI': self.calculate_rsi(hist['Close'])
                })
            except Exception as e:
                print(f"Error en {symbol}: {str(e)}")
                continue
                
        return pd.DataFrame(data)

    def calculate_atr(self, df, period=14):
        """Calcula el Average True Range"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    def calculate_rsi(self, series, period=14):
        """Calcula el RSI"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs.iloc[-1]))

    def scan(self):
        """Escaneo avanzado solo con yfinance: filtra, normaliza y puntúa small caps."""
        print("Descargando listado NASDAQ...")
        nasdaq = self.get_nasdaq_list()
        
        print("Filtrando small caps...")
        small_caps = self.filter_small_caps(nasdaq)
        
        print("Analizando métricas técnicas...")
        # Limita a los primeros 10 tickers para pruebas rápidas
        enhanced = self.enhance_with_yfinance(small_caps['Symbol'].iloc[:10])
        
        # Unir sector y nombre para filtros avanzados
        enhanced = pd.merge(enhanced, small_caps[['Symbol', 'Sector', 'Name']], on='Symbol', how='left')
        
        # Filtros técnicos y sectoriales
        filtered = enhanced[
            (enhanced['VolumeAvg'] > 500e3) &
            (enhanced['Price'] >= 5) &
            (enhanced['Price'] <= 50) &
            (enhanced['ATR%'] > 2) &
            (enhanced['RSI'] < 70) &
            (enhanced['Sector'] != 'Biotechnology')  # Evita sectores riesgosos
        ].copy()
        if filtered.empty:
            print("[WARN] Ningún símbolo pasó los filtros técnicos y sectoriales.")
            return filtered
        
        # ---- Normalización de métricas ----
        filtered['norm_volume'] = (filtered['VolumeAvg'] - filtered['VolumeAvg'].min()) / (filtered['VolumeAvg'].max() - filtered['VolumeAvg'].min())
        filtered['norm_atr'] = (filtered['ATR%'] - filtered['ATR%'].min()) / (filtered['ATR%'].max() - filtered['ATR%'].min())
        filtered['norm_momentum'] = (filtered['Price'] / filtered['SMA50']) - 1
        filtered['norm_momentum'] = (filtered['norm_momentum'] - filtered['norm_momentum'].min()) / (filtered['norm_momentum'].max() - filtered['norm_momentum'].min())
        
        # ---- Score compuesto ----
        weights = {
            'liquidity': 0.4,    # Volumen
            'volatility': 0.2,   # ATR%
            'momentum': 0.2,     # Precio/SMA50
            'trend': 0.2         # RSI bajo = mejor
        }
        filtered['score'] = (
            weights['liquidity'] * filtered['norm_volume'] +
            weights['volatility'] * filtered['norm_atr'] +
            weights['momentum'] * filtered['norm_momentum'] +
            weights['trend'] * (1 - filtered['RSI']/100)
        ) * 100
        
        # Filtro final por score alto
        final = filtered[filtered['score'] >= 60].sort_values('score', ascending=False)
        print(f"[INFO] {len(final)} símbolos con score >= 60")
        return final.head(20)

# --- Uso ---
if __name__ == "__main__":
    scanner = SmallCapScanner()
    top_picks = scanner.scan()
    
    print("\nTop 20 Small Caps para operar:")
    print(top_picks[['Symbol', 'Price', 'ATR%', 'VolumeAvg', 'RSI']].to_string(index=False))
    
    # Exportar a CSV
    top_picks.to_csv("top_small_caps.csv", index=False)
    print("\n[INFO] Resultados exportados a top_small_caps.csv")