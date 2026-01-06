#!/usr/bin/env python3
"""
Quality-Based Targets System

Calcula TP y SL dinámicos basados en:
1. Calidad del setup (quality score)
2. Strength del catalyst
3. Trading horizon
4. Resistencia técnica diaria
5. ATR (volatilidad del ticker)

Strategy:
- Setup A+ (85-100): TP 30-45%, SL amplio para aguantar noise
- Setup A (75-84): TP 15-20%, SL medio
- Setup B+ (65-74): TP 10-12%, SL estándar
- Setup B (50-64): TP 8%, SL tight

Small caps tienen más volatilidad → stops más amplios
"""

import logging
from typing import Dict, Tuple
from enum import Enum


class TradingHorizon(Enum):
    """Trading time horizon"""
    SCALP = "scalp"
    INTRADAY = "intraday"
    SWING_SHORT = "swing_short"
    SWING = "swing"


# Risk parameters por horizonte temporal
HORIZON_RISK_PARAMS = {
    TradingHorizon.SCALP: {
        'base_stop_pct': 3.0,
        'base_tp_pct': 5.0,
        'atr_multiplier': 1.0,
        'trailing_activation': 4.0,
        'trailing_distance': 2.0,
    },
    TradingHorizon.INTRADAY: {
        'base_stop_pct': 5.0,
        'base_tp_pct': 10.0,
        'atr_multiplier': 1.5,
        'trailing_activation': 6.0,
        'trailing_distance': 3.0,
    },
    TradingHorizon.SWING_SHORT: {
        'base_stop_pct': 8.0,
        'base_tp_pct': 15.0,
        'atr_multiplier': 2.0,
        'trailing_activation': 10.0,
        'trailing_distance': 5.0,
    },
    TradingHorizon.SWING: {
        'base_stop_pct': 12.0,
        'base_tp_pct': 25.0,
        'atr_multiplier': 2.5,
        'trailing_activation': 15.0,
        'trailing_distance': 7.0,
    }
}


