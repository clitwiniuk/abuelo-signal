import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Connect to DB
conn = sqlite3.connect('regression_market_data.db')

# List tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"Tables in regression_market_data.db: {tables}")

# Get list of symbols
try:
    symbols_df = pd.read_sql("SELECT DISTINCT symbol FROM intraday_bars", conn)
except:
    print("intraday_bars table not found, trying market_intraday_bars")
    symbols_df = pd.read_sql("SELECT DISTINCT symbol FROM market_intraday_bars", conn)
    
symbols = symbols_df['symbol'].tolist()

print(f"Scanning {len(symbols)} symbols for Balance Day candidates...")

candidates = []

for symbol in symbols:
    # Get daily data
    query = f"""
    SELECT 
        date(bar_timestamp) as date,
        MIN(low_price) as day_low,
        MAX(high_price) as day_high,
        AVG(volume) as avg_vol,
        open_price as day_open
    FROM intraday_bars 
    WHERE symbol = '{symbol}'
    GROUP BY date(bar_timestamp)
    """
    try:
        df = pd.read_sql(query, conn)
        
        for _, row in df.iterrows():
            if row['day_open'] == 0: continue
            
            # Calculate range %
            day_range = row['day_high'] - row['day_low']
            range_pct = (day_range / row['day_open']) * 100
            
            # Balance Day Criteria:
            # 1. Range < 1.5% (relaxed to find candidates, worker uses 1.0%)
            # 2. Sufficient volume (simplified check)
            
            if range_pct < 1.5 and range_pct > 0.2:
                candidates.append({
                    'symbol': symbol,
                    'date': row['date'],
                    'range_pct': range_pct,
                    'volume': row['avg_vol']
                })
                
    except Exception as e:
        print(f"Error processing {symbol}: {e}")

# Convert to DF and sort
results = pd.DataFrame(candidates)
if not results.empty:
    results = results.sort_values('range_pct')
    print(f"\nFound {len(results)} candidates. Top 20 narrowest ranges:")
    print(results.head(20))
    
    # Save to CSV for analysis
    results.to_csv('balance_day_candidates.csv', index=False)
    print("\nSaved to balance_day_candidates.csv")
else:
    print("No candidates found.")

conn.close()
