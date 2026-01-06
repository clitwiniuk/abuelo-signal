# strategies/multi_strategy_engine_ml.py
"""
ML-Powered Multi-Strategy Engine
Motor completamente refactorizado que usa Machine Learning (Contextual Multi-Armed Bandit)
para selección inteligente de estrategias basada en características del ticker y performance real.
"""

import logging
from core.database_manager import DatabaseManager
import asyncio
import configparser
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time, timezone
import pandas as pd
import numpy as np
from collections import defaultdict

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData, EventBus
from core.events import EventHandlerMixin, event_handler
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
from .ml_strategy_selector import (
    create_ml_strategy_selector, 
    create_ticker_profiler,
    ContextualBandit,
    TickerProfiler,
    TickerContext
)
# Smart Game Plan Manager integration for context-aware strategy selection

# Import hybrid ML vs Rules system
try:
    from .rule_based_selector import RuleBasedStrategySelector
    from .ml_vs_rules_tracker import MLvsRulesTracker
    HYBRID_SYSTEM_AVAILABLE = True
except ImportError:
    HYBRID_SYSTEM_AVAILABLE = False

# Import smallcap ML components
try:
    from .smallcap_bandit_adapter import (
        SmallcapContextualBandit,
        SmallcapTickerContext,
        create_smallcap_bandit
    )
    from core.risk_manager import SmallcapMayordomo
    from core.ml_exit_engine import MLExitEngine
    SMALLCAP_ML_AVAILABLE = True
    SMALLCAP_MAYORDOMO_AVAILABLE = True
    ML_EXIT_ENGINE_AVAILABLE = True
except ImportError:
    SMALLCAP_ML_AVAILABLE = False
    SMALLCAP_MAYORDOMO_AVAILABLE = False
    ML_EXIT_ENGINE_AVAILABLE = False

logger = logging.getLogger(__name__)

