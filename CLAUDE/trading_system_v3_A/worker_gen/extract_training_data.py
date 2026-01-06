import sqlite3
import pandas as pd
import argparse
import os
import sys
import json
from datetime import datetime

# Add parent dir to path to find DB paths if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def extract_data(symbol, date, output_dir, db_path='trading_data.db', start_time=None, end_time=None):
    """
    Extracts intraday data for a specific symbol and date from the database
    and saves it as a CSV file.
    """
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    
    # Try different tables where data might be stored
    tables_to_check = ['intraday_bars', 'trade_intraday_bars', 'market_intraday_bars']
    
    df = pd.DataFrame()
    
    for table in tables_to_check:
        try:
            query = f"""
                SELECT bar_timestamp as timestamp, open_price as open, high_price as high, 
                       low_price as low, close_price as close, volume
                FROM {table}
                WHERE symbol = ? AND date(bar_timestamp) = ?
            """
            print(f"Checking table {table}...")
            # Note: Using pandas read_sql directly deals with parameters better
            temp_df = pd.read_sql_query(query, conn, params=(symbol, date))
            
            if not temp_df.empty:
                print(f"Found {len(temp_df)} rows in {table}")
                df = temp_df
                break
        except Exception as e:
            print(f"Could not query {table}: {e}")
            continue
            
    # Fallback to snapshots if still empty
    if df.empty:
        print("Checking trade_ohlc_snapshots...")
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT intraday_bars FROM trade_ohlc_snapshots 
                WHERE symbol = ? AND trading_date = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (symbol, date))
            row = cursor.fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                df = pd.DataFrame(data)
                # Ensure columns match standard
                if 'bar_timestamp' in df.columns:
                    df = df.rename(columns={'bar_timestamp': 'timestamp', 'open_price': 'open', 'high_price': 'high', 'low_price': 'low', 'close_price': 'close'})
                print(f"Found {len(df)} rows in snapshot")
        except Exception as e:
            print(f"Error querying snapshots: {e}")

    conn.close()

    if df.empty:
        print(f"❌ No data found for {symbol} on {date}")
        return False

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort
    df = df.sort_values('timestamp')

    # Filter by time if requested
    if start_time:
        # Assuming start_time is HH:MM string
        # We need to construct full datetime or filter by time component
        # Simplest is filtering by time component string comparison for now
        mask = df['timestamp'].dt.strftime('%H:%M') >= start_time
        df = df[mask]
    
    if end_time:
        mask = df['timestamp'].dt.strftime('%H:%M') <= end_time
        df = df[mask]

    # Save to CSV
    filename = f"{symbol}_{date}.csv"
    output_path = os.path.join(output_dir, filename)
    
    # Save standard columns
    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    # Add vwap if calculated/available
    if 'vwap' in df.columns:
        cols.append('vwap')
        
    df.to_csv(output_path, index=False, columns=[c for c in cols if c in df.columns])
    print(f"✅ Saved {len(df)} bars to {output_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract intraday data to CSV')
    parser.add_argument('--symbol', required=True, help='Ticker symbol')
    parser.add_argument('--date', required=True, help='Date YYYY-MM-DD')
    parser.add_argument('--output', default='worker_gen/input', help='Output directory')
    parser.add_argument('--db', default='trading_data.db', help='Database path')
    parser.add_argument('--start', help='Start time HH:MM (optional)')
    parser.add_argument('--end', help='End time HH:MM (optional)')
    
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    extract_data(args.symbol, args.date, args.output, args.db, args.start, args.end)
