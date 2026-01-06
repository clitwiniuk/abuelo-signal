"""
Worker Stop Manager - Centralized stop loss and take profit management for workers
Reads configuration from config.ini for consistent exit logic across all workers
"""

from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging
def get_config_value(config, section, key, fallback=None, is_float=True):
    """
    Helper function to get configuration values with fallbacks
    Supports ConfigParser, dict, and UnifiedConfig objects
    """
    try:
        # Try ConfigParser methods first (getfloat, get)
        if hasattr(config, 'getfloat') and is_float:
            return config.getfloat(section, key, fallback=float(fallback) if fallback else 0.0)
        elif hasattr(config, 'get') and callable(getattr(config, 'get')):
            # Only use .get() if it's a callable method (ConfigParser)
            value = config.get(section, key, fallback=fallback)
            return float(value) if is_float and value else value
        elif isinstance(config, dict):
            # Handle dict-like config
            section_data = config.get(section, {})
            if isinstance(section_data, dict):
                value = section_data.get(key, fallback)
                return float(value) if is_float and value else value
            else:
                return section_data if not is_float else float(section_data)
        else:
            # Handle UnifiedConfig with direct attribute access
            # Try section.key first (e.g., config.GLOBAL.end_of_day_exit_time)
            section_obj = getattr(config, section, None)
            if section_obj is not None:
                value = getattr(section_obj, key, fallback)
                return float(value) if is_float and value and value != fallback else value
            # Fallback to direct attribute (e.g., config.end_of_day_exit_time)
            value = getattr(config, key, fallback)
            return float(value) if is_float and value and value != fallback else value
    except Exception as e:
        logger = logging.getLogger("WorkerStopManager")
        logger.debug(f"Error getting config {section}.{key}: {e}")
        return fallback


@dataclass
class WorkerStopConfig:
    """Configuration for stop loss and take profit management"""
    # Stop Loss
    stop_loss_pct: float = 5.0

    # Take Profit
    take_profit_pct: float = 20.0
    quick_target_pct: Optional[float] = None  # Optional quick scalp target

    # Trailing Stop
    trailing_activation: float = 3.0
    trailing_distance: float = 2.0

    # Time-based exits
    max_position_hours: Optional[float] = None
    end_of_day_hour: float = 15.97  # Will be overridden by config.ini


