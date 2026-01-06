"""
Test script for MarketCalendar functionality.
Verifies holiday detection, market hours, and trading sessions.
"""

from core.market_calendar import get_market_calendar
from datetime import datetime
import pytz

def test_market_calendar():
    """Test all major MarketCalendar features."""
    
    cal = get_market_calendar()
    et_tz = pytz.timezone('America/New_York')
    
    print("=" * 60)
    print("MARKET CALENDAR TEST SUITE")
    print("=" * 60)
    
    # Test 1: Thanksgiving 2025 (the ABVE issue)
    print("\n1. THANKSGIVING 2025 TEST (ABVE Issue)")
    print("-" * 60)
    thanksgiving = et_tz.localize(datetime(2025, 11, 28, 10, 0))  # Nov 28, 2025 10:00 AM
    print(f"Date: {thanksgiving.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
    print(f"Is market day? {cal.is_market_day(thanksgiving)}")
    print(f"Is market open? {cal.is_market_open(thanksgiving)}")
    print(f"Trading session: {cal.get_trading_session(thanksgiving)}")
    
    # Test 2: Day after Thanksgiving (Early Close)
    print("\n2. DAY AFTER THANKSGIVING (Early Close)")
    print("-" * 60)
    black_friday = et_tz.localize(datetime(2025, 11, 29, 10, 0))
    print(f"Date: {black_friday.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
    print(f"Is market day? {cal.is_market_day(black_friday)}")
    print(f"Is early close? {cal.is_early_close(black_friday)}")
    hours = cal.get_market_hours(black_friday)
    if hours:
        print(f"Market hours: {hours['open'].strftime('%I:%M %p')} - {hours['close'].strftime('%I:%M %p')} ET")
    
    # Test 3: Normal trading day
    print("\n3. NORMAL TRADING DAY")
    print("-" * 60)
    normal_day = et_tz.localize(datetime(2025, 12, 1, 14, 30))  # Dec 1, 2025 2:30 PM
    print(f"Date: {normal_day.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
    print(f"Is market day? {cal.is_market_day(normal_day)}")
    print(f"Is market open? {cal.is_market_open(normal_day)}")
    print(f"Trading session: {cal.get_trading_session(normal_day)}")
    hours = cal.get_market_hours(normal_day)
    if hours:
        print(f"Market hours: {hours['open'].strftime('%I:%M %p')} - {hours['close'].strftime('%I:%M %p')} ET")
    
    # Test 4: Pre-market hours
    print("\n4. PRE-MARKET HOURS")
    print("-" * 60)
    premarket = et_tz.localize(datetime(2025, 12, 1, 8, 0))  # 8:00 AM
    print(f"Time: {premarket.strftime('%I:%M %p %Z')}")
    print(f"Trading session: {cal.get_trading_session(premarket)}")
    
    # Test 5: After-hours
    print("\n5. AFTER-HOURS")
    print("-" * 60)
    afterhours = et_tz.localize(datetime(2025, 12, 1, 17, 30))  # 5:30 PM
    print(f"Time: {afterhours.strftime('%I:%M %p %Z')}")
    print(f"Trading session: {cal.get_trading_session(afterhours)}")
    
    # Test 6: Weekend
    print("\n6. WEEKEND (Saturday)")
    print("-" * 60)
    saturday = et_tz.localize(datetime(2025, 11, 30, 10, 0))  # Nov 30, 2025 (Saturday)
    print(f"Date: {saturday.strftime('%Y-%m-%d %A')}")
    print(f"Is market day? {cal.is_market_day(saturday)}")
    print(f"Trading session: {cal.get_trading_session(saturday)}")
    
    # Test 7: 2025 Holidays
    print("\n7. NASDAQ HOLIDAYS 2025")
    print("-" * 60)
    holidays_2025 = cal.get_holidays(2025)
    for holiday in holidays_2025:
        print(f"  - {holiday.strftime('%Y-%m-%d %A')}")
    
    # Test 8: Next market open/close
    print("\n8. NEXT MARKET OPEN/CLOSE (from Thanksgiving)")
    print("-" * 60)
    next_open = cal.get_next_market_open(thanksgiving)
    next_close = cal.get_next_market_close(thanksgiving)
    print(f"Next open: {next_open.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
    print(f"Next close: {next_close.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
    
    # Test 9: Should close position EOD
    print("\n9. POSITION CLOSE RECOMMENDATIONS")
    print("-" * 60)
    test_dates = [
        et_tz.localize(datetime(2025, 11, 26, 15, 0)),  # Day before Thanksgiving
        et_tz.localize(datetime(2025, 11, 29, 12, 0)),  # Black Friday (early close)
        et_tz.localize(datetime(2025, 12, 1, 15, 0)),   # Normal day
    ]
    for test_date in test_dates:
        should_close, reason = cal.should_close_position_eod(test_date)
        print(f"{test_date.strftime('%Y-%m-%d %A')}:")
        print(f"  Should close? {should_close}")
        print(f"  Reason: {reason}")
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    test_market_calendar()
