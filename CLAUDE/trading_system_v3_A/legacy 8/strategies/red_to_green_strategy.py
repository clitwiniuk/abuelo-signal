# strategies/red_to_green_strategy.py
"""
Red to Green Strategy: Aprovecha short squeeze cuando precio rompe niveles clave

La estrategia Red to Green identifica y opera rupturas de niveles de soporte/resistencia
clave (open del día o close anterior) con confirmación de volumen, capitalizando el
short squeeze resultante.
"""

from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from .base import BaseStrategy
from core.interfaces import Signal, MarketData, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config


class RedToGreenStrategy(BaseStrategy):
    """
    Red to Green Strategy implementation for small cap trading.

    Entry Conditions:
    1. Previous green candle with volume (establece expectativa alcista)
    2. Red sequence breaking key levels (atrae shorts)
    3. Consolidation with declining volume (presión vendedora se agota)
    4. Convincing breakout (5%+) above R2G level with volume
    5. Optional: Entry on dip back to R2G level with lower volume

    Exit Conditions:
    1. Profit targets at next resistance levels
    2. Stop loss below R2G level
    3. Volume exhaustion signals
    4. Gap fill protection
    5. End of day management
    """

    def __init__(self, parameters: Dict[str, Any] = None):
        # RED TO GREEN STRATEGY DEFAULTS - RELAXED FOR EASIER ENTRIES
        fallback_defaults = {
            # R2G Entry Parameters - RELAXED
            'min_r2g_breakout_percent': 2.0,        # RELAXED: Reduced from 5% to 2% for easier breakouts
            'entry_on_dip_enabled': False,          # RELAXED: Immediate entry instead of waiting for dip
            'max_dip_below_r2g': 3.0,               # RELAXED: Increased from 2% to 3%
            'dip_volume_threshold': 0.8,            # RELAXED: Increased from 0.7 to 0.8

            # Volume Confirmation - RELAXED
            'breakout_volume_multiplier': 1.1,      # RELAXED: Reduced from 1.5 to 1.1
            'volume_vs_green_candle': 0.8,          # RELAXED: Reduced from 1.0 to 0.8
            'volume_vs_red_candle': 0.8,            # RELAXED: Reduced from 1.0 to 0.8

            # Risk Management
            'stop_loss_below_r2g': 0.06,            # RELAXED: Increased from 3% to 6% for more room
            'use_recent_low_stop': True,            # Use recent low as stop reference
            'profit_target_1': 0.06,                # RELAXED: Reduced from 8% to 6% for quicker exits
            'profit_target_2': 0.12,                # RELAXED: Reduced from 15% to 12%
            'partial_exit_pct': 0.5,                # Exit 50% at first target

            # Time Management - RELAXED
            'optimal_entry_start': 9.5,             # 9:30 AM start
            'optimal_entry_end': 15.5,              # RELAXED: Extended from 12:00 to 15:30 PM
            'no_entry_after_hour': 15.5,            # RELAXED: Extended from 14:00 to 15:30 PM
            'mandatory_exit_hour': 16.0,            # RELAXED: Extended to market close

            # Position Sizing
            'max_position_value': 300.0,
            'min_position_value': 50.0,
            'min_quantity': 10,
            'max_risk_per_trade': 0.02,             # 2% max risk per trade
            'commission_per_share': 0.01,
            'min_commission': 1.0,

            # Price Filters - RELAXED
            'min_price': 0.5,                       # RELAXED: Reduced from 1.0 to 0.5
            'max_price': 30.0,                      # RELAXED: Increased from 20.0 to 30.0

            # Quality Filters - RELAXED
            'min_daily_volume': 30000,              # RELAXED: Reduced from 100k to 30k (same as MACDV)
            'max_spread_pct': 0.08,                 # RELAXED: Increased from 0.05 to 0.08
            'min_float': 500000,                    # RELAXED: Reduced from 1M to 500k
            'max_float': 200000000,                 # RELAXED: Increased from 100M to 200M

            # R2G Pattern Validation - RELAXED
            'require_previous_green': False,         # RELAXED: Made optional
            'require_red_sequence': False,          # RELAXED: Made optional
            'require_consolidation': False,         # RELAXED: Made optional
            'min_setup_age_minutes': 5,            # RELAXED: Reduced from 30 to 5 minutes
            'max_setup_age_hours': 72,             # RELAXED: Increased from 48 to 72 hours
        }

        # Initialize with fallback defaults first to get logger
        super().__init__("RedToGreen", fallback_defaults)

        # Now load config from config.ini and update parameters
        try:
            config_params = self._load_strategy_config('RED_TO_GREEN_STRATEGY', fallback_defaults)

            # Los parámetros pasados al constructor tienen la máxima prioridad
            if parameters:
                config_params.update(parameters)

            # Update the parameters
            self._parameters = config_params
        except Exception as e:
            self.logger.error(f"Error loading config for Red to Green strategy: {e}")
            # Keep fallback defaults

        # Log received parameters after logger is initialized
        if parameters:
            self.logger.info(f"🔴➡️🟢 RedToGreen received parameters: {parameters}")

        # Get centralized stop loss manager
        self.stop_manager = get_stop_loss_manager()

        # Strategy state - R2G specific tracking
        self.r2g_setups = {}               # Store R2G setup data per symbol
        self.breakout_tracking = {}        # Track breakout confirmations
        self.entry_signals = {}            # Store entry signal data
        self.dip_opportunities = {}        # Track dip entry opportunities

        # Add tracking for signal prevention
        self.last_signal_times = {}        # Track last signal time per symbol
        self.signal_cooldown_minutes = 10  # Minimum time between signals (longer for R2G)

        self.logger.info("🔴➡️🟢 Red to Green Strategy initialized with centralized stop loss management")

    async def _initialize_strategy(self) -> None:
        """Initialize Red to Green strategy"""
        self.logger.info("Initializing Red to Green strategy")
        self.logger.info(f"Parameters: {self.parameters}")

        # Validate time parameters
        if self._parameters['optimal_entry_start'] >= self._parameters['optimal_entry_end']:
            self.logger.warning("optimal_entry_end should be after optimal_entry_start")

    async def _analyze_bar(self, bar: MarketData, context: Optional[Any] = None) -> Optional[Signal]:
        """Analyze bar and generate Red to Green signal"""
        symbol = bar.symbol

        try:
            self.logger.debug(f"[{symbol}] R2G _analyze_bar called - price: ${bar.close:.2f}, volume: {bar.volume:,}")

            # Ensure strategy state is properly initialized
            self._ensure_strategy_dicts_initialized()

            # First, check exit conditions for existing position
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

            current_time = self._get_time_from_timestamp(bar.timestamp)
            self.logger.debug(f"[{symbol}] Current time: {current_time:.2f}")

            # Check if we're in trading hours
            if not self._is_trading_hours(current_time):
                self.logger.debug(f"[{symbol}] Outside trading hours: {current_time:.2f}")
                return None

            # Check if it's too late for new entries
            if current_time >= self._parameters['no_entry_after_hour']:
                self.logger.debug(f"[{symbol}] Too late for entries: {current_time:.2f} >= {self._parameters['no_entry_after_hour']}")
                return None

            # ===================================================
            # RED TO GREEN STRATEGY LOGIC
            # ===================================================

            # STEP 1: Check if symbol has R2G setup from scanner
            self.logger.debug(f"[{symbol}] Checking R2G setup...")
            if not self._has_r2g_setup(symbol, context):
                self.logger.debug(f"[{symbol}] No R2G setup found")
                return None

            self.logger.debug(f"[{symbol}] R2G setup confirmed - proceeding to validation")

            # STEP 2: Validate current R2G setup is still valid
            if not self._validate_current_r2g_setup(symbol, bar):
                return None

            # STEP 3: Detect R2G breakout
            breakout_signal = self._detect_r2g_breakout(symbol, bar)
            if breakout_signal:
                # Check if we should enter immediately or wait for dip
                if self._parameters['entry_on_dip_enabled']:
                    # Store breakout for dip tracking
                    self.breakout_tracking[symbol] = breakout_signal
                    self.logger.info(f"🔴➡️🟢 {symbol}: R2G breakout detected, waiting for dip entry")
                    return None
                else:
                    # Immediate entry on breakout
                    return self._generate_r2g_entry_signal(symbol, bar, breakout_signal, "BREAKOUT")

            # STEP 4: Check for dip entry opportunity
            if symbol in self.breakout_tracking:
                dip_entry = self._check_dip_entry_opportunity(symbol, bar)
                if dip_entry:
                    return self._generate_r2g_entry_signal(symbol, bar, dip_entry, "DIP")

            return None

        except Exception as e:
            self.logger.error(f"Error analyzing bar for {symbol}: {e}")
            import traceback
            self.logger.error(f"Full stack trace: {traceback.format_exc()}")
            return None

    def _ensure_strategy_dicts_initialized(self) -> None:
        """Ensure all strategy state dictionaries are properly initialized"""
        # Fix r2g_setups
        if not hasattr(self, 'r2g_setups') or not isinstance(self.r2g_setups, dict):
            self.logger.warning(f"FIXING r2g_setups: was {type(getattr(self, 'r2g_setups', 'missing'))}, resetting to dict")
            self.r2g_setups = {}

        # Fix breakout_tracking
        if not hasattr(self, 'breakout_tracking') or not isinstance(self.breakout_tracking, dict):
            self.logger.warning(f"FIXING breakout_tracking: was {type(getattr(self, 'breakout_tracking', 'missing'))}, resetting to dict")
            self.breakout_tracking = {}

        # Fix entry_signals
        if not hasattr(self, 'entry_signals') or not isinstance(self.entry_signals, dict):
            self.logger.warning(f"FIXING entry_signals: was {type(getattr(self, 'entry_signals', 'missing'))}, resetting to dict")
            self.entry_signals = {}

        # Fix dip_opportunities
        if not hasattr(self, 'dip_opportunities') or not isinstance(self.dip_opportunities, dict):
            self.logger.warning(f"FIXING dip_opportunities: was {type(getattr(self, 'dip_opportunities', 'missing'))}, resetting to dict")
            self.dip_opportunities = {}

        # Fix last_signal_times
        if not hasattr(self, 'last_signal_times') or not isinstance(self.last_signal_times, dict):
            self.logger.warning(f"FIXING last_signal_times: was {type(getattr(self, 'last_signal_times', 'missing'))}, resetting to dict")
            self.last_signal_times = {}

    def _has_r2g_setup(self, symbol: str, context: Optional[Any] = None) -> bool:
        """Check if symbol has R2G setup from scanner or context - RELAXED VERSION"""
        # Check if we have R2G setup data from scanner
        if symbol in self.r2g_setups:
            return True

        # Check if context indicates R2G opportunity
        if context and hasattr(context, 'opportunity_type'):
            if context.opportunity_type == 'red_to_green':
                # Store R2G setup from context
                self.r2g_setups[symbol] = {
                    'r2g_level': getattr(context, 'r2g_breakout_level', 0),
                    'target_1': getattr(context, 'target_1', 0),
                    'target_2': getattr(context, 'target_2', 0),
                    'stop_loss': getattr(context, 'stop_loss', 0),
                    'score': getattr(context, 'r2g_score', 0),
                    'volume_ratio': getattr(context, 'volume_ratio', 0),
                    'setup_time': datetime.now()
                }
                return True

        # RELAXED: Create synthetic R2G setup from current price action if conditions are relaxed
        self.logger.debug(f"[{symbol}] Checking relaxed conditions: green={self._parameters['require_previous_green']}, red={self._parameters['require_red_sequence']}, consol={self._parameters['require_consolidation']}")

        if (not self._parameters['require_previous_green'] and
            not self._parameters['require_red_sequence'] and
            not self._parameters['require_consolidation']):

            # Auto-generate R2G setup based on recent price action
            bars = self.bars_history.get(symbol, [])
            self.logger.debug(f"[{symbol}] Creating synthetic R2G setup - bars available: {len(bars)}")

            if len(bars) >= 5:  # Need at least 5 bars for basic analysis
                current_price = bars[-1].close
                recent_low = min(bar.low for bar in bars[-10:]) if len(bars) >= 10 else current_price * 0.95
                recent_high = max(bar.high for bar in bars[-10:]) if len(bars) >= 10 else current_price * 1.05

                # Use recent low as R2G level (support level)
                r2g_level = recent_low

                self.r2g_setups[symbol] = {
                    'r2g_level': r2g_level,
                    'target_1': r2g_level * (1 + self._parameters['profit_target_1']),
                    'target_2': r2g_level * (1 + self._parameters['profit_target_2']),
                    'stop_loss': r2g_level * (1 - self._parameters['stop_loss_below_r2g']),
                    'score': 60,  # Medium confidence for synthetic setup
                    'volume_ratio': 1.0,
                    'setup_time': datetime.now()
                }

                self.logger.info(f"🔴➡️🟢 {symbol}: Auto-generated R2G setup - Level: ${r2g_level:.2f}")
                return True
            else:
                self.logger.debug(f"[{symbol}] Not enough bars for synthetic setup: {len(bars)} < 5")

        return False

    def _validate_current_r2g_setup(self, symbol: str, bar: MarketData) -> bool:
        """Validate that R2G setup is still valid - RELAXED VERSION"""
        if symbol not in self.r2g_setups:
            return False

        setup = self.r2g_setups[symbol]

        # Check setup age
        setup_time = setup.get('setup_time', datetime.now())
        age_hours = (datetime.now() - setup_time).total_seconds() / 3600

        if age_hours > self._parameters['max_setup_age_hours']:
            self.logger.debug(f"{symbol}: R2G setup too old ({age_hours:.1f}h)")
            del self.r2g_setups[symbol]
            return False

        # RELAXED: Check minimum setup age (reduced to 5 minutes)
        age_minutes = (datetime.now() - setup_time).total_seconds() / 60
        if age_minutes < self._parameters['min_setup_age_minutes']:
            self.logger.debug(f"{symbol}: R2G setup too recent ({age_minutes:.1f}min)")
            return False

        # RELAXED: Price validation is more lenient
        r2g_level = setup['r2g_level']
        current_price = bar.close

        # RELAXED: Allow wider range - price shouldn't be too far above R2G level
        if current_price > r2g_level * 1.20:  # RELAXED: 20% above R2G level (was 10%)
            self.logger.debug(f"{symbol}: Price too far above R2G level")
            return False

        # RELAXED: Allow entry even if price is below R2G level (dip opportunity)
        return True

    def _detect_r2g_breakout(self, symbol: str, bar: MarketData) -> Optional[Dict]:
        """Detect convincing R2G breakout with volume confirmation - RELAXED VERSION"""
        if symbol not in self.r2g_setups:
            return None

        setup = self.r2g_setups[symbol]
        r2g_level = setup['r2g_level']
        current_price = bar.close

        # RELAXED: Check if price breaks above R2G level (reduced from 5% to 2%)
        breakout_percent = (current_price - r2g_level) / r2g_level * 100

        if breakout_percent < self._parameters['min_r2g_breakout_percent']:
            # RELAXED: Also allow negative breakouts (dip entries) if price is close to R2G level
            if abs(breakout_percent) <= 1.0:  # Within 1% of R2G level
                self.logger.info(f"🔴➡️🟢 {symbol}: Near R2G level entry - "
                                f"Price: ${current_price:.2f}, Level: ${r2g_level:.2f}, "
                                f"Distance: {breakout_percent:.1f}%")
                breakout_percent = 0.5  # Treat as minimal breakout
            else:
                return None

        # RELAXED: Volume confirmation (but don't fail if volume check fails)
        volume_valid = self._validate_breakout_volume(symbol, bar)
        if not volume_valid:
            self.logger.info(f"⚠️ {symbol}: R2G breakout without volume confirmation - allowing entry")

        self.logger.info(f"🚀 {symbol}: R2G BREAKOUT detected! "
                        f"Price: ${current_price:.2f}, Level: ${r2g_level:.2f}, "
                        f"Breakout: {breakout_percent:.1f}%")

        return {
            'breakout_price': current_price,
            'r2g_level': r2g_level,
            'breakout_percent': breakout_percent,
            'volume': bar.volume,
            'timestamp': bar.timestamp
        }

    def _validate_breakout_volume(self, symbol: str, bar: MarketData) -> bool:
        """Validate that breakout has sufficient volume - RELAXED VERSION"""
        try:
            # RELAXED: More lenient volume validation
            current_volume = bar.volume

            # Basic volume check - must have some volume
            if current_volume <= 0:
                return False

            # Check against daily volume minimum (relaxed to 30k)
            daily_vol_per_minute = self._parameters['min_daily_volume'] / 390  # Market minutes
            if current_volume < daily_vol_per_minute * 0.5:  # RELAXED: Half of minimum
                self.logger.debug(f"{symbol}: Very low volume ({current_volume:,})")
                return False

            # RELAXED: Try to get average volume but don't fail if not available
            avg_volume = getattr(bar, 'avg_volume', None)
            if avg_volume and avg_volume > 0:
                volume_ratio = current_volume / avg_volume

                # RELAXED: Reduced multiplier requirement (1.5 -> 1.1)
                if volume_ratio < self._parameters['breakout_volume_multiplier']:
                    self.logger.debug(f"{symbol}: Below volume multiplier ({volume_ratio:.1f}x)")
                    return True  # RELAXED: Still allow entry (was return False)

                self.logger.info(f"✅ {symbol}: Volume confirmation - {volume_ratio:.1f}x average")
            else:
                self.logger.info(f"✅ {symbol}: Volume OK - {current_volume:,} (no avg comparison)")

            return True

        except Exception as e:
            self.logger.error(f"Error validating breakout volume for {symbol}: {e}")
            return True  # Default to True on error

    def _check_dip_entry_opportunity(self, symbol: str, bar: MarketData) -> Optional[Dict]:
        """Check for optimal dip entry back to R2G level"""
        if symbol not in self.breakout_tracking:
            return None

        breakout_data = self.breakout_tracking[symbol]
        r2g_level = breakout_data['r2g_level']
        current_price = bar.close

        # Check if price has dipped back near R2G level
        distance_from_r2g = (current_price - r2g_level) / r2g_level * 100

        # Price should be close to R2G level (within small range)
        if abs(distance_from_r2g) > self._parameters['max_dip_below_r2g']:
            return None

        # Volume should be lower than breakout volume (less selling pressure)
        breakout_volume = breakout_data['volume']
        current_volume = bar.volume
        volume_ratio = current_volume / breakout_volume

        if volume_ratio > self._parameters['dip_volume_threshold']:
            self.logger.debug(f"{symbol}: Dip volume too high ({volume_ratio:.1f}x breakout)")
            return None

        self.logger.info(f"📉➡️🟢 {symbol}: DIP ENTRY opportunity! "
                        f"Price: ${current_price:.2f}, R2G: ${r2g_level:.2f}, "
                        f"Volume: {volume_ratio:.1f}x breakout")

        return {
            'entry_price': current_price,
            'r2g_level': r2g_level,
            'distance_from_r2g': distance_from_r2g,
            'volume_ratio': volume_ratio,
            'timestamp': bar.timestamp,
            'breakout_data': breakout_data
        }

    def _generate_r2g_entry_signal(self, symbol: str, bar: MarketData,
                                  entry_data: Dict, entry_type: str) -> Optional[Signal]:
        """Generate R2G entry signal"""
        try:
            if symbol not in self.r2g_setups:
                return None

            setup = self.r2g_setups[symbol]

            # Calculate confidence based on setup quality and entry type
            base_confidence = min(setup.get('score', 50) / 100, 0.9)

            if entry_type == "DIP":
                confidence = min(base_confidence + 0.1, 0.95)  # Dip entries get bonus
            else:
                confidence = base_confidence

            # Position check
            position_check = self._can_open_new_position(symbol, bar.close, 'long')
            if not position_check['can_open']:
                if position_check['position_action'] == 'blocked':
                    self.logger.debug(f"[{symbol}] {position_check['reason']}")
                return None

            # Store entry signal info
            self.entry_signals[symbol] = {
                'entry_price': bar.close,
                'entry_type': entry_type,
                'r2g_level': setup['r2g_level'],
                'target_1': setup['target_1'],
                'target_2': setup['target_2'],
                'stop_loss': setup['stop_loss'],
                'entry_time': bar.timestamp,
                'entry_data': entry_data,
                'position_action': position_check['position_action']
            }

            # Clean up tracking
            if symbol in self.breakout_tracking:
                del self.breakout_tracking[symbol]

            # Record signal timing
            self._record_signal_time(symbol, bar.timestamp)

            self.logger.info(f"🔴➡️🟢 {symbol}: R2G {entry_type} ENTRY signal generated at ${bar.close:.2f}")

            signal = Signal(
                signal_id=f"R2G-{entry_type}-{symbol}-{bar.timestamp.strftime('%Y%m%d_%H%M%S')}",
                symbol=symbol,
                signal_type=SignalType.LONG,
                strength=confidence,
                price=bar.close,
                timestamp=bar.timestamp,
                strategy_name="RedToGreen",
                metadata={
                    'strategy': 'RedToGreen',
                    'entry_type': entry_type,
                    'r2g_level': setup['r2g_level'],
                    'target_1': setup['target_1'],
                    'target_2': setup['target_2'],
                    'stop_loss': setup['stop_loss'],
                    'setup_score': setup.get('score', 0),
                    'is_entry': True,
                    # Telegram notification fields
                    'setup_type': f'r2g_{entry_type}',
                    'volume_ratio': setup.get('volume_ratio', 0),
                    'pattern': f"r2g_{entry_type}_{setup.get('score', 0):.0f}pt"
                }
            )

            # Register position with centralized stop_loss_manager
            self._register_position_with_stop_manager(symbol, bar, signal)

            return signal

        except Exception as e:
            self.logger.error(f"Error generating R2G entry signal for {symbol}: {e}")
            return None

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

    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hour format"""
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
        """Check if current time is within trading hours"""
        return (self._parameters['optimal_entry_start'] <= time_decimal <=
                self._parameters['mandatory_exit_hour'])

    def _cleanup_position_tracking(self, symbol: str):
        """Clean up our tracking when position exits"""
        if symbol in self.entry_signals:
            del self.entry_signals[symbol]
        if symbol in self.breakout_tracking:
            del self.breakout_tracking[symbol]
        if symbol in self.dip_opportunities:
            del self.dip_opportunities[symbol]

    def _can_open_new_position(self, symbol: str, current_price: float, side: str) -> Dict[str, Any]:
        """
        Control de apertura de nuevas posiciones para Red to Green Strategy

        Returns:
            Dict with 'can_open', 'position_action', 'reason'
        """
        try:
            # 1. Check if already have position for this symbol
            if symbol in self.entry_signals:
                return {
                    'can_open': False,
                    'position_action': 'blocked',
                    'reason': f"Already have position for {symbol}"
                }

            # 2. Check daily trades limit
            from datetime import datetime
            current_date = datetime.now().date()
            if not hasattr(self, 'daily_trades'):
                self.daily_trades = {}

            if current_date not in self.daily_trades:
                self.daily_trades[current_date] = 0

            max_daily_trades = self._parameters.get('max_daily_trades', 10)
            if self.daily_trades[current_date] >= max_daily_trades:
                return {
                    'can_open': False,
                    'position_action': 'blocked',
                    'reason': f"Daily trades limit reached ({max_daily_trades})"
                }

            # 3. Check cooldown period
            if hasattr(self, 'last_signal_times') and symbol in self.last_signal_times:
                try:
                    current_time = datetime.now()
                    last_signal_time = self.last_signal_times[symbol]

                    # Handle timezone differences between datetime objects
                    if hasattr(last_signal_time, 'tzinfo') and last_signal_time.tzinfo is not None:
                        # last_signal_time is timezone-aware, make current_time timezone-aware too
                        from datetime import timezone
                        current_time = current_time.replace(tzinfo=timezone.utc)
                    elif hasattr(current_time, 'tzinfo') and current_time.tzinfo is not None:
                        # current_time is timezone-aware, remove timezone info to match
                        current_time = current_time.replace(tzinfo=None)

                    time_since_last = (current_time - last_signal_time).total_seconds()
                    cooldown_seconds = self.signal_cooldown_minutes * 60  # Convert to seconds
                except Exception as e:
                    self.logger.error(f"Error calculating cooldown time for {symbol}: {e}")
                    time_since_last = 0
                    cooldown_seconds = self.signal_cooldown_minutes * 60

                if time_since_last < cooldown_seconds:
                    return {
                        'can_open': False,
                        'position_action': 'blocked',
                        'reason': f"Cooldown period ({cooldown_seconds}s)"
                    }

            # All checks passed - can open new position
            return {
                'can_open': True,
                'position_action': 'new',
                'reason': 'All checks passed'
            }

        except Exception as e:
            self.logger.error(f"Error in position control for {symbol}: {e}")
            return {
                'can_open': False,
                'position_action': 'blocked',
                'reason': f"Error in position control: {e}"
            }

    def calculate_position_size(self, signal: Signal, capital: float, risk_per_trade: float) -> int:
        """Calculate position size for Red to Green strategy"""
        try:
            symbol = signal.symbol
            price = signal.price

            # Calculate base position size based on risk
            risk_amount = capital * min(risk_per_trade, self._parameters['max_risk_per_trade'])
            stop_distance = price * self._parameters['stop_loss_below_r2g']

            # Calculate base quantity
            if stop_distance > 0:
                base_quantity = int(risk_amount / stop_distance)
            else:
                base_quantity = int(self._parameters['min_position_value'] / price)

            # Apply position limits
            max_shares_value = int(self._parameters['max_position_value'] / price)
            quantity = min(base_quantity, max_shares_value)
            quantity = max(quantity, self._parameters['min_quantity'])

            self.logger.info(f"R2G position size for {symbol}: {quantity} shares @ {price:.2f}")

            return quantity

        except Exception as e:
            self.logger.error(f"Error calculating position size for {symbol}: {e}")
            return self._parameters['min_quantity']

    def get_strategy_info(self) -> dict:
        """Get strategy-specific information"""
        return {
            "name": self.name,
            "type": "Red to Green",
            "timeframe": "Intraday (Small Caps)",
            "parameters": self.parameters,
            "active_setups": len(self.r2g_setups),
            "active_breakouts": len(self.breakout_tracking),
            "active_signals": len(self.entry_signals),
            "performance": self.get_performance_stats()
        }

    # Implement required abstract methods from IStrategy
    async def on_position_update(self, position: Position) -> Optional[Signal]:
        """Handle position updates - required by IStrategy interface"""
        return None

    def should_exit(self, position: Position, current_bar: MarketData) -> Optional[Signal]:
        """SMALLCAP-OPTIMIZED exit with strategy-specific logic + centralized stop_manager"""
        try:
            # PRIORITY 1: Strategy-specific mandatory exit time (keep this unique logic)
            current_time = self._get_time_from_timestamp(current_bar.timestamp)
            if current_time >= self._parameters['mandatory_exit_hour']:
                return Signal(
                    signal_id=f"r2g_eod_exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                    symbol=position.symbol,
                    signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                    strength=1.0,
                    price=current_bar.close,
                    timestamp=current_bar.timestamp,
                    strategy_name="RedToGreen_Smallcaps_Optimized",
                    metadata={
                        'reason': 'end_of_day_exit',
                        'entry_price': position.avg_price,
                        'exit_type': 'EOD_EXIT_STRATEGY_SPECIFIC'
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
                        signal_id=f"r2g_stop_exit_{position.symbol}_{int(current_bar.timestamp.timestamp())}",
                        symbol=position.symbol,
                        signal_type=SignalType.EXIT_LONG if position.quantity > 0 else SignalType.EXIT_SHORT,
                        strength=1.0,
                        price=current_bar.close,
                        timestamp=current_bar.timestamp,
                        strategy_name="RedToGreen_Smallcaps_Optimized",
                        metadata={
                            'reason': exit_signal.get('reason', 'stop_manager'),
                            'exit_type': exit_signal.get('exit_reason', 'advanced_stop'),
                            'entry_price': position.avg_price,
                            'pnl_pct': exit_signal.get('pnl_pct', 0),
                            'smallcap_features': 'EMA_trailing,time_exits,volatility_filter'
                        }
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error in should_exit for {position.symbol}: {e}")
            return None

    def _register_position_with_stop_manager(self, symbol: str, bar: MarketData, signal: Signal):
        """Register the new position with SMALLCAP-OPTIMIZED centralized stop loss manager"""

        # SMALLCAPS RED-TO-GREEN: Use global config.ini parameters optimized for smallcaps
        # This strategy targets intraday reversals requiring:
        # - fallback_stop_loss_pct = 0.06 (6% for volatility during reversal plays)
        # - enable_dynamic_ema_trailing = true (responsive to reversal momentum)
        # - ema_trailing_periods = 5 (fast EMA-5 for quick reversals)
        # - max_hold_minutes = 180 (3 hours - reversal plays work fast or fail)
        # PLUS strategy-specific EOD exit at mandatory_exit_hour
        stop_params = create_stop_params_from_config(self._parameters)

        # Determine side
        side = 'bullish' if signal.signal_type == SignalType.LONG else 'bearish'

        # Register with stop manager
        self.stop_manager.register_position(
            symbol=symbol,
            entry_price=signal.price,
            entry_time=bar.timestamp,
            side=side,
            strategy_name="RedToGreen_Smallcaps_Optimized",
            stop_params=stop_params
        )

        self.logger.info(f"📊 {symbol}: RED-TO-GREEN SMALLCAP-OPTIMIZED - "
                        f"6% stop, EMA-5 trailing, EOD exit protection")