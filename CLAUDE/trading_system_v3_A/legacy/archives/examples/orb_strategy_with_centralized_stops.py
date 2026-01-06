# examples/orb_strategy_with_centralized_stops.py
"""
Example of how to modify ORB Strategy to use the centralized stop loss manager.
This demonstrates the unified approach that eliminates code duplication.
"""

from typing import Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, time, timedelta

from strategies.base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class ORBStrategyWithCentralizedStops(BaseStrategy):
    """
    ORB Strategy modified to use centralized stop loss management.
    
    BEFORE: Each strategy implemented its own stop loss logic (duplicated code)
    AFTER: All stop loss logic is centralized and shared across strategies
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            # Opening range parameters
            'opening_range_minutes': 15,
            'range_min_size': 0.02,
            'range_max_size': 0.15,
            
            # Volume parameters
            'volume_spike_threshold': 2.5,
            'volume_confirmation_threshold': 2.0,
            'volume_period': 20,
            'min_dollar_volume': 200000,
            
            # Price filters
            'min_price': 2.00,
            'max_price': 12.00,
            'max_gap_size': 0.15,
            
            # Risk management (will be handled by centralized manager)
            'stop_loss_pct': 0.05,
            'profit_target': 0.15,
            'trailing_stop_activation': 0.08,
            'trailing_stop_distance': 0.04,
            'max_hold_minutes': 240,
            'end_of_day_exit': True,
            
            # Position sizing
            'max_position_value': 300.0,
            'min_position_value': 80.0,
            'risk_per_trade': 0.008,
            'min_quantity': 10,
            
            # Signal control
            'signal_cooldown_bars': 10,
            'max_signals_per_symbol': 1,
            'min_conditions': 2
        }
        
        # Merge with provided parameters
        if parameters:
            default_params.update(parameters)
        
        super().__init__(default_params)
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # ORB-specific tracking (no longer includes stop loss logic)
        self.opening_ranges = {}
        self.breakout_signals = {}
        self.last_signal_time = {}
        
        self.logger.info("🎯 ORB Strategy initialized with centralized stop loss management")
    
    async def analyze(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Main analysis method - now simplified without stop loss logic
        """
        try:
            # 1. Check for exit signals using centralized manager
            exit_signal = self.stop_manager.check_exit_conditions(symbol, bar)
            if exit_signal:
                # Clean up our tracking when position exits
                self._cleanup_position_tracking(symbol)
                return exit_signal
            
            # 2. Skip entry analysis if we already have a position for this symbol
            if symbol in self.breakout_signals:
                return None
            
            # 3. Update opening range
            self._update_opening_range(symbol, bar)
            
            # 4. Check for entry signals
            entry_signal = self._check_entry_conditions(symbol, bar)
            if entry_signal:
                # Register position with centralized stop manager
                self._register_position_with_stop_manager(symbol, bar, entry_signal)
            
            return entry_signal
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with centralized stop loss manager"""
        
        # Create stop loss parameters from strategy config
        stop_params = create_stop_params_from_config(self._parameters)
        
        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.LONG else 'bearish'
        
        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="ORB",
            stop_params=stop_params
        )
        
        # Still track breakout info for our strategy logic (but not stop losses)
        self.breakout_signals[symbol] = {
            'entry_price': signal.price,
            'entry_time': bar.timestamp,
            'direction': side,
            'range_info': self.opening_ranges[symbol].copy(),
            # Note: No stop_price, target_price, highest_price, etc.
            # These are now handled by the centralized manager
        }
        
        self.logger.info(f"✅ Registered {symbol} position with centralized stop manager")
    
    def _cleanup_position_tracking(self, symbol: str):
        """Clean up our tracking when position exits"""
        if symbol in self.breakout_signals:
            del self.breakout_signals[symbol]
        
        # Note: No need to cleanup stop loss tracking - that's handled by the manager
    
    def _update_opening_range(self, symbol: str, bar: MarketData):
        """Update opening range for symbol (unchanged from original)"""
        if symbol not in self.opening_ranges:
            self.opening_ranges[symbol] = {
                'start_time': bar.timestamp,
                'high': bar.high,
                'low': bar.low,
                'volume': bar.volume,
                'range_defined': False
            }
        else:
            range_info = self.opening_ranges[symbol]
            
            # Update range if still within opening period
            range_minutes = (bar.timestamp - range_info['start_time']).total_seconds() / 60
            
            if range_minutes <= self._parameters['opening_range_minutes']:
                range_info['high'] = max(range_info['high'], bar.high)
                range_info['low'] = min(range_info['low'], bar.low)
                range_info['volume'] += bar.volume
            elif not range_info['range_defined']:
                # Define the range
                range_info['range_defined'] = True
                range_size = (range_info['high'] - range_info['low']) / range_info['low']
                
                self.logger.info(f"📊 Opening range defined for {symbol}: "
                               f"High={range_info['high']:.3f}, Low={range_info['low']:.3f}, "
                               f"Size={range_size:.1%}")
    
    def _check_entry_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Check for ORB entry conditions.
        SIMPLIFIED: No longer contains stop loss calculations!
        """
        if symbol not in self.opening_ranges:
            return None
        
        range_info = self.opening_ranges[symbol]
        
        if not range_info['range_defined']:
            return None
        
        # Check if we're still in cooldown
        if self._is_in_signal_cooldown(symbol, bar):
            return None
        
        # Calculate range metrics
        range_high = range_info['high']
        range_low = range_info['low']
        range_size = (range_high - range_low) / range_low
        
        # 1. Range size filter
        if not (self._parameters['range_min_size'] <= range_size <= self._parameters['range_max_size']):
            return None
        
        # 2. Price filters
        if not (self._parameters['min_price'] <= bar.close <= self._parameters['max_price']):
            return None
        
        # 3. Volume spike check
        avg_volume = self._get_average_volume(symbol, bar)
        if avg_volume == 0:
            return None
        
        volume_ratio = bar.volume / avg_volume
        if volume_ratio < self._parameters['volume_spike_threshold']:
            return None
        
        # 4. Breakout detection
        signal_type = None
        breakout_strength = 0.0
        
        # Bullish breakout
        if bar.close > range_high:
            breakout_distance = (bar.close - range_high) / range_high
            if breakout_distance >= self._parameters.get('breakout_min_size', 0.01):
                signal_type = SignalType.LONG
                breakout_strength = min(breakout_distance * 10, 1.0)  # Normalize to 0-1
        
        # Bearish breakout
        elif bar.close < range_low:
            breakout_distance = (range_low - bar.close) / range_low
            if breakout_distance >= self._parameters.get('breakout_min_size', 0.01):
                signal_type = SignalType.SHORT
                breakout_strength = min(breakout_distance * 10, 1.0)
        
        if signal_type is None:
            return None
        
        # 5. Final validation
        conditions_met = self._count_entry_conditions(symbol, bar, range_info, volume_ratio)
        if conditions_met < self._parameters['min_conditions']:
            return None
        
        # Create signal (simplified - no stop loss calculations here!)
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=breakout_strength,
            price=bar.close,
            timestamp=bar.timestamp,
            metadata={
                'strategy': 'ORB',
                'range_size': range_size,
                'volume_ratio': volume_ratio,
                'breakout_distance': breakout_distance if 'breakout_distance' in locals() else 0,
                'conditions_met': conditions_met,
                'range_high': range_high,
                'range_low': range_low,
                # Note: No stop_price, target_price - handled by centralized manager
            }
        )
        
        self.last_signal_time[symbol] = bar.timestamp
        
        self.logger.info(f"🎯 ORB signal for {symbol}: {signal_type.value} @ {bar.close:.2f} "
                        f"(strength: {breakout_strength:.2f})")
        
        return signal
    
    def _count_entry_conditions(self, symbol: str, bar: MarketData, range_info: Dict, volume_ratio: float) -> int:
        """Count how many entry conditions are met"""
        conditions = 0
        
        # Volume conditions
        if volume_ratio >= self._parameters['volume_spike_threshold']:
            conditions += 1
        
        # Range size condition
        range_size = (range_info['high'] - range_info['low']) / range_info['low']
        if self._parameters['range_min_size'] <= range_size <= self._parameters['range_max_size']:
            conditions += 1
        
        # Price movement condition
        if bar.high != bar.low:  # Some price movement
            conditions += 1
        
        # Dollar volume condition
        dollar_volume = bar.volume * bar.close
        if dollar_volume >= self._parameters['min_dollar_volume']:
            conditions += 1
        
        return conditions
    
    def _is_in_signal_cooldown(self, symbol: str, bar: MarketData) -> bool:
        """Check if symbol is in signal cooldown period"""
        if symbol not in self.last_signal_time:
            return False
        
        # Simple time-based cooldown (could be enhanced to bar-based)
        time_since_last = (bar.timestamp - self.last_signal_time[symbol]).total_seconds() / 60
        cooldown_minutes = self._parameters.get('signal_cooldown_minutes', 30)
        
        return time_since_last < cooldown_minutes
    
    def _get_average_volume(self, symbol: str, current_bar: MarketData) -> float:
        """Get average volume for symbol (simplified implementation)"""
        # This would typically use historical data
        # For now, return a reasonable estimate
        return getattr(current_bar, 'avg_volume', current_bar.volume * 0.8)
    
    def get_current_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions tracked by this strategy"""
        positions = {}
        
        for symbol in self.breakout_signals:
            # Get stop loss info from centralized manager
            stop_info = self.stop_manager.get_position_info(symbol)
            
            if stop_info:
                positions[symbol] = {
                    'strategy': 'ORB',
                    'entry_price': stop_info['entry_price'],
                    'side': stop_info['side'],
                    'trailing_activated': stop_info['trailing_activated'],
                    'trailing_stop_price': stop_info['trailing_stop_price'],
                    'range_info': self.breakout_signals[symbol]['range_info']
                }
        
        return positions
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """Get strategy-specific statistics"""
        return {
            'active_ranges': len(self.opening_ranges),
            'active_breakouts': len(self.breakout_signals),
            'ranges_defined': len([r for r in self.opening_ranges.values() if r['range_defined']]),
            # Stop loss stats come from centralized manager
            'stop_loss_stats': self.stop_manager.get_statistics()
        }


# COMPARISON: Before vs After

class BeforeAndAfterComparison:
    """
    This class shows the difference between old and new approach
    """
    
    def old_approach_problems(self):
        """
        PROBLEMS WITH OLD APPROACH:
        
        1. CODE DUPLICATION:
           - Every strategy implements _check_exit_conditions()
           - Same stop loss logic repeated in ORB, Gap&Go, MACDV, etc.
           - Similar trailing stop calculations everywhere
        
        2. INCONSISTENCIES:
           - Different stop loss implementations across strategies
           - Hard to maintain unified behavior
           - Risk of bugs in one strategy but not others
        
        3. MAINTENANCE NIGHTMARE:
           - Want to improve trailing stops? Need to update 5+ strategies
           - Want to add new exit condition? Copy-paste to all strategies
           - Testing requires checking each strategy individually
        
        4. MIXED RESPONSIBILITIES:
           - Strategies handle both entry logic AND exit logic
           - Makes code harder to understand and test
        """
        pass
    
    def new_approach_benefits(self):
        """
        BENEFITS OF NEW CENTRALIZED APPROACH:
        
        1. SINGLE SOURCE OF TRUTH:
           - All stop loss logic in one place (stop_loss_manager.py)
           - Consistent behavior across all strategies
           - Easy to test and debug
        
        2. SEPARATION OF CONCERNS:
           - Strategies focus on entry signals
           - Stop manager handles all exits
           - Cleaner, more maintainable code
        
        3. EASY ENHANCEMENT:
           - Want better trailing stops? Update one file
           - Want ATR-based stops? Add to manager, all strategies benefit
           - Want partial profit taking? One implementation for all
        
        4. FLEXIBLE CONFIGURATION:
           - Each strategy can have different stop loss parameters
           - Manager handles the complexity
           - Easy to add new exit conditions
        
        5. CENTRALIZED MONITORING:
           - All stop loss events in one place
           - Better statistics and reporting
           - Easier to track performance
        """
        pass


if __name__ == "__main__":
    # Example usage
    print("🎯 ORB Strategy with Centralized Stop Loss Management")
    print("=" * 60)
    print("✅ Benefits:")
    print("  1. No duplicated stop loss code")
    print("  2. Consistent behavior across strategies")
    print("  3. Easy to maintain and enhance")
    print("  4. Centralized monitoring and statistics")
    print("  5. Separation of concerns")
    print()
    print("📊 Integration steps:")
    print("  1. Import get_stop_loss_manager()")
    print("  2. Remove _check_exit_conditions() from strategy")
    print("  3. Register positions with stop manager on entry")
    print("  4. Check for exit signals in analyze() method")
    print("  5. Clean up tracking when positions exit")