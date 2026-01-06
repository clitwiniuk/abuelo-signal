
import pandas_market_calendars as mcal
from datetime import date
import pandas as pd

nasdaq = mcal.get_calendar('NASDAQ')
target_date = '2025-12-24'
schedule = nasdaq.schedule(start_date=target_date, end_date=target_date)

print(f"Schedule for {target_date}:")
if schedule.empty:
    print("Market CLOSED")
else:
    print(schedule)
    close_time = schedule.iloc[0]['market_close']
    print(f"Close Time: {close_time}")
    print(f"Is Early Close (< 16:00)? {close_time.hour < 16}")
