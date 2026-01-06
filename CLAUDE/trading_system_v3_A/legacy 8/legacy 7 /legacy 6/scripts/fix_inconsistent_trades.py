#!/usr/bin/env python3
"""
Fix inconsistent trade data in the database.
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
        return

    print(f"⚠️  Found {len(inconsistent_trades)} inconsistent trades:")
    print("-" * 80)

    for trade_id, symbol, status, exit_filled, exit_price, exit_time in inconsistent_trades:
        print(f"  Trade ID: {trade_id} | Symbol: {symbol}")
        print(f"    Status: {status} | exit_filled: {exit_filled}")
        print(f"    Exit Price: {exit_price} | Exit Time: {exit_time}")
        print()

    # Ask for confirmation
    response = input("Do you want to fix these trades by marking them as CLOSED? (y/n): ")

    if response.lower() != 'y':
        print("❌ Fix cancelled by user.")
        conn.close()
        return

    # Fix the trades
    cursor.execute("""
        UPDATE trades
        SET status = 'CLOSED'
        WHERE status = 'OPEN' AND exit_filled = 1
    """)

    affected_rows = cursor.rowcount
    conn.commit()

    print(f"\n✅ Successfully updated {affected_rows} trades to CLOSED status.")

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
        return

    print(f"\n⚠️  Found {len(suspicious_trades)} trades with suspicious price differences:")
    print("-" * 80)

    for trade_id, symbol, planned, actual, slippage in suspicious_trades:
        print(f"  Trade ID: {trade_id} | Symbol: {symbol}")
        print(f"    Planned: ${planned:.2f} | Actual: ${actual:.2f}")
        print(f"    Difference: {slippage:.1f}%")
        print()

    print("💡 These trades should be reviewed manually.")
    print("   The dashboard will use planned prices as fallback for >50% slippage.")

    conn.close()

if __name__ == "__main__":
    print("=" * 80)
    print("TRADE DATA CONSISTENCY CHECK AND FIX UTILITY")
    print("=" * 80)
    print()

    # Fix status inconsistencies
    fix_inconsistent_trades()

    # Check for price inconsistencies
    check_price_inconsistencies()

    print("\n" + "=" * 80)
    print("Consistency check complete!")
    print("=" * 80)
