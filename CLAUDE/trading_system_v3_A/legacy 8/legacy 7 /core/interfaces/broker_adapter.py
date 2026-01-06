from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class BrokerOrder:
    symbol: str
    quantity: int # Positive for BUY, Negative for SELL? Or use action? Prefer standardized action.
    action: str # 'BUY', 'SELL'
    order_type: str # 'MKT', 'LMT', etc.
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    algo_strategy: Optional[str] = None # Tag for the order
    order_ref: Optional[str] = None # Client reference ID

@dataclass
class BrokerPosition:
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float # Snapshot price at time of query
    market_value: float
    unrealized_pnl: float
    realized_pnl: float # Optional, might be difficult in some brokers
    account: str # Account ID

class AbstractBroker(ABC):
    """
    Abstract Interface for a Trading Broker.
    Standardizes interaction regardless of backend (IBKR, Simulator, Backtest).
    """

    @abstractmethod
    async def get_account_summary(self) -> Dict[str, Any]:
        """Returns map of account metrics: {'NetLiquidation': 100000.0, 'BuyingPower': ...}"""
        pass

    @abstractmethod
    async def get_all_positions(self) -> List[BrokerPosition]:
        """Returns all open positions"""
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[BrokerPosition]:
        """Returns position for specific symbol or None"""
        pass
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Returns all open positions as a list of dicts.
        Legacy compatibility helper for workers using dict-style access.
        """
        all_pos = await self.get_all_positions()
        return [asdict(p) for p in all_pos]
    
    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> Any:
        """
        Places an order. 
        Returns backend-specific order object or generic result.
        Should return immediately (async) but order might be pending.
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancels an order by ID"""
        pass
    
    @abstractmethod
    async def get_pending_orders(self) -> List[Any]:
        """Returns list of pending orders"""
        pass

    @abstractmethod
    async def get_last_price(self, symbol: str) -> float:
        """Returns current market price for symbol"""
        pass
        
    @abstractmethod
    async def get_history(self, symbol: str, duration: str, bar_size: str) -> List[Any]:
        """Returns historical bars for symbol"""
        pass
