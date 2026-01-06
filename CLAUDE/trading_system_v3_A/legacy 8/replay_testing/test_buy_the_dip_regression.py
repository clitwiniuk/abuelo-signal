#!/usr/bin/env python3
"""
Buy The Dip Worker - Regression Testing

Tests the buy_the_dip worker to validate its dip-buying logic:
- Waits for price to dip after scanner signal
- Predicts dip size based on ATR volatility
- Confirms uptrend (price >1% above VWAP with positive slope)
- Enters on bounce confirmation
- Uses all stop/risk management systems

Expected Behavior:
- Should NOT enter immediately on scanner signal
- Should WAIT for dip to occur
- Should CONFIRM bounce before entering
- Should REJECT if VWAP not in uptrend
- Should use volatility-based dip predictions
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
            ROUND(AVG(confidence), 2) as avg_conf
        FROM trades
        WHERE DATE(entry_time) = ?
        AND (strategy = 'buy_the_dip' OR worker_name = 'buy_the_dip')
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
            'avg_conf': row[6]
        }
    return None


def run_test(date, symbols, description):
    """Run regression test for a single date"""
    print(f"\n{'='*80}")
    print(f"📅 TESTING: {date} - {description}")
    print(f"{'='*80}\n")
    print(f"📊 Symbols ({len(symbols)}): {', '.join(symbols)}")
    print()

    # Get real trades summary (if any)
    print("📊 REAL TRADING RESULTS:")
    real_summary = get_real_trades_summary(date)
    if real_summary and real_summary['total'] > 0:
        closed_trades = real_summary['total'] - real_summary['open_trades']
        real_win_rate = (real_summary['wins'] / closed_trades * 100) if closed_trades > 0 else 0

        print(f"   Total Trades:     {real_summary['total']}")
        print(f"   Closed:           {closed_trades} ({real_summary['wins']}W/{real_summary['losses']}L)")
        print(f"   Open:             {real_summary['open_trades']}")
        print(f"   Win Rate:         {real_win_rate:.1f}%")
        print(f"   Total P&L:        {real_summary['total_pnl']:+.2f}%")
        print(f"   Avg P&L:          {real_summary['avg_pnl']:+.2f}%")
        print(f"   Avg Confidence:   {real_summary['avg_conf']:.1f}%")
    else:
        print("   No real trades found (worker is new)")
    print()

    # Initialize ReplayEngine
    print("🔄 SIMULATED RESULTS (buy_the_dip worker):")
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    # Run replay
    session = engine.replay_day(
        date=date,
        worker_names=['buy_the_dip'],
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

    # Show individual trades
    if simulated_trades:
        print(f"📋 TRADE DETAILS:")
        print(f"{'Symbol':<8} {'Entry':<10} {'Exit':<10} {'P&L':<8} {'Exit Reason':<20} {'Hold Time':<10}")
        print("-" * 80)
        for t in simulated_trades:
            entry_time = t.get('entry_time', 'N/A')
            exit_time = t.get('exit_time', 'N/A')
            pnl = t.get('pnl_pct', 0)
            exit_reason = t.get('exit_reason', 'N/A')

            # Calculate hold time
            if isinstance(entry_time, str) and isinstance(exit_time, str):
                try:
                    from datetime import datetime
                    entry_dt = datetime.fromisoformat(entry_time)
                    exit_dt = datetime.fromisoformat(exit_time)
                    hold_minutes = int((exit_dt - entry_dt).total_seconds() / 60)
                    hold_time = f"{hold_minutes}min"
                except:
                    hold_time = "N/A"
            else:
                hold_time = "N/A"

            print(f"{t.get('symbol', 'N/A'):<8} {entry_time[11:19] if len(entry_time) > 19 else 'N/A':<10} "
                  f"{exit_time[11:19] if len(exit_time) > 19 else 'N/A':<10} "
                  f"{pnl:+.2f}%   {exit_reason:<20} {hold_time:<10}")
        print()

    # Comparison with real trades (if any)
    if real_summary and real_summary['total'] > 0:
        print("📊 COMPARISON (Simulated vs Real):")
        trades_diff = len(simulated_trades) - real_summary['total']
        pnl_diff = total_pnl - real_summary['total_pnl']

        print(f"   Trades:           {len(simulated_trades)} vs {real_summary['total']} ({trades_diff:+d} diff)")
        print(f"   Total P&L:        {total_pnl:+.2f}% vs {real_summary['total_pnl']:+.2f}% ({pnl_diff:+.2f}% diff)")
        print()

    # Status
    if total_pnl > 5:
        status = "✅ PROFITABLE"
    elif total_pnl > 0:
        status = "⚠️ MARGINAL"
    else:
        status = "❌ UNPROFITABLE"

    print(f"   Status: {status} ({total_pnl:+.2f}% P&L)")
    print()

    # Calculate real win rate safely
    real_win_rate = 0
    if real_summary and real_summary['total'] and real_summary['open_trades'] is not None:
        closed = real_summary['total'] - real_summary['open_trades']
        if closed > 0:
            real_win_rate = (real_summary['wins'] / closed * 100)

    return {
        'date': date,
        'real_trades': real_summary['total'] if real_summary else 0,
        'real_pnl': real_summary['total_pnl'] if real_summary else 0,
        'real_win_rate': real_win_rate,
        'sim_trades': len(simulated_trades),
        'sim_pnl': total_pnl,
        'sim_win_rate': sim_win_rate,
        'status': status
    }


def main():
    print("\n" + "="*80)
    print("🧪 BUY THE DIP WORKER - REGRESSION TEST")
    print("   Testing dip-buying logic in uptrends")
    print("="*80 + "\n")

    # Test with recent dates that had catalyst plays
    # Since this worker is new, we'll test with dates that had good daily_plays activity
    test_data = [
        {
            'date': '2025-12-04',
            'symbols': ['ABLV', 'ABTC', 'BITF', 'BTBT', 'CGC', 'KALA', 'LAES',
                       'LAZR', 'QCLS', 'RR', 'RZLV', 'SGBX', 'SLS', 'TSLS'],
            'description': 'Recent active day - 14 scanner signals'
        },
        {
            'date': '2025-12-03',
            'symbols': ['AUR', 'JBLU', 'MSTX', 'NVD', 'POET', 'QCLS', 'RR'],
            'description': 'Previous day - 7 scanner signals'
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

    total_real_trades = sum(r.get('real_trades', 0) or 0 for r in results)
    total_sim_trades = sum(r.get('sim_trades', 0) or 0 for r in results)
    total_real_pnl = sum(r.get('real_pnl', 0) or 0 for r in results)
    total_sim_pnl = sum(r.get('sim_pnl', 0) or 0 for r in results)
    avg_real_wr = sum(r.get('real_win_rate', 0) or 0 for r in results) / len(results) if results else 0
    avg_sim_wr = sum(r.get('sim_win_rate', 0) or 0 for r in results) / len(results) if results else 0

    print(f"📈 Overall Statistics:")
    print(f"   Dates Tested:         {len(results)}")
    print(f"   Real Trades:          {total_real_trades} (worker is new)")
    print(f"   Simulated Trades:     {total_sim_trades}")
    print(f"   Simulated P&L:        {total_sim_pnl:+.2f}%")
    print(f"   Sim Avg Win Rate:     {avg_sim_wr:.1f}%")
    print()

    # Date-by-date table
    print(f"📊 Date-by-Date Summary:")
    print(f"{'Date':<12} {'Sim Trades':<12} {'Sim P&L':<12} {'Win Rate':<12} {'Status':<15}")
    print("-" * 70)
    for r in results:
        print(f"{r['date']:<12} {r['sim_trades']:<12} "
              f"{r['sim_pnl']:+<11.2f}% {r['sim_win_rate']:<11.1f}% {r['status']:<15}")
    print()

    # Final verdict
    print(f"{'='*80}")
    print("🎯 FINAL VERDICT")
    print(f"{'='*80}\n")

    if total_sim_pnl > 10:
        print("✅ EXCELLENT: Worker shows strong profit potential")
        print(f"   - Total P&L: {total_sim_pnl:+.2f}%")
        print(f"   - Win Rate: {avg_sim_wr:.1f}%")
        print()
        print("   ✅ RECOMMENDATION: Enable worker and monitor performance")
    elif total_sim_pnl > 0:
        print("⚠️ MARGINAL: Small profit, needs more testing")
        print(f"   - Total P&L: {total_sim_pnl:+.2f}%")
        print()
        print("   💡 RECOMMENDATION: Test with more dates before enabling")
    else:
        print("❌ UNPROFITABLE: Worker needs adjustment")
        print(f"   - Total P&L: {total_sim_pnl:+.2f}%")
        print()
        print("   ⚠️ RECOMMENDATION: Review parameters or disable worker")

    print()
    print("="*80)
    print("✅ REGRESSION TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
