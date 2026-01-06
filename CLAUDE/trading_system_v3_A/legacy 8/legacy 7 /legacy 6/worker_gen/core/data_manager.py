import pandas as pd
import numpy as np
import os
from typing import List, Dict, Optional

class DataManager:
    """
    Manages loading and preprocessing of OHLC data for the Worker Generator.
    Computes technical indicators on load to speed up optimization loop.
    """
    
    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        self.datasets: Dict[str, pd.DataFrame] = {}
        
    def load_all(self):
        """Loads all CSV files from the input directory."""
        files = [f for f in os.listdir(self.input_dir) if f.endswith('.csv')]
        print(f"Found {len(files)} CSV files in {self.input_dir}")
        for f in files:
            path = os.path.join(self.input_dir, f)
            try:
                df = pd.read_csv(path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Check for required columns
                required = ['open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required):
                    print(f"⚠️  Skipping {f}: Missing required columns")
                    continue
                    
                # Feature Engineering (Pre-calc indicators)
                df = self._add_features(df)
                
                self.datasets[f] = df
                print(f"✅ Loaded {f} ({len(df)} rows)")
            except Exception as e:
                print(f"❌ Error loading {f}: {e}")
                
    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates standard indicators used by the optimizer."""
        close = df['close']
        
        # 1. EMAs
        for period in [9, 20, 50, 200]:
            df[f'ema_{period}'] = close.ewm(span=period, adjust=False).mean()
            
        # 2. RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # 3. VWAP
        # Assumes the CSV is a single day (cumulative from start)
        # If multiple days, would need grouping. For simpler patterns, full cumsum is okay
        # typically patterns are intraday.
        df['cum_vol'] = df['volume'].cumsum()
        df['cum_pv'] = (df['close'] * df['volume']).cumsum() # Approximation using close
        # more accurate is (H+L+C)/3
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df['cum_pv_exact'] = (typical_price * df['volume']).cumsum()
        df['vwap'] = df['cum_pv_exact'] / df['cum_vol']
        
        # 4. Relative Volume (Simple Ratio to SMA 20 of volume)
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / df['vol_sma_20']
        
        # 5. Price vs EMA distance (%)
        df['dist_ema_9'] = (close - df['ema_9']) / df['ema_9'] * 100
        
        # Fill NaNs (start of series)
        df = df.fillna(method='bfill')
        
        return df

    def get_data(self) -> Dict[str, pd.DataFrame]:
        return self.datasets
