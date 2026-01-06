import sqlite3
import datetime
from dateutil import parser

# Configuration
DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"

def recover_data():
    print(f"🔌 Connecting to database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Find trades with missing confidence or context
        cursor.execute("""
            SELECT trade_id, symbol, entry_time 
            FROM trades 
            WHERE strategy_confidence IS NULL 
               OR strategy_confidence = ''
               OR market_context_score IS NULL
               OR market_context_score = ''
        """)
        trades = cursor.fetchall()
        
        print(f"🔍 Found {len(trades)} trades with missing metrics.")
        
        updated_count = 0
        
        for trade in trades:
            try:
                trade_id = trade['trade_id']
                symbol = trade['symbol']
                entry_time_str = trade['entry_time']
                
                if not entry_time_str:
                    continue
                    
                entry_dt = parser.parse(entry_time_str)
                
                # Define a time window (e.g., +/- 5 minutes) to find the matching signal
                # Signals usually come just before entry
                window_start = entry_dt - datetime.timedelta(minutes=5)
                window_end = entry_dt + datetime.timedelta(minutes=1)
                
                # Query signal_events
                # We look for the most recent signal before or at entry time
                cursor.execute("""
                    SELECT quality_score, ods_strength, confidence
                    FROM signal_events
                    WHERE symbol = ? 
                      AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol, window_start, window_end))
                
                signal = cursor.fetchone()
                
                if signal:
                    # Map fields
                    # Based on observation: strategy_confidence ~= quality_score
                    # market_context_score ~= quality_score (in some cases) or ods_strength
                    
                    quality = signal['quality_score']
                    ods = signal['ods_strength']
                    conf = signal['confidence']
                    
                    # Use quality_score as primary source for strategy_confidence if available
                    strategy_conf = quality if quality else conf
                    
                    # Use quality_score for market_context_score as observed in NVD trade, 
                    # or fallback to ods_strength if available
                    market_context = quality if quality else ods
                    
                    if strategy_conf is not None:
                        cursor.execute("""
                            UPDATE trades 
                            SET strategy_confidence = ?,
                                market_context_score = ?,
                                confidence = ?
                            WHERE trade_id = ?
                        """, (strategy_conf, market_context, conf, trade_id))
                        
                        updated_count += 1
                        # print(f"✅ Recovered {symbol} ({trade_id}): Conf={strategy_conf}, Ctx={market_context}")
                    else:
                        # print(f"⚠️ Signal found for {symbol} but no scores: {dict(signal)}")
                        pass
                else:
                    # print(f"❌ No signal event found for {symbol} at {entry_time_str}")
                    pass
                
            except Exception as e:
                print(f"❌ Error processing trade {trade['trade_id']}: {e}")
        
        conn.commit()
        print(f"💾 Recovered data for {updated_count} trades.")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    recover_data()
