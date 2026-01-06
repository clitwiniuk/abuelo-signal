# strategies/eod_momentum_strategy.py
"""
End-Of-Day Momentum Strategy

Edge-based strategy designed for the last 2 hours of market session (14:00-16:00 ET).
Exploits institutional rebalancing, final momentum moves, and volume patterns.

Key Edges:
1. Volume acceleration in final 2 hours indicates institutional activity
2. Breakouts after 14:00 have higher follow-through rates
3. Mean reversion opportunities on extreme moves near close
4. VWAP positioning becomes more significant near EOD
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from strategies.base import BaseStrategy
from core.interfaces import Signal, SignalType, Position, MarketData
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
# Technical indicators - simple implementations
def calculate_rsi(prices, period=14):
    """Simple RSI calculation"""
    if len(prices) < period + 1:
        return pd.Series([50] * len(prices), index=prices.index)
    
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_vwap(df):
    """Simple VWAP calculation"""
    if 'volume' not in df.columns or len(df) == 0:
        return pd.Series([df['close'].iloc[-1]] * len(df), index=df.index)
    
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap.fillna(typical_price)

def calculate_atr(df, period=14):
    """Simple ATR calculation"""
    if len(df) < 2:
        return pd.Series([df['close'].iloc[-1] * 0.02] * len(df), index=df.index)
    
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().fillna(df['close'] * 0.02)


@dataclass
class EODSignal:
    """Enhanced signal with EOD-specific metadata"""
    signal_type: SignalType
    confidence: float
    edge_type: str  # 'momentum', 'breakout', 'reversion', 'institutional'
    vwap_position: float
    volume_acceleration: float
    time_to_close_minutes: int
    risk_level: str  # 'low', 'medium', 'high'


class EndOfDayMomentumStrategy(BaseStrategy):
    """
    End-Of-Day Momentum Strategy with Multiple Edges
    
    Combines several proven EOD patterns:
    - Volume acceleration (institutional flow)
    - Breakout continuation (momentum edge) 
    - VWAP mean reversion (statistical edge)
    - Time-decay positioning (closing urgency)
    """

    def __init__(self, params: Dict = None):
        # FALLBACK DEFAULTS - Usado solo si config.ini no existe o está incompleto
        fallback_defaults = {
            # Core EOD parameters
            'active_start_hour': 14.0,  # 14:00 ET
            'active_end_hour': 16.0,     # 16:00 ET
            'min_time_to_close': 15,   # Min 15 min before close
            
            # Volume Edge Parameters
            'volume_acceleration_threshold': 1.8,
            'volume_lookback_periods': 30,  # 30 min lookback
            'min_absolute_volume': 50000,
            
            # Momentum Edge Parameters  
            'momentum_breakout_threshold': 0.015,  # 1.5%
            'momentum_confirmation_periods': 3,
            'rsi_momentum_min': 40,
            'rsi_momentum_max': 85,
            
            # VWAP Edge Parameters
            'vwap_deviation_entry': 0.012,  # 1.2%
            'vwap_reversion_threshold': 0.025,  # 2.5%
            'vwap_trend_min': 0.008,  # Min trend for momentum
            
            # Risk Management
            'max_risk_near_close': 0.015,  # 1.5% max risk
            'position_sizing_factor': 0.8,  # Reduce size for EOD
            'atr_risk_multiplier': 1.5,
            
            # Entry Filters
            'min_conditions_for_entry': 3,
            'required_edge_types': ['momentum', 'volume']
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("eod_momentum", fallback_defaults)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('EOD_MOMENTUM_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if params:
                config_params.update(params)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for EOD_Momentum strategy: {e}")
            # Keep fallback defaults
        
        # Core EOD parameters
        self.active_start_hour = float(config_params.get('active_start_hour', 14.0))  # 14:00 ET
        self.active_end_hour = float(config_params.get('active_end_hour', 16.0))     # 16:00 ET
        self.min_time_to_close = config_params.get('min_time_to_close', 15)   # Min 15 min before close
        
        # Volume Edge Parameters
        self.volume_acceleration_threshold = config_params.get('volume_acceleration_threshold', 1.8)
        self.volume_lookback_periods = config_params.get('volume_lookback_periods', 30)  # 30 min lookback
        self.min_absolute_volume = config_params.get('min_absolute_volume', 50000)
        
        # Momentum Edge Parameters  
        self.momentum_breakout_threshold = config_params.get('momentum_breakout_threshold', 0.015)  # 1.5%
        self.momentum_confirmation_periods = config_params.get('momentum_confirmation_periods', 3)
        self.rsi_momentum_min = config_params.get('rsi_momentum_min', 40)
        self.rsi_momentum_max = config_params.get('rsi_momentum_max', 85)
        
        # VWAP Edge Parameters
        self.vwap_deviation_entry = config_params.get('vwap_deviation_entry', 0.012)  # 1.2%
        self.vwap_reversion_threshold = config_params.get('vwap_reversion_threshold', 0.025)  # 2.5%
        self.vwap_trend_min = config_params.get('vwap_trend_min', 0.008)  # Min trend for momentum
        
        # Risk Management
        self.max_risk_near_close = config_params.get('max_risk_near_close', 0.015)  # 1.5% max risk
        self.position_sizing_factor = config_params.get('position_sizing_factor', 0.8)  # Reduce size for EOD
        self.atr_risk_multiplier = config_params.get('atr_risk_multiplier', 1.5)
        
        # Entry Filters
        self.min_conditions_for_entry = config_params.get('min_conditions_for_entry', 3)
        self.required_edge_types = config_params.get('required_edge_types', ['momentum', 'volume'])
        
        # Performance tracking
        self.edge_performance = {
            'momentum': {'signals': 0, 'wins': 0},
            'breakout': {'signals': 0, 'wins': 0},
            'reversion': {'signals': 0, 'wins': 0},
            'institutional': {'signals': 0, 'wins': 0}
        }
        
        
        self.logger.info(f"🕐 EOD Strategy initialized: {self.active_start_hour:.1f}h-{self.active_end_hour:.1f}h ET")

    def is_active(self, current_time: datetime) -> bool:
        """Check if strategy should be active based on time"""
        # Convert to US Eastern Time decimal hours
        us_hour = current_time.hour + current_time.minute / 60.0
        
        is_time_active = self.active_start_hour <= us_hour <= self.active_end_hour
        
        if not is_time_active:
            if us_hour < self.active_start_hour:
                next_active = f"Active in {(self.active_start_hour - us_hour) * 60:.0f} minutes"
            else:
                next_active = "Market closing soon"
            self.logger.debug(f"⏰ EOD Strategy inactive at US {us_hour:.2f}h ({next_active})")
            
        return is_time_active

    async def _initialize_strategy(self) -> None:
        """Strategy-specific initialization logic"""
        self.logger.info("🎯 EOD Momentum Strategy initialized")
        pass
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate signal - implement in subclasses"""
        signals = self.analyze(bar)
        return signals[0] if signals else None
    
    def analyze(self, data: MarketData) -> List[Signal]:
        """Analyze market data for EOD opportunities"""
        current_time = datetime.now()
        
        if not self.is_active(current_time):
            return []
            
        # TEMPORARY FIX: Skip analysis if no DataFrame available
        # This strategy needs DataFrame conversion from MarketData history
        if not hasattr(data, 'df') or data.df is None:
            return []
            
        if len(data.df) < 50:
            return []

        try:
            # Calculate time to market close
            time_to_close = self._calculate_time_to_close(current_time)
            if time_to_close < self.min_time_to_close:
                return []  # Too close to market close

            # Calculate all technical indicators
            indicators = self._calculate_indicators(data.df)
            if not indicators:
                return []

            # Analyze different edges
            edges_detected = []
            
            # 1. Volume Acceleration Edge (Institutional Flow)
            volume_edge = self._analyze_volume_acceleration(data.df, indicators)
            if volume_edge:
                edges_detected.append(volume_edge)
                
            # 2. Momentum Breakout Edge
            momentum_edge = self._analyze_momentum_breakout(data.df, indicators)  
            if momentum_edge:
                edges_detected.append(momentum_edge)
                
            # 3. VWAP Mean Reversion Edge
            vwap_edge = self._analyze_vwap_positioning(data.df, indicators)
            if vwap_edge:
                edges_detected.append(vwap_edge)

            # 4. Institutional Flow Edge (Large volume + price confirmation)
            institutional_edge = self._analyze_institutional_flow(data.df, indicators)
            if institutional_edge:
                edges_detected.append(institutional_edge)

            # Generate signals based on edge confluence
            signals = self._generate_signals_from_edges(
                data, edges_detected, indicators, time_to_close
            )
            
            if signals:
                self.logger.info(f"🎯 EOD: {len(signals)} signals from {len(edges_detected)} edges ({data.symbol})")
                
            return signals

        except Exception as e:
            self.logger.error(f"❌ EOD analysis error for {data.symbol}: {e}")
            return []

    def _calculate_time_to_close(self, current_time: datetime) -> int:
        """Calculate minutes remaining until market close (16:00 ET)"""
        current_hour = current_time.hour + current_time.minute / 60.0
        close_hour = 16.0
        
        if current_hour >= close_hour:
            return 0
            
        return int((close_hour - current_hour) * 60)

    def _calculate_indicators(self, df: pd.DataFrame) -> Optional[Dict]:
        """Calculate all required technical indicators"""
        try:
            latest = df.iloc[-1]
            
            # Basic price indicators
            sma_20 = df['close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else latest['close']
            sma_10 = df['close'].rolling(10).mean().iloc[-1] if len(df) >= 10 else latest['close']
            
            # Volume indicators
            avg_volume = df['volume'].rolling(self.volume_lookback_periods).mean().iloc[-1] if len(df) >= self.volume_lookback_periods else latest['volume']
            
            # VWAP (today's VWAP)
            vwap = calculate_vwap(df)
            current_vwap = vwap.iloc[-1] if len(vwap) > 0 else latest['close']
            
            # RSI
            rsi = calculate_rsi(df['close'], period=14)
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # ATR for volatility
            atr = calculate_atr(df, period=14)
            current_atr = atr.iloc[-1] if len(atr) > 0 else latest['close'] * 0.02
            
            # Price momentum (last 10 periods)
            if len(df) >= 10:
                price_momentum = (latest['close'] - df['close'].iloc[-10]) / df['close'].iloc[-10]
            else:
                price_momentum = 0
                
            # Volume acceleration (current vs average)
            volume_acceleration = latest['volume'] / avg_volume if avg_volume > 0 else 1.0
            
            return {
                'current_price': latest['close'],
                'current_volume': latest['volume'],
                'sma_20': sma_20,
                'sma_10': sma_10,
                'avg_volume': avg_volume,
                'vwap': current_vwap,
                'rsi': current_rsi,
                'atr': current_atr,
                'price_momentum': price_momentum,
                'volume_acceleration': volume_acceleration,
                'high_of_day': df['high'].max(),
                'low_of_day': df['low'].min(),
                'df': df
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return None

    def _analyze_volume_acceleration(self, df: pd.DataFrame, indicators: Dict) -> Optional[Dict]:
        """Detect institutional volume acceleration edge"""
        volume_accel = indicators['volume_acceleration']
        current_volume = indicators['current_volume']
        
        # Volume acceleration edge conditions
        has_volume_spike = volume_accel >= self.volume_acceleration_threshold
        has_absolute_volume = current_volume >= self.min_absolute_volume
        
        # Additional confirmation: volume trend over last few periods
        recent_volume_trend = 0
        if len(df) >= 5:
            recent_volumes = df['volume'].tail(5)
            if recent_volumes.is_monotonic_increasing:
                recent_volume_trend = 1
                
        if has_volume_spike and has_absolute_volume:
            confidence = min(0.95, 0.5 + (volume_accel - self.volume_acceleration_threshold) * 0.1 + recent_volume_trend * 0.15)
            
            return {
                'edge_type': 'institutional',
                'confidence': confidence,
                'volume_acceleration': volume_accel,
                'reasoning': f"Volume spike {volume_accel:.1f}x avg ({current_volume:,})"
            }
            
        return None

    def _analyze_momentum_breakout(self, df: pd.DataFrame, indicators: Dict) -> Optional[Dict]:
        """Detect momentum breakout edge"""
        current_price = indicators['current_price']
        price_momentum = indicators['price_momentum']
        rsi = indicators['rsi']
        high_of_day = indicators['high_of_day']
        low_of_day = indicators['low_of_day']
        
        # Breakout conditions
        is_near_hod = (current_price / high_of_day) >= 0.995  # Within 0.5% of HOD
        is_near_lod = (current_price / low_of_day) <= 1.005   # Within 0.5% of LOD
        has_momentum = abs(price_momentum) >= self.momentum_breakout_threshold
        rsi_in_range = self.rsi_momentum_min <= rsi <= self.rsi_momentum_max
        
        # Momentum direction
        is_bullish_breakout = is_near_hod and price_momentum > 0 and rsi < 80
        is_bearish_breakout = is_near_lod and price_momentum < 0 and rsi > 20
        
        if (is_bullish_breakout or is_bearish_breakout) and has_momentum and rsi_in_range:
                
            # Additional confirmation: price above/below key SMAs
            sma_confirmation = False
            if is_bullish_breakout and current_price > indicators['sma_10']:
                sma_confirmation = True
            elif is_bearish_breakout and current_price < indicators['sma_10']:
                sma_confirmation = True
                
            confidence = 0.6 + abs(price_momentum) * 10 + (0.1 if sma_confirmation else 0)
            confidence = min(0.9, confidence)
            
            return {
                'edge_type': 'breakout',
                'confidence': confidence,
                'direction': 'bullish' if is_bullish_breakout else 'bearish',
                'price_momentum': price_momentum,
                'reasoning': f"{'Bullish' if is_bullish_breakout else 'Bearish'} breakout {price_momentum*100:.1f}%"
            }
            
        return None

    def _analyze_vwap_positioning(self, df: pd.DataFrame, indicators: Dict) -> Optional[Dict]:
        """Detect VWAP positioning edge"""
        current_price = indicators['current_price']
        vwap = indicators['vwap']
        
        if vwap == 0:
            return None
            
        vwap_deviation = (current_price - vwap) / vwap
        abs_deviation = abs(vwap_deviation)
        
        # VWAP edges
        # 1. Mean reversion opportunity (extreme deviation)
        if abs_deviation >= self.vwap_reversion_threshold:
            confidence = 0.5 + min(0.3, (abs_deviation - self.vwap_reversion_threshold) * 5)
            
            return {
                'edge_type': 'reversion',
                'confidence': confidence,
                'vwap_deviation': vwap_deviation,
                'direction': 'bearish' if vwap_deviation > 0 else 'bullish',
                'reasoning': f"VWAP reversion {vwap_deviation*100:.1f}%"
            }
            
        # 2. Momentum continuation (moderate deviation with trend)
        elif abs_deviation >= self.vwap_deviation_entry:
            # Check if there's a trend supporting the deviation
            price_momentum = indicators['price_momentum']
            
            if abs(price_momentum) >= self.vwap_trend_min:
                # Direction alignment
                deviation_bullish = vwap_deviation > 0 and price_momentum > 0
                deviation_bearish = vwap_deviation < 0 and price_momentum < 0
                
                if deviation_bullish or deviation_bearish:
                    confidence = 0.4 + abs_deviation * 3 + abs(price_momentum) * 2
                    confidence = min(0.85, confidence)
                    
                    return {
                        'edge_type': 'momentum',
                        'confidence': confidence,
                        'vwap_deviation': vwap_deviation,
                        'direction': 'bullish' if deviation_bullish else 'bearish',
                        'reasoning': f"VWAP momentum {vwap_deviation*100:.1f}%"
                    }
                    
        return None

    def _analyze_institutional_flow(self, df: pd.DataFrame, indicators: Dict) -> Optional[Dict]:
        """Detect large institutional order flow"""
        current_volume = indicators['current_volume']
        avg_volume = indicators['avg_volume']
        price_momentum = indicators['price_momentum']
        
        # Large volume with directional price movement suggests institutional flow
        volume_threshold = self.volume_acceleration_threshold * 1.5  # Higher threshold
        has_large_volume = (current_volume / avg_volume) >= volume_threshold
        has_directional_move = abs(price_momentum) >= 0.01  # 1% minimum move
        
        if has_large_volume and has_directional_move and current_volume >= self.min_absolute_volume * 2:
            # Check for sustained flow (last few bars)
            sustained_flow = False
            if len(df) >= 3:
                recent_volumes = df['volume'].tail(3)
                if all(v >= avg_volume * 1.2 for v in recent_volumes):  # All above average
                    sustained_flow = True
                    
            confidence = 0.55 + (current_volume / avg_volume - volume_threshold) * 0.05
            if sustained_flow:
                confidence += 0.15
                
            confidence = min(0.9, confidence)
            
            return {
                'edge_type': 'institutional',
                'confidence': confidence,
                'volume_ratio': current_volume / avg_volume,
                'direction': 'bullish' if price_momentum > 0 else 'bearish',
                'sustained': sustained_flow,
                'reasoning': f"Institutional flow {current_volume/avg_volume:.1f}x volume"
            }
            
        return None

    def _generate_signals_from_edges(self, data: MarketData, edges: List[Dict], 
                                   indicators: Dict, time_to_close: int) -> List[Signal]:
        """Generate trading signals from detected edges"""
        if not edges:
            return []
            
        signals = []
        
        # Check if we have required edge types
        edge_types_detected = {edge['edge_type'] for edge in edges}
        required_met = any(req_type in edge_types_detected for req_type in self.required_edge_types)
        
        if not required_met:
            return []
            
        # Count conditions met
        conditions_met = 0
        total_confidence = 0
        primary_direction = None
        edge_reasons = []
        
        # Analyze edge confluence
        bullish_edges = [e for e in edges if e.get('direction') == 'bullish']
        bearish_edges = [e for e in edges if e.get('direction') == 'bearish']
        
        for edge in edges:
            conditions_met += 1
            total_confidence += edge['confidence']
            edge_reasons.append(edge['reasoning'])
            
            # Determine primary direction from highest confidence edge
            if primary_direction is None or edge['confidence'] > max([e['confidence'] for e in edges if e.get('direction') == primary_direction], default=0):
                primary_direction = edge.get('direction')
        
        # Require minimum conditions
        if conditions_met < self.min_conditions_for_entry:
            return []
            
        # Calculate final confidence
        avg_confidence = total_confidence / len(edges)
        
        # Direction confluence bonus/penalty
        if len(bullish_edges) > 0 and len(bearish_edges) > 0:
            # Conflicting signals - reduce confidence
            avg_confidence *= 0.7
        elif len(bullish_edges) >= 2 or len(bearish_edges) >= 2:
            # Multiple edges in same direction - boost confidence
            avg_confidence *= 1.15
            
        avg_confidence = min(0.95, avg_confidence)
        
        # Risk adjustment based on time to close
        risk_multiplier = 1.0
        if time_to_close < 30:  # Less than 30 minutes
            risk_multiplier = 0.7  # Reduce position size
            avg_confidence *= 0.9  # Slight confidence reduction
            
        # Determine signal type and create signal
        if primary_direction == 'bullish' and avg_confidence >= 0.5:
            signal_type = SignalType.LONG
        elif primary_direction == 'bearish' and avg_confidence >= 0.5:
            signal_type = SignalType.SHORT
        else:
            return []  # Not confident enough
            
        # Create signal with EOD-specific metadata
        signal = Signal(
            strategy_name=self.name,
            symbol=data.symbol,
            signal_type=signal_type,
            confidence=avg_confidence,
            price=indicators['current_price'],
            timestamp=datetime.now(),
            metadata={
                'edge_types': list(edge_types_detected),
                'conditions_met': conditions_met,
                'time_to_close': time_to_close,
                'vwap_deviation': indicators.get('vwap_deviation', 0),
                'volume_acceleration': indicators['volume_acceleration'],
                'risk_multiplier': risk_multiplier,
                'reasoning': ' | '.join(edge_reasons[:3])  # Limit reasoning length
            }
        )
        
        
        signals.append(signal)
        
        # Track edge performance
        for edge in edges:
            edge_type = edge['edge_type']
            if edge_type in self.edge_performance:
                self.edge_performance[edge_type]['signals'] += 1
                
        self.logger.info(f"📊 EOD Signal: {signal_type.value} {data.symbol} confidence={avg_confidence:.2f} "
                        f"edges={list(edge_types_detected)} time_to_close={time_to_close}min")
                        
        return signals

    def get_performance_metrics(self) -> Dict:
        """Get performance metrics for each edge type"""
        metrics = {}
        for edge_type, stats in self.edge_performance.items():
            if stats['signals'] > 0:
                win_rate = stats['wins'] / stats['signals']
                metrics[f"{edge_type}_win_rate"] = win_rate
                metrics[f"{edge_type}_signals"] = stats['signals']
            else:
                metrics[f"{edge_type}_win_rate"] = 0
                metrics[f"{edge_type}_signals"] = 0
                
        return metrics
    
    
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For EODMomentum strategy, we don't need special logic on position updates
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
                        strategy_name="EODMomentum",
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
                        strategy_name="EODMomentum",
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
