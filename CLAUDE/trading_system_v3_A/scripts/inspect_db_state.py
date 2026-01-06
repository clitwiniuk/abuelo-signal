import sqlite3
import pandas as pd
import os
import sys

# Add project root
sys.path.append(os.getcwd())

DB_PATH = "trading_data.db"

def inspect_db():
    print(f"--- Inspecting {DB_PATH} ---")
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found!")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Check proactive_candidates
            try:
                df = pd.read_sql_query("SELECT * FROM proactive_candidates", conn)
                print(f"\n📊 Proactive Candidates Table ({len(df)} rows):")
                if not df.empty:
                    print(df[['symbol', 'detection_date', 'status', 'pattern_type']].to_string())
                    
                    # Check distribution of statuses
                    print("\nStatus Distribution:")
                    print(df['status'].value_counts())
                else:
                    print("⚠️ Table is EMPTY. This explains why Short Squeeze worker is silent.")
            except Exception as e:
                print(f"⚠️ Could not read proactive_candidates: {e}")

            # Check if we can see recent trades for reference
            try:
                trades = pd.read_sql_query("SELECT * FROM trades ORDER BY entry_time DESC LIMIT 5", conn)
                print(f"\nRecent Trades ({len(trades)}):")
                if not trades.empty:
                    print(trades[['symbol', 'strategy', 'entry_time', 'outcome']].to_string())
            except:
                pass

    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    inspect_db()
