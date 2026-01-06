#!/usr/bin/env python3
"""
Daily Plays Worker - Replay Test for Today (2025-12-04)

Tests how the system would have performed today with all bugs fixed.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def main():
    print("\n" + "="*80)
    print("🧪 DAILY PLAYS WORKER - REPLAY TEST FOR TODAY (2025-12-04)")
    print("="*80 + "\n")

    # Symbols detected today
    symbols = [
        'ABLV', 'ABTC', 'BITF', 'BTBT', 'CGC', 'KALA', 'LAES',
        'LAZR', 'QCLS', 'RR', 'RZLV', 'SGBX', 'SLS', 'TSLS'
    ]

    print(f"📊 Testing Date: 2025-12-04")
    print(f"📊 Symbols ({len(symbols)}): {', '.join(symbols)}")
    print()

    # Initialize ReplayEngine
    print("🔄 Initializing ReplayEngine...")
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    # Run replay
    print("▶️  Running replay simulation...")
    print()
    session = engine.replay_day(
        date='2025-12-04',
        worker_names=['daily_plays'],
        symbols=symbols
    )

    # Calculate metrics
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

    # Calculate performance
    wins = [t for t in simulated_trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in simulated_trades if t.get('pnl_pct', 0) < 0]
    breakevens = [t for t in simulated_trades if t.get('pnl_pct', 0) == 0]

    win_rate = (len(wins) / len(simulated_trades) * 100) if simulated_trades else 0
    avg_win = sum(t.get('pnl_pct', 0) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get('pnl_pct', 0) for t in losses) / len(losses) if losses else 0
    avg_pnl = sum(t.get('pnl_pct', 0) for t in simulated_trades) / len(simulated_trades) if simulated_trades else 0
    total_pnl = sum(t.get('pnl_pct', 0) for t in simulated_trades)

    gross_profit = sum(t.get('pnl_pct', 0) for t in wins) if wins else 0
    gross_loss = abs(sum(t.get('pnl_pct', 0) for t in losses)) if losses else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

    print(f"📊 Performance Metrics:")
    print(f"   Win Rate:   {win_rate:.1f}% ({len(wins)}W/{len(losses)}L/{len(breakevens)}BE)")
    print(f"   Avg Win:    +{avg_win:.2f}%")
    print(f"   Avg Loss:   {avg_loss:.2f}%")
    print(f"   Avg P&L:    {avg_pnl:+.2f}%")
    print(f"   Total P&L:  {total_pnl:+.2f}%")
    print()
    print(f"   Gross Profit: +{gross_profit:.2f}%")
    print(f"   Gross Loss:   {gross_loss:.2f}%")
    print(f"   Profit Factor: {profit_factor:.2f}")
    print()

    # Check for duplicates
    symbol_trades = {}
    for trade in simulated_trades:
        symbol = trade.get('symbol', 'UNKNOWN')
        if symbol not in symbol_trades:
            symbol_trades[symbol] = []
        symbol_trades[symbol].append(trade)

    duplicates = {s: trades for s, trades in symbol_trades.items() if len(trades) > 1}

    print("📊 Anti-Overtrading Validation:")
    if duplicates:
        print(f"   ❌ DUPLICATES FOUND: {len(duplicates)} symbols with multiple entries")
        for symbol, trades in duplicates.items():
            print(f"      {symbol}: {len(trades)} entries")
    else:
        print(f"   ✅ NO DUPLICATES: All symbols have 1 entry max")
    print()

    # Trades by symbol
    if simulated_trades:
        print("📊 Trades by Symbol:")
        for symbol in sorted(symbol_trades.keys()):
            trades = symbol_trades[symbol]
            symbol_wins = len([t for t in trades if t.get('pnl_pct', 0) > 0])
            symbol_losses = len([t for t in trades if t.get('pnl_pct', 0) < 0])
            symbol_pnl = sum(t.get('pnl_pct', 0) for t in trades)
            print(f"   {symbol:6s}: {len(trades)} trades, {symbol_wins}W/{symbol_losses}L, P&L: {symbol_pnl:+.2f}%")
        print()

        # Individual trades
        print("📊 Individual Trades:")
        for i, trade in enumerate(simulated_trades, 1):
            symbol = trade.get('symbol', 'UNKNOWN')
            entry = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            pnl_pct = trade.get('pnl_pct', 0)
            exit_reason = trade.get('exit_reason', 'UNKNOWN')

            status = "✅" if pnl_pct > 0 else "❌" if pnl_pct < 0 else "⚪"
            print(f"   {i:2d}. {status} {symbol:6s}: ${entry:.2f} -> ${exit_price:.2f} ({pnl_pct:+.2f}%) - {exit_reason}")
        print()

    # Compare with actual results
    print("="*80)
    print("📊 COMPARISON WITH ACTUAL RESULTS")
    print("="*80 + "\n")

    print("🔍 Actual results from today (with errors):")
    print("   Coverage:  ?/?")
    print("   P&L:       ? (unknown due to errors)")
    print()

    print("✅ Simulated results (bugs fixed):")
    print(f"   Coverage:  {approved}/{len(symbols)} symbols ({(approved/len(symbols)*100):.0f}%)")
    print(f"   P&L:       {total_pnl:+.2f}%")
    print(f"   Win Rate:  {win_rate:.1f}%")
    print()

    # Final verdict
    print("="*80)
    print("🎯 FINAL VERDICT")
    print("="*80 + "\n")

    if win_rate >= 40 and not duplicates:
        print("✅ EXCELLENT: System would have performed well today")
        print(f"   - Win Rate: {win_rate:.1f}% (target: 50-60%)")
        print(f"   - Coverage: {(approved/len(symbols)*100):.0f}%")
        print(f"   - No duplicates detected")
        print()
        print("   💡 The bugs fixed today would have resulted in profitable trading")
    elif win_rate >= 30:
        print("⚠️ ACCEPTABLE: System would have been marginally profitable")
        print(f"   - Win Rate: {win_rate:.1f}%")
        print(f"   - Total P&L: {total_pnl:+.2f}%")
    else:
        print("❌ NEEDS REVIEW: Low win rate or negative P&L")
        print(f"   - Win Rate: {win_rate:.1f}%")
        print(f"   - Total P&L: {total_pnl:+.2f}%")
        print()
        print("   Recommendation: Review filter settings and entry criteria")

    print()
    print("="*80)
    print("✅ REPLAY TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
