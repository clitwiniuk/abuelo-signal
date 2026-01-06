#!/usr/bin/env python3
"""
Walkforward Test - Train/Validation Split

Uses existing ReplayEngine infrastructure to test workers on different symbol sets
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def get_symbol_sets_from_trading_data(date='2025-11-18'):
    """
    Get symbols from trading_data.db for the specified date

    Uses real trade data to get symbols that have intraday bars available

    Args:
        date: Date to query (format: 'YYYY-MM-DD')

    Returns:
        training_symbols, validation_symbols (60/40 split)
    """
    import sqlite3

    # Query trading_data.db for symbols with trades on this date
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()

    query = """
        SELECT t.symbol, COUNT(*) as bars
        FROM trades t
        JOIN trade_intraday_bars tib ON t.trade_id = tib.trade_id
        WHERE date(t.entry_time) = ?
        GROUP BY t.symbol
        ORDER BY t.symbol
    """

    cursor.execute(query, (date,))
    results = cursor.fetchall()
    conn.close()

    if not results:
        raise ValueError(f"No symbols found in trading_data.db for date {date}")

    symbols = [row[0] for row in results]

    print(f"📊 Found {len(symbols)} symbols in trading_data.db for {date}:")
    for symbol, bars in results:
        print(f"   - {symbol}: {bars} bars")
    print()

    # Split: 60% training, 40% validation
    # Use deterministic split (no shuffle) for reproducibility
    split_idx = max(1, int(len(symbols) * 0.6))
    training = symbols[:split_idx]
    validation = symbols[split_idx:]

    return training, validation, date


def main():
    print("\n" + "="*80)
    print("🔬 WALKFORWARD VALIDATION - ALL WORKERS")
    print("="*80 + "\n")

    # Get symbol sets from trading_data.db (60/40 split)
    # Using 2025-11-18 which has 11 symbols (more robust than 2025-12-01 with only 4)
    training_symbols, validation_symbols, test_date = get_symbol_sets_from_trading_data(date='2025-11-18')

    print(f"✅ Training Set ({len(training_symbols)} symbols): {', '.join(training_symbols)}")
    print(f"✅ Validation Set ({len(validation_symbols)} symbols): {', '.join(validation_symbols)}\n")

    # Workers to test (all available workers)
    workers = [
        'volume_absorption',
        'momentum_breakout',
        'daily_plays',
        'ods_swing_universal',
        'vcp_smallcap'
    ]

    # Initialize engine
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db',
        verbose=False  # Reduce noise
    )

    results = {}

    # PHASE 1: Training
    print("="*80)
    print("📈 PHASE 1: TRAINING SET")
    print("="*80 + "\n")

    for worker in workers:
        print(f"Testing {worker}...")
        session = engine.replay_day(
            date=test_date,
            worker_names=[worker],
            symbols=training_symbols
        )

        results[f"{worker}_train"] = {
            'approved': session.entries_approved,
            'rejected': session.entries_rejected,
            'trades': len(session.simulated_trades),
            'exec_rate': (session.entries_approved / (session.entries_approved + session.entries_rejected) * 100)
                         if (session.entries_approved + session.entries_rejected) > 0 else 0
        }

        print(f"  Approved: {session.entries_approved}, Rejected: {session.entries_rejected}")
        print(f"  Execution Rate: {results[f'{worker}_train']['exec_rate']:.1f}%")
        print(f"  Simulated Trades: {len(session.simulated_trades)}\n")

    # PHASE 2: Validation
    print("="*80)
    print("📊 PHASE 2: VALIDATION SET (Out-of-Sample)")
    print("="*80 + "\n")

    for worker in workers:
        print(f"Testing {worker}...")
        session = engine.replay_day(
            date=test_date,
            worker_names=[worker],
            symbols=validation_symbols
        )

        results[f"{worker}_val"] = {
            'approved': session.entries_approved,
            'rejected': session.entries_rejected,
            'trades': len(session.simulated_trades),
            'exec_rate': (session.entries_approved / (session.entries_approved + session.entries_rejected) * 100)
                         if (session.entries_approved + session.entries_rejected) > 0 else 0
        }

        print(f"  Approved: {session.entries_approved}, Rejected: {session.entries_rejected}")
        print(f"  Execution Rate: {results[f'{worker}_val']['exec_rate']:.1f}%")
        print(f"  Simulated Trades: {len(session.simulated_trades)}\n")

    # PHASE 3: Comparison
    print("="*80)
    print("📊 TRAIN vs VALIDATION COMPARISON")
    print("="*80 + "\n")

    for worker in workers:
        train = results[f"{worker}_train"]
        val = results[f"{worker}_val"]

        delta = abs(val['exec_rate'] - train['exec_rate'])

        print(f"{worker.upper()}:")
        print(f"  Training:   {train['exec_rate']:>6.1f}% exec ({train['trades']} trades)")
        print(f"  Validation: {val['exec_rate']:>6.1f}% exec ({val['trades']} trades)")
        print(f"  Delta:      {delta:>6.1f}%")

        if delta < 10:
            print(f"  ✅ CONSISTENT - Ready for production")
        elif delta < 20:
            print(f"  ⚠️  CAUTION - Monitor closely")
        else:
            print(f"  ❌ OVERFITTING - Do not use")

        print()

    print("="*80)
    print("✅ WALKFORWARD TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
