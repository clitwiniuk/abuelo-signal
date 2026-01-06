"""
Worker Stop Manager - Centralized stop loss and take profit management for workers
Reads configuration from config.ini for consistent exit logic across all workers
"""

from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging


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
    end_of_day_hour: float = 15.93  # 15:56 ET (21:56 España)


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
        market_data: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Check if position should exit based on priority order

        Priority Order:
        1. FOMO Exhaustion (prioridad 0)
        2. Trailing Stop (prioridad 1)
        3. Take Profit
        4. Stop Loss
        5. Time Limit
        6. EOD Exit

        Args:
            symbol: Symbol to check
            current_price: Current market price
            entry_price: Position entry price
            market_data: Optional market data for FOMO detection

        Returns:
            Tuple of (should_exit, reason)
        """
        # Calculate PnL percentage
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

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
        if highest_pnl >= self.config.trailing_activation:
            # Trailing stop triggers if price drops X% from highest
            trailing_trigger = highest_pnl - self.config.trailing_distance
            if pnl_pct <= trailing_trigger:
                if symbol in self.highest_pnl:
                    del self.highest_pnl[symbol]
                return True, f"TRAILING_STOP (Peak: {highest_pnl:+.2f}%, Current: {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 2: Take Profit (full target reached)
        # ===================================================================
        if pnl_pct >= self.config.take_profit_pct:
            if symbol in self.highest_pnl:
                del self.highest_pnl[symbol]
            return True, f"TAKE_PROFIT_{self.config.take_profit_pct}% (PnL: {pnl_pct:+.2f}%)"

        # ===================================================================
        # PRIORITY 3: Stop Loss (protect capital)
        # ===================================================================
        if pnl_pct <= -self.config.stop_loss_pct:
            if symbol in self.highest_pnl:
                del self.highest_pnl[symbol]
            return True, f"STOP_LOSS_{self.config.stop_loss_pct}% (PnL: {pnl_pct:+.2f}%)"

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
        # 15:56 ET = 21:56 España (aprovecha más horario de mercado)
        import pytz
        eastern = pytz.timezone('US/Eastern')
        market_time = datetime.now(eastern)
        current_hour = market_time.hour + market_time.minute / 60
        if current_hour >= self.config.end_of_day_hour:
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

        trailing_active = highest_pnl >= self.config.trailing_activation
        trailing_trigger = highest_pnl - self.config.trailing_distance if trailing_active else None

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
    Factory function to create WorkerStopManager from config.ini

    Args:
        config_obj: ConfigParser object or similar with config.ini data
        strategy_name: Name of strategy section (e.g., 'DAILY_PLAYS_STRATEGY')

    Returns:
        WorkerStopManager instance configured from config.ini
    """
    logger = logging.getLogger("WorkerStopManager")

    # Try to get strategy-specific config first, fall back to global defaults
    try:
        # Strategy-specific stop loss
        stop_loss_pct = float(config_obj.get(
            strategy_name, 'stop_loss_pct',
            fallback=config_obj.get('DEFAULT', 'fallback_stop_loss_pct', fallback='0.05')
        )) * 100

        # Strategy-specific take profit
        take_profit_pct = float(config_obj.get(
            strategy_name, 'take_profit_pct',
            fallback=config_obj.get('DEFAULT', 'fallback_take_profit_pct', fallback='0.20')
        )) * 100

        # Quick target (optional)
        quick_target = config_obj.get(strategy_name, 'quick_target_pct', fallback=None)
        quick_target_pct = float(quick_target) * 100 if quick_target else None

        # Trailing stop parameters
        trailing_activation = float(config_obj.get(
            'DEFAULT', 'default_trailing_activation', fallback='0.03'
        )) * 100

        trailing_distance = float(config_obj.get(
            'DEFAULT', 'default_trailing_stop_pct', fallback='0.02'
        )) * 100

        # Time-based parameters
        max_hours = config_obj.get(strategy_name, 'max_hold_hours', fallback=None)
        max_position_hours = float(max_hours) if max_hours else None

        config = WorkerStopConfig(
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            quick_target_pct=quick_target_pct,
            trailing_activation=trailing_activation,
            trailing_distance=trailing_distance,
            max_position_hours=max_position_hours
        )

        logger.info(
            f"✅ Created WorkerStopManager for {strategy_name}: "
            f"SL={stop_loss_pct}%, TP={take_profit_pct}%, QT={quick_target_pct}%"
        )

        return WorkerStopManager(config)

    except Exception as e:
        logger.error(f"❌ Error creating WorkerStopManager: {e}")
        # Return default config
        return WorkerStopManager(WorkerStopConfig())
