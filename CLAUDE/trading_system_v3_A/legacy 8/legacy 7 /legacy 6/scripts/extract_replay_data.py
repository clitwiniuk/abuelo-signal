import sqlite3
import json
import os

DB_PATH = 'trading_data.db'

ids_to_extract = [
    (2890, 'RR', 'test_data/real_replay_data_rr.json'),
    (2888, 'MSTX', 'test_data/real_replay_data_mstx.json')
]

def extract():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        for ID, expected_symbol, output_file in ids_to_extract:
            print(f"\n--- Extracting ID {ID} ({expected_symbol}) ---")
            cursor = conn.execute(f"SELECT symbol, intraday_bars, day_close FROM trade_ohlc_snapshots WHERE id={ID}")
            row = cursor.fetchone()
            
            if not row:
                print(f"No row found for ID {ID}")
                continue
                
            symbol, bars_blob, day_close = row
            print(f"Found {symbol}, blob size: {len(bars_blob) if bars_blob else 0}")
            
            if not bars_blob:
                print("No bars data found")
                continue
            
            # Simple simulation of stronger volume for older data if needed, 
            # but we use the real data primarily.
            bars = json.loads(bars_blob)
            print(f"Parsed {len(bars)} bars")
            
            replay_data = {
                "symbol": symbol,
                "current_price": float(day_close) if day_close else bars[-1]['close'],
                "volume_ratio": 2.5, 
                "bars_1min": bars
            }
            
            with open(output_file, 'w') as f:
                json.dump(replay_data, f, indent=2)
                
            print(f"Successfully wrote to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    extract()
