"""
Consolidation Pattern Detector

Detects long-term consolidation patterns (4 weeks to 6 months) in smallcap stocks
and identifies optimal entry points (breakout OR pullback).

Key Features:
- Dual entry modes: Breakout confirmation vs Pullback entry
- Smallcap-specific logic (gaps, volatility, thin volume)
- Pattern recognition: Triangle, Cup & Handle, Bull Flag, Flat Base
- Breakout scoring (0-100) based on pattern quality
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class ConsolidationPatternDetector:
    """
    Detects consolidation patterns and calculates breakout scores

    Designed for SMALLCAPS with specific considerations:
    - Premarket gaps are common (avoid buying at top)
    - Pullbacks provide better risk/reward entries
    - MACDV + RSI for oversold confirmation
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.ConsolidationPatternDetector")

        # Consolidation parameters - RELAXED for current smallcap market conditions
        self.min_days = self.config.get('min_consolidation_days', 14)  # REDUCED: 2 weeks (was 20)
        self.max_days = self.config.get('max_consolidation_days', 120)  # 6 months
        self.max_range_pct = self.config.get('max_consolidation_range_pct', 35.0)  # INCREASED: 35% (was 25%)

        # Pattern detection - RELAXED for smallcap liquidity
        self.min_resistance_touches = self.config.get('min_resistance_touches', 2)  # REDUCED: 2 (was 3)
        self.min_support_touches = self.config.get('min_support_touches', 1)  # REDUCED: 1 (was 2)

        # Entry mode parameters
        self.max_safe_gap = 3.0  # <3% gap = safe for market open entry
        self.max_dangerous_gap = 5.0  # >5% gap = wait for pullback

        # NEW: Short consolidation parameters for volatile smallcaps
        self.short_consolidation_max_days = 28  # 4 weeks max for short consolidations
        self.short_consolidation_min_days = 7   # 1 week min for short consolidations

        self.logger.info("🔍 ConsolidationPatternDetector initialized (RELAXED for volatile smallcap market)")
        self.logger.info(f"   📊 Dual entry modes: Breakout (<3% gap) | Pullback (>5% gap)")
        self.logger.info(f"   🎯 Range limit: {self.max_range_pct}% (increased from 25%)")
        self.logger.info(f"   📅 Duration: {self.min_days}-{self.max_days} days (reduced min from 20)")
        self.logger.info(f"   🎪 New pattern: SHORT_CONSOLIDATION for 1-4 week setups")

    def analyze_consolidation(self, symbol: str, daily_bars: List[Dict]) -> Optional[Dict]:
        """
        Analyze daily bars for consolidation pattern

        Args:
            symbol: Ticker symbol
            daily_bars: List of daily OHLCV bars (oldest to newest)
                        Each bar: {'date': date, 'open': float, 'high': float,
                                  'low': float, 'close': float, 'volume': int}

        Returns:
            Consolidation setup dict or None if no pattern found
        """
        if len(daily_bars) < self.min_days:
            self.logger.debug(f"{symbol}: Insufficient data ({len(daily_bars)} bars)")
            return None

        # Step 1: Detect consolidation period
        consolidation = self._detect_consolidation_period(daily_bars, symbol)
        if not consolidation:
            return None

        # Step 2: Identify pattern type
        pattern_type = self._identify_pattern_type(consolidation['bars'])

        # Step 3: Calculate support/resistance levels
        resistance = consolidation['high']
        support = consolidation['low']

        # Step 4: Check current price proximity to resistance
        current_price = daily_bars[-1]['close']
        distance_from_resistance = ((resistance - current_price) / current_price) * 100

        max_distance = self.config.get('max_distance_from_resistance_pct', 8.0)  # RELAXED from 5.0%
        if distance_from_resistance > max_distance:
            self.logger.debug(
                f"{symbol}: Too far from resistance ({distance_from_resistance:.1f}% away, max allowed {max_distance:.1f}%)"
            )
            return None

        # Step 5: Calculate breakout score
        breakout_score = self._calculate_breakout_score(
            symbol=symbol,
            consolidation=consolidation,
            pattern_type=pattern_type,
            current_price=current_price,
            resistance=resistance,
            support=support
        )

        # Step 6: Determine recommended entry mode
        entry_mode = self._determine_entry_mode(daily_bars)

        return {
            'symbol': symbol,
            'pattern_type': pattern_type,
            'consolidation_days': consolidation['days'],
            'resistance': resistance,
            'support': support,
            'current_price': current_price,
            'distance_to_resistance': distance_from_resistance,
            'breakout_score': breakout_score,
            'entry_mode': entry_mode,  # 'BREAKOUT' or 'PULLBACK'
            'volume_compression': consolidation['volume_compression'],
            'avg_volume': consolidation['avg_volume'],
            'scan_date': datetime.now().date()
        }

    def _detect_consolidation_period(self, daily_bars: List[Dict], symbol: str = "UNKNOWN") -> Optional[Dict]:
        """
        Detect if recent bars form a consolidation pattern

        A consolidation is:
        - 7-120 days of sideways movement (RELAXED for smallcaps)
        - High-Low range < 35% of average price (INCREASED for volatile smallcaps)
        - Decreasing volume (compression)
        """
        # Try different lookback periods (start with max, reduce if needed)
        # NEW: Also try short consolidation periods for volatile smallcaps
        all_lookbacks = list(range(self.max_days, self.min_days - 1, -5))
        short_lookbacks = list(range(self.short_consolidation_max_days, self.short_consolidation_min_days - 1, -2))

        # Combine and deduplicate
        lookback_periods = list(set(all_lookbacks + short_lookbacks))
        lookback_periods.sort(reverse=True)

        self.logger.debug(f"{symbol}: Testing {len(lookback_periods)} lookback periods: {lookback_periods[:5]}...{lookback_periods[-3:]}")

        for lookback in lookback_periods:
            if len(daily_bars) < lookback:
                continue

            window_bars = daily_bars[-lookback:]

            # Calculate price range
            highs = [bar['high'] for bar in window_bars]
            lows = [bar['low'] for bar in window_bars]
            closes = [bar['close'] for bar in window_bars]
            volumes = [bar['volume'] for bar in window_bars]

            high = max(highs)
            low = min(lows)
            avg_price = np.mean(closes)

            # Check range constraint
            range_pct = ((high - low) / avg_price) * 100
            self.logger.debug(f"{symbol}: Period {lookback}d - Range: ${low:.2f}-${high:.2f} ({range_pct:.1f}%) vs max {self.max_range_pct:.1f}%")
            if range_pct > self.max_range_pct:
                self.logger.debug(f"{symbol}: ❌ REJECTED - Range too wide ({range_pct:.1f}% > {self.max_range_pct:.1f}%)")
                continue  # Too wide, not consolidation

            # Check volume compression (last 1/3 vs first 1/3)
            third = len(window_bars) // 3
            early_volume = np.mean(volumes[:third])
            late_volume = np.mean(volumes[-third:])
            volume_compression = late_volume / early_volume if early_volume > 0 else 1.0

            self.logger.debug(f"{symbol}: Period {lookback}d - Volume: early {early_volume:,.0f}, late {late_volume:,.0f}, compression {volume_compression:.2f}")

            # Consolidations should have decreasing volume
            if volume_compression > 1.2:
                self.logger.debug(f"{symbol}: ❌ REJECTED - Volume increasing ({volume_compression:.2f} > 1.2)")
                continue  # Volume increasing, not compressing

            # Check resistance/support touches
            resistance_touches = self._count_touches(highs, high, tolerance=0.02)
            support_touches = self._count_touches(lows, low, tolerance=0.02)

            self.logger.debug(f"{symbol}: Period {lookback}d - Touches: resistance {resistance_touches} (need ≥{self.min_resistance_touches}), support {support_touches} (need ≥{self.min_support_touches})")

            if (resistance_touches >= self.min_resistance_touches and
                support_touches >= self.min_support_touches):

                self.logger.debug(f"{symbol}: ✅ CONSOLIDATION FOUND - Period {lookback}d, range {range_pct:.1f}%, vol compression {volume_compression:.2f}")

                return {
                    'days': lookback,
                    'high': high,
                    'low': low,
                    'avg_price': avg_price,
                    'range_pct': range_pct,
                    'volume_compression': volume_compression,
                    'avg_volume': np.mean(volumes),
                    'resistance_touches': resistance_touches,
                    'support_touches': support_touches,
                    'bars': window_bars
                }

        self.logger.debug(f"{symbol}: ❌ No consolidation found in any {len(lookback_periods)} tested periods")
        return None

    def _count_touches(self, values: List[float], target: float, tolerance: float = 0.02) -> int:
        """
        Count how many times price touched a level (within tolerance)

        Args:
            values: List of price values
            target: Target level (support/resistance)
            tolerance: % tolerance (0.02 = 2%)
        """
        touches = 0
        threshold_upper = target * (1 + tolerance)
        threshold_lower = target * (1 - tolerance)

        for value in values:
            if threshold_lower <= value <= threshold_upper:
                touches += 1

        return touches

    def _identify_pattern_type(self, bars: List[Dict]) -> str:
        """
        Identify consolidation pattern type

        Patterns:
        - ASCENDING_TRIANGLE: Higher lows, flat resistance
        - DESCENDING_TRIANGLE: Lower highs, flat support
        - BULL_FLAG: Slight downward drift in tight range
        - CUP_HANDLE: U-shape with handle
        - FLAT_BASE: Tight horizontal range
        - SHORT_CONSOLIDATION: Quick consolidation (1-4 weeks) for volatile smallcaps
        """
        lows = [bar['low'] for bar in bars]
        highs = [bar['high'] for bar in bars]
        num_bars = len(bars)

        # Calculate trends
        low_slope = self._calculate_slope(lows)
        high_slope = self._calculate_slope(highs)

        # NEW: Short consolidation for volatile smallcaps (1-4 weeks)
        if num_bars <= self.short_consolidation_max_days and num_bars >= self.short_consolidation_min_days:
            return 'SHORT_CONSOLIDATION'

        # Ascending Triangle: Lows rising, highs flat
        if low_slope > 0.0001 and abs(high_slope) < 0.0001:
            return 'ASCENDING_TRIANGLE'

        # Descending Triangle: Highs falling, lows flat
        if high_slope < -0.0001 and abs(low_slope) < 0.0001:
            return 'DESCENDING_TRIANGLE'

        # Bull Flag: Both slightly declining
        if low_slope < 0 and high_slope < 0:
            return 'BULL_FLAG'

        # Cup & Handle: Check for U-shape (simplified)
        # TODO: Implement proper cup detection

        # Default: Flat base
        return 'FLAT_BASE'

    def _calculate_slope(self, values: List[float]) -> float:
        """Calculate linear regression slope"""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        y = np.array(values)

        # Simple linear regression
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        return slope

    def _calculate_breakout_score(
        self,
        symbol: str,
        consolidation: Dict,
        pattern_type: str,
        current_price: float,
        resistance: float,
        support: float
    ) -> float:
        """
        Calculate breakout score (0-100)

        Components:
        1. Pattern quality (25 pts)
        2. Volume compression (20 pts)
        3. Consolidation duration (20 pts)
        4. Proximity to resistance (20 pts)
        5. Support/Resistance touches (15 pts)
        """
        score = 0.0

        # 1. Pattern quality (25 pts) - UPDATED for smallcap market conditions
        pattern_scores = {
            'ASCENDING_TRIANGLE': 25,  # Best bullish pattern
            'BULL_FLAG': 22,
            'FLAT_BASE': 20,
            'CUP_HANDLE': 23,
            'SHORT_CONSOLIDATION': 24,  # NEW: High score for volatile smallcaps
            'DESCENDING_TRIANGLE': 15  # Weaker
        }
        score += pattern_scores.get(pattern_type, 18)

        # 2. Volume compression (20 pts) - More compression = better
        # Ideal: 0.5-0.7 ratio (late volume is 50-70% of early volume)
        vol_compression = consolidation['volume_compression']
        if 0.5 <= vol_compression <= 0.7:
            score += 20
        elif 0.4 <= vol_compression < 0.5 or 0.7 < vol_compression <= 0.8:
            score += 15
        elif 0.3 <= vol_compression < 0.4 or 0.8 < vol_compression <= 0.9:
            score += 10
        else:
            score += 5

        # 3. Consolidation duration (20 pts) - Optimal: 6-12 weeks
        days = consolidation['days']
        if 42 <= days <= 84:  # 6-12 weeks
            score += 20
        elif 28 <= days < 42 or 84 < days <= 100:  # 4-6 weeks or 12-14 weeks
            score += 15
        elif 20 <= days < 28 or 100 < days <= 120:
            score += 10
        else:
            score += 5

        # 4. Proximity to resistance (20 pts) - Closer = better
        distance_pct = ((resistance - current_price) / current_price) * 100
        if distance_pct <= 1.0:  # Within 1%
            score += 20
        elif distance_pct <= 2.0:
            score += 16
        elif distance_pct <= 3.0:
            score += 12
        elif distance_pct <= 5.0:
            score += 8
        else:
            score += 3

        # 5. Support/Resistance touches (15 pts)
        touches_score = min(
            (consolidation['resistance_touches'] + consolidation['support_touches']) * 2,
            15
        )
        score += touches_score

        self.logger.debug(f"{symbol}: Breakout score = {score:.0f}/100")

        return min(score, 100.0)

    def _determine_entry_mode(self, daily_bars: List[Dict]) -> str:
        """
        Determine recommended entry mode based on current setup

        Returns:
            'BREAKOUT' - Safe to enter at market open (small/no gap)
            'PULLBACK' - Wait for pullback during day (large gap expected)
        """
        # Analyze recent price action (last 5 days)
        recent_bars = daily_bars[-5:]

        # Check for strong momentum into resistance (likely gaps in premarket)
        closes = [bar['close'] for bar in recent_bars]
        volumes = [bar['volume'] for bar in recent_bars]

        # If strong volume + strong close → likely premarket gap
        avg_volume = np.mean(volumes[:-1])
        last_volume = volumes[-1]

        volume_surge = last_volume / avg_volume if avg_volume > 0 else 1.0

        # Strong close + volume surge = likely gap
        if volume_surge > 1.8 and closes[-1] > closes[-2]:
            return 'PULLBACK'  # Expect gap, wait for pullback

        # Default: Breakout confirmation at market open
        return 'BREAKOUT'

    def calculate_pullback_entry_levels(
        self,
        symbol: str,
        resistance: float,
        support: float,
        current_price: float
    ) -> Dict:
        """
        Calculate optimal pullback entry levels for PULLBACK mode

        Returns dict with:
        - Primary entry: Old resistance (now support)
        - Secondary entry: 50% retracement
        - Stop loss: Below support
        """
        # Primary entry: Old resistance becomes new support
        primary_entry = resistance * 0.995  # Slightly below resistance

        # Secondary entry: 50% Fibonacci retracement
        secondary_entry = support + (resistance - support) * 0.5

        # Stop loss: 2% below old consolidation support
        stop_loss = support * 0.98

        # Target: 50% above resistance (swing target)
        target = resistance * 1.50

        risk = abs(primary_entry - stop_loss)
        reward = abs(target - primary_entry)
        risk_reward = reward / risk if risk > 0 else 0

        return {
            'symbol': symbol,
            'entry_mode': 'PULLBACK',
            'primary_entry': primary_entry,
            'secondary_entry': secondary_entry,
            'stop_loss': stop_loss,
            'target': target,
            'risk_reward_ratio': risk_reward,
            'notes': f"Wait for pullback to old resistance (${primary_entry:.2f}). Confirm with MACDV bullish + RSI <40."
        }


