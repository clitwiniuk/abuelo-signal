#!/usr/bin/env python3
"""
Buy and Hold Worker - Immediate Entry on Scanner Opportunities

Strategy:
- Receives opportunity from scanner during market hours (9:30-16:00 ET)
- Buys IMMEDIATELY if price is above VWAP (no waiting for dip)
- Simple momentum capture strategy for strong setups
- Holds with trailing stop to capture extended moves

Entry Criteria:
1. Scanner opportunity received within trading window (9:30-16:00 ET)
2. Price > VWAP at time of opportunity
3. Quality score meets minimum threshold
4. Anti-trap filters: no weak price action, no resistance proximity, positive VWAP slope
5. Standard risk management (SL, TP, trailing stop, break-even)

Philosophy:
- "Buy strength, not weakness" - Enter immediately on momentum
- Trust scanner's quality scoring
- Avoid buying tops/resistance levels (anti-trap filters)
- Let trailing stop capture runners
- Simple execution, minimal complexity

Author: Trading System
Date: 2025-12-11
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, time
from dataclasses import dataclass

from .base_worker_logic import BaseWorkerLogic, TradingHorizon
from core.structured_logger import StructuredLogger, DecisionType


@dataclass
class VWAPAnalysis:
    """VWAP analysis results"""
    current_price: float
    vwap: float
    price_above_vwap_pct: float  # Percentage above VWAP
    vwap_slope: float            # VWAP trend (positive = uptrend)
    is_above_vwap: bool          # Simple boolean check


class BuyAndHoldWorkerLogic(BaseWorkerLogic):
    """
    Buy and Hold Worker - Immediate momentum entry

    Simple strategy:
    1. Scanner sends opportunity during opening window
    2. Check: Price > VWAP?
    3. If YES -> Buy immediately
    4. If NO -> Reject

    No complex analysis, no waiting for dips.
    Trust the scanner + VWAP confirmation.
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config
        )

        # === TRADING WINDOW (ET timezone) ===
        # Start time: 9:30 AM ET (15:30 España)
        self.trading_start_hour = getattr(config, 'trading_start_hour', 9.5)
        # End time: 16:00 PM ET (22:00 España) - Full market day for testing
        self.trading_end_hour = getattr(config, 'trading_end_hour', 16.0)

        # === VWAP REQUIREMENTS ===
        # Minimum % above VWAP (0.5% = must be at least slightly above)
        self.min_price_above_vwap_pct = getattr(config, 'min_price_above_vwap_pct', 0.5)
        # Minimum VWAP slope (positive = uptrend required)
        self.min_vwap_slope = getattr(config, 'min_vwap_slope', 0.0001)

        # === QUALITY FILTERS ===
        # Minimum scanner quality score (0-100)
        self.min_quality_score = getattr(config, 'min_quality_score', 60.0)
        # Minimum price (avoid extreme penny stocks)
        self.min_price = getattr(config, 'min_price', 1.0)
        # Maximum price
        self.max_price = getattr(config, 'max_price', 50.0)

        # === ANTI-OVERTRADING ===
        # Maximum trades per symbol per day
        self.max_trades_per_symbol_per_day = getattr(
            config, 'max_trades_per_symbol_per_day', 1
        )

        # Track symbols already traded today
        self.traded_symbols_today = set()

        # Initialize structured logger for Grafana Loki
        self.structured_logger = StructuredLogger("buy_and_hold")

        # === STOP MANAGER INITIALIZATION ===
        from .worker_stop_manager import create_worker_stop_manager, WorkerStopManager, WorkerStopConfig
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'BUY_AND_HOLD_STRATEGY')
        else:
            # Default stop manager configuration for buy and hold
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,           # 5% stop loss (allow room for momentum)
                take_profit_pct=15.0,        # 15% profit target (capture runners)
                quick_target_pct=0.0,        # No quick target (hold for runners)
                trailing_activation=8.0,     # Trailing at 8% profit
                trailing_distance=3.0,       # 3% trailing distance
                max_position_hours=24.0      # Hold for extended moves (1 day max)
            ))

        self.logger.info(
            f"🚀 Buy and Hold Worker initialized\n"
            f"   Trading window: {self.trading_start_hour:.2f}h - {self.trading_end_hour:.2f}h ET\n"
            f"   VWAP requirement: +{self.min_price_above_vwap_pct:.1f}% minimum, "
            f"slope {self.min_vwap_slope:.4f}\n"
            f"   Quality threshold: {self.min_quality_score:.0f}\n"
            f"   Max trades per symbol: {self.max_trades_per_symbol_per_day}\n"
            f"   Stops: SL=5%, TP=15%, Trailing=8%/3%, Max=24h"
        )

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Determine if we should enter immediately

        Simple decision tree:
        1. In trading window? (9:30-11:30 ET)
        2. Price filters OK?
        3. Quality score OK?
        4. Not already traded today?
        5. Price > VWAP?

        If all YES -> ENTER IMMEDIATELY
        """
        try:
            symbol = opportunity.get('symbol')
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            self.logger.info(
                f"🔍 {symbol}: Starting buy_and_hold evaluation - "
                f"Price: ${current_price:.2f}, Quality: {quality_score:.1f}"
            )

            # ====
            # STEP 1: TRADING WINDOW CHECK (using ET timezone)
            # ====
            # Use centralized time validation from BaseWorkerLogic (handles timezone conversion)
            is_valid_hours, current_time_et = self.is_within_entry_hours(symbol)

            if not is_valid_hours:
                self.logger.info(
                    f"⏰ {symbol}: REJECTED - Outside trading window "
                    f"(current ET: {current_time_et:.2f}h, window: {self.trading_start_hour:.2f}h-{self.trading_end_hour:.2f}h)"
                )
                # Structured log for Grafana
                self.structured_logger.log_decision(
                    symbol=symbol,
                    decision=DecisionType.REJECTED,
                    reason="outside_trading_window",
                    current_time_et=current_time_et,
                    window_start=self.trading_start_hour,
                    window_end=self.trading_end_hour,
                    current_price=current_price,
                    quality_score=quality_score
                )
                return False

            self.logger.info(
                f"⏰ {symbol}: Within trading window (ET: {current_time_et:.2f}h) ✅"
            )

            # ====
            # STEP 2: PRICE FILTERS
            # ====
            if current_price < self.min_price or current_price > self.max_price:
                self.logger.info(
                    f"⚪ {symbol}: Price ${current_price:.2f} outside range "
                    f"(${self.min_price:.2f}-${self.max_price:.2f})"
                )
                return False

            # ====
            # STEP 3: QUALITY SCORE
            # ====
            if quality_score < self.min_quality_score:
                self.logger.info(
                    f"⚪ {symbol}: Quality score {quality_score:.1f} < {self.min_quality_score:.1f}"
                )
                return False

            self.logger.info(
                f"📊 {symbol}: Quality score {quality_score:.1f} ✅"
            )

            # ====
            # STEP 4: ANTI-OVERTRADING
            # ====
            if symbol in self.traded_symbols_today:
                self.logger.debug(
                    f"⚪ {symbol}: Already traded today"
                )
                return False

            # ====
            # STEP 5: VWAP ANALYSIS
            # ====
            # Scanner sends 'bars_1min', older tests might use 'bars'
            bars = opportunity.get('bars')
            if not bars:
                bars = opportunity.get('bars_1min', [])
            
            if not bars or len(bars) < 10:
                self.logger.info(
                    f"⚪ {symbol}: Insufficient bars ({len(bars)}) for VWAP analysis"
                )
                return False

            vwap_analysis = self._analyze_vwap(bars, current_price)

            if not vwap_analysis:
                self.logger.info(f"⚪ {symbol}: Could not analyze VWAP")
                return False

            # Check VWAP requirements
            if not vwap_analysis.is_above_vwap:
                self.logger.info(
                    f"⚪ {symbol}: REJECTED - Price ${current_price:.2f} BELOW VWAP ${vwap_analysis.vwap:.2f} "
                    f"({vwap_analysis.price_above_vwap_pct:.2f}% deviation)"
                )
                return False

            if vwap_analysis.price_above_vwap_pct < self.min_price_above_vwap_pct:
                self.logger.info(
                    f"⚪ {symbol}: REJECTED - Price only {vwap_analysis.price_above_vwap_pct:.2f}% above VWAP "
                    f"(minimum required: {self.min_price_above_vwap_pct:.1f}%)"
                )
                return False

            if vwap_analysis.vwap_slope < self.min_vwap_slope:
                self.logger.info(
                    f"⚪ {symbol}: REJECTED - VWAP slope {vwap_analysis.vwap_slope:.6f} too flat/negative "
                    f"(minimum required: {self.min_vwap_slope:.6f})"
                )
                return False

            # Log VWAP validation success with details
            self.logger.info(
                f"✅ {symbol}: VWAP validation passed - "
                f"Price ${current_price:.2f} is {vwap_analysis.price_above_vwap_pct:.2f}% above VWAP ${vwap_analysis.vwap:.2f}, "
                f"slope {vwap_analysis.vwap_slope:.6f}"
            )

            # ====
            # STEP 5.25: OPENING DRIVE STABILIZATION - Minimum Bar Count
            # ====
            # Ensure we have enough bars after market open to avoid volatile entries
            # This prevents entering in the chaotic first 10 minutes
            min_bars_after_open = 10  # 10 minutes minimum

            if len(bars) < min_bars_after_open:
                self.logger.info(
                    f"⏰ {symbol}: OPENING DRIVE - Waiting for stabilization "
                    f"({len(bars)}/{min_bars_after_open} bars)"
                )
                return False

            self.logger.info(
                f"✅ {symbol}: Opening drive stabilization passed ({len(bars)} bars)"
            )

            # ====
            # STEP 5.3: ODS FILTERS (Opening Drive Structure)
            # ====
            # Validate market structure using Opening Drive Structure classifier
            # Only enter on confirmed bullish trends, reject on failed drives/balance
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)

            if not is_ods_allowed:
                return False

            # Apply confidence boost to opportunity
            if 'confidence' in opportunity:
                opportunity['confidence'] *= confidence_boost

            self.logger.info(
                f"✅ {symbol}: ODS filters passed (boost: {confidence_boost:.2f}x)"
            )


            # ====
            # STEP 5.5: ANTI-TRAP FILTERS (Evitar comprar techos/resistencias)
            # ====
            # FILTRO 1: Detectar price action débil/distribución
            # Evita: premarket tops, lower highs, distribution volume, declining momentum
            if self._is_price_action_weak(bars, current_price):
                self.logger.info(
                    f"⚠️ {symbol}: WEAK PRICE ACTION detected - "
                    f"Potential top/distribution/resistance rejection - REJECTING"
                )
                return False

            # FILTRO 1.5: PROTECTION AGAINST FALLING KNIFE (New MIST Protection)
            # Ensure we are not buying a sharp drop
            is_falling, fall_reason = self._is_falling_knife(bars, current_price)
            if is_falling:
                self.logger.info(
                    f"🛑 {symbol}: FALLING KNIFE DETECTED - {fall_reason} - REJECTING"
                )
                return False

            # 1.5. FUNDAMENTAL ANALYSIS (Float & Halt)
            fundamentals = await self._analyze_smallcap_fundamentals(opportunity)
             # A. HALT RISK CHECK (Safety)
            if fundamentals.get('is_halt_risk', False):
                 self.logger.warning(f"🛑 {symbol}: ABORT BUY & HOLD - Too close to LULD Halt Band")
                 return False

            # B. HIGH ROTATION
            is_high_rotation = fundamentals.get('is_high_rotation', False)

            # FILTRO 2: Verificar distancia a resistencia histórica
            # Usa análisis de Daily Potential (detecta resistencias weekly/monthly)
            # SKIP if Blue Sky (Blue Sky means we are breaking the resistance!)
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)
            is_blue_sky = daily_potential.get('is_52_week_high', False)

            is_too_close_resistance, resistance_distance = await self._check_resistance_proximity(
                opportunity,
                min_distance_pct=5.0  # Requiere al menos 5% de espacio hasta resistencia
            )
            
            # If Blue Sky, we IGNORE resistance proximity (we want to break it)
            if is_blue_sky:
                 self.logger.info(f"🌤️ {symbol}: BLUE SKY EXEMPTION - Ignoring resistance proximity ({resistance_distance:.1f}%)")
                 is_too_close_resistance = False

            if is_too_close_resistance:
                self.logger.info(
                    f"⚠️ {symbol}: TOO CLOSE TO RESISTANCE ({resistance_distance:.1f}% away) - "
                    f"High rejection risk - REJECTING"
                )
                return False

            # FILTRO 3: VWAP slope debe ser positivo (no solo neutral)
            # Rechazar si VWAP está claramente bajando (selling pressure)
            if vwap_analysis.vwap_slope < -0.0005:
                self.logger.info(
                    f"⚠️ {symbol}: VWAP slope NEGATIVE ({vwap_analysis.vwap_slope:.6f}) - "
                    f"Bearish institutional flow - REJECTING"
                )
                return False

            self.logger.info(
                f"✅ {symbol}: Anti-trap filters passed - "
                f"Price action strong, not falling knife, resistance safe ({resistance_distance:.1f}% away), "
                f"VWAP slope positive"
            )

            # ====
            # STEP 6: EARLY RESISTANCE VALIDATION (same as buy_the_dip)
            # ====
            # Get daily potential analysis (includes resistance detection)
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)
            distance_to_resistance = daily_potential.get('distance_to_resistance', 100)

            # Get early validation threshold from config (default 10%)
            early_validation_threshold = getattr(self.config, 'early_validation_threshold', 10.0)

            # If resistance is VERY close (< threshold), verify we can achieve minimum R:R
            # SKIP check if Blue Sky OR High Rotation (momentum overrides static resistance)
            if distance_to_resistance < early_validation_threshold and not (is_blue_sky or is_high_rotation):
                # Estimate TP at 80% of distance to resistance (with buffer)
                estimated_tp_pct = distance_to_resistance * 0.8

                # Typical SL for buy_and_hold (conservative)
                estimated_sl_pct = 5.0  # 5% typical SL

                # Calculate estimated R:R
                estimated_rr = estimated_tp_pct / estimated_sl_pct if estimated_sl_pct > 0 else 0

                # Minimum R:R threshold (from config or default 2.0)
                min_rr = getattr(self, 'min_risk_reward', 2.0)

                if estimated_rr < min_rr:
                    self.logger.info(
                        f"⚪ {symbol}: RESISTANCE TOO CLOSE - Cannot achieve min R:R "
                        f"(resistance {distance_to_resistance:.1f}% away, "
                        f"estimated TP {estimated_tp_pct:.1f}%, estimated SL {estimated_sl_pct:.1f}%, "
                        f"R:R {estimated_rr:.2f} < {min_rr:.1f})"
                    )
                    return False
                else:
                    self.logger.info(
                        f"✅ {symbol}: Resistance check passed - "
                        f"Can achieve R:R {estimated_rr:.2f} "
                        f"(resistance {distance_to_resistance:.1f}% away)"
                    )

            # ====
            # ALL CHECKS PASSED - ENTER IMMEDIATELY
            # ====
            self.logger.info(
                f"✅ {symbol}: BUY AND HOLD ENTRY APPROVED\n"
                f"   💰 Price: ${current_price:.2f} ({vwap_analysis.price_above_vwap_pct:.2f}% above VWAP)\n"
                f"   📈 VWAP: ${vwap_analysis.vwap:.2f} (slope: {vwap_analysis.vwap_slope:.6f})\n"
                f"   ⭐ Quality: {quality_score:.1f}\n"
                f"   🛡️ Anti-trap: Price stable (no falling knife), resistance {resistance_distance:.1f}% away\n"
                f"   🚀 Entering immediately (no wait)"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error in should_enter for {symbol}: {e}", exc_info=True)
            return False

    @staticmethod
    def _get_bar_value(bar, key: str):
        """
        Get value from bar (supports both dict and object formats)

        Args:
            bar: Bar data (dict or object)
            key: Key/attribute name

        Returns:
            Value from bar
        """
        if isinstance(bar, dict):
            return bar.get(key, 0)
        else:
            return getattr(bar, key, 0)

    def _analyze_vwap(self, bars, current_price: float) -> Optional[VWAPAnalysis]:
        """
        Analyze VWAP position and trend

        Args:
            bars: List of IBKR bars (dict or object format)
            current_price: Current price

        Returns:
            VWAPAnalysis or None
        """
        try:
            if not bars or len(bars) < 10:
                return None

            # Calculate VWAP
            total_volume = 0
            total_pv = 0  # price * volume

            for bar in bars:
                high = self._get_bar_value(bar, 'high')
                low = self._get_bar_value(bar, 'low')
                close = self._get_bar_value(bar, 'close')
                volume = self._get_bar_value(bar, 'volume')

                typical_price = (high + low + close) / 3
                total_pv += typical_price * volume
                total_volume += volume

            if total_volume == 0:
                return None

            vwap = total_pv / total_volume

            # Calculate VWAP slope (trend direction)
            # Compare VWAP of last 5 bars vs previous 5 bars
            if len(bars) >= 10:
                recent_vwap = self._calculate_vwap_for_bars(bars[-5:])
                previous_vwap = self._calculate_vwap_for_bars(bars[-10:-5])
                vwap_slope = (recent_vwap - previous_vwap) / previous_vwap if previous_vwap > 0 else 0
            else:
                vwap_slope = 0

            # Calculate position relative to VWAP
            price_above_vwap_pct = ((current_price - vwap) / vwap) * 100 if vwap > 0 else 0
            is_above_vwap = current_price > vwap

            return VWAPAnalysis(
                current_price=current_price,
                vwap=vwap,
                price_above_vwap_pct=price_above_vwap_pct,
                vwap_slope=vwap_slope,
                is_above_vwap=is_above_vwap
            )

        except Exception as e:
            self.logger.debug(f"Error analyzing VWAP: {e}")
            return None

    def _calculate_vwap_for_bars(self, bars) -> float:
        """Calculate VWAP for a subset of bars (supports dict and object formats)"""
        try:
            total_volume = 0
            total_pv = 0

            for bar in bars:
                high = self._get_bar_value(bar, 'high')
                low = self._get_bar_value(bar, 'low')
                close = self._get_bar_value(bar, 'close')
                volume = self._get_bar_value(bar, 'volume')

                typical_price = (high + low + close) / 3
                total_pv += typical_price * volume
                total_volume += volume

            return total_pv / total_volume if total_volume > 0 else 0

        except Exception as e:
            self.logger.debug(f"Error calculating VWAP subset: {e}")
            return 0

    def on_trade_executed(self, symbol: str, side: str, quantity: int, price: float):
        """
        Called after a trade is executed

        Track traded symbols to prevent overtrading
        """
        if side == 'BUY':
            self.traded_symbols_today.add(symbol)
            self.logger.info(f"✅ {symbol}: Added to traded list (total: {len(self.traded_symbols_today)})")

    def reset_daily_state(self):
        """Reset daily tracking (called at market open)"""
        self.traded_symbols_today.clear()
        self.logger.info("🔄 Daily state reset - traded symbols cleared")

    def get_trading_horizon(self) -> TradingHorizon:
        """
        Define trading horizon for this worker

        Buy and Hold can hold positions for multiple hours,
        but typically closes same day (SWING_SHORT = 1-3 day potential)
        """
        return TradingHorizon.SWING_SHORT

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """
        Determine if we should exit the position

        Buy and Hold uses the base strategy's stop management:
        - Stop Loss (SL) from Structural Exit Calculator
        - Take Profit (TP) from Structural Exit Calculator
        - Trailing stop for runners
        - Breakeven protection

        This method delegates to the stop manager which handles all exit logic.

        Args:
            symbol: Symbol of the position
            position: Position data dict
            current_price: Current market price

        Returns:
            Tuple (should_exit, reason)
        """
        try:
            # Delegate to stop manager (handles SL, TP, trailing, breakeven)
            # The base class BaseWorkerLogic already has stop_manager integration
            
            # CRITICAL FIX: Use StopManager instead of manual logic
            # Pass position as metadata to support dynamic/restored parameters
            return self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                position_metadata=position
            )

        except Exception as e:
            self.logger.error(f"Error in should_exit for {symbol}: {e}", exc_info=True)
            # On error, don't exit (be conservative)
            return False, ""

        except Exception as e:
            self.logger.error(f"Error in should_exit for {symbol}: {e}", exc_info=True)
            # On error, don't exit (be conservative)
            return False, ""

    def _is_falling_knife(self, bars: List[Any], current_price: float) -> Tuple[bool, str]:
        """
        Check if the stock is in a "Falling Knife" state (sharp drop)

        Criteria:
        1. Streak: Last 3 candles are RED (Close < Open)
        2. EMA Check: Price is significantly below EMA9 (1.5%+)
        3. Slope Check: EMA9 is trending down

        Args:
            bars: List of bar objects
            current_price: Current market price

        Returns:
            Tuple (is_falling, reason)
        """
        try:
            if not bars or len(bars) < 10:
                return False, ""

            # 1. RED STREAK CHECK
            # Check if last 3 completed bars are red
            recent_bars = bars[-3:]
            red_streak = 0
            for bar in recent_bars:
                open_p = self._get_bar_value(bar, 'open')
                close_p = self._get_bar_value(bar, 'close')
                if close_p < open_p:
                    red_streak += 1

            if red_streak == 3:
                # Calculate severity of drop
                first_open = self._get_bar_value(recent_bars[0], 'open')
                last_close = self._get_bar_value(recent_bars[-1], 'close')
                drop_pct = ((last_close - first_open) / first_open) * 100
                
                if drop_pct < -1.0: # Significant drop (>1%)
                    return True, f"3 consecutive RED candles (drop {drop_pct:.1f}%)"

            # 2. EMA CHECK
            ema9 = self._calculate_ema(bars, period=9)
            if ema9 > 0:
                # Calculate distance from EMA
                dist_pct = ((current_price - ema9) / ema9) * 100
                
                # If price is > 1.5% below EMA9, it's extended to the downside (falling)
                if dist_pct < -1.5:
                     return True, f"Price extended {dist_pct:.1f}% below EMA9"

            # 3. SLOPE CHECK (Momentum)
            # Check slope of last 5 bars close prices
            slope = self._calculate_slope(bars, period=5)
            
            # If slope is strongly negative, avoid
            if slope < -0.05: # Arbitrary threshold, tune based on price?
                # Better to use percentage slope to be price agnostic
                # Slope in % per bar
                if ema9 > 0:
                    slope_pct = (slope / ema9) * 100
                    if slope_pct < -0.1: # Dropping > 0.1% per minute
                        return True, f"Negative momentum (slope {slope_pct:.2f}%/min)"

            return False, ""

        except Exception as e:
            self.logger.warning(f"Error in falling knife check: {e}")
            return False, "" # Fail open (allow trade) if check fails

    def _calculate_ema(self, bars: List[Any], period: int = 9) -> float:
        """Calculate Exponential Moving Average"""
        try:
            if not bars or len(bars) < period:
                return 0.0

            # Get closing prices
            closes = [self._get_bar_value(b, 'close') for b in bars]
            
            # Start with SMA
            ema = sum(closes[:period]) / period
            
            # Multiplier
            multiplier = 2 / (period + 1)
            
            # Calculate EMA
            for price in closes[period:]:
                ema = (price - ema) * multiplier + ema
                
            return ema

        except Exception:
            return 0.0

    def _calculate_slope(self, bars: List[Any], period: int = 5) -> float:
        """Calculate linear regression slope of closing prices"""
        try:
            if not bars or len(bars) < period:
                return 0.0

            closes = [self._get_bar_value(b, 'close') for b in bars[-period:]]
            
            # Simple linear regression slope
            # x = 0, 1, 2... period-1
            # y = closes
            n = len(closes)
            sum_x = sum(range(n))
            sum_y = sum(closes)
            sum_xy = sum(i * y for i, y in enumerate(closes))
            sum_xx = sum(i * i for i in range(n))
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            
            return slope

        except Exception:
            return 0.0
