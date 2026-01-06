
import sqlite3
import json
import pandas as pd
from datetime import datetime

def inspect_data():
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    
    # Get bars for AEHL (ID 576)
    cursor.execute("SELECT intraday_bars FROM trade_ohlc_snapshots WHERE id=576")
    row = cursor.fetchone()
    
    if not row:
        print("No data found")
        return
        
    bars_json = row[0]
    bars = json.loads(bars_json)
    
    print(f"Loaded {len(bars)} bars for AEHL")
    
    if not bars:
        return
        
    # Convert to DataFrame for easy analysis
    df = pd.DataFrame(bars)
    
    print("\nDataFrame Head:")
    print(df.head())
    
    print("\nDataFrame Tail:")
    print(df.tail())
    
    max_high = df['high'].max()
    min_low = df['low'].min()
    vwap = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).sum() / df['volume'].sum()
    
    print(f"\nStats:")
    print(f"Max High: {max_high}")
    print(f"Min Low: {min_low}")
    print(f"VWAP: {vwap:.2f}")
    
    # Print the last bar specifically
    last = bars[-1]
    print(f"\nLast Bar: {last}")

if __name__ == "__main__":
    inspect_data()
