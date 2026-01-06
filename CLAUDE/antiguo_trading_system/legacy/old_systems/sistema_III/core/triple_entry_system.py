#!/usr/bin/env python3
"""
Triple Entry System - Sistema de Triple Entrada

Implementa 3 niveles de entrada basados en diferentes niveles de confirmación:
1. PREDICTIVE ENTRY - Basado en señales early warning (earliest, highest risk/reward)
2. PULLBACK ENTRY - Sistema existente de pullback + recovery (medium timing)
3. CONFIRMATION ENTRY - MACD tradicional + confirmaciones (safest, latest)
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    from core.interfaces import MarketData, Signal, SignalType
    from core.early_warning_system import EarlyWarningSystem, EarlyWarningAlert
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'bid', 'ask', 'bid_size', 'ask_size'])

class EntryType(Enum):
    PREDICTIVE = "PREDICTIVE"
    PULLBACK = "PULLBACK"
    CONFIRMATION = "CONFIRMATION"

@dataclass
class TripleEntrySignal:
    """Señal del sistema de triple entrada"""
    symbol: str
    timestamp: datetime
    entry_type: EntryType
    signal: Signal  # Señal original
    confidence_multiplier: float  # Multiplicador de confianza basado en tipo
    position_size_pct: float  # % de posición recomendada
    stop_loss_distance: float  # Distancia de stop loss
    take_profit_target: float  # Target de take profit
    reason: str
    metadata: Dict

class TripleEntrySystem:
    """
    Sistema de Triple Entrada para maximizar timing y gestión de riesgo

    NIVEL 1 - PREDICTIVE (33% posición): Early warning signals
    NIVEL 2 - PULLBACK (50% posición): Pullback + recovery system
    NIVEL 3 - CONFIRMATION (25% posición): Traditional MACD + confirmations
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.TripleEntrySystem")
        self.config = config or {}

        # Inicializar Early Warning System
        self.early_warning_system = EarlyWarningSystem(self.config.get('early_warning', {}))

        # Configuración de niveles de entrada
        self.predictive_config = self.config.get('predictive', {
            'position_size_pct': 0.33,  # 33% de posición
            'confidence_multiplier': 1.5,  # Mayor reward por timing
            'min_warning_score': 0.7,  # Score mínimo para entrada predictiva
            'stop_loss_multiplier': 1.2,  # Stop más amplio por mayor riesgo
        })

        self.pullback_config = self.config.get('pullback', {
            'position_size_pct': 0.50,  # 50% de posición
            'confidence_multiplier': 1.0,  # Standard confidence
            'min_recovery_pct': 0.01,  # 1% recovery mínimo
            'stop_loss_multiplier': 1.0,  # Stop standard
        })

        self.confirmation_config = self.config.get('confirmation', {
            'position_size_pct': 0.25,  # 25% de posición
            'confidence_multiplier': 0.8,  # Menor reward por entrada tardía
            'min_confirmation_score': 3,  # Score mínimo tradicional
            'stop_loss_multiplier': 0.8,  # Stop más ajustado
        })

        # Estado del sistema
        self.active_entries: Dict[str, List[TripleEntrySignal]] = {}  # symbol -> list of entries
        self.entry_history: Dict[str, List[TripleEntrySignal]] = {}

        self.logger.info(f"🎯 TripleEntrySystem initialized - 3-tier predictive entry system enabled")

    def analyze_triple_entry_opportunity(self, symbol: str, market_data: MarketData,
                                       macd_signal: Optional[Signal] = None) -> List[TripleEntrySignal]:
        """
        Analiza oportunidades de entrada en los 3 niveles

        Args:
            symbol: Símbolo a analizar
            market_data: Datos de mercado actuales
            macd_signal: Señal MACD existente (si hay)

        Returns:
            List[TripleEntrySignal]: Señales de entrada generadas
        """
        entry_signals = []

        try:
            # 1. NIVEL PREDICTIVE - Early Warning Analysis
            predictive_signal = self._analyze_predictive_entry(symbol, market_data)
            if predictive_signal:
                entry_signals.append(predictive_signal)

            # 2. NIVEL PULLBACK - Pullback Recovery Analysis
            if macd_signal:  # Solo si hay señal MACD base
                pullback_signal = self._analyze_pullback_entry(symbol, market_data, macd_signal)
                if pullback_signal:
                    entry_signals.append(pullback_signal)

                # 3. NIVEL CONFIRMATION - Traditional Confirmation
                confirmation_signal = self._analyze_confirmation_entry(symbol, market_data, macd_signal)
                if confirmation_signal:
                    entry_signals.append(confirmation_signal)

            # Registrar entradas activas
            if entry_signals:
                if symbol not in self.active_entries:
                    self.active_entries[symbol] = []
                self.active_entries[symbol].extend(entry_signals)

                # Log de señales generadas
                entry_types = [s.entry_type.value for s in entry_signals]
                self.logger.info(f"🎯 {symbol}: Triple entry signals: {entry_types}")

            return entry_signals

        except Exception as e:
            self.logger.error(f"❌ Error analyzing triple entry for {symbol}: {e}")
            return entry_signals

    def _analyze_predictive_entry(self, symbol: str, market_data: MarketData) -> Optional[TripleEntrySignal]:
        """
        NIVEL 1: Análisis de entrada predictiva basada en early warnings

        Características:
        - Entrada más temprana (mayor riesgo/reward)
        - Basada en desequilibrios de order flow + patrones
        - 33% de posición, stop más amplio
        """
        try:
            # Obtener alertas de early warning
            early_warnings = self.early_warning_system.analyze_for_early_warnings(symbol, market_data)

            if not early_warnings:
                return None

            # Filtrar alertas con score suficiente
            qualifying_alerts = [
                alert for alert in early_warnings
                if alert.breakout_score >= self.predictive_config['min_warning_score']
            ]

            if not qualifying_alerts:
                return None

            # Tomar la alerta con mayor score
            best_alert = max(qualifying_alerts, key=lambda a: a.breakout_score)

            # Solo entradas bullish para MACDV (puede expandirse)
            if best_alert.expected_direction != 'BULLISH':
                return None

            # Verificar que no tengamos ya entrada predictiva activa
            if self._has_active_entry_type(symbol, EntryType.PREDICTIVE):
                return None

            # Crear señal predictiva
            signal = Signal(
                signal_id=f"predictive_{symbol}_{int(datetime.now().timestamp())}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=best_alert.breakout_score,
                price=market_data.close,
                timestamp=datetime.now(),
                strategy_name="TripleEntry_Predictive",
                metadata={
                    'entry_type': 'PREDICTIVE',
                    'early_warning_score': best_alert.breakout_score,
                    'alert_urgency': best_alert.urgency,
                    'contributing_signals': best_alert.contributing_signals,
                    'expected_direction': best_alert.expected_direction,
                    'time_horizon': best_alert.time_horizon
                }
            )

            # Calcular parámetros de entrada
            stop_loss_distance = self._calculate_stop_loss_distance(
                market_data, self.predictive_config['stop_loss_multiplier']
            )
            take_profit_target = self._calculate_take_profit_target(market_data, stop_loss_distance, 2.0)

            return TripleEntrySignal(
                symbol=symbol,
                timestamp=datetime.now(),
                entry_type=EntryType.PREDICTIVE,
                signal=signal,
                confidence_multiplier=self.predictive_config['confidence_multiplier'],
                position_size_pct=self.predictive_config['position_size_pct'],
                stop_loss_distance=stop_loss_distance,
                take_profit_target=take_profit_target,
                reason=f"Predictive entry on early warning score {best_alert.breakout_score:.2f}",
                metadata={
                    'alert_details': {
                        'urgency': best_alert.urgency,
                        'recommended_action': best_alert.recommended_action,
                        'time_horizon': best_alert.time_horizon
                    },
                    'risk_level': 'HIGH',
                    'reward_potential': 'HIGH'
                }
            )

        except Exception as e:
            self.logger.error(f"Error analyzing predictive entry for {symbol}: {e}")
            return None

    def _analyze_pullback_entry(self, symbol: str, market_data: MarketData,
                              macd_signal: Signal) -> Optional[TripleEntrySignal]:
        """
        NIVEL 2: Análisis de entrada en pullback (sistema existente mejorado)

        Características:
        - Entrada en recuperación después de retroceso
        - 50% de posición, riesgo moderado
        - Basada en MACD + pullback recovery
        """
        try:
            # Verificar que la señal MACD es válida y bullish
            if macd_signal.signal_type != SignalType.LONG:
                return None

            # Verificar que no tengamos ya entrada pullback activa
            if self._has_active_entry_type(symbol, EntryType.PULLBACK):
                return None

            # Verificar condiciones específicas de pullback en metadata
            metadata = macd_signal.metadata or {}

            # Debe haber detectado pullback opportunity
            pullback_detected = metadata.get('pullback_opportunity', False)
            if not pullback_detected:
                return None

            # Verificar que hay recovery suficiente
            recovery_pct = metadata.get('recovery_pct', 0)
            if recovery_pct < self.pullback_config['min_recovery_pct']:
                return None

            # Crear señal de pullback
            signal = Signal(
                signal_id=f"pullback_{symbol}_{int(datetime.now().timestamp())}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=macd_signal.strength,
                price=market_data.close,
                timestamp=datetime.now(),
                strategy_name="TripleEntry_Pullback",
                metadata={
                    'entry_type': 'PULLBACK',
                    'original_macd_signal': macd_signal.signal_id,
                    'pullback_recovery_pct': recovery_pct,
                    'macd_score': metadata.get('score', 0),
                    'conditions_met': metadata.get('conditions', [])
                }
            )

            # Calcular parámetros
            stop_loss_distance = self._calculate_stop_loss_distance(
                market_data, self.pullback_config['stop_loss_multiplier']
            )
            take_profit_target = self._calculate_take_profit_target(market_data, stop_loss_distance, 1.8)

            return TripleEntrySignal(
                symbol=symbol,
                timestamp=datetime.now(),
                entry_type=EntryType.PULLBACK,
                signal=signal,
                confidence_multiplier=self.pullback_config['confidence_multiplier'],
                position_size_pct=self.pullback_config['position_size_pct'],
                stop_loss_distance=stop_loss_distance,
                take_profit_target=take_profit_target,
                reason=f"Pullback entry with {recovery_pct:.1%} recovery",
                metadata={
                    'pullback_details': {
                        'recovery_pct': recovery_pct,
                        'pullback_depth': metadata.get('pullback_depth', 0),
                        'volume_confirmation': metadata.get('volume_ok', False)
                    },
                    'risk_level': 'MEDIUM',
                    'reward_potential': 'MEDIUM'
                }
            )

        except Exception as e:
            self.logger.error(f"Error analyzing pullback entry for {symbol}: {e}")
            return None

    def _analyze_confirmation_entry(self, symbol: str, market_data: MarketData,
                                  macd_signal: Signal) -> Optional[TripleEntrySignal]:
        """
        NIVEL 3: Análisis de entrada de confirmación (tradicional)

        Características:
        - Entrada más conservadora con confirmaciones múltiples
        - 25% de posición, menor riesgo
        - Basada en MACD + confirmaciones técnicas
        """
        try:
            # Verificar que la señal MACD es válida y bullish
            if macd_signal.signal_type != SignalType.LONG:
                return None

            # Verificar que no tengamos ya entrada confirmation activa
            if self._has_active_entry_type(symbol, EntryType.CONFIRMATION):
                return None

            # Verificar score mínimo para confirmación
            metadata = macd_signal.metadata or {}
            final_score = metadata.get('final_score', 0)
            if final_score < self.confirmation_config['min_confirmation_score']:
                return None

            # Verificar confirmaciones adicionales
            confirmations = []

            # Volume confirmation
            volume_ratio = metadata.get('volume_ratio', 0)
            if volume_ratio >= 1.5:
                confirmations.append('volume')

            # MACD strength
            macd_value = metadata.get('macd_value', 0)
            if macd_value > 0:
                confirmations.append('macd_positive')

            # Multi-timeframe confirmation
            if 'macd_5min_strong' in metadata.get('conditions', []):
                confirmations.append('multi_timeframe')

            # Requerir al menos 2 confirmaciones para entrada conservadora
            if len(confirmations) < 2:
                return None

            # Crear señal de confirmación
            signal = Signal(
                signal_id=f"confirmation_{symbol}_{int(datetime.now().timestamp())}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=min(0.9, macd_signal.strength * 1.1),  # Boost por confirmaciones
                price=market_data.close,
                timestamp=datetime.now(),
                strategy_name="TripleEntry_Confirmation",
                metadata={
                    'entry_type': 'CONFIRMATION',
                    'original_macd_signal': macd_signal.signal_id,
                    'confirmation_score': final_score,
                    'confirmations': confirmations,
                    'conditions_met': metadata.get('conditions', [])
                }
            )

            # Calcular parámetros más conservadores
            stop_loss_distance = self._calculate_stop_loss_distance(
                market_data, self.confirmation_config['stop_loss_multiplier']
            )
            take_profit_target = self._calculate_take_profit_target(market_data, stop_loss_distance, 1.5)

            return TripleEntrySignal(
                symbol=symbol,
                timestamp=datetime.now(),
                entry_type=EntryType.CONFIRMATION,
                signal=signal,
                confidence_multiplier=self.confirmation_config['confidence_multiplier'],
                position_size_pct=self.confirmation_config['position_size_pct'],
                stop_loss_distance=stop_loss_distance,
                take_profit_target=take_profit_target,
                reason=f"Confirmation entry with {len(confirmations)} confirmations (score: {final_score})",
                metadata={
                    'confirmation_details': {
                        'confirmations': confirmations,
                        'confirmation_count': len(confirmations),
                        'volume_ratio': volume_ratio,
                        'final_score': final_score
                    },
                    'risk_level': 'LOW',
                    'reward_potential': 'LOW'
                }
            )

        except Exception as e:
            self.logger.error(f"Error analyzing confirmation entry for {symbol}: {e}")
            return None

    def _has_active_entry_type(self, symbol: str, entry_type: EntryType) -> bool:
        """Verifica si ya hay una entrada activa de este tipo"""
        if symbol not in self.active_entries:
            return False

        return any(
            entry.entry_type == entry_type
            for entry in self.active_entries[symbol]
        )

    def _calculate_stop_loss_distance(self, market_data: MarketData, multiplier: float) -> float:
        """Calcula distancia de stop loss basada en volatilidad"""
        try:
            # Método simple basado en % del precio
            base_stop_pct = 0.05  # 5% base
            adjusted_stop_pct = base_stop_pct * multiplier
            return market_data.close * adjusted_stop_pct

        except Exception as e:
            self.logger.error(f"Error calculating stop loss distance: {e}")
            return market_data.close * 0.05  # Fallback

    def _calculate_take_profit_target(self, market_data: MarketData, stop_distance: float,
                                    risk_reward_ratio: float) -> float:
        """Calcula target de take profit basado en risk/reward ratio"""
        try:
            profit_distance = stop_distance * risk_reward_ratio
            return market_data.close + profit_distance

        except Exception as e:
            self.logger.error(f"Error calculating take profit target: {e}")
            return market_data.close * 1.1  # Fallback

    def get_active_entries(self, symbol: str = None) -> Dict[str, List[TripleEntrySignal]]:
        """Obtiene entradas activas"""
        if symbol:
            return {symbol: self.active_entries.get(symbol, [])}
        return self.active_entries.copy()

    def close_entry(self, symbol: str, entry_type: EntryType, reason: str = "Manual close"):
        """Cierra una entrada específica"""
        if symbol in self.active_entries:
            self.active_entries[symbol] = [
                entry for entry in self.active_entries[symbol]
                if entry.entry_type != entry_type
            ]

            # Limpiar si no hay más entradas
            if not self.active_entries[symbol]:
                del self.active_entries[symbol]

            self.logger.info(f"🔒 {symbol}: Closed {entry_type.value} entry - {reason}")

    def get_system_status(self) -> Dict:
        """Obtiene estado del sistema triple entry"""
        try:
            total_active = sum(len(entries) for entries in self.active_entries.values())

            return {
                'system_active': True,
                'active_symbols': len(self.active_entries),
                'total_active_entries': total_active,
                'entry_distribution': {
                    'predictive': self.predictive_config['position_size_pct'],
                    'pullback': self.pullback_config['position_size_pct'],
                    'confirmation': self.confirmation_config['position_size_pct']
                },
                'confidence_multipliers': {
                    'predictive': self.predictive_config['confidence_multiplier'],
                    'pullback': self.pullback_config['confidence_multiplier'],
                    'confirmation': self.confirmation_config['confidence_multiplier']
                },
                'early_warning_status': self.early_warning_system.get_system_status()
            }

        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}

    def reset_all_entries(self):
        """Reset todas las entradas activas"""
        self.active_entries.clear()
        self.entry_history.clear()
        self.early_warning_system.reset_alerts_history()
        self.logger.info("🔄 Triple entry system reset - all entries cleared")