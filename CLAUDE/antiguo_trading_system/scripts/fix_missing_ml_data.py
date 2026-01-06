"""
Fix Missing ML Data in Trades
================================

Este script corrige los trades que no tienen datos ML (strategy_confidence,
market_context_score, trade_session) obteniéndolos de las oportunidades del scanner.
"""

import sqlite3
from datetime import datetime

DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"

def fix_missing_ml_data():
    """Fix trades with missing ML data"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find trades without ML data from the last 7 days
    cursor.execute("""
        SELECT trade_id, symbol, entry_time, strategy
        FROM trades
        WHERE (strategy_confidence IS NULL OR market_context_score IS NULL OR trade_session IS NULL)
        AND DATE(entry_time) >= DATE('now', '-7 days')
        ORDER BY entry_time DESC
    """)

    trades_to_fix = cursor.fetchall()
    print(f"Found {len(trades_to_fix)} trades with missing ML data")

    fixed_count = 0
    not_found_count = 0

    for trade_id, symbol, entry_time, strategy in trades_to_fix:
        # Find matching opportunity (closest in time, within 90 minutes to account for timezone issues)
        # We use a larger window because there might be timezone differences between trades and opportunities
        cursor.execute("""
            SELECT quality_score, volume_ratio, gap_percentage
            FROM scanner_opportunities
            WHERE symbol = ?
            AND ABS(JULIANDAY(timestamp) - JULIANDAY(?)) * 24 * 60 < 90
            ORDER BY ABS(JULIANDAY(timestamp) - JULIANDAY(?))
            LIMIT 1
        """, (symbol, entry_time, entry_time))

        opp = cursor.fetchone()

        if opp:
            quality_score, volume_ratio, gap_percentage = opp

            # Determine trade session based on entry time
            entry_dt = datetime.fromisoformat(entry_time)
            hour = entry_dt.hour
            minute = entry_dt.minute
            time_decimal = hour + minute / 60.0

            # Market sessions (ET):
            # PRE_MARKET: 4:00-9:30 (04:00-09:30)
            # REGULAR: 9:30-16:00 (09:30-16:00)
            # AFTER_HOURS: 16:00-20:00 (16:00-20:00)
            if 4.0 <= time_decimal < 9.5:
                trade_session = 'PRE_MARKET'
            elif 9.5 <= time_decimal < 16.0:
                trade_session = 'REGULAR'
            elif 16.0 <= time_decimal < 20.0:
                trade_session = 'AFTER_HOURS'
            else:
                trade_session = 'CLOSED'

            # Update trade with ML data
            cursor.execute("""
                UPDATE trades
                SET strategy_confidence = ?,
                    market_context_score = ?,
                    trade_session = ?,
                    volume_ratio = ?,
                    gap_percentage = ?,
                    confidence = ?
                WHERE trade_id = ?
            """, (quality_score, quality_score, trade_session, volume_ratio, gap_percentage, quality_score, trade_id))

            fixed_count += 1
            print(f"✅ Fixed {symbol} ({trade_id}): confidence={quality_score:.1f}%, session={trade_session}")
        else:
            not_found_count += 1
            print(f"❌ No opportunity found for {symbol} ({trade_id}) at {entry_time}")

    conn.commit()
    conn.close()

    print(f"\n✅ Fixed {fixed_count} trades")
    print(f"❌ Could not fix {not_found_count} trades (no matching opportunity)")

if __name__ == "__main__":
    fix_missing_ml_data()
