# backtesting/backtest_engine.py
"""
Main backtesting engine that uses the same strategies as live trading.
Completely decoupled but compatible with live trading system.
FIXED VERSION - Eliminates the dict/int error
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

from core.interfaces import (
    IStrategy, Signal, Position, MarketData, EventBus,
    SignalType, OrderSide, Order, OrderType, OrderStatus, Trade, TradingConfig
)
from core.events import AsyncEventBus, EventTypes, create_position_event
from core.risk_manager import RiskManager


@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    commission_per_trade: float = 1.0  # Fixed commission
    commission_pct: float = 0.001  # 0.1% commission
    slippage_pct: float = 0.001  # 0.1% slippage
    max_positions: int = 5
    risk_per_trade: float = 0.02  # 2% risk per trade
    data_frequency: str = "1min"  # 1min, 5min, 1hour, 1day
    benchmark_symbol: Optional[str] = None


@dataclass
class BacktestTrade:
    """Individual trade record for backtesting (extends core Trade)"""
    trade_id: str
    symbol: str
    side: OrderSide
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    commission: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_period: Optional[timedelta] = None
    exit_reason: str = ""
    strategy_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_core_trade(self) -> Trade:
        """Convert to core Trade object"""
        return Trade(
            trade_id=self.trade_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            price=self.entry_price,
            timestamp=self.entry_time,
            commission=self.commission
        )


@dataclass
class BacktestResults:
    """Backtesting results and metrics"""
    config: BacktestConfig
    start_date: datetime
    end_date: datetime
    duration: timedelta
    
    # Capital metrics
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    cagr: float
    
    # Trade metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # PnL metrics
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    
    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # Time metrics
    avg_holding_period: timedelta
    max_holding_period: timedelta
    
    # Portfolio metrics
    max_concurrent_positions: int
    avg_capital_utilization: float
    
    # Detailed data
    trades: List[BacktestTrade]
    daily_returns: pd.Series
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    
    # Benchmark comparison (if provided)
    benchmark_return: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None


class BacktestBroker:
    """
    Simulated broker for backtesting.
    Handles order execution, position management, and portfolio accounting.
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.logger = logging.getLogger("BacktestBroker")
        
        # Portfolio state
        self.cash = float(config.initial_capital)  # Ensure it's a float
        self.positions: Dict[str, Position] = {}
        self.trades: List[BacktestTrade] = []
        self.orders_history: List[Order] = []
        
        # Performance tracking
        self.equity_history: List[Dict] = []
        self.daily_pnl: Dict[str, float] = {}
        
        # Trade tracking - ENSURE THESE ARE INTEGERS
        self.trade_counter = 0
        self.current_positions_count = 0
        
        # Signal tracking to prevent the dict/int error
        self.signal_counter = 0
        self.processed_signals = 0
    
    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate current portfolio value"""
        positions_value = 0.0
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                positions_value += abs(position.quantity) * current_prices[symbol]
        
        return float(self.cash + positions_value)  # Ensure return is float
    
    def can_open_position(self, symbol: str, quantity: int, price: float) -> bool:
        """Check if we can open a new position"""
        # Check max positions limit
        if len(self.positions) >= self.config.max_positions:
            return False
        
        # Check if we have enough cash
        required_cash = float(quantity * price)
        commission = self._calculate_commission(quantity, price)
        total_required = required_cash + commission
        
        return float(self.cash) >= total_required
    
    def execute_signal(self, signal: Signal, current_bar: MarketData, 
                      position_size: int) -> Optional[BacktestTrade]:
        """Execute a trading signal"""
        try:
            symbol = signal.symbol
            
            # CRITICAL: Increment signal counter as INTEGER
            self.signal_counter = int(self.signal_counter) + 1
            self.processed_signals = int(self.processed_signals) + 1
            
            if signal.signal_type in [SignalType.LONG, SignalType.SHORT]:
                return self._open_position(signal, current_bar, position_size)
            
            elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                return self._close_position(signal, current_bar)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error executing signal for {signal.symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def _open_position(self, signal: Signal, bar: MarketData, 
                      quantity: int) -> Optional[BacktestTrade]:
        """Open a new position"""
        symbol = signal.symbol
        
        # Check if position already exists
        if symbol in self.positions:
            self.logger.warning(f"Position already exists for {symbol}")
            return None
        
        # Calculate execution price with slippage
        execution_price = self._apply_slippage(bar.close, signal.signal_type)
        
        # Check if we can afford this trade
        if not self.can_open_position(symbol, quantity, execution_price):
            self.logger.warning(f"Cannot afford position for {symbol}")
            return None
        
        # Calculate costs
        commission = self._calculate_commission(quantity, execution_price)
        position_value = float(quantity * execution_price)
        
        # Create position using your Position interface
        pos_quantity = quantity if signal.signal_type == SignalType.LONG else -quantity
        position = Position(
            symbol=symbol,
            quantity=pos_quantity,
            avg_price=execution_price,
            market_price=execution_price,
            market_value=position_value,
            unrealized_pnl=0.0,
            entry_time=bar.timestamp
        )
        
        # Create trade record - ENSURE COUNTER IS INTEGER
        self.trade_counter = int(self.trade_counter) + 1
        side = OrderSide.BUY if signal.signal_type == SignalType.LONG else OrderSide.SELL
        trade = BacktestTrade(
            trade_id=f"T{self.trade_counter:06d}",
            symbol=symbol,
            side=side,
            entry_time=bar.timestamp,
            entry_price=execution_price,
            quantity=quantity,
            commission=commission,
            slippage=abs(execution_price - bar.close),
            strategy_metadata=signal.metadata or {}
        )
        
        # Update portfolio - ENSURE CASH REMAINS FLOAT
        self.positions[symbol] = position
        self.trades.append(trade)
        self.cash = float(self.cash) - (position_value + commission)
        
        self.logger.info(f"Opened {signal.signal_type.value} position: {symbol} "
                        f"{quantity}@{execution_price:.2f}")
        
        return trade
    
    def _close_position(self, signal: Signal, bar: MarketData) -> Optional[BacktestTrade]:
        """Close existing position"""
        symbol = signal.symbol
        
        if symbol not in self.positions:
            self.logger.warning(f"No position to close for {symbol}")
            return None
        
        position = self.positions[symbol]
        
        # Calculate execution price with slippage
        execution_price = self._apply_slippage(bar.close, signal.signal_type)
        
        # Calculate PnL
        if position.quantity > 0:  # Long position
            pnl = (execution_price - position.avg_price) * abs(position.quantity)
        else:  # Short position
            pnl = (position.avg_price - execution_price) * abs(position.quantity)
        
        # Calculate costs
        commission = self._calculate_commission(abs(position.quantity), execution_price)
        net_pnl = float(pnl - commission)
        
        # Find corresponding opening trade
        opening_trade = None
        for trade in reversed(self.trades):
            if trade.symbol == symbol and trade.exit_time is None:
                opening_trade = trade
                break
        
        if opening_trade:
            # Update opening trade with exit information
            opening_trade.exit_time = bar.timestamp
            opening_trade.exit_price = execution_price
            opening_trade.commission = float(opening_trade.commission) + commission
            opening_trade.slippage = float(opening_trade.slippage) + abs(execution_price - bar.close)
            opening_trade.pnl = net_pnl
            opening_trade.pnl_pct = (net_pnl / (opening_trade.entry_price * opening_trade.quantity)) * 100
            opening_trade.holding_period = bar.timestamp - opening_trade.entry_time
            
            # Extract exit reason from signal metadata
            if signal.metadata and 'reason' in signal.metadata:
                opening_trade.exit_reason = signal.metadata['reason']
            else:
                opening_trade.exit_reason = 'signal'
        
        # Update portfolio - ENSURE CASH REMAINS FLOAT
        position_value = float(abs(position.quantity) * execution_price)
        self.cash = float(self.cash) + position_value - commission
        del self.positions[symbol]
        
        self.logger.info(f"Closed position: {symbol} PnL: {net_pnl:.2f}")
        
        return opening_trade
    
    def _apply_slippage(self, price: float, signal_type: SignalType) -> float:
        """Apply slippage to execution price"""
        slippage = float(price * self.config.slippage_pct)
        
        if signal_type in [SignalType.LONG, SignalType.EXIT_SHORT]:
            return float(price + slippage)  # Pay more when buying
        else:
            return float(price - slippage)  # Receive less when selling
    
    def _calculate_commission(self, quantity: int, price: float) -> float:
        """Calculate trading commission"""
        fixed_commission = float(self.config.commission_per_trade)
        pct_commission = float(quantity * price * self.config.commission_pct)
        return fixed_commission + pct_commission
    
    def update_positions(self, current_prices: Dict[str, float]) -> None:
        """Update unrealized PnL and market values for all positions"""
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                current_price = float(current_prices[symbol])
                
                # Update market price and value
                position.market_price = current_price
                position.market_value = float(abs(position.quantity) * current_price)
                
                # Update unrealized PnL
                if position.quantity > 0:  # Long position
                    position.unrealized_pnl = float((current_price - position.avg_price) * position.quantity)
                else:  # Short position
                    position.unrealized_pnl = float((position.avg_price - current_price) * abs(position.quantity))
    
    def record_equity(self, timestamp: datetime, current_prices: Dict[str, float]) -> None:
        """Record equity curve point"""
        portfolio_value = self.get_portfolio_value(current_prices)
        
        self.equity_history.append({
            'timestamp': timestamp,
            'cash': float(self.cash),
            'positions_value': float(portfolio_value - self.cash),
            'total_value': float(portfolio_value),
            'positions_count': int(len(self.positions))  # Ensure this is int
        })


class BacktestEngine:
    """
    Main backtesting engine that orchestrates the entire backtest.
    Uses the same strategies as live trading for consistency.
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.logger = logging.getLogger("BacktestEngine")
        
        # Core components
        self.broker = BacktestBroker(config)
        self.event_bus = AsyncEventBus()  # Use your AsyncEventBus
        self.risk_manager = RiskManager(self._create_trading_config())
        
        # Strategies
        self.strategies: List[IStrategy] = []
        
        # Data
        self.data_loader: Optional[Callable] = None
        self.benchmark_data: Optional[pd.Series] = None
        
        # Processing counters - ENSURE THESE ARE INTEGERS
        self.bars_processed = 0
        self.signals_processed = 0
        self.trades_executed = 0
    
    def _create_trading_config(self):
        """Create TradingConfig from BacktestConfig"""
        # Crear config básico
        config = TradingConfig(
            max_positions=self.config.max_positions,
            max_risk_per_trade=self.config.risk_per_trade,
            max_daily_loss=self.config.initial_capital * -0.05,  # 5% daily loss limit
            max_daily_trades=50
        )
        
        # Propagar el flag simulation_mode si existe en el config del backtest
        if hasattr(self.config, 'simulation_mode'):
            config.simulation_mode = self.config.simulation_mode
            
        return config
    
    def add_strategy(self, strategy: IStrategy) -> None:
        """Add strategy to backtest"""
        self.strategies.append(strategy)
        self.logger.info(f"Added strategy: {strategy.name}")
    
    def set_data_loader(self, loader: Callable[[str, datetime, datetime], pd.DataFrame]) -> None:
        """Set data loading function"""
        self.data_loader = loader
    
    async def run_backtest(self, symbols: List[str]) -> BacktestResults:
        """Run the complete backtest"""
        self.logger.info(f"Starting backtest: {self.config.start_date} to {self.config.end_date}")
        self.logger.info(f"Symbols: {symbols}")
        self.logger.info(f"Strategies: {[s.name for s in self.strategies]}")
        
        if not self.data_loader:
            raise ValueError("Data loader not set")
        
        try:
            # Initialize strategies
            for strategy in self.strategies:
                await strategy.initialize(self.event_bus)
            
            # Load and process data
            await self._process_historical_data(symbols)
            
            # Calculate results
            results = self._calculate_results()
            
            self.logger.info(f"Backtest completed. Final capital: {results.final_capital:.2f}")
            self.logger.info(f"Total return: {results.total_return_pct:.2f}%")
            self.logger.info(f"Total trades: {results.total_trades}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Backtest failed: {e}")
            raise
    
    async def _process_historical_data(self, symbols: List[str]) -> None:
        """Process historical data bar by bar"""
        # Load data for all symbols
        all_data = {}
        for symbol in symbols:
            df = self.data_loader(symbol, self.config.start_date, self.config.end_date)
            if not df.empty:
                all_data[symbol] = df
            else:
                self.logger.warning(f"No data loaded for {symbol}")
        
        if not all_data:
            raise ValueError("No data loaded for any symbol")
        
        # Create unified timeline
        all_timestamps = set()
        for df in all_data.values():
            all_timestamps.update(df.index)
        
        sorted_timestamps = sorted(all_timestamps)
        self.logger.info(f"Processing {len(sorted_timestamps)} time points")
        
        # Process each timestamp
        for i, timestamp in enumerate(sorted_timestamps):
            # ENSURE COUNTER REMAINS INTEGER
            self.bars_processed = int(self.bars_processed) + 1
            
            if i % 1000 == 0:
                progress = (i / len(sorted_timestamps)) * 100
                self.logger.info(f"Processing: {progress:.1f}% ({timestamp})")
            
            current_prices = {}
            
            # Process each symbol at this timestamp
            for symbol, df in all_data.items():
                if timestamp in df.index:
                    row = df.loc[timestamp]
                    
                    # Create market data
                    bar = MarketData(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(row['volume']) if 'volume' in row else 0
                    )
                    
                    current_prices[symbol] = float(bar.close)
                    
                    # Process bar with each strategy
                    for strategy in self.strategies:
                        try:
                            signal = await strategy.on_bar(bar)
                            
                            if signal:
                                # ENSURE SIGNAL COUNTER REMAINS INTEGER
                                self.signals_processed = int(self.signals_processed) + 1
                                
                                # Validate signal with risk manager
                                is_valid = await self.risk_manager.validate_signal(signal)
                                if not is_valid:
                                    self.logger.info(f"Signal rejected by risk manager: {symbol}")
                                    continue
                                
                                # Calculate position size
                                position_size = strategy.calculate_position_size(
                                    signal, 
                                    float(self.broker.cash),
                                    self.config.risk_per_trade
                                )
                                
                                if position_size > 0:
                                    # Execute signal
                                    trade = self.broker.execute_signal(signal, bar, int(position_size))
                                    
                                    if trade:
                                        # ENSURE TRADE COUNTER REMAINS INTEGER
                                        self.trades_executed = int(self.trades_executed) + 1
                                        
                                        # Notify strategy and publish events
                                        await self._handle_trade_events(signal, trade, symbol, strategy)
                        
                        except Exception as e:
                            self.logger.error(f"Error processing {symbol} with {strategy.name}: {e}")
                            import traceback
                            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # Update portfolio
            if current_prices:
                self.broker.update_positions(current_prices)
                self.broker.record_equity(timestamp, current_prices)
    
    async def _handle_trade_events(self, signal: Signal, trade: BacktestTrade, 
                                 symbol: str, strategy: IStrategy) -> None:
        """Handle trade-related events and notifications"""
        try:
            if signal.signal_type in [SignalType.LONG, SignalType.SHORT]:
                position = self.broker.positions.get(symbol)
                if position:
                    # Notify strategy of position update
                    await strategy.on_position_update(position)
                    
                    # Publish position opened event
                    await self.event_bus.publish(
                        create_position_event(position, EventTypes.POSITION_OPENED)
                    )
            
            elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                # Publish position closed event
                position_data = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=trade.exit_price or 0,
                    market_price=trade.exit_price or 0,
                    market_value=0,
                    unrealized_pnl=trade.pnl,
                    entry_time=trade.entry_time
                )
                
                await self.event_bus.publish(
                    create_position_event(position_data, EventTypes.POSITION_CLOSED)
                )
        
        except Exception as e:
            self.logger.error(f"Error handling trade events for {symbol}: {e}")
    
    def _calculate_results(self) -> BacktestResults:
        """Calculate comprehensive backtest results"""
        trades = [t for t in self.broker.trades if t.exit_time is not None]
        equity_df = pd.DataFrame(self.broker.equity_history)
        
        if equity_df.empty:
            raise ValueError("No equity data recorded")
        
        equity_df.set_index('timestamp', inplace=True)
        
        # Basic metrics
        initial_capital = float(self.config.initial_capital)
        final_capital = float(equity_df['total_value'].iloc[-1])
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # Time metrics
        duration = self.config.end_date - self.config.start_date
        years = duration.days / 365.25
        cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # Trade metrics
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl <= 0])
        win_rate = (winning_trades / len(trades) * 100) if trades else 0
        
        # PnL metrics
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        net_profit = gross_profit - gross_loss
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0
        
        largest_win = max([t.pnl for t in trades], default=0)
        largest_loss = min([t.pnl for t in trades], default=0)
        
        # Risk metrics
        returns = equity_df['total_value'].pct_change().dropna()
        daily_returns = returns.resample('D').apply(lambda x: (1 + x).prod() - 1)
        
        # Drawdown calculation
        equity_curve = equity_df['total_value'] / initial_capital
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = max_drawdown * 100
        
        # Sharpe ratio
        if len(daily_returns) > 1:
            excess_returns = daily_returns
            sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Sortino ratio
        negative_returns = daily_returns[daily_returns < 0]
        downside_std = negative_returns.std() if len(negative_returns) > 1 else 0
        sortino_ratio = daily_returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        # Calmar ratio
        calmar_ratio = cagr / abs(max_drawdown_pct) if max_drawdown_pct != 0 else 0
        
        # Holding period metrics
        holding_periods = [t.holding_period for t in trades if t.holding_period]
        avg_holding_period = sum(holding_periods, timedelta()) / len(holding_periods) if holding_periods else timedelta()
        max_holding_period = max(holding_periods, default=timedelta())
        
        # Portfolio metrics
        max_concurrent_positions = int(equity_df['positions_count'].max())
        avg_capital_utilization = (equity_df['positions_value'] / equity_df['total_value']).mean() * 100
        
        return BacktestResults(
            config=self.config,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            duration=duration,
            
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            cagr=cagr,
            
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            
            max_drawdown=max_drawdown * initial_capital,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            
            avg_holding_period=avg_holding_period,
            max_holding_period=max_holding_period,
            
            max_concurrent_positions=max_concurrent_positions,
            avg_capital_utilization=avg_capital_utilization,
            
            trades=trades,
            daily_returns=daily_returns,
            equity_curve=equity_df['total_value'],
            drawdown_curve=drawdown * initial_capital
        )