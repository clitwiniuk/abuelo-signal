#!/usr/bin/env python3
"""
Replay Comparator - Comparador avanzado entre replay y real

Proporciona análisis profundo de las diferencias entre:
- Decisiones de replay vs decisiones reales
- Trades simulados vs trades ejecutados
- Precios usados vs precios reales de IBKR
- Timing de entradas/salidas
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta


class ReplayComparator:
    """
    Comparador avanzado de replay vs real

    Proporciona análisis detallado de discrepancias
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize comparator

        Args:
            verbose: Enable verbose logging
        """
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose

    def compare_trades(
        self,
        simulated_trades: List[Dict],
        real_trades: List[Dict]
    ) -> Dict[str, Any]:
        """
        Compara trades simulados vs trades reales

        Args:
            simulated_trades: List of simulated trades
            real_trades: List of real trades

        Returns:
            Comparison result dict
        """
        comparison = {
            'simulated_count': len(simulated_trades),
            'real_count': len(real_trades),
            'matched_trades': [],
            'unmatched_simulated': [],
            'unmatched_real': [],
            'price_discrepancies': [],
            'timing_discrepancies': [],
            'exit_reason_discrepancies': []
        }

        # Match trades by entry time
        matched_pairs = self._match_trades_by_time(simulated_trades, real_trades)

        for sim_trade, real_trade in matched_pairs:
            match_result = self._compare_trade_pair(sim_trade, real_trade)
            comparison['matched_trades'].append(match_result)

            # Collect specific discrepancies
            if match_result['has_price_discrepancy']:
                comparison['price_discrepancies'].append(match_result)

            if match_result['has_timing_discrepancy']:
                comparison['timing_discrepancies'].append(match_result)

            if match_result['has_exit_reason_discrepancy']:
                comparison['exit_reason_discrepancies'].append(match_result)

        # Find unmatched trades
        matched_sim_indices = [i for i, _ in matched_pairs]
        matched_real_indices = [i for _, i in matched_pairs]

        for i, sim_trade in enumerate(simulated_trades):
            if i not in [idx for idx, _ in matched_pairs]:
                comparison['unmatched_simulated'].append(sim_trade)

        for i, real_trade in enumerate(real_trades):
            if i not in [idx for _, idx in matched_pairs]:
                comparison['unmatched_real'].append(real_trade)

        # Calculate summary statistics
        comparison['summary'] = self._calculate_comparison_summary(comparison)

        return comparison

    def _match_trades_by_time(
        self,
        simulated_trades: List[Dict],
        real_trades: List[Dict],
        max_time_diff_minutes: int = 5
    ) -> List[Tuple[Dict, Dict]]:
        """
        Match trades by entry time (closest match within time window)

        Args:
            simulated_trades: Simulated trades
            real_trades: Real trades
            max_time_diff_minutes: Maximum time difference for matching

        Returns:
            List of (simulated_trade, real_trade) pairs
        """
        matched_pairs = []
        used_real_indices = set()

        for i, sim_trade in enumerate(simulated_trades):
            sim_time = pd.to_datetime(sim_trade['entry_time'])

            best_match_idx = None
            min_time_diff = timedelta(minutes=max_time_diff_minutes)

            for j, real_trade in enumerate(real_trades):
                if j in used_real_indices:
                    continue

                real_time = pd.to_datetime(real_trade['entry_time'])
                time_diff = abs(sim_time - real_time)

                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_match_idx = j

            if best_match_idx is not None:
                matched_pairs.append((simulated_trades[i], real_trades[best_match_idx]))
                used_real_indices.add(best_match_idx)

        return matched_pairs

    def _compare_trade_pair(self, sim_trade: Dict, real_trade: Dict) -> Dict[str, Any]:
        """
        Compare a single pair of matched trades

        Args:
            sim_trade: Simulated trade
            real_trade: Real trade

        Returns:
            Comparison result
        """
        result = {
            'symbol': sim_trade['symbol'],
            'simulated_trade': sim_trade,
            'real_trade': real_trade,
            'has_price_discrepancy': False,
            'has_timing_discrepancy': False,
            'has_exit_reason_discrepancy': False,
            'discrepancies': []
        }

        # 1. Compare entry prices
        sim_entry = sim_trade['entry_price']
        real_entry = real_trade.get('entry_price', 0)

        if real_entry > 0:
            entry_diff_percent = abs(sim_entry - real_entry) / real_entry * 100

            if entry_diff_percent > 1.0:  # >1% difference
                result['has_price_discrepancy'] = True
                result['discrepancies'].append({
                    'type': 'ENTRY_PRICE',
                    'sim_value': sim_entry,
                    'real_value': real_entry,
                    'diff_percent': entry_diff_percent,
                    'message': f'Entry price diff {entry_diff_percent:.1f}%'
                })

        # 2. Compare exit prices (if both closed)
        if sim_trade.get('status') == 'CLOSED' and real_trade.get('exit_price'):
            sim_exit = sim_trade['exit_price']
            real_exit = real_trade['exit_price']

            if real_exit > 0:
                exit_diff_percent = abs(sim_exit - real_exit) / real_exit * 100

                if exit_diff_percent > 1.0:
                    result['has_price_discrepancy'] = True
                    result['discrepancies'].append({
                        'type': 'EXIT_PRICE',
                        'sim_value': sim_exit,
                        'real_value': real_exit,
                        'diff_percent': exit_diff_percent,
                        'message': f'Exit price diff {exit_diff_percent:.1f}%'
                    })

        # 3. Compare entry timing
        sim_entry_time = pd.to_datetime(sim_trade['entry_time'])
        real_entry_time = pd.to_datetime(real_trade['entry_time'])

        entry_time_diff = abs((sim_entry_time - real_entry_time).total_seconds())

        if entry_time_diff > 60:  # More than 1 minute difference
            result['has_timing_discrepancy'] = True
            result['discrepancies'].append({
                'type': 'ENTRY_TIMING',
                'sim_time': sim_entry_time.isoformat(),
                'real_time': real_entry_time.isoformat(),
                'diff_seconds': entry_time_diff,
                'message': f'Entry time diff {entry_time_diff:.0f}s'
            })

        # 4. Compare exit timing (if both closed)
        if sim_trade.get('exit_time') and real_trade.get('exit_time'):
            sim_exit_time = pd.to_datetime(sim_trade['exit_time'])
            real_exit_time = pd.to_datetime(real_trade['exit_time'])

            exit_time_diff = abs((sim_exit_time - real_exit_time).total_seconds())

            if exit_time_diff > 60:
                result['has_timing_discrepancy'] = True
                result['discrepancies'].append({
                    'type': 'EXIT_TIMING',
                    'sim_time': sim_exit_time.isoformat(),
                    'real_time': real_exit_time.isoformat(),
                    'diff_seconds': exit_time_diff,
                    'message': f'Exit time diff {exit_time_diff:.0f}s'
                })

        # 5. Compare exit reasons
        sim_exit_reason = sim_trade.get('exit_reason', '')
        real_exit_reason = real_trade.get('exit_reason', '')

        if sim_exit_reason and real_exit_reason:
            if sim_exit_reason != real_exit_reason:
                result['has_exit_reason_discrepancy'] = True
                result['discrepancies'].append({
                    'type': 'EXIT_REASON',
                    'sim_reason': sim_exit_reason,
                    'real_reason': real_exit_reason,
                    'message': f'Exit reason mismatch'
                })

        return result

    def _calculate_comparison_summary(self, comparison: Dict) -> Dict[str, Any]:
        """
        Calculate summary statistics from comparison

        Args:
            comparison: Comparison result dict

        Returns:
            Summary statistics
        """
        matched_count = len(comparison['matched_trades'])
        total_trades = max(comparison['simulated_count'], comparison['real_count'])

        return {
            'match_rate': matched_count / total_trades if total_trades > 0 else 0.0,
            'price_discrepancy_count': len(comparison['price_discrepancies']),
            'timing_discrepancy_count': len(comparison['timing_discrepancies']),
            'exit_reason_discrepancy_count': len(comparison['exit_reason_discrepancies']),
            'unmatched_simulated_count': len(comparison['unmatched_simulated']),
            'unmatched_real_count': len(comparison['unmatched_real']),
            'has_issues': (
                len(comparison['price_discrepancies']) > 0 or
                len(comparison['timing_discrepancies']) > 0 or
                len(comparison['unmatched_simulated']) > 0 or
                len(comparison['unmatched_real']) > 0
            )
        }

    def analyze_price_accuracy(
        self,
        simulated_trades: List[Dict],
        real_trades: List[Dict]
    ) -> Dict[str, Any]:
        """
        Analiza la precisión de precios entre replay y real

        Args:
            simulated_trades: Simulated trades
            real_trades: Real trades

        Returns:
            Price accuracy analysis
        """
        matched_pairs = self._match_trades_by_time(simulated_trades, real_trades)

        entry_diffs = []
        exit_diffs = []

        for sim_trade, real_trade in matched_pairs:
            # Entry price difference
            sim_entry = sim_trade['entry_price']
            real_entry = real_trade.get('entry_price', 0)

            if real_entry > 0:
                diff_percent = ((sim_entry - real_entry) / real_entry) * 100
                entry_diffs.append({
                    'symbol': sim_trade['symbol'],
                    'sim_price': sim_entry,
                    'real_price': real_entry,
                    'diff_percent': diff_percent,
                    'diff_absolute': abs(diff_percent)
                })

            # Exit price difference (if both closed)
            if sim_trade.get('exit_price') and real_trade.get('exit_price'):
                sim_exit = sim_trade['exit_price']
                real_exit = real_trade['exit_price']

                diff_percent = ((sim_exit - real_exit) / real_exit) * 100
                exit_diffs.append({
                    'symbol': sim_trade['symbol'],
                    'sim_price': sim_exit,
                    'real_price': real_exit,
                    'diff_percent': diff_percent,
                    'diff_absolute': abs(diff_percent)
                })

        # Calculate statistics
        analysis = {
            'entry_prices': {
                'count': len(entry_diffs),
                'mean_diff_percent': sum(d['diff_percent'] for d in entry_diffs) / len(entry_diffs) if entry_diffs else 0,
                'mean_abs_diff_percent': sum(d['diff_absolute'] for d in entry_diffs) / len(entry_diffs) if entry_diffs else 0,
                'max_diff_percent': max((d['diff_absolute'] for d in entry_diffs), default=0),
                'within_1_percent': sum(1 for d in entry_diffs if d['diff_absolute'] <= 1.0),
                'differences': entry_diffs
            },
            'exit_prices': {
                'count': len(exit_diffs),
                'mean_diff_percent': sum(d['diff_percent'] for d in exit_diffs) / len(exit_diffs) if exit_diffs else 0,
                'mean_abs_diff_percent': sum(d['diff_absolute'] for d in exit_diffs) / len(exit_diffs) if exit_diffs else 0,
                'max_diff_percent': max((d['diff_absolute'] for d in exit_diffs), default=0),
                'within_1_percent': sum(1 for d in exit_diffs if d['diff_absolute'] <= 1.0),
                'differences': exit_diffs
            }
        }

        return analysis

    def generate_comparison_report(self, comparison: Dict) -> str:
        """
        Generate text report from comparison

        Args:
            comparison: Comparison result

        Returns:
            Text report
        """
        lines = []
        lines.append("="*80)
        lines.append("REPLAY vs REAL COMPARISON REPORT")
        lines.append("="*80)

        summary = comparison['summary']

        lines.append(f"\nOverall:")
        lines.append(f"  Simulated trades: {comparison['simulated_count']}")
        lines.append(f"  Real trades: {comparison['real_count']}")
        lines.append(f"  Matched trades: {len(comparison['matched_trades'])}")
        lines.append(f"  Match rate: {summary['match_rate']*100:.1f}%")

        if summary['has_issues']:
            lines.append(f"\nIssues Found:")
            lines.append(f"  Price discrepancies: {summary['price_discrepancy_count']}")
            lines.append(f"  Timing discrepancies: {summary['timing_discrepancy_count']}")
            lines.append(f"  Exit reason discrepancies: {summary['exit_reason_discrepancy_count']}")
            lines.append(f"  Unmatched simulated: {summary['unmatched_simulated_count']}")
            lines.append(f"  Unmatched real: {summary['unmatched_real_count']}")

            # Detail price discrepancies
            if comparison['price_discrepancies']:
                lines.append(f"\nPrice Discrepancies:")
                for disc in comparison['price_discrepancies'][:5]:  # Show first 5
                    lines.append(f"  - {disc['symbol']}: {len(disc['discrepancies'])} issues")
                    for d in disc['discrepancies']:
                        if d['type'] in ['ENTRY_PRICE', 'EXIT_PRICE']:
                            lines.append(
                                f"    {d['type']}: "
                                f"sim=${d['sim_value']:.2f} vs real=${d['real_value']:.2f} "
                                f"({d['diff_percent']:.1f}%)"
                            )

            # Detail unmatched trades
            if comparison['unmatched_simulated']:
                lines.append(f"\nUnmatched Simulated Trades:")
                for trade in comparison['unmatched_simulated'][:5]:
                    lines.append(
                        f"  - {trade['symbol']} @ {trade['entry_time']}: "
                        f"${trade['entry_price']:.2f}"
                    )

            if comparison['unmatched_real']:
                lines.append(f"\nUnmatched Real Trades:")
                for trade in comparison['unmatched_real'][:5]:
                    entry_time = trade.get('entry_time', 'UNKNOWN')
                    entry_price = trade.get('entry_price', 0)
                    lines.append(
                        f"  - {trade['symbol']} @ {entry_time}: "
                        f"${entry_price:.2f}"
                    )
        else:
            lines.append(f"\n✅ No issues found - replay matches real trades perfectly")

        lines.append("\n" + "="*80)

        return "\n".join(lines)