class WorkerStopManager:
    """
    Centralized stop loss and take profit manager for workers.
    Provides consistent exit logic across all worker strategies.

    Exit Priority Order:
    1. FOMO Exhaustion (prioridad 0)
    2. Trailing Stop (prioridad 1)
    3. Take Profit
    4. Stop Loss
    5. Time Limit
    6. EOD Exit
    """

    def __init__(self, config: WorkerStopConfig, execution_engine=None):
        """
        Initialize WorkerStopManager with configuration

        Args:
            config: WorkerStopConfig with stop/TP parameters
            execution_engine: ExecutionEngine for market data access
        """
        self.config = config
        self.execution_engine = execution_engine
        self.logger = logging.getLogger("WorkerStopManager")

        # Track highest PnL for trailing stops (per symbol)
        self.highest_pnl: Dict[str, float] = {}

        # Track position entry times (per symbol)
        self.entry_times: Dict[str, datetime] = {}

        # Initialize FOMO Detector
        self.fomo_detector = None
        try:
            from core.fomo_detector import FOMODetector
            fomo_config = {
                'rapid_drop_threshold': 0.03,  # 3% rapid drop
                'volume_spike_multiplier': 2.0,
                'time_window_seconds': 60
            }
            self.fomo_detector = FOMODetector(fomo_config)
            self.logger.info("✅ FOMO Detector initialized")
        except Exception as e:
            self.logger.warning(f"⚠️ FOMO Detector not available: {e}")

        self.logger.info(
            f"✅ WorkerStopManager initialized: "
            f"SL={config.stop_loss_pct}%, TP={config.take_profit_pct}%, "
            f"Trailing={config.trailing_activation}%/{config.trailing_distance}%"
        )

    def register_position(self, symbol: str, entry_time: Optional[datetime] = None) -> None:
        """
        Register a new position for tracking

        Args:
            symbol: Symbol to track
            entry_time: Entry timestamp (defaults to now)
        """
        self.highest_pnl[symbol] = 0.0
        self.entry_times[symbol] = entry_time or datetime.now()
        self.logger.debug(f"📝 Registered position: {symbol}")

    def unregister_position(self, symbol: str) -> None:
        """
        Remove position from tracking

        Args:
            symbol: Symbol to remove
        """
        self.highest_pnl.pop(symbol, None)
        self.entry_times.pop(symbol, None)
        self.logger.debug(f"🗑️ Unregistered position: {symbol}")

    def check_exit(
        self,
        symbol: str,
        current_price: float,
        entry_price: float,
        market_data: Optional[Any] = None,
        position_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Check if position should exit based on priority order

        Priority Order:
        1. FOMO Exhaustion (prioridad 0)
        2. Trailing Stop (prioridad 1)
        3. Take Profit
        4. Stop Loss
        5. Time Limit
        6. EOD Exit (respects EOD_safe flag for swing positions)

        Args:
            symbol: Symbol to check
            current_price: Current market price
            entry_price: Position entry price
            market_data: Optional market data for FOMO detection
            position_metadata: Optional position metadata with EOD_safe flag

        Returns:
            Tuple of (should_exit, reason)
        """
        self.logger.debug(f"🔍 Checking exit for {symbol}: Price={current_price:.2f}, Entry={entry_price:.2f}")

        # Calculate PnL percentage
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        self.logger.debug(f"📊 PnL for {symbol}: {pnl_pct:+.2f}%")

        # Update highest PnL for trailing stop
        if symbol not in self.highest_pnl:
            self.highest_pnl[symbol] = 0.0

        highest_pnl = self.highest_pnl[symbol]
        if pnl_pct > highest_pnl:
            self.highest_pnl[symbol] = pnl_pct
            highest_pnl = pnl_pct

        # ===================================================================
        # PRIORITY 0: FOMO Exhaustion (highest priority)
        # ===================================================================
        if self.fomo_detector and market_data:
            try:
                fomo_result = self.fomo_detector.detect_fomo_exit(
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    market_data=market_data
                )

                if fomo_result['should_exit']:
                    if symbol in self.highest_pnl:
                        del self.highest_pnl[symbol]
                    reason = fomo_result.get('reason', 'FOMO_EXHAUSTION')
                    confidence = fomo_result.get('confidence', 0.0)
                    return True, f"FOMO_EXHAUSTION (confidence: {confidence:.0%}, PnL: {pnl_pct:+.2f}%) - {reason}"
            except Exception as e:
                self.logger.debug(f"FOMO check failed for {symbol}: {e}")

        # ===================================================================
        # PRIORITY 1: Trailing Stop (protects profits)
        # ===================================================================
        try:
            # Use dynamic trailing params from position_metadata if available (quality-based targets)
            trailing_activation = self.config.trailing_activation
            trailing_distance = self.config.trailing_distance

            if position_metadata and 'opportunity_data' in position_metadata:
                dynamic_trailing_activation = position_metadata['opportunity_data'].get('trailing_activation_pct')
                dynamic_trailing_distance = position_metadata['opportunity_data'].get('trailing_distance_pct')
                if dynamic_trailing_activation:
                    trailing_activation = dynamic_trailing_activation
                if dynamic_trailing_distance:
                    trailing_distance = dynamic_trailing_distance

            # Ensure all values are floats to avoid type comparison errors
            highest_pnl_float = float(highest_pnl)
            trailing_activation_float = float(trailing_activation)
            trailing_distance_float = float(trailing_distance)

            if highest_pnl_float >= trailing_activation_float:
                # Trailing stop triggers if price drops X% from highest
                trailing_trigger = highest_pnl_float - trailing_distance_float
                if pnl_pct <= trailing_trigger:
                    if symbol in self.highest_pnl:
                        del self.highest_pnl[symbol]
                    return True, f"TRAILING_STOP (Peak: {highest_pnl_float:+.2f}%, Current: {pnl_pct:+.2f}%)"
        except (TypeError, ValueError) as e:
            self.logger.error(f"❌ Error in trailing stop check for {symbol}: {e}")
            self.logger.error(f"   highest_pnl: {highest_pnl} (type: {type(highest_pnl)})")
            self.logger.error(f"   trailing_activation: {trailing_activation} (type: {type(trailing_activation)})")
            self.logger.error(f"   trailing_distance: {trailing_distance} (type: {type(trailing_distance)})")
            # Continue to next priority check instead of crashing

        # ===================================================================
        # PRIORITY 2: Take Profit (full target reached)
        # ===================================================================
        # Use dynamic TP from position_metadata if available (quality-based targets)
        tp_pct = self.config.take_profit_pct
        if position_metadata and 'opportunity_data' in position_metadata:
            dynamic_tp = position_metadata['opportunity_data'].get('take_profit_pct')
            if dynamic_tp:
                tp_pct = dynamic_tp

        if pnl_pct >= tp_pct:
            if symbol in self.highest_pnl:
                del self.highest_pnl[symbol]
            return True, f"TAKE_PROFIT_{tp_pct:.1f}% (PnL: {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 3: Stop Loss (protect capital)
        # ===================================================================
        # Use dynamic SL from position_metadata if available (quality-based targets)
        sl_pct = self.config.stop_loss_pct
        if position_metadata and 'opportunity_data' in position_metadata:
            dynamic_sl = position_metadata['opportunity_data'].get('stop_loss_pct')
            if dynamic_sl:
                sl_pct = dynamic_sl

        if pnl_pct <= -sl_pct:
            if symbol in self.highest_pnl:
                del self.highest_pnl[symbol]
            return True, f"STOP_LOSS_{sl_pct:.1f}% (PnL: {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 4: Time Limit (position too old)
        # ===================================================================
        if self.config.max_position_hours and symbol in self.entry_times:
            entry_time = self.entry_times[symbol]

            # Handle case where entry_time might be a string (from restoration)
            if isinstance(entry_time, str):
                try:
                    from dateutil import parser
                    entry_time = parser.parse(entry_time)
                except Exception as e:
                    self.logger.warning(f"Could not parse entry_time '{entry_time}': {e}")
                    entry_time = datetime.now()  # Fallback to now

            hours_in_position = (datetime.now() - entry_time).total_seconds() / 3600
            if hours_in_position >= self.config.max_position_hours:
                if symbol in self.highest_pnl:
                    del self.highest_pnl[symbol]
                return True, f"TIME_LIMIT_{self.config.max_position_hours}h (PnL: {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 5: End of Day (market closing)
        # ===================================================================
        # Time configured in config.ini [GLOBAL] end_of_day_exit_time
        # ONLY EXIT IF IN REGULAR MARKET HOURS - NOT IN EXTENDED HOURS
        # RESPECT EOD_safe FLAG: SWING/SWING_SHORT positions can stay overnight
        import pytz
        eastern = pytz.timezone('US/Eastern')
        market_time = datetime.now(eastern)
        current_hour = market_time.hour + market_time.minute / 60

        # Check if we're in regular market hours (9:30 AM - 4:00 PM ET)
        # Only trigger EOD exit during regular hours, not premarket/afterhours
        is_regular_hours = 9.5 <= current_hour < 16.0  # 9:30 AM to 4:00 PM ET

        if is_regular_hours and current_hour >= self.config.end_of_day_hour:
            # Check EOD_safe flag from position metadata
            eod_safe = False
            if position_metadata:
                eod_safe = position_metadata.get('EOD_safe', False)
                trading_horizon = position_metadata.get('trading_horizon', 'unknown')

                if eod_safe:
                    self.logger.info(
                        f"📅 {symbol}: EOD_safe=True ({trading_horizon}) - "
                        f"SKIPPING EOD closure (swing position can stay overnight)"
                    )
                    # Don't close - let it run overnight
                    return False, ""

            # If not EOD_safe (INTRADAY or SCALP), close before EOD
            if symbol in self.highest_pnl:
                del self.highest_pnl[symbol]
            return True, f"END_OF_DAY (PnL: {pnl_pct:+.2f}%)"

        # No exit condition met
        return False, ""

    def get_position_status(self, symbol: str, current_price: float, entry_price: float) -> Dict:
        """
        Get current position status including PnL and trailing stop info

        Args:
            symbol: Symbol to check
            current_price: Current market price
            entry_price: Position entry price

        Returns:
            Dict with position status information
        """
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        highest_pnl = self.highest_pnl.get(symbol, 0.0)

        try:
            trailing_active = float(highest_pnl) >= float(self.config.trailing_activation)
            trailing_trigger = float(highest_pnl) - float(self.config.trailing_distance) if trailing_active else None
        except (TypeError, ValueError):
            trailing_active = False
            trailing_trigger = None

        return {
            'symbol': symbol,
            'pnl_pct': pnl_pct,
            'highest_pnl': highest_pnl,
            'trailing_active': trailing_active,
            'trailing_trigger': trailing_trigger,
            'stop_loss_trigger': -self.config.stop_loss_pct,
            'take_profit_trigger': self.config.take_profit_pct
        }


def create_worker_stop_manager(config_obj, strategy_name: str) -> WorkerStopManager:
    """
    Factory function to create WorkerStopManager from configuration

    Args:
        config_obj: UnifiedConfig dataclass or ConfigParser object
        strategy_name: Name of strategy section (e.g., 'DAILY_PLAYS_STRATEGY')

    Returns:
        WorkerStopManager instance configured from config
    """
    logger = logging.getLogger("WorkerStopManager")
    logger.debug(f"🔧 Creating WorkerStopManager for strategy: {strategy_name}")

    try:
        # Get configuration values with fallbacks
        stop_loss_raw = get_config_value(
            config_obj, strategy_name, 'stop_loss_pct',
            fallback=get_config_value(config_obj, 'DEFAULT', 'fallback_stop_loss_pct', '0.05')
        )
        stop_loss_pct = float(stop_loss_raw) * 100

        take_profit_raw = get_config_value(
            config_obj, strategy_name, 'take_profit_pct',
            fallback=get_config_value(config_obj, 'DEFAULT', 'fallback_take_profit_pct', '0.20')
        )
        take_profit_pct = float(take_profit_raw) * 100

        # Quick target (optional)
        quick_target = get_config_value(config_obj, strategy_name, 'quick_target_pct', is_float=False)
        quick_target_pct = float(quick_target) * 100 if quick_target else None

        # Trailing stop parameters
        # Try strategy-specific first, then GLOBAL, then fallback
        trailing_activation_raw = get_config_value(
            config_obj, strategy_name, 'trailing_activation',
            fallback=get_config_value(config_obj, 'GLOBAL', 'default_trailing_activation', '0.08')
        )
        trailing_activation = float(trailing_activation_raw) * 100

        trailing_distance_raw = get_config_value(
            config_obj, strategy_name, 'trailing_distance',
            fallback=get_config_value(config_obj, 'GLOBAL', 'default_trailing_stop_pct', '0.04')
        )
        trailing_distance = float(trailing_distance_raw) * 100

        # Time-based parameters
        max_hours = get_config_value(config_obj, strategy_name, 'max_hold_hours', is_float=False)
        max_position_hours = float(max_hours) if max_hours else None

        # Read end_of_day_exit_time from config
        eod_time_str = get_config_value(config_obj, 'GLOBAL', 'end_of_day_exit_time', '15:58', is_float=False)
        try:
            hours, minutes = map(int, eod_time_str.split(':'))
            end_of_day_hour = hours + (minutes / 60.0)
        except Exception as e:
            logger.warning(f"Invalid EOD time format: {eod_time_str}, using default")
            end_of_day_hour = 15.97  # Default 3:58 PM ET

        # Create config object
        config = WorkerStopConfig(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            quick_target_pct=quick_target_pct,
            trailing_activation=trailing_activation,
            trailing_distance=trailing_distance,
            max_position_hours=max_position_hours,
            end_of_day_hour=end_of_day_hour
        )

        logger.debug(
            f"DEBUG: stop_loss_pct={stop_loss_pct} (type: {type(stop_loss_pct)}), "
            f"take_profit_pct={take_profit_pct} (type: {type(take_profit_pct)}), "
            f"trailing_activation={trailing_activation} (type: {type(trailing_activation)}), "
            f"trailing_distance={trailing_distance} (type: {type(trailing_distance)})"
        )
        logger.info(
            f"✅ Created WorkerStopManager for {strategy_name}: "
            f"SL={stop_loss_pct}%, TP={take_profit_pct}%, "
            f"Trailing={trailing_activation}%/{trailing_distance}%, "
            f"MaxHours={max_position_hours}, EOD={end_of_day_hour}"
        )

        return WorkerStopManager(config)

    except Exception as e:
        logger.error(f"❌ Error creating WorkerStopManager for {strategy_name}: {e}")
        logger.debug(f"Config object type: {type(config_obj)}")
        # Return default config
        return WorkerStopManager(WorkerStopConfig())
