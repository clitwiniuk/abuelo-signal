
import sqlite3
import json
import pandas as pd
from datetime import datetime

conn = sqlite3.connect('trading_data.db')
cursor = conn.cursor()
cursor.execute("SELECT symbol, trading_date, intraday_bars FROM trade_ohlc_snapshots WHERE length(intraday_bars) > 100 LIMIT 5")
rows = cursor.fetchall()

print(f"Inspecting {len(rows)} snapshots...")

for row in rows:
    symbol = row[0]
    date = row[1]
    data = json.loads(row[2])
    
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data)
        
    # Standardize cols
    df.columns = [c.lower() for c in df.columns]
    
    # Time handling
    if 'timestamp' in df.columns:
        # Check if unix or stri
        sample = df['timestamp'].iloc[0]
        try:
            df['dt'] = pd.to_datetime(df['timestamp'])
        except:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='s')
    
    df['time_str'] = df['dt'].dt.strftime('%H:%M:%S')
    
    max_time = df['time_str'].max()
    min_time = df['time_str'].min()
    
    count_after_1600 = len(df[df['time_str'] > '16:00:00'])
    
    print(f"Symbol: {symbol} | Date: {date} | Range: {min_time} - {max_time} | Rows > 16:00: {count_after_1600}")

conn.close()
