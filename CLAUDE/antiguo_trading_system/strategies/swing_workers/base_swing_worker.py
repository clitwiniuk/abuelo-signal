"""
Base Swing Worker
Base class for all swing trading workers (positions held days/weeks/months)
"""

import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from abc import ABC, abstractmethod


class BaseSwingWorker(ABC):
    """
    Base class for swing trading workers

    Swing trading differs from day trading:
    - Positions held days/weeks/months (not intraday)
    - Larger position sizes ($300-400 vs $100-200)
    - Wider stops (10-20% vs 3-5%)
    - Longer time horizons (days vs hours)
    - Focus on pattern breakouts and position trading
    """

    def __init__(self, worker_name: str, execution_engine, risk_manager):
        self.worker_name = worker_name
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(f"SwingWorker.{worker_name}")

        # Swing-specific configuration
        self.min_position_value = 300.0  # Minimum $300 per position
        self.max_position_value = 400.0  # Maximum $400 per position
        self.max_positions = 2           # Maximum 2 swing positions simultaneously

        self.logger.info(f"🏛️ {worker_name} swing worker initialized")

    @abstractmethod
    async def should_enter(self, swing_pick: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluate if should enter swing position

        Args:
            swing_pick: Swing pick data from scanner/database

        Returns:
            Tuple (should_enter, entry_mode) where entry_mode is 'BREAKOUT' or 'PULLBACK'
        """
        pass

    @abstractmethod
    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """
        Evaluate if should exit swing position

        Args:
            symbol: Symbol of the position
            position: Position data
            current_price: Current price

        Returns:
            Tuple (should_exit, reason)
        """
        pass

    async def process_swing_pick(self, swing_pick: Dict[str, Any]) -> bool:
        """
        Process a swing pick from the scanner

        Args:
            swing_pick: Swing pick data

        Returns:
            True if position entered, False otherwise
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')

            # Check if should enter
            should_enter, entry_mode = await self.should_enter(swing_pick)

            if not should_enter:
                self.logger.debug(f"⏳ {symbol}: Entry criteria not met")
                return False

            # Execute entry
            success = await self._execute_entry(swing_pick, entry_mode)

            return success

        except Exception as e:
            self.logger.error(f"❌ Error processing swing pick: {e}")
            return False

    async def check_position_exit(self, symbol: str, position: Dict[str, Any]) -> bool:
        """
        Check if position should be exited

        Args:
            symbol: Symbol of the position
            position: Position data

        Returns:
            True if position exited, False otherwise
        """
        try:
            # Get current price
            current_price = await self._get_current_price(symbol)

            if current_price is None or current_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Could not get current price")
                return False

            # Check exit criteria
            should_exit, reason = await self.should_exit(symbol, position, current_price)

            if should_exit:
                await self._execute_exit(symbol, reason, current_price)
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking position exit for {symbol}: {e}")
            return False

    async def _execute_entry(self, swing_pick: Dict[str, Any], entry_mode: str) -> bool:
        """
        Execute swing position entry

        Args:
            swing_pick: Swing pick data
            entry_mode: 'BREAKOUT' or 'PULLBACK'

        Returns:
            True if successful, False otherwise
        """
        try:
            symbol = swing_pick.get('symbol', 'UNKNOWN')

            # Check for duplicate positions
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading"
                )
                return False

            # Calculate position size
            current_price = swing_pick.get('current_price', 0)
            if current_price == 0:
                current_price = await self._get_current_price(symbol)

            if current_price is None or current_price == 0:
                self.logger.error(f"❌ {symbol}: Could not get current price for entry")
                return False

            # Position sizing: Use available swing capital
            position_value = min(self.max_position_value, 400.0)  # Max $400 per position
            quantity = int(position_value / current_price)

            if quantity == 0:
                self.logger.warning(f"⚠️ {symbol}: Quantity 0 (price ${current_price:.2f} too high)")
                return False

            # Check capital availability
            can_open, reason = unified_manager.can_open_position(symbol, 'swing', position_value)
            if not can_open:
                self.logger.warning(f"⚠️ {symbol}: Cannot open position - {reason}")
                return False

            # Execute order based on entry mode
            order_type = 'MKT' if entry_mode == 'BREAKOUT' else 'LMT'
            limit_price = current_price if entry_mode == 'PULLBACK' else None

            # Place order via execution engine
            order_result = await self.execution_engine.execute_entry(
                symbol=symbol,
                action='BUY',
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price
            )

            if not order_result or not order_result.get('success', False):
                self.logger.error(f"❌ {symbol}: Order execution failed")
                return False

            # Register position with unified manager
            unified_manager.register_position(
                symbol=symbol,
                strategy_type='swing',
                position_data={
                    'strategy': self.worker_name,
                    'entry_mode': entry_mode,
                    'entry_price': current_price,
                    'quantity': quantity,
                    'position_value': position_value,
                    'entry_time': datetime.now().isoformat(),
                    'resistance': swing_pick.get('resistance_level', 0),
                    'support': swing_pick.get('support_level', 0),
                    'pattern_type': swing_pick.get('pattern_type', 'unknown'),
                    'breakout_score': swing_pick.get('breakout_score', 0)
                }
            )

            self.logger.info(
                f"✅ {symbol}: SWING position entered - "
                f"{quantity} shares @ ${current_price:.2f} = ${position_value:.2f} "
                f"(mode: {entry_mode})"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing swing entry for {symbol}: {e}")
            return False

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """
        Execute swing position exit

        Args:
            symbol: Symbol to exit
            reason: Exit reason
            current_price: Current price
        """
        try:
            # Get position info
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if not unified_manager:
                self.logger.error(f"❌ {symbol}: No unified manager available")
                return

            position = unified_manager.get_position(symbol)
            if not position:
                self.logger.warning(f"⚠️ {symbol}: No position found in unified manager")
                return

            quantity = position.get('quantity', 0)
            entry_price = position.get('entry_price', 0)

            if quantity == 0:
                self.logger.warning(f"⚠️ {symbol}: Quantity is 0, cannot exit")
                return

            # Execute exit order
            order_result = await self.execution_engine.execute_exit(
                symbol=symbol,
                action='SELL',
                quantity=quantity,
                order_type='MKT'
            )

            if not order_result or not order_result.get('success', False):
                self.logger.error(f"❌ {symbol}: Exit order failed")
                return

            # Calculate PnL
            pnl_gross = (current_price - entry_price) * quantity
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Unregister from unified manager
            unified_manager.unregister_position(symbol, 'swing')

            self.logger.info(
                f"🔚 {symbol}: SWING position exited - "
                f"{quantity} shares @ ${current_price:.2f} "
                f"(entry: ${entry_price:.2f}, PnL: ${pnl_gross:+.2f} / {pnl_pct:+.2f}%) "
                f"Reason: {reason}"
            )

        except Exception as e:
            self.logger.error(f"❌ Error executing swing exit for {symbol}: {e}")

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for symbol

        Args:
            symbol: Symbol to get price for

        Returns:
            Current price or None
        """
        try:
            if hasattr(self.execution_engine, 'get_current_price'):
                return await self.execution_engine.get_current_price(symbol)

            # Fallback: use broker directly
            if hasattr(self.execution_engine, 'broker'):
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                ticker = self.execution_engine.broker.ib.reqTicker(contract)

                # Wait for price
                for _ in range(10):
                    await self.execution_engine.broker.ib.sleep(0.1)
                    if ticker.last > 0:
                        return ticker.last
                    if ticker.close > 0:
                        return ticker.close

                return None

            return None

        except Exception as e:
            self.logger.error(f"❌ Error getting current price for {symbol}: {e}")
            return None

    def _calculate_days_held(self, entry_time_str: str) -> int:
        """
        Calculate number of days position has been held

        Args:
            entry_time_str: Entry time as ISO format string

        Returns:
            Number of days held
        """
        try:
            entry_time = datetime.fromisoformat(entry_time_str)
            now = datetime.now()
            delta = now - entry_time
            return delta.days
        except Exception as e:
            self.logger.error(f"❌ Error calculating days held: {e}")
            return 0
