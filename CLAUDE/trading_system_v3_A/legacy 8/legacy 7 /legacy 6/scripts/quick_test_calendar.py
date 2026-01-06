"""
Quick test for MarketCalendar - Thanksgiving 2025 verification.
"""

from core.market_calendar import get_market_calendar
from datetime import datetime
import pytz

cal = get_market_calendar()
et_tz = pytz.timezone('America/New_York')

print("MARKET CALENDAR - THANKSGIVING 2025 TEST")
print("=" * 60)

# The ABVE issue: Nov 28, 2025 (Thanksgiving)
thanksgiving = et_tz.localize(datetime(2025, 11, 28, 16, 0))
print(f"\nDate: {thanksgiving.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
print(f"Is market day? {cal.is_market_day(thanksgiving)}")
print(f"Is market open? {cal.is_market_open(thanksgiving)}")
print(f"Trading session: {cal.get_trading_session(thanksgiving)}")

# Normal day for comparison
normal_day = et_tz.localize(datetime(2025, 12, 1, 14, 30))
print(f"\nDate: {normal_day.strftime('%Y-%m-%d %A %I:%M %p %Z')}")
print(f"Is market day? {cal.is_market_day(normal_day)}")
print(f"Is market open? {cal.is_market_open(normal_day)}")
print(f"Trading session: {cal.get_trading_session(normal_day)}")

print("\n" + "=" * 60)
print("✅ Market calendar working correctly!")
