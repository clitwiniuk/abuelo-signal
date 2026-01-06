# strategies/base.py
"""
Enhanced Base Strategy - Base strategy class mejorada con manejo inteligente de datos
Soluciona problemas de falta de datos en apertura usando continuidad entre días
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import configparser
from pathlib import Path

from core.interfaces import (
    IStrategy, Signal, SignalType, Position, MarketData, EventBus,
    OrderSide, IDataProvider
)
from core.events import EventHandlerMixin, event_handler
from core.enhanced_data_manager import EnhancedDataManager, DataContinuityConfig
from core.trade_ohlc_recorder import get_trade_ohlc_recorder


class BaseStrategy(IStrategy, EventHandlerMixin):
    """
    Base strategy class mejorada con manejo inteligente de datos entre días
    Soluciona automáticamente problemas de falta de datos en apertura
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any] = None, 
                 data_provider: IDataProvider = None,
                 continuity_config: DataContinuityConfig = None):
        self._name = name
        self._parameters = parameters or {}
        self.logger = logging.getLogger(f"Strategy.{name}")
        
        # Enhanced data manager
        if data_provider:
            self.enhanced_data_manager = EnhancedDataManager(data_provider, continuity_config)
        else:
            self.enhanced_data_manager = None
            self.logger.warning("⚠️ No data provider provided, enhanced data management disabled")
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.signals_generated: Dict[str, List[Signal]] = {}
        
        # Enhanced data tracking
        self.confidence_factors: Dict[str, float] = {}
        self.trading_readiness: Dict[str, bool] = {}

        # Performance tracking
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0

        # OHLC Recording for forward testing
        try:
            self.ohlc_recorder = get_trade_ohlc_recorder()
            self.logger.info("📊 OHLC Recorder initialized for forward testing")
        except Exception as e:
            self.logger.warning(f"⚠️ OHLC Recorder initialization failed: {e}")
            self.ohlc_recorder = None
        
        # Trading control basado en confianza
        self.min_confidence_for_signals = 0.7  # Confianza mínima para generar señales
        self.min_confidence_for_execution = 0.8  # Confianza mínima para ejecutar trades
        
        # ML Exit System Integration - DISABLED to use fixed stops
        self.ml_exit_enabled = False  # Use fallback_stop_loss_pct = 0.08 from config.ini
        self.ml_exit_engine = None
        
        # FOMO Exit System (now integrated with ML Exit)
        self.fomo_exit_enabled = False
        self.fomo_detector = None
        
        # Event bus will be set during initialization
        self.event_bus: Optional[EventBus] = None
        
        # Initialize with empty event bus initially
        super().__init__(None)
        
        self.logger.info(f"🚀 Enhanced {name} strategy initialized")
        self.logger.info(f"   Min confidence for signals: {self.min_confidence_for_signals}")
        self.logger.info(f"   Min confidence for execution: {self.min_confidence_for_execution}")
        self.logger.info(f"   FOMO exit system: {'Enabled' if self.fomo_exit_enabled else 'Disabled'}")
    
    def _load_strategy_config(self, section_name: str, fallback_defaults: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Load strategy configuration from config.ini
        
        Args:
            section_name: Name of the config section (e.g., 'MACDV_STRATEGY')
            fallback_defaults: Default values if config section doesn't exist
            
        Returns:
            Dictionary with configuration parameters
        """
        try:
            config_path = Path(__file__).parent.parent / 'config.ini'
            if not config_path.exists():
                self.logger.warning(f"⚠️ Config file not found at {config_path}, using defaults")
                return fallback_defaults or {}
            
            config = configparser.ConfigParser()
            config.read(config_path)
            
            strategy_config = {}
            
            # Load from strategy-specific section first
            if config.has_section(section_name):
                for key, value in config.items(section_name):
                    strategy_config[key] = self._convert_config_value(value)
                self.logger.info(f"📋 Loaded config from [{section_name}]: {len(strategy_config)} parameters")
            else:
                self.logger.warning(f"⚠️ Config section [{section_name}] not found")
            
            # Load global defaults for missing values
            if config.has_section('GLOBAL'):
                for key, value in config.items('GLOBAL'):
                    if key not in strategy_config:  # Don't override strategy-specific values
                        strategy_config[key] = self._convert_config_value(value)
            
            # Apply fallback defaults for any missing values
            if fallback_defaults:
                for key, value in fallback_defaults.items():
                    if key not in strategy_config:
                        strategy_config[key] = value
            
            return strategy_config
            
        except Exception as e:
            self.logger.error(f"❌ Error loading strategy config: {e}")
            return fallback_defaults or {}
    
    def _convert_config_value(self, value: str) -> Any:
        """Convert string config values to appropriate types"""
        # Clean inline comments (everything after #)
        clean_value = value.split('#')[0].strip()
        
        if clean_value.lower() in ('true', 'yes', '1'):
            return True
        elif clean_value.lower() in ('false', 'no', '0'):
            return False
        elif clean_value.lower() in ('none', 'null', ''):
            return None
        else:
            # Try to convert to number
            try:
                if '.' in clean_value:
                    return float(clean_value)
                else:
                    return int(clean_value)
            except ValueError:
                return clean_value  # Return cleaned string
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters
    
    async def initialize(self, event_bus: EventBus, broker=None) -> None:
        """Initialize strategy with event bus and optional broker"""
        self.event_bus = event_bus
        self.broker = broker  # Make broker available to strategies
        
        # Register event handlers
        self._register_event_handlers()
        
        # Strategy-specific initialization
        await self._initialize_strategy()
        
        self.logger.info(f"Strategy {self.name} initialized with parameters: {self.parameters}")
    
    async def _initialize_strategy(self) -> None:
        """Strategy-specific initialization logic - override in subclasses"""
        pass
    
    async def get_enhanced_market_data(self, symbol: str, bars: int = 100) -> Tuple[List[MarketData], float]:
        """
        Obtiene datos de mercado con continuidad entre días
        
        Returns:
            Tuple[List[MarketData], float]: (datos, factor_confianza)
        """
        if not self.enhanced_data_manager:
            # Fallback a método tradicional si no hay enhanced data manager
            return await self._get_traditional_data(symbol, bars), 1.0
        
        try:
            data, confidence = await self.enhanced_data_manager.get_enhanced_market_data(symbol, bars)
            
            # Actualizar tracking
            self.confidence_factors[symbol] = confidence
            self.trading_readiness[symbol] = self.enhanced_data_manager.is_ready_for_trading(symbol)
            
            # Log información si la confianza es baja
            if confidence < 0.8:
                continuity_info = self.enhanced_data_manager.get_continuity_info(symbol)
                minutes_since_open = continuity_info.get('minutes_since_open', 0)
                current_bars = continuity_info.get('current_day_bars', 0)
                
                self.logger.info(f"📊 {symbol}: Confidence={confidence:.2f}, "
                               f"Minutes since open={minutes_since_open}, "
                               f"Current day bars={current_bars}")
            
            return data, confidence
            
        except Exception as e:
            self.logger.error(f"❌ Error getting enhanced data for {symbol}: {e}")
            # Fallback
            return await self._get_traditional_data(symbol, bars), 0.5
    
    async def _get_traditional_data(self, symbol: str, bars: int) -> List[MarketData]:
        """Método tradicional de obtención de datos (fallback)"""
        if symbol in self.bars_history:
            return self.bars_history[symbol][-bars:] if len(self.bars_history[symbol]) > bars else self.bars_history[symbol]
        return []
    
    def should_generate_signals(self, symbol: str) -> bool:
        """Determina si se deben generar señales basado en confianza de datos"""
        confidence = self.confidence_factors.get(symbol, 1.0)  # Default a 1.0 si no hay enhanced manager
        return confidence >= self.min_confidence_for_signals
    
    def should_execute_trade(self, symbol: str) -> bool:
        """Determina si se debe ejecutar un trade basado en confianza y tiempo"""
        confidence = self.confidence_factors.get(symbol, 1.0)  # Default a 1.0 si no hay enhanced manager
        is_ready = self.trading_readiness.get(symbol, True)  # Default a True si no hay enhanced manager
        
        return confidence >= self.min_confidence_for_execution and is_ready
    
    def enable_fomo_exit(self, fomo_config: Dict[str, Any] = None) -> bool:
        """
        Enable FOMO detection exit system for this strategy
        
        Args:
            fomo_config: Configuration for FOMO detector
            
        Returns:
            bool: True if enabled successfully
        """
        try:
            from core.fomo_detector import FOMODetector
            
            self.fomo_detector = FOMODetector(fomo_config or {})
            self.fomo_exit_enabled = True
            
            self.logger.info(f"🎪 FOMO Exit enabled for {self.name}")
            self.logger.info(f"   FOMO threshold: {self.fomo_detector.fomo_threshold:.1%}")
            self.logger.info(f"   Critical threshold: {self.fomo_detector.critical_threshold:.1%}")
            
            return True
            
        except ImportError:
            self.logger.error("❌ FOMO Detector module not available")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error enabling FOMO exit: {e}")
            return False
    
    def check_fomo_exit(self, symbol: str, position: Position, current_bar: MarketData) -> Optional[Dict[str, Any]]:
        """
        Check if FOMO exit conditions are met
        
        Args:
            symbol: Trading symbol
            position: Current position
            current_bar: Current market bar
            
        Returns:
            Dict with exit decision or None if no exit
        """
        if not self.fomo_exit_enabled or not self.fomo_detector:
            return None
            
        try:
            # Get bars history for analysis
            bars_history = self.bars_history.get(symbol, [])[-30:]  # Last 30 bars
            
            if len(bars_history) < 10:
                return None
                
            fomo_analysis = self.fomo_detector.detect_fomo_exit(
                symbol, current_bar, position, bars_history
            )
            
            if fomo_analysis.get('should_exit', False):
                self.logger.warning(f"🎪 FOMO EXIT TRIGGERED: {symbol}")
                return fomo_analysis
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error in FOMO exit check for {symbol}: {e}")
            return None
    
    def get_confidence_adjusted_position_size(self, symbol: str, base_size: float) -> float:
        """Ajusta el tamaño de posición basado en la confianza de datos"""
        confidence = self.confidence_factors.get(symbol, 1.0)
        
        # Reducir tamaño de posición si la confianza es baja
        if confidence < 0.9:
            adjustment_factor = 0.5 + (confidence - 0.5) * 1.0  # Entre 0.5x y 1.0x
            adjusted_size = base_size * adjustment_factor
            
            if adjusted_size != base_size:
                self.logger.info(f"📏 {symbol}: Position size adjusted by confidence "
                               f"{base_size} -> {adjusted_size:.0f} (confidence={confidence:.2f})")
            
            return adjusted_size
        
        return base_size
    
    def get_data_quality_info(self, symbol: str) -> Dict[str, Any]:
        """Obtiene información de calidad de datos para un símbolo"""
        if not self.enhanced_data_manager:
            return {'confidence_factor': 1.0, 'ready_for_trading': True}
        
        continuity_info = self.enhanced_data_manager.get_continuity_info(symbol)
        
        return {
            'confidence_factor': self.confidence_factors.get(symbol, 0.0),
            'ready_for_trading': self.trading_readiness.get(symbol, False),
            'continuity_info': continuity_info,
            'should_generate_signals': self.should_generate_signals(symbol),
            'should_execute_trade': self.should_execute_trade(symbol)
        }
    
    def _get_bar_value(self, bar, field: str):
        """Helper to get value from bar regardless if it's MarketData object or dict"""
        if hasattr(bar, field):
            return getattr(bar, field)
        elif isinstance(bar, dict):
            return bar.get(field)
        else:
            raise ValueError(f"Cannot get {field} from bar of type {type(bar)}")

    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Process new bar data with enhanced data management"""
        try:
            # Store bar in history
            bar_symbol = self._get_bar_value(bar, 'symbol')
            bar_timestamp = self._get_bar_value(bar, 'timestamp')

            if bar_symbol not in self.bars_history:
                self.bars_history[bar_symbol] = []

            # Record market data for OHLC analysis
            if self.ohlc_recorder:
                try:
                    self.ohlc_recorder.record_market_data(bar_symbol, bar)
                except Exception as e:
                    self.logger.debug(f"OHLC recording error for {bar_symbol}: {e}")
            
            # Check for duplicate timestamp before adding
            if self.bars_history[bar_symbol] and bar_timestamp == self._get_bar_value(self.bars_history[bar_symbol][-1], 'timestamp'):
                self.bars_history[bar_symbol][-1] = bar  # overwrite with latest values
            elif self.bars_history[bar_symbol] and bar_timestamp < self._get_bar_value(self.bars_history[bar_symbol][-1], 'timestamp'):
                # Out-of-order bar, ignore silently to avoid noise
                return None
            else:
                self.bars_history[bar_symbol].append(bar)
            
            # Keep only last N bars (configurable)
            max_bars = self._parameters.get('max_history_bars', 1500)
            if len(self.bars_history[bar_symbol]) > max_bars:
                self.bars_history[bar_symbol] = self.bars_history[bar_symbol][-max_bars:]
            
            # Check if we should generate signals based on data confidence
            if not self.should_generate_signals(bar_symbol):
                self.logger.debug(f"🔇 {bar_symbol}: Skipping signal generation due to low data confidence")
                return None
            
            # Generate signal
            signal = await self._analyze_bar(bar)
            
            if signal:
                # Additional check for trade execution readiness
                if not self.should_execute_trade(bar_symbol):
                    self.logger.info(f"⏸️ {bar_symbol}: Signal generated but execution delayed due to data quality")
                    # Store signal but mark it as delayed
                    signal.metadata = signal.metadata or {}
                    signal.metadata['execution_delayed'] = True
                    signal.metadata['delay_reason'] = 'data_quality'
                
                # Store signal
                if bar_symbol not in self.signals_generated:
                    self.signals_generated[bar_symbol] = []
                self.signals_generated[bar_symbol].append(signal)
                
                confidence = self.confidence_factors.get(bar_symbol, 1.0)
                self.logger.info(f"Signal generated for {bar_symbol}: {signal.signal_type} (confidence: {confidence:.2f})")
            
            return signal
            
        except Exception as e:
            bar_symbol = self._get_bar_value(bar, 'symbol') if hasattr(self, '_get_bar_value') else 'UNKNOWN'
            self.logger.error(f"Error processing bar for {bar_symbol}: {e}")
            return None
    
    @abstractmethod
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate signal - implement in subclasses"""
        pass
    
    def update_bars_history(self, symbol: str, bars: List[MarketData]):
        """Actualiza el historial de barras con información de calidad"""
        self.bars_history[symbol] = bars
        
        # Log si usamos datos del día anterior
        if symbol in self.confidence_factors:
            confidence = self.confidence_factors[symbol]
            if confidence < 1.0 and self.enhanced_data_manager:
                continuity_info = self.enhanced_data_manager.get_continuity_info(symbol)
                if continuity_info.get('using_previous_day', False):
                    self.logger.debug(f"📚 {symbol}: Using previous day data continuity")
    
    # Métodos de análisis técnico mejorados con factor de confianza
    def calculate_sma(self, symbol: str, period: int, confidence_factor: float = 1.0) -> Optional[float]:
        """Calcula SMA ajustada por factor de confianza"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        sma = df['close'].tail(period).mean()
        return sma
    
    def calculate_ema(self, symbol: str, period: int, confidence_factor: float = 1.0) -> Optional[float]:
        """Calcula EMA ajustada por factor de confianza"""
        df = self.get_bars_df(symbol, period * 2)  # Get more data for EMA
        if len(df) < period:
            return None
        
        return df['close'].ewm(span=period).mean().iloc[-1]
    
    def calculate_volume_ma(self, symbol: str, period: int) -> Optional[float]:
        """Calcula media móvil de volumen"""
        df = self.get_bars_df(symbol, period)
        if len(df) < period:
            return None
        
        return df['volume'].tail(period).mean()

    def calculate_rsi(self, symbol: str, period: int = 14, price_type: str = 'close') -> Optional[float]:
        """Calcula RSI (Relative Strength Index) para el símbolo dado.

        Args:
            symbol: Símbolo a evaluar
            period: Número de períodos para el cálculo de RSI
            price_type: Tipo de precio a usar ('close', 'open', 'high', 'low')

        Returns:
            Valor RSI (0-100) o None si no hay suficientes datos
        """
        df = self.get_bars_df(symbol, period * 2)
        if len(df) < period + 1 or price_type not in df.columns:
            return None

        delta = df[price_type].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Evitar división por cero
        if loss.iloc[-1] == 0:
            return 100.0

        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))

        return rsi_series.iloc[-1] if not rsi_series.empty else None
    
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
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size with confidence adjustment"""
        try:
            # Parámetros básicos
            max_position_value = float(self._parameters.get('max_position_value', 1000.0))
            min_position_value = float(self._parameters.get('min_position_value', 100.0))
            min_quantity = int(self._parameters.get('min_quantity', 1))
            
            price = float(signal.price)
            
            if price <= 0:
                self.logger.warning(f"Invalid price {price} for {signal.symbol}")
                return 0
            
            # Calcular tamaño base
            target_value = min(max_position_value, capital * 0.1)  # Máximo 10% del capital
            target_value = max(target_value, min_position_value)   # Mínimo valor requerido
            
            # Ajustar por confianza de datos
            adjusted_target_value = self.get_confidence_adjusted_position_size(signal.symbol, target_value)
            
            # Calcular cantidad
            quantity = int(adjusted_target_value / price)
            
            # Aplicar límites
            quantity = max(quantity, min_quantity)
            
            # Verificar que no exceda el capital disponible
            position_value = quantity * price
            commission = max(quantity * 0.005, 1.0)  # Commission estimate
            total_cost = position_value + commission
            
            if total_cost > capital:
                # Reducir cantidad para que quepa en el capital
                available_for_position = capital - commission
                if available_for_position > 0:
                    quantity = max(int(available_for_position / price), 1)
                else:
                    return 0
            
            # Verificar límites finales
            final_value = quantity * price
            if final_value > max_position_value * 1.1:  # 10% tolerance
                quantity = int(max_position_value / price)
            
            confidence = self.confidence_factors.get(signal.symbol, 1.0)
            self.logger.debug(
                f"Position size for {signal.symbol}: {quantity} shares "
                f"@ ${price:.2f} = ${final_value:.2f} (confidence: {confidence:.2f})"
            )
            
            return max(quantity, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {signal.symbol}: {e}")
            return 0
    
    # Event handlers
    @event_handler('market_data_received')
    async def _on_market_data(self, event):
        """Maneja eventos de datos de mercado"""
        symbol = event.data.get('symbol')
        bars = event.data.get('bars', [])
        
        if symbol and bars:
            self.update_bars_history(symbol, bars)
    
    @event_handler('position_opened')
    async def _on_position_opened(self, event):
        """Maneja eventos de apertura de posición"""
        position = event.data.get('position')
        if position:
            self.positions[position.symbol] = position
    
    @event_handler('position_closed')
    async def _on_position_closed(self, event):
        """Maneja eventos de cierre de posición"""
        symbol = event.data.get('symbol')
        if symbol in self.positions:
            del self.positions[symbol]
            
        # Update performance tracking
        position = event.data.get('position')
        if position:
            self.trades_count += 1
            if position.unrealized_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            self.logger.info(f"Position closed: {position.symbol} PnL: {position.unrealized_pnl:.2f}")
    
    def should_exit_position(self, position: Position, current_data: MarketData) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Determines if a position should be exited using ML Exit Engine
        
        Args:
            position: Current position
            current_data: Current market data
            
        Returns:
            Tuple of (should_exit, exit_reason, exit_details)
        """
        try:
            # Initialize ML Exit Engine if not available
            if self.ml_exit_enabled and not self.ml_exit_engine:
                from core.ml_exit_engine import get_global_ml_exit_engine
                self.ml_exit_engine = get_global_ml_exit_engine()
            
            # Get bars history for analysis
            bars_history = self.bars_history.get(position.symbol, [])
            
            if self.ml_exit_enabled and self.ml_exit_engine and len(bars_history) >= 10:
                # Use ML Exit Engine for decision
                ml_decision = self.ml_exit_engine.should_exit(position, current_data, bars_history)
                
                if ml_decision.get('should_exit', False):
                    return (
                        True,
                        f"ML_EXIT_{ml_decision.get('exit_type', 'UNKNOWN')}",
                        {
                            'ml_confidence': ml_decision.get('confidence', 0.5),
                            'ml_expected_value': ml_decision.get('expected_value', 0),
                            'ml_reasons': ml_decision.get('reasons', []),
                            'optimal_hold_minutes': ml_decision.get('optimal_hold_minutes', 60)
                        }
                    )
                else:
                    return (False, "ML_HOLD", {'ml_analysis': ml_decision})
            
            else:
                # Fallback to static exit rules if ML not available
                return self._fallback_exit_logic(position, current_data)
                
        except Exception as e:
            self.logger.error(f"Error in ML exit decision for {position.symbol}: {e}")
            # Fallback to static rules on error
            return self._fallback_exit_logic(position, current_data)
    
    def _fallback_exit_logic(self, position: Position, current_data: MarketData) -> Tuple[bool, str, Dict[str, Any]]:
        """Fallback exit logic using static rules"""
        try:
            current_pnl_pct = (current_data.close - position.entry_price) / position.entry_price
            holding_time = (current_data.timestamp - position.entry_time).total_seconds() / 60
            
            # Static stop loss (8%)
            if current_pnl_pct <= -0.08:
                return (True, "STOP_LOSS", {'pnl_pct': current_pnl_pct})
            
            # Static profit taking (15%+)
            if current_pnl_pct >= 0.15:
                return (True, "PROFIT_TARGET", {'pnl_pct': current_pnl_pct})
            
            # Time-based exit (3+ hours)
            if holding_time >= 180:
                if current_pnl_pct > 0.02:  # Any profit after 3h
                    return (True, "TIME_PROFIT", {'pnl_pct': current_pnl_pct, 'holding_minutes': holding_time})
                elif holding_time >= 240:  # Force exit after 4h
                    return (True, "TIME_FORCE", {'pnl_pct': current_pnl_pct, 'holding_minutes': holding_time})
            
            return (False, "HOLD", {'pnl_pct': current_pnl_pct, 'holding_minutes': holding_time})
            
        except Exception as e:
            self.logger.error(f"Error in fallback exit logic: {e}")
            return (False, "ERROR", {'error': str(e)})

    def clear_daily_data(self):
        """Limpia datos diarios (llamar al inicio de nuevo día de trading)"""
        if self.enhanced_data_manager:
            self.enhanced_data_manager.clear_cache()
        
        self.confidence_factors.clear()
        self.trading_readiness.clear()
        
        self.logger.info("🆕 Daily data cleared for new trading session")
    
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