#!/usr/bin/env python3
"""
Parabolic Extension Detector - Detecta Movimientos Parabólicos para Operativa LONG
===================================================================================

Detecta extensiones parabólicas alcistas en diferentes etapas:
- EARLY STAGE: Inicio de aceleración (OPORTUNIDAD LONG)
- MIDDLE STAGE: Momentum establecido (HOLD/MONITOREAR)
- LATE STAGE: Agotamiento inminente (SEÑAL DE SALIDA)

Concepto: Identifica stocks "in play" con momentum extremo,
          distinguiendo entre oportunidad (early) y riesgo (late).
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    from core.interfaces import MarketData
except ImportError:
    from collections import namedtuple
    MarketData = namedtuple('MarketData', ['timestamp', 'open', 'high', 'low', 'close', 'volume'])


@dataclass
class ParabolicSignal:
    """Señal de extensión parabólica detectada"""
    symbol: str
    timestamp: datetime
    direction: str  # 'BULLISH', 'BEARISH'
    stage: str  # 'EARLY', 'MIDDLE', 'LATE'
    strength: float  # 0.0-1.0 (qué tan parabólico es)
    acceleration: float  # 0.0-1.0 (velocidad de aceleración)
    exhaustion_score: float  # 0.0-1.0 (qué tan cerca del agotamiento)

    # Oportunidades de trading
    long_entry_opportunity: bool  # Early-stage alcista
    short_entry_opportunity: bool # Late-stage reversal (SHORT opportunity)
    hold_signal: bool  # Middle-stage, mantener posición
    exit_warning: bool  # Late-stage, considerar salida

    # Datos técnicos
    reasons: List[str]
    technical_data: Dict[str, float]

    def __str__(self):
        return (f"{self.direction} Parabolic {self.stage} - "
                f"Strength: {self.strength:.2f}, Accel: {self.acceleration:.2f}, "
                f"Exhaustion: {self.exhaustion_score:.2f}")


class ParabolicExtensionDetector:
    """
    Detector de Extensiones Parabólicas - Enfocado en operativa LONG

    Identifica movimientos con aceleración de precio para:
    1. Entrar en early-stage parabólicos (oportunidad LONG)
    2. Mantener en middle-stage (hold con trailing stops)
    3. Salir en late-stage (tomar ganancias antes de reversión)

    Diferencias vs FOMO Detector:
    - FOMO: Detecta agotamiento para salir
    - Parabolic: Detecta aceleración para entrar Y detecta agotamiento
    """

    def __init__(self, config: Dict = None):
        self.logger = logging.getLogger(f"{__name__}.ParabolicExtensionDetector")
        self.config = config or {}

        # Configuración de períodos
        self.roc_period_short = self.config.get('roc_period_short', 3)  # ROC corto (aceleración reciente)
        self.roc_period_medium = self.config.get('roc_period_medium', 5)  # ROC medio
        self.roc_period_long = self.config.get('roc_period_long', 10)  # ROC largo (tendencia)
        self.min_bars_analysis = self.config.get('min_bars_analysis', 15)

        # Thresholds para detección ALCISTA (LONG)
        self.early_stage_roc_threshold = self.config.get('early_stage_roc_threshold', 0.05)  # 5% en 3 bars
        self.middle_stage_roc_threshold = self.config.get('middle_stage_roc_threshold', 0.10)  # 10% en 5 bars
        self.late_stage_roc_threshold = self.config.get('late_stage_roc_threshold', 0.20)  # 20%+ en 10 bars

        # Acceleration thresholds
        self.acceleration_threshold = self.config.get('acceleration_threshold', 1.5)  # ROC short > 1.5x ROC long
        self.extreme_acceleration_threshold = self.config.get('extreme_acceleration_threshold', 2.5)  # 2.5x

        # Volume confirmation thresholds
        self.volume_confirmation_multiplier = self.config.get('volume_confirmation_multiplier', 1.5)  # 1.5x avg
        self.volume_climax_multiplier = self.config.get('volume_climax_multiplier', 3.0)  # 3x avg (warning)

        # Exhaustion signals
        self.consecutive_bars_threshold = self.config.get('consecutive_bars_threshold', 5)  # 5+ consecutive
        self.rsi_exhaustion_level = self.config.get('rsi_exhaustion_level', 75)  # RSI > 75
        self.angle_steep_threshold = self.config.get('angle_steep_threshold', 60)  # Ángulo > 60 grados

        self.logger.info("🚀 ParabolicExtensionDetector initialized (LONG-focused)")
        self.logger.info(f"   Early: ROC>{self.early_stage_roc_threshold:.1%}, Mid: ROC>{self.middle_stage_roc_threshold:.1%}, Late: ROC>{self.late_stage_roc_threshold:.1%}")

    def detect_parabolic_extension(self, symbol: str, bars: List[MarketData]) -> Optional[ParabolicSignal]:
        """
        Detecta extensión parabólica y determina la etapa

        Args:
            symbol: Symbol to analyze
            bars: Historical bars (minimum 15 recommended)

        Returns:
            ParabolicSignal if detected, None otherwise
        """
        try:
            if len(bars) < self.min_bars_analysis:
                return None

            # 1. Calculate Rate of Change (ROC) at different timeframes
            roc_short = self._calculate_roc(bars, self.roc_period_short)
            roc_medium = self._calculate_roc(bars, self.roc_period_medium)
            roc_long = self._calculate_roc(bars, self.roc_period_long)

            if roc_short is None or roc_medium is None or roc_long is None:
                return None

            # 2. Determine direction (bullish or bearish)
            direction = 'BULLISH' if roc_medium > 0 else 'BEARISH'

            # Para operativa LONG, solo nos interesan los alcistas
            if direction != 'BULLISH':
                return None

            # 3. Calculate acceleration (is ROC increasing?)
            acceleration_score = self._calculate_acceleration_score(roc_short, roc_medium, roc_long)

            # 4. Analyze volume confirmation
            volume_score, volume_reasons = self._analyze_volume_pattern(bars)

            # 5. Calculate parabolic strength
            strength_score = self._calculate_parabolic_strength(bars, roc_short, roc_medium, roc_long)

            # 6. Detect exhaustion signals
            exhaustion_score, exhaustion_reasons = self._detect_exhaustion_signals(bars, roc_short, roc_medium)

            # 7. Determine stage (EARLY, MIDDLE, LATE)
            stage, stage_reasons = self._determine_stage(
                roc_short, roc_medium, roc_long,
                acceleration_score, exhaustion_score, volume_score
            )

            # 8. Check if meets minimum threshold for detection
            if strength_score < 0.25:  # Minimum 25% strength to report
                return None

            # 9. Determine trading opportunities
            # LONG: Early stage, good strength, low exhaustion
            long_entry = (stage == 'EARLY' and strength_score >= 0.25 and exhaustion_score < 0.5)
            
            # SHORT: Late stage OR High Exhaustion + Reversal Sign (rejection/red candle)
            # Must be significantly extended (strength > 0.4)
            is_reversal_candidate = (stage == 'LATE' or exhaustion_score >= 0.70)
            has_reversal_confirmation = (
                bars[-1].close < bars[-1].open or # Red candle
                (bars[-1].high - bars[-1].close) > (bars[-1].high - bars[-1].low) * 0.4 # Large upper wick
            )
            short_entry = (is_reversal_candidate and strength_score >= 0.4 and has_reversal_confirmation)

            hold_signal = (stage == 'MIDDLE' and exhaustion_score < 0.6)
            exit_warning = (stage == 'LATE' or exhaustion_score >= 0.7)

            # 10. Compile reasons
            all_reasons = stage_reasons + volume_reasons + exhaustion_reasons

            # 11. Technical data
            technical_data = {
                'roc_short': roc_short,
                'roc_medium': roc_medium,
                'roc_long': roc_long,
                'acceleration_score': acceleration_score,
                'volume_score': volume_score,
                'strength_score': strength_score,
                'exhaustion_score': exhaustion_score,
                'current_price': bars[-1].close,
                'price_change_pct': roc_medium
            }

            # 12. Create signal
            signal = ParabolicSignal(
                symbol=symbol,
                timestamp=bars[-1].timestamp,
                direction=direction,
                stage=stage,
                strength=strength_score,
                acceleration=acceleration_score,
                exhaustion_score=exhaustion_score,
                long_entry_opportunity=long_entry,
                short_entry_opportunity=short_entry,
                hold_signal=hold_signal,
                exit_warning=exit_warning,
                reasons=all_reasons,
                technical_data=technical_data
            )

            # Log detection
            if long_entry:
                self.logger.info(f"🚀 PARABOLIC ENTRY OPPORTUNITY: {symbol} - {signal}")
                for reason in all_reasons[:3]:  # Top 3 reasons
                    self.logger.info(f"   ✓ {reason}")
            elif exit_warning:
                self.logger.warning(f"⚠️ PARABOLIC EXIT WARNING: {symbol} - {signal}")
                for reason in exhaustion_reasons[:2]:
                    self.logger.warning(f"   ⚠️ {reason}")

            return signal

        except Exception as e:
            self.logger.error(f"Error detecting parabolic extension for {symbol}: {e}")
            return None

    def _calculate_roc(self, bars: List[MarketData], period: int) -> Optional[float]:
        """Calculate Rate of Change over period"""
        try:
            if len(bars) < period + 1:
                return None

            current_price = bars[-1].close
            past_price = bars[-(period + 1)].close

            if past_price == 0:
                return None

            roc = (current_price - past_price) / past_price
            return roc

        except Exception as e:
            self.logger.error(f"Error calculating ROC: {e}")
            return None

    def _calculate_acceleration_score(self, roc_short: float, roc_medium: float, roc_long: float) -> float:
        """
        Calculate acceleration score (0.0-1.0)
        Score is high when short-term ROC > medium-term ROC > long-term ROC
        """
        try:
            score = 0.0

            # Check if accelerating (short > medium > long)
            if roc_short > roc_medium > roc_long > 0:
                # Calculate acceleration ratio
                if roc_long > 0:
                    short_to_long_ratio = roc_short / roc_long
                    if short_to_long_ratio >= self.extreme_acceleration_threshold:
                        score = 1.0  # Extreme acceleration
                    elif short_to_long_ratio >= self.acceleration_threshold:
                        score = 0.7 + (short_to_long_ratio - self.acceleration_threshold) * 0.3
                    else:
                        score = 0.5 + (short_to_long_ratio - 1.0) * 0.4
            elif roc_short > roc_medium > 0:
                score = 0.4  # Moderate acceleration
            elif roc_short > 0:
                score = 0.2  # Minimal acceleration

            return min(score, 1.0)

        except Exception as e:
            self.logger.error(f"Error calculating acceleration: {e}")
            return 0.0

    def _analyze_volume_pattern(self, bars: List[MarketData]) -> Tuple[float, List[str]]:
        """Analyze volume pattern for confirmation"""
        try:
            if len(bars) < 20:
                return 0.5, []

            recent_bars = bars[-5:]
            historical_bars = bars[-20:-5]

            avg_historical_volume = np.mean([bar.volume for bar in historical_bars])
            recent_avg_volume = np.mean([bar.volume for bar in recent_bars])
            current_volume = bars[-1].volume

            score = 0.0
            reasons = []

            # Volume confirmation (above average)
            if avg_historical_volume > 0:
                volume_ratio = recent_avg_volume / avg_historical_volume

                if volume_ratio >= self.volume_climax_multiplier:
                    score = 0.9  # High but warning of climax
                    reasons.append(f"Volume climax: {volume_ratio:.1f}x average (warning)")
                elif volume_ratio >= self.volume_confirmation_multiplier:
                    score = 1.0  # Perfect confirmation
                    reasons.append(f"Strong volume: {volume_ratio:.1f}x average")
                else:
                    score = 0.6  # Weak volume
                    reasons.append(f"Below average volume: {volume_ratio:.1f}x")

            # Volume acceleration (increasing each bar)
            recent_volumes = [bar.volume for bar in recent_bars]
            increasing_count = sum(1 for i in range(1, len(recent_volumes))
                                 if recent_volumes[i] > recent_volumes[i-1])

            if increasing_count >= 3:
                score = min(score + 0.2, 1.0)
                reasons.append(f"Volume accelerating: {increasing_count}/4 bars increasing")

            return score, reasons

        except Exception as e:
            self.logger.error(f"Error analyzing volume: {e}")
            return 0.5, []

    def _calculate_parabolic_strength(self, bars: List[MarketData],
                                     roc_short: float, roc_medium: float, roc_long: float) -> float:
        """Calculate overall parabolic strength (0.0-1.0)"""
        try:
            score = 0.0

            # 1. ROC strength (40% weight)
            roc_score = 0.0
            if roc_medium >= self.late_stage_roc_threshold:
                roc_score = 1.0
            elif roc_medium >= self.middle_stage_roc_threshold:
                roc_score = 0.7
            elif roc_medium >= self.early_stage_roc_threshold:
                roc_score = 0.4

            score += roc_score * 0.4

            # 2. Consecutive green bars (30% weight)
            consecutive_green = self._count_consecutive_green_bars(bars)
            consecutive_score = min(consecutive_green / 7.0, 1.0)  # Max at 7 bars
            score += consecutive_score * 0.3

            # 3. Angle of ascent (30% weight)
            angle_score = self._calculate_angle_score(bars)
            score += angle_score * 0.3

            return min(score, 1.0)

        except Exception as e:
            self.logger.error(f"Error calculating strength: {e}")
            return 0.0

    def _detect_exhaustion_signals(self, bars: List[MarketData],
                                  roc_short: float, roc_medium: float) -> Tuple[float, List[str]]:
        """Detect exhaustion signals (0.0-1.0)"""
        try:
            exhaustion_score = 0.0
            reasons = []

            # 1. Extreme consecutive bars (sign of exhaustion)
            consecutive_green = self._count_consecutive_green_bars(bars)
            if consecutive_green >= 7:
                exhaustion_score += 0.4
                reasons.append(f"Extreme run: {consecutive_green} consecutive green bars")
            elif consecutive_green >= 5:
                exhaustion_score += 0.2
                reasons.append(f"Extended run: {consecutive_green} consecutive bars")

            # 2. RSI overbought
            rsi = self._calculate_simple_rsi(bars)
            if rsi >= 85:
                exhaustion_score += 0.4
                reasons.append(f"Extreme RSI: {rsi:.1f}")
            elif rsi >= self.rsi_exhaustion_level:
                exhaustion_score += 0.2
                reasons.append(f"Overbought RSI: {rsi:.1f}")

            # 3. Deceleration (ROC short < ROC medium) - momentum slowing
            if roc_short < roc_medium:
                exhaustion_score += 0.3
                reasons.append(f"Momentum decelerating: ROC short {roc_short:.2%} < medium {roc_medium:.2%}")

            # 4. Large upper wicks (rejection at highs)
            upper_wick_score = self._analyze_upper_wicks(bars[-5:])
            if upper_wick_score >= 0.6:
                exhaustion_score += 0.2
                reasons.append("Large upper wicks detected (rejection)")

            return min(exhaustion_score, 1.0), reasons

        except Exception as e:
            self.logger.error(f"Error detecting exhaustion: {e}")
            return 0.0, []

    def _determine_stage(self, roc_short: float, roc_medium: float, roc_long: float,
                        acceleration_score: float, exhaustion_score: float,
                        volume_score: float) -> Tuple[str, List[str]]:
        """Determine parabolic stage (EARLY, MIDDLE, LATE)"""
        reasons = []

        # LATE STAGE: High exhaustion or extreme ROC
        if exhaustion_score >= 0.6:
            reasons.append(f"Late stage: High exhaustion ({exhaustion_score:.2f})")
            return 'LATE', reasons

        if roc_medium >= self.late_stage_roc_threshold:
            reasons.append(f"Late stage: Extreme ROC ({roc_medium:.1%} in {self.roc_period_medium} bars)")
            return 'LATE', reasons

        # MIDDLE STAGE: Established momentum
        if roc_medium >= self.middle_stage_roc_threshold:
            reasons.append(f"Middle stage: Strong momentum ({roc_medium:.1%})")
            return 'MIDDLE', reasons

        if acceleration_score >= 0.7 and volume_score >= 0.7:
            reasons.append(f"Middle stage: Accelerating with volume (accel={acceleration_score:.2f})")
            return 'MIDDLE', reasons

        # EARLY STAGE: Initial acceleration
        if roc_medium >= self.early_stage_roc_threshold:
            reasons.append(f"Early stage: Initial acceleration ({roc_medium:.1%})")
            return 'EARLY', reasons

        if acceleration_score >= 0.5:
            reasons.append(f"Early stage: Building momentum (accel={acceleration_score:.2f})")
            return 'EARLY', reasons

        # Default to EARLY if showing any parabolic characteristics
        reasons.append("Early stage: Beginning parabolic move")
        return 'EARLY', reasons

    def _count_consecutive_green_bars(self, bars: List[MarketData]) -> int:
        """Count consecutive green (bullish) bars"""
        count = 0
        for bar in reversed(bars):
            if bar.close > bar.open:
                count += 1
            else:
                break
        return count

    def _calculate_angle_score(self, bars: List[MarketData]) -> float:
        """
        Calculate angle of ascent score (0.0-1.0)
        Measures how steep the price rise is
        """
        try:
            if len(bars) < 5:
                return 0.0

            # Use last 5 bars
            recent_bars = bars[-5:]
            closes = [bar.close for bar in recent_bars]

            # Linear regression to find slope
            x = np.arange(len(closes))
            y = np.array(closes)

            # Calculate slope
            slope = np.polyfit(x, y, 1)[0]

            # Normalize slope by price (percentage per bar)
            avg_price = np.mean(closes)
            if avg_price == 0:
                return 0.0

            slope_pct = slope / avg_price

            # Convert to score (higher slope = higher score)
            # 5%+ per bar = maximum score
            score = min(slope_pct / 0.05, 1.0)

            return max(score, 0.0)

        except Exception as e:
            self.logger.error(f"Error calculating angle: {e}")
            return 0.0

    def _calculate_simple_rsi(self, bars: List[MarketData], period: int = 14) -> float:
        """Simplified RSI calculation"""
        try:
            if len(bars) < period + 1:
                return 50.0  # Neutral

            closes = [bar.close for bar in bars[-(period+1):]]
            gains = []
            losses = []

            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return 50.0

    def _analyze_upper_wicks(self, bars: List[MarketData]) -> float:
        """
        Analyze upper wicks as rejection signals
        Returns score 0.0-1.0 (higher = more rejection)
        """
        try:
            if not bars:
                return 0.0

            rejection_count = 0

            for bar in bars:
                body = abs(bar.close - bar.open)
                total_range = bar.high - bar.low

                if total_range == 0:
                    continue

                # Calculate upper wick
                upper_wick = bar.high - max(bar.open, bar.close)
                upper_wick_ratio = upper_wick / total_range

                # Upper wick > 40% of range = rejection
                if upper_wick_ratio >= 0.4:
                    rejection_count += 1

            # Score based on proportion of bars with rejection
            score = rejection_count / len(bars)
            return score

        except Exception as e:
            self.logger.error(f"Error analyzing upper wicks: {e}")
            return 0.0

    def get_detector_status(self) -> str:
        """Get detector status summary"""
        return f"""🚀 PARABOLIC EXTENSION DETECTOR STATUS:
   Mode: LONG-focused (bullish patterns only)
   Stages: EARLY (entry), MIDDLE (hold), LATE (exit)
   ROC Thresholds: Early≥{self.early_stage_roc_threshold:.1%}, Mid≥{self.middle_stage_roc_threshold:.1%}, Late≥{self.late_stage_roc_threshold:.1%}
   Acceleration: ≥{self.acceleration_threshold:.1f}x for detection
   Status: Active and monitoring parabolic moves"""
