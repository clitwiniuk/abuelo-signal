#!/usr/bin/env python3
"""
Context Engine - Market Regime Detection

Analyzes market context for each ticker to determine optimal worker assignment.

Market Contexts:
- CATALYST: News/gaps, high volatility
- MOMENTUM: High volume anomaly + high volatility
- TREND: Strong directional move (ADX > 25)
- RANGE: Low ADX, sideways movement
- NEUTRAL: Default state

Variables:
- ATR%: ATR(14) / Close (volatility measure)
- ADX: ADX(14) (trend strength)
- Volume Z-Score: (VolCurrent - VolMA20) / StdDev(Vol20)
- Gap%: (Open - PrevClose) / PrevClose
- News Flag: Catalyst detected
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketContext(Enum):
    """Market regime classifications"""
    CATALYST = "catalyst"      # News/gaps, explosive moves
    MOMENTUM = "momentum"      # High volume + volatility
    TREND = "trend"           # Strong directional (high ADX, moderate vol)
    RANGE = "range"           # Sideways, low ADX
    NEUTRAL = "neutral"       # Default state


@dataclass
class ContextAnalysis:
    """Complete context analysis for a ticker"""
    symbol: str
    context: MarketContext
    atr_pct: float            # ATR as % of price
    adx: float                # Trend strength
    vol_zscore: float         # Volume anomaly
    gap_pct: float            # Gap percentage
    news_flag: bool           # Catalyst present
    confidence: float         # 0-100, confidence in classification
    metadata: Dict            # Additional context data
    timestamp: datetime

    def __str__(self):
        return (f"Context({self.symbol}): {self.context.value.upper()} "
                f"(conf={self.confidence:.0f}%, ADX={self.adx:.1f}, "
                f"ATR={self.atr_pct:.2%}, VolZ={self.vol_zscore:.1f})")


class ContextEngine:
    """
    Market Context Detection Engine

    Analyzes ticker data to determine market regime and optimal trading approach.
    """

    def __init__(self, config=None):
        self.logger = logging.getLogger(f"{__name__}.ContextEngine")

        # Context detection thresholds - TUNED FOR SMALL CAPS ($1-$25 price range)
        # Small caps are inherently more volatile, need adjusted thresholds
        self.CATALYST_GAP_THRESHOLD = 0.06      # 6% gap (small caps gap larger)
        self.MOMENTUM_VOL_ZSCORE = 2.5          # 2.5σ volume spike (filter noise)
        self.MOMENTUM_ATR_THRESHOLD = 0.08      # 8% ATR (higher volatility baseline)
        self.TREND_ADX_THRESHOLD = 22.0         # 22 ADX (lower threshold for small caps)
        self.TREND_ATR_MAX = 0.10               # Max 10% ATR for clean trend (wider range)
        self.RANGE_ADX_MAX = 18.0               # 18 ADX for weak trend

        # Resistance/Support detection parameters (configurable)
        if config:
            self.resistance_lookback_days = config.getint('GLOBAL', 'resistance_lookback_days', fallback=90)
            self.resistance_clustering_tolerance = config.getfloat('GLOBAL', 'resistance_clustering_tolerance', fallback=0.01)
            self.resistance_min_touches = config.getint('GLOBAL', 'resistance_min_touches', fallback=2)
        else:
            self.resistance_lookback_days = 90
            self.resistance_clustering_tolerance = 0.01
            self.resistance_min_touches = 2

        self.logger.info(
            f"🧠 ContextEngine initialized - SMALL CAP optimized thresholds\n"
            f"   Resistance detection: {self.resistance_lookback_days} days lookback, "
            f"{self.resistance_clustering_tolerance*100:.0f}% clustering tolerance, "
            f"min {self.resistance_min_touches} touches"
        )

    def detect_context(self, ticker_data: Dict) -> ContextAnalysis:
        """
        Detect market context for a ticker

        Args:
            ticker_data: Dict with:
                - symbol: str
                - bars: List of OHLCV bars
                - catalyst_type: Optional str
                - current_price: float

        Returns:
            ContextAnalysis with detected regime and metrics
        """
        try:
            symbol = ticker_data.get('symbol', 'UNKNOWN')
            bars = ticker_data.get('bars', [])
            catalyst_type = ticker_data.get('catalyst_type')
            current_price = ticker_data.get('current_price', 0)

            # EARLY BIRD MODE: Relax bar requirements for pre-market qualified symbols
            is_early_bird = ticker_data.get('early_bird', False) or \
                           ticker_data.get('trading_recommendation', {}).get('early_bird', False)

            min_bars_required = 10 if is_early_bird else 30

            if not bars or len(bars) < min_bars_required:
                if is_early_bird:
                    self.logger.warning(f"🐦 {symbol}: Early Bird with limited bars ({len(bars)}/{min_bars_required}) - creating limited context")
                else:
                    self.logger.warning(f"⚠️ {symbol}: Insufficient bars for context ({len(bars)}/{min_bars_required})")
                return self._create_neutral_context(symbol, "Insufficient data")

            # Debug: Check bar structure
            if len(bars) > 0:
                self.logger.debug(f"🔍 {symbol}: First bar type: {type(bars[0])}, attributes: {dir(bars[0]) if hasattr(bars[0], '__dict__') else 'N/A'}")

            # Calculate all context variables
            atr_pct = self._calculate_atr_percent(bars, current_price)
            adx = self._calculate_adx(bars)
            vol_zscore = self._calculate_volume_zscore(bars)
            gap_pct = self._calculate_gap_percent(bars)

            # Debug: Log calculated values
            self.logger.debug(f"📊 {symbol}: ATR={atr_pct:.4f}, ADX={adx:.2f}, VolZ={vol_zscore:.2f}, Gap={gap_pct:.2%}")
            news_flag = self._detect_news_catalyst(catalyst_type, ticker_data)

            # Classify context based on hierarchical rules
            context, confidence, metadata = self._classify_context(
                atr_pct, adx, vol_zscore, gap_pct, news_flag
            )

            analysis = ContextAnalysis(
                symbol=symbol,
                context=context,
                atr_pct=atr_pct,
                adx=adx,
                vol_zscore=vol_zscore,
                gap_pct=gap_pct,
                news_flag=news_flag,
                confidence=confidence,
                metadata=metadata,
                timestamp=datetime.now()
            )

            self.logger.info(f"🧠 {analysis}")
            return analysis

        except Exception as e:
            self.logger.error(f"❌ Error detecting context for {symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._create_neutral_context(symbol, f"Error: {str(e)}")

    def _classify_context(self, atr_pct: float, adx: float, vol_zscore: float,
                         gap_pct: float, news_flag: bool) -> Tuple[MarketContext, float, Dict]:
        """
        Classify market context using hierarchical rules

        Priority order (highest to lowest):
        1. CATALYST (news or large gap)
        2. MOMENTUM (volume spike + high volatility)
        3. TREND (strong ADX + moderate volatility)
        4. RANGE (low ADX)
        5. NEUTRAL (default)

        Returns:
            Tuple[MarketContext, confidence, metadata]
        """
        metadata = {}

        # RULE 1: CATALYST (highest priority)
        if news_flag or abs(gap_pct) > self.CATALYST_GAP_THRESHOLD:
            confidence = 90.0 if news_flag else 80.0
            metadata['trigger'] = 'news' if news_flag else f'gap_{gap_pct:.1%}'
            metadata['explosive'] = True
            return MarketContext.CATALYST, confidence, metadata

        # RULE 2: MOMENTUM (volume spike + volatility)
        if vol_zscore > self.MOMENTUM_VOL_ZSCORE and atr_pct > self.MOMENTUM_ATR_THRESHOLD:
            confidence = min(70.0 + (vol_zscore - 2.0) * 10, 95.0)
            metadata['trigger'] = f'vol_spike_{vol_zscore:.1f}σ'
            metadata['explosive'] = atr_pct > 0.08
            return MarketContext.MOMENTUM, confidence, metadata

        # RULE 3: TREND (strong directional, moderate volatility)
        if adx > self.TREND_ADX_THRESHOLD:
            # Clean trend has moderate volatility
            if atr_pct < self.TREND_ATR_MAX:
                confidence = min(60.0 + (adx - 25) * 2, 85.0)
                metadata['trigger'] = f'clean_trend_ADX{adx:.0f}'
                metadata['clean_trend'] = True
                return MarketContext.TREND, confidence, metadata
            else:
                # Choppy trend (high ADX + high volatility)
                confidence = 50.0
                metadata['trigger'] = f'choppy_trend_ADX{adx:.0f}'
                metadata['choppy'] = True
                return MarketContext.TREND, confidence, metadata

        # RULE 4: RANGE (low ADX)
        if adx < self.RANGE_ADX_MAX:
            confidence = 55.0
            metadata['trigger'] = f'sideways_ADX{adx:.0f}'
            metadata['mean_reversion'] = True
            return MarketContext.RANGE, confidence, metadata

        # RULE 5: NEUTRAL (default)
        confidence = 40.0
        metadata['trigger'] = 'no_clear_regime'
        return MarketContext.NEUTRAL, confidence, metadata

    def _calculate_atr_percent(self, bars: List, current_price: float) -> float:
        """Calculate ATR as percentage of current price"""
        try:
            if len(bars) < 14:
                return 0.0

            # Helper to get bar value (handles both dict and object format)
            def get_bar_value(bar, key):
                if isinstance(bar, dict):
                    return bar.get(key, 0)
                return getattr(bar, key, 0)

            # Calculate True Range for last 14 bars
            trs = []
            for i in range(len(bars) - 14, len(bars)):
                high = get_bar_value(bars[i], 'high')
                low = get_bar_value(bars[i], 'low')
                prev_close = get_bar_value(bars[i-1], 'close') if i > 0 else get_bar_value(bars[i], 'close')

                if high == 0 or low == 0:
                    continue

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                trs.append(tr)

            if not trs:
                return 0.0

            atr = np.mean(trs)
            atr_pct = atr / current_price if current_price > 0 else 0.0

            return atr_pct

        except Exception as e:
            self.logger.warning(f"Error calculating ATR: {e}")
            return 0.0

    def _calculate_adx(self, bars: List, period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)"""
        try:
            if len(bars) < period + 1:
                return 0.0

            # Helper to get bar value (handles both dict and object format)
            def get_bar_value(bar, key):
                if isinstance(bar, dict):
                    return bar.get(key, 0)
                return getattr(bar, key, 0)

            # Calculate +DM and -DM
            plus_dm = []
            minus_dm = []

            for i in range(1, len(bars)):
                high = get_bar_value(bars[i], 'high')
                high_prev = get_bar_value(bars[i-1], 'high')
                low = get_bar_value(bars[i], 'low')
                low_prev = get_bar_value(bars[i-1], 'low')

                if high == 0 or low == 0:
                    continue

                high_diff = high - high_prev
                low_diff = low_prev - low

                if high_diff > low_diff and high_diff > 0:
                    plus_dm.append(high_diff)
                    minus_dm.append(0)
                elif low_diff > high_diff and low_diff > 0:
                    plus_dm.append(0)
                    minus_dm.append(low_diff)
                else:
                    plus_dm.append(0)
                    minus_dm.append(0)

            # Calculate TR
            trs = []
            for i in range(1, len(bars)):
                high = get_bar_value(bars[i], 'high')
                low = get_bar_value(bars[i], 'low')
                prev_close = get_bar_value(bars[i-1], 'close')

                if high == 0 or low == 0:
                    continue

                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                trs.append(tr)

            # Smooth with EMA
            if len(plus_dm) < period or len(trs) < period:
                return 0.0

            smoothed_plus_dm = np.mean(plus_dm[-period:])
            smoothed_minus_dm = np.mean(minus_dm[-period:])
            smoothed_tr = np.mean(trs[-period:])

            if smoothed_tr == 0:
                return 0.0

            # Calculate DI+ and DI-
            di_plus = (smoothed_plus_dm / smoothed_tr) * 100
            di_minus = (smoothed_minus_dm / smoothed_tr) * 100

            # Calculate DX
            di_sum = di_plus + di_minus
            if di_sum == 0:
                return 0.0

            dx = abs(di_plus - di_minus) / di_sum * 100

            # ADX is EMA of DX (simplified: just return DX for now)
            return dx

        except Exception as e:
            self.logger.warning(f"Error calculating ADX: {e}")
            return 0.0

    def _calculate_volume_zscore(self, bars: List, period: int = 20) -> float:
        """Calculate volume Z-score (anomaly detection)"""
        try:
            if len(bars) < period + 1:
                return 0.0

            # Helper to get bar value (handles both dict and object format)
            def get_bar_value(bar, key):
                if isinstance(bar, dict):
                    return bar.get(key, 0)
                return getattr(bar, key, 0)

            volumes = [get_bar_value(bar, 'volume') for bar in bars[-period-1:]]
            volumes = [v for v in volumes if v > 0]  # Filter out zeros

            if len(volumes) < period:
                return 0.0

            current_vol = volumes[-1]
            historical_vols = volumes[:-1]

            mean_vol = np.mean(historical_vols)
            std_vol = np.std(historical_vols)

            if std_vol == 0:
                return 0.0

            zscore = (current_vol - mean_vol) / std_vol
            return zscore

        except Exception as e:
            self.logger.warning(f"Error calculating volume Z-score: {e}")
            return 0.0

    def _calculate_gap_percent(self, bars: List) -> float:
        """Calculate gap percentage (open vs previous close)"""
        try:
            if len(bars) < 2:
                return 0.0

            # Helper to get bar value (handles both dict and object format)
            def get_bar_value(bar, key):
                if isinstance(bar, dict):
                    return bar.get(key, 0)
                return getattr(bar, key, 0)

            current_open = get_bar_value(bars[-1], 'open')
            prev_close = get_bar_value(bars[-2], 'close')

            if prev_close == 0:
                return 0.0

            gap_pct = (current_open - prev_close) / prev_close
            return gap_pct

        except Exception as e:
            self.logger.warning(f"Error calculating gap: {e}")
            return 0.0

    def _detect_news_catalyst(self, catalyst_type: Optional[str],
                             ticker_data: Dict) -> bool:
        """Detect if ticker has news catalyst"""
        try:
            # Check catalyst_type field
            if catalyst_type and catalyst_type not in ['TECHNICAL', 'NONE', None]:
                return True

            # Check for major catalyst flags
            major_catalysts = ['FDA', 'EARNINGS', 'M&A', 'BREAKTHROUGH', 'HALT']
            if catalyst_type in major_catalysts:
                return True

            # Could also check quality_score or other metadata
            quality_score = ticker_data.get('quality_score', 0)
            if quality_score > 80:  # Very high quality often means catalyst
                return True

            return False

        except Exception as e:
            self.logger.debug(f"Error detecting news catalyst: {e}")
            return False

    def _create_neutral_context(self, symbol: str, reason: str) -> ContextAnalysis:
        """Create neutral context (fallback)"""
        return ContextAnalysis(
            symbol=symbol,
            context=MarketContext.NEUTRAL,
            atr_pct=0.0,
            adx=0.0,
            vol_zscore=0.0,
            gap_pct=0.0,
            news_flag=False,
            confidence=0.0,
            metadata={'reason': reason},
            timestamp=datetime.now()
        )

    def analyze_daily_potential(self, ticker_data: Dict) -> Dict[str, any]:
        """
        Analiza potencial de movimiento multi-day en timeframe diario

        Determina si un ticker tiene espacio técnico para mantener posiciones
        durante múltiples días (SWING/SWING_SHORT) o solo intraday.

        Args:
            ticker_data: Dict with:
                - symbol: str
                - bars_daily: List of daily OHLCV bars (min 60 days recommended)
                - current_price: float

        Returns:
            Dict with:
                - can_swing: bool (3-10 days holding potential)
                - can_swing_short: bool (1-3 days holding potential)
                - distance_to_resistance: float (% to nearest resistance)
                - distance_to_support: float (% to nearest support)
                - daily_trend_strength: float (0-100)
                - rsi_daily: float (RSI on daily timeframe)
                - macd_histogram: float (MACD histogram value)
                - consecutive_days_up: int (days closing higher)
                - reasons: List[str] (why can/cannot swing)
        """
        try:
            symbol = ticker_data.get('symbol', 'UNKNOWN')
            bars_daily = ticker_data.get('bars_daily', [])
            current_price = ticker_data.get('current_price', 0)

            # Validate input
            if not bars_daily or len(bars_daily) < 30:
                return {
                    'can_swing': False,
                    'can_swing_short': False,
                    'distance_to_resistance': 0,
                    'distance_to_support': 0,
                    'daily_trend_strength': 0,
                    'rsi_daily': 50,
                    'macd_histogram': 0,
                    'consecutive_days_up': 0,
                    'reasons': ['Insufficient daily bars for analysis']
                }

            if current_price == 0:
                current_price = bars_daily[-1].close

            # Calculate daily indicators
            rsi_daily = self._calculate_rsi(bars_daily, period=14)
            macd_hist = self._calculate_macd_histogram(bars_daily)
            adx_daily = self._calculate_adx(bars_daily, period=14)

            # Find support and resistance levels
            resistance = self._find_nearest_resistance(bars_daily, current_price)
            support = self._find_nearest_support(bars_daily, current_price)

            distance_to_resistance = ((resistance - current_price) / current_price) * 100 if resistance > 0 else 100
            distance_to_support = ((current_price - support) / current_price) * 100 if support > 0 else 100

            # Count consecutive bullish days
            consecutive_days_up = self._count_consecutive_days(bars_daily, direction='up')

            # Calculate daily trend strength (0-100)
            daily_trend_strength = min(100, adx_daily * 2)  # ADX 50 = 100% strength

            # Build reasons list
            reasons = []

            # Check for Strong Catalyst
            catalyst_type = ticker_data.get('catalyst_type', 'NONE')
            strong_catalysts = ['M&A', 'FDA', 'EARNINGS', 'BREAKTHROUGH', 'HALT', 'BIOTECH_NEWS']
            is_strong_catalyst = catalyst_type in strong_catalysts
            
            # 52-Week High/Low Calculation (Needs ~252 bars, we fetch 1 year now)
            high_52w = max([b.high for b in bars_daily[-252:]]) if len(bars_daily) > 0 else current_price
            low_52w = min([b.low for b in bars_daily[-252:]]) if len(bars_daily) > 0 else current_price
            
            # Blue Sky / 52-Week Breakout Detection
            # We consider it a "Blue Sky Breakout" setup if price is within 5% of 52w High
            dist_to_52w_high_pct = ((high_52w - current_price) / current_price) * 100
            is_near_52w_high = dist_to_52w_high_pct < 5.0
            
            if is_near_52w_high:
                self.logger.info(f"🌤️ {symbol}: BLUE SKY SETUP - Near 52-week high ({high_52w:.2f}). Resistance checks relaxed.")

            # Adjust thresholds based on catalyst OR Blue Sky
            # If strong catalyst OR Blue Sky, we ignore prior trend (ADX) and accept tighter resistance
            is_super_setup = is_strong_catalyst or is_near_52w_high
            
            min_adx = 10.0 if is_super_setup else 22.0
            min_dist_res_swing = 0.0 if is_near_52w_high else (5.0 if is_strong_catalyst else 15.0) 
            # Note: 0.0 distance for Blue Sky because the "resistance" IS the breakout level we want to cross
            
            min_dist_res_short = 3.0 if is_strong_catalyst else 8.0
            
            if is_strong_catalyst:
                self.logger.info(f"🚀 {symbol}: Strong Catalyst detected ({catalyst_type}). Relaxing Swing criteria (ADX>{min_adx})")

            # SWING VALIDATION (3-10 days holding)
            swing_checks = {
                'rsi_ok': rsi_daily < 70,
                'resistance_space': distance_to_resistance > min_dist_res_swing,
                'macd_positive': macd_hist > 0,
                'not_extended': consecutive_days_up < 5,
                'strong_trend': adx_daily > min_adx
            }

            can_swing = all(swing_checks.values())

            if not swing_checks['rsi_ok']:
                reasons.append(f"RSI daily overbought ({rsi_daily:.1f} >= 70)")
            if not swing_checks['resistance_space']:
                reasons.append(f"Too close to resistance ({distance_to_resistance:.1f}% < {min_dist_res_swing}%)")
            if not swing_checks['macd_positive']:
                reasons.append(f"MACD histogram negative ({macd_hist:.3f})")
            if not swing_checks['not_extended']:
                reasons.append(f"Extended run ({consecutive_days_up} consecutive up days)")
            if not swing_checks['strong_trend']:
                reasons.append(f"Weak daily trend (ADX {adx_daily:.1f} < {min_adx})")

            # SWING_SHORT VALIDATION (1-3 days holding) - more relaxed
            swing_short_checks = {
                'rsi_ok': rsi_daily < 75,
                'resistance_space': distance_to_resistance > min_dist_res_short,
                'macd_not_extreme': macd_hist > -0.5,
                'not_too_extended': consecutive_days_up < 7
            }

            can_swing_short = all(swing_short_checks.values())

            if is_near_52w_high:
                reasons.append(f"🌤️ BLUE SKY POTENTIAL (Near 52w High ${high_52w:.2f})")
                # Force Swing Enable for Blue Sky if RSI isn't completely blown out
                if rsi_daily < 80:
                    can_swing = True
                    reasons.append("✅ FORCE ACCEPT: 52-Week High Breakout Play")

            if can_swing:
                reasons.append("✅ Can hold SWING (3-10 days)")
            elif can_swing_short:
                reasons.append("✅ Can hold SWING_SHORT (1-3 days)")
            else:
                reasons.append("❌ Intraday only - no multi-day potential")

            result = {
                'can_swing': can_swing,
                'can_swing_short': can_swing_short,
                'distance_to_resistance': distance_to_resistance,
                'distance_to_support': distance_to_support,
                'daily_trend_strength': daily_trend_strength,
                'rsi_daily': rsi_daily,
                'macd_histogram': macd_hist,
                'consecutive_days_up': consecutive_days_up,
                'is_52_week_high': is_near_52w_high,
                'high_52w': high_52w,
                'reasons': reasons
            }

            self.logger.debug(
                f"📊 {symbol} Daily Analysis: "
                f"swing={can_swing}, swing_short={can_swing_short}, "
                f"RSI={rsi_daily:.1f}, resistance={distance_to_resistance:.1f}%, "
                f"BlueSky={is_near_52w_high}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing daily potential for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                'can_swing': False,
                'can_swing_short': False,
                'distance_to_resistance': 0,
                'distance_to_support': 0,
                'daily_trend_strength': 0,
                'rsi_daily': 50,
                'macd_histogram': 0,
                'consecutive_days_up': 0,
                'is_52_week_high': False,
                'reasons': [f'Error: {str(e)}']
            }

    def _calculate_rsi(self, bars: List, period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        try:
            if len(bars) < period + 1:
                return 50.0

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

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.debug(f"Error calculating RSI: {e}")
            return 50.0

    def _calculate_macd_histogram(self, bars: List) -> float:
        """Calculate MACD histogram (MACD - Signal)"""
        try:
            if len(bars) < 26:
                return 0.0

            closes = [bar.close for bar in bars]

            # EMA 12, 26, 9
            ema12 = self._calculate_ema(closes, 12)
            ema26 = self._calculate_ema(closes, 26)

            macd = ema12 - ema26

            # Signal line (EMA 9 of MACD - simplified)
            signal = macd * 0.9  # Simplified signal approximation

            histogram = macd - signal

            return histogram

        except Exception as e:
            self.logger.debug(f"Error calculating MACD histogram: {e}")
            return 0.0

    def _calculate_ema(self, values: List[float], period: int) -> float:
        """Calculate EMA (Exponential Moving Average)"""
        try:
            if len(values) < period:
                return np.mean(values)

            multiplier = 2 / (period + 1)
            ema = np.mean(values[:period])  # Start with SMA

            for price in values[period:]:
                ema = (price - ema) * multiplier + ema

            return ema

        except Exception as e:
            self.logger.debug(f"Error calculating EMA: {e}")
            return 0.0

    def _find_nearest_resistance(self, bars: List, current_price: float) -> float:
        """
        Find nearest SIGNIFICANT resistance level above current price

        Uses zone clustering algorithm to detect real resistance areas
        (multiple touches) rather than isolated highs.

        Improvements over old version:
        - Analyzes 90 days instead of 30 (detects historical resistances)
        - Uses clustering to find resistance ZONES (not isolated highs)
        - Counts touches to determine significance
        - Prioritizes stronger resistances (more touches)

        Returns:
            Price of nearest significant resistance, or current_price * 1.20 if none found
        """
        try:
            if len(bars) < 20:
                return current_price * 1.20  # Default 20% above

            # Use configurable lookback days for historical resistance detection
            lookback_days = min(self.resistance_lookback_days, len(bars))
            historical_bars = bars[-lookback_days:]

            # Extract all highs and their indices
            highs_data = [(i, bar.high) for i, bar in enumerate(historical_bars)]

            # Cluster highs into resistance zones (configurable tolerance)
            resistance_zones = self._cluster_price_levels(
                [h[1] for h in highs_data],
                tolerance_pct=self.resistance_clustering_tolerance
            )

            # Filter zones above current price
            zones_above = [
                zone for zone in resistance_zones
                if zone['price'] > current_price
            ]

            if not zones_above:
                return current_price * 1.20  # Default 20% above

            # Sort by significance (touches DESC, then proximity ASC)
            # Prioritize zones with more touches (stronger resistance)
            zones_above.sort(key=lambda z: (-z['touches'], z['price']))

            # Get most significant zone above price
            nearest_zone = zones_above[0]

            # Log for debugging
            self.logger.debug(
                f"Resistance found: ${nearest_zone['price']:.2f} "
                f"({nearest_zone['touches']} touches, "
                f"{((nearest_zone['price'] - current_price) / current_price * 100):.1f}% away)"
            )

            return nearest_zone['price']

        except Exception as e:
            self.logger.debug(f"Error finding resistance: {e}")
            return current_price * 1.20

    def _find_nearest_support(self, bars: List, current_price: float) -> float:
        """
        Find nearest SIGNIFICANT support level below current price

        Uses zone clustering algorithm to detect real support areas
        (multiple touches) rather than isolated lows.

        Improvements over old version:
        - Analyzes 90 days instead of 30 (detects historical supports)
        - Uses clustering to find support ZONES (not isolated lows)
        - Counts touches to determine significance
        - Prioritizes stronger supports (more touches)

        Returns:
            Price of nearest significant support, or current_price * 0.85 if none found
        """
        try:
            if len(bars) < 20:
                return current_price * 0.85  # Default 15% below

            # Use configurable lookback days for historical support detection
            lookback_days = min(self.resistance_lookback_days, len(bars))
            historical_bars = bars[-lookback_days:]

            # Extract all lows
            lows_data = [(i, bar.low) for i, bar in enumerate(historical_bars)]

            # Cluster lows into support zones (configurable tolerance)
            support_zones = self._cluster_price_levels(
                [l[1] for l in lows_data],
                tolerance_pct=self.resistance_clustering_tolerance
            )

            # Filter zones below current price
            zones_below = [
                zone for zone in support_zones
                if zone['price'] < current_price
            ]

            if not zones_below:
                return current_price * 0.85  # Default 15% below

            # Sort by significance (touches DESC, then proximity DESC for supports)
            # Prioritize zones with more touches (stronger support)
            zones_below.sort(key=lambda z: (-z['touches'], -z['price']))

            # Get most significant zone below price
            nearest_zone = zones_below[0]

            # Log for debugging
            self.logger.debug(
                f"Support found: ${nearest_zone['price']:.2f} "
                f"({nearest_zone['touches']} touches, "
                f"{((current_price - nearest_zone['price']) / current_price * 100):.1f}% away)"
            )

            return nearest_zone['price']

        except Exception as e:
            self.logger.debug(f"Error finding support: {e}")
            return current_price * 0.85

    def _cluster_price_levels(self, prices: List[float], tolerance_pct: float = 0.01) -> List[Dict]:
        """
        Cluster price levels into zones using tolerance-based grouping

        Algorithm:
        1. Sort all prices
        2. Group prices that are within tolerance_pct of each other
        3. Calculate average price for each zone
        4. Count touches (number of prices in zone)
        5. Return zones sorted by touches (significance)

        Args:
            prices: List of price levels (highs or lows)
            tolerance_pct: Clustering tolerance as percentage (0.01 = 1%)

        Returns:
            List of zones: [{'price': avg_price, 'touches': count}, ...]
            Sorted by touches DESC (most significant first)

        Example:
            prices = [10.0, 10.1, 10.05, 15.0, 15.2]
            tolerance = 0.01 (1%)

            Zone 1: [10.0, 10.1, 10.05] -> avg=10.05, touches=3
            Zone 2: [15.0, 15.2] -> avg=15.1, touches=2

            Returns: [
                {'price': 10.05, 'touches': 3},
                {'price': 15.1, 'touches': 2}
            ]
        """
        try:
            if not prices or len(prices) == 0:
                return []

            # Remove duplicates and sort
            unique_prices = sorted(set(prices))

            if len(unique_prices) == 0:
                return []

            # Cluster prices into zones
            zones = []
            current_zone = [unique_prices[0]]

            for price in unique_prices[1:]:
                # Calculate tolerance from current zone average
                zone_avg = sum(current_zone) / len(current_zone)
                tolerance = zone_avg * tolerance_pct

                # If price is within tolerance, add to current zone
                if abs(price - zone_avg) <= tolerance:
                    current_zone.append(price)
                else:
                    # Save current zone and start new one
                    zones.append({
                        'price': sum(current_zone) / len(current_zone),
                        'touches': len(current_zone)
                    })
                    current_zone = [price]

            # Don't forget last zone
            if current_zone:
                zones.append({
                    'price': sum(current_zone) / len(current_zone),
                    'touches': len(current_zone)
                })

            # Sort by touches (significance) DESC
            zones.sort(key=lambda z: -z['touches'])

            return zones

        except Exception as e:
            self.logger.debug(f"Error clustering price levels: {e}")
            return []

    def _count_consecutive_days(self, bars: List, direction: str = 'up') -> int:
        """Count consecutive days closing in same direction"""
        try:
            if len(bars) < 2:
                return 0

            count = 0

            for i in range(len(bars) - 1, 0, -1):
                if direction == 'up':
                    if bars[i].close > bars[i-1].close:
                        count += 1
                    else:
                        break
                else:  # down
                    if bars[i].close < bars[i-1].close:
                        count += 1
                    else:
                        break

            return count

        except Exception as e:
            self.logger.debug(f"Error counting consecutive days: {e}")
            return 0


# Singleton instance
_context_engine_instance = None

def get_context_engine(config=None) -> ContextEngine:
    """
    Get singleton ContextEngine instance

    Args:
        config: Optional config object with resistance detection parameters

    Returns:
        ContextEngine singleton instance
    """
    global _context_engine_instance
    if _context_engine_instance is None:
        _context_engine_instance = ContextEngine(config=config)
    return _context_engine_instance
