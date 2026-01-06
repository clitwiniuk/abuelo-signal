#!/usr/bin/env python3
"""
Insights Engine - Motor de Insights Accionables
===============================================

Genera insights accionables basados en el análisis del sistema,
con recomendaciones específicas para optimización automática.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ActionableInsight:
    """Insight accionable con recomendación específica"""
    insight_id: str
    category: str  # 'risk', 'performance', 'efficiency', 'strategy'
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    title: str
    description: str
    recommendation: str
    expected_impact: str
    confidence_score: float  # 0-100
    data_evidence: Dict[str, Any]
    actionable: bool = True
    auto_implementable: bool = False
    implementation_complexity: str = 'LOW'  # 'LOW', 'MEDIUM', 'HIGH'
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para serialización"""
        return {
            'insight_id': self.insight_id,
            'category': self.category,
            'severity': self.severity,
            'title': self.title,
            'description': self.description,
            'recommendation': self.recommendation,
            'expected_impact': self.expected_impact,
            'confidence_score': self.confidence_score,
            'data_evidence': self.data_evidence,
            'actionable': self.actionable,
            'auto_implementable': self.auto_implementable,
            'implementation_complexity': self.implementation_complexity,
            'timestamp': self.timestamp.isoformat()
        }

class InsightsEngine:
    """
    Motor que genera insights accionables basados en análisis del sistema
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.InsightsEngine")
        self.generated_insights = []

    def generate_system_insights(self, system_analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """
        Generar insights específicos basados en análisis completo del sistema

        Args:
            system_analysis: Resultado del análisis del sistema

        Returns:
            Lista de insights accionables específicos
        """
        insights = []

        # 🔍 Insights de Rendimiento por Hora
        hourly_insights = self._analyze_hourly_performance(system_analysis)
        insights.extend(hourly_insights)

        # ✅ Insights de Estrategias
        strategy_insights = self._analyze_strategy_performance(system_analysis)
        insights.extend(strategy_insights)

        # ❌ Insights de Riesgo
        risk_insights = self._analyze_risk_metrics(system_analysis)
        insights.extend(risk_insights)

        # ⚡ Insights de Eficiencia
        efficiency_insights = self._analyze_system_efficiency(system_analysis)
        insights.extend(efficiency_insights)

        # 🔍 Insights de anomalías adicionales
        anomaly_insights = self._analyze_anomalies(system_analysis)
        insights.extend(anomaly_insights)

        # Filtrar y priorizar insights
        filtered_insights = self._filter_and_prioritize_insights(insights)

        self.generated_insights.extend(filtered_insights)
        self.logger.info(f"✅ Generated {len(filtered_insights)} actionable insights")

        return filtered_insights

    def _analyze_hourly_performance(self, analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """Analizar rendimiento por hora y generar insights específicos"""
        insights = []

        hourly_perf = analysis.get('hourly_performance', {})

        if not hourly_perf:
            return insights

        # 1. 🔍 Mejor Hora de Trading: Identifica horas con >60% win rate
        best_hour = None
        best_win_rate = 0
        best_trades = 0

        # 2. ❌ Hora con Alto Slippage: Detecta horas con >0.5% slippage promedio
        worst_hour_slippage = None
        worst_slippage = 0

        # 4. ❌ Hourly Overtrading: Exceso de trades en hora específica
        overtrading_hours = []

        for hour, metrics in hourly_perf.items():
            trade_count = metrics.get('trade_count', 0)

            if trade_count >= 5:  # Suficientes datos
                win_rate = metrics.get('win_rate', 0)
                slippage = metrics.get('avg_slippage_pct', 0)

                # Mejor hora para trading (>60% win rate)
                if win_rate > 0.6 and win_rate > best_win_rate:
                    best_win_rate = win_rate
                    best_hour = hour
                    best_trades = trade_count

                # Hora con alto slippage (>0.5%)
                if slippage > 0.5 and slippage > worst_slippage:
                    worst_slippage = slippage
                    worst_hour_slippage = hour

            # Hourly overtrading (>20 trades por hora)
            if trade_count > 20:
                overtrading_hours.append({
                    'hour': hour,
                    'trade_count': trade_count,
                    'avg_pnl': metrics.get('avg_pnl_per_trade', 0)
                })

        # Insight: Mejor Hora de Trading
        if best_hour is not None:
            insight = ActionableInsight(
                insight_id=f"best_trading_hour_{best_hour}",
                category='performance',
                severity='MEDIUM',
                title='Mejor Hora de Trading Identificada',
                description=f"Hora {best_hour}:00 muestra rendimiento excepcional con {best_win_rate:.1%} win rate ({best_trades} trades)",
                recommendation=f"Aumentar position sizing en 25-50% durante las horas {best_hour}:00",
                expected_impact='Mejorar rentabilidad general enfocándose en slots de alta probabilidad',
                confidence_score=min(95, best_win_rate * 100),
                data_evidence={
                    'best_hour': best_hour,
                    'win_rate': best_win_rate,
                    'trade_count': best_trades,
                    'avg_pnl_per_trade': hourly_perf[best_hour].get('avg_pnl_per_trade', 0)
                },
                auto_implementable=True,
                implementation_complexity='LOW'
            )
            insights.append(insight)

        # Insight: Hora con Alto Slippage
        if worst_hour_slippage is not None:
            insight = ActionableInsight(
                insight_id=f"high_slippage_hour_{worst_hour_slippage}",
                category='risk',
                severity='HIGH' if worst_slippage > 1.0 else 'MEDIUM',
                title='Hora con Alto Slippage Detectada',
                description=f"Hora {worst_hour_slippage}:00 muestra slippage elevado de {worst_slippage:.2f}%, incrementando costos de transacción",
                recommendation=f"Reducir position sizing en 30-50% o evitar trading durante horas {worst_hour_slippage}:00",
                expected_impact='Reducir costos de transacción y mejorar returns risk-adjusted',
                confidence_score=min(90, worst_slippage * 50),
                data_evidence={
                    'problem_hour': worst_hour_slippage,
                    'avg_slippage_pct': worst_slippage,
                    'trade_count': hourly_perf[worst_hour_slippage].get('trade_count', 0)
                },
                auto_implementable=True,
                implementation_complexity='LOW'
            )
            insights.append(insight)

        # Insight: Hourly Overtrading
        for overtrade in overtrading_hours:
            insight = ActionableInsight(
                insight_id=f"hourly_overtrading_{overtrade['hour']}",
                category='efficiency',
                severity='MEDIUM',
                title='Overtrading por Hora Detectado',
                description=f"Hora {overtrade['hour']}:00 tiene {overtrade['trade_count']} trades, excediendo límite saludable",
                recommendation=f"Implementar límites de frecuencia de trades para hora {overtrade['hour']}:00",
                expected_impact='Reducir costos de transacción y mejorar calidad de trades',
                confidence_score=75,
                data_evidence=overtrade,
                auto_implementable=True,
                implementation_complexity='LOW'
            )
            insights.append(insight)

        return insights

    def _analyze_strategy_performance(self, analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """Analizar rendimiento de estrategias y generar insights específicos"""
        insights = []

        strategy_perf = analysis.get('strategy_performance', {})

        if not strategy_perf:
            return insights

        # 1. ✅ Top Performing Strategy: Estrategias con >$500 profit total
        best_strategy = None
        best_pnl = 0
        best_win_rate = 0

        # 2. ❌ Underperforming Strategy: Estrategias con <40% win rate
        worst_strategy = None
        worst_win_rate = 1.0

        for strategy, metrics in strategy_perf.items():
            pnl = metrics.get('total_pnl', 0)
            win_rate = metrics.get('win_rate', 0)
            trades = metrics.get('total_trades', 0)

            if trades >= 10:  # Suficientes datos
                # Top performing strategy (> $500 profit)
                if pnl > 500 and pnl > best_pnl:
                    best_pnl = pnl
                    best_strategy = strategy
                    best_win_rate = win_rate

                # Underperforming strategy (<40% win rate)
                if win_rate < 0.4 and win_rate < worst_win_rate:
                    worst_win_rate = win_rate
                    worst_strategy = strategy

        # Insight: Top Performing Strategy
        if best_strategy:
            insight = ActionableInsight(
                insight_id=f"top_strategy_{best_strategy.replace(' ', '_').lower()}",
                category='performance',
                severity='MEDIUM',
                title='Top Performing Strategy Identificada',
                description=f"{best_strategy} muestra rendimiento outstanding con ${best_pnl:.2f} total PnL y {best_win_rate:.1%} win rate",
                recommendation=f"Aumentar capital allocation a {best_strategy} en 20-30%",
                expected_impact='Optimizar capital allocation para maximum returns',
                confidence_score=85,
                data_evidence={
                    'strategy': best_strategy,
                    'total_pnl': best_pnl,
                    'win_rate': best_win_rate,
                    'total_trades': strategy_perf[best_strategy].get('total_trades', 0)
                },
                auto_implementable=True,
                implementation_complexity='MEDIUM'
            )
            insights.append(insight)

        # Insight: Underperforming Strategy
        if worst_strategy:
            insight = ActionableInsight(
                insight_id=f"underperforming_strategy_{worst_strategy.replace(' ', '_').lower()}",
                category='strategy',
                severity='HIGH' if worst_win_rate < 0.3 else 'MEDIUM',
                title='Underperforming Strategy Detectada',
                description=f"{worst_strategy} muestra poor performance con {worst_win_rate:.1%} win rate",
                recommendation=f"Revisar {worst_strategy} strategy parameters o considerar desactivación temporal",
                expected_impact='Mejorar overall system win rate removiendo low-performing strategies',
                confidence_score=80,
                data_evidence={
                    'strategy': worst_strategy,
                    'win_rate': worst_win_rate,
                    'total_trades': strategy_perf[worst_strategy].get('total_trades', 0),
                    'total_pnl': strategy_perf[worst_strategy].get('total_pnl', 0)
                },
                auto_implementable=True,
                implementation_complexity='MEDIUM'
            )
            insights.append(insight)

        return insights

    def _analyze_risk_metrics(self, analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """Analizar métricas de riesgo y generar insights específicos"""
        insights = []

        # Análisis de volatilidad
        summary = analysis.get('summary', {})

        # 3. ❌ High Drawdown Risk: Drawdown >15% (CRITICAL si >25%)
        max_dd = summary.get('max_drawdown', 0)
        if max_dd > 0.15:  # >15% drawdown
            severity = 'CRITICAL' if max_dd > 0.25 else 'HIGH'

            insight = ActionableInsight(
                insight_id='high_drawdown_detected',
                category='risk',
                severity=severity,
                title='High Drawdown Risk Detectado',
                description=f"System experienced {max_dd:.1%} maximum drawdown, indicando elevated risk",
                recommendation='Implementar stricter risk management: reducir position sizes en 20-30% y agregar trailing stops',
                expected_impact='Reducir portfolio volatility y maximum loss potential',
                confidence_score=90,
                data_evidence={
                    'max_drawdown': max_dd,
                    'analysis_period_days': analysis.get('analysis_period_days', 30)
                },
                auto_implementable=True,
                implementation_complexity='LOW'
            )
            insights.append(insight)

        # 4. ❌ Low Sharpe Ratio: Sharpe <0.5 indica poor risk-adjusted returns
        sharpe = summary.get('sharpe_ratio', 0)
        if sharpe < 0.5:  # Sharpe ratio bajo
            insight = ActionableInsight(
                insight_id='low_sharpe_ratio',
                category='risk',
                severity='MEDIUM',
                title='Low Risk-Adjusted Returns',
                description=f"Sharpe ratio de {sharpe:.2f} indica poor risk-adjusted performance",
                recommendation='Enfocarse en strategies con better risk/reward profiles y reducir market exposure durante high volatility',
                expected_impact='Mejorar risk-adjusted returns optimizando strategy selection',
                confidence_score=75,
                data_evidence={
                    'sharpe_ratio': sharpe,
                    'total_pnl': summary.get('total_pnl', 0),
                    'total_trades': summary.get('total_trades_analyzed', 0)
                },
                auto_implementable=False,
                implementation_complexity='HIGH'
            )
            insights.append(insight)

        return insights

    def _analyze_system_efficiency(self, analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """Analizar eficiencia del sistema y detectar overtrading"""
        insights = []

        summary = analysis.get('summary', {})

        # 4. ❌ Overtrading Detection: >20 trades/día promedio
        total_trades = summary.get('total_trades_analyzed', 0)
        analysis_days = analysis.get('analysis_period_days', 30)
        avg_trades_per_day = total_trades / analysis_days if analysis_days > 0 else 0

        if avg_trades_per_day > 20:  # Más de 20 trades/día
            insight = ActionableInsight(
                insight_id='overtrading_detected',
                category='efficiency',
                severity='MEDIUM',
                title='Overtrading Detectado',
                description=f"System promediando {avg_trades_per_day:.1f} trades por día, potencialmente incrementando costos",
                recommendation='Implementar trade frequency limits y enfocarse en higher-quality opportunities',
                expected_impact='Reducir transaction costs y mejorar trade quality',
                confidence_score=70,
                data_evidence={
                    'avg_trades_per_day': avg_trades_per_day,
                    'total_trades': total_trades,
                    'analysis_period_days': analysis_days
                },
                auto_implementable=True,
                implementation_complexity='MEDIUM'
            )
            insights.append(insight)

        return insights

    def _analyze_anomalies(self, analysis: Dict[str, Any]) -> List[ActionableInsight]:
        """Convertir anomalías detectadas en insights"""
        insights = []

        anomalies = analysis.get('anomalies', [])

        for anomaly in anomalies:
            anomaly_type = anomaly.get('type', '')

            if anomaly_type == 'high_slippage_hour':
                # Ya manejado en _analyze_hourly_performance
                continue
            elif anomaly_type == 'underperforming_strategy':
                # Ya manejado en _analyze_strategy_performance
                continue
            elif anomaly_type == 'overtrading_hour':
                insight = ActionableInsight(
                    insight_id=f"overtrading_hour_{anomaly.get('hour', 0)}",
                    category='efficiency',
                    severity='MEDIUM',
                    title='Hourly Overtrading Detected',
                    description=f"Hour {anomaly.get('hour', 0)}:00 shows {anomaly.get('current_value', 0)} trades, exceeding recommended limit",
                    recommendation=f"Implement hourly trade limits for {anomaly.get('hour', 0)}:00 to prevent overtrading",
                    expected_impact='Reduce transaction costs and improve capital efficiency',
                    confidence_score=75,
                    data_evidence=anomaly,
                    auto_implementable=True,
                    implementation_complexity='LOW'
                )
                insights.append(insight)

        return insights

    def _filter_and_prioritize_insights(self, insights: List[ActionableInsight]) -> List[ActionableInsight]:
        """Filtrar y priorizar insights basado en severidad y confianza"""
        # Filtrar insights con baja confianza
        filtered = [i for i in insights if i.confidence_score >= 60]

        # Ordenar por severidad y confianza
        severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}

        filtered.sort(key=lambda x: (
            severity_order.get(x.severity, 0),
            x.confidence_score
        ), reverse=True)

        # Limitar a top 10 insights más importantes
        return filtered[:10]

    def get_insights_summary(self) -> Dict[str, Any]:
        """Obtener resumen de insights generados"""
        if not self.generated_insights:
            return {'total_insights': 0, 'insights_by_category': {}, 'insights_by_severity': {}}

        # Contar por categoría
        categories = {}
        severities = {}

        for insight in self.generated_insights:
            # Por categoría
            cat = insight.category
            categories[cat] = categories.get(cat, 0) + 1

            # Por severidad
            sev = insight.severity
            severities[sev] = severities.get(sev, 0) + 1

        return {
            'total_insights': len(self.generated_insights),
            'insights_by_category': categories,
            'insights_by_severity': severities,
            'auto_implementable': len([i for i in self.generated_insights if i.auto_implementable]),
            'high_priority': len([i for i in self.generated_insights if i.severity in ['CRITICAL', 'HIGH']])
        }

    def get_implementation_plan(self) -> List[Dict[str, Any]]:
        """Generar plan de implementación para insights auto-implementables"""
        implementable = [i for i in self.generated_insights if i.auto_implementable]

        plan = []
        for insight in implementable:
            plan.append({
                'insight_id': insight.insight_id,
                'title': insight.title,
                'implementation_complexity': insight.implementation_complexity,
                'expected_impact': insight.expected_impact,
                'recommendation': insight.recommendation,
                'priority': insight.severity
            })

        # Ordenar por complejidad (LOW primero) y severidad
        complexity_order = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}

        plan.sort(key=lambda x: (
            complexity_order.get(x['implementation_complexity'], 99),
            severity_order.get(x['priority'], 0)
        ), reverse=True)  # Más complejos primero? No, LOW primero

        plan.sort(key=lambda x: complexity_order.get(x['implementation_complexity'], 99))

        return plan