#!/usr/bin/env python3
"""
Close All Open Positions - Emergency Manual Close
Used after swing transition timing fix to close positions that weren't evaluated
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def close_all_open_positions(db_path: str = "trading_data.db", dry_run: bool = True):
    """Close specific positions that were affected by old swing transition timing"""

    print("=" * 80)
    print("🔴 Manual Close - Positions Affected by Old Timing")
    print("=" * 80)
    print("Closing: LEE, SIDU, ULY (not evaluated due to old 15:30 ET timing)")
    print()

    if dry_run:
        print("⚠️  DRY RUN - No changes will be made\n")
    else:
        print("🔴 EXECUTE MODE - Positions WILL be closed!\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get specific positions to close
    symbols_to_close = ['LEE', 'SIDU', 'ULY']

    cursor.execute(f"""
        SELECT id, trade_id, symbol, side, entry_price, entry_time,
               stop_loss_price, take_profit_price
        FROM trades
        WHERE status='OPEN'
        AND symbol IN ({','.join('?' * len(symbols_to_close))})
        ORDER BY entry_time DESC
    """, symbols_to_close)

    open_trades = cursor.fetchall()

    if not open_trades:
        print("✅ No open positions to close")
        conn.close()
        return

    print(f"📊 Found {len(open_trades)} open positions:\n")

    for trade in open_trades:
        entry_time = trade['entry_time'][:19] if trade['entry_time'] else 'N/A'
        print(f"   {trade['symbol']:6} | {trade['side']:5} | ${trade['entry_price']:.2f} | {entry_time}")

    print()

    if dry_run:
        print("⚠️  DRY RUN - To actually close positions, run with --execute")
        conn.close()
        return

    # Close all positions
    close_time = datetime.now().isoformat()
    close_reason = "MANUAL_CLOSE - After swing transition timing fix"

    for trade in open_trades:
        symbol = trade['symbol']
        trade_id = trade['trade_id']
        entry_price = trade['entry_price']

        # Use entry price as exit price (0% PnL - simulate immediate close)
        # In real system, you'd fetch current market price
        exit_price = entry_price
        pnl = 0.0

        cursor.execute("""
            UPDATE trades
            SET status = 'CLOSED',
                exit_time = ?,
                exit_price = ?,
                pnl = ?,
                exit_reason_detailed = ?
            WHERE id = ?
        """, (close_time, exit_price, pnl, close_reason, trade['id']))

        print(f"✅ Closed {symbol} ({trade_id}) @ ${exit_price:.2f} | PnL: ${pnl:.2f}")

    conn.commit()

    print()
    print(f"✅ Successfully closed {len(open_trades)} positions")
    print(f"   Close time: {close_time[:19]}")
    print(f"   Reason: {close_reason}")

    conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Close all open positions manually")
    parser.add_argument('--execute', action='store_true',
                       help='Actually close positions (default is dry-run)')
    parser.add_argument('--db', default='trading_data.db',
                       help='Database path')

    args = parser.parse_args()

    close_all_open_positions(args.db, dry_run=not args.execute)

    print("=" * 80)


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
