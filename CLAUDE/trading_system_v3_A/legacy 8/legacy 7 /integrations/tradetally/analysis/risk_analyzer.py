#!/usr/bin/env python3
"""
Risk Analyzer - Análisis de Riesgo del Sistema
==============================================

Analiza riesgos del sistema de trading incluyendo volatilidad,
correlación, exposición máxima, y detección de anomalías.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import statistics
import math

logger = logging.getLogger(__name__)

class RiskAnalyzer:
    """
    Analizador de riesgo que evalúa la exposición y volatilidad
    del sistema de trading usando datos históricos.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(f"{__name__}.RiskAnalyzer")

    def analyze_volatility_by_hour(self, days_back: int = 30) -> Dict[int, Dict[str, float]]:
        """
        Analizar volatilidad de PnL por hora del día

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas de volatilidad por hora
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            query = """
                SELECT
                    strftime('%H', entry_time) as entry_hour,
                    pnl
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND pnl IS NOT NULL
                ORDER BY entry_time
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()
            conn.close()

            # Agrupar por hora
            hourly_pnls = {}
            for row in rows:
                hour = int(row['entry_hour'])
                pnl = row['pnl']

                if hour not in hourly_pnls:
                    hourly_pnls[hour] = []
                hourly_pnls[hour].append(pnl)

            # Calcular métricas de volatilidad por hora
            volatility_analysis = {}

            for hour in range(24):
                pnls = hourly_pnls.get(hour, [])

                if len(pnls) >= 3:  # Necesitamos al menos 3 trades para estadísticas significativas
                    volatility_analysis[hour] = {
                        'trade_count': len(pnls),
                        'mean_pnl': statistics.mean(pnls),
                        'std_dev_pnl': statistics.stdev(pnls),
                        'min_pnl': min(pnls),
                        'max_pnl': max(pnls),
                        'cv_pnl': statistics.stdev(pnls) / abs(statistics.mean(pnls)) if statistics.mean(pnls) != 0 else 0,
                        'skewness': self._calculate_skewness(pnls),
                        'kurtosis': self._calculate_kurtosis(pnls)
                    }
                else:
                    volatility_analysis[hour] = {
                        'trade_count': len(pnls),
                        'mean_pnl': statistics.mean(pnls) if pnls else 0,
                        'std_dev_pnl': 0,
                        'min_pnl': min(pnls) if pnls else 0,
                        'max_pnl': max(pnls) if pnls else 0,
                        'cv_pnl': 0,
                        'skewness': 0,
                        'kurtosis': 0
                    }

            self.logger.info(f"✅ Volatility analysis completed: {sum(1 for v in volatility_analysis.values() if v['trade_count'] >= 3)} hours with sufficient data")
            return volatility_analysis

        except Exception as e:
            self.logger.error(f"❌ Error analyzing volatility by hour: {e}")
            return {}

    def analyze_slippage_patterns(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Analizar patrones de slippage en el sistema

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con análisis de slippage
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            query = """
                SELECT
                    entry_slippage_pct,
                    total_slippage_impact,
                    strftime('%H', entry_time) as entry_hour,
                    strategy,
                    pnl
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND entry_slippage_pct IS NOT NULL
                ORDER BY entry_time
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {'error': 'No slippage data available'}

            # Análisis general
            slippage_pcts = [row['entry_slippage_pct'] for row in rows if row['entry_slippage_pct'] is not None]
            slippage_impacts = [row['total_slippage_impact'] for row in rows if row['total_slippage_impact'] is not None]

            # Análisis por hora
            hourly_slippage = {}
            for row in rows:
                hour = int(row['entry_hour'])
                slippage_pct = row['entry_slippage_pct']

                if slippage_pct is not None:
                    if hour not in hourly_slippage:
                        hourly_slippage[hour] = []
                    hourly_slippage[hour].append(slippage_pct)

            # Calcular slippage promedio por hora
            avg_hourly_slippage = {}
            for hour, slippages in hourly_slippage.items():
                if slippages:
                    avg_hourly_slippage[hour] = {
                        'avg_slippage_pct': statistics.mean(slippages),
                        'max_slippage_pct': max(slippages),
                        'slippage_count': len(slippages)
                    }

            # Análisis por estrategia
            strategy_slippage = {}
            for row in rows:
                strategy = row['strategy'] or 'unknown'
                slippage_pct = row['entry_slippage_pct']

                if slippage_pct is not None:
                    if strategy not in strategy_slippage:
                        strategy_slippage[strategy] = []
                    strategy_slippage[strategy].append(slippage_pct)

            avg_strategy_slippage = {}
            for strategy, slippages in strategy_slippage.items():
                if len(slippages) >= 3:
                    avg_strategy_slippage[strategy] = {
                        'avg_slippage_pct': statistics.mean(slippages),
                        'slippage_std_dev': statistics.stdev(slippages),
                        'trade_count': len(slippages)
                    }

            # Detectar horas problemáticas
            problematic_hours = []
            for hour, data in avg_hourly_slippage.items():
                if data['avg_slippage_pct'] > 0.5:  # >0.5% slippage promedio
                    problematic_hours.append({
                        'hour': hour,
                        'avg_slippage_pct': data['avg_slippage_pct'],
                        'severity': 'HIGH' if data['avg_slippage_pct'] > 1.0 else 'MEDIUM'
                    })

            result = {
                'overall_stats': {
                    'total_trades_with_slippage': len(slippage_pcts),
                    'avg_slippage_pct': statistics.mean(slippage_pcts) if slippage_pcts else 0,
                    'median_slippage_pct': statistics.median(slippage_pcts) if slippage_pcts else 0,
                    'max_slippage_pct': max(slippage_pcts) if slippage_pcts else 0,
                    'slippage_std_dev': statistics.stdev(slippage_pcts) if len(slippage_pcts) > 1 else 0,
                    'total_slippage_impact': sum(slippage_impacts) if slippage_impacts else 0
                },
                'hourly_slippage': avg_hourly_slippage,
                'strategy_slippage': avg_strategy_slippage,
                'problematic_hours': problematic_hours,
                'analysis_period_days': days_back
            }

            self.logger.info(f"✅ Slippage analysis completed: {len(problematic_hours)} problematic hours detected")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error analyzing slippage patterns: {e}")
            return {'error': str(e)}

    def analyze_correlation_matrix(self, strategies: List[str], days_back: int = 30) -> Dict[str, Any]:
        """
        Analizar matriz de correlación entre estrategias

        Args:
            strategies: Lista de estrategias a analizar
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con matriz de correlación
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Obtener retornos diarios por estrategia
            strategy_returns = {}

            for strategy in strategies:
                query = """
                    SELECT date(entry_time) as trade_date, SUM(pnl) as daily_pnl
                    FROM trades
                    WHERE strategy = ?
                      AND status = 'CLOSED'
                      AND entry_time >= ?
                      AND pnl IS NOT NULL
                    GROUP BY date(entry_time)
                    ORDER BY trade_date
                """

                cursor.execute(query, (strategy, cutoff_date))
                rows = cursor.fetchall()

                daily_returns = [row['daily_pnl'] / 10000 for row in rows]  # Normalizar a retornos
                strategy_returns[strategy] = daily_returns

            conn.close()

            # Calcular matriz de correlación
            correlation_matrix = {}

            for strat1 in strategies:
                correlation_matrix[strat1] = {}
                returns1 = strategy_returns.get(strat1, [])

                if len(returns1) < 3:  # Necesitamos suficientes datos
                    for strat2 in strategies:
                        correlation_matrix[strat1][strat2] = 0.0
                    continue

                for strat2 in strategies:
                    returns2 = strategy_returns.get(strat2, [])

                    if len(returns2) < 3:
                        correlation_matrix[strat1][strat2] = 0.0
                        continue

                    # Calcular correlación solo si ambas estrategias tienen datos suficientes
                    min_length = min(len(returns1), len(returns2))
                    if min_length >= 3:
                        try:
                            correlation = statistics.correlation(
                                returns1[:min_length],
                                returns2[:min_length]
                            )
                            correlation_matrix[strat1][strat2] = correlation
                        except:
                            correlation_matrix[strat1][strat2] = 0.0
                    else:
                        correlation_matrix[strat1][strat2] = 0.0

            # Identificar estrategias altamente correlacionadas
            high_correlation_pairs = []
            for i, strat1 in enumerate(strategies):
                for strat2 in strategies[i+1:]:
                    corr = abs(correlation_matrix[strat1][strat2])
                    if corr > 0.7:  # Correlación alta
                        high_correlation_pairs.append({
                            'strategy1': strat1,
                            'strategy2': strat2,
                            'correlation': correlation_matrix[strat1][strat2],
                            'risk_level': 'HIGH' if corr > 0.8 else 'MEDIUM'
                        })

            result = {
                'correlation_matrix': correlation_matrix,
                'high_correlation_pairs': high_correlation_pairs,
                'strategies_analyzed': strategies,
                'analysis_period_days': days_back
            }

            self.logger.info(f"✅ Correlation analysis completed: {len(high_correlation_pairs)} high correlation pairs found")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error analyzing correlation matrix: {e}")
            return {'error': str(e)}

    def calculate_var_metrics(self, confidence_level: float = 0.95, days_back: int = 30) -> Dict[str, Any]:
        """
        Calcular métricas de Value at Risk (VaR)

        Args:
            confidence_level: Nivel de confianza (0.95 = 95%)
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas de VaR
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Obtener PnL diario
            query = """
                SELECT date(entry_time) as trade_date, SUM(pnl) as daily_pnl
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND pnl IS NOT NULL
                GROUP BY date(entry_time)
                ORDER BY trade_date
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()
            conn.close()

            daily_pnls = [row['daily_pnl'] for row in rows]

            if len(daily_pnls) < 10:  # Necesitamos suficientes datos
                return {'error': 'Insufficient data for VaR calculation'}

            # Calcular retornos diarios
            daily_returns = [pnl / 10000 for pnl in daily_pnls]  # Normalizar

            # VaR histórico
            sorted_returns = sorted(daily_returns)
            var_index = int((1 - confidence_level) * len(sorted_returns))
            historical_var = abs(sorted_returns[var_index])

            # Expected Shortfall (CVaR)
            tail_returns = sorted_returns[:var_index + 1]
            expected_shortfall = abs(statistics.mean(tail_returns))

            # Volatilidad anualizada
            volatility = statistics.stdev(daily_returns) * math.sqrt(252)  # 252 días de trading

            result = {
                'confidence_level': confidence_level,
                'historical_var': historical_var,
                'expected_shortfall': expected_shortfall,
                'volatility_ann': volatility,
                'max_daily_loss': abs(min(daily_pnls)),
                'var_as_percentage': historical_var * 100,
                'analysis_period_days': days_back,
                'data_points': len(daily_returns)
            }

            self.logger.info(f"✅ VaR analysis completed: {confidence_level:.0%} VaR = {historical_var:.4f}")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error calculating VaR metrics: {e}")
            return {'error': str(e)}

    def _calculate_skewness(self, data: List[float]) -> float:
        """Calcular skewness de una distribución"""
        if len(data) < 3:
            return 0.0

        try:
            mean = statistics.mean(data)
            std_dev = statistics.stdev(data)

            if std_dev == 0:
                return 0.0

            skewness = sum(((x - mean) / std_dev) ** 3 for x in data) / len(data)
            return skewness

        except:
            return 0.0

    def _calculate_kurtosis(self, data: List[float]) -> float:
        """Calcular kurtosis de una distribución"""
        if len(data) < 4:
            return 0.0

        try:
            mean = statistics.mean(data)
            std_dev = statistics.stdev(data)

            if std_dev == 0:
                return 0.0

            kurtosis = sum(((x - mean) / std_dev) ** 4 for x in data) / len(data) - 3
            return kurtosis

        except:
            return 0.0