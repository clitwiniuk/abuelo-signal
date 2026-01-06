#!/usr/bin/env python3
"""
Verify Market Hours Tool
========================
Checks the current market status, open/close times, and detects early closes.
Useful for verifying if the system correctly identifies half-days or holidays.

Usage:
    python3 verify_market_hours.py
"""

import sys
import os
import pytz
from datetime import datetime

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.market_calendar import get_market_calendar

def main():
    print("=" * 50)
    print("🗓️  MARKET HOURS VERIFICATION TOOL")
    print("=" * 50)
    
    try:
        # Initialize calendar
        calendar = get_market_calendar()
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        print(f"Current Time (ET):   {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("-" * 50)
        
        # Check if today is a trading day
        is_open_day = calendar.is_market_day(now)
        print(f"Is Trading Day:      {'✅ YES' if is_open_day else '❌ NO'}")
        
        if is_open_day:
            hours = calendar.get_market_hours(now)
            if hours:
                open_time = hours['open'].strftime('%H:%M %p')
                close_time = hours['close'].strftime('%H:%M %p')
                print(f"Market Open:         {open_time} ET")
                print(f"Market Close:        {close_time} ET")
                
                # Check early close
                is_early = calendar.is_early_close(now)
                print(f"Early Close:         {'⚠️ YES' if is_early else 'No'}")
                
                # Check current session
                session = calendar.get_trading_session(now)
                print(f"Current Session:     {session.upper()}")
            else:
                print("Error: Could not retrieve market hours.")
        else:
            print("Reason: Holiday or Weekend")

        print("-" * 50)
        
        # Check overrides
        if hasattr(calendar, 'overrides') and calendar.overrides:
            print("🔧 MONITORING OVERRIDES ACTIVE:")
            for k, v in calendar.overrides.items():
                if v:
                    print(f"   - {k}: {v}")
        else:
            print("No manual overrides active in config.ini")

        print("=" * 50)

    except Exception as e:
        print(f"❌ Error verifying market hours: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
