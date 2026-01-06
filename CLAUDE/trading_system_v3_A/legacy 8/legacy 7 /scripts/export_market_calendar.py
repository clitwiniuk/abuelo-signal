"""
Export Market Calendar Data to JSON
Used by Node.js backend to get holidays and market hours.
"""

import json
import sys
from datetime import datetime
from core.market_calendar import get_market_calendar

def export_calendar(year):
    cal = get_market_calendar()
    
    # Get holidays
    holidays = cal.get_holidays(year)
    
    # Get early closes (checking every day of the year)
    # This is a bit expensive but safe. Optimization: check only known potential dates if needed.
    early_closes = []
    
    # We'll check a range of dates for early closes
    # Typically day after Thanksgiving and Christmas Eve
    import pandas as pd
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # Get full schedule
    schedule = cal.nasdaq.schedule(start_date=start_date, end_date=end_date)
    
    # Find early closes (close before 16:00)
    for date, row in schedule.iterrows():
        close_time = row['market_close'].time()
        if close_time.hour < 16:
            early_closes.append({
                'date': date.strftime('%Y-%m-%d'),
                'close_time': close_time.strftime('%H:%M')
            })
            
    # Format holidays
    formatted_holidays = [h.strftime('%Y-%m-%d') for h in holidays]
    
    data = {
        'year': year,
        'holidays': formatted_holidays,
        'early_closes': early_closes
    }
    
    print(json.dumps(data))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        year = int(sys.argv[1])
    else:
        year = datetime.now().year
        
    export_calendar(year)