class QualityBasedTargets:
    """
    Sistema de TP/SL dinámicos basados en calidad del setup
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.QualityBasedTargets")

        # Strong catalysts que justifican targets más altos
        self.STRONG_CATALYSTS = ['FDA', 'M&A', 'BREAKTHROUGH', 'HALT_RESUME', 'CONTRACT']

        self.logger.info("🎯 QualityBasedTargets system initialized")

    def calculate_targets(
        self,
        entry_price: float,
        quality_score: float,
        catalyst_type: str,
        trading_horizon: str,
        daily_potential: Dict,
        atr: float = 0.0,
        support_level: float = 0.0
    ) -> Dict:
        """
        Calcula TP y SL dinámicos basados en calidad y contexto

        Args:
            entry_price: Precio de entrada
            quality_score: Calidad del setup (0-100)
            catalyst_type: Tipo de catalyst
            trading_horizon: Horizonte temporal (SCALP, INTRADAY, SWING_SHORT, SWING)
            daily_potential: Análisis diario con resistencia/soporte
            atr: ATR del ticker (Average True Range)
            support_level: Support level detected by entry logic (0 if not detected)

        Returns:
            Dict con TP, SL, trailing params, y reasoning
        """
        try:
            # Convert horizon string to enum
            horizon_map = {
                'scalp': TradingHorizon.SCALP,
                'intraday': TradingHorizon.INTRADAY,
                'swing_short': TradingHorizon.SWING_SHORT,
                'swing': TradingHorizon.SWING
            }
            horizon = horizon_map.get(trading_horizon.lower(), TradingHorizon.INTRADAY)

            # Get base parameters for this horizon
            params = HORIZON_RISK_PARAMS[horizon]

            # 1. CALCULATE TAKE PROFIT (quality-based)
            tp_pct = self._calculate_quality_tp(
                quality_score=quality_score,
                catalyst_type=catalyst_type,
                base_tp_pct=params['base_tp_pct'],
                resistance_distance=daily_potential.get('distance_to_resistance', 100)
            )

            # 2. CALCULATE STOP LOSS (ATR-based + horizon + support level)
            sl_pct = self._calculate_dynamic_sl(
                entry_price=entry_price,
                atr=atr,
                base_sl_pct=params['base_stop_pct'],
                atr_multiplier=params['atr_multiplier'],
                catalyst_type=catalyst_type,
                trading_horizon=horizon,
                support_level=support_level
            )

            # 3. CALCULATE PRICES
            tp_price = entry_price * (1 + tp_pct / 100)
            sl_price = entry_price * (1 - sl_pct / 100)

            # 4. VALIDATE R:R RATIO
            risk_reward = tp_pct / sl_pct
            position_adjustment = 1.0

            if risk_reward < 1.5:
                self.logger.warning(
                    f"⚠️ Low R:R ratio ({risk_reward:.2f}) - "
                    f"TP={tp_pct:.1f}%, SL={sl_pct:.1f}%"
                )
                # Adjust position size instead of rejecting
                position_adjustment = 0.5  # Half size for poor R:R

            # 5. BUILD REASONING
            reasoning = self._build_reasoning(
                quality_score=quality_score,
                catalyst_type=catalyst_type,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                risk_reward=risk_reward,
                atr=atr,
                support_level=support_level
            )

            return {
                'take_profit_price': tp_price,
                'take_profit_pct': tp_pct,
                'stop_loss_price': sl_price,
                'stop_loss_pct': sl_pct,
                'risk_reward': risk_reward,
                'trailing_activation_pct': params['trailing_activation'],
                'trailing_distance_pct': params['trailing_distance'],
                'position_size_adjustment': position_adjustment,
                'reasoning': reasoning
            }

        except Exception as e:
            self.logger.error(f"Error calculating targets: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

            # Return conservative defaults
            return {
                'take_profit_price': entry_price * 1.10,
                'take_profit_pct': 10.0,
                'stop_loss_price': entry_price * 0.95,
                'stop_loss_pct': 5.0,
                'risk_reward': 2.0,
                'trailing_activation_pct': 6.0,
                'trailing_distance_pct': 3.0,
                'position_size_adjustment': 1.0,
                'reasoning': ['Error in calculation - using defaults']
            }

    def _calculate_quality_tp(
        self,
        quality_score: float,
        catalyst_type: str,
        base_tp_pct: float,
        resistance_distance: float
    ) -> float:
        """
        Calcula TP basado en calidad del setup

        Quality tiers:
        - A+ (85-100): 3.0x base
        - A (75-84): 2.0x base
        - A- (65-74): 1.5x base
        - B+ (50-64): 1.0x base
        """
        # Quality multiplier
        if quality_score >= 85:
            quality_multiplier = 3.0  # A+: 30% para INTRADAY, 75% para SWING
        elif quality_score >= 75:
            quality_multiplier = 2.0  # A: 20% para INTRADAY, 50% para SWING
        elif quality_score >= 65:
            quality_multiplier = 1.5  # A-: 15% para INTRADAY, 37.5% para SWING
        else:
            quality_multiplier = 1.0  # B+: Base target

        # Catalyst boost (strong catalysts get +50% target)
        catalyst_boost = 1.5 if catalyst_type in self.STRONG_CATALYSTS else 1.0

        # Calculate TP
        calculated_tp = base_tp_pct * quality_multiplier * catalyst_boost

        # Cap at 80% of distance to resistance (conservador)
        resistance_cap = resistance_distance * 0.8 if resistance_distance > 0 else 50.0
        final_tp = min(calculated_tp, resistance_cap)

        return final_tp

    def _calculate_dynamic_sl(
        self,
        entry_price: float,
        atr: float,
        base_sl_pct: float,
        atr_multiplier: float,
        catalyst_type: str,
        trading_horizon: TradingHorizon,
        support_level: float = 0.0
    ) -> float:
        """
        Calcula SL fijo basado en porcentaje configurable

        Strategy: Entry AT support, SL fixed % below entry price
        - Support is used for ENTRY timing (wait for pullback to support)
        - SL is fixed % below entry (not based on support distance)
        - TP is based on resistance (previous high)

        Base SL percentages (configurable in HORIZON_RISK_PARAMS):
        - SCALP: 3.0%
        - INTRADAY: 5.0%
        - SWING_SHORT: 8.0%
        - SWING: 12.0%
        """
        # Use fixed base stop percentage from horizon config
        stop_pct = base_sl_pct

        # Catalyst adjustment (catalysts = más volatilidad = wider stop)
        if catalyst_type in self.STRONG_CATALYSTS:
            stop_pct *= 1.3  # +30% wider para strong catalysts

        # Cap máximo (no más de 15% para evitar pérdidas grandes)
        stop_pct = min(stop_pct, 15.0)

        return stop_pct

    def _build_reasoning(
        self,
        quality_score: float,
        catalyst_type: str,
        tp_pct: float,
        sl_pct: float,
        risk_reward: float,
        atr: float,
        support_level: float = 0.0
    ) -> list:
        """Build human-readable reasoning for targets"""
        reasons = []

        # Quality tier
        if quality_score >= 85:
            reasons.append(f"A+ setup (Q={quality_score:.0f}) → High TP target ({tp_pct:.1f}%)")
        elif quality_score >= 75:
            reasons.append(f"A setup (Q={quality_score:.0f}) → Medium-high TP ({tp_pct:.1f}%)")
        elif quality_score >= 65:
            reasons.append(f"A- setup (Q={quality_score:.0f}) → Standard TP ({tp_pct:.1f}%)")
        else:
            reasons.append(f"B+ setup (Q={quality_score:.0f}) → Conservative TP ({tp_pct:.1f}%)")

        # Stop loss method
        if support_level > 0:
            reasons.append(f"🎯 Dynamic SL based on support level (${support_level:.2f}, SL={sl_pct:.1f}%)")
        elif atr > 0:
            reasons.append(f"ATR-based SL ({sl_pct:.1f}%)")
        else:
            reasons.append(f"Fixed SL ({sl_pct:.1f}%)")

        # Catalyst
        if catalyst_type in self.STRONG_CATALYSTS:
            reasons.append(f"Strong catalyst ({catalyst_type}) → +50% TP boost, wider SL")

        # R:R
        if risk_reward >= 2.5:
            reasons.append(f"Excellent R:R ({risk_reward:.2f})")
        elif risk_reward >= 1.5:
            reasons.append(f"Good R:R ({risk_reward:.2f})")
        else:
            reasons.append(f"⚠️ Poor R:R ({risk_reward:.2f}) - reduced position size")

        return reasons


# Singleton instance
_quality_targets_instance = None

def get_quality_targets() -> QualityBasedTargets:
    """Get singleton QualityBasedTargets instance"""
    global _quality_targets_instance
    if _quality_targets_instance is None:
        _quality_targets_instance = QualityBasedTargets()
    return _quality_targets_instance
