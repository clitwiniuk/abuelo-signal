"""
TP/SL Optimizer - Análisis de Event Study para optimización

Analiza signal_events de trading_data.db para calcular TP/SL óptimos por:
- Worker
- Confidence bucket (high/med/low)
- ODS classification

Genera recomendaciones basadas en percentiles de forward returns.

Usage:
    python analysis/tp_sl_optimizer.py --period 30  # Analiza últimos 30 días
    python analysis/tp_sl_optimizer.py --worker daily_plays  # Solo un worker

Author: Trading System
Date: 2025-11-09
"""

import sqlite3
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path


class TPSLOptimizer:
    """
    Optimizador de TP/SL basado en Event Study
    """

    def __init__(self, db_path: str = "trading_data.db"):
        """
        Args:
            db_path: Ruta a trading_data.db
        """
        self.db_path = db_path

        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database {db_path} not found")

    def load_signal_events(
        self,
        worker_name: str = None,
        days_back: int = 30,
        min_samples: int = 20
    ) -> pd.DataFrame:
        """
        Carga signal_events de la base de datos

        Args:
            worker_name: Filtrar por worker (None = todos)
            days_back: Cuántos días atrás cargar
            min_samples: Mínimo de samples para análisis

        Returns:
            DataFrame con eventos
        """
        conn = sqlite3.connect(self.db_path)

        query = '''
            SELECT *
            FROM signal_events
            WHERE timestamp >= datetime('now', '-{} days')
              AND forward_tracked_at IS NOT NULL
        '''.format(days_back)

        if worker_name:
            query += f" AND worker_name = '{worker_name}'"

        df = pd.read_sql_query(query, conn)
        conn.close()

        print(f"\n📊 Loaded {len(df)} signal events from last {days_back} days")

        if len(df) < min_samples:
            print(f"⚠️  WARNING: Only {len(df)} samples (min {min_samples} recommended)")

        return df

    def calculate_percentiles(
        self,
        df: pd.DataFrame,
        return_column: str = 'forward_return_60m'
    ) -> Dict[str, float]:
        """
        Calcula percentiles de forward returns

        Args:
            df: DataFrame con signal_events
            return_column: Columna de returns a analizar

        Returns:
            Dict con percentiles
        """
        # Filter only positive returns (winners)
        winners = df[df[return_column] > 0]

        if len(winners) == 0:
            return {}

        percentiles = {
            'p50': winners[return_column].quantile(0.50),
            'p60': winners[return_column].quantile(0.60),
            'p70': winners[return_column].quantile(0.70),
            'p75': winners[return_column].quantile(0.75),
            'p80': winners[return_column].quantile(0.80),
            'p90': winners[return_column].quantile(0.90),
        }

        return percentiles

    def calculate_expectancy(
        self,
        df: pd.DataFrame,
        tp_pct: float,
        sl_pct: float,
        return_column: str = 'forward_return_60m'
    ) -> Tuple[float, float, float]:
        """
        Calcula expectancy para un par TP/SL específico

        Args:
            df: DataFrame con signal_events
            tp_pct: Take profit % (decimal, e.g., 0.10 = 10%)
            sl_pct: Stop loss % (decimal, e.g., 0.05 = 5%)
            return_column: Columna de returns

        Returns:
            (expectancy, win_rate, avg_trade_return)
        """
        # Simulate trades with this TP/SL
        trades = []

        for _, row in df.iterrows():
            actual_return = row[return_column]
            mfe = row['mfe_percent'] / 100.0 if row['mfe_percent'] else actual_return
            mae = row['mae_percent'] / 100.0 if row['mae_percent'] else actual_return

            # Did it hit SL first?
            if mae <= -sl_pct:
                result = -sl_pct  # SL hit
            # Did it hit TP?
            elif mfe >= tp_pct:
                result = tp_pct  # TP hit
            # Neither (time exit)
            else:
                result = actual_return

            trades.append(result)

        trades_array = np.array(trades)

        wins = trades_array[trades_array > 0]
        losses = trades_array[trades_array <= 0]

        win_rate = len(wins) / len(trades_array) if len(trades_array) > 0 else 0
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        avg_trade = trades_array.mean()

        return expectancy, win_rate, avg_trade

    def optimize_worker(
        self,
        df: pd.DataFrame,
        worker_name: str,
        confidence_bucket: str = None
    ) -> Dict[str, any]:
        """
        Optimiza TP/SL para un worker específico

        Args:
            df: DataFrame con todos los eventos
            worker_name: Nombre del worker
            confidence_bucket: 'high', 'med', 'low' o None para todos

        Returns:
            Dict con resultados de optimización
        """
        # Filter by worker
        worker_df = df[df['worker_name'] == worker_name].copy()

        if len(worker_df) == 0:
            return {'error': f'No data for worker {worker_name}'}

        # Filter by confidence bucket
        if confidence_bucket:
            if confidence_bucket == 'high':
                worker_df = worker_df[worker_df['confidence'] >= 80]
            elif confidence_bucket == 'med':
                worker_df = worker_df[
                    (worker_df['confidence'] >= 60) & (worker_df['confidence'] < 80)
                ]
            elif confidence_bucket == 'low':
                worker_df = worker_df[worker_df['confidence'] < 60]

        if len(worker_df) < 10:
            return {'error': f'Insufficient data ({len(worker_df)} samples)'}

        # Calculate percentiles
        percentiles = self.calculate_percentiles(worker_df, 'forward_return_60m')

        if not percentiles:
            return {'error': 'No winning trades'}

        # Calculate average MAE for SL
        avg_mae = abs(worker_df['mae_percent'].mean()) / 100.0
        median_mae = abs(worker_df['mae_percent'].median()) / 100.0

        # Test different TP levels (percentiles)
        tp_candidates = [
            ('p60', percentiles['p60']),
            ('p70', percentiles['p70']),
            ('p75', percentiles['p75']),
            ('p80', percentiles['p80']),
        ]

        # SL = median MAE + buffer
        suggested_sl = median_mae * 1.2  # 20% buffer

        results = []

        for tp_name, tp_value in tp_candidates:
            if tp_value is None or np.isnan(tp_value):
                continue

            expectancy, win_rate, avg_trade = self.calculate_expectancy(
                worker_df,
                tp_pct=tp_value,
                sl_pct=suggested_sl,
                return_column='forward_return_60m'
            )

            results.append({
                'tp_name': tp_name,
                'tp_pct': tp_value,
                'sl_pct': suggested_sl,
                'expectancy': expectancy,
                'win_rate': win_rate,
                'avg_trade': avg_trade,
                'r_r': tp_value / suggested_sl if suggested_sl > 0 else 0,
            })

        # Find optimal (max expectancy)
        if not results:
            return {'error': 'No valid TP/SL combinations'}

        optimal = max(results, key=lambda x: x['expectancy'])

        return {
            'worker_name': worker_name,
            'confidence_bucket': confidence_bucket or 'all',
            'sample_size': len(worker_df),
            'win_rate_overall': len(worker_df[worker_df['forward_return_60m'] > 0]) / len(worker_df),

            # Percentiles
            'percentiles': percentiles,

            # Optimal TP/SL
            'optimal_tp_pct': optimal['tp_pct'],
            'optimal_sl_pct': optimal['sl_pct'],
            'optimal_r_r': optimal['r_r'],
            'expected_win_rate': optimal['win_rate'],
            'expected_expectancy': optimal['expectancy'],

            # All tested combinations
            'tested_combinations': results,

            # MAE stats
            'avg_mae': avg_mae,
            'median_mae': median_mae,

            # MFE stats
            'avg_mfe': worker_df['mfe_percent'].mean() / 100.0,
            'median_mfe': worker_df['mfe_percent'].median() / 100.0,
        }

    def print_report(self, results: Dict[str, any]):
        """Pretty print optimization results"""
        print("\n" + "=" * 80)
        print(f"TP/SL OPTIMIZATION REPORT: {results['worker_name']} ({results['confidence_bucket']})")
        print("=" * 80)
        print()

        print(f"Sample Size: {results['sample_size']}")
        print(f"Overall Win Rate: {results['win_rate_overall']*100:.1f}%")
        print()

        print("Forward Return Percentiles (60min):")
        print("-" * 80)
        for p, val in results['percentiles'].items():
            print(f"  {p.upper()}: {val*100:+.2f}%")
        print()

        print("MFE/MAE Statistics:")
        print("-" * 80)
        print(f"  Avg MFE: {results['avg_mfe']*100:+.2f}%")
        print(f"  Median MFE: {results['median_mfe']*100:+.2f}%")
        print(f"  Avg MAE: {results['avg_mae']*100:.2f}%")
        print(f"  Median MAE: {results['median_mae']*100:.2f}%")
        print()

        print("OPTIMAL TP/SL:")
        print("=" * 80)
        print(f"  TP: {results['optimal_tp_pct']*100:.2f}%")
        print(f"  SL: {results['optimal_sl_pct']*100:.2f}%")
        print(f"  R:R: {results['optimal_r_r']:.2f}:1")
        print(f"  Expected Win Rate: {results['expected_win_rate']*100:.1f}%")
        print(f"  Expected Expectancy: {results['expected_expectancy']*100:+.3f}% per trade")
        print()

        print("All Tested Combinations:")
        print("-" * 80)
        for combo in results['tested_combinations']:
            print(
                f"  TP={combo['tp_pct']*100:.1f}% ({combo['tp_name']}) | "
                f"SL={combo['sl_pct']*100:.1f}% | "
                f"R:R={combo['r_r']:.1f}:1 | "
                f"WR={combo['win_rate']*100:.1f}% | "
                f"EXP={combo['expectancy']*100:+.2f}%"
            )
        print()
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Optimize TP/SL from signal events')
    parser.add_argument('--db', default='trading_data.db', help='Database path')
    parser.add_argument('--worker', help='Filter by worker name')
    parser.add_argument('--period', type=int, default=30, help='Days to analyze')
    parser.add_argument('--confidence', choices=['high', 'med', 'low'], help='Confidence bucket')

    args = parser.parse_args()

    optimizer = TPSLOptimizer(db_path=args.db)

    # Load data
    df = optimizer.load_signal_events(
        worker_name=args.worker,
        days_back=args.period
    )

    if df.empty:
        print("❌ No data found")
        return

    # Get unique workers
    workers = df['worker_name'].unique()

    print(f"\n📈 Found {len(workers)} workers: {list(workers)}")

    # Analyze each worker
    for worker in workers:
        # Skip if filtering by specific worker
        if args.worker and worker != args.worker:
            continue

        # Analyze by confidence buckets
        buckets = ['high', 'med'] if not args.confidence else [args.confidence]

        for bucket in buckets:
            results = optimizer.optimize_worker(df, worker, bucket)

            if 'error' in results:
                print(f"\n⚠️  {worker} ({bucket}): {results['error']}")
                continue

            optimizer.print_report(results)


if __name__ == "__main__":
    main()
