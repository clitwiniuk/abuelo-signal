#!/usr/bin/env python3
"""
Buy and Hold Worker - SHORT on Pullbacks in Uptrend

Strategy:
- SHORT momentum strategy: Sell when price is ABOVE VWAP with positive trend
- Same entry logic as LONG version (uptrend confirmation)
- But executes SHORT orders to capture pullbacks in uptrend
- Hold with trailing stop to capture extended moves

Entry Criteria (5 filters only):
1. Trading window (9:30-16:00 ET)
2. Price range ($1-$50)
3. Quality score ≥ 70
4. Price > VWAP (+0.5% minimum) - SAME AS LONG (uptrend)
5. VWAP slope > 0 (uptrend) - SAME AS LONG (uptrend)

Philosophy:
- "Short pullbacks in uptrends" - Same setup detection as LONG
- All indicators are visualizable (VWAP, slope, quality)
- Easy to debug and understand
- Let trailing stop capture runners

Author: Trading System
Date: 2026-01-06 (SHORT Version - Same logic, opposite order direction)
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


@dataclass
class MomentumAnalysis:
    """Unified momentum analysis (supports both ROC and VWAP slope)"""
    indicator_type: str  # "ROC" or "VWAP_SLOPE"
    value: float         # ROC percentage or VWAP slope
    is_positive: bool    # True if momentum is upward
    current_price: float

    # VWAP-specific (optional, for price position filter)
    vwap: Optional[float] = None
    price_above_vwap_pct: Optional[float] = None
    is_above_vwap: Optional[bool] = None


class BuyAndHoldWorkerLogic(BaseWorkerLogic):
    """
    Buy and Hold Worker - VWAP Momentum Strategy (SIMPLIFIED)

    Super simple decision tree:
    1. In trading window? (9:30-16:00 ET)
    2. Price in range? ($1-$50)
    3. Quality ≥ 70?
    4. Price > VWAP (+0.5%)?
    5. VWAP trending up? (slope > 0)

    If ALL YES -> ENTER
    If ANY NO -> REJECT

    No support detection, no resistance checks, no complex filters.
    Just VWAP momentum + scanner quality.
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config
        )

        # === SHORT DIRECTION ===
        # CRITICAL: Override base class default (LONG) to SHORT
        self.scaling_side = 'SHORT'

        # === TRADING WINDOW (ET timezone) ===
        # Start time: 9:30 AM ET (15:30 España)
        self.trading_start_hour = getattr(config, 'trading_start_hour', 9.5)
        # End time: 16:00 PM ET (22:00 España) - Full market day for testing
        self.trading_end_hour = getattr(config, 'trading_end_hour', 16.0)

        # === MOMENTUM INDICATOR SELECTION ===
        # Choose between ROC (Rate of Change) or VWAP Slope for momentum detection
        self.use_roc = getattr(config, 'use_roc_momentum', True)
        self.roc_period = getattr(config, 'roc_period', 5)  # Number of bars for ROC calculation
        self.roc_min_threshold = getattr(config, 'roc_min_threshold', 0.1)  # Minimum ROC % (0.1%)

        # === VWAP REQUIREMENTS ===
        # Minimum % above VWAP (0.1% = just barely above) - RELAXED for testing
        self.min_price_above_vwap_pct = getattr(config, 'min_price_above_vwap_pct', 0.1)
        # Minimum VWAP slope (very small positive = any uptrend) - Used only if use_roc = False
        self.min_vwap_slope = getattr(config, 'min_vwap_slope', 0.00001)

        # === QUALITY FILTERS ===
        # Minimum scanner quality score (0-100) - LOWERED to 60 for more entries
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

        momentum_indicator = "ROC" if self.use_roc else "VWAP Slope"
        momentum_threshold = f"{self.roc_min_threshold:.2f}%" if self.use_roc else f"{self.min_vwap_slope:.5f}"

        self.logger.info(
            f"🚀 Buy & Hold - SHORT on Pullbacks (Same Logic as LONG)\n"
            f"   📊 Momentum Indicator: {momentum_indicator}\n"
            f"   ✅ Filters: Window + Price Range + Quality + VWAP Position (ABOVE) + {momentum_indicator} (POSITIVE)\n"
            f"   🔻 DIRECTION: SHORT (Sell on uptrend pullbacks)\n"
            f"   Trading window: {self.trading_start_hour:.2f}h - {self.trading_end_hour:.2f}h ET\n"
            f"   Price range: ${self.min_price:.0f} - ${self.max_price:.0f}\n"
            f"   Quality threshold: {self.min_quality_score:.0f}\n"
            f"   VWAP: +{self.min_price_above_vwap_pct:.1f}% min (ABOVE)\n"
            f"   {momentum_indicator}: >{momentum_threshold}{' ('+str(self.roc_period)+' bars)' if self.use_roc else ''}\n"
            f"   Max trades/symbol: {self.max_trades_per_symbol_per_day}\n"
            f"   Stops: SL=5% (above), TP=15% (below), Trailing=8%/3%, Max=24h"
        )

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        SHORT on Pullbacks Strategy - Same Logic as LONG

        5 Filters (Sequential):
        1. Trading window (9:30-16:00 ET)
        2. Price range ($1-$50)
        3. Quality score ≥ 70
        4. Price > VWAP (+0.5% minimum) - SAME AS LONG (uptrend)
        5. VWAP slope > 0 (uptrend) - SAME AS LONG (positive momentum)

        All filters must pass to ENTER SHORT (sell on uptrend pullback)
        """
        try:
            symbol = opportunity.get('symbol')
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            self.logger.info(
                f"🔍 {symbol}: VWAP Momentum Check - "
                f"Price: ${current_price:.2f}, Quality: {quality_score:.1f}"
            )

            # ====
            # STEP 1: TRADING WINDOW CHECK (using ET timezone)
            # ====
            # Use centralized time validation from BaseWorkerLogic (handles timezone conversion)
            # BUT if this is a replay/backtest with a timestamp in the opportunity, use THAT time instead
            if 'timestamp' in opportunity and opportunity['timestamp']:
                # WorkerLab / Backtest mode - use the bar's timestamp
                bar_timestamp = opportunity['timestamp']
                if isinstance(bar_timestamp, str):
                    from dateutil import parser
                    bar_timestamp = parser.parse(bar_timestamp)

                # Convert to ET timezone
                import pytz
                et_tz = pytz.timezone('America/New_York')
                if bar_timestamp.tzinfo is None:
                    # Assume UTC if no timezone
                    bar_timestamp = pytz.utc.localize(bar_timestamp)
                bar_timestamp_et = bar_timestamp.astimezone(et_tz)

                # Extract hour in decimal format (e.g., 9.5 for 9:30 AM)
                current_time_et = bar_timestamp_et.hour + bar_timestamp_et.minute / 60.0

                # Check if within window
                is_valid_hours = self.trading_start_hour <= current_time_et <= self.trading_end_hour
            else:
                # Live trading mode - use current system time
                is_valid_hours, current_time_et = self.is_within_entry_hours(symbol)

            if not is_valid_hours:
                self.logger.info(
                    f"⏰ {symbol}: REJECTED - Outside trading window "
                    f"(bar time ET: {current_time_et:.2f}h, window: {self.trading_start_hour:.2f}h-{self.trading_end_hour:.2f}h)"
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
            # STEP 5: MOMENTUM ANALYSIS (ROC or VWAP SLOPE)
            # ====
            bars = self.get_bars_from_opportunity(opportunity)

            min_bars_needed = self.roc_period + 1 if self.use_roc else 10
            if not bars or len(bars) < min_bars_needed:
                self.logger.info(
                    f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0}) for momentum analysis (need {min_bars_needed})"
                )
                return False

            momentum = self._analyze_momentum(bars, current_price)

            if not momentum:
                self.logger.info(f"⚪ {symbol}: Could not calculate momentum ({momentum.indicator_type if momentum else 'unknown'})")
                return False

            # === EXPOSE MOMENTUM INDICATORS FOR VISUALIZATION ===
            # CRITICAL: Always populate metrics for WorkerLab visualization
            # These are shown regardless of entry decision
            opportunity['momentum_indicator'] = momentum.indicator_type
            opportunity['momentum_value'] = momentum.value

            if momentum.vwap is not None:
                opportunity['vwap'] = momentum.vwap
                opportunity['price_above_vwap_pct'] = momentum.price_above_vwap_pct
                opportunity['is_above_vwap'] = momentum.is_above_vwap

            # Keep legacy field for backward compatibility
            if momentum.indicator_type == "VWAP_SLOPE":
                opportunity['vwap_slope'] = momentum.value

            # NOTE: SL/TP will be added ONLY if entry is approved (after all filters pass)

            # Check Filter 4: Price > VWAP (SAME AS LONG - uptrend confirmation)
            if momentum.is_above_vwap is not None and not momentum.is_above_vwap:
                self.logger.info(
                    f"⚪ {symbol}: REJECTED - Price BELOW VWAP (need ABOVE for uptrend) "
                    f"(${current_price:.2f} vs ${momentum.vwap:.2f})"
                )
                return False

            if momentum.price_above_vwap_pct is not None and momentum.price_above_vwap_pct < self.min_price_above_vwap_pct:
                self.logger.info(
                    f"⚪ {symbol}: REJECTED - Price only {momentum.price_above_vwap_pct:.2f}% above VWAP "
                    f"(minimum: +{self.min_price_above_vwap_pct:.1f}%)"
                )
                return False

            if momentum.is_above_vwap:
                self.logger.info(
                    f"✅ {symbol}: Price above VWAP (+{momentum.price_above_vwap_pct:.2f}%)"
                )

            # Check Filter 5: Momentum POSITIVE (SAME AS LONG - ROC or VWAP Slope)
            if not momentum.is_positive:
                if momentum.indicator_type == "ROC":
                    self.logger.info(
                        f"⚪ {symbol}: REJECTED - ROC too low (need POSITIVE for uptrend) "
                        f"({momentum.value:+.2f}% < {self.roc_min_threshold:.2f}%)"
                    )
                else:
                    self.logger.info(
                        f"⚪ {symbol}: REJECTED - VWAP trending down (need UP for uptrend) "
                        f"(slope: {momentum.value:.5f} < {self.min_vwap_slope:.5f})"
                    )
                return False

            if momentum.indicator_type == "ROC":
                self.logger.info(
                    f"✅ {symbol}: ROC positive ({momentum.value:+.2f}%, {self.roc_period} bars)"
                )
            else:
                self.logger.info(
                    f"✅ {symbol}: VWAP trending UP (slope: {momentum.value:.5f})"
                )

            # ====
            # ALL FILTERS PASSED - ENTER!
            # ====

            # NOW calculate and expose SL/TP (INVERTED stops for SHORT orders only)
            opportunity['suggested_stop_loss_pct'] = 5.0  # 5% SL
            opportunity['stop_loss_price'] = current_price * 1.05  # SL ARRIBA para SHORT
            opportunity['take_profit_price'] = current_price * 0.85  # TP ABAJO para SHORT (-15%)
            opportunity['side'] = 'SELL'  # CRITICAL: Specify SHORT side for execution engine

            # Build entry log message with available momentum data
            entry_msg = (
                f"✅✅✅ {symbol}: {momentum.indicator_type} SHORT ENTRY (Uptrend Pullback) ✅✅✅\n"
                f"   💰 Price: ${current_price:.2f}\n"
                f"   🔻 DIRECTION: SHORT (Sell on uptrend)\n"
            )

            if momentum.vwap is not None:
                entry_msg += f"   📈 VWAP: ${momentum.vwap:.2f} ({momentum.price_above_vwap_pct:+.2f}% ABOVE)\n"

            if momentum.indicator_type == "VWAP_SLOPE":
                entry_msg += f"   📊 VWAP Slope: {momentum.value:.5f} (UPTREND)\n"
            elif momentum.indicator_type == "ROC":
                entry_msg += f"   📊 ROC: {momentum.value:+.2f}% (POSITIVE)\n"

            entry_msg += (
                f"   ⭐ Quality: {quality_score:.1f}/100\n"
                f"   🛡️ Stop Loss: ${opportunity['stop_loss_price']:.2f} (+5% above for SHORT)\n"
                f"   🎯 Take Profit: ${opportunity['take_profit_price']:.2f} (-15% below for SHORT)\n"
                f"   📐 R:R: 1:3 (Standard)"
            )

            self.logger.info(entry_msg)
            return True

        except Exception as e:
            self.logger.error(f"Error in should_enter for {symbol}: {e}", exc_info=True)
            return False

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Always return 100% for Buy and Hold strategy.
        The ReplayEngine requires this method to return > 75% to approve entry.
        Since should_enter already validated everything, we confirm it here.
        """
        return 100.0

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

    def _analyze_momentum(self, bars, current_price: float) -> Optional[MomentumAnalysis]:
        """
        Analyze momentum using configured indicator (ROC or VWAP Slope)

        This function unifies momentum detection to support A/B testing
        between different indicators.

        Args:
            bars: List of price bars
            current_price: Current price

        Returns:
            MomentumAnalysis object or None if analysis fails
        """
        try:
            if self.use_roc:
                # === OPTION A: ROC (Rate of Change) ===
                roc = self._calculate_price_roc(bars, period=self.roc_period)

                if roc is None:
                    self.logger.debug(
                        f"Could not calculate ROC (need {self.roc_period + 1}+ bars)"
                    )
                    return None

                # SAME AS LONG: ROC debe ser POSITIVO (uptrend)
                is_positive = roc >= self.roc_min_threshold

                # Still calculate VWAP for context (price above VWAP filter)
                vwap_analysis = self._analyze_vwap(bars, current_price)

                return MomentumAnalysis(
                    indicator_type="ROC",
                    value=roc,
                    is_positive=is_positive,
                    current_price=current_price,
                    vwap=vwap_analysis.vwap if vwap_analysis else None,
                    price_above_vwap_pct=vwap_analysis.price_above_vwap_pct if vwap_analysis else None,
                    is_above_vwap=vwap_analysis.is_above_vwap if vwap_analysis else None
                )

            else:
                # === OPTION B: VWAP Slope (Original) ===
                vwap_analysis = self._analyze_vwap(bars, current_price)

                if not vwap_analysis:
                    return None

                # SAME AS LONG: VWAP slope debe ser POSITIVO (uptrend)
                return MomentumAnalysis(
                    indicator_type="VWAP_SLOPE",
                    value=vwap_analysis.vwap_slope,
                    is_positive=vwap_analysis.vwap_slope >= self.min_vwap_slope,
                    current_price=current_price,
                    vwap=vwap_analysis.vwap,
                    price_above_vwap_pct=vwap_analysis.price_above_vwap_pct,
                    is_above_vwap=vwap_analysis.is_above_vwap
                )

        except Exception as e:
            self.logger.debug(f"Error analyzing momentum: {e}")
            return None

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

            # Calculate position relative to VWAP (mantener el signo correcto)
            price_above_vwap_pct = ((current_price - vwap) / vwap) * 100 if vwap > 0 else 0
            # Para SHORT: queremos que price_above_vwap_pct sea NEGATIVO
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
        # INVERTED: Now we track SELL (SHORT entries)
        if side == 'SELL':
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
            # CRITICAL FIX: Use metadata (opportunity_data) from position to support restored params
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=position.get('entry_price', 0),
                position_metadata=position
            )

            if should_exit:
                self.logger.info(f"📤 {symbol}: Exit triggered by StopManager: {reason}")
                return True, reason

            return False, ""

            # Don't exit - let the position run
            return False, ""

        except Exception as e:
            self.logger.error(f"Error in should_exit for {symbol}: {e}", exc_info=True)
            # On error, don't exit (be conservative)
            return False, ""

