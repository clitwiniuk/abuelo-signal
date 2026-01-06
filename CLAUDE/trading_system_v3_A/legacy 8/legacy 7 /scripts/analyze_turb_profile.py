import sqlite3
import json
import pandas as pd
from datetime import datetime

# Connect to DB
conn = sqlite3.connect('trading_data.db')
cursor = conn.cursor()

# Get data
cursor.execute("SELECT intraday_bars FROM trade_ohlc_snapshots WHERE symbol='TURB' AND trading_date='2025-09-16'")
row = cursor.fetchone()

if not row:
    print("No data found for TURB")
    exit()

data = json.loads(row[0])
df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('US/Eastern')

# Filter 09:30 - 16:00
market_df = df[(df['timestamp'].dt.time >= datetime.strptime("09:30", "%H:%M").time()) & 
               (df['timestamp'].dt.time <= datetime.strptime("16:00", "%H:%M").time())]

print(f"Total Bars: {len(df)}")
print(f"Market Hours Bars: {len(market_df)}")

if len(market_df) > 0:
    print(f"Market High: {market_df['high'].max()}")
    print(f"Market Low: {market_df['low'].min()}")
    # Print hourly stats
    market_df['hour'] = market_df['timestamp'].dt.hour
    hourly = market_df.groupby('hour')['high'].max()
    print("\nHourly Highs:")
    print(hourly)
    
    # Locate the peak
    peak_idx = market_df['high'].idxmax()
    peak_time = market_df.loc[peak_idx, 'timestamp']
    print(f"\nPeak Time: {peak_time}")
    print(f"Peak Price: {market_df.loc[peak_idx, 'high']}")
else:
    print("No market hours data found!")

conn.close()
