#!/usr/bin/env python3
"""
Run Replay - Script principal para ejecutar replay testing

Uso:
    python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01
    python replay_testing/run_replay.py --date 2025-10-31 --worker generic_01 --symbols MSAI,DFSC
    python replay_testing/run_replay.py --start-date 2025-10-25 --end-date 2025-10-31 --worker generic_01
"""

import argparse
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def main():
    parser = argparse.ArgumentParser(
        description='Worker Replay Testing - Reproduce condiciones reales para verificar workers'
    )

    # Date options
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument('--date', type=str, help='Fecha específica (YYYY-MM-DD)')
    date_group.add_argument('--start-date', type=str, help='Fecha inicio para rango')

    parser.add_argument('--end-date', type=str, help='Fecha fin para rango (solo con --start-date)')

    # Worker selection
    parser.add_argument('--workers', type=str,
                        help='Workers a testear (separados por coma). Si no se especifica, usa todos los workers disponibles.')

    # Symbol filter
    parser.add_argument('--symbols', type=str, help='Símbolos específicos (separados por coma)')

    # Database paths
    # NOTE: market-db is only for fallback - replay will automatically use trade_ohlc_snapshots from trading_data.db
    parser.add_argument('--market-db', type=str,
                        default='trading_data.db',
                        help='Path to market_data.db (will fallback to trade_ohlc_snapshots automatically)')
    parser.add_argument('--trading-db', type=str,
                        default='trading_data.db',
                        help='Path to trading_data.db')

    # Options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--strict', action='store_true',
                        help='Modo estricto: falla si encuentra discrepancias')
    parser.add_argument('--output-dir', type=str, default='replay_testing/reports',
                        help='Directorio para reportes')

    args = parser.parse_args()

    # Validate arguments
    if args.start_date and not args.end_date:
        parser.error("--end-date es requerido cuando usas --start-date")

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]

    # Parse workers
    workers = None
    if args.workers:
        workers = [w.strip() for w in args.workers.split(',')]

    # Initialize Replay Engine
    print("\n" + "="*80)
    print("🔄 WORKER REPLAY TESTING SYSTEM")
    print("="*80 + "\n")

    engine = ReplayEngine(
        market_data_db_path=args.market_db,
        trading_data_db_path=args.trading_db,
        verbose=args.verbose
    )

    # Run replay
    if args.date:
        # Single day
        session = engine.replay_day(
            date=args.date,
            worker_names=workers,
            symbols=symbols
        )

        # Print summary
        print_session_summary(session)

        # Check for discrepancies
        if args.strict and session.discrepancies:
            print(f"\n❌ STRICT MODE: Found {len(session.discrepancies)} discrepancies")
            sys.exit(1)

    else:
        # Date range
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

        current_date = start_date
        all_sessions = []

        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')

            session = engine.replay_day(
                date=date_str,
                worker_names=workers,
                symbols=symbols
            )

            all_sessions.append(session)
            current_date += timedelta(days=1)

        # Print aggregate summary
        print_aggregate_summary(all_sessions)

        # Check for discrepancies
        total_discrepancies = sum(len(s.discrepancies) for s in all_sessions)
        if args.strict and total_discrepancies > 0:
            print(f"\n❌ STRICT MODE: Found {total_discrepancies} total discrepancies")
            sys.exit(1)

    print("\n✅ Replay testing completed\n")


