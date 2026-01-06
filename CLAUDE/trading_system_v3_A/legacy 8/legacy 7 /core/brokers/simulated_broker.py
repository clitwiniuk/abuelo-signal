import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.interfaces.broker_adapter import AbstractBroker, BrokerOrder, BrokerPosition

class SimulatedBroker(AbstractBroker):
    """
    In-Memory Broker for Simulation/Replay.
    Executes orders immediately based on current injected data.
    """
    
    def __init__(self, initial_cash: float = 100000.0, logger: Optional[logging.Logger] = None):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: Dict[str, BrokerPosition] = {} # Symbol -> Position
        self.pending_orders: List[BrokerOrder] = []
        self.market_data: Dict[str, float] = {} # Symbol -> Last known price
        
        # History provider service (to be injected by ReplayEngine)
        self.market_history_provider = None 
        
        self.logger = logger or logging.getLogger("SimulatedBroker")
        self.transaction_log: List[Dict] = []
        
    def update_market_data(self, symbol: str, price: float):
        """Called by Engine to update 'live' price of symbol"""
        self.market_data[symbol] = price
        
        # Update observable metrics on positions (unrealized PnL)
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.market_price = price
            pos.market_value = pos.quantity * price
            pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity

    async def get_account_summary(self) -> Dict[str, Any]:
        """Simple summary"""
        liquidation_value = self.cash + sum(p.market_value for p in self.positions.values())
        return {
            'NetLiquidation': liquidation_value,
            'Cash': self.cash,
            'BuyingPower': self.cash * 4, # Standard intraday leverage
            'FullAvailableFunds': self.cash
        }

    async def get_all_positions(self) -> List[BrokerPosition]:
        return list(self.positions.values())

    async def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        return self.positions.get(symbol)
    
    async def place_order(self, order: BrokerOrder) -> Any:
        """
        Simulate immediate execution for MKT orders.
        FUTURE: Handle limits/stops via queue and check logic.
        """
        if order.order_type != 'MKT':
            self.logger.warning(f"SimulatedBroker currently typically supports MKT for instant replay. Got {order.order_type}")
            # In a real heavy simulation, we'd add to pending and check every tick.
            # For simplicity in V3 Replay, we often treat everything as MKT or fill immediately if price valid.
        
        # Determine execution price
        symbol = order.symbol
        price = self.market_data.get(symbol, 0.0)
        
        # If no price known, we can't fill MKT.
        if price <= 0:
            self.logger.error(f"Cannot fill order for {symbol}: No market price available")
            return None
            
        # Execute
        quantity = order.quantity
        cost = price * quantity
        action_multiplier = 1 if order.action == 'BUY' else -1
        
        # Check cash (Simplified)
        if order.action == 'BUY' and cost > self.cash:
             self.logger.warning(f"Insufficient cash for {symbol}. Needed {cost}, have {self.cash}")
             # return None # Strict mode?
        
        # Update State
        self.cash -= (cost * action_multiplier)
        
        # Update Position
        if symbol not in self.positions:
            self.positions[symbol] = BrokerPosition(
                symbol=symbol,
                quantity=0,
                avg_cost=0.0,
                market_price=price,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                account='SIMULATION'
            )
            
        pos = self.positions[symbol]
        
        # Calculate new avg cost (Weighted Average)
        # If flipping sides (Long -> Short), realized PnL happens.
        # This logic can be complex. Backtrader logic:
        # 1. Closing portion? -> realize PnL
        # 2. Increasing portion? -> adjust avg cost
        
        # SIMPLIFIED V1: Just average cost for same side, or FIFO for close
        # Actually, for V3 Replay, we assume we just track Net Quantity.
        
        # PnL only realized on reduction
        is_reduction = (pos.quantity > 0 and order.action == 'SELL') or \
                       (pos.quantity < 0 and order.action == 'BUY')
                       
        if is_reduction:
            # Realizing PnL
            qty_closed = min(abs(pos.quantity), quantity)
            pnl = (price - pos.avg_cost) * qty_closed * (1 if pos.quantity > 0 else -1)
            pos.realized_pnl += pnl
            self.cash += pnl # Add profit to cash? Or is it already handled by basis?
            # Cash flow is: -Cost to Buy, +Proceeds to Sell.
            # Cash was updated above by FULL proceeds/cost.
            # e.g. Buy 10 @ 100 -> Cash -1000. Sell 10 @ 110 -> Cash +1100. Net +100. Correct.
            pass
        else:
            # Increasing position
            total_cost_old = pos.quantity * pos.avg_cost
            added_cost = quantity * price * (1 if order.action == 'BUY' else -1)
            # This sign logic is tricky for shorts. 
            # Let's stick to signed quantity: Buy = +Qty, Sell = -Qty
            pass
            
        # Update Quantity
        signed_qty = quantity if order.action == 'BUY' else -quantity
        
        # Avg Price Update (only if increasing position size in same direction)
        if (pos.quantity >= 0 and signed_qty > 0) or (pos.quantity <= 0 and signed_qty < 0):
             new_total_qty = pos.quantity + signed_qty
             if abs(new_total_qty) > 0:
                 total_val = (pos.quantity * pos.avg_cost) + (signed_qty * price)
                 pos.avg_cost = total_val / new_total_qty
        
        pos.quantity += signed_qty
        
        # Cleanup if flat
        if abs(pos.quantity) < 0.0001:
            del self.positions[symbol]
        else:
             # Update metrics
             pos.market_value = pos.quantity * price
             pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity

        # Log
        fill_info = {
            'time': datetime.now(),
            'symbol': symbol,
            'action': order.action,
            'qty': quantity,
            'price': price,
            'strategy': order.algo_strategy
        }
        self.transaction_log.append(fill_info)
        self.logger.info(f"SIM ORDER FILLED: {order.action} {quantity} {symbol} @ {price}")
        
        # Return generic result object (mocking IBKR's trade object somewhat)
        class SimTradeResult:
            def __init__(self, p, q):
                self.avgFillPrice = p
                self.filledQuantity = q
        return SimTradeResult(price, quantity)

    async def cancel_order(self, order_id: str) -> bool:
        return True # Mock success
    
    async def get_pending_orders(self) -> List[Any]:
        return self.pending_orders

    async def get_last_price(self, symbol: str) -> float:
        return self.market_data.get(symbol, 0.0)
        
    async def get_history(self, symbol: str, duration: str, bar_size: str) -> List[Any]:
        """Delegate to ReplayEngine's injected provider"""
        if self.market_history_provider:
             return await self.market_history_provider(symbol, duration, bar_size)
        return []
