# strategies/orb_strategy.py - Opening Range Breakout Strategy - FIXED
"""
Opening Range Breakout (ORB) Strategy: Optimized for penny stocks and small caps
without requiring pre-market data.

CRITICAL FIXES:
1. Prevent duplicate signals for same symbol
2. Fix stop loss and target price calculations
3. Proper exit signal generation
4. Control signal frequency
"""

from typing import Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, time, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class ORBStrategy(BaseStrategy):
    """
    Opening Range Breakout Strategy implementation.
    
    Entry Conditions:
    1. First 15-30 minutes define the opening range (high/low)
    2. Volume spike >3x average volume
    3. Price breaks above/below opening range
    4. Volume confirmation on breakout
    5. Additional filters (price range, float size, etc.)
    
    Exit Conditions:
    1. Target hit (1.5-2x opening range)
    2. Stop loss (below/above opening range)
    3. Time-based exit (no overnight holds)
    4. Volume drying up
    5. End of momentum session (11:30 AM typically)
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # FALLBACK DEFAULTS - Usado solo si config.ini no existe o está incompleto
        fallback_defaults = {
            # Opening range parameters
            'opening_range_minutes': 15,
            'range_min_size': 0.02,      # Reducido de 3% a 2% para más oportunidades
            'range_max_size': 0.15,      # Aumentado para más flexibilidad
            
            # Volume parameters (más estrictos para evitar falsos breakouts)
            'volume_spike_threshold': 3.0,    # Aumentado a 3.0x para mayor confirmación
            'volume_confirmation_threshold': 2.5,  # Aumentado a 2.5x
            'volume_period': 20,
            
            # Price filters for penny stocks
            'min_price': 2.00,             # Aumentado de $1 a $2 (evitar penny stocks extremos)
            'max_price': 15.00,
            'min_dollar_volume': 150000,   # Aumentado a 150k para mejor liquidez
            
            # Breakout confirmation
            'breakout_min_size': 0.005,     # Reducido de 1% a 0.5%
            'consolidation_bars': 2,
            
            # Risk management
            'stop_loss_pct': 0.05,          # Reducido de 7% a 5%
            'profit_target': 0.15,          # Reducido de 20% a 15%
            'trailing_stop_activation': 0.08,  # Reducido de 10% a 8%
            'trailing_stop_distance': 0.04,    # Reducido de 5% a 4%
            
            # Position sizing
            'max_position_value': 300.0,     # Valor por defecto (real viene de config.ini)
            'min_position_value': 80.0,      # Valor por defecto (real viene de config.ini)
            'risk_per_trade': 0.01,
            'min_quantity': 10,              # Valor por defecto (real viene de config.ini)
            'commission_per_share': 0.01,
            'min_commission': 1.0,
            
            # Additional filters (más estrictos)
            'max_gap_size': 0.15,           # Reducido de 20% a 15% (gaps grandes problemáticos)
            'min_conditions': 6,            # Aumentado de 4 a 6 (más selectivo)
            
            # Trading session timing
            'trading_start_time': '09:30:00',
            'trading_end_time': '15:30:00',    # Extendido hasta 3:30 PM
            'max_hold_hours': 6.5,
            
            # Signal control - NUEVO
            'signal_cooldown_bars': 5,      # Esperar 5 bars antes de nueva señal del mismo símbolo
            'max_signals_per_symbol': 1,    # Máximo 1 señal activa por símbolo
            
            # History requirements
            'max_history_bars': 100
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("ORB", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('ORB_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for ORB strategy: {e}")
            # Keep fallback defaults
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Strategy state tracking
        self.opening_ranges = {}          # Store opening range data per symbol
        self.daily_stats = {}            # Daily statistics per symbol
        self.breakout_signals = {}       # Active breakout signals (simplified - no stop logic)
        self.trading_session_active = {} # Track if still in trading window
        
        # Signal control - NUEVO
        self.last_signal_bar = {}        # Track last signal bar per symbol
        self.active_signals = set()      # Track symbols with active signals
        
        
        self.logger.info("🎯 ORB Strategy initialized with centralized stop loss management")
    
    async def _initialize_strategy(self) -> None:
        """Initialize ORB strategy"""
        self.logger.info("Initializing Opening Range Breakout strategy")
        self.logger.info(f"Parameters: {self.parameters}")
        
        # Reset daily data at market open
        self._reset_daily_data()
    
    def _reset_daily_data(self) -> None:
        """Reset daily tracking data"""
        self.opening_ranges.clear()
        self.daily_stats.clear()
        self.breakout_signals.clear()
        self.trading_session_active.clear()
        self.last_signal_bar.clear()
        self.active_signals.clear()
    
    async def _analyze_bar(self, bar: MarketData) -> Optional[Signal]:
        """Analyze bar and generate ORB signal, including exit management"""
        symbol = bar.symbol
        
        exit_signal = self.stop_manager.check_exit_conditions(symbol, bar)
        if exit_signal:
            # Clean up our tracking when position exits
            self._cleanup_position_tracking(symbol)
            return exit_signal
        
        # PRIORITY 2: Check if we should skip signal generation
        if self._should_skip_signal_generation(symbol, bar):
            return None
        
        # Check if we have enough history
        if len(self.bars_history[symbol]) < self._parameters['volume_period']:
            return None
        
        try:
            # Initialize daily tracking if new day
            if not self._is_same_trading_day(symbol, bar.timestamp):
                self._reset_symbol_daily_data(symbol)
            
            # Update daily statistics
            self._update_daily_stats(symbol, bar)
            
            # Check if still in trading session
            if not self._is_trading_session_active(bar.timestamp):
                self.trading_session_active[symbol] = False
                return None
            
            # Define or update opening range
            self._update_opening_range(symbol, bar)
            
            # Check for breakout signal
            breakout_signal = self._check_opening_range_breakout(symbol, bar)
            
            if breakout_signal:
                # Evaluate all entry conditions
                conditions_met = self._evaluate_entry_conditions(symbol, bar, breakout_signal)
                
                # Check if minimum conditions are met
                min_conditions = self._parameters['min_conditions']
                conditions_count = sum(1 for condition in conditions_met.values() if condition)
                
                if conditions_count >= min_conditions and breakout_signal['direction'] == 'bullish':
                    # ENTRADA INMEDIATA - Sin esperar pullback
                    # Solo operamos en largo (LONG)
                    signal_type = SignalType.LONG
                    strength = min(conditions_count / len(conditions_met), 1.0)
                    
                    # Create signal
                    signal = Signal(
                        signal_id="",
                        symbol=symbol,
                        signal_type=signal_type,
                        strength=strength,
                        price=bar.close,
                        timestamp=bar.timestamp,
                        metadata={
                            'strategy': 'ORB',
                            'breakout_direction': breakout_signal['direction'],
                            'opening_range': self.opening_ranges[symbol],
                            'conditions_met': conditions_met
                        }
                    )
                    
                    # Register position with centralized stop manager
                    self._register_position_with_stop_manager(symbol, bar, signal)
                    
                    self.logger.info(
                        f"ORB signal for {symbol}: {signal_type.value} @ {bar.close:.2f} "
                        f"(strength: {strength:.2f})"
                    )
                    
                    return signal
                else:
                    if conditions_count >= min_conditions and breakout_signal['direction'] == 'bearish':
                        self.logger.debug(f"[{symbol}] Señal SHORT ignorada (solo operamos en LARGO)")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing bar for {symbol}: {e}")
            return None
    
    def _should_skip_signal_generation(self, symbol: str, bar: MarketData) -> bool:
        """Check if we should skip generating new signals for this symbol"""
        # Skip if already have active signal for this symbol
        if symbol in self.active_signals:
            return True
        
        # Skip if in cooldown period
        if symbol in self.last_signal_bar:
            current_bar_index = len(self.bars_history[symbol]) - 1
            bars_since_last_signal = current_bar_index - self.last_signal_bar[symbol]
            if bars_since_last_signal < self._parameters['signal_cooldown_bars']:
                return True
        
        return False
    
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
        
        # Mark as active signal and record bar
        self.active_signals.add(symbol)
        self.last_signal_bar[symbol] = len(self.bars_history[symbol]) - 1
        
        self.logger.info(f"✅ Registered {symbol} position with centralized stop manager")
    
    def _cleanup_position_tracking(self, symbol: str):
        """Clean up our tracking when position exits"""
        if symbol in self.breakout_signals:
            del self.breakout_signals[symbol]
        
        self.active_signals.discard(symbol)
        
        # Note: No need to cleanup stop loss tracking - that's handled by the manager

    def _is_same_trading_day(self, symbol: str, current_time: datetime) -> bool:
        """Check if current bar is from same trading day"""
        if symbol not in self.daily_stats:
            return False
        
        last_time = self.daily_stats[symbol].get('last_update')
        if not last_time:
            return False
        
        # Simple check - same date
        return current_time.date() == last_time.date()
    
    def _reset_symbol_daily_data(self, symbol: str) -> None:
        """Reset daily data for specific symbol"""
        self.opening_ranges.pop(symbol, None)
        self.daily_stats[symbol] = {
            'day_high': 0,
            'day_low': float('inf'),
            'total_volume': 0,
            'bar_count': 0,
            'first_bar_time': None,
            'last_update': None
        }
        self.breakout_signals.pop(symbol, None)
        self.trading_session_active[symbol] = True
        # Reset signal control for new day
        self.active_signals.discard(symbol)
        self.last_signal_bar.pop(symbol, None)
    
    def _update_daily_stats(self, symbol: str, bar: MarketData) -> None:
        """Update daily statistics for symbol"""
        if symbol not in self.daily_stats:
            self._reset_symbol_daily_data(symbol)
        
        stats = self.daily_stats[symbol]
        
        # Update daily high/low
        stats['day_high'] = max(stats['day_high'], bar.high)
        stats['day_low'] = min(stats['day_low'], bar.low)
        stats['total_volume'] += bar.volume
        stats['bar_count'] += 1
        stats['last_update'] = bar.timestamp
        
        if not stats['first_bar_time']:
            stats['first_bar_time'] = bar.timestamp
    
    def _is_trading_session_active(self, current_time: datetime) -> bool:
        """Check if still within active trading session"""
        trading_end_str = self._parameters.get('trading_end_time', '15:30:00')
        trading_start_str = self._parameters.get('trading_start_time', '09:30:00')
        
        # Parse time strings
        trading_end = time.fromisoformat(trading_end_str)
        trading_start = time.fromisoformat(trading_start_str)
        current_time_only = current_time.time()
        
        return trading_start <= current_time_only <= trading_end
    
    def _update_opening_range(self, symbol: str, bar: MarketData) -> None:
        """Define or update opening range with enhanced data quality validation"""
        if symbol not in self.opening_ranges:
            self.opening_ranges[symbol] = {
                'high': bar.high,
                'low': bar.low,
                'start_time': bar.timestamp,
                'range_defined': False,
                'range_size': 0,
                'midpoint': 0,
                'bar_count': 1,
                'total_volume': bar.volume,
                'data_quality_score': 0
            }
            return
        
        range_data = self.opening_ranges[symbol]
        
        # Check if still within opening range period
        minutes_elapsed = (bar.timestamp - range_data['start_time']).total_seconds() / 60
        
        if minutes_elapsed <= self._parameters['opening_range_minutes']:
            # Still defining range - update high/low
            range_data['high'] = max(range_data['high'], bar.high)
            range_data['low'] = min(range_data['low'], bar.low)
            range_data['bar_count'] += 1
            range_data['total_volume'] += bar.volume
            
        elif not range_data['range_defined']:
            # Range period ended - validate data quality and timing before finalizing

            # TIMING CHECK: Ensure enough time has passed (minimum 10 minutes)
            minutes_elapsed = (bar.timestamp - range_data['start_time']).total_seconds() / 60
            if minutes_elapsed < 10:
                self.logger.debug(f"🕐 {symbol}: Opening range too short ({minutes_elapsed:.1f} min), waiting...")
                return

            data_quality_ok = self._validate_opening_range_quality(symbol, range_data)

            if not data_quality_ok:
                self.logger.warning(f"❌ {symbol}: Opening range failed quality validation - SKIPPING ORB")
                # Mark as invalid range
                range_data['range_defined'] = False
                range_data['data_quality_score'] = 0
                return
            
            # Finalize valid range
            range_data['range_defined'] = True
            range_data['range_size'] = (range_data['high'] - range_data['low']) / range_data['low']
            range_data['midpoint'] = (range_data['high'] + range_data['low']) / 2
            
            self.logger.info(
                f"✅ {symbol}: Opening range defined with {range_data['bar_count']} bars, "
                f"High=${range_data['high']:.3f}, Low=${range_data['low']:.3f}, "
                f"Size={range_data['range_size']:.1%}, Quality={range_data['data_quality_score']:.1f}"
            )
    
    def _validate_opening_range_quality(self, symbol: str, range_data: Dict) -> bool:
        """Validate opening range data quality to prevent false signals"""
        try:
            quality_score = 0
            issues = []
            
            # 1. Minimum bar count (relaxed for smallcaps)
            min_bars_needed = max(3, self._parameters['opening_range_minutes'] // 5)  # 1 bar per 5 min (relaxed)
            if range_data['bar_count'] >= min_bars_needed:
                quality_score += 25
            else:
                issues.append(f"Insufficient bars: {range_data['bar_count']}/{min_bars_needed}")

            # 2. Minimum total volume (very relaxed for real market conditions)
            min_total_volume = 500  # Further reduced from 1K to 500 for better opportunity detection
            if range_data['total_volume'] >= min_total_volume:
                quality_score += 25
            else:
                issues.append(f"Low liquidity: {range_data['total_volume']:,.0f}/{min_total_volume:,.0f}")

            # 3. Range size validation (more permissive bounds)
            range_size = range_data.get('range_size', 0)
            if range_size == 0:  # Calculate if not set
                range_size = (range_data['high'] - range_data['low']) / range_data['low']

            # More lenient range size - allow very small ranges for consolidation breakouts
            min_range = max(0.005, self._parameters['range_min_size'] * 0.5)  # 50% reduction, minimum 0.5%
            max_range = self._parameters['range_max_size'] * 1.5  # 50% increase

            if min_range <= range_size <= max_range:
                quality_score += 25
            else:
                issues.append(f"Range size out of bounds: {range_size:.1%} (need {min_range:.1%}-{max_range:.1%})")

            # 4. Average volume per bar (very lenient)
            avg_volume_per_bar = range_data['total_volume'] / range_data['bar_count']
            if avg_volume_per_bar >= 25:  # Further reduced from 50 to 25
                quality_score += 25
            else:
                issues.append(f"Low avg volume per bar: {avg_volume_per_bar:.0f}")

            # Store quality score
            range_data['data_quality_score'] = quality_score

            # Significantly relaxed threshold for real market conditions
            quality_threshold = 25  # Reduced from 50% to 25% - need only 1 criterion to pass
            is_valid = quality_score >= quality_threshold
            
            if not is_valid:
                self.logger.warning(f"🚫 {symbol}: Quality score {quality_score}/100 < {quality_threshold}")
                for issue in issues:
                    self.logger.warning(f"   - {issue}")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error validating opening range quality for {symbol}: {e}")
            return False
    
    def _check_opening_range_breakout(self, symbol: str, bar: MarketData) -> Optional[Dict]:
        """Check for opening range breakout with enhanced validation"""
        if symbol not in self.opening_ranges:
            return None
        
        range_data = self.opening_ranges[symbol]
        
        # Range must be defined and validated
        if not range_data['range_defined']:
            return None
        
        # Must have passed quality validation (relaxed threshold)
        if range_data.get('data_quality_score', 0) < 50:
            return None
        
        # Check range size is within acceptable limits (redundant check)
        if not (self._parameters['range_min_size'] <= range_data['range_size'] <= self._parameters['range_max_size']):
            return None
        
        # Check for breakout
        breakout_buffer = self._parameters['breakout_min_size']
        
        # Bullish breakout (above range high)
        if bar.close > range_data['high'] * (1 + breakout_buffer):
            return {
                'direction': 'bullish',
                'breakout_price': bar.close,
                'range_high': range_data['high'],
                'range_low': range_data['low']
            }
        
        # Bearish breakout (below range low)
        elif bar.close < range_data['low'] * (1 - breakout_buffer):
            return {
                'direction': 'bearish',
                'breakout_price': bar.close,
                'range_high': range_data['high'],
                'range_low': range_data['low']
            }
        
        return None
    
    def _evaluate_entry_conditions(self, symbol: str, bar: MarketData, breakout_signal: Dict) -> Dict:
        """Evaluate all entry conditions for ORB strategy"""
        conditions = {}
        
        try:
            # 1. Opening range breakout (already confirmed)
            conditions['range_breakout'] = True
            
            # 2. Volume spike condition
            conditions['volume_spike'] = self._check_volume_spike(symbol)
            
            # 3. Volume confirmation on breakout
            conditions['breakout_volume'] = self._check_breakout_volume_confirmation(symbol)
            
            # 4. Price filter (penny stock range)
            conditions['price_filter'] = self._check_price_filter(bar)
            
            # 5. Gap size filter (not too large gap)
            conditions['gap_filter'] = self._check_gap_filter(symbol)
            
            # 6. Dollar volume filter
            conditions['dollar_volume'] = self._check_dollar_volume_filter(symbol)
            
            # 7. Time filter (not too late in session)
            conditions['time_filter'] = self._check_time_filter(bar.timestamp)
            
            # 8. Range quality filter
            conditions['range_quality'] = self._check_range_quality(symbol)
            
            return conditions
            
        except Exception as e:
            self.logger.error(f"Error evaluating conditions for {symbol}: {e}")
            return {'error': False}
    
    def _check_volume_spike(self, symbol: str) -> bool:
        """Check for volume spike compared to average"""
        try:
            df = self.get_bars_df(symbol, self._parameters['volume_period'])
            if len(df) < self._parameters['volume_period']:
                return False
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[:-1].mean()  # Exclude current bar
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            return volume_ratio >= self._parameters['volume_spike_threshold']
            
        except Exception as e:
            self.logger.error(f"Error checking volume spike for {symbol}: {e}")
            return False
    
    def _check_breakout_volume_confirmation(self, symbol: str) -> bool:
        """Check volume confirmation on breakout"""
        try:
            df = self.get_bars_df(symbol, 5)  # Last 5 bars
            if len(df) < 5:
                return False
            
            current_volume = df['volume'].iloc[-1]
            recent_avg_volume = df['volume'].iloc[-4:-1].mean()  # Previous 3 bars
            
            volume_ratio = current_volume / recent_avg_volume if recent_avg_volume > 0 else 0
            
            return volume_ratio >= self._parameters['volume_confirmation_threshold']
            
        except Exception as e:
            self.logger.error(f"Error checking breakout volume for {symbol}: {e}")
            return False
    
    def _check_price_filter(self, bar: MarketData) -> bool:
        """Check if price is within acceptable range for penny stocks"""
        return self._parameters['min_price'] <= bar.close <= self._parameters['max_price']
    
    def _check_gap_filter(self, symbol: str) -> bool:
        """Check gap size is not too large"""
        try:
            if len(self.bars_history[symbol]) < 2:
                return True
            
            current_open = self.bars_history[symbol][-1].open
            previous_close = self.bars_history[symbol][-2].close
            
            gap_size = abs(current_open - previous_close) / previous_close
            
            return gap_size <= self._parameters['max_gap_size']
            
        except Exception as e:
            self.logger.error(f"Error checking gap filter for {symbol}: {e}")
            return True
    
    def _check_dollar_volume_filter(self, symbol: str) -> bool:
        """Check minimum dollar volume requirement with enhanced validation"""
        try:
            # Enhanced dollar volume check
            if len(self.bars_history[symbol]) < 10:
                return False
            
            # Calculate recent dollar volume (last 10 bars)
            recent_bars = self.bars_history[symbol][-10:]
            total_dollar_volume = sum(bar.volume * bar.close for bar in recent_bars)
            avg_dollar_volume = total_dollar_volume / len(recent_bars)
            
            # Higher threshold for ORB
            min_dollar_volume = max(self._parameters['min_dollar_volume'], 50000)  # At least 50K
            
            is_valid = avg_dollar_volume >= min_dollar_volume
            
            if not is_valid:
                self.logger.debug(f"💰 {symbol}: Dollar volume {avg_dollar_volume:,.0f} < {min_dollar_volume:,.0f}")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Error checking dollar volume for {symbol}: {e}")
            return False
    
    def _check_time_filter(self, current_time: datetime) -> bool:
        """Check if within ORB trading window (9:30 AM - 11:30 AM)"""
        # ORB strategy should only trade in the morning session
        # Early entry: 9:45 AM (after opening range is defined)
        # Late cutoff: 11:30 AM (before lunch lull)
        early_start = time(9, 45)  # Allow 15 min for opening range
        late_cutoff = time(11, 30)  # Stop before lunch momentum dies
        current_time_only = current_time.time()

        return early_start <= current_time_only <= late_cutoff
    
    def _check_range_quality(self, symbol: str) -> bool:
        """Check opening range quality"""
        if symbol not in self.opening_ranges:
            return False
        
        range_data = self.opening_ranges[symbol]
        
        # Range should be well-defined but not too large
        range_size = range_data['range_size']
        
        return (self._parameters['range_min_size'] <= range_size <= self._parameters['range_max_size'])
    
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
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for ORB strategy with commission consideration"""
        try:
            symbol = signal.symbol
            price = signal.price
            
            # 1. Calculate base position size based on risk
            risk_amount = capital * min(risk_per_trade, self._parameters.get('risk_per_trade', 0.01))
            
            # Get stop price from signal metadata
            stop_price = signal.metadata.get('stop_price', 0)
            if stop_price <= 0:
                stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)
                if signal.signal_type == SignalType.LONG:
                    stop_price = price * (1 - stop_loss_pct)
                else:
                    stop_price = price * (1 + stop_loss_pct)
            
            # Calculate stop distance
            if signal.signal_type == SignalType.LONG:
                stop_distance = price - stop_price
            else:
                stop_distance = stop_price - price
            
            # 2. Calculate base quantity
            if stop_distance > 0:
                base_quantity = int(risk_amount / stop_distance)
            else:
                base_quantity = int(self._parameters.get('min_position_value', 80.0) / price)
            
            # 3. Apply position limits
            max_position_value = self._parameters.get('max_position_value', 300.0)
            max_shares_value = int(max_position_value / price)
            
            # Max shares based on max risk per trade (5% of capital)
            max_shares_risk = int((capital * 0.05) / price)
            
            # Take the more restrictive limit
            max_shares = min(max_shares_value, max_shares_risk)
            
            # 4. Final position size
            position_size = min(base_quantity, max_shares)
            position_size = max(position_size, self._parameters.get('min_quantity', 10))
            
            # 5. Round to nearest 10 for small accounts
            if price < 10.0:
                position_size = (position_size // 10) * 10
                position_size = max(position_size, 10)
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {signal.symbol}: {e}")
            return self._parameters['min_quantity']
    
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For ORB strategy, we don't need special logic on position updates
        # The stop loss management is handled by the centralized stop manager
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """Determine if position should be exited - required by IStrategy interface"""
        try:
            # Delegate to the centralized stop manager for exit decisions
            if hasattr(self, 'stop_manager') and self.stop_manager:
                exit_signal = self.stop_manager.check_exit_conditions(
                    symbol=position.symbol,
                    current_bar=current_bar
                )
                if exit_signal:
                    # Convert stop manager signal to our Signal format
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="ORB",
                        metadata={
                            'reason': exit_signal.get('reason', 'stop_manager'),
                            'entry_price': position.avg_price,
                            'pnl': (current_bar.close - position.avg_price) / position.avg_price if position.avg_price > 0 else 0
                        }
                    )
            
            # Fallback: Basic stop loss if no stop manager
            if position.quantity > 0:  # Long position
                stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)
                stop_price = position.avg_price * (1 - stop_loss_pct)
                
                if current_bar.close <= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="ORB",
                        metadata={
                            'reason': 'basic_stop_loss',
                            'entry_price': position.avg_price,
                            'stop_price': stop_price
                        }
                    )
            elif position.quantity < 0:  # Short position
                stop_loss_pct = self._parameters.get('stop_loss_pct', 0.05)
                stop_price = position.avg_price * (1 + stop_loss_pct)
                
                if current_bar.close >= stop_price:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="ORB",
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

    def get_strategy_info(self) -> dict:
        """Get strategy-specific information"""
        active_ranges = len([r for r in self.opening_ranges.values() if r.get('range_defined', False)])
        
        return {
            "name": self.name,
            "type": "Breakout + Volume",
            "timeframe": "Intraday (Opening Session)",
            "parameters": self.parameters,
            "active_ranges": active_ranges,
            "active_signals": len(self.breakout_signals),
            "signal_control": {
                "active_symbols": len(self.active_signals),
                "cooldown_symbols": len(self.last_signal_bar)
            },
            "performance": self.get_performance_stats(),
            # Stop loss stats come from centralized manager
            "stop_loss_stats": self.stop_manager.get_statistics()
        }