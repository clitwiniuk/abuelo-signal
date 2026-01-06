#!/usr/bin/env python3
"""
Worker Correlation Analysis

Analiza la correlación entre workers para determinar si operan
los mismos símbolos al mismo tiempo (están correlacionados) o
si son independientes y descorrelacionados.

Métricas:
- Overlap de símbolos por día
- Timing de trades (mismo símbolo, mismo día)
- Correlación de P&L
- Diversificación del portfolio
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

DB_PATH = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db'


def analyze_worker_correlation(days_back=30):
    """
    Analiza correlación entre workers en los últimos N días
    """
    conn = sqlite3.connect(DB_PATH)

    # Get recent trades grouped by worker
    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    query = f"""
    SELECT
        strategy,
        symbol,
        date(entry_time) as trade_date,
        strftime('%Y-%m-%d %H', entry_time) as trade_hour,
        entry_time,
        exit_time,
        pnl,
        entry_price,
        exit_price
    FROM trades
    WHERE entry_time >= '{cutoff_date}'
        AND strategy IS NOT NULL
        AND strategy != ''
    ORDER BY entry_time
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print(f"❌ No trades found in last {days_back} days")
        return

    print("=" * 80)
    print(f"WORKER CORRELATION ANALYSIS - Last {days_back} days")
    print("=" * 80)
    print(f"Total trades: {len(df)}")
    print(f"Date range: {df['entry_time'].min()} to {df['entry_time'].max()}")
    print()

    # 1. WORKER TRADE COUNT
    print("1️⃣  TRADES BY WORKER")
    print("-" * 80)
    worker_counts = df['strategy'].value_counts()
    for worker, count in worker_counts.items():
        pct = (count / len(df)) * 100
        print(f"  {worker:30s}: {count:4d} trades ({pct:5.1f}%)")
    print()

    # 2. SYMBOL OVERLAP ANALYSIS
    print("2️⃣  SYMBOL OVERLAP BETWEEN WORKERS (Same Day)")
    print("-" * 80)

    # Group by worker and get symbols traded each day
    worker_symbols_by_day = defaultdict(lambda: defaultdict(set))

    for _, row in df.iterrows():
        worker = row['strategy']
        symbol = row['symbol']
        date = row['trade_date']
        worker_symbols_by_day[worker][date].add(symbol)

    # Calculate overlap for each worker pair
    workers = list(worker_counts.index)

    overlap_matrix = {}
    for i, w1 in enumerate(workers):
        for w2 in workers[i+1:]:
            # Count days where both workers traded
            overlap_days = 0
            overlap_symbols = []

            for date in set(list(worker_symbols_by_day[w1].keys()) + list(worker_symbols_by_day[w2].keys())):
                w1_symbols = worker_symbols_by_day[w1].get(date, set())
                w2_symbols = worker_symbols_by_day[w2].get(date, set())

                common = w1_symbols & w2_symbols
                if common:
                    overlap_days += 1
                    overlap_symbols.extend(list(common))

            if overlap_days > 0:
                overlap_matrix[(w1, w2)] = {
                    'days': overlap_days,
                    'symbols': overlap_symbols,
                    'unique_symbols': len(set(overlap_symbols))
                }

    # Print overlap results
    if overlap_matrix:
        print("\n⚠️  CORRELATIONS FOUND (Workers trading same symbols on same days):\n")
        for (w1, w2), data in sorted(overlap_matrix.items(), key=lambda x: -x[1]['days']):
            print(f"  {w1} ↔️ {w2}:")
            print(f"    - Overlapped on {data['days']} days")
            print(f"    - Shared {data['unique_symbols']} unique symbols: {', '.join(set(data['symbols'][:10]))}")
            print()
    else:
        print("✅ NO OVERLAP FOUND - Workers are fully descorrelated!")
        print()

    # 3. TIMING OVERLAP (Same symbol, same hour)
    print("3️⃣  TIMING OVERLAP (Same symbol within same hour)")
    print("-" * 80)

    timing_overlaps = defaultdict(list)

    for symbol in df['symbol'].unique():
        symbol_trades = df[df['symbol'] == symbol].copy()

        for hour in symbol_trades['trade_hour'].unique():
            hour_trades = symbol_trades[symbol_trades['trade_hour'] == hour]

            if len(hour_trades) > 1:
                workers_in_hour = list(hour_trades['strategy'].unique())
                if len(workers_in_hour) > 1:
                    timing_overlaps[symbol].append({
                        'hour': hour,
                        'workers': workers_in_hour,
                        'count': len(hour_trades)
                    })

    if timing_overlaps:
        print("\n⚠️  TIMING CONFLICTS (Multiple workers trading same symbol in same hour):\n")
        for symbol, overlaps in sorted(timing_overlaps.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"  {symbol}:")
            for overlap in overlaps[:3]:
                workers_str = ', '.join(overlap['workers'])
                print(f"    - {overlap['hour']}: {workers_str} ({overlap['count']} trades)")
            print()
    else:
        print("✅ NO TIMING OVERLAP - Workers enter at different times")
        print()

    # 4. P&L CORRELATION
    print("4️⃣  P&L CORRELATION BETWEEN WORKERS")
    print("-" * 80)

    # Create daily P&L by worker
    df['trade_date_dt'] = pd.to_datetime(df['trade_date'])

    daily_pnl = df.groupby(['strategy', 'trade_date_dt'])['pnl'].sum().unstack(fill_value=0)

    if len(daily_pnl.index) >= 2:
        corr_matrix = daily_pnl.T.corr()

        print("\nCorrelation Matrix (Daily P&L):\n")
        print(corr_matrix.round(2))
        print()

        # Find high correlations
        high_corr = []
        for i, w1 in enumerate(corr_matrix.index):
            for w2 in corr_matrix.columns[i+1:]:
                corr_value = corr_matrix.loc[w1, w2]
                if abs(corr_value) > 0.5:  # High correlation threshold
                    high_corr.append((w1, w2, corr_value))

        if high_corr:
            print("⚠️  HIGH P&L CORRELATIONS (>0.5):")
            for w1, w2, corr in sorted(high_corr, key=lambda x: -abs(x[2])):
                print(f"  {w1} ↔️ {w2}: {corr:.2f}")
            print()
        else:
            print("✅ LOW P&L CORRELATION - Workers have independent performance")
            print()
    else:
        print("⚠️  Not enough data for P&L correlation")
        print()

    # 5. DIVERSIFICATION SCORE
    print("5️⃣  PORTFOLIO DIVERSIFICATION SCORE")
    print("-" * 80)

    total_symbol_overlap_pct = 0
    total_timing_overlap_pct = 0

    if overlap_matrix:
        # Calculate average overlap
        total_days = len(df['trade_date'].unique())
        avg_overlap_days = np.mean([data['days'] for data in overlap_matrix.values()])
        total_symbol_overlap_pct = (avg_overlap_days / total_days) * 100

    if timing_overlaps:
        total_trades = len(df)
        overlapping_trades = sum(sum(o['count'] for o in overlaps) for overlaps in timing_overlaps.values())
        total_timing_overlap_pct = (overlapping_trades / total_trades) * 100

    diversification_score = 100 - (total_symbol_overlap_pct * 0.6 + total_timing_overlap_pct * 0.4)

    print(f"\n  Symbol Overlap:  {total_symbol_overlap_pct:.1f}%")
    print(f"  Timing Overlap:  {total_timing_overlap_pct:.1f}%")
    print(f"\n  📊 DIVERSIFICATION SCORE: {diversification_score:.1f}/100")
    print()

    if diversification_score >= 80:
        print("  ✅ EXCELLENT - Workers are well diversified")
    elif diversification_score >= 60:
        print("  ⚠️  GOOD - Some overlap but acceptable")
    elif diversification_score >= 40:
        print("  ⚠️  MODERATE - Significant overlap, consider review")
    else:
        print("  ❌ POOR - High correlation, workers may be redundant")

    print()
    print("=" * 80)

    # 6. RECOMMENDATIONS
    print("\n6️⃣  RECOMMENDATIONS")
    print("-" * 80)

    if overlap_matrix and len(overlap_matrix) > 0:
        worst_overlap = max(overlap_matrix.items(), key=lambda x: x[1]['days'])
        w1, w2 = worst_overlap[0]
        days = worst_overlap[1]['days']

        print(f"\n⚠️  {w1} and {w2} have the highest overlap ({days} days)")
        print(f"   Consider:")
        print(f"   - Review entry criteria to differentiate")
        print(f"   - Add filters to reduce overlap")
        print(f"   - Disable one worker if redundant")

    if timing_overlaps:
        print(f"\n⚠️  Found {len(timing_overlaps)} symbols with timing conflicts")
        print(f"   Consider:")
        print(f"   - Add priority system to workers")
        print(f"   - Use Trade Arbiter to prevent conflicts")
        print(f"   - Stagger entry times between workers")

    if diversification_score >= 80:
        print("\n✅ Workers are well diversified - continue current strategy")

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Analyze worker correlation')
    parser.add_argument('--days', type=int, default=30, help='Days to analyze (default: 30)')
    args = parser.parse_args()

    analyze_worker_correlation(days_back=args.days)
