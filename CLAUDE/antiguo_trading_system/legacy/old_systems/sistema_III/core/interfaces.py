# core/interfaces.py
"""
Core interfaces and abstractions for the trading system.
This module defines the contracts that all components must follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime
import uuid


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"


@dataclass
class MarketData:
    """Standardized market data container"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    timeframe: Optional[str] = None
    # Extended hours support - bid/ask data
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    last_price: Optional[float] = None
    # Strategy support - for gap and volume calculations
    prev_close: Optional[float] = None
    avg_volume: Optional[int] = None
    
    def __post_init__(self):
        if self.vwap is None:
            self.vwap = (self.high + self.low + self.close) / 3
        if self.last_price is None:
            self.last_price = self.close


@dataclass
class Position:
    """Position information"""
    symbol: str
    quantity: int
    avg_price: float
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)
    realized_pnl: float = 0.0
    side: str = field(init=False)
    
    # ML Exit Engine fields
    entry_price: Optional[float] = None
    strategy: str = "unknown"
    entry_volume_ratio: float = 1.0
    
    def __post_init__(self):
        self.side = "LONG" if self.quantity > 0 else "SHORT" if self.quantity < 0 else "FLAT"
        # Set entry_price from avg_price if not provided
        if self.entry_price is None:
            self.entry_price = self.avg_price


@dataclass
class Order:
    """Order representation"""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    
    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())


@dataclass
class Signal:
    """Trading signal"""
    signal_id: str
    symbol: str
    signal_type: SignalType
    strength: float  # 0.0 to 1.0
    price: float
    timestamp: datetime
    strategy_name: str = ""  # Name of strategy that generated this signal
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # Alias de strength para compatibilidad retroactiva
    
    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())
        # Mantener alias entre strength y confidence
        if self.confidence is None or self.confidence == 1.0:
            self.confidence = self.strength
        else:
            # Si se proporciona confidence diferente, sincronizar strength
            self.strength = self.confidence


@dataclass
class Trade:
    """Completed trade information"""
    trade_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    
    def __post_init__(self):
        if not self.trade_id:
            self.trade_id = str(uuid.uuid4())


# Event System
@dataclass
class Event:
    """Base event class"""
    event_id: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())


class EventHandler(ABC):
    """Base event handler interface"""
    
    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle an event"""
        pass


class EventBus(ABC):
    """Event bus interface for decoupled communication"""
    
    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers"""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe from events"""
        pass


# Core Interfaces
class IDataProvider(ABC):
    """Interface for market data providers"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to data source"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from data source"""
        pass
    
    @abstractmethod
    async def get_bars(self, symbol: str, timeframe: str, count: int) -> List[MarketData]:
        """Get historical bars"""
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected"""
        pass


class IBroker(ABC):
    """Interface for broker connections"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker"""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> str:
        """Place an order, returns order ID"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    async def get_orders(self) -> List[Order]:
        """Get current orders"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected"""
        pass


class IStrategy(ABC):
    """Interface for trading strategies"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Strategy parameters"""
        pass
    
    @abstractmethod
    async def initialize(self, event_bus: EventBus) -> None:
        """Initialize strategy with event bus"""
        pass
    
    @abstractmethod
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new bar data"""
        pass
    
    @abstractmethod
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates"""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for a signal"""
        pass
    
    @abstractmethod
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited"""
        pass


class IRiskManager(ABC):
    """Interface for risk management"""
    
    @abstractmethod
    async def validate_signal(self, signal: Signal) -> bool:
        """Validate if signal meets risk criteria"""
        pass
    
    @abstractmethod
    async def validate_order(self, order: Order) -> bool:
        """Validate if order meets risk criteria"""
        pass
    
    @abstractmethod
    async def check_portfolio_risk(self, positions: Dict[str, Position]) -> bool:
        """Check overall portfolio risk"""
        pass


class IFilter(ABC):
    """Interface for trade filters"""
    
    @abstractmethod
    async def should_trade(self, symbol: str, bars: List[MarketData]) -> tuple[bool, str]:
        """Determine if symbol should be traded"""
        pass


# Configuration
@dataclass
class TradingConfig:
    """Trading system configuration"""
    max_positions: int = 5
    max_risk_per_trade: float = 0.02
    max_daily_loss: float = -1000.0
    max_daily_trades: int = 20
    enable_filters: bool = True
    portfolio_capital: float = 2000.0
    min_signal_strength: float = 0.3
    
    # Position sizing config (from config.ini)
    max_position_value: float = 200.0
    min_position_value: float = 50.0
    portfolio_value: float = 10000.0
    
    # Broker config
    broker_host: str = "127.0.0.1"
    broker_port: int = 7497
    broker_client_id: int = 1
    
    # Strategy config
    strategy_name: str = "macdv"
    timeframe: str = "1 min"
    
    # Market session config (US Eastern Time)
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    minutes_before_close_to_exit: int = 3
    close_positions_on_stop: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "trading.log"
    
    # Synthetic data mode
    use_synthetic_data: bool = False


# Exceptions
class TradingSystemError(Exception):
    """Base exception for trading system"""
    pass


class BrokerConnectionError(TradingSystemError):
    """Broker connection related errors"""
    pass


class DataProviderError(TradingSystemError):
    """Data provider related errors"""
    pass


class StrategyError(TradingSystemError):
    """Strategy related errors"""
    pass


class RiskManagementError(TradingSystemError):
    """Risk management related errors"""
    pass