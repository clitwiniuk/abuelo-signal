#!/usr/bin/env python3
"""
Exit Performance Analyzer - Módulo 4 del Backtest Modular

Analiza performance de exits para optimizar parámetros de salida.

Métricas:
- MFE (Max Favorable Excursion): ¿Dejamos dinero en la mesa?
- MAE (Max Adverse Excursion): ¿Stop loss es óptimo?
- Exit Reason Analysis: ¿Qué exits funcionan mejor?
- Parameter Optimization: ¿Qué TP/SL/trailing serían mejores?

Usage:
    python analyze_exit_performance.py --worker vcp_smallcap
    python analyze_exit_performance.py --worker parabolic --start-date 2024-01-01
"""

import sys
import os
import sqlite3
import pandas as pd
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExitPerformanceAnalyzer:
    """
    Analiza performance de exits usando datos históricos de trades
    """

    def __init__(self, db_path: str = "../trading_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def get_trades_for_worker(
        self,
        worker_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Obtiene trades del worker especificado

        Args:
            worker_name: Nombre del worker (ej: 'vcp_smallcap')
            start_date: Fecha inicial YYYY-MM-DD (opcional)
            end_date: Fecha final YYYY-MM-DD (opcional)

        Returns:
            DataFrame con trades
        """
        query = """
        SELECT
            id,
            symbol,
            strategy,
            entry_time,
            exit_time,
            actual_entry_price,
            actual_exit_price,
            quantity,
            actual_pnl,
            notes
        FROM trades
        WHERE strategy LIKE ?
        """

        params = [f"%{worker_name}%"]

        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date)

        query += " ORDER BY entry_time"

        df = pd.read_sql_query(query, self.conn, params=params)

        # Parse timestamps (formato mixto en la DB)
        df['entry_time'] = pd.to_datetime(df['entry_time'], format='mixed')
        df['exit_time'] = pd.to_datetime(df['exit_time'], format='mixed')

        # Calculate hold time
        df['hold_minutes'] = (df['exit_time'] - df['entry_time']).dt.total_seconds() / 60

        # Calculate P&L percentage
        df['pnl_pct'] = ((df['actual_exit_price'] - df['actual_entry_price']) /
                         df['actual_entry_price'] * 100)

        logger.info(f"Loaded {len(df)} trades for {worker_name}")
        return df

    def calculate_mfe_mae(
        self,
        symbol: str,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float
    ) -> Tuple[float, float]:
        """
        Calcula MFE y MAE para un trade usando datos OHLC

        Args:
            symbol: Symbol del trade
            entry_time: Timestamp de entrada
            exit_time: Timestamp de salida
            entry_price: Precio de entrada

        Returns:
            Tuple (MFE %, MAE %)
        """
        # Query OHLC bars usando trade_ohlc_snapshots
        query = """
        SELECT intraday_bars, day_high, day_low
        FROM trade_ohlc_snapshots
        WHERE symbol = ?
        AND datetime(entry_time) = datetime(?)
        LIMIT 1
        """
        params = [symbol, entry_time.isoformat()]

        snapshot = pd.read_sql_query(query, self.conn, params=params)

        if snapshot.empty:
            logger.warning(f"No OHLC snapshot for {symbol} at {entry_time}")
            return (0.0, 0.0)

        # Parse intraday_bars JSON
        import json
        intraday_bars_json = snapshot['intraday_bars'].iloc[0]

        if pd.isna(intraday_bars_json) or not intraday_bars_json:
            # Fallback: usar day_high/day_low
            day_high = snapshot['day_high'].iloc[0]
            day_low = snapshot['day_low'].iloc[0]

            if pd.isna(day_high) or pd.isna(day_low):
                logger.warning(f"No OHLC data for {symbol} between {entry_time} and {exit_time}")
                return (0.0, 0.0)

            mfe_pct = ((day_high - entry_price) / entry_price) * 100
            mae_pct = ((entry_price - day_low) / entry_price) * 100
            return (mfe_pct, mae_pct)

        # Parse JSON bars
        try:
            bars_data = json.loads(intraday_bars_json)
            bars = pd.DataFrame(bars_data)
        except Exception as e:
            logger.warning(f"Error parsing intraday_bars JSON for {symbol}: {e}")
            return (0.0, 0.0)

        if bars.empty:
            logger.warning(f"No OHLC data for {symbol} between {entry_time} and {exit_time}")
            return (0.0, 0.0)

        # Detectar nombres de columnas (pueden variar)
        high_col = 'high' if 'high' in bars.columns else 'high_price'
        low_col = 'low' if 'low' in bars.columns else 'low_price'

        # MFE: Max Favorable Excursion (max profit seen)
        max_high = bars[high_col].max()
        mfe_pct = ((max_high - entry_price) / entry_price) * 100

        # MAE: Max Adverse Excursion (max drawdown seen)
        min_low = bars[low_col].min()
        mae_pct = ((entry_price - min_low) / entry_price) * 100

        return (mfe_pct, mae_pct)

    def extract_exit_reason(self, notes: str) -> str:
        """
        Extrae exit reason de las notas del trade

        Args:
            notes: Campo notes del trade

        Returns:
            Exit reason string
        """
        if pd.isna(notes):
            return 'unknown'

        notes_lower = notes.lower()

        # Common exit reasons
        if 'stop loss' in notes_lower or 'sl' in notes_lower:
            return 'stop_loss'
        elif 'take profit' in notes_lower or 'tp' in notes_lower:
            return 'take_profit'
        elif 'trailing' in notes_lower:
            return 'trailing_stop'
        elif 'eod' in notes_lower or 'end of day' in notes_lower:
            return 'end_of_day'
        elif 'time' in notes_lower or 'timeout' in notes_lower:
            return 'time_based'
        else:
            return 'other'

    def analyze_exits(
        self,
        worker_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Análisis completo de exits para un worker

        Args:
            worker_name: Nombre del worker
            start_date: Fecha inicial (opcional)
            end_date: Fecha final (opcional)

        Returns:
            Dict con análisis completo
        """
        logger.info(f"Analyzing exit performance for {worker_name}...")

        # 1. Get trades
        trades = self.get_trades_for_worker(worker_name, start_date, end_date)

        if trades.empty:
            logger.error(f"No trades found for {worker_name}")
            return {}

        # 2. Calculate MFE/MAE for each trade
        logger.info("Calculating MFE/MAE for each trade...")
        mfe_mae_list = []

        for idx, trade in trades.iterrows():
            mfe, mae = self.calculate_mfe_mae(
                trade['symbol'],
                trade['entry_time'],
                trade['exit_time'],
                trade['actual_entry_price']
            )
            mfe_mae_list.append({'mfe': mfe, 'mae': mae})

        mfe_mae_df = pd.DataFrame(mfe_mae_list)
        trades['mfe'] = mfe_mae_df['mfe']
        trades['mae'] = mfe_mae_df['mae']

        # 3. Extract exit reasons
        trades['exit_reason'] = trades['notes'].apply(self.extract_exit_reason)

        # 4. Overall statistics
        overall_stats = {
            'total_trades': len(trades),
            'winning_trades': len(trades[trades['pnl_pct'] > 0]),
            'losing_trades': len(trades[trades['pnl_pct'] < 0]),
            'win_rate': len(trades[trades['pnl_pct'] > 0]) / len(trades) * 100,
            'avg_win_pct': trades[trades['pnl_pct'] > 0]['pnl_pct'].mean(),
            'avg_loss_pct': trades[trades['pnl_pct'] < 0]['pnl_pct'].mean(),
            'avg_pnl_pct': trades['pnl_pct'].mean(),
            'avg_hold_minutes': trades['hold_minutes'].mean()
        }

        # 5. MFE Analysis
        mfe_analysis = {
            'avg_mfe': trades['mfe'].mean(),
            'avg_pnl': trades['pnl_pct'].mean(),
            'money_left_on_table': trades['mfe'].mean() - trades['pnl_pct'].mean(),
            'pct_captured': (trades['pnl_pct'].mean() / trades['mfe'].mean() * 100)
                           if trades['mfe'].mean() > 0 else 0
        }

        # 6. MAE Analysis
        mae_analysis = {
            'avg_mae': trades['mae'].mean(),
            'max_mae': trades['mae'].max(),
            'min_mae': trades['mae'].min(),
            'mae_vs_avg_loss': trades['mae'].mean() / abs(overall_stats['avg_loss_pct'])
                               if overall_stats['avg_loss_pct'] < 0 else 0
        }

        # 7. Exit Reason Analysis
        exit_reason_stats = trades.groupby('exit_reason').agg({
            'pnl_pct': ['count', 'mean', 'std'],
            'mfe': 'mean',
            'mae': 'mean',
            'hold_minutes': 'mean'
        }).round(2)

        # 8. Parameter Optimization Suggestions
        optimization = self._suggest_optimal_parameters(trades)

        return {
            'worker_name': worker_name,
            'analysis_period': {
                'start': start_date or trades['entry_time'].min().strftime('%Y-%m-%d'),
                'end': end_date or trades['exit_time'].max().strftime('%Y-%m-%d')
            },
            'overall_stats': overall_stats,
            'mfe_analysis': mfe_analysis,
            'mae_analysis': mae_analysis,
            'exit_reason_stats': exit_reason_stats.to_dict(),
            'optimization_suggestions': optimization,
            'raw_trades': trades  # For further analysis
        }

    def _suggest_optimal_parameters(self, trades: pd.DataFrame) -> Dict:
        """
        Sugiere parámetros óptimos basado en MFE/MAE analysis

        Args:
            trades: DataFrame con trades y MFE/MAE

        Returns:
            Dict con sugerencias
        """
        suggestions = {}

        # Take Profit optimization
        avg_mfe = trades['mfe'].mean()
        current_avg_pnl = trades['pnl_pct'].mean()

        if avg_mfe > current_avg_pnl * 1.2:  # Dejando >20% en la mesa
            suggested_tp = avg_mfe * 0.9  # Target 90% del MFE
            suggestions['take_profit'] = {
                'current_capture': f"{current_avg_pnl:.2f}%",
                'avg_mfe': f"{avg_mfe:.2f}%",
                'suggested_tp': f"{suggested_tp:.2f}%",
                'reason': f"Leaving {avg_mfe - current_avg_pnl:.2f}% on table"
            }

        # Stop Loss optimization
        avg_mae = trades['mae'].mean()
        losing_trades = trades[trades['pnl_pct'] < 0]

        if not losing_trades.empty:
            avg_loss = abs(losing_trades['pnl_pct'].mean())

            if avg_mae < avg_loss * 0.7:  # Stop demasiado amplio
                suggested_sl = avg_mae * 1.1  # 110% del MAE promedio
                suggestions['stop_loss'] = {
                    'avg_mae': f"{avg_mae:.2f}%",
                    'avg_loss': f"{avg_loss:.2f}%",
                    'suggested_sl': f"{suggested_sl:.2f}%",
                    'reason': "Stop loss puede ser tighter"
                }
            elif avg_mae > avg_loss * 1.3:  # Stop demasiado tight
                suggested_sl = avg_mae * 0.9  # 90% del MAE
                suggestions['stop_loss'] = {
                    'avg_mae': f"{avg_mae:.2f}%",
                    'avg_loss': f"{avg_loss:.2f}%",
                    'suggested_sl': f"{suggested_sl:.2f}%",
                    'reason': "Stop loss puede ser wider para evitar noise"
                }

        # Trailing Stop analysis
        trailing_trades = trades[trades['exit_reason'] == 'trailing_stop']

        if not trailing_trades.empty and len(trailing_trades) > 5:
            trailing_avg_pnl = trailing_trades['pnl_pct'].mean()
            trailing_avg_mfe = trailing_trades['mfe'].mean()

            if trailing_avg_mfe > trailing_avg_pnl * 1.5:  # Cortando winners muy pronto
                suggestions['trailing_stop'] = {
                    'current_capture': f"{trailing_avg_pnl:.2f}%",
                    'avg_mfe': f"{trailing_avg_mfe:.2f}%",
                    'reason': "Trailing cutting winners too early",
                    'suggestion': "Widen trailing_distance by 1-2%"
                }

        return suggestions

    def print_report(self, analysis: Dict):
        """
        Imprime reporte formateado de análisis

        Args:
            analysis: Dict retornado por analyze_exits()
        """
        print("\n" + "=" * 80)
        print(f"EXIT PERFORMANCE ANALYSIS - {analysis['worker_name'].upper()}")
        print("=" * 80)

        # Period
        period = analysis['analysis_period']
        print(f"\n📅 Analysis Period: {period['start']} to {period['end']}")

        # Overall Stats
        stats = analysis['overall_stats']
        print(f"\n📊 OVERALL STATISTICS")
        print(f"   Total Trades:     {stats['total_trades']}")
        print(f"   Winning Trades:   {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
        print(f"   Losing Trades:    {stats['losing_trades']}")
        print(f"   Avg Win:          +{stats['avg_win_pct']:.2f}%")
        print(f"   Avg Loss:         {stats['avg_loss_pct']:.2f}%")
        print(f"   Avg P&L:          {stats['avg_pnl_pct']:.2f}%")
        print(f"   Avg Hold Time:    {stats['avg_hold_minutes']:.0f} minutes")

        # MFE Analysis
        mfe = analysis['mfe_analysis']
        print(f"\n🎯 MFE ANALYSIS (Max Favorable Excursion)")
        print(f"   Avg MFE:          +{mfe['avg_mfe']:.2f}%")
        print(f"   Avg P&L:          {mfe['avg_pnl']:.2f}%")
        print(f"   Money Left:       {mfe['money_left_on_table']:.2f}%")
        print(f"   Capture Rate:     {mfe['pct_captured']:.1f}%")

        if mfe['money_left_on_table'] > 2.0:
            print(f"   ⚠️  Leaving significant profit on table!")

        # MAE Analysis
        mae = analysis['mae_analysis']
        print(f"\n🛑 MAE ANALYSIS (Max Adverse Excursion)")
        print(f"   Avg MAE:          -{mae['avg_mae']:.2f}%")
        print(f"   Max MAE:          -{mae['max_mae']:.2f}%")
        print(f"   Min MAE:          -{mae['min_mae']:.2f}%")

        # Exit Reason Stats
        print(f"\n🚪 EXIT REASON BREAKDOWN")
        exit_stats = analysis['exit_reason_stats']
        for reason in exit_stats.get('pnl_pct', {}).get('count', {}).keys():
            count = exit_stats['pnl_pct']['count'].get(reason, 0)
            avg_pnl = exit_stats['pnl_pct']['mean'].get(reason, 0)
            print(f"   {reason:15s}: {count:3.0f} trades → Avg P&L = {avg_pnl:+.2f}%")

        # Optimization Suggestions
        opt = analysis['optimization_suggestions']
        if opt:
            print(f"\n💡 OPTIMIZATION SUGGESTIONS")

            if 'take_profit' in opt:
                tp = opt['take_profit']
                print(f"\n   Take Profit:")
                print(f"      Current Capture: {tp['current_capture']}")
                print(f"      Avg MFE:         {tp['avg_mfe']}")
                print(f"      ✅ Suggested TP:  {tp['suggested_tp']}")
                print(f"      Reason: {tp['reason']}")

            if 'stop_loss' in opt:
                sl = opt['stop_loss']
                print(f"\n   Stop Loss:")
                print(f"      Avg MAE:         {sl['avg_mae']}")
                print(f"      Avg Loss:        {sl['avg_loss']}")
                print(f"      ✅ Suggested SL:  {sl['suggested_sl']}")
                print(f"      Reason: {sl['reason']}")

            if 'trailing_stop' in opt:
                trail = opt['trailing_stop']
                print(f"\n   Trailing Stop:")
                print(f"      Current Capture: {trail['current_capture']}")
                print(f"      Avg MFE:         {trail['avg_mfe']}")
                print(f"      ✅ {trail['suggestion']}")
                print(f"      Reason: {trail['reason']}")
        else:
            print(f"\n✅ Exit parameters appear optimal - no changes suggested")

        print("\n" + "=" * 80 + "\n")

    def close(self):
        """Cierra conexión a DB"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Analyze exit performance for a worker'
    )
    parser.add_argument(
        '--worker',
        type=str,
        required=True,
        help='Worker name (e.g., vcp_smallcap, parabolic)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date YYYY-MM-DD (optional)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date YYYY-MM-DD (optional)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='../trading_data.db',
        help='Path to trading_data.db'
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = ExitPerformanceAnalyzer(db_path=args.db_path)

    try:
        analysis = analyzer.analyze_exits(
            worker_name=args.worker,
            start_date=args.start_date,
            end_date=args.end_date
        )

        if analysis:
            analyzer.print_report(analysis)
        else:
            logger.error("Analysis failed - no data returned")

    finally:
        analyzer.close()


if __name__ == '__main__':
    main()
