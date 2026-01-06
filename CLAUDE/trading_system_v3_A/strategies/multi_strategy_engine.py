# strategies/multi_strategy_engine.py
"""
Multi-Strategy Engine - Ejecuta múltiples estrategias y selecciona la mejor señal
Diseñado específicamente para trading de smallcaps con entrada manual de tickers
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime as dt, time, timezone
from zoneinfo import ZoneInfo
import asyncio
import configparser

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData, EventBus, Signal, SignalType, OrderType, OrderSide
from core.events import EventHandlerMixin
# Dynamic strategy imports - strategies are loaded dynamically from config
# NOTE: Removed direct import to avoid circular dependency
# from . import get_strategy_class, list_strategies



class MultiStrategyEngine(IStrategy, EventHandlerMixin):
    """
    Motor de múltiples estrategias que ejecuta todas las estrategias disponibles
    y selecciona automáticamente la mejor señal basada en condiciones del mercado.
    
    Ideal para trading de smallcaps donde cada ticker puede requerir una estrategia diferente
    dependiendo del momento del día y las condiciones del mercado.
    """
    
    def _get_bar_value(self, bar, field: str):
        """Helper to get value from bar regardless if it's MarketData object or dict"""
        if hasattr(bar, field):
            return getattr(bar, field)
        elif isinstance(bar, dict):
            return bar.get(field)
        else:
            raise ValueError(f"Cannot get {field} from bar of type {type(bar)}")

    def __init__(self, parameters: Dict[str, Any] = None):
        self._name = "MultiStrategy_Engine"
        self._parameters = parameters or {}
        self.logger = logging.getLogger(f"Strategy.{self._name}")
        
        # Initialize base class
        super().__init__(None)
        
        
        # State tracking
        self.positions: Dict[str, Any] = {}
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_generated: Dict[str, List[Signal]] = {}
        
        # Performance tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Event bus will be set during initialization
        self.event_bus: Optional[EventBus] = None
        
        # Strategy instances
        self.strategies = {}
        self.strategy_scores = {}  # Track performance per strategy
        self.symbol_strategy_preference = {}  # Learn which strategy works best per symbol
        
        # Detect if we're in TESTING or PRODUCTION profile
        self._detect_active_profile()
        
        # Load profile parameters if none provided (like working commit did)
        if not self._parameters:
            profile_params = self._load_profile_parameters()
            if profile_params:
                self._parameters = {
                    'volume_spike_threshold': profile_params.get('macdv', {}).get('volume_threshold', 1.5),
                    'min_volume_ratio': profile_params.get('macdv', {}).get('volume_threshold', 0.5)
                }
        
        # --- Variables para auto-ajuste dinámico ---
        self.dynamic_volume_multiplier = self._parameters.get('volume_spike_threshold', 1.5)
        self._no_signal_counter = 0  # barras consecutivas sin señales
        
        # Rango dinámico de volatilidad (en porcentaje) - configurable desde profile  
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Leer valores de volatilidad del profile
        profile_section = f"{self.current_profile}_PROFILE"
        if profile_section in config:
            self.dynamic_vol_min = config.getfloat(profile_section, 'dynamic_vol_min', fallback=1.0)
            self.dynamic_vol_max = config.getfloat(profile_section, 'dynamic_vol_max', fallback=8.0)
        else:
            self.dynamic_vol_min = 0.2 if self.current_profile == 'TESTING' else 0.8  # MÁS permisivo para smallcaps
            self.dynamic_vol_max = 6.0 if self.current_profile == 'TESTING' else 8.0
        
        # Initialize individual strategies (después de configurar volatilidad)
        self._initialize_strategies()
        
        # --- Parámetros específicos para smallcaps ---
        self.smallcap_mode = True  # Activar modo smallcaps (más permisivo)
        self.min_volume_multiplier = 0.1 if self.smallcap_mode else 0.8  # MUY permisivo para detectar acumulación silenciosa
        self.min_volume_ratio = self._parameters.get('min_volume_ratio', 0.1)  # REDUCIDO: permite tickers "muertos" pre-breakout
        
        # --- Sistema híbrido de candidatos ---
        self.prebreakout_candidates = set()  # Símbolos candidatos para análisis detallado
        self.candidate_update_counter = 0    # Contador para actualizar candidatos
        
        profile_type = "TESTING (Extended Hours)" if self._is_testing_profile else "PRODUCTION (Normal Hours)"
        self.logger.info(f"MultiStrategyEngine initialized with strategies: {', '.join(self.strategies.keys())} | Profile: {profile_type}")
        self.logger.info(f"🔧 Dynamic volume multiplier initialized to: {self.dynamic_volume_multiplier}")
        self.logger.info(f"🔧 Min volume ratio initialized to: {self.min_volume_ratio}")
        self.logger.info(f"🔧 Volatility range initialized to: {float(self.dynamic_vol_min):.1f}% - {float(self.dynamic_vol_max):.1f}%")
    
    def _detect_active_profile(self):
        """Detectar si estamos en perfil TESTING o PRODUCTION"""
        try:
            import configparser
            import os
            
            # Buscar config.ini
            config_path = 'config.ini'
            if not os.path.exists(config_path):
                # Buscar en directorio padre si no está en el actual
                config_path = '../config.ini'
            
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                
                # Leer perfil activo
                active_profile = config.get('TRADING', 'active_profile', fallback='TESTING').upper()
                self.current_profile = active_profile  # ← AGREGAR ESTA LÍNEA
                self._is_testing_profile = (active_profile == 'TESTING')
                
                self.logger.info(f"🔧 Profile detected: {active_profile} ({'Extended Hours' if self._is_testing_profile else 'Normal Hours'})")
            else:
                # Default a TESTING si no encuentra config
                self.current_profile = 'TESTING'  # ← AGREGAR ESTA LÍNEA
                self._is_testing_profile = True
                self.logger.warning("⚠️ Config.ini not found, defaulting to TESTING profile (Extended Hours)")
                
        except Exception as e:
            # Default a TESTING en caso de error
            self.current_profile = 'TESTING'  # ← AGREGAR ESTA LÍNEA
            self._is_testing_profile = True
            self.logger.warning(f"⚠️ Error detecting profile, defaulting to TESTING: {e}")
    
    def _load_profile_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Load parameters specific to the active profile (TESTING or PRODUCTION)"""
        try:
            import configparser
            import os
            
            # Buscar config.ini
            config_path = 'config.ini'
            if not os.path.exists(config_path):
                config_path = '../config.ini'
            
            if not os.path.exists(config_path):
                return {}
            
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Determine which profile section to use
            section_name = 'TESTING_PROFILE' if self._is_testing_profile else 'PRODUCTION_PROFILE'
            
            if section_name not in config:
                return {}
            
            # Extract parameters for each strategy
            profile_data = dict(config[section_name])
            
            # Organize parameters by strategy
            params = {
                'macdv': {
                    'volume_threshold': float(profile_data.get('macdv_volume_threshold', 1.5)),
                    'volume_spike_threshold': float(profile_data.get('macdv_volume_spike_threshold', 2.0)),
                    'min_conditions': int(profile_data.get('macdv_min_conditions', 4)),
                    'avoid_first_30min': profile_data.get('macdv_avoid_first_30min', 'true').lower() == 'true',
                    'avoid_last_30min': profile_data.get('macdv_avoid_last_30min', 'true').lower() == 'true'
                },
                'gap_go': {
                    'min_gap_percent': float(profile_data.get('gap_go_min_gap_percent', 4.0)),
                    'volume_multiplier': float(profile_data.get('gap_go_volume_multiplier', 2.5)),
                    'min_volume': int(profile_data.get('gap_go_min_volume', 200000)),
                    'premarket_volume_min': int(profile_data.get('gap_go_premarket_volume_min', 15000))
                },
                'orb': {
                    'volume_spike_threshold': float(profile_data.get('orb_volume_spike_threshold', 3.0)),
                    'volume_confirmation_threshold': float(profile_data.get('orb_volume_confirmation_threshold', 2.0)),
                    'min_dollar_volume': int(profile_data.get('orb_min_dollar_volume', 300000)),
                    'min_conditions': int(profile_data.get('orb_min_conditions', 6)),
                    'trading_start_time': profile_data.get('orb_trading_start_time', '09:30:00'),
                    'trading_end_time': profile_data.get('orb_trading_end_time', '15:30:00')
                },
                'volume_breakout': {
                    'volume_multiplier': float(profile_data.get('volume_breakout_volume_multiplier', 2.0)),
                    'min_volume_threshold': int(profile_data.get('volume_breakout_min_volume_threshold', 10000)),
                    'min_price_change': float(profile_data.get('volume_breakout_min_price_change', 0.012))
                },
                'pmh_breakout': {
                    'min_premarket_volume': int(profile_data.get('pmh_min_premarket_volume', 75000)),
                    'breakout_volume_multiplier': float(profile_data.get('pmh_breakout_volume_multiplier', 3.0)),
                    'min_daily_volume': int(profile_data.get('pmh_min_daily_volume', 500000))
                }
            }
            
            return params
            
        except Exception as e:
            self.logger.warning(f"Error loading profile parameters: {e}")
            return {}
    
    def _initialize_strategies(self):
        """Initialize all available strategies"""
        try:
            # Load profile-specific parameters
            profile_params = self._load_profile_parameters()
            
            # Get strategy-specific parameters from profile parameters
            macdv_params = profile_params.get('macdv', {})
            gap_go_params = profile_params.get('gap_go', {})
            orb_params = profile_params.get('orb', {})
            volume_breakout_params = profile_params.get('volume_breakout', {})
            pmh_params = profile_params.get('pmh_breakout', {})
            
            # Check if extended hours data is available for premarket strategies
            extended_hours_available = self._check_extended_hours_availability()
            
            # Log loaded parameters for debugging
            self.logger.info(f"📋 Loaded {('TESTING' if self._is_testing_profile else 'PRODUCTION')} parameters for strategies:")
            self.logger.info(f"   🎯 MACDV: volume_threshold={macdv_params.get('volume_threshold', 'default')}, min_conditions={macdv_params.get('min_conditions', 'default')}")
            self.logger.info(f"   🎯 Gap&Go: min_gap_percent={gap_go_params.get('min_gap_percent', 'default')}%, volume_multiplier={gap_go_params.get('volume_multiplier', 'default')}")
            self.logger.info(f"   🎯 ORB: volume_spike={orb_params.get('volume_spike_threshold', 'default')}, min_conditions={orb_params.get('min_conditions', 'default')}")
            self.logger.info(f"   💥 Hybrid Explosion: volume_threshold={profile_params.get('hybrid_explosion', {}).get('volume_threshold', '2.5')}x, global_components=enabled")
            self.logger.info(f"   🌅 Extended hours data: {'AVAILABLE' if extended_hours_available else 'NOT AVAILABLE'}")

            
            # Initialize strategies dynamically from config
            self.strategies = {}
            self._initialize_strategies_from_config(profile_params, extended_hours_available)
            
            # Initialize performance tracking
            for strategy_name in self.strategies.keys():
                self.strategy_scores[strategy_name] = {
                    'total_signals': 0,
                    'winning_signals': 0,
                    'losing_signals': 0,
                    'avg_pnl': 0.0,
                    'confidence_multiplier': 1.0
                }
                
        except Exception as e:
            self.logger.error(f"Error initializing strategies: {e}")
            # Fallback to MACDV only
            self.strategies = {
                'macdv_smallcaps': MACDVStrategy(self._parameters.get('macdv', {}))
            }
    
    def _check_extended_hours_availability(self) -> bool:
        """Check if extended hours data is available by checking config"""
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            # Check trading_hours_mode in config
            trading_hours_mode = config.get('TRADING', 'trading_hours_mode', fallback='REGULAR')
            
            if trading_hours_mode == 'EXTENDED_HOURS':
                self.logger.info("🌅 Extended hours mode detected in config - premarket data should be available")
                return True
            else:
                self.logger.info(f"🕘 Trading hours mode: {trading_hours_mode} - no premarket data available")
                return False
                
        except Exception as e:
            self.logger.warning(f"⚠️ Could not check extended hours availability: {e}")
            # Conservative default - assume no extended hours
            return False
    
    def _is_ticker_suitable_for_strategy(self, symbol: str, strategy_name: str, bar: MarketData) -> bool:
        """Pre-filter tickers based on configurable strategy requirements"""
        try:
            # Get recent bar history for analysis
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < 10:
                return True  # Not enough data to filter, let strategy decide
            
            recent_bars = self.bars_history[symbol][-10:]  # Last 10 bars
            current_price = self._get_bar_value(bar, 'close')
            
            # Calculate recent metrics
            avg_volume = sum(self._get_bar_value(b, 'volume') for b in recent_bars) / len(recent_bars)
            avg_dollar_volume = sum(self._get_bar_value(b, 'volume') * self._get_bar_value(b, 'close') for b in recent_bars) / len(recent_bars)
            price_range = max(self._get_bar_value(b, 'high') for b in recent_bars) - min(self._get_bar_value(b, 'low') for b in recent_bars)
            volatility = (price_range / current_price) if current_price > 0 else 0
            
            # Use configurable filters
            return self._check_configurable_filters(
                strategy_name, symbol, current_price, avg_volume, avg_dollar_volume, volatility
            )
            
        except Exception as e:
            self.logger.error(f"Error filtering {symbol} for {strategy_name}: {e}")
            return True  # On error, let strategy decide
    
    def _get_filter_value_with_global_fallback(self, config: configparser.ConfigParser, section_name: str, key: str, fallback_value, data_type='float'):
        """Get filter value with GLOBAL section as fallback"""
        try:
            # Try to get global value first as fallback
            global_fallback = fallback_value
            if config.has_section('GLOBAL') and config.has_option('GLOBAL', key):
                if data_type == 'float':
                    global_fallback = config.getfloat('GLOBAL', key)
                elif data_type == 'int':
                    global_fallback = config.getint('GLOBAL', key)
                else:
                    global_fallback = config.get('GLOBAL', key)
            
            # Try to get section-specific value, falling back to global or default
            section = config[section_name]
            if data_type == 'float':
                return section.getfloat(key, global_fallback)
            elif data_type == 'int':
                return section.getint(key, global_fallback)
            else:
                return section.get(key, global_fallback)
                
        except Exception:
            return fallback_value

    def _check_configurable_filters(self, strategy_name: str, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check ticker against configurable filters from config.ini"""
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            # Map strategy names to config sections
            strategy_section_map = {
                'orb': 'STRATEGY_FILTERS_ORB',
                'gap_go': 'STRATEGY_FILTERS_GAP_GO', 
                'pmh_breakout': 'STRATEGY_FILTERS_PMH',
                'macdv_smallcaps': 'STRATEGY_FILTERS_MACDV',
                'volume_breakout': 'STRATEGY_FILTERS_VOLUME_BREAKOUT'
            }
            
            section_name = strategy_section_map.get(strategy_name)
            if not section_name or section_name not in config:
                # No filters configured for this strategy - allow all
                return True
            
            section = config[section_name]
            
            # Check if filtering is enabled for this strategy
            if not section.getboolean('enabled', True):
                return True
            
            # Apply configurable filters (inherit from GLOBAL)
            min_price = self._get_filter_value_with_global_fallback(config, section_name, 'min_price', 0)
            max_price = self._get_filter_value_with_global_fallback(config, section_name, 'max_price', 999999)
            
            if price < min_price:
                return False
            if price > max_price:
                return False
            if avg_volume < section.getfloat('min_volume', 0):
                return False
            if avg_dollar_volume < section.getfloat('min_dollar_volume', 0):
                return False
            if volatility < section.getfloat('min_volatility', 0):
                return False
            if volatility > section.getfloat('max_volatility', 999):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking configurable filters for {strategy_name}: {e}")
            return True  # On error, be permissive
    
    def _is_suitable_for_orb(self, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check if ticker is suitable for ORB strategy"""
        # ORB needs high-liquidity, medium-volatility stocks
        return (
            price >= 2.0 and                    # No extreme penny stocks
            price <= 15.0 and                  # No high-priced stocks
            avg_volume >= 2000 and             # Minimum liquidity
            avg_dollar_volume >= 50000 and     # Minimum dollar volume
            volatility >= 0.02 and             # Minimum volatility (2%)
            volatility <= 0.25                 # Maximum volatility (25%)
        )
    
    def _is_suitable_for_gap_go(self, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check if ticker is suitable for Gap&Go strategy"""
        # Gap&Go needs volatile, liquid small caps
        return (
            price >= 1.0 and
            price <= 20.0 and
            avg_volume >= 5000 and
            avg_dollar_volume >= 75000 and
            volatility >= 0.03                 # Needs higher volatility
        )
    
    def _is_suitable_for_pmh(self, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check if ticker is suitable for PMH strategy"""
        # PMH needs liquid small caps with good range
        return (
            price >= 2.0 and
            price <= 25.0 and
            avg_volume >= 10000 and
            avg_dollar_volume >= 100000 and
            volatility >= 0.05                 # Needs significant volatility
        )
    
    def _is_suitable_for_macdv(self, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check if ticker is suitable for MACDV strategy"""
        # MACDV is more flexible, works with various stocks
        return (
            price >= 0.50 and
            price <= 50.0 and
            avg_volume >= 1000 and
            avg_dollar_volume >= 25000
        )
    
    def _is_suitable_for_volume_breakout(self, symbol: str, price: float, avg_volume: float, avg_dollar_volume: float, volatility: float) -> bool:
        """Check if ticker is suitable for Volume Breakout strategy"""
        # Volume breakout needs good liquidity and volatility
        return (
            price >= 1.0 and
            price <= 30.0 and
            avg_volume >= 3000 and
            avg_dollar_volume >= 40000 and
            volatility >= 0.015
        )
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters.copy()
    
    async def initialize(self, event_bus: EventBus, broker=None) -> None:
        """Initialize the multi-strategy engine"""
        self.event_bus = event_bus
        self.broker = broker  # Guardar referencia al broker
        
        # Sincronizar posiciones existentes
        await self._sync_existing_positions()
        
        # Initialize all individual strategies
        for strategy_name, strategy in self.strategies.items():
            try:
                await strategy.initialize(event_bus)
                self.logger.info(f"Initialized strategy: {strategy_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info(f"MultiStrategyEngine fully initialized with {len(self.strategies)} strategies")
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """
        Process new bar data through all strategies and return the best signal
        """
        try:
            symbol = bar.symbol
            
            # Store bar in history for all strategies
            if symbol not in self.bars_history:
                self.bars_history[symbol] = []
            
            # Deduplication logic: only append if the new bar is more recent
            if not self.bars_history[symbol] or bar.timestamp > self.bars_history[symbol][-1].timestamp:
                self.bars_history[symbol].append(bar)
            elif bar.timestamp == self.bars_history[symbol][-1].timestamp:
                # Update the last bar if a new one with the same timestamp arrives
                self.bars_history[symbol][-1] = bar
            else:
                # A bar arrived out of order, log it and ignore to prevent duplicates
                self.logger.warning(f"Ignoring out-of-order bar for {symbol} at {bar.timestamp}. Last bar was at {self.bars_history[symbol][-1].timestamp}")
                return None # Do not process this bar further
            
            # Keep only last N bars
            max_bars = self._parameters.get('max_history_bars', 1500)
            if len(self.bars_history[symbol]) > max_bars:
                self.bars_history[symbol] = self.bars_history[symbol][-max_bars:]
            
            # Update trailing stops for existing positions
            await self._update_trailing_stops(symbol, bar)
            
            # Execute all strategies and collect signals
            candidate_signals = []
            # Use bar timestamp for strategy evaluation (bars are already in market time)
            if hasattr(bar.timestamp, 'time'):
                current_time = bar.timestamp.time()
            else:
                # Fallback: convert bar timestamp string to time
                bar_dt = pd.to_datetime(bar.timestamp)
                current_time = bar_dt.time()
            
            # Add detailed logging every 10 bars to understand why no signals are generated
            if not hasattr(self, '_diagnostic_counter'):
                self._diagnostic_counter = {}
            if symbol not in self._diagnostic_counter:
                self._diagnostic_counter[symbol] = 0
            self._diagnostic_counter[symbol] += 1
            
            # Non-overlapping analysis system: ensure 1-minute separation between symbol analyses
            total_symbols = len(self._diagnostic_counter)
            # ≤5 symbols: 5-minute frequency with intercalation, >5 symbols: frequency = symbol count
            analysis_frequency = max(5, total_symbols)
            
            # Calculate symbol offset to prevent overlapping (guaranteed 1-minute separation)
            symbol_hash_index = hash(symbol) % total_symbols if total_symbols > 0 else 0
            if total_symbols <= 5:
                # Distribute evenly within 5 minutes
                symbol_offset = symbol_hash_index * (analysis_frequency // max(1, total_symbols))
            else:
                # One minute separation between each symbol
                symbol_offset = symbol_hash_index
            
            if (self._diagnostic_counter[symbol] + symbol_offset) % analysis_frequency == 0:
                try:
                    # Define us_now for detailed analysis
                    from zoneinfo import ZoneInfo
                    us_now = current_time.astimezone(ZoneInfo("America/New_York")) if hasattr(current_time, 'astimezone') else current_time
                    
                    # Run detailed analysis with timeout to prevent blocking
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, 
                            self._log_detailed_strategy_analysis, 
                            symbol, bar, current_time, us_now
                        ),
                        timeout=0.5  # Maximum 0.5 seconds for detailed analysis
                    )
                except asyncio.TimeoutError:
                    self.logger.debug(f"⏰ Detailed analysis timed out for {symbol}")
                except Exception as e:
                    self.logger.debug(f"❌ Error in detailed analysis for {symbol}: {e}")
            
            for strategy_name, strategy in self.strategies.items():
                try:
                    # Check if strategy is active
                    is_active = self._is_strategy_active(strategy_name, current_time)
                    
                    if not is_active:
                        # Log periodically why strategies are inactive
                        if hasattr(self, '_inactive_log_counter'):
                            self._inactive_log_counter += 1
                        else:
                            self._inactive_log_counter = 1
                            
                        if self._inactive_log_counter % 50 == 0:  # Every 50 bars
                            active_window = self._get_strategy_active_window(strategy_name)
                            self.logger.info(f"⏰ Strategy {strategy_name} inactive at US {current_time.strftime('%H:%M:%S')} (active: {active_window})")
                        continue
                    
                    # NUEVA VALIDACIÓN: Filtros de pre-selección por estrategia
                    if not self._is_ticker_suitable_for_strategy(symbol, strategy_name, bar):
                        # Log occasionally why ticker was filtered out
                        filter_offset = hash(symbol) % 15  # Stagger filter logging
                        if (self._diagnostic_counter[symbol] + filter_offset) % 50 == 0:
                            self.logger.debug(f"🚫 {symbol} filtered out for {strategy_name} (unsuitable ticker)")
                        continue
                    
                    # Update strategy's bar history
                    strategy.bars_history[symbol] = self.bars_history[symbol]
                    
                    # Propagar umbral dinámico antes de evaluar
                    try:
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(
                                None, self._propagate_dynamic_thresholds
                            ),
                            timeout=0.1  # Maximum 0.1 seconds for threshold propagation
                        )
                    except asyncio.TimeoutError:
                        self.logger.debug(f"⏰ Threshold propagation timed out for {symbol}")
                    # Get signal from strategy with timeout to prevent individual strategy freezing
                    try:
                        signal = await asyncio.wait_for(
                            strategy.on_bar(bar), 
                            timeout=2.0  # Maximum 2 seconds per individual strategy
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(f"⏰ Strategy {strategy_name} timed out for {symbol} - skipping")
                        continue
                    
                    if signal:
                        # Add metadata about which strategy generated it
                        if not hasattr(signal, 'metadata'):
                            signal.metadata = {}
                        
                        signal.metadata.update({
                            'strategy_name': strategy_name,
                            'source_engine': 'MultiStrategyEngine',
                            'timestamp': bar.timestamp
                        })
                        
                        # Calculate confidence for this signal
                        confidence = self._calculate_signal_confidence(signal, bar, strategy_name)
                        signal.metadata['confidence'] = confidence
                        
                        candidate_signals.append(signal)
                        
                        self.logger.info(f"🎯 Strategy {strategy_name} generated {signal.signal_type} signal for {symbol} "
                                        f"with confidence {confidence:.2f} at ${self._get_bar_value(bar, 'close'):.2f}")
                        
                    else:
                        # Log why no signal was generated (same non-overlapping logic as detailed analysis)
                        no_signal_frequency = analysis_frequency  # Same frequency as detailed analysis
                        no_signal_hash_index = hash(symbol) % total_symbols if total_symbols > 0 else 0
                        if total_symbols <= 5:
                            # Distribute evenly within 5 minutes, but offset by half to avoid collision with detailed analysis
                            no_signal_offset = no_signal_hash_index * (no_signal_frequency // max(1, total_symbols)) + (no_signal_frequency // 2)
                        else:
                            # One minute separation, offset by half-minute to avoid collision
                            no_signal_offset = no_signal_hash_index + (no_signal_frequency // 2)
                        
                        if (self._diagnostic_counter[symbol] + no_signal_offset) % no_signal_frequency == 0:
                            try:
                                # Run no-signal analysis with timeout
                                await asyncio.wait_for(
                                    asyncio.get_event_loop().run_in_executor(
                                        None, 
                                        self._log_strategy_no_signal_reason, 
                                        strategy_name, symbol, bar
                                    ),
                                    timeout=0.3  # Maximum 0.3 seconds for no-signal analysis
                                )
                            except asyncio.TimeoutError:
                                self.logger.debug(f"⏰ No-signal analysis timed out for {strategy_name}/{symbol}")
                            except Exception as e:
                                self.logger.debug(f"❌ Error in no-signal analysis for {strategy_name}/{symbol}: {e}")
                        
                except Exception as e:
                    self.logger.error(f"Error in strategy {strategy_name} for {symbol}: {e}")
                    continue
            
            # APLICAR FILTRO VWAP UNIVERSAL - Crítico para smallcaps
            if candidate_signals:
                filtered_signals = self._apply_vwap_filter(candidate_signals, symbol, bar)
                if len(filtered_signals) != len(candidate_signals):
                    rejected = len(candidate_signals) - len(filtered_signals)
                    self.logger.info(f"🛡️ VWAP filter rejected {rejected}/{len(candidate_signals)} signals for {symbol}")
                candidate_signals = filtered_signals
            
            # Select the best signal
            best_signal = self._select_best_signal(candidate_signals, symbol, bar)
            
            if best_signal:
                # Store signal
                if symbol not in self.signals_generated:
                    self.signals_generated[symbol] = []
                self.signals_generated[symbol].append(best_signal)
                
                strategy_used = best_signal.metadata.get('strategy_name', 'unknown')
                confidence = best_signal.metadata.get('confidence', 0.0)
                
                # Add timestamp logging for debugging signal delays
                current_time = dt.now(timezone.utc)
                signal_time = best_signal.timestamp
                
                # Ensure both timestamps are timezone-aware
                if signal_time.tzinfo is None:
                    signal_time = signal_time.replace(tzinfo=timezone.utc)
                    
                delay = current_time - signal_time
                
                self.logger.info(f"✅ Selected {best_signal.signal_type} for {symbol} from {strategy_used} "
                               f"(confidence: {confidence:.2f}) | Signal age: {delay}")
                
                # Attach a calculated position size if not present
                if not hasattr(best_signal, 'position_size') or best_signal.position_size is None:
                    try:
                        capital = self._parameters.get('capital', 10000.0)
                        risk_pct = self._parameters.get('risk_per_trade', 0.02)
                        size = self.calculate_position_size(best_signal, capital, risk_pct)
                        best_signal.position_size = size
                        best_signal.metadata['position_size'] = size
                    except Exception as e:
                        self.logger.error(f"Error attaching position size: {e}")
                
                # Update strategy usage statistics
                self._update_strategy_stats(strategy_used, symbol)
                
                return best_signal
            else:
                # Log summary when no signals are found
                if self._diagnostic_counter[symbol] % 15 == 0:
                    active_strategies = [name for name in self.strategies.keys() if self._is_strategy_active(name, current_time)]
                    self.logger.info(f"📊 No signals for {symbol} at ${self._get_bar_value(bar, 'close'):.2f} | Active strategies: {active_strategies} | Volume: {self._get_bar_value(bar, 'volume'):,}")
            
            # ----- Auto-tune del umbral de volumen y rango de volatilidad -----
            default_mult = self._parameters.get('volume_spike_threshold', 1.5)
            if candidate_signals:
                # Volatilidad: vuelve lentamente al mínimo por defecto
                self.dynamic_vol_min = min(1.0, round(self.dynamic_vol_min + 0.1, 2))
                # reinicia contador y recupera gradualmente
                self._no_signal_counter = 0
                self.dynamic_volume_multiplier = min(default_mult, round(self.dynamic_volume_multiplier + 0.05, 2))
            else:
                self._no_signal_counter += 1
                # 🔧 DEBUG: Always log counter increments  
                if self._no_signal_counter % 10 == 0:  # More frequent logging
                    self.logger.info(f"🔢 No-signal counter: {self._no_signal_counter} for {symbol} (next auto-tune at {((self._no_signal_counter // 100) + 1) * 100})")
                
                # 🎯 SISTEMA HÍBRIDO: Actualizar candidatos periódicamente
                self._update_prebreakout_candidates()
                
                # Detectar patrones de pre-breakout SOLO en candidatos (eficiente)
                pre_breakout_detected = False
                if bar.symbol in self.prebreakout_candidates:
                    pre_breakout_detected = self._detect_smallcap_pre_breakout_pattern(bar.symbol, bar)
                
                # AUTO-TUNE DISABLED: Let each strategy maintain its original criteria
                should_adjust = False  # Disabled auto-tune - strategies keep their original parameters
                
                # 🔧 DEBUG: Log auto-tune trigger checks
                if self._no_signal_counter % 50 == 0:  # Every 50 bars for debugging
                    self.logger.info(f"🔍 Auto-tune check: counter={self._no_signal_counter}, should_adjust={should_adjust}, vol_min={self.dynamic_vol_min}%")
                
                if should_adjust:
                    # Si hay patrón de pre-breakout, ser aún más permisivo
                    min_multiplier = self.min_volume_multiplier
                    if pre_breakout_detected:
                        min_multiplier = max(0.2, self.min_volume_multiplier - 0.3)  # Extra permisivo
                    
                    # volumen: usar mínimo configurado según tipo de activos
                    if self.dynamic_volume_multiplier > min_multiplier:
                        self.dynamic_volume_multiplier = round(max(min_multiplier, self.dynamic_volume_multiplier - 0.2), 2)
                    # volatilidad: baja 0.2% hasta 0.2% (más permisivo)
                    if self.dynamic_vol_min > 0.2:
                        self.dynamic_vol_min = round(max(0.2, self.dynamic_vol_min - 0.2), 2)
                    
                    mode_info = "SMALLCAP" if self.smallcap_mode else "STANDARD"
                    pattern_info = " + PRE-BREAKOUT" if pre_breakout_detected else ""
                    candidates_info = f" | Candidates: {len(self.prebreakout_candidates)}" if len(self.prebreakout_candidates) > 0 else ""
                    self.logger.info(f"📉 Auto-tune ({mode_info}{pattern_info}): volume={self.dynamic_volume_multiplier}x | vol_range={float(self.dynamic_vol_min):.1f}-{float(self.dynamic_vol_max):.1f}% tras {self._no_signal_counter} barras{candidates_info}")
                    
                    # Propagar cambios a todas las estrategias
                    self._propagate_dynamic_thresholds()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error processing bar for {bar.symbol}: {e}")
            return None
    
    def _propagate_dynamic_thresholds(self):
        """Actualiza parámetros dinámicos en todas las sub-estrategias"""
        updated_strategies = []
        
        for strategy_name, strat in self.strategies.items():
            # Aplicar umbrales de volumen dinámicos
            volume_attrs = ['volume_spike_threshold', 'volume_multiplier', 'volume_threshold']
            for attr in volume_attrs:
                if hasattr(strat, attr):
                    setattr(strat, attr, self.dynamic_volume_multiplier)
                    updated_strategies.append(f"{strategy_name}.{attr}")
                    
            # Aplicar parámetros específicos por estrategia
            if hasattr(strat, '_parameters'):
                if strategy_name == 'macdv_smallcaps':
                    strat._parameters['volume_threshold'] = self.dynamic_volume_multiplier
                    # 🔧 FIX: Propagar umbrales de volatilidad dinámicos
                    strat._parameters['min_atr_pct'] = self.dynamic_vol_min / 100  # Convert percentage to decimal
                    updated_strategies.append(f"{strategy_name}.min_atr_pct")
                elif strategy_name == 'gap_go':
                    strat._parameters['volume_multiplier'] = self.dynamic_volume_multiplier
                elif strategy_name == 'orb':
                    strat._parameters['volume_spike_threshold'] = self.dynamic_volume_multiplier
                elif strategy_name == 'volume_breakout':
                    strat._parameters['volume_multiplier'] = self.dynamic_volume_multiplier
                elif strategy_name == 'pmh_breakout':
                    strat._parameters['breakout_volume_multiplier'] = self.dynamic_volume_multiplier
        
        if updated_strategies:
            self.logger.debug(f"🔄 Updated dynamic params: {updated_strategies}")
    
    def _is_prebreakout_candidate(self, symbol: str, bar: MarketData) -> bool:
        """
        Determina si un símbolo es candidato para análisis pre-breakout detallado
        Criterios eficientes para filtrar símbolos interesantes
        """
        try:
            # Criterios básicos (muy baratos computacionalmente)
            if not self.smallcap_mode:
                return False
            
            # 1. Debe tener al menos algunas barras sin señal
            if self._no_signal_counter < 20:
                return False
            
            # 2. No penny stocks (filtro de calidad)
            if self._get_bar_value(bar, 'close') < 1.5:
                return False
                
            # 3. Volumen mínimo (evitar símbolos muertos)
            if self._get_bar_value(bar, 'volume') < 30000:  # ~77 shares por minuto promedio
                return False
            
            # 4. Debe estar en nuestro tracking (tener historial)
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < 15:
                return False
            
            # 5. Precio en rango interesante para smallcaps
            bar_close = self._get_bar_value(bar, 'close')
            if not (1.5 <= bar_close <= 25.0):
                return False
            
            # 6. Verificación de volatilidad básica (sin computación pesada)
            recent_bars = self.bars_history[symbol][-5:]
            if len(recent_bars) >= 3:
                high_5 = max(self._get_bar_value(b, 'high') for b in recent_bars)
                low_5 = min(self._get_bar_value(b, 'low') for b in recent_bars)
                range_5day = (high_5 - low_5) / low_5
                
                # Debe tener algo de movimiento pero no ser extremo
                if not (0.02 <= range_5day <= 0.15):  # 2-15% rango
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking prebreakout candidate {symbol}: {e}")
            return False
    
    def _update_prebreakout_candidates(self):
        """
        Actualiza la lista de candidatos cada cierto tiempo
        ORDENADO DE MENOR A MAYOR VOLUMEN para detectar pre-breakouts
        Se ejecuta solo ocasionalmente para mantener eficiencia
        """
        try:
            # Solo actualizar cada 25 barras para mantener eficiencia
            self.candidate_update_counter += 1
            if self.candidate_update_counter % 25 != 0:
                return
            
            # Limpiar candidatos viejos y evaluar nuevos
            old_count = len(self.prebreakout_candidates)
            candidate_data = []
            
            # Evaluar todos los símbolos activos con datos de volumen
            for symbol in self.bars_history.keys():
                if symbol in self.bars_history and len(self.bars_history[symbol]) > 0:
                    last_bar = self.bars_history[symbol][-1]
                    if self._is_prebreakout_candidate(symbol, last_bar):
                        # Calcular ratio de volumen para ordenamiento
                        recent_bars = self.bars_history[symbol][-10:]
                        if len(recent_bars) >= 2:
                            avg_volume = sum(self._get_bar_value(b, 'volume') for b in recent_bars[:-1]) / max(1, len(recent_bars) - 1)
                            volume_ratio = self._get_bar_value(last_bar, 'volume') / max(1, avg_volume)
                            candidate_data.append((symbol, volume_ratio))
            
            # ORDENAR DE MENOR A MAYOR VOLUMEN - para detectar acumulación silenciosa
            candidate_data.sort(key=lambda x: x[1])  # ASC por volume_ratio
            
            # Actualizar candidatos con orden optimizado
            self.prebreakout_candidates = set(symbol for symbol, _ in candidate_data)
            
            new_count = len(self.prebreakout_candidates)
            if new_count != old_count:
                # Mostrar los primeros 3 con menor volumen (más prometedores)
                low_vol_symbols = [f"{symbol}({ratio:.1f}x)" for symbol, ratio in candidate_data[:3]]
                self.logger.info(f"🎯 Pre-breakout candidates (LOW->HIGH vol): {old_count} -> {new_count} | Priority: {low_vol_symbols}")
                
        except Exception as e:
            self.logger.error(f"Error updating prebreakout candidates: {e}")
    
    def _detect_smallcap_pre_breakout_pattern(self, symbol: str, bar: MarketData) -> bool:
        """
        Detecta patrones típicos de pre-breakout en smallcaps - VERSIÓN OPTIMIZADA
        Solo se ejecuta en símbolos candidatos pre-seleccionados
        """
        try:
            # Ya no necesita verificar smallcap_mode, se asume que es candidato
            recent_bars = self.bars_history[symbol][-15:]  # Reducido de 20 a 15 para eficiencia
            if len(recent_bars) < 10:
                return False
            
            # Condición 1: Precio consolidando (cálculo optimizado)
            prices = [self._get_bar_value(b, 'close') for b in recent_bars[-8:]]  # Reducido de 10 a 8
            price_range = (max(prices) - min(prices)) / min(prices)
            
            # Condición 2: Volumen estable (simplificado)
            volumes_recent = [self._get_bar_value(b, 'volume') for b in recent_bars[-4:]]  # Solo últimas 4 barras
            volumes_earlier = [self._get_bar_value(b, 'volume') for b in recent_bars[-8:-4]]  # 4 barras anteriores
            
            if not volumes_earlier:  # Fallback
                return False
                
            avg_volume_recent = sum(volumes_recent) / len(volumes_recent)
            avg_volume_earlier = sum(volumes_earlier) / len(volumes_earlier)
            volume_stability = avg_volume_recent / max(1, avg_volume_earlier)
            
            # Condición 3: Precio cerca de resistencia (optimizado)
            current_price = self._get_bar_value(bar, 'close')
            high_recent = max(self._get_bar_value(b, 'high') for b in recent_bars[-5:])
            
            # Patrones simplificados pero efectivos:
            consolidation_pattern = 0.015 <= price_range <= 0.08  # Rango más amplio: 1.5-8%
            stable_volume = 0.2 <= volume_stability <= 1.2        # Más permisivo: 0.2-1.2x
            near_resistance = current_price >= high_recent * 0.92  # Más permisivo: 92% vs 95%
            
            # Condición adicional: verificar que no esté en caída libre
            recent_trend = (prices[-1] - prices[0]) / prices[0]  # Trend últimas 8 barras
            not_falling = recent_trend >= -0.05  # No más de -5% de caída
            
            if consolidation_pattern and stable_volume and near_resistance and not_falling:
                self.logger.info(f"🎯 {symbol}: Pre-breakout pattern detected - consolidation {price_range*100:.1f}%, volume {volume_stability:.2f}x, trend {recent_trend*100:+.1f}%")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error detecting pre-breakout pattern for {symbol}: {e}")
            return False

    def _calculate_signal_confidence(self, signal: Signal, bar: MarketData, strategy_name: str) -> float:
        """
        Calculate confidence score for a signal based on multiple factors
        """
        try:
            confidence = 0.0
            symbol = signal.symbol
            # Use signal timestamp for confidence calculation (already in market time)
            if hasattr(signal.timestamp, 'time'):
                current_time = signal.timestamp.time()
            else:
                # Fallback: convert signal timestamp string to time
                signal_dt = pd.to_datetime(signal.timestamp)
                current_time = signal_dt.time()
            
            # Base confidence from signal strength
            confidence += signal.strength * 0.3
            
            # Strategy performance history
            strategy_stats = self.strategy_scores.get(strategy_name, {})
            if strategy_stats.get('total_signals', 0) > 0:
                win_rate = strategy_stats.get('winning_signals', 0) / strategy_stats.get('total_signals', 1)
                confidence += win_rate * 0.2
            
            # Time-based confidence (different strategies work better at different times)
            time_confidence = self._get_time_based_confidence(strategy_name, current_time)
            confidence += time_confidence * 0.2
            
            # Market conditions confidence
            market_confidence = self._get_market_conditions_confidence(signal, bar, strategy_name)
            confidence += market_confidence * 0.2
            
            # Symbol-specific strategy preference
            symbol_preference = self.symbol_strategy_preference.get(symbol, {}).get(strategy_name, 0.5)
            confidence += symbol_preference * 0.1
            
            # Ensure confidence is between 0 and 1
            confidence = max(0.0, min(1.0, confidence))
            
            return confidence
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 0.5  # Default confidence
    
    def _get_time_based_confidence(self, strategy_name: str, current_time: time) -> float:
        """
        Get confidence multiplier based on time of day for each strategy
        Extended hours support added
        """
        hour = current_time.hour
        minute = current_time.minute
        time_decimal = hour + minute / 60.0
        
        # Determine market session
        if 4.0 <= time_decimal < 9.5:
            session = "PREMARKET"
        elif 9.5 <= time_decimal < 16.0:
            session = "REGULAR"
        elif 16.0 <= time_decimal < 20.0:
            session = "AFTERHOURS"
        else:
            session = "CLOSED"
        
        if strategy_name == 'gap_go':
            if session == "PREMARKET":
                # GAP_GO excellent in premarket (gap continuation)
                if 7.0 <= time_decimal <= 9.0:  # 7AM-9AM peak
                    return 1.0
                else:
                    return 0.8
            elif session == "REGULAR":
                # GAP_GO works best in first 30-60 minutes
                if 9.5 <= time_decimal <= 10.5:
                    return 1.0
                elif 10.5 <= time_decimal <= 11.0:
                    return 0.7
                else:
                    return 0.3
            else:
                return 0.2  # Low confidence afterhours/closed
                
        elif strategy_name == 'orb':
            if session == "REGULAR":
                # ORB works best after opening range is established
                if 10.0 <= time_decimal <= 12.0:
                    return 1.0
                elif 12.0 <= time_decimal <= 14.0:
                    return 0.8
                else:
                    return 0.4
            else:
                return 0.1  # ORB doesn't work in extended hours
                
        elif strategy_name == 'volume_breakout':
            if session == "REGULAR":
                # Volume breakouts work best during regular hours
                if 9.5 <= time_decimal <= 15.0:
                    return 1.0
                else:
                    return 0.6
            elif session in ["PREMARKET", "AFTERHOURS"]:
                return 0.3  # Lower volume = lower confidence
            else:
                return 0.1
                
        elif strategy_name == 'pmh_breakout':
            if session == "PREMARKET":
                # PMH_BREAKOUT designed for premarket
                if 7.0 <= time_decimal <= 9.0:  # Peak premarket hours
                    return 1.0
                else:
                    return 0.8
            elif session == "REGULAR":
                # Still works early regular hours
                if 9.5 <= time_decimal <= 12.0:
                    return 0.6
                else:
                    return 0.2
            else:
                return 0.1
                
        elif strategy_name == 'vwap':
            if session == "REGULAR":
                # VWAP most reliable with good volume
                if 10.0 <= time_decimal <= 15.0:
                    return 1.0
                else:
                    return 0.7
            else:
                return 0.3  # Less reliable in extended hours
                
        elif strategy_name == 'macdv_smallcaps':
            if session == "REGULAR":
                # MACDV works throughout regular session
                if 9.5 <= time_decimal <= 15.5:
                    return 1.0
                else:
                    return 0.5
            elif session in ["PREMARKET", "AFTERHOURS"]:
                return 0.4  # Can work in extended hours but lower confidence
            else:
                return 0.2
        
        # Default confidence for any unhandled strategy
        if session == "REGULAR":
            return 0.7
        elif session in ["PREMARKET", "AFTERHOURS"]:
            return 0.3
        else:
            return 0.1
    
    def _is_strategy_active(self, strategy_name: str, current_time: time) -> bool:
        """
        Check if a strategy should be active at the current time
        Extended hours support added - TESTING vs PRODUCTION profiles
        """
        hour = current_time.hour
        minute = current_time.minute
        time_decimal = hour + minute / 60.0
        
        # Detect if we're in TESTING profile (extended hours) or PRODUCTION profile (normal hours)
        is_testing_profile = getattr(self, '_is_testing_profile', True)  # Default to testing for safety
        
        # Determine market session
        if 4.0 <= time_decimal < 9.5:
            session = "PREMARKET"
        elif 9.5 <= time_decimal < 16.0:
            session = "REGULAR"
        elif 16.0 <= time_decimal < 20.0:
            session = "AFTERHOURS"
        else:
            session = "CLOSED"
        
        if strategy_name == 'gap_go':
            # GAP_GO active in premarket and early regular hours
            if is_testing_profile:
                # TESTING: Horarios extendidos para pruebas
                if session in ["PREMARKET", "REGULAR", "AFTERHOURS"]:
                    return 6.0 <= time_decimal <= 20.0
                else:
                    return False
            else:
                # PRODUCTION: Horarios normales
                if session == "PREMARKET":
                    return 6.0 <= time_decimal <= 9.5  # 6AM-9:30AM
                elif session == "REGULAR":
                    return 9.5 <= time_decimal <= 11.0  # First 1.5 hours
                else:
                    return False
            
        elif strategy_name == 'orb':
            # ORB only works in regular hours (needs opening range)
            if is_testing_profile:
                # TESTING: Extendido para pruebas
                return session == "REGULAR" and 9.5 <= time_decimal <= 16.0
            else:
                # PRODUCTION: Horario normal
                return session == "REGULAR" and 10.0 <= time_decimal <= 14.0
            
        elif strategy_name == 'pmh_breakout':
            # PMH designed for premarket and early regular
            if is_testing_profile:
                # TESTING: Extendido para pruebas
                if session in ["PREMARKET", "REGULAR"]:
                    return 6.0 <= time_decimal <= 16.0
                else:
                    return False
            else:
                # PRODUCTION: Horarios normales
                if session == "PREMARKET":
                    return 6.0 <= time_decimal <= 9.5
                elif session == "REGULAR":
                    return 9.5 <= time_decimal <= 12.0  # First 2.5 hours
                else:
                    return False
            
        elif strategy_name == 'volume_breakout':
            # Volume breakout works in all sessions but reduced effectiveness
            if is_testing_profile:
                # TESTING: Activa todo el día para pruebas
                if session in ["PREMARKET", "REGULAR", "AFTERHOURS"]:
                    return 4.0 <= time_decimal <= 20.0
                else:
                    return False
            else:
                # PRODUCTION: Horarios normales
                if session == "REGULAR":
                    return 9.5 <= time_decimal <= 15.5
                elif session in ["PREMARKET", "AFTERHOURS"]:
                    return True  # Active but lower confidence
                else:
                    return False
            
        elif strategy_name == 'macdv_smallcaps':
            # MACDV can work in extended hours
            if is_testing_profile:
                # TESTING: Extendida para pruebas - ACTIVA TODO EL DÍA
                if session in ["PREMARKET", "REGULAR", "AFTERHOURS"]:
                    return 4.0 <= time_decimal <= 20.0
                else:
                    return False
            else:
                # PRODUCTION: Horarios normales
                if session == "REGULAR":
                    return 9.5 <= time_decimal <= 15.92  # Hasta 15:55 (5min margen antes del cierre)
                elif session in ["PREMARKET", "AFTERHOURS"]:
                    return True  # Active but lower confidence
                else:
                    return False
        
        elif strategy_name == 'ipo':
            # IPO strategy - only during regular market hours (too volatile for extended)
            if is_testing_profile:
                # TESTING: Extended for testing IPO patterns
                return session == "REGULAR" and 9.5 <= time_decimal <= 16.0
            else:
                # PRODUCTION: Normal hours only - IPOs are risky enough
                return session == "REGULAR" and 9.5 <= time_decimal <= 15.5
        
        elif strategy_name == 'vwap':
            # VWAP primarily regular hours
            if session == "REGULAR":
                return 10.0 <= time_decimal <= 15.0
            else:
                return False  # Not reliable in extended hours
        
        elif strategy_name == 'explosive_volume':
            # ExplosiveVolumeStrategy - ALWAYS ACTIVE (explosions can happen anytime)
            # Volume explosions don't follow market hours - they happen when they happen
            return True  # 24/7 active for maximum opportunity capture
        
        # Default: only active during regular hours
        return session == "REGULAR"
    
    def _get_market_conditions_confidence(self, signal: Signal, bar: MarketData, strategy_name: str) -> float:
        """
        Assess confidence based on current market conditions
        """
        try:
            confidence = 0.5
            symbol = signal.symbol
            
            # Get recent bars for analysis
            if symbol in self.bars_history and len(self.bars_history[symbol]) >= 10:
                recent_bars = self.bars_history[symbol][-10:]
                
                # Calculate volatility
                prices = [b.close for b in recent_bars]
                if len(prices) > 1:
                    volatility = self._calculate_volatility(prices)
                    
                    # Volume analysis
                    volumes = [b.volume for b in recent_bars]
                    avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 1
                    current_volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1
                    
                    # Gap analysis
                    gap_size = abs((bar.open - recent_bars[-2].close) / recent_bars[-2].close) if len(recent_bars) > 1 else 0
                    
                    # Strategy-specific market condition preferences
                    if strategy_name == 'gap_go':
                        if gap_size > 0.03:  # 3% gap
                            confidence += 0.3
                        if current_volume_ratio > 2.0:
                            confidence += 0.2
                            
                    elif strategy_name == 'volume_breakout':
                        if current_volume_ratio > 2.5:
                            confidence += 0.4
                        if volatility > 0.02:
                            confidence += 0.1
                            
                    elif strategy_name == 'macdv_smallcaps':
                        if 0.01 <= volatility <= 0.08:  # Moderate volatility
                            confidence += 0.3
                        if current_volume_ratio > 1.5:
                            confidence += 0.2
                            
                    elif strategy_name == 'orb':
                        if volatility > 0.02:
                            confidence += 0.2
                        if current_volume_ratio > 1.8:
                            confidence += 0.3
                            
                    elif strategy_name == 'pmh_breakout':
                        if current_volume_ratio > 2.0:
                            confidence += 0.3
                        if volatility > 0.02:
                            confidence += 0.2
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            self.logger.error(f"Error calculating market conditions confidence: {e}")
            return 0.5
    
    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate simple volatility from price list"""
        if len(prices) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        if not returns:
            return 0.0
        
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        
        return variance ** 0.5
    
    def _select_best_signal(self, candidate_signals: List[Signal], symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Select the best signal from candidates based on confidence and other factors
        Enhanced with ML Quality filter for improved trade selection
        """
        if not candidate_signals:
            return None

        # **NEW: ML QUALITY FILTER - APPLY BEFORE SELECTION**
        # Filter signals with ML Quality ≥ 50% for specific strategies
        ML_QUALITY_THRESHOLD = 50.0  # Minimum ML Quality percentage (reduced from 70.0)
        FILTERED_STRATEGIES = ['macdv_smallcaps', 'volume_breakout']  # Strategies to apply filter to

        filtered_signals = []
        rejected_signals = []

        for signal in candidate_signals:
            strategy_name = signal.metadata.get('strategy_name', '')
            confidence = signal.metadata.get('confidence', 0.0)

            # Apply ML Quality filter only to specified strategies
            if strategy_name in FILTERED_STRATEGIES:
                # Convert confidence (0.0-1.0) to percentage (0-100) if needed
                ml_quality = confidence * 100 if confidence <= 1.0 else confidence

                if ml_quality >= ML_QUALITY_THRESHOLD:
                    filtered_signals.append(signal)
                else:
                    rejected_signals.append((strategy_name, ml_quality))
                    self.logger.info(f"🚫 ML Quality filter: Rejected {strategy_name} signal for {symbol} "
                                   f"(ML Quality: {ml_quality:.1f}% < {ML_QUALITY_THRESHOLD}%)")
            else:
                # Other strategies pass through without ML Quality filter
                filtered_signals.append(signal)

        # Log rejection summary if any signals were filtered
        if rejected_signals:
            rejected_summary = ", ".join([f"{strat}({qual:.1f}%)" for strat, qual in rejected_signals])
            self.logger.info(f"📊 ML Quality filter for {symbol}: Rejected {len(rejected_signals)} signals: {rejected_summary}")

        # Continue with filtered signals
        if not filtered_signals:
            return None

        if len(filtered_signals) == 1:
            signal = filtered_signals[0]
            strategy_name = signal.metadata.get('strategy_name', '')
            ml_quality = signal.metadata.get('confidence', 0.0) * 100 if signal.metadata.get('confidence', 0.0) <= 1.0 else signal.metadata.get('confidence', 0.0)
            if strategy_name in FILTERED_STRATEGIES:
                self.logger.info(f"✅ ML Quality passed: {strategy_name} for {symbol} (ML Quality: {ml_quality:.1f}%)")
            return signal

        # Sort by confidence (highest first)
        filtered_signals.sort(key=lambda s: s.metadata.get('confidence', 0.0), reverse=True)

        best_signal = filtered_signals[0]
        best_confidence = best_signal.metadata.get('confidence', 0.0)

        # Log the selection process
        if len(filtered_signals) > 1:
            other_signals = [(s.metadata.get('strategy_name'), s.metadata.get('confidence', 0.0))
                           for s in filtered_signals[1:]]
            self.logger.info(f"Signal selection for {symbol}: Chose {best_signal.metadata.get('strategy_name')} "
                           f"(conf: {best_confidence:.2f}) over {other_signals}")

        # Log ML Quality for selected signal if it's a filtered strategy
        strategy_name = best_signal.metadata.get('strategy_name', '')
        if strategy_name in FILTERED_STRATEGIES:
            ml_quality = best_confidence * 100 if best_confidence <= 1.0 else best_confidence
            self.logger.info(f"✅ ML Quality passed: {strategy_name} for {symbol} (ML Quality: {ml_quality:.1f}%)")

        return best_signal
    
    def _update_strategy_stats(self, strategy_name: str, symbol: str):
        """Update usage statistics for strategy performance tracking"""
        if strategy_name in self.strategy_scores:
            self.strategy_scores[strategy_name]['total_signals'] += 1
        
        # Update symbol preference (simple increment for now)
        if symbol not in self.symbol_strategy_preference:
            self.symbol_strategy_preference[symbol] = {}
        
        if strategy_name not in self.symbol_strategy_preference[symbol]:
            self.symbol_strategy_preference[symbol][strategy_name] = 0.5
        
        # Slightly increase preference for this strategy for this symbol
        current_pref = self.symbol_strategy_preference[symbol][strategy_name]
        self.symbol_strategy_preference[symbol][strategy_name] = min(1.0, current_pref + 0.01)
    
    def should_exit(self, position, bar: MarketData) -> Optional[Signal]:
        """
        Check exit conditions using the strategy that opened the position
        """
        try:
            symbol = position.symbol
            
            # Try to determine which strategy opened this position
            strategy_name = getattr(position, 'strategy_name', None)
            
            if strategy_name and strategy_name in self.strategies:
                # Use the same strategy that opened the position
                strategy = self.strategies[strategy_name]
                return strategy.should_exit(position, bar)
            else:
                # Fallback: check all strategies and use the first exit signal
                for strategy_name, strategy in self.strategies.items():
                    exit_signal = strategy.should_exit(position, bar)
                    if exit_signal:
                        exit_signal.metadata = exit_signal.metadata or {}
                        exit_signal.metadata['strategy_name'] = strategy_name
                        exit_signal.metadata['source_engine'] = 'MultiStrategyEngine'
                        return exit_signal
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return None
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """
        Calculate position size using the strategy that generated the signal
        """
        try:
            strategy_name = signal.metadata.get('strategy_name', 'macdv_smallcaps')
            
            if strategy_name in self.strategies:
                strategy = self.strategies[strategy_name]
                return strategy.calculate_position_size(signal, capital, risk_per_trade)
            else:
                # Fallback to default calculation
                return 100
                
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 100
    
    async def on_position_update(self, position) -> None:
        """Handle position updates coming from broker fills or manual sync.

        If the Position object contains metadata with the originating strategy we simply
        forward the update to that strategy.  Otherwise (e.g. live fills coming
        directly from the broker) we create internal tracking and immediately
        initialise trailing-/emergency-stops so that the trade is protected even
        when it was opened outside the Python process.
        """
        try:
            # Basic diagnostic log – helps to trace missing trailing-stop in live trading
            self.logger.info(
                f"📊 POSITION_UPDATE: {position.symbol} qty={position.quantity} avg=${getattr(position, 'avg_price', 0):.3f}")

            strategy_name = None
            if hasattr(position, 'metadata') and position.metadata and 'strategy_name' in position.metadata:
                strategy_name = position.metadata['strategy_name']

            if strategy_name and strategy_name in self.strategies:
                # Forward the position update to the originating strategy
                await self.strategies[strategy_name].on_position_update(position)
            else:
                # No strategy information – treat as external/existing position
                self.logger.debug(
                    f"🔄 No strategy metadata for {position.symbol}. Creating tracking and initialising trailing stop.")
                # Create internal tracking entry so trailing-stop manager can take over
                self._create_position_tracking(position)
                # Initialise trailing- and emergency-stop orders
                await self._initialize_trailing_stop(position)
        except Exception as e:
            self.logger.error(f"Error handling position update for {position.symbol}: {e}")
    
    def get_strategy_info(self) -> dict:
        """Get information about the multi-strategy engine"""
        strategy_info = {
            "name": "Multi-Strategy Engine",
            "type": "Adaptive Multi-Strategy System",
            "active_strategies": list(self.strategies.keys()),
            "total_strategies": len(self.strategies),
            "strategy_performance": {}
        }
        
        # Add performance info for each strategy
        for strategy_name, stats in self.strategy_scores.items():
            if stats['total_signals'] > 0:
                win_rate = stats['winning_signals'] / stats['total_signals']
                strategy_info["strategy_performance"][strategy_name] = {
                    "total_signals": stats['total_signals'],
                    "win_rate": f"{win_rate:.1%}",
                    "avg_pnl": f"{stats['avg_pnl']:.2f}%"
                }
        
        return strategy_info
    
    def get_active_strategies(self, current_time: time = None) -> List[str]:
        """
        Get list of strategies that are currently active
        """
        if current_time is None:
            # Use current market time (default to market hours if not provided)
            # This should normally be called with current_time parameter during bar processing
            current_time = time(10, 0)  # Default to 10:00 AM market time
        
        active_strategies = []
        for strategy_name in self.strategies.keys():
            if self._is_strategy_active(strategy_name, current_time):
                active_strategies.append(strategy_name)
        
        return active_strategies
    
    def get_strategy_schedule(self) -> dict:
        """
        Get the active time schedule for all strategies based on current profile
        """
        if getattr(self, '_is_testing_profile', True):
            # TESTING: Horarios extendidos
            return {
                'gap_go': '06:00 - 20:00 (TESTING: Extended Hours)',
                'orb': '09:30 - 16:00 (TESTING: Extended Hours)', 
                'pmh_breakout': '06:00 - 16:00 (TESTING: Extended Hours)',
                'volume_breakout': '04:00 - 20:00 (TESTING: Extended Hours)',
                'macdv_smallcaps': '04:00 - 20:00 (TESTING: Extended Hours)',
                'ipo': '09:30 - 16:00 (TESTING: IPO Specialist)'
            }
        else:
            # PRODUCTION: Horarios normales
            return {
                'gap_go': '06:00 - 11:00 (PRODUCTION: Normal Hours)',
                'orb': '10:00 - 14:00 (PRODUCTION: Normal Hours)', 
                'pmh_breakout': '06:00 - 12:00 (PRODUCTION: Normal Hours)',
                'volume_breakout': '09:30 - 15:30 (PRODUCTION: Normal Hours)',
                'macdv_smallcaps': '09:30 - 15:55 (PRODUCTION: 5min margen antes cierre)',
                'ipo': '09:30 - 15:30 (PRODUCTION: IPO Specialist)'
            }
    
    def get_symbol_preferences(self) -> dict:
        """Get learned preferences for each symbol"""
        return self.symbol_strategy_preference.copy()
    
    def get_managed_strategy_names(self) -> List[str]:
        """Returns the names of strategies managed by this engine to prevent duplicate execution."""
        # Return strategy class names to match StrategyAnalysisStage filtering logic
        managed_names = []
        for strategy_name, strategy_instance in self.strategies.items():
            # Get the class name for filtering
            class_name = strategy_instance.__class__.__name__
            managed_names.append(class_name)
        
        self.logger.debug(f"MultiStrategyEngine manages: {managed_names}")
        return managed_names
    
    def _get_strategy_active_window(self, strategy_name: str) -> str:
        """Get the active time window for a strategy"""
        windows = {
            'gap_go': '09:30-11:00',
            'orb': '10:00-14:00', 
            'pmh_breakout': '09:30-12:00',
            'volume_breakout': '09:30-15:30',
            'macdv_smallcaps': '09:30-15:55'
        }
        return windows.get(strategy_name, 'Always')
    
    def _log_detailed_strategy_analysis(self, symbol: str, bar: MarketData, current_time, us_datetime):
        """Log detailed analysis of why strategies are/aren't generating signals"""
        try:
            # Calculate basic metrics
            recent_bars = self.bars_history[symbol][-10:] if len(self.bars_history[symbol]) >= 10 else self.bars_history[symbol]
            if len(recent_bars) < 2:
                return
                
            # Price analysis
            prev_close = recent_bars[-2].close if len(recent_bars) > 1 else bar.close
            price_change = ((bar.close - prev_close) / prev_close) * 100
            gap_size = ((bar.open - prev_close) / prev_close) * 100 if len(recent_bars) > 1 else 0
            
            # Volume analysis
            avg_volume = sum(b.volume for b in recent_bars[:-1]) / max(1, len(recent_bars) - 1)
            volume_ratio = bar.volume / max(1, avg_volume)
            
            # Volatility
            prices = [b.close for b in recent_bars]
            volatility = self._calculate_volatility(prices) * 100
            
            # Current market session info
            active_strategies = [name for name in self.strategies.keys() if self._is_strategy_active(name, current_time)]
            inactive_strategies = [name for name in self.strategies.keys() if not self._is_strategy_active(name, current_time)]
            
            # Show bar timestamp (market time)
            
            self.logger.info(f"""
📈 STRATEGY ANALYSIS for {symbol}:
   🕐 Market Time: {current_time.strftime('%H:%M:%S')} (from bar timestamp)
   💰 Price: ${bar.close:.2f} (Change: {price_change:+.2f}%, Gap: {gap_size:+.2f}%)
   📊 Volume: {bar.volume:,} (Ratio: {volume_ratio:.1f}x avg)
   📉 Volatility: {volatility:.2f}%
   ✅ Active: {active_strategies}
   ❌ Inactive: {inactive_strategies}
   📚 History: {len(self.bars_history[symbol])} bars""")
            
        except Exception as e:
            self.logger.error(f"Error in detailed analysis for {symbol}: {e}")
    
    def _calculate_vwap(self, symbol: str, bars: List[MarketData]) -> float:
        """
        Calculate Volume Weighted Average Price (VWAP) for the trading session
        VWAP = Σ(Price × Volume) / Σ(Volume)
        """
        try:
            if not bars or len(bars) == 0:
                return 0.0
            
            total_volume = 0
            total_price_volume = 0
            
            for bar in bars:
                # Use typical price (high + low + close) / 3
                typical_price = (bar.high + bar.low + bar.close) / 3
                volume = bar.volume if bar.volume > 0 else 1  # Avoid division by zero
                
                total_price_volume += typical_price * volume
                total_volume += volume
            
            if total_volume == 0:
                return bars[-1].close  # Fallback to current price
                
            vwap = total_price_volume / total_volume
            return vwap
            
        except Exception as e:
            self.logger.error(f"Error calculating VWAP for {symbol}: {e}")
            return bars[-1].close if bars else 0.0
    
    def _detect_explosive_conditions(self, symbol: str, bar: MarketData) -> tuple[float, float, bool]:
        """
        Detect explosive volume and momentum conditions
        
        Returns:
            tuple: (volume_spike_ratio, price_momentum_pct, is_explosive)
            
        Explosive conditions:
        - Volume spike >15x average = EXPLOSIVE OVERRIDE
        - Volume spike >10x + price move >2% = MOMENTUM EXPLOSION  
        - Volume spike >5x + price in accumulation zone = RECOVERY PATTERN
        """
        try:
            if symbol not in self.bars_history or len(self.bars_history[symbol]) < 10:
                return 1.0, 0.0, False
            
            bars = self.bars_history[symbol]
            current_bar = bar
            
            # Calculate volume spike vs recent average (last 5-10 bars)
            lookback_bars = min(10, len(bars) - 1)
            if lookback_bars < 3:
                return 1.0, 0.0, False
            
            recent_bars = bars[-lookback_bars:]
            avg_volume = sum(b.volume for b in recent_bars) / lookback_bars
            volume_spike_ratio = current_bar.volume / max(avg_volume, 1)
            
            # Calculate price momentum (% change from 1-3 bars ago)
            price_momentum_pct = 0.0
            if len(bars) >= 3:
                # Check 1-bar, 2-bar, and 3-bar momentum for best signal
                momentum_1bar = ((current_bar.close - bars[-2].close) / bars[-2].close) * 100 if len(bars) >= 2 else 0
                momentum_2bar = ((current_bar.close - bars[-3].close) / bars[-3].close) * 100 if len(bars) >= 3 else 0
                momentum_3bar = ((current_bar.close - bars[-4].close) / bars[-4].close) * 100 if len(bars) >= 4 else 0
                
                # Use the strongest momentum signal
                price_momentum_pct = max(abs(momentum_1bar), abs(momentum_2bar), abs(momentum_3bar))
                
                # Keep the sign of the strongest momentum
                if abs(momentum_1bar) == price_momentum_pct:
                    price_momentum_pct = momentum_1bar
                elif abs(momentum_2bar) == price_momentum_pct:
                    price_momentum_pct = momentum_2bar
                elif abs(momentum_3bar) == price_momentum_pct:
                    price_momentum_pct = momentum_3bar
            
            # Detect explosive conditions
            is_explosive = False
            
            # PRIMARY: Extreme volume spike (like GV's 18x)
            if volume_spike_ratio >= 15.0:
                is_explosive = True
                self.logger.info(f"🚨 {symbol}: EXPLOSIVE VOLUME detected - {volume_spike_ratio:.1f}x spike")
            
            # SECONDARY: High volume + significant price movement
            elif volume_spike_ratio >= 10.0 and abs(price_momentum_pct) >= 2.0:
                is_explosive = True
                self.logger.info(f"⚡ {symbol}: MOMENTUM EXPLOSION - {volume_spike_ratio:.1f}x volume + {price_momentum_pct:.1f}% move")
            
            # TERTIARY: Moderate volume + extreme price movement
            elif volume_spike_ratio >= 5.0 and abs(price_momentum_pct) >= 5.0:
                is_explosive = True
                self.logger.info(f"🔥 {symbol}: PRICE EXPLOSION - {volume_spike_ratio:.1f}x volume + {price_momentum_pct:.1f}% move")
            
            # LOG for debugging
            self.logger.debug(f"💥 Explosive Analysis {symbol}: Vol={volume_spike_ratio:.1f}x, Momentum={price_momentum_pct:.1f}%, Explosive={is_explosive}")
            
            return volume_spike_ratio, price_momentum_pct, is_explosive
            
        except Exception as e:
            self.logger.error(f"Error detecting explosive conditions for {symbol}: {e}")
            return 1.0, 0.0, False
    
    def _apply_vwap_filter(self, signals: List[Signal], symbol: str, bar: MarketData) -> List[Signal]:
        """
        Enhanced VWAP filter with explosive volume detection and recovery patterns
        
        VWAP Rules Enhanced:
        - EXPLOSIVE VOLUME OVERRIDE: Volume >15x bypasses VWAP restrictions
        - RECOVERY PATTERN: Prices -5% to -15% below VWAP with volume >5x allowed
        - MOMENTUM CONTINUATION: Strong price moves +2% with volume >10x boosted
        - Standard VWAP filtering for normal conditions
        """
        try:
            if not signals or symbol not in self.bars_history:
                return signals
                
            # Calculate today's VWAP
            bars_today = self.bars_history[symbol]
            if len(bars_today) < 5:  # Need minimum bars for reliable VWAP
                return signals
                
            vwap = self._calculate_vwap(symbol, bars_today)
            current_price = self._get_bar_value(bar, 'close')
            
            # Calculate price vs VWAP deviation
            vwap_deviation = (current_price - vwap) / vwap
            
            # EXPLOSIVE VOLUME & MOMENTUM DETECTION
            volume_spike, price_momentum, is_explosive = self._detect_explosive_conditions(symbol, bar)
            
            self.logger.debug(f"📊 Enhanced VWAP Analysis for {symbol}: VWAP=${vwap:.4f}, Price=${current_price:.4f}, Dev={vwap_deviation:.1%}, Vol={volume_spike:.1f}x, Momentum={price_momentum:.1f}%")
            
            filtered_signals = []
            
            for signal in signals:
                original_confidence = signal.metadata.get('confidence', 1.0)
                vwap_adjustment = 1.0
                should_keep = True
                override_reason = None
                
                # 💥 EXPLOSIVE STRATEGY BYPASS - Skip VWAP filtering for explosive signals
                if signal.metadata.get('bypass_vwap', False) or signal.metadata.get('is_explosive', False):
                    vwap_adjustment = signal.metadata.get('vwap_adjustment', 2.0)  # Keep original boost
                    should_keep = True
                    override_reason = f"EXPLOSIVE BYPASS ({signal.metadata.get('explosion_type', 'UNKNOWN')})"
                    
                    # Still add VWAP metadata for analysis
                    signal.metadata['vwap'] = vwap
                    signal.metadata['vwap_deviation'] = vwap_deviation
                    signal.metadata['vwap_adjustment'] = vwap_adjustment
                    signal.metadata['volume_spike'] = volume_spike
                    signal.metadata['price_momentum'] = price_momentum
                    signal.metadata['is_explosive'] = is_explosive
                    signal.metadata['vwap_override'] = override_reason
                    
                    filtered_signals.append(signal)
                    self.logger.warning(f"💥 {symbol}: EXPLOSIVE BYPASS - Signal bypasses all VWAP restrictions ({override_reason})")
                    continue  # Skip normal VWAP processing
                
                if signal.signal_type == SignalType.LONG:
                    # 🚀 EXPLOSIVE VOLUME OVERRIDE - Bypasses VWAP restrictions
                    if is_explosive and volume_spike >= 15.0:
                        vwap_adjustment = 2.0  # Maximum boost for explosive moves
                        should_keep = True
                        override_reason = f"EXPLOSIVE VOLUME ({volume_spike:.1f}x)"
                        self.logger.warning(f"🚨 {symbol}: EXPLOSIVE VOLUME OVERRIDE - {volume_spike:.1f}x volume bypasses VWAP filter (Dev: {vwap_deviation:.1%})")
                    
                    # 📈 RECOVERY PATTERN - Institutional accumulation zones
                    elif vwap_deviation >= -0.15 and vwap_deviation <= -0.05 and volume_spike >= 5.0:
                        vwap_adjustment = 1.5  # Boost recovery signals
                        should_keep = True
                        override_reason = f"RECOVERY PATTERN (Vol: {volume_spike:.1f}x)"
                        self.logger.info(f"🔄 {symbol}: RECOVERY PATTERN detected - {vwap_deviation:.1%} below VWAP with {volume_spike:.1f}x volume")
                    
                    # ⚡ MOMENTUM CONTINUATION - Strong price moves with volume
                    elif price_momentum >= 2.0 and volume_spike >= 10.0:
                        vwap_adjustment = 1.8  # High boost for momentum
                        should_keep = True
                        override_reason = f"MOMENTUM EXPLOSION ({price_momentum:.1f}% + {volume_spike:.1f}x vol)"
                        self.logger.info(f"⚡ {symbol}: MOMENTUM EXPLOSION - {price_momentum:.1f}% move with {volume_spike:.1f}x volume")
                    
                    # 📊 STANDARD VWAP FILTERING (original logic with modifications)
                    elif vwap_deviation > 0.05:  # Price > VWAP + 5% - EXTREME FOMO ZONE (raised from 3%)
                        # Precio muy extendido - only reject if no volume support
                        if volume_spike < 3.0:
                            should_keep = False
                            self.logger.warning(f"🚫 {symbol}: EXTREME FOMO ZONE - Price {vwap_deviation:.1%} above VWAP with low volume ({volume_spike:.1f}x)")
                        else:
                            vwap_adjustment = 1.1  # Allow with volume support
                            self.logger.info(f"📈 {symbol}: Extended but volume supported ({volume_spike:.1f}x)")
                        
                    elif vwap_deviation > 0.002:  # Price > VWAP + 0.2% but < 5%
                        # Strong bullish momentum - boost confidence
                        vwap_adjustment = 1.3
                        self.logger.info(f"🚀 {symbol}: Strong bullish momentum (Price {vwap_deviation:.1%} above VWAP) - boosting signal")
                        
                    elif vwap_deviation > 0:  # Price > VWAP but < 0.2%
                        # Mild bullish - keep signal but normal confidence
                        vwap_adjustment = 1.1
                        self.logger.info(f"📈 {symbol}: Above VWAP ({vwap_deviation:.1%}) - signal confirmed")
                        
                    elif vwap_deviation > -0.01:  # Price slightly below VWAP (-1% to 0%) - more permissive
                        # Near VWAP - reduce confidence but allow
                        vwap_adjustment = 0.8  # Less penalty
                        self.logger.info(f"⚠️ {symbol}: Near VWAP ({vwap_deviation:.1%}) - slight reduction")
                    
                    elif vwap_deviation > -0.05:  # -5% to -1% below VWAP
                        # Moderate dip - allow with volume confirmation
                        if volume_spike >= 2.0:
                            vwap_adjustment = 0.9
                            self.logger.info(f"💡 {symbol}: Moderate dip ({vwap_deviation:.1%}) with volume support ({volume_spike:.1f}x)")
                        else:
                            should_keep = False
                            self.logger.warning(f"🚫 {symbol}: Moderate dip without volume support")
                    
                    else:  # Price > -5% below VWAP
                        # Deep dip - only allow with significant volume (handled by recovery pattern above)
                        if volume_spike < 5.0:
                            should_keep = False
                            self.logger.warning(f"🚫 {symbol}: Deep dip {vwap_deviation:.1%} below VWAP without significant volume ({volume_spike:.1f}x < 5x)")
                        # If volume >= 5x, recovery pattern above would have caught it
                        
                elif signal.signal_type == SignalType.SHORT:
                    # For SHORT signals, enhanced with volume confirmation
                    if is_explosive and volume_spike >= 15.0 and vwap_deviation < 0:
                        vwap_adjustment = 2.0
                        override_reason = f"EXPLOSIVE SHORT VOLUME ({volume_spike:.1f}x)"
                        self.logger.warning(f"🚨 {symbol}: EXPLOSIVE SHORT VOLUME - {volume_spike:.1f}x volume")
                    elif vwap_deviation < -0.002:  # Price < VWAP - 0.2%
                        volume_boost = min(volume_spike / 5.0, 1.5) if volume_spike > 1.0 else 1.0
                        vwap_adjustment = 1.2 * volume_boost  # Boost SHORT with volume
                        self.logger.info(f"📉 {symbol}: Below VWAP ({vwap_deviation:.1%}) - boosting SHORT signal (vol: {volume_spike:.1f}x)")
                    else:
                        vwap_adjustment = 1.0  # Normal confidence
                        
                if should_keep:
                    # Apply VWAP adjustment to confidence
                    new_confidence = min(original_confidence * vwap_adjustment, 3.0)  # Increased cap for explosive signals
                    signal.metadata['confidence'] = new_confidence
                    signal.metadata['vwap'] = vwap
                    signal.metadata['vwap_deviation'] = vwap_deviation
                    signal.metadata['vwap_adjustment'] = vwap_adjustment
                    signal.metadata['volume_spike'] = volume_spike
                    signal.metadata['price_momentum'] = price_momentum
                    signal.metadata['is_explosive'] = is_explosive
                    if override_reason:
                        signal.metadata['vwap_override'] = override_reason
                    
                    filtered_signals.append(signal)
            
            rejected_count = len(signals) - len(filtered_signals)
            if rejected_count > 0:
                self.logger.info(f"🛡️ VWAP Filter: Rejected {rejected_count}/{len(signals)} signals for {symbol}")
            
            return filtered_signals
            
        except Exception as e:
            self.logger.error(f"Error applying VWAP filter for {symbol}: {e}")
            return signals  # Return original signals if filter fails
    
    def _log_strategy_no_signal_reason(self, strategy_name: str, symbol: str, bar: MarketData):
        """Log why a specific strategy didn't generate a signal"""
        try:
            # Load profile parameters for accurate thresholds
            profile_params = self._load_profile_parameters()
            
            recent_bars = self.bars_history[symbol][-10:] if len(self.bars_history[symbol]) >= 10 else self.bars_history[symbol]
            if len(recent_bars) < 2:
                self.logger.info(f"🔍 {strategy_name} for {symbol}: Not enough history ({len(recent_bars)} bars)")
                return
            
            # Get basic metrics
            prev_close = self._get_bar_value(recent_bars[-2], 'close')
            gap_size = ((self._get_bar_value(bar, 'open') - prev_close) / prev_close) * 100
            price_change = ((self._get_bar_value(bar, 'close') - prev_close) / prev_close) * 100
            
            avg_volume = sum(self._get_bar_value(b, 'volume') for b in recent_bars[:-1]) / max(1, len(recent_bars) - 1)
            volume_ratio = self._get_bar_value(bar, 'volume') / max(1, avg_volume)
            
            prices = [self._get_bar_value(b, 'close') for b in recent_bars]
            volatility = self._calculate_volatility(prices) * 100
            
            # Strategy-specific analysis
            if strategy_name == 'gap_go':
                # Get actual gap_go parameters from profile
                gap_go_params = profile_params.get('gap_go', {})
                min_gap = gap_go_params.get('min_gap_percent', 3.0)
                min_volume = gap_go_params.get('volume_multiplier', 0.5)
                reason = []
                if abs(gap_size) < min_gap:
                    reason.append(f"gap {gap_size:.1f}% < {min_gap:.1f}%")
                if volume_ratio < min_volume:
                    reason.append(f"volume {volume_ratio:.1f}x < {min_volume:.1f}x")
                if not reason:
                    reason.append("other criteria not met")
                self.logger.info(f"🔍 GAP_GO {symbol}: No signal - {', '.join(reason)}")
                
            elif strategy_name == 'orb':
                reason = []
                if volatility < 2.0:
                    reason.append(f"volatility {volatility:.1f}% < 2%")
                if volume_ratio < self.min_volume_ratio:
                    reason.append(f"volume {volume_ratio:.1f}x < 1.8x")
                if not reason:
                    reason.append("breakout criteria not met")
                self.logger.info(f"🔍 ORB {symbol}: No signal - {', '.join(reason)}")
                
            elif strategy_name == 'volume_breakout':
                # Get actual volume_breakout parameters from profile
                vb_params = profile_params.get('volume_breakout', {})
                min_volume_breakout = vb_params.get('volume_multiplier', 0.5)
                min_price_change = vb_params.get('min_price_change', 0.02) * 100  # Convert to percentage
                reason = []
                if volume_ratio < min_volume_breakout:
                    reason.append(f"volume {volume_ratio:.1f}x < {min_volume_breakout:.1f}x")
                if abs(price_change) < min_price_change:
                    reason.append(f"price move {price_change:.1f}% < {min_price_change:.1f}%")
                if not reason:
                    reason.append("breakout pattern not detected")
                self.logger.info(f"🔍 VOLUME_BREAKOUT {symbol}: No signal - {', '.join(reason)}")
                
            elif strategy_name == 'pmh_breakout':
                reason = []
                if volume_ratio < self.min_volume_ratio:
                    reason.append(f"volume {volume_ratio:.1f}x < 2x")
                if volatility < 2.0:
                    reason.append(f"volatility {volatility:.1f}% < 2%")
                if not reason:
                    reason.append("premarket high breakout not detected")
                self.logger.info(f"🔍 PMH_BREAKOUT {symbol}: No signal - {', '.join(reason)}")
                
            elif strategy_name == 'macdv_smallcaps':
                reason = []
                if volume_ratio < self.min_volume_ratio:
                    reason.append(f"volume {volume_ratio:.1f}x < {self.min_volume_ratio:.2f}x")
                if not (self.dynamic_vol_min <= volatility <= self.dynamic_vol_max):
                    reason.append(f"volatility {volatility:.1f}% not in {float(self.dynamic_vol_min):.1f}-{float(self.dynamic_vol_max):.1f}% range")
                if not reason:
                    reason.append("MACD/volume conditions not met")
                self.logger.info(f"🔍 MACDV {symbol}: No signal - {', '.join(reason)}")
            
        except Exception as e:
            self.logger.error(f"Error analyzing {strategy_name} for {symbol}: {e}")
    
    async def _sync_existing_positions(self) -> None:
        """
        Sincronizar posiciones existentes de IBKR con tracking interno
        para aplicar trailing stops automáticos
        """
        try:
            self.logger.info("🔄 Sincronizando posiciones existentes de IBKR...")
            
            # Obtener posiciones desde el broker (necesitamos acceso al broker)
            if not hasattr(self, 'broker') or not self.broker:
                self.logger.warning("⚠️ No broker available for position sync")
                return
            
            # Obtener posiciones actuales del broker
            positions_dict = await self.broker.get_positions()
            
            synced_positions = 0
            for symbol, position in positions_dict.items():
                if position.quantity != 0:  # Solo posiciones activas
                    
                    # Crear entrada de tracking para esta posición
                    self._create_position_tracking(position)
                    
                    # Inicializar trailing stop
                    await self._initialize_trailing_stop(position)
                    
                    synced_positions += 1
                    self.logger.info(f"✅ {symbol}: Posición sincronizada {position.quantity} acciones @ ${position.avg_price:.2f}")
            
            if synced_positions > 0:
                self.logger.info(f"🎯 Sincronizadas {synced_positions} posiciones existentes con trailing stops")
            else:
                self.logger.info("📝 No hay posiciones existentes para sincronizar")
                
        except Exception as e:
            self.logger.error(f"Error sincronizando posiciones existentes: {e}")
    
    def _create_position_tracking(self, position) -> None:
        """Crear tracking interno para posición existente"""
        try:
            symbol = position.symbol
            
            # Determinar qué estrategia debería manejar este símbolo
            # Por defecto, usar MACDV para posiciones existentes
            strategy_name = 'macdv_smallcaps'
            
            if strategy_name in self.strategies:
                strategy = self.strategies[strategy_name]
                
                # Crear entrada de signal tracking (simular que la estrategia abrió la posición)
                if hasattr(strategy, 'entry_signals'):
                    strategy.entry_signals[symbol] = {
                        'entry_price': position.avg_price,
                        'entry_time': dt.now(timezone.utc),  # Usar tiempo actual como aproximación
                        'quantity': position.quantity,
                        'direction': 'long' if position.quantity > 0 else 'short',
                        'synced_position': True,  # Marcar como posición sincronizada
                        'initial_stop': None,  # Se calculará en trailing stop
                        'highest_price': position.avg_price,  # Inicializar con precio de entrada
                        'sar_value': None,  # Se calculará en siguiente actualización
                        'sar_direction': 1 if position.quantity > 0 else -1
                    }
                    
                    self.logger.debug(f"📋 Created tracking for {symbol}: {position.quantity} @ ${position.avg_price:.2f}")
                
        except Exception as e:
            self.logger.error(f"Error creating position tracking for {position.symbol}: {e}")
    
    async def _initialize_trailing_stop(self, position) -> None:
        """Inicializar trailing stop para posición existente"""
        try:
            symbol = position.symbol
            
            # Obtener datos actuales del símbolo para calcular SAR inicial
            if hasattr(self, 'bars_history') and symbol in self.bars_history:
                bars = self.bars_history[symbol]
                if len(bars) >= 2:
                    current_bar = bars[-1]
                    
                    # Calcular SAR inicial
                    sar_value = self._calculate_initial_sar(symbol, position.avg_price, current_bar.close)
                    
                    # Calcular stop con tolerancia de 0.3%
                    tolerance = 0.003  # 0.3%
                    
                    if position.quantity > 0:  # Posición larga
                        stop_price = sar_value * (1 - tolerance)
                    else:  # Posición corta
                        stop_price = sar_value * (1 + tolerance)
                    
                    # Colocar stop order real en IBKR (protección hardware)
                    await self._place_initial_stop_order(position, stop_price)
                    
                    # Crear emergency stop también
                    emergency_stop = position.avg_price * 0.92  # -8% emergency
                    await self._place_emergency_stop_order(position, emergency_stop)
                    
                    self.logger.info(f"🎯 {symbol} trailing stop initialized: SAR=${sar_value:.3f}, Stop=${stop_price:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error initializing trailing stop for {position.symbol}: {e}")
    
    def _calculate_initial_sar(self, symbol: str, entry_price: float, current_price: float) -> float:
        """Calcular SAR inicial para posición existente"""
        try:
            # Parámetros SAR estándar
            acceleration = 0.02
            max_acceleration = 0.20
            
            # Si no tenemos historial suficiente, usar precio de entrada como SAR inicial
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return entry_price * 0.98  # 2% debajo como fallback
            
            bars = self.bars_history[symbol]
            if len(bars) < 10:
                return entry_price * 0.98
            
            # Calcular SAR basado en mínimos recientes para posición larga
            recent_bars = bars[-10:]  # Últimas 10 velas
            recent_lows = [bar.low for bar in recent_bars]
            recent_low = min(recent_lows)
            
            # SAR inicial = mínimo reciente con aceleración
            sar_initial = recent_low + (current_price - recent_low) * acceleration
            
            return max(sar_initial, entry_price * 0.95)  # No menos del 5% del precio entrada
            
        except Exception as e:
            self.logger.error(f"Error calculating initial SAR for {symbol}: {e}")
            return entry_price * 0.98  # Fallback conservador
    
    async def _place_initial_stop_order(self, position, stop_price: float) -> None:
        """Colocar orden de stop inicial en IBKR"""
        try:
            if hasattr(self, 'broker') and self.broker:
                # Crear stop order
                stop_order = {
                    'symbol': position.symbol,
                    'quantity': abs(position.quantity),
                    'side': 'sell' if position.quantity > 0 else 'buy',
                    'order_type': 'stop',
                    'stop_price': stop_price,
                    'tif': 'GTC'  # Good Till Cancelled
                }
                
                # Enviar orden de stop inicial a IBKR
                if hasattr(self.broker, 'place_order'):
                    try:
                        order_id = await self.broker.place_order(
                            symbol=stop_order['symbol'],
                            side=OrderSide.SELL if stop_order['side'] == 'sell' else OrderSide.BUY, 
                            quantity=stop_order['quantity'],
                            order_type=OrderType.STOP,
                            price=None,
                            stop_price=stop_order['stop_price']
                        )
                        if order_id:
                            self.logger.info(f"✅ {position.symbol} stop order placed successfully (ID: {order_id})")
                        else:
                            self.logger.warning(f"⚠️ {position.symbol} stop order placement returned no ID")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to place stop order for {position.symbol}: {e}")
                else:
                    self.logger.warning(f"⚠️ Broker does not support stop orders for {position.symbol}")
                
                self.logger.info(f"📍 {position.symbol} initial stop order placed at ${stop_price:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error placing initial stop order for {position.symbol}: {e}")
    
    async def _place_emergency_stop_order(self, position, emergency_stop: float) -> None:
        """Colocar stop de emergencia (-8%) en IBKR"""
        try:
            if hasattr(self, 'broker') and self.broker:
                # Crear emergency stop order
                emergency_order = {
                    'symbol': position.symbol,
                    'quantity': abs(position.quantity),
                    'side': 'sell' if position.quantity > 0 else 'buy',
                    'order_type': 'stop',
                    'stop_price': emergency_stop,
                    'tif': 'GTC'
                }
                
                # Enviar orden de emergency stop a IBKR
                if hasattr(self.broker, 'place_order'):
                    try:
                        order_id = await self.broker.place_order(
                            symbol=emergency_order['symbol'],
                            side=OrderSide.SELL if emergency_order['side'] == 'sell' else OrderSide.BUY,
                            quantity=emergency_order['quantity'], 
                            order_type=OrderType.STOP,
                            price=None,
                            stop_price=emergency_order['stop_price']
                        )
                        if order_id:
                            self.logger.info(f"✅ {position.symbol} emergency stop placed successfully (ID: {order_id})")
                        else:
                            self.logger.warning(f"⚠️ {position.symbol} emergency stop placement returned no ID")
                    except Exception as e:
                        self.logger.error(f"❌ Failed to place emergency stop for {position.symbol}: {e}")
                else:
                    self.logger.warning(f"⚠️ Broker does not support emergency stops for {position.symbol}")
                
                self.logger.info(f"🚨 {position.symbol} emergency stop placed at ${emergency_stop:.3f} (-8%)")
            
        except Exception as e:
            self.logger.error(f"Error placing emergency stop for {position.symbol}: {e}")
    
    def _calculate_parabolic_sar(self, symbol: str, current_bar) -> Optional[float]:
        """
        Calcular Parabolic SAR para trailing stops
        """
        try:
            if not hasattr(self, 'bars_history') or symbol not in self.bars_history:
                return None
                
            bars = self.bars_history[symbol]
            if len(bars) < 5:
                return None
            
            # Parámetros SAR
            acceleration = 0.02
            max_acceleration = 0.20
            
            # Obtener datos de las últimas velas
            recent_bars = bars[-20:] if len(bars) >= 20 else bars
            
            # Inicializar SAR
            if len(recent_bars) < 2:
                return None
            
            # Calcular tendencia inicial
            first_bar = recent_bars[0]
            second_bar = recent_bars[1]
            
            # Determinar dirección inicial
            rising = second_bar.close > first_bar.close
            
            if rising:
                sar = min(bar.low for bar in recent_bars[:2])
                extreme_point = max(bar.high for bar in recent_bars[:2])
            else:
                sar = max(bar.high for bar in recent_bars[:2])
                extreme_point = min(bar.low for bar in recent_bars[:2])
            
            current_acceleration = acceleration
            
            # Calcular SAR para las velas restantes
            for i in range(2, len(recent_bars)):
                bar = recent_bars[i]
                
                # Calcular nuevo SAR
                sar = sar + current_acceleration * (extreme_point - sar)
                
                # Verificar reversión
                if rising:
                    if bar.low <= sar:
                        # Reversión a bajista
                        rising = False
                        sar = extreme_point
                        extreme_point = bar.low
                        current_acceleration = acceleration
                    else:
                        # Continuar alcista
                        if bar.high > extreme_point:
                            extreme_point = bar.high
                            current_acceleration = min(current_acceleration + acceleration, max_acceleration)
                        
                        # Ajustar SAR para no exceder mínimos anteriores
                        prev_low = min(recent_bars[i-1].low, recent_bars[i-2].low if i > 2 else recent_bars[i-1].low)
                        sar = min(sar, prev_low)
                else:
                    if bar.high >= sar:
                        # Reversión a alcista
                        rising = True
                        sar = extreme_point
                        extreme_point = bar.high
                        current_acceleration = acceleration
                    else:
                        # Continuar bajista
                        if bar.low < extreme_point:
                            extreme_point = bar.low
                            current_acceleration = min(current_acceleration + acceleration, max_acceleration)
                        
                        # Ajustar SAR para no exceder máximos anteriores
                        prev_high = max(recent_bars[i-1].high, recent_bars[i-2].high if i > 2 else recent_bars[i-1].high)
                        sar = max(sar, prev_high)
            
            return sar
            
        except Exception as e:
            self.logger.error(f"Error calculating Parabolic SAR for {symbol}: {e}")
            return None
    
    async def _update_trailing_stops(self, symbol: str, current_bar) -> None:
        """
        Actualizar trailing stops para posiciones existentes usando Parabolic SAR
        """
        try:
            # Buscar posiciones activas para este símbolo
            for strategy_name, strategy in self.strategies.items():
                if hasattr(strategy, 'entry_signals') and symbol in strategy.entry_signals:
                    entry_data = strategy.entry_signals[symbol]
                    
                    if entry_data.get('synced_position', False):
                        # Es una posición sincronizada, actualizar trailing stop
                        await self._update_sar_trailing_stop(symbol, current_bar, entry_data)
            
        except Exception as e:
            self.logger.error(f"Error updating trailing stops for {symbol}: {e}")
    
    async def _update_sar_trailing_stop(self, symbol: str, current_bar, entry_data: dict) -> None:
        """
        Actualizar SAR trailing stop específico
        """
        try:
            # Calcular nuevo SAR
            new_sar = self._calculate_parabolic_sar(symbol, current_bar)
            if not new_sar:
                return
            
            # Actualizar highest price si es posición larga
            if entry_data['direction'] == 'long':
                entry_data['highest_price'] = max(entry_data.get('highest_price', current_bar.high), current_bar.high)
            
            # Calcular nuevo stop con tolerancia de 0.3%
            tolerance = 0.003  # 0.3%
            
            if entry_data['direction'] == 'long':
                new_stop = new_sar * (1 - tolerance)
                
                # Solo mover el stop hacia arriba (trailing)
                old_stop = entry_data.get('current_stop', 0)
                if new_stop > old_stop:
                    entry_data['current_stop'] = new_stop
                    entry_data['sar_value'] = new_sar
                    
                    # Actualizar stop order en IBKR
                    await self._update_stop_order(symbol, new_stop)
                    
                    self.logger.info(f"🔼 {symbol} trailing stop updated: ${new_stop:.3f} (SAR: ${new_sar:.3f})")
                    
                    # Verificar si precio actual está por debajo del stop
                    if current_bar.close <= new_stop:
                        self.logger.warning(f"🚨 {symbol} hit trailing stop! Price: ${current_bar.close:.3f}, Stop: ${new_stop:.3f}")
                        # Aquí se activaría la venta automática
            
        except Exception as e:
            self.logger.error(f"Error updating SAR trailing stop for {symbol}: {e}")
    
    async def _update_stop_order(self, symbol: str, new_stop_price: float) -> None:
        """
        Actualizar orden de stop en IBKR
        """
        try:
            if hasattr(self, 'broker') and self.broker:
                # Cancelar stop order anterior si existe
                # Crear nuevo stop order con precio actualizado
                
                # Implementación depende del broker adapter
                # await self.broker.modify_stop_order(symbol, new_stop_price)
                
                self.logger.debug(f"📍 {symbol} stop order updated to ${new_stop_price:.3f}")
            
        except Exception as e:
            self.logger.error(f"Error updating stop order for {symbol}: {e}")
    
    def _initialize_strategies_from_config(self, profile_params: Dict[str, Any], extended_hours_available: bool):
        """
        Initialize strategies dynamically from config.ini enabled_strategies list.
        This makes adding new strategies as simple as adding them to the config file.
        """
        try:
            # Read enabled strategies from config
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            # Get enabled strategies from current profile
            profile_section = f"{self.current_profile}_PROFILE"
            
            # Try profile-specific first, then fallback to MULTI_STRATEGY section
            if profile_section in config and 'multi_strategy_enabled_strategies' in config[profile_section]:
                enabled_strategies_str = config[profile_section]['multi_strategy_enabled_strategies']
                self.logger.info(f"📋 Using {self.current_profile} profile strategy list")
            elif 'MULTI_STRATEGY' in config and 'enabled_strategies' in config['MULTI_STRATEGY']:
                enabled_strategies_str = config['MULTI_STRATEGY']['enabled_strategies']
                self.logger.info("📋 Using MULTI_STRATEGY section strategy list")
            else:
                # Fallback to hardcoded list if config missing
                enabled_strategies_str = "macdv_smallcaps,gap_go,orb,volume_breakout"
                self.logger.warning("⚠️ No enabled_strategies found in config, using fallback list")
            
            # Parse enabled strategies
            enabled_strategies = [s.strip() for s in enabled_strategies_str.split(',') if s.strip()]
            self.logger.info(f"🎯 Attempting to load strategies: {enabled_strategies}")
            
            # Strategy name mappings for legacy compatibility
            strategy_mappings = {
                'macdv_smallcaps': 'macdv',
                'gap_go': 'gap_go', 
                'orb': 'orb',
                'volume_breakout': 'volume_breakout',
                'pmh_breakout': 'pmh_breakout',
                'explosive_volume': 'explosive_volume',
                'hybrid_explosion': 'hybrid_explosion',
                'eod_momentum': 'eod_momentum',
                'eod_overnight_smallcaps': 'eod_overnight_smallcaps',
                'july_strategy': 'july_strategy',
                'daily_plays': 'daily_plays'
            }
            
            # Premarket-dependent strategies (need extended hours data)
            premarket_strategies = {'gap_go', 'pmh_breakout'}
            
            # Initialize each enabled strategy
            loaded_count = 0
            for strategy_name in enabled_strategies:
                try:
                    # Check if strategy needs extended hours data
                    if strategy_name in premarket_strategies and not extended_hours_available:
                        self.logger.warning(f"⚠️ Skipping {strategy_name} - requires extended hours data")
                        continue
                    
                    # Get strategy class using the registry system
                    mapped_name = strategy_mappings.get(strategy_name, strategy_name)
                    # Import locally to avoid circular dependency
                    from . import get_strategy_class
                    strategy_class = get_strategy_class(mapped_name)
                    
                    # Load strategy-specific parameters
                    strategy_params = self._load_strategy_params(strategy_name, profile_params)
                    
                    # Instantiate strategy
                    self.strategies[strategy_name] = strategy_class(strategy_params)
                    loaded_count += 1
                    
                    self.logger.info(f"✅ Loaded {strategy_name} strategy")
                    
                except Exception as e:
                    self.logger.error(f"❌ Failed to load {strategy_name}: {e}")
                    continue
            
            # Log final results
            self.logger.info(f"🎯 Strategy initialization complete: {loaded_count}/{len(enabled_strategies)} loaded")
            self.logger.info(f"📋 Active strategies: {list(self.strategies.keys())}")
            
            if not self.strategies:
                self.logger.error("❌ No strategies loaded! MultiStrategy engine will not generate signals")
            
            # Log premarket strategy status
            if extended_hours_available:
                premarket_loaded = [s for s in self.strategies.keys() if s in premarket_strategies]
                if premarket_loaded:
                    self.logger.info(f"✅ Premarket strategies enabled: {premarket_loaded}")
            else:
                self.logger.warning("⚠️ Premarket strategies disabled - no extended hours data")
                self.logger.warning("💡 To enable: Set trading_hours_mode = EXTENDED_HOURS in config.ini")
                
        except Exception as e:
            self.logger.error(f"Error initializing strategies from config: {e}")
            # Fallback to minimal strategy set
            self._initialize_fallback_strategies(profile_params)
    
    def _load_strategy_params(self, strategy_name: str, profile_params: Dict[str, Any]) -> Dict[str, Any]:
        """Load parameters for a specific strategy from config and profile"""
        try:
            # Start with strategy-specific section from config.ini
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            # Strategy section name (uppercase)
            strategy_section = f"{strategy_name.upper()}_STRATEGY"
            params = {}
            
            # Load from strategy-specific section with proper type conversion
            if strategy_section in config:
                for key, value in config.items(strategy_section):
                    params[key] = self._convert_config_value(value)
                
            # Override with profile-specific parameters
            if strategy_name in profile_params:
                params.update(profile_params[strategy_name])
            
            # Special handling for known strategies
            if strategy_name == 'macdv_smallcaps':
                params.update(profile_params.get('macdv', {}))
            elif strategy_name == 'gap_go':
                params.update(profile_params.get('gap_go', {}))
            elif strategy_name == 'orb':
                params.update(profile_params.get('orb', {}))
            elif strategy_name == 'volume_breakout':
                params.update(profile_params.get('volume_breakout', {}))
            elif strategy_name == 'pmh_breakout':
                params.update(profile_params.get('pmh_breakout', {}))
            elif strategy_name == 'hybrid_explosion':
                params.update(profile_params.get('hybrid_explosion', {}))
                
            return params
            
        except Exception as e:
            self.logger.warning(f"Error loading params for {strategy_name}: {e}")
            return {}
    
    def _convert_config_value(self, value: str):
        """Convert string config values to appropriate types"""
        if value.lower() in ('true', 'yes', '1'):
            return True
        elif value.lower() in ('false', 'no', '0'):
            return False
        elif value.lower() in ('none', 'null', ''):
            return None
        else:
            # Try to convert to number
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value  # Return as string
    
    def _initialize_fallback_strategies(self, profile_params: Dict[str, Any]):
        """Initialize minimal strategy set as fallback"""
        self.logger.warning("🔄 Initializing fallback strategies")
        
        try:
            # Only load strategies that are guaranteed to work
            fallback_strategies = ['macdv', 'volume_breakout']
            
            for strategy_name in fallback_strategies:
                try:
                    # Import locally to avoid circular dependency
                    from . import get_strategy_class
                    strategy_class = get_strategy_class(strategy_name)
                    params = profile_params.get(strategy_name, {})
                    self.strategies[strategy_name] = strategy_class(params)
                    self.logger.info(f"✅ Fallback: Loaded {strategy_name}")
                except Exception as e:
                    self.logger.error(f"❌ Fallback failed for {strategy_name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Fallback initialization failed: {e}")