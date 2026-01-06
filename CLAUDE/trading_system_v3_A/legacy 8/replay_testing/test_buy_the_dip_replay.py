#!/usr/bin/env python3
"""
Buy The Dip Worker Replay Test

Tests the buy_the_dip worker with real market data from 2025-12-05 (viernes)
to verify entry/exit logic and compare against actual trades.

Usage:
    python replay_testing/test_buy_the_dip_replay.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def main():
    print("\n" + "="*80)
    print("🔬 BUY THE DIP WORKER REPLAY TEST")
    print("="*80 + "\n")
    
    # Initialize Replay Engine
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db',
        verbose=True
    )
    
    # Test date: 2025-12-05 (viernes - día de oportunidades)
    test_date = '2025-12-05'
    
    # Symbols from actual trades on 2025-12-05
    # POM, TSDD, TSLS, WHLR - estos son los tickers que tuvieron plays ese día
    test_symbols = ['POM', 'TSDD', 'TSLS', 'WHLR']
    
    print(f"📅 Test Date: {test_date}")
    print(f"📊 Test Symbols: {', '.join(test_symbols)}")
    print(f"🎯 Worker: buy_the_dip\n")
    
    # Run replay with buy_the_dip worker
    session = engine.replay_day(
        date=test_date,
        worker_names=['buy_the_dip'],
        symbols=test_symbols
    )
    
    # Print detailed summary
    print("\n" + "="*80)
    print("📊 REPLAY RESULTS SUMMARY")
    print("="*80)
    print(f"\nDate: {session.date}")
    print(f"Worker: {session.worker_name}")
    print(f"Symbols tested: {len(session.symbols)}")
    
    print(f"\n📈 Statistics:")
    print(f"  Total bars processed: {session.total_bars_processed}")
    print(f"  Total decisions: {session.total_decisions}")
    print(f"  Entries approved: {session.entries_approved}")
    print(f"  Entries rejected: {session.entries_rejected}")
    print(f"  Exits executed: {session.exits_executed}")
    print(f"  Simulated trades: {len(session.simulated_trades)}")
    
    # Detailed per-symbol analysis
    print(f"\n📊 Per-Symbol Analysis:")
    print("-" * 80)
    
    for symbol in test_symbols:
        event = session.get_event(symbol)
        if event:
            print(f"\n{symbol}:")
            print(f"  Bars: {event.total_bars}")
            print(f"  Decisions: {event.decisions_made}")
            print(f"  Entries approved: {event.entries_approved}")
            print(f"  Entries rejected: {event.entries_rejected}")
            print(f"  Simulated trades: {len(event.simulated_trades)}")
            print(f"  Real trades: {len(event.real_trades)}")
            
            # Show simulated trade details
            if event.simulated_trades:
                print(f"\n  🔄 Simulated Trades:")
                for i, trade in enumerate(event.simulated_trades, 1):
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    pnl = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    print(f"    Trade #{i}:")
                    print(f"      Entry: ${entry_price:.2f} @ {trade.get('entry_time', 'N/A')}")
                    print(f"      Exit: ${exit_price:.2f} @ {trade.get('exit_time', 'N/A')}")
                    print(f"      P&L: {pnl:+.2f}%")
                    print(f"      Exit reason: {trade.get('exit_reason', 'UNKNOWN')}")
            
            # Show real trade details for comparison
            if event.real_trades:
                print(f"\n  ✅ Real Trades (for comparison):")
                for i, trade in enumerate(event.real_trades, 1):
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    pnl = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 and exit_price > 0 else 0
                    print(f"    Trade #{i}:")
                    print(f"      Entry: ${entry_price:.2f} @ {trade.get('entry_time', 'N/A')}")
                    if exit_price > 0:
                        print(f"      Exit: ${exit_price:.2f} @ {trade.get('exit_time', 'N/A')}")
                        print(f"      P&L: {pnl:+.2f}%")
                    else:
                        print(f"      Status: OPEN (no exit yet)")
            
            # Show discrepancies
            if event.discrepancies:
                print(f"\n  ⚠️  Discrepancies: {len(event.discrepancies)}")
                for disc in event.discrepancies[:3]:
                    print(f"    - {disc.get('type', 'UNKNOWN')}: {disc.get('message', '')}")
            
            # Show rejection reasons (if any)
            if event.entries_rejected > 0:
                print(f"\n  🚫 Rejection Analysis:")
                decisions = event.get_all_decisions()
                rejected_decisions = [d for d in decisions if d.decision_type == 'REJECTED']
                
                # Group rejections by reason
                rejection_reasons = {}
                for decision in rejected_decisions:
                    for reason, msg in decision.checks_failed.items():
                        if reason not in rejection_reasons:
                            rejection_reasons[reason] = 0
                        rejection_reasons[reason] += 1
                
                for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
                    print(f"    - {reason}: {count} times")
    
    # Overall verdict
    print("\n" + "="*80)
    print("📊 OVERALL SUMMARY")
    print("="*80)
    
    # Calculate overall P&L
    total_pnl = 0
    winning_trades = 0
    losing_trades = 0
    
    for trade in session.simulated_trades:
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        if entry_price > 0 and exit_price > 0:
            pnl = ((exit_price - entry_price) / entry_price * 100)
            total_pnl += pnl
            if pnl > 0:
                winning_trades += 1
            else:
                losing_trades += 1
    
    print(f"\nSimulated Trading Results:")
    print(f"  Total trades: {len(session.simulated_trades)}")
    print(f"  Winning trades: {winning_trades}")
    print(f"  Losing trades: {losing_trades}")
    if len(session.simulated_trades) > 0:
        win_rate = (winning_trades / len(session.simulated_trades)) * 100
        avg_pnl = total_pnl / len(session.simulated_trades)
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Average P&L: {avg_pnl:+.2f}%")
        print(f"  Total P&L: {total_pnl:+.2f}%")
    
    print(f"\nVerification:")
    if session.total_discrepancies == 0:
        print("  ✅ REPLAY TEST PASSED - No discrepancies found")
    else:
        print(f"  ⚠️  {session.total_discrepancies} discrepancies found")
        print(f"     (This may be expected if worker logic has changed)")
    
    print("="*80 + "\n")
    
    return session


if __name__ == '__main__':
    main()
