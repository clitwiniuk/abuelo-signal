#!/usr/bin/env python3
"""
TradeTally System Analyzer - Advanced Performance Analysis
==========================================================

Sistema de análisis avanzado que aprovecha la arquitectura híbrida:
- SQLite: Datos detallados de trades del sistema de trading
- PostgreSQL: Analytics agregados de TradeTally

Detecta ineficiencias, volatilidad anómala, y genera insights accionables
para optimizar el sistema de trading automático.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import statistics
import json

from .tradetally_sync import TradeTallyIntegration, TradeRecord

logger = logging.getLogger(__name__)

@dataclass
class HourlyPerformanceMetrics:
    """Métricas de rendimiento por hora del día"""
    hour: int
    total_trades: int = 0
    profitable_trades: int = 0
    total_pnl: float = 0.0
    avg_slippage_pct: float = 0.0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    volatility_score: float = 0.0

@dataclass
class StrategyPerformanceMetrics:
    """Métricas de rendimiento por estrategia"""
    strategy_name: str
    total_trades: int = 0
    profitable_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    avg_duration_minutes: float = 0.0

@dataclass
class SystemAnomaly:
    """Representa una anomalía detectada en el sistema"""
    anomaly_type: str  # 'high_slippage_hour', 'underperforming_strategy', 'volatility_spike'
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description: str
    recommendation: str
    affected_metric: str
    threshold_breached: Any
    current_value: Any
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SystemInsight:
    """Insight accionable generado por el análisis"""
    insight_type: str  # 'optimization', 'risk_warning', 'performance_improvement'
    priority: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    title: str
    description: str
    recommendation: str
    expected_impact: str
    data_evidence: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

class TradeTallySystemAnalyzer:
    """
    Analizador avanzado del sistema de trading usando arquitectura híbrida

    Aprovecha:
    - SQLite: Datos detallados de trades para análisis granular
    - TradeTally: Analytics agregados para validación

    Genera insights para optimización automática del sistema.
    """

    def __init__(self, db_path: str, tradetally_integration: Optional[TradeTallyIntegration] = None):
        """
        Inicializar el analizador del sistema

        Args:
            db_path: Ruta a la base de datos SQLite local
            tradetally_integration: Instancia de TradeTallyIntegration (opcional)
        """
        self.db_path = db_path
        self.tradetally_integration = tradetally_integration
        self.logger = logging.getLogger(f"{__name__}.TradeTallySystemAnalyzer")

        # Thresholds para detección de anomalías
        self.anomaly_thresholds = {
            'min_strategy_win_rate': 0.40,  # 40% mínimo win rate
            'max_hourly_slippage_pct': 0.50,  # 0.5% máximo slippage por hora
            'min_strategy_trades': 10,  # Mínimo 10 trades para análisis
            'volatility_zscore_threshold': 2.0,  # 2 desviaciones estándar
            'max_hourly_trades': 20  # Máximo trades saludables por hora
        }

    def analyze_hourly_performance(self, days_back: int = 30) -> Dict[int, HourlyPerformanceMetrics]:
        """
        Analizar rendimiento por hora del día basado en datos históricos

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas por hora (0-23)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Calcular fecha límite
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            # Query para obtener trades con hora de entrada
            query = """
                SELECT
                    strftime('%H', entry_time) as entry_hour,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                    SUM(pnl) as total_pnl,
                    AVG(ABS(entry_slippage_pct)) as avg_slippage_pct
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND entry_time IS NOT NULL
                GROUP BY strftime('%H', entry_time)
                ORDER BY entry_hour
            """

            cursor.execute(query, (cutoff_date,))
            rows = cursor.fetchall()
            conn.close()

            # Inicializar métricas para todas las horas
            hourly_metrics = {}
            for hour in range(24):
                hourly_metrics[hour] = HourlyPerformanceMetrics(hour=hour)

            # Llenar con datos reales
            for row in rows:
                hour = int(row['entry_hour'])
                if hour in hourly_metrics:
                    metrics = hourly_metrics[hour]
                    metrics.total_trades = row['total_trades']
                    metrics.profitable_trades = row['profitable_trades']
                    metrics.total_pnl = row['total_pnl'] or 0.0
                    metrics.avg_slippage_pct = row['avg_slippage_pct'] or 0.0

                    # Calcular métricas derivadas
                    if metrics.total_trades > 0:
                        metrics.win_rate = metrics.profitable_trades / metrics.total_trades
                        metrics.avg_pnl_per_trade = metrics.total_pnl / metrics.total_trades

            # Calcular volatilidad relativa entre horas
            pnl_values = [m.avg_pnl_per_trade for m in hourly_metrics.values() if m.total_trades > 0]
            if len(pnl_values) > 1:
                mean_pnl = statistics.mean(pnl_values)
                stdev_pnl = statistics.stdev(pnl_values)

                for metrics in hourly_metrics.values():
                    if metrics.total_trades > 0 and stdev_pnl > 0:
                        metrics.volatility_score = abs(metrics.avg_pnl_per_trade - mean_pnl) / stdev_pnl

            self.logger.info(f"✅ Análisis hourly performance completado: {sum(1 for m in hourly_metrics.values() if m.total_trades > 0)} horas con datos")
            return hourly_metrics

        except Exception as e:
            self.logger.error(f"❌ Error analizando hourly performance: {e}")
            return {}

    def analyze_strategy_performance(self, days_back: int = 30) -> Dict[str, StrategyPerformanceMetrics]:
        """
        Analizar rendimiento por estrategia basado en datos históricos

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con métricas por estrategia
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

            query = """
                SELECT
                    strategy,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as profitable_trades,
                    SUM(pnl) as total_pnl,
                    SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as total_losses,
                    AVG(duration_minutes) as avg_duration_minutes,
                    MIN(pnl) as max_drawdown
                FROM trades
                WHERE status = 'CLOSED'
                  AND entry_time >= ?
                  AND strategy IS NOT NULL
                  AND strategy != ''
                GROUP BY strategy
                HAVING COUNT(*) >= ?
                ORDER BY total_pnl DESC
            """

            cursor.execute(query, (cutoff_date, self.anomaly_thresholds['min_strategy_trades']))
            rows = cursor.fetchall()
            conn.close()

            strategy_metrics = {}

            for row in rows:
                strategy = row['strategy']
                metrics = StrategyPerformanceMetrics(strategy_name=strategy)

                metrics.total_trades = row['total_trades']
                metrics.profitable_trades = row['profitable_trades']
                metrics.total_pnl = row['total_pnl'] or 0.0
                total_losses = row['total_losses'] or 0.0
                metrics.avg_duration_minutes = row['avg_duration_minutes'] or 0.0
                metrics.max_drawdown = abs(row['max_drawdown']) if row['max_drawdown'] else 0.0

                # Calcular métricas derivadas
                if metrics.total_trades > 0:
                    metrics.win_rate = metrics.profitable_trades / metrics.total_trades
                    metrics.avg_pnl_per_trade = metrics.total_pnl / metrics.total_trades

                # Profit factor
                if total_losses > 0:
                    metrics.profit_factor = metrics.total_pnl / total_losses if metrics.total_pnl > 0 else 0.0

                strategy_metrics[strategy] = metrics

            self.logger.info(f"✅ Análisis strategy performance completado: {len(strategy_metrics)} estrategias analizadas")
            return strategy_metrics

        except Exception as e:
            self.logger.error(f"❌ Error analizando strategy performance: {e}")
            return {}

    def detect_anomalies(self, hourly_metrics: Dict[int, HourlyPerformanceMetrics],
                        strategy_metrics: Dict[str, StrategyPerformanceMetrics]) -> List[SystemAnomaly]:
        """
        Detectar anomalías en el sistema basadas en métricas analizadas

        Args:
            hourly_metrics: Métricas por hora
            strategy_metrics: Métricas por estrategia

        Returns:
            Lista de anomalías detectadas
        """
        anomalies = []

        # 1. Detectar horas con alto slippage
        for hour, metrics in hourly_metrics.items():
            if (metrics.total_trades >= 5 and
                metrics.avg_slippage_pct > self.anomaly_thresholds['max_hourly_slippage_pct']):

                anomaly = SystemAnomaly(
                    anomaly_type='high_slippage_hour',
                    severity='HIGH' if metrics.avg_slippage_pct > 1.0 else 'MEDIUM',
                    description=f"High slippage at {hour}:00 ({metrics.avg_slippage_pct:.2f}%)",
                    recommendation=f"Reduce position sizing during {hour}:00 hours or avoid trading in this time slot",
                    affected_metric='avg_slippage_pct',
                    threshold_breached=self.anomaly_thresholds['max_hourly_slippage_pct'],
                    current_value=metrics.avg_slippage_pct
                )
                anomalies.append(anomaly)

        # 2. Detectar estrategias con bajo rendimiento
        for strategy, metrics in strategy_metrics.items():
            if metrics.win_rate < self.anomaly_thresholds['min_strategy_win_rate']:
                severity = 'CRITICAL' if metrics.win_rate < 0.30 else 'HIGH'

                anomaly = SystemAnomaly(
                    anomaly_type='underperforming_strategy',
                    severity=severity,
                    description=f"{strategy} win rate: {metrics.win_rate:.1%} ({metrics.total_trades} trades)",
                    recommendation=f"Review or disable {strategy} strategy. Consider modifying entry conditions or risk management.",
                    affected_metric='win_rate',
                    threshold_breached=self.anomaly_thresholds['min_strategy_win_rate'],
                    current_value=metrics.win_rate
                )
                anomalies.append(anomaly)

        # 3. Detectar horas con demasiados trades (posible overtrading)
        for hour, metrics in hourly_metrics.items():
            if metrics.total_trades > self.anomaly_thresholds['max_hourly_trades']:
                anomaly = SystemAnomaly(
                    anomaly_type='overtrading_hour',
                    severity='MEDIUM',
                    description=f"High trade frequency at {hour}:00 ({metrics.total_trades} trades)",
                    recommendation=f"Implement trade frequency limits for {hour}:00 hour to prevent overtrading",
                    affected_metric='total_trades',
                    threshold_breached=self.anomaly_thresholds['max_hourly_trades'],
                    current_value=metrics.total_trades
                )
                anomalies.append(anomaly)

        # 4. Detectar volatilidad extrema en horas
        pnl_values = [m.avg_pnl_per_trade for m in hourly_metrics.values() if m.total_trades >= 3]
        if len(pnl_values) > 1:
            mean_pnl = statistics.mean(pnl_values)
            stdev_pnl = statistics.stdev(pnl_values)

            for hour, metrics in hourly_metrics.items():
                if metrics.total_trades >= 3 and stdev_pnl > 0:
                    z_score = abs(metrics.avg_pnl_per_trade - mean_pnl) / stdev_pnl
                    if z_score > self.anomaly_thresholds['volatility_zscore_threshold']:
                        direction = "extremely profitable" if metrics.avg_pnl_per_trade > mean_pnl else "extremely unprofitable"

                        anomaly = SystemAnomaly(
                            anomaly_type='volatility_spike',
                            severity='MEDIUM',
                            description=f"{hour}:00 shows {direction} performance (z-score: {z_score:.1f})",
                            recommendation=f"Investigate unusual performance at {hour}:00. Check for data quality or external factors.",
                            affected_metric='pnl_volatility',
                            threshold_breached=self.anomaly_thresholds['volatility_zscore_threshold'],
                            current_value=z_score
                        )
                        anomalies.append(anomaly)

        self.logger.info(f"🔍 Anomalías detectadas: {len(anomalies)}")
        return anomalies

    def generate_insights(self, anomalies: List[SystemAnomaly],
                         hourly_metrics: Dict[int, HourlyPerformanceMetrics],
                         strategy_metrics: Dict[str, StrategyPerformanceMetrics]) -> List[SystemInsight]:
        """
        Generar insights accionables basados en anomalías y métricas

        Args:
            anomalies: Lista de anomalías detectadas
            hourly_metrics: Métricas por hora
            strategy_metrics: Métricas por estrategia

        Returns:
            Lista de insights accionables
        """
        insights = []

        # Convertir anomalías en insights
        for anomaly in anomalies:
            if anomaly.anomaly_type == 'high_slippage_hour':
                insight = SystemInsight(
                    insight_type='risk_warning',
                    priority=anomaly.severity,
                    title='High Slippage Time Slot Detected',
                    description=anomaly.description,
                    recommendation=anomaly.recommendation,
                    expected_impact='Reduce transaction costs and improve profitability',
                    data_evidence={
                        'anomaly_type': anomaly.anomaly_type,
                        'affected_hour': anomaly.description.split()[2].replace(':00', ''),
                        'current_slippage': anomaly.current_value,
                        'threshold': anomaly.threshold_breached
                    }
                )
                insights.append(insight)

            elif anomaly.anomaly_type == 'underperforming_strategy':
                insight = SystemInsight(
                    insight_type='optimization',
                    priority=anomaly.severity,
                    title='Underperforming Strategy Identified',
                    description=anomaly.description,
                    recommendation=anomaly.recommendation,
                    expected_impact='Improve overall system win rate and profitability',
                    data_evidence={
                        'anomaly_type': anomaly.anomaly_type,
                        'strategy': anomaly.description.split()[0],
                        'win_rate': anomaly.current_value,
                        'total_trades': anomaly.description.split('(')[1].split()[0]
                    }
                )
                insights.append(insight)

        # Insights adicionales basados en patrones generales

        # 1. Encontrar mejor hora para trading
        best_hour = None
        best_win_rate = 0.0

        for hour, metrics in hourly_metrics.items():
            if metrics.total_trades >= 10 and metrics.win_rate > best_win_rate:
                best_win_rate = metrics.win_rate
                best_hour = hour

        if best_hour is not None:
            insight = SystemInsight(
                insight_type='performance_improvement',
                priority='MEDIUM',
                title='Optimal Trading Hour Identified',
                description=f"Best performance at {best_hour}:00 with {best_win_rate:.1%} win rate",
                recommendation=f"Consider increasing position sizing or trade frequency during {best_hour}:00 hours",
                expected_impact='Maximize returns by focusing on high-probability time slots',
                data_evidence={
                    'best_hour': best_hour,
                    'win_rate': best_win_rate,
                    'total_trades': hourly_metrics[best_hour].total_trades
                }
            )
            insights.append(insight)

        # 2. Encontrar estrategia más rentable
        best_strategy = None
        best_pnl = 0.0

        for strategy, metrics in strategy_metrics.items():
            if metrics.total_pnl > best_pnl:
                best_pnl = metrics.total_pnl
                best_strategy = strategy

        if best_strategy and best_pnl > 100:  # Más de $100 profit
            insight = SystemInsight(
                insight_type='performance_improvement',
                priority='MEDIUM',
                title='Top Performing Strategy Identified',
                description=f"{best_strategy} shows strongest performance with ${best_pnl:.2f} total PnL",
                recommendation=f"Increase allocation to {best_strategy} strategy",
                expected_impact='Optimize capital allocation for maximum returns',
                data_evidence={
                    'strategy': best_strategy,
                    'total_pnl': best_pnl,
                    'win_rate': strategy_metrics[best_strategy].win_rate
                }
            )
            insights.append(insight)

        self.logger.info(f"💡 Insights generados: {len(insights)}")
        return insights

    def generate_full_analysis(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Generar análisis completo del sistema

        Args:
            days_back: Días hacia atrás para analizar

        Returns:
            Dict con análisis completo
        """
        self.logger.info(f"🔍 Iniciando análisis completo del sistema ({days_back} días)")

        try:
            # Obtener métricas base
            hourly_metrics = self.analyze_hourly_performance(days_back)
            strategy_metrics = self.analyze_strategy_performance(days_back)

            # Detectar anomalías
            anomalies = self.detect_anomalies(hourly_metrics, strategy_metrics)

            # Generar insights
            insights = self.generate_insights(anomalies, hourly_metrics, strategy_metrics)

            # Obtener datos de TradeTally para validación (si disponible)
            tradetally_validation = {}
            if self.tradetally_integration:
                try:
                    # Comparar con analytics de TradeTally
                    tt_analytics = self.tradetally_integration.get_current_analytics()
                    if tt_analytics:
                        tradetally_validation = {
                            'total_trades_tt': tt_analytics.get('totalTrades', 0),
                            'win_rate_tt': tt_analytics.get('winRate', 0),
                            'total_pnl_tt': tt_analytics.get('totalPnl', 0)
                        }
                except Exception as e:
                    self.logger.warning(f"Could not get TradeTally validation data: {e}")

            # Compilar resultado final
            analysis = {
                'analysis_period_days': days_back,
                'generated_at': datetime.now().isoformat(),
                'hourly_performance': {
                    hour: {
                        'total_trades': metrics.total_trades,
                        'win_rate': metrics.win_rate,
                        'avg_pnl_per_trade': metrics.avg_pnl_per_trade,
                        'avg_slippage_pct': metrics.avg_slippage_pct,
                        'volatility_score': metrics.volatility_score
                    }
                    for hour, metrics in hourly_metrics.items()
                    if metrics.total_trades > 0
                },
                'strategy_performance': {
                    strategy: {
                        'total_trades': metrics.total_trades,
                        'win_rate': metrics.win_rate,
                        'total_pnl': metrics.total_pnl,
                        'profit_factor': metrics.profit_factor,
                        'avg_duration_minutes': metrics.avg_duration_minutes
                    }
                    for strategy, metrics in strategy_metrics.items()
                },
                'anomalies': [
                    {
                        'type': anomaly.anomaly_type,
                        'severity': anomaly.severity,
                        'description': anomaly.description,
                        'recommendation': anomaly.recommendation,
                        'timestamp': anomaly.timestamp.isoformat()
                    }
                    for anomaly in anomalies
                ],
                'insights': [
                    {
                        'type': insight.insight_type,
                        'priority': insight.priority,
                        'title': insight.title,
                        'description': insight.description,
                        'recommendation': insight.recommendation,
                        'expected_impact': insight.expected_impact,
                        'data_evidence': insight.data_evidence,
                        'timestamp': insight.timestamp.isoformat()
                    }
                    for insight in insights
                ],
                'tradetally_validation': tradetally_validation,
                'summary': {
                    'total_trades_analyzed': sum(m.total_trades for m in hourly_metrics.values()),
                    'strategies_analyzed': len(strategy_metrics),
                    'anomalies_detected': len(anomalies),
                    'insights_generated': len(insights),
                    'analysis_status': 'completed'
                }
            }

            self.logger.info(f"✅ Análisis completo generado: {analysis['summary']}")
            return analysis

        except Exception as e:
            self.logger.error(f"❌ Error generando análisis completo: {e}")
            return {
                'error': str(e),
                'analysis_status': 'failed',
                'generated_at': datetime.now().isoformat()
            }

    def get_quick_health_check(self) -> Dict[str, Any]:
        """
        Health check rápido del sistema (últimas 24 horas)

        Returns:
            Dict con estado de salud del sistema
        """
        try:
            # Análisis rápido de últimas 24 horas
            analysis = self.generate_full_analysis(days_back=1)

            if 'error' in analysis:
                return {
                    'status': 'error',
                    'message': analysis['error'],
                    'timestamp': datetime.now().isoformat()
                }

            # Evaluar salud basada en anomalías críticas
            critical_anomalies = [a for a in analysis.get('anomalies', [])
                                if a['severity'] == 'CRITICAL']

            if critical_anomalies:
                health_status = 'critical'
                message = f"{len(critical_anomalies)} critical issues detected"
            elif len(analysis.get('anomalies', [])) > 0:
                health_status = 'warning'
                message = f"{len(analysis['anomalies'])} issues detected"
            else:
                health_status = 'healthy'
                message = 'System operating normally'

            return {
                'status': health_status,
                'message': message,
                'trades_last_24h': analysis['summary']['total_trades_analyzed'],
                'anomalies_count': len(analysis.get('anomalies', [])),
                'insights_count': len(analysis.get('insights', [])),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f"Health check failed: {e}",
                'timestamp': datetime.now().isoformat()
            }