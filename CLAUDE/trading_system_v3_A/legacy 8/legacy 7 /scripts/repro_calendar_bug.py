
import pandas_market_calendars as mcal
from datetime import datetime
import pytz

# Mimic the logic in core/market_calendar.py
nasdaq = mcal.get_calendar('NASDAQ')
target_date = '2025-12-24'
schedule = nasdaq.schedule(start_date=target_date, end_date=target_date)
close_dt = schedule.iloc[0]['market_close'].to_pydatetime()

print(f"Original Close DT: {close_dt}")
print(f"Original TZ: {close_dt.tzinfo}")
print(f"Hour: {close_dt.hour}")

# Mimic the buggy check
is_early_buggy = close_dt.hour < 16
print(f"Buggy Check (hour < 16): {is_early_buggy}")

# Correct logic
et_tz = pytz.timezone('America/New_York')
close_et = close_dt.astimezone(et_tz)
print(f"Converted to ET: {close_et}")
print(f"ET Hour: {close_et.hour}")
is_early_correct = close_et.hour < 16
print(f"Correct Check (hour < 16): {is_early_correct}")
