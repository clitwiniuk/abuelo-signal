#!/usr/bin/env python3
"""
Real vs Simulated Validation Tool

Compares real trading results with replay simulations to detect:
1. Coverage differences (symbols traded)
2. Entry timing differences
3. Exit timing differences
4. P&L discrepancies
5. Decision pattern differences

This helps ensure production system matches tested behavior.
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine


class ValidationReport:
    """Stores validation metrics and discrepancies"""

    def __init__(self, date: str):
        self.date = date
        self.metrics = {}
        self.discrepancies = []
        self.warnings = []
        self.critical_issues = []

    def add_metric(self, name: str, real_value, simulated_value, tolerance_pct=10):
        """Add a metric comparison"""
        diff_pct = 0
        if simulated_value != 0:
            diff_pct = abs((real_value - simulated_value) / simulated_value * 100)

        status = "✅" if diff_pct <= tolerance_pct else "⚠️" if diff_pct <= 25 else "❌"

        self.metrics[name] = {
            'real': real_value,
            'simulated': simulated_value,
            'diff_pct': diff_pct,
            'tolerance': tolerance_pct,
            'status': status
        }

        if diff_pct > 25:
            self.critical_issues.append(f"{name}: {diff_pct:.1f}% deviation (critical)")
        elif diff_pct > tolerance_pct:
            self.warnings.append(f"{name}: {diff_pct:.1f}% deviation")

    def add_discrepancy(self, discrepancy_type: str, symbol: str, details: str, severity: str = "warning"):
        """Add a specific discrepancy"""
        self.discrepancies.append({
            'type': discrepancy_type,
            'symbol': symbol,
            'details': details,
            'severity': severity
        })

        if severity == "critical":
            self.critical_issues.append(f"{discrepancy_type} - {symbol}: {details}")
        elif severity == "warning":
            self.warnings.append(f"{discrepancy_type} - {symbol}: {details}")


def get_real_trades(date: str, db_path: str = 'trading_data.db') -> List[Dict]:
    """Get real trades from database for a specific date"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            symbol,
            strategy,
            worker_name,
            entry_price,
            exit_price,
            entry_time,
            exit_time,
            pnl,
            status,
            exit_reason_detailed as exit_reason,
            confidence
        FROM trades
        WHERE DATE(entry_time) = ?
        AND (deleted = 0 OR deleted IS NULL)
        ORDER BY entry_time
    """

    cursor.execute(query, (date,))
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return trades


def run_simulation(date: str, symbols: List[str], workers: List[str] = ['daily_plays']) -> Dict:
    """Run replay simulation for the date"""
    engine = ReplayEngine(
        market_data_db_path='market_data.db',
        trading_data_db_path='trading_data.db'
    )

    session = engine.replay_day(
        date=date,
        worker_names=workers,
        symbols=symbols
    )

    return {
        'session': session,
        'trades': session.simulated_trades,
        'entries_approved': session.entries_approved,
        'entries_rejected': session.entries_rejected
    }


def compare_coverage(real_trades: List[Dict], sim_trades: List[Dict], report: ValidationReport):
    """Compare symbol coverage between real and simulated"""
    real_symbols = set(t['symbol'] for t in real_trades)
    sim_symbols = set(t['symbol'] for t in sim_trades)

    # Symbols in real but not in simulation
    missing_in_sim = real_symbols - sim_symbols
    # Symbols in simulation but not in real
    missing_in_real = sim_symbols - real_symbols

    report.add_metric(
        "Coverage (symbols traded)",
        len(real_symbols),
        len(sim_symbols),
        tolerance_pct=15
    )

    for symbol in missing_in_sim:
        report.add_discrepancy(
            "Missing Symbol",
            symbol,
            "Symbol traded in REAL but NOT in simulation - possible entry criteria changed",
            severity="warning"
        )

    for symbol in missing_in_real:
        report.add_discrepancy(
            "Extra Symbol",
            symbol,
            "Symbol traded in SIMULATION but NOT in real - possible execution issue or filters too strict in production",
            severity="critical"
        )


def compare_entries(real_trades: List[Dict], sim_trades: List[Dict], report: ValidationReport):
    """Compare entry timing and prices"""

    for sim_trade in sim_trades:
        symbol = sim_trade['symbol']
        real_trade = next((t for t in real_trades if t['symbol'] == symbol), None)

        if not real_trade:
            continue  # Already reported in coverage

        # Compare entry prices
        sim_entry = sim_trade.get('entry_price', 0)
        real_entry = real_trade.get('entry_price', 0)

        if sim_entry > 0 and real_entry > 0:
            price_diff_pct = abs((real_entry - sim_entry) / sim_entry * 100)

            if price_diff_pct > 2:
                report.add_discrepancy(
                    "Entry Price Deviation",
                    symbol,
                    f"Real: ${real_entry:.2f} vs Sim: ${sim_entry:.2f} ({price_diff_pct:.1f}% diff)",
                    severity="warning" if price_diff_pct < 5 else "critical"
                )

        # Compare entry timing
        if real_trade['entry_time'] and sim_trade.get('entry_time'):
            try:
                real_time = datetime.fromisoformat(real_trade['entry_time'].replace('Z', '+00:00'))
                sim_time = datetime.fromisoformat(sim_trade['entry_time'].replace('Z', '+00:00'))

                time_diff = abs((real_time - sim_time).total_seconds() / 60)  # minutes

                if time_diff > 5:
                    report.add_discrepancy(
                        "Entry Timing Deviation",
                        symbol,
                        f"Real vs Sim: {time_diff:.1f} minutes difference",
                        severity="warning" if time_diff < 15 else "critical"
                    )
            except Exception:
                pass


def compare_exits(real_trades: List[Dict], sim_trades: List[Dict], report: ValidationReport):
    """Compare exit behavior"""

    for sim_trade in sim_trades:
        symbol = sim_trade['symbol']
        real_trade = next((t for t in real_trades if t['symbol'] == symbol), None)

        if not real_trade:
            continue

        sim_exit_reason = sim_trade.get('exit_reason', 'UNKNOWN')
        real_exit_reason = real_trade.get('exit_reason') or 'UNKNOWN'

        # Compare exit reasons
        if sim_exit_reason != real_exit_reason:
            # Normalize exit reasons for comparison
            sim_reason_type = sim_exit_reason.split('_')[0] if '_' in sim_exit_reason else sim_exit_reason
            real_reason_type = real_exit_reason.split('_')[0] if '_' in real_exit_reason else real_exit_reason

            if sim_reason_type != real_reason_type:
                report.add_discrepancy(
                    "Exit Reason Mismatch",
                    symbol,
                    f"Real: {real_exit_reason} vs Sim: {sim_exit_reason}",
                    severity="warning"
                )


def compare_pnl(real_trades: List[Dict], sim_trades: List[Dict], report: ValidationReport):
    """Compare P&L results"""

    real_total_pnl = sum(t.get('pnl', 0) or 0 for t in real_trades)
    sim_total_pnl = sum(t.get('pnl_pct', 0) or 0 for t in sim_trades)

    report.add_metric(
        "Total P&L (%)",
        real_total_pnl,
        sim_total_pnl,
        tolerance_pct=20
    )

    # Per-symbol P&L comparison
    for sim_trade in sim_trades:
        symbol = sim_trade['symbol']
        real_trade = next((t for t in real_trades if t['symbol'] == symbol), None)

        if not real_trade:
            continue

        sim_pnl = sim_trade.get('pnl_pct', 0) or 0
        real_pnl = real_trade.get('pnl', 0) or 0

        if abs(sim_pnl) > 0.1 or abs(real_pnl) > 0.1:  # Only compare if non-trivial
            pnl_diff = abs(real_pnl - sim_pnl)

            if pnl_diff > 3:  # More than 3% difference
                report.add_discrepancy(
                    "P&L Discrepancy",
                    symbol,
                    f"Real: {real_pnl:+.2f}% vs Sim: {sim_pnl:+.2f}% (diff: {pnl_diff:.2f}%)",
                    severity="warning" if pnl_diff < 5 else "critical"
                )


def print_report(report: ValidationReport):
    """Print validation report"""
    print("\n" + "="*80)
    print(f"📊 REAL vs SIMULATED VALIDATION REPORT - {report.date}")
    print("="*80 + "\n")

    # Metrics comparison
    print("📈 KEY METRICS COMPARISON:")
    print(f"{'Metric':<30} {'Real':<15} {'Simulated':<15} {'Diff %':<10} {'Status':<5}")
    print("-" * 80)

    for name, data in report.metrics.items():
        print(f"{name:<30} {data['real']:<15} {data['simulated']:<15} "
              f"{data['diff_pct']:<10.1f} {data['status']:<5}")

    print()

    # Discrepancies by type
    if report.discrepancies:
        discrepancy_types = {}
        for d in report.discrepancies:
            dtype = d['type']
            if dtype not in discrepancy_types:
                discrepancy_types[dtype] = []
            discrepancy_types[dtype].append(d)

        print("🔍 DISCREPANCIES FOUND:")
        print()

        for dtype, discs in discrepancy_types.items():
            print(f"  {dtype} ({len(discs)}):")
            for d in discs[:5]:  # Show first 5 of each type
                severity_icon = "❌" if d['severity'] == "critical" else "⚠️"
                print(f"    {severity_icon} {d['symbol']}: {d['details']}")
            if len(discs) > 5:
                print(f"    ... and {len(discs) - 5} more")
            print()
    else:
        print("✅ NO DISCREPANCIES FOUND - Perfect match!")
        print()

    # Summary
    print("="*80)
    print("🎯 VALIDATION SUMMARY")
    print("="*80 + "\n")

    if report.critical_issues:
        print("❌ CRITICAL ISSUES:")
        for issue in report.critical_issues[:5]:
            print(f"   - {issue}")
        if len(report.critical_issues) > 5:
            print(f"   ... and {len(report.critical_issues) - 5} more")
        print()

    if report.warnings:
        print("⚠️  WARNINGS:")
        for warning in report.warnings[:5]:
            print(f"   - {warning}")
        if len(report.warnings) > 5:
            print(f"   ... and {len(report.warnings) - 5} more")
        print()

    # Overall status
    metrics_ok = sum(1 for m in report.metrics.values() if m['status'] == '✅')
    total_metrics = len(report.metrics)

    print(f"📊 Metrics Matching: {metrics_ok}/{total_metrics}")
    print(f"🔍 Total Discrepancies: {len(report.discrepancies)}")
    print(f"❌ Critical Issues: {len(report.critical_issues)}")
    print(f"⚠️  Warnings: {len(report.warnings)}")
    print()

    if len(report.critical_issues) == 0 and len(report.warnings) <= 2:
        print("✅ VALIDATION PASSED: Production matches simulation closely")
        print("   System behavior is consistent and reliable")
    elif len(report.critical_issues) == 0:
        print("⚠️  VALIDATION ACCEPTABLE: Minor deviations detected")
        print("   Production mostly matches simulation, monitor warnings")
    else:
        print("❌ VALIDATION FAILED: Significant deviations detected")
        print("   Production behavior differs from simulation - investigate critical issues")

    print()
    print("="*80 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Validate real trading vs simulation')
    parser.add_argument('--date', type=str, help='Date to validate (YYYY-MM-DD), default: today')
    parser.add_argument('--workers', type=str, default='daily_plays',
                       help='Comma-separated list of workers to validate')

    args = parser.parse_args()

    # Use provided date or today
    test_date = args.date or datetime.now().strftime('%Y-%m-%d')
    workers = [w.strip() for w in args.workers.split(',')]

    print("\n" + "="*80)
    print("🔍 REAL vs SIMULATED VALIDATION")
    print("="*80 + "\n")
    print(f"📅 Date: {test_date}")
    print(f"👷 Workers: {', '.join(workers)}")
    print()

    # Get real trades
    print("📊 Loading real trades from database...")
    real_trades = get_real_trades(test_date)
    print(f"   Found {len(real_trades)} real trades")

    if not real_trades:
        print("\n⚠️  No real trades found for this date")
        print("   Cannot perform validation without real data")
        return

    # Get symbols from real trades
    symbols = list(set(t['symbol'] for t in real_trades))
    print(f"   Symbols: {', '.join(symbols)}")
    print()

    # Run simulation
    print("🔄 Running replay simulation...")
    sim_result = run_simulation(test_date, symbols, workers)
    sim_trades = sim_result['trades']
    print(f"   Simulated {len(sim_trades)} trades")
    print()

    # Create validation report
    report = ValidationReport(test_date)

    # Run comparisons
    print("🔍 Analyzing differences...")
    compare_coverage(real_trades, sim_trades, report)
    compare_entries(real_trades, sim_trades, report)
    compare_exits(real_trades, sim_trades, report)
    compare_pnl(real_trades, sim_trades, report)

    # Print report
    print_report(report)


if __name__ == '__main__':
    main()
