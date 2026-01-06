#!/usr/bin/env python3
"""
Ascending Triangle Strategy - Smallcaps Intraday
Specialized for bullish breakout patterns with hybrid static/scoring approach

Pattern Focus: Only Ascending Triangles
- Horizontal resistance (multiple touches)
- Ascending support line (higher lows)
- Volume contraction during formation
- Explosive breakout on increased volume

Target: Smallcaps ($1-$15) with high volatility potential
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from core.interfaces import MarketData, Signal, SignalType, Position
from .base import BaseStrategy


class AscendingTriangleStrategy(BaseStrategy):
    """
    Ascending Triangle Strategy - Pure bullish breakout focus

    Static Rules (Hard Requirements):
    - Minimum 3 touches on horizontal resistance
    - Minimum 3 higher lows forming ascending support
    - Formation time: 15-120 minutes
    - Price range: $1-$15 (smallcaps)
    - Volume contraction during formation

    Flexible Scoring (0-500 points):
    - Pattern Quality (0-100): Line precision and touch quality
    - Volume Profile (0-100): Contraction + breakout confirmation
    - Breakout Strength (0-150): Distance and momentum of break
    - Market Context (0-75): Overall trend and sector strength
    - Timing Score (0-75): Time of day optimization
    """

    def __init__(self, parameters: Dict = None):
        """Initialize Ascending Triangle Strategy"""
        super().__init__("AscendingTriangle", parameters)

        # Initialize pattern detection data
        self.swing_points = {}  # {symbol: {'highs': [], 'lows': []}}
        self.resistance_levels = {}  # {symbol: price_level}
        self.support_lines = {}  # {symbol: {'slope': float, 'intercept': float}}
        self.formation_start = {}  # {symbol: timestamp}

        self.logger = logging.getLogger(__name__)
        self.logger.info("🔺 Ascending Triangle Strategy initialized - Smallcaps bullish breakouts")

    def _get_default_parameters(self) -> Dict:
        """Default parameters optimized for smallcaps ascending triangles"""
        return {
            # === STATIC REQUIREMENTS (Hard Filters) ===
            'min_resistance_touches': 3,      # Minimum touches on horizontal line
            'min_support_touches': 3,         # Minimum higher lows for ascending line
            'min_formation_minutes': 15,      # Minimum time to form pattern
            'max_formation_minutes': 120,     # Maximum time (2 hours max)
            'min_price': 1.0,                 # Smallcaps minimum
            'max_price': 15.0,                # Smallcaps maximum
            'min_daily_volume': 50000,        # Minimum liquidity
            'max_resistance_variance': 0.02,  # 2% variance allowed in resistance
            'min_ascending_slope': 0.001,     # Support must be clearly ascending

            # === FLEXIBLE SCORING THRESHOLDS ===
            'min_triangle_score': 300,        # Minimum total score (300/500 = 60%)
            'good_triangle_score': 375,       # Good setup (375/500 = 75%)
            'excellent_triangle_score': 450,  # Excellent setup (450/500 = 90%)

            # === SCORING WEIGHTS ===
            'pattern_quality_weight': 100,    # Pattern precision and clarity
            'volume_profile_weight': 100,     # Volume contraction + breakout
            'breakout_strength_weight': 150,  # Most important: breakout quality
            'market_context_weight': 75,      # Market/sector conditions
            'timing_weight': 75,              # Time of day optimization

            # === BREAKOUT DETECTION ===
            'breakout_threshold_pct': 0.5,    # 0.5% above resistance for confirmation
            'breakout_volume_multiplier': 1.5, # 1.5x average volume for confirmation
            'false_breakout_retest_pct': 0.3, # If drops 0.3% below resistance = false

            # === RISK MANAGEMENT ===
            'stop_loss_pct': 0.04,           # 4% stop loss (tight for triangles)
            'take_profit_pct': 0.12,         # 12% take profit (3:1 R/R)
            'breakeven_move_pct': 0.06,      # Move to breakeven at 6%
            'max_hold_minutes': 180,         # 3 hours maximum hold

            # === TIMING OPTIMIZATION ===
            'optimal_start_hour': 10.0,      # Best formation start (10 AM)
            'optimal_end_hour': 15.0,        # Best breakout time (3 PM)
            'avoid_lunch_hour': True,        # Avoid 12-1 PM breakouts

            # === ENTRY/EXIT ===
            'entry_mode': 'breakout_confirmation', # Wait for confirmed breakout
            'min_confidence_threshold': 0.65,     # Minimum signal confidence
            'position_sizing_mode': 'risk_based', # Size based on stop distance
        }

    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Analyze current bar for ascending triangle patterns and breakouts

        Process:
        1. Update swing point detection
        2. Check if ascending triangle is forming
        3. Detect breakout if pattern exists
        4. Score the setup using hybrid approach
        5. Generate signal if thresholds met
        """
        try:
            symbol = bar.symbol

            # Ensure we have enough history
            if not self._has_sufficient_history(symbol, min_bars=20):
                return None

            # Update swing points for pattern detection
            self._update_swing_points(symbol, bar)

            # Check if we have an ascending triangle forming
            triangle_data = self._detect_ascending_triangle(symbol, bar)
            if not triangle_data:
                return None

            # Check for breakout if triangle exists
            breakout_data = self._detect_breakout(symbol, bar, triangle_data)
            if not breakout_data:
                return None

            # Apply static filters (hard requirements)
            if not self._passes_static_filters(symbol, bar, triangle_data, breakout_data):
                return None

            # Calculate flexible scoring
            scores = self._calculate_triangle_scores(symbol, bar, triangle_data, breakout_data)
            total_score = sum(scores.values())

            # Check scoring thresholds
            min_score = self._parameters['min_triangle_score']
            if total_score < min_score:
                self.logger.debug(f"🔺 {symbol}: Triangle score {total_score:.0f} below threshold {min_score}")
                return None

            # Determine signal strength based on score
            signal_strength = self._calculate_signal_strength(total_score)

            # Generate ascending triangle breakout signal
            signal = self._create_triangle_signal(symbol, bar, triangle_data, breakout_data, scores, signal_strength)

            self.logger.info(f"🔺 {symbol}: ASCENDING TRIANGLE BREAKOUT! Score: {total_score:.0f}/500, "
                           f"Resistance: ${triangle_data['resistance']:.2f}, "
                           f"Breakout: ${bar.close:.2f} (+{breakout_data['breakout_pct']:.1f}%)")

            return signal

        except Exception as e:
            self.logger.error(f"Error analyzing ascending triangle for {symbol}: {e}")
            return None

    def _update_swing_points(self, symbol: str, bar: MarketData) -> None:
        """Update swing highs and lows for pattern detection"""
        if symbol not in self.swing_points:
            self.swing_points[symbol] = {'highs': [], 'lows': []}

        # Get recent bars for swing detection
        recent_bars = self.bars_history[symbol][-20:]  # Last 20 bars
        if len(recent_bars) < 5:
            return

        # Detect swing highs and lows (simplified pivot detection)
        for i in range(2, len(recent_bars) - 2):
            current = recent_bars[i]

            # Swing high detection
            if (current.high > recent_bars[i-1].high and
                current.high > recent_bars[i-2].high and
                current.high > recent_bars[i+1].high and
                current.high > recent_bars[i+2].high):

                swing_high = {
                    'price': current.high,
                    'timestamp': current.timestamp,
                    'bar_index': len(self.bars_history[symbol]) - len(recent_bars) + i
                }
                self.swing_points[symbol]['highs'].append(swing_high)

                # Keep only recent swing points (last 2 hours)
                cutoff_time = bar.timestamp - timedelta(hours=2)
                self.swing_points[symbol]['highs'] = [
                    h for h in self.swing_points[symbol]['highs']
                    if h['timestamp'] > cutoff_time
                ]

            # Swing low detection
            if (current.low < recent_bars[i-1].low and
                current.low < recent_bars[i-2].low and
                current.low < recent_bars[i+1].low and
                current.low < recent_bars[i+2].low):

                swing_low = {
                    'price': current.low,
                    'timestamp': current.timestamp,
                    'bar_index': len(self.bars_history[symbol]) - len(recent_bars) + i
                }
                self.swing_points[symbol]['lows'].append(swing_low)

                # Keep only recent swing points
                cutoff_time = bar.timestamp - timedelta(hours=2)
                self.swing_points[symbol]['lows'] = [
                    l for l in self.swing_points[symbol]['lows']
                    if l['timestamp'] > cutoff_time
                ]

    def _detect_ascending_triangle(self, symbol: str, bar: MarketData) -> Optional[Dict]:
        """
        Detect ascending triangle pattern

        Requirements:
        - Horizontal resistance (multiple touches at similar level)
        - Ascending support (higher lows trend line)
        - Converging pattern
        """
        if symbol not in self.swing_points:
            return None

        highs = self.swing_points[symbol]['highs']
        lows = self.swing_points[symbol]['lows']

        # Need minimum swing points
        if len(highs) < self._parameters['min_resistance_touches'] or len(lows) < self._parameters['min_support_touches']:
            return None

        # Detect horizontal resistance
        resistance_data = self._find_horizontal_resistance(highs)
        if not resistance_data:
            return None

        # Detect ascending support
        support_data = self._find_ascending_support(lows)
        if not support_data:
            return None

        # Verify pattern convergence and timing
        if not self._validate_triangle_formation(resistance_data, support_data, bar):
            return None

        return {
            'resistance': resistance_data['level'],
            'resistance_touches': resistance_data['touches'],
            'support_slope': support_data['slope'],
            'support_intercept': support_data['intercept'],
            'support_touches': support_data['touches'],
            'formation_start': min(resistance_data['first_touch'], support_data['first_touch']),
            'apex_time': self._calculate_apex_time(resistance_data, support_data),
            'height': resistance_data['level'] - min([low['price'] for low in support_data['touches']])
        }

    def _find_horizontal_resistance(self, highs: List[Dict]) -> Optional[Dict]:
        """Find horizontal resistance level from swing highs"""
        if len(highs) < self._parameters['min_resistance_touches']:
            return None

        # Group swing highs by price level (within variance tolerance)
        variance = self._parameters['max_resistance_variance']
        resistance_groups = []

        for high in highs:
            added_to_group = False
            for group in resistance_groups:
                group_avg = np.mean([h['price'] for h in group])
                if abs(high['price'] - group_avg) / group_avg <= variance:
                    group.append(high)
                    added_to_group = True
                    break

            if not added_to_group:
                resistance_groups.append([high])

        # Find group with most touches
        best_group = max(resistance_groups, key=len, default=[])

        if len(best_group) < self._parameters['min_resistance_touches']:
            return None

        return {
            'level': np.mean([h['price'] for h in best_group]),
            'touches': best_group,
            'first_touch': min(best_group, key=lambda x: x['timestamp'])['timestamp'],
            'variance': np.std([h['price'] for h in best_group])
        }

    def _find_ascending_support(self, lows: List[Dict]) -> Optional[Dict]:
        """Find ascending support line from swing lows"""
        if len(lows) < self._parameters['min_support_touches']:
            return None

        # Sort lows by time
        sorted_lows = sorted(lows, key=lambda x: x['timestamp'])

        # Try different combinations to find best ascending line
        best_line = None
        best_score = 0

        for i in range(len(sorted_lows) - self._parameters['min_support_touches'] + 1):
            for j in range(i + self._parameters['min_support_touches'] - 1, len(sorted_lows)):
                line_points = sorted_lows[i:j+1]
                line_data = self._calculate_support_line(line_points)

                if line_data and line_data['slope'] >= self._parameters['min_ascending_slope']:
                    score = len(line_points) * (1 - line_data['deviation'])
                    if score > best_score:
                        best_score = score
                        best_line = line_data

        return best_line

    def _calculate_support_line(self, points: List[Dict]) -> Optional[Dict]:
        """Calculate linear regression for support line"""
        if len(points) < 2:
            return None

        # Convert to timestamps (minutes since first point) and prices
        first_time = points[0]['timestamp']
        x = [(p['timestamp'] - first_time).total_seconds() / 60 for p in points]
        y = [p['price'] for p in points]

        # Linear regression
        x_array = np.array(x)
        y_array = np.array(y)

        if len(x_array) < 2:
            return None

        # Calculate slope and intercept
        slope, intercept = np.polyfit(x_array, y_array, 1)

        # Calculate line quality (R-squared)
        y_pred = slope * x_array + intercept
        ss_res = np.sum((y_array - y_pred) ** 2)
        ss_tot = np.sum((y_array - np.mean(y_array)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        return {
            'slope': slope,
            'intercept': intercept,
            'touches': points,
            'first_touch': points[0]['timestamp'],
            'r_squared': r_squared,
            'deviation': 1 - r_squared
        }

    def _validate_triangle_formation(self, resistance_data: Dict, support_data: Dict, current_bar: MarketData) -> bool:
        """Validate that we have a proper ascending triangle formation"""

        # Check formation time is within acceptable range
        formation_time = current_bar.timestamp - min(resistance_data['first_touch'], support_data['first_touch'])
        min_time = timedelta(minutes=self._parameters['min_formation_minutes'])
        max_time = timedelta(minutes=self._parameters['max_formation_minutes'])

        if formation_time < min_time or formation_time > max_time:
            return False

        # Check that support line is actually ascending
        if support_data['slope'] < self._parameters['min_ascending_slope']:
            return False

        # Check that resistance is above current support level
        current_support = self._get_current_support_level(support_data, current_bar.timestamp)
        if resistance_data['level'] <= current_support:
            return False

        # Check convergence (lines are getting closer)
        triangle_height = resistance_data['level'] - current_support
        if triangle_height <= 0:
            return False

        return True

    def _get_current_support_level(self, support_data: Dict, timestamp: datetime) -> float:
        """Calculate current support level based on ascending line"""
        first_time = support_data['first_touch']
        minutes_elapsed = (timestamp - first_time).total_seconds() / 60
        return support_data['slope'] * minutes_elapsed + support_data['intercept']

    def _calculate_apex_time(self, resistance_data: Dict, support_data: Dict) -> datetime:
        """Calculate when support and resistance lines would meet (apex)"""
        # This is theoretical - we want to trade before the apex
        if support_data['slope'] <= 0:
            return resistance_data['first_touch'] + timedelta(hours=4)  # Default far future

        # Time when support line reaches resistance level
        first_time = support_data['first_touch']
        minutes_to_apex = (resistance_data['level'] - support_data['intercept']) / support_data['slope']
        return first_time + timedelta(minutes=minutes_to_apex)

    def _detect_breakout(self, symbol: str, bar: MarketData, triangle_data: Dict) -> Optional[Dict]:
        """Detect breakout above resistance level"""
        resistance_level = triangle_data['resistance']
        breakout_threshold = resistance_level * (1 + self._parameters['breakout_threshold_pct'] / 100)

        # Check if current bar breaks above resistance
        if bar.high < breakout_threshold:
            return None

        # Calculate breakout percentage
        breakout_pct = ((bar.close - resistance_level) / resistance_level) * 100

        # Check volume confirmation
        recent_bars = self.bars_history[symbol][-10:]
        avg_volume = np.mean([b.volume for b in recent_bars[:-1]]) if len(recent_bars) > 1 else bar.volume
        volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0

        return {
            'breakout_price': bar.high,
            'breakout_pct': breakout_pct,
            'volume_ratio': volume_ratio,
            'resistance_level': resistance_level,
            'current_price': bar.close
        }

    def _passes_static_filters(self, symbol: str, bar: MarketData, triangle_data: Dict, breakout_data: Dict) -> bool:
        """Apply static/hard filters that must be met"""

        # Price range filter
        if not (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
            return False

        # Volume confirmation
        required_volume_ratio = self._parameters['breakout_volume_multiplier']
        if breakout_data['volume_ratio'] < required_volume_ratio:
            self.logger.debug(f"🔺 {symbol}: Volume ratio {breakout_data['volume_ratio']:.1f}x below required {required_volume_ratio}x")
            return False

        # Breakout strength (not too weak)
        if breakout_data['breakout_pct'] < 0.1:  # At least 0.1% breakout
            return False

        # Formation quality minimums
        if len(triangle_data['resistance_touches']) < self._parameters['min_resistance_touches']:
            return False

        if len(triangle_data['support_touches']) < self._parameters['min_support_touches']:
            return False

        return True

    def _calculate_triangle_scores(self, symbol: str, bar: MarketData, triangle_data: Dict, breakout_data: Dict) -> Dict[str, float]:
        """Calculate flexible scoring components"""

        scores = {}

        # 1. Pattern Quality Score (0-100)
        scores['pattern_quality'] = self._score_pattern_quality(triangle_data)

        # 2. Volume Profile Score (0-100)
        scores['volume_profile'] = self._score_volume_profile(symbol, bar, breakout_data)

        # 3. Breakout Strength Score (0-150) - Most important
        scores['breakout_strength'] = self._score_breakout_strength(breakout_data)

        # 4. Market Context Score (0-75)
        scores['market_context'] = self._score_market_context(symbol, bar)

        # 5. Timing Score (0-75)
        scores['timing'] = self._score_timing(bar.timestamp)

        return scores

    def _score_pattern_quality(self, triangle_data: Dict) -> float:
        """Score the quality of the triangle pattern (0-100)"""
        score = 0

        # More resistance touches = better
        resistance_touches = len(triangle_data['resistance_touches'])
        if resistance_touches >= 3:
            score += min(40, (resistance_touches - 2) * 10)  # Max 40 points

        # More support touches = better
        support_touches = len(triangle_data['support_touches'])
        if support_touches >= 3:
            score += min(30, (support_touches - 2) * 8)  # Max 30 points

        # Good ascending slope (not too steep or flat)
        slope = triangle_data['support_slope']
        if 0.001 <= slope <= 0.01:  # Optimal range
            score += 20
        elif 0.0005 <= slope <= 0.002:  # Decent range
            score += 15
        elif slope > 0:  # At least ascending
            score += 10

        # Triangle height (bigger triangles often more significant)
        height_pct = (triangle_data['height'] / triangle_data['resistance']) * 100
        if 3 <= height_pct <= 8:  # Optimal 3-8% height
            score += 10
        elif 1 <= height_pct <= 12:  # Acceptable range
            score += 5

        return min(100, score)

    def _score_volume_profile(self, symbol: str, bar: MarketData, breakout_data: Dict) -> float:
        """Score volume characteristics (0-100)"""
        score = 0

        # Breakout volume ratio
        vol_ratio = breakout_data['volume_ratio']
        if vol_ratio >= 3.0:
            score += 50  # Explosive volume
        elif vol_ratio >= 2.0:
            score += 40  # Strong volume
        elif vol_ratio >= 1.5:
            score += 30  # Good volume
        elif vol_ratio >= 1.2:
            score += 20  # Acceptable volume
        else:
            score += 10  # Weak volume

        # Volume trend during formation (decreasing = good)
        recent_bars = self.bars_history[symbol][-15:]
        if len(recent_bars) >= 10:
            early_vol = np.mean([b.volume for b in recent_bars[:5]])
            middle_vol = np.mean([b.volume for b in recent_bars[5:10]])

            if middle_vol < early_vol * 0.8:  # Volume decreased 20%+
                score += 25
            elif middle_vol < early_vol * 0.9:  # Volume decreased 10%+
                score += 15
            elif middle_vol < early_vol:  # Volume decreased
                score += 10

        # Above average daily volume
        if bar.volume > 100000:  # High absolute volume
            score += 15
        elif bar.volume > 50000:  # Good absolute volume
            score += 10
        elif bar.volume > 25000:  # Acceptable volume
            score += 5

        return min(100, score)

    def _score_breakout_strength(self, breakout_data: Dict) -> float:
        """Score breakout strength (0-150) - Most important component"""
        score = 0

        # Breakout percentage above resistance
        breakout_pct = breakout_data['breakout_pct']
        if breakout_pct >= 2.0:
            score += 60  # Strong breakout 2%+
        elif breakout_pct >= 1.0:
            score += 50  # Good breakout 1%+
        elif breakout_pct >= 0.5:
            score += 40  # Decent breakout 0.5%+
        elif breakout_pct >= 0.2:
            score += 30  # Minimal breakout
        else:
            score += 10  # Very weak

        # Volume confirmation strength
        vol_ratio = breakout_data['volume_ratio']
        if vol_ratio >= 4.0:
            score += 40  # Massive volume
        elif vol_ratio >= 2.5:
            score += 35  # Very strong volume
        elif vol_ratio >= 2.0:
            score += 30  # Strong volume
        elif vol_ratio >= 1.5:
            score += 25  # Good volume
        elif vol_ratio >= 1.2:
            score += 15  # Acceptable
        else:
            score += 5   # Weak

        # Clean breakout (current price near high of breakout bar)
        price_high_ratio = breakout_data['current_price'] / breakout_data['breakout_price']
        if price_high_ratio >= 0.98:  # Very clean
            score += 25
        elif price_high_ratio >= 0.95:  # Clean
            score += 20
        elif price_high_ratio >= 0.90:  # Decent
            score += 15
        else:
            score += 5  # Pullback after breakout

        # Momentum (gap above resistance)
        gap_pct = ((breakout_data['breakout_price'] - breakout_data['resistance_level']) /
                  breakout_data['resistance_level']) * 100
        if gap_pct >= 1.0:
            score += 25  # Gapped above resistance
        elif gap_pct >= 0.5:
            score += 15  # Strong break
        elif gap_pct >= 0.2:
            score += 10  # Clean break
        else:
            score += 5   # Minimal break

        return min(150, score)

    def _score_market_context(self, symbol: str, bar: MarketData) -> float:
        """Score market context (0-75)"""
        score = 0

        # Market trend (simplified - could integrate with broader market data)
        recent_bars = self.bars_history[symbol][-20:]
        if len(recent_bars) >= 10:
            early_avg = np.mean([b.close for b in recent_bars[:10]])
            recent_avg = np.mean([b.close for b in recent_bars[-10:]])

            trend_pct = ((recent_avg - early_avg) / early_avg) * 100
            if trend_pct >= 2:
                score += 25  # Strong uptrend
            elif trend_pct >= 0.5:
                score += 20  # Uptrend
            elif trend_pct >= -0.5:
                score += 15  # Sideways
            elif trend_pct >= -2:
                score += 10  # Mild downtrend
            else:
                score += 5   # Strong downtrend
        else:
            score += 15  # Neutral if insufficient data

        # Volatility (higher volatility = better for breakouts)
        if len(recent_bars) >= 5:
            prices = [b.close for b in recent_bars[-5:]]
            volatility = np.std(prices) / np.mean(prices)

            if volatility >= 0.05:  # High volatility (5%+)
                score += 25
            elif volatility >= 0.03:  # Good volatility (3%+)
                score += 20
            elif volatility >= 0.015:  # Moderate volatility
                score += 15
            else:
                score += 10  # Low volatility

        # Price level appropriateness for smallcaps
        if 2.0 <= bar.close <= 8.0:  # Sweet spot
            score += 25
        elif 1.0 <= bar.close <= 12.0:  # Good range
            score += 20
        elif self._parameters['min_price'] <= bar.close <= self._parameters['max_price']:  # Acceptable
            score += 15
        else:
            score += 5  # Outside preferred range

        return min(75, score)

    def _score_timing(self, timestamp: datetime) -> float:
        """Score timing factors (0-75)"""
        score = 0

        # Time of day (market hours impact)
        hour = timestamp.hour + timestamp.minute / 60.0

        if 10.0 <= hour <= 11.5:  # Morning momentum
            score += 30
        elif 13.5 <= hour <= 15.0:  # Afternoon momentum
            score += 25
        elif 9.5 <= hour <= 10.0:  # Early morning
            score += 20
        elif 15.0 <= hour <= 15.5:  # Late afternoon
            score += 20
        elif 11.5 <= hour <= 13.5:  # Lunch hours
            score += 10  # Avoid lunch period
        else:
            score += 5   # Outside optimal hours

        # Day of week (if needed)
        weekday = timestamp.weekday()  # 0=Monday, 4=Friday
        if weekday in [1, 2, 3]:  # Tuesday, Wednesday, Thursday
            score += 25  # Best days
        elif weekday in [0, 4]:  # Monday, Friday
            score += 20  # Good days
        else:
            score += 10  # Weekend (shouldn't happen)

        # Avoid first/last 30 minutes of market
        if 9.5 <= hour <= 10.0 or 15.5 <= hour <= 16.0:
            score -= 10  # Reduce score for volatile open/close

        return min(75, max(0, score))

    def _calculate_signal_strength(self, total_score: float) -> float:
        """Convert total score to signal strength (0.0-1.0)"""
        excellent_threshold = self._parameters['excellent_triangle_score']
        good_threshold = self._parameters['good_triangle_score']
        min_threshold = self._parameters['min_triangle_score']

        if total_score >= excellent_threshold:
            return 0.95  # Excellent setup
        elif total_score >= good_threshold:
            return 0.80  # Good setup
        elif total_score >= min_threshold:
            return 0.65  # Acceptable setup
        else:
            return 0.50  # Below threshold (shouldn't reach here)

    def _create_triangle_signal(self, symbol: str, bar: MarketData, triangle_data: Dict,
                              breakout_data: Dict, scores: Dict, strength: float) -> Signal:
        """Create ascending triangle breakout signal"""

        resistance_level = triangle_data['resistance']
        triangle_height = triangle_data['height']

        # Calculate targets based on triangle height projection
        profit_target_pct = max(
            self._parameters['take_profit_pct'],
            (triangle_height / resistance_level) * 1.2  # 120% of triangle height
        )
        profit_target_pct = min(profit_target_pct, 0.25)  # Cap at 25%

        signal = Signal(
            signal_id=f"AscTriangle-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol,
            signal_type=SignalType.LONG,
            strength=strength,
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name="AscendingTriangle",
            metadata={
                'strategy': 'AscendingTriangle',
                'setup_type': 'ascending_triangle_breakout',
                'resistance_level': resistance_level,
                'breakout_price': breakout_data['breakout_price'],
                'breakout_pct': breakout_data['breakout_pct'],
                'volume_ratio': breakout_data['volume_ratio'],
                'triangle_height': triangle_height,
                'formation_minutes': (bar.timestamp - triangle_data['formation_start']).total_seconds() / 60,
                'resistance_touches': len(triangle_data['resistance_touches']),
                'support_touches': len(triangle_data['support_touches']),
                'total_score': sum(scores.values()),
                'score_breakdown': scores,
                'is_entry': True,
                'stop_loss': resistance_level * (1 - self._parameters['stop_loss_pct']),
                'take_profit': bar.close * (1 + profit_target_pct),
                'pattern': f"asc_triangle_{resistance_level:.2f}_height_{triangle_height:.2f}"
            }
        )

        return signal

    def _has_sufficient_history(self, symbol: str, min_bars: int = 20) -> bool:
        """Check if we have enough historical data"""
        return (symbol in self.bars_history and
                len(self.bars_history[symbol]) >= min_bars)

    def get_strategy_info(self) -> Dict:
        """Return strategy information"""
        return {
            'name': 'AscendingTriangle',
            'description': 'Ascending triangle breakout strategy for smallcaps',
            'version': '1.0.0',
            'parameters_count': len(self._parameters),
            'pattern_type': 'Ascending Triangle Only',
            'market_focus': 'Smallcaps ($1-$15)',
            'timeframe': 'Intraday (15-120 min formation)',
            'signal_type': 'Bullish breakouts only',
            'risk_reward': '1:3 minimum (4% stop, 12% target)'
        }

    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For ascending triangle strategy, we don't need special logic on position updates
        # Position management is handled by the main strategy logic and risk management
        return None

    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited based on ascending triangle conditions"""
        try:
            symbol = position.symbol
            current_price = current_bar.close

            # Basic exit conditions for ascending triangle breakouts

            # 1. Stop loss check (below resistance level that was broken)
            if hasattr(position, 'metadata') and position.metadata:
                resistance_level = position.metadata.get('resistance_level')
                if resistance_level:
                    # Stop loss 2% below the resistance level that was broken
                    stop_loss_price = resistance_level * 0.98
                    if current_price <= stop_loss_price:
                        return Signal(
                            signal_id=f"AscTriangle-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=1.0,
                            price=current_price,
                            timestamp=current_bar.timestamp,
                            strategy_name="AscendingTriangle",
                            metadata={
                                'exit_reason': 'stop_loss',
                                'resistance_level': resistance_level,
                                'entry_price': position.avg_price
                            }
                        )

            # 2. Profit target check (configurable target based on triangle height)
            profit_target_pct = self._parameters.get('take_profit_pct', 0.12)  # 12% default
            target_price = position.avg_price * (1 + profit_target_pct)
            if current_price >= target_price:
                return Signal(
                    signal_id=f"AscTriangle-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,
                    price=current_price,
                    timestamp=current_bar.timestamp,
                    strategy_name="AscendingTriangle",
                    metadata={
                        'exit_reason': 'profit_target',
                        'target_price': target_price,
                        'entry_price': position.avg_price,
                        'profit_pct': ((current_price - position.avg_price) / position.avg_price) * 100
                    }
                )

            # 3. Time-based exit (maximum hold time)
            if hasattr(position, 'entry_time') and position.entry_time:
                hold_time = (current_bar.timestamp - position.entry_time).total_seconds() / 60
                max_hold_minutes = self._parameters.get('max_hold_minutes', 180)  # 3 hours default

                if hold_time > max_hold_minutes:
                    return Signal(
                        signal_id=f"AscTriangle-EXIT-{symbol}-{current_bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.8,
                        price=current_price,
                        timestamp=current_bar.timestamp,
                        strategy_name="AscendingTriangle",
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