class MLMultiStrategyEngine(IStrategy, EventHandlerMixin):
    """
    Motor de estrategias potenciado por Machine Learning
    
    Características principales:
    1. Selección inteligente de 1-2 estrategias óptimas por ticker
    2. Aprendizaje continuo basado en performance real
    3. Análisis contextual profundo de cada ticker
    4. Eliminación de desperdicio computacional
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        self._name = "ML_MultiStrategy_Engine"
        self._parameters = parameters or {}
        self.logger = logging.getLogger(f"Strategy.{self._name}")
        
        # Initialize base classes
        super().__init__(None)
        
        # Load configuration
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        
        # Core ML components
        self.ml_selector: ContextualBandit = None
        self.ticker_profiler: TickerProfiler = None
        self.available_strategies: List[str] = []
        
        # Smallcap ML components
        self.smallcap_ml_enabled = self._parameters.get('smallcap_ml_enabled', SMALLCAP_ML_AVAILABLE)
        self.smallcap_ml_selector: SmallcapContextualBandit = None
        self.smallcap_price_threshold = self._parameters.get('smallcap_price_threshold', 15.0)  # $15 threshold
        
        # Smallcap Mayordomo integration
        self.smallcap_mayordomo_enabled = self._parameters.get('smallcap_mayordomo_enabled', SMALLCAP_MAYORDOMO_AVAILABLE)
        self.smallcap_mayordomo: SmallcapMayordomo = None
        
        # ML Exit Engine integration
        self.ml_exit_engine = None
        
        # NUEVO: Centralized Stop Loss Manager integration for EMA trailing stops
        self.stop_manager = get_stop_loss_manager()
        
        # Strategy instances (loaded on demand)
        self.strategy_instances: Dict[str, IStrategy] = {}
        
        # CRITICAL FIX: Add strategies attribute for detection by StrategyAnalysisStage
        self.strategies: Dict[str, IStrategy] = {}  # This is needed for multi-engine detection
        
        # Data management
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_generated: Dict[str, List[Signal]] = {}
        self.positions: Dict[str, Position] = {}
        
        # Trailing stop tracking
        self.position_highest_prices: Dict[str, float] = {}  # Track highest price per position
        
        # Persistence
        self.db_manager: DatabaseManager = DatabaseManager()

        # ML-specific tracking
        self.active_trades: Dict[str, Dict[str, Any]] = {}  # Tracking trades for feedback
        self.context_cache: Dict[str, TickerContext] = {}  # Cache contextos
        
        # Performance metrics
        self.total_selections: int = 0
        self.ml_vs_random_comparison: Dict[str, List[float]] = defaultdict(list)
        
        # Configuration
        self.max_strategies_per_ticker = 2  # Máximo estrategias por ticker
        self.min_bars_required = 20  # Mínimo bars para análisis
        
        # NUEVO: Smart Game Plan Manager - Reemplaza al strategy orchestrator
        self.smart_game_plan_manager = None  # Will be injected by service locator
        self.logger.info("🧠 Smart Game Plan Manager will be injected - Context-aware strategy selection")
        self.model_save_frequency = 50  # Guardar modelo cada N trades
        self.trades_since_save = 0

        # Strategy Selection Mode - NEW
        self.strategy_selection_mode = self.config.get('MULTI_STRATEGY', 'strategy_selection_mode', fallback='ml_based')
        self.logger.info(f"🎯 Strategy selection mode: {self.strategy_selection_mode}")
        
        # Event bus (set during initialization)
        self.event_bus: Optional[EventBus] = None
    
    def set_smart_game_plan_manager(self, smart_game_plan_manager):
        """Inject Smart Game Plan Manager from service locator"""
        self.smart_game_plan_manager = smart_game_plan_manager
        self.logger.info("🧠 Smart Game Plan Manager injected successfully")
        
        self.logger.info(f"🤖 ML Multi-Strategy Engine initialized")
        self.logger.info(f"   Strategies dict: {type(self.strategies)} - {len(self.strategies)} strategies loaded")
        self.logger.info(f"   Detection attributes: strategies={hasattr(self, 'strategies')}, is_dict={isinstance(getattr(self, 'strategies', None), dict)}")
    
    async def initialize(self, event_bus: EventBus, broker=None) -> None:
        """Initialize the ML-powered multi-strategy engine"""
        self.event_bus = event_bus
        self.broker = broker
        
        # Load available strategies from config
        self._load_available_strategies()
        
        # Initialize ML components
        self.ml_selector = create_ml_strategy_selector(
            self.available_strategies,
            "data/ml_models/strategy_selector.json"
        )
        self.ticker_profiler = create_ticker_profiler()
        
        # Initialize smallcap ML components if enabled
        self.logger.info(f"🔍 Smallcap ML initialization: enabled={self.smallcap_ml_enabled}, available={SMALLCAP_ML_AVAILABLE}")
        self.logger.info(f"🔍 Available strategies: {self.available_strategies}")
        
        if self.smallcap_ml_enabled and SMALLCAP_ML_AVAILABLE:
            try:
                # Smallcap-specific strategies (mapped from available strategies)
                smallcap_strategies = self._map_to_smallcap_strategies(self.available_strategies)
                self.logger.info(f"🔍 Mapped smallcap strategies: {smallcap_strategies}")
                
                # Ensure we have at least some default strategies
                if not smallcap_strategies:
                    self.logger.warning("No smallcap strategies mapped, using enabled strategies from config")
                    smallcap_strategies = self.available_strategies  # Use enabled strategies from config.ini
                
                self.smallcap_ml_selector = create_smallcap_bandit(smallcap_strategies)
                self.logger.info(f"✅ SmallcapContextualBandit created successfully: {type(self.smallcap_ml_selector)}")
                
                # Try to load existing smallcap model
                smallcap_model_path = "data/ml_models/smallcap_strategy_bandit.json"
                try:
                    import os
                    if os.path.exists(smallcap_model_path):
                        self.smallcap_ml_selector.load_model(smallcap_model_path)
                        self.logger.info(f"📂 Loaded smallcap ML model from {smallcap_model_path}")
                except Exception as load_error:
                    self.logger.warning(f"Could not load smallcap ML model: {load_error}")
                
                self.logger.info(f"🧠 Smallcap ML enabled with strategies: {smallcap_strategies}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize smallcap ML: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.smallcap_ml_enabled = False
                self.smallcap_ml_selector = None
        else:
            self.logger.warning(f"🚫 Smallcap ML not initialized: enabled={self.smallcap_ml_enabled}, available={SMALLCAP_ML_AVAILABLE}")
            self.smallcap_ml_selector = None
        
        # EMERGENCY FALLBACK: If smallcap_ml_selector is still None, create a minimal one
        if self.smallcap_ml_enabled and self.smallcap_ml_selector is None:
            try:
                self.logger.warning("🔧 Emergency fallback: creating minimal smallcap ML selector")
                default_strategies = ['gap_go', 'daily_plays', 'first_day_bounce', 'red_to_green', 'gap_crap_reversal']
                self.smallcap_ml_selector = create_smallcap_bandit(default_strategies)
                self.logger.info(f"✅ Emergency smallcap ML selector created with: {default_strategies}")
            except Exception as fallback_error:
                self.logger.error(f"❌ Emergency fallback failed: {fallback_error}")
                self.smallcap_ml_enabled = False
                self.smallcap_ml_selector = None
        
        # Initialize SmallcapMayordomo if enabled
        if self.smallcap_mayordomo_enabled and SMALLCAP_MAYORDOMO_AVAILABLE:
            try:
                from core.interfaces import TradingConfig
                
                # Create config object for mayordomo (load from config.ini)
                mayordomo_config = TradingConfig(
                    max_daily_trades=self.config.getint('TRADING', 'max_daily_trades', fallback=10),
                    max_daily_loss=self.config.getfloat('TRADING', 'max_daily_loss', fallback=-500.0),
                    max_position_value=self.config.getfloat('TRADING', 'max_position_value', fallback=200.0),
                    max_positions=self.config.getint('TRADING', 'max_positions', fallback=1),
                    portfolio_value=self.config.getfloat('TRADING', 'portfolio_capital', fallback=2000.0)
                )
                
                self.smallcap_mayordomo = SmallcapMayordomo(mayordomo_config)
                self.logger.info("🏛️ SmallcapMayordomo initialized - Daily plays orchestrator active")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize SmallcapMayordomo: {e}")
                self.smallcap_mayordomo_enabled = False
        
        # Initialize ML Exit Engine
        if ML_EXIT_ENGINE_AVAILABLE:
            try:
                self.ml_exit_engine = MLExitEngine()
                self.logger.info("🎯 MLExitEngine initialized - Intelligent exit system active")
            except Exception as e:
                self.logger.error(f"Failed to initialize MLExitEngine: {e}")
                self.ml_exit_engine = None
        else:
            self.ml_exit_engine = None
            self.logger.warning("MLExitEngine not available - using fallback exit logic")

        # Initialize Hybrid ML vs Rules System
        self.hybrid_system_enabled = self.config.getboolean('ML_MULTI_STRATEGY', 'hybrid_system_enabled', fallback=True)
        if self.hybrid_system_enabled and HYBRID_SYSTEM_AVAILABLE:
            try:
                self.rule_based_selector = RuleBasedStrategySelector()
                self.ml_vs_rules_tracker = MLvsRulesTracker()
                self.logger.info("🔄 Hybrid ML vs Rules system initialized - Transparent comparison active")
            except Exception as e:
                self.logger.error(f"Failed to initialize hybrid system: {e}")
                self.hybrid_system_enabled = False
                self.rule_based_selector = None
                self.ml_vs_rules_tracker = None
        else:
            self.hybrid_system_enabled = False
            self.rule_based_selector = None
            self.ml_vs_rules_tracker = None
            if not HYBRID_SYSTEM_AVAILABLE:
                self.logger.warning("Hybrid system not available - using ML only")

        # Pre-load most common strategies
        await self._preload_common_strategies()
        
        # Register event handlers
        self._register_event_handlers()
        
        # Sync existing positions
        await self._sync_existing_positions()
        
        # Initialize strategy-specific scanner dispatcher
        try:
            from scanner.strategy_scanner_dispatcher import StrategyScannerDispatcher
            self.scanner_dispatcher = StrategyScannerDispatcher()
            self.scanner_enabled = True
            self.logger.info("🎯 Strategy Scanner Dispatcher initialized")
        except ImportError as e:
            self.scanner_dispatcher = None
            self.scanner_enabled = False
            self.logger.warning(f"Strategy Scanner Dispatcher not available: {e}")
        
        self.logger.info(f"🚀 ML Engine initialized with {len(self.available_strategies)} strategies")
        self.logger.info(f"   Available: {self.available_strategies}")
        self.logger.info(f"   Max strategies per ticker: {self.max_strategies_per_ticker}")
        self.logger.info(f"   Scanner integration: {self.scanner_enabled}")
    
    def _load_available_strategies(self):
        """Load available strategies from config"""
        try:
            if self.config.has_section('MULTI_STRATEGY'):
                enabled_str = self.config.get('MULTI_STRATEGY', 'enabled_strategies', fallback='')
                self.available_strategies = [s.strip() for s in enabled_str.split(',') if s.strip()]

            if not self.available_strategies:
                # Fallback strategies (prioritize new catalyst_momentum strategy)
                self.available_strategies = [
                    'catalyst_momentum',      # NEW: Primary strategy for catalyst detection
                    'macdv_smallcaps', 'gap_go', 'first_day_bounce', 'red_to_green', 'vwap_smallcaps', 'vwap_reclaim', 'gap_crap_reversal'
                ]

            self.logger.info(f"📋 Loaded {len(self.available_strategies)} available strategies")

        except Exception as e:
            self.logger.error(f"Error loading strategies config: {e}")
            self.available_strategies = ['macdv_smallcaps', 'gap_go']  # Minimal fallback
    
    def _map_to_smallcap_strategies(self, available_strategies: List[str]) -> List[str]:
        """Map available strategies to smallcap bandit strategies"""
        strategy_mapping = {
            # NEW: Primary catalyst momentum strategy
            # 'catalyst_momentum': 'catalyst_momentum',  # DISABLED: Causing instantiation errors
            'gap_go': 'gap_go',
            'daily_plays': 'daily_plays',
            'first_day_bounce': 'first_day_bounce',
            'macdv_smallcaps': 'macdv_smallcaps',
            'gap_crap_reversal': 'gap_crap_reversal',
            'ascending_triangle': 'ascending_triangle',
            'bull_flag': 'bull_flag',
            'falling_wedge': 'falling_wedge',
            # Map various volume explosion strategies to explosive_volume
            'explosive_volume': 'explosive_volume',
            'simple_volume_explosion': 'explosive_volume',
            'improved_simple_explosion': 'explosive_volume',
            'volume_explosion_pullback': 'explosive_volume',
            'volume_momentum': 'explosive_volume',
            # Map gap strategies
            'optimized_gap_go': 'gap_go',
            # Map other strategies
            # 'orb': removed - no real edge
            'vcp': 'daily_plays',      # VCP is a catalyst-type play
            'vwap_smallcaps': 'daily_plays',
            'vwap_reclaim': 'daily_plays',
            'eod_momentum': 'daily_plays',
            'pmh_breakout': 'gap_go'   # Premarket high breakout similar to gap
        }
        
        smallcap_strategies = []
        for strategy in available_strategies:
            mapped = strategy_mapping.get(strategy)
            if mapped and mapped not in smallcap_strategies:
                smallcap_strategies.append(mapped)
        
        # Ensure we have at least the core smallcap strategies
        core_strategies = ['gap_go', 'daily_plays', 'explosive_volume', 'macdv_smallcaps', 'first_day_bounce', 'gap_crap_reversal']
        for core in core_strategies:
            if core not in smallcap_strategies:
                smallcap_strategies.append(core)
        
        return smallcap_strategies
    
    async def _preload_common_strategies(self):
        """Pre-load most commonly used strategies"""
        common_strategies = ['macdv_smallcaps', 'gap_go', 'first_day_bounce']
        
        for strategy_name in common_strategies:
            if strategy_name in self.available_strategies:
                try:
                    strategy_instance = await self._load_strategy_instance(strategy_name)
                    if strategy_instance:
                        self.strategy_instances[strategy_name] = strategy_instance
                        self.logger.info(f"✅ Pre-loaded strategy: {strategy_name}")
                except Exception as e:
                    self.logger.error(f"❌ Failed to pre-load {strategy_name}: {e}")
    
    async def _load_strategy_instance(self, strategy_name: str) -> Optional[IStrategy]:
        """Load strategy instance dynamically"""
        try:
            # Map strategy names to their correct imports
            strategy_mapping = {
                'macdv_smallcaps': ('macdv_strategy', 'MACDVStrategy'),
                'gap_go': ('gap_go_strategy', 'GapGoStrategy'),
                # 'orb': removed - no real edge
                'vcp': ('vcp_strategy', 'VCPStrategy'),
                'daily_plays': ('daily_plays_strategy', 'DailyPlaysStrategy'),
                'first_day_bounce': ('first_day_bounce_strategy', 'FirstDayBounceStrategy'),
                'gap_crap_reversal': ('gap_crap_reversal_strategy', 'GapCrapReversalStrategy'),
                # Pattern strategies - NEW
                'ascending_triangle': ('ascending_triangle_strategy', 'AscendingTriangleStrategy'),
                'bull_flag': ('bull_flag_strategy', 'BullFlagStrategy'),
                'falling_wedge': ('falling_wedge_strategy', 'FallingWedgeStrategy'),
                # 'catalyst_momentum': ('catalyst_momentum_strategy', 'CatalystMomentumStrategy'),  # DISABLED: Causing instantiation errors
                'vwap_smallcaps': ('vwap_strategy', 'VWAPSmallcapsStrategy'),
                'vwap_reclaim': ('vwap_reclaim_strategy', 'VWAPReclaimStrategy'),
                'eod_momentum': ('eod_momentum_strategy', 'EndOfDayMomentumStrategy'),
                'pmh_breakout': ('pmh_breakout_strategy', 'PremarketHighBreakoutStrategy'),
                'july_strategy': ('july_strategy', 'JulyStrategy')
            }
            
            if strategy_name not in strategy_mapping:
                self.logger.warning(f"Unknown strategy: {strategy_name}")
                return None
                
            module_name, class_name = strategy_mapping[strategy_name]
            
            try:
                # Try to import the module
                module = __import__(f'strategies.{module_name}', fromlist=[class_name])
                strategy_class = getattr(module, class_name)

                # Load strategy-specific parameters from config
                config_section = f"{strategy_name.upper()}_STRATEGY"
                strategy_parameters = {}
                if self.config.has_section(config_section):
                    strategy_parameters = dict(self.config.items(config_section))
                    # Convert numeric values
                    for key, value in strategy_parameters.items():
                        try:
                            if '.' in value:
                                strategy_parameters[key] = float(value)
                            else:
                                strategy_parameters[key] = int(value)
                        except ValueError:
                            # Keep as string if not numeric
                            pass

                return strategy_class(strategy_parameters)
                
            except ImportError as e:
                self.logger.warning(f"Strategy module not found: {strategy_name} ({module_name}) - {e}")
                return None
            except AttributeError as e:
                self.logger.warning(f"Strategy class not found: {class_name} in {module_name} - {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error loading strategy {strategy_name}: {e}")
            return None
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Main ML-powered bar processing logic
        """
        try:
            symbol = bar.symbol
            
            # DEBUG: Log that ML engine is processing (every 5th symbol to see more activity)
            if hash(symbol) % 5 == 0:  # Log only for some symbols
                self.logger.info(f"🤖 ML Engine processing bar for {symbol} @ ${bar.close:.2f}")
            
            # 1. Update data structures
            await self._update_data_structures(symbol, bar)
            
            # 2. **CRITICAL FIX** - Check exit conditions FIRST for existing positions
            if symbol in self.positions:
                self.logger.info(f"🔍 ML Engine: Checking exit conditions for existing position in {symbol}")
                exit_signal = await self._check_exit_conditions(symbol, bar)
                if exit_signal:
                    self.logger.info(f"🚪 ML Engine: Exit signal for {symbol} - {exit_signal.metadata.get('reason', 'unknown')}")
                    return exit_signal
                else:
                    self.logger.debug(f"🔍 ML Engine: No exit signal for {symbol} - holding position")
            elif symbol == 'XOS':  # Debug XOS specifically
                self.logger.info(f"⚠️ ML Engine: XOS not found in positions dict. Available positions: {list(self.positions.keys())}")
            
            # 3. Check if we have enough data for new entries
            bars_count = len(self.bars_history.get(symbol, []))
            if bars_count < self.min_bars_required:
                if hash(symbol) % 10 == 0:  # Log occasionally to avoid spam
                    self.logger.info(f"📊 {symbol}: Insufficient data ({bars_count}/{self.min_bars_required} bars) - skipping ML analysis")
                return None
            
            # 4. Generate ticker context for ML
            context = await self._generate_ticker_context(symbol, bar)
            
            # 4. ML-powered strategy selection (CORE INNOVATION)
            selected_strategies = await self._ml_select_strategies(symbol, context)
            
            if not selected_strategies:
                if hash(symbol) % 15 == 0:  # Log occasionally  
                    self.logger.info(f"🤖 {symbol}: No strategies selected by ML")
                return None
            
            if hash(symbol) % 10 == 0:  # Log ML selections occasionally
                self.logger.info(f"🎯 {symbol}: ML selected strategies: {selected_strategies}")
            
            # 5. Execute only selected strategies
            candidate_signals = await self._execute_selected_strategies(
                symbol, bar, selected_strategies
            )
            
            if not candidate_signals:
                if hash(symbol) % 15 == 0:  # Log occasionally
                    self.logger.info(f"📊 {symbol}: Selected strategies {selected_strategies} generated no signals")
                return None
            
            # 7. ML-powered signal selection
            best_signal = await self._ml_select_best_signal(
                candidate_signals, context
            )
            
            if best_signal:
                # CRITICAL FIX: Filter SHORT signals if long_only mode is enabled
                long_only = self.config.getboolean('GLOBAL', 'long_only', fallback=False)
                if long_only and best_signal.signal_type == SignalType.SHORT:
                    self.logger.info(f"🚫 ML Engine: Filtered SHORT signal for {symbol} (long_only mode)")
                    return None
                
                # 8. Track for ML feedback
                await self._track_signal_for_feedback(best_signal, context)
                
                # 9. Update statistics
                self.total_selections += 1
                
                self.logger.info(f"🎯 ML Selected: {best_signal.signal_type} for {symbol} "
                              f"using {best_signal.metadata.get('strategy_name', 'unknown')} "
                              f"| Confidence: {best_signal.confidence:.2f}")
                
                return best_signal
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in ML bar processing for {bar.symbol}: {e}")
            return None
    
    async def _update_data_structures(self, symbol: str, bar: MarketData):
        """Update internal data structures efficiently"""
        # Update bars history
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        # Deduplication
        if (not self.bars_history[symbol] or 
            bar.timestamp > self.bars_history[symbol][-1].timestamp):
            self.bars_history[symbol].append(bar)
        elif bar.timestamp == self.bars_history[symbol][-1].timestamp:
            self.bars_history[symbol][-1] = bar  # Update latest
        
        # Keep reasonable history size
        max_bars = 500  # Sufficient for most technical analysis
        if len(self.bars_history[symbol]) > max_bars:
            self.bars_history[symbol] = self.bars_history[symbol][-max_bars:]
        
        # Update ticker profiler
        self.ticker_profiler.update_ticker_data(bar)
    
    async def _generate_ticker_context(self, symbol: str, bar: MarketData) -> TickerContext:
        """Generate rich context for ML decision making"""
        # Check cache first
        cache_key = f"{symbol}_{bar.timestamp}"
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        # Generate new context
        context = self.ticker_profiler.get_ticker_context(symbol, bar)
        
        # Cache it
        self.context_cache[cache_key] = context
        
        # Clean old cache entries (keep last 100)
        if len(self.context_cache) > 100:
            # Remove oldest entries
            old_keys = list(self.context_cache.keys())[:-50]
            for key in old_keys:
                del self.context_cache[key]
        
        return context
    
    def _create_ticker_context_for_ml(self, symbol: str, bar: MarketData) -> Optional['SmallcapTickerContext']:
        """
        Create SmallcapTickerContext from MarketData bar for ML exit strategy selection
        This method is called during exit condition evaluation when no existing strategy is found
        """
        try:
            if not SMALLCAP_ML_AVAILABLE:
                self.logger.warning(f"SmallcapTickerContext not available for {symbol}")
                return None
            
            # Get current time for time-based calculations
            current_time = datetime.now()
            market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
            
            # Calculate time of day (0.0 = market open, 1.0 = market close)
            if current_time < market_open:
                time_of_day = 0.0
            elif current_time > market_close:
                time_of_day = 1.0
            else:
                total_minutes = (market_close - market_open).total_seconds() / 60
                elapsed_minutes = (current_time - market_open).total_seconds() / 60
                time_of_day = min(1.0, max(0.0, elapsed_minutes / total_minutes))
            
            # Calculate basic volume ratio (use default if not available)
            volume_ratio = 1.0
            if hasattr(bar, 'volume') and bar.volume and symbol in self.bars_history:
                recent_volumes = [b.volume for b in self.bars_history[symbol][-10:] if b.volume > 0]
                if recent_volumes:
                    avg_volume = sum(recent_volumes) / len(recent_volumes)
                    volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0
            
            # Calculate price tier (normalize price to 0-1 range for $0.50-$15)
            price_tier = min(1.0, max(0.0, (bar.close - 0.5) / 14.5))
            
            # Calculate basic momentum score (price change over recent bars)
            momentum_score = 0.5  # Default neutral
            if symbol in self.bars_history and len(self.bars_history[symbol]) >= 5:
                recent_bars = self.bars_history[symbol][-5:]
                if len(recent_bars) >= 2:
                    price_change = (bar.close - recent_bars[0].close) / recent_bars[0].close
                    momentum_score = min(1.0, max(0.0, 0.5 + price_change * 2))  # Scale to 0-1
            
            # Create SmallcapTickerContext with estimated values for exit evaluation
            from .smallcap_bandit_adapter import SmallcapTickerContext
            
            context = SmallcapTickerContext(
                symbol=symbol,
                current_price=bar.close,
                avg_volume_10=100000,  # Default values since we're focusing on exits
                avg_volume_50=100000,
                volatility_10=0.2,
                volatility_50=0.2,
                price_change_1h=0.0,
                price_change_4h=0.0,
                rsi_14=50.0,
                volume_ratio_current=volume_ratio,
                volume_spike_frequency=0.1,
                hour_of_day=current_time.hour + current_time.minute/60.0,
                minutes_from_open=120,  # Default 2 hours from open
                is_first_hour=time_of_day < 0.15,  # First hour of market
                is_last_hour=time_of_day > 0.85,   # Last hour of market
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.5,
                mean_reversion_tendency=0.5,
                # SmallcapTickerContext specific fields
                gap_percentage=0.0,  # Default since we don't have previous close
                volume_ratio=volume_ratio,
                catalyst_strength=0.5,  # Default neutral
                news_age_hours=2.0,
                catalyst_type_score=0.3,
                price_tier=price_tier,
                time_of_day=time_of_day,
                momentum_score=momentum_score,
                premarket_factor=1.0 if current_time < market_open else 0.0,
                volume_spike_confirmed=volume_ratio >= 3.0,
                htb_status=0.0  # Default not hard to borrow
            )
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error creating ticker context for {symbol}: {e}")
            return None
    
    async def _ml_select_strategies(self, symbol: str, context: TickerContext) -> List[str]:
        """
        STRATEGY SELECTION - Rule-based or ML-based depending on configuration
        """
        try:
            # DEBUG: Log all available strategies and context
            self.logger.info(f"🎯 DEBUG {symbol}: Strategy selection for ${context.current_price:.2f}, available: {self.available_strategies}")
            self.logger.info(f"🎯 DEBUG {symbol}: Selection mode: {self.strategy_selection_mode}, smallcap_enabled: {self.smallcap_ml_enabled}")

            # STEP 0: Check if we should use rule-based selection FIRST
            if self.strategy_selection_mode == 'rule_based':
                # Use rule-based selection only
                rule_strategies = await self._rule_based_select_strategies(symbol, context)
                self.logger.info(f"🎯 DEBUG {symbol}: RULE-BASED selection: {rule_strategies}")
                return rule_strategies

            # STEP 1: Get ML selection (existing logic)
            is_smallcap = context.current_price <= self.smallcap_price_threshold
            use_smallcap_ml = (is_smallcap and
                              self.smallcap_ml_enabled and
                              self.smallcap_ml_selector is not None)

            self.logger.info(f"🎯 DEBUG {symbol}: Smallcap check - price: ${context.current_price:.2f}, threshold: ${self.smallcap_price_threshold:.2f}, is_smallcap: {is_smallcap}, use_smallcap_ml: {use_smallcap_ml}")

            if use_smallcap_ml:
                ml_strategies = await self._smallcap_mayordomo_select_strategies(symbol, context)
                self.logger.info(f"🎯 DEBUG {symbol}: SMALLCAP ML selection: {ml_strategies}")
            else:
                ml_strategies = await self._original_ml_select_strategies(symbol, context)
                self.logger.info(f"🎯 DEBUG {symbol}: ORIGINAL ML selection: {ml_strategies}")

            # STEP 2: Get rule-based selection (if hybrid system enabled)
            rule_strategies = []
            if self.hybrid_system_enabled and self.rule_based_selector:
                try:
                    rule_strategies = self.rule_based_selector.select_strategies(symbol, context)
                except Exception as e:
                    self.logger.error(f"Error in rule-based selection for {symbol}: {e}")
                    rule_strategies = []

            # STEP 3: Hybrid decision logic
            if self.hybrid_system_enabled:
                final_strategies, selection_method = self._hybrid_decision_logic(
                    symbol, ml_strategies, rule_strategies, context
                )

                # STEP 4: Track comparison for analysis
                if self.ml_vs_rules_tracker:
                    context_data = {
                        'price': context.current_price,
                        'volume_ratio': getattr(context, 'volume_ratio', 0),
                        'gap_percent': getattr(context, 'gap_percent', 0),
                        'is_smallcap': is_smallcap
                    }
                    self.ml_vs_rules_tracker.record_selection(
                        symbol=symbol,
                        ml_choice=ml_strategies,
                        rule_choice=rule_strategies,
                        actual_choice=final_strategies,
                        selection_method=selection_method,
                        context_data=context_data
                    )

                return final_strategies
            else:
                # If hybrid disabled, check strategy_selection_mode from config
                selection_mode = getattr(self, 'strategy_selection_mode', 'ml_based')
                if selection_mode == 'rule_based':
                    # Use rule-based selection only
                    rule_strategies = await self._rule_based_select_strategies(symbol, context)
                    return rule_strategies
                else:
                    # Fallback to ML only
                    return ml_strategies

        except Exception as e:
            self.logger.error(f"Error in hybrid strategy selection: {e}")
            # Emergency fallback: return first available strategy
            return self.available_strategies[:1] if self.available_strategies else []

    def _hybrid_decision_logic(self, symbol: str, ml_strategies: List[str],
                              rule_strategies: List[str], context: TickerContext) -> tuple[List[str], str]:
        """
        Hybrid decision logic: Choose between ML and rule-based selections

        Returns:
            tuple: (final_strategies, selection_method)
        """
        try:
            # Strategy 1: If both agree, use ML with high confidence
            ml_set = set(ml_strategies)
            rule_set = set(rule_strategies)

            if ml_set == rule_set and ml_strategies:
                self.logger.info(f"🤝 {symbol}: ML and Rules AGREE: {ml_strategies}")
                return ml_strategies, "ML_VALIDATED"

            # Strategy 2: If rules found strategies but ML didn't, use rules as fallback
            if rule_strategies and not ml_strategies:
                self.logger.info(f"🔄 {symbol}: ML empty, using Rules fallback: {rule_strategies}")
                return rule_strategies, "RULES_FALLBACK"

            # Strategy 3: If ML found strategies but rules didn't, use ML
            if ml_strategies and not rule_strategies:
                self.logger.info(f"🤖 {symbol}: Rules empty, using ML: {ml_strategies}")
                return ml_strategies, "ML_OVERRIDE"

            # Strategy 4: Both have different strategies - prioritize based on confidence
            if ml_strategies and rule_strategies:
                # For now, trust ML but log the disagreement for analysis
                self.logger.info(f"❌ {symbol}: DISAGREEMENT - ML: {ml_strategies}, Rules: {rule_strategies}")
                self.logger.info(f"   Using ML selection: {ml_strategies}")
                return ml_strategies, "ML_OVERRIDE"

            # Strategy 5: Neither found anything - return empty
            self.logger.debug(f"❌ {symbol}: Both ML and Rules returned empty")
            return [], "NO_SELECTION"

        except Exception as e:
            self.logger.error(f"Error in hybrid decision logic for {symbol}: {e}")
            # Emergency fallback to ML
            return ml_strategies if ml_strategies else rule_strategies, "ERROR_FALLBACK"

    async def _smallcap_ml_select_strategies(self, symbol: str, context: TickerContext) -> List[str]:
        """
        Smallcap-specific ML strategy selection using SmallcapContextualBandit
        """
        try:
            # Convert TickerContext to SmallcapTickerContext
            smallcap_context = self._convert_to_smallcap_context(symbol, context)
            
            # Filter strategies by basic suitability
            suitable_strategies = await self._filter_suitable_strategies(context)
            
            # Map to smallcap strategy names
            smallcap_suitable = []
            strategy_mapping = self._get_strategy_mapping()
            
            for strategy in suitable_strategies:
                mapped = strategy_mapping.get(strategy)
                if mapped and mapped not in smallcap_suitable:
                    smallcap_suitable.append(mapped)
            
            if not smallcap_suitable:
                # Fallback to default smallcap strategies
                smallcap_suitable = ['gap_go', 'daily_plays', 'first_day_bounce', 'red_to_green', 'gap_crap_reversal']
            
            # Use SmallcapContextualBandit to select strategies
            selected_smallcap_strategies = []
            
            # Safety check: ensure smallcap_ml_selector is initialized
            if self.smallcap_ml_selector is None:
                self.logger.warning("smallcap_ml_selector is None - falling back to original ML")
                return await self._original_ml_select_strategies(symbol, context)
            
            for _ in range(self.max_strategies_per_ticker):
                if not smallcap_suitable:
                    break
                    
                # Use smallcap ML selection
                best_strategy = self.smallcap_ml_selector.select_strategy(
                    smallcap_context, smallcap_suitable
                )
                
                if best_strategy:
                    selected_smallcap_strategies.append(best_strategy)
                    smallcap_suitable.remove(best_strategy)  # Avoid duplicates
            
            # Map back to original strategy names
            reverse_mapping = {v: k for k, v in strategy_mapping.items()}
            selected_strategies = []
            
            for smallcap_strategy in selected_smallcap_strategies:
                # Find original strategies that map to this smallcap strategy
                original_strategies = [k for k, v in strategy_mapping.items() if v == smallcap_strategy]
                for orig in original_strategies:
                    if orig in self.available_strategies and orig not in selected_strategies:
                        selected_strategies.append(orig)
                        break
            
            if selected_strategies:
                self.logger.info(f"🧠💎 Smallcap ML selected for {symbol} (${context.current_price:.2f}): {selected_strategies}")
            
            return selected_strategies
            
        except Exception as e:
            self.logger.error(f"Error in smallcap ML strategy selection: {e}")
            # Fallback to original ML
            return await self._original_ml_select_strategies(symbol, context)
    
    async def _smallcap_mayordomo_select_strategies(self, symbol: str, context: TickerContext) -> List[str]:
        """
        Enhanced smallcap strategy selection with Mayordomo orchestration
        This method should work WITHOUT requiring smallcap_ml_selector
        """
        try:
            # FAILSAFE: If this method is called but smallcap_ml_selector is None, 
            # just use simple strategy selection based on context
            if self.smallcap_ml_selector is None:
                self.logger.info(f"🔧 Mayordomo method: smallcap_ml_selector is None, using context-based selection")
                # Simple fallback: select strategies based on price and context
                basic_strategies = []
                if context.current_price < 5.0:  # Very low price - ultra volatile, low volume
                    basic_strategies = ['gap_go', 'daily_plays']  # Focus on gaps and momentum
                elif context.current_price < 10.0:  # Mid smallcap - sweet spot with good volume & movement
                    basic_strategies = ['daily_plays', 'gap_go', 'first_day_bounce', 'red_to_green', 'macdv_smallcaps']
                else:  # Higher smallcap - exclude from trading
                    basic_strategies = []
                
                self.logger.info(f"🎯 Selected strategies for {symbol} (${context.current_price:.2f}): {basic_strategies}")
                return basic_strategies
            
            # NEW APPROACH: Let ML learn timing patterns first, then apply risk management
            # Step 1: ML selects strategies based on learned patterns (including timing)
            ml_selected_strategies = []
            
            if self.smallcap_ml_selector:
                try:
                    # Convert to smallcap context and let ML decide
                    smallcap_context = self._convert_to_smallcap_context(symbol, context)
                    selected_strategy = self.smallcap_ml_selector.select_strategy(smallcap_context)
                    if selected_strategy:
                        ml_selected_strategies = [selected_strategy]
                        self.logger.info(f"🧠 Smallcap ML selected: {selected_strategy} for {symbol}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Smallcap ML selection failed for {symbol}: {e}")
            
            # Fallback if ML doesn't select anything
            if not ml_selected_strategies:
                # Use context-based selection as fallback
                if context.current_price < 5.0:  # Very low price - ultra volatile, low volume
                    ml_selected_strategies = ['gap_go', 'daily_plays']  # Focus on gaps and momentum
                elif context.current_price < 10.0:  # Mid smallcap - sweet spot with good volume & movement
                    ml_selected_strategies = ['daily_plays', 'gap_go', 'orb', 'first_day_bounce', 'red_to_green', 'macdv_smallcaps']
                else:  # Higher smallcap - exclude from trading
                    ml_selected_strategies = []
                self.logger.info(f"🎯 Fallback selection for {symbol} (${context.current_price:.2f}): {ml_selected_strategies}")
            
            # Step 2: Apply Mayordomo risk management (but don't block completely)
            if self.smallcap_mayordomo_enabled and self.smallcap_mayordomo:
                timing_analysis = self.smallcap_mayordomo.get_optimal_entry_timing(
                    symbol, 
                    'TECHNICAL'  # Default catalyst type, could be enhanced with actual catalyst detection
                )
                
                # Instead of blocking, adjust strategy confidence and risk parameters
                if timing_analysis['recommendation'] == 'AVOID':
                    self.logger.info(f"🏛️ Mayordomo: Poor timing for {symbol} - {timing_analysis['reasoning']} - But letting ML learn")
                    # Continue with strategies but with more conservative parameters
                elif timing_analysis['recommendation'] == 'CAUTION':
                    self.logger.info(f"🏛️ Mayordomo: Caution for {symbol} - {timing_analysis['reasoning']}")
                else:
                    self.logger.info(f"🏛️ Mayordomo: Good timing for {symbol} - {timing_analysis['reasoning']}")
            
            # Optional: Check position rotation (but don't reject completely)
            if (self.smallcap_mayordomo_enabled and self.smallcap_mayordomo and 
                hasattr(context, 'gap_percentage') and hasattr(context, 'volume_ratio_current')):
                
                new_opportunity = {
                    'symbol': symbol,
                    'catalyst_type': 'TECHNICAL',  
                    'catalyst_strength': 5,
                    'gap_percentage': getattr(context, 'gap_percentage', 0.0),
                    'volume_ratio': context.volume_ratio_current,
                    'current_price': context.current_price
                }
                
                rotation_decision = self.smallcap_mayordomo.evaluate_position_rotation(new_opportunity)
                
                if rotation_decision['action'] == 'ROTATE':
                    self.logger.info(f"🏛️ Mayordomo: Recommends rotation - Close {rotation_decision['close_symbol']} for {symbol}")
                
                # Log market regime for context (but don't use it to block)
                market_regime = self.smallcap_mayordomo.assess_smallcap_market_regime()
                regime_info = market_regime.get('regime', {})
                self.logger.info(f"🏛️ Market regime: {regime_info.get('risk_sentiment', 'NEUTRAL')} - ML will learn from this")
            
            # Return strategies selected by ML - let ML learn from all market conditions
            return ml_selected_strategies
            
        except Exception as e:
            self.logger.error(f"Error in smallcap mayordomo strategy selection: {e}")
            # Fallback to direct smallcap ML
            return await self._smallcap_ml_select_strategies(symbol, context)
    
    async def _original_ml_select_strategies(self, symbol: str, context: TickerContext) -> List[str]:
        """
        Original ML strategy selection (for non-smallcaps or when smallcap ML is disabled)
        """
        # Filter strategies by basic suitability (performance optimization)
        suitable_strategies = await self._filter_suitable_strategies(context)
        
        if len(suitable_strategies) <= self.max_strategies_per_ticker:
            return suitable_strategies
        
        # Use ML to select best strategies
        selected_strategies = []
        
        for _ in range(self.max_strategies_per_ticker):
            if not suitable_strategies:
                break
                
            # ML selection
            best_strategy = self.ml_selector.select_strategy(
                context, suitable_strategies
            )
            
            if best_strategy:
                selected_strategies.append(best_strategy)
                suitable_strategies.remove(best_strategy)  # Avoid duplicates
        
        if selected_strategies:
            self.logger.debug(f"🧠 Original ML selected for {symbol}: {selected_strategies}")
        
        return selected_strategies
    
    async def _filter_suitable_strategies(self, context: TickerContext) -> List[str]:
        """
        Context-aware strategy filtering using Smart Game Plan Manager
        Elimina duplicación y centraliza lógica temporal
        """
        # Preparar datos para el orquestador
        market_data = {
            'market_change_pct': getattr(context, 'market_trend', 0.0),
        }
        
        ticker_context_data = {
            'volume_ratio_current': getattr(context, 'volume_ratio_current', 1.0),
            'volatility_10': getattr(context, 'volatility_10', 0.0),
            'has_catalyst': hasattr(context, 'catalyst_strength') and getattr(context, 'catalyst_strength', 0) > 0,
        }
        
        # SMART GAME PLAN MANAGER: Context-aware strategy selection
        compatible_strategies = []
        rejections = {}
        
        if self.smart_game_plan_manager:
            # Create opportunity data for Smart Game Plan Manager
            opportunity_data = {
                'symbol': context.symbol,
                'current_price': getattr(context, 'current_price', market_data.get('close', 0.0)),
                'volume_ratio': ticker_context_data.get('volume_ratio_current', 1.0),
                'gap_percentage': getattr(context, 'gap_percentage', 0.0),
                'catalyst_type': getattr(context, 'catalyst_type', 'OTHER'),
                'quality_score': getattr(context, 'quality_score', 5.0)
            }
            
            # Get instant decision from Smart Game Plan Manager (use cache to avoid double evaluation)
            try:
                decision = self.smart_game_plan_manager.get_instant_decision(context.symbol, opportunity_data, use_cache=True)
                
                # Log cache status for debugging
                is_cached = decision.get('cached', False)
                cache_info = f" (CACHED)" if is_cached else " (FRESH)"
                
                if decision.get('action') == 'EXECUTE':
                    # Strategy approved by Smart Game Plan Manager - use all available strategies
                    compatible_strategies = list(self.available_strategies)
                    self.logger.info(f"🧠 Smart Game Plan approved {context.symbol}{cache_info}: {decision.get('reason', '')}")
                else:
                    # Strategy rejected or waiting
                    reason = decision.get('reason', 'Unknown')
                    rejections = {s: f"Smart Game Plan: {reason}" for s in self.available_strategies}
                    self.logger.info(f"🧠 Smart Game Plan rejected {context.symbol}{cache_info}: {reason}")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Smart Game Plan Manager error for {context.symbol}: {e}")
                # Fallback to all strategies if Game Plan Manager fails
                compatible_strategies = list(self.available_strategies)
        else:
            # Fallback: No Smart Game Plan Manager available
            self.logger.warning("⚠️ No Smart Game Plan Manager available - using all strategies")
            compatible_strategies = list(self.available_strategies)
        
        # Log detallado para debugging
        if rejections:
            self.logger.debug(f"🧠 Smart Game Plan rejected {len(rejections)} strategies for {context.symbol}")
        elif compatible_strategies:
            self.logger.debug(f"🧠 Smart Game Plan approved {len(compatible_strategies)} strategies for {context.symbol}")
        
        self.logger.info(f"🎭 Orchestrator filtered {context.symbol}: {len(self.available_strategies)} → {len(compatible_strategies)}")
        self.logger.info(f"     Compatible: {compatible_strategies}")
        
        return compatible_strategies
    
    async def _execute_selected_strategies(self, symbol: str, bar: MarketData,
                                          selected_strategies: List[str]) -> List[Signal]:
        """Execute only the ML-selected strategies"""
        candidate_signals = []

        self.logger.info(f"🎯 DEBUG {symbol}: Executing {len(selected_strategies)} selected strategies: {selected_strategies}")

        for strategy_name in selected_strategies:
            try:
                self.logger.debug(f"🎯 DEBUG {symbol}: Loading/executing strategy: {strategy_name}")

                # Load strategy if not cached
                if strategy_name not in self.strategy_instances:
                    strategy_instance = await self._load_strategy_instance(strategy_name)
                    if strategy_instance:
                        # Initialize strategy
                        if self.event_bus:
                            await strategy_instance.initialize(self.event_bus)
                        self.strategy_instances[strategy_name] = strategy_instance
                        # Sync with strategies dict for detection by StrategyAnalysisStage
                        self.strategies[strategy_name] = strategy_instance
                        self.logger.debug(f"🎯 DEBUG {symbol}: Successfully loaded strategy: {strategy_name}")
                    else:
                        self.logger.warning(f"🎯 DEBUG {symbol}: Failed to load strategy: {strategy_name}")
                        continue

                strategy = self.strategy_instances.get(strategy_name)
                if not strategy:
                    self.logger.warning(f"🎯 DEBUG {symbol}: Strategy instance not found: {strategy_name}")
                    continue

                # Update strategy's data
                if hasattr(strategy, 'bars_history'):
                    if isinstance(strategy.bars_history, dict):
                        strategy.bars_history[symbol] = self.bars_history[symbol]
                    elif isinstance(strategy.bars_history, list):
                        strategy.bars_history = self.bars_history[symbol]
                strategy.positions = self.positions  # Share positions

                # Get signal with timeout
                signal = await asyncio.wait_for(
                    strategy.on_bar(bar),
                    timeout=1.0  # 1 second max per strategy
                )

                if signal:
                    # Add metadata
                    if not hasattr(signal, 'metadata'):
                        signal.metadata = {}

                    signal.metadata.update({
                        'strategy_name': strategy_name,
                        'ml_selected': True,
                        'selection_confidence': getattr(signal, 'confidence', 0.5)
                    })

                    candidate_signals.append(signal)

                    self.logger.info(f"📊 DEBUG {symbol}: ✅ {strategy_name} generated signal - {signal.signal_type} @ ${signal.price:.2f} (confidence: {getattr(signal, 'confidence', 0.5):.2f})")
                else:
                    self.logger.info(f"📊 DEBUG {symbol}: ❌ {strategy_name} generated NO signal")

            except asyncio.TimeoutError:
                self.logger.warning(f"⏰ DEBUG {symbol}: Strategy {strategy_name} timed out")
                continue
            except Exception as e:
                self.logger.error(f"❌ DEBUG {symbol}: Error executing {strategy_name}: {e}")
                continue

        self.logger.info(f"🎯 DEBUG {symbol}: Execution complete - {len(candidate_signals)} signals from {len(selected_strategies)} strategies")
        return candidate_signals
    
    async def _ml_select_best_signal(self, signals: List[Signal], 
                                   context: TickerContext) -> Optional[Signal]:
        """ML-powered signal selection (could be enhanced further)"""
        if not signals:
            return None
        
        if len(signals) == 1:
            return signals[0]
        
        # For now, use confidence + ML strategy ranking
        # TODO: Could implement another ML model here for signal selection
        
        # Get strategy rankings from ML model
        strategy_rankings = self.ml_selector.get_strategy_rankings(context)
        strategy_scores = dict(strategy_rankings)
        
        # Score each signal
        scored_signals = []
        for signal in signals:
            strategy_name = signal.metadata.get('strategy_name', '')
            
            # Base score from signal confidence
            base_score = getattr(signal, 'confidence', 0.5)
            
            # ML strategy score
            ml_score = strategy_scores.get(strategy_name, 0.5)
            
            # Combined score
            combined_score = 0.6 * base_score + 0.4 * ml_score
            
            scored_signals.append((signal, combined_score))
        
        # Return best signal
        best_signal, best_score = max(scored_signals, key=lambda x: x[1])
        
        self.logger.debug(f"🏆 Best signal: {best_signal.metadata.get('strategy_name')} "
                         f"with score {best_score:.3f}")
        
    async def _track_signal_for_feedback(self, signal: Signal, context: TickerContext):
        """Track signal for later ML feedback"""
        # Track trade for ML feedback
        trade_id = f"{signal.symbol}_{int(datetime.now().timestamp())}"
        self.active_trades[trade_id] = {
            'symbol': signal.symbol,
            'strategy': signal.metadata.get('strategy_name'),
            'context': context,
            'entry_time': datetime.now(),
            'trade_opened': True,
            'entry_price': signal.price,
            'signal_strength': signal.strength
        }
        
        self.logger.info(f"🧠 ML Tracking: Registered trade {trade_id} for {signal.symbol} using {signal.metadata.get('strategy_name')}")
        self.logger.info(f"🧠 ML Active Trades: {len([t for t in self.active_trades.values() if t['trade_opened']])} open, {len([t for t in self.active_trades.values() if not t['trade_opened']])} closed")
        
        # Clean old trades (keep last 1000)
        if len(self.active_trades) > 1000:
            old_trades = list(self.active_trades.keys())[:-500]
            for trade_id in old_trades:
                del self.active_trades[trade_id]
    
    async def scan_strategy_opportunities(self) -> Dict[str, List[Any]]:
        """
        Scan for opportunities across all strategies using the dispatcher
        
        Returns:
            Dict mapping strategy names to their opportunities
        """
        if not self.scanner_enabled or not self.scanner_dispatcher:
            self.logger.warning("Scanner dispatcher not available - no opportunities found")
            return {}
        
        try:
            self.logger.info("🎯 Scanning for strategy-specific opportunities...")
            all_opportunities = await self.scanner_dispatcher.scan_all_strategies()
            
            # Log results summary
            total_opps = sum(len(opps) for opps in all_opportunities.values())
            self.logger.info(f"📊 Multi-strategy scan results: {total_opps} opportunities across {len(all_opportunities)} strategies")
            
            for strategy, opportunities in all_opportunities.items():
                self.logger.info(f"   {strategy}: {len(opportunities)} opportunities")
            
            return all_opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning strategy opportunities: {e}")
            return {}
    
    async def get_strategy_specific_signals(self, strategy_type: str) -> List[Any]:
        """
        Get opportunities for a specific strategy type
        
        Args:
            strategy_type: Strategy type (orb, vwap_reclaim, daily_plays, etc.)
            
        Returns:
            List of opportunities for that strategy
        """
        if not self.scanner_enabled or not self.scanner_dispatcher:
            return []
        
        try:
            return await self.scanner_dispatcher.scan_specific_strategy(strategy_type)
        except Exception as e:
            self.logger.error(f"Error getting {strategy_type} opportunities: {e}")
            return []
    
    async def _sync_existing_positions(self):
        """Sync existing positions from broker with DB strategy information"""
        self.logger.info(f"🔄 Starting position sync - Broker available: {self.broker is not None}")
        
        if self.broker:
            try:
                # 1) Get actual positions from broker first
                broker_positions = await self.broker.get_positions()
                self.logger.info(f"🔄 Found {len(broker_positions)} live positions from broker")
                
                # 2) Get latest open trades from DB (one per symbol)
                open_trades = self.db_manager.load_latest_open_trades_by_symbol()
                self.logger.info(f"🔍 Found {len(open_trades)} unique open trades in database")
                
                # 3) Create mapping of symbol to most recent strategy
                symbol_to_strategy = {}
                for t in open_trades:
                    symbol = t['symbol']
                    strategy = t.get('strategy', 'unknown')
                    
                    # Only keep if this symbol has a live position
                    if symbol in broker_positions:
                        # Use most recent trade's strategy (trades are sorted by entry_time DESC)
                        if symbol not in symbol_to_strategy:
                            symbol_to_strategy[symbol] = {
                                'strategy': strategy,
                                'trade_id': t.get('trade_id'),
                                'entry_price': t['entry_price'],
                                'entry_time': t['entry_time']
                            }
                
                # 4) Sync positions and active trades for symbols with live positions
                for symbol, position in broker_positions.items():
                    # Update positions
                    self.positions[symbol] = position
                    
                    # Add to active trades with strategy info if available
                    if symbol in symbol_to_strategy:
                        strategy_info = symbol_to_strategy[symbol]
                        trade_data = {
                            'symbol': symbol,
                            'strategy': strategy_info['strategy'],
                            'entry_price': strategy_info['entry_price'],
                            'entry_time': strategy_info['entry_time'],
                            'trade_opened': True
                        }
                        self.active_trades[strategy_info['trade_id']] = trade_data
                        
                        self.logger.info(f"✅ Restored: {symbol} → {strategy_info['strategy']} (ID: {strategy_info['trade_id']})")
                    else:
                        self.logger.warning(f"⚠️ No DB strategy info for live position: {symbol}")
                
                self.logger.info(f"📊 Successfully synced {len(self.positions)} positions with strategy info")
                
            except Exception as e:
                self.logger.error(f"Error syncing positions: {e}")
        else:
            self.logger.warning("⚠️ No broker available during position sync - skipping")
    
    # Event handlers for ML feedback
    @event_handler('position_opened')
    async def _on_position_opened(self, event):
        """Handle position opened events"""
        position = event.data.get('position')
        if position:
            self.positions[position.symbol] = position
    
    @event_handler('position_closed')
    async def _on_position_closed(self, event):
        """Handle position closed events - CRITICAL for ML feedback"""
        position = event.data.get('position')
        if not position:
            return
        
        symbol = position.symbol
        pnl = getattr(position, 'realized_pnl', 0.0)
        
        # Find matching active trade for ML feedback
        matching_trades = [
            (trade_id, trade_data) for trade_id, trade_data in self.active_trades.items()
            if trade_data['symbol'] == symbol and trade_data['trade_opened']
        ]
        
        if matching_trades:
            # Use most recent trade
            trade_id, trade_data = matching_trades[-1]
            
            # Provide ML feedback
            strategy_name = trade_data['strategy']
            context = trade_data['context']
            
            # Normalize PnL to -1 to 1 range for ML
            normalized_reward = np.tanh(pnl / 50.0)  # Tanh scaling
            
            # Update ML model (with context validation)
            if context is not None:
                try:
                    # CRITICAL: Update ML model with trade outcome
                    self.ml_selector.update_model(context, strategy_name, normalized_reward)
                    self.logger.info(f"🧠 ML Learning: Updated model for {strategy_name} with reward {normalized_reward:.3f}")
                    
                    # Update smallcap ML if applicable
                    if context.current_price <= self.smallcap_price_threshold:
                        duration_hours = (datetime.now() - trade_data['entry_time']).total_seconds() / 3600
                        self.update_smallcap_ml_with_trade_result(symbol, strategy_name, pnl, duration_hours)
                    
                    # Log learning statistics
                    if hasattr(self.ml_selector, 'strategy_stats') and strategy_name in self.ml_selector.strategy_stats:
                        stats = self.ml_selector.strategy_stats[strategy_name]
                        self.logger.info(f"🧠 ML Stats for {strategy_name}: {stats.total_trades} trades, {stats.win_rate:.1%} win rate, avg PnL: {stats.avg_pnl:.2f}")
                    
                except Exception as ml_error:
                    self.logger.error(f"❌ ML Learning Error for {symbol}: {ml_error}")
            else:
                self.logger.warning(f"🤖 ML Feedback: No context available for {symbol} - skipping model update")
            
            # Mark trade as closed
            trade_data['trade_opened'] = False
            trade_data['close_pnl'] = pnl
            trade_data['close_time'] = datetime.now()
            
            self.logger.info(f"🤖 ML Feedback: {symbol} closed with PnL ${pnl:.2f} → reward {normalized_reward:.3f} for strategy {strategy_name}")
            
            # Increment save counter and save model periodically
            self.trades_since_save += 1
            self.logger.info(f"🧠 ML Progress: {self.trades_since_save}/{self.model_save_frequency} trades since last model save")
            
            if self.trades_since_save >= self.model_save_frequency:
                await self._save_ml_model()
                self.trades_since_save = 0
        else:
            self.logger.warning(f"⚠️ Position closed for {symbol} but no matching active trade found")
        
        # Clean up position reference and trailing stop tracking
        if symbol in self.positions:
            del self.positions[symbol]
        
        # Clean up trailing stop tracking to prevent memory leaks
        if symbol in self.position_highest_prices:
            del self.position_highest_prices[symbol]
            self.logger.debug(f"🧹 Cleaned up trailing stop tracking for {symbol}")
    
    async def _check_healthy_high_profits(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """
        Check for HEALTHY HIGH PROFITS - Exit at top without waiting for exhaustion
        
        This covers the gap when price is "arriba del todo" but NO FOMO exhaustion detected.
        Different from FOMO exit - this is about taking profits at healthy highs.
        """
        try:
            # Get current time for time-based adjustments
            from zoneinfo import ZoneInfo
            et_time = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
            hour = et_time.hour
            minute = et_time.minute
            
            current_price = bar.close
            entry_price = position.avg_price
            
            # Time-based profit thresholds (more aggressive near close)
            if hour >= 15 and minute >= 30:  # Last 30 minutes
                min_profit_threshold = 0.06  # 6% minimum to consider exit
                healthy_profit_threshold = 0.10  # 10% = healthy high
                great_profit_threshold = 0.15   # 15% = great profit
                self.logger.debug(f"🕐 {symbol}: End-of-day mode - lower profit thresholds")
            elif hour >= 14:  # 2 PM onwards  
                min_profit_threshold = 0.08  # 8% minimum
                healthy_profit_threshold = 0.12  # 12% = healthy high
                great_profit_threshold = 0.18   # 18% = great profit
            else:  # Before 2 PM - be more patient
                min_profit_threshold = 0.10  # 10% minimum
                healthy_profit_threshold = 0.15  # 15% = healthy high
                great_profit_threshold = 0.22   # 22% = great profit
            
            # Only consider if we have minimum profit
            if profit_pct < min_profit_threshold:
                return None
            
            # Check if we're near recent highs (key indicator)
            bars = self.bars_history.get(symbol, [])
            if len(bars) < 20:
                return None
            
            recent_bars = bars[-20:]  # Last 20 bars
            recent_prices = [b.close for b in recent_bars]
            recent_high = max(recent_prices)
            price_from_high = (recent_high - current_price) / recent_high
            
            # We're within 2% of recent high = "arriba del todo"
            near_high = price_from_high <= 0.02
            
            if not near_high:
                return None  # Not at highs, don't exit yet
            
            # Volume analysis - healthy vs exhaustion
            recent_volumes = [b.volume for b in recent_bars[-5:]]
            avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1])
            current_volume = bar.volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Healthy volume (not extreme) suggests good exit point
            healthy_volume = 1.5 <= volume_ratio <= 4.0  # Not too low, not too high
            
            # Price momentum analysis
            price_changes = []
            for i in range(1, min(6, len(recent_bars))):  # Last 5 price changes
                prev_price = recent_bars[-i-1].close
                curr_price = recent_bars[-i].close
                change = (curr_price - prev_price) / prev_price
                price_changes.append(change)
            
            # Momentum is slowing but not crashing (healthy deceleration)
            if len(price_changes) >= 3:
                recent_momentum = sum(price_changes[:3]) / 3  # Last 3 bars average
                momentum_slowing = recent_momentum < 0.01  # Less than 1% average move
            else:
                momentum_slowing = False
            
            # Decision matrix
            exit_reason = None
            strength = 0.7  # Default strength
            
            # GREAT PROFIT + Near highs = Always exit
            if profit_pct >= great_profit_threshold and near_high:
                exit_reason = f"Great profit secured: {profit_pct:.1%} at recent highs"
                strength = 0.95
                
            # HEALTHY PROFIT + Near highs + End of day = Exit
            elif profit_pct >= healthy_profit_threshold and near_high and hour >= 15:
                exit_reason = f"Healthy profit + EOD: {profit_pct:.1%} near close"
                strength = 0.90
                
            # HEALTHY PROFIT + Near highs + Healthy volume + Momentum slowing = Exit  
            elif profit_pct >= healthy_profit_threshold and near_high and healthy_volume and momentum_slowing:
                exit_reason = f"Healthy high exit: {profit_pct:.1%}, good volume, momentum slowing"
                strength = 0.85
                
            # MINIMUM PROFIT + Near highs + Very end of day = Exit
            elif profit_pct >= min_profit_threshold and near_high and hour == 15 and minute >= 45:
                exit_reason = f"Late day profit protection: {profit_pct:.1%} near close"
                strength = 0.80
            
            if exit_reason:
                self.logger.info(f"💰 {symbol}: HEALTHY HIGH EXIT - {exit_reason}")
                self.logger.info(f"   📊 Analysis: Price from high: {price_from_high:.1%}, Volume: {volume_ratio:.1f}x, Time: {hour:02d}:{minute:02d}")
                
                return Signal(
                    signal_id=f"healthy_high_{symbol}_{int(bar.timestamp.timestamp())}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=strength,
                    price=current_price,
                    timestamp=bar.timestamp,
                    strategy_name="ML_MultiStrategy_Engine",
                    metadata={
                        'reason': 'healthy_high_profits',
                        'exit_reason': exit_reason,
                        'entry_price': entry_price,
                        'profit_pct': profit_pct,
                        'price_from_high': price_from_high,
                        'volume_ratio': volume_ratio,
                        'time_hour': hour,
                        'exit_type': 'smart_profit_taking',
                        'strength': strength
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error in healthy high profits check for {symbol}: {e}")
            return None

    async def _cleanup_external_close(self, symbol: str):
        """Complete cleanup when position was closed externally"""
        try:
            # Clean up position reference and trailing stop tracking
            if symbol in self.positions:
                del self.positions[symbol]
                self.logger.info(f"🧹 Cleaned up position tracking for {symbol}")
            
            # Clean up trailing stop tracking
            if symbol in self.position_highest_prices:
                del self.position_highest_prices[symbol]
                self.logger.info(f"🧹 Cleaned up trailing stop tracking for {symbol}")
            
            # Clean up active trades tracking
            trades_to_close = []
            for trade_id, trade_data in self.active_trades.items():
                if trade_data['symbol'] == symbol and trade_data.get('trade_opened', False):
                    trades_to_close.append((trade_id, trade_data))
            
            for trade_id, trade_data in trades_to_close:
                # Mark trade as externally closed
                trade_data['trade_opened'] = False
                trade_data['close_reason'] = 'external_close'
                trade_data['close_time'] = datetime.now()
                self.logger.info(f"🧹 Marked trade {trade_id} as externally closed for {symbol}")
                
        except Exception as e:
            self.logger.error(f"❌ Error during external close cleanup for {symbol}: {e}")

    async def _save_ml_model(self):
        """Save the ML model periodically"""
        try:
            # Save original ML model
            model_path = "data/ml_models/strategy_selector.json"
            self.ml_selector.save_model(model_path)
            self.logger.info(f"💾 ML model saved after {self.model_save_frequency} trades")
            
            # Save smallcap ML model if enabled
            if self.smallcap_ml_enabled and self.smallcap_ml_selector:
                self.save_smallcap_ml_model()
                
        except Exception as e:
            self.logger.error(f"Error saving ML model: {e}")
    
    # Properties and utility methods
    @property
    def name(self) -> str:
        return self._name
    
    @property 
    def parameters(self) -> Dict[str, Any]:
        return self._parameters
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size (delegated to individual strategies or use global logic)"""
        try:
            # Get strategy that generated the signal
            strategy_name = signal.metadata.get('strategy_name') if hasattr(signal, 'metadata') else None
            
            if strategy_name and strategy_name in self.strategy_instances:
                # Use strategy-specific position sizing
                strategy = self.strategy_instances[strategy_name]
                if hasattr(strategy, 'calculate_position_size'):
                    return strategy.calculate_position_size(signal, capital, risk_per_trade)
            
            # Fallback: global position sizing logic
            max_position_value = 200.0  # From global config
            min_position_value = 50.0
            min_quantity = 10
            
            price = float(signal.price)
            if price <= 0:
                return 0
            
            # Calculate target value
            target_value = min(max_position_value, capital * 0.1)
            target_value = max(target_value, min_position_value)
            
            # Calculate quantity
            quantity = int(target_value / price)
            quantity = max(quantity, min_quantity)
            
            # Verify capital constraints
            position_value = quantity * price
            commission = max(quantity * 0.005, 1.0)
            total_cost = position_value + commission
            
            if total_cost > capital:
                available_for_position = capital - commission
                if available_for_position > 0:
                    quantity = max(int(available_for_position / price), 1)
                else:
                    return 0
            
            return max(quantity, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0
    
    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates"""
        self.positions[symbol] = position
        self.logger.info(f"🔄 ML Engine: Position updated for {symbol}: {position.quantity} shares @ ${position.avg_price:.2f}")
        
        # NUEVO: Register with CentralizedStopLossManager for EMA trailing stops
        if position.quantity > 0:  # Only for long positions
            try:
                # Check if position is already registered
                if symbol not in self.stop_manager.active_positions:
                    stop_params = create_stop_params_from_config(self._parameters)
                    self.stop_manager.register_position(
                        symbol=symbol,
                        entry_price=position.avg_price,
                        entry_time=datetime.now(timezone.utc),  # Position update time
                        side='bullish',
                        strategy_name=self._name,
                        stop_params=stop_params
                    )
                    self.logger.info(f"🔄 Registered {symbol} with CentralizedStopLossManager (EMA trailing enabled)")
            except Exception as e:
                self.logger.error(f"Error registering {symbol} with stop manager: {e}")
        
        # Update SmallcapMayordomo if enabled and this is a smallcap
        if (self.smallcap_mayordomo_enabled and self.smallcap_mayordomo and 
            hasattr(position, 'avg_price') and position.avg_price <= self.smallcap_price_threshold):
            
            try:
                # Register daily play if this is a new position
                if position.quantity > 0 and symbol not in self.smallcap_mayordomo.active_daily_plays:
                    catalyst_type = getattr(position, 'catalyst_type', 'TECHNICAL')
                    gap_percentage = getattr(position, 'gap_percentage', 0.0)
                    volume_ratio = getattr(position, 'volume_ratio', 1.0)
                    
                    success = self.smallcap_mayordomo.register_daily_play(
                        symbol=symbol,
                        catalyst_type=catalyst_type,
                        catalyst_strength=5,  # Default strength
                        gap_percentage=gap_percentage,
                        volume_ratio=volume_ratio,
                        entry_price=position.avg_price
                    )
                    
                    if success:
                        self.logger.info(f"🏛️ Mayordomo: Registered daily play for {symbol}")
                        
            except Exception as e:
                self.logger.error(f"Error updating mayordomo with position: {e}")
        
        # Debug: List all tracked positions
        self.logger.info(f"   All tracked positions: {list(self.positions.keys())}")
    
    async def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Check exit conditions - PRIORITY ORDER: EOD -> CentralizedStopLoss (EMA trailing) -> ML analysis
        """
        try:
            if symbol not in self.positions:
                return None
            
            position = self.positions[symbol]
            
            # PRIORITY 1: End of Day Exit - ALWAYS checked first, unconditional
            eod_exit_signal = await self._check_eod_exit(symbol, bar, position)
            if eod_exit_signal:
                return eod_exit_signal
            
            # PRIORITY 2: CentralizedStopLossManager (EMA trailing, stops, profit targets)
            stop_exit = self.stop_manager.check_exit_conditions(symbol, bar)
            if stop_exit:
                self.logger.info(f"🚨 CentralizedStopLoss exit for {symbol}: {stop_exit.metadata.get('exit_reason', 'Stop triggered')}")
                # Convert to Signal format
                exit_signal = Signal(
                    signal_id=f"stop_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=0.95,  # High confidence for stop losses
                    price=stop_exit.price,
                    timestamp=bar.timestamp,
                    strategy_name='centralized_stop_loss',
                    metadata=stop_exit.metadata
                )
                return exit_signal
            
            # PRIORITY 3: Use ML Exit Engine if available (fallback)
            if self.ml_exit_engine is not None:
                self.logger.debug(f"🧠 {symbol}: Using ML Exit Engine for intelligent exit analysis")
                
                # Get bars history for ML analysis
                bars_history = self.bars_history.get(symbol, [])
                if len(bars_history) < 3:  # AJUSTADO: Reducido de 10 a 3 para permitir decisiones más ágiles
                    self.logger.debug(f"🔄 {symbol}: Insufficient history for ML exit ({len(bars_history)} < 3), using fallback logic")
                    return await self._fallback_exit_logic(symbol, bar, position)
                
                # Get ML exit decision
                ml_decision = self.ml_exit_engine.should_exit(position, bar, bars_history)
                
                if ml_decision.get('should_exit', False):
                    # Create exit signal from ML decision
                    exit_signal = Signal(
                        signal_id=f"ml_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=ml_decision.get('confidence', 0.8),
                        price=bar.close,
                        timestamp=bar.timestamp,
                        strategy_name='ml_exit_engine',
                        metadata={
                            'reason': ml_decision.get('exit_type', 'ML_EXIT'),
                            'expected_value': ml_decision.get('expected_value', 0.0),
                            'ml_confidence': ml_decision.get('confidence', 0.8),
                            'optimal_hold_minutes': ml_decision.get('optimal_hold_minutes', 0),
                            'exit_reasons': ml_decision.get('reasons', [])
                        }
                    )
                    
                    self.logger.info(f"🎯 ML EXIT: {symbol} | Type: {ml_decision.get('exit_type')} | Confidence: {ml_decision.get('confidence', 0):.2f}")
                    return exit_signal
                else:
                    self.logger.debug(f"🔍 {symbol}: ML Exit Engine recommends holding position")
                    return None
            
            # Fallback to comprehensive exit logic if ML Exit Engine not available
            else:
                self.logger.debug(f"🔄 {symbol}: ML Exit Engine not available, using comprehensive exit logic")
                return await self._comprehensive_exit_logic(symbol, bar, position)
            
        except Exception as e:
            self.logger.error(f"❌ Error checking exit conditions for {symbol}: {e}")
            return await self._fallback_exit_logic(symbol, bar, position)
    
    async def _check_eod_exit(self, symbol: str, bar: MarketData, position: Position) -> Optional[Signal]:
        """
        Check End of Day exit conditions - UNCONDITIONAL at 15:55 ET
        """
        try:
            # EOD exit is ALWAYS enabled for risk management
            eod_exit_enabled = self.config.getboolean('GLOBAL', 'end_of_day_exit', fallback=True)
            
            if not eod_exit_enabled:
                return None
                
            # Get current time in US/Eastern timezone
            try:
                from zoneinfo import ZoneInfo
                ny_tz = ZoneInfo('US/Eastern')
                current_time_et = bar.timestamp.astimezone(ny_tz) if bar.timestamp.tzinfo else bar.timestamp.replace(tzinfo=ny_tz)
            except ImportError:
                import pytz
                ny_tz = pytz.timezone('US/Eastern')
                current_time_et = bar.timestamp.astimezone(ny_tz) if bar.timestamp.tzinfo else ny_tz.localize(bar.timestamp)
            
            hour = current_time_et.hour
            minute = current_time_et.minute
            
            # Close positions at 15:55 ET (5 minutes before market close)
            if (hour == 15 and minute >= 55) or hour >= 16:
                self.logger.info(f"🕐 EOD Exit triggered for {symbol} at {hour:02d}:{minute:02d} ET")
                self.logger.info(f"🚪 ML Engine: Exit signal for {symbol} - end_of_day_exit")
                
                return Signal(
                    signal_id=f"eod_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,  # Maximum strength for EOD exits
                    price=bar.close,
                    timestamp=bar.timestamp,
                    strategy_name=self._name,
                    metadata={
                        'reason': 'end_of_day_exit',
                        'entry_price': position.avg_price,
                        'exit_time': f'{hour:02d}:{minute:02d}_ET',
                        'exit_type': 'automatic_eod',
                        'strategy_name': self._name
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in EOD exit check for {symbol}: {e}")
            return None
    
    async def _fallback_exit_logic(self, symbol: str, bar: MarketData, position: Position) -> Optional[Signal]:
        """
        Fallback exit logic when strategy-specific exit logic is not available
        Enhanced with SmallcapMayordomo momentum tracking
        """
        try:
            current_price = bar.close
            entry_price = position.avg_price
            
            if position.quantity <= 0:  # Not a long position
                return None
            
            # Check SmallcapMayordomo momentum analysis for smallcaps
            is_smallcap = entry_price <= self.smallcap_price_threshold
            if (is_smallcap and self.smallcap_mayordomo_enabled and 
                self.smallcap_mayordomo and symbol in self.smallcap_mayordomo.active_daily_plays):
                
                try:
                    # Update momentum and get recommendation
                    volume_ratio = getattr(bar, 'volume_ratio', 1.0)  # Would need to calculate actual volume ratio
                    momentum_recommendation = self.smallcap_mayordomo.update_daily_play_momentum(
                        symbol, current_price, volume_ratio
                    )
                    
                    # If mayordomo recommends exit, prioritize it
                    if (momentum_recommendation.get('action') == 'EXIT' and 
                        momentum_recommendation.get('urgency') == 'HIGH'):
                        
                        self.logger.info(f"🏛️ Mayordomo urgent exit for {symbol}: {momentum_recommendation['reason']}")
                        
                        # Unregister from mayordomo tracking
                        if symbol in self.smallcap_mayordomo.active_daily_plays:
                            del self.smallcap_mayordomo.active_daily_plays[symbol]
                        
                        return Signal(
                            signal_id=f"MAYORDOMO_EXIT_{symbol}_{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=momentum_recommendation.get('confidence', 0.8),
                            price=current_price,
                            timestamp=bar.timestamp,
                            metadata={
                                'reason': f"Mayordomo momentum exit: {momentum_recommendation['reason']}",
                                'strategy_name': 'SmallcapMayordomo',
                                'urgency': momentum_recommendation.get('urgency', 'HIGH'),
                                'momentum_strength': momentum_recommendation.get('momentum_strength', 0.0)
                            }
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error getting mayordomo momentum analysis for {symbol}: {e}")
            
            # NOTE: EOD exit logic moved to _check_eod_exit() for priority handling
            # This fallback no longer handles EOD exits to avoid duplication
            
            # Basic stop loss (5% - more aggressive to preserve capital)
            loss_pct = (entry_price - current_price) / entry_price
            if loss_pct >= 0.05:
                # Verify position still exists before returning signal
                if await self._verify_position_exists(symbol):
                    return Signal(
                        signal_id=f"fallback_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_price,
                        timestamp=bar.timestamp,
                        strategy_name="ML_MultiStrategy_Engine",
                        metadata={
                            'reason': 'fallback_stop_loss',
                            'entry_price': entry_price,
                            'loss_pct': loss_pct,
                            'exit_type': 'emergency_fallback'
                        }
                    )
                else:
                    self.logger.warning(f"⚠️ {symbol}: Stop loss triggered but position no longer exists - cleaning up")
                    # Complete cleanup of internal tracking
                    await self._cleanup_external_close(symbol)
                    return None
            
            # Update highest price for trailing stop
            if symbol not in self.position_highest_prices:
                self.position_highest_prices[symbol] = current_price
                self.logger.info(f"🎯 {symbol}: Initialized trailing stop tracking at ${current_price:.2f}")
            else:
                old_highest = self.position_highest_prices[symbol]
                self.position_highest_prices[symbol] = max(self.position_highest_prices[symbol], current_price)
                if self.position_highest_prices[symbol] > old_highest:
                    self.logger.info(f"🎯 {symbol}: New highest price ${self.position_highest_prices[symbol]:.2f} (was ${old_highest:.2f})")
            
            highest_price = self.position_highest_prices[symbol]
            profit_pct = (current_price - entry_price) / entry_price
            
            # Trailing stop logic (more aggressive activation)
            trailing_activation = self.config.getfloat('GLOBAL', 'default_trailing_activation', fallback=0.03)  # 3% (was 6%)
            trailing_distance = self.config.getfloat('GLOBAL', 'default_trailing_stop_pct', fallback=0.06)     # 6% (was 8%)
            
            # DEBUG: Log trailing stop analysis for positions with some profit
            if profit_pct > 0.01:  # Log if profit > 1%
                self.logger.info(f"🎯 {symbol}: Profit {profit_pct:.1%} | Entry: ${entry_price:.2f} | Current: ${current_price:.2f} | Highest: ${highest_price:.2f}")
                self.logger.info(f"🎯 {symbol}: Trailing activation at {trailing_activation:.1%} | Distance: {trailing_distance:.1%}")
            
            # PRIORITY 0: Check for FOMO/Momentum Exhaustion (most important)
            fomo_exit = await self._check_fomo_exhaustion(symbol, bar, position, profit_pct)
            if fomo_exit:
                # Verify position still exists before returning signal
                if await self._verify_position_exists(symbol):
                    return fomo_exit
                else:
                    self.logger.warning(f"⚠️ {symbol}: FOMO exit detected but position no longer exists - cleaning up")
                    # Complete cleanup of internal tracking
                    await self._cleanup_external_close(symbol)
                    return None
            
            # PRIORITY 0.5: Check for HEALTHY HIGH PROFITS (new addition)
            # Exit when profit is significant but no FOMO exhaustion detected
            healthy_high_exit = await self._check_healthy_high_profits(symbol, bar, position, profit_pct)
            if healthy_high_exit:
                # Verify position still exists before returning signal
                if await self._verify_position_exists(symbol):
                    return healthy_high_exit
                else:
                    self.logger.warning(f"⚠️ {symbol}: Healthy high exit detected but position no longer exists - cleaning up")
                    await self._cleanup_external_close(symbol)
                    return None
            
            # PRIORITY 1: Check trailing stop (if activated)
            if profit_pct >= trailing_activation:
                trailing_stop_price = highest_price * (1 - trailing_distance)
                
                # Log trailing stop analysis
                self.logger.info(f"🎯 {symbol}: Trailing stop active - Stop price: ${trailing_stop_price:.2f} | Current: ${current_price:.2f}")
                
                if current_price <= trailing_stop_price:
                    self.logger.info(f"🎯 Trailing stop triggered for {symbol}: price ${current_price:.2f} <= stop ${trailing_stop_price:.2f} (highest: ${highest_price:.2f})")
                    
                    # Verify position still exists before returning signal
                    if await self._verify_position_exists(symbol):
                        return Signal(
                            signal_id=f"trailing_stop_{symbol}_{int(bar.timestamp.timestamp())}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=1.0,
                            price=current_price,
                            timestamp=bar.timestamp,
                            strategy_name="trailing_stop",
                            metadata={
                                'reason': 'trailing_stop',
                                'entry_price': entry_price,
                                'highest_price': highest_price,
                                'trailing_stop_price': trailing_stop_price,
                                'profit_pct': profit_pct,
                                'trailing_distance': trailing_distance,
                                'exit_type': 'fallback_trailing_stop',
                                'strategy_name': 'trailing_stop'
                            }
                        )
                    else:
                        self.logger.warning(f"⚠️ {symbol}: Trailing stop triggered but position no longer exists - cleaning up")
                        # Complete cleanup of internal tracking
                        await self._cleanup_external_close(symbol)
                        return None
                else:
                    # Trailing stop is active but not triggered - don't use take profit
                    self.logger.debug(f"🎯 {symbol}: Trailing stop active but not triggered (${current_price:.2f} > ${trailing_stop_price:.2f})")
                    return None
            
            # PRIORITY 2: Dynamic take profit (before trailing stop activation)
            # Only if trailing stop is not yet activated
            if profit_pct < trailing_activation:
                # Dynamic take profit based on position performance and time
                # Try to get entry time from active trades or estimate from position data
                entry_time = None
                for trade_id, trade_data in self.active_trades.items():
                    if trade_data.get('symbol') == symbol and trade_data.get('trade_opened'):
                        # Try to get entry timestamp from trade data
                        entry_time = trade_data.get('entry_timestamp', bar.timestamp.timestamp())
                        break
                
                if not entry_time:
                    # Fallback: assume position opened recently (conservative estimate)
                    entry_time = bar.timestamp.timestamp() - 3600  # 1 hour ago
                
                time_in_position_hours = (bar.timestamp.timestamp() - entry_time) / 3600
                
                # Aggressive take profit for quick moves
                if profit_pct >= 0.08 and time_in_position_hours < 0.5:  # 8% profit in < 30min
                    self.logger.info(f"💰 Quick profit taking for {symbol}: {profit_pct:.1%} in {time_in_position_hours:.1f}h")
                    # Verify position still exists before returning signal
                    if await self._verify_position_exists(symbol):
                        return Signal(
                            signal_id=f"quick_profit_{symbol}_{int(bar.timestamp.timestamp())}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=1.0,
                            price=current_price,
                            timestamp=bar.timestamp,
                            strategy_name="ML_MultiStrategy_Engine",
                            metadata={
                                'reason': 'quick_profit_take',
                                'entry_price': entry_price,
                                'profit_pct': profit_pct,
                                'time_hours': time_in_position_hours,
                                'exit_type': 'dynamic_profit'
                            }
                        )
                    else:
                        self.logger.warning(f"⚠️ {symbol}: Quick profit signal but position no longer exists - cleaning up")
                        await self._cleanup_external_close(symbol)
                        return None
                
                # Standard take profit for slower moves
                elif profit_pct >= 0.12:  # 12% profit - reasonable target
                    self.logger.info(f"💰 Standard profit taking for {symbol}: {profit_pct:.1%}")
                    # Verify position still exists before returning signal
                    if await self._verify_position_exists(symbol):
                        return Signal(
                            signal_id=f"profit_take_{symbol}_{int(bar.timestamp.timestamp())}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=1.0,
                            price=current_price,
                            timestamp=bar.timestamp,
                            strategy_name="ML_MultiStrategy_Engine",
                            metadata={
                                'reason': 'profit_target_reached',
                                'entry_price': entry_price,
                                'profit_pct': profit_pct,
                                'exit_type': 'profit_take'
                            }
                        )
                    else:
                        self.logger.warning(f"⚠️ {symbol}: Profit target signal but position no longer exists - cleaning up")
                        await self._cleanup_external_close(symbol)
                        return None
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error in fallback exit logic for {symbol}: {e}")
            return None
    
    async def _comprehensive_exit_logic(self, symbol: str, bar: MarketData, position: Position) -> Optional[Signal]:
        """
        COMPREHENSIVE exit logic that combines ALL exit systems:
        FIXED: Evaluates ALL conditions, then selects by priority (0 = highest priority)
        
        1. FOMO Detection (Priority 0)
        2. Healthy High Profits (Priority 0.5) 
        3. Trailing Stop Loss (Priority 1)
        4. Take Profit (Priority 2)
        5. Stop Loss (Priority 3)
        """
        try:
            current_price = bar.close
            entry_price = position.avg_price
            profit_pct = (current_price - entry_price) / entry_price
            
            if position.quantity <= 0:
                return None
                
            self.logger.info(f"🎯 {symbol}: Comprehensive Exit Check - Profit {profit_pct:.1%} | Entry: ${entry_price:.2f} | Current: ${current_price:.2f}")
            
            # STEP 1: EVALUATE ALL EXIT CONDITIONS IN PARALLEL
            exit_signals = []
            
            # Priority 0: FOMO Exit Detection
            try:
                fomo_exit = await self._check_fomo_detector(symbol, bar, position, profit_pct)
                if fomo_exit:
                    exit_signals.append((0, "FOMO Exhaustion", fomo_exit))
                    self.logger.info(f"🚨 {symbol}: FOMO exit condition MET")
                else:
                    self.logger.debug(f"🔍 {symbol}: FOMO exit condition - No exhaustion detected")
            except Exception as e:
                self.logger.error(f"Error checking FOMO for {symbol}: {e}")
            
            # Priority 0.5: Healthy High Profits
            try:
                healthy_exit = await self._check_healthy_high_profits(symbol, bar, position, profit_pct)
                if healthy_exit:
                    exit_signals.append((0.5, "Healthy High Profits", healthy_exit))
                    self.logger.info(f"💎 {symbol}: Healthy High exit condition MET - {healthy_exit.metadata.get('exit_reason', '')}")
                else:
                    self.logger.debug(f"🔍 {symbol}: Healthy High exit condition - Not at profitable highs")
            except Exception as e:
                self.logger.error(f"Error checking Healthy High for {symbol}: {e}")
            
            # Priority 1: Trailing Stop Loss
            try:
                trailing_exit = await self._check_trailing_stop_loss(symbol, bar, position, profit_pct)
                if trailing_exit:
                    exit_signals.append((1, "Trailing Stop", trailing_exit))
                    self.logger.info(f"📉 {symbol}: Trailing Stop exit condition MET")
                else:
                    self.logger.debug(f"🔍 {symbol}: Trailing Stop exit condition - Not triggered")
            except Exception as e:
                self.logger.error(f"Error checking Trailing Stop for {symbol}: {e}")
                
            # Priority 2: Take Profit
            try:
                take_profit_exit = await self._check_take_profit(symbol, bar, position, profit_pct)
                if take_profit_exit:
                    exit_signals.append((2, "Take Profit", take_profit_exit))
                    self.logger.info(f"💰 {symbol}: Take Profit exit condition MET")
                else:
                    self.logger.debug(f"🔍 {symbol}: Take Profit exit condition - Target not reached")
            except Exception as e:
                self.logger.error(f"Error checking Take Profit for {symbol}: {e}")
                
            # Priority 3: Stop Loss
            try:
                stop_loss_exit = await self._check_stop_loss(symbol, bar, position, profit_pct)
                if stop_loss_exit:
                    exit_signals.append((3, "Stop Loss", stop_loss_exit))
                    self.logger.info(f"🛑 {symbol}: Stop Loss exit condition MET")
                else:
                    self.logger.debug(f"🔍 {symbol}: Stop Loss exit condition - Not triggered")
            except Exception as e:
                self.logger.error(f"Error checking Stop Loss for {symbol}: {e}")
            
            # STEP 2: SELECT HIGHEST PRIORITY EXIT (LOWEST NUMBER = HIGHEST PRIORITY)
            if exit_signals:
                # Sort by priority (lower number = higher priority)
                exit_signals.sort(key=lambda x: x[0])
                priority, reason, signal = exit_signals[0]
                
                # Log all available exits for transparency
                all_reasons = [f"{reason} (P{priority})" for priority, reason, _ in exit_signals]
                self.logger.info(f"🎯 {symbol}: Multiple exits available: {', '.join(all_reasons)}")
                self.logger.info(f"🚪 {symbol}: Selected HIGHEST PRIORITY exit: {reason} (Priority {priority})")
                
                return signal
            
            # No exit conditions met
            self.logger.debug(f"✅ {symbol}: No exit conditions met - holding position")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error in comprehensive exit logic for {symbol}: {e}")
            return None
    
    async def _check_fomo_detector(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """Check FOMO detector for exit signal"""
        try:
            # Use existing FOMO detector
            from core.fomo_detector import fomo_detector
            
            # Check if FOMO exhaustion detected
            fomo_decision = fomo_detector.check_fomo_exhaustion(
                symbol=symbol,
                current_price=bar.close,
                volume=bar.volume,
                timestamp=bar.timestamp
            )
            
            if fomo_decision.should_exit:
                self.logger.info(f"🚨 {symbol}: FOMO Exit triggered - {fomo_decision.reasoning}")
                return self._create_exit_signal(
                    symbol=symbol,
                    reason="FOMO Exhaustion",
                    details=fomo_decision.reasoning,
                    priority=0,
                    strength=0.95,
                    price=bar.close
                )
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking FOMO detector for {symbol}: {e}")
            return None
    
    async def _check_trailing_stop_loss(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """Check trailing stop loss conditions"""
        try:
            current_price = bar.close
            entry_price = position.avg_price
            
            # Update highest price seen
            if symbol not in self.position_highest_prices:
                self.position_highest_prices[symbol] = current_price
            else:
                self.position_highest_prices[symbol] = max(self.position_highest_prices[symbol], current_price)
            
            highest_price = self.position_highest_prices[symbol]
            
            # Get trailing parameters
            activation_threshold = self._parameters.get('default_trailing_activation', 0.03)  # 3%
            trailing_pct = self._parameters.get('default_trailing_stop_pct', 0.06)  # 6%
            
            # Check if trailing should be active
            if profit_pct >= activation_threshold:
                stop_price = highest_price * (1 - trailing_pct)
                
                self.logger.info(f"🎯 {symbol}: Trailing activation at {activation_threshold:.1%} | Distance: {trailing_pct:.1%}")
                self.logger.info(f"🎯 {symbol}: Trailing stop active - Stop price: ${stop_price:.2f} | Current: ${current_price:.2f}")
                
                if current_price <= stop_price:
                    self.logger.info(f"🚪 {symbol}: Trailing stop triggered at ${current_price:.2f} (stop: ${stop_price:.2f})")
                    return self._create_exit_signal(
                        symbol=symbol,
                        reason="Trailing Stop Loss",
                        details=f"Price ${current_price:.2f} hit trailing stop ${stop_price:.2f}",
                        priority=1,
                        strength=0.9,
                        price=current_price
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking trailing stop for {symbol}: {e}")
            return None
    
    async def _check_take_profit(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """Check take profit conditions"""
        try:
            take_profit_threshold = self._parameters.get('fallback_take_profit_pct', 0.12)  # 12%
            
            if profit_pct >= take_profit_threshold:
                self.logger.info(f"💰 {symbol}: Take profit triggered at {profit_pct:.1%} (target: {take_profit_threshold:.1%})")
                return self._create_exit_signal(
                    symbol=symbol,
                    reason="Take Profit",
                    details=f"Profit {profit_pct:.1%} reached target {take_profit_threshold:.1%}",
                    priority=2,
                    strength=0.8,
                    price=bar.close
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking take profit for {symbol}: {e}")
            return None
    
    async def _check_stop_loss(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """Check stop loss conditions"""
        try:
            stop_loss_threshold = -abs(self._parameters.get('fallback_stop_loss_pct', 0.05))  # -5%
            
            if profit_pct <= stop_loss_threshold:
                self.logger.info(f"🛑 {symbol}: Stop loss triggered at {profit_pct:.1%} (limit: {stop_loss_threshold:.1%})")
                return self._create_exit_signal(
                    symbol=symbol,
                    reason="Stop Loss",
                    details=f"Loss {profit_pct:.1%} hit stop limit {stop_loss_threshold:.1%}",
                    priority=3,
                    strength=1.0,
                    price=bar.close
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking stop loss for {symbol}: {e}")
            return None
    
    def _create_exit_signal(self, symbol: str, reason: str, details: str, priority: int, strength: float, price: float) -> Signal:
        """Create standardized exit signal"""
        return Signal(
            symbol=symbol,
            signal_type=SignalType.SELL,
            strength=strength,
            metadata={
                'exit_reason': reason,
                'details': details,
                'priority': priority,
                'exit_price': price,
                'timestamp': datetime.now(),
                'source': 'ML_Exit_Engine'
            }
        )
    
    async def _check_fomo_exhaustion(self, symbol: str, bar: MarketData, position: Position, profit_pct: float) -> Optional[Signal]:
        """
        Advanced FOMO/Momentum Exhaustion Detection for Early Exits
        
        Detects:
        1. Volume Spike + Price Stall (FOMO exhaustion)
        2. RSI Divergence (momentum weakening)
        3. Velocity Decay (acceleration slowing)
        4. Parabolic Exhaustion (unsustainable moves)
        """
        try:
            # Need at least 2% profit to consider FOMO exit (lowered from 3%)
            if profit_pct < 0.02:
                return None
            
            bars = self.bars_history.get(symbol, [])
            if len(bars) < 10:  # Need enough history
                return None
            
            current_price = bar.close
            entry_price = position.avg_price
            current_volume = bar.volume
            
            # TIME-BASED SCALING: Adjust thresholds based on market time
            # Get current time in ET for time-based scaling
            try:
                from zoneinfo import ZoneInfo
                et_time = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
                hour = et_time.hour
                minute = et_time.minute
                
                # Time periods:
                # 9:30-14:00: Conservative (maximize profits)
                # 14:00-15:00: Intermediate (balance) 
                # 15:00-15:55: Aggressive (protect profits)
                
                if hour < 14:  # Morning/Midday (9:30-14:00)
                    time_period = "conservative"
                    volume_multiplier = 2.0      # Current setting
                    price_stall_pct = 0.015      # Current setting  
                    min_profit_volume = 0.03     # Current setting
                    min_profit_velocity = 0.05   # Current setting
                elif hour < 15:  # Afternoon (14:00-15:00)
                    time_period = "intermediate"
                    volume_multiplier = 1.8      # More sensitive
                    price_stall_pct = 0.02       # More relaxed
                    min_profit_volume = 0.025    # Lower threshold
                    min_profit_velocity = 0.04   # Lower threshold
                else:  # Late day (15:00-15:55)
                    time_period = "aggressive"
                    volume_multiplier = 1.5      # Very sensitive
                    price_stall_pct = 0.025      # Very relaxed
                    min_profit_volume = 0.02     # Very low threshold
                    min_profit_velocity = 0.03   # Very low threshold
                
                # Log time-based adjustment occasionally
                if minute % 10 == 0:  # Every 10 minutes
                    self.logger.info(f"🕐 {symbol} Time-based FOMO scaling: {time_period} mode at {hour:02d}:{minute:02d} ET")
                    self.logger.debug(f"   Volume threshold: {volume_multiplier:.1f}x, Price stall: {price_stall_pct:.1%}, Min profit: {min_profit_volume:.1%}")
                    
            except Exception as e:
                # Fallback to conservative settings if timezone fails
                self.logger.warning(f"Timezone conversion failed for {symbol}: {e}")
                time_period = "conservative"
                volume_multiplier = 2.0
                price_stall_pct = 0.015
                min_profit_volume = 0.03
                min_profit_velocity = 0.05
            
            # Get recent bars for analysis
            recent_bars = bars[-10:]  # Last 10 bars
            recent_prices = [b.close for b in recent_bars]
            recent_volumes = [b.volume for b in recent_bars]
            
            # 1. VOLUME SPIKE + PRICE STALL DETECTION (using time-based thresholds)
            avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1])
            volume_spike = current_volume > (avg_volume * volume_multiplier)  # Dynamic based on time
            
            # Price stall: current price within time-based threshold of recent high
            recent_high = max(recent_prices[-3:])  # High of last 3 bars
            price_stall = abs(current_price - recent_high) / recent_high < price_stall_pct
            
            if volume_spike and price_stall and profit_pct > min_profit_volume:
                self.logger.info(f"🚨 {symbol}: FOMO EXHAUSTION detected - Volume spike + price stall (profit: {profit_pct:.1%}) [Mode: {time_period}]")
                return Signal(
                    signal_id=f"fomo_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=0.9,
                    price=current_price,
                    timestamp=bar.timestamp,
                    strategy_name="ML_MultiStrategy_Engine",
                    metadata={
                        'reason': 'fomo_exhaustion',
                        'entry_price': entry_price,
                        'profit_pct': profit_pct,
                        'volume_spike': volume_spike,
                        'price_stall': price_stall,
                        'exit_type': 'smart_fomo_exit',
                        'time_period': time_period,
                        'volume_threshold': volume_multiplier,
                        'profit_threshold': min_profit_volume,
                        'exit_strategy': 'fomo_exhaustion'
                    }
                )       
            # 2. VELOCITY DECAY DETECTION
            if len(recent_prices) >= 5:
                # Calculate price velocity (rate of change)
                velocity_1 = (recent_prices[-1] - recent_prices[-2]) / recent_prices[-2]
                velocity_2 = (recent_prices[-2] - recent_prices[-3]) / recent_prices[-3]
                velocity_3 = (recent_prices[-3] - recent_prices[-4]) / recent_prices[-4]
                
                # Velocity decay: each bar moving slower than previous
                velocity_decay = (velocity_1 < velocity_2 < velocity_3) and velocity_3 > 0.02
                
                if velocity_decay and profit_pct > min_profit_velocity:  # Dynamic threshold based on time
                    self.logger.info(f"🚨 {symbol}: VELOCITY DECAY detected - Momentum slowing (profit: {profit_pct:.1%}) [Mode: {time_period}]")
                    return Signal(
                        signal_id=f"velocity_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                        symbol=symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=0.8,
                        price=current_price,
                        timestamp=bar.timestamp,
                        strategy_name="ML_MultiStrategy_Engine",
                        metadata={
                            'reason': 'velocity_decay',
                            'entry_price': entry_price,
                            'profit_pct': profit_pct,
                            'velocity_1': velocity_1,
                            'velocity_2': velocity_2,
                            'exit_strategy': 'velocity_decay',
                            'velocity_3': velocity_3,
                            'exit_type': 'smart_momentum_exit',
                            'time_period': time_period,
                            'profit_threshold': min_profit_velocity
                        }
                    )
            
            # 3. PARABOLIC EXHAUSTION (very high profits with slowing momentum)
            if profit_pct > 0.20:  # 20%+ profit
                # Check if recent moves are getting smaller
                recent_moves = []
                for i in range(len(recent_prices)-1):
                    move = abs(recent_prices[i+1] - recent_prices[i]) / recent_prices[i]
                    recent_moves.append(move)
                
                if len(recent_moves) >= 3:
                    avg_recent_move = sum(recent_moves[-3:]) / 3
                    avg_earlier_move = sum(recent_moves[-6:-3]) / 3 if len(recent_moves) >= 6 else avg_recent_move
                    
                    # Parabolic exhaustion: moves getting smaller despite high profit
                    if avg_recent_move < (avg_earlier_move * 0.6):  # 40% slower moves
                        self.logger.info(f"🚨 {symbol}: PARABOLIC EXHAUSTION detected - High profit but slowing moves (profit: {profit_pct:.1%})")
                        return Signal(
                            signal_id=f"parabolic_exit_{symbol}_{int(bar.timestamp.timestamp())}",
                            symbol=symbol,
                            signal_type=SignalType.EXIT_LONG,
                            strength=0.95,
                            price=current_price,
                            timestamp=bar.timestamp,
                            strategy_name="ML_MultiStrategy_Engine",
                            metadata={
                                'reason': 'parabolic_exhaustion',
                                'entry_price': entry_price,
                                'profit_pct': profit_pct,
                                'avg_recent_move': avg_recent_move,
                                'avg_earlier_move': avg_earlier_move,
                                'exit_type': 'smart_parabolic_exit'
                            }
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error in FOMO exhaustion check for {symbol}: {e}")
            return None
    
    async def _verify_position_exists(self, symbol: str) -> bool:
        """
        Verify that a position actually exists in the broker/execution system
        before generating exit signals to prevent synchronization issues
        """
        try:
            # Check if we have a broker connection
            if not hasattr(self, 'broker') or not self.broker:
                self.logger.debug(f"🔍 {symbol}: No broker connection - assuming position exists")
                return True
            
            # Try to get current positions from broker
            try:
                if hasattr(self.broker, 'get_positions'):
                    broker_positions = await self.broker.get_positions()
                    if broker_positions:
                        broker_symbols = [pos.symbol for pos in broker_positions if hasattr(pos, 'symbol')]
                        position_exists = symbol in broker_symbols
                        if not position_exists:
                            self.logger.warning(f"⚠️ {symbol}: Position not found in broker positions: {broker_symbols}")
                        return position_exists
                elif hasattr(self.broker, 'positions'):
                    broker_positions = self.broker.positions
                    position_exists = symbol in broker_positions
                    if not position_exists:
                        self.logger.warning(f"⚠️ {symbol}: Position not found in broker.positions: {list(broker_positions.keys())}")
                    return position_exists
            except Exception as broker_error:
                self.logger.debug(f"🔍 {symbol}: Broker position check failed: {broker_error} - assuming position exists")
                return True
            
            # If no broker method available, assume position exists
            self.logger.debug(f"🔍 {symbol}: No broker position verification method - assuming position exists")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error verifying position for {symbol}: {e}")
            return True  # Default to assuming position exists to avoid blocking valid exits
    
    def should_exit(self, symbol: str, current_bar: MarketData, position: Position) -> Optional[Signal]:
        """Check if we should exit position (now properly implemented)"""
        # This method is kept for interface compatibility but the actual logic is in _check_exit_conditions
        # which is called from on_bar
        return None
    
    def get_ml_statistics(self) -> Dict[str, Any]:
        """Get ML performance statistics"""
        stats = {
            'total_selections': self.total_selections,
            'active_trades': len([t for t in self.active_trades.values() if t['trade_opened']]),
            'completed_trades': len([t for t in self.active_trades.values() if not t['trade_opened']]),
            'cached_contexts': len(self.context_cache),
            'loaded_strategies': len(self.strategy_instances),
            'available_strategies': len(self.available_strategies),
            'trades_since_save': self.trades_since_save,
            'model_save_frequency': self.model_save_frequency,
            'smallcap_ml_enabled': self.smallcap_ml_enabled,
            'smallcap_price_threshold': self.smallcap_price_threshold
        }
        
        # Strategy performance from ML model
        if self.ml_selector:
            try:
                if hasattr(self.ml_selector, 'strategy_stats'):
                    for strategy, perf in self.ml_selector.strategy_stats.items():
                        stats[f'{strategy}_trades'] = perf.total_trades
                        stats[f'{strategy}_win_rate'] = perf.win_rate
                        stats[f'{strategy}_avg_pnl'] = perf.avg_pnl
                        
                # Log ML learning status periodically
                if self.total_selections % 100 == 0:  # Every 100 selections
                    self.logger.info(f"🧠 ML Learning Status: {stats['completed_trades']} completed trades, {stats['trades_since_save']}/{stats['model_save_frequency']} until next save")
                    
            except Exception as e:
                self.logger.error(f"❌ Error getting ML statistics: {e}")
        
        return stats
    
    def diagnose_ml_learning(self) -> None:
        """Diagnose ML learning status - call this manually to check if learning is working"""
        self.logger.info("🔍 ML Learning Diagnostic Report")
        self.logger.info("=" * 50)
        
        # Check ML selector
        if not self.ml_selector:
            self.logger.error("❌ ML Selector not initialized!")
            return
        else:
            self.logger.info("✅ ML Selector initialized")
        
        # Check active trades
        active_count = len([t for t in self.active_trades.values() if t['trade_opened']])
        closed_count = len([t for t in self.active_trades.values() if not t['trade_opened']])
        self.logger.info(f"📊 Trades: {active_count} active, {closed_count} closed, {len(self.active_trades)} total")
        
        # Check recent trades
        if self.active_trades:
            recent_trades = list(self.active_trades.values())[-5:]  # Last 5 trades
            self.logger.info("📋 Recent trades:")
            for i, trade in enumerate(recent_trades, 1):
                status = "OPEN" if trade['trade_opened'] else "CLOSED"
                strategy = trade.get('strategy', 'unknown')
                symbol = trade.get('symbol', 'unknown')
                self.logger.info(f"   {i}. {symbol} - {strategy} - {status}")
        
        # Check ML model stats
        if hasattr(self.ml_selector, 'strategy_stats'):
            self.logger.info("🧠 ML Strategy Performance:")
            for strategy, stats in self.ml_selector.strategy_stats.items():
                self.logger.info(f"   {strategy}: {stats.total_trades} trades, {stats.win_rate:.1%} win rate, avg PnL: {stats.avg_pnl:.2f}")
        else:
            self.logger.warning("⚠️ No ML strategy stats available")
        
        # Check save status
        self.logger.info(f"💾 Model Save Status: {self.trades_since_save}/{self.model_save_frequency} trades until next save")
        
        self.logger.info("=" * 50)
    
    def _convert_to_smallcap_context(self, symbol: str, context: TickerContext) -> Optional['SmallcapTickerContext']:
        """Convert TickerContext to SmallcapTickerContext"""
        try:
            if not SMALLCAP_ML_AVAILABLE:
                return None
            
            if context is None:
                self.logger.warning(f"Cannot convert None context for {symbol}")
                return None
            
            # Calculate simplified features for smallcap context
            gap_percentage = context.price_change_1h  # Use 1h change as gap approximation
            volume_ratio = context.volume_ratio_current
            
            # Estimate catalyst information based on context
            catalyst_strength = 0.5  # Default
            catalyst_type_score = 0.3  # Default to technical
            
            # Price tier (normalize to 0-1 for $0.50-$15 range)
            price_tier = min(max((context.current_price - 0.5) / 14.5, 0.0), 1.0)
            
            # Time of day (normalize)
            time_of_day = min(max(context.minutes_from_open / 390, 0.0), 1.0)  # 390 minutes = 6.5 hours
            
            # Momentum score based on volume and price change
            momentum_score = min(
                (abs(gap_percentage) * 3 + min(volume_ratio / 5, 1.0)) / 2,
                1.0
            )
            
            # Premarket factor (if early in session with high volume)
            premarket_factor = 1.0 if (context.minutes_from_open < 60 and volume_ratio > 2.0) else 0.0
            
            return SmallcapTickerContext(
                symbol=symbol,
                gap_percentage=gap_percentage,
                volume_ratio=volume_ratio,
                catalyst_strength=catalyst_strength,
                catalyst_type_score=catalyst_type_score,
                price_tier=price_tier,
                time_of_day=time_of_day,
                momentum_score=momentum_score,
                premarket_factor=premarket_factor,
                # Required parent fields
                current_price=context.current_price,
                avg_volume_10=context.avg_volume_10,
                avg_volume_50=context.avg_volume_50,
                volatility_10=context.volatility_10,
                volatility_50=context.volatility_50,
                price_change_1h=context.price_change_1h,
                price_change_4h=context.price_change_4h,
                rsi_14=context.rsi_14,
                volume_ratio_current=context.volume_ratio_current,
                volume_spike_frequency=context.volume_spike_frequency,
                hour_of_day=context.hour_of_day,
                minutes_from_open=context.minutes_from_open,
                is_first_hour=context.is_first_hour,
                is_last_hour=context.is_last_hour,
                market_trend=context.market_trend,
                sector_performance=context.sector_performance,
                breakout_success_rate=context.breakout_success_rate,
                mean_reversion_tendency=context.mean_reversion_tendency
            )
            
        except Exception as e:
            self.logger.error(f"Error converting to smallcap context: {e}")
            return None

    def get_hybrid_system_report(self) -> Dict[str, Any]:
        """Get comprehensive report of ML vs Rules system performance"""
        if not self.hybrid_system_enabled or not self.ml_vs_rules_tracker:
            return {"error": "Hybrid system not enabled"}

        try:
            # Get performance summary
            performance = self.ml_vs_rules_tracker.get_performance_summary()

            # Get rule-based selector stats
            rule_stats = {}
            if self.rule_based_selector:
                rule_stats = self.rule_based_selector.get_selection_stats()

            # Get detailed analysis
            detailed_analysis = self.ml_vs_rules_tracker.get_detailed_analysis()

            return {
                "system_status": "ACTIVE",
                "hybrid_enabled": self.hybrid_system_enabled,
                "performance_summary": performance,
                "rule_based_stats": rule_stats,
                "detailed_analysis": detailed_analysis,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error generating hybrid system report: {e}")
            return {"error": str(e)}

    def print_hybrid_system_summary(self) -> None:
        """Print a summary of the hybrid system performance to console"""
        if not self.hybrid_system_enabled:
            print("🔄 Hybrid ML vs Rules system is DISABLED")
            return

        try:
            if self.ml_vs_rules_tracker:
                self.ml_vs_rules_tracker.print_summary_report()
            else:
                print("⚠️ Hybrid system enabled but tracker not available")

        except Exception as e:
            self.logger.error(f"Error printing hybrid summary: {e}")

    def _get_strategy_mapping(self) -> Dict[str, str]:
        """Get strategy mapping for smallcap conversion"""
        return {
            'catalyst_momentum': 'catalyst_momentum',  # NEW: Map catalyst_momentum to itself
            'gap_go': 'gap_go',
            'optimized_gap_go': 'gap_go',
            'daily_plays': 'daily_plays',
            'first_day_bounce': 'first_day_bounce',
            'red_to_green': 'red_to_green',
            'gap_crap_reversal': 'gap_crap_reversal',
            'macdv_smallcaps': 'macdv_smallcaps',
            'explosive_volume': 'explosive_volume',
            'simple_volume_explosion': 'explosive_volume',
            'improved_simple_explosion': 'explosive_volume',
            'volume_explosion_pullback': 'explosive_volume',
            'volume_momentum': 'explosive_volume',
            'orb': 'orb',
            'vcp': 'daily_plays',
            'vwap_smallcaps': 'daily_plays',
            'vwap_reclaim': 'daily_plays',
            'eod_momentum': 'daily_plays',
            'pmh_breakout': 'gap_go'
        }
    
    def update_smallcap_ml_with_trade_result(self, symbol: str, strategy: str, pnl: float, 
                                           duration_hours: float = None):
        """Update smallcap ML model with trade results"""
        if not self.smallcap_ml_enabled or not self.smallcap_ml_selector:
            return
        
        try:
            # Find the most recent context for this symbol
            matching_trades = [
                (trade_id, trade_data) for trade_id, trade_data in self.active_trades.items()
                if trade_data['symbol'] == symbol and not trade_data['trade_opened']
            ]
            
            if matching_trades:
                # Get the most recent trade
                trade_id, trade_data = matching_trades[-1]
                
                # Check if original context exists and can be converted
                original_context = trade_data.get('context')
                if original_context and isinstance(original_context, TickerContext):
                    smallcap_context = self._convert_to_smallcap_context(symbol, original_context)
                    
                    if smallcap_context:
                        # Map strategy name to smallcap strategy
                        strategy_mapping = self._get_strategy_mapping()
                        smallcap_strategy = strategy_mapping.get(strategy, strategy)
                        
                        # Normalize PnL to 0-1 scale for reward
                        reward = max(-1.0, min(1.0, pnl / 0.10))  # ±10% = ±1.0 reward
                        
                        # Update the smallcap ML model
                        self.smallcap_ml_selector.update_reward(
                            smallcap_strategy, smallcap_context, reward, duration_hours
                        )
                        
                        self.logger.info(f"🧠💎 Updated Smallcap ML: {smallcap_strategy} on {symbol} = {pnl:.1%} -> reward {reward:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error updating smallcap ML: {e}")
    
    def save_smallcap_ml_model(self):
        """Save the smallcap ML model"""
        if self.smallcap_ml_selector:
            try:
                model_path = "data/ml_models/smallcap_strategy_bandit.json"
                self.smallcap_ml_selector.save_model(model_path)
                self.logger.info(f"💾 Saved smallcap ML model to {model_path}")
            except Exception as e:
                self.logger.error(f"Error saving smallcap ML model: {e}")
    
    def get_smallcap_ml_summary(self) -> str:
        """Get smallcap ML performance summary"""
        if not self.smallcap_ml_selector:
            return "Smallcap ML not available"
        
        return self.smallcap_ml_selector.format_performance_summary()
    
    def _check_fomo_exit(self, symbol: str, current_price: float, volume: int, position: Position) -> bool:
        """
        Check FOMO exit conditions with time-based scaling
        """
        try:
            # Get current market hour
            current_time = datetime.now()
            hour = current_time.hour
            
            # Get time-based thresholds
            thresholds = self._get_time_based_thresholds(hour)
            
            # Calculate profit percentage
            entry_price = position.avg_price
            profit_pct = (current_price - entry_price) / entry_price
            
            # Calculate volume ratio (mock for testing - in real implementation would use historical data)
            avg_volume = 1000000  # Mock average volume
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
            
            # Check FOMO conditions
            volume_condition = volume_ratio >= thresholds['volume_multiplier']
            profit_condition = profit_pct >= thresholds['min_profit_volume']
            
            self.logger.debug(f"FOMO check for {symbol}: profit={profit_pct:.3f} (need {thresholds['min_profit_volume']:.3f}), "
                            f"volume={volume_ratio:.1f}x (need {thresholds['volume_multiplier']:.1f}x)")
            
            return volume_condition and profit_condition
            
        except Exception as e:
            self.logger.error(f"Error in FOMO exit check for {symbol}: {e}")
            return False
    
    def _get_time_based_thresholds(self, hour: int) -> Dict[str, float]:
        """
        Get time-based thresholds for FOMO exits (Option C implementation)
        """
        try:
            # TIME-BASED SCALING: Adjust thresholds based on market time
            if hour < 14:  # Morning/Midday (9:30-14:00)
                return {
                    "time_period": "conservative",
                    "volume_multiplier": 2.0,
                    "min_profit_volume": 0.03  # 3%
                }
            elif hour < 15:  # Afternoon (14:00-15:00)
                return {
                    "time_period": "intermediate",  
                    "volume_multiplier": 1.8,
                    "min_profit_volume": 0.025  # 2.5%
                }
            else:  # Late day (15:00-15:55)
                return {
                    "time_period": "aggressive",
                    "volume_multiplier": 1.5,
                    "min_profit_volume": 0.02  # 2%
                }
                
        except Exception as e:
            self.logger.error(f"Error getting time-based thresholds: {e}")
            # Return conservative defaults on error
            return {
                "time_period": "conservative",
                "volume_multiplier": 2.0,
                "min_profit_volume": 0.03
            }

    async def _rule_based_select_strategies(self, symbol: str, context: TickerContext) -> List[str]:
        """
        Rule-based strategy selection - Each strategy decides for itself
        """
        selected_strategies = []

        try:
            # Get basic symbol characteristics
            current_price = context.current_price
            volume_ratio = getattr(context, 'volume_ratio', 1.0)
            gap_percent = getattr(context, 'gap_percent', 0.0)
            is_news = getattr(context, 'has_catalyst', False)

            # Rule 1: Gap Go Strategy - Only for significant gaps with volume
            if abs(gap_percent) >= 8.0 and volume_ratio >= 2.0:
                selected_strategies.append('gap_go')
                self.logger.debug(f"🎯 {symbol}: Gap Go selected (gap: {gap_percent:.1f}%, vol: {volume_ratio:.1f}x)")

            # Rule 2: Daily Plays Strategy - Only for symbols with news/catalyst
            if is_news or volume_ratio >= 3.0:
                selected_strategies.append('daily_plays')
                self.logger.debug(f"🎯 {symbol}: Daily Plays selected (news: {is_news}, vol: {volume_ratio:.1f}x)")

            # Rule 3: MACDV Strategy - For technical setups without major gaps or catalysts
            if abs(gap_percent) <= 5.0 and volume_ratio >= 1.5 and not is_news:
                selected_strategies.append('macdv_smallcaps')
                self.logger.debug(f"🎯 {symbol}: MACDV selected (small gap: {gap_percent:.1f}%, vol: {volume_ratio:.1f}x, no news)")

            # Rule 4: Gap Crap Reversal - For negative gaps that are reversing
            if gap_percent <= -8.0 and volume_ratio >= 2.0:
                selected_strategies.append('gap_crap_reversal')
                self.logger.debug(f"🎯 {symbol}: Gap Crap Reversal selected (gap: {gap_percent:.1f}%, vol: {volume_ratio:.1f}x)")

            # Rule 5: First Day Bounce - For potential bounce plays
            if gap_percent <= -3.0 and current_price <= 10.0:
                selected_strategies.append('first_day_bounce')
                self.logger.debug(f"🎯 {symbol}: First Day Bounce selected (gap: {gap_percent:.1f}%, price: ${current_price:.2f})")

            # Rule 6-8: Pattern Strategies - Let them decide through their own analysis
            # These will be evaluated by their specific pattern detection logic
            pattern_strategies = ['ascending_triangle', 'bull_flag', 'falling_wedge']
            for pattern_strategy in pattern_strategies:
                if volume_ratio >= 0.8:  # Lower volume requirement for patterns (let pattern logic decide)
                    selected_strategies.append(pattern_strategy)
                    self.logger.debug(f"🎯 {symbol}: {pattern_strategy} added for pattern analysis")

            # Limit to max strategies per ticker
            if len(selected_strategies) > self.max_strategies_per_ticker:
                selected_strategies = selected_strategies[:self.max_strategies_per_ticker]

            if selected_strategies:
                self.logger.info(f"🎯 {symbol}: Rule-based selection: {selected_strategies}")

            return selected_strategies

        except Exception as e:
            self.logger.error(f"Error in rule-based selection for {symbol}: {e}")
            # Fallback: return most conservative strategy
            return ['macdv_smallcaps'] if current_price <= 15.0 else []

# Factory function for easy instantiation
def create_ml_multi_strategy_engine(parameters: Dict[str, Any] = None) -> MLMultiStrategyEngine:
    """Create ML-powered multi-strategy engine"""
    return MLMultiStrategyEngine(parameters)

if __name__ == "__main__":
    # Test básico
    print("🧪 ML Multi-Strategy Engine Test")
    print("=" * 50)
    
    engine = create_ml_multi_strategy_engine()
    print(f"Engine: {engine.name}")
    print(f"Max strategies per ticker: {engine.max_strategies_per_ticker}")
    print("=" * 50)
    print("✅ ML Multi-Strategy Engine ready for intelligent trading!")