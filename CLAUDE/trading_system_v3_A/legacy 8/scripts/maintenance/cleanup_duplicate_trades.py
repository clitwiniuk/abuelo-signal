#!/usr/bin/env python3
"""
Trade Duplicates Cleanup Tool
Identifies and removes true duplicate trades (same symbol, entry_time, entry_price)
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def analyze_trade_duplicates(db_path: str = "trading_data.db"):
    """Analyze trades for duplicates"""

    print("=" * 80)
    print("🔍 Trade Duplicates Analysis")
    print("=" * 80)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get total trades
    cursor.execute("SELECT COUNT(*) FROM trades")
    total_trades = cursor.fetchone()[0]
    print(f"\n📊 Total trades: {total_trades}")

    # Find exact duplicates (same symbol, entry_time, entry_price)
    cursor.execute("""
        SELECT
            symbol,
            entry_time,
            entry_price,
            COUNT(*) as count,
            GROUP_CONCAT(id) as ids,
            GROUP_CONCAT(trade_id) as trade_ids
        FROM trades
        GROUP BY symbol, entry_time, entry_price
        HAVING count > 1
        ORDER BY count DESC, symbol
    """)

    exact_duplicates = cursor.fetchall()

    if exact_duplicates:
        print(f"\n❌ Found {len(exact_duplicates)} groups of EXACT duplicates:")
        print(f"   (same symbol + entry_time + entry_price)")
        print()

        for dup in exact_duplicates:
            ids = dup['ids'].split(',')
            trade_ids = dup['trade_ids'].split(',')

            print(f"   {dup['symbol']} @ ${dup['entry_price']} on {dup['entry_time']}")
            print(f"   Count: {dup['count']} duplicates")
            print(f"   IDs: {ids}")
            print(f"   Trade IDs: {trade_ids[:3]}..." if len(trade_ids) > 3 else f"   Trade IDs: {trade_ids}")

            # Show details of each duplicate
            for id_val in ids:
                cursor.execute("""
                    SELECT id, trade_id, status, exit_time, exit_price, pnl
                    FROM trades WHERE id = ?
                """, (id_val,))
                detail = cursor.fetchone()

                status = detail['status']
                exit_info = ""
                if detail['exit_time']:
                    exit_info = f", exited @ ${detail['exit_price']} on {detail['exit_time'][:19]}"
                pnl_info = f", PnL: ${detail['pnl']:.2f}" if detail['pnl'] else ""

                print(f"      - ID {detail['id']}: {detail['trade_id']} ({status}{exit_info}{pnl_info})")
            print()
    else:
        print("\n✅ No exact duplicates found!")

    # Check for near-duplicates (same symbol, similar entry_time within 1 second)
    print("\n🔍 Checking for near-duplicates (within 1 second)...")

    cursor.execute("""
        SELECT
            t1.id as id1,
            t1.trade_id as trade_id1,
            t1.symbol,
            t1.entry_time as time1,
            t1.entry_price as price1,
            t1.status as status1,
            t2.id as id2,
            t2.trade_id as trade_id2,
            t2.entry_time as time2,
            t2.entry_price as price2,
            t2.status as status2
        FROM trades t1
        INNER JOIN trades t2 ON t1.symbol = t2.symbol
            AND t1.id < t2.id
            AND ABS(CAST((julianday(t1.entry_time) - julianday(t2.entry_time)) * 86400 AS INTEGER)) <= 1
            AND ABS(t1.entry_price - t2.entry_price) < 0.01
        ORDER BY t1.symbol, t1.entry_time
    """)

    near_duplicates = cursor.fetchall()

    if near_duplicates:
        print(f"\n⚠️  Found {len(near_duplicates)} pairs of near-duplicates:")
        for dup in near_duplicates[:20]:  # Show first 20
            time_diff = abs((datetime.fromisoformat(dup['time1']) - datetime.fromisoformat(dup['time2'])).total_seconds())
            print(f"\n   {dup['symbol']}")
            print(f"      Trade 1: ID {dup['id1']} ({dup['trade_id1']}) @ ${dup['price1']} - {dup['status1']}")
            print(f"      Trade 2: ID {dup['id2']} ({dup['trade_id2']}) @ ${dup['price2']} - {dup['status2']}")
            print(f"      Time diff: {time_diff:.1f} seconds")
    else:
        print("   ✅ No near-duplicates found")

    # Check split trades
    cursor.execute("""
        SELECT COUNT(*) FROM trades WHERE trade_id LIKE '%_split_%'
    """)
    split_count = cursor.fetchone()[0]

    if split_count > 0:
        print(f"\n📌 Note: {split_count} split trades found (these are intentional, not duplicates)")

    # Summary
    print("\n" + "=" * 80)
    print("📋 Summary")
    print("=" * 80)
    print(f"Total trades: {total_trades}")
    print(f"Exact duplicates: {len(exact_duplicates)} groups")
    print(f"Near duplicates: {len(near_duplicates)} pairs")
    print(f"Split trades: {split_count} (intentional)")

    conn.close()

    return exact_duplicates, near_duplicates


def cleanup_exact_duplicates(db_path: str = "trading_data.db", dry_run: bool = True):
    """
    Remove exact duplicate trades
    Strategy: Keep the trade with the LOWEST id (oldest), remove others
    """

    print("\n" + "=" * 80)
    print("🧹 Cleaning Exact Duplicates")
    print("=" * 80)

    if dry_run:
        print("⚠️  DRY RUN - No data will be deleted\n")
    else:
        print("🔴 EXECUTE MODE - Data WILL be deleted!\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find duplicates
    cursor.execute("""
        SELECT
            symbol,
            entry_time,
            entry_price,
            GROUP_CONCAT(id ORDER BY id) as ids
        FROM trades
        GROUP BY symbol, entry_time, entry_price
        HAVING COUNT(*) > 1
    """)

    duplicates = cursor.fetchall()

    if not duplicates:
        print("✅ No exact duplicates to clean")
        conn.close()
        return

    total_to_delete = 0
    ids_to_delete = []

    for dup in duplicates:
        ids = [int(x) for x in dup[3].split(',')]
        # Keep first (lowest) id, delete rest
        to_delete = ids[1:]
        total_to_delete += len(to_delete)
        ids_to_delete.extend(to_delete)

        print(f"   {dup[0]} @ ${dup[1]} on {dup[2]}")
        print(f"      Keeping ID: {ids[0]}")
        print(f"      Deleting IDs: {to_delete}")

    print(f"\n📊 Total trades to delete: {total_to_delete}")

    if dry_run:
        print("   ⚠️  DRY RUN - No data deleted")
    else:
        # Delete duplicates
        placeholders = ','.join('?' * len(ids_to_delete))
        cursor.execute(f"DELETE FROM trades WHERE id IN ({placeholders})", ids_to_delete)

        conn.commit()
        print(f"   ✅ Deleted {cursor.rowcount} duplicate trades")

    conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze and clean duplicate trades")
    parser.add_argument('--execute', action='store_true', help='Actually delete duplicates (default is dry-run)')
    parser.add_argument('--db', default='trading_data.db', help='Database path')

    args = parser.parse_args()

    # Analyze
    exact_dups, near_dups = analyze_trade_duplicates(args.db)

    # If duplicates found, offer cleanup
    if exact_dups:
        print("\n" + "=" * 80)

        if args.execute:
            cleanup_exact_duplicates(args.db, dry_run=False)
        else:
            print("\n💡 To remove exact duplicates, run:")
            print(f"   python {sys.argv[0]} --execute")
            print("\n   This will keep the oldest trade and delete newer duplicates.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
