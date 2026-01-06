# core/simulation_manager.py
"""
Simulation manager for coordinated backtesting and development.
Manages mock adapters and provides comprehensive testing environment.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.interfaces import TradingConfig, OrderSide, OrderType, MarketData, SignalType


class SimulationManager:
    """
    Manager for trading system simulation and backtesting.
    Coordinates mock adapters and provides testing utilities.
    """
    
    def __init__(self, config: TradingConfig, data_path: str = "data/csv"):
        self.config = config
        self.data_path = Path(data_path)
        self.logger = logging.getLogger("SimulationManager")
        self.logger.info("🎮 SIMULATION MANAGER INITIALIZED")
        
        # Create adapters
        self.mock_broker = MockIBKRAdapter(data_path=str(self.data_path), simulation_mode=True)
        self.csv_provider = CSVDataProvider(data_path=str(self.data_path))
        
        # Simulation state
        self._simulation_running = False
        self._simulation_start_time = None
        self._simulation_speed = 1.0  # 1x real-time
        self._current_sim_time = datetime.now()
        
        # Performance tracking
        self._simulation_stats = {
            'trades_executed': 0,
            'signals_generated': 0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_return': 0.0
        }
        
        # Data setup
        self.data_path.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self, create_sample_data: bool = True):
        """Initialize simulation environment"""
        try:
            # Connect adapters
            await self.mock_broker.connect()
            await self.csv_provider.connect()
            
            # Create sample data if requested
            if create_sample_data and not self.csv_provider.get_available_symbols():
                self.logger.info("📊 Creating sample data for simulation...")
                self.csv_provider.create_sample_data(days=30)
                self.mock_broker.load_sample_data()
            
            self.logger.info("✅ Simulation environment initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize simulation: {e}")
            return False
    
    async def start_simulation(self, duration_hours: int = 24, speed_multiplier: float = 1.0):
        """Start simulation for specified duration"""
        if self._simulation_running:
            self.logger.warning("Simulation already running")
            return
        
        self._simulation_running = True
        self._simulation_start_time = datetime.now()
        self._simulation_speed = speed_multiplier
        self._current_sim_time = datetime.now()
        
        self.logger.info(f"🚀 Starting simulation: {duration_hours}h @ {speed_multiplier}x speed")
        
        try:
            end_time = self._simulation_start_time + timedelta(hours=duration_hours)
            
            while self._simulation_running and datetime.now() < end_time:
                # Update simulation time
                self._current_sim_time += timedelta(minutes=1 * speed_multiplier)
                
                # Simulate market movements
                await self._simulate_market_tick()
                
                # Sleep based on speed multiplier
                sleep_time = 60 / speed_multiplier if speed_multiplier > 0 else 1
                await asyncio.sleep(min(sleep_time, 1.0))  # Max 1 second between ticks
            
            self.logger.info("⏹️ Simulation completed")
            
        except Exception as e:
            self.logger.error(f"Simulation error: {e}")
        finally:
            self._simulation_running = False
    
    async def _simulate_market_tick(self):
        """Simulate a market tick with price movements"""
        # This would update mock prices, trigger events, etc.
        # For now, just update simulation stats
        pass
    
    def stop_simulation(self):
        """Stop running simulation"""
        self._simulation_running = False
        self.logger.info("🛑 Simulation stopped")
    
    async def run_backtest(self, symbols: List[str], start_date: datetime, 
                          end_date: datetime, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run comprehensive backtest
        """
        self.logger.info(f"🧪 Starting backtest: {len(symbols)} symbols from {start_date} to {end_date}")
        
        results = {
            'start_date': start_date,
            'end_date': end_date,
            'symbols': symbols,
            'strategy_config': strategy_config,
            'trades': [],
            'performance': {},
            'risk_metrics': {},
            'daily_returns': []
        }
        
        try:
            # Reset simulation state
            self.mock_broker.reset_simulation()
            
            # Validate data availability
            available_symbols = []
            for symbol in symbols:
                bars = await self.csv_provider.get_bars(symbol, "1 min", 1)
                if bars:
                    available_symbols.append(symbol)
                else:
                    self.logger.warning(f"No data available for {symbol}")
            
            if not available_symbols:
                self.logger.error("No data available for any symbols")
                return results
            
            results['available_symbols'] = available_symbols
            self.logger.info(f"📊 Backtesting {len(available_symbols)} symbols with data")
            
            # Simulate trading period
            current_date = start_date
            daily_values = []
            
            while current_date <= end_date:
                # Get market data for the day
                daily_value = await self._simulate_trading_day(available_symbols, current_date)
                daily_values.append({
                    'date': current_date,
                    'portfolio_value': daily_value
                })
                
                current_date += timedelta(days=1)
            
            # Calculate performance metrics
            results['daily_returns'] = daily_values
            results['performance'] = self._calculate_performance_metrics(daily_values)
            results['trades'] = await self._get_trade_history()
            results['final_stats'] = self.mock_broker.get_performance_stats()
            
            self.logger.info("✅ Backtest completed")
            return results
            
        except Exception as e:
            self.logger.error(f"Backtest error: {e}")
            results['error'] = str(e)
            return results
    
    async def _simulate_trading_day(self, symbols: List[str], date: datetime, 
                                   realistic_timing: bool = True) -> float:
        """Simulate one trading day with realistic bar-by-bar processing"""
        print(f"   📅 Procesando día {date.strftime('%Y-%m-%d')} - {len(symbols)} símbolos")
        
        daily_trades = 0
        
        for symbol_idx, symbol in enumerate(symbols):
            try:
                # Get bars for this symbol for the day
                bars = await self.csv_provider.get_bars(symbol, "1 min", 390)  # Full trading day
                
                if not bars:
                    continue
                    
                # Filter bars for the specific date
                date_bars = [bar for bar in bars if bar.timestamp.date() == date.date()]
                
                if not date_bars:
                    continue
                
                print(f"      📊 {symbol} ({symbol_idx+1}/{len(symbols)}): {len(date_bars)} barras")
                
                # Process bars sequentially with realistic timing
                for i, bar in enumerate(date_bars):
                    # Simulate processing time for realistic execution
                    if realistic_timing and i % 100 == 0 and i > 0:
                        await asyncio.sleep(0.05)  # Smaller delay for multi-symbol
                        
                    # Use configured trading hours
                    if not self.config.is_trading_time(bar.timestamp):
                        continue  # Outside configured trading hours
                    
                    # Use multi-strategy engine for trading decisions
                    try:
                        # Import and create multi-strategy engine
                        if not hasattr(self, '_multi_engine'):
                            try:
                                from strategies.multi_strategy_engine import MultiStrategyEngine
                                # Create strategy engine (EventBus is optional)
                                self._multi_engine = MultiStrategyEngine()
                            except ImportError:
                                # Fallback to simple logic if multi-strategy not available
                                self._multi_engine = None
                        
                        if self._multi_engine:
                            # Create market data for the strategy
                            market_data = MarketData(
                                symbol=symbol,
                                timestamp=bar.timestamp,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                volume=bar.volume
                            )
                            
                            # Get signal from multi-strategy engine
                            signal = await self._multi_engine.on_bar(market_data)
                            
                            if signal and signal.signal_type:
                                # Execute trade based on signal
                                if signal.signal_type == SignalType.LONG:
                                    position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 50)
                                    await self.mock_broker.place_order(
                                        symbol=symbol,
                                        side=OrderSide.BUY,
                                        quantity=position_size,
                                        order_type=OrderType.MARKET,
                                        price=bar.close,
                                        signal=signal
                                    )
                                    daily_trades += 1
                                    
                                elif signal.signal_type == SignalType.SHORT:
                                    position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 50)
                                    await self.mock_broker.place_order(
                                        symbol=symbol,
                                        side=OrderSide.SELL,
                                        quantity=position_size,
                                        order_type=OrderType.MARKET,
                                        price=bar.close,
                                        signal=signal
                                    )
                                    daily_trades += 1
                                    
                                elif signal.signal_type == SignalType.EXIT_LONG:
                                    positions = await self.mock_broker.get_positions()
                                    if symbol in positions and positions[symbol].get('quantity', 0) > 0:
                                        position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 50)
                                        await self.mock_broker.place_order(
                                            symbol=symbol,
                                            side=OrderSide.SELL,
                                            quantity=min(position_size, positions[symbol]['quantity']),
                                            order_type=OrderType.MARKET,
                                            price=bar.close,
                                            signal=signal
                                        )
                                        daily_trades += 1
                                        
                                elif signal.signal_type == SignalType.EXIT_SHORT:
                                    positions = await self.mock_broker.get_positions()
                                    if symbol in positions and positions[symbol].get('quantity', 0) < 0:
                                        await self.mock_broker.place_order(
                                            symbol=symbol,
                                            side=OrderSide.BUY,
                                            quantity=abs(positions[symbol]['quantity']),
                                            order_type=OrderType.MARKET,
                                            price=bar.close,
                                            signal=signal
                                        )
                                        daily_trades += 1
                        else:
                            # Fallback to simple logic when multi-strategy unavailable
                            if i % 120 == 60 and i > 60:  # Buy signal
                                class SimpleSignal:
                                    def __init__(self):
                                        self.strategy_name = "Simple_Fallback"
                                        self.metadata = {"strategy": "Simple_Fallback", "reason": "no_multi_strategy"}
                                        
                                await self.mock_broker.place_order(
                                    symbol=symbol,
                                    side=OrderSide.BUY,
                                    quantity=50,
                                    order_type=OrderType.MARKET,
                                    price=bar.close,
                                    signal=SimpleSignal()
                                )
                                daily_trades += 1
                                
                            elif i % 160 == 0 and i > 120:  # Sell signal
                                positions = await self.mock_broker.get_positions()
                                if symbol in positions and positions[symbol].get('quantity', 0) > 0:
                                    class SimpleExitSignal:
                                        def __init__(self):
                                            self.strategy_name = "Simple_Exit"
                                            self.metadata = {"strategy": "Simple_Exit", "reason": "simple_fallback_exit"}
                                            
                                    await self.mock_broker.place_order(
                                        symbol=symbol,
                                        side=OrderSide.SELL,
                                        quantity=min(50, positions[symbol]['quantity']),
                                        order_type=OrderType.MARKET,
                                        price=bar.close,
                                        signal=SimpleExitSignal()
                                    )
                                    daily_trades += 1
                                
                    except Exception as e:
                        self.logger.debug(f"Error in {symbol} trade simulation: {e}")
                        
            except Exception as e:
                self.logger.debug(f"Error processing {symbol}: {e}")
                continue
        
        if daily_trades > 0:
            print(f"      ✅ Trades ejecutados en el día: {daily_trades}")
        
        # Return updated portfolio value
        account_info = await self.mock_broker.get_account_info()
        return account_info.get('total_value', 10000.0)
    
    async def _get_trade_history(self) -> List[Dict]:
        """Get history of executed trades"""
        orders = await self.mock_broker.get_orders()
        trades = []
        
        for order in orders:
            if order.status.value == "filled":
                trades.append({
                    'timestamp': order.timestamp,
                    'symbol': order.symbol,
                    'side': order.side.value,
                    'quantity': order.quantity,
                    'price': order.avg_fill_price,
                    'value': order.quantity * order.avg_fill_price
                })
        
        return trades
    
    def _calculate_performance_metrics(self, daily_values: List[Dict]) -> Dict[str, Any]:
        """Calculate performance metrics from daily values"""
        if not daily_values:
            return {}
        
        values = [d['portfolio_value'] for d in daily_values]
        initial_value = values[0]
        final_value = values[-1]
        
        # Calculate returns
        returns = []
        for i in range(1, len(values)):
            daily_return = (values[i] - values[i-1]) / values[i-1]
            returns.append(daily_return)
        
        # Performance metrics
        total_return = (final_value - initial_value) / initial_value
        total_return_pct = total_return * 100
        
        # Drawdown calculation
        peak = initial_value
        max_drawdown = 0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe ratio (simplified)
        if returns:
            avg_return = sum(returns) / len(returns)
            return_std = (sum([(r - avg_return)**2 for r in returns]) / len(returns))**0.5
            sharpe_ratio = (avg_return / return_std) * (252**0.5) if return_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'sharpe_ratio': sharpe_ratio,
            'trading_days': len(daily_values),
            'initial_value': initial_value,
            'final_value': final_value
        }
    
    async def test_strategy_on_symbol(self, symbol: str, timeframe: str = "1 min", 
                                     bars_count: int = 100, strategy_name: str = "simple",
                                     realistic_timing: bool = True, days_back: int = None) -> Dict[str, Any]:
        """Test strategy on a single symbol with realistic timing"""
        try:
            # Get historical data - use days_back if specified, otherwise use bars_count
            if days_back is not None:
                bars = await self.csv_provider.get_bars_by_date_range(symbol, timeframe, days_back)
                self.logger.info(f"📅 Using date range: {days_back} days back from today")
            else:
                bars = await self.csv_provider.get_bars(symbol, timeframe, bars_count)
                self.logger.info(f"📊 Using bar count: {bars_count} bars")
            
            if not bars:
                return {'error': f'No data available for {symbol}'}
            
            print(f"   📊 Analizando {len(bars)} barras desde {bars[0].timestamp} hasta {bars[-1].timestamp}")
            
            # Reset broker state
            self.mock_broker.reset_simulation()
            
            # Reset strategy daily counters if multi_strategy is used
            if strategy_name == "multi_strategy" and hasattr(self, '_multi_engine') and self._multi_engine:
                # Reset all strategy daily counters
                if hasattr(self._multi_engine, 'strategies'):
                    for strategy_instance in self._multi_engine.strategies.values():
                        if hasattr(strategy_instance, 'daily_signals_count'):
                            strategy_instance.daily_signals_count = 0
                            self.logger.info(f"🔄 Reset daily signals counter for {strategy_instance.__class__.__name__}")
                        if hasattr(strategy_instance, 'last_explosion_time'):
                            strategy_instance.last_explosion_time.clear()
                        if hasattr(strategy_instance, 'explosion_tracking'):
                            strategy_instance.explosion_tracking.clear()
            
            # Simulate trading based on strategy with realistic timing
            signals_generated = 0
            trades_executed = 0
            start_time = datetime.now()
            
            if strategy_name == "simple":
                print(f"   🎯 Estrategia: Compra/venta secuencial con timing realista")
                # Simple strategy: process bar by bar with timing
                for i, bar in enumerate(bars):
                    # Simulate real-time processing
                    if realistic_timing and i % 50 == 0:  # Show progress every 50 bars
                        await asyncio.sleep(0.1)  # Small delay to simulate processing
                        print(f"      📈 Procesando barra {i+1}/{len(bars)} - Precio: ${bar.close:.2f}")
                    
                    try:
                        # Use configured trading hours
                        if not self.config.is_trading_time(bar.timestamp):
                            continue  # Outside configured trading hours
                            
                        if i % 80 == 40 and i > 50:  # Buy signal (less frequent)
                            class SimpleTestSignal:
                                def __init__(self):
                                    self.strategy_name = "Simple_Test"
                                    self.metadata = {"strategy": "Simple_Test", "reason": "simple_strategy_test"}
                                    
                            order_id = await self.mock_broker.place_order(
                                symbol=symbol,
                                side=OrderSide.BUY,
                                quantity=100,
                                order_type=OrderType.MARKET,
                                signal=SimpleTestSignal()
                            )
                            signals_generated += 1
                            trades_executed += 1
                            print(f"      🛒 BUY ejecutado en barra {i+1} @ ${bar.close:.2f}")
                            
                        elif i % 80 == 0 and i > 100:  # Sell signal
                            positions = await self.mock_broker.get_positions()
                            if symbol in positions and positions[symbol].quantity > 0:
                                class SimpleTestExitSignal:
                                    def __init__(self):
                                        self.strategy_name = "Simple_Test_Exit" 
                                        self.metadata = {"strategy": "Simple_Test_Exit", "reason": "simple_test_exit"}
                                        
                                order_id = await self.mock_broker.place_order(
                                    symbol=symbol,
                                    side=OrderSide.SELL,
                                    quantity=min(100, positions[symbol].quantity),
                                    order_type=OrderType.MARKET,
                                    signal=SimpleTestExitSignal()
                                )
                                signals_generated += 1
                                trades_executed += 1
                                print(f"      💸 SELL ejecutado en barra {i+1} @ ${bar.close:.2f}")
                                
                    except Exception as e:
                        self.logger.debug(f"Error in trade simulation: {e}")
                        pass
            
            elif strategy_name == "momentum":
                print(f"   📈 Estrategia: Momentum basado en MA20")
                # Momentum strategy with realistic timing
                if len(bars) >= 20:
                    for i in range(20, len(bars)):
                        # Simulate processing time
                        if realistic_timing and i % 50 == 0:
                            await asyncio.sleep(0.1)
                            print(f"      📊 Analizando barra {i+1}/{len(bars)}")
                            
                        current_bar = bars[i]
                        current_price = current_bar.close
                        ma_20 = sum(bars[j].close for j in range(i-20, i)) / 20
                        
                        # Only trade during market hours
                        bar_hour = current_bar.timestamp.hour if hasattr(current_bar.timestamp, 'hour') else 10
                        bar_minute = current_bar.timestamp.minute if hasattr(current_bar.timestamp, 'minute') else 0
                        
                        if not self.config.is_trading_time(bar.timestamp):
                            continue  # Outside configured trading hours
                        
                        try:
                            if current_price > ma_20 * 1.005 and i % 30 == 0:  # 0.5% above MA, less frequent
                                class MomentumSignal:
                                    def __init__(self):
                                        self.strategy_name = "Momentum_MA20"
                                        self.metadata = {"strategy": "Momentum_MA20", "reason": "above_ma20"}
                                        
                                order_id = await self.mock_broker.place_order(
                                    symbol=symbol,
                                    side=OrderSide.BUY,
                                    quantity=50,
                                    order_type=OrderType.MARKET,
                                    signal=MomentumSignal()
                                )
                                signals_generated += 1
                                trades_executed += 1
                                print(f"      🚀 MOMENTUM BUY en barra {i+1} @ ${current_price:.2f} (MA20: ${ma_20:.2f})")
                                
                            elif current_price < ma_20 * 0.995:  # 0.5% below MA
                                positions = await self.mock_broker.get_positions()
                                if symbol in positions and positions[symbol].quantity > 0:
                                    class MomentumExitSignal:
                                        def __init__(self):
                                            self.strategy_name = "Momentum_MA20_Exit"
                                            self.metadata = {"strategy": "Momentum_MA20_Exit", "reason": "below_ma20"}
                                            
                                    order_id = await self.mock_broker.place_order(
                                        symbol=symbol,
                                        side=OrderSide.SELL,
                                        quantity=min(50, positions[symbol].quantity),
                                        order_type=OrderType.MARKET,
                                        signal=MomentumExitSignal()
                                    )
                                    signals_generated += 1
                                    trades_executed += 1
                                    print(f"      📉 MOMENTUM SELL en barra {i+1} @ ${current_price:.2f} (MA20: ${ma_20:.2f})")
                                    
                        except Exception as e:
                            self.logger.debug(f"Error in momentum trade: {e}")
                            pass
            
            elif strategy_name == "multi_strategy":
                print(f"   🎯 Estrategia: Multi-Strategy Engine con todas las estrategias")
                
                # Import the multi-strategy engine
                try:
                    from strategies.multi_strategy_engine import MultiStrategyEngine
                    
                    # Create strategy engine (EventBus is optional)
                    multi_engine = MultiStrategyEngine()
                    
                    # Process bars with multi-strategy logic
                    for i, bar in enumerate(bars):
                        # Simulate processing time
                        if realistic_timing and i % 50 == 0:
                            await asyncio.sleep(0.1)
                            print(f"      🔄 Multi-análisis barra {i+1}/{len(bars)} - Precio: ${bar.close:.2f}")
                        
                        # Use configured trading hours
                        if not self.config.is_trading_time(bar.timestamp):
                            continue  # Outside configured trading hours
                        
                        # Extract time for day trading rules
                        bar_hour = bar.timestamp.hour if hasattr(bar.timestamp, 'hour') else 10
                        bar_minute = bar.timestamp.minute if hasattr(bar.timestamp, 'minute') else 0
                        # Day trading close time depends on mode
                        if self.config.trading_hours_mode == "SIMULATION_MODE":
                            day_trade_close = (15, 50)  # 15:50 ES - Close based on available CSV data
                        else:
                            day_trade_close = (21, 50)  # 21:50 ES = 3:50 PM ET for real trading
                        
                        # DAY TRADING RULE: Close all positions at 3:50 PM
                        if (bar_hour == day_trade_close[0] and bar_minute >= day_trade_close[1]) or bar_hour > day_trade_close[0]:
                            await self._close_all_day_trading_positions(symbol, bar)
                            continue  # Skip strategy processing during close time
                        
                        try:
                            # Update current price in mock broker to avoid loops during order execution
                            if hasattr(self.mock_broker, 'update_current_price'):
                                self.mock_broker.update_current_price(symbol, bar.close)
                            
                            # Create market data for the strategy
                            market_data = MarketData(
                                symbol=symbol,
                                timestamp=bar.timestamp,
                                open=bar.open,
                                high=bar.high,
                                low=bar.low,
                                close=bar.close,
                                volume=bar.volume
                            )
                            
                            # Get signal from multi-strategy engine
                            signal = await multi_engine.on_bar(market_data)
                            
                            # DEBUG: Log EVERY signal check to find the disconnect
                            if signal and signal.signal_type:
                                print(f"      ✅ SIGNAL RECEIVED! Barra {i+1}: {signal.signal_type.value} @ ${bar.close:.2f}")
                            
                            # Debug: mostrar qué señales se generan
                            if i % 100 == 0:  # Cada 100 barras mostrar debug
                                if signal:
                                    print(f"      🔍 Debug barra {i}: Señal={signal.signal_type.value if signal.signal_type else 'None'}")
                                else:
                                    print(f"      🔍 Debug barra {i}: Sin señal generada")
                            
                            if signal and signal.signal_type:
                                signals_generated += 1
                                # Ensure position size attached
                                if not hasattr(signal, 'position_size') or signal.position_size is None:
                                    try:
                                        default_capital = 10000.0
                                        risk_pct = 0.02
                                        size = multi_engine.calculate_position_size(signal, default_capital, risk_pct)
                                        signal.position_size = size
                                        signal.metadata['position_size'] = size
                                    except Exception as e:
                                        print(f"      ⚠️ Error calculating position size: {e}")
                                print(f"      🔥 ABOUT TO EXECUTE! Señal: {signal.signal_type.value}, Position size: {getattr(signal, 'position_size', 'NOT_SET')}")
                                
                                # Execute trade based on signal
                                if signal.signal_type == SignalType.LONG:
                                    print(f"      💰 EXECUTING LONG ORDER for {symbol} @ ${bar.close:.2f}")
                                    try:
                                        # Get position size from signal metadata or use default
                                        position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 100)
                                        
                                        order_id = await self.mock_broker.place_order(
                                            symbol=symbol,
                                            side=OrderSide.BUY,
                                            quantity=position_size,
                                            order_type=OrderType.MARKET,
                                            price=bar.close,  # Pass current bar price
                                            timestamp=bar.timestamp,  # Pass real timestamp from CSV
                                            signal=signal  # Pass signal with strategy info
                                        )
                                        trades_executed += 1
                                        print(f"      ✅ ORDER EXECUTED! ID: {order_id}")
                                        print(f"      🎯 MULTI-LONG en barra {i+1} @ ${bar.close:.2f} (Estrategia: {getattr(signal, 'strategy_name', 'MultiStrategy')})")
                                    except Exception as trade_error:
                                        print(f"      ❌ TRADE EXECUTION ERROR: {trade_error}")
                                        import traceback
                                        print(f"      📋 Trade error stack:")
                                        traceback.print_exc()
                                    
                                elif signal.signal_type == SignalType.SHORT:
                                    try:
                                        position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 100)
                                        order_id = await self.mock_broker.place_order(
                                            symbol=symbol,
                                            side=OrderSide.SELL,
                                            quantity=position_size,
                                            order_type=OrderType.MARKET,
                                            price=bar.close,
                                            timestamp=bar.timestamp,
                                            signal=signal
                                        )
                                        trades_executed += 1
                                        print(f"      ✅ SHORT ORDER EXECUTED! ID: {order_id}")
                                        print(f"      🎯 MULTI-SHORT en barra {i+1} @ ${bar.close:.2f} (Estrategia: {getattr(signal, 'strategy_name', 'MultiStrategy')})")
                                    except Exception as e:
                                        print(f"      ❌ SHORT TRADE ERROR: {e}")
                                    
                                elif signal.signal_type == SignalType.EXIT_LONG:
                                    try:
                                        positions = await self.mock_broker.get_positions()
                                        if symbol in positions and positions[symbol].get('quantity', 0) > 0:
                                            position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 100)
                                            order_id = await self.mock_broker.place_order(
                                                symbol=symbol,
                                                side=OrderSide.SELL,
                                                quantity=min(position_size, positions[symbol]['quantity']),
                                                order_type=OrderType.MARKET,
                                                price=bar.close,
                                                timestamp=bar.timestamp,
                                                signal=signal
                                            )
                                            trades_executed += 1
                                            print(f"      ✅ EXIT-LONG ORDER EXECUTED! ID: {order_id}")
                                            print(f"      🎯 MULTI-EXIT-LONG en barra {i+1} @ ${bar.close:.2f} (Estrategia: {getattr(signal, 'strategy_name', 'MultiStrategy')})")
                                        else:
                                            print(f"      ⚠️ No LONG position to exit for {symbol}")
                                    except Exception as e:
                                        print(f"      ❌ EXIT-LONG TRADE ERROR: {e}")
                                        
                                elif signal.signal_type == SignalType.EXIT_SHORT:
                                    try:
                                        positions = await self.mock_broker.get_positions()
                                        if symbol in positions and positions[symbol].get('quantity', 0) < 0:
                                            order_id = await self.mock_broker.place_order(
                                                symbol=symbol,
                                                side=OrderSide.BUY,
                                                quantity=abs(positions[symbol]['quantity']),
                                                order_type=OrderType.MARKET,
                                                price=bar.close,
                                                timestamp=bar.timestamp,
                                                signal=signal
                                            )
                                            trades_executed += 1
                                            print(f"      ✅ EXIT-SHORT ORDER EXECUTED! ID: {order_id}")
                                            print(f"      🎯 MULTI-EXIT-SHORT en barra {i+1} @ ${bar.close:.2f} (Estrategia: {getattr(signal, 'strategy_name', 'MultiStrategy')})")
                                        else:
                                            print(f"      ⚠️ No SHORT position to exit for {symbol}")
                                    except Exception as e:
                                        print(f"      ❌ EXIT-SHORT TRADE ERROR: {e}")
                                        
                        except Exception as e:
                            self.logger.debug(f"Error in multi-strategy trade: {e}")
                            pass
                            
                except ImportError as e:
                    print(f"      ⚠️ Multi-strategy no disponible, usando estrategia simple: {e}")
                    # Fallback to simple strategy
                    strategy_name = "simple"
                    
            else:
                print(f"   ❌ Estrategia '{strategy_name}' no reconocida, usando 'simple'")
                strategy_name = "simple"
            
            # Close any remaining open positions to realize P&L before final stats
            try:
                await self.mock_broker.close_all_positions()
            except AttributeError:
                pass

            # Get final statistics
            final_stats = self.mock_broker.get_performance_stats()
            positions = await self.mock_broker.get_positions()
            
            # Debug: print the actual values to verify
            print(f"      📊 Final debug - signals_generated: {signals_generated}")
            print(f"      📊 Final debug - trades_executed: {trades_executed}")
            print(f"      📊 Final debug - broker stats: {final_stats}")
            
            return {
                'symbol': symbol,
                'bars_analyzed': len(bars),
                'signals_generated': signals_generated,
                'trades_executed': trades_executed,
                'final_stats': final_stats,
                'positions': {k: {
                    'quantity': v.get('quantity', 0) if isinstance(v, dict) else getattr(v, 'quantity', 0),
                    'avg_price': v.get('avg_price', 0) if isinstance(v, dict) else getattr(v, 'avg_price', 0),
                    'market_value': v.get('market_value', 0) if isinstance(v, dict) else getattr(v, 'market_value', 0),
                    'unrealized_pnl': v.get('unrealized_pnl', 0) if isinstance(v, dict) else getattr(v, 'unrealized_pnl', 0)
                } for k, v in positions.items()},
                'data_range': {
                    'start': bars[0].timestamp,
                    'end': bars[-1].timestamp
                }
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status"""
        return {
            'running': self._simulation_running,
            'start_time': self._simulation_start_time,
            'current_time': self._current_sim_time,
            'speed_multiplier': self._simulation_speed,
            'broker_connected': self.mock_broker.is_connected(),
            'data_provider_connected': self.csv_provider.is_connected(),
            'available_symbols': self.csv_provider.get_available_symbols(),
            'stats': self._simulation_stats
        }
    
    async def cleanup(self):
        """Cleanup simulation resources"""
        try:
            self.stop_simulation()
            await self.mock_broker.disconnect()
            await self.csv_provider.disconnect()
            self.logger.info("🧹 Simulation cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    # Utility methods for development
    
    def create_test_scenario(self, scenario_name: str, symbols: List[str], 
                           config_override: Dict[str, Any] = None):
        """Create a test scenario with specific configuration"""
        scenario_config = self.config.__dict__.copy()
        if config_override:
            scenario_config.update(config_override)
        
        self.logger.info(f"🎯 Created test scenario '{scenario_name}' with {len(symbols)} symbols")
        return scenario_config
    
    def get_market_replay(self, symbol: str, date: datetime, hours: int = 6) -> List[Dict]:
        """Get market replay data for a specific day"""
        # This would return intraday data for replay
        # Useful for debugging specific market conditions
        return []
    
    async def _close_all_day_trading_positions(self, symbol: str, bar: MarketData):
        """Close all open positions for day trading rules (at 3:50 PM)"""
        try:
            positions = await self.mock_broker.get_positions()
            if symbol in positions:
                position = positions[symbol]
                quantity = position.get('quantity', 0) if isinstance(position, dict) else getattr(position, 'quantity', 0)
                
                if quantity != 0:
                    # Determine order side
                    side = OrderSide.SELL if quantity > 0 else OrderSide.BUY
                    abs_quantity = abs(quantity)
                    
                    print(f"      🔔 DAY TRADING CLOSE: Cerrando posición {symbol} {abs_quantity} acciones @ ${bar.close:.2f}")
                    
                    # Create a mock signal for day trading close to capture strategy info
                    class MockCloseSignal:
                        def __init__(self):
                            self.strategy_name = "Day_Trading_Close"
                            self.metadata = {"strategy": "Day_Trading_Close", "reason": "automatic_eod_close"}
                    
                    close_signal = MockCloseSignal()
                    
                    # Close position at market price
                    await self.mock_broker.place_order(
                        symbol=symbol,
                        side=side,
                        quantity=abs_quantity,
                        order_type=OrderType.MARKET,
                        price=bar.close,
                        timestamp=bar.timestamp,
                        signal=close_signal
                    )
                    
        except Exception as e:
            self.logger.debug(f"Error closing day trading position for {symbol}: {e}")
    
    async def simulate_daily_sessions(self, symbol: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Simular operativa intraday día por día de forma independiente
        
        Args:
            symbol: Símbolo a simular (ej: "GV")  
            days_back: Número de días hacia atrás a simular
            
        Returns:
            Dict con resultados consolidados de todos los días
        """
        
        self.logger.info(f"🔄 Iniciando simulación intraday por días independientes")
        self.logger.info(f"📊 Símbolo: {symbol} | Días a simular: {days_back}")
        
        # Calcular fechas
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        self.logger.info(f"📅 Período: {start_date} a {end_date}")
        
        # Resultados consolidados
        all_results = {
            'total_days_simulated': 0,
            'days_with_trades': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'total_commissions': 0.0,
            'daily_results': [],
            'symbol': symbol,
            'period': f"{start_date} to {end_date}"
        }
        
        current_date = start_date
        
        while current_date <= end_date:
            # Solo procesar días de semana (lunes a viernes)
            if current_date.weekday() >= 5:  # 5=Sábado, 6=Domingo
                current_date += timedelta(days=1)
                continue
                
            self.logger.debug(f"Simulando día {current_date.strftime('%Y-%m-%d')}")
            
            try:
                # Obtener datos SOLO de este día específico
                daily_data = await self._get_daily_intraday_data(symbol, current_date)
                
                if not daily_data:
                    self.logger.debug(f"No hay datos para {current_date} - saltando día")
                    current_date += timedelta(days=1)
                    continue
                
                # Crear entorno fresco para cada día
                fresh_broker = MockIBKRAdapter()
                await fresh_broker.connect()
                
                # Resetear estado para el día
                await self._reset_daily_state()
                
                # Simular SOLO con datos de este día
                day_result = await self._simulate_single_day(
                    fresh_broker,
                    symbol, 
                    current_date, 
                    daily_data
                )
                
                # Procesar resultados del día
                all_results['total_days_simulated'] += 1
                
                if day_result['trades_executed'] > 0:
                    all_results['days_with_trades'] += 1
                    all_results['total_trades'] += day_result['trades_executed']
                    all_results['winning_trades'] += day_result.get('winning_trades', 0)
                    all_results['losing_trades'] += day_result.get('losing_trades', 0)
                    all_results['total_pnl'] += day_result.get('pnl', 0.0)
                    all_results['total_commissions'] += day_result.get('commissions', 0.0)
                    
                    self.logger.info(f"✅ {current_date}: {day_result['trades_executed']} trades, "
                                   f"P&L: ${day_result.get('pnl', 0.0):.2f}")
                
                # Guardar resultados del día
                day_summary = {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'weekday': current_date.strftime('%A'),
                    'trades_executed': day_result['trades_executed'],
                    'pnl': day_result.get('pnl', 0.0),
                    'commissions': day_result.get('commissions', 0.0),
                    'signals_generated': day_result.get('signals_generated', 0),
                    'winning_trades': day_result.get('winning_trades', 0),
                    'losing_trades': day_result.get('losing_trades', 0)
                }
                all_results['daily_results'].append(day_summary)
                
                await fresh_broker.disconnect()
                
            except Exception as e:
                self.logger.error(f"Error simulando {current_date}: {e}")
                
            current_date += timedelta(days=1)
        
        # Calcular estadísticas finales
        if all_results['total_trades'] > 0:
            all_results['win_rate'] = (all_results['winning_trades'] / all_results['total_trades']) * 100
            all_results['net_pnl'] = all_results['total_pnl'] - all_results['total_commissions']
            all_results['avg_pnl_per_trade'] = all_results['net_pnl'] / all_results['total_trades']
        else:
            all_results['win_rate'] = 0.0
            all_results['net_pnl'] = 0.0
            all_results['avg_pnl_per_trade'] = 0.0
        
        self._print_consolidated_results(all_results)
        
        return all_results
    
    async def _get_daily_intraday_data(self, symbol: str, date: datetime.date) -> List[MarketData]:
        """Obtener datos intraday SOLO de un día específico"""
        
        try:
            # Usar el data provider para obtener datos del día específico
            # Por ahora usamos el CSV provider existente con filtrado por fecha
            
            # Obtener todos los datos y filtrar por fecha
            all_data = await self.data_provider.get_historical_data(
                symbol=symbol,
                timeframe="1 min",
                count=2000  # Suficientes barras para cubrir un día
            )
            
            # Filtrar solo las barras de la fecha específica
            daily_data = []
            for bar in all_data:
                if bar.timestamp.date() == date:
                    daily_data.append(bar)
            
            return daily_data
            
        except Exception as e:
            self.logger.debug(f"Error obteniendo datos para {symbol} en {date}: {e}")
            return []
    
    async def _simulate_single_day(self, broker: MockIBKRAdapter, symbol: str, 
                                 date: datetime.date, daily_data: List[MarketData]) -> Dict[str, Any]:
        """Simular un único día de operativa con datos solo de ese día"""
        
        result = {
            'trades_executed': 0,
            'signals_generated': 0,
            'pnl': 0.0,
            'commissions': 0.0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        
        if not daily_data:
            return result
            
        self.logger.debug(f"Simulando {len(daily_data)} barras para {symbol} en {date}")
        
        try:
            # Inicializar strategy engine para el día
            if not hasattr(self, '_multi_engine') or self._multi_engine is None:
                try:
                    from strategies.multi_strategy_engine import MultiStrategyEngine
                    self._multi_engine = MultiStrategyEngine()
                except ImportError:
                    self._multi_engine = None
            
            signals_generated = 0
            trades_executed = 0
            
            # Procesar cada barra del día
            for bar in daily_data:
                
                # Solo usar MultiStrategy engine si está disponible
                if self._multi_engine:
                    signal = await self._multi_engine.on_bar(bar)
                    
                    if signal and signal.signal_type:
                        signals_generated += 1
                        
                        # Ejecutar trade basado en la señal
                        if signal.signal_type == SignalType.LONG:
                            position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 100)
                            await broker.place_order(
                                symbol=symbol,
                                side=OrderSide.BUY,
                                quantity=position_size,
                                order_type=OrderType.MARKET,
                                price=bar.close,
                                signal=signal
                            )
                            trades_executed += 1
                            
                        elif signal.signal_type == SignalType.SHORT:
                            position_size = getattr(signal, 'position_size', None) or signal.metadata.get('position_size', 100)
                            await broker.place_order(
                                symbol=symbol,
                                side=OrderSide.SELL,
                                quantity=position_size,
                                order_type=OrderType.MARKET,
                                price=bar.close,
                                signal=signal
                            )
                            trades_executed += 1
                            
                        elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                            positions = await broker.get_positions()
                            if symbol in positions and positions[symbol].get('quantity', 0) != 0:
                                position = positions[symbol]
                                quantity = abs(position.get('quantity', 0))
                                side = OrderSide.SELL if position.get('quantity', 0) > 0 else OrderSide.BUY
                                
                                await broker.place_order(
                                    symbol=symbol,
                                    side=side,
                                    quantity=quantity,
                                    order_type=OrderType.MARKET,
                                    price=bar.close,
                                    signal=signal
                                )
                                trades_executed += 1
                
                # Cerrar posiciones al final del día (15:50 ET)
                if bar.timestamp.hour == 15 and bar.timestamp.minute >= 50:
                    await self._close_all_day_trading_positions(symbol, bar)
            
            # Calcular estadísticas finales del día
            account_info = await broker.get_account_info()
            
            result['signals_generated'] = signals_generated
            result['trades_executed'] = trades_executed
            result['pnl'] = account_info.get('realized_pnl', 0.0)
            result['commissions'] = account_info.get('total_commissions', 0.0)
            result['winning_trades'] = account_info.get('wins', 0)
            result['losing_trades'] = account_info.get('losses', 0)
            
        except Exception as e:
            self.logger.error(f"Error en simulación de {symbol} para {date}: {e}")
            
        return result
    
    async def _reset_daily_state(self):
        """Resetear estado para comenzar un nuevo día"""
        
        # Reset multi-strategy engine state if available
        if hasattr(self, '_multi_engine') and self._multi_engine:
            # Reset any daily state in the strategy engine
            # This would depend on the specific implementation
            pass
    
    def _print_consolidated_results(self, results: Dict[str, Any]):
        """Mostrar resultados consolidados de todos los días"""
        
        print(f"\n" + "="*70)
        print(f"📊 RESUMEN CONSOLIDADO - SIMULACIÓN INTRADAY POR DÍAS")
        print(f"Símbolo: {results['symbol']} | Período: {results['period']}")
        print(f"="*70)
        
        print(f"📅 Días simulados: {results['total_days_simulated']}")
        print(f"📈 Días con trades: {results['days_with_trades']}")
        print(f"💼 Total trades: {results['total_trades']}")
        
        if results['total_trades'] > 0:
            print(f"✅ Trades ganadores: {results['winning_trades']}")
            print(f"❌ Trades perdedores: {results['losing_trades']}")
            print(f"📊 Win Rate: {results['win_rate']:.1f}%")
            print(f"💰 P&L Bruto: ${results['total_pnl']:.2f}")
            print(f"💸 Comisiones: ${results['total_commissions']:.2f}")
            print(f"💵 P&L Neto: ${results['net_pnl']:.2f}")
            print(f"📈 P&L Promedio por Trade: ${results['avg_pnl_per_trade']:.2f}")
        
        print(f"\n📋 BREAKDOWN POR DÍA (Solo días con actividad):")
        print(f"{'Fecha':<12} {'Día':<10} {'Trades':<8} {'P&L':<10} {'Señales':<8}")
        print(f"-" * 55)
        
        for day in results['daily_results']:
            if day['trades_executed'] > 0:
                pnl_display = f"${day['pnl']:>6.2f}"
                print(f"{day['date']:<12} {day['weekday'][:3]:<10} {day['trades_executed']:<8} "
                      f"{pnl_display:<10} {day['signals_generated']:<8}")
        
        print(f"\n💡 VENTAJAS DE ESTA IMPLEMENTACIÓN:")
        print(f"   ✅ Cada día es independiente (no mezcla datos de diferentes fechas)")
        print(f"   ✅ Resultados consistentes y reproducibles") 
        print(f"   ✅ Apropiado para operativa intraday real")
        print(f"   ✅ Fácil identificar patrones por día de la semana")
        print(f"   ✅ No más confusión con diferentes cantidades de barras")