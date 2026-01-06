#!/usr/bin/env python3
"""
Volume Absorption Worker - Regression Testing

Tests the volume_absorption worker with the new minimum confidence filter (50%)
to validate if it improves performance compared to real trading results.

Change Applied: Added MIN_PATTERN_COMPLETION = 50.0 filter in should_enter()
Expected Impact: Reject low-quality setups (3 trades on 2025-12-04 with <30% conf lost -19.24%)
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def get_real_trades_summary(date: str, db_path: str = 'trading_data.db'):
    """Get summary of real trades for comparison"""
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN pnl IS NULL THEN 1 ELSE 0 END) as open_trades,
            ROUND(SUM(COALESCE(pnl, 0)), 2) as total_pnl,
            ROUND(AVG(COALESCE(pnl, 0)), 2) as avg_pnl,
            ROUND(AVG(confidence), 2) as avg_conf,
            COUNT(CASE WHEN confidence < 50 THEN 1 END) as low_conf_count,
            ROUND(SUM(CASE WHEN confidence < 50 THEN COALESCE(pnl, 0) ELSE 0 END), 2) as low_conf_pnl
        FROM trades
        WHERE DATE(entry_time) = ?
        AND (strategy = 'volume_absorption' OR worker_name = 'volume_absorption')
        AND (deleted = 0 OR deleted IS NULL)
    """

    cursor.execute(query, (date,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'total': row[0],
            'wins': row[1],
            'losses': row[2],
            'open_trades': row[3],
            'total_pnl': row[4],
            'avg_pnl': row[5],
            'avg_conf': row[6],
            'low_conf_count': row[7],
            'low_conf_pnl': row[8]
        }
    return None


def run_test(date, symbols, description):
    """Run regression test for a single date"""
    print(f"\n{'='*80}")
    print(f"📅 TESTING: {date} - {description}")
    print(f"{'='*80}\n")
    print(f"📊 Symbols ({len(symbols)}): {', '.join(symbols)}")
    print()

    # Get real trades summary
    print("📊 REAL TRADING RESULTS:")
    real_summary = get_real_trades_summary(date)
    if real_summary:
        closed_trades = real_summary['total'] - real_summary['open_trades']
        real_win_rate = (real_summary['wins'] / closed_trades * 100) if closed_trades > 0 else 0

        print(f"   Total Trades:     {real_summary['total']}")
        print(f"   Closed:           {closed_trades} ({real_summary['wins']}W/{real_summary['losses']}L)")
        print(f"   Open:             {real_summary['open_trades']}")
        print(f"   Win Rate:         {real_win_rate:.1f}%")
        print(f"   Total P&L:        {real_summary['total_pnl']:+.2f}%")
        print(f"   Avg P&L:          {real_summary['avg_pnl']:+.2f}%")
        print(f"   Avg Confidence:   {real_summary['avg_conf']:.1f}%")
        print(f"   Low Conf Trades:  {real_summary['low_conf_count']} (<50%)")
        print(f"   Low Conf P&L:     {real_summary['low_conf_pnl']:+.2f}%")
    else:
        print("   No real trades found")
    print()

    # Initialize ReplayEngine
    print("🔄 SIMULATED RESULTS (with 50% min confidence filter):")
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    # Run replay
    session = engine.replay_day(
        date=date,
        worker_names=['volume_absorption'],
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

    sim_win_rate = (len(wins) / len(simulated_trades) * 100) if simulated_trades else 0
    total_pnl = sum(t.get('pnl_pct', 0) for t in simulated_trades)
    avg_pnl = total_pnl / len(simulated_trades) if simulated_trades else 0

    print(f"   Coverage:         {approved}/{len(symbols)} symbols ({(approved/len(symbols)*100):.0f}%)")
    print(f"   Exec Rate:        {exec_rate:.1f}% ({approved}/{total} evaluations)")
    print(f"   Trades:           {len(simulated_trades)}")
    print(f"   Win Rate:         {sim_win_rate:.1f}% ({len(wins)}W/{len(losses)}L)")
    print(f"   Total P&L:        {total_pnl:+.2f}%")
    print(f"   Avg P&L:          {avg_pnl:+.2f}%")
    print()

    # Comparison
    if real_summary and real_summary['total'] > 0:
        print("📊 COMPARISON (Simulated vs Real):")
        trades_diff = len(simulated_trades) - real_summary['total']
        pnl_diff = total_pnl - real_summary['total_pnl']
        wr_diff = sim_win_rate - real_win_rate

        print(f"   Trades:           {len(simulated_trades)} vs {real_summary['total']} ({trades_diff:+d} diff)")
        print(f"   Win Rate:         {sim_win_rate:.1f}% vs {real_win_rate:.1f}% ({wr_diff:+.1f}% diff)")
        print(f"   Total P&L:        {total_pnl:+.2f}% vs {real_summary['total_pnl']:+.2f}% ({pnl_diff:+.2f}% diff)")
        print()

        # Impact of filter
        if real_summary['low_conf_count'] > 0:
            print("💡 IMPACT OF 50% CONFIDENCE FILTER:")
            print(f"   Real trades <50% conf:  {real_summary['low_conf_count']}")
            print(f"   P&L from low conf:      {real_summary['low_conf_pnl']:+.2f}%")
            print(f"   Expected improvement:   {-real_summary['low_conf_pnl']:+.2f}% (if filter worked)")
            print()

    # Status
    improvement = (total_pnl - real_summary['total_pnl']) if real_summary else 0
    status = "✅ IMPROVEMENT" if improvement > 5 else "⚠️ MARGINAL" if improvement > 0 else "❌ WORSE"
    print(f"   Status: {status} ({improvement:+.2f}% P&L change)")
    print()

    return {
        'date': date,
        'real_trades': real_summary['total'] if real_summary else 0,
        'real_pnl': real_summary['total_pnl'] if real_summary else 0,
        'real_win_rate': real_win_rate if real_summary else 0,
        'sim_trades': len(simulated_trades),
        'sim_pnl': total_pnl,
        'sim_win_rate': sim_win_rate,
        'improvement': improvement,
        'status': status
    }


def main():
    print("\n" + "="*80)
    print("🧪 VOLUME ABSORPTION WORKER - REGRESSION TEST")
    print("   Testing 50% Minimum Confidence Filter")
    print("="*80 + "\n")

    test_data = [
        {
            'date': '2025-12-04',
            'symbols': ['ABLV', 'ABTC', 'BITF', 'BTBT', 'CGC', 'KALA', 'LAES',
                       'LAZR', 'QCLS', 'RR', 'RZLV', 'SGBX', 'SLS', 'TSLS'],
            'description': 'Recent day - Real: 14 trades, -22.36% P&L'
        },
        {
            'date': '2025-12-03',
            'symbols': ['AUR', 'JBLU', 'MSTX', 'NVD', 'POET', 'QCLS', 'RR'],
            'description': 'Previous day - Real: 11 trades, +83.85% P&L'
        }
    ]

    results = []
    for test in test_data:
        result = run_test(test['date'], test['symbols'], test['description'])
        results.append(result)

    # Summary
    print(f"{'='*80}")
    print("📊 AGGREGATE RESULTS")
    print(f"{'='*80}\n")

    total_real_trades = sum(r['real_trades'] for r in results)
    total_sim_trades = sum(r['sim_trades'] for r in results)
    total_real_pnl = sum(r['real_pnl'] for r in results)
    total_sim_pnl = sum(r['sim_pnl'] for r in results)
    avg_real_wr = sum(r['real_win_rate'] for r in results) / len(results)
    avg_sim_wr = sum(r['sim_win_rate'] for r in results) / len(results)
    total_improvement = total_sim_pnl - total_real_pnl

    print(f"📈 Overall Statistics:")
    print(f"   Dates Tested:         {len(results)}")
    print(f"   Real Trades:          {total_real_trades}")
    print(f"   Simulated Trades:     {total_sim_trades} ({total_sim_trades - total_real_trades:+d} diff)")
    print(f"   Real P&L:             {total_real_pnl:+.2f}%")
    print(f"   Simulated P&L:        {total_sim_pnl:+.2f}%")
    print(f"   Improvement:          {total_improvement:+.2f}%")
    print(f"   Real Avg Win Rate:    {avg_real_wr:.1f}%")
    print(f"   Sim Avg Win Rate:     {avg_sim_wr:.1f}%")
    print()

    # Date-by-date table
    print(f"📊 Date-by-Date Summary:")
    print(f"{'Date':<12} {'Real Trades':<12} {'Sim Trades':<12} {'Real P&L':<12} {'Sim P&L':<12} {'Improvement':<12} {'Status':<15}")
    print("-" * 95)
    for r in results:
        print(f"{r['date']:<12} {r['real_trades']:<12} {r['sim_trades']:<12} "
              f"{r['real_pnl']:+<11.2f}% {r['sim_pnl']:+<11.2f}% {r['improvement']:+<11.2f}% {r['status']:<15}")
    print()

    # Final verdict
    print(f"{'='*80}")
    print("🎯 FINAL VERDICT")
    print(f"{'='*80}\n")

    if total_improvement > 10:
        print("✅ EXCELLENT: 50% confidence filter significantly improves performance")
        print(f"   - Improvement: {total_improvement:+.2f}%")
        print(f"   - Trade reduction: {total_real_trades - total_sim_trades} trades filtered")
        print()
        print("   ✅ RECOMMENDATION: Keep the 50% minimum confidence filter")
    elif total_improvement > 0:
        print("⚠️ MARGINAL: Small improvement, more testing needed")
        print(f"   - Improvement: {total_improvement:+.2f}%")
        print()
        print("   💡 RECOMMENDATION: Test with more dates or adjust threshold to 60%")
    else:
        print("❌ WORSE: Filter reduced performance")
        print(f"   - Degradation: {total_improvement:+.2f}%")
        print()
        print("   ⚠️ RECOMMENDATION: Revert filter or investigate why it's counterproductive")

    print()
    print("="*80)
    print("✅ REGRESSION TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
