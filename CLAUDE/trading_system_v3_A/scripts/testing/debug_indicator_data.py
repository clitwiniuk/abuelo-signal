
import sqlite3
import os
import sys
from datetime import datetime
import dateutil.parser

# Path to database
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'trading_data.db')
SYMBOL = 'PETS'

def run_debug():
    print(f"📂 Opening database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Find the opportunity
        print(f"🔍 Searching for {SYMBOL} opportunity...")
        cursor.execute("SELECT * FROM scanner_opportunities WHERE symbol = ? ORDER BY timestamp DESC LIMIT 5", (SYMBOL,))
        rows = cursor.fetchall()
        
        target_opp = None
        for row in rows:
            print(f"   Found Opp: {row['timestamp']} | Type: {row['opportunity_type']}")
            if '2025-11-12' in row['timestamp'] or '2025-12-11' in row['timestamp']:
                target_opp = row
                break
        
        if not target_opp:
            print("❌ Target opportunity not found matching date.")
            return

        print(f"✅ Selected Opportunity: {target_opp['timestamp']}")
        opp_ts_str = target_opp['timestamp']
        try:
            opp_dt = dateutil.parser.parse(opp_ts_str)
            print(f"   Parsed Opp DT: {opp_dt} (TZ: {opp_dt.tzinfo})")
            opp_ts = opp_dt.timestamp()
            print(f"   Opp Timestamp: {opp_ts}")
        except Exception as e:
            print(f"❌ Failed to parse opp timestamp: {e}")
            return

        # 2. Fetch Bars
        date_str = opp_ts_str[:10]
        print(f"📅 Fetching bars for {date_str}...")
        
        cursor.execute("""
            SELECT bar_timestamp, open_price, high_price, low_price, close_price, volume 
            FROM market_intraday_bars 
            WHERE symbol = ? AND date(bar_timestamp) = ?
            ORDER BY bar_timestamp ASC
        """, (SYMBOL, date_str))
        
        bars = cursor.fetchall()
        print(f"📊 Found {len(bars)} bars.")
        
        if not bars:
            print("⚠️ No bars found.")
            return

        # 3. Simulate Logic
        print("🧮 Simulating VWAP Logic...")
        
        vwap_at_opp = None
        cum_vol = 0
        cum_tpv = 0
        
        first_bar = bars[0]
        print(f"   First Bar: {first_bar['bar_timestamp']}")
        
        for bar in bars:
            bar_ts_str = bar['bar_timestamp']
            # JS Logic: new Date(bar.timestamp).getTime()
            # If string doesn't have Z, JS might treat as local or UTC depending on runtime.
            # Python parser is more strict/explicit.
            
            try:
                bar_dt = dateutil.parser.parse(bar_ts_str)
                bar_ts = bar_dt.timestamp()
            except:
                print(f"Failed to parse bar ts: {bar_ts_str}")
                continue
                
            tp = (bar['high_price'] + bar['low_price'] + bar['close_price']) / 3
            tpv = tp * bar['volume']
            cum_vol += bar['volume']
            cum_tpv += tpv
            
            current_vwap = cum_tpv / cum_vol if cum_vol > 0 else 0
            
            # Comparison
            if bar_ts <= opp_ts:
                vwap_at_opp = current_vwap
            else:
                print(f"      🛑 Past Opp Time: Bar {bar_ts_str} ({bar_ts}) > Opp {opp_ts_str} ({opp_ts})")
                print(f"      Diff: {bar_ts - opp_ts} seconds")
                break
                
        print(f"🏁 Final Calculated VWAP: {vwap_at_opp}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_debug()
