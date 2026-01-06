#!/usr/bin/env python3
"""
Scanner Backtest Tool (Database Version)
Allows retrospective analysis of scanner behavior using local DB data.
"""

import sqlite3
import json
import sys
import os
import argparse
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def backtest_scanner_db(symbol: str, date_str: str, db_path: str = 'trading_data.db'):
    """
    Backtest scanner logic using data from local SQLite database.
    """
    print(f"\n🕵️‍♂️ SCANNER DB BACKTEST: {symbol} on {date_str}")
    print("=" * 60)
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Fetch Snapshot
        print(f"📥 Querying trade_ohlc_snapshots for {symbol}...")
        
        # Try to find by exact date match in trading_date or created_at
        cursor.execute("""
            SELECT * FROM trade_ohlc_snapshots 
            WHERE symbol = ? 
            AND (trading_date = ? OR created_at LIKE ?)
            ORDER BY created_at DESC
            LIMIT 1
        """, (symbol, date_str, f"{date_str}%"))
        
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ No snapshot found for {symbol} on {date_str}")
            print("   (Data might not have been recorded if no trade/opportunity occurred)")
            
            # Suggest available dates
            cursor.execute("SELECT DISTINCT trading_date FROM trade_ohlc_snapshots WHERE symbol = ?", (symbol,))
            dates = [r[0] for r in cursor.fetchall()]
            if dates:
                print(f"   💡 Available dates for {symbol}: {', '.join(dates)}")
            return

        # 2. Parse Intraday Bars
        bars_json = row['intraday_bars']
        if not bars_json:
            print("❌ Snapshot found but 'intraday_bars' column is empty")
            return

        try:
            bars_data = json.loads(bars_json)
        except json.JSONDecodeError:
            print("❌ Failed to parse intraday_bars JSON")
            return
            
        if not bars_data:
            print("❌ Parsed bars list is empty")
            return

        print(f"✅ Loaded {len(bars_data)} intraday bars from database")
        
        # Convert to DataFrame for easier handling
        df = pd.DataFrame(bars_data)
        
        # Ensure regex parsing for timestamps if needed, or simple conversion
        # The JSON usually has 'timestamp' in ISO format
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=False)
            df.sort_values('timestamp', inplace=True)
        
        # 3. Define Scanner Rules (Must match ibkr_native_scanner.py)
        rules = [
            # 1. Early Movers
            {
                "name": "Early Movers",
                "min_price": 0.5,
                "max_price": 25.0,
                "min_volume": 15000, 
                "min_change": 3.0 
            },
            # 2. Volume Surge
            {
                "name": "Volume Surge",
                "min_price": 0.5,
                "max_price": 15.0,
                "min_volume": 100000, 
                "min_change": 0.0
            },
             # 3. Gap Up
            {
                "name": "Gap Up",
                "min_price": 0.5,
                "max_price": 15.0,
                "min_volume": 20000,
                "min_gap": 3.0, 
            }
        ]
        
        # 4. Run Simulation
        prev_close = row['day_open'] # Fallback if prev_close not explicitly stored, or use open
        # Ideally we want true previous close.
        # Let's see if we can deduce it. 
        # Gap% = (Open - PrevClose)/PrevClose
        # PrevClose = Open / (1 + Gap%)
        gap_pct = row['gap_percent'] if row['gap_percent'] else 0.0
        day_open = row['day_open']
        
        if day_open and gap_pct:
            calculated_prev_close = day_open / (1 + (gap_pct/100))
            print(f"📉 Derived Prev Close from Gap: ${calculated_prev_close:.2f} (Gap: {gap_pct}%, Open: ${day_open})")
            prev_close = calculated_prev_close
        else:
             print(f"⚠️ Warning: Using Day Open (${day_open}) as Prev Close proxy (Gap data missing)")
             prev_close = day_open

        start_of_day = pd.Timestamp(date_str).replace(hour=9, minute=30)
        
        triggers = {r['name']: None for r in rules}
        cum_volume = 0
        
        print("\n⏱️ TIMELINE ANALYSIS (Replay):")
        print(f"{'TIME':<10} | {'PRICE':<8} | {'VOL (Cum)':<10} | {'CHANGE%':<8} | {'TRIGGERS'}")
        print("-" * 70)
        
        for i, bar in df.iterrows():
            timestamp = bar['timestamp']
            price = bar['close']
            volume = bar['volume']
            
            # Accumulate volume (Reset if new day? Assuming snapshot is 1 day)
            # The snapshot might contain recent bars only.
            # If bars are 1-min for the day, we sum them up.
            cum_volume += volume
            
            change_pct = ((price - prev_close) / prev_close) * 100
            
            triggered_now = []
            
            for rule in rules:
                if triggers[rule['name']] is not None:
                    continue 
                
                # Check metrics
                price_ok = rule['min_price'] <= price <= rule['max_price']
                vol_ok = cum_volume >= rule['min_volume']
                change_ok = change_pct >= rule.get('min_change', -999)
                gap_ok = change_pct >= rule.get('min_gap', -999) # Proxy
                
                if price_ok and vol_ok and change_ok and gap_ok:
                    triggers[rule['name']] = timestamp
                    triggered_now.append(rule['name'])
            
            if triggered_now:
                time_str = timestamp.strftime("%H:%M:%S")
                print(f"{time_str:<10} | ${price:<7.2f} | {int(cum_volume):<10} | {change_pct:+.2f}%   | ✅ {', '.join(triggered_now)}")

        print("\n🏁 SUMMARY OF THEORETICAL DETECTIONS:")
        print("-" * 40)
        for name, time in triggers.items():
            if time:
                 print(f"✅ {name:<15}: {time.strftime('%H:%M:%S')}")
            else:
                 print(f"❌ {name:<15}: NEVER (Conditions not met)")
                 
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scanner DB Backtest')
    parser.add_argument('--symbol', required=True, help='Ticker Symbol (e.g., OCG)')
    parser.add_argument('--date', required=True, help='Date YYYY-MM-DD')
    parser.add_argument('--db', default='trading_data.db', help='Path to database')
    
    args = parser.parse_args()
    
    backtest_scanner_db(args.symbol, args.date, args.db)
