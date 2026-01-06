#!/usr/bin/env python3
"""
Daily Plays Worker v2.0 - Multi-Date Regression Testing

Tests the refactored daily_plays worker across multiple dates to validate consistency
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def get_test_data():
    """
    Returns test dates and symbols
    """
    return [
        {
            'date': '2025-12-03',
            'symbols': ['ARBE', 'ARTL', 'AUR', 'BTBT', 'CGC', 'JBLU', 'MSTX', 'NVD', 'POET', 'QCLS', 'RR', 'TSLG'],
            'description': 'Most recent trading day (12 symbols)'
        },
        {
            'date': '2025-11-28',
            'symbols': ['ABVE', 'BITF', 'BTBT', 'CRCG', 'HIVE', 'IBRX', 'NVD', 'TMC', 'VEEE'],
            'description': 'Good catalyst activity (9 symbols)'
        },
        {
            'date': '2025-11-21',
            'symbols': ['DVLT', 'ESPR', 'FOXX', 'IONZ', 'IVDA', 'MSTX', 'NVD', 'PACB'],
            'description': 'Mid-volume day (8 symbols)'
        },
        {
            'date': '2025-11-20',
            'symbols': ['BITF', 'CYPH', 'IONZ', 'MNDR', 'NVD', 'PLTD', 'PLTZ', 'RZLV', 'SGBX'],
            'description': 'Diverse tickers (9 symbols)'
        }
    ]


def run_test(date, symbols, description):
    """Run test for a single date"""
    print(f"\n{'='*80}")
    print(f"📅 TESTING: {date} - {description}")
    print(f"{'='*80}\n")
    print(f"📊 Symbols ({len(symbols)}): {', '.join(symbols)}")
    print()

    # Initialize ReplayEngine
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    # Run replay
    session = engine.replay_day(
        date=date,
        worker_names=['daily_plays'],
        symbols=symbols
    )

    # Calculate metrics
    approved = session.entries_approved
    rejected = session.entries_rejected
    total = approved + rejected
    exec_rate = (approved / total * 100) if total > 0 else 0

    simulated_trades = session.simulated_trades

    # Calculate performance
    wins = [t for t in simulated_trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in simulated_trades if t.get('pnl_pct', 0) < 0]

    win_rate = (len(wins) / len(simulated_trades) * 100) if simulated_trades else 0
    avg_win = sum(t.get('pnl_pct', 0) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get('pnl_pct', 0) for t in losses) / len(losses) if losses else 0
    total_pnl = sum(t.get('pnl_pct', 0) for t in simulated_trades)

    gross_profit = sum(t.get('pnl_pct', 0) for t in wins) if wins else 0
    gross_loss = abs(sum(t.get('pnl_pct', 0) for t in losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    # Print summary
    print(f"\n📊 RESULTS:")
    print(f"   Coverage:      {approved}/{len(symbols)} symbols ({(approved/len(symbols)*100):.0f}%)")
    print(f"   Exec Rate:     {exec_rate:.1f}% ({approved}/{total} evaluations)")
    print(f"   Trades:        {len(simulated_trades)}")
    print(f"   Win Rate:      {win_rate:.1f}% ({len(wins)}W/{len(losses)}L)")
    print(f"   Avg Win:       +{avg_win:.2f}%")
    print(f"   Avg Loss:      {avg_loss:.2f}%")
    print(f"   Total P&L:     {total_pnl:+.2f}%")
    print(f"   Profit Factor: {profit_factor:.2f}")

    # Check for duplicates
    symbol_trades = {}
    for trade in simulated_trades:
        symbol = trade.get('symbol', 'UNKNOWN')
        if symbol not in symbol_trades:
            symbol_trades[symbol] = []
        symbol_trades[symbol].append(trade)

    duplicates = {s: trades for s, trades in symbol_trades.items() if len(trades) > 1}
    if duplicates:
        print(f"   Anti-overtrade: ❌ FAILED ({len(duplicates)} duplicates)")
    else:
        print(f"   Anti-overtrade: ✅ PASSED")

    # Status
    status = "✅ PASS" if win_rate >= 35 and not duplicates else "⚠️ CHECK" if win_rate >= 25 else "❌ FAIL"
    print(f"\n   Status: {status}")

    return {
        'date': date,
        'symbols_count': len(symbols),
        'coverage': approved / len(symbols) * 100,
        'exec_rate': exec_rate,
        'trades': len(simulated_trades),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_pnl': total_pnl,
        'profit_factor': profit_factor,
        'has_duplicates': len(duplicates) > 0,
        'status': status
    }


def main():
    print("\n" + "="*80)
    print("🧪 DAILY PLAYS WORKER v2.0 - MULTI-DATE REGRESSION TEST")
    print("="*80 + "\n")

    test_data = get_test_data()
    results = []

    for test in test_data:
        result = run_test(test['date'], test['symbols'], test['description'])
        results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("📊 AGGREGATE RESULTS")
    print(f"{'='*80}\n")

    total_symbols = sum(r['symbols_count'] for r in results)
    total_trades = sum(r['trades'] for r in results)
    avg_coverage = sum(r['coverage'] for r in results) / len(results)
    avg_win_rate = sum(r['win_rate'] for r in results) / len(results)
    avg_pnl = sum(r['total_pnl'] for r in results) / len(results)
    passed_count = sum(1 for r in results if '✅' in r['status'])

    print(f"📈 Overall Statistics:")
    print(f"   Dates Tested:     {len(results)}")
    print(f"   Total Symbols:    {total_symbols}")
    print(f"   Total Trades:     {total_trades}")
    print(f"   Avg Coverage:     {avg_coverage:.1f}%")
    print(f"   Avg Win Rate:     {avg_win_rate:.1f}%")
    print(f"   Avg P&L per Day:  {avg_pnl:+.2f}%")
    print(f"   Tests Passed:     {passed_count}/{len(results)}")
    print()

    # Per-date summary table
    print(f"📊 Date-by-Date Summary:")
    print(f"{'Date':<12} {'Symbols':<8} {'Trades':<7} {'Win%':<8} {'P&L':<10} {'Status':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['date']:<12} {r['symbols_count']:<8} {r['trades']:<7} {r['win_rate']:<7.1f}% {r['total_pnl']:+<9.2f}% {r['status']:<10}")
    print()

    # Final verdict
    print(f"{'='*80}")
    print("🎯 FINAL VERDICT")
    print(f"{'='*80}\n")

    if passed_count == len(results) and avg_win_rate >= 40:
        print("✅ EXCELLENT: All tests passed with strong win rate")
        print(f"   - Avg Win Rate: {avg_win_rate:.1f}% (target: 50-60%)")
        print(f"   - Avg Coverage: {avg_coverage:.1f}%")
        print(f"   - No duplicates detected")
        print()
        print("   ✅ Worker v2.0 is consistent and ready for paper trading")
    elif passed_count >= len(results) * 0.75:
        print("⚠️ GOOD: Most tests passed but needs monitoring")
        print(f"   - Tests Passed: {passed_count}/{len(results)}")
        print(f"   - Avg Win Rate: {avg_win_rate:.1f}%")
        print()
        print("   Recommendation: Monitor paper trading closely")
    else:
        print("❌ NEEDS WORK: Performance inconsistent")
        print(f"   - Tests Passed: {passed_count}/{len(results)}")
        print(f"   - Avg Win Rate: {avg_win_rate:.1f}%")
        print()
        print("   Recommendation: Review filter settings and test with more dates")

    print()
    print("="*80)
    print("✅ MULTI-DATE REGRESSION TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
