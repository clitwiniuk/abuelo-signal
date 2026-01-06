#!/usr/bin/env python3
"""
Ultra Simple Explosion Strategy
===============================

ULTRA permissive strategy designed specifically for synthetic explosion data.
Almost no filters - if there's an explosion in the data, we enter.

PHILOSOPHY: The synthetic data IS the signal. Don't overthink it.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import IStrategy, Signal, SignalType, Position, MarketData
from .base import BaseStrategy


class UltraSimpleExplosionStrategy(BaseStrategy):
    """
    Ultra permissive strategy for explosion data
    
    ONLY requirements:
    1. Volume > 0 (basic sanity check)
    2. Price movement exists
    3. In trading hours
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # Initialize with name
        self._name = "UltraSimpleExplosion"
        self.logger = logging.getLogger(f"Strategy.{self._name}")
        
        # MINIMAL parameters
        default_params = {
            # Almost no thresholds
            'volume_threshold': 1.0,              # Any volume > average
            'momentum_threshold': 0.0,            # ANY momentum (even 0%)
            'min_history_bars': 2,                # Only 2 bars minimum
            
            # Basic config
            'max_position_value': 500.0,          
            'cooldown_minutes': 1,                # 1min cooldown
            'max_daily_signals': 50,              # Many signals allowed
            
            # Wide trading hours
            'start_hour': 4.0,                    # 4:00 AM (premarket)
            'end_hour': 20.0,                     # 8:00 PM (aftermarket)
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__("UltraSimpleExplosion", default_params)
        
        # Minimal state
        self.bars_history: Dict[str, List[MarketData]] = {}
        self.last_signal_time: Dict[str, datetime] = {}
        self.daily_signals_count = 0
        self.last_date = None
        
        self.logger.info("🔥 Ultra Simple Explosion Strategy - MAXIMUM PERMISSIVE MODE!")
    
    async def _initialize_strategy(self) -> None:
        """Initialize strategy"""
        self.logger.info("🚀 Ultra Simple Explosion - Ready to catch EVERYTHING!")
        self.logger.info(f"🎯 ULTRA PERMISSIVE MODE: Almost no filters")
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar - ultra simple"""
        return await self.on_bar(bar)
    
    async def on_bar(self, bar: MarketData) -> Optional[Signal]:
        """Ultra simple processing with debug logging"""
        
        symbol = bar.symbol
        
        # Only log every 10th bar to reduce noise
        if len(self.bars_history.get(symbol, [])) % 10 == 0:
            self.logger.info(f"🔍 Processing bar {len(self.bars_history.get(symbol, []))}: {symbol} @ {bar.timestamp} | Close: ${bar.close:.2f}")
        
        # Reset daily counter
        self._reset_daily_counter(bar.timestamp)
        
        # Daily limit
        if self.daily_signals_count >= self._parameters['max_daily_signals']:
            self.logger.info(f"❌ Daily signal limit reached: {self.daily_signals_count}")
            return None
        
        # Basic trading hours (very wide)
        if not self._is_trading_hours(bar.timestamp):
            self.logger.info(f"❌ Outside trading hours: {bar.timestamp.hour}:{bar.timestamp.minute}")
            return None
        
        # Update history
        self._update_bars_history(bar)
        
        # Need minimal history
        if len(self.bars_history.get(symbol, [])) < self._parameters['min_history_bars']:
            self.logger.info(f"❌ Not enough history: {len(self.bars_history.get(symbol, []))} < {self._parameters['min_history_bars']}")
            return None
        
        # Cooldown
        if self._is_in_cooldown(symbol, bar.timestamp):
            self.logger.info(f"❌ In cooldown")
            return None
        
        # CONDITION 1: Volume exists (almost no threshold)
        if not self._has_volume(bar):
            self.logger.info(f"❌ Volume check failed")
            return None
        
        # CONDITION 2: ANY price movement
        if not self._has_movement(bar):
            self.logger.info(f"❌ Movement check failed")
            return None
        
        # ✅ GENERATE SIGNAL - We made it through the minimal filters!
        signal = Signal(
            signal_id=f"ultra_{symbol}_{int(bar.timestamp.timestamp())}",
            signal_type=SignalType.LONG,
            symbol=symbol,
            strength=0.8,  # High strength since data is pre-filtered
            price=bar.close,
            timestamp=bar.timestamp,
            strategy_name="UltraSimpleExplosion",
            metadata={
                'strategy': 'UltraSimpleExplosion',
                'volume': bar.volume,
                'volume_ratio': self._get_volume_ratio(bar),
                'momentum': self._get_momentum(bar),
                'entry_type': 'ultra_permissive'
            }
        )
        
        # Update state
        self.last_signal_time[symbol] = bar.timestamp
        self.daily_signals_count += 1
        
        self.logger.info(
            f"🔥 ULTRA ENTRY: {symbol} @ ${bar.close:.2f} | "
            f"Vol: {self._get_volume_ratio(bar):.1f}x | "
            f"Move: {self._get_momentum(bar):+.2%}"
        )
        
        return signal
    
    def _has_volume(self, bar: MarketData) -> bool:
        """CONDITION 1: Has volume (ultra permissive with debug)"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 3:  # Need at least 3 bars (including current)
            result = bar.volume > 0
            self.logger.info(f"🔍 Volume check (early): {bar.volume} > 0 = {result}")
            return result
        
        # Compare current bar with average of previous 2 bars (excluding current)
        previous_volumes = [b.volume for b in bars[-3:-1]]  # Get 2 bars before current
        avg_volume = np.mean(previous_volumes)
        
        if avg_volume <= 0:
            result = bar.volume > 0
            self.logger.info(f"🔍 Volume check (zero avg): {bar.volume} > 0 = {result}")
            return result
        
        # Ultra low threshold
        volume_ratio = bar.volume / avg_volume
        threshold = self._parameters['volume_threshold']
        result = volume_ratio >= threshold
        
        self.logger.info(f"🔍 Volume check: {bar.volume}/{avg_volume:.0f} = {volume_ratio:.2f}x >= {threshold} = {result}")
        return result
    
    def _has_movement(self, bar: MarketData) -> bool:
        """CONDITION 2: Has ANY price movement with debug"""
        
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 2:
            self.logger.info(f"🔍 Movement check (early): True (not enough history)")
            return True  # If we don't have history, assume movement exists
        
        # Check movement vs previous bar
        prev_bar = bars[-2]
        momentum = (bar.close - prev_bar.close) / prev_bar.close
        threshold = self._parameters['momentum_threshold']
        result = abs(momentum) >= threshold
        
        self.logger.info(f"🔍 Movement check: {bar.close:.2f} vs {prev_bar.close:.2f} = {momentum:+.4f} >= {threshold} = {result}")
        return result
    
    def _get_volume_ratio(self, bar: MarketData) -> float:
        """Helper: volume ratio"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 2:
            return 1.0
        
        recent_volumes = [b.volume for b in bars[-2:]]
        avg_volume = np.mean(recent_volumes)
        
        return bar.volume / avg_volume if avg_volume > 0 else 1.0
    
    def _get_momentum(self, bar: MarketData) -> float:
        """Helper: momentum"""
        symbol = bar.symbol
        bars = self.bars_history[symbol]
        
        if len(bars) < 2:
            return 0.0
        
        prev_bar = bars[-2]
        return (bar.close - prev_bar.close) / prev_bar.close
    
    def _update_bars_history(self, bar: MarketData) -> None:
        """Maintain minimal history"""
        symbol = bar.symbol
        
        if symbol not in self.bars_history:
            self.bars_history[symbol] = []
        
        self.bars_history[symbol].append(bar)
        
        # Keep only what we need
        if len(self.bars_history[symbol]) > 5:
            self.bars_history[symbol] = self.bars_history[symbol][-5:]
    
    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """Ultra wide trading hours"""
        if timestamp.weekday() >= 5:
            return False
        
        hour_decimal = timestamp.hour + timestamp.minute / 60.0
        return (self._parameters['start_hour'] <= hour_decimal <= self._parameters['end_hour'])
    
    def _is_in_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """Ultra short cooldown"""
        if symbol not in self.last_signal_time:
            return False
        
        time_diff = current_time - self.last_signal_time[symbol]
        return time_diff.total_seconds() / 60 < self._parameters['cooldown_minutes']
    
    def _reset_daily_counter(self, current_time: datetime) -> None:
        """Reset daily counter"""
        current_date = current_time.date()
        
        if self.last_date != current_date:
            self.daily_signals_count = 0
            self.last_date = current_date
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Strategy info"""
        return {
            'name': 'UltraSimpleExplosionStrategy',
            'version': '1.0',
            'description': 'Ultra permissive - catches almost every explosion',
            'complexity_score': 1,  # ULTRA SIMPLE
            'conditions_count': 2,   # Only 2 basic conditions
            'parameters': {
                'volume_threshold': self._parameters['volume_threshold'],
                'momentum_threshold': self._parameters['momentum_threshold'],
                'min_history_bars': self._parameters['min_history_bars']
            },
            'daily_signals_used': f"{self.daily_signals_count}/{self._parameters['max_daily_signals']}",
            'optimal_for': [
                'synthetic_explosion_data',
                'maximum_signal_capture',
                'testing_data_quality',
                'minimum_filters'
            ],
            'entry_style': 'ultra_permissive',
            'risk_profile': 'aggressive'
        }


# Helper functions
def create_ultra_simple_strategy(custom_params: Dict[str, Any] = None) -> UltraSimpleExplosionStrategy:
    """Create ultra simple instance"""
    return UltraSimpleExplosionStrategy(custom_params)
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For UltraSimpleExplosion strategy, we don't need special logic on position updates
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
                        strategy_name="UltraSimpleExplosion",
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
                        strategy_name="UltraSimpleExplosion",
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
