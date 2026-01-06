#!/usr/bin/env python3
"""
Automatically fix inconsistent trade data in the database.
Addresses trades that are marked as OPEN but have exit_filled=1.
"""

import sqlite3
from datetime import datetime

DB_PATH = "trading_data.db"

def fix_inconsistent_trades():
    """Fix trades marked as OPEN but with exit_filled=1"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find inconsistent trades
    cursor.execute("""
        SELECT trade_id, symbol, status, exit_filled, actual_exit_price, actual_exit_time
        FROM trades
        WHERE status = 'OPEN' AND exit_filled = 1
    """)

    inconsistent_trades = cursor.fetchall()

    if not inconsistent_trades:
        print("✅ No inconsistent trades found. Database is clean.")
        conn.close()
        return 0

    print(f"⚠️  Found {len(inconsistent_trades)} inconsistent trades:")
    print("-" * 80)

    for trade_id, symbol, status, exit_filled, exit_price, exit_time in inconsistent_trades:
        print(f"  Trade ID: {trade_id} | Symbol: {symbol}")
        print(f"    Status: {status} | exit_filled: {exit_filled}")
        print(f"    Exit Price: {exit_price} | Exit Time: {exit_time}")

    # Automatically fix the trades
    print("\n🔧 Automatically fixing trades...")

    cursor.execute("""
        UPDATE trades
        SET status = 'CLOSED'
        WHERE status = 'OPEN' AND exit_filled = 1
    """)

    affected_rows = cursor.rowcount
    conn.commit()

    print(f"✅ Successfully updated {affected_rows} trades to CLOSED status.")

    # Verify the fix
    cursor.execute("""
        SELECT COUNT(*) FROM trades
        WHERE status = 'OPEN' AND exit_filled = 1
    """)

    remaining = cursor.fetchone()[0]

    if remaining == 0:
        print("✅ All inconsistencies have been resolved!")
    else:
        print(f"⚠️  {remaining} inconsistent trades still remain.")

    conn.close()
    return affected_rows

def check_price_inconsistencies():
    """Check for trades with suspicious price differences"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT trade_id, symbol, entry_price, actual_entry_price,
               ABS((actual_entry_price - entry_price) / entry_price * 100) as slippage_pct
        FROM trades
        WHERE actual_entry_price IS NOT NULL
          AND entry_price IS NOT NULL
          AND ABS((actual_entry_price - entry_price) / entry_price * 100) > 50
        ORDER BY slippage_pct DESC
    """)

    suspicious_trades = cursor.fetchall()

    if not suspicious_trades:
        print("\n✅ No suspicious price inconsistencies found.")
        conn.close()
        return 0

    print(f"\n⚠️  Found {len(suspicious_trades)} trades with suspicious price differences:")
    print("-" * 80)

    for trade_id, symbol, planned, actual, slippage in suspicious_trades:
        print(f"  Trade ID: {trade_id} | Symbol: {symbol}")
        print(f"    Planned: ${planned:.2f} | Actual: ${actual:.2f}")
        print(f"    Difference: {slippage:.1f}%")

    print("\n💡 These trades will use planned prices as fallback in the dashboard.")

    conn.close()
    return len(suspicious_trades)

if __name__ == "__main__":
    print("=" * 80)
    print("AUTOMATIC TRADE DATA CONSISTENCY FIX")
    print("=" * 80)
    print()

    # Fix status inconsistencies
    fixed = fix_inconsistent_trades()

    # Check for price inconsistencies
    print()
    suspicious = check_price_inconsistencies()

    print("\n" + "=" * 80)
    print(f"Summary: Fixed {fixed} trades, {suspicious} price warnings remain")
    print("=" * 80)
