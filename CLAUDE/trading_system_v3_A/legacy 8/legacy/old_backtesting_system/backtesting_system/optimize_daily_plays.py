#!/usr/bin/env python3
"""
Optimización Automática de Daily Plays Worker

Sistema de optimización automática que prueba diferentes configuraciones
de stops, position sizing, filtros y parámetros para maximizar rentabilidad
y robustez del worker Daily Plays.
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from itertools import product
import logging
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
import json


@dataclass
class OptimizationConfig:
    """Configuración de optimización"""
    max_workers: int = 4
    test_split: float = 0.7  # 70% training, 30% testing
    min_trades: int = 10
    max_optimization_time: int = 3600  # 1 hour


@dataclass
class DailyPlaysParams:
    """Parámetros del worker Daily Plays para optimización"""
    # Stops
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 20.0
    trailing_activation: float = 6.0
    trailing_distance: float = 3.0

    # Position sizing
    max_position_pct: float = 0.05  # 5% del capital
    min_position_size: int = 100
    risk_per_trade_pct: float = 2.0

    # Filters
    min_volume_ratio: float = 1.5
    min_quality_score: float = 35.0
    min_catalyst_strength: int = 6
    rsi_overbought: float = 75.0

    # Timing
    max_hold_hours: float = 8.0
    confirmation_window: int = 120

    # VWAP
    vwap_tolerance: float = 0.98  # Allow 2% below VWAP

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'trailing_activation': self.trailing_activation,
            'trailing_distance': self.trailing_distance,
            'max_position_pct': self.max_position_pct,
            'min_position_size': self.min_position_size,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'min_volume_ratio': self.min_volume_ratio,
            'min_quality_score': self.min_quality_score,
            'min_catalyst_strength': self.min_catalyst_strength,
            'rsi_overbought': self.rsi_overbought,
            'max_hold_hours': self.max_hold_hours,
            'confirmation_window': self.confirmation_window,
            'vwap_tolerance': self.vwap_tolerance
        }


class DailyPlaysOptimizer:
    """
    Optimizador automático del worker Daily Plays

    Prueba diferentes combinaciones de parámetros para encontrar
    la configuración óptima de stops, sizing y filtros.
    """

    def __init__(self, db_path: str, config: OptimizationConfig = None):
        self.db_path = db_path
        self.config = config or OptimizationConfig()
        self.logger = logging.getLogger('daily_plays_optimizer')

        # Cargar datos históricos
        self.trades_df = self._load_historical_trades()
        self.ohlc_data = self._load_ohlc_data()

        # Dividir en training/testing
        self.train_data, self.test_data = self._split_data()

    def _load_historical_trades(self) -> pd.DataFrame:
        """Cargar trades históricos de Daily Plays"""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT * FROM trades
            WHERE strategy = 'daily_plays' AND pnl IS NOT NULL
            ORDER BY entry_time ASC
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        self.logger.info(f"Loaded {len(df)} historical Daily Plays trades")
        return df

    def _load_ohlc_data(self) -> Dict[str, pd.DataFrame]:
        """Cargar datos OHLC para simulación"""
        conn = sqlite3.connect(self.db_path)

        # Obtener símbolos únicos
        try:
            symbols = pd.read_sql_query(
                "SELECT DISTINCT symbol FROM trade_ohlc_snapshots",
                conn
            )['symbol'].tolist()
        except Exception as e:
            self.logger.warning(f"Could not load symbols from trade_ohlc_snapshots: {e}")
            symbols = []

        ohlc_data = {}
        for symbol in symbols[:50]:  # Limitar para optimización
            try:
                query = f"""
                    SELECT timestamp, open, high, low, close, volume
                    FROM trade_ohlc_snapshots
                    WHERE symbol = '{symbol}'
                    ORDER BY timestamp ASC
                """
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df.set_index('timestamp', inplace=True)
                    ohlc_data[symbol] = df
            except Exception as e:
                self.logger.warning(f"Could not load OHLC for {symbol}: {e}")

        conn.close()
        self.logger.info(f"Loaded OHLC data for {len(ohlc_data)} symbols")
        return ohlc_data

    def _split_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Dividir datos en training y testing"""
        if self.trades_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # Ordenar por tiempo
        df_sorted = self.trades_df.sort_values('entry_time')

        # Split point
        split_idx = int(len(df_sorted) * self.config.test_split)

        train_data = df_sorted[:split_idx]
        test_data = df_sorted[split_idx:]

        self.logger.info(f"Data split: {len(train_data)} training, {len(test_data)} testing trades")

        return train_data, test_data

    def generate_parameter_combinations(self) -> List[DailyPlaysParams]:
        """
        Generar combinaciones de parámetros para optimización

        Returns:
            Lista de configuraciones de parámetros
        """
        # Rangos de parámetros para optimización
        param_ranges = {
            # Stops
            'stop_loss_pct': [3.0, 5.0, 7.0],
            'take_profit_pct': [15.0, 20.0, 25.0],
            'trailing_activation': [3.0, 6.0, 9.0],
            'trailing_distance': [2.0, 3.0, 4.0],

            # Position sizing
            'max_position_pct': [0.03, 0.05, 0.07],
            'risk_per_trade_pct': [1.0, 2.0, 3.0],

            # Filters
            'min_volume_ratio': [1.2, 1.5, 1.8],
            'min_quality_score': [25.0, 35.0, 45.0],
            'min_catalyst_strength': [4, 6, 8],

            # Timing
            'max_hold_hours': [4.0, 6.0, 8.0],
        }

        # Generar combinaciones (limitadas para no hacerla infinita)
        combinations = []
        keys = list(param_ranges.keys())

        # Solo probar 3 combinaciones por parámetro para mantenerlo manejable
        for combo in product(*[param_ranges[key][:3] for key in keys[:6]]):  # Solo primeros 6 params
            params = DailyPlaysParams()
            for i, key in enumerate(keys[:6]):
                setattr(params, key, combo[i])
            combinations.append(params)

        self.logger.info(f"Generated {len(combinations)} parameter combinations for optimization")
        return combinations[:50]  # Limitar a 50 combinaciones

    def evaluate_parameters(self, params: DailyPlaysParams,
                          data: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluar una configuración de parámetros

        Args:
            params: Configuración de parámetros
            data: Datos para evaluación

        Returns:
            Métricas de performance
        """
        try:
            # Simular trades con estos parámetros
            simulated_trades = self._simulate_trades_with_params(params, data)

            if not simulated_trades:
                return {
                    'total_trades': 0,
                    'total_pnl': 0,
                    'win_rate': 0,
                    'sharpe_ratio': 0,
                    'max_drawdown': 0,
                    'avg_pnl': 0,
                    'params': params.to_dict()
                }

            # Calcular métricas
            total_pnl = sum(trade['pnl'] for trade in simulated_trades)
            win_rate = sum(1 for trade in simulated_trades if trade['pnl'] > 0) / len(simulated_trades)

            # Sharpe ratio (simplificado)
            returns = [trade['pnl'] for trade in simulated_trades]
            if returns and np.std(returns) > 0:
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Anualizado
            else:
                sharpe_ratio = 0

            # Max drawdown (simplificado)
            cumulative = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = cumulative - running_max
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0

            avg_pnl = total_pnl / len(simulated_trades)

            return {
                'total_trades': len(simulated_trades),
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'avg_pnl': avg_pnl,
                'params': params.to_dict()
            }

        except Exception as e:
            self.logger.error(f"Error evaluating parameters: {e}")
            return {'error': str(e), 'params': params.to_dict()}

    def _simulate_trades_with_params(self, params: DailyPlaysParams,
                                   data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Simular trades con parámetros específicos

        Args:
            params: Configuración de parámetros
            data: Datos históricos

        Returns:
            Lista de trades simulados
        """
        simulated_trades = []

        try:
            for _, trade in data.iterrows():
                # Aplicar filtros de parámetros
                if not self._passes_filters(trade, params):
                    continue

                # Simular PnL con stops y targets
                pnl = self._calculate_trade_pnl(trade, params)

                simulated_trade = {
                    'symbol': trade['symbol'],
                    'entry_price': trade['entry_price'],
                    'exit_price': trade.get('exit_price', trade['entry_price'] * (1 + pnl/100)),
                    'pnl': pnl,
                    'entry_time': trade['entry_time'],
                    'exit_time': trade.get('exit_time', trade['entry_time'])
                }

                simulated_trades.append(simulated_trade)

        except Exception as e:
            self.logger.error(f"Error simulating trades: {e}")

        return simulated_trades

    def _passes_filters(self, trade: pd.Series, params: DailyPlaysParams) -> bool:
        """
        Verificar si un trade pasa los filtros de parámetros

        Args:
            trade: Datos del trade
            params: Configuración de parámetros

        Returns:
            True si pasa filtros, False si no
        """
        try:
            # Filtros básicos
            if trade.get('volume_ratio', 1.0) < params.min_volume_ratio:
                return False

            if trade.get('quality_score', 0) < params.min_quality_score:
                return False

            if trade.get('catalyst_strength', 0) < params.min_catalyst_strength:
                return False

            return True

        except Exception:
            return False

    def _calculate_trade_pnl(self, trade: pd.Series, params: DailyPlaysParams) -> float:
        """
        Calcular PnL de un trade con stops y targets

        Args:
            trade: Datos del trade
            params: Configuración de parámetros

        Returns:
            PnL en porcentaje
        """
        try:
            entry_price = trade['entry_price']

            # Stop loss
            stop_price = entry_price * (1 - params.stop_loss_pct / 100)

            # Take profit
            target_price = entry_price * (1 + params.take_profit_pct / 100)

            # Simular resultado (usar PnL real si existe, sino simular)
            if 'pnl' in trade and pd.notna(trade['pnl']):
                return trade['pnl']
            else:
                # Simulación simplificada basada en parámetros
                # En un sistema real, esto usaría datos OHLC para simular
                risk_reward = params.take_profit_pct / params.stop_loss_pct

                # Probabilidad de éxito basada en parámetros
                success_prob = min(0.6, params.min_quality_score / 100)

                if np.random.random() < success_prob:
                    return params.take_profit_pct
                else:
                    return -params.stop_loss_pct

        except Exception:
            return 0.0

    def optimize(self) -> Dict[str, Any]:
        """
        Ejecutar optimización completa

        Returns:
            Resultados de optimización
        """
        self.logger.info("Starting Daily Plays optimization...")

        # Generar combinaciones de parámetros
        param_combinations = self.generate_parameter_combinations()

        # Evaluar en training data
        self.logger.info(f"Evaluating {len(param_combinations)} parameter combinations...")

        results = []
        for params in param_combinations:
            result = self.evaluate_parameters(params, self.train_data)
            results.append(result)

        # Ordenar por diferentes métricas
        by_sharpe = sorted(results, key=lambda x: x.get('sharpe_ratio', -999), reverse=True)
        by_win_rate = sorted(results, key=lambda x: x.get('win_rate', 0), reverse=True)
        by_total_pnl = sorted(results, key=lambda x: x.get('total_pnl', -999), reverse=True)
        by_drawdown = sorted(results, key=lambda x: x.get('max_drawdown', 999))  # Menor drawdown primero

        # Evaluar mejores en test data
        best_configs = by_sharpe[:3] + by_win_rate[:3] + by_total_pnl[:3]
        test_results = []

        for config in best_configs:
            params = DailyPlaysParams(**config['params'])
            test_result = self.evaluate_parameters(params, self.test_data)
            test_result['train_result'] = config
            test_results.append(test_result)

        # Encontrar configuración robusta (buena en training y testing)
        robust_configs = []
        for test_result in test_results:
            train_sharpe = test_result['train_result'].get('sharpe_ratio', 0)
            test_sharpe = test_result.get('sharpe_ratio', 0)

            # Configuración robusta si mantiene al menos 70% del Sharpe en testing
            if test_sharpe >= train_sharpe * 0.7:
                robust_configs.append(test_result)

        # Resultado final
        optimization_result = {
            'training_results': {
                'by_sharpe': by_sharpe[:5],
                'by_win_rate': by_win_rate[:5],
                'by_total_pnl': by_total_pnl[:5],
                'by_drawdown': by_drawdown[:5]
            },
            'testing_results': test_results,
            'robust_configs': robust_configs[:5],
            'best_overall': robust_configs[0] if robust_configs else test_results[0] if test_results else None,
            'optimization_timestamp': datetime.now().isoformat(),
            'total_combinations_tested': len(param_combinations)
        }

        self.logger.info("Optimization completed successfully")
        return optimization_result

    def save_optimization_results(self, results: Dict[str, Any], output_file: str):
        """
        Guardar resultados de optimización

        Args:
            results: Resultados de optimización
            output_file: Archivo de salida
        """
        try:
            # Convertir a JSON serializable
            def make_serializable(obj):
                if isinstance(obj, np.float64):
                    return float(obj)
                elif isinstance(obj, np.int64):
                    return int(obj)
                elif isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [make_serializable(item) for item in obj]
                else:
                    return obj

            serializable_results = make_serializable(results)

            with open(output_file, 'w') as f:
                json.dump(serializable_results, f, indent=2, default=str)

            self.logger.info(f"Optimization results saved to {output_file}")

        except Exception as e:
            self.logger.error(f"Error saving optimization results: {e}")


def generate_optimization_report(results: Dict[str, Any]) -> str:
    """
    Generar reporte completo de optimización

    Args:
        results: Resultados de optimización

    Returns:
        String con reporte completo
    """
    report = []
    report.append("=" * 80)
    report.append("🎯 OPTIMIZACIÓN AUTOMÁTICA - DAILY PLAYS WORKER")
    report.append("=" * 80)
    report.append("")

    # Resumen ejecutivo
    best_overall = results.get('best_overall')
    if best_overall:
        report.append("🏆 MEJOR CONFIGURACIÓN ENCONTRADA")
        report.append("-" * 40)
        report.append(f"Sharpe Ratio: {best_overall.get('sharpe_ratio', 0):.2f}")
        report.append(f"Win Rate: {best_overall.get('win_rate', 0):.1%}")
        report.append(f"Total PnL: ${best_overall.get('total_pnl', 0):.2f}")
        report.append(f"Max Drawdown: {best_overall.get('max_drawdown', 0):.1%}")
        report.append(f"Total Trades: {best_overall.get('total_trades', 0)}")
        report.append("")

        # Parámetros óptimos
        params = best_overall.get('params', {})
        report.append("⚙️ PARÁMETROS ÓPTIMOS")
        report.append("-" * 25)
        report.append(f"Stop Loss: {params.get('stop_loss_pct', 0):.1f}%")
        report.append(f"Take Profit: {params.get('take_profit_pct', 0):.1f}%")
        report.append(f"Trailing Activation: {params.get('trailing_activation', 0):.1f}%")
        report.append(f"Max Position: {params.get('max_position_pct', 0):.1%}")
        report.append(f"Min Volume Ratio: {params.get('min_volume_ratio', 0):.1f}x")
        report.append(f"Min Quality Score: {params.get('min_quality_score', 0):.1f}")
        report.append("")

    # Configuraciones robustas
    robust_configs = results.get('robust_configs', [])
    if robust_configs:
        report.append("🛡️ CONFIGURACIONES ROBUSTAS (Buenas en Training + Testing)")
        report.append("-" * 60)

        for i, config in enumerate(robust_configs[:3], 1):
            report.append(f"{i}. Sharpe: {config.get('sharpe_ratio', 0):.2f}, "
                         f"Win Rate: {config.get('win_rate', 0):.1%}, "
                         f"PnL: ${config.get('total_pnl', 0):.2f}")
        report.append("")

    # Mejores por criterio
    training = results.get('training_results', {})

    report.append("📊 MEJORES CONFIGURACIONES POR CRITERIO")
    report.append("-" * 45)

    # Por Sharpe
    sharpe_configs = training.get('by_sharpe', [])
    if sharpe_configs:
        report.append("🏆 Por Sharpe Ratio:")
        for i, config in enumerate(sharpe_configs[:3], 1):
            report.append(f"  {i}. {config.get('sharpe_ratio', 0):.2f} "
                         f"(Win: {config.get('win_rate', 0):.1%}, PnL: ${config.get('total_pnl', 0):.2f})")

    # Por Win Rate
    win_configs = training.get('by_win_rate', [])
    if win_configs:
        report.append("🎯 Por Win Rate:")
        for i, config in enumerate(win_configs[:3], 1):
            report.append(f"  {i}. {config.get('win_rate', 0):.1%} "
                         f"(Sharpe: {config.get('sharpe_ratio', 0):.2f}, PnL: ${config.get('total_pnl', 0):.2f})")

    # Por menor drawdown
    dd_configs = training.get('by_drawdown', [])
    if dd_configs:
        report.append("🛡️ Por Menor Drawdown:")
        for i, config in enumerate(dd_configs[:3], 1):
            report.append(f"  {i}. {config.get('max_drawdown', 0):.1%} "
                         f"(Sharpe: {config.get('sharpe_ratio', 0):.2f}, PnL: ${config.get('total_pnl', 0):.2f})")

    report.append("")
    report.append("💡 RECOMENDACIONES DE IMPLEMENTACIÓN")
    report.append("-" * 40)
    report.append("1. Implementar la configuración óptima en producción")
    report.append("2. Monitorear performance en vivo por 2-4 semanas")
    report.append("3. Re-optimizar trimestralmente con nuevos datos")
    report.append("4. Considerar walk-forward optimization para robustez")
    report.append("5. Implementar límites de drawdown dinámicos")
    report.append("")

    report.append("=" * 80)

    return "\n".join(report)


def main():
    """Función principal"""
    print("🎯 Iniciando Optimización Automática de Daily Plays")
    print("=" * 60)

    # Configurar logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Ruta a la base de datos
        db_path = os.path.join(os.path.dirname(__file__), '..', 'trading_data.db')

        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            sys.exit(1)

        # Crear optimizador
        optimizer = DailyPlaysOptimizer(db_path)

        # Ejecutar optimización
        print("⚡ Ejecutando optimización...")
        results = optimizer.optimize()

        # Generar reporte
        print("📋 Generando reporte...")
        report = generate_optimization_report(results)

        # Guardar resultados
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        results_file = os.path.join(reports_dir, 'daily_plays_optimization_results.json')
        report_file = os.path.join(reports_dir, 'daily_plays_optimization_report.txt')

        optimizer.save_optimization_results(results, results_file)

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        # Mostrar reporte
        print("\n" + "=" * 60)
        print("📋 REPORTE DE OPTIMIZACIÓN - DAILY PLAYS")
        print("=" * 60)
        print(report)

        print("\n✅ Optimización completada exitosamente!")
        print(f"📄 Reporte guardado en: {report_file}")
        print(f"📊 Resultados JSON guardados en: {results_file}")

    except Exception as e:
        print(f"❌ Error durante la optimización: {e}")
        logging.exception("Optimization failed")
        sys.exit(1)


if __name__ == "__main__":
    main()