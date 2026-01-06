# strategies/gap_go_strategy.py
"""
Gap & Go Strategy: Intraday strategy for small caps that gap significantly at market open.
FIXED VERSION - Eliminates duplicate methods and fixes all data structure issues
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class GapGoStrategy(BaseStrategy):
    """
    Gap & Go Strategy implementation for intraday small cap trading.
    
    Entry Conditions:
    1. Significant gap at market open (3-10%+)
    2. High volume confirmation (2-5x average)
    3. Price action confirmation (breakout of first candle)
    4. Gap direction momentum maintained
    5. No immediate reversal patterns
    
    Exit Conditions:
    1. Profit targets (1:2 or 1:3 risk/reward)
    2. Stop loss (below/above gap fill level)
    3. Volume drying up
    4. End of day exit
    5. Gap fill (partial or complete)
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        # ENHANCED GAP&GO DEFAULTS - Based on advanced PMH breakout strategy
        fallback_defaults = {
            # Enhanced Gap parameters (based on PMH strategy)
            'min_gap_percent': 3.0,           # Minimum 15% gap (vs 3% before)
            'max_gap_percent': 15.0,           # Extended max for bigger movers
            'max_gap_to_pmh': 15.0,            # NEW: Max 15% gap between open and PMH
            'gap_timeout_minutes': 60,         # Extended timeout for PMH development

            # Enhanced Volume parameters
            'volume_multiplier': 2.0,          # Higher volume requirement (vs 1.8)
            'volume_period': 10,               # Longer period for average
            'min_volume': 200000,              # Higher minimum volume
            'breakout_volume_multiplier': 1.5, # NEW: Volume confirmation for PMH breakout

            # PMH Strategy Parameters (NEW)
            'pmh_consolidation_period': 15,    # Minutes to detect consolidation below PMH
            'pmh_support_tolerance': 0.02,     # 2% tolerance for support level detection
            'pmh_breakout_confirmation': 0.05, # 5% spike above PMH breakout required
            'dip_volume_ratio': 0.7,           # Dip volume should be <70% of breakout volume
            
            # Enhanced Entry filters
            'max_price': 15.0,                 # Lower max price for better float control
            'min_price': 1.0,                  # Higher min price for quality
            'premarket_volume_min': 25000,     # Higher premarket volume requirement
            'max_float': 100000000,             # NEW: Max float for better control (50M)
            'catalyst_required': False,     # NEW: Require strong catalyst/news (0.7)

            # Enhanced Risk management (PMH-based) - REMOVED hardcoded stop_loss_pct
            # stop_loss_pct now uses config.ini fallback_stop_loss_pct = 0.05 (5%)
            'gap_fill_protection': True,       # NEW: Exit if approaching gap fill    # NEW: Use PMH as stop reference
            'profit_target': 0.25,             # Higher target (25% vs 20%)
            'trailing_stop_activation': 0.08,  # Higher activation (10%)
            'trailing_stop_distance': 0.05,    # Wider trailing distance

            # Enhanced Time management (First hour focus)
            'market_open_hour': 9.5,
            'market_close_hour': 16.0,
            'no_entry_after_hour': 12.0,       # STRICT: Only first hour (vs 15.0)
            'pmh_analysis_start': 4.0,         # Start PMH analysis at 4 AM
            
            # Position sizing (ML-configurable)
            'max_position_value': 300.0,
            'min_position_value': 50.0,
            'min_quantity': 10,
            'max_risk_per_trade': 0.01,
            'commission_per_share': 0.01,
            'min_commission': 1.0,
            
            # Gap direction (PMH strategy - only up gaps)
            'allow_gap_up': True,
            'allow_gap_down': False,            # PMH strategy focuses on gap ups

            # History requirements
            'min_history_days': 5,              # Reduced for faster detection
            'max_history_bars': 100,

            # Stuffed Move Detection (NEW - Failure detection)
            'stuffed_move_volume_ratio': 1.2,   # Rejection volume > 1.2x breakout volume
            'stuffed_move_below_pmh': True,     # Price must close below PMH
            'stuffed_move_immediate_exit': True, # Exit immediately on stuffed move

            # Enhanced FOMO detection
            'fomo_threshold': 0.60,             # Lower threshold for better entries
            'fomo_critical_threshold': 0.80,
            'fomo_volume_explosion_multiplier': 4.0, # Reduced for more sensitivity

            # FLEXIBLE SCORING SYSTEM parameters (NEW - ML-configurable)
            'use_flexible_scoring': True,        # Enable flexible scoring vs binary conditions
            'min_total_score': 350,             # Minimum score threshold (350/700 = 50%)
            'good_total_score': 450,            # Good setup threshold (450/700 = 64%)
            'excellent_total_score': 550,       # Excellent setup threshold (550/700 = 79%)

            # PMH Strategy Entry Conditions (NEW)
            'require_pmh_breakout': True,       # Must break premarket high
            'require_consolidation': True,      # Must show consolidation below PMH
            'require_spike_confirmation': True, # Must have 5%+ spike over PMH
            'require_dip_entry': True,          # Enter on dip back to PMH level
        }
        
        # Initialize with fallback defaults first to get logger
        super().__init__("GapGo", fallback_defaults)
        
        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('GAP_GO_STRATEGY', fallback_defaults)
            
            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)
            
            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for Gap&Go strategy: {e}")
            # Keep fallback defaults
        
        # Enable FOMO detection for GapGo (ML-configurable)
        fomo_config = {
            'fomo_threshold': self._parameters.get('fomo_threshold', 0.70),
            'critical_threshold': self._parameters.get('fomo_critical_threshold', 0.85),
            'volume_explosion_multiplier': self._parameters.get('fomo_volume_explosion_multiplier', 6.0),
            'consecutive_green_bars': self._parameters.get('fomo_consecutive_green_bars', 4),
            'rsi_overbought_level': self._parameters.get('fomo_rsi_overbought_level', 80)
        }
        
        if self.enable_fomo_exit(fomo_config):
            self.logger.info("🎪 FOMO Detection enabled for Gap & Go Strategy")
        else:
            self.logger.warning("⚠️ FOMO Detection could not be enabled")
        
        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🔧 GapGo received parameters: {parameters}")
        
        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()
        
        # Strategy state - EXPLICITLY initialize as dictionaries to prevent corruption
        self.gap_info = {}           # Store gap information per symbol
        self.first_candles = {}      # Store first candle data
        self.entry_signals = {}      # Store entry signal data (simplified - no stop logic)
        self.market_open_prices = {} # Store market open prices

        # PMH Strategy State (NEW)
        self.pmh_data = {}           # Store premarket high data per symbol
        self.consolidation_data = {} # Store consolidation analysis per symbol
        self.breakout_data = {}      # Store PMH breakout information
        self.dip_tracking = {}       # Track dip back to PMH level
        self.stuffed_moves = {}      # Track stuffed move detection
        self.spike_confirmations = {} # Track 5%+ spike confirmations

        # Add tracking for signal prevention
        self.last_signal_times = {}  # Track last signal time per symbol
        self.signal_cooldown_minutes = 5  # Minimum time between signals for same symbol
        
        self.logger.info("🎯 Gap&Go Strategy initialized with centralized stop loss management")
        
    async def _initialize_strategy(self) -> None:
        """Initialize Gap & Go strategy"""
        self.logger.info("Initializing Gap & Go strategy")
        self.logger.info(f"Parameters: {self.parameters}")
        
        # Validate time parameters
        if self._parameters['market_open_hour'] >= self._parameters['no_entry_after_hour']:
            self.logger.warning("no_entry_after_hour should be after market_open_hour")
    
    def _ensure_strategy_dicts_initialized(self) -> None:
        """Ensure all strategy state dictionaries are properly initialized"""
        # Fix entry_signals
        if not hasattr(self, 'entry_signals') or not isinstance(self.entry_signals, dict):
            self.logger.warning(f"FIXING entry_signals: was {type(getattr(self, 'entry_signals', 'missing'))}, resetting to dict")
            self.entry_signals = {}
        
        # Fix gap_info
        if not hasattr(self, 'gap_info') or not isinstance(self.gap_info, dict):
            self.logger.warning(f"FIXING gap_info: was {type(getattr(self, 'gap_info', 'missing'))}, resetting to dict")
            self.gap_info = {}
        
        # Fix first_candles
        if not hasattr(self, 'first_candles') or not isinstance(self.first_candles, dict):
            self.logger.warning(f"FIXING first_candles: was {type(getattr(self, 'first_candles', 'missing'))}, resetting to dict")
            self.first_candles = {}
        
        # Fix market_open_prices
        if not hasattr(self, 'market_open_prices') or not isinstance(self.market_open_prices, dict):
            self.logger.warning(f"FIXING market_open_prices: was {type(getattr(self, 'market_open_prices', 'missing'))}, resetting to dict")
            self.market_open_prices = {}
        
        # Fix last_signal_times
        if not hasattr(self, 'last_signal_times') or not isinstance(self.last_signal_times, dict):
            self.logger.warning(f"FIXING last_signal_times: was {type(getattr(self, 'last_signal_times', 'missing'))}, resetting to dict")
            self.last_signal_times = {}
    
    def _is_signal_too_recent(self, symbol: str, timestamp) -> bool:
        """Check if we've generated a signal too recently for this symbol"""
        if symbol not in self.last_signal_times:
            return False
        
        try:
            last_time = self.last_signal_times[symbol]
            current_time = timestamp
            
            # Convert to datetime if needed
            if isinstance(last_time, (int, float)):
                last_time = datetime.fromtimestamp(last_time)
            if isinstance(current_time, (int, float)):
                current_time = datetime.fromtimestamp(current_time)
            
            time_diff = (current_time - last_time).total_seconds() / 60  # Minutes
            return time_diff < self.signal_cooldown_minutes
            
        except Exception as e:
            self.logger.error(f"Error checking signal timing for {symbol}: {e}")
            return False
    
    def _record_signal_time(self, symbol: str, timestamp) -> None:
        """Record when we generated a signal for this symbol"""
        self.last_signal_times[symbol] = timestamp
    
    def _ensure_bars_history_is_list(self, symbol: str) -> None:
        """Ensure bars_history[symbol] is properly initialized as a list"""
        # Debug logging to identify the problem
        if symbol not in self.bars_history:
            self.logger.debug(f"Initializing bars_history for {symbol}")
            self.bars_history[symbol] = []
        else:
            current_type = type(self.bars_history[symbol])
            self.logger.debug(f"bars_history[{symbol}] type: {current_type}, value: {self.bars_history[symbol]}")
            
            if not isinstance(self.bars_history[symbol], list):
                self.logger.warning(f"FIXING bars_history for {symbol}: was {current_type}, converting to list")
                # Try to convert to list if possible, otherwise start fresh
                try:
                    if hasattr(self.bars_history[symbol], '__iter__') and not isinstance(self.bars_history[symbol], (str, bytes)):
                        self.bars_history[symbol] = list(self.bars_history[symbol])
                        self.logger.info(f"Successfully converted bars_history[{symbol}] to list")
                    else:
                        self.bars_history[symbol] = []
                        self.logger.info(f"Reset bars_history[{symbol}] to empty list")
                except Exception as e:
                    self.logger.error(f"Error converting bars_history[{symbol}]: {e}")
                    self.bars_history[symbol] = []

    async def _analyze_bar(self, bar: MarketData, context: Optional[Any] = None) -> Optional[Signal]:
        """Analyze bar and generate Gap & Go signal, including exit management"""
        symbol = bar.symbol
        
        try:
            # CRITICAL: Ensure all strategy state dictionaries are properly initialized
            self._ensure_bars_history_is_list(symbol)
            self._ensure_strategy_dicts_initialized()
            
            # First, check exit conditions for existing position
            # DEBUG: STOP LOSS DESACTIVADO - Comentado para debugging
            exit_sig = self.stop_manager.check_exit_conditions(symbol, bar)
            if exit_sig:
                # Clean up our tracking when position exits
                self._cleanup_position_tracking(symbol)
                self._record_signal_time(symbol, bar.timestamp)
                return exit_sig
            
            # Check if signal is too recent
            if self._is_signal_too_recent(symbol, bar.timestamp):
                self.logger.debug(f"[{symbol}] Signal too recent, in cooldown period")
                return None
            
            # Need sufficient history for gap calculation
            if len(self.bars_history[symbol]) < self._parameters['min_history_days']:
                self.logger.debug(f"{symbol}: Not enough history ({len(self.bars_history[symbol])} bars)")
                return None
                
            current_time = self._get_time_from_timestamp(bar.timestamp)
            
            # Check if we're in trading hours
            if not self._is_trading_hours(current_time):
                return None
            
            # Check if it's too late for new entries
            if current_time >= self._parameters['no_entry_after_hour']:
                return None
            
            # ===================================================
            # ENHANCED PMH GAP&GO STRATEGY LOGIC (NEW)
            # ===================================================

            # STEP 1: Detect gap if not already detected today
            if symbol not in self.gap_info or not self._is_same_day(self.gap_info[symbol]['timestamp'], bar.timestamp):
                gap_data = self._detect_gap(symbol, bar)
                if gap_data:
                    self.gap_info[symbol] = gap_data

                    # Enhanced gap validation - must meet new stricter criteria
                    gap_percent = abs(gap_data['gap_percent'])
                    if gap_percent >= self._parameters['min_gap_percent']:  # 15%+ gap required
                        self.logger.info(f"✅ {symbol}: Valid gap detected {gap_data['gap_percent']:.1f}% "
                                       f"(meets {self._parameters['min_gap_percent']:.0f}% requirement)")
                    else:
                        self.logger.debug(f"❌ {symbol}: Gap {gap_percent:.1f}% too small "
                                        f"(need {self._parameters['min_gap_percent']:.0f}%+)")
                        return None
                else:
                    return None

            # Check if we have a valid gap for this symbol
            if symbol not in self.gap_info:
                return None

            gap_data = self.gap_info[symbol]

            # Store market open prices for PMH analysis
            current_time = self._get_time_from_timestamp(bar.timestamp)
            if current_time >= 9.5 and current_time <= 9.6:  # Market open period
                self.market_open_prices[symbol] = bar.open

            # STEP 2: PMH Analysis (using centralized ML context)
            pmh_resistance_strength = 0.0
            if context and hasattr(context, 'pmh_resistance_strength'):
                pmh_resistance_strength = context.pmh_resistance_strength
                self.logger.info(f"🎯 {symbol}: PMH resistance strength = {pmh_resistance_strength:.2f}")

            # PMH <80% gain = good for Gap_Go (more room to run)
            pmh_suitable_for_gap_go = pmh_resistance_strength < 0.7  # <80% PMH gain

            if not pmh_suitable_for_gap_go and pmh_resistance_strength > 0:
                self.logger.info(f"⏭️ {symbol}: PMH too strong ({pmh_resistance_strength:.2f}) for Gap_Go - better for retroceso patterns")
                return None

            # STEP 3: Gap_Go PMH Logic (simplified - no need for complex consolidation)
            # With centralized PMH, we focus on gap + momentum instead of PMH breakouts

            # STEP 4: Enhanced Gap + Momentum Logic (simplified without PMH complexities)
            # Focus on gap strength + volume + momentum for Gap_Go pattern

            # STEP 6: Check for Stuffed Move (Failure Scenario)
            stuffed_move = self._detect_stuffed_move(symbol, bar)
            if stuffed_move and self._parameters.get('stuffed_move_immediate_exit', True):
                # Generate immediate exit signal for stuffed move
                self.logger.warning(f"🚨 {symbol}: STUFFED MOVE - Generating exit signal")
                return self._generate_exit_signal(symbol, bar, "STUFFED_MOVE")

            # STEP 5: Enhanced Gap_Go Entry Logic (using centralized PMH context)
            if pmh_suitable_for_gap_go:
                # PMH <80% = good for Gap_Go, check traditional gap conditions
                if self._should_enter_gap_go_with_pmh_context(symbol, bar, pmh_resistance_strength):
                    return self._generate_enhanced_gap_go_signal(symbol, bar, pmh_resistance_strength)

            # FALLBACK: Traditional Gap&Go logic if no PMH context available
            
            # Check if gap is still valid (within timeout)
            if self._is_gap_expired(gap_data, bar.timestamp):
                return None
            
            # CONTROL DE POSICIONES: Anti-martingala + piramidación inteligente  
            position_check = self._can_open_new_position(symbol, bar.close, 'long' if gap_data['direction'] == 'up' else 'short')
            if not position_check['can_open']:
                if position_check['position_action'] == 'blocked':
                    self.logger.debug(f"[{symbol}] {position_check['reason']}")
                return None
            
            # Log piramidación si es el caso
            if position_check['position_action'] == 'pyramid':
                self.logger.info(f"[{symbol}] {position_check['reason']}")
            
            # Store first candle data
            if symbol not in self.first_candles:
                self.first_candles[symbol] = self._create_first_candle(bar, gap_data)
            
            # FLEXIBLE SCORING SYSTEM: Use weighted scores instead of binary conditions
            use_scoring_system = self._parameters.get('use_flexible_scoring', True)  # Enable by default

            if use_scoring_system:
                # Get detailed scoring for each factor
                entry_scores = self._evaluate_gap_entry_conditions_scoring(symbol, bar, gap_data)
                total_score = entry_scores['total_score']

                # ML-configurable scoring thresholds for smallcaps
                min_score_threshold = self._parameters.get('min_total_score', 350)  # 350/700 = 50% threshold
                good_score_threshold = self._parameters.get('good_total_score', 450)  # 450/700 = 64% threshold
                excellent_score_threshold = self._parameters.get('excellent_total_score', 550)  # 550/700 = 79% threshold

                # Determine signal strength based on score
                if total_score >= excellent_score_threshold:
                    strength = 0.95  # Excellent setup
                elif total_score >= good_score_threshold:
                    strength = 0.80  # Good setup
                elif total_score >= min_score_threshold:
                    strength = 0.65  # Acceptable setup
                else:
                    # Score too low - no signal
                    self.logger.info(f"🎯 {symbol}: Score {total_score:.0f} below threshold {min_score_threshold}")
                    return None

                # Only gap up for now (direction score should be 100 for gap up)
                direction_acceptable = entry_scores.get('direction_score', 0) >= 80

                if total_score >= min_score_threshold and direction_acceptable:
                    # ENTRADA INMEDIATA - Scoring-based entry
                    signal_type = SignalType.LONG

                    self.logger.info(f"🎯 {symbol}: SCORING ENTRY - Score: {total_score:.0f}/{700} "
                                   f"(Gap:{entry_scores.get('gap_size_score', 0):.0f} "
                                   f"Vol:{entry_scores.get('volume_score', 0):.0f} "
                                   f"Mom:{entry_scores.get('momentum_score', 0):.0f}) "
                                   f"Strength: {strength:.2f}")
                else:
                    return None
            else:
                # LEGACY BINARY SYSTEM: Use old 70% threshold method
                entry_conditions = self._evaluate_gap_entry_conditions(symbol, bar, gap_data)

                # Count conditions met
                conditions_met = sum(1 for condition in entry_conditions.values() if condition)
                total_conditions = len(entry_conditions)

                # ML-configurable condition threshold
                min_conditions_threshold = self._parameters.get('min_conditions_threshold', 0.7)  # 70% by default
                min_conditions_needed = int(total_conditions * min_conditions_threshold)

                if conditions_met >= min_conditions_needed and gap_data['direction'] == 'up':
                    # ENTRADA INMEDIATA - Sin esperar pullback
                    # Solo operamos en largo (LONG) - Ignoramos SHORT
                    signal_type = SignalType.LONG
                    strength = min(conditions_met / total_conditions, 1.0)

                    self.logger.info(f"🎯 {symbol}: BINARY ENTRY - Conditions: {conditions_met}/{total_conditions} "
                                   f"Strength: {strength:.2f}")
                else:
                    return None

                # Store entry signal info BEFORE creating the signal to prevent duplicates
                # Actualizar para piramidación
                existing_entry = self.entry_signals.get(symbol, {})
                entry_count = existing_entry.get('entry_count', 0) + 1

                # Calcular precio promedio si es piramidación
                if position_check['position_action'] == 'pyramid':
                    prev_price = existing_entry.get('entry_price', bar.close)
                    prev_count = existing_entry.get('entry_count', 1)
                    avg_price = (prev_price * prev_count + bar.close) / (prev_count + 1)
                else:
                    avg_price = bar.close

                self.entry_signals[symbol] = {
                    'gap_data': gap_data,
                    'entry_price': bar.close,  # Precio de esta entrada específica
                    'avg_price': avg_price,    # Precio promedio de todas las entradas
                    'entry_count': entry_count,
                    'position_action': position_check['position_action'],
                    'bars_in_trade': 0,
                    'entry_time': bar.timestamp,
                    'conditions': entry_conditions,
                    'first_candle': self.first_candles[symbol],
                    'signal_created': True,  # Flag to track signal creation
                    'direction': 'long' if gap_data['direction'] == 'up' else 'short'
                }

                # Record signal timing
                self._record_signal_time(symbol, bar.timestamp)

                signal = Signal(
                    signal_id=f"GapGo-ENTRY-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                    symbol=symbol,
                    signal_type=signal_type,
                    strength=strength,
                    price=bar.close,
                    timestamp=bar.timestamp,
                    strategy_name="Gap_Go",
                    metadata={
                        'strategy': 'GapGo',
                        'setup_type': 'gap_go_breakout',
                        'gap_percent': gap_data['gap_percent'],
                        'volume_ratio': gap_data.get('volume_ratio', 0),
                        'pattern': f"gap_{abs(gap_data['gap_percent']):.0f}pct_{conditions_met}of{total_conditions}",
                        'conditions_met': conditions_met,
                        'total_conditions': total_conditions,
                        'is_entry': True,
                        'stop_loss': bar.close * (1 - self._parameters['stop_loss_pct']),
                        'take_profit': bar.close * (1 + self._parameters['profit_target'])
                    }
                )

                # Register position with centralized stop_loss_manager
                self._register_position_with_stop_manager(symbol, bar, signal)

                return signal
                
        except Exception as e:
            self.logger.error(f"Error analyzing bar for {symbol}: {e}")
            import traceback
            self.logger.error(f"Full stack trace: {traceback.format_exc()}")
            
            # Add extra debugging to identify where the error occurs
            try:
                self.logger.error(f"bars_history type for {symbol}: {type(self.bars_history.get(symbol, 'NOT_FOUND'))}")
                
                # Debug strategy state dictionaries
                self.logger.error(f"entry_signals type: {type(getattr(self, 'entry_signals', 'missing'))}")
                self.logger.error(f"gap_info type: {type(getattr(self, 'gap_info', 'missing'))}")
                self.logger.error(f"first_candles type: {type(getattr(self, 'first_candles', 'missing'))}")
                self.logger.error(f"market_open_prices type: {type(getattr(self, 'market_open_prices', 'missing'))}")
            except Exception as debug_e:
                self.logger.error(f"Error in debugging: {debug_e}")
            
            return None
    
    def _check_exit_conditions(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """Generate EXIT signal based on stop-loss, trailing stop, or profit target"""
        # CRITICAL FIX: Ensure entry_signals is properly initialized as dict
        if not hasattr(self, 'entry_signals') or not isinstance(self.entry_signals, dict):
            self.logger.warning(f"FIXING entry_signals in exit check: was {type(getattr(self, 'entry_signals', 'missing'))}, resetting to dict")
            self.entry_signals = {}
        
        if symbol not in self.entry_signals:
            return None
        
        info = self.entry_signals[symbol]
        
        # Validate info structure
        if not isinstance(info, dict) or 'gap_data' not in info or 'entry_price' not in info:
            self.logger.warning(f"Invalid entry_signals info for {symbol}, removing")
            self.entry_signals.pop(symbol, None)
            return None
            
        side = 'bullish' if info['gap_data']['direction'] == 'up' else 'bearish'
        entry_price = info['entry_price']
        current_price = bar.close
        
        # Initialize tracking values if they don't exist
        if 'highest_price' not in info:
            info['highest_price'] = entry_price if side == 'bullish' else float('inf')
        if 'lowest_price' not in info:
            info['lowest_price'] = entry_price if side == 'bearish' else float('inf')
        
        # Update highest/lowest price seen
        if side == 'bullish':
            info['highest_price'] = max(info['highest_price'], current_price)
            current_pnl = (current_price - entry_price) / entry_price
        else:  # bearish
            info['lowest_price'] = min(info['lowest_price'], current_price)
            current_pnl = (entry_price - current_price) / entry_price
        
        # Check exit conditions
        exit_reason = None
        
        # 1. Initial Stop Loss
        stop_price = entry_price * (1 - self._parameters['stop_loss_pct']) if side == 'bullish' else \
                     entry_price * (1 + self._parameters['stop_loss_pct'])
        
        if (side == 'bullish' and current_price <= stop_price) or \
           (side == 'bearish' and current_price >= stop_price):
            exit_reason = 'initial_stop_loss'
        
        # 2. Trailing Stop (only if we've reached activation threshold)
        if not exit_reason and current_pnl >= self._parameters['trailing_stop_activation']:
            if side == 'bullish':
                trailing_stop = info['highest_price'] * (1 - self._parameters['trailing_stop_distance'])
                if current_price <= trailing_stop:
                    exit_reason = 'trailing_stop'
            else:  # bearish
                trailing_stop = info['lowest_price'] * (1 + self._parameters['trailing_stop_distance'])
                if current_price >= trailing_stop:
                    exit_reason = 'trailing_stop'
        
        # 3. Profit Target
        if not exit_reason:
            target_price = entry_price * (1 + self._parameters['profit_target']) if side == 'bullish' else \
                          entry_price * (1 - self._parameters['profit_target'])
            
            if (side == 'bullish' and current_price >= target_price) or \
               (side == 'bearish' and current_price <= target_price):
                exit_reason = 'profit_target'
        
        # Generate exit signal if any condition is met
        if exit_reason:
            # Calculate time held
            time_held_minutes = 0
            if 'entry_time' in info:
                try:
                    time_diff = (bar.timestamp - info['entry_time']).total_seconds() / 60
                    time_held_minutes = max(0, time_diff)  # Ensure non-negative
                except:
                    time_held_minutes = 0
            
            # Calculate P&L dollars (simple calculation)
            pnl_dollars = (current_price - entry_price) * 100  # Assuming 100 shares
            
            self.logger.info(f"[GapGo EXIT] {symbol}: {exit_reason} at {current_price:.2f} "
                           f"(Entry: {entry_price:.2f}, PnL: {current_pnl*100:.1f}%)")
            
            # Clean up entry info BEFORE creating signal
            self.entry_signals.pop(symbol, None)
            
            # Create and return exit signal with unique ID
            sig_type = SignalType.EXIT_LONG if side == 'bullish' else SignalType.EXIT_SHORT
            return Signal(
                signal_id=f"GapGo-EXIT-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                signal_type=sig_type,
                strength=1.0,
                price=current_price,
                timestamp=bar.timestamp,
                strategy_name="Gap_Go",
                metadata={
                    'reason': exit_reason,
                    'strategy': 'GapGo',
                    'entry_price': entry_price,
                    'pnl': current_pnl,
                    'pnl_pct': current_pnl * 100,
                    'pnl_dollars': pnl_dollars,
                    'is_exit': True,
                    'time_held_minutes': time_held_minutes,
                    'position_size': 100  # Default position size for calculation
                }
            )
        
        return None
    
    def _detect_gap(self, symbol: str, current_bar: MarketData) -> Optional[Dict]:
        """Detect if current bar represents a significant gap"""
        try:
            # Ensure bars_history is properly initialized
            self._ensure_bars_history_is_list(symbol)
            # Ensure strategy dicts are initialized
            self._ensure_strategy_dicts_initialized()
                
            bars = self.bars_history[symbol]
                
            if len(bars) < 2:
                return None
                
            # Get previous day's close (assuming last bar is previous close)
            previous_close = bars[-2].close
            current_open = current_bar.open
            current_price = current_bar.close
                
            # Calculate gap percentage
            gap_percent = ((current_open - previous_close) / previous_close) * 100
            gap_direction = 'up' if gap_percent > 0 else 'down'
            gap_abs_percent = abs(gap_percent)
            
            # Check if gap meets minimum requirements
            if gap_abs_percent < self._parameters['min_gap_percent']:
                return None
                
            # Check if gap is not too extreme
            if gap_abs_percent > self._parameters['max_gap_percent']:
                self.logger.warning(f"Gap too large for {symbol}: {gap_abs_percent:.2f}%")
                return None
                
            # Check price range filter
            if (current_price < self._parameters['min_price'] or 
                current_price > self._parameters['max_price']):
                return None
                
            # Check direction filter
            if gap_direction == 'up' and not self._parameters['allow_gap_up']:
                return None
            if gap_direction == 'down' and not self._parameters['allow_gap_down']:
                return None
                
            # Calculate volume ratio
            volume_ratio = self._calculate_volume_ratio(symbol, current_bar)
                
            # Check minimum volume requirements
            if (current_bar.volume < self._parameters['min_volume'] or
                volume_ratio < self._parameters['volume_multiplier']):
                return None
                
            return {
                'previous_close': previous_close,
                'current_open': current_open,
                'gap_percent': gap_percent,
                'gap_abs_percent': gap_abs_percent,
                'direction': gap_direction,
                'volume_ratio': volume_ratio,
                'timestamp': current_bar.timestamp,
                'confirmed': False
            }
                
        except Exception as e:
            self.logger.error(f"Error detecting gap for {symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def _calculate_volume_ratio(self, symbol: str, current_bar: MarketData) -> float:
        """Calculate volume ratio compared to average - SAFE VERSION"""
        try:
            # Ensure bars_history is properly initialized
            self._ensure_bars_history_is_list(symbol)
            
            # Get bars directly from bars_history instead of using get_bars_df
            bars = self.bars_history[symbol]
            if not isinstance(bars, list) or len(bars) < self._parameters['volume_period']:
                self.logger.debug(f"Not enough bars for volume ratio: {len(bars) if isinstance(bars, list) else 'not a list'}")
                return 0.0
            
            # Take the last N bars (excluding current one which might not be in history yet)
            recent_bars = bars[-self._parameters['volume_period']:]
            if len(recent_bars) < 2:
                return 0.0
            
            # Calculate average volume from recent bars
            volumes = [bar.volume for bar in recent_bars if hasattr(bar, 'volume')]
            if not volumes:
                return 0.0
                
            avg_volume = sum(volumes) / len(volumes)
            
            if avg_volume == 0:
                return 0.0
                
            # Calculate volume ratio
            volume_ratio = current_bar.volume / avg_volume
            self.logger.debug(f"Volume ratio for {symbol}: {volume_ratio:.2f} (current: {current_bar.volume}, avg: {avg_volume:.0f})")
            return volume_ratio
                
        except Exception as e:
            self.logger.error(f"Error calculating volume ratio for {symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace in volume ratio: {traceback.format_exc()}")
            return 0.0
    
    def _evaluate_gap_entry_conditions_scoring(self, symbol: str, bar: MarketData, gap_data: Dict) -> Dict[str, float]:
        """FLEXIBLE SCORING SYSTEM: Evaluate entry conditions with weighted scores (0-100) instead of binary"""
        try:
            # Ensure bars_history is properly initialized
            self._ensure_bars_history_is_list(symbol)

            scores = {}

            # 1. GAP SIZE SCORE (0-100): Reward larger gaps for smallcaps
            gap_pct = gap_data['gap_abs_percent']
            min_gap = self._parameters['min_gap_percent']  # 2.0%
            max_gap = self._parameters['max_gap_percent']  # 50.0%

            if gap_pct < min_gap:
                scores['gap_size_score'] = max(0, (gap_pct / min_gap) * 50)  # Partial credit below minimum
            elif gap_pct > max_gap:
                scores['gap_size_score'] = max(0, 100 - ((gap_pct - max_gap) * 2))  # Penalty for excessive gaps
            else:
                # Sweet spot: 2-8% gets max score, then gradual decline
                if gap_pct <= 8.0:
                    scores['gap_size_score'] = 100
                else:
                    scores['gap_size_score'] = max(60, 100 - ((gap_pct - 8.0) * 2))

            # 2. VOLUME SCORE (0-100): Reward higher volume ratios
            vol_ratio = gap_data.get('volume_ratio', 1.0)
            min_vol = self._parameters['volume_multiplier']  # 2.0x

            if vol_ratio < min_vol * 0.5:  # Below 50% of requirement
                scores['volume_score'] = 0
            elif vol_ratio < min_vol:  # Below requirement but give partial credit
                scores['volume_score'] = (vol_ratio / min_vol) * 60
            elif vol_ratio < min_vol * 2:  # 1x-2x requirement = excellent
                scores['volume_score'] = 60 + ((vol_ratio - min_vol) / min_vol) * 40  # 60-100 points
            else:  # Above 2x requirement = exceptional
                scores['volume_score'] = min(100, 100 + ((vol_ratio - min_vol * 2) * 5))

            # 3. PRICE RANGE SCORE (0-100): Reward optimal smallcap price range
            price = bar.close
            min_price = self._parameters['min_price']  # 1.0
            max_price = self._parameters['max_price']  # 15.0

            if price < min_price or price > max_price:
                scores['price_range_score'] = 0  # Hard rejection for out of range
            elif 3.0 <= price <= 8.0:  # Sweet spot for smallcaps
                scores['price_range_score'] = 100
            elif 1.0 <= price < 3.0:  # Lower range - partial credit
                scores['price_range_score'] = 50 + ((price - 1.0) / 2.0) * 50
            else:  # 8-15 range - declining score
                scores['price_range_score'] = max(40, 100 - ((price - 8.0) / 7.0) * 60)

            # 4. DIRECTION SCORE (0-100): Binary but allow partial for shorts in rare cases
            if gap_data['direction'] == 'up' and self._parameters['allow_gap_up']:
                scores['direction_score'] = 100
            elif gap_data['direction'] == 'down' and self._parameters['allow_gap_down']:
                scores['direction_score'] = 80  # Lower score for gap downs
            else:
                scores['direction_score'] = 0

            # 5. CURRENT VOLUME STRENGTH SCORE (0-100)
            try:
                current_vol_strong = self._check_current_volume_strength(symbol, bar)
                current_vol_ratio = self._calculate_volume_ratio(symbol, bar)

                if current_vol_strong:
                    scores['current_volume_score'] = min(100, 70 + (current_vol_ratio * 10))
                else:
                    scores['current_volume_score'] = max(0, current_vol_ratio * 50)  # Partial credit

            except Exception as e:
                self.logger.error(f"Error in current_volume_score for {symbol}: {e}")
                scores['current_volume_score'] = 50  # Neutral score on error

            # 6. MOMENTUM SCORE (0-100)
            try:
                momentum_maintained = self._check_momentum_maintained(symbol, bar, gap_data)
                momentum_strength = self._calculate_momentum_strength(symbol, bar, gap_data)

                if momentum_maintained:
                    scores['momentum_score'] = min(100, 80 + (momentum_strength * 20))
                else:
                    scores['momentum_score'] = max(20, momentum_strength * 60)  # Partial credit

            except Exception as e:
                self.logger.error(f"Error in momentum_score for {symbol}: {e}")
                scores['momentum_score'] = 50  # Neutral score on error

            # 7. PRICE EXTENSION SCORE (0-100): Reward entries that aren't overextended
            try:
                not_extended = self._check_price_not_extended(symbol, bar, gap_data)
                extension_ratio = self._calculate_extension_ratio(symbol, bar, gap_data)

                if not_extended:
                    scores['extension_score'] = 100
                else:
                    # Give partial credit based on how extended (0.0 = not extended, 1.0 = very extended)
                    scores['extension_score'] = max(0, 100 - (extension_ratio * 100))

            except Exception as e:
                self.logger.error(f"Error in extension_score for {symbol}: {e}")
                scores['extension_score'] = 70  # Slightly positive score on error

            # Calculate total score and log details
            total_score = sum(scores.values())
            scores['total_score'] = total_score

            self.logger.info(f"🎯 {symbol} SCORING: Gap={scores['gap_size_score']:.0f} Vol={scores['volume_score']:.0f} "
                           f"Price={scores['price_range_score']:.0f} Mom={scores['momentum_score']:.0f} "
                           f"Ext={scores['extension_score']:.0f} -> TOTAL={total_score:.0f}")

            return scores

        except Exception as e:
            self.logger.error(f"Error evaluating scoring conditions for {symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace in scoring conditions: {traceback.format_exc()}")
            return {'total_score': 0}

    def _evaluate_gap_entry_conditions(self, symbol: str, bar: MarketData, gap_data: Dict) -> Dict[str, bool]:
        """LEGACY BINARY VERSION: Kept for compatibility - converts scoring to binary"""
        try:
            # Get flexible scoring
            scores = self._evaluate_gap_entry_conditions_scoring(symbol, bar, gap_data)

            # Convert scores to binary conditions for backward compatibility
            conditions = {
                'gap_size_ok': scores.get('gap_size_score', 0) >= 60,
                'volume_ok': scores.get('volume_score', 0) >= 60,
                'price_range_ok': scores.get('price_range_score', 0) >= 60,
                'direction_allowed': scores.get('direction_score', 0) >= 80,
                'current_volume_ok': scores.get('current_volume_score', 0) >= 50,
                'momentum_ok': scores.get('momentum_score', 0) >= 50,
                'price_not_extended': scores.get('extension_score', 0) >= 60
            }

            self.logger.debug(f"Binary conditions for {symbol}: {conditions}")
            return conditions

        except Exception as e:
            self.logger.error(f"Error evaluating entry conditions for {symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace in entry conditions: {traceback.format_exc()}")
            return {}
    
    def _create_first_candle(self, bar: MarketData, gap_data: Dict) -> Dict:
        """Create first candle data for breakout analysis"""
        return {
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'timestamp': bar.timestamp,
            'gap_data': gap_data
        }
    
    def _check_current_volume_strength(self, symbol: str, bar: MarketData) -> bool:
        """Check that current volume is still strong"""
        try:
            # Ensure bars_history is properly initialized
            self._ensure_bars_history_is_list(symbol)
            
            current_ratio = self._calculate_volume_ratio(symbol, bar)
            return current_ratio >= (self._parameters['volume_multiplier'] * 0.7)  # 70% of required ratio
            
        except Exception as e:
            self.logger.error(f"Error checking volume strength for {symbol}: {e}")
            import traceback
            self.logger.error(f"Stack trace in volume strength: {traceback.format_exc()}")
            return True
            
    def _check_momentum_maintained(self, symbol: str, current_bar: MarketData, gap_data: Dict) -> bool:
        """Check that price momentum is maintained in gap direction"""
        try:
            # Ensure bars_history is properly initialized
            self._ensure_bars_history_is_list(symbol)
                
            # Need at least 3 recent bars to check momentum
            if len(self.bars_history[symbol]) < 3:
                return True  # Not enough data to determine momentum loss
                
            # Get recent bars (last 3)
            recent_bars = self.bars_history[symbol][-3:]
            if not recent_bars or len(recent_bars) < 3:
                return True  # Not enough data
                
            # Check momentum based on gap direction
            if gap_data['direction'] == 'up':
                # For gap up: recent bars should show upward momentum
                recent_highs = [b.high for b in recent_bars]
                return recent_highs[-1] >= max(recent_highs[:-1])
            else:
                # For gap down: recent bars should show downward momentum
                recent_lows = [b.low for b in recent_bars]
                return recent_lows[-1] <= min(recent_lows[:-1])
                
        except Exception as e:
            self.logger.error(f"Error checking momentum for {symbol}: {e}")
            return True  # Default to True to avoid false exits
    
    def _check_price_not_extended(self, symbol: str, bar: MarketData, gap_data: Dict) -> bool:
        """Check that price is not too extended from gap open"""
        try:
            gap_open = gap_data['current_open']
            current_price = bar.close
            
            # Calculate extension from gap open
            extension_pct = abs((current_price - gap_open) / gap_open) * 100
            
            # Allow up to 5% extension from gap open
            max_extension = 5.0
            
            return extension_pct <= max_extension
            
        except Exception as e:
            self.logger.error(f"Error checking price extension for {symbol}: {e}")
            return True
    
    
    
    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for Gap & Go strategy with commission consideration"""
        try:
            symbol = signal.symbol
            price = signal.price
            
            # 1. Calculate base position size based on risk
            risk_amount = capital * min(risk_per_trade, self._parameters['max_risk_per_trade'])
            stop_distance = price * self._parameters['stop_loss_pct']
            
            # 2. Calculate minimum viable position size to cover commissions
            min_commission = self._parameters['min_commission']
            commission_per_share = self._parameters['commission_per_share']
            
            # Minimum position value to make trade viable after commissions
            min_position_value = max(
                self._parameters['min_position_value'],
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
            max_shares_value = int(self._parameters['max_position_value'] / price)
            
            # Max shares based on max risk per trade (5% of capital)
            max_shares_risk = int((capital * 0.05) / price)
            
            # Take the more restrictive limit
            max_shares = min(max_shares_value, max_shares_risk)
            
            # Apply limits
            quantity = min(base_quantity, max_shares)
            quantity = max(quantity, self._parameters['min_quantity'])
            
            # Calculate estimated commissions
            total_commission = (quantity * commission_per_share * 2) + (min_commission * 2)
            position_value = quantity * price
            commission_pct = (total_commission / position_value) * 100
            
            self.logger.info(
                f"Gap & Go position size for {symbol}: {quantity} shares @ {price:.2f} "
                f"(Value: ${position_value:,.2f}, Comm: ${total_commission:.2f} = {commission_pct:.2f}%)"
            )
            
            # Log warning if commission is too high relative to position size
            if commission_pct > 1.0:  # More than 1% in commissions
                self.logger.warning(
                    f"High commission impact ({commission_pct:.2f}%) for {symbol}. "
                    f"Consider increasing position size or finding lower commission options."
                )
            
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {symbol}: {e}")
            return self._parameters['min_quantity']
    
    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hour format in US/Eastern timezone"""
        try:
            import pytz

            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            else:
                dt = timestamp

            # Convert to US/Eastern timezone
            eastern = pytz.timezone('US/Eastern')
            dt_eastern = dt.astimezone(eastern) if dt.tzinfo else eastern.localize(dt)

            return dt_eastern.hour + dt_eastern.minute / 60.0

        except Exception as e:
            self.logger.error(f"Error converting timestamp: {e}")
            return 0.0
    
    def _is_trading_hours(self, time_decimal: float) -> bool:
        """Check if current time is within trading hours"""
        return (self._parameters['market_open_hour'] <= time_decimal <= 
                self._parameters['market_close_hour'])
    
    def _is_same_day(self, timestamp1, timestamp2) -> bool:
        """Check if two timestamps are on the same day"""
        try:
            if isinstance(timestamp1, (int, float)):
                dt1 = datetime.fromtimestamp(timestamp1)
            else:
                dt1 = timestamp1
                
            if isinstance(timestamp2, (int, float)):
                dt2 = datetime.fromtimestamp(timestamp2)
            else:
                dt2 = timestamp2
                
            return dt1.date() == dt2.date()
            
        except Exception as e:
            self.logger.error(f"Error comparing dates: {e}")
            return False

    def _calculate_momentum_strength(self, symbol: str, bar: MarketData, gap_data: Dict) -> float:
        """Calculate momentum strength for scoring (0.0 - 1.0)"""
        try:
            if len(self.bars_history[symbol]) < 3:
                return 0.5  # Neutral if insufficient data

            recent_bars = self.bars_history[symbol][-3:]

            # Check price momentum in gap direction
            if gap_data['direction'] == 'up':
                # For gap up, we want to see continued upward momentum
                price_momentum = (bar.close - recent_bars[0].close) / recent_bars[0].close
                volume_momentum = bar.volume / np.mean([b.volume for b in recent_bars])
            else:
                # For gap down, we want to see continued downward momentum
                price_momentum = (recent_bars[0].close - bar.close) / recent_bars[0].close
                volume_momentum = bar.volume / np.mean([b.volume for b in recent_bars])

            # Combine price and volume momentum
            momentum_score = min(1.0, (price_momentum * 2 + volume_momentum / 3) / 2)
            return max(0.0, momentum_score)

        except Exception as e:
            self.logger.error(f"Error calculating momentum strength for {symbol}: {e}")
            return 0.5

    def _calculate_extension_ratio(self, symbol: str, bar: MarketData, gap_data: Dict) -> float:
        """Calculate how extended price is from gap open (0.0 = not extended, 1.0 = very extended)"""
        try:
            gap_open = gap_data.get('gap_open', bar.open)
            current_price = bar.close

            if gap_data['direction'] == 'up':
                # For gap up, check how far we've moved above gap open
                extension = (current_price - gap_open) / gap_open
            else:
                # For gap down, check how far we've moved below gap open
                extension = (gap_open - current_price) / gap_open

            # Normalize: 0-5% extension = not extended, 15%+ = very extended
            extension_ratio = min(1.0, max(0.0, (extension - 0.05) / 0.10))
            return extension_ratio

        except Exception as e:
            self.logger.error(f"Error calculating extension ratio for {symbol}: {e}")
            return 0.3  # Slightly extended as default

    def _is_gap_expired(self, gap_data: Dict, current_timestamp) -> bool:
        """Check if gap detection has expired"""
        try:
            gap_time = gap_data['timestamp']
            
            if isinstance(current_timestamp, (int, float)):
                current_dt = datetime.fromtimestamp(current_timestamp)
            else:
                current_dt = current_timestamp
                
            if isinstance(gap_time, (int, float)):
                gap_dt = datetime.fromtimestamp(gap_time)
            else:
                gap_dt = gap_time
            
            time_diff = (current_dt - gap_dt).total_seconds() / 60  # Minutes
            
            return time_diff > self._parameters['gap_timeout_minutes']
            
        except Exception as e:
            self.logger.error(f"Error checking gap expiration: {e}")
            return True
    
    def _cleanup_position_tracking(self, symbol: str):
        """Clean up our tracking when position exits"""
        if symbol in self.entry_signals:
            del self.entry_signals[symbol]
        
        # Note: No need to cleanup stop loss tracking - that's handled by the manager
    
    def get_strategy_info(self) -> dict:
        """Get strategy-specific information"""
        return {
            "name": self.name,
            "type": "Gap & Go Intraday",
            "timeframe": "Intraday (Small Caps)",
            "parameters": self.parameters,
            "active_gaps": len(self.gap_info),
            "active_signals": len(self.entry_signals),
            "performance": self.get_performance_stats()
        }
    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        # For GapGo strategy, we don't need special logic on position updates
        return None
    
    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """SMALLCAP-OPTIMIZED exit with FOMO detection + centralized stop_manager"""
        try:
            # PRIORITY 1: Check FOMO exit first (overrides traditional exits)
            fomo_analysis = self.check_fomo_exit(position.symbol, position, current_bar)
            if fomo_analysis and fomo_analysis.get('should_exit', False):
                fomo_signal = fomo_analysis.get('fomo_signal')

                return Signal(
                    signal_id=f"fomo_exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                    symbol=position.symbol,
                    signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                    strength=fomo_signal.confidence,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    strategy_name="GapGo_Smallcaps_Optimized",
                    metadata={
                        'reason': 'fomo_top_detection',
                        'fomo_score': fomo_signal.fomo_score,
                        'urgency': fomo_signal.exit_urgency,
                        'fomo_reasons': fomo_signal.fomo_reasons,
                        'entry_price': position.avg_price,
                        'exit_type': 'FOMO_EXIT_PRIORITY'
                    }
                )

            # PRIORITY 2: SMALLCAP-OPTIMIZED centralized stop_manager (replaces basic stop loss)
            if hasattr(self, 'stop_manager') and self.stop_manager:
                exit_signal = self.stop_manager.check_exit_conditions(
                    symbol=position.symbol,
                    current_bar=current_bar
                )

                if exit_signal:
                    return Signal(
                        signal_id=f"exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="GapGo_Smallcaps_Optimized",
                        metadata={
                            'reason': exit_signal.get('reason', 'stop_manager'),
                            'exit_type': exit_signal.get('exit_reason', 'advanced_stop'),
                            'entry_price': position.avg_price,
                            'pnl_pct': exit_signal.get('pnl_pct', 0),
                            'smallcap_features': 'EMA_trailing,time_exits,volatility_filter'
                        }
                    )

            # FALLBACK: Log warning if no stop_manager available
            else:
                self.logger.warning(f"⚠️ {position.symbol}: No stop_manager available for advanced exits!")

            return None

        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None

    # =============================================
    # ENHANCED PMH GAP&GO STRATEGY FUNCTIONS (NEW)
    # =============================================

    # REMOVED: _detect_premarket_high - now using centralized PMH from SmallcapTickerContext

    def _should_enter_gap_go_with_pmh_context(self, symbol: str, bar: MarketData, pmh_resistance: float) -> bool:
        """
        Enhanced Gap_Go entry logic using centralized PMH context

        Key insight: PMH <80% = more room to run = better for Gap_Go
        """
        try:
            # Basic gap and volume requirements
            if not self._check_gap_and_volume_requirements(symbol, bar):
                return False

            # PMH Quality Scoring (your insight implemented)
            pmh_score = 0
            if pmh_resistance < 0.3:  # <50% PMH gain = excellent room to run
                pmh_score = 3  # High confidence
                self.logger.info(f"🚀 {symbol}: Excellent PMH room to run ({pmh_resistance:.2f})")
            elif pmh_resistance < 0.7:  # 50-80% PMH gain = good room
                pmh_score = 2  # Medium confidence
                self.logger.info(f"📈 {symbol}: Good PMH room to run ({pmh_resistance:.2f})")
            else:  # >80% PMH gain = limited room
                pmh_score = 0  # Low confidence
                self.logger.info(f"⚠️ {symbol}: Limited PMH room to run ({pmh_resistance:.2f})")

            # Time of day scoring (Gap_Go works best morning to midday)
            current_time = self._get_time_from_timestamp(bar.timestamp)
            time_score = 0
            if 9.5 <= current_time <= 12.0:  # Prime Gap_Go hours
                time_score = 2
            elif 12.0 < current_time <= 14.0:  # Still good
                time_score = 1
            else:  # Too late/early
                time_score = 0

            total_score = pmh_score + time_score
            min_score = 3  # Need at least 3 points to enter

            self.logger.info(f"🎯 {symbol}: Gap_Go score = {total_score} (PMH: {pmh_score}, Time: {time_score})")

            return total_score >= min_score

        except Exception as e:
            self.logger.error(f"Error in Gap_Go PMH context check for {symbol}: {e}")
            return False

    def _generate_enhanced_gap_go_signal(self, symbol: str, bar: MarketData, pmh_resistance: float) -> Optional[Signal]:
        """
        Generate Gap_Go signal with PMH context enhancement
        """
        try:
            # Enhanced confidence based on PMH room to run
            confidence_base = 0.75
            if pmh_resistance < 0.3:  # Excellent room
                confidence = min(0.95, confidence_base + 0.20)
            elif pmh_resistance < 0.7:  # Good room
                confidence = min(0.90, confidence_base + 0.10)
            else:  # Limited room
                confidence = confidence_base

            signal_id = f"enhanced_gap_go_{symbol}_{int(bar.timestamp.timestamp())}"

            signal = Signal(
                timestamp=bar.timestamp,
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=confidence,
                price=bar.close,
                signal_id=signal_id,
                strategy_name=self.strategy_id,
                metadata={
                    'gap_percent': self.gap_info[symbol]['gap_percent'],
                    'pmh_resistance_strength': pmh_resistance,
                    'pmh_room_to_run': 1.0 - pmh_resistance,  # Higher = more room
                    'entry_reason': 'ENHANCED_GAP_GO_WITH_PMH_CONTEXT',
                    'expected_timeframe': 'MORNING_TO_MIDDAY'
                }
            )

            self.logger.info(f"🚀 {symbol}: Enhanced Gap_Go signal generated - "
                           f"confidence: {confidence:.2f}, PMH room: {(1.0-pmh_resistance)*100:.0f}%")

            # Register position with centralized stop_loss_manager
            self._register_position_with_stop_manager(symbol, bar, signal)

            return signal

        except Exception as e:
            self.logger.error(f"Error generating enhanced Gap_Go signal for {symbol}: {e}")
            return None

    def _check_gap_and_volume_requirements(self, symbol: str, bar: MarketData) -> bool:
        """
        Check basic gap and volume requirements for Gap_Go entry
        """
        try:
            # Check if we have gap data
            if symbol not in self.gap_info:
                return False

            gap_data = self.gap_info[symbol]
            gap_percent = abs(gap_data['gap_percent'])

            # Gap size requirement
            min_gap = self._parameters.get('min_gap_percent', 15.0)
            if gap_percent < min_gap:
                self.logger.debug(f"{symbol}: Gap {gap_percent:.1f}% < {min_gap}%")
                return False

            # Volume requirement
            avg_volume = getattr(bar, 'avg_volume', 0)
            if avg_volume > 0:
                volume_ratio = bar.volume / avg_volume
                min_volume_ratio = self._parameters.get('volume_multiplier', 2.0)
                if volume_ratio < min_volume_ratio:
                    self.logger.debug(f"{symbol}: Volume ratio {volume_ratio:.1f}x < {min_volume_ratio}x")
                    return False

            # Gap not expired
            if self._is_gap_expired(gap_data, bar.timestamp):
                self.logger.debug(f"{symbol}: Gap expired")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking gap/volume requirements for {symbol}: {e}")
            return False

    # DEPRECATED: Old PMH methods - replaced by centralized PMH context
    def _detect_pmh_consolidation(self, symbol: str, current_bar: MarketData) -> bool:
        """
        DEPRECATED: Detect consolidation below PMH - key for entry timing
        Now using centralized PMH resistance strength from SmallcapTickerContext
        """
        try:
            if symbol not in self.pmh_data:
                return False

            pmh_price = self.pmh_data[symbol]['pmh_price']
            current_price = current_bar.close

            # Must be below PMH for consolidation
            if current_price >= pmh_price:
                return False

            # Look for consolidation in recent bars
            recent_bars = self.bars_history[symbol][-self._parameters.get('pmh_consolidation_period', 15):]

            if len(recent_bars) < 5:
                return False

            # Analyze price action for consolidation
            highs = [bar.high for bar in recent_bars]
            lows = [bar.low for bar in recent_bars]

            # Consolidation criteria
            range_size = (max(highs) - min(lows)) / min(lows)
            avg_high = sum(highs) / len(highs)
            avg_low = sum(lows) / len(lows)

            # Must be consolidating below PMH with tight range
            consolidation_below_pmh = avg_high < pmh_price * 0.98  # 2% below PMH
            tight_range = range_size < 0.05  # 5% max range

            if consolidation_below_pmh and tight_range:
                # Find support level
                support_level = min(lows)
                tolerance = self._parameters.get('pmh_support_tolerance', 0.02)

                # Support should be within tolerance
                if abs(current_price - support_level) / support_level <= tolerance:
                    self.consolidation_data[symbol] = {
                        'support_level': support_level,
                        'consolidation_range': range_size,
                        'bars_in_consolidation': len(recent_bars),
                        'avg_volume': sum(bar.volume for bar in recent_bars) / len(recent_bars)
                    }

                    self.logger.debug(f"📊 {symbol}: Consolidation detected below PMH, "
                                    f"support: ${support_level:.2f}, range: {range_size:.1%}")

                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error detecting consolidation for {symbol}: {e}")
            return False

    def _detect_pmh_breakout(self, symbol: str, current_bar: MarketData) -> Optional[Dict]:
        """
        Detect PMH breakout with volume confirmation

        Returns:
            Breakout data dict or None if no valid breakout
        """
        try:
            if symbol not in self.pmh_data:
                return None

            pmh_price = self.pmh_data[symbol]['pmh_price']
            current_price = current_bar.close
            current_volume = current_bar.volume

            # Must break above PMH
            if current_price <= pmh_price:
                return None

            # Check for volume confirmation
            if symbol in self.consolidation_data:
                avg_consolidation_volume = self.consolidation_data[symbol]['avg_volume']
                volume_multiplier = self._parameters.get('breakout_volume_multiplier', 1.5)

                if current_volume >= avg_consolidation_volume * volume_multiplier:
                    breakout_data = {
                        'breakout_price': current_price,
                        'breakout_time': current_bar.timestamp,
                        'breakout_volume': current_volume,
                        'pmh_price': pmh_price,
                        'volume_multiplier': current_volume / avg_consolidation_volume,
                        'breakout_percentage': (current_price - pmh_price) / pmh_price
                    }

                    # Store breakout data
                    self.breakout_data[symbol] = breakout_data

                    self.logger.info(f"🚀 {symbol}: PMH BREAKOUT! Price: ${current_price:.2f}, "
                                   f"PMH: ${pmh_price:.2f}, Volume: {current_volume/avg_consolidation_volume:.1f}x")

                    return breakout_data

            return None

        except Exception as e:
            self.logger.error(f"Error detecting PMH breakout for {symbol}: {e}")
            return None

    def _check_spike_confirmation(self, symbol: str, current_bar: MarketData) -> bool:
        """
        Check for 5%+ spike above PMH breakout (confirmation requirement)

        Returns:
            True if spike confirmation met
        """
        try:
            if symbol not in self.breakout_data:
                return False

            breakout_price = self.breakout_data[symbol]['breakout_price']
            current_price = current_bar.close

            spike_percentage = (current_price - breakout_price) / breakout_price
            required_spike = self._parameters.get('pmh_breakout_confirmation', 0.05)  # 5%

            if spike_percentage >= required_spike:
                self.spike_confirmations[symbol] = {
                    'spike_price': current_price,
                    'spike_percentage': spike_percentage,
                    'confirmed_time': current_bar.timestamp
                }

                self.logger.info(f"⚡ {symbol}: SPIKE CONFIRMED! {spike_percentage:.1%} above breakout")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking spike confirmation for {symbol}: {e}")
            return False

    def _check_dip_entry_opportunity(self, symbol: str, current_bar: MarketData) -> bool:
        """
        Check for dip back to PMH level with lower volume (ideal entry)

        Returns:
            True if dip entry opportunity exists
        """
        try:
            if symbol not in self.pmh_data or symbol not in self.spike_confirmations:
                return False

            pmh_price = self.pmh_data[symbol]['pmh_price']
            current_price = current_bar.close
            current_volume = current_bar.volume

            # Check if price has dipped back near PMH level
            distance_from_pmh = abs(current_price - pmh_price) / pmh_price
            pmh_tolerance = 0.02  # 2% tolerance for PMH level

            if distance_from_pmh <= pmh_tolerance:
                # Check if volume is lower than breakout volume
                if symbol in self.breakout_data:
                    breakout_volume = self.breakout_data[symbol]['breakout_volume']
                    dip_volume_ratio = self._parameters.get('dip_volume_ratio', 0.7)

                    if current_volume <= breakout_volume * dip_volume_ratio:
                        self.dip_tracking[symbol] = {
                            'dip_price': current_price,
                            'dip_volume': current_volume,
                            'volume_ratio': current_volume / breakout_volume,
                            'dip_time': current_bar.timestamp
                        }

                        self.logger.info(f"📉 {symbol}: DIP ENTRY OPPORTUNITY! "
                                       f"Price: ${current_price:.2f} near PMH: ${pmh_price:.2f}, "
                                       f"Volume: {current_volume/breakout_volume:.1%} of breakout")

                        return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking dip entry for {symbol}: {e}")
            return False

    def _detect_stuffed_move(self, symbol: str, current_bar: MarketData) -> bool:
        """
        Detect 'stuffed move' - violent rejection below PMH (failure scenario)

        Returns:
            True if stuffed move detected (immediate exit signal)
        """
        try:
            if symbol not in self.pmh_data or symbol not in self.breakout_data:
                return False

            pmh_price = self.pmh_data[symbol]['pmh_price']
            current_price = current_bar.close
            current_volume = current_bar.volume
            breakout_volume = self.breakout_data[symbol]['breakout_volume']

            # Must close below PMH
            if current_price >= pmh_price:
                return False

            # Volume must be higher than breakout volume
            volume_ratio = self._parameters.get('stuffed_move_volume_ratio', 1.2)

            if current_volume >= breakout_volume * volume_ratio:
                self.stuffed_moves[symbol] = {
                    'stuffed_price': current_price,
                    'stuffed_volume': current_volume,
                    'rejection_strength': current_volume / breakout_volume,
                    'stuffed_time': current_bar.timestamp
                }

                self.logger.warning(f"🚨 {symbol}: STUFFED MOVE DETECTED! "
                                  f"Price: ${current_price:.2f} below PMH: ${pmh_price:.2f}, "
                                  f"Volume: {current_volume/breakout_volume:.1f}x breakout")

                return True

            return False

        except Exception as e:
            self.logger.error(f"Error detecting stuffed move for {symbol}: {e}")
            return False

    def _should_enter_pmh_strategy(self, symbol: str, bar: MarketData, conditions: Dict) -> bool:
        """
        Determine if PMH strategy entry conditions are met

        Args:
            symbol: Stock symbol
            bar: Current market data
            conditions: Dict with PMH analysis results

        Returns:
            True if all PMH strategy entry conditions are satisfied
        """
        try:
            # Check required conditions based on strategy parameters
            required_conditions = []

            # 1. PMH must be detected
            if self._parameters.get('require_pmh_breakout', True):
                required_conditions.append(('PMH Detected', conditions['pmh_detected']))

            # 2. Breakout must have occurred
            if self._parameters.get('require_pmh_breakout', True):
                required_conditions.append(('PMH Breakout', conditions['breakout']))

            # 3. Spike confirmation required (5%+ above PMH)
            if self._parameters.get('require_spike_confirmation', True):
                required_conditions.append(('Spike Confirmation', conditions['spike_confirmed']))

            # 4. Dip entry opportunity (optimal entry point)
            if self._parameters.get('require_dip_entry', True):
                required_conditions.append(('Dip Entry', conditions['dip_entry']))

            # 5. Consolidation (if required)
            if self._parameters.get('require_consolidation', True):
                # Allow entry if consolidation was detected OR if we're in a dip entry
                consolidation_ok = conditions['consolidation'] or conditions['dip_entry']
                required_conditions.append(('Consolidation/Dip', consolidation_ok))

            # Check if all required conditions are met
            passed_conditions = [name for name, condition in required_conditions if condition]
            failed_conditions = [name for name, condition in required_conditions if not condition]

            if not failed_conditions:
                self.logger.info(f"🎯 {symbol}: PMH STRATEGY ENTRY CONDITIONS MET!")
                self.logger.info(f"   ✅ Passed: {', '.join(passed_conditions)}")
                return True
            else:
                self.logger.debug(f"⏳ {symbol}: PMH strategy conditions - "
                                f"Passed: {len(passed_conditions)}/{len(required_conditions)}")
                self.logger.debug(f"   ✅ Met: {', '.join(passed_conditions) if passed_conditions else 'None'}")
                self.logger.debug(f"   ❌ Missing: {', '.join(failed_conditions)}")
                return False

        except Exception as e:
            self.logger.error(f"Error checking PMH strategy conditions for {symbol}: {e}")
            return False

    def _generate_pmh_entry_signal(self, symbol: str, bar: MarketData) -> Optional[Signal]:
        """
        Generate PMH strategy entry signal with enhanced metadata

        Returns:
            Signal object for PMH Gap&Go entry
        """
        try:
            # Create comprehensive signal with PMH strategy metadata
            signal_id = f"pmh_gap_go_{symbol}_{int(bar.timestamp.timestamp())}"

            # Gather all PMH-related data for signal metadata
            pmh_data = self.pmh_data.get(symbol, {})
            breakout_data = self.breakout_data.get(symbol, {})
            spike_data = self.spike_confirmations.get(symbol, {})
            dip_data = self.dip_tracking.get(symbol, {})

            # Enhanced metadata for PMH strategy
            metadata = {
                'strategy': 'PMH_GAP_GO',
                'entry_type': 'PMH_DIP_ENTRY',
                'gap_percent': self.gap_info[symbol]['gap_percent'],
                'pmh_price': pmh_data.get('pmh_price', 0),
                'breakout_price': breakout_data.get('breakout_price', 0),
                'spike_confirmation': spike_data.get('spike_percentage', 0),
                'entry_near_pmh': True,
                'volume_multiplier': breakout_data.get('volume_multiplier', 0),
                'dip_volume_ratio': dip_data.get('volume_ratio', 0),
                'strategy_confidence': self._calculate_pmh_confidence(symbol),
                'risk_level': 'MODERATE',  # PMH strategy is moderate risk
                'expected_target': self._parameters.get('profit_target', 0.25),
                'stop_loss_ref': 'PMH_LEVEL'  # Use PMH as stop reference
            }

            # Create the signal
            signal = Signal(
                signal_id=signal_id,
                symbol=symbol,
                signal_type=SignalType.LONG,  # PMH strategy is long-only
                strength=metadata['strategy_confidence'],
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name="GapGo",
                metadata=metadata
            )

            # Register with stop loss manager using PMH-based stop
            if self._parameters.get('pmh_stop_loss', True):
                stop_price = pmh_data.get('pmh_price', bar.close * 0.94)  # PMH or 6% fallback
            else:
                stop_price = bar.close * (1 - self._parameters.get('stop_loss_pct', 0.05))  # Uses config.ini fallback_stop_loss_pct

            stop_params = create_stop_params_from_config(
                symbol=symbol,
                entry_price=bar.close,
                entry_time=bar.timestamp,
                side='LONG',
                strategy_name="GapGo",
                stop_params={
                    'stop_loss_price': stop_price,
                    'profit_target_pct': self._parameters.get('profit_target', 0.25),
                    'trailing_stop_activation_pct': self._parameters.get('trailing_stop_activation', 0.10),
                    'trailing_stop_distance_pct': self._parameters.get('trailing_stop_distance', 0.05)
                }
            )

            # Clean up tracking data to prevent duplicate signals
            self._cleanup_position_tracking(symbol)
            self._record_signal_time(symbol, bar.timestamp)

            self.logger.info(f"🚀 {symbol}: PMH GAP&GO ENTRY SIGNAL generated at ${bar.close:.2f}")
            self.logger.info(f"   📊 Gap: {metadata['gap_percent']:.1f}%, "
                           f"PMH: ${metadata['pmh_price']:.2f}, "
                           f"Confidence: {metadata['strategy_confidence']:.1%}")

            return signal

        except Exception as e:
            self.logger.error(f"Error generating PMH entry signal for {symbol}: {e}")
            return None

    def _calculate_pmh_confidence(self, symbol: str) -> float:
        """
        Calculate confidence score for PMH strategy entry (0.0 - 1.0)

        Returns:
            Confidence score based on PMH analysis quality
        """
        try:
            confidence = 0.0

            # Base confidence for having PMH data
            if symbol in self.pmh_data:
                confidence += 0.3

            # Bonus for strong breakout
            if symbol in self.breakout_data:
                volume_mult = self.breakout_data[symbol].get('volume_multiplier', 1.0)
                confidence += min(volume_mult * 0.1, 0.2)  # Up to +0.2 for volume

            # Bonus for spike confirmation
            if symbol in self.spike_confirmations:
                spike_pct = self.spike_confirmations[symbol].get('spike_percentage', 0)
                confidence += min(spike_pct * 2, 0.2)  # Up to +0.2 for spike

            # Bonus for good dip entry timing
            if symbol in self.dip_tracking:
                volume_ratio = self.dip_tracking[symbol].get('volume_ratio', 1.0)
                if volume_ratio <= 0.7:  # Low volume on dip is good
                    confidence += 0.2

            # Bonus for consolidation pattern
            if symbol in self.consolidation_data:
                range_size = self.consolidation_data[symbol].get('consolidation_range', 0.1)
                if range_size <= 0.05:  # Tight consolidation is good
                    confidence += 0.1

            return min(confidence, 1.0)  # Cap at 1.0

        except Exception as e:
            self.logger.error(f"Error calculating PMH confidence for {symbol}: {e}")
            return 0.5  # Default moderate confidence

    def _generate_exit_signal(self, symbol: str, bar: MarketData, exit_reason: str) -> Optional[Signal]:
        """
        Generate exit signal for failure scenarios (like stuffed moves)

        Returns:
            Exit signal or None if error
        """
        try:
            signal_id = f"exit_{symbol}_{int(bar.timestamp.timestamp())}"

            signal = Signal(
                signal_id=signal_id,
                symbol=symbol,
                signal_type=SignalType.EXIT_LONG,
                strength=1.0,  # Max strength for failure exit
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name="GapGo",
                metadata={
                    'reason': exit_reason,
                    'exit_type': 'FAILURE_EXIT',
                    'strategy': 'PMH_GAP_GO'
                }
            )

            self.logger.warning(f"🚨 {symbol}: EXIT SIGNAL - {exit_reason} at ${bar.close:.2f}")
            return signal

        except Exception as e:
            self.logger.error(f"Error generating exit signal for {symbol}: {e}")
            return None

    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS: Use global config.ini parameters optimized for smallcaps
        # These parameters are centralized in config.ini:
        # - fallback_stop_loss_pct = 0.06 (6% for volatility)
        # - enable_dynamic_ema_trailing = true
        # - ema_trailing_periods = 5 (faster response)
        # - max_hold_minutes = 180 (3 hours max)
        stop_params = create_stop_params_from_config(self._parameters)

        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.LONG else 'bearish'

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="GapGo_Smallcaps_Optimized",
            stop_params=stop_params
        )

        self.logger.info(f"📊 {symbol}: GAP_GO SMALLCAP-OPTIMIZED - "
                        f"6% stop, EMA-5 trailing, FOMO detection, 3h max hold")
