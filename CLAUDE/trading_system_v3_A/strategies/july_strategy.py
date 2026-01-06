# strategies/july_strategy.py
"""
July Strategy: EMA 9 / SMA 20 crossover strategy with momentum filters.

Entry Conditions:
1. EMA 9 crosses above SMA 20 (bullish crossover)
2. ADX > 20 (trending market)
3. Bollinger Band Width > threshold (volatility filter)
4. ATR Relative > threshold (movement filter)

Exit Conditions:
1. Trailing stop loss (percentage-based)
2. EMA 9 crosses below SMA 20 (bearish crossover)
"""

from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class JulyStrategy(BaseStrategy):
    """
    EMA/SMA crossover strategy with advanced momentum and volatility filters.
    
    Technical Indicators:
    - EMA 9: Fast exponential moving average
    - SMA 20: Slow simple moving average  
    - ADX: Average Directional Index (trend strength)
    - Bollinger Bands: Volatility measurement
    - ATR: Average True Range (price movement)
    
    Strategy Logic:
    1. Wait for EMA 9 to cross above SMA 20
    2. Confirm trend strength with ADX > 20
    3. Confirm volatility with Bollinger Width
    4. Confirm movement potential with ATR
    5. Enter long position if all conditions met
    6. Exit with trailing stop or reverse crossover
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Strategy defaults - usa variables globales cuando están disponibles
        fallback_defaults = {
            # EMA/SMA parameters
            'ema_period': 9,           # Fast EMA period
            'sma_period': 20,          # Slow SMA period
            
            # ADX parameters
            'adx_period': 14,          # ADX calculation period
            'adx_threshold': 20,       # Minimum ADX for trend confirmation
            
            # Bollinger Bands parameters
            'bb_period': 20,           # Bollinger Bands period
            'bb_std': 2.0,            # Standard deviations for bands
            'bb_width_threshold': 0.05, # Minimum BB width (5% of price)
            
            # ATR parameters
            'atr_period': 14,          # ATR calculation period
            'atr_threshold': 0.02,     # Minimum ATR relative to price (2%)
            
            # Entry filters - USAN VARIABLES GLOBALES
            # min_price y max_price se obtienen de [GLOBAL]
            'min_volume': 100000,      # Minimum daily volume
            
            # Exit parameters - USAN VARIABLES GLOBALES
            # trailing_stop_pct usa default_trailing_stop_pct de [GLOBAL]
            'use_crossover_exit': True, # Exit on reverse crossover
            
            # Position management
            'max_positions': 5,        # Maximum concurrent positions
            'position_size_pct': 0.02, # 2% of portfolio per position
            
            # Risk management - USAN VARIABLES GLOBALES
            # stop_loss_pct usa default_stop_loss_pct de [GLOBAL]
            # take_profit_pct usa default_take_profit_pct de [GLOBAL]
        }
        
        super().__init__("JulyStrategy", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('JULY_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for July strategy: {e}")
            # Keep fallback defaults
        
        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🔧 July strategy received parameters: {parameters}")
        
        # Initialize strategy-specific data structures
        self.entry_signals = {}       # Track active entry signals
        self.position_data = {}       # Track position entry data
        self.bars_history = {}        # Store price history for indicators
        self.indicator_cache = {}     # Cache calculated indicators
        
        # Technical indicator periods (for data requirements)
        self.max_period = max(
            int(self._clean_config_value(self._parameters.get('sma_period', 20))),
            int(self._clean_config_value(self._parameters.get('adx_period', 14))),
            int(self._clean_config_value(self._parameters.get('bb_period', 20))),
            int(self._clean_config_value(self._parameters.get('atr_period', 14)))
        ) + 5  # Add buffer for calculations
        
        # Initialize stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        self.logger.info(f"🎯 JulyStrategy initialized:")
        self.logger.info(f"   EMA: {self._clean_config_value(self._parameters.get('ema_period', 9))} | SMA: {self._clean_config_value(self._parameters.get('sma_period', 20))}")
        self.logger.info(f"   ADX threshold: {self._clean_config_value(self._parameters.get('adx_threshold', 20))}")
        self.logger.info(f"   BB width threshold: {float(self._clean_config_value(self._parameters.get('bb_width_threshold', 0.05))):.1%}")
        self.logger.info(f"   ATR threshold: {float(self._clean_config_value(self._parameters.get('atr_threshold', 0.02))):.1%}")
        self.logger.info(f"   Trailing stop: {float(self._clean_config_value(self._parameters.get('default_trailing_stop_pct', 0.08))):.1%}")
    
    @property
    def name(self) -> str:
        return "july_strategy"
    
    @property
    def required_bars(self) -> int:
        """Minimum bars needed for indicator calculations"""
        return self.max_period
    
    def _get_bar_value(self, bar, field: str):
        """Helper to get value from bar regardless if it's MarketData object or dict"""
        if hasattr(bar, field):
            return getattr(bar, field)
        elif isinstance(bar, dict):
            return bar.get(field)
        else:
            raise ValueError(f"Cannot get {field} from bar of type {type(bar)}")
    
    def _clean_config_value(self, value):
        """Clean config values that may have inline comments"""
        if isinstance(value, str):
            # Split by # to remove comments, then by space to get first value
            return str(value).split('#')[0].strip().split()[0]
        return value
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Main analysis method for July Strategy"""
        symbol = self._get_bar_value(bar, 'symbol')
        
        try:
            # Ensure we have enough data
            self._update_price_history(symbol, bar)
            
            if len(self.bars_history.get(symbol, [])) < self.required_bars:
                return None
            
            # Check exit conditions using centralized stop manager
            exit_signal = self.stop_manager.check_exit_conditions(symbol, bar)
            if exit_signal:
                # Clean up position tracking
                if symbol in self.entry_signals:
                    del self.entry_signals[symbol]
                if symbol in self.position_data:
                    del self.position_data[symbol]
                    
                return Signal(
                    signal_id=f"JULY-EXIT-{symbol}-{bar.timestamp}",
                    symbol=symbol,
                    signal_type=SignalType.EXIT_LONG,
                    strength=1.0,
                    price=bar.close,
                    timestamp=bar.timestamp,
                    strategy_name="JulyStrategy",
                    metadata={
                        'reason': exit_signal.get('reason', 'stop_manager'),
                        'strategy': 'JulyStrategy'
                    }
                )
            
            # Skip if already have position
            if symbol in self.entry_signals:
                return None
            
            # Check basic filters first
            if not self._passes_basic_filters(bar):
                return None
            
            # Calculate all indicators
            indicators = self._calculate_indicators(symbol, bar)
            if not indicators:
                return None
            
            # Check for EMA/SMA crossover
            if not self._check_ema_sma_crossover(indicators, symbol):
                return None
            
            # Check momentum and volatility filters
            if not self._check_momentum_filters(indicators, bar):
                return None
            
            # Generate entry signal
            return self._generate_entry_signal(symbol, bar, indicators)
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _update_price_history(self, symbol: str, bar: MarketData):
        """Update price history for indicator calculations"""
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        # Store OHLCV data
        bar_data = {
            'timestamp': self._get_bar_value(bar, 'timestamp'),
            'open': self._get_bar_value(bar, 'open'),
            'high': self._get_bar_value(bar, 'high'),
            'low': self._get_bar_value(bar, 'low'),
            'close': self._get_bar_value(bar, 'close'),
            'volume': self._get_bar_value(bar, 'volume')
        }
        
        self.bars_history[symbol].append(bar_data)
        
        # Keep only required number of bars
        if len(self.bars_history[symbol]) > self.max_period + 10:
            self.bars_history[symbol] = self.bars_history[symbol][-self.max_period:]
    
    def _passes_basic_filters(self, bar: MarketData) -> bool:
        """Check basic price and volume filters using global variables"""
        # Usa variables globales de [GLOBAL] section
        min_price = float(self._clean_config_value(self._parameters.get('min_price', 0.10)))  # Default from GLOBAL
        max_price = float(self._clean_config_value(self._parameters.get('max_price', 15.0)))  # Default from GLOBAL
        min_volume = int(self._clean_config_value(self._parameters.get('min_volume', 100000)))
        
        bar_close = self._get_bar_value(bar, 'close')
        bar_volume = self._get_bar_value(bar, 'volume')
        
        if bar_close < min_price or bar_close > max_price:
            return False
        
        if bar_volume < min_volume:
            return False
        
        return True
    
    def _calculate_indicators(self, symbol: str, bar: MarketData) -> Optional[Dict[str, float]]:
        """Calculate all technical indicators"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < self.required_bars:
                return None
            
            # Convert to arrays for calculations
            closes = np.array([self._get_bar_value(b, 'close') for b in bars])
            highs = np.array([self._get_bar_value(b, 'high') for b in bars])
            lows = np.array([self._get_bar_value(b, 'low') for b in bars])
            volumes = np.array([self._get_bar_value(b, 'volume') for b in bars])
            
            indicators = {}
            
            # EMA 9
            ema_period = int(self._clean_config_value(self._parameters.get('ema_period', 9)))
            indicators['ema'] = self._calculate_ema(closes, ema_period)
            
            # SMA 20
            sma_period = int(self._clean_config_value(self._parameters.get('sma_period', 20)))
            indicators['sma'] = self._calculate_sma(closes, sma_period)
            
            # ADX
            adx_period = int(self._clean_config_value(self._parameters.get('adx_period', 14)))
            indicators['adx'] = self._calculate_adx(highs, lows, closes, adx_period)
            
            # Bollinger Bands
            bb_period = int(self._clean_config_value(self._parameters.get('bb_period', 20)))
            bb_std = float(self._clean_config_value(self._parameters.get('bb_std', 2.0)))
            bb_data = self._calculate_bollinger_bands(closes, bb_period, bb_std)
            indicators.update(bb_data)
            
            # ATR
            atr_period = int(self._clean_config_value(self._parameters.get('atr_period', 14)))
            indicators['atr'] = self._calculate_atr(highs, lows, closes, atr_period)
            bar_close = self._get_bar_value(bar, 'close')
            indicators['atr_relative'] = indicators['atr'] / bar_close if bar_close > 0 else 0
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators for {symbol}: {e}")
            return None
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return prices[-1]
        
        alpha = 2.0 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        
        return np.mean(prices[-period:])
    
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate Average Directional Index"""
        if len(closes) < period + 1:
            return 0.0
        
        try:
            # Calculate True Range
            tr1 = highs[1:] - lows[1:]
            tr2 = np.abs(highs[1:] - closes[:-1])
            tr3 = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            # Calculate Directional Movement
            dm_plus = np.where(highs[1:] - highs[:-1] > lows[:-1] - lows[1:], 
                              np.maximum(highs[1:] - highs[:-1], 0), 0)
            dm_minus = np.where(lows[:-1] - lows[1:] > highs[1:] - highs[:-1], 
                               np.maximum(lows[:-1] - lows[1:], 0), 0)
            
            # Smooth with Wilder's moving average
            alpha = 1.0 / period
            
            atr = tr[0]
            di_plus = dm_plus[0]
            di_minus = dm_minus[0]
            
            for i in range(1, len(tr)):
                atr = alpha * tr[i] + (1 - alpha) * atr
                di_plus = alpha * dm_plus[i] + (1 - alpha) * di_plus
                di_minus = alpha * dm_minus[i] + (1 - alpha) * di_minus
            
            if atr == 0:
                return 0.0
            
            di_plus_pct = 100 * di_plus / atr
            di_minus_pct = 100 * di_minus / atr
            
            di_sum = di_plus_pct + di_minus_pct
            if di_sum == 0:
                return 0.0
            
            dx = 100 * abs(di_plus_pct - di_minus_pct) / di_sum
            
            return dx
            
        except Exception:
            return 0.0
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int, std_dev: float) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            sma = np.mean(prices)
            std = np.std(prices) if len(prices) > 1 else 0
        else:
            recent_prices = prices[-period:]
            sma = np.mean(recent_prices)
            std = np.std(recent_prices)
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        # Calculate band width as percentage of price
        if sma > 0:
            bb_width = (upper_band - lower_band) / sma
        else:
            bb_width = 0
        
        return {
            'bb_upper': upper_band,
            'bb_middle': sma,
            'bb_lower': lower_band,
            'bb_width': bb_width
        }
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate Average True Range"""
        if len(closes) < 2:
            return 0.0
        
        try:
            # Calculate True Range
            tr1 = highs[1:] - lows[1:]
            tr2 = np.abs(highs[1:] - closes[:-1])
            tr3 = np.abs(lows[1:] - closes[:-1])
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            # Calculate ATR (simple average for simplicity)
            if len(tr) < period:
                return np.mean(tr)
            else:
                return np.mean(tr[-period:])
                
        except Exception:
            return 0.0
    
    def _check_ema_sma_crossover(self, indicators: Dict[str, float], symbol: str) -> bool:
        """Check for bullish EMA/SMA crossover with historical data"""
        current_ema = indicators.get('ema', 0)
        current_sma = indicators.get('sma', 0)
        
        if current_ema <= 0 or current_sma <= 0:
            return False
        
        # Need at least 2 bars to detect crossover
        if len(self.bars_history[symbol]) < 2:
            return current_ema > current_sma
        
        # Calculate previous EMA/SMA
        prev_bars = self.bars_history[symbol][:-1]
        if len(prev_bars) < self.required_bars:
            return current_ema > current_sma
            
        prev_closes = np.array([bar['close'] for bar in prev_bars])
        
        ema_period = int(self._clean_config_value(self._parameters.get('ema_period', 9)))
        sma_period = int(self._clean_config_value(self._parameters.get('sma_period', 20)))
        
        prev_ema = self._calculate_ema(prev_closes, ema_period)
        prev_sma = self._calculate_sma(prev_closes, sma_period)
        
        # True crossover: EMA was below SMA and now is above
        crossover_detected = (prev_ema <= prev_sma) and (current_ema > current_sma)
        
        if crossover_detected:
            self.logger.info(f"{symbol}: EMA/SMA Crossover detected! EMA: {current_ema:.2f} > SMA: {current_sma:.2f}")
        
        return crossover_detected
    
    def _check_momentum_filters(self, indicators: Dict[str, float], bar: MarketData) -> bool:
        """Check ADX, Bollinger Width, and ATR filters"""
        
        bar_symbol = self._get_bar_value(bar, 'symbol')
        
        # ADX filter
        adx_threshold = float(self._clean_config_value(self._parameters.get('adx_threshold', 20)))
        adx = indicators.get('adx', 0)
        if adx < adx_threshold:
            self.logger.debug(f"{bar_symbol}: ADX {adx:.1f} < {adx_threshold} (trend too weak)")
            return False
        
        # Bollinger Band Width filter
        bb_width_threshold = float(self._clean_config_value(self._parameters.get('bb_width_threshold', 0.05)))
        bb_width = indicators.get('bb_width', 0)
        if bb_width < bb_width_threshold:
            self.logger.debug(f"{bar_symbol}: BB Width {bb_width:.1%} < {bb_width_threshold:.1%} (volatility too low)")
            return False
        
        # ATR Relative filter
        atr_threshold = float(self._clean_config_value(self._parameters.get('atr_threshold', 0.02)))
        atr_relative = indicators.get('atr_relative', 0)
        if atr_relative < atr_threshold:
            self.logger.debug(f"{bar_symbol}: ATR Relative {atr_relative:.1%} < {atr_threshold:.1%} (movement too low)")
            return False
        
        return True
    
    def _generate_entry_signal(self, symbol: str, bar: MarketData, indicators: Dict[str, float]) -> Signal:
        """Generate entry signal"""
        
        # Calculate signal strength based on indicator values
        strength = self._calculate_signal_strength(indicators, bar)
        
        # Create signal
        bar_close = self._get_bar_value(bar, 'close')
        bar_timestamp = self._get_bar_value(bar, 'timestamp')
        
        signal = Signal(
            signal_id=f"JULY-{symbol}-{bar_timestamp.strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol,
            signal_type=SignalType.LONG,
            strength=strength,
            price=bar_close,
            timestamp=bar_timestamp,
            metadata={
                'strategy': self.name,
                'ema': indicators.get('ema', 0),
                'sma': indicators.get('sma', 0),
                'adx': indicators.get('adx', 0),
                'bb_width': indicators.get('bb_width', 0),
                'atr_relative': indicators.get('atr_relative', 0),
                'entry_reason': 'EMA_SMA_crossover_with_momentum_confirmation'
            }
        )
        
        # Track entry signal
        self.entry_signals[symbol] = {
            'signal': signal,
            'entry_time': bar_timestamp,
            'entry_price': bar_close,
            'indicators': indicators.copy()
        }
        
        # Register with stop loss manager
        self._register_position_with_stop_manager(symbol, bar_close, bar_timestamp)
        
        self.logger.info(f"🎯 JULY ENTRY: {symbol} @ ${bar_close:.2f} | "
                        f"EMA: {indicators.get('ema', 0):.2f} > SMA: {indicators.get('sma', 0):.2f} | "
                        f"ADX: {indicators.get('adx', 0):.1f} | "
                        f"BB Width: {indicators.get('bb_width', 0):.1%} | "
                        f"ATR: {indicators.get('atr_relative', 0):.1%}")
        
        return signal
    
    def _calculate_signal_strength(self, indicators: Dict[str, float], bar: MarketData) -> float:
        """Calculate signal strength based on indicator values"""
        try:
            strength = 0.5  # Base strength
            
            # EMA/SMA spread bonus
            ema = indicators.get('ema', 0)
            sma = indicators.get('sma', 0)
            if sma > 0:
                spread = (ema - sma) / sma
                strength += min(spread * 2, 0.2)  # Max 0.2 bonus
            
            # ADX strength bonus
            adx = indicators.get('adx', 0)
            adx_threshold = self._parameters.get('adx_threshold', 20)
            if adx > adx_threshold:
                adx_bonus = min((adx - adx_threshold) / 30, 0.2)  # Max 0.2 bonus
                strength += adx_bonus
            
            # Volatility bonus
            bb_width = indicators.get('bb_width', 0)
            bb_threshold = self._parameters.get('bb_width_threshold', 0.05)
            if bb_width > bb_threshold:
                vol_bonus = min((bb_width - bb_threshold) * 2, 0.1)  # Max 0.1 bonus
                strength += vol_bonus
            
            return min(max(strength, 0.1), 1.0)  # Clamp between 0.1 and 1.0
            
        except Exception:
            return 0.6  # Default strength
    
    def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Check exit conditions for active positions"""
        if symbol not in self.entry_signals:
            return None
        
        position_data = self.entry_signals[symbol]
        entry_price = position_data['entry_price']
        
        # Calculate current P&L
        bar_close = self._get_bar_value(bar, 'close')
        current_pnl = (bar_close - entry_price) / entry_price
        
        # Trailing stop check - usa variable global
        trailing_stop = self._parameters.get('default_trailing_stop_pct', 0.04)  # Default from GLOBAL
        if current_pnl <= -trailing_stop:
            return self._generate_exit_signal(symbol, bar, 'trailing_stop_loss', current_pnl)
        
        # Crossover exit (if enabled)
        if self._parameters.get('use_crossover_exit', True):
            indicators = self._calculate_indicators(symbol, bar)
            if indicators:
                ema = indicators.get('ema', 0)
                sma = indicators.get('sma', 0)
                
                # Exit if EMA crosses below SMA
                if ema > 0 and sma > 0 and ema < sma:
                    return self._generate_exit_signal(symbol, bar, 'bearish_crossover', current_pnl)
        
        return None
    
    def _generate_exit_signal(self, symbol: str, bar: MarketData, reason: str, pnl: float) -> Signal:
        """Generate exit signal"""
        
        bar_close = self._get_bar_value(bar, 'close')
        bar_timestamp = self._get_bar_value(bar, 'timestamp')
        
        signal = Signal(
            signal_id=f"JULY-EXIT-{symbol}-{bar_timestamp.strftime('%Y%m%d_%H%M%S')}",
            symbol=symbol,
            signal_type=SignalType.EXIT_LONG,
            strength=0.9,  # High confidence for exits
            price=bar_close,
            timestamp=bar_timestamp,
            metadata={
                'strategy': self.name,
                'exit_reason': reason,
                'pnl_pct': pnl,
                'entry_price': self.entry_signals[symbol]['entry_price'],
                'hold_time': (bar_timestamp - self.entry_signals[symbol]['entry_time']).total_seconds() / 60
            }
        )
        
        self.logger.info(f"🚪 JULY EXIT: {symbol} @ ${bar_close:.2f} | "
                        f"Reason: {reason} | P&L: {pnl:.1%}")
        
        # Clean up tracking
        del self.entry_signals[symbol]
        
        return signal
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get current strategy information"""
        return {
            'name': self.name,
            'active_positions': len(self.entry_signals),
            'symbols_tracked': list(self.entry_signals.keys()),
            'parameters': {
                'ema_period': self._parameters.get('ema_period'),
                'sma_period': self._parameters.get('sma_period'),
                'adx_threshold': self._parameters.get('adx_threshold'),
                'bb_width_threshold': self._parameters.get('bb_width_threshold'),
                'atr_threshold': self._parameters.get('atr_threshold'),
                'trailing_stop_pct': self._parameters.get('trailing_stop_pct')
            }
        }
    
    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates from broker"""
        # Required abstract method - can be empty for now
        pass
    
    def should_exit(self, symbol: str, current_price: float, position: Position) -> bool:
        """Determine if position should be exited"""
        # Required abstract method - delegated to _check_exit_conditions
        if symbol in self.entry_signals:
            # Use our exit logic
            return False  # Let _check_exit_conditions handle exits
        return False
    
    def _register_position_with_stop_manager(self, symbol: str, entry_price: float, entry_time: datetime):
        """Register position with centralized stop loss manager"""
        try:
            # Create stop parameters from strategy config
            stop_params = create_stop_params_from_config({
                'stop_loss_pct': float(self._clean_config_value(self._parameters.get('default_stop_loss_pct', 0.08))),
                'trailing_stop_activation': float(self._clean_config_value(self._parameters.get('default_trailing_stop_pct', 0.08))),
                'trailing_stop_distance': 0.04,  # 4% trailing distance
                'take_profit_pct': float(self._clean_config_value(self._parameters.get('default_take_profit_pct', 0.15))),
                'max_hold_minutes': int(self._clean_config_value(self._parameters.get('max_hold_minutes', 360))),
                'end_of_day_exit': True
            })
            
            # Register position
            self.stop_manager.register_position(
                symbol=symbol,
                entry_price=entry_price,
                entry_time=entry_time,
                side='bullish',
                strategy_name=self.name,
                stop_params=stop_params
            )
            
            self.logger.info(f"🛡️ Position registered with Stop Loss Manager: {symbol} @ ${entry_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error registering position with stop manager: {e}")