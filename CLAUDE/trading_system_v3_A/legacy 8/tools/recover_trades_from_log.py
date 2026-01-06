#!/usr/bin/env python3
"""
Recover Trades from Log
========================

Reads trader.log and recovers trades that weren't saved to the database
due to the "43 values for 42 columns" error.

Usage:
    python tools/recover_trades_from_log.py --date 2025-11-21
"""

import re
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path


def parse_trade_entry(log_lines, index):
    """Parse a trade entry from log lines starting at index."""
    entry_line = log_lines[index]

    # Extract trade info from: "Position opened - SYMBOL @ $PRICE x QUANTITY shares (Trade ID: XXXXX...)"
    match = re.search(r'Position opened - (\w+) @ \$([0-9.]+) x (\d+) shares \(Trade ID: (\d+)', entry_line)
    if not match:
        return None

    symbol = match.group(1)
    entry_price = float(match.group(2))
    quantity = int(match.group(3))
    trade_id = match.group(4)

    # Extract timestamp
    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', entry_line)
    if not time_match:
        return None
    entry_time = time_match.group(1)

    # Extract worker/strategy
    worker_match = re.search(r'(daily_plays|vcp_smallcap|momentum_surge|gap_and_go):', entry_line)
    strategy = worker_match.group(1) if worker_match else 'generic_01'

    # Extract side (scalp, swing, etc)
    side_match = re.search(r'\[(scalp|swing|day)', entry_line)
    trade_type = side_match.group(1) if side_match else 'scalp'

    return {
        'trade_id': trade_id,
        'symbol': symbol,
        'strategy': strategy,
        'side': 'BUY',  # All entries are BUY
        'quantity': quantity,
        'entry_price': entry_price,
        'entry_time': entry_time,
        'status': 'OPEN',
        'trade_type': trade_type
    }


def parse_trade_exit(log_lines, symbol, entry_trade_id):
    """Find the exit for a given symbol after the entry."""
    exit_pattern = rf'Position closed - {symbol}'

    for i, line in enumerate(log_lines):
        if exit_pattern in line and entry_trade_id in str(log_lines[max(0, i-50):i+1]):
            # Found potential exit, extract time
            time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if time_match:
                return {
                    'exit_time': time_match.group(1),
                    'status': 'CLOSED'
                }
    return None


def recover_trades_from_log(log_file, target_date):
    """Recover trades from log file for a specific date."""
    print(f"\n📖 Reading log file: {log_file}")
    print(f"🎯 Target date: {target_date}\n")

    with open(log_file, 'r') as f:
        log_lines = f.readlines()

    trades = []
    date_str = target_date.strftime('%Y-%m-%d')

    # Find all "Position opened" entries for the target date
    for i, line in enumerate(log_lines):
        if date_str in line and 'Position opened' in line:
            trade = parse_trade_entry(log_lines, i)
            if trade:
                # Try to find exit for this trade
                exit_info = parse_trade_exit(log_lines[i:], trade['symbol'], trade['trade_id'])
                if exit_info:
                    trade.update(exit_info)

                trades.append(trade)
                print(f"✅ Found trade: {trade['symbol']} @ ${trade['entry_price']} x {trade['quantity']} "
                      f"({trade['status']}) - ID: {trade['trade_id']}")

    return trades


def insert_trades_into_db(trades, db_path):
    """Insert recovered trades into SQLite database."""
    print(f"\n💾 Inserting {len(trades)} trades into: {db_path}\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0

    for trade in trades:
        try:
            # Check if trade already exists
            cursor.execute("SELECT trade_id FROM trades WHERE trade_id = ?", (trade['trade_id'],))
            if cursor.fetchone():
                print(f"⏭️  Skipped {trade['symbol']} (ID: {trade['trade_id']}) - already exists")
                skipped += 1
                continue

            # Calculate P&L if trade is closed
            pnl = None
            exit_price = None
            if trade['status'] == 'CLOSED':
                # We need exit price - try to get from broker or estimate
                # For now, we'll leave it NULL and user can fill manually
                pass

            # Insert trade with minimal required fields
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, strategy, side, quantity, entry_price,
                    entry_time, exit_time, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                trade['trade_id'],
                trade['symbol'],
                trade['strategy'],
                trade['side'],
                trade['quantity'],
                trade['entry_price'],
                trade['entry_time'],
                trade.get('exit_time'),
                trade['status'],
                f"Recovered from log (2025-11-21) - {trade['trade_type']} trade"
            ))

            print(f"✅ Inserted {trade['symbol']} @ ${trade['entry_price']} x {trade['quantity']} - ID: {trade['trade_id']}")
            inserted += 1

        except sqlite3.Error as e:
            print(f"❌ Error inserting {trade['symbol']}: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\n📊 Summary:")
    print(f"   ✅ Inserted: {inserted}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   📝 Total: {len(trades)}")

    return inserted


def main():
    parser = argparse.ArgumentParser(description='Recover trades from trader.log')
    parser.add_argument('--date', type=str, required=True,
                       help='Date to recover trades from (YYYY-MM-DD)')
    parser.add_argument('--log', type=str,
                       default='logs/trader.log',
                       help='Path to trader.log file')
    parser.add_argument('--db', type=str,
                       default='trading_data.db',
                       help='Path to trading_data.db')

    args = parser.parse_args()

    # Parse date
    try:
        target_date = datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        print(f"❌ Invalid date format: {args.date}. Use YYYY-MM-DD")
        return 1

    # Check if log file exists
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return 1

    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1

    print("=" * 60)
    print("📦 Trade Recovery Tool")
    print("=" * 60)

    # Recover trades from log
    trades = recover_trades_from_log(log_path, target_date)

    if not trades:
        print(f"\n❌ No trades found for {args.date}")
        return 1

    # Insert into database
    inserted = insert_trades_into_db(trades, db_path)

    print(f"\n✅ Recovery complete! {inserted} trades inserted.")
    print(f"💡 Note: Trades marked as CLOSED may need manual exit price entry in TradeTally")

    return 0


if __name__ == '__main__':
    exit(main())
