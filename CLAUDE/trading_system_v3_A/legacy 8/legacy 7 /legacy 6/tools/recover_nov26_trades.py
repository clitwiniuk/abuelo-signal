#!/usr/bin/env python3
"""
Recover Lost Trades from November 26, 2025
==========================================
This script recovers trades that failed to save due to SQL column mismatch bug.
It parses the trader.log file and reconstructs trades from execDetails entries.
"""

import re
import sqlite3
from datetime import datetime
from collections import defaultdict
import uuid

def parse_execution(line):
    """Parse execDetails line from trader.log"""
    # Example: execDetails Execution(execId='0000e0d5.6927859a.01.01', time=datetime.datetime(2025, 11, 26, 18, 36, 30, tzinfo=datetime.timezone.utc), acctNumber='DUA998722', exchange='BYX', side='BOT', shares=67.0, price=2.95, permId=2132345901, clientId=6000, orderId=169255, liquidation=0, cumQty=67.0, avgPrice=2.95, orderRef='', evRule='', evMultiplier=0.0, modelCode='', lastLiquidity=2)

    match = re.search(r"time=datetime\.datetime\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+)", line)
    if not match:
        return None

    year, month, day, hour, minute, second = map(int, match.groups())
    exec_time = datetime(year, month, day, hour, minute, second)

    # Extract side
    side_match = re.search(r"side='(BOT|SLD)'", line)
    side = side_match.group(1) if side_match else None

    # Extract shares
    shares_match = re.search(r"shares=([\d.]+)", line)
    shares = float(shares_match.group(1)) if shares_match else None

    # Extract price
    price_match = re.search(r"price=([\d.]+)", line)
    price = float(price_match.group(1)) if price_match else None

    # Extract permId (unique identifier for the position)
    perm_match = re.search(r"permId=(\d+)", line)
    perm_id = perm_match.group(1) if perm_match else None

    return {
        'time': exec_time,
        'side': side,
        'shares': int(shares) if shares else None,
        'price': price,
        'perm_id': perm_id
    }


def find_symbol_for_execution(log_file, exec_time):
    """Find the symbol for an execution by looking at recent log entries"""
    # Look for entries/exits around that time
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Find lines around the execution time
    time_str = exec_time.strftime('%Y-%m-%d %H:%M')
    relevant_lines = [l for l in lines if time_str in l]

    # Look for symbol mentions in signal processing
    for line in relevant_lines:
        # Match patterns like "MBOT routing", "processing MBOT", etc.
        symbol_match = re.search(r'\b([A-Z]{2,5})\b.*(?:routing|processing|Entry|Exit)', line)
        if symbol_match:
            return symbol_match.group(1)

    return None


def match_executions_to_trades(executions):
    """Match buy and sell executions to form complete trades"""
    # Group by permId
    by_perm = defaultdict(list)
    for exec in executions:
        if exec['perm_id']:
            by_perm[exec['perm_id']].append(exec)

    trades = []

    for perm_id, execs in by_perm.items():
        # Separate buys and sells
        buys = [e for e in execs if e['side'] == 'BOT']
        sells = [e for e in execs if e['side'] == 'SLD']

        if not buys or not sells:
            continue

        # Match them (simple: first buy with first sell)
        for buy, sell in zip(buys, sells):
            pnl = (sell['price'] - buy['price']) * buy['shares']
            # Rough commission estimate: $1 per trade side
            commission = 2.0
            net_pnl = pnl - commission

            duration = (sell['time'] - buy['time']).total_seconds() / 60.0

            trades.append({
                'entry_time': buy['time'],
                'exit_time': sell['time'],
                'entry_price': buy['price'],
                'exit_price': sell['price'],
                'quantity': buy['shares'],
                'pnl': net_pnl,
                'commission': commission,
                'duration_minutes': int(duration),
                'perm_id': perm_id
            })

    return trades


