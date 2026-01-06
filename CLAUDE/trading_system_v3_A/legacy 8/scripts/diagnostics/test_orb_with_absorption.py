#!/usr/bin/env python3
"""
Test ORB Worker with Absorption Detection using Replay System

This script tests the ORB worker with the new absorption detection feature
using historical data from market_data.db.

Usage:
    python test_orb_with_absorption.py --date 2025-10-31
    python test_orb_with_absorption.py --start-date 2025-10-25 --end-date 2025-10-31
    python test_orb_with_absorption.py --date 2025-10-31 --symbols AAPL,TSLA
"""

import argparse
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


def main():
    parser = argparse.ArgumentParser(
        description='Test ORB Worker with Absorption Detection'
    )

    # Date options
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument('--date', type=str, help='Specific date (YYYY-MM-DD)')
    date_group.add_argument('--start-date', type=str, help='Start date for range')

    parser.add_argument('--end-date', type=str, help='End date for range (only with --start-date)')
    parser.add_argument('--symbols', type=str, help='Specific symbols (comma-separated)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--no-absorption', action='store_true', 
                        help='Disable absorption filter for comparison')

    args = parser.parse_args()

    # Validate arguments
    if args.start_date and not args.end_date:
        parser.error("--end-date is required when using --start-date")

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]

    # Print header
    print("\n" + "="*80)
    print("🎯 ORB WORKER ABSORPTION TESTING")
    print("="*80)
    print(f"Absorption Filter: {'DISABLED' if args.no_absorption else 'ENABLED'}")
    print("="*80 + "\n")

    # Initialize Replay Engine
    engine = ReplayEngine(
        market_data_db_path='backtesting_system/market_data.db',
        trading_data_db_path='trading_data.db',
        verbose=args.verbose
    )

    # Configure ORB worker
    # Note: Absorption filter is controlled by worker config
    # For now, we'll just run with default settings
    workers = ['orb_breakout']

    # Run replay
    if args.date:
        # Single day
        print(f"📅 Testing date: {args.date}\n")
        
        session = engine.replay_day(
            date=args.date,
            worker_names=workers,
            symbols=symbols
        )

        # Print detailed summary
        print_orb_summary(session)

    else:
        # Date range
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

        print(f"📅 Testing date range: {args.start_date} to {args.end_date}\n")

        current_date = start_date
        all_sessions = []

        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            print(f"  Processing {date_str}...")
            
            session = engine.replay_day(
                date=date_str,
                worker_names=workers,
                symbols=symbols
            )

            all_sessions.append(session)
            current_date += timedelta(days=1)

        # Print aggregate summary
        print_orb_aggregate_summary(all_sessions)

    print("\n✅ ORB testing completed\n")


def print_orb_summary(session):
    """Print detailed summary for ORB worker testing"""
    print(f"\n{'='*80}")
    print(f"📊 ORB WORKER TEST RESULTS")
    print(f"{'='*80}")
    print(f"Date: {session.date}")
    print(f"Worker: {session.worker_name}")
    
    print(f"\n📈 Signals:")
    print(f"  Total events: {session.total_events}")
    print(f"  Symbols tested: {len(session.symbols)}")
    print(f"  Bars processed: {session.total_bars_processed}")
    
    print(f"\n🎯 Decisions:")
    print(f"  Total decisions: {session.total_decisions}")
    print(f"  Entries approved: {session.entries_approved}")
    print(f"  Entries rejected: {session.entries_rejected}")
    print(f"  Exits executed: {session.exits_executed}")
    
    print(f"\n💼 Trades:")
    print(f"  Simulated trades: {len(session.simulated_trades)}")
    
    # Calculate P&L
    total_pnl = 0.0
    total_pnl_pct = 0.0
    wins = 0
    losses = 0
    
    for trade in session.simulated_trades:
        if trade.get('status') == 'CLOSED':
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            quantity = trade.get('quantity', 0)
            
            if entry_price > 0:
                pnl = (exit_price - entry_price) * quantity
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                
                total_pnl += pnl
                total_pnl_pct += pnl_pct
                
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
    
    if len(session.simulated_trades) > 0:
        win_rate = (wins / len(session.simulated_trades)) * 100
        avg_pnl = total_pnl / len(session.simulated_trades)
        print(f"  Total P&L: ${total_pnl:.2f}")
        print(f"  Win Rate: {win_rate:.1f}% ({wins}W-{losses}L)")
        print(f"  Avg Trade: ${avg_pnl:.2f}")
    
    # Show per-symbol breakdown
    if session.events:
        print(f"\n📋 Symbol Breakdown:")
        for symbol, event in session.events.items():
            decisions = event.get_all_decisions()
            entries = [d for d in decisions if d.get('decision_type') == 'ENTRY']
            approved = [d for d in entries if d.get('approved')]
            
            # Calculate symbol P&L
            symbol_pnl = 0.0
            symbol_trades = 0
            for trade in event.simulated_trades:
                if trade.get('status') == 'CLOSED':
                    entry_price = trade.get('entry_price', 0)
                    exit_price = trade.get('exit_price', 0)
                    quantity = trade.get('quantity', 0)
                    symbol_pnl += (exit_price - entry_price) * quantity
                    symbol_trades += 1
            
            print(f"  {symbol}:")
            print(f"    Bars: {len(event.bars)}")
            print(f"    Decisions: {len(decisions)}")
            print(f"    Entries approved: {len(approved)}/{len(entries)}")
            print(f"    Simulated trades: {len(event.simulated_trades)}")
            if symbol_trades > 0:
                print(f"    P&L: ${symbol_pnl:.2f}")
            
            # Show rejection reasons
            rejected = [d for d in entries if not d.get('approved')]
            if rejected:
                reasons = {}
                for d in rejected:
                    reason = d.get('reason', 'Unknown')
                    reasons[reason] = reasons.get(reason, 0) + 1
                
                print(f"    Rejection reasons:")
                for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
                    print(f"      - {reason}: {count}")
    
    # Show discrepancies
    if session.discrepancies:
        print(f"\n⚠️  Discrepancies: {len(session.discrepancies)}")
        for disc in session.discrepancies[:3]:
            print(f"  - {disc.get('type', 'UNKNOWN')}: {disc.get('message', '')}")
    else:
        print(f"\n✅ No discrepancies found")


