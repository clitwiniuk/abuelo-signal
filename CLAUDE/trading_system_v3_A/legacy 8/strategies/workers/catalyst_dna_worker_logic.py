"""
Catalyst DNA Worker Logic (LONG Only)

ADAPTED FROM: Market DNA Strategy (Large-cap tape reading)
OPTIMIZED FOR: Smallcaps with scanner catalyst integration

PHILOSOPHY:
- Trading based on REAL AGGRESSION (buyers stepping in), not lagging indicators
- DNA Points = VWAP (institutional positioning level)
- Aggression Proxies = Volume surge + Quality score + Candle size
- Catalyst = Scanner quality score >70 (strong news/catalyst)

STRATEGY EDGE:
- Win Rate Target: 70-75%
- TP Target: 5-10%
- Frequency: 5-10 setups/day
- R:R: 3:1 minimum (tight stops at VWAP)

ENTRY RULES (ALL must be TRUE):
1. Quality Score ≥ min_quality_score (strong catalyst = aggression entering)
2. Pullback to VWAP zone (DNA level test)
3. Volume surge ≥ min_volume_surge_ratio (buyers stepping in aggressively)
4. Green candle ≥ min_candle_size_atr (buyers overwhelming sellers)
5. Price action confirms bounce (close > open on confirmation candle)

EXIT RULES:
- Take Profit: +5-10% (scaled based on volatility)
- Stop Loss: -2-3% below VWAP (tight risk at DNA level)
- Trailing Stop: Activates at +8%, trails at -3%
- Time Stop: Max 2 hours (intraday only)

TODOS LOS PARÁMETROS SON CONFIGURABLES EN CONFIG.INI
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np

from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class CatalystDNAWorkerLogic(BaseWorkerLogic):
    """
    Catalyst DNA Worker - Market DNA adapted for smallcaps (LONG only)

    Core Concept:
    - DNA Point = VWAP (where institutions are positioned)
    - Aggression = Strong catalyst + Volume surge + Large green candles
    - Entry = When buyers aggressively defend VWAP on pullback

    This is NOT tape reading (smallcaps don't have reliable Level II).
    Instead, we use volume, candle size, and quality score as aggression proxies.
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Anti-overtrading
        self.traded_symbols_today = set()
        self._last_reset_date = None

        # ===== READ ALL PARAMS FROM CONFIG.INI =====
        if config:
            section = 'CATALYST_DNA_WORKER'

            # ===== BASIC FILTERS =====
            self.min_price = config.getfloat(section, 'min_price', fallback=1.0)
            self.max_price = config.getfloat(section, 'max_price', fallback=15.0)

            # ===== CATALYST FILTER (DNA Strategy: Strong catalyst = Aggression) =====
            self.min_quality_score = config.getfloat(section, 'min_quality_score', fallback=70.0)

            # ===== DNA POINT (VWAP Zone) =====
            self.vwap_pullback_min_pct = config.getfloat(section, 'vwap_pullback_min_pct', fallback=0.5)
            self.vwap_pullback_max_pct = config.getfloat(section, 'vwap_pullback_max_pct', fallback=3.0)
            self.vwap_zone_buffer_pct = config.getfloat(section, 'vwap_zone_buffer_pct', fallback=1.0)

            # ===== AGGRESSION DETECTION =====
            # Volume aggression (buyers stepping in)
            self.min_volume_surge_ratio = config.getfloat(section, 'min_volume_surge_ratio', fallback=2.0)
            self.volume_lookback_bars = config.getint(section, 'volume_lookback_bars', fallback=20)

            # Candle size aggression (buyers overwhelming sellers)
            self.min_candle_size_atr = config.getfloat(section, 'min_candle_size_atr', fallback=1.5)
            self.atr_period = config.getint(section, 'atr_period', fallback=14)

            # Bounce confirmation
            self.min_bounce_candles = config.getint(section, 'min_bounce_candles', fallback=1)
            self.require_closing_strength = config.getboolean(section, 'require_closing_strength', fallback=True)

            # ===== VWAP TREND FILTER =====
            self.require_vwap_uptrend = config.getboolean(section, 'require_vwap_uptrend', fallback=True)
            self.vwap_slope_lookback = config.getint(section, 'vwap_slope_lookback', fallback=10)
            self.min_vwap_slope = config.getfloat(section, 'min_vwap_slope', fallback=0.0)

            # ===== ANTI-OVERTRADING =====
            self.max_trades_per_symbol_per_day = config.getint(section, 'max_trades_per_symbol_per_day', fallback=1)
            self.max_positions_per_day = config.getint(section, 'max_positions_per_day', fallback=10)

            # ===== RISK MANAGEMENT (WorkerStopManager) =====
            self.stop_manager = create_worker_stop_manager(config, section)

        else:
            # Fallback defaults
            self.min_price = 1.0
            self.max_price = 15.0
            self.min_quality_score = 70.0

            self.vwap_pullback_min_pct = 0.5
            self.vwap_pullback_max_pct = 3.0
            self.vwap_zone_buffer_pct = 1.0

            self.min_volume_surge_ratio = 2.0
            self.volume_lookback_bars = 20
            self.min_candle_size_atr = 1.5
            self.atr_period = 14

            self.min_bounce_candles = 1
            self.require_closing_strength = True

            self.require_vwap_uptrend = True
            self.vwap_slope_lookback = 10
            self.min_vwap_slope = 0.0

            self.max_trades_per_symbol_per_day = 1
            self.max_positions_per_day = 10

            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,      # Tight stop below VWAP
                take_profit_pct=8.0,    # Conservative TP (5-10% range)
                trailing_activation=8.0, # Let winners run
                trailing_distance=3.0,   # Trail with room
                max_position_hours=2.0   # Intraday only
            ))

        self.logger.info(f"🧬 Catalyst DNA Worker (LONG) configured:")
        self.logger.info(f"   Price Range: ${self.min_price:.2f} - ${self.max_price:.2f}")
        self.logger.info(f"   Min Quality Score: {self.min_quality_score:.0f} (strong catalyst required)")
        self.logger.info(f"   VWAP Pullback: {self.vwap_pullback_min_pct:.1f}-{self.vwap_pullback_max_pct:.1f}%")
        self.logger.info(f"   Volume Surge: >{self.min_volume_surge_ratio:.1f}x")
        self.logger.info(f"   Candle Size: >{self.min_candle_size_atr:.1f}x ATR")
        self.logger.info(f"   Anti-Overtrading: Max {self.max_positions_per_day} positions/day")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def should_enter(self, opportunity: Dict) -> bool:
        """
        Determines if we should enter LONG now

        DNA Strategy Logic:
        1. Strong catalyst (quality score) = Aggression entering market
        2. Pullback to VWAP (DNA level) = Testing institutional support
        3. Volume surge = Buyers stepping in aggressively
        4. Large green candle = Buyers overwhelming sellers
        5. Enter when all align = High conviction trade
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # ====
            # STEP 0: Anti-overtrading
            # ====
            self._reset_daily_tracking()

            if symbol in self.traded_symbols_today:
                self.logger.debug(f"⚪ {symbol}: Already traded today")
                return False

            if len(self.traded_symbols_today) >= self.max_positions_per_day:
                self.logger.debug(f"⚪ {symbol}: Max positions per day reached ({self.max_positions_per_day})")
                return False

            # ====
            # STEP 1: Time check
            # ====
            is_valid_time, current_decimal_time = self.is_within_entry_hours(symbol, opportunity.get('timestamp'))
            if not is_valid_time:
                self.logger.debug(f"⚪ {symbol}: Outside trading hours")
                return False

            # ====
            # STEP 2: Get bars
            # ====
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 30:
                self.logger.debug(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0} < 30)")
                return False

            # ====
            # STEP 3: ODS filters
            # ====
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)
            if not is_ods_allowed:
                return False

            if 'confidence' in opportunity:
                opportunity['confidence'] *= confidence_boost

            # ====
            # STEP 4: Check duplicate positions
            # ====
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.warning(f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()}")
                return False

            # ====
            # STEP 5: Get market data
            # ====
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            # ====
            # STEP 6: Basic filters
            # ====
            if not (self.min_price <= current_price <= self.max_price):
                self.logger.debug(f"⚪ {symbol}: Price ${current_price:.2f} outside range")
                return False

            # ====
            # STEP 7: CATALYST FILTER (DNA: Strong catalyst = Aggression)
            # ====
            if quality_score < self.min_quality_score:
                self.logger.debug(f"⚪ {symbol}: Quality {quality_score:.0f} < {self.min_quality_score:.0f} (weak catalyst)")
                return False

            self.logger.info(f"✅ {symbol}: STRONG CATALYST - Quality={quality_score:.0f} (>={self.min_quality_score:.0f})")

            # ====
            # STEP 8: Calculate VWAP (DNA Point)
            # ====
            vwap_data = self._calculate_vwap(bars)
            if not vwap_data or len(vwap_data) == 0:
                self.logger.debug(f"⚪ {symbol}: Could not calculate VWAP")
                return False

            vwap_current = vwap_data[-1]

            # Check VWAP uptrend (optional)
            if self.require_vwap_uptrend:
                vwap_slope = self._calculate_vwap_slope(vwap_data, self.vwap_slope_lookback)
                if vwap_slope < self.min_vwap_slope:
                    self.logger.debug(f"⚪ {symbol}: VWAP downtrend (slope={vwap_slope:.6f})")
                    return False

            # ====
            # STEP 9: Check if we're in VWAP pullback zone (DNA Level Test)
            # ====
            distance_from_vwap = ((current_price - vwap_current) / vwap_current) * 100

            # We want to be NEAR vwap (pullback zone)
            if distance_from_vwap < -self.vwap_zone_buffer_pct:
                self.logger.debug(f"⚪ {symbol}: Too far below VWAP ({distance_from_vwap:.2f}% < -{self.vwap_zone_buffer_pct:.1f}%)")
                return False

            if distance_from_vwap > self.vwap_zone_buffer_pct:
                self.logger.debug(f"⚪ {symbol}: Too far above VWAP ({distance_from_vwap:.2f}% > {self.vwap_zone_buffer_pct:.1f}%)")
                return False

            self.logger.info(f"✅ {symbol}: AT DNA LEVEL - Distance from VWAP={distance_from_vwap:.2f}% (within ±{self.vwap_zone_buffer_pct:.1f}%)")

            # ====
            # STEP 10: AGGRESSION DETECTION - Volume Surge
            # ====
            avg_volume = self._calculate_average_volume(bars, self.volume_lookback_bars)
            last_bar_volume = bars[-1].volume if hasattr(bars[-1], 'volume') else 0
            volume_ratio = last_bar_volume / avg_volume if avg_volume > 0 else 0

            if volume_ratio < self.min_volume_surge_ratio:
                self.logger.debug(f"⚪ {symbol}: Volume ratio {volume_ratio:.2f}x < {self.min_volume_surge_ratio:.1f}x (no aggression)")
                return False

            self.logger.info(f"✅ {symbol}: VOLUME AGGRESSION - {volume_ratio:.2f}x (buyers stepping in)")

            # ====
            # STEP 11: AGGRESSION DETECTION - Candle Size
            # ====
            atr = self._calculate_atr(bars, self.atr_period)
            if not atr or atr == 0:
                self.logger.debug(f"⚪ {symbol}: Could not calculate ATR")
                return False

            last_bar = bars[-1]
            candle_size = abs(last_bar.close - last_bar.open)
            candle_size_atr = candle_size / atr if atr > 0 else 0

            if candle_size_atr < self.min_candle_size_atr:
                self.logger.debug(f"⚪ {symbol}: Candle size {candle_size_atr:.2f}x ATR < {self.min_candle_size_atr:.1f}x (weak aggression)")
                return False

            self.logger.info(f"✅ {symbol}: CANDLE AGGRESSION - {candle_size_atr:.2f}x ATR (buyers overwhelming)")

            # ====
            # STEP 12: Bounce Confirmation
            # ====
            green_bars_count = self._count_consecutive_green_bars(bars)
            if green_bars_count < self.min_bounce_candles:
                self.logger.debug(f"⚪ {symbol}: Only {green_bars_count} green bars (< {self.min_bounce_candles})")
                return False

            # Check closing strength (close in upper half of candle)
            if self.require_closing_strength:
                candle_range = last_bar.high - last_bar.low
                close_position = (last_bar.close - last_bar.low) / candle_range if candle_range > 0 else 0
                if close_position < 0.6:  # Close in upper 40% of candle
                    self.logger.debug(f"⚪ {symbol}: Weak close (position={close_position:.2f} < 0.6)")
                    return False

            self.logger.info(f"✅ {symbol}: BOUNCE CONFIRMED - {green_bars_count} green bars with strong close")

            # ====
            # ALL CONDITIONS MET - ENTRY!
            # ====
            self.logger.info(
                f"🧬 {symbol}: CATALYST DNA ENTRY (LONG) - "
                f"Quality={quality_score:.0f}, "
                f"VWAP_dist={distance_from_vwap:.2f}%, "
                f"Vol={volume_ratio:.2f}x, "
                f"Candle={candle_size_atr:.2f}x ATR, "
                f"Bounce={green_bars_count} bars"
            )

            # Track entry
            self.traded_symbols_today.add(symbol)

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_enter: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def should_exit(self, symbol: str, position: Dict, current_price: float, bars: Any) -> tuple[bool, str]:
        """
        Determines if we should exit position

        Uses WorkerStopManager for exits:
        - Take profit: 5-10%
        - Stop loss: -2-3% (tight at VWAP)
        - Trailing stop: Activates at +8%, trails -3%
        - Time stop: 2 hours max
        """
        try:
            # Use WorkerStopManager
            should_exit, reason = self.stop_manager.should_exit(
                symbol=symbol,
                entry_price=position['entry_price'],
                current_price=current_price,
                entry_time=position['entry_time'],
                highest_price=position.get('highest_price', position['entry_price']),
                worker_name=self.worker_name
            )

            if should_exit:
                self.logger.info(f"🔔 {symbol}: EXIT signal - {reason}")
                return True, reason

            return False, ""

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_exit: {e}")
            return False, ""

    def _reset_daily_tracking(self):
        """Reset daily tracking at market open"""
        from datetime import date
        today = date.today()

        if self._last_reset_date != today:
            self.traded_symbols_today.clear()
            self._last_reset_date = today
            self.logger.info(f"🔄 Daily tracking reset for {today}")

    def _calculate_vwap(self, bars) -> Optional[list]:
        """Calculate VWAP (DNA Point)"""
        try:
            if not bars:
                return None

            vwap_values = []
            cumulative_tpv = 0
            cumulative_volume = 0

            for bar in bars:
                typical_price = (bar.high + bar.low + bar.close) / 3
                tpv = typical_price * bar.volume

                cumulative_tpv += tpv
                cumulative_volume += bar.volume

                if cumulative_volume > 0:
                    vwap = cumulative_tpv / cumulative_volume
                    vwap_values.append(vwap)
                else:
                    vwap_values.append(typical_price)

            return vwap_values

        except Exception as e:
            self.logger.error(f"Error calculating VWAP: {e}")
            return None

    def _calculate_vwap_slope(self, vwap_data: list, lookback: int) -> float:
        """Calculate VWAP slope (trend)"""
        try:
            if len(vwap_data) < lookback:
                return 0.0

            recent_vwap = vwap_data[-lookback:]
            x = np.arange(len(recent_vwap))
            slope = np.polyfit(x, recent_vwap, 1)[0]

            return slope

        except Exception as e:
            self.logger.error(f"Error calculating VWAP slope: {e}")
            return 0.0

    def _calculate_average_volume(self, bars, lookback: int = 20) -> float:
        """Calculate average volume"""
        try:
            if len(bars) < lookback:
                lookback = len(bars)

            recent_bars = bars[-lookback:]
            return np.mean([bar.volume for bar in recent_bars])

        except Exception as e:
            self.logger.error(f"Error calculating average volume: {e}")
            return 0.0

    def _calculate_atr(self, bars, period: int = 14) -> Optional[float]:
        """Calculate ATR (Average True Range)"""
        try:
            if len(bars) < period + 1:
                return None

            true_ranges = []
            for i in range(1, len(bars)):
                high = bars[i].high
                low = bars[i].low
                prev_close = bars[i-1].close

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            # Take last 'period' TRs
            recent_trs = true_ranges[-(period):]
            atr = np.mean(recent_trs)

            return atr

        except Exception as e:
            self.logger.error(f"Error calculating ATR: {e}")
            return None

    def _count_consecutive_green_bars(self, bars) -> int:
        """Count consecutive green bars from the end"""
        try:
            count = 0
            for bar in reversed(bars):
                if bar.close > bar.open:
                    count += 1
                else:
                    break
            return count

        except Exception as e:
            self.logger.error(f"Error counting green bars: {e}")
            return 0

    def get_trading_horizon(self) -> TradingHorizon:
        """Returns trading horizon"""
        return TradingHorizon.INTRADAY

    def get_min_confidence(self) -> float:
        """Returns minimum confidence threshold"""
        return 70.0
