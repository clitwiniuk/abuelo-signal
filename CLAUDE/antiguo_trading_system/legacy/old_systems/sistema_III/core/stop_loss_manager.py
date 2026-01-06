# core/stop_loss_manager.py
"""
Centralized Stop Loss and Trailing Stop Manager.
Unifies stop loss management across all strategies to eliminate code duplication.
"""

from typing import Dict, Optional, Any, NamedTuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import sqlite3
import json
import os

from core.interfaces import MarketData, SignalType, Signal
from collections import deque
import numpy as np


class EMACalculator:
    """Calculate EMA for trailing stop purposes"""
    
    def __init__(self, periods: int):
        self.periods = periods
        self.price_history = deque(maxlen=periods * 2)  # Keep extra history
        self.multiplier = 2 / (periods + 1)
        self.ema = None
        
    def add_price(self, price: float) -> Optional[float]:
        """Add new price and calculate EMA"""
        self.price_history.append(price)
        
        if len(self.price_history) < self.periods:
            return None  # Need minimum periods
            
        if self.ema is None:
            # Initialize with SMA of first N periods
            self.ema = sum(list(self.price_history)[-self.periods:]) / self.periods
        else:
            # Calculate EMA: EMA = (Price - EMA_prev) * multiplier + EMA_prev
            self.ema = (price - self.ema) * self.multiplier + self.ema
            
        return self.ema
    
    def get_ema(self) -> Optional[float]:
        """Get current EMA value"""
        return self.ema
    
    def is_ready(self) -> bool:
        """Check if EMA is ready (has enough data)"""
        return len(self.price_history) >= self.periods
    
    def get_ema_change_pct(self, lookback_periods: int = 3) -> Optional[float]:
        """Calculate EMA change percentage over lookback periods"""
        if not self.ema or len(self.price_history) < lookback_periods + 1:
            return None
        
        # Get historical prices for EMA calculation
        recent_prices = list(self.price_history)[-lookback_periods-1:-1]
        if len(recent_prices) < lookback_periods:
            return None
            
        # Calculate EMA at lookback_periods ago
        temp_ema = sum(recent_prices[:self.periods]) / self.periods if len(recent_prices) >= self.periods else recent_prices[0]
        for price in recent_prices[self.periods:] if len(recent_prices) >= self.periods else recent_prices[1:]:
            temp_ema = (price - temp_ema) * self.multiplier + temp_ema
        
        # Calculate change percentage
        ema_change_pct = (self.ema - temp_ema) / temp_ema
        return ema_change_pct


class VolatilityFilter:
    """Detect lateral movements and low volatility periods"""
    
    def __init__(self, lookback_periods: int = 10):
        self.lookback_periods = lookback_periods
        self.price_history = deque(maxlen=lookback_periods * 2)
        self.volume_history = deque(maxlen=lookback_periods * 2) 
        self.high_history = deque(maxlen=lookback_periods)
        self.low_history = deque(maxlen=lookback_periods)
        self.timestamp_history = deque(maxlen=lookback_periods)
        
    def add_bar(self, bar: MarketData) -> None:
        """Add new market data bar"""
        self.price_history.append(bar.close)
        self.volume_history.append(bar.volume)
        self.high_history.append(bar.high)
        self.low_history.append(bar.low)
        self.timestamp_history.append(bar.timestamp)
    
    def is_lateral_movement(self, range_threshold_pct: float = 0.015, 
                          volume_threshold: float = 0.7,
                          ema_change_threshold: float = 0.005) -> tuple[bool, Dict[str, Any]]:
        """
        Detect if current market is in lateral movement.
        
        Args:
            range_threshold_pct: Maximum range (high-low)/close to be considered lateral (default: 1.5%)
            volume_threshold: Minimum volume relative to average to avoid lateral detection (default: 70%)
            ema_change_threshold: Maximum EMA change to be considered lateral (default: 0.5%)
            
        Returns:
            tuple[bool, dict]: (is_lateral, analysis_info)
        """
        if len(self.price_history) < self.lookback_periods:
            return False, {'reason': 'insufficient_data'}
        
        analysis = {}
        lateral_signals = 0
        total_signals = 3  # Number of criteria we check
        
        # 1. Check price range (recent bars should have small ranges)
        recent_ranges = []
        for i in range(min(5, len(self.high_history))):
            high = self.high_history[-(i+1)]
            low = self.low_history[-(i+1)]
            close = self.price_history[-(i+1)]
            if close > 0:
                range_pct = (high - low) / close
                recent_ranges.append(range_pct)
        
        if recent_ranges:
            avg_range_pct = sum(recent_ranges) / len(recent_ranges)
            analysis['avg_range_pct'] = avg_range_pct
            if avg_range_pct < range_threshold_pct:
                lateral_signals += 1
                analysis['range_signal'] = 'lateral'
            else:
                analysis['range_signal'] = 'volatile'
        
        # 2. Check volume (low volume suggests consolidation)
        if len(self.volume_history) >= self.lookback_periods:
            recent_volumes = list(self.volume_history)[-5:]  # Last 5 bars
            avg_recent_volume = sum(recent_volumes) / len(recent_volumes)
            
            historical_volumes = list(self.volume_history)[:-5] if len(self.volume_history) > 5 else list(self.volume_history)
            if historical_volumes:
                avg_historical_volume = sum(historical_volumes) / len(historical_volumes)
                volume_ratio = avg_recent_volume / avg_historical_volume if avg_historical_volume > 0 else 1.0
                
                analysis['volume_ratio'] = volume_ratio
                if volume_ratio < volume_threshold:
                    lateral_signals += 1
                    analysis['volume_signal'] = 'low'
                else:
                    analysis['volume_signal'] = 'normal'
        
        # 3. Check price momentum (flat trend)
        if len(self.price_history) >= 6:
            recent_prices = list(self.price_history)[-6:]  # Last 6 prices
            price_change_pct = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
            
            analysis['price_momentum_pct'] = price_change_pct
            if abs(price_change_pct) < ema_change_threshold:
                lateral_signals += 1
                analysis['momentum_signal'] = 'flat'
            else:
                analysis['momentum_signal'] = 'trending'
        
        # Decision: lateral if majority of signals agree
        is_lateral = lateral_signals >= 2  # At least 2 out of 3 criteria
        analysis['lateral_signals'] = lateral_signals
        analysis['total_signals'] = total_signals
        analysis['is_lateral'] = is_lateral
        
        return is_lateral, analysis


