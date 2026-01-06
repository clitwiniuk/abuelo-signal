"""Base Swing Worker

Base class for swing trading workers.
Handles common logic: UnifiedPositionManager check, position sizing, execution.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class BaseSwingWorker(ABC):
    def __init__(self, worker_name: str, execution_engine, unified_manager, config):
        self.worker_name = worker_name
        self.execution_engine = execution_engine
        self.unified_manager = unified_manager
        self.config = config
        self.logger = logging.getLogger(f"SwingWorker.{worker_name}")

    async def process_swing_pick(self, pick: Dict) -> bool:
        """Process swing pick from scanner"""
        symbol = pick['symbol']
        
        # Check UnifiedPositionManager first
        if not self.unified_manager.can_open_position(symbol, 'swing'):
            self.logger.info(f"⚪ {symbol}: Blocked by UnifiedPositionManager")
            return False

        # Strategy specific logic
        if await self._should_enter(pick):
            return await self._execute_entry(pick)
        
        return False

    async def should_enter(self, pick: Dict) -> bool:
        """Compatibility for ReplayEngine (public alias for _should_enter)"""
        return await self._should_enter(pick)

    @abstractmethod
    async def _should_enter(self, pick: Dict) -> bool:
        """Strategy specific entry logic"""
        pass

    async def _execute_entry(self, pick: Dict) -> bool:
        """Execute entry order"""
        symbol = pick['symbol']
        entry_price = await self.execution_engine.get_current_price(symbol)
        
        # Position sizing
        position_size = self._calculate_position_size(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=pick['support'] * 0.995,
            risk_pct=self.config.get('risk_per_swing_trade', 0.02)
        )
        
        if position_size < self.config.get('min_swing_position_value', 300):
            self.logger.info(f"⚪ {symbol}: Position too small (${position_size:.0f})")
            return False

        # Place order
        order = self.execution_engine.create_market_order(symbol, 'BUY', position_size)
        trade = await self.execution_engine.enter_position(symbol, self.worker_name, pick)
        
        if trade:
            self.logger.info(f"✅ {symbol}: Swing entry executed ${entry_price:.2f} x {position_size}")
            self.unified_manager.register_position(symbol, 'swing', trade)
            return True
        
        return False

    def _calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float, risk_pct: float) -> int:
        """Calculate position size based on risk"""
        risk_per_share = entry_price - stop_loss
        capital_risk = self.config.get('portfolio_capital', 2000) * risk_pct
        shares = int(capital_risk / risk_per_share)
        return min(shares, int(self.config.get('max_swing_position_value', 400) / entry_price))

    async def check_position_exit(self, symbol: str, position: Dict) -> bool:
        """Check if position should exit"""
        # Strategy specific exit logic
        should_exit, reason = await self._should_exit_position(symbol, position)
        if should_exit:
            await self._execute_exit(symbol, position, reason)
            return True
        return False

    @abstractmethod
    async def _should_exit_position(self, symbol: str, position: Dict) -> Tuple[bool, Optional[str]]:
        """Strategy specific exit logic"""
        pass

    async def _execute_exit(self, symbol: str, position: Dict, reason: str):
        """Execute exit order"""
        quantity = position['quantity']
        order = self.execution_engine.create_market_order(symbol, 'SELL', quantity)
        trade = await self.execution_engine.exit_position(symbol, reason)
        if trade:
            self.logger.info(f"🔚 {symbol}: Exit {reason}")
            self.unified_manager.deregister_position(symbol)
