# strategies/base.py
"""
Base strategy classes and common functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from core.interfaces import (
    IStrategy, Signal, Position, MarketData, EventBus,
    SignalType, OrderSide
)
from core.events import EventHandlerMixin, event_handler


class BaseStrategy(IStrategy, EventHandlerMixin):
    """
    Base strategy class that provides common functionality.
    All strategies should inherit from this class.
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None):
        self._name = name
        self._parameters = parameters or {}
        self.logger = logging.getLogger(f"Strategy.{name}")
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_generated: Dict[str, List[Signal]] = {}
        
        # Performance tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Event bus will be set during initialization
        self.event_bus: Optional[EventBus] = None
        
        # Initialize with empty event bus initially
        super().__init__(None)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters.copy()
    
    async def initialize(self, event_bus: EventBus) -> None:
        """Initialize strategy with event bus"""
        self.event_bus = event_bus
        
        # Register event handlers
        self._register_event_handlers()
        
        # Strategy-specific initialization
        await self._initialize_strategy()
        
        self.logger.info(f"Strategy {self.name} initialized with parameters: {self.parameters}")
    
    @abstractmethod
    async def _initialize_strategy(self) -> None:
        """Strategy-specific initialization logic"""
        pass
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new bar data"""
        try:
            # Store bar in history
            if bar.symbol not in self.bars_history:
                self.bars_history[bar.symbol] = []
            
            self.bars_history[bar.symbol].append(bar)
            
            # Keep only last N bars (configurable)
            max_bars = self._parameters.get('max_history_bars', 1500)
            if len(self.bars_history[bar.symbol]) > max_bars:
                self.bars_history[bar.symbol] = self.bars_history[bar.symbol][-max_bars:]
            
            # Generate signal
            signal = await self._analyze_bar(bar)
            
            if signal:
                # Store signal
                if bar.symbol not in self.signals_generated:
                    self.signals_generated[bar.symbol] = []
                self.signals_generated[bar.symbol].append(signal)
                
                self.logger.info(f"Signal generated for {bar.symbol}: {signal.signal_type}")
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error processing bar for {bar.symbol}: {e}")
            return None
    
    @abstractmethod
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate signal - implement in subclasses"""
        pass
    
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates"""
        try:
            self.positions[position.symbol] = position
            
            # Check for exit conditions
            if position.symbol in self.bars_history and self.bars_history[position.symbol]:
                latest_bar = self.bars_history[position.symbol][-1]
                return self.should_exit(position, latest_bar)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error handling position update for {position.symbol}: {e}")
            return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited"""
        try:
            # Check basic exit conditions
            exit_reasons = []
            
            # Stop loss
            if self._check_stop_loss(position, current_bar):
                exit_reasons.append("stop_loss")
            
            # Take profit
            if self._check_take_profit(position, current_bar):
                exit_reasons.append("take_profit")
            
            # Time exit
            if self._check_time_exit(position):
                exit_reasons.append("time_exit")
            
            # Strategy-specific exit conditions
            strategy_exit = self._check_strategy_exit(position, current_bar)
            if strategy_exit:
                exit_reasons.append(strategy_exit)
            
            if exit_reasons:
                signal_type = SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT
                
                return Signal(
                    signal_id="",
                    symbol=position.symbol,
                    signal_type=signal_type,
                    strength=1.0,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    metadata={"exit_reasons": exit_reasons}
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions for {position.symbol}: {e}")
            return None
    
    def _check_stop_loss(self, position: Position, current_bar: MarketData) -> bool:
        """Check stop loss condition"""
        stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)  # 5% default
        
        if position.quantity > 0:  # Long position
            stop_price = position.avg_price * (1 - stop_loss_pct)
            return current_bar.close <= stop_price
        else:  # Short position
            stop_price = position.avg_price * (1 + stop_loss_pct)
            return current_bar.close >= stop_price
    
    def _check_take_profit(self, position: Position, current_bar: MarketData) -> bool:
        """Check take profit condition"""
        take_profit_pct = self._parameters.get('take_profit_pct', 0.10)  # 10% default
        
        if position.quantity > 0:  # Long position
            target_price = position.avg_price * (1 + take_profit_pct)
            return current_bar.close >= target_price
        else:  # Short position
            target_price = position.avg_price * (1 - take_profit_pct)
            return current_bar.close <= target_price
    
    def _check_time_exit(self, position: Position) -> bool:
        """Check time-based exit condition"""
        max_hold_hours = self._parameters.get('max_hold_hours', 24)  # 24 hours default
        
        hold_time = datetime.now() - position.entry_time
        return hold_time > timedelta(hours=max_hold_hours)
    
    def _check_strategy_exit(self, position: Position, current_bar: MarketData) -> Optional[str]:
        """Override in subclasses for strategy-specific exit logic"""
        return None
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """
        Calculate position size based on risk management and position limits.
        
        Args:
            signal: Trading signal with price information
            capital: Available trading capital
            risk_per_trade: Risk percentage per trade (0.0 to 1.0)
            
        Returns:
            int: Number of shares to trade, or 0 if position cannot be taken
        """
        try:
            # Get parameters with defaults
            max_position_value = float(self._parameters.get('max_position_value', 1000.0))
            min_quantity = int(self._parameters.get('min_quantity', 1))
            
            # If price exceeds max_position_value, don't take the position
            if signal.price > max_position_value:
                self.logger.warning(
                    f"Price ${signal.price:.2f} exceeds max position value "
                    f"${max_position_value:.2f} for {signal.symbol}"
                )
                return 0
            
            # Calculate maximum possible quantity based on max position value
            max_possible_quantity = int(max_position_value // signal.price)
            
            # If we can't even buy the minimum quantity within position limits, return 0
            if max_possible_quantity < min_quantity:
                self.logger.warning(
                    f"Cannot meet minimum quantity {min_quantity} for {signal.symbol} "
                    f"at ${signal.price:.2f} within max position value ${max_position_value:.2f}"
                )
                return 0
                
            # Start with the maximum possible quantity within position limits
            quantity = max_possible_quantity
            
            # Calculate position value
            position_value = signal.price * quantity
            
            # Ensure we don't exceed max position value (handle floating point precision)
            while position_value > max_position_value * 1.001 and quantity > 0:  # 0.1% tolerance
                quantity -= 1
                position_value = signal.price * quantity
            
            # Final validation
            if quantity < min_quantity or position_value > max_position_value * 1.001:
                self.logger.error(
                    f"Failed to calculate valid position size for {signal.symbol}: "
                    f"price=${signal.price:.2f}, qty={quantity}, value=${position_value:.2f}, "
                    f"max=${max_position_value:.2f}, min_qty={min_quantity}"
                )
                return 0
                
            self.logger.debug(
                f"Position size for {signal.symbol}: {quantity} shares at ${signal.price:.2f} "
                f"= ${position_value:.2f} (max: ${max_position_value:.2f})"
            )
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {signal.symbol}: {e}")
            return 0
    
    # Helper methods for technical analysis
    def get_bars_df(self, symbol: str, count: Optional[int] = None) -> pd.DataFrame:
        """Get bars as pandas DataFrame"""
        if symbol not in self.bars_history:
            return pd.DataFrame()
        
        bars = self.bars_history[symbol]
        if count:
            bars = bars[-count:]
        
        data = []
        for bar in bars:
            data.append({
                'timestamp': bar.timestamp,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
        
        return df
    
    def calculate_sma(self, symbol: str, period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        return df['close'].tail(period).mean()
    
    def calculate_ema(self, symbol: str, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        df = self.get_bars_df(symbol, period * 2)  # Get more data for EMA
        if len(df) < period:
            return None
        
        return df['close'].ewm(span=period).mean().iloc[-1]
    
    def calculate_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate RSI"""
        df = self.get_bars_df(symbol, period * 2)
        if len(df) < period + 1:
            return None
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1]
    
    def calculate_macd(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
        """Calculate MACD"""
        df = self.get_bars_df(symbol, slow * 3)
        if len(df) < slow:
            return None
        
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line.iloc[-1],
            'signal': signal_line.iloc[-1],
            'histogram': histogram.iloc[-1]
        }
    
    def calculate_bollinger_bands(self, symbol: str, period: int = 20, std_dev: float = 2) -> Optional[dict]:
        """Calculate Bollinger Bands"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        closes = df['close'].tail(period)
        sma = closes.mean()
        std = closes.std()
        
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }
    
    def calculate_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        df = self.get_bars_df(symbol, period + 1)
        if len(df) < period:
            return None
        
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1]
    
    # Event handlers
    @event_handler("position_opened")
    async def on_position_opened(self, event):
        """Handle position opened events"""
        position = event.data["position"]
        self.logger.info(f"Position opened: {position.symbol} {position.quantity}@{position.avg_price}")
    
    @event_handler("position_closed")
    async def on_position_closed(self, event):
        """Handle position closed events"""
        position = event.data["position"]
        self.trades_count += 1
        
        if position.unrealized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        self.logger.info(f"Position closed: {position.symbol} PnL: {position.unrealized_pnl:.2f}")
    
    # Performance metrics
    def get_performance_stats(self) -> dict:
        """Get strategy performance statistics"""
        win_rate = (self.winning_trades / self.trades_count * 100) if self.trades_count > 0 else 0
        
        return {
            "trades_count": self.trades_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "active_positions": len(self.positions)
        }