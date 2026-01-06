#!/usr/bin/env python3
"""
Backtesting Científico con Replay - Sistema Completo

Este script ejecuta backtests rigurosos usando el sistema de replay existente
y analiza consistencia de workers a través de múltiples períodos.

Características:
1. Usa datos REALES de OHLC ya almacenados
2. Ejecuta con configuración ACTUAL de cada worker
3. Divide en períodos para validar consistencia
4. Genera reportes detallados con métricas
5. Da recomendación final: mantener/revisar/eliminar
"""

import sys
import os
import asyncio
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from replay_testing.core.replay_engine import ReplayEngine
from strategies.workers import base_worker_logic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScientificBacktester:
    """
    Backtester científico que valida consistencia de workers
    """

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def get_available_date_range(self) -> tuple:
        """Obtiene rango de fechas con datos OHLC disponibles"""
        query = """
        SELECT MIN(timestamp) as start, MAX(timestamp) as end
        FROM broker_ohlc
        WHERE timestamp IS NOT NULL
        """
        result = pd.read_sql_query(query, self.conn)

        if result.empty or pd.isna(result['start'].iloc[0]):
            # Fallback: usar trades
            query = """
            SELECT MIN(entry_time) as start, MAX(exit_time) as end
            FROM trades
            WHERE entry_time IS NOT NULL
            """
            result = pd.read_sql_query(query, self.conn)

        return (result['start'].iloc[0], result['end'].iloc[0])

    def split_into_periods(
        self,
        start_date: str,
        end_date: str,
        period_months: int = 2
    ) -> List[tuple]:
        """
        Divide rango de fechas en períodos para análisis de consistencia

        Args:
            start_date: Fecha inicial YYYY-MM-DD
            end_date: Fecha final YYYY-MM-DD
            period_months: Meses por período

        Returns:
            Lista de tuplas (start, end) por período
        """
        periods = []
        current = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        while current < end:
            period_end = min(current + pd.DateOffset(months=period_months), end)
            periods.append((
                current.strftime('%Y-%m-%d'),
                period_end.strftime('%Y-%m-%d')
            ))
            current = period_end

        return periods

    def get_worker_config(self, worker_name: str) -> Dict:
        """
        Obtiene configuración actual del worker

        Args:
            worker_name: Nombre del worker

        Returns:
            Dict con configuración
        """
        # Importar dinámicamente el worker
        try:
            module = __import__(
                f'strategies.workers.{worker_name}_worker_logic',
                fromlist=[f'{worker_name.title().replace("_", "")}WorkerLogic']
            )

            worker_class_name = f'{worker_name.title().replace("_", "")}WorkerLogic'

            # Intentar diferentes variaciones del nombre
            possible_names = [
                worker_class_name,
                f'{worker_name.upper()}WorkerLogic',
                f'{worker_name.capitalize()}WorkerLogic'
            ]

            worker_class = None
            for name in possible_names:
                if hasattr(module, name):
                    worker_class = getattr(module, name)
                    break

            if worker_class is None:
                logger.warning(f"No se encontró clase para {worker_name}, usando config por defecto")
                return self._get_default_config(worker_name)

            # Crear instancia temporal para obtener config
            worker_instance = worker_class(
                broker=None,
                execution=None,
                risk_manager=None,
                worker_id=f"{worker_name}_backtest"
            )

            return {
                'worker_name': worker_name,
                'min_price': getattr(worker_instance, 'min_price', 0.0),
                'max_price': getattr(worker_instance, 'max_price', 999999.0),
                'min_volume': getattr(worker_instance, 'min_volume', 0),
                'max_volume_ratio': getattr(worker_instance, 'max_volume_ratio', 10.0),
                'position_size': getattr(worker_instance, 'position_size', 100),
                'stop_loss_pct': getattr(worker_instance, 'stop_loss_pct', 0.05),
                'take_profit_pct': getattr(worker_instance, 'take_profit_pct', 0.15)
            }

        except Exception as e:
            logger.error(f"Error cargando config de {worker_name}: {e}")
            return self._get_default_config(worker_name)

    def _get_default_config(self, worker_name: str) -> Dict:
        """Config por defecto si no se puede cargar el worker"""
        return {
            'worker_name': worker_name,
            'min_price': 1.0,
            'max_price': 50.0,
            'min_volume': 500000,
            'max_volume_ratio': 5.0,
            'position_size': 100,
            'stop_loss_pct': 0.05,
            'take_profit_pct': 0.15
        }

    async def run_backtest_period(
        self,
        worker_name: str,
        start_date: str,
        end_date: str,
        config: Dict
    ) -> Dict:
        """
        Ejecuta backtest para un período específico

        Args:
            worker_name: Nombre del worker
            start_date: Fecha inicio YYYY-MM-DD
            end_date: Fecha fin YYYY-MM-DD
            config: Configuración del worker

        Returns:
            Resultados del backtest para este período
        """
        logger.info(f"🔄 Running backtest: {worker_name} | {start_date} to {end_date}")

        # Inicializar replay engine
        replay_engine = ReplayEngine(db_path=self.db_path)

        try:
            # Ejecutar replay
            results = await replay_engine.run_replay(
                worker_name=worker_name,
                start_date=start_date,
                end_date=end_date,
                config=config
            )

            # Analizar resultados
            trades = results.get('trades', [])

            if not trades:
                return {
                    'period': f"{start_date} to {end_date}",
                    'trades': 0,
                    'total_pnl': 0,
                    'win_rate': 0,
                    'profit_factor': 0,
                    'avg_winner': 0,
                    'avg_loser': 0,
                    'max_drawdown': 0,
                    'sharpe_ratio': 0,
                    'verdict': '⚠️ NO DATA'
                }

            # Calcular métricas
            pnls = [t.get('pnl', 0) for t in trades]
            total_pnl = sum(pnls)

            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]

            win_rate = len(winners) / len(pnls) * 100 if pnls else 0

            avg_winner = sum(winners) / len(winners) if winners else 0
            avg_loser = sum(losers) / len(losers) if losers else 0

            # Profit factor
            total_wins = sum(winners) if winners else 0
            total_losses = abs(sum(losers)) if losers else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0

            # R/R Ratio
            rr_ratio = abs(avg_winner / avg_loser) if avg_loser != 0 else 0

            # Max Drawdown
            cumulative = 0
            peak = 0
            max_dd = 0
            for pnl in pnls:
                cumulative += pnl
                if cumulative > peak:
                    peak = cumulative
                drawdown = peak - cumulative
                if drawdown > max_dd:
                    max_dd = drawdown

            max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0

            # Sharpe Ratio (simplificado)
            if len(pnls) > 1:
                avg_pnl = sum(pnls) / len(pnls)
                std_pnl = (sum((p - avg_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5
                sharpe = (avg_pnl / std_pnl) * (252 ** 0.5) if std_pnl > 0 else 0
            else:
                sharpe = 0

            # Verdict del período
            verdict = self._evaluate_period(
                win_rate, profit_factor, len(trades), max_dd_pct
            )

            return {
                'period': f"{start_date} to {end_date}",
                'trades': len(trades),
                'total_pnl': round(total_pnl, 2),
                'win_rate': round(win_rate, 1),
                'profit_factor': round(profit_factor, 2),
                'rr_ratio': round(rr_ratio, 2),
                'avg_winner': round(avg_winner, 2),
                'avg_loser': round(avg_loser, 2),
                'max_drawdown': round(max_dd, 2),
                'max_drawdown_pct': round(max_dd_pct, 1),
                'sharpe_ratio': round(sharpe, 2),
                'verdict': verdict,
                'raw_trades': trades  # Guardar trades para análisis
            }

        except Exception as e:
            logger.error(f"Error en backtest: {e}")
            return {
                'period': f"{start_date} to {end_date}",
                'error': str(e),
                'verdict': '❌ ERROR'
            }

    def _evaluate_period(
        self,
        win_rate: float,
        profit_factor: float,
        trade_count: int,
        max_dd_pct: float
    ) -> str:
        """
        Evalúa si un período pasa los criterios de validación

        Returns:
            '✅ PASS', '⚠️ MARGINAL', o '❌ FAIL'
        """
        # Criterios de aprobación
        min_trades = 10  # Mínimo sample size por período
        min_win_rate = 45
        min_profit_factor = 1.3
        max_drawdown = 25

        if trade_count < min_trades:
            return '⚠️ INSUF DATA'

        passing_criteria = 0
        total_criteria = 4

        if win_rate >= min_win_rate:
            passing_criteria += 1
        if profit_factor >= min_profit_factor:
            passing_criteria += 1
        if max_dd_pct <= max_drawdown:
            passing_criteria += 1
        if trade_count >= min_trades:
            passing_criteria += 1

        if passing_criteria >= 3:
            return '✅ PASS'
        elif passing_criteria >= 2:
            return '⚠️ MARGINAL'
        else:
            return '❌ FAIL'

    def calculate_consistency_score(self, period_results: List[Dict]) -> float:
        """
        Calcula score de consistencia basado en períodos que pasan

        Args:
            period_results: Lista de resultados por período

        Returns:
            Consistency score 0-100%
        """
        valid_periods = [p for p in period_results if p.get('trades', 0) >= 10]

        if not valid_periods:
            return 0.0

        passed = sum(1 for p in valid_periods if '✅' in p.get('verdict', ''))
        return (passed / len(valid_periods)) * 100

    def generate_final_recommendation(
        self,
        worker_name: str,
        period_results: List[Dict],
        consistency_score: float
    ) -> Dict:
        """
        Genera recomendación final para el worker

        Returns:
            Dict con recomendación y justificación
        """
        # Métricas agregadas
        total_trades = sum(p.get('trades', 0) for p in period_results)
        total_pnl = sum(p.get('total_pnl', 0) for p in period_results)

        valid_periods = [p for p in period_results if p.get('trades', 0) >= 10]
        avg_win_rate = sum(p.get('win_rate', 0) for p in valid_periods) / len(valid_periods) if valid_periods else 0
        avg_pf = sum(p.get('profit_factor', 0) for p in valid_periods) / len(valid_periods) if valid_periods else 0

        # Decisión
        if consistency_score >= 75 and avg_win_rate >= 45 and avg_pf >= 1.3:
            action = '✅ MANTENER Y ESCALAR'
            reason = 'Consistentemente rentable en múltiples períodos'
            size_adjustment = 2.0  # 2x size
        elif consistency_score >= 50 and avg_win_rate >= 40:
            action = '⚠️ MANTENER PERO MONITOREAR'
            reason = 'Resultados inconsistentes, necesita más validación'
            size_adjustment = 1.0  # Mantener size
        else:
            action = '❌ DESHABILITAR'
            reason = 'No pasa criterios mínimos de rentabilidad o consistencia'
            size_adjustment = 0.0  # Deshabilitar

        return {
            'worker': worker_name,
            'action': action,
            'reason': reason,
            'size_adjustment': size_adjustment,
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 2),
            'consistency_score': round(consistency_score, 1),
            'avg_win_rate': round(avg_win_rate, 1),
            'avg_profit_factor': round(avg_pf, 2),
            'periods_tested': len(valid_periods)
        }

    def print_backtest_report(
        self,
        worker_name: str,
        period_results: List[Dict],
        recommendation: Dict
    ):
        """Imprime reporte detallado de backtest"""
        print("\n" + "=" * 100)
        print(f"BACKTEST CIENTÍFICO - {worker_name.upper()}")
        print("=" * 100)
        print()

        # Resumen por período
        print("📊 RESULTADOS POR PERÍODO")
        print("-" * 100)

        for i, result in enumerate(period_results, 1):
            if 'error' in result:
                print(f"\nPeríodo {i}: {result['period']}")
                print(f"   ❌ ERROR: {result['error']}")
                continue

            print(f"\nPeríodo {i}: {result['period']}")
            print(f"   Trades:         {result['trades']}")
            print(f"   P&L:            ${result['total_pnl']:>8.2f}")
            print(f"   Win Rate:       {result['win_rate']:>6.1f}%")
            print(f"   Profit Factor:  {result['profit_factor']:>6.2f}")
            print(f"   R/R Ratio:      {result['rr_ratio']:>6.2f}:1")
            print(f"   Avg Winner:     ${result['avg_winner']:>7.2f}")
            print(f"   Avg Loser:      ${result['avg_loser']:>7.2f}")
            print(f"   Max DD:         ${result['max_drawdown']:>7.2f} ({result['max_drawdown_pct']:.1f}%)")
            print(f"   Sharpe Ratio:   {result['sharpe_ratio']:>6.2f}")
            print(f"   Verdict:        {result['verdict']}")

        print()
        print("=" * 100)
        print("🎯 ANÁLISIS DE CONSISTENCIA")
        print("=" * 100)
        print()

        rec = recommendation
        print(f"Períodos testeados:     {rec['periods_tested']}")
        print(f"Total trades:           {rec['total_trades']}")
        print(f"Total P&L:              ${rec['total_pnl']:,.2f}")
        print(f"Consistency Score:      {rec['consistency_score']:.1f}%")
        print(f"Avg Win Rate:           {rec['avg_win_rate']:.1f}%")
        print(f"Avg Profit Factor:      {rec['avg_profit_factor']:.2f}")
        print()
        print(f"RECOMENDACIÓN FINAL:    {rec['action']}")
        print(f"Razón:                  {rec['reason']}")
        print(f"Ajuste de size:         {rec['size_adjustment']}x")
        print()
        print("=" * 100)
        print()

    async def backtest_worker(
        self,
        worker_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period_months: int = 2
    ) -> Dict:
        """
        Ejecuta backtest completo para un worker

        Args:
            worker_name: Nombre del worker
            start_date: Fecha inicio (opcional, usa todo el rango disponible)
            end_date: Fecha fin (opcional)
            period_months: Meses por período de análisis

        Returns:
            Dict con resultados completos
        """
        logger.info(f"\n🚀 Starting scientific backtest for: {worker_name}")

        # Obtener rango de fechas
        if not start_date or not end_date:
            db_start, db_end = self.get_available_date_range()
            start_date = start_date or db_start
            end_date = end_date or db_end

        logger.info(f"📅 Date range: {start_date} to {end_date}")

        # Dividir en períodos
        periods = self.split_into_periods(start_date, end_date, period_months)
        logger.info(f"📊 Divided into {len(periods)} periods for consistency analysis")

        # Obtener configuración del worker
        config = self.get_worker_config(worker_name)
        logger.info(f"⚙️  Worker config loaded: {config}")

        # Ejecutar backtest por período
        period_results = []
        for period_start, period_end in periods:
            result = await self.run_backtest_period(
                worker_name, period_start, period_end, config
            )
            period_results.append(result)

        # Calcular consistency score
        consistency_score = self.calculate_consistency_score(period_results)

        # Generar recomendación
        recommendation = self.generate_final_recommendation(
            worker_name, period_results, consistency_score
        )

        # Imprimir reporte
        self.print_backtest_report(worker_name, period_results, recommendation)

        # Guardar resultados
        results = {
            'worker': worker_name,
            'date_range': {'start': start_date, 'end': end_date},
            'period_results': period_results,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }

        return results

    def save_results(self, results: Dict, output_file: str):
        """Guarda resultados en JSON"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"✅ Results saved to: {output_file}")


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Scientific backtesting with replay')
    parser.add_argument('--worker', required=True, help='Worker name (e.g., vcp_smallcap)')
    parser.add_argument('--start-date', help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', help='End date YYYY-MM-DD')
    parser.add_argument('--period-months', type=int, default=2, help='Months per period')
    parser.add_argument('--output', help='Output JSON file')

    args = parser.parse_args()

    backtester = ScientificBacktester()

    results = await backtester.backtest_worker(
        worker_name=args.worker,
        start_date=args.start_date,
        end_date=args.end_date,
        period_months=args.period_months
    )

    if args.output:
        backtester.save_results(results, args.output)

    print("\n✅ Backtest complete!")


if __name__ == "__main__":
    asyncio.run(main())
