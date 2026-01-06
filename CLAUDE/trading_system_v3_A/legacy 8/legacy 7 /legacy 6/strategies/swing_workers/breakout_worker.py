"""
Breakout Worker (Qullamaggie-style Swing Trading)

Implements the Qullamaggie consolidation breakout strategy:
1. Enter on opening range highs (OR breakouts)
2. Stop at lows of day (max ATR/ADR)
3. Partial profit at 3-5 days (sell 1/3 to 1/2)
4. Trail remainder with 10-day or 20-day MA (first close below)

Hold Time: Multi-day to multi-week (potential 10-20x R moves in bull markets)
"""

import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import pytz
from .base_swing_worker import BaseSwingWorker

class BreakoutWorker(BaseSwingWorker):
    """
    Swing worker for Qullamaggie-style breakout trades.

    Strategy:
    - Entry: Opening range highs (1min, 5min, or 60min breakout)
    - Hold: Multi-day/week positions
    - Partial Exit: 1/3 to 1/2 after 3-5 days
    - Trail: 10-day or 20-day MA (first close below)
    - Target: 10-20x+ initial risk in bull markets
    """

    def __init__(self, execution_engine, risk_manager, config):
        super().__init__(
            worker_name="breakout",
            execution_engine=execution_engine,
            unified_manager=risk_manager,
            config=config
        )

        # Entry Configuration
        self.opening_range_minutes = [1, 5, 60]  # Can use any of these
        self.use_daily_breakout = True  # Can also just watch daily chart

        # Stop Loss Configuration
        self.use_lows_of_day_stop = True
        self.max_stop_atr_multiplier = 1.0  # Stop should not exceed 1x ATR
        self.max_stop_pct = 7.0  # Absolute max stop (7% based on Qullamaggie guidance)

        # Partial Profit Configuration
        self.partial_profit_days_min = 3
        self.partial_profit_days_max = 5
        self.partial_profit_size = 0.40  # Sell 40% (slightly less than 1/2)
        self.breakeven_stop_after_partial = True  # Move stop to breakeven after partial

        # Trailing Stop Configuration
        self.trailing_ma_period_fast = 10  # 10-day MA (for fast movers)
        self.trailing_ma_period_slow = 20  # 20-day MA (for slower movers)
        self.use_close_below_ma = True  # Exit on CLOSE below MA (not intraday)

        # Position Sizing
        self.risk_per_trade = 100.0  # Risk $100 per trade (can adjust based on account)

        # Hold Time
        self.max_hold_days = 90  # Max 90 days (can go much longer in practice)
        
        # Replay Support
        self.current_replay_date = None
        self.exit_manager = None

        self.logger.info("📈🔥 Breakout Worker (Qullamaggie) initialized")
        self.logger.info(f"   Entry: Opening Range Highs | Stop: LOD (max {self.max_stop_pct}%)")
        self.logger.info(f"   Partial: {self.partial_profit_size*100:.0f}% @ {self.partial_profit_days_min}-{self.partial_profit_days_max} days")
        self.logger.info(f"   Trail: {self.trailing_ma_period_fast}d or {self.trailing_ma_period_slow}d MA")

    def set_replay_date(self, date: str):
        """Set current simulation date (YYYY-MM-DD or datetime)"""
        if isinstance(date, str):
            # Parse only if it's a string
            try:
                # Handle ISO format including time if present
                if 'T' in date:
                    self.current_replay_date = datetime.fromisoformat(date)
                else:
                    self.current_replay_date = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                self.logger.warning(f"Invalid replay date format: {date}")
        elif isinstance(date, datetime):
            self.current_replay_date = date
            
        # Update dataprovider if using one
        if hasattr(self.exit_manager, 'data_provider') and self.exit_manager.data_provider:
             # Check if it's the backtest provider
             if hasattr(self.exit_manager.data_provider, 'set_date'):
                 self.exit_manager.data_provider.set_date(self.current_replay_date)

    def _get_current_time(self) -> datetime:
        """Get current time (real or simulated)"""
        if self.current_replay_date:
            return self.current_replay_date
        return datetime.now()

    def calculate_position_size(self, entry_price: float, stop_price: float) -> int:
        """
        Calculate position size based on fixed risk.

        Risk = (Entry - Stop) * Shares
        Shares = Risk / (Entry - Stop)
        """
        if entry_price <= 0 or stop_price <= 0 or entry_price <= stop_price:
            return 0

        risk_per_share = entry_price - stop_price

        if risk_per_share <= 0:
            return 0

        # Calculate shares
        shares = int(self.risk_per_trade / risk_per_share)

        # Cap at reasonable position value (e.g., $5000)
        max_position_value = 5000.0
        if shares * entry_price > max_position_value:
            shares = int(max_position_value / entry_price)

        return max(shares, 10)  # Minimum 10 shares

    async def _should_enter(self, pick: Dict[str, Any]) -> bool:
        """
        Evaluate entry for Breakout setup.

        Qullamaggie Entry Criteria:
        1. Stock is from breakout scanner (consolidation breakout setup)
        2. Price is breaking above consolidation resistance
        3. Volume is confirming (1.5x+ average)
        4. Market regime is favorable (optional but important)
        """
        opportunity = pick
        symbol = opportunity.get('symbol', 'UNKNOWN')
        breakout_data = opportunity.get('breakout_data', {})

        # 1. Verify Breakout Data
        if not breakout_data:
            self.logger.warning(f"⚠️ {symbol}: Missing breakout data")
            return False

        # 2. Check if we're near breakout level
        current_price = opportunity.get('current_price', 0)
        resistance = breakout_data.get('resistance', 0)

        if current_price <= 0 or resistance <= 0:
            return False

        distance_to_breakout_pct = breakout_data.get('distance_to_breakout_pct', 100)

        # Should be very close to breakout (within 3%)
        if distance_to_breakout_pct > 3.0:
            self.logger.debug(f"⚪ {symbol}: Too far from breakout ({distance_to_breakout_pct:.1f}%)")
            return False

        # 3. Volume Confirmation
        volume_ratio = opportunity.get('volume_ratio', 0)
        if volume_ratio < 1.5:
            self.logger.debug(f"⚪ {symbol}: Volume too low ({volume_ratio:.1f}x)")
            return False

        # 4. Quality Score
        quality_score = opportunity.get('quality_score', 0)
        if quality_score < 60:
            self.logger.debug(f"⚪ {symbol}: Quality score too low ({quality_score})")
            return False

        # 5. Market Regime Check (optional - prefer bullish markets for breakouts)
        # In a strong bull market, breakouts can go 10-20x+
        # In weak markets, they tend to fail
        try:
            from core.adaptive_threshold_manager import get_adaptive_threshold_manager
            threshold_mgr = get_adaptive_threshold_manager()
            regime = threshold_mgr.get_regime_summary()

            if not regime.get('entries_allowed', True):
                self.logger.info(f"⚪ {symbol}: Market regime unfavorable")
                return False
        except:
            pass  # If regime check fails, proceed anyway

        self.logger.info(
            f"✅ {symbol}: Breakout Entry Approved "
            f"(Q={quality_score}, Vol={volume_ratio:.1f}x, To BO: {distance_to_breakout_pct:.1f}%)"
        )
        return True

    async def _execute_entry(self, swing_pick: Dict[str, Any], entry_mode: str = 'BREAKOUT') -> bool:
        """
        Execute entry for breakout trade.

        Entry Mechanics:
        - Use market order on breakout (speed is important)
        - Calculate stop based on LOD (lows of day) or max ATR
        - Position size based on risk ($100 per trade)
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')
            breakout_data = swing_pick.get('breakout_data', {})

            # Get current price
            current_price = swing_pick.get('current_price', 0)
            if current_price == 0:
                current_price = await self._get_current_price(symbol)

            if not current_price or current_price <= 0:
                self.logger.error(f"❌ {symbol}: Could not get price for entry")
                return False

            # Calculate Stop Price
            stop_price = self._calculate_stop_price(current_price, breakout_data)

            if stop_price <= 0 or stop_price >= current_price:
                self.logger.error(f"❌ {symbol}: Invalid stop price {stop_price}")
                return False

            # Calculate Position Size
            quantity = self.calculate_position_size(current_price, stop_price)
            position_value = quantity * current_price

            if quantity <= 0:
                self.logger.warning(f"⚠️ {symbol}: Calculated quantity is 0")
                return False

            risk_amount = (current_price - stop_price) * quantity
            risk_pct = ((current_price - stop_price) / current_price) * 100

            self.logger.info(
                f"📏 Sizing {symbol}: Entry ${current_price:.2f}, Stop ${stop_price:.2f} "
                f"({risk_pct:.1f}%), Risk ${risk_amount:.2f}, Qty: {quantity} (${position_value:.2f})"
            )

            # Inject stop price and entry metadata into opportunity
            swing_pick['calculated_stop_price'] = stop_price
            swing_pick['calculated_stop_pct'] = risk_pct
            swing_pick['position_value'] = position_value
            swing_pick['force_gtc'] = True  # GTC orders for multi-day holds
            swing_pick['outside_rth'] = True  # Allow extended hours
            swing_pick['entry_date'] = datetime.now().isoformat()

            # Execute Order
            order_result = await self.execution_engine.enter_position(
                symbol=symbol,
                strategy=self.worker_name,
                opportunity_data=swing_pick
            )

            if not order_result:
                self.logger.error(f"❌ {symbol}: Order execution failed")
                return False

            self.logger.info(f"✅ {symbol}: Breakout entry executed @ ${current_price:.2f} x {quantity}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing breakout entry for {symbol}: {e}", exc_info=True)
            return False

    def _calculate_stop_price(self, entry_price: float, breakout_data: Dict) -> float:
        """
        Calculate stop price using Qullamaggie methodology.

        Stop = Lows of Day (LOD)
        BUT:
        - Stop should not be wider than ATR
        - Stop should not be wider than ADR (Average Daily Range)
        - Absolute max: 7% (to prevent R/R from getting out of whack)

        Since we're entering EOD or on opening range, we use:
        - Support level from consolidation as proxy for "lows"
        - Compare against ATR to ensure it's reasonable
        """
        support = breakout_data.get('support', 0)
        atr = breakout_data.get('atr', 0)

        # Method 1: Use consolidation support as stop
        stop_from_support = support * 0.98  # 2% below support for buffer

        # Method 2: Use ATR-based stop
        stop_from_atr = entry_price - (atr * self.max_stop_atr_multiplier)

        # Method 3: Use percentage stop (max 7%)
        stop_from_pct = entry_price * (1 - self.max_stop_pct / 100)

        # Use the HIGHEST stop (tightest risk)
        # But ensure it's not too tight (min 3% stop for volatility)
        min_stop = entry_price * 0.97  # Min 3% stop

        stop_price = max(stop_from_support, stop_from_atr, stop_from_pct, min_stop)

        # Ensure stop is valid
        if stop_price >= entry_price:
            stop_price = entry_price * 0.93  # Fallback: 7% stop

        return stop_price

    async def _get_current_price(self, symbol: str) -> float:
        """Get current price from execution engine"""
        try:
            if hasattr(self.execution_engine, 'get_current_price'):
                return await self.execution_engine.get_current_price(symbol)
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {e}")
        return 0.0

    async def _should_exit_position(self, symbol: str, position: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Evaluate exit for Breakout position.

        Exit Logic:
        1. Hard Stop Loss (LOD or max %)
        2. Partial Profit (after 3-5 days, sell 1/3-1/2)
        3. Trailing Stop (10-day or 20-day MA close below)
        4. Time Limit (max 90 days, but can extend)
        """
        # Get current price
        current_price = position.get('current_price', 0)
        if current_price == 0:
            try:
                current_price = await self._get_current_price(symbol)
            except:
                pass

        entry_price = position.get('entry_price', 0)
        stop_price = position.get('stop_price', 0)

        if entry_price == 0 or current_price == 0:
            return False, None

        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # 1. Hard Stop Loss
        if stop_price > 0 and current_price <= stop_price:
            return True, f"STOP_LOSS (${current_price:.2f} <= ${stop_price:.2f})"

        # Fallback percentage stop
        max_stop_pct = position.get('calculated_stop_pct', self.max_stop_pct)
        if pnl_pct <= -max_stop_pct:
            return True, f"STOP_LOSS_PCT ({pnl_pct:.1f}%)"

        # 2. Partial Profit Check
        # (This would be handled by a separate partial exit mechanism)
        # For now, we'll just note when we should take partial profit
        entry_date = position.get('entry_date')
        if entry_date:
            try:
                entry_dt = datetime.fromisoformat(entry_date)
                days_held = (self._get_current_time() - entry_dt).days

                # Check if we should take partial profit
                partial_taken = position.get('partial_profit_taken', False)
                if not partial_taken and self.partial_profit_days_min <= days_held <= self.partial_profit_days_max:
                    if pnl_pct > 5.0:  # Only take partial if in profit
                        # Signal to take partial (would need to implement partial exit logic)
                        self.logger.info(
                            f"📊 {symbol}: Partial profit signal (Day {days_held}, +{pnl_pct:.1f}%) "
                            f"- Would sell {self.partial_profit_size*100:.0f}% here"
                        )
                        # In real implementation, would call partial_exit() here
                        position['partial_profit_taken'] = True

                        # Move stop to breakeven after partial
                        if self.breakeven_stop_after_partial:
                            position['stop_price'] = entry_price
                            self.logger.info(f"🔒 {symbol}: Stop moved to breakeven @ ${entry_price:.2f}")

            except Exception as e:
                self.logger.debug(f"Error checking partial profit: {e}")

        # 3. Trailing Stop (MA-based)
        # Check if we should exit based on MA close
        # This would require daily closing price data
        # For now, we'll use a simple trailing stop logic

        # If we're in significant profit, protect it with trailing stop
        if pnl_pct > 20.0:
            # Trail with 10% stop from high
            trailing_stop_pct = 10.0
            # Would need to track position high watermark
            # For simplicity, use a percentage trailing stop
            # In real implementation, would fetch daily MA and check close vs MA

            pass  # Placeholder for MA trailing logic

        # 4. Time Limit
        if entry_date:
            try:
                entry_dt = datetime.fromisoformat(entry_date)
                days_held = (datetime.now() - entry_dt).days

                if days_held >= self.max_hold_days:
                    return True, f"MAX_HOLD_TIME ({days_held} days)"
            except:
                pass

        return False, None

    async def check_ma_trailing_stop(self, symbol: str, position: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if price closed below 10-day or 20-day MA.

        This should be called EOD (after market close) to check daily closing prices.
        """
        try:
            # Fetch recent daily bars
            # Would need access to historical data fetcher
            # For now, placeholder

            # Example logic:
            # daily_bars = await self._fetch_daily_bars(symbol, bars=30)
            # ma_10 = calculate_ma(daily_bars, period=10)
            # ma_20 = calculate_ma(daily_bars, period=20)
            # latest_close = daily_bars[-1]['close']
            #
            # if latest_close < ma_10:
            #     return True, f"CLOSE_BELOW_MA10 (${latest_close:.2f} < ${ma_10:.2f})"
            # if latest_close < ma_20:
            #     return True, f"CLOSE_BELOW_MA20 (${latest_close:.2f} < ${ma_20:.2f})"

            return False, None

        except Exception as e:
            self.logger.error(f"Error checking MA trailing stop for {symbol}: {e}")
            return False, None
