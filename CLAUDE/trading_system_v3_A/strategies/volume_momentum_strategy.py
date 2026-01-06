# strategies/volume_momentum_strategy.py
"""
Volume-Weighted Momentum Strategy: Intraday strategy that follows momentum 
with volume confirmation for small caps.
"""

from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from enum import Enum

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position


class CandlePattern(Enum):
    """Candlestick patterns for momentum confirmation"""
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    BULLISH_HAMMER = "bullish_hammer"
    BEARISH_HAMMER = "bearish_hammer"
    STRONG_BULLISH = "strong_bullish"
    STRONG_BEARISH = "strong_bearish"
    NEUTRAL = "neutral"


class VolumeMomentumStrategy(BaseStrategy):
    """
    Volume-Weighted Momentum Strategy implementation.
    
    Entry Logic:
    1. Significant volume surge (2x+ average in recent hours)
    2. Price above/below VWAP for direction
    3. Bullish/Bearish candlestick pattern confirmation
    4. Momentum indicators (MACD, ADX) confirm strength
    5. Small cap criteria and spread filters
    
    Exit Logic:
    1. Profit targets based on ATR levels
    2. Volume-based trailing stops
    3. VWAP reversal signals
    4. Time-based exits
    5. Support/resistance levels
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # VALORES POR DEFECTO (fallback) - MAS FLEXIBLES
        default_params = {
            # Volume analysis - Valores más permisivos como fallback
            'volume_surge_multiplier': 2.0,          # Reducido de 2.5 a 2.0
            'volume_lookback_hours': 8,              
            'volume_timeframe_minutes': 30,          
            'min_absolute_volume': 500000,           # Reducido de 750k a 500k
            'float_rotation_threshold': 0.10,        # Reducido de 0.15 a 0.10
            
            # Price and market cap filters
            'min_price': 1.5,                        
            'max_price': 20.0,                       
            'max_market_cap': 750000000,             
            'max_spread_pct': 0.4,                   
            'min_daily_volume': 1000000,             # Reducido de 1.5M a 1M
            
            # VWAP parameters - Más flexibles
            'vwap_period': 15,                       
            'vwap_deviation_threshold': 0.005,       # Reducido de 0.008 a 0.005
            'require_vwap_direction': True,          
            
            # Momentum indicators - Más permisivos
            'use_macd_confirmation': True,           
            'macd_fast': 8,                          
            'macd_slow': 21,                         
            'macd_signal': 8,                        
            'use_adx_filter': False,                 # CAMBIADO: Desactivado por defecto
            'adx_period': 12,                        
            'adx_threshold': 25,                     # Reducido de 28 a 25
            
            # Candlestick patterns - Más flexibles
            'require_candle_pattern': False,         # CAMBIADO: Desactivado por defecto
            'engulfing_min_body_ratio': 0.55,        # Reducido de 0.65 a 0.55
            'hammer_wick_ratio': 2.0,                # Reducido de 2.2 a 2.0
            'strong_candle_min_size': 0.02,          # Reducido de 0.025 a 0.02
            
            # Entry timing and filters
            'market_open_hour': 9.5,                 
            'market_close_hour': 16.0,               
            'no_entry_after_hour': 14.5,             
            'min_time_between_entries': 30,          # Reducido de 45 a 30
            'max_positions_per_symbol': 1,           
            
            # Risk management
            'atr_period': 14,                        
            'stop_loss_atr_mult': 1.5,               # Reducido de 1.7 a 1.5
            'profit_target': 0.15,                   # Reducido de 0.20 a 0.15
            'min_risk_reward': 2.0,                  # Reducido de 2.5 a 2.0
            
            # Trailing stop
            'use_trailing_stop': True,               
            'trailing_activation_pct': 0.08,         # Reducido de 0.10 a 0.08
            'trailing_stop_distance': 0.04,          # Reducido de 0.05 a 0.04
            
            # Position sizing
            'max_position_value': 2000.0,            
            'min_position_value': 400.0,             # Reducido de 500 a 400
            'risk_per_trade': 0.01,                  
            'min_quantity': 100,                     
            'commission_per_share': 0.01,            
            'min_commission': 1.0,                   
            'volume_trail_threshold': 0.7,           
            
            # Multiple timeframe analysis
            'use_multiple_timeframes': False,        # CAMBIADO: Desactivado por defecto
            'signal_timeframe': 5,                   
            'context_timeframe': 15,                 
            
            # Exit conditions
            'use_vwap_reversal_exit': True,          
            'vwap_reversal_threshold': 0.01,         
            'time_based_exit_enabled': True,         
            'max_hold_minutes': 240,                 
            'eod_exit_time': 15.75,                  
            
            # Strategy conditions - MAS FLEXIBLES
            'min_conditions_for_entry': 3,           # CAMBIADO: Reducido de 6 a 3
            'allow_short_positions': True,           
            'require_momentum_acceleration': False,   # CAMBIADO: Desactivado por defecto
            
            # Logging and monitoring
            'log_volume_analysis': True,             
            'log_pattern_detection': True,           
            'log_entry_conditions': True,            
            'log_exit_analysis': True,               
            
            # History requirements
            'min_history_bars': 100,                 
            'max_history_bars': 300                  
        }
        
        # PRIORIDAD AL CONFIG.INI: Si se pasan parámetros externos, sobrescriben defaults
        if parameters:
            # Los parámetros del config.ini tienen PRIORIDAD sobre los defaults
            for key, value in parameters.items():
                default_params[key] = value
        
        super().__init__("VolumeMomentum", default_params)
        
        # Log de configuración final para debug
        self.logger.info(f"🔧 Strategy initialized with config priority:")
        self.logger.info(f"   min_conditions_for_entry: {self._parameters['min_conditions_for_entry']}")
        self.logger.info(f"   require_candle_pattern: {self._parameters['require_candle_pattern']}")
        self.logger.info(f"   volume_surge_multiplier: {self._parameters['volume_surge_multiplier']}")
        self.logger.info(f"   use_adx_filter: {self._parameters['use_adx_filter']}")
        
        # Strategy state
        self.vwap_values = {}                   
        self.volume_profiles = {}               
        self.entry_signals = {}                 
        self.trailing_stops = {}                
        self.last_entry_times = {}              
        self.momentum_data = {}                 
        self.pattern_history = {}
        
        # Breakout tracking for pullback entries
        self.breakout_tracking = {}  # symbol -> {'timestamp': dt, 'price': float, 'momentum_data': dict}               
        
        # Performance tracking
        self.trade_statistics = {
            'total_signals': 0,
            'entries_taken': 0,
            'volume_filtered': 0,
            'pattern_filtered': 0,
            'momentum_filtered': 0,
            'spread_filtered': 0
        }
    
    async def _initialize_strategy(self) -> None:
        """Initialize Volume-Weighted Momentum strategy"""
        self.logger.info("🚀 Initializing Volume-Weighted Momentum Strategy")
        self.logger.info(f"📊 Strategy Parameters: {self.parameters}")
        
        # Log key thresholds
        self.logger.info(f"💰 Position sizing: Max ${self._parameters['max_position_value']}, "
                        f"Risk {self._parameters['max_risk_per_trade']*100:.1f}% per trade")
        self.logger.info(f"📈 Volume criteria: {self._parameters['volume_surge_multiplier']}x surge, "
                        f"Min {self._parameters['min_absolute_volume']:,} volume")
        self.logger.info(f"⏰ Trading hours: {self._parameters['market_open_hour']:.1f} - "
                        f"{self._parameters['no_entry_after_hour']:.1f}")
        
        if self._parameters['log_volume_analysis']:
            self.logger.info("📊 Volume analysis logging enabled")
        if self._parameters['log_pattern_detection']:
            self.logger.info("🕯️ Candlestick pattern logging enabled")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate Volume-Momentum signal"""
        symbol = bar.symbol
        
        # Need sufficient history
        if len(self.bars_history[symbol]) < self._parameters['min_history_bars']:
            if self._parameters['log_entry_conditions']:
                self.logger.debug(f"📊 {symbol}: Insufficient history ({len(self.bars_history[symbol])} bars)")
            return None
        
        try:
            current_time = self._get_time_from_timestamp(bar.timestamp)
            
            # Check trading hours
            if not self._is_trading_hours(current_time):
                return None
            
            # Check if too late for entries
            if current_time >= self._parameters['no_entry_after_hour']:
                return None
            
            # Check time between entries
            if not self._can_enter_new_position(symbol, bar.timestamp):
                return None
            
            self.trade_statistics['total_signals'] += 1
            
            # 1. Volume Analysis
            volume_analysis = self._analyze_volume_surge(symbol, bar)
            if not volume_analysis['surge_detected']:
                self.trade_statistics['volume_filtered'] += 1
                if self._parameters['log_volume_analysis']:
                    self.logger.debug(f"📊 {symbol}: Volume filter failed - "
                                    f"Ratio: {volume_analysis['volume_ratio']:.2f}, "
                                    f"Required: {self._parameters['volume_surge_multiplier']:.2f}")
                return None
            
            # Log volume surge detection
            if self._parameters['log_volume_analysis']:
                self.logger.info(f"📈 {symbol}: Volume surge detected! "
                               f"Ratio: {volume_analysis['volume_ratio']:.2f}x, "
                               f"Current: {bar.volume:,}, Avg: {volume_analysis['avg_volume']:,.0f}")
            
            # 2. Price filters
            if not self._check_price_filters(symbol, bar):
                return None
            
            # 3. Calculate VWAP
            vwap = self._calculate_vwap(symbol)
            if vwap is None:
                return None
            
            self.vwap_values[symbol] = vwap
            
            # 4. Analyze candlestick patterns
            pattern_analysis = self._analyze_candlestick_patterns(symbol, bar)
            if self._parameters['require_candle_pattern'] and pattern_analysis['pattern'] == CandlePattern.NEUTRAL:
                self.trade_statistics['pattern_filtered'] += 1
                if self._parameters['log_pattern_detection']:
                    self.logger.debug(f"🕯️ {symbol}: No valid candlestick pattern detected")
                return None
            
            # Log pattern detection
            if self._parameters['log_pattern_detection'] and pattern_analysis['pattern'] != CandlePattern.NEUTRAL:
                self.logger.info(f"🕯️ {symbol}: Pattern detected - {pattern_analysis['pattern'].value}, "
                               f"Strength: {pattern_analysis['strength']:.2f}")
            
            # 5. Momentum analysis
            momentum_analysis = self._analyze_momentum_indicators(symbol, bar)
            if not momentum_analysis['momentum_confirmed']:
                self.trade_statistics['momentum_filtered'] += 1
                if self._parameters['log_entry_conditions']:
                    self.logger.debug(f"📊 {symbol}: Momentum filter failed - "
                                    f"MACD: {momentum_analysis.get('macd_bullish', 'N/A')}, "
                                    f"ADX: {momentum_analysis.get('adx_value', 'N/A')}")
                return None
            
            # 6. Determine signal direction
            signal_direction = self._determine_signal_direction(bar, vwap, pattern_analysis, momentum_analysis)
            if signal_direction is None:
                return None
            
            # 7. Evaluate all entry conditions
            entry_conditions = self._evaluate_all_entry_conditions(
                symbol, bar, vwap, volume_analysis, pattern_analysis, momentum_analysis, signal_direction
            )
            
            # Count conditions met
            conditions_met = sum(1 for condition in entry_conditions.values() if condition)
            min_conditions = self._parameters['min_conditions_for_entry']
            
            # Log entry condition analysis
            if self._parameters['log_entry_conditions']:
                self.logger.info(f"📋 {symbol}: Entry conditions - {conditions_met}/{len(entry_conditions)} met "
                               f"(need {min_conditions}): {entry_conditions}")
            
            if conditions_met >= min_conditions and signal_direction == 'long':
                # NUEVA LÓGICA: Track momentum y esperar pullback válido
                # Registrar momentum breakout para tracking (no genera señal aún)
                self.breakout_tracking[symbol] = {
                    'timestamp': bar.timestamp,
                    'price': bar.close,
                    'momentum_data': {
                        'volume_surge': volume_surge,
                        'vwap_analysis': vwap_analysis,
                        'entry_conditions': entry_conditions.copy()
                    }
                }
                
                # Verificar si hay pullback válido después del momentum
                pullback_valid = self._check_volume_momentum_pullback(symbol, bar)
                if not pullback_valid:
                    self.logger.debug(f"[{symbol}] Volume momentum breakout registrado @{bar.close:.2f} - esperando pullback de calidad")
                    return None  # No señal aún, solo tracking
                
                # Solo operamos en largo (LONG) - Ignoramos SHORT
                signal_type = SignalType.LONG
                strength = min(conditions_met / len(entry_conditions), 1.0)
                
                # Calculate risk/reward
                atr = self.calculate_atr(symbol, self._parameters['atr_period'])
                risk_reward = self._calculate_risk_reward(bar.close, signal_direction, atr)
                
                if risk_reward < self._parameters['min_risk_reward']:
                    if self._parameters['log_entry_conditions']:
                        self.logger.debug(f"⚠️ {symbol}: Risk/reward too low: {risk_reward:.2f}")
                    return None
                
                self.trade_statistics['entries_taken'] += 1
            else:
                if conditions_met >= min_conditions and signal_direction == 'short':
                    self.logger.debug(f"[{symbol}] Señal SHORT ignorada (solo operamos en LARGO)")
                return None
                
                # Store comprehensive entry data
                self.entry_signals[symbol] = {
                    'entry_price': bar.close,
                    'entry_time': bar.timestamp,
                    'signal_direction': signal_direction,
                    'vwap_at_entry': vwap,
                    'atr_at_entry': atr,
                    'volume_analysis': volume_analysis,
                    'pattern_analysis': pattern_analysis,
                    'momentum_analysis': momentum_analysis,
                    'conditions_met': entry_conditions,
                    'risk_reward_ratio': risk_reward
                }
                
                # Update last entry time
                self.last_entry_times[symbol] = bar.timestamp
                
                # Comprehensive entry log
                self.logger.info(f"🎯 ENTRY SIGNAL: {symbol} {signal_type.value.upper()}")
                self.logger.info(f"   💰 Price: ${bar.close:.2f} | VWAP: ${vwap:.2f} | ATR: ${atr:.3f}")
                self.logger.info(f"   📊 Volume: {bar.volume:,} ({volume_analysis['volume_ratio']:.1f}x avg)")
                self.logger.info(f"   🕯️ Pattern: {pattern_analysis['pattern'].value}")
                # Clean up breakout tracking after successful entry
                if symbol in self.breakout_tracking:
                    del self.breakout_tracking[symbol]
                
                self.logger.info(f"   📈 Momentum: MACD {momentum_analysis.get('macd_bullish', 'N/A')} | "
                               f"ADX {momentum_analysis.get('adx_value', 'N/A'):.1f}")
                self.logger.info(f"   🎲 R/R: {risk_reward:.2f} | Strength: {strength:.2f}")
                
                return Signal(
                    signal_id="",
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=strength,
                    price=bar.close,
                    timestamp=bar.timestamp,
                    metadata={
                        'strategy': 'VolumeMomentum',
                        'signal_direction': signal_direction,
                        'vwap': vwap,
                        'atr': atr,
                        'volume_ratio': volume_analysis['volume_ratio'],
                        'pattern': pattern_analysis['pattern'].value,
                        'risk_reward': risk_reward,
                        'conditions_met': entry_conditions,
                        'momentum_data': momentum_analysis
                    }
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error analyzing bar for {symbol}: {e}", exc_info=True)
            return None
    
    def _analyze_volume_surge(self, symbol: str, current_bar: MarketData) -> Dict[str, Any]:
        """Analyze volume surge patterns"""
        try:
            bars = self.bars_history[symbol]
            
            # Calculate average volume over lookback period
            lookback_bars = min(len(bars), self._parameters['volume_lookback_hours'])
            if lookback_bars < 5:
                return {'surge_detected': False, 'volume_ratio': 0, 'avg_volume': 0}
            
            recent_volumes = [bar.volume for bar in bars[-lookback_bars:-1]]  # Exclude current
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            if avg_volume == 0:
                return {'surge_detected': False, 'volume_ratio': 0, 'avg_volume': 0}
            
            # Calculate volume ratio
            volume_ratio = current_bar.volume / avg_volume
            
            # Check surge criteria
            surge_detected = (
                volume_ratio >= self._parameters['volume_surge_multiplier'] and
                current_bar.volume >= self._parameters['min_absolute_volume']
            )
            
            # Additional volume analysis
            volume_trend = self._calculate_volume_trend(bars[-5:])  # Last 5 bars trend
            
            return {
                'surge_detected': surge_detected,
                'volume_ratio': volume_ratio,
                'avg_volume': avg_volume,
                'current_volume': current_bar.volume,
                'volume_trend': volume_trend,
                'relative_volume_rank': self._calculate_volume_percentile(symbol, current_bar.volume)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing volume surge for {symbol}: {e}")
            return {'surge_detected': False, 'volume_ratio': 0, 'avg_volume': 0}
    
    def _calculate_volume_trend(self, recent_bars: List[MarketData]) -> str:
        """Calculate volume trend over recent bars"""
        if len(recent_bars) < 3:
            return 'neutral'
        
        volumes = [bar.volume for bar in recent_bars]
        
        # Simple trend analysis
        increasing = sum(1 for i in range(1, len(volumes)) if volumes[i] > volumes[i-1])
        decreasing = sum(1 for i in range(1, len(volumes)) if volumes[i] < volumes[i-1])
        
        if increasing > decreasing:
            return 'increasing'
        elif decreasing > increasing:
            return 'decreasing'
        else:
            return 'neutral'
    
    def _calculate_volume_percentile(self, symbol: str, current_volume: int) -> float:
        """Calculate current volume percentile vs recent history"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < 20:
                return 0.5
            
            recent_volumes = [bar.volume for bar in bars[-20:]]
            sorted_volumes = sorted(recent_volumes)
            
            # Find percentile
            position = len([v for v in sorted_volumes if v <= current_volume])
            return position / len(sorted_volumes)
            
        except Exception as e:
            return 0.5
    
    def _check_price_filters(self, symbol: str, bar: MarketData) -> bool:
        """Check price and spread filters"""
        try:
            # Price range check
            if bar.close < self._parameters['min_price'] or bar.close > self._parameters['max_price']:
                return False
            
            # Spread check (approximate using high-low)
            if bar.high > bar.low:
                spread_pct = ((bar.high - bar.low) / bar.close) * 100
                if spread_pct > self._parameters['max_spread_pct']:
                    self.trade_statistics['spread_filtered'] += 1
                    if self._parameters['log_entry_conditions']:
                        self.logger.debug(f"💸 {symbol}: Spread too wide: {spread_pct:.2f}%")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking price filters for {symbol}: {e}")
            return False
    
    def _calculate_vwap(self, symbol: str) -> Optional[float]:
        """Calculate Volume Weighted Average Price"""
        try:
            bars = self.bars_history[symbol]
            period = min(len(bars), self._parameters['vwap_period'])
            
            if period < 5:
                return None
            
            recent_bars = bars[-period:]
            
            total_volume = 0
            total_price_volume = 0
            
            for bar in recent_bars:
                typical_price = (bar.high + bar.low + bar.close) / 3
                price_volume = typical_price * bar.volume
                total_price_volume += price_volume
                total_volume += bar.volume
            
            if total_volume == 0:
                return None
            
            return total_price_volume / total_volume
            
        except Exception as e:
            self.logger.error(f"Error calculating VWAP for {symbol}: {e}")
            return None
    
    def _analyze_candlestick_patterns(self, symbol: str, current_bar: MarketData) -> Dict[str, Any]:
        """Analyze candlestick patterns for momentum confirmation"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < 2:
                return {'pattern': CandlePattern.NEUTRAL, 'strength': 0.0}
            
            prev_bar = bars[-1]
            curr_bar = current_bar
            
            # Calculate candle properties
            curr_body = abs(curr_bar.close - curr_bar.open)
            curr_range = curr_bar.high - curr_bar.low
            prev_body = abs(prev_bar.close - prev_bar.open)
            prev_range = prev_bar.high - prev_bar.low
            
            # Avoid division by zero
            if curr_range == 0 or prev_range == 0:
                return {'pattern': CandlePattern.NEUTRAL, 'strength': 0.0}
            
            curr_body_ratio = curr_body / curr_range
            prev_body_ratio = prev_body / prev_range
            
            pattern = CandlePattern.NEUTRAL
            strength = 0.0
            
            # Bullish Engulfing
            if (curr_bar.close > curr_bar.open and  # Current is bullish
                prev_bar.close < prev_bar.open and  # Previous was bearish
                curr_bar.close > prev_bar.open and  # Current close > prev open
                curr_bar.open < prev_bar.close and  # Current open < prev close
                curr_body_ratio > self._parameters['engulfing_min_body_ratio']):
                pattern = CandlePattern.BULLISH_ENGULFING
                strength = min(curr_body_ratio, 1.0)
            
            # Bearish Engulfing
            elif (curr_bar.close < curr_bar.open and  # Current is bearish
                  prev_bar.close > prev_bar.open and  # Previous was bullish
                  curr_bar.close < prev_bar.open and  # Current close < prev open
                  curr_bar.open > prev_bar.close and  # Current open > prev close
                  curr_body_ratio > self._parameters['engulfing_min_body_ratio']):
                pattern = CandlePattern.BEARISH_ENGULFING
                strength = min(curr_body_ratio, 1.0)
            
            # Strong Bullish Candle
            elif (curr_bar.close > curr_bar.open and
                  curr_body_ratio > 0.7 and
                  ((curr_bar.close - curr_bar.open) / curr_bar.open) > self._parameters['strong_candle_min_size']):
                pattern = CandlePattern.STRONG_BULLISH
                strength = curr_body_ratio
            
            # Strong Bearish Candle
            elif (curr_bar.close < curr_bar.open and
                  curr_body_ratio > 0.7 and
                  ((curr_bar.open - curr_bar.close) / curr_bar.open) > self._parameters['strong_candle_min_size']):
                pattern = CandlePattern.STRONG_BEARISH
                strength = curr_body_ratio
            
            # Hammer patterns (simplified)
            elif curr_body_ratio < 0.3:  # Small body
                lower_wick = min(curr_bar.open, curr_bar.close) - curr_bar.low
                upper_wick = curr_bar.high - max(curr_bar.open, curr_bar.close)
                
                if lower_wick > curr_body * self._parameters['hammer_wick_ratio']:
                    pattern = CandlePattern.BULLISH_HAMMER
                    strength = lower_wick / curr_range
                elif upper_wick > curr_body * self._parameters['hammer_wick_ratio']:
                    pattern = CandlePattern.BEARISH_HAMMER
                    strength = upper_wick / curr_range
            
            return {
                'pattern': pattern,
                'strength': strength,
                'body_ratio': curr_body_ratio,
                'range_size': curr_range / curr_bar.close if curr_bar.close > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing candlestick patterns for {symbol}: {e}")
            return {'pattern': CandlePattern.NEUTRAL, 'strength': 0.0}
    
    def _analyze_momentum_indicators(self, symbol: str, current_bar: MarketData) -> Dict[str, Any]:
        """Analyze momentum indicators (MACD, ADX)"""
        try:
            momentum_data = {
                'momentum_confirmed': False,
                'macd_bullish': None,
                'adx_value': None,
                'momentum_acceleration': False
            }
            
            # MACD Analysis
            if self._parameters['use_macd_confirmation']:
                macd_data = self.calculate_macd(
                    symbol,
                    self._parameters['macd_fast'],
                    self._parameters['macd_slow'],
                    self._parameters['macd_signal']
                )
                
                if macd_data:
                    macd_bullish = macd_data['macd'] > macd_data['signal']
                    momentum_data['macd_bullish'] = macd_bullish
                    momentum_data['macd_histogram'] = macd_data['histogram']
                    
                    # Check for momentum acceleration
                    if symbol in self.momentum_data:
                        prev_histogram = self.momentum_data[symbol].get('macd_histogram', 0)
                        momentum_data['momentum_acceleration'] = abs(macd_data['histogram']) > abs(prev_histogram)
                else:
                    return momentum_data  # Failed MACD calculation
            
            # ADX Analysis
            if self._parameters['use_adx_filter']:
                adx = self.calculate_adx(symbol, self._parameters['adx_period'])
                if adx is not None:
                    momentum_data['adx_value'] = adx
                    adx_strong = adx >= self._parameters['adx_threshold']
                else:
                    adx_strong = True  # Don't filter if can't calculate
            else:
                adx_strong = True
            
            # Overall momentum confirmation
            macd_ok = not self._parameters['use_macd_confirmation'] or momentum_data.get('macd_bullish') is not None
            adx_ok = not self._parameters['use_adx_filter'] or adx_strong
            acceleration_ok = not self._parameters['require_momentum_acceleration'] or momentum_data['momentum_acceleration']
            
            momentum_data['momentum_confirmed'] = macd_ok and adx_ok and acceleration_ok
            
            # Store for next iteration
            self.momentum_data[symbol] = momentum_data.copy()
            
            return momentum_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing momentum indicators for {symbol}: {e}")
            return {'momentum_confirmed': False}
    
    def _determine_signal_direction(self, bar: MarketData, vwap: float, 
                                  pattern_analysis: Dict, momentum_analysis: Dict) -> Optional[str]:
        """Determine signal direction based on price action and indicators"""
        try:
            # VWAP direction
            price_vs_vwap = bar.close - vwap
            vwap_deviation_pct = abs(price_vs_vwap / vwap)
            
            # Must have sufficient deviation from VWAP
            if vwap_deviation_pct < self._parameters['vwap_deviation_threshold']:
                return None
            
            # Determine base direction from VWAP
            if bar.close > vwap:
                base_direction = 'long'
            else:
                base_direction = 'short'
            
            # Check if short positions are allowed
            if base_direction == 'short' and not self._parameters['allow_short_positions']:
                return None
            
            # Confirm with pattern analysis
            pattern = pattern_analysis['pattern']
            pattern_supports_direction = False
            
            if base_direction == 'long':
                pattern_supports_direction = pattern in [
                    CandlePattern.BULLISH_ENGULFING,
                    CandlePattern.STRONG_BULLISH,
                    CandlePattern.BULLISH_HAMMER
                ]
            else:  # short
                pattern_supports_direction = pattern in [
                    CandlePattern.BEARISH_ENGULFING,
                    CandlePattern.STRONG_BEARISH,
                    CandlePattern.BEARISH_HAMMER
                ]
            
            # Confirm with MACD if available
            macd_supports_direction = True
            if momentum_analysis.get('macd_bullish') is not None:
                if base_direction == 'long':
                    macd_supports_direction = momentum_analysis['macd_bullish']
                else:
                    macd_supports_direction = not momentum_analysis['macd_bullish']
            
            # Final direction confirmation
            if self._parameters['require_candle_pattern'] and not pattern_supports_direction:
                return None
            
            if not macd_supports_direction:
                return None
            
            return base_direction
            
        except Exception as e:
            self.logger.error(f"Error determining signal direction: {e}")
            return None
    
    def _evaluate_all_entry_conditions(self, symbol: str, bar: MarketData, vwap: float,
                                     volume_analysis: Dict, pattern_analysis: Dict,
                                     momentum_analysis: Dict, signal_direction: str) -> Dict[str, bool]:
        """Evaluate all entry conditions comprehensively"""
        conditions = {}
        
        try:
            # 1. Volume surge confirmed
            conditions['volume_surge'] = volume_analysis['surge_detected']
            
            # 2. VWAP direction alignment
            if signal_direction == 'long':
                conditions['vwap_alignment'] = bar.close > vwap
            else:
                conditions['vwap_alignment'] = bar.close < vwap
            
            # 3. Pattern confirmation
            pattern = pattern_analysis['pattern']
            if signal_direction == 'long':
                conditions['pattern_confirmation'] = pattern in [
                    CandlePattern.BULLISH_ENGULFING, CandlePattern.STRONG_BULLISH, CandlePattern.BULLISH_HAMMER
                ]
            else:
                conditions['pattern_confirmation'] = pattern in [
                    CandlePattern.BEARISH_ENGULFING, CandlePattern.STRONG_BEARISH, CandlePattern.BEARISH_HAMMER
                ]
            
            # 4. Momentum confirmation
            conditions['momentum_confirmed'] = momentum_analysis['momentum_confirmed']
            
            # 5. Volume trend alignment
            volume_trend = volume_analysis.get('volume_trend', 'neutral')
            conditions['volume_trend_ok'] = volume_trend in ['increasing', 'neutral']
            
            # 6. Price action quality
            conditions['price_action_quality'] = self._check_price_action_quality(symbol, bar)
            
            # 7. Risk/reward feasible
            atr = self.calculate_atr(symbol, self._parameters['atr_period'])
            if atr:
                risk_reward = self._calculate_risk_reward(bar.close, signal_direction, atr)
                conditions['risk_reward_ok'] = risk_reward >= self._parameters['min_risk_reward']
            else:
                conditions['risk_reward_ok'] = False
            
            # 8. Time window appropriate
            current_time = self._get_time_from_timestamp(bar.timestamp)
            conditions['time_window_ok'] = (
                self._parameters['market_open_hour'] <= current_time <= self._parameters['no_entry_after_hour']
            )
            
            # 9. No recent entry (avoid overtrading)
            conditions['no_recent_entry'] = self._check_no_recent_entry(symbol, bar.timestamp)
            
            return conditions
            
        except Exception as e:
            self.logger.error(f"Error evaluating entry conditions for {symbol}: {e}")
            return {'error': False}
    
    def _check_price_action_quality(self, symbol: str, current_bar: MarketData) -> bool:
        """Check overall price action quality"""
        try:
            bars = self.bars_history[symbol]
            if len(bars) < 5:
                return True
            
            # Check for clean price action (no excessive gaps or erratic movement)
            recent_bars = bars[-5:] + [current_bar]
            
            # Calculate average true range as percentage
            atr_pcts = []
            for i in range(1, len(recent_bars)):
                prev_bar = recent_bars[i-1]
                curr_bar = recent_bars[i]
                
                high_low = curr_bar.high - curr_bar.low
                high_prev_close = abs(curr_bar.high - prev_bar.close)
                low_prev_close = abs(curr_bar.low - prev_bar.close)
                
                true_range = max(high_low, high_prev_close, low_prev_close)
                atr_pct = (true_range / curr_bar.close) * 100 if curr_bar.close > 0 else 0
                atr_pcts.append(atr_pct)
            
            # Price action is good if ATR is reasonable (not too volatile)
            avg_atr_pct = sum(atr_pcts) / len(atr_pcts) if atr_pcts else 0
            return avg_atr_pct < 8.0  # Less than 8% average true range
            
        except Exception as e:
            self.logger.error(f"Error checking price action quality for {symbol}: {e}")
            return True
    
    def _calculate_risk_reward(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate risk/reward ratio for the trade"""
        try:
            if not atr or atr <= 0:
                return 0.0
            
            stop_distance = atr * self._parameters['stop_loss_atr_mult']
            profit_distance = atr * self._parameters['profit_target_1_atr']
            
            if stop_distance <= 0:
                return 0.0
            
            return profit_distance / stop_distance
            
        except Exception as e:
            self.logger.error(f"Error calculating risk/reward: {e}")
            return 0.0
    
    def _check_no_recent_entry(self, symbol: str, current_timestamp) -> bool:
        """Check if enough time has passed since last entry"""
        try:
            if symbol not in self.last_entry_times:
                return True
            
            last_entry = self.last_entry_times[symbol]
            
            if isinstance(current_timestamp, (int, float)):
                current_dt = datetime.fromtimestamp(current_timestamp)
            else:
                current_dt = current_timestamp
            
            if isinstance(last_entry, (int, float)):
                last_dt = datetime.fromtimestamp(last_entry)
            else:
                last_dt = last_entry
            
            time_diff = (current_dt - last_dt).total_seconds() / 60  # Minutes
            
            return time_diff >= self._parameters['min_time_between_entries']
            
        except Exception as e:
            self.logger.error(f"Error checking recent entry for {symbol}: {e}")
            return True
    
    def _can_enter_new_position(self, symbol: str, timestamp) -> bool:
        """Check if we can enter a new position for this symbol"""
        # Check time between entries
        if not self._check_no_recent_entry(symbol, timestamp):
            return False
        
        # Check max positions per symbol
        current_positions = getattr(self, 'current_positions', {})
        symbol_positions = len([p for p in current_positions.values() if p.symbol == symbol])
        
        return symbol_positions < self._parameters['max_positions_per_symbol']
    
    def _check_strategy_exit(self, position: Position, current_bar: MarketData) -> Optional[str]:
        """Volume-Momentum specific exit conditions optimized for small accounts"""
        try:
            symbol = position.symbol
            
            # Check if we have entry signal info
            if symbol not in self.entry_signals:
                return None
            
            entry_info = self.entry_signals[symbol]
            entry_price = entry_info['entry_price']
            signal_direction = entry_info['signal_direction']
            
            # Initialize tracking values if they don't exist
            if 'highest_price' not in entry_info:
                entry_info['highest_price'] = entry_price if signal_direction == 'long' else float('inf')
            if 'lowest_price' not in entry_info:
                entry_info['lowest_price'] = entry_price if signal_direction == 'bearish' else float('inf')
            
            # Update highest/lowest price seen
            current_price = current_bar.close
            if signal_direction == 'long':
                entry_info['highest_price'] = max(entry_info['highest_price'], current_price)
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
            else:  # short
                entry_info['lowest_price'] = min(entry_info['lowest_price'], current_price)
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
            
            # Log current P&L status periodically
            if self._parameters.get('log_exit_analysis', True) and current_bar.timestamp.minute % 15 == 0:
                self.logger.info(f"📊 {symbol}: Current P&L: {pnl_pct:.2f}% from entry {entry_price:.2f}")
            
            # 1. Initial Stop Loss - Based on ATR or fixed percentage
            atr_at_entry = entry_info.get('atr_at_entry', 0)
            if atr_at_entry > 0:
                stop_loss_pct = (atr_at_entry * self._parameters.get('stop_loss_atr_mult', 1.7) / entry_price) * 100
            else:
                stop_loss_pct = self._parameters.get('stop_loss_pct', 7.0)
                
            if pnl_pct <= -stop_loss_pct:
                self.logger.info(f"🛑 {symbol}: Stop loss hit - P&L: {pnl_pct:.2f}%")
                return "stop_loss"
            
            # 2. Trailing Stop (only if we've reached activation threshold)
            trailing_activation = self._parameters.get('trailing_activation_pct', 10.0)
            if pnl_pct >= trailing_activation:
                trailing_distance = self._parameters.get('trailing_stop_distance', 5.0)
                
                if signal_direction == 'long':
                    trailing_stop_price = entry_info['highest_price'] * (1 - trailing_distance/100)
                    if current_price <= trailing_stop_price:
                        self.logger.info(f"🔄 {symbol}: Trailing stop hit at {current_price:.2f} - "
                                       f"Max: {entry_info['highest_price']:.2f}, P&L: {pnl_pct:.2f}%")
                        return "trailing_stop"
                else:  # short
                    trailing_stop_price = entry_info['lowest_price'] * (1 + trailing_distance/100)
                    if current_price >= trailing_stop_price:
                        self.logger.info(f"🔄 {symbol}: Trailing stop hit at {current_price:.2f} - "
                                       f"Min: {entry_info['lowest_price']:.2f}, P&L: {pnl_pct:.2f}%")
                        return "trailing_stop"
            
            # 3. Profit Target - Single ambitious target
            profit_target = self._parameters.get('profit_target', 20.0)
            if pnl_pct >= profit_target:
                self.logger.info(f"🎯 {symbol}: Profit target hit - P&L: {pnl_pct:.2f}%")
                return "profit_target"
            
            # 4. VWAP reversal exit (mantenido por ser un buen filtro técnico)
            if self._parameters.get('use_vwap_reversal_exit', True):
                vwap_exit = self._check_vwap_reversal_exit(symbol, current_bar, signal_direction)
                if vwap_exit:
                    return vwap_exit
            
            # 5. Momentum loss exit (mantenido por ser un buen filtro técnico)
            momentum_exit = self._check_momentum_loss_exit(symbol, current_bar, signal_direction)
            if momentum_exit:
                return momentum_exit
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error checking strategy exit for {symbol}: {e}")
            return None
    
    def _check_volume_trailing_exit(self, symbol: str, current_bar: MarketData, 
                                  entry_info: Dict, current_pnl_pct: float) -> Optional[str]:
        """Check volume-based trailing stop"""
        try:
            atr_at_entry = entry_info.get('atr_at_entry', 0)
            activation_pct = (atr_at_entry * self._parameters['trailing_activation_atr'] / entry_info['entry_price']) * 100
            
            # Only activate trailing if we're in profit above activation threshold
            if current_pnl_pct < activation_pct:
                return None
            
            # Check volume decline
            current_volume_ratio = self._analyze_volume_surge(symbol, current_bar)['volume_ratio']
            entry_volume_ratio = entry_info['volume_analysis']['volume_ratio']
            
            volume_decline_ratio = current_volume_ratio / entry_volume_ratio
            
            if volume_decline_ratio < self._parameters['volume_trail_threshold']:
                if self._parameters['log_exit_analysis']:
                    self.logger.info(f"📉 {symbol}: Volume trailing exit - Volume declined to {volume_decline_ratio:.2f}x entry")
                return "volume_trailing"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking volume trailing exit for {symbol}: {e}")
            return None
    
    def _check_vwap_reversal_exit(self, symbol: str, current_bar: MarketData, signal_direction: str) -> Optional[str]:
        """Check VWAP reversal exit"""
        try:
            current_vwap = self._calculate_vwap(symbol)
            if not current_vwap:
                return None
            
            reversal_threshold = self._parameters['vwap_reversal_threshold']
            
            if signal_direction == 'long':
                # Exit long if price falls significantly below VWAP
                if current_bar.close < current_vwap * (1 - reversal_threshold):
                    if self._parameters['log_exit_analysis']:
                        self.logger.info(f"📉 {symbol}: VWAP reversal exit (long) - Price: ${current_bar.close:.2f}, VWAP: ${current_vwap:.2f}")
                    return "vwap_reversal"
            else:
                # Exit short if price rises significantly above VWAP
                if current_bar.close > current_vwap * (1 + reversal_threshold):
                    if self._parameters['log_exit_analysis']:
                        self.logger.info(f"📈 {symbol}: VWAP reversal exit (short) - Price: ${current_bar.close:.2f}, VWAP: ${current_vwap:.2f}")
                    return "vwap_reversal"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking VWAP reversal exit for {symbol}: {e}")
            return None
    
    def _check_time_based_exit(self, symbol: str, current_bar: MarketData, entry_info: Dict) -> Optional[str]:
        """Check time-based exit"""
        try:
            entry_time = entry_info['entry_time']
            
            if isinstance(current_bar.timestamp, (int, float)):
                current_dt = datetime.fromtimestamp(current_bar.timestamp)
            else:
                current_dt = current_bar.timestamp
            
            if isinstance(entry_time, (int, float)):
                entry_dt = datetime.fromtimestamp(entry_time)
            else:
                entry_dt = entry_time
            
            hold_time_minutes = (current_dt - entry_dt).total_seconds() / 60
            
            if hold_time_minutes >= self._parameters['max_hold_minutes']:
                if self._parameters['log_exit_analysis']:
                    self.logger.info(f"⏰ {symbol}: Time-based exit - Held for {hold_time_minutes:.1f} minutes")
                return "time_based"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking time-based exit for {symbol}: {e}")
            return None
    
    def _check_momentum_loss_exit(self, symbol: str, current_bar: MarketData, signal_direction: str) -> Optional[str]:
        """Check for momentum loss exit"""
        try:
            # Get current momentum
            current_momentum = self._analyze_momentum_indicators(symbol, current_bar)
            
            if not current_momentum['momentum_confirmed']:
                if self._parameters['log_exit_analysis']:
                    self.logger.info(f"📊 {symbol}: Momentum loss exit - Momentum no longer confirmed")
                return "momentum_loss"
            
            # Check MACD direction reversal
            if current_momentum.get('macd_bullish') is not None:
                if signal_direction == 'long' and not current_momentum['macd_bullish']:
                    if self._parameters['log_exit_analysis']:
                        self.logger.info(f"📊 {symbol}: MACD reversal exit (long)")
                    return "macd_reversal"
                elif signal_direction == 'short' and current_momentum['macd_bullish']:
                    if self._parameters['log_exit_analysis']:
                        self.logger.info(f"📊 {symbol}: MACD reversal exit (short)")
                    return "macd_reversal"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking momentum loss exit for {symbol}: {e}")
            return None
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for Volume-Momentum strategy optimized for small accounts
        
        Args:
            signal: Trading signal with price and symbol information
            capital: Available trading capital
            risk_per_trade: Risk percentage per trade (0.0 to 1.0)
            
        Returns:
            int: Number of shares to trade, or 0 if position cannot be taken
        """
        try:
            symbol = signal.symbol
            price = signal.price
            
            # Early exit if price itself exceeds max allowable position value
            max_position_value_param = self._parameters.get('max_position_value', 2000.0)
            if price > max_position_value_param:
                self.logger.info(
                    f"🚫 {symbol}: Price ${price:.2f} exceeds max_position_value ${max_position_value_param:.2f}. Skipping trade."
                )
                return 0
            
            # 1. Calculate base position size based on risk
            risk_amount = capital * min(risk_per_trade, self._parameters.get('risk_per_trade', 0.01))
            
            # Get stop distance based on ATR or fixed percentage
            atr = self.calculate_atr(symbol, self._parameters.get('atr_period', 14))
            if atr and atr > 0:
                stop_distance = atr * self._parameters.get('stop_loss_atr_mult', 1.7)
            else:
                stop_loss_pct = self._parameters.get('stop_loss_pct', 0.07)
                stop_distance = price * stop_loss_pct
            
            # 2. Calculate minimum viable position size to cover commissions
            min_commission = self._parameters.get('min_commission', 1.0)
            commission_per_share = self._parameters.get('commission_per_share', 0.01)
            
            # Minimum position value to make trade viable after commissions
            min_position_value = max(
                self._parameters.get('min_position_value', 500.0),
                (min_commission * 2) / 0.01  # Ensure at least 1% profit covers commissions
            )
            
            # 3. Calculate base quantity
            if stop_distance > 0:
                base_quantity = int(risk_amount / stop_distance)
                
                # Calculate position value and adjust if below minimum
                position_value = base_quantity * price
                if position_value < min_position_value:
                    base_quantity = int(min_position_value / price) + 1
            else:
                base_quantity = int(min_position_value / price) + 1
            
            # 4. Apply position limits
            # Max shares based on max position value
            max_position_value = self._parameters.get('max_position_value', 2000.0)
            max_shares_value = int(max_position_value / price)
            
            # Max shares based on max risk per trade (5% of capital)
            max_shares_risk = int((capital * 0.05) / price)
            
            # Take the more restrictive limit
            max_shares = min(max_shares_value, max_shares_risk)
            
            # Scale based on volume if enabled (mantenido por ser útil)
            if (self._parameters.get('position_scale_on_volume', False) and 
                symbol in self.entry_signals and 
                'volume_analysis' in self.entry_signals[symbol]):
                volume_ratio = self.entry_signals[symbol]['volume_analysis'].get('volume_ratio', 1.0)
                volume_multiplier = min(volume_ratio / 2.0, 1.5)  # Cap at 1.5x
                base_quantity = int(base_quantity * volume_multiplier)
            
            # 5. Round down to nearest 100 for small caps
            if price < 10.0:  # Para acciones de bajo precio
                position_size = (int(min(base_quantity, max_shares)) // 100) * 100
                position_size = max(position_size, self._parameters.get('min_quantity', 100))
            else:  # Para acciones de mayor precio
                position_size = int(min(base_quantity, max_shares))
                position_size = max(position_size, self._parameters.get('min_quantity', 100))
            
            # 6. Calculate estimated commissions
            total_commission = (position_size * commission_per_share * 2) + (min_commission * 2)
            position_value = position_size * price
            commission_pct = (total_commission / position_value) * 100 if position_value > 0 else 0
            
            # Log detailed position sizing decision
            self.logger.info(
                f"💰 {symbol}: Position size - {position_size} shares @ ${price:.2f} = ${position_value:,.2f} "
                f"(Value: ${position_value:,.2f}, Comm: ${total_commission:.2f} = {commission_pct:.2f}%)"
            )
            
            # 7. Log warning if commission is too high relative to position size
            if commission_pct > 1.0:  # More than 1% in commissions
                self.logger.warning(
                    f"⚠️ High commission impact ({commission_pct:.2f}%) for {symbol}. "
                    f"Consider increasing position size or finding lower commission options."
                )
            
            return max(0, position_size)  # Ensure we don't return negative quantities
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating position size for {signal.symbol}: {e}")
            return 0  # Return 0 on error to prevent invalid position sizes
    
    # Helper methods
    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hour"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            else:
                dt = timestamp
            return dt.hour + dt.minute / 60.0
        except Exception as e:
            self.logger.error(f"Error converting timestamp: {e}")
            return 0.0
    
    def _is_trading_hours(self, time_decimal: float) -> bool:
        """Check if in trading hours"""
        return (self._parameters['market_open_hour'] <= time_decimal <= 
                self._parameters['market_close_hour'])
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """Get detailed strategy statistics"""
        return {
            **self.trade_statistics,
            'success_rate': (
                (self.trade_statistics['entries_taken'] / max(self.trade_statistics['total_signals'], 1)) * 100
            ),
            'active_positions': len(self.entry_signals),
            'symbols_tracked': len(self.vwap_values)
        }
    
    def _check_volume_momentum_pullback(self, symbol: str, bar: MarketData) -> bool:
        """Check if we should enter after a pullback from volume momentum"""
        try:
            # Must have tracked breakout first
            if symbol not in self.breakout_tracking:
                return False
                
            # Need sufficient history to detect pullback
            if len(self.bars_history[symbol]) < 5:  # Reduced from 12 to 5
                return False
            
            breakout_data = self.breakout_tracking[symbol]
            breakout_price = breakout_data['price']
            current_price = bar.close
            
            # Get recent bars for pullback analysis
            recent_bars = self.bars_history[symbol][-5:]  # Reduced lookback
            
            # IMPROVED VOLUME MOMENTUM PULLBACK ANALYSIS using tracked breakout
            # 1. Find the highest point since momentum breakout
            highs_since_breakout = [b.high for b in recent_bars if b.timestamp >= breakout_data['timestamp']]
            if not highs_since_breakout:
                return False
                
            recent_high = max(highs_since_breakout)
            
            # 2. Find recent low (pullback point)
            lows_last_2 = [b.low for b in recent_bars[-2:]]
            recent_low = min(lows_last_2)
            
            # 3. Calculate pullback from breakout reference
            pullback_from_high = (recent_high - recent_low) / recent_high if recent_high > recent_low else 0
            
            # More lenient pullback requirements for volume momentum
            min_pullback = 0.004  # 0.4% minimum pullback (reduced from 0.6%)
            if pullback_from_high < min_pullback:
                return False
            
            # 4. Price recovery confirmation
            recovery_threshold = recent_low * 1.001  # Only 0.1% above low needed
            if current_price <= recovery_threshold:
                return False
            
            # 5. Don't chase - reasonable distance from breakout
            max_chase_pct = 0.06  # 6% above breakout for volume momentum
            if current_price > breakout_price * (1 + max_chase_pct):
                return False
            
            # 6. Volume analysis - pullback should be on lower volume
            recent_volume_avg = sum(b.volume for b in recent_bars[-3:]) / 3
            if bar.volume > recent_volume_avg * 1.5:  # Current volume not too high
                return False
                
            self.logger.info(f"[{symbol}] Volume momentum pullback entry confirmed: Breakout@{breakout_price:.2f}, High={recent_high:.2f}, Low={recent_low:.2f}, Current={current_price:.2f}, Pullback={pullback_from_high*100:.1f}%")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking volume momentum pullback for {symbol}: {e}")
            return False
    
    def _cleanup_old_breakout_tracking(self):
        """Clean up breakout tracking entries older than 30 minutes"""
        try:
            from datetime import datetime, timedelta
            import pandas as pd
            
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(minutes=30)
            
            symbols_to_remove = []
            for symbol, data in self.breakout_tracking.items():
                try:
                    timestamp = data['timestamp']
                    if isinstance(timestamp, str):
                        timestamp = pd.to_datetime(timestamp)
                    elif hasattr(timestamp, 'to_pydatetime'):
                        timestamp = timestamp.to_pydatetime()
                    
                    if hasattr(timestamp, 'replace'):
                        timestamp = timestamp.replace(tzinfo=None)
                    
                    if timestamp < cutoff_time:
                        symbols_to_remove.append(symbol)
                        
                except Exception as e:
                    self.logger.debug(f"Error processing timestamp for {symbol}: {e}")
                    symbols_to_remove.append(symbol)
            
            for symbol in symbols_to_remove:
                del self.breakout_tracking[symbol]
                self.logger.debug(f"Cleaned up old Volume Momentum breakout tracking for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Error in Volume Momentum breakout tracking cleanup: {e}")
    
    def get_strategy_info(self) -> dict:
        """Get strategy-specific information"""
        stats = self.get_strategy_statistics()
        
        return {
            "name": self.name,
            "type": "Volume-Weighted Momentum",
            "timeframe": "Intraday (Small Caps)",
            "parameters": self.parameters,
            "statistics": stats,
            "active_signals": len(self.entry_signals),
            "performance": self.get_performance_stats()
        }
    
    def log_daily_summary(self):
        """Log daily strategy summary"""
        stats = self.get_strategy_statistics()
        
        self.logger.info("📊 === VOLUME MOMENTUM DAILY SUMMARY ===")
        self.logger.info(f"🎯 Signals processed: {stats['total_signals']}")
        self.logger.info(f"✅ Entries taken: {stats['entries_taken']}")
        self.logger.info(f"📊 Success rate: {stats['success_rate']:.1f}%")
        self.logger.info(f"🚫 Filtered - Volume: {stats['volume_filtered']}, "
                        f"Pattern: {stats['pattern_filtered']}, "
                        f"Momentum: {stats['momentum_filtered']}, "
                        f"Spread: {stats['spread_filtered']}")
        self.logger.info(f"📈 Active positions: {stats['active_positions']}")
        self.logger.info("=" * 50)
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For VolumeMomentum strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - required by IStrategy interface"""
        try:
            # Basic stop loss for positions
            if position.quantity > 0:  # Long position
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="VolumeMomentum",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            elif position.quantity < 0:  # Short position  
                stop_loss_pct = 0.05  # 5% default stop loss
                stop_price = position.avg_price * (1 + stop_loss_pct)
                
                if current_bar.close >= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="VolumeMomentum",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None
