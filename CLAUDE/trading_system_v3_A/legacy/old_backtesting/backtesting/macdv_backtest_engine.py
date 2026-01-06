#!/usr/bin/env python3
"""
Real System Backtesting Engine - MACDV Strategy with Trailing Stops
Replicates the exact system used in live trading for accurate backtesting
"""

import asyncio
import logging
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import live system components
from adapters.traded_symbols_data_provider import TradedSymbolsDataProvider
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from core.interfaces import MarketData, Position, Order, OrderSide, OrderType
from strategies.multi_strategy_engine import MultiStrategyEngine
from core.events import AsyncEventBus


@dataclass
class BacktestTrade:
    """Individual trade record for backtesting"""
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    strategy: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    duration_minutes: int = 0
    exit_reason: str = ""
    max_profit_reached: float = 0.0
    max_drawdown: float = 0.0


@dataclass
class BacktestResults:
    """Comprehensive backtesting results"""
    symbol: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_duration_minutes: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    trades: List[BacktestTrade] = None
    
    def __post_init__(self):
        if self.trades is None:
            self.trades = []


class MacdvBacktestEngine:
    """
    Backtesting engine that replicates the exact live trading system:
    - Uses macdv_smallcaps strategy
    - Implements trailing stops
    - Tests only symbols that have been actually traded
    - Uses real historical data
    """
    
    def __init__(self, 
                 position_size: float = 200.0,
                 trailing_stop_pct: float = 0.05,
                 max_hold_minutes: int = 240,
                 debug: bool = False):
        """
        Initialize the backtesting engine
        
        Args:
            position_size: Dollar amount per position
            trailing_stop_pct: Trailing stop percentage (5% = 0.05)
            max_hold_minutes: Maximum hold time in minutes
            debug: Enable debug logging
        """
        self.position_size = position_size
        self.trailing_stop_pct = trailing_stop_pct
        self.max_hold_minutes = max_hold_minutes
        
        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(level=log_level)
        self.logger = logging.getLogger("MacdvBacktestEngine")
        
        # Initialize components
        self.data_provider = None
        self.broker = None
        self.strategy_engine = None
        self.event_bus = None
        
        # Results tracking
        self.results: Dict[str, BacktestResults] = {}
        self.overall_results = None
        
        self.logger.info("🎯 MACDV BACKTESTING ENGINE INITIALIZED")
        self.logger.info(f"   💰 Position size: ${position_size}")
        self.logger.info(f"   🛑 Trailing stop: {trailing_stop_pct*100}%")
        self.logger.info(f"   ⏱️  Max hold: {max_hold_minutes} minutes")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            self.logger.info("🔧 Initializing backtesting components...")
            
            # Initialize data provider WITHOUT auto-download (data should already exist)
            self.data_provider = TradedSymbolsDataProvider(
                db_path="../trading_data.db",
                data_path="../data/backtesting_csv",
                auto_download=False,  # No downloading during backtesting
                days_history=90
            )
            
            # Initialize mock broker
            self.broker = MockIBKRAdapter(
                data_path="../data/backtesting_csv",
                simulation_mode=True
            )
            
            # Initialize event bus
            self.event_bus = AsyncEventBus()
            
            # Connect components
            await self.data_provider.connect()
            await self.broker.connect()
            
            # Initialize strategy engine (same as live system)
            self.strategy_engine = MultiStrategyEngine()
            await self.strategy_engine.initialize(self.event_bus)
            
            self.logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            return False
    
    async def run_backtest(self, 
                          symbols: Optional[List[str]] = None,
                          max_symbols: int = 10,
                          days_back: int = 30) -> Dict[str, BacktestResults]:
        """
        Run backtest on traded symbols
        
        Args:
            symbols: Specific symbols to test (None = all available)
            max_symbols: Maximum number of symbols to test
            days_back: How many days of history to test
            
        Returns:
            Dictionary of results per symbol
        """
        self.logger.info("🚀 STARTING MACDV BACKTESTING...")
        self.logger.info("=" * 60)
        
        # Get symbols to test
        if symbols is None:
            available_symbols = self.data_provider.get_available_traded_symbols()
            symbols = available_symbols[:max_symbols]
        
        self.logger.info(f"📊 Testing {len(symbols)} symbols:")
        self.logger.info(f"   {symbols}")
        self.logger.info(f"📅 Testing period: {days_back} days back")
        
        # Test each symbol
        for i, symbol in enumerate(symbols):
            self.logger.info(f"\n📈 Testing {i+1}/{len(symbols)}: {symbol}")
            self.logger.info("-" * 40)
            
            try:
                result = await self._test_symbol(symbol, days_back)
                self.results[symbol] = result
                
                self.logger.info(f"   ✅ {symbol}: {result.total_trades} trades, "
                                f"{result.win_rate:.1f}% WR, ${result.total_pnl:.2f} PnL")
                
            except Exception as e:
                self.logger.error(f"   ❌ Error testing {symbol}: {e}")
                continue
        
        # Calculate overall results
        self._calculate_overall_results()
        
        # Print summary
        self._print_results_summary()
        
        return self.results
    
    async def _test_symbol(self, symbol: str, days_back: int) -> BacktestResults:
        """Test a single symbol"""
        result = BacktestResults(symbol=symbol)
        
        # Get historical data
        bars = await self.data_provider.get_bars_by_date_range(
            symbol=symbol,
            timeframe="1 min", 
            days_back=days_back
        )
        
        if not bars:
            self.logger.warning(f"   No data available for {symbol}")
            return result
        
        self.logger.info(f"   📊 Processing {len(bars)} bars...")
        
        # Track active position
        active_position = None
        trailing_stop_price = None
        position_high_price = None
        
        # Process each bar
        for i, bar in enumerate(bars):
            try:
                # Check for strategy signal
                signal = await self.strategy_engine.on_bar(bar)
                
                # Handle new entry signal
                if signal and not active_position:
                    active_position = await self._handle_entry_signal(signal, bar, result)
                    if active_position:
                        position_high_price = bar.close
                        trailing_stop_price = bar.close * (1 - self.trailing_stop_pct)
                
                # Handle active position management
                elif active_position:
                    active_position, trailing_stop_price, position_high_price = await self._handle_position_management(
                        active_position, bar, result, trailing_stop_price, position_high_price, i
                    )
            
            except Exception as e:
                self.logger.debug(f"Error processing bar {i} for {symbol}: {e}")
                continue
        
        # Close any remaining position at end of data
        if active_position:
            await self._close_position(active_position, bars[-1], result, "END_OF_DATA")
        
        # Calculate metrics
        self._calculate_symbol_metrics(result)
        
        return result
    
    async def _handle_entry_signal(self, signal, bar: MarketData, result: BacktestResults) -> Optional[BacktestTrade]:
        """Handle new entry signal"""
        try:
            # Calculate position size
            quantity = int(self.position_size / bar.close)
            if quantity <= 0:
                return None
            
            # Create trade record
            trade = BacktestTrade(
                symbol=bar.symbol,
                entry_time=bar.timestamp,
                entry_price=bar.close,
                quantity=quantity,
                strategy="macdv_smallcaps"
            )
            
            # Execute order through mock broker
            order = await self.broker.place_order(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET
            )
            
            if order:
                self.logger.debug(f"   📈 ENTRY: {bar.symbol} @ ${bar.close:.2f} x{quantity}")
                return trade
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error handling entry signal: {e}")
            return None
    
    async def _handle_position_management(self, 
                                        position: BacktestTrade, 
                                        bar: MarketData, 
                                        result: BacktestResults,
                                        trailing_stop_price: float,
                                        position_high_price: float,
                                        bar_index: int) -> tuple:
        """Handle active position management with trailing stops"""
        try:
            current_price = bar.close
            
            # Update position high
            if current_price > position_high_price:
                position_high_price = current_price
                # Update trailing stop
                new_trailing_stop = current_price * (1 - self.trailing_stop_pct)
                trailing_stop_price = max(trailing_stop_price, new_trailing_stop)
            
            # Calculate current P&L
            unrealized_pnl = (current_price - position.entry_price) * position.quantity
            unrealized_pnl_pct = (current_price / position.entry_price - 1) * 100
            
            # Update position metrics
            position.max_profit_reached = max(position.max_profit_reached, unrealized_pnl)
            if unrealized_pnl < 0:
                position.max_drawdown = min(position.max_drawdown, unrealized_pnl)
            
            # Check exit conditions
            
            # 1. Trailing stop hit
            if current_price <= trailing_stop_price:
                await self._close_position(position, bar, result, "TRAILING_STOP")
                return None, None, None
            
            # 2. Maximum hold time reached
            hold_time = (bar.timestamp - position.entry_time).total_seconds() / 60
            if hold_time >= self.max_hold_minutes:
                await self._close_position(position, bar, result, "MAX_HOLD_TIME")
                return None, None, None
            
            # 3. End of trading day (4:00 PM ET)
            if bar.timestamp.hour >= 16:
                await self._close_position(position, bar, result, "END_OF_DAY")
                return None, None, None
            
            # Position remains active
            return position, trailing_stop_price, position_high_price
            
        except Exception as e:
            self.logger.error(f"Error in position management: {e}")
            # Close position on error
            await self._close_position(position, bar, result, "ERROR")
            return None, None, None
    
    async def _close_position(self, 
                            position: BacktestTrade, 
                            bar: MarketData, 
                            result: BacktestResults, 
                            exit_reason: str):
        """Close an active position"""
        try:
            # Execute exit order
            order = await self.broker.place_order(
                symbol=bar.symbol,
                side=OrderSide.SELL,
                quantity=position.quantity,
                order_type=OrderType.MARKET
            )
            
            if order:
                # Update trade record
                position.exit_time = bar.timestamp
                position.exit_price = bar.close
                position.exit_reason = exit_reason
                
                # Calculate P&L
                position.pnl = (position.exit_price - position.entry_price) * position.quantity
                position.pnl_pct = (position.exit_price / position.entry_price - 1) * 100
                
                # Calculate duration
                duration = position.exit_time - position.entry_time
                position.duration_minutes = int(duration.total_seconds() / 60)
                
                # Add to results
                result.trades.append(position)
                
                self.logger.debug(f"   📉 EXIT: {position.symbol} @ ${position.exit_price:.2f} "
                                f"| PnL: ${position.pnl:.2f} ({position.pnl_pct:.1f}%) "
                                f"| Reason: {exit_reason}")
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
    
    def _calculate_symbol_metrics(self, result: BacktestResults):
        """Calculate metrics for a symbol's results"""
        if not result.trades:
            return
        
        trades = result.trades
        result.total_trades = len(trades)
        
        # Win/Loss metrics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)
        result.win_rate = (result.winning_trades / result.total_trades) * 100 if result.total_trades > 0 else 0
        
        # P&L metrics
        result.total_pnl = sum(t.pnl for t in trades)
        result.avg_pnl = result.total_pnl / result.total_trades if result.total_trades > 0 else 0
        result.best_trade = max(t.pnl for t in trades) if trades else 0
        result.worst_trade = min(t.pnl for t in trades) if trades else 0
        
        # Duration metrics
        result.avg_duration_minutes = sum(t.duration_minutes for t in trades) / result.total_trades if result.total_trades > 0 else 0
        
        # Consecutive wins/losses
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        for trade in trades:
            if trade.pnl > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        result.max_consecutive_wins = max_consecutive_wins
        result.max_consecutive_losses = max_consecutive_losses
    
    def _calculate_overall_results(self):
        """Calculate overall results across all symbols"""
        if not self.results:
            return
        
        all_trades = []
        for result in self.results.values():
            all_trades.extend(result.trades)
        
        if not all_trades:
            return
        
        self.overall_results = BacktestResults(symbol="OVERALL", trades=all_trades)
        self._calculate_symbol_metrics(self.overall_results)
    
    def _print_results_summary(self):
        """Print formatted results summary"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 BACKTESTING RESULTS SUMMARY")
        self.logger.info("=" * 60)
        
        if self.overall_results:
            r = self.overall_results
            self.logger.info(f"🎯 OVERALL PERFORMANCE:")
            self.logger.info(f"   Total trades: {r.total_trades}")
            self.logger.info(f"   Win rate: {r.win_rate:.1f}%")
            self.logger.info(f"   Total P&L: ${r.total_pnl:.2f}")
            self.logger.info(f"   Average P&L: ${r.avg_pnl:.2f}")
            self.logger.info(f"   Best trade: ${r.best_trade:.2f}")
            self.logger.info(f"   Worst trade: ${r.worst_trade:.2f}")
            self.logger.info(f"   Avg duration: {r.avg_duration_minutes:.1f} minutes")
        
        self.logger.info(f"\n📈 PER-SYMBOL RESULTS:")
        for symbol, result in sorted(self.results.items()):
            if result.total_trades > 0:
                self.logger.info(f"   {symbol}: {result.total_trades} trades, "
                                f"{result.win_rate:.1f}% WR, ${result.total_pnl:.2f} PnL")
        
        self.logger.info(f"\n✅ BACKTESTING COMPLETED")
    
    def save_results_to_csv(self, filename: str = None, suffix: str = ""):
        """Save detailed results to CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results{suffix}_{timestamp}.csv"
        
        all_trades = []
        for symbol, result in self.results.items():
            for trade in result.trades:
                trade_dict = {
                    'symbol': trade.symbol,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'pnl': trade.pnl,
                    'pnl_pct': trade.pnl_pct,
                    'duration_minutes': trade.duration_minutes,
                    'exit_reason': trade.exit_reason,
                    'max_profit_reached': trade.max_profit_reached,
                    'max_drawdown': trade.max_drawdown,
                    'strategy': trade.strategy
                }
                all_trades.append(trade_dict)
        
        if all_trades:
            df = pd.DataFrame(all_trades)
            df.to_csv(filename, index=False)
            self.logger.info(f"📁 Results saved to: {filename}")
        
        return filename


async def main():
    """Example usage of the backtesting engine"""
    # Initialize and run backtest
    engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,
        max_hold_minutes=240,
        debug=True
    )
    
    # Initialize
    if not await engine.initialize():
        print("❌ Failed to initialize backtesting engine")
        return
    
    # Run backtest with already downloaded symbols
    results = await engine.run_backtest(
        symbols=['DLTH', 'NUKK', 'NEXT', 'ASST', 'HOUR', 'HUDI', 'SHFS', 'BBLG', 'CRWG', 'REVB', 'BTBD', 'DSY'],
        max_symbols=12,
        days_back=30
    )
    
    # Save results
    engine.save_results_to_csv()


if __name__ == "__main__":
    asyncio.run(main())