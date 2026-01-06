#!/usr/bin/env python3
"""
Dynamic Position Sizing - Tamaño Dinámico de Posiciones

Ajusta el tamaño de posiciones basado en:
1. Confianza de señales predictivas
2. Tipo de entrada (predictive/pullback/confirmation)
3. Contexto de mercado
4. Gestión de riesgo de portfolio
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math

try:
    from core.interfaces import MarketData, Signal
    from core.triple_entry_system import TripleEntrySignal, EntryType
except ImportError:
    pass

@dataclass
class PositionSizeRecommendation:
    """Recomendación de tamaño de posición"""
    symbol: str
    recommended_size: int  # Cantidad de acciones
    recommended_value: float  # Valor en $
    confidence_score: float  # Score de confianza total
    risk_score: float  # Score de riesgo
    sizing_factors: Dict  # Factores que influyen el tamaño
    max_loss_amount: float  # Pérdida máxima estimada
    position_weight: float  # Peso como % del portfolio
    reason: str

class DynamicPositionSizing:
    """
    Sistema de Position Sizing Dinámico basado en múltiples factores

    Factores considerados:
    1. Confidence Score - Fuerza de señales predictivas
    2. Entry Type - Predictive (33%) vs Pullback (50%) vs Confirmation (25%)
    3. Market Volatility - Ajuste por volatilidad del mercado
    4. Portfolio Risk - Gestión de riesgo total del portfolio
    5. Symbol Characteristics - Características específicas del símbolo
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.DynamicPositionSizing")
        self.config = config or {}

        # Configuración de portfolio
        self.portfolio_value = self.config.get('portfolio_value', 10000.0)
        self.max_risk_per_trade = self.config.get('max_risk_per_trade', 0.02)  # 2%
        self.max_portfolio_risk = self.config.get('max_portfolio_risk', 0.10)  # 10%
        self.max_position_value = self.config.get('max_position_value', 2000.0)  # $2000
        self.min_position_value = self.config.get('min_position_value', 100.0)  # $100

        # Multiplicadores por tipo de entrada
        self.entry_type_multipliers = {
            EntryType.PREDICTIVE: self.config.get('predictive_multiplier', 1.5),  # Más tamaño por timing
            EntryType.PULLBACK: self.config.get('pullback_multiplier', 1.0),  # Tamaño base
            EntryType.CONFIRMATION: self.config.get('confirmation_multiplier', 0.8)  # Menos tamaño (conservador)
        }

        # Configuración de confianza
        self.min_confidence_for_sizing = self.config.get('min_confidence', 0.5)
        self.max_confidence_multiplier = self.config.get('max_confidence_multiplier', 2.0)

        # Configuración de volatilidad
        self.volatility_adjustment = self.config.get('volatility_adjustment', True)
        self.high_volatility_threshold = self.config.get('high_volatility_threshold', 0.15)  # 15%

        # Estado del sistema
        self.current_positions: Dict[str, float] = {}  # symbol -> current_value
        self.total_portfolio_risk = 0.0

        self.logger.info(f"📏 DynamicPositionSizing initialized - intelligent sizing enabled")

    def calculate_position_size(self, triple_entry_signal: TripleEntrySignal,
                              market_data: MarketData,
                              current_portfolio_value: Optional[float] = None) -> PositionSizeRecommendation:
        """
        Calcula tamaño óptimo de posición para señal de triple entry

        Args:
            triple_entry_signal: Señal del sistema de triple entrada
            market_data: Datos de mercado actuales
            current_portfolio_value: Valor actual del portfolio (opcional)

        Returns:
            PositionSizeRecommendation: Recomendación de tamaño
        """
        try:
            # Usar portfolio value actual o configurado
            portfolio_value = current_portfolio_value or self.portfolio_value

            # 1. CALCULAR CONFIDENCE SCORE TOTAL
            confidence_score = self._calculate_total_confidence(triple_entry_signal)

            # 2. CALCULAR RISK SCORE
            risk_score = self._calculate_risk_score(triple_entry_signal, market_data)

            # 3. CALCULAR TAMAÑO BASE
            base_size_value = self._calculate_base_size(
                portfolio_value, confidence_score, triple_entry_signal.entry_type
            )

            # 4. APLICAR AJUSTES
            adjusted_size_value = self._apply_adjustments(
                base_size_value, triple_entry_signal, market_data, confidence_score, risk_score
            )

            # 5. VERIFICAR LÍMITES Y RIESGO
            final_size_value = self._apply_risk_limits(
                adjusted_size_value, triple_entry_signal, portfolio_value
            )

            # 6. CALCULAR CANTIDAD DE ACCIONES
            share_quantity = self._calculate_share_quantity(final_size_value, market_data.close)

            # 7. CALCULAR PÉRDIDA MÁXIMA ESTIMADA
            max_loss = self._calculate_max_loss(share_quantity, market_data.close, triple_entry_signal)

            # 8. GENERAR FACTORES Y RAZÓN
            sizing_factors = self._generate_sizing_factors(
                triple_entry_signal, confidence_score, risk_score, market_data
            )

            reason = self._generate_sizing_reason(
                triple_entry_signal.entry_type, confidence_score, final_size_value, sizing_factors
            )

            return PositionSizeRecommendation(
                symbol=triple_entry_signal.symbol,
                recommended_size=share_quantity,
                recommended_value=final_size_value,
                confidence_score=confidence_score,
                risk_score=risk_score,
                sizing_factors=sizing_factors,
                max_loss_amount=max_loss,
                position_weight=final_size_value / portfolio_value,
                reason=reason
            )

        except Exception as e:
            self.logger.error(f"❌ Error calculating position size for {triple_entry_signal.symbol}: {e}")
            # Fallback a tamaño mínimo
            return self._create_fallback_recommendation(triple_entry_signal, market_data)

    def _calculate_total_confidence(self, triple_entry_signal: TripleEntrySignal) -> float:
        """Calcula confidence score total"""
        try:
            # Base confidence de la señal
            base_confidence = triple_entry_signal.signal.strength

            # Multiplicador por tipo de entrada
            confidence_multiplier = triple_entry_signal.confidence_multiplier

            # Ajuste por metadata específico
            metadata_boost = 0.0
            metadata = triple_entry_signal.signal.metadata or {}

            # Boost por order flow
            order_flow_boost = metadata.get('order_flow_boost', 0)
            if order_flow_boost > 0:
                metadata_boost += order_flow_boost * 0.1  # 10% boost por punto

            # Boost por early warning score
            early_warning_score = metadata.get('early_warning_score', 0)
            if early_warning_score > 0.7:
                metadata_boost += (early_warning_score - 0.7) * 0.5

            # Boost por confirmaciones múltiples
            confirmations = metadata.get('confirmations', [])
            if len(confirmations) >= 2:
                metadata_boost += len(confirmations) * 0.05

            # Calcular confidence total
            total_confidence = (base_confidence * confidence_multiplier) + metadata_boost

            # Limitar a rango válido
            return min(1.0, max(0.0, total_confidence))

        except Exception as e:
            self.logger.error(f"Error calculating total confidence: {e}")
            return 0.5  # Fallback

    def _calculate_risk_score(self, triple_entry_signal: TripleEntrySignal, market_data: MarketData) -> float:
        """Calcula score de riesgo (0.0 = bajo riesgo, 1.0 = alto riesgo)"""
        try:
            risk_factors = []

            # 1. Riesgo por tipo de entrada
            entry_risk = {
                EntryType.PREDICTIVE: 0.8,  # Alto riesgo (entrada temprana)
                EntryType.PULLBACK: 0.5,    # Riesgo medio
                EntryType.CONFIRMATION: 0.3  # Bajo riesgo (entrada conservadora)
            }
            risk_factors.append(entry_risk.get(triple_entry_signal.entry_type, 0.5))

            # 2. Riesgo por volatilidad implícita en stop loss
            stop_distance_pct = triple_entry_signal.stop_loss_distance / market_data.close
            volatility_risk = min(1.0, stop_distance_pct / 0.1)  # Normalizar por 10%
            risk_factors.append(volatility_risk)

            # 3. Riesgo por urgencia de early warning
            metadata = triple_entry_signal.signal.metadata or {}
            urgency = metadata.get('alert_urgency', 'LOW')
            urgency_risk = {
                'LOW': 0.2,
                'MEDIUM': 0.4,
                'HIGH': 0.6,
                'CRITICAL': 0.8
            }.get(urgency, 0.5)
            risk_factors.append(urgency_risk)

            # 4. Riesgo por tiempo de mercado
            hour = market_data.timestamp.hour if hasattr(market_data.timestamp, 'hour') else 12
            if hour < 10 or hour > 15:  # Horarios de mayor volatilidad
                time_risk = 0.7
            else:
                time_risk = 0.3
            risk_factors.append(time_risk)

            # Promedio de factores de riesgo
            return sum(risk_factors) / len(risk_factors)

        except Exception as e:
            self.logger.error(f"Error calculating risk score: {e}")
            return 0.5  # Fallback

    def _calculate_base_size(self, portfolio_value: float, confidence_score: float, entry_type: EntryType) -> float:
        """Calcula tamaño base de posición"""
        try:
            # Tamaño base como % del portfolio
            base_percentage = triple_entry_signal.position_size_pct if hasattr(triple_entry_signal, 'position_size_pct') else {
                EntryType.PREDICTIVE: 0.15,  # 15% para predictive
                EntryType.PULLBACK: 0.20,    # 20% para pullback
                EntryType.CONFIRMATION: 0.10  # 10% para confirmation
            }.get(entry_type, 0.15)

            # Ajustar por confidence
            confidence_adjustment = 0.5 + (confidence_score * 0.5)  # 0.5-1.0 range
            adjusted_percentage = base_percentage * confidence_adjustment

            # Aplicar multiplicador por tipo
            entry_multiplier = self.entry_type_multipliers.get(entry_type, 1.0)
            final_percentage = adjusted_percentage * entry_multiplier

            # Calcular valor en dólares
            base_value = portfolio_value * final_percentage

            return base_value

        except Exception as e:
            self.logger.error(f"Error calculating base size: {e}")
            return self.min_position_value

    def _apply_adjustments(self, base_size: float, triple_entry_signal: TripleEntrySignal,
                         market_data: MarketData, confidence_score: float, risk_score: float) -> float:
        """Aplica ajustes adicionales al tamaño base"""
        try:
            adjusted_size = base_size

            # 1. AJUSTE POR VOLATILIDAD
            if self.volatility_adjustment:
                volatility_factor = self._calculate_volatility_adjustment(market_data, triple_entry_signal)
                adjusted_size *= volatility_factor

            # 2. AJUSTE POR RATIO RISK/REWARD
            risk_reward_ratio = self._calculate_risk_reward_ratio(triple_entry_signal, market_data)
            if risk_reward_ratio > 2.0:  # Buen risk/reward
                adjusted_size *= 1.2
            elif risk_reward_ratio < 1.5:  # Mal risk/reward
                adjusted_size *= 0.8

            # 3. AJUSTE POR SCORE DE CONFIANZA EXTREMO
            if confidence_score > 0.8:  # Muy alta confianza
                adjusted_size *= 1.15
            elif confidence_score < 0.3:  # Baja confianza
                adjusted_size *= 0.7

            # 4. AJUSTE POR RIESGO EXTREMO
            if risk_score > 0.8:  # Alto riesgo
                adjusted_size *= 0.8
            elif risk_score < 0.3:  # Bajo riesgo
                adjusted_size *= 1.1

            return adjusted_size

        except Exception as e:
            self.logger.error(f"Error applying adjustments: {e}")
            return base_size

    def _apply_risk_limits(self, size_value: float, triple_entry_signal: TripleEntrySignal,
                         portfolio_value: float) -> float:
        """Aplica límites de riesgo y tamaño"""
        try:
            # 1. LÍMITE DE VALOR MÁXIMO POR POSICIÓN
            size_value = min(size_value, self.max_position_value)

            # 2. LÍMITE DE VALOR MÍNIMO
            size_value = max(size_value, self.min_position_value)

            # 3. LÍMITE DE RIESGO POR TRADE
            max_risk_amount = portfolio_value * self.max_risk_per_trade
            stop_loss_pct = triple_entry_signal.stop_loss_distance / triple_entry_signal.signal.price
            max_size_by_risk = max_risk_amount / stop_loss_pct if stop_loss_pct > 0 else size_value
            size_value = min(size_value, max_size_by_risk)

            # 4. LÍMITE DE PESO EN PORTFOLIO
            max_weight = 0.25  # Máximo 25% del portfolio en una posición
            max_size_by_weight = portfolio_value * max_weight
            size_value = min(size_value, max_size_by_weight)

            # 5. LÍMITE DE RIESGO TOTAL DEL PORTFOLIO
            current_portfolio_risk = self._calculate_current_portfolio_risk()
            if current_portfolio_risk > self.max_portfolio_risk * 0.8:  # 80% del límite
                size_value *= 0.5  # Reducir tamaño si estamos cerca del límite

            return size_value

        except Exception as e:
            self.logger.error(f"Error applying risk limits: {e}")
            return min(size_value, self.max_position_value)

    def _calculate_share_quantity(self, size_value: float, price: float) -> int:
        """Calcula cantidad de acciones"""
        try:
            raw_quantity = size_value / price
            # Redondear hacia abajo para no exceder el valor
            return int(raw_quantity)

        except Exception as e:
            self.logger.error(f"Error calculating share quantity: {e}")
            return 1

    def _calculate_max_loss(self, quantity: int, price: float, triple_entry_signal: TripleEntrySignal) -> float:
        """Calcula pérdida máxima estimada"""
        try:
            position_value = quantity * price
            stop_loss_distance = triple_entry_signal.stop_loss_distance
            max_loss = quantity * stop_loss_distance

            return max_loss

        except Exception as e:
            self.logger.error(f"Error calculating max loss: {e}")
            return 0.0

    def _calculate_volatility_adjustment(self, market_data: MarketData, triple_entry_signal: TripleEntrySignal) -> float:
        """Calcula ajuste por volatilidad"""
        try:
            # Usar stop loss distance como proxy de volatilidad
            volatility_pct = triple_entry_signal.stop_loss_distance / market_data.close

            if volatility_pct > self.high_volatility_threshold:
                # Alta volatilidad -> reducir tamaño
                return 0.8
            elif volatility_pct < 0.05:  # Baja volatilidad
                # Baja volatilidad -> aumentar tamaño ligeramente
                return 1.1
            else:
                return 1.0  # Volatilidad normal

        except Exception as e:
            self.logger.error(f"Error calculating volatility adjustment: {e}")
            return 1.0

    def _calculate_risk_reward_ratio(self, triple_entry_signal: TripleEntrySignal, market_data: MarketData) -> float:
        """Calcula ratio risk/reward"""
        try:
            risk = triple_entry_signal.stop_loss_distance
            reward = triple_entry_signal.take_profit_target - market_data.close

            if risk > 0:
                return reward / risk
            return 1.0

        except Exception as e:
            self.logger.error(f"Error calculating risk/reward ratio: {e}")
            return 1.0

    def _calculate_current_portfolio_risk(self) -> float:
        """Calcula riesgo actual del portfolio"""
        try:
            # Simplificación: asumir 2% de riesgo por posición activa
            active_positions = len(self.current_positions)
            return active_positions * 0.02  # 2% por posición

        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
            return 0.0

    def _generate_sizing_factors(self, triple_entry_signal: TripleEntrySignal, confidence_score: float,
                               risk_score: float, market_data: MarketData) -> Dict:
        """Genera factores que influyen el sizing"""
        return {
            'entry_type': triple_entry_signal.entry_type.value,
            'confidence_score': confidence_score,
            'risk_score': risk_score,
            'entry_type_multiplier': self.entry_type_multipliers.get(triple_entry_signal.entry_type, 1.0),
            'stop_loss_distance_pct': triple_entry_signal.stop_loss_distance / market_data.close,
            'risk_reward_ratio': self._calculate_risk_reward_ratio(triple_entry_signal, market_data),
            'volatility_adjustment': self._calculate_volatility_adjustment(market_data, triple_entry_signal)
        }

    def _generate_sizing_reason(self, entry_type: EntryType, confidence_score: float,
                              final_size: float, factors: Dict) -> str:
        """Genera razón del tamaño calculado"""
        try:
            reason_parts = []

            # Tipo de entrada
            reason_parts.append(f"{entry_type.value} entry")

            # Confidence
            if confidence_score > 0.7:
                reason_parts.append("high confidence")
            elif confidence_score < 0.4:
                reason_parts.append("low confidence")

            # Risk/reward
            rr_ratio = factors.get('risk_reward_ratio', 1.0)
            if rr_ratio > 2.0:
                reason_parts.append("good R/R")
            elif rr_ratio < 1.5:
                reason_parts.append("poor R/R")

            # Volatilidad
            vol_adj = factors.get('volatility_adjustment', 1.0)
            if vol_adj < 0.9:
                reason_parts.append("high volatility")
            elif vol_adj > 1.05:
                reason_parts.append("low volatility")

            base_reason = f"${final_size:.0f} position based on " + ", ".join(reason_parts)
            return base_reason

        except Exception as e:
            self.logger.error(f"Error generating sizing reason: {e}")
            return f"${final_size:.0f} position calculated"

    def _create_fallback_recommendation(self, triple_entry_signal: TripleEntrySignal,
                                      market_data: MarketData) -> PositionSizeRecommendation:
        """Crea recomendación de fallback en caso de error"""
        try:
            fallback_value = self.min_position_value
            fallback_quantity = int(fallback_value / market_data.close)

            return PositionSizeRecommendation(
                symbol=triple_entry_signal.symbol,
                recommended_size=fallback_quantity,
                recommended_value=fallback_value,
                confidence_score=0.5,
                risk_score=0.5,
                sizing_factors={'fallback': True},
                max_loss_amount=fallback_value * 0.05,  # 5% estimado
                position_weight=fallback_value / self.portfolio_value,
                reason="Fallback minimum position due to calculation error"
            )

        except Exception as e:
            self.logger.error(f"Error creating fallback recommendation: {e}")
            return PositionSizeRecommendation(
                symbol=triple_entry_signal.symbol,
                recommended_size=1,
                recommended_value=100.0,
                confidence_score=0.0,
                risk_score=1.0,
                sizing_factors={'error': True},
                max_loss_amount=5.0,
                position_weight=0.01,
                reason="Error in position sizing calculation"
            )

    def update_position(self, symbol: str, value: float):
        """Actualiza posición activa"""
        if value > 0:
            self.current_positions[symbol] = value
        elif symbol in self.current_positions:
            del self.current_positions[symbol]

    def get_sizing_status(self) -> Dict:
        """Obtiene estado del sistema de sizing"""
        return {
            'portfolio_value': self.portfolio_value,
            'max_risk_per_trade': self.max_risk_per_trade,
            'max_portfolio_risk': self.max_portfolio_risk,
            'current_portfolio_risk': self._calculate_current_portfolio_risk(),
            'active_positions': len(self.current_positions),
            'total_position_value': sum(self.current_positions.values()),
            'entry_type_multipliers': {k.value: v for k, v in self.entry_type_multipliers.items()},
            'position_limits': {
                'max_value': self.max_position_value,
                'min_value': self.min_position_value
            }
        }