# Test function
def test_pattern_detector():
    """Test consolidation pattern detector"""
    print("🧪 Testing ConsolidationPatternDetector")
    print("=" * 50)

    # Create test data: 60-day consolidation
    test_bars = []
    base_price = 10.0

    for i in range(60):
        # Simulate tight range ($9-11)
        bar = {
            'date': datetime.now().date() - timedelta(days=60-i),
            'open': base_price + np.random.uniform(-0.5, 0.5),
            'high': base_price + np.random.uniform(0.5, 1.0),
            'low': base_price + np.random.uniform(-1.0, -0.5),
            'close': base_price + np.random.uniform(-0.3, 0.3),
            'volume': int(100000 * (1 - i/120))  # Decreasing volume
        }
        test_bars.append(bar)

    # Current price near resistance
    test_bars[-1]['close'] = 10.8

    detector = ConsolidationPatternDetector()
    result = detector.analyze_consolidation('TEST', test_bars)

    if result:
        print(f"✅ Pattern detected: {result['pattern_type']}")
        print(f"   Consolidation: {result['consolidation_days']} days")
        print(f"   Resistance: ${result['resistance']:.2f}")
        print(f"   Support: ${result['support']:.2f}")
        print(f"   Current: ${result['current_price']:.2f}")
        print(f"   Breakout Score: {result['breakout_score']:.0f}/100")
        print(f"   Entry Mode: {result['entry_mode']}")

        if result['entry_mode'] == 'PULLBACK':
            pullback_levels = detector.calculate_pullback_entry_levels(
                'TEST',
                result['resistance'],
                result['support'],
                result['current_price']
            )
            print(f"\n📊 Pullback Entry Levels:")
            print(f"   Primary: ${pullback_levels['primary_entry']:.2f}")
            print(f"   Secondary: ${pullback_levels['secondary_entry']:.2f}")
            print(f"   Stop: ${pullback_levels['stop_loss']:.2f}")
            print(f"   Target: ${pullback_levels['target']:.2f}")
            print(f"   R:R: {pullback_levels['risk_reward_ratio']:.1f}:1")
    else:
        print("❌ No consolidation pattern detected")


if __name__ == "__main__":
    test_pattern_detector()
