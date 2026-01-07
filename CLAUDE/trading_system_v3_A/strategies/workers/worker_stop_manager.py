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
    min_profit_for_trailing: Optional[float] = None  # Minimum profit % before trailing activates

    # Break-Even Logic
    breakeven_activation_pct: Optional[float] = None  # Fixed threshold (e.g., 3.0%)
    breakeven_r_multiplier: Optional[float] = None    # Dynamic threshold (e.g., 1.0 * SL)
    breakeven_minimum_pct: Optional[float] = None      # Floor for dynamic threshold (e.g., min(1R, 4%))

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

        # Current time override for replay/backtest mode (None = use datetime.now())
        self._current_time: Optional[datetime] = None

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

    def register_position(self, symbol: str, entry_time: Optional[datetime] = None, restored_highest_pnl: float = 0.0) -> None:
        """
        Register a new position for tracking

        Args:
            symbol: Symbol to track
            entry_time: Entry timestamp (defaults to now)
            restored_highest_pnl: Restored highest PnL from database (for trailing stop persistence)
        """
        self.highest_pnl[symbol] = restored_highest_pnl
        self.entry_times[symbol] = entry_time or datetime.now()

        if restored_highest_pnl > 0:
            self.logger.info(f"📝 Registered position: {symbol} (Restored trailing state: {restored_highest_pnl:+.2f}%)")
        else:
            self.logger.debug(f"📝 Registered position: {symbol}")

    def get_trailing_state(self, symbol: str) -> float:
        """
        Get current trailing stop state for persistence

        Args:
            symbol: Symbol to get state for

        Returns:
            Current highest_pnl value (0.0 if not tracked)
        """
        return self.highest_pnl.get(symbol, 0.0)

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
        print(f"[DEBUG] check_exit called: symbol={symbol}, price=${current_price:.2f}, entry=${entry_price:.2f}, _current_time={self._current_time}")

        # Determine if this is a SHORT position
        is_short = position_metadata.get('side', 'BUY') == 'SELL' if position_metadata else False

        # Calculate PnL percentage (inverted for SHORT)
        if is_short:
            # SHORT: Profit when price goes DOWN
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        else:
            # LONG: Profit when price goes UP
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

        self.logger.debug(f"📊 PnL for {symbol}: {pnl_pct:+.2f}% ({'SHORT' if is_short else 'LONG'})")

        # Update highest PnL for trailing stop
        if symbol not in self.highest_pnl:
            self.highest_pnl[symbol] = 0.0

        highest_pnl = self.highest_pnl[symbol]
        if pnl_pct > highest_pnl:
            print(f"[DEBUG] {symbol}: NEW PEAK PnL {pnl_pct:.2f}% (previous: {highest_pnl:.2f}%)")
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
        print(f"[DEBUG] Trailing Stop evaluation: pnl={pnl_pct:.2f}%, highest={highest_pnl:.2f}%, min_profit_for_trailing={self.config.min_profit_for_trailing}")
        try:
            # Check if we need minimum profit before trailing activates
            if self.config.min_profit_for_trailing is not None:
                if pnl_pct < self.config.min_profit_for_trailing:
                    # Skip trailing stop - let trade develop through initial volatility
                    # Break-even protection is still active at lower profit levels
                    pass
                else:
                    # Profit threshold reached - activate normal trailing logic
                    # Use dynamic trailing params from position_metadata if available (quality-based targets)
                    trailing_activation = self.config.trailing_activation
                    trailing_distance = self.config.trailing_distance
                    print(f"[DEBUG] Using config defaults: activation={trailing_activation}, distance={trailing_distance}")

                    if position_metadata and 'opportunity_data' in position_metadata:
                        dynamic_trailing_activation = position_metadata['opportunity_data'].get('trailing_activation_pct')
                        dynamic_trailing_distance = position_metadata['opportunity_data'].get('trailing_distance_pct')
                        print(f"[DEBUG] Dynamic trailing from opportunity_data: activation={dynamic_trailing_activation}, distance={dynamic_trailing_distance}")
                        if dynamic_trailing_activation:
                            trailing_activation = dynamic_trailing_activation
                        if dynamic_trailing_distance:
                            trailing_distance = dynamic_trailing_distance

                    # Ensure all values are floats to avoid type comparison errors
                    highest_pnl_float = float(highest_pnl)
                    trailing_activation_float = float(trailing_activation)
                    trailing_distance_float = float(trailing_distance)
                    print(f"[DEBUG] Trailing config: activation={trailing_activation_float:.2f}%, distance={trailing_distance_float:.2f}%")

                    if highest_pnl_float >= trailing_activation_float:
                        # Trailing stop triggers if price drops X% from highest
                        trailing_trigger = highest_pnl_float - trailing_distance_float
                        print(f"[DEBUG] Trailing check: highest={highest_pnl_float:.2f}%, current={pnl_pct:.2f}%, trigger={trailing_trigger:.2f}%")
                        if pnl_pct <= trailing_trigger:
                            if symbol in self.highest_pnl:
                                del self.highest_pnl[symbol]
                            return True, f"TRAILING_STOP (Peak: {highest_pnl_float:+.2f}%, Current: {pnl_pct:+.2f}%)"
            else:
                # No minimum profit threshold - use normal trailing logic
                # Use dynamic trailing params from position_metadata if available (quality-based targets)
                trailing_activation = self.config.trailing_activation
                trailing_distance = self.config.trailing_distance
                print(f"[DEBUG] ELSE branch - config defaults: activation={trailing_activation}, distance={trailing_distance}")

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
                print(f"[DEBUG] Trailing config (NO min_profit): activation={trailing_activation_float:.2f}%, distance={trailing_distance_float:.2f}%")

                if highest_pnl_float >= trailing_activation_float:
                    # Trailing stop triggers if price drops X% from highest
                    trailing_trigger = highest_pnl_float - trailing_distance_float
                    print(f"[DEBUG] Trailing check (NO min_profit): highest={highest_pnl_float:.2f}%, current={pnl_pct:.2f}%, trigger={trailing_trigger:.2f}%")
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
        # PRIORITY 1.5: Break-Even Protection (moves SL to entry)
        # ===================================================================
        # Use dynamic SL from position_metadata if available
        sl_pct = self.config.stop_loss_pct
        if position_metadata and 'opportunity_data' in position_metadata:
            dynamic_sl = position_metadata['opportunity_data'].get('stop_loss_pct')
            if dynamic_sl:
                sl_pct = dynamic_sl

        # Calculate activation threshold
        be_activation = self.config.breakeven_activation_pct
        
        # Hybrid Logic: Use smaller of 1R or minimum floor if configured
        if self.config.breakeven_r_multiplier is not None:
            dynamic_be_activation = sl_pct * self.config.breakeven_r_multiplier
            if self.config.breakeven_minimum_pct is not None:
                be_activation = min(dynamic_be_activation, self.config.breakeven_minimum_pct)
            else:
                be_activation = dynamic_be_activation
        
        # Check if Break-Even should trigger
        if be_activation is not None and highest_pnl >= be_activation:
            # Price reached activation threshold, now protect entry
            # Threshold for exit: 0.1% profit (covers some fees)
            be_exit_threshold = 0.1
            if pnl_pct <= be_exit_threshold:
                if symbol in self.highest_pnl:
                    del self.highest_pnl[symbol]
                return True, f"BREAK_EVEN (Activated at {be_activation:.1f}%, protected at {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 2: Take Profit (full target reached)
        # ===================================================================
        # Use dynamic TP from position_metadata if available (quality-based targets)
        tp_pct = self.config.take_profit_pct
        if position_metadata and 'opportunity_data' in position_metadata:
            dynamic_tp = position_metadata['opportunity_data'].get('take_profit_pct')
            if dynamic_tp:
                tp_pct = dynamic_tp

        print(f"[DEBUG] Take Profit check: pnl={pnl_pct:.2f}%, target={tp_pct:.2f}%")
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
        # CRITICAL FIX: Skip time limit check for SWING trades (EOD_safe=True)
        # We don't want to close a swing trade just because it's been open 8 hours
        eod_safe_for_time_limit = False
        if position_metadata:
             # Check nested structure first (adapter format)
             if 'opportunity_data' in position_metadata:
                 eod_safe_for_time_limit = position_metadata['opportunity_data'].get('EOD_safe', False)
             
             # Fallback to root (direct format)
             if not eod_safe_for_time_limit:
                 eod_safe_for_time_limit = position_metadata.get('EOD_safe', False)

        if self.config.max_position_hours and symbol in self.entry_times and not eod_safe_for_time_limit:
            entry_time = self.entry_times[symbol]

            # Handle case where entry_time might be a string (from restoration)
            if isinstance(entry_time, str):
                try:
                    from dateutil import parser
                    entry_time = parser.parse(entry_time)
                except Exception as e:
                    self.logger.warning(f"Could not parse entry_time '{entry_time}': {e}")
                    entry_time = datetime.now()  # Fallback to now

            # Use _current_time if set (replay/backtest mode), otherwise use datetime.now() (live mode)
            current_time = self._current_time if self._current_time else datetime.now()
            hours_in_position = (current_time - entry_time).total_seconds() / 3600
            print(f"[DEBUG] check_exit time_limit: _current_time={self._current_time}, current_time={current_time}, entry_time={entry_time}, hours={hours_in_position:.2f}")
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

        # Use _current_time if set (replay/backtest mode), otherwise use datetime.now() (live mode)
        current_time = self._current_time if self._current_time else datetime.now()

        # Ensure timezone awareness
        if current_time.tzinfo is None:
            # Assume UTC if no timezone
            current_time = pytz.utc.localize(current_time)

        market_time = current_time.astimezone(eastern)
        current_hour = market_time.hour + market_time.minute / 60

        # Check if we're in regular market hours (9:30 AM - 4:00 PM ET)
        # Only trigger EOD exit during regular hours, not premarket/afterhours
        is_regular_hours = 9.5 <= current_hour < 16.0  # 9:30 AM to 4:00 PM ET
        
        # FIX: Also allow "cleanup window" (16:00-16:30) to catch missed EOD exits
        # This handles cases where the system loop lags/sleeps past 16:00:00
        is_cleanup_window = 16.0 <= current_hour < 16.5

        if (is_regular_hours and current_hour >= self.config.end_of_day_hour) or is_cleanup_window:
            # Check EOD_safe flag from position metadata
            eod_safe = False
            trading_horizon = 'unknown'
            
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
                    
                # === MERIT-BASED PROMOTION (Intraday -> Swing) ===
                # If Intraday trade closes STRONG (Elite Strength >= 0.80), promote to Swing
                # Rule: Strength >= 0.80 AND PnL > 0 (Winner) AND Not Scalp
                # SAFETY: EXPLICITLY RESTRICT TO LONG TRADES
                # Risk: Losing Shorts (Price > Entry) have Positive Naive PnL and High Strength (Close near High)
                # This would wrongly promote losing shorts!
                side = position_metadata.get('side', 'LONG')
                is_short_strategy = 'short' in position_metadata.get('strategy', '').lower()
                
                if trading_horizon == 'intraday' and market_data and side == 'LONG' and not is_short_strategy:
                    try:
                        # Calculate EOD Strength
                        day_high = getattr(market_data, 'high', 0)
                        day_low = getattr(market_data, 'low', 0)
                        day_close = current_price
                        
                        if day_high > day_low:
                            strength = (day_close - day_low) / (day_high - day_low)
                            
                            # Check conditions
                            is_winner = pnl_pct > 0
                            is_elite_strength = strength >= 0.80
                            
                            if is_winner and is_elite_strength:
                                self.logger.info(
                                    f"🏅 {symbol}: MERIT PROMOTION! "
                                    f"Strength={strength:.2f} (>=0.80) & PnL={pnl_pct:.2f}% (>0). "
                                    f"Promoting INTRADAY -> SWING (Holding Overnight)"
                                )
                                return False, "" # Skip EOD exit
                    except Exception as e:
                        self.logger.warning(f"Failed to calculate EOD strength for {symbol}: {e}")

            # If not EOD_safe AND not Promoted, close before EOD
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
    print(f"[DEBUG create_worker_stop_manager] config_obj type: {type(config_obj)}")
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
        # NOTE: Config values are in decimal format (0.08 = 8%), convert to percentage for internal use
        trailing_activation_raw = get_config_value(
            config_obj, strategy_name, 'trailing_activation',
            fallback=get_config_value(config_obj, 'GLOBAL', 'default_trailing_activation', '0.08')
        )
        print(f"[DEBUG create_worker_stop_manager] strategy={strategy_name}, trailing_activation_raw={trailing_activation_raw}")
        # FIX: Values in config are already in "ready-to-use" format (0.08 means 8%)
        # Just multiply by 100 to convert to percentage representation
        trailing_activation = float(trailing_activation_raw) * 100
        print(f"[DEBUG create_worker_stop_manager] After *100: trailing_activation={trailing_activation}")

        trailing_distance_raw = get_config_value(
            config_obj, strategy_name, 'trailing_distance',
            fallback=get_config_value(config_obj, 'GLOBAL', 'default_trailing_stop_pct', '0.04')
        )
        trailing_distance = float(trailing_distance_raw) * 100

        # Minimum profit before trailing activates (optional)
        min_profit_for_trailing_raw = get_config_value(
            config_obj, strategy_name, 'min_profit_for_trailing',
            is_float=False
        )
        min_profit_for_trailing = float(min_profit_for_trailing_raw) if min_profit_for_trailing_raw else None

        # Break-even parameters
        breakeven_activation_pct = None
        be_activation_raw = get_config_value(config_obj, strategy_name, 'breakeven_activation_pct', is_float=False)
        if be_activation_raw:
            breakeven_activation_pct = float(be_activation_raw) * 100

        breakeven_r_multiplier = None
        be_r_raw = get_config_value(config_obj, strategy_name, 'breakeven_r_multiplier', is_float=False)
        if be_r_raw:
            breakeven_r_multiplier = float(be_r_raw)

        breakeven_minimum_pct = None
        be_min_raw = get_config_value(config_obj, strategy_name, 'breakeven_minimum_pct', is_float=False)
        if be_min_raw:
            breakeven_minimum_pct = float(be_min_raw) * 100

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
            min_profit_for_trailing=min_profit_for_trailing,
            breakeven_activation_pct=breakeven_activation_pct,
            breakeven_r_multiplier=breakeven_r_multiplier,
            breakeven_minimum_pct=breakeven_minimum_pct,
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
