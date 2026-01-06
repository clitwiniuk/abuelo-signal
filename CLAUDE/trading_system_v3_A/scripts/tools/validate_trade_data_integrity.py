#!/usr/bin/env python3
"""
Trade Data Integrity Validator
Detects and optionally fixes data inconsistencies in the trades database

Usage:
    python scripts/tools/validate_trade_data_integrity.py          # Check only
    python scripts/tools/validate_trade_data_integrity.py --fix    # Check and fix
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_PATH = "trading_data.db"

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

def check_data_integrity(fix_issues=False):
    """
    Check for data integrity issues in trades table

    Checks:
    1. Extreme slippage (>50% between entry_price and actual_entry_price)
    2. OPEN trades with exit_filled=1
    3. Execution times before trade creation times
    4. Duplicate entry fills
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    issues_found = []
    fixes_applied = []

    print("=" * 80)
    print("TRADE DATA INTEGRITY VALIDATOR")
    print("=" * 80)
    print()

    # Check 1: Extreme slippage
    print("📊 Check 1: Extreme Slippage Detection")
    print("-" * 80)

    cursor.execute("""
        SELECT trade_id, symbol, entry_price, actual_entry_price,
               entry_time, actual_entry_time, status, entry_filled
        FROM trades
        WHERE actual_entry_price IS NOT NULL
          AND entry_price IS NOT NULL
          AND ABS((actual_entry_price - entry_price) / entry_price * 100) > 50
    """)

    extreme_slippage = cursor.fetchall()

    if extreme_slippage:
        for trade in extreme_slippage:
            trade_id, symbol, entry_price, actual_entry, entry_time, actual_time, status, filled = trade
            slippage_pct = ((actual_entry - entry_price) / entry_price * 100)

            issue = {
                'type': 'EXTREME_SLIPPAGE',
                'trade_id': trade_id,
                'symbol': symbol,
                'details': f"Entry: ${entry_price:.2f} → Actual: ${actual_entry:.2f} ({slippage_pct:+.1f}%)"
            }
            issues_found.append(issue)

            print(f"⚠️  {symbol} ({trade_id})")
            print(f"    Planned Entry:  ${entry_price:.2f}")
            print(f"    Actual Entry:   ${actual_entry:.2f}")
            print(f"    Slippage:       {slippage_pct:+.2f}%")
            print(f"    Status:         {status}")
            print(f"    Entry Time:     {entry_time}")
            print(f"    Actual Time:    {actual_time}")

            if fix_issues:
                # Fix: Use planned entry price as it's likely more reliable
                cursor.execute("""
                    UPDATE trades
                    SET actual_entry_price = entry_price,
                        actual_entry_time = entry_time
                    WHERE trade_id = ?
                """, (trade_id,))
                fixes_applied.append(f"Fixed {symbol} ({trade_id}): Reset actual_entry_price to {entry_price:.2f}")
                print(f"    ✅ FIXED: Reset to planned entry price ${entry_price:.2f}")

            print()
    else:
        print("✅ No extreme slippage detected")
        print()

    # Check 2: OPEN trades with exit_filled=1
    print("📊 Check 2: Inconsistent Exit Status")
    print("-" * 80)

    cursor.execute("""
        SELECT trade_id, symbol, status, exit_filled, exit_time, actual_exit_time
        FROM trades
        WHERE status = 'OPEN' AND exit_filled = 1
    """)

    exit_inconsistencies = cursor.fetchall()

    if exit_inconsistencies:
        for trade in exit_inconsistencies:
            trade_id, symbol, status, exit_filled, exit_time, actual_exit_time = trade

            issue = {
                'type': 'EXIT_INCONSISTENCY',
                'trade_id': trade_id,
                'symbol': symbol,
                'details': f"Status={status} but exit_filled={exit_filled}"
            }
            issues_found.append(issue)

            print(f"⚠️  {symbol} ({trade_id})")
            print(f"    Status:           {status}")
            print(f"    Exit Filled:      {exit_filled}")
            print(f"    Exit Time:        {exit_time}")
            print(f"    Actual Exit Time: {actual_exit_time}")

            if fix_issues:
                # Fix: Clear exit data for OPEN positions
                cursor.execute("""
                    UPDATE trades
                    SET exit_filled = 0,
                        exit_time = NULL,
                        actual_exit_time = NULL,
                        actual_exit_price = NULL
                    WHERE trade_id = ?
                """, (trade_id,))
                fixes_applied.append(f"Fixed {symbol} ({trade_id}): Cleared exit data for OPEN position")
                print(f"    ✅ FIXED: Cleared exit data")

            print()
    else:
        print("✅ No exit status inconsistencies detected")
        print()

    # Check 3: Time anomalies - entry_time vs actual_entry_time mismatch
    print("📊 Check 3: entry_time vs actual_entry_time Mismatch")
    print("-" * 80)

    cursor.execute("""
        SELECT trade_id, symbol, entry_time, actual_entry_time, created_at
        FROM trades
        WHERE actual_entry_time IS NOT NULL
          AND entry_time IS NOT NULL
          AND ABS((julianday(entry_time) - julianday(actual_entry_time)) * 24) > 24
    """)

    time_mismatches = cursor.fetchall()

    if time_mismatches:
        for trade in time_mismatches:
            trade_id, symbol, entry_time, actual_time, created_at = trade

            # Determine which timestamp is more likely correct
            # actual_entry_time is usually more reliable (from broker execution)
            # entry_time may have been overwritten by recovery scripts

            time_diff_hours = abs((datetime.fromisoformat(entry_time) -
                                  datetime.fromisoformat(actual_time)).total_seconds() / 3600)

            issue = {
                'type': 'TIME_MISMATCH',
                'trade_id': trade_id,
                'symbol': symbol,
                'details': f"entry_time and actual_entry_time differ by {time_diff_hours:.1f}h"
            }
            issues_found.append(issue)

            print(f"⚠️  {symbol} ({trade_id})")
            print(f"    entry_time:        {entry_time}")
            print(f"    actual_entry_time: {actual_time}")
            print(f"    created_at:        {created_at}")
            print(f"    Difference:        {time_diff_hours:.1f} hours")

            if fix_issues:
                # Fix: Use actual_entry_time as source of truth (broker execution time)
                # Update entry_time to match actual_entry_time
                cursor.execute("""
                    UPDATE trades
                    SET entry_time = actual_entry_time
                    WHERE trade_id = ?
                """, (trade_id,))
                fixes_applied.append(f"Fixed {symbol} ({trade_id}): Aligned entry_time with actual_entry_time (broker execution)")
                print(f"    ✅ FIXED: Set entry_time to broker execution time ({actual_time})")

            print()
    else:
        print("✅ No time mismatches detected")
        print()

    # Check 4: Duplicate fills (same trade_id with entry_filled=1 updated multiple times)
    # This is harder to detect from current data, but we log it in real-time now

    # Commit changes if fixing
    if fix_issues and fixes_applied:
        conn.commit()
        print("=" * 80)
        print(f"✅ {len(fixes_applied)} fixes applied to database")
        print("=" * 80)
        for fix in fixes_applied:
            print(f"  - {fix}")
        print()

    conn.close()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total issues found: {len(issues_found)}")

    if issues_found:
        print()
        print("Issues by type:")
        issue_types = {}
        for issue in issues_found:
            issue_type = issue['type']
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

        for issue_type, count in issue_types.items():
            print(f"  - {issue_type}: {count}")

    if fix_issues:
        print(f"\nFixes applied: {len(fixes_applied)}")
    else:
        print("\nℹ️  Run with --fix flag to automatically fix issues")

    print("=" * 80)

    return len(issues_found)

if __name__ == "__main__":
    fix_mode = "--fix" in sys.argv

    if fix_mode:
        print("⚠️  FIX MODE ENABLED - Issues will be automatically corrected")
        print()

    issue_count = check_data_integrity(fix_issues=fix_mode)

    # Exit code: 0 if no issues, 1 if issues found
    sys.exit(0 if issue_count == 0 else 1)
