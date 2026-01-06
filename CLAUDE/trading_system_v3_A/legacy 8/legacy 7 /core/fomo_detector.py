# core/fomo_detector.py
"""
FOMO Detector - Market Euphoria Detection System
===============================================

Detecta cuando el mercado está en FOMO extremo para optimizar salidas.
Complementa el sistema anti-FOMO existente detectando euforia del mercado.

Concepto: Sale cuando otros tienen FOMO, no cuando tú tienes miedo.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from core.interfaces import MarketData, Position


@dataclass
class FOMOSignal:
    """Señal de FOMO detectada"""
    symbol: str
    timestamp: datetime
    fomo_score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    exit_urgency: str  # LOW, MEDIUM, HIGH, CRITICAL
    fomo_reasons: List[str]
    technical_data: Dict[str, float]


class FOMODetector:
    """
    Market FOMO Detection System
    
    Detecta cuando el mercado está en pánico comprador extremo,
    indicando un posible techo y momento óptimo para salir.
    
    Diferente al anti-FOMO: Este detecta euforia del MERCADO,
    no previene las emociones del trader.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger("FOMODetector")
        
        # Configuración
        config = config or {}
        self.fomo_threshold = config.get('fomo_threshold', 0.55)  # 55% threshold for exit (was 75% - too high)
        self.critical_threshold = config.get('critical_threshold', 0.75)  # 75% critical (was 90% - too high)
        self.min_bars_for_analysis = config.get('min_bars_for_analysis', 10)
        self.volume_lookback_bars = config.get('volume_lookback_bars', 20)
        
        # Pesos de componentes
        self.volume_weight = config.get('volume_weight', 0.40)  # 40% peso
        self.price_action_weight = config.get('price_action_weight', 0.30)  # 30% peso  
        self.technical_weight = config.get('technical_weight', 0.20)  # 20% peso
        self.time_weight = config.get('time_weight', 0.10)  # 10% peso
        
        # Thresholds específicos - OPTIMIZED FOR BETTER SENSITIVITY
        self.volume_explosion_multiplier = config.get('volume_explosion_multiplier', 5.0)  # 5x volume (was 8x - too high)
        self.consecutive_green_bars = config.get('consecutive_green_bars', 4)  # 4 bars (was 5)
        self.rsi_overbought_level = config.get('rsi_overbought_level', 80)  # 80 RSI (was 85)
        self.price_vwap_ratio_extreme = config.get('price_vwap_ratio_extreme', 1.20)  # 20% above VWAP (was 25%)
        
        self.logger.info("🎪 FOMODetector initialized")
        self.logger.info(f"   Thresholds: FOMO={self.fomo_threshold:.1%}, Critical={self.critical_threshold:.1%}")
        self.logger.info(f"   Weights: Vol={self.volume_weight:.1%}, Price={self.price_action_weight:.1%}, Tech={self.technical_weight:.1%}, Time={self.time_weight:.1%}")
    
    def _normalize_datetimes(self, dt1: datetime, dt2: datetime) -> Tuple[datetime, datetime]:
        """Normalize two datetime objects to handle timezone differences"""
        try:
            if dt1.tzinfo is None and dt2.tzinfo is None:
                # Both naive, return as is
                return dt1, dt2
            elif dt1.tzinfo is None:
                # dt1 is naive, make dt2 naive
                return dt1, dt2.replace(tzinfo=None)
            elif dt2.tzinfo is None:
                # dt2 is naive, make dt1 naive
                return dt1.replace(tzinfo=None), dt2
            else:
                # Both timezone-aware, return as is
                return dt1, dt2
        except Exception as e:
            self.logger.warning(f"Error normalizing datetimes: {e}")
            # Fallback: make both naive
            return dt1.replace(tzinfo=None), dt2.replace(tzinfo=None)
    
    def detect_fomo_exit(self, symbol: str, current_bar: MarketData, 
                        position: Position, bars_history: List[MarketData]) -> Dict[str, Any]:
        """
        Detecta si el mercado está en FOMO extremo y debería salir
        
        Args:
            symbol: Symbol being analyzed
            current_bar: Current market data bar
            position: Current position (for context)
            bars_history: Historical bars for analysis
            
        Returns:
            Dict with exit decision and analysis
        """
        try:
            if len(bars_history) < self.min_bars_for_analysis:
                return {'should_exit': False, 'reason': 'Insufficient data for FOMO analysis'}
            
            fomo_components = {}
            fomo_reasons = []
            
            # 1. Volume FOMO Analysis (40% weight)
            volume_fomo, volume_reasons = self._analyze_volume_fomo(bars_history)
            fomo_components['volume'] = volume_fomo
            fomo_reasons.extend(volume_reasons)
            
            # 2. Price Action FOMO Analysis (30% weight)
            price_fomo, price_reasons = self._analyze_price_action_fomo(bars_history, current_bar)
            fomo_components['price_action'] = price_fomo
            fomo_reasons.extend(price_reasons)
            
            # 3. Technical FOMO Analysis (20% weight)
            tech_fomo, tech_reasons = self._analyze_technical_fomo(bars_history, current_bar)
            fomo_components['technical'] = tech_fomo
            fomo_reasons.extend(tech_reasons)
            
            # 4. Time-based FOMO Analysis (10% weight)
            time_fomo, time_reasons = self._analyze_time_fomo(current_bar, position)
            fomo_components['time'] = time_fomo
            fomo_reasons.extend(time_reasons)
            
            # Calculate weighted FOMO score
            fomo_score = (
                volume_fomo * self.volume_weight +
                price_fomo * self.price_action_weight +
                tech_fomo * self.technical_weight +
                time_fomo * self.time_weight
            )
            
            # Determine exit urgency
            if fomo_score >= self.critical_threshold:
                urgency = 'CRITICAL'
                confidence = 0.95
            elif fomo_score >= self.fomo_threshold:
                urgency = 'HIGH'  
                confidence = 0.85
            elif fomo_score >= 0.40:  # Lowered from 0.60 to 0.40
                urgency = 'MEDIUM'
                confidence = 0.70
            else:
                urgency = 'LOW'
                confidence = 0.50
            
            # Log analysis
            self.logger.info(f"🎪 FOMO Analysis {symbol}: Score={fomo_score:.2f} ({urgency})")
            self.logger.info(f"   Components: Vol={volume_fomo:.2f}, Price={price_fomo:.2f}, Tech={tech_fomo:.2f}, Time={time_fomo:.2f}")
            
            # Decision
            should_exit = fomo_score >= self.fomo_threshold
            
            if should_exit:
                self.logger.warning(f"🚨 FOMO EXIT SIGNAL: {symbol} | Score: {fomo_score:.2f} | Urgency: {urgency}")
                for reason in fomo_reasons:
                    self.logger.warning(f"   📊 {reason}")
            
            return {
                'should_exit': should_exit,
                'fomo_signal': FOMOSignal(
                    symbol=symbol,
                    timestamp=current_bar.timestamp,
                    fomo_score=fomo_score,
                    confidence=confidence,
                    exit_urgency=urgency,
                    fomo_reasons=fomo_reasons,
                    technical_data=fomo_components
                ) if should_exit else None,
                'analysis': {
                    'fomo_score': fomo_score,
                    'components': fomo_components,
                    'reasons': fomo_reasons,
                    'urgency': urgency,
                    'confidence': confidence
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in FOMO detection for {symbol}: {e}")
            return {'should_exit': False, 'reason': f'FOMO detection error: {e}'}
    
    def _analyze_volume_fomo(self, bars_history: List[MarketData]) -> Tuple[float, List[str]]:
        """Analiza FOMO basado en volumen explosivo"""
        try:
            if len(bars_history) < self.volume_lookback_bars:
                return 0.0, []
            
            recent_bars = bars_history[-10:]  # Last 10 bars
            historical_bars = bars_history[-self.volume_lookback_bars:-10]  # Previous bars for average
            
            if len(historical_bars) == 0:
                return 0.0, []
            
            # Calculate volume metrics
            current_volume = recent_bars[-1].volume
            avg_historical_volume = np.mean([bar.volume for bar in historical_bars])
            recent_avg_volume = np.mean([bar.volume for bar in recent_bars[-5:]])
            
            volume_ratio = current_volume / avg_historical_volume if avg_historical_volume > 0 else 1.0
            recent_volume_ratio = recent_avg_volume / avg_historical_volume if avg_historical_volume > 0 else 1.0
            
            # Volume acceleration (increasing each bar)
            recent_volumes = [bar.volume for bar in recent_bars[-5:]]
            volume_acceleration = 0.0
            if len(recent_volumes) >= 3:
                acceleration_count = sum(1 for i in range(1, len(recent_volumes)) 
                                       if recent_volumes[i] > recent_volumes[i-1])
                volume_acceleration = acceleration_count / (len(recent_volumes) - 1)
            
            fomo_score = 0.0
            reasons = []
            
            # Volume explosion (current bar)
            if volume_ratio >= self.volume_explosion_multiplier:
                explosion_score = min((volume_ratio / self.volume_explosion_multiplier - 1) * 0.5 + 0.4, 1.0)
                fomo_score += explosion_score * 0.5
                reasons.append(f"Volume explosion: {volume_ratio:.1f}x average")
            
            # Sustained high volume (recent average)  
            if recent_volume_ratio >= 3.0:  # Lowered from 4.0x to 3.0x
                sustained_score = min(recent_volume_ratio / 6.0, 1.0)  # Lowered denominator from 8.0 to 6.0
                fomo_score += sustained_score * 0.3
                reasons.append(f"Sustained high volume: {recent_volume_ratio:.1f}x average")
            
            # Volume acceleration
            if volume_acceleration >= 0.6:  # 60%+ of bars increasing
                fomo_score += volume_acceleration * 0.2
                reasons.append(f"Volume accelerating: {volume_acceleration:.1%} increasing bars")
            
            return min(fomo_score, 1.0), reasons
            
        except Exception as e:
            self.logger.error(f"Error in volume FOMO analysis: {e}")
            return 0.0, []
    
    def _analyze_price_action_fomo(self, bars_history: List[MarketData], 
                                  current_bar: MarketData) -> Tuple[float, List[str]]:
        """Analiza FOMO basado en price action parabólico"""
        try:
            if len(bars_history) < 10:
                return 0.0, []
            
            recent_bars = bars_history[-10:]
            
            fomo_score = 0.0
            reasons = []
            
            # 1. Consecutive green bars with strong bodies
            green_count = 0
            strong_body_count = 0
            
            for bar in recent_bars[-self.consecutive_green_bars:]:
                if bar.close > bar.open:  # Green bar
                    green_count += 1
                    body_ratio = (bar.close - bar.open) / (bar.high - bar.low) if (bar.high - bar.low) > 0 else 0
                    if body_ratio >= 0.7:  # Strong body (70%+ of range)
                        strong_body_count += 1
            
            if green_count >= self.consecutive_green_bars:
                consecutive_score = min(green_count / 7.0, 1.0)  # Max at 7 consecutive
                fomo_score += consecutive_score * 0.4
                reasons.append(f"Consecutive green bars: {green_count} in a row")
                
                if strong_body_count >= 3:
                    fomo_score += 0.2
                    reasons.append(f"Strong bodies: {strong_body_count} bars with 70%+ body")
            
            # 2. Gap ups (intraday gaps)
            gap_count = 0
            for i in range(1, min(len(recent_bars), 6)):
                prev_bar = recent_bars[-(i+1)]
                curr_bar = recent_bars[-i]
                gap_pct = (curr_bar.open - prev_bar.close) / prev_bar.close if prev_bar.close > 0 else 0
                if gap_pct >= 0.02:  # 2%+ gap up
                    gap_count += 1
            
            if gap_count >= 2:
                gap_score = min(gap_count / 4.0, 1.0)  # Max at 4 gaps
                fomo_score += gap_score * 0.3
                reasons.append(f"Multiple gap ups: {gap_count} gaps ≥2%")
            
            # 3. Parabolic acceleration (increasing price increments)
            if len(recent_bars) >= 5:
                price_changes = []
                for i in range(1, 5):
                    curr_bar = recent_bars[-i]
                    prev_bar = recent_bars[-(i+1)]
                    change_pct = (curr_bar.close - prev_bar.close) / prev_bar.close if prev_bar.close > 0 else 0
                    price_changes.append(change_pct)
                
                # Check if moves are accelerating
                if len(price_changes) >= 3:
                    accelerating = sum(1 for i in range(1, len(price_changes)) 
                                     if price_changes[i] > price_changes[i-1])
                    if accelerating >= 2:
                        accel_score = accelerating / 3.0
                        fomo_score += accel_score * 0.3
                        reasons.append(f"Parabolic acceleration: {accelerating} accelerating moves")
            
            return min(fomo_score, 1.0), reasons
            
        except Exception as e:
            self.logger.error(f"Error in price action FOMO analysis: {e}")
            return 0.0, []
    
    def _analyze_technical_fomo(self, bars_history: List[MarketData], 
                               current_bar: MarketData) -> Tuple[float, List[str]]:
        """Analiza FOMO basado en indicadores técnicos extremos"""
        try:
            if len(bars_history) < 20:
                return 0.0, []
            
            fomo_score = 0.0
            reasons = []
            
            # 1. RSI extremo (simplified RSI calculation)
            rsi = self._calculate_simple_rsi(bars_history, period=14)
            if rsi > self.rsi_overbought_level:
                rsi_score = min((rsi - self.rsi_overbought_level) / (100 - self.rsi_overbought_level), 1.0)
                fomo_score += rsi_score * 0.4
                reasons.append(f"Extreme RSI: {rsi:.1f} (>{self.rsi_overbought_level})")
            
            # 2. Price vs VWAP ratio (simplified VWAP)
            vwap = self._calculate_simple_vwap(bars_history[-20:])  # 20-bar VWAP
            if vwap > 0:
                price_vwap_ratio = current_bar.close / vwap
                if price_vwap_ratio >= self.price_vwap_ratio_extreme:
                    vwap_score = min((price_vwap_ratio - 1) / 0.5, 1.0)  # Max at 50% above VWAP
                    fomo_score += vwap_score * 0.3
                    reasons.append(f"Far above VWAP: {price_vwap_ratio:.2f}x VWAP")
            
            # 3. Bollinger Bands extension (simplified)
            if len(bars_history) >= 20:
                closes = [bar.close for bar in bars_history[-20:]]
                bb_mean = np.mean(closes)
                bb_std = np.std(closes)
                bb_upper = bb_mean + (2.5 * bb_std)  # 2.5 standard deviations
                
                if current_bar.close > bb_upper:
                    bb_score = min((current_bar.close - bb_upper) / bb_upper * 4, 1.0)
                    fomo_score += bb_score * 0.3
                    reasons.append(f"Above extended Bollinger: {((current_bar.close - bb_upper) / bb_upper * 100):.1f}%")
            
            return min(fomo_score, 1.0), reasons
            
        except Exception as e:
            self.logger.error(f"Error in technical FOMO analysis: {e}")
            return 0.0, []
    
    def _analyze_time_fomo(self, current_bar: MarketData, 
                          position: Position) -> Tuple[float, List[str]]:
        """Analiza FOMO basado en timing y duración"""
        try:
            current_time = current_bar.timestamp
            hour = current_time.hour
            minute = current_time.minute
            
            fomo_score = 0.0
            reasons = []
            
            # 1. Market session FOMO periods - REVISED LOGIC
            # First 15 minutes (9:30-9:45) - Retail opening FOMO
            if (hour == 9 and minute >= 30 and minute < 45):
                fomo_score += 0.4
                reasons.append("Opening bell retail FOMO")
            
            # Mid-morning FOMO continuation (10:30-11:30) - Often fake breakouts
            elif (hour == 10 and minute >= 30) or (hour == 11 and minute < 30):
                fomo_score += 0.3
                reasons.append("Mid-morning FOMO continuation")
            
            # Lunch time low volume manipulation (12:00-14:00) - Thin book moves
            elif 12 <= hour < 14:
                fomo_score += 0.35
                reasons.append("Low volume lunch manipulation")
            
            # End-of-day FOMO periods - MOST DANGEROUS TIME - RESTORED!
            elif hour == 15 and minute >= 45:
                # Last 15 minutes (15:45-16:00) - CRITICAL exit time
                fomo_score += 0.6  # VERY high score for last 15 minutes
                reasons.append("Market close FOMO - critical exit time")
            elif hour == 15 and minute >= 30:
                # End-of-day FOMO (15:30-15:45) - High exit priority
                fomo_score += 0.45  # High score for end-of-day period
                reasons.append("End-of-day FOMO - prime exit window")
            
            # 2. Position holding time vs catalyst freshness
            if hasattr(position, 'entry_time') and position.entry_time:
                # Use helper function to handle timezone differences
                current_time_normalized, entry_time_normalized = self._normalize_datetimes(
                    current_time, position.entry_time
                )
                
                holding_time = current_time_normalized - entry_time_normalized
                holding_hours = holding_time.total_seconds() / 3600
                
                # More nuanced holding time analysis
                if holding_hours >= 4:  # After 4+ hours, momentum usually fades
                    # Exponential decay of momentum strength
                    time_decay_score = min((holding_hours - 4) / 6, 0.5)  # Max 0.5 at 10+ hours
                    fomo_score += time_decay_score
                    reasons.append(f"Momentum decay: {holding_hours:.1f}h hold time")
                elif holding_hours >= 2:  # 2-4 hours: moderate momentum fade
                    # Light penalty for extended momentum moves
                    time_decay_score = (holding_hours - 2) / 8  # Max 0.25 at 4 hours
                    fomo_score += time_decay_score
                    reasons.append(f"Moderate momentum age: {holding_hours:.1f}h")
            
            return min(fomo_score, 1.0), reasons
            
        except Exception as e:
            self.logger.error(f"Error in time FOMO analysis: {e}")
            return 0.0, []
    
    def _calculate_simple_rsi(self, bars_history: List[MarketData], period: int = 14) -> float:
        """Simplified RSI calculation"""
        try:
            if len(bars_history) < period + 1:
                return 50.0  # Neutral
            
            closes = [bar.close for bar in bars_history[-(period+1):]]
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
    
    def _calculate_simple_vwap(self, bars_history: List[MarketData]) -> float:
        """Simplified VWAP calculation"""
        try:
            if not bars_history:
                return 0.0
            
            total_volume = 0
            total_price_volume = 0
            
            for bar in bars_history:
                typical_price = (bar.high + bar.low + bar.close) / 3
                total_price_volume += typical_price * bar.volume
                total_volume += bar.volume
            
            return total_price_volume / total_volume if total_volume > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating VWAP: {e}")
            return 0.0
    
    def get_fomo_status_summary(self) -> str:
        """Get summary status of FOMO detector"""
        return f"""🎪 FOMO DETECTOR STATUS:
   Thresholds: Exit≥{self.fomo_threshold:.1%}, Critical≥{self.critical_threshold:.1%}
   Components: Volume({self.volume_weight:.1%}), Price({self.price_action_weight:.1%}), Technical({self.technical_weight:.1%}), Time({self.time_weight:.1%})
   Status: Active and monitoring market euphoria"""