#!/usr/bin/env python3
"""
Falling Wedge Strategy - Pattern Recognition for Smallcaps Intraday
Ubicación: strategies/falling_wedge_strategy.py

Falling Wedge Pattern Characteristics:
- Converging trend lines with both sloping downward
- Lower trend line (support) declines more steeply than upper trend line (resistance)
- Volume typically decreases as pattern develops (selling pressure diminishes)
- Breakout occurs above resistance line with volume expansion
- Bullish reversal pattern indicating accumulation phase

Smallcaps Focus:
- Price range: $1-$15 (optimal for smallcaps)
- Volume requirements adjusted for smaller float
- Faster pattern development (5-90 minutes vs daily charts)
- Higher breakout percentage thresholds due to volatility

Hybrid Approach:
- Static Rules: Pattern validation, basic filters
- Flexible Scoring: 0-500 points for signal quality
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import math

from core.interfaces import MarketData, Signal, SignalType, Position
from .base import BaseStrategy

logger = logging.getLogger(__name__)

class FallingWedgeStrategy(BaseStrategy):
    """
    Falling Wedge Pattern Strategy for Smallcaps Intraday Trading

    Pattern Detection:
    1. Minimum 4-6 swing points (2-3 highs, 2-3 lows)
    2. Converging trend lines both sloping downward
    3. Support line steeper than resistance line
    4. Volume decline during pattern formation
    5. Breakout above resistance with volume confirmation

    Scoring Components (500 points total):
    - Pattern Quality: 150 points (convergence, slope angles, swing point quality)
    - Volume Profile: 120 points (volume decline during formation, breakout volume)
    - Breakout Strength: 130 points (breakout distance, momentum, follow-through)
    - Market Context: 70 points (trend, sector strength, market conditions)
    - Timing Factors: 30 points (optimal trading hours, pattern maturity)
    """

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.strategy_name = "falling_wedge"

        # Pattern tracking per symbol
        self.pattern_state = {}  # 'none', 'forming', 'mature', 'breakout'
        self.wedge_data = {}     # Pattern formation data
        self.swing_points = {}   # High/low swing points
        self.trend_lines = {}    # Support/resistance lines
        self.volume_profile = {} # Volume analysis

        # Performance tracking
        self.pattern_count = 0
        self.successful_breakouts = 0
        self.false_breakouts = 0

        logger.info(f"✅ Falling Wedge Strategy initialized for smallcaps intraday")

    def _get_default_parameters(self) -> Dict[str, Any]:
        """Default parameters optimized for smallcaps falling wedge patterns"""
        return {
            # === BASIC FILTERS ===
            'min_price': 1.0,          # Minimum price for smallcaps
            'max_price': 15.0,         # Maximum price for smallcaps
            'min_volume': 50000,       # Minimum daily volume for liquidity
            'max_float': 50000000,     # Maximum float (50M shares) for smallcaps
            'min_market_cap': 10000000,    # $10M minimum market cap
            'max_market_cap': 2000000000,  # $2B maximum for smallcaps

            # === PATTERN FORMATION ===
            'min_swing_points': 4,     # Minimum swing points (2 highs, 2 lows)
            'max_swing_points': 8,     # Maximum swing points to avoid complexity
            'min_pattern_duration': 15,    # Minimum 15 minutes for pattern
            'max_pattern_duration': 120,   # Maximum 2 hours intraday
            'swing_detection_window': 5,   # Bars to confirm swing point
            'min_swing_distance': 0.8,     # Minimum 0.8% between swing points

            # === TREND LINE REQUIREMENTS ===
            'min_convergence_angle': 5.0,     # Minimum 5 degrees convergence
            'max_convergence_angle': 45.0,    # Maximum 45 degrees convergence
            'support_slope_min': -15.0,       # Support line must slope down (negative)
            'support_slope_max': -2.0,        # But not too steep
            'resistance_slope_min': -8.0,     # Resistance slopes down less steeply
            'resistance_slope_max': -0.5,     # Slight downward slope
            'min_trend_line_touches': 2,      # Minimum touches per trend line
            'trend_line_tolerance': 0.5,      # 0.5% tolerance for trend line touches

            # === VOLUME REQUIREMENTS ===
            'volume_decline_ratio': 0.75,     # Volume should decline to 75% during formation
            'breakout_volume_multiplier': 1.8, # 1.8x average volume for breakout
            'min_volume_consistency': 3,       # Minimum bars showing volume decline
            'volume_spike_threshold': 2.5,     # 2.5x volume for strong breakouts

            # === BREAKOUT VALIDATION ===
            'breakout_threshold': 0.4,        # 0.4% above resistance for breakout
            'breakout_confirmation_bars': 2,   # Bars to confirm breakout
            'false_breakout_threshold': 0.8,   # 0.8% pullback = false breakout
            'min_breakout_momentum': 1.5,      # Minimum momentum after breakout
            'breakout_follow_through': 0.6,    # 0.6% follow-through required

            # === TIMING CONSTRAINTS ===
            'entry_start_time': 9.5,          # 9:30 AM earliest entry
            'entry_end_time': 15.5,           # 3:30 PM latest entry
            'pattern_maturity_min': 20,       # 20 minutes minimum before breakout
            'optimal_breakout_window': 60,    # 1 hour optimal breakout timing

            # === MARKET CONDITIONS ===
            'min_relative_volume': 1.2,       # 1.2x average volume
            'max_daily_decline': -8.0,        # Max 8% daily decline allowed
            'sector_correlation_threshold': 0.3, # Sector correlation factor
            'market_volatility_max': 25.0,    # Maximum VIX for entries

            # === RISK MANAGEMENT ===
            'stop_loss_percent': 3.5,         # 3.5% stop loss for smallcaps
            'profit_target_1': 4.5,           # 4.5% first profit target
            'profit_target_2': 8.0,           # 8.0% extended target
            'risk_reward_ratio': 1.3,         # Minimum 1.3:1 R/R
            'max_position_size': 0.05,        # 5% max position of portfolio
            'partial_profit_percent': 60,     # Take 60% profit at target 1

            # === SCORING WEIGHTS ===
            'pattern_quality_weight': 150,    # Pattern formation quality
            'volume_profile_weight': 120,     # Volume characteristics
            'breakout_strength_weight': 130,  # Breakout power and follow-through
            'market_context_weight': 70,      # Market and sector conditions
            'timing_weight': 30,              # Optimal timing factors

            # === SIGNAL THRESHOLDS ===
            'min_signal_score': 280,          # Minimum 280/500 points for signal
            'high_confidence_score': 380,     # High confidence threshold
            'max_signals_per_day': 8,         # Maximum signals per day
            'cooldown_period': 45,            # 45 minutes between signals same symbol
        }

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Main analysis method for falling wedge pattern detection

        Process:
        1. Update pattern state tracking
        2. Detect and validate swing points
        3. Calculate trend lines and convergence
        4. Analyze volume characteristics
        5. Detect breakout conditions
        6. Calculate signal confidence score
        """
        try:
            symbol = bar.symbol

            # Initialize tracking for new symbol
            if symbol not in self.pattern_state:
                self._initialize_symbol_tracking(symbol)

            # Update bars history
            if symbol not in self.bars_history:
                self.bars_history[symbol] = []
            self.bars_history[symbol].append(bar)

            # Keep reasonable history (3 hours of 1-min bars)
            if len(self.bars_history[symbol]) > 180:
                self.bars_history[symbol] = self.bars_history[symbol][-180:]

            # Need minimum bars for pattern analysis
            if len(self.bars_history[symbol]) < self._parameters['min_pattern_duration']:
                return None

            # Apply basic filters
            if not self._passes_basic_filters(bar):
                return None

            # Check trading time window
            if not self._is_trading_time(bar.timestamp):
                return None

            # Update swing points detection
            self._update_swing_points(symbol)

            # Update pattern state
            self._update_pattern_state(symbol)

            # Check for breakout signal
            signal = await self._check_breakout_signal(bar)

            if signal:
                logger.info(f"🔺 Falling Wedge signal generated for {symbol}: {signal.confidence:.1f}%")
                self.pattern_count += 1

            return signal

        except Exception as e:
            logger.error(f"❌ Error analyzing bar for {bar.symbol}: {e}")
            return None

    def _initialize_symbol_tracking(self, symbol: str):
        """Initialize pattern tracking data structures for symbol"""
        self.pattern_state[symbol] = 'none'
        self.wedge_data[symbol] = {
            'formation_start': None,
            'formation_bars': 0,
            'convergence_point': None,
            'pattern_width': 0.0,
            'volume_trend': []
        }
        self.swing_points[symbol] = {
            'highs': [],  # (timestamp, price, bar_index)
            'lows': [],   # (timestamp, price, bar_index)
            'last_high_idx': -1,
            'last_low_idx': -1
        }
        self.trend_lines[symbol] = {
            'support': {'slope': 0, 'intercept': 0, 'touches': 0, 'quality': 0},
            'resistance': {'slope': 0, 'intercept': 0, 'touches': 0, 'quality': 0},
            'convergence_angle': 0,
            'convergence_distance': 0
        }
        self.volume_profile[symbol] = {
            'formation_avg_volume': 0,
            'recent_volume_trend': [],
            'volume_decline_confirmed': False,
            'breakout_volume_ready': False
        }

    def _passes_basic_filters(self, bar: MarketData) -> bool:
        """Apply basic filters for falling wedge candidates"""
        # Price range filter for smallcaps
        if not (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
            return False

        # Volume filter
        if bar.volume < self._parameters['min_volume'] * 0.1:  # 10% of daily minimum
            return False

        # Basic liquidity check
        dollar_volume = bar.close * bar.volume
        if dollar_volume < 25000:  # Minimum $25K bar volume
            return False

        return True

    def _is_trading_time(self, timestamp: datetime) -> bool:
        """Check if within trading time window"""
        hour = timestamp.hour + timestamp.minute / 60.0
        return self._parameters['entry_start_time'] <= hour <= self._parameters['entry_end_time']

    def _update_swing_points(self, symbol: str):
        """Update swing point detection for falling wedge pattern"""
        bars = self.bars_history[symbol]
        if len(bars) < self._parameters['swing_detection_window'] * 2:
            return

        swing_window = self._parameters['swing_detection_window']
        min_distance = self._parameters['min_swing_distance'] / 100.0

        # Detect new swing highs
        for i in range(swing_window, len(bars) - swing_window):
            current_bar = bars[i]

            # Check for swing high (local maximum)
            is_swing_high = True
            for j in range(i - swing_window, i + swing_window + 1):
                if j != i and bars[j].high >= current_bar.high:
                    is_swing_high = False
                    break

            if is_swing_high and i > self.swing_points[symbol]['last_high_idx']:
                # Verify minimum distance from last swing high
                if (not self.swing_points[symbol]['highs'] or
                    abs(current_bar.high - self.swing_points[symbol]['highs'][-1][1]) /
                    self.swing_points[symbol]['highs'][-1][1] >= min_distance):

                    self.swing_points[symbol]['highs'].append(
                        (current_bar.timestamp, current_bar.high, i)
                    )
                    self.swing_points[symbol]['last_high_idx'] = i

        # Detect new swing lows
        for i in range(swing_window, len(bars) - swing_window):
            current_bar = bars[i]

            # Check for swing low (local minimum)
            is_swing_low = True
            for j in range(i - swing_window, i + swing_window + 1):
                if j != i and bars[j].low <= current_bar.low:
                    is_swing_low = False
                    break

            if is_swing_low and i > self.swing_points[symbol]['last_low_idx']:
                # Verify minimum distance from last swing low
                if (not self.swing_points[symbol]['lows'] or
                    abs(current_bar.low - self.swing_points[symbol]['lows'][-1][1]) /
                    current_bar.low >= min_distance):

                    self.swing_points[symbol]['lows'].append(
                        (current_bar.timestamp, current_bar.low, i)
                    )
                    self.swing_points[symbol]['last_low_idx'] = i

        # Keep reasonable number of swing points
        max_points = self._parameters['max_swing_points'] // 2
        if len(self.swing_points[symbol]['highs']) > max_points:
            self.swing_points[symbol]['highs'] = self.swing_points[symbol]['highs'][-max_points:]
        if len(self.swing_points[symbol]['lows']) > max_points:
            self.swing_points[symbol]['lows'] = self.swing_points[symbol]['lows'][-max_points:]

    def _update_pattern_state(self, symbol: str):
        """Update falling wedge pattern formation state"""
        highs = self.swing_points[symbol]['highs']
        lows = self.swing_points[symbol]['lows']
        min_points = self._parameters['min_swing_points']

        # Need minimum swing points for pattern
        if len(highs) < min_points // 2 or len(lows) < min_points // 2:
            self.pattern_state[symbol] = 'none'
            return

        # Calculate trend lines
        self._calculate_trend_lines(symbol)

        # Check pattern formation criteria
        if self._validate_wedge_pattern(symbol):
            bars_in_pattern = len(self.bars_history[symbol])
            pattern_duration = self._parameters['pattern_maturity_min']

            if bars_in_pattern >= pattern_duration:
                if self.pattern_state[symbol] != 'mature':
                    self.pattern_state[symbol] = 'mature'
                    self.wedge_data[symbol]['formation_start'] = self.bars_history[symbol][0].timestamp
                    logger.debug(f"📐 Falling wedge pattern mature for {symbol}")
            else:
                self.pattern_state[symbol] = 'forming'
        else:
            self.pattern_state[symbol] = 'none'

    def _calculate_trend_lines(self, symbol: str):
        """Calculate support and resistance trend lines for wedge pattern"""
        highs = self.swing_points[symbol]['highs']
        lows = self.swing_points[symbol]['lows']

        if len(highs) < 2 or len(lows) < 2:
            return

        # Calculate resistance line (connecting swing highs)
        try:
            high_times = [h[2] for h in highs[-4:]]  # Use last 4 highs max
            high_prices = [h[1] for h in highs[-4:]]

            if len(high_times) >= 2:
                resistance_slope, resistance_intercept = np.polyfit(high_times, high_prices, 1)

                # Count touches to resistance line
                resistance_touches = 0
                tolerance = self._parameters['trend_line_tolerance'] / 100.0

                for i, price in enumerate(high_prices):
                    predicted_price = resistance_slope * high_times[i] + resistance_intercept
                    if abs(price - predicted_price) / price <= tolerance:
                        resistance_touches += 1

                self.trend_lines[symbol]['resistance'] = {
                    'slope': resistance_slope,
                    'intercept': resistance_intercept,
                    'touches': resistance_touches,
                    'quality': min(resistance_touches * 25, 100)  # Quality score 0-100
                }
        except Exception as e:
            logger.debug(f"Error calculating resistance line for {symbol}: {e}")

        # Calculate support line (connecting swing lows)
        try:
            low_times = [l[2] for l in lows[-4:]]  # Use last 4 lows max
            low_prices = [l[1] for l in lows[-4:]]

            if len(low_times) >= 2:
                support_slope, support_intercept = np.polyfit(low_times, low_prices, 1)

                # Count touches to support line
                support_touches = 0
                tolerance = self._parameters['trend_line_tolerance'] / 100.0

                for i, price in enumerate(low_prices):
                    predicted_price = support_slope * low_times[i] + support_intercept
                    if abs(price - predicted_price) / price <= tolerance:
                        support_touches += 1

                self.trend_lines[symbol]['support'] = {
                    'slope': support_slope,
                    'intercept': support_intercept,
                    'touches': support_touches,
                    'quality': min(support_touches * 25, 100)  # Quality score 0-100
                }

                # Calculate convergence angle
                if self.trend_lines[symbol]['resistance']['slope'] != 0:
                    resistance_angle = math.degrees(math.atan(self.trend_lines[symbol]['resistance']['slope']))
                    support_angle = math.degrees(math.atan(support_slope))
                    self.trend_lines[symbol]['convergence_angle'] = abs(resistance_angle - support_angle)

        except Exception as e:
            logger.debug(f"Error calculating support line for {symbol}: {e}")

    def _validate_wedge_pattern(self, symbol: str) -> bool:
        """Validate if current formation is a valid falling wedge pattern"""
        support = self.trend_lines[symbol]['support']
        resistance = self.trend_lines[symbol]['resistance']

        # Check if we have valid trend lines
        if (support['touches'] < self._parameters['min_trend_line_touches'] or
            resistance['touches'] < self._parameters['min_trend_line_touches']):
            return False

        # Check slope requirements for falling wedge
        # Support line should slope down more steeply than resistance line
        if not (self._parameters['support_slope_min'] <= support['slope'] <= self._parameters['support_slope_max']):
            return False

        if not (self._parameters['resistance_slope_min'] <= resistance['slope'] <= self._parameters['resistance_slope_max']):
            return False

        # Support should be steeper (more negative) than resistance
        if support['slope'] >= resistance['slope']:
            return False

        # Check convergence angle
        convergence_angle = self.trend_lines[symbol]['convergence_angle']
        if not (self._parameters['min_convergence_angle'] <= convergence_angle <= self._parameters['max_convergence_angle']):
            return False

        # Volume validation - should be declining during formation
        self._update_volume_profile(symbol)
        if not self.volume_profile[symbol]['volume_decline_confirmed']:
            return False

        return True

    def _update_volume_profile(self, symbol: str):
        """Update volume characteristics during wedge formation"""
        bars = self.bars_history[symbol]
        if len(bars) < 10:  # Need minimum history
            return

        # Calculate average volume over formation period
        recent_volumes = [bar.volume for bar in bars[-20:]]  # Last 20 bars
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        self.volume_profile[symbol]['formation_avg_volume'] = avg_volume

        # Check volume decline trend
        if len(recent_volumes) >= 10:
            first_half_avg = sum(recent_volumes[:10]) / 10
            second_half_avg = sum(recent_volumes[10:]) / len(recent_volumes[10:])

            volume_decline_ratio = second_half_avg / first_half_avg if first_half_avg > 0 else 1.0

            # Volume should decline during wedge formation (bullish sign)
            if volume_decline_ratio <= self._parameters['volume_decline_ratio']:
                self.volume_profile[symbol]['volume_decline_confirmed'] = True
            else:
                self.volume_profile[symbol]['volume_decline_confirmed'] = False

        # Track recent volume trend
        self.volume_profile[symbol]['recent_volume_trend'] = recent_volumes[-5:]  # Last 5 bars

    async def _check_breakout_signal(self, bar: MarketData) -> Optional[Signal]:
        """Check for falling wedge breakout signal"""
        symbol = bar.symbol

        # Only generate signals for mature patterns
        if self.pattern_state[symbol] != 'mature':
            return None

        # Check if price is breaking above resistance line
        resistance = self.trend_lines[symbol]['resistance']
        if resistance['slope'] == 0:  # No valid resistance line
            return None

        # Calculate current resistance level
        bars = self.bars_history[symbol]
        current_bar_index = len(bars) - 1
        resistance_price = resistance['slope'] * current_bar_index + resistance['intercept']

        # Check for breakout above resistance
        breakout_threshold = resistance_price * (1 + self._parameters['breakout_threshold'] / 100.0)

        if bar.close <= breakout_threshold:
            return None  # No breakout yet

        # Validate breakout with volume
        recent_volume_avg = self.volume_profile[symbol]['formation_avg_volume']
        volume_multiplier = bar.volume / recent_volume_avg if recent_volume_avg > 0 else 1.0

        if volume_multiplier < self._parameters['breakout_volume_multiplier']:
            return None  # Insufficient volume for breakout

        # Calculate signal confidence score
        confidence_score = self._calculate_signal_confidence(symbol, bar, volume_multiplier)

        if confidence_score < self._parameters['min_signal_score']:
            return None  # Signal not strong enough

        # Create signal
        signal = self._create_breakout_signal(bar, confidence_score, resistance_price)

        # Update pattern state
        self.pattern_state[symbol] = 'breakout'
        self.successful_breakouts += 1

        return signal

    def _calculate_signal_confidence(self, symbol: str, bar: MarketData, volume_multiplier: float) -> float:
        """
        Calculate confidence score for falling wedge breakout signal
        Total possible: 500 points

        Pattern Quality (150 points):
        - Trend line quality and touches
        - Convergence angle optimization
        - Pattern duration and maturity

        Volume Profile (120 points):
        - Volume decline during formation
        - Breakout volume expansion
        - Volume consistency

        Breakout Strength (130 points):
        - Breakout distance above resistance
        - Price momentum and follow-through
        - Gap strength if present

        Market Context (70 points):
        - Overall market condition
        - Sector performance
        - Time of day factors

        Timing Factors (30 points):
        - Optimal breakout timing
        - Pattern maturity
        """
        total_score = 0.0

        # === PATTERN QUALITY SCORING (150 points) ===
        pattern_score = 0.0

        # Trend line quality (60 points)
        support_quality = self.trend_lines[symbol]['support']['quality']
        resistance_quality = self.trend_lines[symbol]['resistance']['quality']
        pattern_score += (support_quality + resistance_quality) * 0.3  # Max 60 points

        # Convergence angle optimization (45 points)
        convergence_angle = self.trend_lines[symbol]['convergence_angle']
        optimal_angle = 15.0  # 15 degrees is optimal for wedges
        angle_score = max(0, 45 - abs(convergence_angle - optimal_angle) * 2)
        pattern_score += angle_score

        # Pattern maturity (45 points)
        bars_in_pattern = len(self.bars_history[symbol])
        optimal_duration = 45  # 45 minutes optimal
        if bars_in_pattern >= optimal_duration:
            maturity_score = 45
        else:
            maturity_score = (bars_in_pattern / optimal_duration) * 45
        pattern_score += maturity_score

        total_score += min(pattern_score, 150)

        # === VOLUME PROFILE SCORING (120 points) ===
        volume_score = 0.0

        # Volume decline confirmation (50 points)
        if self.volume_profile[symbol]['volume_decline_confirmed']:
            volume_score += 50

        # Breakout volume strength (50 points)
        volume_strength = min(volume_multiplier / self._parameters['breakout_volume_multiplier'], 2.0)
        volume_score += volume_strength * 25  # Max 50 points

        # Volume spike bonus (20 points)
        if volume_multiplier >= self._parameters['volume_spike_threshold']:
            volume_score += 20

        total_score += min(volume_score, 120)

        # === BREAKOUT STRENGTH SCORING (130 points) ===
        breakout_score = 0.0

        # Breakout distance (60 points)
        resistance = self.trend_lines[symbol]['resistance']
        bars = self.bars_history[symbol]
        current_bar_index = len(bars) - 1
        resistance_price = resistance['slope'] * current_bar_index + resistance['intercept']

        breakout_distance_percent = ((bar.close - resistance_price) / resistance_price) * 100
        breakout_score += min(breakout_distance_percent * 15, 60)  # Max 60 at 4% breakout

        # Price momentum (40 points)
        if len(bars) >= 3:
            recent_momentum = ((bar.close - bars[-3].close) / bars[-3].close) * 100
            momentum_score = min(abs(recent_momentum) * 10, 40)
            breakout_score += momentum_score

        # Follow-through potential (30 points)
        bars_above_resistance = sum(1 for b in bars[-5:] if b.close > resistance_price * 0.995)
        followthrough_score = min(bars_above_resistance * 6, 30)
        breakout_score += followthrough_score

        total_score += min(breakout_score, 130)

        # === MARKET CONTEXT SCORING (70 points) ===
        market_score = 0.0

        # Time of day bonus (25 points)
        hour = bar.timestamp.hour + bar.timestamp.minute / 60.0
        if 10.0 <= hour <= 11.5 or 14.0 <= hour <= 15.5:  # Optimal momentum hours
            market_score += 25
        elif 9.5 <= hour <= 15.5:  # Trading hours
            market_score += 15

        # Relative volume (25 points)
        daily_volume_estimate = sum(b.volume for b in bars) * (390 / len(bars)) if bars else 0
        if daily_volume_estimate >= self._parameters['min_volume']:
            relative_vol_score = min(25, (daily_volume_estimate / self._parameters['min_volume']) * 10)
            market_score += relative_vol_score

        # Price action context (20 points)
        if len(bars) >= 20:
            daily_range = max(b.high for b in bars) - min(b.low for b in bars)
            range_percent = (daily_range / bars[0].open) * 100
            if 2.0 <= range_percent <= 12.0:  # Healthy range for smallcaps
                market_score += 20
            else:
                market_score += 10

        total_score += min(market_score, 70)

        # === TIMING FACTORS SCORING (30 points) ===
        timing_score = 0.0

        # Pattern timing (20 points)
        pattern_duration = len(bars)
        if self._parameters['pattern_maturity_min'] <= pattern_duration <= self._parameters['optimal_breakout_window']:
            timing_score += 20
        else:
            timing_score += 10

        # Breakout timing (10 points)
        if 10.5 <= hour <= 11.0 or 14.5 <= hour <= 15.0:  # Peak momentum times
            timing_score += 10
        elif 10.0 <= hour <= 15.5:
            timing_score += 6

        total_score += min(timing_score, 30)

        # Final confidence score (0-500 points)
        final_score = min(total_score, 500)

        logger.debug(f"📊 Falling Wedge confidence for {symbol}: {final_score:.1f}/500 "
                    f"(Pattern: {min(pattern_score, 150):.0f}, Volume: {min(volume_score, 120):.0f}, "
                    f"Breakout: {min(breakout_score, 130):.0f}, Market: {min(market_score, 70):.0f}, "
                    f"Timing: {min(timing_score, 30):.0f})")

        return final_score

    def _create_breakout_signal(self, bar: MarketData, confidence_score: float, resistance_price: float) -> Signal:
        """Create falling wedge breakout signal with risk management"""

        # Calculate position sizing
        stop_loss_percent = self._parameters['stop_loss_percent'] / 100.0
        profit_target_1_percent = self._parameters['profit_target_1'] / 100.0
        profit_target_2_percent = self._parameters['profit_target_2'] / 100.0

        # Entry price (slightly above current price for confirmation)
        entry_price = bar.close * 1.002  # 0.2% above current price

        # Risk management levels
        stop_loss_price = entry_price * (1 - stop_loss_percent)
        profit_target_1 = entry_price * (1 + profit_target_1_percent)
        profit_target_2 = entry_price * (1 + profit_target_2_percent)

        # Signal metadata
        metadata = {
            'strategy': 'falling_wedge',
            'pattern': 'falling_wedge_breakout',
            'resistance_level': resistance_price,
            'breakout_distance': ((bar.close - resistance_price) / resistance_price) * 100,
            'convergence_angle': self.trend_lines[bar.symbol]['convergence_angle'],
            'support_touches': self.trend_lines[bar.symbol]['support']['touches'],
            'resistance_touches': self.trend_lines[bar.symbol]['resistance']['touches'],
            'volume_multiplier': bar.volume / self.volume_profile[bar.symbol]['formation_avg_volume'],
            'pattern_duration_minutes': len(self.bars_history[bar.symbol]),
            'confidence_components': {
                'pattern_quality': f"{min(150, confidence_score * 0.3):.0f}/150",
                'volume_profile': f"{min(120, confidence_score * 0.24):.0f}/120",
                'breakout_strength': f"{min(130, confidence_score * 0.26):.0f}/130",
                'market_context': f"{min(70, confidence_score * 0.14):.0f}/70",
                'timing_factors': f"{min(30, confidence_score * 0.06):.0f}/30"
            },
            'risk_management': {
                'stop_loss': stop_loss_price,
                'profit_target_1': profit_target_1,
                'profit_target_2': profit_target_2,
                'risk_reward_ratio': (profit_target_1 - entry_price) / (entry_price - stop_loss_price)
            }
        }

        # Create signal
        signal = Signal(
            symbol=bar.symbol,
            signal_type=SignalType.BUY,
            confidence=confidence_score / 500.0,  # Convert to 0-1 scale
            entry_price=entry_price,
            stop_loss=stop_loss_price,
            profit_target=profit_target_1,
            metadata=metadata,
            timestamp=bar.timestamp,
            strategy_name="falling_wedge"
        )

        return signal

    async def cleanup(self):
        """Cleanup method for strategy"""
        logger.info(f"🧹 Falling Wedge Strategy cleanup")
        logger.info(f"📊 Patterns detected: {self.pattern_count}")
        logger.info(f"✅ Successful breakouts: {self.successful_breakouts}")
        logger.info(f"❌ False breakouts: {self.false_breakouts}")

        # Clear tracking data
        self.pattern_state.clear()
        self.wedge_data.clear()
        self.swing_points.clear()
        self.trend_lines.clear()
        self.volume_profile.clear()

    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For falling wedge strategy, we don't need special logic on position updates
        # Position management is handled by the main strategy logic and risk management
        return None

    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited based on falling wedge conditions"""
        try:
            symbol = position.symbol
            current_price = current_bar.close

            # Basic exit conditions for falling wedge breakouts

            # 1. Stop loss check (below support line or pattern low)
            if hasattr(position, 'metadata') and position.metadata:
                stop_loss_price = position.metadata.get('stop_loss')
                if stop_loss_price and current_price <= stop_loss_price:
                    return Signal(
                        signal_id=f"FallingWedge-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="falling_wedge",
                        metadata={
                            'exit_reason': 'stop_loss',
                            'stop_loss_price': stop_loss_price,
                            'entry_price': position.avg_price
                        }
                    )

            # 2. Profit target check (based on wedge height projection)
            profit_target_1_pct = self._parameters.get('profit_target_1', 4.5) / 100.0  # 4.5% default
            profit_target_2_pct = self._parameters.get('profit_target_2', 8.0) / 100.0  # 8.0% default

            target_price_1 = position.avg_price * (1 + profit_target_1_pct)
            target_price_2 = position.avg_price * (1 + profit_target_2_pct)

            # Check first profit target
            if current_price >= target_price_1:
                # Check if we should take partial profits or full exit
                partial_profit_percent = self._parameters.get('partial_profit_percent', 60)

                if current_price >= target_price_2:
                    # Full exit at second target
                    return Signal(
                        signal_id=f"FallingWedge-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="falling_wedge",
                        metadata={
                            'exit_reason': 'profit_target_2',
                            'target_price': target_price_2,
                            'entry_price': position.avg_price,
                            'profit_pct': ((current_price - position.avg_price) / position.avg_price) * 100
                        }
                    )
                else:
                    # Partial exit at first target (if not already done)
                    return Signal(
                        signal_id=f"FallingWedge-PARTIAL-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.6,  # Partial exit strength
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="falling_wedge",
                        metadata={
                            'exit_reason': 'profit_target_1_partial',
                            'target_price': target_price_1,
                            'entry_price': position.avg_price,
                            'profit_pct': ((current_price - position.avg_price) / position.avg_price) * 100,
                            'partial_percent': partial_profit_percent
                        }
                    )

            # 3. Failed breakout (price returns below resistance)
            if hasattr(position, 'metadata') and position.metadata:
                resistance_level = position.metadata.get('resistance_level')
                if resistance_level and current_price < resistance_level * 0.98:  # 2% below resistance
                    return Signal(
                        signal_id=f"FallingWedge-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="falling_wedge",
                        metadata={
                            'exit_reason': 'failed_breakout',
                            'resistance_level': resistance_level,
                            'entry_price': position.avg_price
                        }
                    )

            # 4. Time-based exit (maximum hold time)
            if hasattr(position, 'entry_time') and position.entry_time:
                hold_time = (current_bar.timestamp - position.entry_time).total_seconds() / 60
                max_hold_minutes = 240  # 4 hours default for falling wedge (longer than other patterns)

                if hold_time > max_hold_minutes:
                    return Signal(
                        signal_id=f"FallingWedge-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.8,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="falling_wedge",
                        metadata={
                            'exit_reason': 'time_limit',
                            'hold_time_minutes': hold_time,
                            'entry_price': position.avg_price
                        }
                    )

            # 5. Volume-based exit (if volume dries up significantly after breakout)
            if symbol in self.volume_profile and hasattr(position, 'entry_time'):
                recent_bars = self.bars_history.get(symbol, [])[-5:]  # Last 5 bars
                if len(recent_bars) >= 3:
                    recent_avg_volume = sum(bar.volume for bar in recent_bars) / len(recent_bars)
                    formation_avg_volume = self.volume_profile[symbol].get('formation_avg_volume', recent_avg_volume)

                    # If volume drops to 30% of formation average, consider exit
                    if formation_avg_volume > 0 and recent_avg_volume / formation_avg_volume < 0.3:
                        return Signal(
                            signal_id=f"FallingWedge-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=0.7,
                            price=current_price,
                            timestamp=current_bar.timestamp,
                            strategy_name="falling_wedge",
                            metadata={
                                'exit_reason': 'volume_exhaustion',
                                'volume_ratio': recent_avg_volume / formation_avg_volume,
                                'entry_price': position.avg_price
                            }
                        )

            # No exit signal
            return None

        except Exception as e:
            logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None