"""
Breakout Exit Manager

Manages complex exit logic for Qullamaggie-style breakout trades:
1. Partial profit-taking (1/3 to 1/2 after 3-5 days)
2. MA-based trailing stops (10-day and 20-day MA)
3. Breakeven stop after partial profit
4. Time-based exits
"""

import logging
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import asyncio
from yahooquery import Ticker
import pandas as pd
import numpy as np


class BreakoutExitManager:
    """
    Manages exits for breakout positions using Qullamaggie rules.

    Exit Logic:
    1. Partial Profit: Sell 1/3-1/2 after 3-5 days (if profitable)
    2. Breakeven Stop: Move stop to entry price after partial
    3. MA Trailing: Exit on CLOSE below 10-day or 20-day MA
    4. Hard Stop: Initial stop at LOD or max %
    """

    def __init__(self, config: Dict[str, Any], logger=None, data_provider=None):
        self.config = config
        self.logger = logger or logging.getLogger("BreakoutExitManager")
        
        # Dependency Injection: Data Provider
        from strategies.swing_workers.breakout_data_provider import IBKRBreakoutDataProvider
        self.data_provider = data_provider
        
        # If no provider given, we can't default blindly usually, but for backward compat:
        # We will initialize it lazily or allow it to be None and fail if used without assignment
        
        # Partial Profit Configuration
        self.partial_profit_days_min = config.get('partial_profit_days_min', 3)
        self.partial_profit_days_max = config.get('partial_profit_days_max', 5)
        self.partial_profit_size = config.get('partial_profit_size', 0.40)  # 40%
        self.min_profit_for_partial = config.get('min_profit_for_partial', 5.0)  # Min 5% profit

        # Trailing Stop Configuration
        self.trailing_ma_period_fast = config.get('trailing_ma_period_fast', 10)
        self.trailing_ma_period_slow = config.get('trailing_ma_period_slow', 20)
        self.use_fast_ma_for_volatile = True  # Use 10-day for fast movers

        # Breakeven Configuration
        self.move_to_breakeven_after_partial = config.get('breakeven_after_partial', True)

        # Track partial exits (symbol -> {partial_taken, partial_date, original_qty})
        self.partial_exits: Dict[str, Dict] = {}

        self.logger.info("🚪 BreakoutExitManager initialized")
        self.logger.info(f"   Partial: {self.partial_profit_size*100:.0f}% @ {self.partial_profit_days_min}-{self.partial_profit_days_max} days")
        self.logger.info(f"   Trailing: {self.trailing_ma_period_fast}d or {self.trailing_ma_period_slow}d MA")

    def register_position(self, symbol: str, quantity: int, entry_date: datetime) -> None:
        """Register a new position for tracking"""
        self.partial_exits[symbol] = {
            'partial_taken': False,
            'partial_date': None,
            'original_qty': quantity,
            'remaining_qty': quantity,
            'entry_date': entry_date
        }
        self.logger.debug(f"📝 Registered {symbol} for exit tracking (Qty: {quantity})")

    def unregister_position(self, symbol: str) -> None:
        """Remove position from tracking"""
        self.partial_exits.pop(symbol, None)
        self.logger.debug(f"🗑️ Unregistered {symbol} from exit tracking")

    async def check_partial_profit(
        self,
        symbol: str,
        current_price: float,
        entry_price: float,
        current_date: datetime
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Check if we should take partial profit.

        Returns:
            (should_take_partial, quantity_to_sell, reason)
        """
        if symbol not in self.partial_exits:
            return False, None, None

        position_data = self.partial_exits[symbol]

        # Already took partial?
        if position_data['partial_taken']:
            return False, None, None

        # Check days held
        entry_date = position_data['entry_date']
        days_held = (current_date - entry_date).days

        # Within partial profit window?
        if not (self.partial_profit_days_min <= days_held <= self.partial_profit_days_max):
            return False, None, None

        # Check if profitable enough
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        if pnl_pct < self.min_profit_for_partial:
            self.logger.debug(
                f"⚪ {symbol}: Day {days_held} but profit too low ({pnl_pct:.1f}% < {self.min_profit_for_partial}%)"
            )
            return False, None, None

        # Calculate quantity to sell
        original_qty = position_data['original_qty']
        qty_to_sell = int(original_qty * self.partial_profit_size)

        if qty_to_sell <= 0:
            return False, None, None

        # Mark as partial taken
        position_data['partial_taken'] = True
        position_data['partial_date'] = current_date
        position_data['remaining_qty'] = original_qty - qty_to_sell

        reason = f"PARTIAL_PROFIT (Day {days_held}, +{pnl_pct:.1f}%)"

        self.logger.info(
            f"📊 {symbol}: Partial Profit Signal - Sell {qty_to_sell}/{original_qty} shares "
            f"({self.partial_profit_size*100:.0f}%) @ ${current_price:.2f}"
        )

        return True, qty_to_sell, reason

    async def check_ma_trailing_stop(
        self,
        symbol: str,
        current_date: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if price closed below 10-day or 20-day MA.

        This is the core Qullamaggie exit: wait for CLOSE below MA.

        Returns:
            (should_exit, reason)
        """
        try:
            if not self.data_provider:
                self.logger.error(f"❌ No DataProvider set for BreakoutExitManager")
                return False, None

            # Fetch daily data via Provider (Abstracts live vs backtest)
            daily_data = await self.data_provider.get_daily_history(symbol, end_date=current_date, days=60)

            if daily_data is None or daily_data.empty or len(daily_data) < 30:
                self.logger.warning(f"⚠️ {symbol}: Insufficient daily data for MA calculation")
                return False, None

            # Calculate MAs
            ma_10 = daily_data['close'].rolling(window=self.trailing_ma_period_fast).mean()
            ma_20 = daily_data['close'].rolling(window=self.trailing_ma_period_slow).mean()

            # Get latest close and MAs
            latest_close = daily_data['close'].iloc[-1]
            latest_ma_10 = ma_10.iloc[-1]
            latest_ma_20 = ma_20.iloc[-1]

            # Determine which MA to use based on volatility
            # For fast movers (high volatility), use 10-day
            # For slower movers, use 20-day
            atr = self._calculate_atr(daily_data)
            volatility_pct = (atr / latest_close) * 100

            use_fast_ma = volatility_pct > 5.0  # If ATR > 5%, it's volatile -> use 10-day

            if use_fast_ma:
                trailing_ma = latest_ma_10
                ma_name = "10-day"
            else:
                trailing_ma = latest_ma_20
                ma_name = "20-day"

            # Check if CLOSED below MA
            if latest_close < trailing_ma:
                self.logger.info(
                    f"🔴 {symbol}: CLOSE below {ma_name} MA "
                    f"(Close: ${latest_close:.2f}, {ma_name} MA: ${trailing_ma:.2f})"
                )
                return True, f"CLOSE_BELOW_{ma_name.upper()}_MA"

            # Optional: Check if it's VERY close to MA (within 1%) as warning
            distance_pct = ((latest_close - trailing_ma) / trailing_ma) * 100
            if 0 < distance_pct < 1.0:
                self.logger.info(
                    f"⚠️ {symbol}: Very close to {ma_name} MA ({distance_pct:.1f}% above)"
                )

            return False, None

        except Exception as e:
            self.logger.error(f"❌ Error checking MA trailing stop for {symbol}: {e}", exc_info=True)
            return False, None

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            high = df['high']
            low = df['low']
            close = df['close'].shift(1)

            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]

            return atr if not np.isnan(atr) else 0.0

        except:
            return 0.0

    def get_position_data(self, symbol: str) -> Optional[Dict]:
        """Get position tracking data"""
        return self.partial_exits.get(symbol)

    def should_move_stop_to_breakeven(self, symbol: str) -> bool:
        """Check if we should move stop to breakeven (after partial taken)"""
        if symbol not in self.partial_exits:
            return False

        position_data = self.partial_exits[symbol]
        return position_data['partial_taken'] and self.move_to_breakeven_after_partial

    async def check_all_exits(
        self,
        symbol: str,
        current_price: float,
        entry_price: float,
        stop_price: float,
        current_date: datetime
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check all exit conditions in priority order.

        Returns:
            (should_exit, exit_reason, exit_metadata)
        """
        # 1. Check Hard Stop Loss
        if current_price <= stop_price:
            return True, f"STOP_LOSS (${current_price:.2f} <= ${stop_price:.2f})", None

        # 2. Check Partial Profit
        should_partial, qty_to_sell, partial_reason = await self.check_partial_profit(
            symbol, current_price, entry_price, current_date
        )

        if should_partial:
            return True, partial_reason, {'partial_exit': True, 'quantity': qty_to_sell}

        # 3. Check MA Trailing Stop (only after partial taken or after certain time)
        position_data = self.partial_exits.get(symbol)
        if position_data:
            days_held = (current_date - position_data['entry_date']).days

            # Only start checking MA trailing after 5 days (let position develop)
            if days_held >= 5:
                should_exit_ma, ma_reason = await self.check_ma_trailing_stop(symbol, current_date)
                if should_exit_ma:
                    return True, ma_reason, None

        return False, None, None
