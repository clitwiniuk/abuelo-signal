"""
Market Calendar Utility
Handles NASDAQ market hours, holidays, and trading session validation.
Uses pandas_market_calendars for accurate, future-proof calendar data.
"""

import pandas_market_calendars as mcal
from datetime import datetime, time, timedelta
import pytz
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class MarketCalendar:
    """
    Centralized market calendar for NASDAQ trading hours and holidays.
    
    Features:
    - Holiday detection (Thanksgiving, Christmas, etc.)
    - Early close detection (day after Thanksgiving, Christmas Eve)
    - Market hours validation (pre-market, regular, after-hours)
    - Trading session classification
    """
    
    def __init__(self):
        """Initialize NASDAQ calendar and timezone."""
        self.nasdaq = mcal.get_calendar('NASDAQ')
        self.et_tz = pytz.timezone('America/New_York')
        
        # Standard market hours (Eastern Time)
        self.PREMARKET_OPEN = time(4, 0)   # 4:00 AM ET
        self.PREMARKET_CLOSE = time(9, 30) # 9:30 AM ET
        self.REGULAR_OPEN = time(9, 30)    # 9:30 AM ET
        self.REGULAR_CLOSE = time(16, 0)   # 4:00 PM ET
        self.AFTERHOURS_OPEN = time(16, 0) # 4:00 PM ET
        self.AFTERHOURS_CLOSE = time(20, 0) # 8:00 PM ET
        
        # Early close time (e.g., day after Thanksgiving)
        self.EARLY_CLOSE = time(13, 0)     # 1:00 PM ET
        
        # Load overrides
        self.overrides = self._load_config_overrides()
        
        logger.info("MarketCalendar initialized with NASDAQ schedule (ET Timezone Fixed)")

    def _load_config_overrides(self) -> dict:
        """Load manual overrides from config.ini if present."""
        try:
            import configparser
            import os
            
            # Look for config.ini in common locations
            paths = ['config.ini', '../config.ini', '../../config.ini']
            config_path = None
            for p in paths:
                if os.path.exists(p):
                    config_path = p
                    break
            
            if not config_path:
                return {}
                
            config = configparser.ConfigParser()
            config.read(config_path)
            
            if 'CALENDAR_OVERRIDE' in config:
                section = config['CALENDAR_OVERRIDE']
                return {
                    'force_early_close': section.getboolean('force_early_close', fallback=False),
                    'force_close_time': section.get('force_close_time', fallback=None),
                    'force_holiday': section.getboolean('force_holiday', fallback=False)
                }
            return {}
        except Exception as e:
            logger.warning(f"Failed to load calendar overrides: {e}")
            return {}

    
    def is_market_day(self, date: datetime) -> bool:
        """
        Check if a given date is a valid trading day.
        
        Args:
            date: datetime object to check
            
        Returns:
            bool: True if market is open on this date
        """
        schedule = self.nasdaq.schedule(start_date=date.date(), end_date=date.date())
        return not schedule.empty
    
    def is_market_open_now(self) -> bool:
        """
        Check if the market is currently open (regular hours).
        
        Returns:
            bool: True if market is open right now
        """
        now = datetime.now(self.et_tz)
        return self.is_market_open(now)
    
    def is_market_open(self, dt: datetime) -> bool:
        """
        Check if the market is open at a specific datetime.

        Args:
            dt: datetime to check (will be converted to ET if needed)

        Returns:
            bool: True if market is open at this time
        """
        # Ensure datetime is in ET timezone
        if dt.tzinfo is None:
            dt = self.et_tz.localize(dt)
        else:
            dt = dt.astimezone(self.et_tz)

        # Check if it's a valid trading day
        schedule = self.nasdaq.schedule(start_date=dt.date(), end_date=dt.date())
        if schedule.empty:
            return False

        # Check if current time is within market hours
        try:
            return self.nasdaq.open_at_time(schedule, dt)
        except Exception as e:
            # If timestamp is not covered by schedule, fall back to manual time check
            logger.warning(f"open_at_time failed for {dt}: {e}. Using fallback time check.")
            market_open = schedule.iloc[0]['market_open'].to_pydatetime()
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            return market_open <= dt <= market_close
    
    def get_market_hours(self, date: datetime) -> Optional[Dict[str, datetime]]:
        """
        Get market open and close times for a specific date.
        
        Args:
            date: datetime object for the date to check
            
        Returns:
            # dict with 'open' and 'close' datetime objects (ET), or None if market is closed
        """
        # Check overrides first
        if self.overrides.get('force_holiday'):
            logger.info("OVERRIDE: Forcing holiday status")
            return None

        schedule = self.nasdaq.schedule(start_date=date.date(), end_date=date.date())
        if schedule.empty:
            return None
        
        # FIX: Convert UTC from pandas_market_calendars to ET explicitly
        market_open_utc = schedule.iloc[0]['market_open'].to_pydatetime()
        market_close_utc = schedule.iloc[0]['market_close'].to_pydatetime()
        
        # Convert to ET
        if market_open_utc.tzinfo is None:
            market_open_utc = pytz.utc.localize(market_open_utc)
        market_open_et = market_open_utc.astimezone(self.et_tz)
        
        if market_close_utc.tzinfo is None:
            market_close_utc = pytz.utc.localize(market_close_utc)
        market_close_et = market_close_utc.astimezone(self.et_tz)
        
        # Apply manual close time override if set and check logic matches
        if self.overrides.get('force_early_close') and self.overrides.get('force_close_time'):
             try:
                 override_time_str = self.overrides.get('force_close_time')
                 # Parse HH:MM
                 h, m = map(int, override_time_str.split(':'))
                 # Replace time component of close_et
                 market_close_et = market_close_et.replace(hour=h, minute=m, second=0, microsecond=0)
                 logger.info(f"OVERRIDE: Enforcing close time {market_close_et}")
             except Exception as e:
                 logger.error(f"Failed to apply override time: {e}")

        return {
            'open': market_open_et,
            'close': market_close_et
        }
    
    def is_early_close(self, date: datetime) -> bool:
        """
        Check if a date has an early market close (e.g., 1:00 PM instead of 4:00 PM).
        
        Args:
            date: datetime to check
            
        Returns:
            bool: True if market closes early on this date
        """
        hours = self.get_market_hours(date)
        if not hours:
            return False
        
        close_time = hours['close'].time()
        # Early close is typically 1:00 PM ET (13:00)
        return close_time.hour < 16
    
    def get_trading_session(self, dt: Optional[datetime] = None) -> str:
        """
        Determine the current trading session.
        
        Args:
            dt: datetime to check (defaults to now)
            
        Returns:
            str: 'premarket', 'regular', 'afterhours', or 'closed'
        """
        if dt is None:
            dt = datetime.now(self.et_tz)
        elif dt.tzinfo is None:
            dt = self.et_tz.localize(dt)
        else:
            dt = dt.astimezone(self.et_tz)
        
        # Check if it's a valid trading day
        if not self.is_market_day(dt):
            return 'closed'
        
        current_time = dt.time()
        
        # Check for early close
        if self.is_early_close(dt):
            early_close = self.EARLY_CLOSE
            if self.REGULAR_OPEN <= current_time < early_close:
                return 'regular'
            elif early_close <= current_time < self.AFTERHOURS_CLOSE:
                return 'afterhours'
        else:
            # Normal trading hours
            if self.PREMARKET_OPEN <= current_time < self.PREMARKET_CLOSE:
                return 'premarket'
            elif self.REGULAR_OPEN <= current_time < self.REGULAR_CLOSE:
                return 'regular'
            elif self.AFTERHOURS_OPEN <= current_time < self.AFTERHOURS_CLOSE:
                return 'afterhours'
        
        return 'closed'
    
    def get_next_market_open(self, from_date: Optional[datetime] = None) -> datetime:
        """
        Get the next market open datetime.
        
        Args:
            from_date: starting point (defaults to now)
            
        Returns:
            datetime: next market open time
        """
        if from_date is None:
            from_date = datetime.now(self.et_tz)
        elif from_date.tzinfo is None:
            from_date = self.et_tz.localize(from_date)
        
        # Get schedule for next 10 days
        end_date = from_date + timedelta(days=10)
        schedule = self.nasdaq.schedule(start_date=from_date.date(), end_date=end_date.date())
        
        if schedule.empty:
            raise ValueError("No market open found in next 10 days")
        
        # Find first open after from_date
        for idx, row in schedule.iterrows():
            market_open = row['market_open'].to_pydatetime()
            if market_open > from_date:
                return market_open
        
        raise ValueError("No market open found in next 10 days")
    
    def get_next_market_close(self, from_date: Optional[datetime] = None) -> datetime:
        """
        Get the next market close datetime.
        
        Args:
            from_date: starting point (defaults to now)
            
        Returns:
            datetime: next market close time
        """
        if from_date is None:
            from_date = datetime.now(self.et_tz)
        elif from_date.tzinfo is None:
            from_date = self.et_tz.localize(from_date)
        
        # Get schedule for next 10 days
        end_date = from_date + timedelta(days=10)
        schedule = self.nasdaq.schedule(start_date=from_date.date(), end_date=end_date.date())
        
        if schedule.empty:
            raise ValueError("No market close found in next 10 days")
        
        # Find first close after from_date
        for idx, row in schedule.iterrows():
            market_close = row['market_close'].to_pydatetime()
            if market_close > from_date:
                return market_close
        
        raise ValueError("No market close found in next 10 days")
    
    def is_holiday(self, date: datetime) -> bool:
        """
        Check if a date is a market holiday.
        
        Args:
            date: datetime to check
            
        Returns:
            bool: True if it's a holiday
        """
        return not self.is_market_day(date)
    
    def get_holidays(self, year: int) -> list:
        """
        Get all market holidays for a specific year.
        
        Args:
            year: year to get holidays for
            
        Returns:
            list of datetime objects for holidays
        """
        import pandas as pd
        holidays = self.nasdaq.holidays().holidays
        # Convert numpy datetime64 to Python datetime
        year_holidays = [pd.Timestamp(h).to_pydatetime().date() for h in holidays 
                        if pd.Timestamp(h).year == year]
        return sorted(year_holidays)
    
    def should_close_position_eod(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Determine if positions should be closed at end of day.
        Useful for detecting early closes or holidays.
        
        Args:
            dt: datetime to check (defaults to now)
            
        Returns:
            tuple: (should_close, reason)
        """
        if dt is None:
            dt = datetime.now(self.et_tz)
        
        # Check if tomorrow is a holiday
        tomorrow = dt + timedelta(days=1)
        if self.is_holiday(tomorrow):
            return True, f"Tomorrow is a holiday ({tomorrow.strftime('%Y-%m-%d')})"
        
        # Check if today is an early close
        if self.is_early_close(dt):
            return True, f"Early close today at {self.EARLY_CLOSE.strftime('%I:%M %p')} ET"
        
        return False, "Normal trading day"


# Singleton instance
_market_calendar_instance = None

def get_market_calendar() -> MarketCalendar:
    """Get singleton instance of MarketCalendar."""
    global _market_calendar_instance
    if _market_calendar_instance is None:
        _market_calendar_instance = MarketCalendar()
    return _market_calendar_instance


# Convenience functions
def is_market_open() -> bool:
    """Quick check if market is currently open."""
    return get_market_calendar().is_market_open_now()

def get_trading_session() -> str:
    """Quick check of current trading session."""
    return get_market_calendar().get_trading_session()

def is_market_day(date: datetime) -> bool:
    """Quick check if date is a trading day."""
    return get_market_calendar().is_market_day(date)
