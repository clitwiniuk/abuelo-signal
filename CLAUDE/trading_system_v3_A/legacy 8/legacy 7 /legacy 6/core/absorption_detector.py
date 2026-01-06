#!/usr/bin/env python3
"""
Absorption Detector - Orderflow Analysis for Entry Timing

Detects absorption patterns (price rejection with high volume) and buyer/seller
intention to improve entry timing for workers.

Absorption = Price doesn't advance despite aggressive volume
- Long wick (rejection)
- High volume
- Small body

Buyer/Seller Intention (without Time & Sales):
- Close position relative to bar VWAP
- Next bar closes higher/lower
- Volume sustained

Edge conditions:
- RVOL > 2.0 (high relative volume)
- First hour of market (9:30-10:30 ET)
- Technical level (VWAP, ORB, support/resistance)
- Spread < 3%
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, time
import pytz


@dataclass
class AbsorptionSignal:
    """Result of absorption detection"""
    has_signal: bool
    direction: str  # 'bullish' or 'bearish'
    strength: float  # 0-100
    confidence: float  # 0-100
    absorption_bar_index: int  # Index of absorption bar
    confirmation_bar_index: int  # Index of confirmation bar
    reason: str
    metadata: Dict[str, Any]


class AbsorptionDetector:
    """
    Detects absorption patterns and buyer/seller intention.
    
    Three levels of detection:
    1. Basic absorption (wick + volume)
    2. Buyer/seller intention (proxies)
    3. Combined signal (absorption + intention + context)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.AbsorptionDetector")
        
        # Thresholds for absorption detection
        self.MIN_WICK_TO_BODY_RATIO = 2.0  # Wick must be 2x body
        self.MIN_VOLUME_MULTIPLIER = 1.5  # Volume must be 1.5x average
        self.MIN_RVOL = 2.0  # Minimum relative volume for edge
        self.MAX_SPREAD_PCT = 3.0  # Maximum bid-ask spread
        
        # Time filters (ET)
        self.EDGE_START_TIME = time(9, 30)  # 9:30 AM ET
        self.EDGE_END_TIME = time(10, 30)  # 10:30 AM ET
        
        self.logger.info("📊 AbsorptionDetector initialized")
    
    def detect_absorption(
        self, 
        bars: List,
        direction: str = 'bullish'
    ) -> Dict[str, Any]:
        """
        Level 1: Detect basic absorption pattern.
        
        Args:
            bars: List of OHLCV bars (minimum 10 bars needed)
            direction: 'bullish' (rejection down) or 'bearish' (rejection up)
        
        Returns:
            Dict with:
                - has_absorption: bool
                - strength: 0-100
                - bar_index: index of absorption bar
                - wick_size: size of rejection wick
                - body_size: size of bar body
                - volume_ratio: volume vs average
        """
        try:
            if len(bars) < 10:
                return {
                    'has_absorption': False,
                    'reason': 'Insufficient bars (need 10+)'
                }
            
            # Analyze the second-to-last bar (absorption bar)
            # We need the last bar for confirmation
            absorption_bar = bars[-2]
            
            # Calculate wick and body sizes
            bar_open = self._get_bar_value(absorption_bar, 'open')
            bar_close = self._get_bar_value(absorption_bar, 'close')
            bar_high = self._get_bar_value(absorption_bar, 'high')
            bar_low = self._get_bar_value(absorption_bar, 'low')
            bar_volume = self._get_bar_value(absorption_bar, 'volume')
            
            if direction == 'bullish':
                # Bullish absorption: rejection down (long lower wick)
                wick_size = min(bar_open, bar_close) - bar_low
                body_size = abs(bar_close - bar_open)
            else:
                # Bearish absorption: rejection up (long upper wick)
                wick_size = bar_high - max(bar_open, bar_close)
                body_size = abs(bar_close - bar_open)
            
            # Avoid division by zero
            if body_size == 0:
                body_size = 0.0001
            
            wick_to_body_ratio = wick_size / body_size
            
            # Calculate volume ratio
            avg_volume = np.mean([self._get_bar_value(b, 'volume') for b in bars[-10:-2]])
            volume_ratio = bar_volume / avg_volume if avg_volume > 0 else 0
            
            # Check if absorption criteria are met
            has_absorption = (
                wick_to_body_ratio >= self.MIN_WICK_TO_BODY_RATIO and
                volume_ratio >= self.MIN_VOLUME_MULTIPLIER
            )
            
            # Calculate strength (0-100)
            # Based on wick ratio and volume
            strength = min(100, (wick_to_body_ratio / 5.0) * 50 + (volume_ratio / 3.0) * 50)
            
            return {
                'has_absorption': has_absorption,
                'strength': strength,
                'bar_index': len(bars) - 2,
                'wick_size': wick_size,
                'body_size': body_size,
                'wick_to_body_ratio': wick_to_body_ratio,
                'volume_ratio': volume_ratio,
                'reason': f"Wick/Body={wick_to_body_ratio:.1f}, Vol={volume_ratio:.1f}x" if has_absorption else "Insufficient wick or volume"
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting absorption: {e}")
            return {'has_absorption': False, 'reason': f'Error: {str(e)}'}
    
    def detect_buyer_intention(
        self,
        bars: List,
        absorption_bar_index: int = -2
    ) -> Dict[str, Any]:
        """
        Level 2: Detect buyer/seller intention after absorption.
        
        Uses proxies (no Time & Sales needed):
        1. Close position relative to bar VWAP
        2. Next bar closes higher than absorption bar open
        3. Volume sustained
        
        Args:
            bars: List of OHLCV bars
            absorption_bar_index: Index of absorption bar (default -2)
        
        Returns:
            Dict with:
                - has_intention: bool
                - direction: 'bullish' or 'bearish'
                - strength: 0-100
                - buy_pressure: 0-1 (close position in bar)
                - closes_higher: bool
                - volume_sustained: bool
        """
        try:
            if len(bars) < 3:
                return {
                    'has_intention': False,
                    'reason': 'Insufficient bars for confirmation'
                }
            
            absorption_bar = bars[absorption_bar_index]
            confirmation_bar = bars[-1]
            
            # Proxy 1: Buy pressure (close position in bar)
            # If close > VWAP of bar -> buyers dominated
            bar_vwap = self._calculate_bar_vwap(confirmation_bar)
            bar_close = self._get_bar_value(confirmation_bar, 'close')
            bar_high = self._get_bar_value(confirmation_bar, 'high')
            bar_low = self._get_bar_value(confirmation_bar, 'low')

            # Avoid division by zero if high == low (doji/no range bar)
            bar_range = bar_high - bar_low
            if bar_range > 0:
                buy_pressure = (bar_close - bar_low) / bar_range
            else:
                # No range - assume neutral (50% pressure)
                buy_pressure = 0.5
            
            buyer_dominated = bar_close > bar_vwap
            
            # Proxy 2: Confirmation bar closes higher than absorption bar open
            absorption_open = self._get_bar_value(absorption_bar, 'open')
            closes_higher = bar_close > absorption_open
            
            # Proxy 3: Volume sustained
            absorption_volume = self._get_bar_value(absorption_bar, 'volume')
            confirmation_volume = self._get_bar_value(confirmation_bar, 'volume')
            volume_sustained = confirmation_volume > absorption_volume * 0.7
            
            # Determine direction and strength
            if buyer_dominated and closes_higher and volume_sustained:
                has_intention = True
                direction = 'bullish'
                strength = min(100, buy_pressure * 100)
            elif not buyer_dominated and not closes_higher and volume_sustained:
                has_intention = True
                direction = 'bearish'
                strength = min(100, (1 - buy_pressure) * 100)
            else:
                has_intention = False
                direction = 'neutral'
                strength = 0
            
            return {
                'has_intention': has_intention,
                'direction': direction,
                'strength': strength,
                'buy_pressure': buy_pressure,
                'buyer_dominated': buyer_dominated,
                'closes_higher': closes_higher,
                'volume_sustained': volume_sustained,
                'reason': f"Pressure={buy_pressure:.2f}, Higher={closes_higher}, Vol={volume_sustained}" if has_intention else "No clear intention"
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting buyer intention: {e}")
            return {'has_intention': False, 'reason': f'Error: {str(e)}'}
    
    def detect_absorption_with_intention(
        self,
        bars: List,
        level_price: Optional[float] = None,
        direction: str = 'bullish',
        current_time: Optional[datetime] = None,
        spread_pct: Optional[float] = None
    ) -> AbsorptionSignal:
        """
        Level 3: Combined absorption + intention detection with context filters.
        
        This is the main method to use. It combines:
        - Absorption detection (Level 1)
        - Buyer/seller intention (Level 2)
        - Context validation (RVOL, time, spread)
        
        Args:
            bars: List of OHLCV bars (minimum 10)
            level_price: Optional price level to check proximity (VWAP, ORB, etc.)
            direction: 'bullish' or 'bearish' expected absorption
            current_time: Current time for time filter (ET timezone)
            spread_pct: Current bid-ask spread percentage
        
        Returns:
            AbsorptionSignal with complete analysis
        """
        try:
            if len(bars) < 10:
                return AbsorptionSignal(
                    has_signal=False,
                    direction='neutral',
                    strength=0,
                    confidence=0,
                    absorption_bar_index=-1,
                    confirmation_bar_index=-1,
                    reason='Insufficient bars (need 10+)',
                    metadata={}
                )
            
            # Step 1: Detect absorption
            absorption = self.detect_absorption(bars, direction)
            
            if not absorption['has_absorption']:
                return AbsorptionSignal(
                    has_signal=False,
                    direction='neutral',
                    strength=0,
                    confidence=0,
                    absorption_bar_index=-2,
                    confirmation_bar_index=-1,
                    reason=f"No absorption: {absorption['reason']}",
                    metadata=absorption
                )
            
            # Step 2: Detect buyer/seller intention
            intention = self.detect_buyer_intention(bars)
            
            if not intention['has_intention']:
                return AbsorptionSignal(
                    has_signal=False,
                    direction='neutral',
                    strength=absorption['strength'],
                    confidence=0,
                    absorption_bar_index=-2,
                    confirmation_bar_index=-1,
                    reason=f"Absorption found but no intention: {intention['reason']}",
                    metadata={'absorption': absorption, 'intention': intention}
                )
            
            # Check direction match
            if intention['direction'] != direction:
                return AbsorptionSignal(
                    has_signal=False,
                    direction=intention['direction'],
                    strength=absorption['strength'],
                    confidence=0,
                    absorption_bar_index=-2,
                    confirmation_bar_index=-1,
                    reason=f"Direction mismatch: expected {direction}, got {intention['direction']}",
                    metadata={'absorption': absorption, 'intention': intention}
                )
            
            # Step 3: Context validation
            context_valid, context_reason = self._validate_context(
                bars=bars,
                current_time=current_time,
                spread_pct=spread_pct
            )
            
            # Calculate final confidence
            # Base confidence from absorption strength and intention strength
            base_confidence = (absorption['strength'] + intention['strength']) / 2
            
            # Boost confidence if context is valid
            if context_valid:
                final_confidence = min(100, base_confidence * 1.2)
            else:
                final_confidence = base_confidence * 0.7
            
            # Determine if signal is strong enough
            has_signal = (
                absorption['has_absorption'] and
                intention['has_intention'] and
                final_confidence >= 60
            )
            
            return AbsorptionSignal(
                has_signal=has_signal,
                direction=direction,
                strength=absorption['strength'],
                confidence=final_confidence,
                absorption_bar_index=-2,
                confirmation_bar_index=-1,
                reason=f"Absorption + {direction} intention confirmed. Context: {context_reason}",
                metadata={
                    'absorption': absorption,
                    'intention': intention,
                    'context_valid': context_valid,
                    'context_reason': context_reason
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error in combined detection: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return AbsorptionSignal(
                has_signal=False,
                direction='neutral',
                strength=0,
                confidence=0,
                absorption_bar_index=-1,
                confirmation_bar_index=-1,
                reason=f'Error: {str(e)}',
                metadata={}
            )
    
    def _validate_context(
        self,
        bars: List,
        current_time: Optional[datetime] = None,
        spread_pct: Optional[float] = None
    ) -> tuple[bool, str]:
        """
        Validate context for absorption edge.
        
        Checks:
        - RVOL > 2.0
        - Time window (9:30-10:30 ET)
        - Spread < 3%
        
        Returns:
            (is_valid, reason)
        """
        reasons = []
        
        # Check RVOL
        rvol = self._calculate_rvol(bars)
        if rvol < self.MIN_RVOL:
            reasons.append(f"Low RVOL ({rvol:.1f} < {self.MIN_RVOL})")
        
        # Check time window (if provided)
        if current_time:
            # Convert to ET
            et_tz = pytz.timezone('US/Eastern')
            if current_time.tzinfo is None:
                current_time = pytz.utc.localize(current_time)
            current_time_et = current_time.astimezone(et_tz)
            current_time_only = current_time_et.time()
            
            if not (self.EDGE_START_TIME <= current_time_only <= self.EDGE_END_TIME):
                reasons.append(f"Outside edge hours ({current_time_only} not in 9:30-10:30 ET)")
        
        # Check spread (if provided)
        if spread_pct is not None and spread_pct > self.MAX_SPREAD_PCT:
            reasons.append(f"Wide spread ({spread_pct:.1f}% > {self.MAX_SPREAD_PCT}%)")
        
        is_valid = len(reasons) == 0
        reason = "All context checks passed" if is_valid else "; ".join(reasons)
        
        return is_valid, reason
    
    def _calculate_rvol(self, bars: List, period: int = 20) -> float:
        """Calculate relative volume (current vs average)."""
        try:
            if len(bars) < period + 1:
                return 0.0
            
            current_volume = self._get_bar_value(bars[-1], 'volume')
            avg_volume = np.mean([self._get_bar_value(b, 'volume') for b in bars[-(period+1):-1]])
            
            return current_volume / avg_volume if avg_volume > 0 else 0.0
        except Exception as e:
            self.logger.debug(f"Error calculating RVOL: {e}")
            return 0.0
    
    def _calculate_bar_vwap(self, bar) -> float:
        """Calculate VWAP for a single bar (approximation)."""
        try:
            high = self._get_bar_value(bar, 'high')
            low = self._get_bar_value(bar, 'low')
            close = self._get_bar_value(bar, 'close')
            
            # Simple approximation: (H + L + C) / 3
            return (high + low + close) / 3
        except Exception as e:
            self.logger.debug(f"Error calculating bar VWAP: {e}")
            return 0.0
    
    def _get_bar_value(self, bar, key: str):
        """Helper to get bar value (handles both dict and object format)."""
        if isinstance(bar, dict):
            return bar.get(key, 0)
        return getattr(bar, key, 0)


# Singleton instance
_absorption_detector_instance = None

def get_absorption_detector() -> AbsorptionDetector:
    """Get singleton AbsorptionDetector instance."""
    global _absorption_detector_instance
    if _absorption_detector_instance is None:
        _absorption_detector_instance = AbsorptionDetector()
    return _absorption_detector_instance
