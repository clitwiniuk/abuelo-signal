
import sys
import os
from datetime import datetime, time
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.market_calendar import get_market_calendar

def test_dec_24_fix():
    print("Testing Dec 24 2025 with FIXED MarketCalendar...")
    calendar = get_market_calendar()
    
    # Create Dec 24 2025 datetime in ET
    et_tz = pytz.timezone('America/New_York')
    target_dt = et_tz.localize(datetime(2025, 12, 24, 10, 0, 0)) # 10 AM ET
    
    print(f"Target Date: {target_dt}")
    
    hours = calendar.get_market_hours(target_dt)
    print(f"Market Hours: Open={hours['open']}, Close={hours['close']}")
    
    is_early = calendar.is_early_close(target_dt)
    print(f"Is Early Close? {is_early}")
    
    if is_early and hours['close'].hour == 13:
        print("✅ SUCCESS: Correctly identified 1:00 PM close!")
    else:
        print("❌ FAILURE: Failed to identify 1:00 PM close.")

if __name__ == "__main__":
    test_dec_24_fix()