def main():
    print("=" * 60)
    print("RECOVERING LOST TRADES FROM NOVEMBER 26, 2025")
    print("=" * 60)

    log_file = "logs/trader.log"
    db_path = "trading_data.db"

    # Parse executions from log
    print("\n📖 Parsing trader.log for executions...")
    executions = []

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '2025-11-26' in line and 'execDetails Execution' in line:
                exec_data = parse_execution(line)
                if exec_data:
                    executions.append(exec_data)

    print(f"✅ Found {len(executions)} executions")

    # Match executions to trades
    print("\n🔗 Matching executions to complete trades...")
    trades = match_executions_to_trades(executions)
    print(f"✅ Matched {len(trades)} complete trades")

    if not trades:
        print("\n⚠️  No complete trades found to recover")
        return

    # Get symbol mapping from commissionReport entries
    print("\n🔍 Looking for symbols in log...")
    symbol_map = {}

    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '2025-11-26' in line and 'commissionReport' in line:
                # Try to extract execId and match to symbols from updatePortfolio
                pass

    # Manual symbol mapping based on log analysis
    # From the logs we saw: SMX (realizedPNL=8.01)
    # We need to map permIds to symbols - let's use a heuristic
    print("\n📝 Assigning symbols to trades...")

    # Get symbols from updatePortfolio entries
    portfolio_symbols = set()
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '2025-11-26' in line and 'updatePortfolio' in line:
                symbol_match = re.search(r"symbol='([A-Z]+)'", line)
                if symbol_match:
                    portfolio_symbols.add(symbol_match.group(1))

    print(f"   Found symbols in portfolio: {', '.join(sorted(portfolio_symbols))}")

    # Assign symbols to trades (need manual mapping or better heuristic)
    # For now, we'll use 'UNKNOWN' and let user correct manually
    for trade in trades:
        trade['symbol'] = 'UNKNOWN'  # Will need manual correction
        trade['strategy'] = 'recovered_nov26'
        trade['side'] = 'LONG'
        trade['status'] = 'CLOSED'
        trade['notes'] = f'Recovered from Nov 26 logs (permId: {trade["perm_id"]})'
        trade['trade_id'] = str(uuid.uuid4())

    # Show trades for review
    print("\n📊 RECOVERED TRADES:")
    print("-" * 60)
    for i, trade in enumerate(trades, 1):
        print(f"\nTrade {i}:")
        print(f"  Entry:    {trade['entry_time']} @ ${trade['entry_price']:.2f}")
        print(f"  Exit:     {trade['exit_time']} @ ${trade['exit_price']:.2f}")
        print(f"  Quantity: {trade['quantity']} shares")
        print(f"  Duration: {trade['duration_minutes']} minutes")
        print(f"  P&L:      ${trade['pnl']:.2f}")
        print(f"  PermID:   {trade['perm_id']}")

    # Ask for confirmation
    print("\n" + "=" * 60)
    response = input("\n💾 Save these trades to database? (yes/no): ").strip().lower()

    if response != 'yes':
        print("❌ Aborted. No trades saved.")
        return

    # Save to database
    print("\n💾 Saving trades to database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    saved_count = 0
    for trade in trades:
        try:
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, strategy, side, quantity, entry_price,
                    exit_price, entry_time, exit_time, duration_minutes,
                    pnl, commission, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['trade_id'], trade['symbol'], trade['strategy'],
                trade['side'], trade['quantity'], trade['entry_price'],
                trade['exit_price'], trade['entry_time'].isoformat(),
                trade['exit_time'].isoformat(), trade['duration_minutes'],
                trade['pnl'], trade['commission'], trade['status'], trade['notes']
            ))
            saved_count += 1
        except Exception as e:
            print(f"   ❌ Error saving trade {trade['trade_id']}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ Successfully saved {saved_count}/{len(trades)} trades")
    print("\n⚠️  NOTE: Symbols are set to 'UNKNOWN'. Please update them manually:")
    print("   1. Check the trader.log around each execution time")
    print("   2. Update symbols in database with:")
    print("      UPDATE trades SET symbol='SYMBOL' WHERE trade_id='...'")
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
