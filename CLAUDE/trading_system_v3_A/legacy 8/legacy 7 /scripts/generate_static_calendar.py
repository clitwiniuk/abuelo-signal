"""
Generate Static Market Calendar JSON
Generates a JSON file with market holidays and early closes for a range of years.
This allows the Node.js backend to serve calendar data without needing Python runtime.
"""

import json
import pandas_market_calendars as mcal
from datetime import datetime, time

def generate_static_calendar(start_year, end_year, output_file):
    print(f"Generating calendar from {start_year} to {end_year}...")
    
    nasdaq = mcal.get_calendar('NASDAQ')
    calendar_data = {}
    
    for year in range(start_year, end_year + 1):
        print(f"Processing {year}...")
        
        # Get holidays
        import pandas as pd
        holidays = nasdaq.holidays().holidays
        year_holidays = [pd.Timestamp(h).to_pydatetime().date() for h in holidays 
                        if pd.Timestamp(h).year == year]
        formatted_holidays = [h.strftime('%Y-%m-%d') for h in sorted(year_holidays)]
        
        # Get early closes
        early_closes = []
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        schedule = nasdaq.schedule(start_date=start_date, end_date=end_date)
        
        for date, row in schedule.iterrows():
            close_time = row['market_close'].time()
            if close_time.hour < 16:
                early_closes.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'close_time': close_time.strftime('%H:%M')
                })
        
        calendar_data[year] = {
            'holidays': formatted_holidays,
            'early_closes': early_closes
        }
    
    # Save to file
    with open(output_file, 'w') as f:
        json.dump(calendar_data, f, indent=2)
        
    print(f"✅ Calendar data saved to {output_file}")

if __name__ == "__main__":
    # Generate for 2024-2030
    output_path = "tradetally/backend/src/data/market_calendar.json"
    generate_static_calendar(2024, 2030, output_path)