class ExitReason(Enum):
    """Reasons for position exit"""
    INITIAL_STOP_LOSS = "initial_stop_loss"
    TRAILING_STOP = "trailing_stop"
    EMA_TRAILING_STOP = "ema_trailing_stop"  # NUEVO: EMA-based trailing stop
    PROFIT_TARGET = "profit_target"
    TIME_STOP = "time_stop"
    MANUAL_EXIT = "manual_exit"
    END_OF_DAY = "end_of_day"


@dataclass
class StopLossParameters:
    """Stop loss and trailing stop parameters for a position"""
    # Default values (NOTE: These are rarely used - real values come from create_stop_params_from_config)
    stop_loss_pct: float = 0.08  # 8% stop loss por defecto
    
    # Trailing stop ACTIVADO
    trailing_stop_activation: float = 0.08  # Activar en 8% profit
    trailing_stop_distance: float = 0.04   # 4% trailing distance
    
    # Profit target ACTIVADO
    profit_target: float = 0.15  # 15% profit target
    
    # Time-based exits ACTIVADOS
    max_hold_minutes: int = 360  # 6 horas máximo (base)
    end_of_day_exit: bool = True  # ACTIVADO - Cerrar antes del final del día
    
    # NUEVO: Dynamic hold time extension for winners
    enable_profit_based_extension: bool = True  # Activar extensión para ganadoras
    min_profit_for_extension: float = 0.10     # Mínimo 10% profit para extender
    max_hold_minutes_extended: int = 300       # 5 horas para posiciones ganadoras
    trailing_stop_extension: bool = True       # Extender si trailing stop activo
    
    # Advanced features
    partial_profit_enabled: bool = False
    partial_profit_threshold: float = 0.10  # Take partial at 10%
    partial_profit_size: float = 0.5       # Take 50% of position
    
    # NUEVO: Dynamic EMA Trailing Stop
    enable_dynamic_ema_trailing: bool = False  # Use EMA-based trailing instead of fixed
    ema_trailing_periods: int = 6              # EMA periods (default: 6)
    ema_trailing_timeframe: str = "1m"         # Timeframe for EMA calculation
    ema_trailing_activation_profit_pct: float = 0.02  # Activate after 2% profit
    enable_fixed_stops_fallback: bool = True   # Keep fixed stops as backup
    
    # ATR-based stops (if available)
    use_atr_stops: bool = False
    atr_stop_multiplier: float = 2.0

    # RUNNER DETECTION (NEW FEATURE for smallcaps)
    enable_runner_detection: bool = True        # Enable runner detection
    runner_detection_threshold: float = 0.8     # Start checking at 80% of profit target
    runner_rapid_profit_pct: float = 0.08      # 8% profit threshold for rapid moves
    runner_rapid_time_minutes: int = 30         # Under 30 minutes = rapid move
    runner_momentum_burst_pct: float = 0.03     # 3% momentum burst detection
    runner_sustained_profit_pct: float = 0.10   # 10% for sustained move detection


@dataclass
class PositionTracking:
    """Track stop loss state for a specific position"""
    symbol: str
    entry_price: float
    entry_time: datetime
    side: str  # 'bullish' or 'bearish'
    strategy_name: str
    
    # Stop loss parameters
    stop_params: StopLossParameters
    
    # Dynamic tracking
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    trailing_stop_price: Optional[float] = None
    trailing_activated: bool = False
    partial_profit_taken: bool = False
    
    # NUEVO: EMA Trailing Stop tracking
    ema_calculator: Optional[EMACalculator] = None
    ema_trailing_active: bool = False
    last_ema_value: Optional[float] = None
    
    # NUEVO: Volatility filter for lateral movement detection
    volatility_filter: Optional[VolatilityFilter] = None
    ema_paused_due_to_lateral: bool = False
    
    # ATR data (if available)
    atr_at_entry: Optional[float] = None
    
    def __post_init__(self):
        """Initialize tracking values"""
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == float('inf'):
            self.lowest_price = self.entry_price
            
        # Initialize EMA calculator if dynamic trailing is enabled
        if self.stop_params.enable_dynamic_ema_trailing:
            self.ema_calculator = EMACalculator(self.stop_params.ema_trailing_periods)
            # Add entry price as first data point
            self.ema_calculator.add_price(self.entry_price)
            
            # Initialize volatility filter for lateral movement detection
            self.volatility_filter = VolatilityFilter(lookback_periods=10)


