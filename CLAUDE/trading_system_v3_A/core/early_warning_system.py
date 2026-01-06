#!/usr/bin/env python3
"""
Early Warning System - Sistema de Alertas Tempranas

Combina señales de Order Flow + Consolidation Patterns para generar alertas predictivas
de breakouts inminentes antes de que ocurran.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

try:
    from core.interfaces import MarketData
    from core.order_flow_analyzer import OrderFlowAnalyzer, OrderFlowSignal
    from core.consolidation_detector import ConsolidationDetector, ConsolidationSignal
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'bid', 'ask', 'bid_size', 'ask_size'])

@dataclass
class EarlyWarningAlert:
    """Alerta de early warning generada"""
    symbol: str
    timestamp: datetime
    alert_type: str  # 'BREAKOUT_IMMINENT', 'MOMENTUM_BUILDING', 'INSTITUTIONAL_ACTIVITY'
    urgency: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    breakout_score: float  # 0.0-1.0 score total de breakout
    expected_direction: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    time_horizon: str  # 'IMMEDIATE' (<5min), 'SHORT_TERM' (5-30min), 'MEDIUM_TERM' (30min-2h)
    contributing_signals: List[Dict]  # Señales que contribuyen
    recommended_action: str
    metadata: Dict

class EarlyWarningSystem:
    """
    Sistema de Early Warning que combina múltiples señales para alertas predictivas

    Combina:
    1. Order Flow Analysis - Desequilibrios bid/ask
    2. Consolidation Patterns - Patrones pre-breakout
    3. Volume/Price Action - Momentum building
    4. Timing Filters - Contexto de mercado
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.EarlyWarningSystem")
        self.config = config or {}

        # Inicializar analizadores
        self.order_flow_analyzer = OrderFlowAnalyzer(self.config.get('order_flow', {}))
        self.consolidation_detector = ConsolidationDetector(self.config.get('consolidation', {}))

        # Configuración de scoring
        self.order_flow_weight = self.config.get('order_flow_weight', 0.4)  # 40%
        self.pattern_weight = self.config.get('pattern_weight', 0.3)  # 30%
        self.volume_weight = self.config.get('volume_weight', 0.2)  # 20%
        self.timing_weight = self.config.get('timing_weight', 0.1)  # 10%

        # Thresholds para alertas
        self.low_threshold = self.config.get('low_threshold', 0.3)
        self.medium_threshold = self.config.get('medium_threshold', 0.5)
        self.high_threshold = self.config.get('high_threshold', 0.7)
        self.critical_threshold = self.config.get('critical_threshold', 0.85)

        # Historial de alertas para evitar spam
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=self.config.get('alert_cooldown_minutes', 5))

        self.logger.info(f"🚨 EarlyWarningSystem initialized - predictive breakout detection enabled")

    def analyze_for_early_warnings(self, symbol: str, market_data: MarketData) -> List[EarlyWarningAlert]:
        """
        Analiza múltiples señales para generar alertas tempranas

        Returns:
            List[EarlyWarningAlert]: Alertas generadas
        """
        alerts = []

        try:
            # Verificar cooldown para evitar spam
            if self._is_in_cooldown(symbol):
                return alerts

            # 1. ANALIZAR ORDER FLOW
            order_flow_signals = self.order_flow_analyzer.analyze_order_flow(symbol, market_data)

            # 2. ANALIZAR CONSOLIDATION PATTERNS
            consolidation_signals = self.consolidation_detector.detect_consolidation_patterns(symbol, market_data)

            # 3. CALCULAR BREAKOUT SCORE COMBINADO
            breakout_score, score_breakdown = self._calculate_breakout_score(
                symbol, market_data, order_flow_signals, consolidation_signals
            )

            # 4. GENERAR ALERTAS BASADAS EN SCORE
            if breakout_score >= self.low_threshold:
                alert = self._generate_alert(
                    symbol, market_data, breakout_score, score_breakdown,
                    order_flow_signals, consolidation_signals
                )
                if alert:
                    alerts.append(alert)
                    self._update_alert_history(symbol)

            return alerts

        except Exception as e:
            self.logger.error(f"❌ Error analyzing early warnings for {symbol}: {e}")
            return alerts

    def _calculate_breakout_score(self, symbol: str, market_data: MarketData,
                                order_flow_signals: List[OrderFlowSignal],
                                consolidation_signals: List[ConsolidationSignal]) -> Tuple[float, Dict]:
        """
        Calcula score combinado de probabilidad de breakout

        Returns:
            Tuple[float, Dict]: (score, breakdown)
        """
        try:
            # 1. ORDER FLOW SCORE
            order_flow_score = self._score_order_flow_signals(order_flow_signals)

            # 2. PATTERN SCORE
            pattern_score = self._score_consolidation_patterns(consolidation_signals)

            # 3. VOLUME SCORE
            volume_score = self._score_volume_momentum(symbol, market_data)

            # 4. TIMING SCORE
            timing_score = self._score_market_timing(market_data)

            # SCORE COMBINADO WEIGHTED
            breakout_score = (
                order_flow_score * self.order_flow_weight +
                pattern_score * self.pattern_weight +
                volume_score * self.volume_weight +
                timing_score * self.timing_weight
            )

            score_breakdown = {
                'order_flow_score': order_flow_score,
                'pattern_score': pattern_score,
                'volume_score': volume_score,
                'timing_score': timing_score,
                'weights': {
                    'order_flow': self.order_flow_weight,
                    'pattern': self.pattern_weight,
                    'volume': self.volume_weight,
                    'timing': self.timing_weight
                },
                'final_score': breakout_score
            }

            return breakout_score, score_breakdown

        except Exception as e:
            self.logger.error(f"Error calculating breakout score for {symbol}: {e}")
            return 0.0, {}

    def _score_order_flow_signals(self, signals: List[OrderFlowSignal]) -> float:
        """Score basado en señales de order flow"""
        if not signals:
            return 0.0

        try:
            # Calcular score basado en fuerza y tipo de señales
            total_score = 0.0
            signal_weights = {
                'BULLISH_PRESSURE': 0.8,
                'BEARISH_PRESSURE': 0.8,
                'INSTITUTIONAL_ACTIVITY': 1.0,  # Peso más alto
                'AGGRESSIVE_BUYING': 0.9,
                'AGGRESSIVE_SELLING': 0.9,
                'PRESSURE_BUILDING': 0.7
            }

            for signal in signals:
                weight = signal_weights.get(signal.signal_type, 0.5)
                signal_score = signal.strength * signal.confidence * weight
                total_score += signal_score

            # Normalizar por número de señales y limitar a 1.0
            avg_score = total_score / len(signals)
            return min(1.0, avg_score)

        except Exception as e:
            self.logger.error(f"Error scoring order flow signals: {e}")
            return 0.0

    def _score_consolidation_patterns(self, signals: List[ConsolidationSignal]) -> float:
        """Score basado en patrones de consolidación"""
        if not signals:
            return 0.0

        try:
            # Calcular score basado en patrones detectados
            total_score = 0.0
            pattern_weights = {
                'RANGE_COMPRESSION': 0.9,  # Alto peso - coiling pattern muy predictivo
                'BOLLINGER_SQUEEZE': 1.0,  # Peso máximo - squeeze muy fiable
                'TRIANGLE': 0.8,  # Buen peso - triángulos son predictivos
                'FLAG': 0.7  # Peso moderado - flags menos fiables
            }

            for signal in signals:
                weight = pattern_weights.get(signal.pattern_type, 0.5)
                pattern_score = signal.strength * signal.breakout_probability * weight
                total_score += pattern_score

            # Normalizar y limitar
            avg_score = total_score / len(signals)
            return min(1.0, avg_score)

        except Exception as e:
            self.logger.error(f"Error scoring consolidation patterns: {e}")
            return 0.0

    def _score_volume_momentum(self, symbol: str, market_data: MarketData) -> float:
        """Score basado en momentum de volumen"""
        try:
            # Obtener historial de volumen del consolidation detector
            if (symbol in self.consolidation_detector.volume_history and
                len(self.consolidation_detector.volume_history[symbol]) >= 10):

                recent_volumes = list(self.consolidation_detector.volume_history[symbol])[-10:]
                current_volume = market_data.volume
                avg_volume = sum(recent_volumes) / len(recent_volumes)

                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

                # Score basado en volumen relativo
                if volume_ratio >= 3.0:  # 3x volumen
                    return 1.0
                elif volume_ratio >= 2.0:  # 2x volumen
                    return 0.8
                elif volume_ratio >= 1.5:  # 1.5x volumen
                    return 0.6
                elif volume_ratio >= 1.2:  # 1.2x volumen
                    return 0.4
                else:
                    return 0.2

            return 0.5  # Score neutral si no hay datos

        except Exception as e:
            self.logger.error(f"Error scoring volume momentum for {symbol}: {e}")
            return 0.0

    def _score_market_timing(self, market_data: MarketData) -> float:
        """Score basado en timing de mercado"""
        try:
            current_time = market_data.timestamp
            hour = current_time.hour
            minute = current_time.minute

            # Horarios óptimos para breakouts (ET)
            if (9, 30) <= (hour, minute) <= (10, 30):  # Primera hora
                return 1.0
            elif (10, 30) <= (hour, minute) <= (11, 30):  # Segunda hora
                return 0.8
            elif (13, 30) <= (hour, minute) <= (14, 30):  # Después del almuerzo
                return 0.7
            elif (15, 0) <= (hour, minute) <= (15, 30):  # Power hour
                return 0.9
            elif (11, 30) <= (hour, minute) <= (13, 30):  # Mediodía (menor actividad)
                return 0.4
            else:  # Otros horarios
                return 0.6

        except Exception as e:
            self.logger.error(f"Error scoring market timing: {e}")
            return 0.5

    def _generate_alert(self, symbol: str, market_data: MarketData, breakout_score: float,
                       score_breakdown: Dict, order_flow_signals: List[OrderFlowSignal],
                       consolidation_signals: List[ConsolidationSignal]) -> Optional[EarlyWarningAlert]:
        """Genera alerta basada en score y señales"""
        try:
            # Determinar urgencia basada en score
            if breakout_score >= self.critical_threshold:
                urgency = 'CRITICAL'
                alert_type = 'BREAKOUT_IMMINENT'
                time_horizon = 'IMMEDIATE'
            elif breakout_score >= self.high_threshold:
                urgency = 'HIGH'
                alert_type = 'BREAKOUT_IMMINENT'
                time_horizon = 'SHORT_TERM'
            elif breakout_score >= self.medium_threshold:
                urgency = 'MEDIUM'
                alert_type = 'MOMENTUM_BUILDING'
                time_horizon = 'SHORT_TERM'
            else:
                urgency = 'LOW'
                alert_type = 'MOMENTUM_BUILDING'
                time_horizon = 'MEDIUM_TERM'

            # Determinar dirección esperada
            expected_direction = self._determine_expected_direction(order_flow_signals, consolidation_signals)

            # Crear lista de señales contribuyentes
            contributing_signals = []

            # Añadir señales de order flow
            for signal in order_flow_signals:
                contributing_signals.append({
                    'type': 'order_flow',
                    'signal_type': signal.signal_type,
                    'strength': signal.strength,
                    'confidence': signal.confidence,
                    'reason': signal.reason
                })

            # Añadir señales de patrones
            for signal in consolidation_signals:
                contributing_signals.append({
                    'type': 'consolidation',
                    'pattern_type': signal.pattern_type,
                    'strength': signal.strength,
                    'breakout_probability': signal.breakout_probability,
                    'reason': signal.reason
                })

            # Generar recomendación
            recommended_action = self._generate_recommendation(
                urgency, expected_direction, breakout_score, contributing_signals
            )

            return EarlyWarningAlert(
                symbol=symbol,
                timestamp=datetime.now(),
                alert_type=alert_type,
                urgency=urgency,
                breakout_score=breakout_score,
                expected_direction=expected_direction,
                time_horizon=time_horizon,
                contributing_signals=contributing_signals,
                recommended_action=recommended_action,
                metadata={
                    'score_breakdown': score_breakdown,
                    'market_price': market_data.close,
                    'volume': market_data.volume,
                    'bid_ask_spread': (market_data.ask - market_data.bid) if (market_data.bid and market_data.ask) else None,
                    'analysis_timestamp': datetime.now().isoformat()
                }
            )

        except Exception as e:
            self.logger.error(f"Error generating alert for {symbol}: {e}")
            return None

    def _determine_expected_direction(self, order_flow_signals: List[OrderFlowSignal],
                                   consolidation_signals: List[ConsolidationSignal]) -> str:
        """Determina dirección esperada basada en todas las señales"""
        try:
            bullish_votes = 0
            bearish_votes = 0

            # Votos de order flow
            for signal in order_flow_signals:
                if 'BULLISH' in signal.signal_type or 'BUYING' in signal.signal_type:
                    bullish_votes += signal.strength
                elif 'BEARISH' in signal.signal_type or 'SELLING' in signal.signal_type:
                    bearish_votes += signal.strength

            # Votos de patrones
            for signal in consolidation_signals:
                if signal.expected_direction == 'BULLISH':
                    bullish_votes += signal.strength
                elif signal.expected_direction == 'BEARISH':
                    bearish_votes += signal.strength

            # Determinar dirección
            if bullish_votes > bearish_votes * 1.2:  # 20% más votes bullish
                return 'BULLISH'
            elif bearish_votes > bullish_votes * 1.2:  # 20% más votes bearish
                return 'BEARISH'
            else:
                return 'NEUTRAL'

        except Exception as e:
            self.logger.error(f"Error determining direction: {e}")
            return 'NEUTRAL'

    def _generate_recommendation(self, urgency: str, direction: str, score: float,
                               signals: List[Dict]) -> str:
        """Genera recomendación de acción"""
        try:
            if urgency == 'CRITICAL':
                if direction == 'BULLISH':
                    return f"🚨 CRITICAL: Prepare for BULLISH breakout (score: {score:.2f}). Consider immediate long entry."
                elif direction == 'BEARISH':
                    return f"🚨 CRITICAL: Prepare for BEARISH breakout (score: {score:.2f}). Consider immediate short entry or exit longs."
                else:
                    return f"🚨 CRITICAL: Breakout imminent (score: {score:.2f}). Monitor closely for direction."

            elif urgency == 'HIGH':
                if direction == 'BULLISH':
                    return f"🔥 HIGH: Strong BULLISH setup developing (score: {score:.2f}). Prepare for long entry."
                elif direction == 'BEARISH':
                    return f"🔥 HIGH: Strong BEARISH setup developing (score: {score:.2f}). Prepare for short entry."
                else:
                    return f"🔥 HIGH: Strong setup developing (score: {score:.2f}). Monitor for breakout direction."

            elif urgency == 'MEDIUM':
                return f"⚠️ MEDIUM: Momentum building (score: {score:.2f}). Watch for confirmation signals."

            else:  # LOW
                return f"ℹ️ LOW: Early signals detected (score: {score:.2f}). Monitor for development."

        except Exception as e:
            self.logger.error(f"Error generating recommendation: {e}")
            return f"Monitor for breakout signals (score: {score:.2f})"

    def _is_in_cooldown(self, symbol: str) -> bool:
        """Verifica si el símbolo está en cooldown"""
        if symbol in self.recent_alerts:
            time_since_last = datetime.now() - self.recent_alerts[symbol]
            return time_since_last < self.alert_cooldown
        return False

    def _update_alert_history(self, symbol: str):
        """Actualiza historial de alertas"""
        self.recent_alerts[symbol] = datetime.now()

        # Limpiar alertas antiguas
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.recent_alerts = {
            s: t for s, t in self.recent_alerts.items()
            if t > cutoff_time
        }

    def get_system_status(self) -> Dict:
        """Obtiene estado del sistema de early warning"""
        try:
            return {
                'system_active': True,
                'analyzers': {
                    'order_flow': hasattr(self, 'order_flow_analyzer'),
                    'consolidation': hasattr(self, 'consolidation_detector')
                },
                'thresholds': {
                    'low': self.low_threshold,
                    'medium': self.medium_threshold,
                    'high': self.high_threshold,
                    'critical': self.critical_threshold
                },
                'weights': {
                    'order_flow': self.order_flow_weight,
                    'pattern': self.pattern_weight,
                    'volume': self.volume_weight,
                    'timing': self.timing_weight
                },
                'alert_cooldown_minutes': self.alert_cooldown.total_seconds() / 60,
                'active_alerts': len(self.recent_alerts)
            }

        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}

    def reset_alerts_history(self):
        """Reset historial de alertas"""
        self.recent_alerts.clear()
        self.logger.info("🔄 Early warning alerts history reset")