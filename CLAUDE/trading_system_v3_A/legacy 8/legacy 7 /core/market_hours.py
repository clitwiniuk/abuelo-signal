"""
Market Hours Utility - Horarios de mercado y restricciones para operaciones

Gestiona:
1. Horarios de mercado (premarket, regular, afterhours)
2. Restricciones para operaciones SHORT (solo regular hours)
3. Tiempo de cierre forzado para shorts (antes del cierre)
4. Validaciones de entrada según tipo de operación

Author: Trading System
Date: 2025-12-26
"""

import logging
from datetime import datetime, time as datetime_time
from typing import Tuple, Optional
import pytz

logger = logging.getLogger(__name__)


class MarketHours:
    """
    Gestión centralizada de horarios de mercado y restricciones de trading.

    Horarios US Eastern Time (NYSE/NASDAQ):
    - Premarket: 4:00 AM - 9:30 AM ET
    - Regular Hours: 9:30 AM - 4:00 PM ET
    - After Hours: 4:00 PM - 8:00 PM ET

    Restricciones SHORT:
    - Solo durante regular hours
    - Cierre forzado: 15:45 ET (15 min antes del cierre)
    - No overnight positions
    - No premarket/afterhours entries
    """

    # Market hours (US Eastern Time)
    PREMARKET_START = datetime_time(4, 0)     # 4:00 AM ET
    MARKET_OPEN = datetime_time(9, 30)        # 9:30 AM ET
    MARKET_CLOSE = datetime_time(16, 0)       # 4:00 PM ET
    AFTERHOURS_END = datetime_time(20, 0)     # 8:00 PM ET

    # Short position restrictions
    SHORT_ENTRY_EARLIEST = datetime_time(9, 35)   # 5 min después de apertura (volatilidad inicial)
    SHORT_ENTRY_LATEST = datetime_time(15, 0)     # 1h antes del cierre (margen para gestión)
    SHORT_EXIT_DEADLINE = datetime_time(15, 45)   # 15 min antes del cierre (forzar cierre)

    def __init__(self):
        self.et_timezone = pytz.timezone('US/Eastern')
        self.logger = logging.getLogger(f"{__name__}.MarketHours")

    def get_current_et_time(self) -> datetime:
        """Get current time in US Eastern timezone"""
        return datetime.now(self.et_timezone)

    def get_market_session(self, dt: Optional[datetime] = None) -> str:
        """
        Determine current market session.

        Args:
            dt: Optional datetime to check (uses current time if None)

        Returns:
            str: 'PREMARKET', 'REGULAR', 'AFTERHOURS', 'CLOSED'
        """
        if dt is None:
            dt = self.get_current_et_time()

        # Convert to ET if needed
        if dt.tzinfo is None:
            dt = self.et_timezone.localize(dt)
        elif dt.tzinfo != self.et_timezone:
            dt = dt.astimezone(self.et_timezone)

        current_time = dt.time()

        if self.PREMARKET_START <= current_time < self.MARKET_OPEN:
            return 'PREMARKET'
        elif self.MARKET_OPEN <= current_time < self.MARKET_CLOSE:
            return 'REGULAR'
        elif self.MARKET_CLOSE <= current_time < self.AFTERHOURS_END:
            return 'AFTERHOURS'
        else:
            return 'CLOSED'

    def is_regular_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if market is in regular trading hours"""
        return self.get_market_session(dt) == 'REGULAR'

    def is_premarket(self, dt: Optional[datetime] = None) -> bool:
        """Check if market is in premarket"""
        return self.get_market_session(dt) == 'PREMARKET'

    def is_afterhours(self, dt: Optional[datetime] = None) -> bool:
        """Check if market is in afterhours"""
        return self.get_market_session(dt) == 'AFTERHOURS'

    def is_extended_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if market is in premarket or afterhours (extended hours)"""
        session = self.get_market_session(dt)
        return session in ('PREMARKET', 'AFTERHOURS')

    def can_enter_short(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if SHORT entry is allowed at given time.

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        if dt is None:
            dt = self.get_current_et_time()

        # Convert to ET
        if dt.tzinfo is None:
            dt = self.et_timezone.localize(dt)
        elif dt.tzinfo != self.et_timezone:
            dt = dt.astimezone(self.et_timezone)

        current_time = dt.time()
        session = self.get_market_session(dt)

        # CRITICAL: Only regular hours
        if session != 'REGULAR':
            return False, f"SHORT entries only during regular hours (current: {session})"

        # Check time window
        if current_time < self.SHORT_ENTRY_EARLIEST:
            return False, f"SHORT entries start at {self.SHORT_ENTRY_EARLIEST.strftime('%H:%M')} ET (current: {current_time.strftime('%H:%M')} ET)"

        if current_time > self.SHORT_ENTRY_LATEST:
            return False, f"SHORT entries end at {self.SHORT_ENTRY_LATEST.strftime('%H:%M')} ET (current: {current_time.strftime('%H:%M')} ET)"

        return True, "SHORT entry allowed"

    def can_enter_long(self, dt: Optional[datetime] = None, allow_extended_hours: bool = True) -> Tuple[bool, str]:
        """
        Check if LONG entry is allowed at given time.

        Args:
            dt: Time to check (current time if None)
            allow_extended_hours: Whether to allow premarket/afterhours entries

        Returns:
            Tuple[bool, str]: (allowed, reason)
        """
        if dt is None:
            dt = self.get_current_et_time()

        session = self.get_market_session(dt)

        if session == 'CLOSED':
            return False, "Market is closed"

        if session in ('PREMARKET', 'AFTERHOURS') and not allow_extended_hours:
            return False, f"LONG entries not allowed in {session} (extended hours disabled)"

        return True, "LONG entry allowed"

    def should_force_exit_short(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if SHORT positions should be force-closed.

        CRITICAL: Prevents overnight SHORT positions (high risk).

        Returns:
            Tuple[bool, str]: (should_exit, reason)
        """
        if dt is None:
            dt = self.get_current_et_time()

        # Convert to ET
        if dt.tzinfo is None:
            dt = self.et_timezone.localize(dt)
        elif dt.tzinfo != self.et_timezone:
            dt = dt.astimezone(self.et_timezone)

        current_time = dt.time()

        # Force exit at deadline
        if current_time >= self.SHORT_EXIT_DEADLINE:
            return True, f"SHORT exit deadline reached ({self.SHORT_EXIT_DEADLINE.strftime('%H:%M')} ET) - FORCE CLOSE"

        # Also force exit if market is not in regular hours
        session = self.get_market_session(dt)
        if session != 'REGULAR':
            return True, f"Market session changed to {session} - FORCE CLOSE SHORT"

        return False, "No forced exit required"

    def minutes_until_short_deadline(self, dt: Optional[datetime] = None) -> Optional[int]:
        """
        Calculate minutes until SHORT exit deadline.

        Returns:
            int: Minutes until deadline, or None if already past deadline
        """
        if dt is None:
            dt = self.get_current_et_time()

        # Convert to ET
        if dt.tzinfo is None:
            dt = self.et_timezone.localize(dt)
        elif dt.tzinfo != self.et_timezone:
            dt = dt.astimezone(self.et_timezone)

        current_time = dt.time()

        # Already past deadline
        if current_time >= self.SHORT_EXIT_DEADLINE:
            return None

        # Calculate minutes
        deadline_datetime = dt.replace(
            hour=self.SHORT_EXIT_DEADLINE.hour,
            minute=self.SHORT_EXIT_DEADLINE.minute,
            second=0,
            microsecond=0
        )

        delta = deadline_datetime - dt
        return int(delta.total_seconds() / 60)

    def get_market_status_summary(self, dt: Optional[datetime] = None) -> dict:
        """
        Get comprehensive market status summary.

        Returns:
            dict: Market status information
        """
        if dt is None:
            dt = self.get_current_et_time()

        session = self.get_market_session(dt)
        can_short, short_reason = self.can_enter_short(dt)
        can_long, long_reason = self.can_enter_long(dt)
        should_exit, exit_reason = self.should_force_exit_short(dt)
        mins_to_deadline = self.minutes_until_short_deadline(dt)

        return {
            'current_time_et': dt.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'session': session,
            'is_regular_hours': session == 'REGULAR',
            'is_extended_hours': session in ('PREMARKET', 'AFTERHOURS'),
            'can_enter_short': can_short,
            'short_entry_reason': short_reason,
            'can_enter_long': can_long,
            'long_entry_reason': long_reason,
            'should_force_exit_short': should_exit,
            'force_exit_reason': exit_reason,
            'minutes_to_short_deadline': mins_to_deadline
        }

    def log_market_status(self):
        """Log current market status (useful for debugging)"""
        status = self.get_market_status_summary()

        self.logger.info("=" * 60)
        self.logger.info("MARKET STATUS SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Current Time (ET): {status['current_time_et']}")
        self.logger.info(f"Session: {status['session']}")
        self.logger.info(f"Regular Hours: {status['is_regular_hours']}")
        self.logger.info("")
        self.logger.info("ENTRY PERMISSIONS:")
        self.logger.info(f"  SHORT: {'✅ ALLOWED' if status['can_enter_short'] else '❌ BLOCKED'}")
        self.logger.info(f"    → {status['short_entry_reason']}")
        self.logger.info(f"  LONG: {'✅ ALLOWED' if status['can_enter_long'] else '❌ BLOCKED'}")
        self.logger.info(f"    → {status['long_entry_reason']}")
        self.logger.info("")
        self.logger.info("EXIT REQUIREMENTS:")
        self.logger.info(f"  Force Exit SHORT: {'⚠️ YES' if status['should_force_exit_short'] else '✅ NO'}")
        self.logger.info(f"    → {status['force_exit_reason']}")

        if status['minutes_to_short_deadline'] is not None:
            self.logger.info(f"  Minutes to SHORT deadline: {status['minutes_to_short_deadline']} min")

        self.logger.info("=" * 60)


# Singleton instance for easy access
_market_hours_instance = None


def get_market_hours() -> MarketHours:
    """Get singleton MarketHours instance"""
    global _market_hours_instance
    if _market_hours_instance is None:
        _market_hours_instance = MarketHours()
    return _market_hours_instance


# Convenience functions
def is_regular_hours(dt: Optional[datetime] = None) -> bool:
    """Quick check if market is in regular hours"""
    return get_market_hours().is_regular_hours(dt)


def can_enter_short(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Quick check if SHORT entry is allowed"""
    return get_market_hours().can_enter_short(dt)


def should_force_exit_short(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """Quick check if SHORT positions should be force-closed"""
    return get_market_hours().should_force_exit_short(dt)


def get_market_session(dt: Optional[datetime] = None) -> str:
    """Quick check of current market session"""
    return get_market_hours().get_market_session(dt)


if __name__ == "__main__":
    # Test/Demo
    logging.basicConfig(level=logging.INFO)

    market_hours = MarketHours()
    market_hours.log_market_status()

    print("\n" + "=" * 60)
    print("TEST SCENARIOS")
    print("=" * 60)

    # Test different times
    test_times = [
        ("Premarket", datetime_time(8, 0)),
        ("Market Open", datetime_time(9, 30)),
        ("Early Morning", datetime_time(9, 35)),
        ("Mid Day", datetime_time(12, 0)),
        ("Late Afternoon", datetime_time(14, 55)),
        ("Near Deadline", datetime_time(15, 40)),
        ("Past Deadline", datetime_time(15, 50)),
        ("Market Close", datetime_time(16, 0)),
        ("After Hours", datetime_time(17, 0)),
    ]

    for label, test_time in test_times:
        test_dt = datetime.now(market_hours.et_timezone).replace(
            hour=test_time.hour,
            minute=test_time.minute,
            second=0
        )

        can_short, reason = market_hours.can_enter_short(test_dt)
        should_exit, exit_reason = market_hours.should_force_exit_short(test_dt)

        print(f"\n{label} ({test_time.strftime('%H:%M')} ET):")
        print(f"  Can enter SHORT: {'✅' if can_short else '❌'} - {reason}")
        print(f"  Force exit: {'⚠️' if should_exit else '✅'} - {exit_reason}")
