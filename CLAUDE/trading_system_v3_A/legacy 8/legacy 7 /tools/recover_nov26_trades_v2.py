#!/usr/bin/env python3
"""
Recover Lost Trades from November 26, 2025 - Version 2
======================================================
Manually reconstructed from trader.log analysis with exact symbols and P&L.
"""

import sqlite3
import uuid
from datetime import datetime

# Trades reconstructed from log analysis
TRADES = [
    {
        'symbol': 'SMX',  # From commissionReport realizedPNL=8.01
        'entry_time': '2025-11-26 19:39:36',
        'exit_time': '2025-11-26 19:45:53',
        'entry_price': 10.26,
        'exit_price': 11.03,
        'quantity': 13,
        'commission': 2.0027,  # 1.000286 + 1.002444
        'realized_pnl': 8.00727,  # From commissionReport
    },
    {
        'symbol': 'BITF',
        'entry_time': '2025-11-26 18:36:30',
        'exit_time': '2025-11-26 20:58:03',
        'entry_price': 2.95,
        'exit_price': 3.08,
        'quantity': 67,
        'commission': 2.01407,  # 1.001474 + 1.012596
        'realized_pnl': 6.69593,  # From commissionReport
    },
    {
        'symbol': 'BTBT',
        'entry_time': '2025-11-26 19:46:58',
        'exit_time': '2025-11-26 20:58:03',
        'entry_price': 2.34,
        'exit_price': 2.31,
        'quantity': 85,
        'commission': 2.01785,  # 1.00187 + 1.01598
        'realized_pnl': -4.56785,  # From commissionReport
    },
    {
        'symbol': 'NVTS',
        'entry_time': '2025-11-26 20:03:24',
        'exit_time': '2025-11-26 20:58:05',
        'entry_price': 8.6,
        'exit_price': 8.36,
        'quantity': 23,
        'commission': 2.00483,  # 1.000506 + 1.004324
        'realized_pnl': -7.52483,  # From commissionReport
    },
    {
        'symbol': 'MBOT',
        'entry_time': '2025-11-26 20:22:41',
        'exit_time': '2025-11-26 20:58:00',
        'entry_price': 2.32,
        'exit_price': 2.30,
        'quantity': 86,
        'commission': 2.01806,  # 1.001892 + 1.016168
        'realized_pnl': -3.73806,  # From commissionReport
    },
]


def calculate_duration(entry_time, exit_time):
    """Calculate trade duration in minutes"""
    entry = datetime.fromisoformat(entry_time)
    exit = datetime.fromisoformat(exit_time)
    return int((exit - entry).total_seconds() / 60)


def main():
    print("=" * 70)
    print("RECOVERING LOST TRADES FROM NOVEMBER 26, 2025")
    print("=" * 70)

    db_path = "trading_data.db"

    print(f"\n📊 Found {len(TRADES)} complete trades to recover:\n")

    total_pnl = 0
    for i, trade in enumerate(TRADES, 1):
        duration = calculate_duration(trade['entry_time'], trade['exit_time'])
        total_pnl += trade['realized_pnl']

        print(f"Trade {i}: {trade['symbol']}")
        print(f"  Entry:    {trade['entry_time']} @ ${trade['entry_price']:.2f}")
        print(f"  Exit:     {trade['exit_time']} @ ${trade['exit_price']:.2f}")
        print(f"  Quantity: {trade['quantity']} shares")
        print(f"  Duration: {duration} minutes")
        print(f"  P&L:      ${trade['realized_pnl']:.2f} (net)")
        print(f"  Comm:     ${trade['commission']:.2f}")
        print()

    print("-" * 70)
    print(f"Total P&L: ${total_pnl:.2f}")
    print("-" * 70)

    # Ask for confirmation
    response = input("\n💾 Save these trades to database? (yes/no): ").strip().lower()

    if response != 'yes':
        print("❌ Aborted. No trades saved.")
        return

    # Save to database
    print("\n💾 Saving trades to database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    saved_count = 0
    for trade in TRADES:
        try:
            trade_id = str(uuid.uuid4())
            duration = calculate_duration(trade['entry_time'], trade['exit_time'])

            # Determine strategy based on duration
            if duration < 60:
                strategy = 'scalp_recovered'
            elif duration < 240:
                strategy = 'momentum_recovered'
            else:
                strategy = 'swing_recovered'

            cursor.execute("""
                INSERT INTO trades (
                    trade_id, symbol, strategy, side, quantity, entry_price,
                    exit_price, entry_time, exit_time, duration_minutes,
                    pnl, commission, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                trade['symbol'],
                strategy,
                'LONG',
                trade['quantity'],
                trade['entry_price'],
                trade['exit_price'],
                trade['entry_time'],
                trade['exit_time'],
                duration,
                trade['realized_pnl'],
                trade['commission'],
                'CLOSED',
                'Recovered from Nov 26, 2025 logs - SQL bug fixed'
            ))

            saved_count += 1
            print(f"  ✅ Saved {trade['symbol']}: ${trade['realized_pnl']:.2f}")

        except Exception as e:
            print(f"  ❌ Error saving {trade['symbol']}: {e}")

    conn.commit()
    conn.close()

    print(f"\n✅ Successfully saved {saved_count}/{len(TRADES)} trades")
    print("\n" + "=" * 70)
    print("RECOVERY COMPLETE!")
    print("=" * 70)
    print("\nThese trades are now available in TradeTally.")
    print("The autosync service will pick them up automatically.\n")


if __name__ == '__main__':
    main()