def print_orb_aggregate_summary(sessions):
    """Print aggregate summary for multiple ORB sessions"""
    print(f"\n{'='*80}")
    print(f"📊 ORB WORKER AGGREGATE RESULTS")
    print(f"{'='*80}")
    print(f"Total days tested: {len(sessions)}")
    
    total_events = sum(s.total_events for s in sessions)
    total_bars = sum(s.total_bars_processed for s in sessions)
    total_decisions = sum(s.total_decisions for s in sessions)
    total_approved = sum(s.entries_approved for s in sessions)
    total_rejected = sum(s.entries_rejected for s in sessions)
    total_exits = sum(s.exits_executed for s in sessions)
    total_trades = sum(len(s.simulated_trades) for s in sessions)
    total_discrepancies = sum(len(s.discrepancies) for s in sessions)
    
    print(f"\n📈 Overall Statistics:")
    print(f"  Total events: {total_events}")
    print(f"  Total bars processed: {total_bars}")
    print(f"  Total decisions: {total_decisions}")
    print(f"  Entries approved: {total_approved}")
    print(f"  Entries rejected: {total_rejected}")
    print(f"  Entry approval rate: {total_approved/(total_approved+total_rejected)*100:.1f}%" if (total_approved+total_rejected) > 0 else "  Entry approval rate: N/A")
    print(f"  Exits executed: {total_exits}")
    print(f"  Simulated trades: {total_trades}")
    
    # Calculate Aggregate P&L
    agg_pnl = 0.0
    agg_wins = 0
    agg_losses = 0
    
    for session in sessions:
        for trade in session.simulated_trades:
            if trade.get('status') == 'CLOSED':
                entry_price = trade.get('entry_price', 0)
                exit_price = trade.get('exit_price', 0)
                quantity = trade.get('quantity', 0)
                
                if entry_price > 0:
                    pnl = (exit_price - entry_price) * quantity
                    agg_pnl += pnl
                    
                    if pnl > 0:
                        agg_wins += 1
                    else:
                        agg_losses += 1
    
    if total_trades > 0:
        win_rate = (agg_wins / total_trades) * 100
        avg_pnl = agg_pnl / total_trades
        print(f"\n💰 Financial Performance:")
        print(f"  Total P&L: ${agg_pnl:.2f}")
        print(f"  Win Rate: {win_rate:.1f}% ({agg_wins}W-{agg_losses}L)")
        print(f"  Avg Trade: ${avg_pnl:.2f}")
    
    print(f"\n🔍 Verification:")
    print(f"  Total discrepancies: {total_discrepancies}")
    
    if total_discrepancies > 0:
        print(f"\n⚠️  Days with issues:")
        for session in sessions:
            if session.discrepancies:
                print(f"  {session.date}: {len(session.discrepancies)} discrepancies")
    
    # Calculate daily averages
    if len(sessions) > 0:
        print(f"\n📊 Daily Averages:")
        print(f"  Events per day: {total_events/len(sessions):.1f}")
        print(f"  Decisions per day: {total_decisions/len(sessions):.1f}")
        print(f"  Approved entries per day: {total_approved/len(sessions):.1f}")
        print(f"  Trades per day: {total_trades/len(sessions):.1f}")


if __name__ == '__main__':
    main()
