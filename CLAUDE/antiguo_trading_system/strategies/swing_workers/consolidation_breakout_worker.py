"""
Consolidation Breakout Swing Worker
Executes swing trades based on consolidation pattern breakouts

DUAL ENTRY MODES:
- BREAKOUT: Small gap (<3%), enter at market open with confirmation
- PULLBACK: Large gap (>5%), wait for retrace with MACDV + RSI confirmation
"""

import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, time
import pytz
from .base_swing_worker import BaseSwingWorker


class ConsolidationBreakoutWorker(BaseSwingWorker):
    """
    Swing worker for consolidation pattern breakouts

    Strategy:
    1. Scanner identifies consolidation patterns (20-120 days)
    2. Pattern detector determines entry mode (BREAKOUT vs PULLBACK)
    3. Worker executes based on entry mode:
       - BREAKOUT: Market open entry if gap <3%
       - PULLBACK: Wait for pullback to old resistance with MACDV/RSI confirmation

    Exit strategy:
    - Stop loss: 10% below support
    - Trailing stop: 15% activation, 8% distance
    - Time-based: Exit after 30 days if no movement
    - Target: 50% gain from resistance
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="consolidation_breakout",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Load configuration from config.ini
        self._load_config()
    def _load_config(self):
        """
        Load swing worker configuration from config.ini
        """
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read('config.ini')

            # Load entry mode thresholds
            self.max_safe_gap_pct = config.getfloat('SWING_WORKER', 'max_safe_gap_pct', fallback=3.0)
            self.max_dangerous_gap_pct = config.getfloat('SWING_WORKER', 'max_dangerous_gap_pct', fallback=5.0)

            # Load pullback confirmation parameters
            self.pullback_rsi_oversold = config.getfloat('SWING_WORKER', 'pullback_rsi_oversold', fallback=40.0)
            self.pullback_min_volume_ratio = config.getfloat('SWING_WORKER', 'pullback_min_volume_ratio', fallback=1.2)

            # Load exit parameters
            self.stop_loss_pct = config.getfloat('SWING_WORKER', 'stop_loss_pct', fallback=10.0)
            self.trailing_activation_pct = config.getfloat('SWING_WORKER', 'trailing_activation_pct', fallback=15.0)
            self.trailing_distance_pct = config.getfloat('SWING_WORKER', 'trailing_distance_pct', fallback=8.0)
            self.max_hold_days = config.getint('SWING_WORKER', 'max_hold_days', fallback=30)
            self.target_gain_pct = config.getfloat('SWING_WORKER', 'target_gain_pct', fallback=50.0)

            # Load entry timing
            entry_start_str = config.get('SWING_WORKER', 'entry_window_start', fallback='10:00')
            entry_end_str = config.get('SWING_WORKER', 'entry_window_end', fallback='11:00')

            from datetime import datetime
            self.entry_window_start = datetime.strptime(entry_start_str, '%H:%M').time()
            self.entry_window_end = datetime.strptime(entry_end_str, '%H:%M').time()

            self.logger.info("✅ Swing worker configuration loaded from config.ini")

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load swing worker config from config.ini ({e}), using defaults")

            # Fallback to hardcoded defaults
            self.max_safe_gap_pct = 3.0
            self.max_dangerous_gap_pct = 5.0
            self.pullback_rsi_oversold = 40.0
            self.pullback_min_volume_ratio = 1.2
            self.stop_loss_pct = 10.0
            self.trailing_activation_pct = 15.0
            self.trailing_distance_pct = 8.0
            self.max_hold_days = 30
            self.target_gain_pct = 50.0

            from datetime import time
            self.entry_window_start = time(10, 0)
            self.entry_window_end = time(11, 0)

        # Tracking
        self.trailing_stops = {}         # {symbol: highest_price}

        self.logger.info(
            f"🏛️ Consolidation Breakout Worker configured: "
            f"BREAKOUT mode (gap<{self.max_safe_gap_pct}%), "
            f"PULLBACK mode (gap>{self.max_dangerous_gap_pct}%), "
            f"Entry window: {self.entry_window_start}-{self.entry_window_end} ET"
        )

    async def should_enter(self, swing_pick: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluate if should enter swing position

        Args:
            swing_pick: Swing pick from scanner/database

        Returns:
            Tuple (should_enter, entry_mode) where entry_mode is 'BREAKOUT' or 'PULLBACK'
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')
            entry_mode = swing_pick.get('entry_mode', 'BREAKOUT')

            self.logger.info(f"🔍 {symbol}: Evaluating swing entry (mode: {entry_mode})")

            # Get current market time
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)
            current_time = now_et.time()

            # BREAKOUT MODE: Enter at market open (9:30-9:45 AM ET)
            if entry_mode == 'BREAKOUT':
                return await self._evaluate_breakout_entry(swing_pick, current_time)

            # PULLBACK MODE: Wait for pullback during regular hours
            elif entry_mode == 'PULLBACK':
                return await self._evaluate_pullback_entry(swing_pick, current_time)

            else:
                self.logger.warning(f"⚠️ {symbol}: Unknown entry mode '{entry_mode}'")
                return False, entry_mode

        except Exception as e:
            self.logger.error(f"❌ Error evaluating swing entry: {e}")
            return False, 'BREAKOUT'

    async def _evaluate_breakout_entry(self, swing_pick: Dict[str, Any], current_time: time) -> Tuple[bool, str]:
        """
        Evaluate BREAKOUT mode entry (market open)

        Enter at market open if:
        - Time is 9:30-9:45 AM ET
        - Gap is <3% (safe breakout)
        - Volume confirms (>1.5x average)

        Args:
            swing_pick: Swing pick data
            current_time: Current time (ET)

        Returns:
            Tuple (should_enter, entry_mode)
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')

            # Check market open window (configured from config.ini)
            market_open = self.entry_window_start
            entry_window_end = self.entry_window_end

            if not (market_open <= current_time <= entry_window_end):
                self.logger.debug(
                    f"⏳ {symbol}: BREAKOUT mode - outside entry window "
                    f"(current: {current_time}, window: {self.entry_window_start}-{self.entry_window_end})"
                )
                return False, 'BREAKOUT'

            # Get current price and calculate gap
            current_price = await self._get_current_price(symbol)
            if current_price is None or current_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Could not get current price")
                return False, 'BREAKOUT'

            resistance = swing_pick.get('resistance_level', 0)
            if resistance == 0:
                self.logger.warning(f"⚠️ {symbol}: No resistance level in swing pick")
                return False, 'BREAKOUT'

            gap_pct = ((current_price - resistance) / resistance) * 100

            # Check gap is safe (<3%)
            if gap_pct > self.max_safe_gap_pct:
                self.logger.warning(
                    f"⚠️ {symbol}: Gap {gap_pct:.1f}% > {self.max_safe_gap_pct}% - too large for BREAKOUT mode"
                )
                return False, 'BREAKOUT'

            # Check volume confirmation
            volume_confirmed = await self._check_volume_confirmation(symbol)
            if not volume_confirmed:
                self.logger.debug(f"⏳ {symbol}: Volume not confirmed yet")
                return False, 'BREAKOUT'

            # All criteria met - enter at market open
            self.logger.info(
                f"✅ {symbol}: BREAKOUT entry approved - "
                f"gap {gap_pct:.1f}%, price ${current_price:.2f}, time {current_time} ({self.entry_window_start}-{self.entry_window_end} window)"
            )
            return True, 'BREAKOUT'

        except Exception as e:
            self.logger.error(f"❌ Error evaluating breakout entry: {e}")
            return False, 'BREAKOUT'

    async def _evaluate_pullback_entry(self, swing_pick: Dict[str, Any], current_time: time) -> Tuple[bool, str]:
        """
        Evaluate PULLBACK mode entry (wait for retrace)

        Enter during regular hours if:
        - Price pulled back to old resistance (support now)
        - MACDV shows bullish divergence
        - RSI < 40 (oversold)
        - Volume > 1.2x average

        Args:
            swing_pick: Swing pick data
            current_time: Current time (ET)

        Returns:
            Tuple (should_enter, entry_mode)
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')

            # Check regular trading hours (9:30 AM - 4:00 PM ET)
            market_open = time(9, 30)
            market_close = time(16, 0)

            if not (market_open <= current_time <= market_close):
                self.logger.debug(f"⏳ {symbol}: PULLBACK mode - market closed")
                return False, 'PULLBACK'

            # Get current price
            current_price = await self._get_current_price(symbol)
            if current_price is None or current_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Could not get current price")
                return False, 'PULLBACK'

            resistance = swing_pick.get('resistance_level', 0)
            support = swing_pick.get('support_level', 0)

            if resistance == 0 or support == 0:
                self.logger.warning(f"⚠️ {symbol}: Missing resistance/support levels")
                return False, 'PULLBACK'

            # Calculate pullback levels
            primary_entry = resistance * 0.995   # Old resistance (now support)
            secondary_entry = support + (resistance - support) * 0.5  # 50% Fib

            # Check if price is at pullback level (within 2%)
            at_primary = abs(current_price - primary_entry) / primary_entry <= 0.02
            at_secondary = abs(current_price - secondary_entry) / secondary_entry <= 0.02

            if not (at_primary or at_secondary):
                self.logger.debug(
                    f"⏳ {symbol}: Price ${current_price:.2f} not at pullback levels "
                    f"(primary: ${primary_entry:.2f}, secondary: ${secondary_entry:.2f})"
                )
                return False, 'PULLBACK'

            # Check MACDV confirmation (bullish signal)
            macdv_bullish = await self._check_macdv_bullish(symbol)
            if not macdv_bullish:
                self.logger.debug(f"⏳ {symbol}: MACDV not bullish yet")
                return False, 'PULLBACK'

            # Check RSI oversold (<40)
            rsi = await self._calculate_rsi(symbol)
            if rsi is None or rsi >= self.pullback_rsi_oversold:
                self.logger.debug(
                    f"⏳ {symbol}: RSI {rsi:.1f if rsi else 'N/A'} not oversold "
                    f"(need <{self.pullback_rsi_oversold})"
                )
                return False, 'PULLBACK'

            # Check volume confirmation
            volume_confirmed = await self._check_volume_confirmation(symbol, min_ratio=self.pullback_min_volume_ratio)
            if not volume_confirmed:
                self.logger.debug(f"⏳ {symbol}: Volume not confirmed")
                return False, 'PULLBACK'

            # All criteria met - enter on pullback
            entry_level = "primary" if at_primary else "secondary"
            self.logger.info(
                f"✅ {symbol}: PULLBACK entry approved - "
                f"price ${current_price:.2f} at {entry_level} level, "
                f"MACDV bullish, RSI {rsi:.1f}"
            )
            return True, 'PULLBACK'

        except Exception as e:
            self.logger.error(f"❌ Error evaluating pullback entry: {e}")
            return False, 'PULLBACK'

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """
        Evaluate if should exit swing position

        Exit conditions (priority order):
        1. Stop loss hit (10% below support)
        2. Target reached (50% gain)
        3. Trailing stop triggered (15% activation, 8% distance)
        4. Time-based exit (30 days no movement)

        Args:
            symbol: Symbol of position
            position: Position data
            current_price: Current price

        Returns:
            Tuple (should_exit, reason)
        """
        try:
            entry_price = position.get('entry_price', 0)
            support = position.get('support', 0)
            entry_time_str = position.get('entry_time', '')

            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price")
                return False, ""

            # Calculate gain/loss
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # EXIT 1: Stop loss (configured % below support)
            if support > 0:
                stop_loss = support * (1 - self.stop_loss_pct / 100)
                if current_price <= stop_loss:
                    self.logger.warning(
                        f"🛑 {symbol}: STOP LOSS hit - "
                        f"${current_price:.2f} <= ${stop_loss:.2f} (PnL: {pnl_pct:+.2f}%)"
                    )
                    return True, f"STOP_LOSS (PnL: {pnl_pct:+.2f}%)"

            # EXIT 2: Target reached (configured % gain)
            if pnl_pct >= self.target_gain_pct:
                self.logger.info(
                    f"🎯 {symbol}: TARGET reached - "
                    f"PnL {pnl_pct:+.2f}% >= {self.target_gain_pct}%"
                )
                return True, f"TARGET_REACHED (PnL: {pnl_pct:+.2f}%)"

            # EXIT 3: Trailing stop
            if pnl_pct >= self.trailing_activation_pct:
                # Activate trailing stop
                if symbol not in self.trailing_stops:
                    self.trailing_stops[symbol] = current_price
                    self.logger.info(
                        f"📈 {symbol}: TRAILING STOP activated at ${current_price:.2f} "
                        f"(gain: {pnl_pct:+.2f}%)"
                    )
                else:
                    # Update highest price
                    if current_price > self.trailing_stops[symbol]:
                        self.trailing_stops[symbol] = current_price

                    # Check if trailing stop triggered
                    highest = self.trailing_stops[symbol]
                    trailing_stop = highest * (1 - self.trailing_distance_pct / 100)

                    if current_price <= trailing_stop:
                        self.logger.info(
                            f"📉 {symbol}: TRAILING STOP triggered - "
                            f"${current_price:.2f} <= ${trailing_stop:.2f} "
                            f"(high: ${highest:.2f}, PnL: {pnl_pct:+.2f}%)"
                        )
                        # Clean up trailing stop tracking
                        del self.trailing_stops[symbol]
                        return True, f"TRAILING_STOP (PnL: {pnl_pct:+.2f}%)"

            # EXIT 4: Time-based exit (configured days)
            if entry_time_str:
                days_held = self._calculate_days_held(entry_time_str)

                if days_held >= self.max_hold_days:
                    self.logger.warning(
                        f"⏰ {symbol}: TIME LIMIT reached - "
                        f"{days_held} days >= {self.max_hold_days} days (PnL: {pnl_pct:+.2f}%)"
                    )
                    return True, f"TIME_LIMIT (PnL: {pnl_pct:+.2f}%, {days_held} days)"

            # No exit conditions met
            return False, ""

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            return True, "ERROR_EXIT"

    async def _check_volume_confirmation(self, symbol: str, min_ratio: float = 1.5) -> bool:
        """
        Check if current volume confirms the move

        Args:
            symbol: Symbol to check
            min_ratio: Minimum volume ratio (default 1.5x)

        Returns:
            True if volume confirmed, False otherwise
        """
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            if not bars or len(bars) < 10:
                return False

            # Get current volume (last 5 minutes)
            recent_volume = sum(bar.volume for bar in bars[-5:])

            # Get average volume (first 30 minutes for baseline)
            if len(bars) < 35:
                return False

            avg_volume = sum(bar.volume for bar in bars[5:30]) / 25

            if avg_volume == 0:
                return False

            volume_ratio = recent_volume / (avg_volume * 5)  # 5 bars

            confirmed = volume_ratio >= min_ratio
            self.logger.debug(
                f"📊 {symbol}: Volume ratio {volume_ratio:.2f}x "
                f"({'✅ confirmed' if confirmed else '❌ not confirmed'})"
            )

            return confirmed

        except Exception as e:
            self.logger.error(f"❌ Error checking volume confirmation: {e}")
            return False

    async def _check_macdv_bullish(self, symbol: str) -> bool:
        """
        Check if MACDV shows bullish signal

        Returns:
            True if MACDV is bullish, False otherwise
        """
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            if not bars or len(bars) < 35:
                return False

            # Calculate MACD (simplified)
            closes = [bar.close for bar in bars]

            # Fast EMA (12)
            fast_ema = self._calculate_ema(closes, 12)
            # Slow EMA (26)
            slow_ema = self._calculate_ema(closes, 26)

            if fast_ema is None or slow_ema is None:
                return False

            macd = fast_ema - slow_ema

            # Bullish if MACD positive and increasing
            bullish = macd > 0

            self.logger.debug(
                f"📊 {symbol}: MACD {macd:.4f} "
                f"({'✅ bullish' if bullish else '❌ not bullish'})"
            )

            return bullish

        except Exception as e:
            self.logger.error(f"❌ Error checking MACDV: {e}")
            return False

    async def _calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Calculate RSI for symbol

        Args:
            symbol: Symbol to calculate RSI for
            period: RSI period (default 14)

        Returns:
            RSI value or None
        """
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            if not bars or len(bars) < period + 1:
                return None

            closes = [bar.close for bar in bars[-(period + 1):]]

            # Calculate gains and losses
            gains = []
            losses = []

            for i in range(1, len(closes)):
                change = closes[i] - closes[i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

            if len(gains) == 0:
                return None

            avg_gain = sum(gains) / len(gains)
            avg_loss = sum(losses) / len(losses)

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception as e:
            self.logger.error(f"❌ Error calculating RSI: {e}")
            return None

    def _calculate_ema(self, prices: list, period: int) -> Optional[float]:
        """
        Calculate Exponential Moving Average

        Args:
            prices: List of prices
            period: EMA period

        Returns:
            EMA value or None
        """
        try:
            if len(prices) < period:
                return None

            multiplier = 2 / (period + 1)
            ema = sum(prices[:period]) / period  # Initial SMA

            for price in prices[period:]:
                ema = (price - ema) * multiplier + ema

            return ema

        except Exception as e:
            self.logger.error(f"❌ Error calculating EMA: {e}")
            return None