class CentralizedStopLossManager:
    """
    Centralized stop loss management system that handles all stop losses, 
    trailing stops, and profit targets across all strategies.
    
    This replaces the individual stop loss implementations in each strategy.
    """
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.logger = logging.getLogger("StopLossManager")
        self.db_path = db_path

        # Track all active positions
        self.active_positions: Dict[str, PositionTracking] = {}

        # Statistics
        self.total_stops_triggered = 0
        self.total_profits_taken = 0
        self.total_time_exits = 0

        # Track delayed trailing stops for synchronization
        self.delayed_trailing_stops = {}  # symbol -> trailing_info

        # Initialize persistence using existing trading_data.db and position_risk_config table
        self._extend_position_risk_table()
        self._load_positions_from_existing_table()

        self.logger.info("📊 Centralized Stop Loss Manager initialized with persistence")
    
    def register_position(self, symbol: str, entry_price: float, entry_time: datetime, 
                         side: str, strategy_name: str, stop_params: StopLossParameters,
                         atr_at_entry: Optional[float] = None) -> None:
        """Register a new position for stop loss tracking"""
        
        position = PositionTracking(
            symbol=symbol,
            entry_price=entry_price,
            entry_time=entry_time,
            side=side,
            strategy_name=strategy_name,
            stop_params=stop_params,
            atr_at_entry=atr_at_entry
        )
        
        self.active_positions[symbol] = position

        # Save to database
        self._save_position_to_existing_table(symbol, position)

        self.logger.info(f"📊 Stop tracking registered for {symbol} [{strategy_name}]: "
                        f"Entry ${entry_price:.2f}, Side: {side}, "
                        f"Stop: {stop_params.stop_loss_pct:.1%}, "
                        f"Target: {stop_params.profit_target:.1%}")
    
    def register_delayed_trailing_stop(self, symbol: str, trailing_info: Dict) -> None:
        """Register a trailing stop that was delayed due to entry synchronization"""
        self.delayed_trailing_stops[symbol] = trailing_info
        self.logger.info(f"📈 Registered delayed trailing stop for {symbol}")
        
        # If position already exists, activate trailing stop immediately
        if symbol in self.active_positions:
            position = self.active_positions[symbol]
            if trailing_info.get('enable_trailing', True):
                position.trailing_activated = True
                self.logger.info(f"📈 Activated delayed trailing stop for existing position {symbol}")
    
    def should_delay_trailing_stop_update(self, symbol: str) -> bool:
        """Check if trailing stop updates should be delayed due to pending entry"""
        return symbol in self.delayed_trailing_stops
    
    def check_exit_conditions(self, symbol: str, current_bar: MarketData) -> Optional[Signal]:
        """
        Check if position should be exited based on stop loss conditions.
        
        Returns:
            Signal if position should be closed, None otherwise
        """
        if symbol not in self.active_positions:
            return None
        
        position = self.active_positions[symbol]
        current_price = current_bar.close
        current_time = current_bar.timestamp
        
        # Update price tracking
        if position.side == 'bullish':
            position.highest_price = max(position.highest_price, current_price)
        else:  # bearish
            position.lowest_price = min(position.lowest_price, current_price)
        
        # Check all exit conditions
        exit_info = self._check_all_exit_conditions(position, current_price, current_time)
        
        if exit_info:
            # Create exit signal
            signal_type = SignalType.EXIT_LONG if position.side == 'bullish' else SignalType.EXIT_SHORT
            
            # Add EMA and lateral filter info to metadata
            metadata = {
                'exit_reason': exit_info['reason'].value,
                'strategy': position.strategy_name,
                'entry_price': position.entry_price,
                'pnl_pct': exit_info.get('pnl_pct', 0),
                'stop_price': exit_info.get('stop_price'),
                'highest_price': position.highest_price,
                'lowest_price': position.lowest_price
            }
            
            # Add EMA-specific metadata
            if exit_info['reason'] == ExitReason.EMA_TRAILING_STOP:
                metadata.update({
                    'ema_value': exit_info.get('ema_value'),
                    'ema_periods': exit_info.get('ema_periods'),
                    'lateral_filter_active': exit_info.get('lateral_filter_active', False)
                })
            
            signal = Signal(
                signal_id=f"STOP-{symbol}-{current_time.strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                signal_type=signal_type,
                strength=0.9,  # High confidence for stop loss exits
                price=current_price,
                timestamp=current_time,
                metadata=metadata
            )
            
            # Update statistics
            reason = exit_info['reason']
            if reason == ExitReason.INITIAL_STOP_LOSS or reason == ExitReason.TRAILING_STOP or reason == ExitReason.EMA_TRAILING_STOP:
                self.total_stops_triggered += 1
            elif reason == ExitReason.PROFIT_TARGET:
                self.total_profits_taken += 1
            elif reason == ExitReason.TIME_STOP or reason == ExitReason.END_OF_DAY:
                self.total_time_exits += 1
            
            # Log exit
            self.logger.info(f"🚨 {reason.value.upper()} for {symbol} [{position.strategy_name}]: "
                           f"${position.entry_price:.2f} → ${current_price:.2f} "
                           f"({exit_info.get('pnl_pct', 0):.1%})")
            
            # Remove from tracking
            self.unregister_position(symbol)
            
            return signal
        
        return None
    
    def _check_all_exit_conditions(self, position: PositionTracking, current_price: float, 
                                  current_time: datetime) -> Optional[Dict[str, Any]]:
        """Check all exit conditions for a position"""
        
        # Calculate current P&L
        if position.side == 'bullish':
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:  # bearish
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        # 1. Initial Stop Loss
        exit_info = self._check_initial_stop_loss(position, current_price, pnl_pct)
        if exit_info:
            return exit_info
        
        # 2. Trailing Stop (choose between fixed or EMA-based)
        if position.stop_params.enable_dynamic_ema_trailing:
            # Use EMA trailing stop instead of fixed trailing stop
            exit_info = self._check_ema_trailing_stop(position, current_price, pnl_pct)
            if exit_info:
                return exit_info
            
            # Optional: Use fixed trailing as fallback if enabled
            if position.stop_params.enable_fixed_stops_fallback:
                exit_info = self._check_trailing_stop(position, current_price, pnl_pct)
                if exit_info:
                    return exit_info
        else:
            # Use traditional fixed trailing stop
            exit_info = self._check_trailing_stop(position, current_price, pnl_pct)
            if exit_info:
                return exit_info
        
        # 3. Profit Target
        exit_info = self._check_profit_target(position, current_price, pnl_pct)
        if exit_info:
            return exit_info
        
        # 4. Time-based exits
        exit_info = self._check_time_exits(position, current_time)
        if exit_info:
            return exit_info
        
        # 5. Partial profit taking (doesn't exit, just logs)
        self._check_partial_profit(position, current_price, pnl_pct)
        
        return None
    
    def _check_initial_stop_loss(self, position: PositionTracking, current_price: float, 
                                pnl_pct: float) -> Optional[Dict[str, Any]]:
        """Check initial stop loss condition"""
        
        if position.stop_params.use_atr_stops and position.atr_at_entry:
            # ATR-based stop loss
            atr_stop_distance = position.atr_at_entry * position.stop_params.atr_stop_multiplier
            if position.side == 'bullish':
                stop_price = position.entry_price - atr_stop_distance
                triggered = current_price <= stop_price
            else:
                stop_price = position.entry_price + atr_stop_distance
                triggered = current_price >= stop_price
        else:
            # Percentage-based stop loss
            triggered = pnl_pct <= -position.stop_params.stop_loss_pct
            stop_price = (position.entry_price * (1 - position.stop_params.stop_loss_pct) 
                         if position.side == 'bullish' 
                         else position.entry_price * (1 + position.stop_params.stop_loss_pct))
        
        if triggered:
            return {
                'reason': ExitReason.INITIAL_STOP_LOSS,
                'exit_price': current_price,
                'stop_price': stop_price,
                'pnl_pct': pnl_pct
            }
        
        return None
    
    def _check_trailing_stop(self, position: PositionTracking, current_price: float, 
                           pnl_pct: float) -> Optional[Dict[str, Any]]:
        """Check trailing stop condition"""
        
        # Only activate trailing stop after reaching activation threshold
        if pnl_pct < position.stop_params.trailing_stop_activation:
            return None
        
        # Activate trailing stop
        if not position.trailing_activated:
            position.trailing_activated = True
            self.logger.info(f"🔄 Trailing stop activated for {position.symbol} at {pnl_pct:.1%} profit")
        
        # Calculate trailing stop price
        if position.side == 'bullish':
            trailing_stop_price = position.highest_price * (1 - position.stop_params.trailing_stop_distance)
            triggered = current_price <= trailing_stop_price
        else:
            trailing_stop_price = position.lowest_price * (1 + position.stop_params.trailing_stop_distance)
            triggered = current_price >= trailing_stop_price
        
        position.trailing_stop_price = trailing_stop_price
        
        if triggered:
            return {
                'reason': ExitReason.TRAILING_STOP,
                'exit_price': current_price,
                'stop_price': trailing_stop_price,
                'pnl_pct': pnl_pct,
                'highest_price': position.highest_price,
                'lowest_price': position.lowest_price
            }
        
        return None
    
    def _check_ema_trailing_stop(self, position: PositionTracking, current_price: float, 
                                pnl_pct: float) -> Optional[Dict[str, Any]]:
        """Check EMA-based trailing stop condition"""
        
        # Only check if EMA trailing is enabled
        if not position.stop_params.enable_dynamic_ema_trailing or not position.ema_calculator:
            return None
        
        # Add current price to EMA calculation
        current_ema = position.ema_calculator.add_price(current_price)
        position.last_ema_value = current_ema
        
        # Wait until EMA is ready (has enough data points)
        if not position.ema_calculator.is_ready():
            return None
        
        # Check if we should activate EMA trailing
        if not position.ema_trailing_active:
            # Activate when profit threshold is reached
            if pnl_pct >= position.stop_params.ema_trailing_activation_profit_pct:
                position.ema_trailing_active = True
                self.logger.info(f"🔄 EMA Trailing stop activated for {position.symbol} at {pnl_pct:.1%} profit (EMA: {current_ema:.4f})")
            else:
                return None  # Not activated yet
        
        # Check exit condition: price closes below EMA for bullish positions
        if position.side == 'bullish':
            # Exit when price closes below EMA
            if current_price < current_ema:
                return {
                    'reason': ExitReason.EMA_TRAILING_STOP,
                    'exit_price': current_price,
                    'ema_value': current_ema,
                    'pnl_pct': pnl_pct,
                    'ema_periods': position.stop_params.ema_trailing_periods
                }
        else:
            # For bearish positions: exit when price closes above EMA
            if current_price > current_ema:
                return {
                    'reason': ExitReason.EMA_TRAILING_STOP,
                    'exit_price': current_price,
                    'ema_value': current_ema,
                    'pnl_pct': pnl_pct,
                    'ema_periods': position.stop_params.ema_trailing_periods
                }
        
        return None
    
    def _check_profit_target(self, position: PositionTracking, current_price: float,
                           pnl_pct: float) -> Optional[Dict[str, Any]]:
        """Check profit target condition with RUNNER DETECTION for smallcaps"""

        # Check if runner detection is enabled
        if not getattr(position.stop_params, 'enable_runner_detection', True):
            # Standard behavior if runner detection disabled
            if pnl_pct >= position.stop_params.profit_target:
                return {
                    'reason': ExitReason.PROFIT_TARGET,
                    'exit_price': current_price,
                    'pnl_pct': pnl_pct
                }
            return None

        # SMALLCAP RUNNER DETECTION: If volatility increases near profit target, disable fixed target
        detection_threshold = getattr(position.stop_params, 'runner_detection_threshold', 0.8)
        if pnl_pct >= (position.stop_params.profit_target * detection_threshold):

            # Check if this is becoming a "runner" (high volatility momentum play)
            if self._detect_runner_behavior(position, current_price, pnl_pct):
                # RUNNER DETECTED: Disable fixed profit target, let trailing stop handle it
                self.logger.info(f"🚀 {position.symbol}: RUNNER DETECTED at {pnl_pct:.1%}! "
                               f"Disabling {position.stop_params.profit_target:.0%} target, using trailing stop for max gains")

                # Mark position as runner to avoid future fixed exits
                if not hasattr(position, 'is_runner'):
                    position.is_runner = True

                # Return None to continue with trailing stop logic instead
                return None

        # NORMAL BEHAVIOR: Use fixed profit target if not a runner
        if not hasattr(position, 'is_runner') or not position.is_runner:
            if pnl_pct >= position.stop_params.profit_target:
                return {
                    'reason': ExitReason.PROFIT_TARGET,
                    'exit_price': current_price,
                    'pnl_pct': pnl_pct
                }

        return None

    def _detect_runner_behavior(self, position: PositionTracking, current_price: float, pnl_pct: float) -> bool:
        """
        Detect if a smallcap position is becoming a 'runner' based on:
        1. Rate of price change acceleration (configurable via config.ini)
        2. Sustained momentum above key levels
        3. Price momentum bursts
        """
        try:
            # Get configurable parameters from stop_params
            rapid_profit_threshold = getattr(position.stop_params, 'runner_rapid_profit_pct', 0.08)
            rapid_time_minutes = getattr(position.stop_params, 'runner_rapid_time_minutes', 30)
            momentum_burst_threshold = getattr(position.stop_params, 'runner_momentum_burst_pct', 0.03)
            sustained_profit_threshold = getattr(position.stop_params, 'runner_sustained_profit_pct', 0.10)

            # CRITERION 1: Rapid profit acceleration (configurable threshold in short time)
            if pnl_pct >= rapid_profit_threshold:
                time_held = datetime.now() - position.entry_time
                if time_held.total_seconds() < (rapid_time_minutes * 60):
                    self.logger.info(f"🎯 {position.symbol}: Runner criterion 1: {pnl_pct:.1%} profit in {time_held.total_seconds()/60:.1f} min "
                                   f"(threshold: {rapid_profit_threshold:.1%} in {rapid_time_minutes} min)")
                    return True

            # CRITERION 2: Price acceleration (current price significantly above recent high)
            if position.side == 'bullish':
                # If current price is above momentum burst threshold vs previous high
                recent_momentum = (current_price - position.highest_price) / position.highest_price if position.highest_price > 0 else 0
                if recent_momentum >= momentum_burst_threshold:
                    self.logger.info(f"🚀 {position.symbol}: Runner criterion 2: {recent_momentum:.1%} momentum burst "
                                   f"(threshold: {momentum_burst_threshold:.1%})")
                    return True

            # CRITERION 3: Strong sustained move (configurable profit with sustained momentum)
            if pnl_pct >= sustained_profit_threshold:
                # If we're still making new highs, likely a runner
                if position.side == 'bullish' and current_price >= position.highest_price * 0.98:  # Within 2% of high
                    self.logger.info(f"🎯 {position.symbol}: Runner criterion 3: {pnl_pct:.1%} profit with sustained highs "
                                   f"(threshold: {sustained_profit_threshold:.1%})")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error detecting runner behavior for {position.symbol}: {e}")
            return False
    
    def _check_time_exits(self, position: PositionTracking, current_time: datetime) -> Optional[Dict[str, Any]]:
        """Check time-based exit conditions with intelligent profit-based extension"""
        
        # Calculate current P&L
        current_price = position.current_price if hasattr(position, 'current_price') else position.entry_price
        if position.side == 'bullish':
            pnl_pct = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price
        
        # Calculate hold time
        hold_minutes = (current_time - position.entry_time).total_seconds() / 60
        
        # Determine effective max hold time based on position performance
        effective_max_hold = self._get_effective_max_hold_time(position, pnl_pct)
        
        if hold_minutes >= effective_max_hold:
            # Log the reason for time exit
            exit_reason = "standard" if effective_max_hold == position.stop_params.max_hold_minutes else "extended"
            self.logger.info(f"⏰ Time stop triggered for {position.symbol}: {hold_minutes:.0f}min >= {effective_max_hold:.0f}min ({exit_reason}), P&L: {pnl_pct:.1%}")
            
            return {
                'reason': ExitReason.TIME_STOP,
                'exit_time': current_time,
                'hold_minutes': hold_minutes,
                'effective_max_hold': effective_max_hold,
                'pnl_pct': pnl_pct
            }
        
        # End of day exit (if enabled)
        if position.stop_params.end_of_day_exit:
            # Read end of day configuration from config.ini
            import configparser
            global_config = configparser.ConfigParser()
            global_config.read('config.ini')
            
            # Get market close time (default: 16:00 ET)
            market_close_time_str = global_config.get('GLOBAL', 'market_close_time', fallback='16:00')
            # Clean the value (remove comments)
            market_close_time_str = market_close_time_str.split('#')[0].strip()
            market_close_hour, market_close_minute = map(int, market_close_time_str.split(':'))
            
            # Get minutes before close to exit (default: 5)
            minutes_before = global_config.getint('GLOBAL', 'minutes_before_close_to_exit', fallback=5)
            
            # Calculate the time to start closing positions using the same logic as trading_engine_old.py
            close_positions_hour = market_close_hour
            close_positions_minute = market_close_minute - minutes_before
            
            # Handle minute underflow
            if close_positions_minute < 0:
                close_positions_hour -= 1
                close_positions_minute += 60
            
            # Convert current time to Eastern Time for comparison with config values
            import pytz
            eastern_tz = pytz.timezone('US/Eastern')
            
            # Convert UTC time to Eastern Time
            if current_time.tzinfo is None:
                # If no timezone info, assume UTC
                current_time_utc = current_time.replace(tzinfo=pytz.UTC)
            else:
                current_time_utc = current_time
                
            current_time_et = current_time_utc.astimezone(eastern_tz)
            current_hour = current_time_et.hour
            current_minute = current_time_et.minute
            
            # Check if current time is between close_positions_time and market_close
            # Create time objects for comparison
            from datetime import time
            close_positions_time = time(close_positions_hour, close_positions_minute)
            market_close = time(market_close_hour, market_close_minute) 
            current_time_only = time(current_hour, current_minute)
            
            if close_positions_time <= current_time_only < market_close:
                return {
                    'reason': ExitReason.END_OF_DAY,
                    'exit_time': current_time,
                    'close_positions_time': f"{close_positions_hour:02d}:{close_positions_minute:02d}",
                    'market_close_time': f"{market_close_hour:02d}:{market_close_minute:02d}"
                }
        
        return None
    
    def _get_effective_max_hold_time(self, position: PositionTracking, pnl_pct: float) -> float:
        """
        Calculate effective max hold time based on position performance
        
        Logic:
        - If losing or small profit: Use standard max_hold_minutes
        - If profitable AND trailing stop active: Use extended time
        - If very profitable: Use extended time even without trailing
        """
        base_hold_time = position.stop_params.max_hold_minutes
        
        # If profit-based extension is disabled, use base time
        if not position.stop_params.enable_profit_based_extension:
            return base_hold_time
        
        # If position is losing or small profit, use standard time
        if pnl_pct < position.stop_params.min_profit_for_extension:
            return base_hold_time
        
        # Check for extension criteria
        should_extend = False
        extension_reason = []
        
        # Criterion 1: Trailing stop is active
        if position.stop_params.trailing_stop_extension and position.trailing_activated:
            should_extend = True
            extension_reason.append("trailing_active")
        
        # Criterion 2: High profit (double the minimum)
        if pnl_pct >= position.stop_params.min_profit_for_extension * 2:
            should_extend = True
            extension_reason.append("high_profit")
        
        # Criterion 3: Very strong momentum (>20% profit)
        if pnl_pct >= 0.20:
            should_extend = True
            extension_reason.append("strong_momentum")
        
        if should_extend:
            extended_time = position.stop_params.max_hold_minutes_extended
            self.logger.info(f"⏰🚀 Hold time EXTENDED for {position.symbol}: {base_hold_time}min → {extended_time}min "
                           f"(P&L: {pnl_pct:.1%}, reasons: {', '.join(extension_reason)})")
            return extended_time
        
        return base_hold_time
    
    def _check_partial_profit(self, position: PositionTracking, current_price: float, 
                            pnl_pct: float) -> None:
        """Check and handle partial profit taking"""
        
        if (not position.stop_params.partial_profit_enabled or 
            position.partial_profit_taken or 
            pnl_pct < position.stop_params.partial_profit_threshold):
            return
        
        # Mark partial profit as taken
        position.partial_profit_taken = True
        
        self.logger.info(f"💰 Partial profit triggered for {position.symbol}: "
                        f"{pnl_pct:.1%} profit, should take {position.stop_params.partial_profit_size:.0%} of position")
    
    def unregister_position(self, symbol: str) -> None:
        """Remove position from stop loss tracking"""
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            # Remove from database
            self._remove_position_from_existing_table(symbol)
            self.logger.debug(f"🗑️ Removed {symbol} from stop loss tracking")
    
    def get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current stop loss information for a position"""
        if symbol not in self.active_positions:
            return None
        
        position = self.active_positions[symbol]
        
        return {
            'symbol': symbol,
            'entry_price': position.entry_price,
            'side': position.side,
            'strategy': position.strategy_name,
            'highest_price': position.highest_price,
            'lowest_price': position.lowest_price,
            'trailing_activated': position.trailing_activated,
            'trailing_stop_price': position.trailing_stop_price,
            'partial_profit_taken': position.partial_profit_taken,
            'stop_params': position.stop_params
        }
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get information for all tracked positions"""
        return {symbol: self.get_position_info(symbol) for symbol in self.active_positions}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get stop loss management statistics"""
        return {
            'active_positions': len(self.active_positions),
            'total_stops_triggered': self.total_stops_triggered,
            'total_profits_taken': self.total_profits_taken,
            'total_time_exits': self.total_time_exits,
            'symbols_tracked': list(self.active_positions.keys())
        }
    
    def clear_all_positions(self) -> None:
        """Clear all position tracking (for reset/cleanup)"""
        self.active_positions.clear()
        # Also clear from database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE position_risk_config SET is_active = 0 WHERE is_active = 1")
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error clearing positions from database: {e}")
        self.logger.info("🧹 Cleared all stop loss tracking")

    def _extend_position_risk_table(self) -> None:
        """Extend existing position_risk_config table with fields needed for stop_loss_manager"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Add missing columns to existing table (if they don't exist)
                columns_to_add = [
                    ("entry_time", "TIMESTAMP"),
                    ("side", "TEXT DEFAULT 'BUY'"),
                    ("highest_price", "REAL"),
                    ("lowest_price", "REAL"),
                    ("trailing_activated", "INTEGER DEFAULT 0"),
                    ("ema_trailing_active", "INTEGER DEFAULT 0"),
                    ("last_ema_value", "REAL"),
                    ("partial_profit_taken", "INTEGER DEFAULT 0"),
                    ("atr_at_entry", "REAL")
                ]

                for column_name, column_type in columns_to_add:
                    try:
                        conn.execute(f"ALTER TABLE position_risk_config ADD COLUMN {column_name} {column_type}")
                        self.logger.info(f"✅ Added column {column_name} to position_risk_config")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            # Column already exists, skip
                            continue
                        else:
                            raise

                conn.commit()
                self.logger.info("✅ Extended position_risk_config table for stop_loss_manager")

        except Exception as e:
            self.logger.error(f"❌ Error extending position_risk_config table: {e}")
            raise

    def _save_position_to_existing_table(self, symbol: str, position: PositionTracking) -> None:
        """Save or update position in existing position_risk_config table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Calculate stop_loss_price and take_profit_price from percentages
                stop_loss_price = position.entry_price * (1 - position.stop_params.stop_loss_pct) if position.side == 'bullish' else position.entry_price * (1 + position.stop_params.stop_loss_pct)
                take_profit_price = position.entry_price * (1 + position.stop_params.profit_target) if position.side == 'bullish' else position.entry_price * (1 - position.stop_params.profit_target)
                trailing_stop_activation_price = position.entry_price * (1 + position.stop_params.trailing_stop_activation) if position.side == 'bullish' else position.entry_price * (1 - position.stop_params.trailing_stop_activation)

                conn.execute("""
                    INSERT OR REPLACE INTO position_risk_config (
                        symbol, entry_price, quantity, stop_loss_price, take_profit_price,
                        trailing_stop_activation_price, trailing_stop_distance_pct, max_hold_time_minutes,
                        strategy_used, entry_time, side, highest_price, lowest_price,
                        trailing_activated, ema_trailing_active, last_ema_value,
                        partial_profit_taken, atr_at_entry, is_active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    position.entry_price,
                    100,  # Default quantity, will be updated by trading engine
                    stop_loss_price,
                    take_profit_price,
                    trailing_stop_activation_price,
                    position.stop_params.trailing_stop_distance,
                    position.stop_params.max_hold_minutes,
                    position.strategy_name,
                    position.entry_time.isoformat(),
                    position.side,
                    position.highest_price,
                    position.lowest_price,
                    1 if position.trailing_activated else 0,
                    1 if position.ema_trailing_active else 0,
                    position.last_ema_value,
                    1 if position.partial_profit_taken else 0,
                    position.atr_at_entry,
                    1,  # is_active
                    datetime.now().isoformat()
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"❌ Error saving position {symbol} to database: {e}")

    def _load_positions_from_existing_table(self) -> None:
        """Load active positions from existing position_risk_config table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT symbol, entry_price, stop_loss_price, take_profit_price,
                           trailing_stop_activation_price, trailing_stop_distance_pct, max_hold_time_minutes,
                           strategy_used, entry_time, side, highest_price, lowest_price,
                           trailing_activated, ema_trailing_active, last_ema_value,
                           partial_profit_taken, atr_at_entry
                    FROM position_risk_config
                    WHERE is_active = 1
                """)

                rows = cursor.fetchall()
                loaded_count = 0

                for row in rows:
                    try:
                        (symbol, entry_price, stop_loss_price, take_profit_price,
                         trailing_stop_activation_price, trailing_stop_distance_pct, max_hold_time_minutes,
                         strategy_used, entry_time_str, side, highest_price, lowest_price,
                         trailing_activated, ema_trailing_active, last_ema_value,
                         partial_profit_taken, atr_at_entry) = row

                        # Parse entry_time (handle None case)
                        if entry_time_str:
                            entry_time = datetime.fromisoformat(entry_time_str)
                        else:
                            entry_time = datetime.now()  # Fallback for existing records

                        # Convert prices back to percentages for StopLossParameters
                        side_clean = 'bullish' if side == 'BUY' else 'bearish'

                        if side_clean == 'bullish':
                            stop_loss_pct = (entry_price - stop_loss_price) / entry_price if stop_loss_price else 0.05
                            profit_target = (take_profit_price - entry_price) / entry_price if take_profit_price else 0.15
                            trailing_activation = (trailing_stop_activation_price - entry_price) / entry_price if trailing_stop_activation_price else 0.08
                        else:
                            stop_loss_pct = (stop_loss_price - entry_price) / entry_price if stop_loss_price else 0.05
                            profit_target = (entry_price - take_profit_price) / entry_price if take_profit_price else 0.15
                            trailing_activation = (entry_price - trailing_stop_activation_price) / entry_price if trailing_stop_activation_price else 0.08

                        # Create StopLossParameters
                        stop_params = StopLossParameters(
                            stop_loss_pct=abs(stop_loss_pct),
                            trailing_stop_activation=abs(trailing_activation),
                            trailing_stop_distance=trailing_stop_distance_pct or 0.05,
                            profit_target=abs(profit_target),
                            max_hold_minutes=max_hold_time_minutes or 360
                        )

                        # Create position tracking object
                        position = PositionTracking(
                            symbol=symbol,
                            entry_price=entry_price,
                            entry_time=entry_time,
                            side=side_clean,
                            strategy_name=strategy_used or "unknown",
                            stop_params=stop_params,
                            highest_price=highest_price or entry_price,
                            lowest_price=lowest_price or entry_price,
                            trailing_stop_price=None,  # Will be calculated
                            trailing_activated=bool(trailing_activated),
                            partial_profit_taken=bool(partial_profit_taken),
                            ema_trailing_active=bool(ema_trailing_active),
                            last_ema_value=last_ema_value,
                            atr_at_entry=atr_at_entry
                        )

                        # Add to active positions
                        self.active_positions[symbol] = position
                        loaded_count += 1

                    except Exception as e:
                        self.logger.error(f"❌ Error loading position {symbol}: {e}")
                        continue

                if loaded_count > 0:
                    self.logger.info(f"📊 Loaded {loaded_count} active stop positions from position_risk_config")
                else:
                    self.logger.info("📊 No active stop positions found in position_risk_config")

        except Exception as e:
            self.logger.error(f"❌ Error loading positions from database: {e}")

    def _remove_position_from_existing_table(self, symbol: str) -> None:
        """Mark position as inactive in existing table when exited"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE position_risk_config
                    SET is_active = 0, updated_at = ?
                    WHERE symbol = ? AND is_active = 1
                """, (datetime.now().isoformat(), symbol))
                conn.commit()
        except Exception as e:
            self.logger.error(f"❌ Error removing position {symbol} from database: {e}")


