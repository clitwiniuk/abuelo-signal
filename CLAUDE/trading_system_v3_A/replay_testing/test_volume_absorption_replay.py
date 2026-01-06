#!/usr/bin/env python3
"""
Volume Absorption Worker Replay Test

Tests the volume_absorption worker with real market data from 2025-11-15
to verify entry/exit logic across different market phases.

Usage:
    python replay_testing/test_volume_absorption_replay.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def main():
    print("\n" + "="*80)
    print("🔬 VOLUME ABSORPTION WORKER REPLAY TEST")
    print("="*80 + "\n")
    
    # Initialize Replay Engine
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db',
        verbose=True
    )
    
    # Test date: 2025-12-01 (user requested)
    test_date = '2025-12-01'
    
    # Symbols from actual trades on 2025-12-01
    # Note: Using market_data.db which may have older data for these symbols
    test_symbols = ['BITF', 'MSTX', 'HIVE', 'FTEL']
    
    print(f"📅 Test Date: {test_date}")
    print(f"📊 Test Symbols: {', '.join(test_symbols)}")
    print(f"🎯 Worker: volume_absorption\n")
    
    # Run replay with volume_absorption worker
    session = engine.replay_day(
        date=test_date,
        worker_names=['volume_absorption'],
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
            
            # Show trade details
            if event.simulated_trades:
                for i, trade in enumerate(event.simulated_trades, 1):
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    pnl = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    print(f"    Trade #{i}:")
                    print(f"      Entry: ${entry_price:.2f}")
                    print(f"      Exit: ${exit_price:.2f}")
                    print(f"      P&L: {pnl:+.2f}%")
                    print(f"      Exit reason: {trade.get('exit_reason', 'UNKNOWN')}")
            
            # Show discrepancies
            if event.discrepancies:
                print(f"  ⚠️  Discrepancies: {len(event.discrepancies)}")
                for disc in event.discrepancies[:3]:
                    print(f"    - {disc.get('type', 'UNKNOWN')}: {disc.get('message', '')}")
    
    # Overall verdict
    print("\n" + "="*80)
    if session.total_discrepancies == 0:
        print("✅ REPLAY TEST PASSED - No discrepancies found")
    else:
        print(f"⚠️  REPLAY TEST COMPLETED - {session.total_discrepancies} discrepancies found")
    print("="*80 + "\n")
    
    return session


if __name__ == '__main__':
    main()
