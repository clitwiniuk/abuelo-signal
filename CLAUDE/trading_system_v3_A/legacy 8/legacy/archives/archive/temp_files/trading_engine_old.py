# engine/trading_engine.py
"""
Main trading engine that orchestrates all components.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, time
from dataclasses import dataclass

from core.interfaces import (
    IDataProvider, IBroker, IStrategy, IRiskManager, IFilter,
    Position, Signal, Order, MarketData, TradingConfig,
    OrderSide, OrderType, OrderStatus, SignalType, Event
)
from core.events import (
    AsyncEventBus, EventTypes, BaseEventHandler,
    create_bar_event, create_signal_event, create_order_event,
    create_position_event, create_error_event
)

@dataclass
class MarketSession:
    """Information about current US market session from Spain"""
    name: str
    is_premarket: bool
    is_regular: bool
    is_afterhours: bool
    is_closed: bool
    us_time: datetime
    spain_time: datetime
    optimal_timeout: float
    optimal_delay: float

logger = logging.getLogger(__name__)


class TradingEngine(BaseEventHandler):
    """
    Main trading engine that coordinates all system components.
    Uses event-driven architecture for loose coupling.
    """
    
    @staticmethod
    def get_market_session() -> MarketSession:
        """Get current US market session information from Spain"""
        from zoneinfo import ZoneInfo
        
        spain_now = datetime.now(ZoneInfo("Europe/Madrid"))
        us_now = spain_now.astimezone(ZoneInfo("America/New_York"))
        us_hour = us_now.hour
        us_minute = us_now.minute
        
        # Define US market sessions
        is_premarket = (4 <= us_hour < 9) or (us_hour == 9 and us_minute < 30)
        is_regular = (9 <= us_hour < 16) or (us_hour == 9 and us_minute >= 30)
        is_afterhours = (16 <= us_hour <= 20)
        is_closed = not (is_premarket or is_regular or is_afterhours)
        
        # Set optimal parameters based on session
        if is_premarket:
            name = "PREMARKET"
            timeout = 90.0
            delay = 2.0
        elif is_regular:
            name = "REGULAR"
            timeout = 75.0  # Increased due to IBKR performance issues
            delay = 1.0     # Increased delay to reduce pressure on IBKR
        elif is_afterhours:
            name = "AFTERHOURS"
            timeout = 75.0
            delay = 1.0
        else:
            name = "CLOSED"
            timeout = 120.0
            delay = 3.0
            
        return MarketSession(
            name=name,
            is_premarket=is_premarket,
            is_regular=is_regular,
            is_afterhours=is_afterhours,
            is_closed=is_closed,
            us_time=us_now,
            spain_time=spain_now,
            optimal_timeout=timeout,
            optimal_delay=delay
        )
    
    @staticmethod
    def get_trading_recommendations() -> Dict[str, Any]:
        """Get trading recommendations based on current market session"""
        session = TradingEngine.get_market_session()
        
        if session.is_premarket:
            return {
                "focus_strategies": ["gap_go", "momentum_breakout"],
                "avoid_strategies": ["mean_reversion", "arbitrage"],
                "expected_volatility": "HIGH",
                "expected_spreads": "WIDE",
                "data_reliability": "MEDIUM",
                "volume_threshold_multiplier": 0.5,  # Lower volume expected
                "timeout_multiplier": 2.0,
                "session_advantages": [
                    "Gap opportunities more visible",
                    "Less competition from algorithms", 
                    "Extended runway for position development"
                ],
                "session_risks": [
                    "Lower liquidity can cause slippage",
                    "News gaps can be extreme",
                    "Fewer market makers active"
                ]
            }
        elif session.is_regular:
            return {
                "focus_strategies": ["volume_breakout", "macdv", "vwap"],
                "avoid_strategies": ["low_liquidity_plays"],
                "expected_volatility": "MEDIUM",
                "expected_spreads": "TIGHT", 
                "data_reliability": "HIGH",
                "volume_threshold_multiplier": 1.0,  # Normal volume
                "timeout_multiplier": 1.0,
                "session_advantages": [
                    "High liquidity for easy entries/exits",
                    "Reliable price discovery",
                    "Full market participation"
                ],
                "session_risks": [
                    "More algorithmic competition",
                    "Faster price movements",
                    "Higher trading costs due to volume"
                ]
            }
        elif session.is_afterhours:
            return {
                "focus_strategies": ["earnings_reactions", "news_based"],
                "avoid_strategies": ["high_frequency", "scalping"],
                "expected_volatility": "MEDIUM",
                "expected_spreads": "MEDIUM",
                "data_reliability": "MEDIUM",
                "volume_threshold_multiplier": 0.3,  # Much lower volume
                "timeout_multiplier": 1.5,
                "session_advantages": [
                    "Earnings reactions more pronounced",
                    "Less day-trader competition",
                    "Extended time for analysis"
                ],
                "session_risks": [
                    "Thin orderbooks",
                    "Potential for gaps at next open",
                    "Limited liquidity for large positions"
                ]
            }
        else:  # CLOSED
            return {
                "focus_strategies": ["research", "planning"],
                "avoid_strategies": ["all_active_trading"],
                "expected_volatility": "NONE",
                "expected_spreads": "N/A",
                "data_reliability": "LOW",
                "volume_threshold_multiplier": 0.0,
                "timeout_multiplier": 3.0,
                "session_advantages": [
                    "Time for research and analysis",
                    "Planning next day strategies",
                    "System maintenance window"
                ],
                "session_risks": [
                    "No trading opportunities",
                    "Stale data",
                    "Overnight gap risk building"
                ]
            }
    
    def __init__(
        self,
        config: TradingConfig,
        data_provider: IDataProvider,
        broker: IBroker,
        strategy: IStrategy,
        risk_manager: IRiskManager,
        filters: List[IFilter] = None
    ):
        super().__init__("TradingEngine")
        
        self.config = config
        self.data_provider = data_provider
        self.broker = broker
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.filters = filters or []
        
        # Event system
        self.event_bus = AsyncEventBus()
        
        # Internal state
        self.is_running = False
        self.positions: Dict[str, Position] = {}
        self.active_orders: Dict[str, Order] = {}
        self.monitored_symbols: Set[str] = set()
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.start_time: Optional[datetime] = None
        
        # Circuit breaker for problematic symbols
        self.failed_symbols: Dict[str, int] = {}
        self.max_symbol_failures = 2  # Max failures before circuit breaker (reduced from 3)
        
        # PROFESSIONAL CONCURRENCY THROTTLING
        # Semaphore to limit concurrent symbol processing to prevent event loop saturation
        self.max_concurrent_symbols = min(3, max(1, len(getattr(config, 'symbols', [])))) if hasattr(config, 'symbols') else 3
        self.symbol_processing_semaphore = asyncio.Semaphore(self.max_concurrent_symbols)
        
        # Dynamic performance tracking for concurrency optimization
        self.processing_times = []
        self.max_processing_time_samples = 20
        self.performance_adjustment_threshold = 10.0  # seconds
        
        # ACCOUNT CAPITAL CACHING to prevent continuous IBKR requests
        self._cached_capital = None
        self._capital_cache_time = None
        self._capital_cache_ttl = 300  # 5 minutes cache
        
        self.logger.info(f"🚦 Professional concurrency throttling initialized: max {self.max_concurrent_symbols} simultaneous symbols")
        
        # Register for events
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup event handlers"""
        self.event_bus.subscribe(EventTypes.SIGNAL_GENERATED, self)
        self.event_bus.subscribe(EventTypes.ORDER_FILLED, self)
        self.event_bus.subscribe(EventTypes.ORDER_REJECTED, self)
        self.event_bus.subscribe(EventTypes.ERROR_OCCURRED, self)
    
    async def initialize(self):
        """Initialize the trading engine"""
        try:
            self.logger.info("Initializing trading engine...")
            
            # Initialize strategy
            await self.strategy.initialize(self.event_bus)
            
            # Set trading engine reference in strategy for position validation
            if hasattr(self.strategy, 'set_trading_engine'):
                self.strategy.set_trading_engine(self)
            
            # Connect to data provider
            if not await self.data_provider.connect():
                raise Exception("Failed to connect to data provider")
            
            # Connect to broker (skip if same instance as data_provider)
            if self.broker is not self.data_provider:
                if not await self.broker.connect():
                    raise Exception("Failed to connect to broker")
            
            # Load existing positions
            await self._load_positions()
            
            self.logger.info("Trading engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading engine: {e}")
            raise
    
    async def start(self, symbols: List[str] = None):
        """Start the trading engine"""
        if self.is_running:
            self.logger.warning("Trading engine is already running")
            return
        
        try:
            await self.initialize()
            
            self.is_running = True
            self.start_time = datetime.now()
            self.monitored_symbols = set(symbols) if symbols else set()
            
            self.logger.info(f"Starting trading engine with symbols: {symbols}")
            
            # Publish system started event
            await self.event_bus.publish(Event(
                event_id="",
                event_type=EventTypes.SYSTEM_STARTED,
                timestamp=datetime.now(),
                data={"symbols": symbols}
            ))
            
            # Start main trading loop
            await self._run_trading_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting trading engine: {e}")
            await self._handle_error(e, "TradingEngine.start")
            raise
    
    async def stop(self):
        """Stop the trading engine with faster shutdown"""
        self.logger.info("🛑 Stopping trading engine (fast shutdown)...")
        
        # Set shutdown flag immediately
        self.is_running = False
        
        try:
            # Skip position closing for faster shutdown (positions will be handled by IBKR)
            # Close positions only if explicitly configured and not in emergency shutdown
            if self.config.close_positions_on_stop and len(self.positions) < 5:
                self.logger.info("Closing positions...")
                # Add timeout for position closing
                try:
                    await asyncio.wait_for(self._close_all_positions(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.logger.warning("Position closing timeout, proceeding with shutdown")
            else:
                self.logger.info("Skipping position closing for faster shutdown")
            
            # Skip order cancellation for faster shutdown (IBKR will handle)
            self.logger.info("Skipping order cancellation for faster shutdown")
            
            # Aggressive disconnect from services
            self.logger.info("Disconnecting from services...")
            
            # Disconnect with timeout
            disconnect_tasks = []
            if self.broker is not self.data_provider:
                disconnect_tasks.append(self.broker.disconnect())
            disconnect_tasks.append(self.data_provider.disconnect())
            
            # Wait max 3 seconds for disconnections
            try:
                await asyncio.wait_for(
                    asyncio.gather(*disconnect_tasks, return_exceptions=True),
                    timeout=3.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("Disconnect timeout, forcing shutdown")
            
            # Clear all tracking
            self.monitored_symbols.clear()
            self.failed_symbols.clear()
            self.positions.clear()
            self.active_orders.clear()
            
            self.logger.info("✅ Trading engine stopped (fast shutdown)")
            
        except Exception as e:
            self.logger.error(f"Error stopping trading engine: {e}")
            # Force cleanup
            self.is_running = False
    
    async def add_symbol(self, symbol: str, skip_validation: bool = False):
        """Add a symbol to monitor with optional validation"""
        # Basic validation - check if symbol is valid format
        if not symbol or not symbol.isalpha() or len(symbol) > 5:
            self.logger.warning(f"Invalid symbol format: {symbol}")
            return False
            
        # Skip validation if requested
        if skip_validation:
            self.monitored_symbols.add(symbol)
            self.logger.info(f"Added symbol for monitoring (no validation): {symbol}")
            return True
            
        # Try to validate symbol exists by fetching a small amount of data with fast timeout
        try:
            test_bars = await asyncio.wait_for(
                self.data_provider.get_bars(symbol, self.config.timeframe, 1), 
                timeout=12.0  # Balanced timeout for symbol validation
            )
            if not test_bars:
                self.logger.warning(f"❌ Symbol {symbol} validation failed - no data available")
                return False
        except ValueError as e:
            # Catch Error 366 immediately during validation
            if "NO_HISTORICAL_DATA:" in str(e):
                self.logger.warning(f"❌ Symbol {symbol} has no historical data (Error 366) - rejected during validation")
                return False
            else:
                self.logger.warning(f"Error validating symbol {symbol}: {e}")
                return False
        except asyncio.TimeoutError:
            self.logger.warning(f"❌ Timeout validating symbol {symbol} - likely invalid symbol")
            return False
        except Exception as e:
            error_str = str(e).lower()
            if ("366" in error_str or "no historical data" in error_str or 
                "no se encontraron datos" in error_str):
                self.logger.warning(f"❌ Symbol {symbol} has no historical data (Error 366) - rejected during validation")
                return False
            self.logger.warning(f"Error validating symbol {symbol}: {e}")
            return False
        
        self.monitored_symbols.add(symbol)
        self.logger.info(f"✅ Added symbol for monitoring: {symbol} (validation passed)")
        return True

    async def _apply_filters_to_symbol(self, symbol: str) -> bool:
        """Apply filters to validate symbol"""
        if self.filters:
            for filter_impl in self.filters:
                try:
                    bars = await self.data_provider.get_bars(symbol, self.config.timeframe, 50)
                    should_trade, reason = await filter_impl.should_trade(symbol, bars)
                    if not should_trade:
                        self.logger.info(f"Symbol {symbol} filtered out: {reason}")
                        return False
                except Exception as e:
                    self.logger.error(f"Error applying filter to {symbol}: {e}")
                    return False
        return True
    
    async def remove_symbol(self, symbol: str):
        """Remove a symbol from monitoring"""
        self.monitored_symbols.discard(symbol)
        self.logger.info(f"Removed symbol from monitoring: {symbol}")
        
        # Close position if exists
        if symbol in self.positions:
            await self._close_position(symbol, "Symbol removed from monitoring")
    
    async def _run_trading_loop(self):
        """Main trading loop with fast shutdown detection"""
        self.logger.info("Starting main trading loop")
        
        while self.is_running:
            try:
                # Check shutdown more frequently
                if not self.is_running:
                    self.logger.info("📴 Shutdown detected in main loop")
                    break
                    
                # Check risk limits
                if not await self._check_risk_limits():
                    self.logger.warning("Risk limits exceeded, pausing trading")
                    # Wait 60 seconds but check shutdown every 1 second for faster response
                    for _ in range(60):  # 60 iterations of 1 second = 60 seconds
                        if not self.is_running:
                            self.logger.info("📴 Shutdown detected during risk limit pause")
                            return  # Exit immediately
                        await asyncio.sleep(0.5)  # Faster check for shutdown
                    continue
                
                # Check if it's time to close positions before market close
                if await self._should_close_positions_before_market_close():
                    self.logger.info("Closing all positions before market close")
                    await self._close_all_positions_before_market_close()
                
                # Process each monitored symbol
                if self.monitored_symbols:
                    # Log periodically (every 10 cycles = ~30 seconds)
                    if not hasattr(self, '_log_counter'):
                        self._log_counter = 0
                    
                    self._log_counter += 1
                    if self._log_counter % 10 == 0:
                        self.logger.info(f"🔄 System running: {len(self.monitored_symbols)} symbols, {len(self.positions)} positions")
                        if self.failed_symbols:
                            self.logger.info(f"🚫 Circuit breakers: {list(self.failed_symbols.keys())}")
                    
                    # MEMORY OPTIMIZATION: Deep cleanup every 100 cycles (~5 minutes)
                    if self._log_counter % 100 == 0:
                        await self._deep_memory_cleanup()
                        self.logger.info(f"🧹 Deep memory cleanup completed at cycle {self._log_counter}")
                    
                    # PROFESSIONAL THROTTLED PARALLEL PROCESSING
                    # Process symbols with concurrency throttling to prevent event loop saturation
                    symbols_to_process = list(self.monitored_symbols)
                    
                    # BATCH PROCESSING for very large symbol lists to reduce event loop overhead
                    if len(symbols_to_process) > 10:
                        # Process in batches of 10 to reduce event loop stress
                        batch_size = 10
                        for i in range(0, len(symbols_to_process), batch_size):
                            if not self.is_running:
                                break
                            batch = symbols_to_process[i:i+batch_size]
                            self.logger.debug(f"📎 Processing batch {i//batch_size + 1}/{(len(symbols_to_process) + batch_size - 1)//batch_size}: {len(batch)} symbols")
                            await self._process_symbols_with_throttling(batch)
                            
                            # Brief pause between batches to prevent overwhelming
                            if i + batch_size < len(symbols_to_process):
                                await asyncio.sleep(0.1)
                    else:
                        # For smaller lists, process all at once
                        await self._process_symbols_with_throttling(symbols_to_process)
                else:
                    self.logger.info("⚠️ No symbols to process (monitored_symbols is empty)")
                
                # Update positions
                self.logger.debug("🔄 Updating positions...")
                await self._update_positions()
                self.logger.debug("✅ Positions updated")
                
                # Cleanup problematic symbols periodically
                self.logger.debug("🧹 Cleaning up problematic symbols...")
                await self._cleanup_problematic_symbols()
                self.logger.debug("✅ Cleanup completed")
                
                # Wait before next iteration with very fast shutdown detection
                self.logger.debug("⏸️ Starting inter-iteration sleep (checking shutdown every 0.1s)")
                # Use very short sleeps to be maximally responsive to shutdown
                for i in range(30):  # 30 iterations of 0.1 seconds = 3 seconds total
                    if not self.is_running:
                        self.logger.info("📴 Shutdown detected during sleep, exiting immediately")
                        return  # Exit immediately without cleanup
                    await asyncio.sleep(0.1)
                    if i % 10 == 0:  # Log every second
                        self.logger.debug(f"💤 Sleep progress: {i/10:.1f}s/3.0s")
                
                self.logger.debug("🔄 Main loop iteration completed, starting next cycle")
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await self._handle_error(e, "trading_loop")
                # Wait 5 seconds but check shutdown every second
                for _ in range(5):
                    if not self.is_running:
                        break
                    await asyncio.sleep(1)
        
        self.logger.info("Trading loop terminated")
    
    async def _cleanup_problematic_symbols(self):
        """Remove symbols that consistently fail to get data"""
        try:
            symbols_to_remove = []
            
            # Find symbols that should be removed (already at max failures)
            for symbol, failure_count in list(self.failed_symbols.items()):
                if failure_count >= self.max_symbol_failures and symbol in self.monitored_symbols:
                    symbols_to_remove.append(symbol)
            
            # Remove symbols that have failed multiple times
            for symbol in symbols_to_remove:
                self.monitored_symbols.discard(symbol)
                self.logger.info(f"Cleaned up problematic symbol {symbol} from monitoring (failed {self.failed_symbols[symbol]} times)")
                
                # Remove from failed_symbols dict to clean up
                self.failed_symbols.pop(symbol, None)
            
            # MEMORY OPTIMIZATION: Clean up failed_symbols that are no longer monitored
            orphaned_symbols = []
            for symbol in list(self.failed_symbols.keys()):
                if symbol not in self.monitored_symbols:
                    orphaned_symbols.append(symbol)
            
            for symbol in orphaned_symbols:
                self.failed_symbols.pop(symbol, None)
                self.logger.debug(f"🧹 Cleaned up orphaned failed symbol: {symbol}")
            
            # Log memory cleanup if significant
            if len(orphaned_symbols) > 0:
                self.logger.info(f"🧹 Memory cleanup: removed {len(orphaned_symbols)} orphaned symbols from failed_symbols dict")
                    
        except Exception as e:
            self.logger.error(f"Error in cleanup_problematic_symbols: {e}")
    
    async def _deep_memory_cleanup(self):
        """Perform deep memory cleanup every few minutes"""
        try:
            cleanup_count = 0
            
            # 1. Clean up closed positions that might be lingering
            closed_positions = []
            for symbol, position in list(self.positions.items()):
                if position.quantity == 0:
                    closed_positions.append(symbol)
            
            for symbol in closed_positions:
                self.positions.pop(symbol, None)
                cleanup_count += 1
            
            # 2. Clean up completed/cancelled orders
            completed_orders = []
            for order_id, order in list(self.active_orders.items()):
                if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    completed_orders.append(order_id)
            
            for order_id in completed_orders:
                self.active_orders.pop(order_id, None)
                cleanup_count += 1
            
            # 3. Reset failed symbols counter for symbols with low failure counts
            reset_symbols = []
            for symbol, count in list(self.failed_symbols.items()):
                if count == 1 and symbol in self.monitored_symbols:  # Reset single failures
                    reset_symbols.append(symbol)
            
            for symbol in reset_symbols:
                self.failed_symbols[symbol] = 0
                cleanup_count += 1
            
            # 4. Clear data provider cache if available
            if hasattr(self.data_provider, 'clear_cache'):
                await self.data_provider.clear_cache()
                cleanup_count += 1
            
            if cleanup_count > 0:
                self.logger.info(f"🧹 Deep cleanup: removed {cleanup_count} items from memory")
                
        except Exception as e:
            self.logger.error(f"Error in deep memory cleanup: {e}")
    
    async def _process_symbols_with_throttling(self, symbols: List[str]):
        """
        PROFESSIONAL CONCURRENCY THROTTLING
        Process symbols with controlled parallelism to prevent event loop saturation.
        Uses semaphore-based throttling to limit concurrent symbol processing.
        """
        if not symbols:
            self.logger.debug("📭 No symbols to process")
            return
        
        start_time = datetime.now()
        total_symbols = len(symbols)
        
        self.logger.info(f"🚦 Starting throttled processing: {total_symbols} symbols, max {self.max_concurrent_symbols} concurrent")
        
        async def _throttled_symbol_processor(symbol: str):
            """Process single symbol with semaphore throttling"""
            async with self.symbol_processing_semaphore:
                if not self.is_running:
                    self.logger.debug(f"🛑 Skipping {symbol} - system shutdown")
                    return
                
                symbol_start = datetime.now()
                try:
                    self.logger.debug(f"🔄 Processing {symbol} (semaphore acquired)")
                    await self._process_symbol(symbol)
                    elapsed = (datetime.now() - symbol_start).total_seconds()
                    self.logger.debug(f"✅ {symbol} completed in {elapsed:.2f}s")
                except Exception as e:
                    elapsed = (datetime.now() - symbol_start).total_seconds()
                    self.logger.error(f"❌ {symbol} failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
                    # Handle symbol failure
                    await self._handle_symbol_failure(symbol, e)
        
        # Create tasks with throttling
        tasks = []
        for symbol in symbols:
            if not self.is_running:
                self.logger.warning("🛑 System shutdown during task creation")
                break
            task = asyncio.create_task(_throttled_symbol_processor(symbol))
            tasks.append(task)
        
        # Wait for all tasks to complete with timeout protection
        if tasks:
            try:
                # AGGRESSIVE TIMEOUT: Much shorter timeout to force faster processing
                timeout = min(15, max(10, len(tasks) * 2))  # 2 seconds per symbol, min 10s, max 15s
                self.logger.debug(f"⏳ Waiting for {len(tasks)} throttled tasks (timeout: {timeout}s)")
                
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), 
                    timeout=timeout
                )
                
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / total_symbols if total_symbols > 0 else 0
                
                # Performance tracking for adaptive optimization
                self._track_processing_performance(elapsed, total_symbols)
                
                self.logger.info(f"✅ Throttled processing completed: {total_symbols} symbols in {elapsed:.2f}s "
                               f"(avg: {avg_time:.2f}s per symbol)")
                
            except asyncio.TimeoutError:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.logger.error(f"⏰ Throttled processing timed out after {elapsed:.2f}s")
                
                # Cancel remaining tasks
                cancelled_count = 0
                for task in tasks:
                    if not task.done():
                        task.cancel()
                        cancelled_count += 1
                
                if cancelled_count > 0:
                    self.logger.warning(f"🚫 Cancelled {cancelled_count} incomplete tasks")
    
    def _track_processing_performance(self, elapsed_time: float, symbol_count: int):
        """Track processing performance and adaptively adjust concurrency if needed"""
        try:
            # Store performance data
            self.processing_times.append(elapsed_time)
            
            # Keep only recent samples
            if len(self.processing_times) > self.max_processing_time_samples:
                self.processing_times = self.processing_times[-self.max_processing_time_samples:]
            
            # Check if we need to adjust concurrency (only after we have enough samples)
            if len(self.processing_times) >= 10:
                recent_avg = sum(self.processing_times[-5:]) / 5
                overall_avg = sum(self.processing_times) / len(self.processing_times)
                
                # If recent performance is consistently worse than threshold, reduce concurrency
                if recent_avg > self.performance_adjustment_threshold and self.max_concurrent_symbols > 1:
                    self.max_concurrent_symbols = max(1, self.max_concurrent_symbols - 1)
                    # Create new semaphore with adjusted limit
                    self.symbol_processing_semaphore = asyncio.Semaphore(self.max_concurrent_symbols)
                    self.logger.warning(f"🔻 Reduced concurrency to {self.max_concurrent_symbols} due to slow performance "
                                      f"(recent avg: {recent_avg:.1f}s > {self.performance_adjustment_threshold}s)")
                
                # If recent performance is good and overall performance improved, cautiously increase
                elif (recent_avg < self.performance_adjustment_threshold * 0.5 and 
                      recent_avg < overall_avg * 0.8 and 
                      self.max_concurrent_symbols < 3):
                    self.max_concurrent_symbols = min(3, self.max_concurrent_symbols + 1)
                    self.symbol_processing_semaphore = asyncio.Semaphore(self.max_concurrent_symbols)
                    self.logger.info(f"🔺 Increased concurrency to {self.max_concurrent_symbols} due to good performance "
                                   f"(recent avg: {recent_avg:.1f}s)")
            
        except Exception as e:
            self.logger.error(f"Error tracking processing performance: {e}")
    
    async def _process_symbol_safe(self, symbol: str):
        """Safely process a symbol with error handling for parallel execution"""
        start_time = datetime.now()
        try:
            self.logger.debug(f"🔄 Starting safe processing of {symbol}")
            await self._process_symbol(symbol)
            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"✅ Completed processing {symbol} in {elapsed:.2f}s")
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"❌ Error processing {symbol} after {elapsed:.2f}s: {type(e).__name__}: {e}")
            try:
                await self._handle_error(e, f"process_symbol({symbol})")
            except Exception as handle_error:
                self.logger.error(f"❌ Error in error handler for {symbol}: {handle_error}")
    
    async def _process_symbol(self, symbol: str):
        """Process a single symbol"""
        # Double check: Skip if symbol was removed during this loop iteration
        if symbol not in self.monitored_symbols:
            self.logger.debug(f"⚠️ Skipping {symbol} - was removed from monitoring during this iteration")
            return
            
        # Circuit breaker: Skip symbols that consistently fail
        if self.failed_symbols.get(symbol, 0) >= self.max_symbol_failures:
            self.logger.info(f"🚫 Skipping {symbol} - circuit breaker active (failures: {self.failed_symbols.get(symbol, 0)})")
            return  # Skip this symbol
        
        # Only log if there are failures to track
        if self.failed_symbols.get(symbol, 0) > 0:
            self.logger.info(f"📊 Processing {symbol} (failures: {self.failed_symbols.get(symbol, 0)})")
        
        # Retry mechanism for data fetching
        max_retries = 1  # Keep single retry for faster handling
        
        # Use longer timeout for symbols, especially those that might be slower to respond
        # Small cap symbols often take longer to get data from IBKR
        # Also account for market conditions and IBKR rate limiting
        
        # Get current market session information
        session = self.get_market_session()
        base_timeout = session.optimal_timeout
        
        self.logger.info(f"🕐 US Market Session: {session.name} (US: {session.us_time.strftime('%H:%M')} | Spain: {session.spain_time.strftime('%H:%M')})")
        
        # If symbol has failed before, give it even more time
        if self.failed_symbols.get(symbol, 0) > 0:
            timeout_seconds = base_timeout + (self.failed_symbols.get(symbol, 0) * 20.0)  # Add 20s per failure during special sessions
            self.logger.info(f"🕐 Extended timeout for {symbol}: {timeout_seconds}s (failures: {self.failed_symbols.get(symbol, 0)}, session: {session.name})")
        else:
            timeout_seconds = base_timeout
            self.logger.debug(f"🕐 Base timeout for {symbol}: {timeout_seconds}s (session: {session.name})")
        
        for attempt in range(max_retries + 1):
            # Check if system is shutting down
            if not self.is_running:
                return
                
            try:
                # Check shutdown before starting request
                if not self.is_running:
                    self.logger.info(f"🚫 Skipping {symbol} - system shutting down")
                    return
                
                # Get latest bars with timeout
                self.logger.info(f"📊 Requesting bars for {symbol} (attempt {attempt+1}/{max_retries+1}, timeout: {timeout_seconds}s)")
                
                import time
                start_time = time.time()
                
                # Create the request task so we can cancel it if needed
                request_task = asyncio.create_task(
                    self.data_provider.get_bars(symbol, self.config.timeframe, 100)
                )
                
                # Use a loop to check for shutdown while waiting
                timeout_end = start_time + timeout_seconds
                while time.time() < timeout_end:
                    # Check if system is shutting down
                    if not self.is_running:
                        self.logger.warning(f"🚫 CANCELLING {symbol} request - system shutting down")
                        request_task.cancel()
                        try:
                            await request_task
                        except asyncio.CancelledError:
                            pass
                        return
                    
                    # Check if request is done
                    if request_task.done():
                        break
                        
                    # Short sleep to avoid busy waiting
                    await asyncio.sleep(0.1)
                
                # Get the result
                if request_task.done():
                    bars = await request_task
                else:
                    # Timeout occurred
                    request_task.cancel()
                    try:
                        await request_task
                    except asyncio.CancelledError:
                        pass
                    raise asyncio.TimeoutError(f"Request for {symbol} timed out after {timeout_seconds}s")
                
                end_time = time.time()
                self.logger.info(f"✅ Data request for {symbol} completed in {end_time - start_time:.2f}s")
                if not bars:
                    self.logger.warning(f"⚠️ No bars returned for {symbol}")
                    return
                
                # Only log data details if debugging needed
                self.logger.debug(f"📈 Got {len(bars)} bars for {symbol}, latest: {bars[-1].timestamp}, price: ${bars[-1].close}")
                
                # Reset failure count on successful data fetch
                if symbol in self.failed_symbols:
                    self.failed_symbols[symbol] = 0
                
                # Add delay after successful request based on market session
                # But check for shutdown during the delay
                delay_time = session.optimal_delay
                steps = max(1, int(delay_time / 0.1))  # Break delay into 0.1s steps
                step_delay = delay_time / steps
                
                for _ in range(steps):
                    if not self.is_running:
                        self.logger.info(f"🚫 Shutdown detected during delay for {symbol}")
                        return
                    await asyncio.sleep(step_delay)
                    
                break  # Success, exit retry loop
                
            except asyncio.TimeoutError:
                self.logger.warning(f"⏰ Timeout for {symbol} after {timeout_seconds}s on attempt {attempt+1}/{max_retries+1}")
                
                # Instead of immediately removing, increment failure counter and try different approach
                if symbol not in self.failed_symbols:
                    self.failed_symbols[symbol] = 0
                self.failed_symbols[symbol] += 1
                
                # Only remove after multiple timeout failures, not on first timeout
                if self.failed_symbols[symbol] >= 3:  # Allow 3 timeouts before removal
                    self.logger.warning(f"❌ Symbol {symbol} has failed {self.failed_symbols[symbol]} times - removing from monitoring")
                    self.monitored_symbols.discard(symbol)
                    self.failed_symbols.pop(symbol, None)
                    
                    # Clear adapter cache for this symbol
                    if hasattr(self.data_provider, '_contracts_cache'):
                        self.data_provider._contracts_cache.pop(symbol, None)
                    
                    self.logger.info(f"✅ Removed {symbol} from monitoring after multiple timeout failures")
                    return
                else:
                    self.logger.info(f"🔄 Keeping {symbol} - timeout count: {self.failed_symbols[symbol]}/3")
                    return  # Don't retry immediately, wait for next cycle
            except ValueError as e:
                # Check for specific NO_HISTORICAL_DATA error - immediate removal
                if "NO_HISTORICAL_DATA:" in str(e):
                    self.logger.warning(f"✅ Symbol {symbol} has no historical data (Error 366) - IMMEDIATELY REMOVED from monitoring")
                    self.monitored_symbols.discard(symbol)
                    # Remove from failed_symbols to clean up tracking
                    self.failed_symbols.pop(symbol, None)
                    
                    # Clear adapter cache for this symbol
                    if hasattr(self.data_provider, '_contracts_cache'):
                        self.data_provider._contracts_cache.pop(symbol, None)
                    
                    return  # Exit immediately, no retries needed
                else:
                    self.logger.error(f"ValueError getting bars for {symbol}: {e}")
                    # Increment failure count for other ValueError types
                    self.failed_symbols[symbol] = self.failed_symbols.get(symbol, 0) + 1
                    
            except Exception as e:
                self.logger.error(f"Error getting bars for {symbol}: {e}")
                
                # Check for specific IBKR error 366 (no historical data) in case it wasn't caught above
                error_str = str(e).lower()
                if ("366" in error_str or "no historical data" in error_str or 
                    "no se encontraron datos" in error_str or "security not found" in error_str):
                    self.logger.warning(f"✅ Symbol {symbol} has no historical data (Error 366) - IMMEDIATELY REMOVED from monitoring")
                    self.monitored_symbols.discard(symbol)
                    # Remove from failed_symbols to clean up tracking
                    self.failed_symbols.pop(symbol, None)
                    
                    # Clear adapter cache for this symbol
                    if hasattr(self.data_provider, '_contracts_cache'):
                        self.data_provider._contracts_cache.pop(symbol, None)
                    
                    return  # Exit immediately, no circuit breaker needed
                
                # Increment failure count for circuit breaker
                self.failed_symbols[symbol] = self.failed_symbols.get(symbol, 0) + 1
                if self.failed_symbols[symbol] >= self.max_symbol_failures:
                    self.logger.warning(f"Symbol {symbol} reached max failures ({self.max_symbol_failures}), removing from monitoring")
                    self.monitored_symbols.discard(symbol)
                    # Clean up failed_symbols tracking for removed symbol
                    self.failed_symbols.pop(symbol, None)
                return
        
        try:
            latest_bar = bars[-1]
            
            # Publish bar event
            await self.event_bus.publish(create_bar_event(latest_bar))
            
            # Let strategy analyze the bar
            self.logger.debug(f"🎯 Analyzing {symbol} with strategy: price=${latest_bar.close:.2f}, volume={latest_bar.volume}")
            
            try:
                # ULTRA AGGRESSIVE TIMEOUT for strategy analysis to prevent freezing
                strategy_timeout = 2.0  # Maximum 2 seconds for strategy analysis
                self.logger.debug(f"⏱️ Starting strategy analysis for {symbol} (timeout: {strategy_timeout}s)")
                
                signal = await asyncio.wait_for(
                    self.strategy.on_bar(latest_bar), 
                    timeout=strategy_timeout
                )
                
                if signal:
                    self.logger.info(f"🚨 SIGNAL GENERATED: {signal.signal_type} for {symbol} at ${signal.price}")
                    # Publish signal event
                    await self.event_bus.publish(create_signal_event(signal))
                else:
                    # Log why no signal was generated (every 10th iteration to avoid spam)
                    if hasattr(self, '_analysis_counter'):
                        self._analysis_counter += 1
                    else:
                        self._analysis_counter = 1
                        
                    if self._analysis_counter % 10 == 0:
                        # Get market session to understand why no signals
                        session = self.get_market_session()
                        recommendations = self.get_trading_recommendations()
                        self.logger.info(f"📊 Strategy analyzed {symbol} - no signal (analysis #{self._analysis_counter})")
                        self.logger.info(f"🕐 Current session: {session.name} (US: {session.us_time.strftime('%H:%M')}) - Focus strategies: {recommendations['focus_strategies']}")
                        self.logger.info(f"💰 Latest data: ${latest_bar.close:.2f} (Vol: {latest_bar.volume:,}) | Time: {latest_bar.timestamp}")
                        
                        # Get strategy name for specific analysis
                        strategy_name = getattr(self.strategy, '__class__', type(self.strategy)).__name__
                        self.logger.info(f"🎯 Active strategy: {strategy_name}")
                        
            except asyncio.TimeoutError:
                self.logger.error(f"⏰ Strategy analysis TIMED OUT for {symbol} after {strategy_timeout}s - forcing symbol removal")
                # Force remove this symbol as it's causing delays
                await self._handle_symbol_failure(symbol, Exception(f"Strategy timeout ({strategy_timeout}s)"))
                return  # Skip further processing for this symbol
            except Exception as e:
                self.logger.error(f"❌ Strategy analysis failed for {symbol}: {e}", exc_info=True)
                # Also remove symbol if it's consistently causing errors
                await self._handle_symbol_failure(symbol, e)
            
            # Check existing position for exit signals with timeout
            if symbol in self.positions:
                try:
                    # Run should_exit in executor with timeout since it's not async
                    exit_signal = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, 
                            self.strategy.should_exit, 
                            self.positions[symbol], 
                            latest_bar
                        ),
                        timeout=2.0  # Exit signal analysis should be even faster
                    )
                    if exit_signal:
                        self.logger.info(f"🚪 EXIT SIGNAL: {exit_signal.signal_type} for {symbol}")
                        await self.event_bus.publish(create_signal_event(exit_signal))
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏰ Exit signal analysis timed out for {symbol} position")
                except Exception as e:
                    self.logger.error(f"❌ Exit signal analysis failed for {symbol}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error processing symbol {symbol}: {e}")
            raise
    
    async def process_event(self, event):
        """Process events from the event bus"""
        if event.event_type == EventTypes.SIGNAL_GENERATED:
            await self._handle_signal(event.data["signal"])
        
        elif event.event_type == EventTypes.ORDER_FILLED:
            await self._handle_order_fill(event.data["order"])
        
        elif event.event_type == EventTypes.ORDER_REJECTED:
            await self._handle_order_rejection(event.data["order"])
        
        elif event.event_type == EventTypes.ERROR_OCCURRED:
            await self._handle_system_error(event.data)
    
    async def _handle_signal(self, signal: Signal):
        """Handle trading signals from strategy"""
        try:
            strategy_name = signal.metadata.get('strategy', 'Unknown') if hasattr(signal, 'metadata') else 'Unknown'
            self.logger.info(f"Processing signal: {signal.signal_type} for {signal.symbol} from {strategy_name} strategy")
            
            # Log position status for debugging
            if signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                position_exists = signal.symbol in self.positions
                strategy_tracking = hasattr(self.strategy, 'entry_signals') and signal.symbol in self.strategy.entry_signals
                self.logger.info(f"[POSITION-STATUS] {signal.symbol}: Engine position={position_exists}, Strategy tracking={strategy_tracking}")
            
            # Validate signal with risk manager
            if not await self.risk_manager.validate_signal(signal):
                self.logger.warning(f"Signal rejected by risk manager: {signal.signal_type} for {signal.symbol} from {strategy_name}")
                return
            
            self.logger.info(f"Signal validated by risk manager: {signal.signal_type} for {signal.symbol} from {strategy_name}")
            
            # Convert signal to order
            order = await self._signal_to_order(signal)
            if not order:
                self.logger.warning(f"Failed to convert signal to order: {signal.signal_type} for {signal.symbol} from {strategy_name}")
                return
            
            self.logger.info(f"Signal converted to order: {order.side} {order.quantity} {order.symbol} at ${order.price if order.price else 'MARKET'}")
            
            # Validate order
            if not await self.risk_manager.validate_order(order):
                self.logger.warning(f"Order rejected by risk manager: {order.side} {order.quantity} {order.symbol} from {strategy_name}")
                
                # Clean up strategy tracking when order is rejected
                if hasattr(self.strategy, 'entry_signals') and signal.symbol in self.strategy.entry_signals:
                    self.logger.info(f"[CLEANUP] {signal.symbol}: Removing strategy entry signal (order rejected by risk manager)")
                    self.strategy.entry_signals.pop(signal.symbol, None)
                
                # Clean up VolumeBreakout strategy tracking
                if hasattr(self.strategy, 'active_positions') and signal.symbol in self.strategy.active_positions:
                    self.logger.info(f"[CLEANUP] {signal.symbol}: Removing strategy active position (order rejected by risk manager)")
                    self.strategy.active_positions.pop(signal.symbol, None)
                
                # Clean up MultiStrategy tracking if applicable
                if hasattr(self.strategy, 'strategies'):
                    for strategy_name, strategy in self.strategy.strategies.items():
                        if hasattr(strategy, 'active_positions') and signal.symbol in strategy.active_positions:
                            self.logger.info(f"[CLEANUP] {signal.symbol}: Removing {strategy_name} active position (order rejected)")
                            strategy.active_positions.pop(signal.symbol, None)
                        if hasattr(strategy, 'entry_signals') and signal.symbol in strategy.entry_signals:
                            self.logger.info(f"[CLEANUP] {signal.symbol}: Removing {strategy_name} entry signal (order rejected)")
                            strategy.entry_signals.pop(signal.symbol, None)
                
                return
            
            self.logger.info(f"Order validated by risk manager: {order.side} {order.quantity} {order.symbol} from {strategy_name}")
            
            # Place order
            order_id = await self.broker.place_order(order)
            if order_id:
                order.order_id = order_id
                self.active_orders[order_id] = order
                
                # Publish order placed event
                await self.event_bus.publish(create_order_event(order, EventTypes.ORDER_PLACED))
                
                self.logger.info(f"Order placed successfully: {order.side} {order.quantity} {order.symbol} (ID: {order_id}) from {strategy_name}")
            else:
                self.logger.error(f"Failed to place order: {order.side} {order.quantity} {order.symbol} from {strategy_name}")
                
                # Clean up strategy tracking when order placement fails
                if hasattr(self.strategy, 'entry_signals') and signal.symbol in self.strategy.entry_signals:
                    self.logger.info(f"[CLEANUP] {signal.symbol}: Removing strategy entry signal (order placement failed)")
                    self.strategy.entry_signals.pop(signal.symbol, None)
                
                await self._handle_error(Exception("Failed to place order"), "place_order")
            
        except Exception as e:
            self.logger.error(f"Error handling signal: {e}")
            await self._handle_error(e, "handle_signal")
    
    async def _signal_to_order(self, signal: Signal) -> Optional[Order]:
        """Convert a signal to an order"""
        try:
            # Determine order side
            if signal.signal_type in [SignalType.LONG]:
                side = OrderSide.BUY
            elif signal.signal_type in [SignalType.SHORT, SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                side = OrderSide.SELL
            else:
                self.logger.warning(f"Unknown signal type: {signal.signal_type}")
                return None
            
            # Calculate position size
            if signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                # Exit entire position
                position = self.positions.get(signal.symbol)
                if not position:
                    # Clean up orphaned signals from strategy
                    if hasattr(self.strategy, 'entry_signals') and signal.symbol in self.strategy.entry_signals:
                        self.logger.info(f"[CLEANUP] {signal.symbol}: Cleaning up orphaned entry signal")
                        self.strategy.entry_signals.pop(signal.symbol, None)
                    
                    # Clean up orphaned VolumeBreakout positions
                    if hasattr(self.strategy, 'active_positions') and signal.symbol in self.strategy.active_positions:
                        self.logger.info(f"[CLEANUP] {signal.symbol}: Cleaning up orphaned active position")
                        self.strategy.active_positions.pop(signal.symbol, None)
                    
                    # Clean up orphaned MultiStrategy positions
                    if hasattr(self.strategy, 'strategies'):
                        for strategy_name, strategy in self.strategy.strategies.items():
                            if hasattr(strategy, 'active_positions') and signal.symbol in strategy.active_positions:
                                self.logger.info(f"[CLEANUP] {signal.symbol}: Cleaning up orphaned {strategy_name} position")
                                strategy.active_positions.pop(signal.symbol, None)
                    self.logger.warning(f"No position to exit for {signal.symbol}")
                    return None
                quantity = abs(position.quantity)
            else:
                # Calculate new position size from account or config
                capital = await self._get_account_capital()
                quantity = self.strategy.calculate_position_size(
                    signal, capital, self.config.max_risk_per_trade
                )
            
            if quantity <= 0:
                self.logger.warning(f"Invalid quantity calculated: {quantity}")
                return None
            
            # Create order
            order = Order(
                order_id="",
                symbol=signal.symbol,
                side=side,
                quantity=quantity,
                order_type=OrderType.MARKET,  # Could be configurable
                price=signal.price if side == OrderSide.BUY else None
            )
            
            return order
            
        except Exception as e:
            self.logger.error(f"Error converting signal to order: {e}")
            return None
    
    async def _handle_order_fill(self, order: Order):
        """Handle order fills"""
        try:
            self.logger.info(f"Order filled: {order}")
            
            # Remove from active orders
            self.active_orders.pop(order.order_id, None)
            
            # Update positions
            await self._update_position_from_fill(order)
            
            # Force refresh positions from broker to ensure synchronization
            try:
                broker_positions = await self.broker.get_positions()
                if broker_positions:
                    self.positions.update(broker_positions)
                    # Update risk manager with latest positions
                    if hasattr(self.risk_manager, 'update_positions'):
                        self.risk_manager.update_positions(self.positions)
                    self.logger.info(f"Position synchronization completed: {len(self.positions)} positions")
            except Exception as e:
                self.logger.warning(f"Failed to synchronize positions after fill: {e}")
            
            # Update daily stats
            self.daily_trades += 1

            # Inform RiskManager so symbol trade counters are updated
            if hasattr(self.risk_manager, "_record_symbol_trade"):
                # Increment trade count for this symbol by filled quantity > 0 trade (assume 1 trade)
                self.risk_manager._record_symbol_trade(order.symbol)
            
            # Notify strategy
            if order.symbol in self.positions:
                await self.strategy.on_position_update(self.positions[order.symbol])
            
        except Exception as e:
            self.logger.error(f"Error handling order fill: {e}")
            await self._handle_error(e, "handle_order_fill")
    
    async def _handle_order_rejection(self, order: Order):
        """Handle order rejections"""
        self.logger.warning(f"Order rejected: {order}")
        self.active_orders.pop(order.order_id, None)
    
    async def _update_position_from_fill(self, order: Order):
        """Update position based on order fill"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            # New position
            position = Position(
                symbol=symbol,
                quantity=order.filled_quantity if order.side == OrderSide.BUY else -order.filled_quantity,
                avg_price=order.avg_fill_price,
                market_price=order.avg_fill_price,
                market_value=order.filled_quantity * order.avg_fill_price,
                unrealized_pnl=0.0,
                entry_time=datetime.now()
            )
            self.positions[symbol] = position
            
            await self.event_bus.publish(create_position_event(position, EventTypes.POSITION_OPENED))
            
        else:
            # Update existing position
            position = self.positions[symbol]
            
            if order.side == OrderSide.BUY:
                new_quantity = position.quantity + order.filled_quantity
            else:
                new_quantity = position.quantity - order.filled_quantity
            
            if new_quantity == 0:
                # Position closed
                self.logger.info(f"[POSITION-CLOSED] {symbol}: Position closed, removing from tracking")
                await self.event_bus.publish(create_position_event(position, EventTypes.POSITION_CLOSED))
                del self.positions[symbol]
                
                # Clean up strategy tracking
                if hasattr(self.strategy, 'entry_signals') and symbol in self.strategy.entry_signals:
                    self.logger.info(f"[CLEANUP] {symbol}: Removing strategy entry signal (position closed)")
                    self.strategy.entry_signals.pop(symbol, None)
            else:
                # Position modified
                if (position.quantity > 0 and new_quantity > 0) or (position.quantity < 0 and new_quantity < 0):
                    # Same side, update average price
                    total_cost = position.quantity * position.avg_price + order.filled_quantity * order.avg_fill_price
                    position.avg_price = total_cost / new_quantity
                
                position.quantity = new_quantity
                await self.event_bus.publish(create_position_event(position, EventTypes.POSITION_UPDATED))
    
    async def _load_positions(self):
        """Load existing positions from broker"""
        try:
            broker_positions = await self.broker.get_positions()
            self.positions = broker_positions
            
            self.logger.info(f"Loaded {len(self.positions)} existing positions")
            
            # Notify strategy about existing positions
            for position in self.positions.values():
                await self.strategy.on_position_update(position)
                
        except Exception as e:
            self.logger.error(f"Error loading positions: {e}")
            raise
    
    async def _update_positions(self):
        """Update position values with current market prices"""
        try:
            for symbol, position in self.positions.items():
                try:
                    current_price = await self.data_provider.get_current_price(symbol)
                    position.market_price = current_price
                    position.market_value = position.quantity * current_price
                    position.unrealized_pnl = (current_price - position.avg_price) * position.quantity
                    
                except Exception as e:
                    self.logger.error(f"Error updating position for {symbol}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
    
    async def _check_risk_limits(self) -> bool:
        """Check if trading should continue based on risk limits"""
        try:
            # Check daily loss limit
            total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            if total_pnl <= self.config.max_daily_loss:
                self.logger.warning(f"Daily loss limit exceeded: {total_pnl}")
                return False
            
            # Check daily trade limit
            if self.daily_trades >= self.config.max_daily_trades:
                self.logger.warning(f"Daily trade limit exceeded: {self.daily_trades}")
                return False
            
            # Check max positions
            if len(self.positions) >= self.config.max_positions:
                self.logger.info(f"Max positions reached: {len(self.positions)}")
                return False
            
            # Check portfolio risk
            return await self.risk_manager.check_portfolio_risk(self.positions)
            
        except Exception as e:
            self.logger.error(f"Error checking risk limits: {e}")
            return False
    
    async def _close_position(self, symbol: str, reason: str):
        """Close a specific position"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # Create exit signal
        signal_type = SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT
        
        signal = Signal(
            signal_id="",
            symbol=symbol,
            signal_type=signal_type,
            strength=1.0,
            price=position.market_price,
            timestamp=datetime.now(),
            metadata={"reason": reason}
        )
        
        await self.event_bus.publish(create_signal_event(signal))
    
    async def _close_all_positions(self):
        """Close all open positions"""
        self.logger.info("Closing all positions...")
        
        for symbol in list(self.positions.keys()):
            await self._close_position(symbol, "System shutdown")
            
    async def _should_close_positions_before_market_close(self) -> bool:
        """Check if it's time to close positions before market close"""
        # TEMPORAL: Deshabilitar cierre automático para depuración
        # El sistema estaba cerrando posiciones porque usaba hora local en lugar de Eastern Time
        return False
        
        # TODO: Implementar conversión a Eastern Time
        # El código siguiente está comentado temporalmente
        """
        now = datetime.now()
        current_time = time(now.hour, now.minute)
        
        # Calculate market close time
        market_close = time(
            self.config.market_close_hour,
            self.config.market_close_minute
        )
        
        # Calculate the time to start closing positions
        minutes_before = self.config.minutes_before_close_to_exit
        close_positions_hour = self.config.market_close_hour
        close_positions_minute = self.config.market_close_minute - minutes_before
        
        # Handle minute underflow
        if close_positions_minute < 0:
            close_positions_hour -= 1
            close_positions_minute += 60
            
        close_positions_time = time(close_positions_hour, close_positions_minute)
        
        # Check if current time is between the close positions time and market close
        if close_positions_time <= current_time < market_close:
            # Only log once when we first enter this time window
            if not hasattr(self, '_positions_closing_logged') or not self._positions_closing_logged:
                self.logger.info(f"Time to close positions: {minutes_before} minutes before market close")
                self._positions_closing_logged = True
            return True
        else:
            # Reset the log flag when outside the window
            if hasattr(self, '_positions_closing_logged') and self._positions_closing_logged:
                self._positions_closing_logged = False
            return False
        """
    
    async def _close_all_positions_before_market_close(self):
        """Close all open positions before market close"""
        if not self.positions:
            return
            
        self.logger.info(f"Closing all {len(self.positions)} positions before market close")
        
        for symbol in list(self.positions.keys()):
            await self._close_position(symbol, "Market closing soon")
    
    async def _cancel_pending_orders(self):
        """Cancel all pending orders"""
        self.logger.info("Cancelling pending orders...")
        
        for order_id in list(self.active_orders.keys()):
            try:
                await self.broker.cancel_order(order_id)
            except Exception as e:
                self.logger.error(f"Error cancelling order {order_id}: {e}")
    
    async def _handle_symbol_failure(self, symbol: str, error: Exception):
        """Handle symbol processing failure with circuit breaker logic"""
        try:
            # Increment failure count
            if symbol not in self.failed_symbols:
                self.failed_symbols[symbol] = 0
            self.failed_symbols[symbol] += 1
            
            failure_count = self.failed_symbols[symbol]
            
            if failure_count >= self.max_symbol_failures:
                # Circuit breaker triggered
                self.logger.warning(f"🚫 Circuit breaker triggered for {symbol} after {failure_count} failures - removing from monitoring")
                await self.remove_symbol(symbol)
            else:
                self.logger.warning(f"⚠️ Symbol {symbol} failed ({failure_count}/{self.max_symbol_failures} failures): {error}")
                
        except Exception as e:
            self.logger.error(f"Error handling symbol failure for {symbol}: {e}")
    
    async def _handle_error(self, error: Exception, context: str):
        """Handle system errors"""
        await self.event_bus.publish(create_error_event(error, context))
    
    async def _get_account_capital(self) -> float:
        """Get account capital from broker or config with intelligent caching"""
        from datetime import datetime
        
        # Check if we have valid cached capital
        if (self._cached_capital is not None and 
            self._capital_cache_time is not None and
            (datetime.now() - self._capital_cache_time).total_seconds() < self._capital_cache_ttl):
            self.logger.debug(f"Using cached capital: ${self._cached_capital:,.2f}")
            return self._cached_capital
        
        try:
            # Only fetch from broker occasionally to prevent continuous requests
            self.logger.debug("Fetching fresh account capital from broker...")
            account_info = await asyncio.wait_for(
                self.broker.get_account_info(), 
                timeout=3.0
            )
            if account_info:
                # Try different ways to get capital from account info
                capital = None
                if hasattr(account_info, 'equity'):
                    capital = float(account_info.equity)
                elif isinstance(account_info, dict):
                    capital = account_info.get('NetLiquidation') or account_info.get('TotalCashValue')
                
                if capital and capital > 0:
                    # Cache the result
                    self._cached_capital = capital
                    self._capital_cache_time = datetime.now()
                    self.logger.info(f"✅ Fresh account capital cached: ${capital:,.2f}")
                    return capital
        except asyncio.TimeoutError:
            self.logger.warning("⏰ Timeout getting account capital from broker - using cached/config value")
        except Exception as e:
            self.logger.warning(f"❌ Could not get account capital from broker: {e} - using cached/config value")
        
        # Return cached value if available, otherwise use config
        if self._cached_capital is not None:
            self.logger.debug(f"Using stale cached capital: ${self._cached_capital:,.2f}")
            return self._cached_capital
        
        # Fallback to config value and cache it
        capital = getattr(self.config, 'portfolio_capital', 2000.0)
        self._cached_capital = capital
        self._capital_cache_time = datetime.now()
        self.logger.info(f"Using configured capital (cached): ${capital:,.2f}")
        return capital
    
    async def _handle_system_error(self, error_data: dict):
        """Handle system-level errors"""
        component = error_data.get("component", "unknown")
        error_msg = error_data.get("error", "unknown error")
        
        self.logger.error(f"System error in {component}: {error_msg}")
        
        # Could implement error recovery logic here
        # For now, just log the error
    
    # Public API methods
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions"""
        return self.positions.copy()
    
    def get_active_orders(self) -> Dict[str, Order]:
        """Get active orders"""
        return self.active_orders.copy()
    
    def get_monitored_symbols(self) -> Set[str]:
        """Get monitored symbols"""
        return self.monitored_symbols.copy()
    
    def get_daily_stats(self) -> dict:
        """Get daily trading statistics"""
        total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        
        return {
            "daily_trades": self.daily_trades,
            "daily_pnl": total_pnl,
            "active_positions": len(self.positions),
            "monitored_symbols": len(self.monitored_symbols),
            "runtime": datetime.now() - self.start_time if self.start_time else None
        }
    
    def reset_circuit_breaker(self, symbol: str = None):
        """Reset circuit breaker for a specific symbol or all symbols"""
        if symbol:
            if symbol in self.failed_symbols:
                self.failed_symbols[symbol] = 0
                self.logger.info(f"Circuit breaker reset for symbol {symbol}")
        else:
            self.failed_symbols.clear()
            self.logger.info("Circuit breaker reset for all symbols")
    
    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        failed_symbols = {symbol: count for symbol, count in self.failed_symbols.items() if count > 0}
        circuit_breaker_active = {symbol: count for symbol, count in self.failed_symbols.items() if count >= self.max_symbol_failures}
        
        return {
            "failed_symbols": failed_symbols,
            "circuit_breaker_active": circuit_breaker_active,
            "max_symbol_failures": self.max_symbol_failures
        }
            