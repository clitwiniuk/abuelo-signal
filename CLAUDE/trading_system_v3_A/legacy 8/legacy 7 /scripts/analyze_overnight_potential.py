
import sqlite3
import pandas as pd
import json
from datetime import datetime
import pytz

DB_PATH = "trading_data.db"
# Check wider range of dates
DATES_TO_CHECK = ["2025-12-19", "2025-12-17", "2025-12-16", "2025-12-15"]

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def analyze_date(target_date):
    print(f"\n{'='*60}")
    print(f"ANALYZING DATE: {target_date}")
    print(f"{'='*60}")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get symbols for this date
    query = """
    SELECT symbol, intraday_bars 
    FROM trade_ohlc_snapshots 
    WHERE trading_date = ? 
    ORDER BY  length(intraday_bars) DESC
    LIMIT 5
    """
    
    cursor.execute(query, (target_date,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"❌ No snapshots found for {target_date}")
        return

    for row in rows:
        symbol = row[0]
        intraday_json = row[1]
        analyze_ticker(symbol, target_date, intraday_json)

def analyze_ticker(symbol, date, intraday_json):
    if not intraday_json: return

    try:
        bars_data = json.loads(intraday_json)
        if isinstance(bars_data, dict) and 'timestamp' in bars_data:
             df = pd.DataFrame(bars_data)
        elif isinstance(bars_data, list):
             df = pd.DataFrame(bars_data)
        else:
             return
             
        df.columns = [c.lower() for c in df.columns]
        
        try:
            df['datetime'] = pd.to_datetime(df['timestamp'])
        except:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        
        df = df.sort_values('datetime')
        df['time_str'] = df['datetime'].dt.strftime('%H:%M:%S')
        
        # Approximate Entry (VWAP of first 30m)
        df_open = df[(df['time_str'] >= '09:30:00') & (df['time_str'] <= '10:00:00')]
        if df_open.empty: 
             entry_price = df['close'].iloc[0]
        else:
             entry_price = df_open['close'].mean()

        # Start trade at 10:00
        df_trade = df[df['time_str'] >= '10:00:00'].copy()
        if df_trade.empty: return

        # Stop Loss 5%
        stop_price = entry_price * 0.95
        
        # Outcome
        min_low = df_trade['low'].min()
        
        # Market Close or Aftermarket
        df_am = df[df['time_str'] > '16:00:00']
        has_am = not df_am.empty
        close_price = df_am['close'].iloc[-1] if has_am else df_trade['close'].iloc[-1]
        
        pnl_pct = ((close_price - entry_price) / entry_price) * 100
        
        print(f"👉 {symbol}: Entry ${entry_price:.2f} -> End ${close_price:.2f} ({pnl_pct:+.1f}%)", end=" ")
        
        if min_low <= stop_price:
            print(f"| ❌ STOPPED OUT (Low ${min_low:.2f})")
        else:
            if pnl_pct > 0:
                print(f"| 🎉 PROFITABLE HOLD! ✅")
            else:
                print(f"| ⚠️ HELD BUT LOSS")

    except Exception:
        pass

if __name__ == "__main__":
    for d in DATES_TO_CHECK:
        analyze_date(d)
