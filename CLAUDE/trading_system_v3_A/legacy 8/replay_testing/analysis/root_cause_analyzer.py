#!/usr/bin/env python3
"""
Root Cause Analyzer - Analiza decisiones paso a paso para identificar por qué workers son agresivos

Este tool NO modifica parámetros - solo ANALIZA decisiones existentes
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from replay_testing.core import ReplayEngine, ReplayBar
from strategies.workers.base_worker_logic import BaseWorkerLogic


class RootCauseAnalyzer:
    """
    Analiza root causes de decisiones agresivas

    NO optimiza parámetros - solo ANALIZA comportamiento
    """

    def __init__(self, market_data_db: str = 'market_data.db',
                 trading_data_db: str = 'trading_data.db'):
        self.market_data_db = market_data_db
        self.trading_data_db = trading_data_db
        self.engine = ReplayEngine(market_data_db, trading_data_db, verbose=False)

    def analyze_trade_discrepancy(self,
                                   symbol: str,
                                   date: str,
                                   worker_name: str,
                                   entry_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Analiza por qué hubo discrepancia entre simulado y real

        Args:
            symbol: Symbol to analyze
            date: Date (YYYY-MM-DD)
            worker_name: Worker name
            entry_time: Optional entry time to focus on specific trade

        Returns:
            Root cause analysis dict
        """
        print(f"\n{'='*80}")
        print(f"🔍 ROOT CAUSE ANALYSIS - {symbol} @ {date}")
        print(f"{'='*80}\n")

        print(f"Worker: {worker_name}")
        print(f"Date: {date}")
        print(f"Symbol: {symbol}")
        if entry_time:
            print(f"Entry Time: {entry_time}")

        # 1. Load real trades for this symbol/date/worker
        real_trades = self._load_real_trades(symbol, date, worker_name)

        print(f"\n📊 Real Trades Found: {len(real_trades)}")
        for i, trade in enumerate(real_trades, 1):
            print(f"   {i}. {trade['entry_time']} @ ${trade['entry_price']:.2f}")

        # 2. Run replay for this date/symbol
        print(f"\n🔄 Running Replay Analysis...")
        session = self.engine.replay_day(date, [worker_name], [symbol])

        # 3. Get simulated trades
        event = session.events.get(symbol)
        if not event:
            print(f"\n❌ No event found for {symbol}")
            return {}

        simulated_trades = event.simulated_trades
        print(f"\n📈 Simulated Trades: {len(simulated_trades)}")
        for i, trade in enumerate(simulated_trades, 1):
            print(f"   {i}. {trade['entry_time']} @ ${trade['entry_price']:.2f}")

        # 4. Analyze discrepancies
        print(f"\n🎯 DISCREPANCY ANALYSIS")
        print(f"{'='*80}")

        if len(real_trades) == 0 and len(simulated_trades) == 0:
            print("✅ MATCH: No trades in both real and simulated")
            return {'status': 'MATCH', 'trades': 0}

        elif len(real_trades) > 0 and len(simulated_trades) == 0:
            print(f"❌ MISSING SIMULATED: Real system entered but replay did not")
            print(f"\n🔬 Analyzing why replay rejected...")

            # Analyze all decisions for this symbol
            decisions = event.get_all_decisions()
            rejected_count = sum(1 for d in decisions if d.decision_type == 'REJECTED')

            print(f"\n📊 Decision Summary:")
            print(f"   Total decisions: {len(decisions)}")
            print(f"   Rejected: {rejected_count}")
            print(f"   Approved: {len(decisions) - rejected_count}")

            # Show why decisions were rejected
            print(f"\n🚫 Rejection Reasons:")
            for decision in decisions[:10]:  # Show first 10
                if decision.decision_type == 'REJECTED':
                    print(f"   {decision.timestamp.strftime('%H:%M:%S')} - {decision.notes}")

            return {
                'status': 'MISSING_SIMULATED',
                'real_trades': len(real_trades),
                'simulated_trades': 0,
                'decisions': len(decisions),
                'rejected': rejected_count
            }

        elif len(real_trades) == 0 and len(simulated_trades) > 0:
            print(f"❌ FALSE POSITIVES: Replay entered but real system did not")
            print(f"\n⚠️ This indicates worker is TOO AGGRESSIVE")

            # Analyze why replay approved these trades
            print(f"\n🔬 Analyzing false positive trades...")

            for i, sim_trade in enumerate(simulated_trades[:5], 1):  # Show first 5
                print(f"\n   False Positive #{i}:")
                print(f"   Time: {sim_trade['entry_time']}")
                print(f"   Price: ${sim_trade['entry_price']:.2f}")
                print(f"   Pattern Completion: {sim_trade.get('pattern_completion', 0):.1f}%")

                # Find corresponding decision
                sim_time = pd.to_datetime(sim_trade['entry_time'])
                for decision in event.get_all_decisions():
                    if abs((decision.timestamp - sim_time).total_seconds()) < 10:
                        print(f"   Checks Passed: {list(decision.checks_passed.keys())}")
                        break

            return {
                'status': 'FALSE_POSITIVES',
                'real_trades': 0,
                'simulated_trades': len(simulated_trades),
                'severity': 'HIGH' if len(simulated_trades) > 5 else 'MEDIUM'
            }

        else:
            # Both have trades - compare
            print(f"⚠️ PARTIAL MATCH: Both have trades but counts differ")
            print(f"   Real: {len(real_trades)} trades")
            print(f"   Simulated: {len(simulated_trades)} trades")
            print(f"   Difference: {abs(len(real_trades) - len(simulated_trades))} trades")

            return {
                'status': 'PARTIAL_MATCH',
                'real_trades': len(real_trades),
                'simulated_trades': len(simulated_trades),
                'difference': abs(len(real_trades) - len(simulated_trades))
            }

    def analyze_worker_aggressiveness(self,
                                       worker_name: str,
                                       start_date: str,
                                       end_date: str) -> Dict[str, Any]:
        """
        Analiza por qué un worker es demasiado agresivo

        Args:
            worker_name: Worker to analyze
            start_date: Start date
            end_date: End date

        Returns:
            Aggressiveness analysis
        """
        print(f"\n{'='*80}")
        print(f"🎯 WORKER AGGRESSIVENESS ANALYSIS - {worker_name}")
        print(f"{'='*80}\n")

        print(f"Period: {start_date} to {end_date}")

        # Get all dates in range
        dates = pd.date_range(start_date, end_date, freq='D')
        dates = [d.strftime('%Y-%m-%d') for d in dates]

        total_decisions = 0
        total_entries_approved = 0
        total_entries_rejected = 0
        filter_rejection_counts = {}

        for date in dates:
            print(f"\n📅 Analyzing {date}...")

            # Run replay for this date
            session = self.engine.replay_day(date, [worker_name], None)

            total_decisions += session.total_decisions
            total_entries_approved += session.entries_approved
            total_entries_rejected += session.entries_rejected

            # Analyze rejection reasons
            for event in session.events.values():
                for decision in event.get_all_decisions():
                    if decision.decision_type == 'REJECTED':
                        # Count which filters caused rejection
                        if decision.notes:
                            reason = decision.notes
                            filter_rejection_counts[reason] = filter_rejection_counts.get(reason, 0) + 1

        # Calculate statistics
        selectivity_ratio = total_entries_approved / total_decisions if total_decisions > 0 else 0

        print(f"\n📊 ANALYSIS RESULTS")
        print(f"{'='*80}")
        print(f"Total Decisions: {total_decisions}")
        print(f"Entries Approved: {total_entries_approved}")
        print(f"Entries Rejected: {total_entries_rejected}")
        print(f"Selectivity Ratio: {selectivity_ratio*100:.1f}%")

        if selectivity_ratio > 0.10:
            print(f"\n⚠️ WARNING: Selectivity ratio TOO HIGH (>10%)")
            print(f"   Expected: <5% (1 in 20 decisions)")
            print(f"   Actual: {selectivity_ratio*100:.1f}% (1 in {int(1/selectivity_ratio)} decisions)")

        # Show top rejection reasons
        print(f"\n🚫 TOP REJECTION REASONS:")
        sorted_reasons = sorted(filter_rejection_counts.items(), key=lambda x: x[1], reverse=True)
        for i, (reason, count) in enumerate(sorted_reasons[:10], 1):
            percentage = count / total_entries_rejected * 100 if total_entries_rejected > 0 else 0
            print(f"   {i}. {reason}: {count} ({percentage:.1f}%)")

        return {
            'worker': worker_name,
            'period': f'{start_date} to {end_date}',
            'total_decisions': total_decisions,
            'entries_approved': total_entries_approved,
            'entries_rejected': total_entries_rejected,
            'selectivity_ratio': selectivity_ratio,
            'top_rejection_reasons': sorted_reasons[:10],
            'severity': 'HIGH' if selectivity_ratio > 0.20 else 'MEDIUM' if selectivity_ratio > 0.10 else 'LOW'
        }

    def _load_real_trades(self, symbol: str, date: str, worker_name: str) -> List[Dict]:
        """Load real trades from trading_data.db"""
        try:
            conn = sqlite3.connect(self.trading_data_db)

            query = """
                SELECT *
                FROM trades
                WHERE DATE(entry_time) = ?
                AND symbol = ?
                AND strategy = ?
                ORDER BY entry_time
            """

            df = pd.read_sql_query(query, conn, params=[date, symbol, worker_name])
            conn.close()

            return df.to_dict('records')

        except Exception as e:
            print(f"Error loading real trades: {e}")
            return []


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Root Cause Analyzer')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # analyze-trade command
    trade_parser = subparsers.add_parser('analyze-trade', help='Analyze specific trade discrepancy')
    trade_parser.add_argument('--symbol', required=True, help='Symbol')
    trade_parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    trade_parser.add_argument('--worker', required=True, help='Worker name')
    trade_parser.add_argument('--entry-time', help='Entry time (HH:MM:SS)')

    # analyze-worker command
    worker_parser = subparsers.add_parser('analyze-worker', help='Analyze worker aggressiveness')
    worker_parser.add_argument('--worker', required=True, help='Worker name')
    worker_parser.add_argument('--start-date', required=True, help='Start date')
    worker_parser.add_argument('--end-date', required=True, help='End date')

    # Database paths
    parser.add_argument('--market-db', default='market_data.db', help='Path to market_data.db')
    parser.add_argument('--trading-db', default='trading_data.db', help='Path to trading_data.db')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize analyzer
    analyzer = RootCauseAnalyzer(args.market_db, args.trading_db)

    if args.command == 'analyze-trade':
        result = analyzer.analyze_trade_discrepancy(
            args.symbol,
            args.date,
            args.worker,
            args.entry_time
        )

        print(f"\n{'='*80}")
        print(f"✅ Analysis Complete")
        print(f"{'='*80}\n")

        return 0 if result.get('status') == 'MATCH' else 1

    elif args.command == 'analyze-worker':
        result = analyzer.analyze_worker_aggressiveness(
            args.worker,
            args.start_date,
            args.end_date
        )

        print(f"\n{'='*80}")
        print(f"✅ Analysis Complete")
        print(f"{'='*80}\n")

        return 0 if result['severity'] == 'LOW' else 1


if __name__ == '__main__':
    sys.exit(main())
