import sqlite3
import datetime
import os
from dateutil import parser

# Configuration
DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"

def get_market_session(dt):
    """
    Determine market session from datetime.
    Pre-Market: < 09:30
    Regular: 09:30 - 16:00
    After-Hours: > 16:00
    """
    # Convert to time
    t = dt.time()
    
    # Define boundaries
    market_open = datetime.time(9, 30)
    market_close = datetime.time(16, 0)
    
    if t < market_open:
        return "PRE_MARKET"
    elif t >= market_open and t < market_close:
        return "REGULAR"
    else:
        return "AFTER_HOURS"

def repair_data():
    print(f"🔌 Connecting to database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Find trades with missing trade_session
        cursor.execute("SELECT trade_id, entry_time, symbol FROM trades WHERE trade_session IS NULL OR trade_session = ''")
        trades = cursor.fetchall()
        
        print(f"🔍 Found {len(trades)} trades with missing session data.")
        
        updated_count = 0
        
        for trade in trades:
            try:
                entry_time_str = trade['entry_time']
                if not entry_time_str:
                    print(f"⚠️ Skipping {trade['symbol']} (ID: {trade['trade_id']}): No entry time")
                    continue
                    
                # Parse timestamp
                # Handle potential formats
                try:
                    dt = parser.parse(entry_time_str)
                except:
                    print(f"❌ Error parsing date for {trade['symbol']}: {entry_time_str}")
                    continue
                
                # Determine session
                session = get_market_session(dt)
                
                # Update record
                cursor.execute(
                    "UPDATE trades SET trade_session = ? WHERE trade_id = ?",
                    (session, trade['trade_id'])
                )
                updated_count += 1
                # print(f"✅ Updated {trade['symbol']}: {entry_time_str} -> {session}")
                
            except Exception as e:
                print(f"❌ Error processing trade {trade['trade_id']}: {e}")
        
        conn.commit()
        print(f"💾 Committed updates for {updated_count} trades.")
        
        # 2. Check for missing confidence/context (Just reporting for now)
        cursor.execute("SELECT COUNT(*) FROM trades WHERE strategy_confidence IS NULL")
        missing_conf = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM trades WHERE market_context_score IS NULL")
        missing_context = cursor.fetchone()[0]
        
        print(f"\n📊 Remaining Missing Data:")
        print(f"   - Missing Strategy Confidence: {missing_conf}")
        print(f"   - Missing Market Context Score: {missing_context}")
        print("\n💡 Note: 'Confidence' and 'Context' cannot be deterministically recovered from timestamps.")
        print("   They would require parsing historical logs. Future trades will be correct due to the code fix.")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    repair_data()