# Factory function to create stop loss parameters from strategy config
def create_stop_params_from_config(config: Dict[str, Any]) -> StopLossParameters:
    """Create StopLossParameters from strategy configuration - SMALLCAP-OPTIMIZED using config.ini"""

    # Read global config.ini smallcap-optimized values
    import configparser
    global_config = configparser.ConfigParser()
    global_config.read('config.ini')

    # Get SMALLCAP-OPTIMIZED values from config.ini GLOBAL section
    fallback_stop_loss = global_config.getfloat('GLOBAL', 'fallback_stop_loss_pct', fallback=0.06)  # 6% for smallcaps
    fallback_take_profit = global_config.getfloat('GLOBAL', 'fallback_take_profit_pct', fallback=0.12)  # 12% conservative
    fallback_trailing_activation = global_config.getfloat('GLOBAL', 'default_trailing_activation', fallback=0.06)  # 6% activation
    fallback_trailing_distance = global_config.getfloat('GLOBAL', 'default_trailing_stop_pct', fallback=0.035)  # 3.5% distance

    # Read all SMALLCAP-OPTIMIZED parameters from config.ini
    return StopLossParameters(
        # BASIC STOPS (smallcap-optimized)
        stop_loss_pct=config.get('stop_loss_pct', fallback_stop_loss),  # 6% for volatility
        trailing_stop_activation=config.get('trailing_stop_activation', fallback_trailing_activation),  # 6% activation
        trailing_stop_distance=config.get('trailing_stop_distance', fallback_trailing_distance),  # 3.5% distance
        profit_target=config.get('take_profit_pct', fallback_take_profit),  # 12% conservative target

        # EMA TRAILING (smallcap-optimized from config.ini)
        enable_dynamic_ema_trailing=global_config.getboolean('GLOBAL', 'enable_dynamic_ema_trailing', fallback=True),
        ema_trailing_periods=global_config.getint('GLOBAL', 'ema_trailing_periods', fallback=5),  # Fast EMA-5
        ema_trailing_timeframe=global_config.get('GLOBAL', 'ema_trailing_timeframe', fallback='1m').split('#')[0].strip(),
        ema_trailing_activation_profit_pct=global_config.getfloat('GLOBAL', 'ema_trailing_activation_profit_pct', fallback=0.04),  # 4% activation
        enable_fixed_stops_fallback=global_config.getboolean('GLOBAL', 'enable_fixed_stops_fallback', fallback=True),

        # PARTIAL PROFITS (smallcap-optimized from config.ini)
        partial_profit_enabled=global_config.getboolean('GLOBAL', 'enable_partial_profits', fallback=True),
        partial_profit_threshold=global_config.getfloat('GLOBAL', 'partial_profit_threshold', fallback=0.08),  # 8% partial
        partial_profit_size=global_config.getfloat('GLOBAL', 'partial_profit_size', fallback=0.4),  # 40% of position

        # TIME-BASED EXITS (smallcap-optimized from config.ini)
        max_hold_minutes=global_config.getint('GLOBAL', 'max_hold_minutes', fallback=180),  # 3 hours
        enable_profit_based_extension=global_config.getboolean('GLOBAL', 'enable_profit_based_extension', fallback=True),
        min_profit_for_extension=global_config.getfloat('GLOBAL', 'min_profit_for_extension', fallback=0.12),  # 12% for extension
        max_hold_minutes_extended=global_config.getint('GLOBAL', 'max_hold_minutes_extended', fallback=240),  # 4 hours extended

        # VOLATILITY FILTER - handled internally by VolatilityFilter class

        # RUNNER DETECTION (NEW FEATURE - smallcap-optimized from config.ini)
        enable_runner_detection=global_config.getboolean('GLOBAL', 'enable_runner_detection', fallback=True),
        runner_detection_threshold=global_config.getfloat('GLOBAL', 'runner_detection_threshold', fallback=0.8),
        runner_rapid_profit_pct=global_config.getfloat('GLOBAL', 'runner_rapid_profit_pct', fallback=0.08),
        runner_rapid_time_minutes=global_config.getint('GLOBAL', 'runner_rapid_time_minutes', fallback=30),
        runner_momentum_burst_pct=global_config.getfloat('GLOBAL', 'runner_momentum_burst_pct', fallback=0.03),
        runner_sustained_profit_pct=global_config.getfloat('GLOBAL', 'runner_sustained_profit_pct', fallback=0.10),

        # END OF DAY - use existing parameter
        end_of_day_exit=True,  # Always enabled for smallcaps (gap risk)

        # ATR STOPS (optional)
        use_atr_stops=config.get('use_atr_stops', False),
        atr_stop_multiplier=config.get('atr_stop_multiplier', 2.0)
    )


# Singleton instance for global access
_stop_loss_manager = None

def get_stop_loss_manager() -> CentralizedStopLossManager:
    """Get the global stop loss manager instance"""
    global _stop_loss_manager
    if _stop_loss_manager is None:
        _stop_loss_manager = CentralizedStopLossManager()
    return _stop_loss_manager