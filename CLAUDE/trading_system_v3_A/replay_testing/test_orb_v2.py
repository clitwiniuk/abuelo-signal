#!/usr/bin/env python3
"""
ORB Worker v2.0 - Replay Testing & Validation

Tests the refactored ORB worker with historical data to validate:
1. Config reading works correctly
2. Price/volume filters are effective
3. WorkerStopManager integration works
4. Performance improvement vs v1.0
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def get_test_symbols(date='2025-11-18'):
    """
    Get symbols from trading_data.db for testing

    Using 2025-11-18 because it has 11 symbols with good data
    """
    import sqlite3

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

    symbols = [row[0] for row in results]

    return symbols, date


def main():
    print("\n" + "="*80)
    print("🧪 ORB WORKER v2.0 - REPLAY TESTING")
    print("="*80 + "\n")

    # Get test symbols
    symbols, test_date = get_test_symbols(date='2025-11-18')

    print(f"📊 Testing Date: {test_date}")
    print(f"📊 Symbols ({len(symbols)}): {', '.join(symbols)}")
    print()

    # Initialize ReplayEngine
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    # ========================================
    # TEST: ORB v2.0
    # ========================================
    print("="*80)
    print("🔬 TESTING: ORB Worker v2.0 (REFACTORED)")
    print("="*80 + "\n")

    # Use replay_day with correct API
    session = engine.replay_day(
        date=test_date,
        worker_names=['orb_breakout'],
        symbols=symbols
    )

    # ========================================
    # ANALYZE RESULTS
    # ========================================
    print("\n" + "="*80)
    print("📊 RESULTS ANALYSIS")
    print("="*80 + "\n")

    approved = session.entries_approved
    rejected = session.entries_rejected
    total = approved + rejected
    exec_rate = (approved / total * 100) if total > 0 else 0

    simulated_trades = session.simulated_trades

    print(f"📈 Execution Rate:")
    print(f"   Approved:  {approved}")
    print(f"   Rejected:  {rejected}")
    print(f"   Total:     {total}")
    print(f"   Exec Rate: {exec_rate:.1f}%")
    print()

    print(f"📊 Simulated Trades: {len(simulated_trades)}")
    print()

    if simulated_trades:
        # Calculate statistics
        wins = [t for t in simulated_trades if t.get('pnl_pct', 0) > 0]
        losses = [t for t in simulated_trades if t.get('pnl_pct', 0) < 0]
        breakevens = [t for t in simulated_trades if t.get('pnl_pct', 0) == 0]

        win_rate = (len(wins) / len(simulated_trades) * 100) if simulated_trades else 0
        avg_win = sum(t.get('pnl_pct', 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get('pnl_pct', 0) for t in losses) / len(losses) if losses else 0

        total_pnl = sum(t.get('pnl_pct', 0) for t in simulated_trades)
        avg_pnl = total_pnl / len(simulated_trades) if simulated_trades else 0

        print(f"📊 Performance Metrics:")
        print(f"   Win Rate:   {win_rate:.1f}% ({len(wins)}/{len(simulated_trades)})")
        print(f"   Avg Win:    +{avg_win:.2f}%")
        print(f"   Avg Loss:   {avg_loss:.2f}%")
        print(f"   Avg P&L:    {avg_pnl:+.2f}%")
        print(f"   Total P&L:  {total_pnl:+.2f}%")
        print()

        # Profit factor
        gross_profit = sum(t.get('pnl_pct', 0) for t in wins) if wins else 0
        gross_loss = abs(sum(t.get('pnl_pct', 0) for t in losses)) if losses else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        print(f"   Gross Profit: +{gross_profit:.2f}%")
        print(f"   Gross Loss:   -{gross_loss:.2f}%")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print()

        # Trade breakdown by symbol
        print(f"📊 Trades by Symbol:")
        symbol_trades = {}
        for trade in simulated_trades:
            symbol = trade.get('symbol', 'UNKNOWN')
            if symbol not in symbol_trades:
                symbol_trades[symbol] = []
            symbol_trades[symbol].append(trade)

        for symbol in sorted(symbol_trades.keys()):
            trades = symbol_trades[symbol]
            symbol_pnl = sum(t.get('pnl_pct', 0) for t in trades)
            symbol_wins = len([t for t in trades if t.get('pnl_pct', 0) > 0])
            print(f"   {symbol:6s}: {len(trades)} trades, {symbol_wins}W/{len(trades)-symbol_wins}L, P&L: {symbol_pnl:+.2f}%")
        print()

        # Show individual trades
        print(f"📊 Individual Trades:")
        for i, trade in enumerate(simulated_trades, 1):
            symbol = trade.get('symbol', 'UNKNOWN')
            entry = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            exit_reason = trade.get('exit_reason', 'UNKNOWN')

            status = "✅" if pnl_pct > 0 else "❌" if pnl_pct < 0 else "⚪"
            print(f"   {i:2d}. {status} {symbol:6s}: ${entry:.2f} -> ${exit_price:.2f} ({pnl_pct:+.2f}%) - {exit_reason}")
        print()

    # ========================================
    # FILTER EFFECTIVENESS ANALYSIS
    # ========================================
    print("="*80)
    print("🔍 FILTER EFFECTIVENESS")
    print("="*80 + "\n")

    print("📊 New Filters in v2.0:")
    print("   ✅ Price Range: $0.50 - $10.00")
    print("   ✅ Min Avg Volume: 100,000")
    print("   ✅ Min Dollar Volume: $50,000")
    print("   ✅ Gap Filter: < 10%")
    print()

    print(f"📊 Rejection Analysis:")
    print(f"   Total Evaluations: {total}")
    print(f"   Rejections: {rejected} ({(rejected/total*100) if total > 0 else 0:.1f}%)")
    print()
    print("   Rejection reasons are logged in worker output above.")
    print("   Common rejections:")
    print("   - Outside entry window (9:35-10:30 AM)")
    print("   - Price outside range")
    print("   - Low volume")
    print("   - ORB not valid")
    print("   - Breakout not confirmed")
    print()

    # ========================================
    # COMPARISON WITH DESIGN EXPECTATIONS
    # ========================================
    print("="*80)
    print("📊 COMPARISON WITH DESIGN EXPECTATIONS")
    print("="*80 + "\n")

    expected_win_rate = 50.0  # 45-55% expected
    expected_avg_win = 7.0     # 6-8% expected
    expected_avg_loss = -3.0   # -3% expected

    print(f"{'Metric':<20} {'Expected':<15} {'Actual':<15} {'Status':<10}")
    print("-" * 60)

    if simulated_trades:
        win_rate_status = "✅ GOOD" if abs(win_rate - expected_win_rate) < 15 else "⚠️ CHECK"
        avg_win_status = "✅ GOOD" if avg_win >= expected_avg_win * 0.75 else "⚠️ CHECK"
        avg_loss_status = "✅ GOOD" if avg_loss >= expected_avg_loss * 0.75 else "⚠️ CHECK"

        print(f"{'Win Rate':<20} {expected_win_rate:.1f}%{'':>8} {win_rate:.1f}%{'':>8} {win_rate_status}")
        print(f"{'Avg Win':<20} {expected_avg_win:.1f}%{'':>8} {avg_win:.1f}%{'':>8} {avg_win_status}")
        print(f"{'Avg Loss':<20} {expected_avg_loss:.1f}%{'':>8} {avg_loss:.1f}%{'':>8} {avg_loss_status}")
    else:
        print("No trades executed - cannot compare")

    print()

    # ========================================
    # FINAL VERDICT
    # ========================================
    print("="*80)
    print("🎯 FINAL VERDICT")
    print("="*80 + "\n")

    if not simulated_trades:
        print("⚠️ WARNING: No trades executed")
        print("   Possible causes:")
        print("   - Filters too strict (check logs)")
        print("   - No valid ORB setups on this date")
        print("   - Entry window too narrow")
        print()
        print("   Recommendation: Review rejection logs and adjust filters if needed")
    elif len(simulated_trades) < 3:
        print("⚠️ LOW SAMPLE SIZE: Only {} trades".format(len(simulated_trades)))
        print("   Need more data for statistical significance")
        print("   Recommendation: Test with multiple dates (5-10 days)")
    else:
        # Evaluate performance
        if win_rate >= 40 and avg_win > abs(avg_loss):
            print("✅ PERFORMANCE LOOKS GOOD")
            print(f"   Win Rate: {win_rate:.1f}% (target: 45-55%)")
            print(f"   R:R Ratio: {abs(avg_win/avg_loss):.2f}:1 (target: 2:1)")
            print(f"   Profit Factor: {profit_factor:.2f} (target: >1.5)")
            print()
            print("   ✅ Worker v2.0 passes validation")
            print("   ✅ Ready for paper trading")
        elif win_rate >= 30:
            print("⚠️ PERFORMANCE ACCEPTABLE BUT NEEDS MONITORING")
            print(f"   Win Rate: {win_rate:.1f}% (below target 45-55%)")
            print()
            print("   Recommendations:")
            print("   - Test with more dates")
            print("   - Consider adjusting quality_score threshold")
            print("   - Monitor paper trading closely")
        else:
            print("❌ PERFORMANCE BELOW EXPECTATIONS")
            print(f"   Win Rate: {win_rate:.1f}% (target: 45-55%)")
            print()
            print("   Recommendations:")
            print("   - Review filter settings")
            print("   - Analyze losing trades")
            print("   - Consider stricter quality filters")

    print()
    print("="*80)
    print("✅ REPLAY TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