def print_session_summary(session):
    """Print summary of a single replay session"""
    print(f"\n{'='*80}")
    print(f"📊 REPLAY SESSION SUMMARY")
    print(f"{'='*80}")
    print(f"Date: {session.date}")
    print(f"Worker: {session.worker_name}")
    print(f"Events: {session.total_events} (one per ticker)")
    print(f"Symbols: {', '.join(session.symbols)}")
    print(f"\nGlobal Statistics:")
    print(f"  Bars processed: {session.total_bars_processed}")
    print(f"  Decisions made: {session.total_decisions}")
    print(f"  Entries approved: {session.entries_approved}")
    print(f"  Entries rejected: {session.entries_rejected}")
    print(f"  Exits executed: {session.exits_executed}")
    print(f"  Simulated trades: {len(session.simulated_trades)}")
    print(f"\nVerification:")
    print(f"  Total discrepancies: {session.total_discrepancies}")

    # WORKER PERFORMANCE ANALYSIS
    print(f"\n{'='*80}")
    print(f"🎯 WORKER PERFORMANCE BREAKDOWN")
    print(f"{'='*80}")

    # Aggregate trades by worker
    worker_stats = {}
    for trade in session.simulated_trades:
        worker = trade.get('worker', 'UNKNOWN')
        if worker not in worker_stats:
            worker_stats[worker] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'breakeven': 0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'symbols': set()
            }

        worker_stats[worker]['trades'] += 1
        worker_stats[worker]['symbols'].add(trade['symbol'])

        # Calculate P&L
        pnl_pct = trade.get('pnl_percent', trade.get('pnl_pct', 0))
        worker_stats[worker]['total_pnl_pct'] += pnl_pct

        if pnl_pct > 0.1:
            worker_stats[worker]['wins'] += 1
        elif pnl_pct < -0.1:
            worker_stats[worker]['losses'] += 1
        else:
            worker_stats[worker]['breakeven'] += 1

    # Print worker stats
    for worker, stats in sorted(worker_stats.items(), key=lambda x: x[1]['trades'], reverse=True):
        total_trades = stats['trades']
        wins = stats['wins']
        losses = stats['losses']
        breakeven = stats['breakeven']
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_pnl = stats['total_pnl_pct'] / total_trades if total_trades > 0 else 0
        unique_symbols = len(stats['symbols'])

        print(f"\n📌 {worker.upper()}")
        print(f"   Trades: {total_trades} ({unique_symbols} unique symbols)")
        print(f"   Win Rate: {win_rate:.1f}% ({wins}W / {losses}L / {breakeven}BE)")
        print(f"   Avg P&L: {avg_pnl:+.2f}%")
        print(f"   Total P&L: {stats['total_pnl_pct']:+.2f}%")
        print(f"   Symbols: {', '.join(sorted(stats['symbols']))}")

    if not worker_stats:
        print("\n⚠️  No trades executed by any worker")

    # Show per-event summary
    if session.events:
        print(f"\n{'='*80}")
        print(f"📈 EVENTS SUMMARY")
        print(f"{'='*80}")
        for symbol, event in session.events.items():
            status = "✅" if len(event.discrepancies) == 0 else f"⚠️ ({len(event.discrepancies)} issues)"
            print(f"  {symbol}: {len(event.get_all_decisions())} decisions, "
                  f"{len(event.simulated_trades)} simulated trades, "
                  f"{len(event.real_trades)} real trades {status}")

    # Show discrepancies
    if session.discrepancies:
        print(f"\n⚠️  Discrepancies found:")
        for disc in session.discrepancies[:5]:  # Show first 5
            print(f"  - {disc.get('type', 'UNKNOWN')}: {disc.get('message', '')}")
        if len(session.discrepancies) > 5:
            print(f"  ... and {len(session.discrepancies) - 5} more")

    if session.start_time and session.end_time:
        elapsed = (session.end_time - session.start_time).total_seconds()
        print(f"\nElapsed time: {elapsed:.1f}s")


def print_aggregate_summary(sessions):
    """Print aggregate summary for multiple sessions"""
    print(f"\n{'='*80}")
    print(f"📊 AGGREGATE REPLAY SUMMARY")
    print(f"{'='*80}")
    print(f"Total days: {len(sessions)}")

    total_bars = sum(s.total_bars_processed for s in sessions)
    total_decisions = sum(s.total_decisions for s in sessions)
    total_entries_approved = sum(s.entries_approved for s in sessions)
    total_entries_rejected = sum(s.entries_rejected for s in sessions)
    total_exits = sum(s.exits_executed for s in sessions)
    total_trades = sum(len(s.simulated_trades) for s in sessions)
    total_discrepancies = sum(len(s.discrepancies) for s in sessions)

    print(f"\nStatistics:")
    print(f"  Total bars processed: {total_bars}")
    print(f"  Total decisions made: {total_decisions}")
    print(f"  Total entries approved: {total_entries_approved}")
    print(f"  Total entries rejected: {total_entries_rejected}")
    print(f"  Total exits executed: {total_exits}")
    print(f"  Total simulated trades: {total_trades}")
    print(f"\nVerification:")
    print(f"  Total discrepancies: {total_discrepancies}")

    if total_discrepancies > 0:
        print(f"\n⚠️  Days with discrepancies:")
        for session in sessions:
            if session.discrepancies:
                print(f"  {session.date}: {len(session.discrepancies)} issues")


if __name__ == '__main__':
    main()
