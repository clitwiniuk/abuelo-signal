# engine/trading_engine_pipeline.py
"""
Pipeline-based Trading Engine
Ultra-fast, non-blocking architecture for optimal performance
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Any
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
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config

# Pipeline imports
from core.pipeline import TradingPipeline
from core.data_collection_stage import DataCollectionStage
from core.strategy_analysis_stage import StrategyAnalysisStage
from core.trading_execution_stage import TradingExecutionStage

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
    PIPELINE-BASED TRADING ENGINE
    - Ultra-fast execution with separated stages
    - No blocking operations during analysis
    - Minimal IBKR calls concentrated in data stage
    - Pure computation in analysis stage
    - Optimized for performance and reliability
    """
    
    @staticmethod
    def get_market_session() -> MarketSession:
        """Get current US market session information from Spain"""
        from zoneinfo import ZoneInfo
        
        spain_now = datetime.now(ZoneInfo("Europe/Madrid"))
        us_now = spain_now.astimezone(ZoneInfo("America/New_York"))
        us_time = us_now.time()
        
        # Define market sessions
        if time(4, 0) <= us_time < time(9, 30):
            return MarketSession(
                name="PREMARKET", is_premarket=True, is_regular=False, 
                is_afterhours=False, is_closed=False,
                us_time=us_now, spain_time=spain_now,
                optimal_timeout=60.0, optimal_delay=2.0
            )
        elif time(9, 30) <= us_time < time(16, 0):
            return MarketSession(
                name="REGULAR", is_premarket=False, is_regular=True,
                is_afterhours=False, is_closed=False,
                us_time=us_now, spain_time=spain_now,
                optimal_timeout=75.0, optimal_delay=1.0
            )
        elif time(16, 0) <= us_time < time(20, 0):
            return MarketSession(
                name="AFTERHOURS", is_premarket=False, is_regular=False,
                is_afterhours=True, is_closed=False,
                us_time=us_now, spain_time=spain_now,
                optimal_timeout=90.0, optimal_delay=3.0
            )
        else:
            return MarketSession(
                name="CLOSED", is_premarket=False, is_regular=False,
                is_afterhours=False, is_closed=True,
                us_time=us_now, spain_time=spain_now,
                optimal_timeout=120.0, optimal_delay=5.0
            )
    
    def __init__(self, config: TradingConfig, data_provider: IDataProvider, 
                 broker: IBroker, strategy: IStrategy, risk_manager: IRiskManager,
                 filters: List[IFilter] = None):
        self.config = config
        self.data_provider = data_provider
        self.broker = broker
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.filters = filters or []
        
        self.logger = logging.getLogger("TradingEnginePipeline")
        
        # System state
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.event_bus = AsyncEventBus()
        
        # Symbol management
        self.monitored_symbols: Set[str] = set()
        self.failed_symbols: Set[str] = set()
        
        # Performance tracking
        self.cycle_count = 0
        self.total_cycle_time = 0.0
        self.performance_metrics = {
            'cycles_completed': 0,
            'avg_cycle_time': 0.0,
            'signals_generated': 0,
            'orders_executed': 0
        }
        
        # PIPELINE COMPONENTS
        self.data_stage = DataCollectionStage(data_provider, config)
        
        # STRATEGY REGISTRY PATTERN: Intelligent strategy selection
        if hasattr(strategy, 'strategies') and isinstance(strategy.strategies, dict):
            # MultiStrategyEngine detected - use ONLY the coordinator
            strategies_list = [strategy]  # Pass only MultiStrategyEngine
            self.logger.info(f"🎯 STRATEGY REGISTRY: Using MultiStrategyEngine (coordinates {len(strategy.strategies)} strategies)")
            self.logger.info(f"   MultiStrategyEngine will handle: {list(strategy.strategies.keys())}")
        else:
            # Individual strategy - use as-is
            strategies_list = [strategy]
            self.logger.info(f"🎯 STRATEGY REGISTRY: Using individual strategy: {strategy.__class__.__name__}")
        
        self.analysis_stage = StrategyAnalysisStage(strategies_list, risk_manager)
        self.execution_stage = TradingExecutionStage(broker, risk_manager, config, self.event_bus)
        
        # Create the pipeline
        self.pipeline = TradingPipeline(
            self.data_stage,
            self.analysis_stage, 
            self.execution_stage
        )
        
        # Pipeline settings
        self.pipeline_cycle_delay = 3.0  # 3 seconds between cycles
        self.max_cycle_time = 45.0  # Max time per cycle
        
        self.logger.info("🚀 Pipeline-based TradingEngine initialized")
        self.logger.info(f"📊 Pipeline stages: {[stage.name for stage in [self.data_stage, self.analysis_stage, self.execution_stage]]}")
    
    async def initialize(self):
        """Initialize the trading engine and pipeline"""
        try:
            self.logger.info("🔧 Initializing pipeline trading engine...")
            
            # Initialize strategies (individual strategies, not MultiStrategyEngine)
            for strategy in self.analysis_stage.strategies:
                # CRITICAL FIX: Pass broker to ML Engine for position sync
                await strategy.initialize(self.event_bus, self.broker)
            
            # Connect to data provider
            if not await self.data_provider.connect():
                raise Exception("Failed to connect to data provider")
            
            # Connect to broker (skip if same instance as data_provider)
            if self.broker is not self.data_provider:
                if not await self.broker.connect():
                    raise Exception("Failed to connect to broker")
            
            # CRITICAL FIX: Re-sync ML Engine positions AFTER broker connection
            for strategy in self.analysis_stage.strategies:
                if hasattr(strategy, '_sync_existing_positions'):
                    self.logger.info(f"🔄 Re-syncing positions for {strategy.__class__.__name__} after broker connection")
                    await strategy._sync_existing_positions()
            
            # Load existing positions
            await self._load_positions()
            
            self.logger.info("✅ Pipeline trading engine initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize pipeline trading engine: {e}")
            raise
    
    async def start(self, symbols: List[str] = None):
        """Start the pipeline-based trading engine"""
        if self.is_running:
            self.logger.warning("⚠️ Pipeline trading engine is already running")
            return
        
        try:
            await self.initialize()
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # If no symbols provided but we have existing positions, monitor those
            if not symbols and hasattr(self, 'monitored_symbols') and self.monitored_symbols:
                symbols = list(self.monitored_symbols)
                self.logger.info(f"🔄 No symbols provided, using existing position symbols: {symbols}")
            
            self.monitored_symbols = set(symbols) if symbols else set()
            
            self.logger.info(f"🚀 Starting pipeline trading engine with {len(self.monitored_symbols)} symbols")
            
            # Publish system started event
            await self.event_bus.publish(Event(
                event_id="",
                event_type=EventTypes.SYSTEM_STARTED,
                timestamp=datetime.now(),
                data={"symbols": symbols}
            ))
            
            # Start main pipeline loop
            await self._run_pipeline_loop()
            
        except Exception as e:
            self.logger.error(f"❌ Error starting pipeline trading engine: {e}")
            raise
    
    async def stop(self):
        """Stop the pipeline trading engine"""
        self.logger.info("🛑 Stopping pipeline trading engine...")
        
        self.is_running = False
        
        try:
            # Quick disconnect
            if self.data_provider and self.data_provider.is_connected():
                await asyncio.wait_for(self.data_provider.disconnect(), timeout=3.0)
            
            # Clear symbol tracking
            self.monitored_symbols.clear()
            self.failed_symbols.clear()
            
            self.logger.info("✅ Pipeline trading engine stopped successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping pipeline trading engine: {e}")
    
    async def _run_pipeline_loop(self):
        """Main pipeline execution loop - ULTRA OPTIMIZED"""
        self.logger.info("🔄 Starting pipeline execution loop")
        
        while self.is_running:
            cycle_start = datetime.now()
            
            try:
                # Quick shutdown check
                if not self.is_running:
                    self.logger.info("🛑 Shutdown detected in pipeline loop")
                    break
                
                # Check if we have symbols to process
                active_symbols = list(self.monitored_symbols - self.failed_symbols)
                if not active_symbols:
                    self.logger.debug("📭 No active symbols to process")
                    await self._pipeline_sleep()
                    continue
                
                # Get market session for optimization
                session = self.get_market_session()
                
                # Log periodic status
                if self.cycle_count % 10 == 0:
                    self.logger.info(f"🔄 Pipeline cycle #{self.cycle_count}: {len(active_symbols)} symbols, session: {session.name}")
                
                # RUN PIPELINE CYCLE
                await self._execute_pipeline_cycle(active_symbols, session)
                
                # Update performance metrics
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                self._update_performance_metrics(cycle_time)
                
                # Periodic cleanup
                if self.cycle_count % 50 == 0:
                    await self._pipeline_cleanup()
                
                # Inter-cycle delay
                await self._pipeline_sleep()
                
            except Exception as e:
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                self.logger.error(f"❌ Pipeline cycle failed after {cycle_time:.2f}s: {e}")
                # Continue running - don't crash on single cycle failure
                await asyncio.sleep(5.0)  # Longer delay on error
    
    async def _execute_pipeline_cycle(self, symbols: List[str], session: MarketSession):
        """Execute a single pipeline cycle"""
        try:
            # Execute pipeline with timeout
            results = await asyncio.wait_for(
                self.pipeline.run_cycle(symbols),
                timeout=self.max_cycle_time
            )
            
            # Process results
            market_data = results.get('market_data', {})
            signals = results.get('signals', [])
            execution_results = results.get('execution_results', {})
            
            # Update metrics
            self.performance_metrics['signals_generated'] += len(signals)
            self.performance_metrics['orders_executed'] += len(execution_results.get('orders', []))
            
            # Log pipeline performance
            if signals:
                self.logger.info(f"🎯 Pipeline generated {len(signals)} signals from {len(market_data)} datasets")
            
            if execution_results.get('orders'):
                self.logger.info(f"💼 Pipeline executed {len(execution_results['orders'])} orders")
            
        except asyncio.TimeoutError:
            self.logger.error(f"⏰ Pipeline cycle timed out after {self.max_cycle_time}s")
        except Exception as e:
            self.logger.error(f"❌ Pipeline execution error: {e}")
    
    async def _pipeline_sleep(self):
        """Smart inter-cycle delay with shutdown detection"""
        sleep_interval = 0.1
        total_slept = 0.0
        
        while total_slept < self.pipeline_cycle_delay and self.is_running:
            await asyncio.sleep(sleep_interval)
            total_slept += sleep_interval
    
    async def _pipeline_cleanup(self):
        """Periodic pipeline cleanup"""
        try:
            # Clear failed symbols periodically
            if self.failed_symbols:
                self.data_stage.clear_failed_symbols()
                self.failed_symbols.clear()
                self.logger.info("🧹 Cleared failed symbols for retry")
            
            # Log performance metrics
            metrics = self.get_performance_metrics()
            self.logger.info(f"📊 Pipeline performance: {metrics['avg_cycle_time']:.2f}s avg, "
                           f"{metrics['signals_generated']} signals, {metrics['orders_executed']} orders")
            
        except Exception as e:
            self.logger.error(f"❌ Pipeline cleanup error: {e}")
    
    def _update_performance_metrics(self, cycle_time: float):
        """Update pipeline performance metrics"""
        self.cycle_count += 1
        self.total_cycle_time += cycle_time
        
        self.performance_metrics['cycles_completed'] = self.cycle_count
        self.performance_metrics['avg_cycle_time'] = self.total_cycle_time / self.cycle_count
    
    # Symbol management methods
    async def add_symbol(self, symbol: str, skip_validation: bool = False) -> bool:
        """Add symbol to pipeline monitoring"""
        if symbol in self.monitored_symbols:
            self.logger.info(f"📈 Symbol {symbol} already being monitored")
            return True
        
        # Known working symbols that can bypass validation if needed
        known_working_symbols = {'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'NVDA', 'OTRK'}
        
        if not skip_validation:
            # Enhanced validation with retry logic
            validation_attempts = 0
            max_attempts = 3
            
            while validation_attempts < max_attempts:
                try:
                    self.logger.info(f"🔍 Validating {symbol} (attempt {validation_attempts + 1}/{max_attempts})")
                    
                    data = await asyncio.wait_for(
                        self.data_provider.get_bars(symbol, self.config.timeframe, 10),
                        timeout=25.0  # Increased timeout to accommodate IBKR retries
                    )
                    if not data:
                        self.logger.warning(f"❌ No data available for {symbol}")
                        return False
                    else:
                        self.logger.info(f"✅ Validation successful for {symbol} - got {len(data)} bars")
                        break  # Success, exit retry loop
                        
                except asyncio.TimeoutError:
                    validation_attempts += 1
                    if validation_attempts < max_attempts:
                        self.logger.warning(f"⏰ Validation timeout for {symbol}, retrying ({validation_attempts}/{max_attempts})")
                        await asyncio.sleep(2.0)  # Brief delay before retry
                    else:
                        # Final fallback for timeout: if this is a known working symbol, add it anyway
                        if symbol.upper() in known_working_symbols:
                            self.logger.warning(f"⏰ Validation timeout for {symbol} after {max_attempts} attempts, but adding anyway (known working symbol)")
                            break  # Skip validation and add the symbol
                        else:
                            self.logger.warning(f"❌ Validation failed for {symbol} after {max_attempts} timeout attempts")
                            return False
                except Exception as e:
                    validation_attempts += 1
                    if validation_attempts < max_attempts:
                        self.logger.warning(f"⚠️ Validation error for {symbol}, retrying ({validation_attempts}/{max_attempts}): {e}")
                        await asyncio.sleep(2.0)
                    else:
                        # Final fallback: if this is a known working symbol, add it anyway
                        if symbol.upper() in known_working_symbols:
                            self.logger.warning(f"⚠️ Validation failed for {symbol} after {max_attempts} attempts, but adding anyway (known working symbol): {e}")
                            break  # Skip validation and add the symbol
                        else:
                            self.logger.warning(f"❌ Validation failed for {symbol} after {max_attempts} attempts: {e}")
                            return False
        
        self.monitored_symbols.add(symbol)
        self.failed_symbols.discard(symbol)  # Remove from failed if it was there
        
        self.logger.info(f"✅ Added {symbol} to pipeline monitoring ({len(self.monitored_symbols)} total)")
        return True
    
    async def remove_symbol(self, symbol: str):
        """Remove symbol from pipeline monitoring"""
        self.monitored_symbols.discard(symbol)
        self.failed_symbols.discard(symbol)
        self.logger.info(f"❌ Removed {symbol} from pipeline monitoring ({len(self.monitored_symbols)} total)")
    
    # Status and metrics methods
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        return {
            'is_running': self.is_running,
            'start_time': self.start_time,
            'monitored_symbols': self.monitored_symbols.copy(),
            'failed_symbols': self.failed_symbols.copy(),
            'performance_metrics': self.get_performance_metrics(),
            'pipeline_metrics': self.pipeline.get_pipeline_metrics()
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return self.performance_metrics.copy()
    
    def get_monitored_symbols(self) -> Set[str]:
        """Get currently monitored symbols"""
        return self.monitored_symbols.copy()
    
    # Legacy compatibility methods
    def get_positions(self):
        """Get current positions (for Streamlit compatibility - sync version)"""
        try:
            # Get real-time positions from broker to ensure accuracy
            if hasattr(self, 'execution_stage') and self.execution_stage.broker:
                # Use asyncio to call the async broker method synchronously
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're in an async context, we can't call async from sync
                        # Fall back to cached positions but log a warning
                        self.logger.debug("Using cached positions due to async context")
                        return getattr(self.execution_stage, 'positions', {})
                    else:
                        # Safe to call async method
                        return loop.run_until_complete(self.execution_stage.broker.get_positions())
                except Exception as async_e:
                    self.logger.warning(f"Could not get real-time positions: {async_e}")
                    # Fall back to cached positions
                    return getattr(self.execution_stage, 'positions', {})
            
            # Final fallback to cached positions
            if hasattr(self, 'execution_stage') and hasattr(self.execution_stage, 'positions'):
                return self.execution_stage.positions
            return {}
        except Exception as e:
            self.logger.error(f"❌ Error getting positions: {e}")
            return {}
    
    async def force_position_update(self):
        """Force a real-time position update from broker"""
        if hasattr(self, 'execution_stage'):
            await self.execution_stage._update_positions()
            return self.execution_stage.positions
        return {}
    
    def get_active_orders(self):
        """Get active orders (for Streamlit compatibility - sync version)"""
        try:
            # For sync compatibility, return cached pending orders from execution stage
            if hasattr(self, 'execution_stage') and hasattr(self.execution_stage, 'pending_orders'):
                return list(self.execution_stage.pending_orders.values())
            return []
        except Exception as e:
            self.logger.error(f"❌ Error getting active orders: {e}")
            return []
    
    def get_daily_stats(self):
        """Get daily trading statistics (for Streamlit compatibility)"""
        try:
            # Return basic pipeline stats as daily stats
            stats = {
                'trades_today': self.performance_metrics.get('orders_executed', 0),
                'signals_generated': self.performance_metrics.get('signals_generated', 0),
                'avg_cycle_time': self.performance_metrics.get('avg_cycle_time', 0.0),
                'cycles_completed': self.performance_metrics.get('cycles_completed', 0),
                'uptime_minutes': (datetime.now() - self.start_time).total_seconds() / 60 if self.start_time else 0,
                'monitored_symbols': len(self.monitored_symbols),
                'failed_symbols': len(self.failed_symbols),
                'pipeline_performance': 'EXCELLENT' if self.performance_metrics.get('avg_cycle_time', 0) < 1.0 else 'GOOD'
            }
            return stats
        except Exception as e:
            self.logger.error(f"❌ Error getting daily stats: {e}")
            return {}
    
    async def _load_positions(self):
        """Load existing positions and auto-add them to monitoring"""
        try:
            positions = await self.broker.get_positions()
            self.logger.info(f"📊 Loaded {len(positions)} existing positions")
            
            # Transfer positions to execution stage for Streamlit access
            if hasattr(self, 'execution_stage') and self.execution_stage:
                self.execution_stage.positions = {}
                for symbol, position in positions.items():
                    self.execution_stage.positions[symbol] = {
                        'quantity': position.quantity,
                        'avg_price': position.avg_price,
                        'market_price': getattr(position, 'market_price', position.avg_price),
                        'market_value': getattr(position, 'market_value', position.quantity * position.avg_price),
                        'unrealized_pnl': getattr(position, 'unrealized_pnl', 0.0)
                    }
                self.logger.info(f"📊 Transferred {len(self.execution_stage.positions)} positions to execution stage")

            # Register existing positions with centralized stop_loss_manager
            await self._register_existing_positions_with_stop_manager(positions)

            # Auto-add existing position symbols to monitoring
            if positions:
                symbols_to_add = list(positions.keys())
                self.logger.info(f"🔄 Auto-adding existing position symbols to monitoring: {symbols_to_add}")
                
                # Add symbols to the monitored symbols set
                if not hasattr(self, 'monitored_symbols'):
                    self.monitored_symbols = set()
                
                for symbol in symbols_to_add:
                    self.monitored_symbols.add(symbol)
                    
                    # Also add to data collection stage if available
                    if hasattr(self, 'data_stage') and self.data_stage:
                        try:
                            await self.data_stage.add_symbol(symbol)
                            self.logger.info(f"✅ Added {symbol} to data collection monitoring")
                        except Exception as e:
                            self.logger.warning(f"⚠️ Could not add {symbol} to data stage: {e}")
                
                self.logger.info(f"🎯 Now monitoring {len(self.monitored_symbols)} symbols for existing positions")
            
        except Exception as e:
            self.logger.error(f"❌ Error loading positions: {e}")

    async def _register_existing_positions_with_stop_manager(self, positions: Dict[str, Position]) -> None:
        """Register existing positions with centralized stop_loss_manager"""
        if not positions:
            return

        try:
            # Get the centralized stop_loss_manager
            stop_manager = get_stop_loss_manager()

            # Get database manager to retrieve strategy information
            from core.database_manager import DatabaseManager
            db_manager = DatabaseManager()

            registered_count = 0

            for symbol, position in positions.items():
                try:
                    # Get the strategy used for this symbol from recent trades
                    strategy_name = db_manager.get_latest_strategy(symbol) or "recovery_mode"

                    # Create stop loss parameters using config.ini fallbacks
                    # Since we don't have specific strategy config, use conservative defaults
                    stop_params = create_stop_params_from_config({
                        # No hardcoded values - will use config.ini fallbacks
                        # This ensures consistent 5% stop loss from config
                    })

                    # Determine position side
                    side = 'bullish' if position.quantity > 0 else 'bearish'

                    # Use current time as entry_time (approximate for existing positions)
                    entry_time = datetime.now()

                    # Register with stop_loss_manager
                    stop_manager.register_position(
                        symbol=symbol,
                        entry_price=position.avg_price,
                        entry_time=entry_time,
                        side=side,
                        strategy_name=strategy_name,
                        stop_params=stop_params
                    )

                    registered_count += 1
                    self.logger.info(f"📊 Registered existing position {symbol} with stop_loss_manager")

                except Exception as e:
                    self.logger.error(f"❌ Error registering position {symbol} with stop_manager: {e}")
                    continue

            if registered_count > 0:
                self.logger.info(f"✅ Successfully registered {registered_count} existing positions with stop_loss_manager")
            else:
                self.logger.info("📊 No positions registered with stop_loss_manager")

        except Exception as e:
            self.logger.error(f"❌ Error during stop_manager registration: {e}")

    # Event handling (simplified)
    async def process_event(self, event):
        """Process events from the event bus"""
        # Simplified event processing for pipeline
        pass