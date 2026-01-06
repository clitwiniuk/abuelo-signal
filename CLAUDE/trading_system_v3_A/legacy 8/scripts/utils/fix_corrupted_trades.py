#!/usr/bin/env python3
"""
Fix corrupted trades: AMST (1000006) and BITF (1000003)
"""

import sqlite3
import time
from datetime import datetime

DB_PATH = "trading_data.db"
MAX_RETRIES = 10
RETRY_DELAY = 2

def execute_with_retry(query, params=None, max_retries=MAX_RETRIES):
    """Execute query with retry logic for locked database"""
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            conn.commit()
            result = cursor.fetchall()
            conn.close()
            return result

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"⏳ Database locked, retrying in {RETRY_DELAY}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(RETRY_DELAY)
            else:
                raise
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

def main():
    print("=" * 80)
    print("FIXING CORRUPTED TRADES")
    print("=" * 80)

    # Fix 1: Close AMST (unfilled order)
    print("\n📋 Fix 1: Closing AMST (1000006) - unfilled order")
    print("-" * 80)

    query_amst = """
    UPDATE trades
    SET status = 'CLOSED',
        actual_pnl = -0.35,
        exit_time = ?,
        exit_filled = 0,
        notes = 'Order never filled - probable broker rejection. Closed administratively with commission-only loss.'
    WHERE trade_id = '1000006'
    """

    try:
        execute_with_retry(query_amst, (datetime.now().isoformat(),))
        print("✅ AMST (1000006) closed successfully")

        # Verify
        result = execute_with_retry("SELECT trade_id, symbol, status, actual_pnl, notes FROM trades WHERE trade_id = '1000006'")
        if result:
            trade_id, symbol, status, pnl, notes = result[0]
            print(f"   Trade ID: {trade_id}")
            print(f"   Symbol: {symbol}")
            print(f"   Status: {status}")
            print(f"   P&L: ${pnl}")
            print(f"   Notes: {notes[:80]}...")
    except Exception as e:
        print(f"❌ Failed to close AMST: {e}")
        return False

    # Fix 2: Correct BITF entry price
    print("\n📋 Fix 2: Correcting BITF (1000003) entry price")
    print("-" * 80)

    # First check current values
    result = execute_with_retry("""
        SELECT actual_entry_price, actual_exit_price, quantity, actual_pnl
        FROM trades WHERE trade_id = '1000003'
    """)

    if result:
        old_entry, exit_price, quantity, old_pnl = result[0]
        print(f"   Current entry price: ${old_entry}")
        print(f"   Exit price: ${exit_price}")
        print(f"   Quantity: {quantity}")
        print(f"   Current P&L: ${old_pnl}")

        # Calculate correct P&L
        correct_entry = 2.494
        correct_pnl = (exit_price - correct_entry) * quantity if exit_price else old_pnl

        print(f"\n   Corrected entry price: ${correct_entry}")
        print(f"   Corrected P&L: ${correct_pnl:.2f}")

        query_bitf = """
        UPDATE trades
        SET actual_entry_price = ?,
            actual_pnl = ?,
            notes = COALESCE(notes || ' | ', '') || 'Entry price corrected from corrupted value $' || ? || ' to correct value $' || ?
        WHERE trade_id = '1000003'
        """

        try:
            execute_with_retry(query_bitf, (correct_entry, correct_pnl, old_entry, correct_entry))
            print("✅ BITF (1000003) corrected successfully")

            # Verify
            result = execute_with_retry("SELECT trade_id, symbol, actual_entry_price, actual_pnl FROM trades WHERE trade_id = '1000003'")
            if result:
                trade_id, symbol, entry, pnl = result[0]
                print(f"   Trade ID: {trade_id}")
                print(f"   Symbol: {symbol}")
                print(f"   Entry Price: ${entry}")
                print(f"   P&L: ${pnl:.2f}")
        except Exception as e:
            print(f"❌ Failed to correct BITF: {e}")
            return False

    print("\n" + "=" * 80)
    print("✅ ALL FIXES APPLIED SUCCESSFULLY")
    print("=" * 80)

    # Summary
    print("\n📊 Summary of changes:")
    result = execute_with_retry("""
        SELECT trade_id, symbol, status, actual_entry_price, actual_pnl
        FROM trades
        WHERE trade_id IN ('1000003', '1000006')
        ORDER BY trade_id
    """)

    print("\n| Trade ID | Symbol | Status | Entry Price | P&L |")
    print("|----------|--------|--------|-------------|-----|")
    for row in result:
        trade_id, symbol, status, entry, pnl = row
        entry_str = f"${entry:.2f}" if entry else "N/A"
        pnl_str = f"${pnl:.2f}" if pnl else "$0.00"
        print(f"| {trade_id} | {symbol} | {status} | {entry_str} | {pnl_str} |")

    print("\n✅ Database fixes complete. You can now refresh the dashboard.")
    return True

if __name__ == "__main__":
    main()
