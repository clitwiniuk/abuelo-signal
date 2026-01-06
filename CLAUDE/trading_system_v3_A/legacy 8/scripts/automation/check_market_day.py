#!/usr/bin/env python3
"""
Market Day Checker - CLI Helper for Supervisor Script
======================================================

Provides command-line interface to market_calendar.py for bash scripts.

Usage:
    python check_market_day.py is_market_day
    python check_market_day.py get_close_time
    python check_market_day.py get_next_trading_day
    python check_market_day.py is_early_close

Exit Codes:
    0 - Success (market is open / command succeeded)
    1 - Failure (market is closed / command failed)
"""

import sys
import os
from datetime import datetime, time
import pytz

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from core.market_calendar import get_market_calendar
except ImportError as e:
    print(f"Error importing market_calendar: {e}", file=sys.stderr)
    print("Make sure pandas_market_calendars is installed:", file=sys.stderr)
    print("  pip install pandas_market_calendars", file=sys.stderr)
    sys.exit(1)


def is_market_day():
    """
    Check if today is a trading day

    Returns:
        Exit 0 if market is open today
        Exit 1 if market is closed (holiday/weekend)
    """
    try:
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)

        if calendar.is_market_day(now):
            # Market is open
            return 0
        else:
            # Market is closed (holiday/weekend)
            return 1

    except Exception as e:
        print(f"Error checking market day: {e}", file=sys.stderr)
        return 1  # Assume closed on error


def get_close_time():
    """
    Get market close time for today (handles early closes)

    Prints:
        Hour (int) when market closes (e.g., "16" for 4:00 PM, "13" for 1:00 PM early close)

    Returns:
        Exit 0 on success
        Exit 1 on error
    """
    try:
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)

        # Check if today is a trading day
        if not calendar.is_market_day(now):
            return 1  # Not a trading day

        # Get market hours
        hours = calendar.get_market_hours(now)
        if not hours:
            return 1  # No hours available

        # Extract close hour
        close_hour = hours['close'].hour
        print(close_hour)
        return 0

    except Exception as e:
        print(f"Error getting close time: {e}", file=sys.stderr)
        return 1


def get_next_trading_day():
    """
    Get the next trading day date

    Prints:
        Date in YYYY-MM-DD format

    Returns:
        Exit 0 on success
        Exit 1 on error
    """
    try:
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)

        next_open = calendar.get_next_market_open(now)
        print(next_open.strftime('%Y-%m-%d'))
        return 0

    except Exception as e:
        print(f"Error getting next trading day: {e}", file=sys.stderr)
        return 1


def is_early_close():
    """
    Check if today is an early close day

    Returns:
        Exit 0 if early close (closes before 4:00 PM)
        Exit 1 if normal close or not a trading day
    """
    try:
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)

        if calendar.is_early_close(now):
            return 0  # Early close
        else:
            return 1  # Normal close or not trading day

    except Exception as e:
        print(f"Error checking early close: {e}", file=sys.stderr)
        return 1


def get_holidays():
    """
    Get holidays for current year

    Prints:
        One holiday per line in YYYY-MM-DD format

    Returns:
        Exit 0 on success
        Exit 1 on error
    """
    try:
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)

        holidays = calendar.get_holidays(now.year)
        for holiday in holidays:
            print(holiday.strftime('%Y-%m-%d'))
        return 0

    except Exception as e:
        print(f"Error getting holidays: {e}", file=sys.stderr)
        return 1


def print_usage():
    """Print usage information"""
    print("Usage: check_market_day.py <command>")
    print("")
    print("Commands:")
    print("  is_market_day         - Check if today is a trading day (exit 0=yes, 1=no)")
    print("  get_close_time        - Get market close hour for today (prints hour)")
    print("  get_next_trading_day  - Get next trading day (prints YYYY-MM-DD)")
    print("  is_early_close        - Check if early close today (exit 0=yes, 1=no)")
    print("  get_holidays          - Get all holidays for current year")
    print("")
    print("Examples:")
    print("  # Check if market is open today")
    print("  python check_market_day.py is_market_day && echo 'Market is open'")
    print("")
    print("  # Get close time")
    print("  CLOSE_HOUR=$(python check_market_day.py get_close_time)")
    print("  echo \"Market closes at ${CLOSE_HOUR}:00 ET\"")


def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1].lower()

    commands = {
        'is_market_day': is_market_day,
        'get_close_time': get_close_time,
        'get_next_trading_day': get_next_trading_day,
        'is_early_close': is_early_close,
        'get_holidays': get_holidays,
    }

    if command in commands:
        return commands[command]()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main())
