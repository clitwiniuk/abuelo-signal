#!/usr/bin/env python3
"""
Bull Flag Strategy - Smallcaps Intraday
Specialized for bullish continuation patterns with hybrid static/scoring approach

Pattern Focus: Bull Flags Only
- Strong flagpole move (4-15% rapid gain)
- Flag consolidation (parallel/descending channel)
- Volume contraction during flag formation
- Explosive breakout continuation on increased volume

Target: Smallcaps ($1-$15) with strong intraday momentum
Timeframe: 5-30 minute formations optimal for intraday
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from core.interfaces import MarketData, Signal, SignalType, Position
from .base import BaseStrategy


class BullFlagStrategy(BaseStrategy):
    """
    Bull Flag Strategy - Pure continuation momentum focus

    Static Rules (Hard Requirements):
    - Flagpole: Minimum 3% gain in maximum 20 minutes
    - Flag: Consolidation with 1-8% pullback from flagpole high
    - Volume: Decreasing during flag, explosive on breakout
    - Formation time: 5-45 minutes total
    - Price range: $1-$15 (smallcaps)

    Flexible Scoring (0-500 points):
    - Flagpole Quality (0-120): Strength, speed, and volume of initial move
    - Flag Quality (0-100): Clean consolidation and volume profile
    - Breakout Strength (0-150): Volume and momentum of continuation
    - Market Context (0-75): Trend alignment and sector strength
    - Timing Score (0-55): Time of day and momentum windows
    """

    def __init__(self, parameters: Dict = None):
        """Initialize Bull Flag Strategy"""
        super().__init__("BullFlag", parameters)

        # Initialize pattern detection data
        self.flagpole_data = {}  # {symbol: {'start': timestamp, 'end': timestamp, 'low': float, 'high': float}}
        self.flag_data = {}     # {symbol: {'start': timestamp, 'high': float, 'low': float, 'channel': dict}}
        self.pattern_state = {} # {symbol: 'none'|'flagpole'|'flag'|'breakout'}
        self.volume_profile = {} # {symbol: {'flagpole_vol': [], 'flag_vol': []}}

        self.logger = logging.getLogger(__name__)
        self.logger.info("🏴 Bull Flag Strategy initialized - Smallcaps momentum continuation")

    def _get_default_parameters(self) -> Dict:
        """Default parameters optimized for smallcaps bull flags"""
        return {
            # === FLAGPOLE REQUIREMENTS ===
            'min_flagpole_pct': 3.0,          # Minimum 3% gain for flagpole
            'max_flagpole_pct': 25.0,         # Maximum 25% (avoid extended moves)
            'max_flagpole_minutes': 20,       # Maximum 20 minutes for flagpole
            'min_flagpole_minutes': 2,        # Minimum 2 minutes (avoid false spikes)
            'flagpole_volume_multiplier': 1.5, # 1.5x average volume during flagpole

            # === FLAG CONSOLIDATION REQUIREMENTS ===
            'min_flag_pullback_pct': 1.0,     # Minimum 1% pullback from flagpole high
            'max_flag_pullback_pct': 8.0,     # Maximum 8% pullback (still continuation)
            'max_flag_minutes': 45,           # Maximum 45 minutes flag duration
            'min_flag_minutes': 5,            # Minimum 5 minutes consolidation
            'flag_volume_decline_ratio': 0.7,  # Flag volume should be <70% of flagpole

            # === BREAKOUT REQUIREMENTS ===
            'breakout_threshold_pct': 0.3,    # 0.3% above flag high for confirmation
            'breakout_volume_multiplier': 2.0, # 2.0x average volume for breakout
            'min_breakout_momentum': 0.5,     # Minimum 0.5% immediate follow-through

            # === STATIC FILTERS ===
            'min_price': 1.0,                 # Smallcaps minimum
            'max_price': 15.0,                # Smallcaps maximum
            'min_daily_volume': 75000,        # Higher volume requirement (flags need liquidity)
            'max_formation_minutes': 60,      # Total pattern max 60 minutes

            # === FLEXIBLE SCORING THRESHOLDS ===
            'min_flag_score': 280,            # Minimum total score (280/500 = 56%)
            'good_flag_score': 350,           # Good setup (350/500 = 70%)
            'excellent_flag_score': 420,      # Excellent setup (420/500 = 84%)

            # === SCORING WEIGHTS ===
            'flagpole_quality_weight': 120,   # Most important: flagpole strength
            'flag_quality_weight': 100,       # Flag consolidation quality
            'breakout_strength_weight': 150,  # Breakout momentum and volume
            'market_context_weight': 75,      # Market conditions
            'timing_weight': 55,              # Time of day factors

            # === RISK MANAGEMENT ===
            'stop_loss_pct': 0.05,           # 5% stop loss (below flag low)
            'take_profit_pct': 0.15,         # 15% take profit (flagpole projection)
            'breakeven_move_pct': 0.07,      # Move to breakeven at 7%
            'max_hold_minutes': 120,         # 2 hours maximum hold

            # === TIMING OPTIMIZATION ===
            'optimal_start_hour': 9.5,       # Best from market open
            'optimal_end_hour': 15.0,        # Until late afternoon
            'momentum_hours_start': 10.0,    # Prime momentum 10-11 AM
            'momentum_hours_end': 11.0,      # And 2-3 PM
            'afternoon_momentum_start': 14.0,
            'afternoon_momentum_end': 15.0,

            # === ENTRY/EXIT ===
            'entry_mode': 'breakout_confirmation', # Wait for confirmed breakout
            'min_confidence_threshold': 0.60,     # Minimum signal confidence
            'position_sizing_mode': 'volatility_based', # Size based on recent volatility
        }

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Analyze current bar for bull flag patterns and breakouts

        Process:
        1. Update pattern state machine (none -> flagpole -> flag -> breakout)
        2. Detect flagpole formation (strong rapid move)
        3. Detect flag consolidation (pullback with volume decline)
        4. Detect breakout (continuation above flag high)
        5. Score the complete pattern
        6. Generate signal if thresholds met
        """
        try:
            symbol = bar.symbol

            # Ensure we have enough history
            if not self._has_sufficient_history(symbol, min_bars=15):
                return None

            # Update pattern state and detection
            self._update_pattern_state(symbol, bar)

            # Only generate signals on breakout
            if self.pattern_state.get(symbol) != 'breakout':
                return None

            # Validate complete flag pattern
            pattern_data = self._validate_complete_pattern(symbol, bar)
            if not pattern_data:
                return None

            # Apply static filters
            if not self._passes_static_filters(symbol, bar, pattern_data):
                return None

            # Calculate flexible scoring
            scores = self._calculate_flag_scores(symbol, bar, pattern_data)
            total_score = sum(scores.values())

            # Check scoring thresholds
            min_score = self._parameters['min_flag_score']
            if total_score < min_score:
                self.logger.debug(f"🏴 {symbol}: Flag score {total_score:.0f} below threshold {min_score}")
                return None

            # Determine signal strength
            signal_strength = self._calculate_signal_strength(total_score)

            # Generate bull flag breakout signal
            signal = self._create_flag_signal(symbol, bar, pattern_data, scores, signal_strength)

            self.logger.info(f"🏴 {symbol}: BULL FLAG BREAKOUT! Score: {total_score:.0f}/500, "
                           f"Flagpole: +{pattern_data['flagpole_gain_pct']:.1f}%, "
                           f"Flag pullback: -{pattern_data['flag_pullback_pct']:.1f}%, "
                           f"Breakout: ${bar.close:.2f}")

            return signal

        except Exception as e:
            self.logger.error(f"Error analyzing bull flag for {symbol}: {e}")
            return None

    def _update_pattern_state(self, symbol: str, bar: MarketData) -> None:
        """Update pattern state machine for bull flag detection"""
        current_state = self.pattern_state.get(symbol, 'none')

        if current_state == 'none':
            # Look for flagpole start
            if self._detect_flagpole_start(symbol, bar):
                self.pattern_state[symbol] = 'flagpole'
                self.logger.debug(f"🏴 {symbol}: Flagpole detection started")

        elif current_state == 'flagpole':
            # Check if flagpole is complete or continuing
            if self._is_flagpole_complete(symbol, bar):
                self.pattern_state[symbol] = 'flag'
                self.logger.debug(f"🏴 {symbol}: Flag consolidation phase started")
            elif self._is_flagpole_failed(symbol, bar):
                self._reset_pattern_state(symbol)

        elif current_state == 'flag':
            # Check for flag completion or breakout
            if self._detect_flag_breakout(symbol, bar):
                self.pattern_state[symbol] = 'breakout'
                self.logger.debug(f"🏴 {symbol}: Flag breakout detected!")
            elif self._is_flag_failed(symbol, bar):
                self._reset_pattern_state(symbol)

        elif current_state == 'breakout':
            # Reset after processing breakout
            self._reset_pattern_state(symbol)

    def _detect_flagpole_start(self, symbol: str, bar: MarketData) -> bool:
        """Detect start of potential flagpole (strong upward move beginning)"""
        recent_bars = self.bars_history[symbol][-10:]  # Last 10 bars
        if len(recent_bars) < 5:
            return False

        # Look for acceleration in price and volume
        current_bar = recent_bars[-1]
        prev_bars = recent_bars[-5:-1]  # Previous 4 bars

        # Check for price acceleration (current bar significantly higher)
        prev_avg_close = np.mean([b.close for b in prev_bars])
        price_jump = (current_bar.close - prev_avg_close) / prev_avg_close

        # Check for volume spike
        prev_avg_volume = np.mean([b.volume for b in prev_bars])
        volume_ratio = current_bar.volume / prev_avg_volume if prev_avg_volume > 0 else 1.0

        # Flagpole start criteria
        if (price_jump >= 0.015 and  # 1.5% jump minimum
            volume_ratio >= 1.3 and  # 1.3x volume increase
            current_bar.close > current_bar.open):  # Green bar

            # Initialize flagpole tracking
            self.flagpole_data[symbol] = {
                'start_time': current_bar.timestamp,
                'start_price': prev_avg_close,
                'start_bar_idx': len(self.bars_history[symbol]) - 1,
                'high_price': current_bar.high,
                'high_time': current_bar.timestamp
            }

            # Initialize volume tracking
            self.volume_profile[symbol] = {
                'flagpole_vol': [current_bar.volume],
                'flag_vol': []
            }
            return True

        return False

    def _is_flagpole_complete(self, symbol: str, bar: MarketData) -> bool:
        """Check if flagpole formation is complete"""
        if symbol not in self.flagpole_data:
            return False

        flagpole = self.flagpole_data[symbol]

        # Update flagpole high if current bar is higher
        if bar.high > flagpole['high_price']:
            flagpole['high_price'] = bar.high
            flagpole['high_time'] = bar.timestamp
            self.volume_profile[symbol]['flagpole_vol'].append(bar.volume)
            return False  # Still extending

        # Check if we've started to pullback (flag formation)
        pullback_from_high = (flagpole['high_price'] - bar.close) / flagpole['high_price']

        # Flagpole complete if we see pullback and meet minimum requirements
        if pullback_from_high >= 0.005:  # 0.5% pullback from high
            # Validate flagpole meets requirements
            total_gain = (flagpole['high_price'] - flagpole['start_price']) / flagpole['start_price']
            time_elapsed = (flagpole['high_time'] - flagpole['start_time']).total_seconds() / 60

            if (total_gain >= self._parameters['min_flagpole_pct'] / 100 and
                total_gain <= self._parameters['max_flagpole_pct'] / 100 and
                self._parameters['min_flagpole_minutes'] <= time_elapsed <= self._parameters['max_flagpole_minutes']):

                # Initialize flag tracking
                self.flag_data[symbol] = {
                    'start_time': bar.timestamp,
                    'start_price': bar.close,
                    'high_price': flagpole['high_price'],  # Flag high = flagpole high
                    'low_price': bar.low,
                    'consolidation_bars': 1
                }
                return True

        return False

    def _is_flagpole_failed(self, symbol: str, bar: MarketData) -> bool:
        """Check if flagpole formation has failed"""
        if symbol not in self.flagpole_data:
            return True

        flagpole = self.flagpole_data[symbol]
        time_elapsed = (bar.timestamp - flagpole['start_time']).total_seconds() / 60

        # Failed if too much time has passed
        if time_elapsed > self._parameters['max_flagpole_minutes']:
            return True

        # Failed if price dropped too much from start
        current_gain = (bar.close - flagpole['start_price']) / flagpole['start_price']
        if current_gain < 0:  # Below starting point
            return True

        return False

    def _detect_flag_breakout(self, symbol: str, bar: MarketData) -> bool:
        """Detect breakout above flag consolidation"""
        if symbol not in self.flag_data:
            return False

        flag = self.flag_data[symbol]
        breakout_threshold = flag['high_price'] * (1 + self._parameters['breakout_threshold_pct'] / 100)

        # Check if we've broken above flag high
        if bar.high >= breakout_threshold:
            # Validate volume confirmation
            recent_flag_vol = self.volume_profile[symbol]['flag_vol']
            avg_flag_vol = np.mean(recent_flag_vol) if recent_flag_vol else bar.volume

            volume_ratio = bar.volume / avg_flag_vol if avg_flag_vol > 0 else 1.0

            if volume_ratio >= self._parameters['breakout_volume_multiplier']:
                return True

        return False

    def _is_flag_failed(self, symbol: str, bar: MarketData) -> bool:
        """Check if flag formation has failed"""
        if symbol not in self.flag_data:
            return True

        flag = self.flag_data[symbol]
        flagpole = self.flagpole_data[symbol]

        # Update flag data
        flag['low_price'] = min(flag['low_price'], bar.low)
        flag['consolidation_bars'] += 1
        self.volume_profile[symbol]['flag_vol'].append(bar.volume)

        # Check time limits
        flag_time = (bar.timestamp - flag['start_time']).total_seconds() / 60
        total_time = (bar.timestamp - flagpole['start_time']).total_seconds() / 60

        if (flag_time > self._parameters['max_flag_minutes'] or
            total_time > self._parameters['max_formation_minutes']):
            return True

        # Check if pullback is too deep
        pullback_pct = (flag['high_price'] - flag['low_price']) / flag['high_price'] * 100
        if pullback_pct > self._parameters['max_flag_pullback_pct']:
            return True

        # Check if trend is breaking down (close below flag start)
        if bar.close < flag['start_price'] * 0.95:  # 5% below flag start
            return True

        return False

    def _validate_complete_pattern(self, symbol: str, bar: MarketData) -> Optional[Dict]:
        """Validate complete bull flag pattern"""
        if (symbol not in self.flagpole_data or symbol not in self.flag_data):
            return None

        flagpole = self.flagpole_data[symbol]
        flag = self.flag_data[symbol]

        # Calculate pattern metrics
        flagpole_gain_pct = ((flagpole['high_price'] - flagpole['start_price']) /
                            flagpole['start_price']) * 100

        flag_pullback_pct = ((flag['high_price'] - flag['low_price']) /
                           flag['high_price']) * 100

        flagpole_duration = (flagpole['high_time'] - flagpole['start_time']).total_seconds() / 60
        flag_duration = (bar.timestamp - flag['start_time']).total_seconds() / 60

        # Validate pattern proportions
        if not (self._parameters['min_flag_pullback_pct'] <= flag_pullback_pct <=
                self._parameters['max_flag_pullback_pct']):
            return None

        return {
            'flagpole_start': flagpole['start_time'],
            'flagpole_end': flagpole['high_time'],
            'flagpole_low': flagpole['start_price'],
            'flagpole_high': flagpole['high_price'],
            'flagpole_gain_pct': flagpole_gain_pct,
            'flagpole_duration': flagpole_duration,

            'flag_start': flag['start_time'],
            'flag_end': bar.timestamp,
            'flag_high': flag['high_price'],
            'flag_low': flag['low_price'],
            'flag_pullback_pct': flag_pullback_pct,
            'flag_duration': flag_duration,

            'total_duration': flagpole_duration + flag_duration,
            'breakout_price': bar.close,
            'pattern_height': flagpole['high_price'] - flagpole['start_price']
        }

    def _passes_static_filters(self, symbol: str, bar: MarketData, pattern_data: Dict) -> bool:
        """Apply static filters that must be met"""

        # Price range filter
        if not (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
            return False

        # Flagpole strength requirement
        if pattern_data['flagpole_gain_pct'] < self._parameters['min_flagpole_pct']:
            return False

        # Volume requirements during breakout
        recent_bars = self.bars_history[symbol][-5:]
        avg_volume = np.mean([b.volume for b in recent_bars[:-1]]) if len(recent_bars) > 1 else bar.volume
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < self._parameters['breakout_volume_multiplier']:
            self.logger.debug(f"🏴 {symbol}: Breakout volume {volume_ratio:.1f}x below required {self._parameters['breakout_volume_multiplier']}x")
            return False

        # Formation timing requirements
        if pattern_data['total_duration'] > self._parameters['max_formation_minutes']:
            return False

        return True

    def _calculate_flag_scores(self, symbol: str, bar: MarketData, pattern_data: Dict) -> Dict[str, float]:
        """Calculate flexible scoring components"""
        scores = {}

        # 1. Flagpole Quality Score (0-120) - Most important
        scores['flagpole_quality'] = self._score_flagpole_quality(pattern_data)

        # 2. Flag Quality Score (0-100)
        scores['flag_quality'] = self._score_flag_quality(symbol, pattern_data)

        # 3. Breakout Strength Score (0-150)
        scores['breakout_strength'] = self._score_breakout_strength(symbol, bar, pattern_data)

        # 4. Market Context Score (0-75)
        scores['market_context'] = self._score_market_context(symbol, bar)

        # 5. Timing Score (0-55)
        scores['timing'] = self._score_timing(bar.timestamp)

        return scores

    def _score_flagpole_quality(self, pattern_data: Dict) -> float:
        """Score the quality of the flagpole (0-120)"""
        score = 0

        # Flagpole strength (gain percentage)
        gain_pct = pattern_data['flagpole_gain_pct']
        if gain_pct >= 10:
            score += 50  # Excellent flagpole
        elif gain_pct >= 7:
            score += 45  # Very strong flagpole
        elif gain_pct >= 5:
            score += 40  # Strong flagpole
        elif gain_pct >= 3:
            score += 30  # Good flagpole
        else:
            score += 20  # Minimum flagpole

        # Flagpole speed (time efficiency)
        duration = pattern_data['flagpole_duration']
        if duration <= 5:
            score += 30  # Very fast
        elif duration <= 10:
            score += 25  # Fast
        elif duration <= 15:
            score += 20  # Good speed
        else:
            score += 10  # Slower

        # Volume during flagpole
        if symbol in self.volume_profile:
            flagpole_volumes = self.volume_profile[symbol]['flagpole_vol']
            if flagpole_volumes:
                avg_flagpole_vol = np.mean(flagpole_volumes)
                recent_bars = self.bars_history[symbol][-20:]
                historical_avg = np.mean([b.volume for b in recent_bars[:-len(flagpole_volumes)]])

                if historical_avg > 0:
                    vol_ratio = avg_flagpole_vol / historical_avg
                    if vol_ratio >= 3.0:
                        score += 25  # Explosive volume
                    elif vol_ratio >= 2.0:
                        score += 20  # Strong volume
                    elif vol_ratio >= 1.5:
                        score += 15  # Good volume
                    else:
                        score += 10  # Adequate volume

        # Clean flagpole (minimal pullbacks during formation)
        gain_to_duration_ratio = gain_pct / max(duration, 1)
        if gain_to_duration_ratio >= 1.0:  # 1%+ gain per minute
            score += 15  # Very clean
        elif gain_to_duration_ratio >= 0.5:
            score += 10  # Clean
        else:
            score += 5   # Choppy

        return min(120, score)

    def _score_flag_quality(self, symbol: str, pattern_data: Dict) -> float:
        """Score the quality of the flag consolidation (0-100)"""
        score = 0

        # Flag pullback percentage (ideal range)
        pullback_pct = pattern_data['flag_pullback_pct']
        if 2 <= pullback_pct <= 5:  # Ideal range
            score += 30
        elif 1 <= pullback_pct <= 7:  # Good range
            score += 25
        elif pullback_pct <= 8:  # Acceptable
            score += 20
        else:
            score += 10  # Too deep

        # Flag duration (quick consolidation preferred)
        flag_duration = pattern_data['flag_duration']
        if flag_duration <= 15:
            score += 25  # Quick consolidation
        elif flag_duration <= 25:
            score += 20  # Good consolidation
        elif flag_duration <= 35:
            score += 15  # Acceptable
        else:
            score += 10  # Too long

        # Volume decline during flag
        if symbol in self.volume_profile:
            flag_volumes = self.volume_profile[symbol]['flag_vol']
            flagpole_volumes = self.volume_profile[symbol]['flagpole_vol']

            if flag_volumes and flagpole_volumes:
                avg_flag_vol = np.mean(flag_volumes)
                avg_flagpole_vol = np.mean(flagpole_volumes)

                if avg_flagpole_vol > 0:
                    vol_decline_ratio = avg_flag_vol / avg_flagpole_vol
                    if vol_decline_ratio <= 0.5:  # 50%+ volume decline
                        score += 25  # Excellent volume pattern
                    elif vol_decline_ratio <= 0.7:  # 30%+ decline
                        score += 20  # Good volume pattern
                    elif vol_decline_ratio <= 0.85:  # Some decline
                        score += 15  # Acceptable
                    else:
                        score += 10  # Poor volume pattern

        # Flag trend (should be orderly consolidation)
        pattern_ratio = pullback_pct / max(flag_duration, 1)  # Pullback per minute
        if 0.1 <= pattern_ratio <= 0.5:  # Orderly consolidation
            score += 20
        elif pattern_ratio <= 0.8:  # Acceptable
            score += 15
        else:
            score += 10  # Too steep or too flat

        return min(100, score)

    def _score_breakout_strength(self, symbol: str, bar: MarketData, pattern_data: Dict) -> float:
        """Score breakout strength (0-150)"""
        score = 0

        # Volume on breakout
        if symbol in self.volume_profile:
            flag_volumes = self.volume_profile[symbol]['flag_vol']
            if flag_volumes:
                avg_flag_vol = np.mean(flag_volumes)
                breakout_vol_ratio = bar.volume / avg_flag_vol if avg_flag_vol > 0 else 1.0

                if breakout_vol_ratio >= 4.0:
                    score += 60  # Explosive breakout volume
                elif breakout_vol_ratio >= 3.0:
                    score += 50  # Very strong volume
                elif breakout_vol_ratio >= 2.0:
                    score += 40  # Strong volume
                elif breakout_vol_ratio >= 1.5:
                    score += 30  # Good volume
                else:
                    score += 15  # Weak volume

        # Breakout distance above flag high
        breakout_distance = ((bar.close - pattern_data['flag_high']) /
                           pattern_data['flag_high']) * 100

        if breakout_distance >= 1.0:
            score += 35  # Strong breakout
        elif breakout_distance >= 0.5:
            score += 30  # Good breakout
        elif breakout_distance >= 0.2:
            score += 25  # Decent breakout
        else:
            score += 15  # Minimal breakout

        # Momentum follow-through (current price vs breakout bar)
        momentum_ratio = bar.close / bar.open
        if momentum_ratio >= 1.02:  # 2%+ gain on breakout bar
            score += 25
        elif momentum_ratio >= 1.01:  # 1%+ gain
            score += 20
        elif momentum_ratio >= 1.005:  # 0.5%+ gain
            score += 15
        else:
            score += 10

        # Pattern completion timing
        if pattern_data['total_duration'] <= 30:  # Quick pattern
            score += 15
        elif pattern_data['total_duration'] <= 45:  # Good timing
            score += 10
        else:
            score += 5

        # Clean breakout (close near high of breakout bar)
        close_to_high_ratio = bar.close / bar.high
        if close_to_high_ratio >= 0.98:
            score += 15  # Very clean
        elif close_to_high_ratio >= 0.95:
            score += 10  # Clean
        else:
            score += 5   # Some pullback

        return min(150, score)

    def _score_market_context(self, symbol: str, bar: MarketData) -> float:
        """Score market context (0-75)"""
        score = 0

        # Recent trend direction
        recent_bars = self.bars_history[symbol][-15:]
        if len(recent_bars) >= 10:
            early_avg = np.mean([b.close for b in recent_bars[:5]])
            recent_avg = np.mean([b.close for b in recent_bars[-5:]])
            trend_pct = ((recent_avg - early_avg) / early_avg) * 100

            if trend_pct >= 3:
                score += 25  # Strong uptrend context
            elif trend_pct >= 1:
                score += 20  # Uptrend context
            elif trend_pct >= -1:
                score += 15  # Neutral context
            else:
                score += 10  # Downtrend context

        # Volatility (higher better for breakouts)
        if len(recent_bars) >= 5:
            prices = [b.close for b in recent_bars[-5:]]
            volatility = np.std(prices) / np.mean(prices)

            if volatility >= 0.04:  # High volatility
                score += 20
            elif volatility >= 0.025:  # Good volatility
                score += 15
            else:
                score += 10  # Low volatility

        # Price level for smallcaps
        if 3.0 <= bar.close <= 10.0:  # Sweet spot
            score += 20
        elif 1.5 <= bar.close <= 12.0:  # Good range
            score += 15
        else:
            score += 10  # Suboptimal range

        # Overall volume trend
        if len(recent_bars) >= 5:
            recent_vol_avg = np.mean([b.volume for b in recent_bars[-3:]])
            earlier_vol_avg = np.mean([b.volume for b in recent_bars[-8:-5]])

            if earlier_vol_avg > 0:
                vol_trend = recent_vol_avg / earlier_vol_avg
                if vol_trend >= 1.5:  # Increasing volume
                    score += 10
                elif vol_trend >= 1.2:  # Some increase
                    score += 5

        return min(75, score)

    def _score_timing(self, timestamp: datetime) -> float:
        """Score timing factors (0-55)"""
        score = 0

        # Time of day
        hour = timestamp.hour + timestamp.minute / 60.0

        # Prime momentum hours
        if (self._parameters['momentum_hours_start'] <= hour <= self._parameters['momentum_hours_end'] or
            self._parameters['afternoon_momentum_start'] <= hour <= self._parameters['afternoon_momentum_end']):
            score += 25  # Prime momentum times
        elif 9.5 <= hour <= 15.0:  # Regular market hours
            score += 20
        elif 15.0 <= hour <= 15.5:  # Late afternoon
            score += 15
        else:
            score += 5   # Suboptimal times

        # Day of week
        weekday = timestamp.weekday()
        if weekday in [1, 2, 3]:  # Tue, Wed, Thu
            score += 20
        elif weekday in [0, 4]:  # Mon, Fri
            score += 15
        else:
            score += 5

        # Avoid first 15 minutes (can be choppy)
        if hour >= 9.75:  # After 9:45 AM
            score += 10

        return min(55, score)

    def _calculate_signal_strength(self, total_score: float) -> float:
        """Convert total score to signal strength (0.0-1.0)"""
        excellent_threshold = self._parameters['excellent_flag_score']
        good_threshold = self._parameters['good_flag_score']
        min_threshold = self._parameters['min_flag_score']

        if total_score >= excellent_threshold:
            return 0.95  # Excellent setup
        elif total_score >= good_threshold:
            return 0.80  # Good setup
        elif total_score >= min_threshold:
            return 0.65  # Acceptable setup
        else:
            return 0.50  # Below threshold

    def _create_flag_signal(self, symbol: str, bar: MarketData, pattern_data: Dict,
                          scores: Dict, strength: float) -> Signal:
        """Create bull flag breakout signal"""

        # Calculate profit target based on flagpole height projection
        flagpole_height = pattern_data['pattern_height']
        flagpole_height_pct = (flagpole_height / pattern_data['flagpole_low']) * 100

        # Project flagpole height from breakout point
        profit_target_pct = max(
            self._parameters['take_profit_pct'],
            flagpole_height_pct / 100 * 0.8  # 80% of flagpole height
        )
        profit_target_pct = min(profit_target_pct, 0.30)  # Cap at 30%

        # Stop loss below flag low
        stop_loss_price = pattern_data['flag_low'] * 0.98  # 2% below flag low

        signal = Signal(
            signal_id=f"BullFlag-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol,
            signal_type=SignalType.LONG,
            strength=strength,
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name="BullFlag",
            metadata={
                'strategy': 'BullFlag',
                'setup_type': 'bull_flag_breakout',
                'flagpole_gain_pct': pattern_data['flagpole_gain_pct'],
                'flag_pullback_pct': pattern_data['flag_pullback_pct'],
                'flagpole_duration': pattern_data['flagpole_duration'],
                'flag_duration': pattern_data['flag_duration'],
                'total_duration': pattern_data['total_duration'],
                'breakout_price': pattern_data['breakout_price'],
                'flagpole_high': pattern_data['flagpole_high'],
                'flag_low': pattern_data['flag_low'],
                'total_score': sum(scores.values()),
                'score_breakdown': scores,
                'is_entry': True,
                'stop_loss': stop_loss_price,
                'take_profit': bar.close * (1 + profit_target_pct),
                'pattern': f"bull_flag_{pattern_data['flagpole_gain_pct']:.1f}pct_pole"
            }
        )

        return signal

    def _reset_pattern_state(self, symbol: str) -> None:
        """Reset pattern tracking for symbol"""
        self.pattern_state[symbol] = 'none'
        if symbol in self.flagpole_data:
            del self.flagpole_data[symbol]
        if symbol in self.flag_data:
            del self.flag_data[symbol]
        if symbol in self.volume_profile:
            del self.volume_profile[symbol]

    def _has_sufficient_history(self, symbol: str, min_bars: int = 15) -> bool:
        """Check if we have enough historical data"""
        return (symbol in self.bars_history and
                len(self.bars_history[symbol]) >= min_bars)

    def get_strategy_info(self) -> Dict:
        """Return strategy information"""
        return {
            'name': 'BullFlag',
            'description': 'Bull flag continuation pattern strategy for smallcaps',
            'version': '1.0.0',
            'parameters_count': len(self._parameters),
            'pattern_type': 'Bull Flag Continuation',
            'market_focus': 'Smallcaps ($1-$15)',
            'timeframe': 'Intraday (5-45 min formation)',
            'signal_type': 'Momentum continuation',
            'risk_reward': '1:3+ (5% stop, 15% target)',
            'pattern_phases': ['Flagpole', 'Flag Consolidation', 'Breakout']
        }

    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For bull flag strategy, we don't need special logic on position updates
        # Position management is handled by the main strategy logic and risk management
        return None

    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited based on bull flag conditions"""
        try:
            symbol = position.symbol
            current_price = current_bar.close

            # Basic exit conditions for bull flag breakouts

            # 1. Stop loss check (below flag low)
            if hasattr(position, 'metadata') and position.metadata:
                flag_low = position.metadata.get('flag_low')
                if flag_low:
                    # Stop loss 2% below the flag low
                    stop_loss_price = flag_low * 0.98
                    if current_price <= stop_loss_price:
                        return Signal(
                            signal_id=f"BullFlag-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=1.0,
                            price=current_price,
                            timestamp=current_bar.timestamp,
                            strategy_name="BullFlag",
                            metadata={
                                'exit_reason': 'stop_loss',
                                'flag_low': flag_low,
                                'entry_price': position.avg_price
                            }
                        )

            # 2. Profit target check (based on flagpole projection)
            profit_target_pct = self._parameters.get('take_profit_pct', 0.15)  # 15% default
            target_price = position.avg_price * (1 + profit_target_pct)
            if current_price >= target_price:
                return Signal(
                    signal_id=f"BullFlag-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,
                    price=current_price,
                    timestamp=current_bar.timestamp,
                    strategy_name="BullFlag",
                    metadata={
                        'exit_reason': 'profit_target',
                        'target_price': target_price,
                        'entry_price': position.avg_price,
                        'profit_pct': ((current_price - position.avg_price) / position.avg_price) * 100
                    }
                )

            # 3. Failed flag pattern (price drops significantly below breakout)
            if hasattr(position, 'metadata') and position.metadata:
                breakout_price = position.metadata.get('breakout_price')
                if breakout_price and current_price < breakout_price * 0.97:  # 3% below breakout
                    return Signal(
                        signal_id=f"BullFlag-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="BullFlag",
                        metadata={
                            'exit_reason': 'failed_pattern',
                            'breakout_price': breakout_price,
                            'entry_price': position.avg_price
                        }
                    )

            # 4. Time-based exit (maximum hold time)
            if hasattr(position, 'entry_time') and position.entry_time:
                hold_time = (current_bar.timestamp - position.entry_time).total_seconds() / 60
                max_hold_minutes = self._parameters.get('max_hold_minutes', 120)  # 2 hours default

                if hold_time > max_hold_minutes:
                    return Signal(
                        signal_id=f"BullFlag-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.8,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="BullFlag",
                        metadata={
                            'exit_reason': 'time_limit',
                            'hold_time_minutes': hold_time,
                            'entry_price': position.avg_price
                        }
                    )

            # No exit signal
            return None

        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None