import pandas as pd
import numpy as np
from tqdm import tqdm
import sqlite3
from datetime import datetime, timedelta

class Backtester:
    def __init__(self):
        self.historical_data = {}
        self.results = []
    
    def load_historical_data(self, tickers, start_date, end_date):
        """Carga datos históricos desde tu base de datos o archivos"""
        print("Cargando datos históricos...")
        conn = sqlite3.connect('database.db')  # Asume estructura OHLCV diaria/intradía
        
        for ticker in tqdm(tickers):
            query = f"""
            SELECT date, open, high, low, close, volume 
            FROM prices 
            WHERE ticker = '{ticker}' 
            AND date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY date
            """
            df = pd.read_sql(query, conn, parse_dates=['date'])
            if not df.empty:
                self.historical_data[ticker] = df
                
        conn.close()
    
    def simulate_intraday(self, lookback_days=20):
        """Simula ejecución intradía basada en datos históricos"""
        print("\nSimulando estrategia...")
        
        for ticker, data in tqdm(self.historical_data.items()):
            if len(data) < lookback_days + 5:  # Mínimo de datos requeridos
                continue
                
            for i in range(lookback_days, len(data)-1):
                window = data.iloc[i-lookback_days:i]
                current_day = data.iloc[i]
                next_day = data.iloc[i+1]
                
                # Calcula señales (misma lógica que tu scanner)
                signals = self.calculate_signals(window, current_day)
                
                if signals['entry_signal']:
                    entry_price = current_day['close']
                    exit_price = next_day['close']
                    pct_change = (exit_price - entry_price) / entry_price * 100
                    
                    self.results.append({
                        'date': current_day['date'],
                        'ticker': ticker,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pct_change': pct_change,
                        'vwap_slope': signals['vwap_slope'],
                        'rel_volume': signals['rel_volume'],
                        'resistance_break': signals['resistance_break']
                    })
    
    def calculate_signals(self, historical, current):
        """Replica la lógica de tu scanner"""
        # Calcula VWAP
        typical_price = (historical['high'] + historical['low'] + historical['close']) / 3
        pv = typical_price * historical['volume']
        vwap = pv.cumsum() / historical['volume'].cumsum()
        
        # Pendiente VWAP (5 días)
        slope = linregress(np.arange(5), vwap.tail(5).values).slope
        
        # Volumen relativo
        avg_volume = historical['volume'].rolling(20).mean().iloc[-1]
        rel_volume = current['volume'] / avg_volume
        
        # Resistencia
        high_20d = historical['high'].max()
        resistance_break = current['close'] > high_20d
        
        # Score (misma fórmula que tu scanner)
        score = (slope * 200) + (rel_volume * 0.7) + ((current['close'] - historical.iloc[-1]['open']) / historical.iloc[-1]['open'] * 100 * 1.5)
        
        return {
            'entry_signal': score > 150 and rel_volume > 1.5,
            'vwap_slope': slope,
            'rel_volume': rel_volume,
            'resistance_break': resistance_break,
            'score': score
        }
    
    def analyze_results(self):
        """Analiza estadísticamente los resultados"""
        if not self.results:
            print("No hay resultados para analizar")
            return
            
        df = pd.DataFrame(self.results)
        
        print("\n=== Estadísticas Clave ===")
        print(f"Total operaciones: {len(df)}")
        print(f"Tasa de aciertos: {len(df[df['pct_change'] > 0])/len(df)*100:.2f}%")
        print(f"Retorno promedio: {df['pct_change'].mean():.2f}%")
        print(f"Ratio Win/Loss: {len(df[df['pct_change'] > 0])/max(1, len(df[df['pct_change'] < 0])):.2f}")
        
        # Análisis por condiciones
        print("\n=== Performance por Condición ===")
        print("Resistencia rota:")
        print(df[df['resistance_break']]['pct_change'].describe())
        print("\nAlto volumen relativo (>3x):")
        print(df[df['rel_volume'] > 3]['pct_change'].describe())
        print("\nPendiente VWAP > 0.02:")
        print(df[df['vwap_slope'] > 0.02]['pct_change'].describe())

# Uso del backtester
if __name__ == "__main__":
    bt = Backtester()
    
    # Cargar los mismos tickers que usa tu scanner
    conn = sqlite3.connect('tickers.db')
    tickers = pd.read_sql("SELECT ticker FROM tickers", conn)['ticker'].tolist()
    conn.close()
    
    # Periodo de backtesting (ajusta según tus datos disponibles)
    bt.load_historical_data(tickers, '2023-01-01', '2023-12-31')
    bt.simulate_intraday()
    bt.analyze_results()