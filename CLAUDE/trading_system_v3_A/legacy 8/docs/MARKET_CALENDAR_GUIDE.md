# Market Calendar Integration Guide

## Overview

The `market_calendar.py` module provides comprehensive NASDAQ market hours and holiday detection using `pandas_market_calendars`.

## Installation

```bash
pip install pandas_market_calendars
```

## Basic Usage

### Quick Checks

```python
from core.market_calendar import is_market_open, get_trading_session, is_market_day
from datetime import datetime

# Check if market is open right now
if is_market_open():
    print("Market is open!")

# Get current trading session
session = get_trading_session()  # Returns: 'premarket', 'regular', 'afterhours', or 'closed'

# Check if a specific date is a trading day
date = datetime(2025, 11, 28)  # Thanksgiving
if not is_market_day(date):
    print("Market is closed - holiday!")
```

### Advanced Usage

```python
from core.market_calendar import get_market_calendar
from datetime import datetime
import pytz

cal = get_market_calendar()
et_tz = pytz.timezone('America/New_York')

# Check market hours for a specific date
date = et_tz.localize(datetime(2025, 12, 1, 10, 0))
hours = cal.get_market_hours(date)
if hours:
    print(f"Market open: {hours['open']}")
    print(f"Market close: {hours['close']}")

# Detect early close days
if cal.is_early_close(date):
    print("Market closes early today!")

# Get next market open/close
next_open = cal.get_next_market_open()
next_close = cal.get_next_market_close()

# Check if positions should be closed EOD
should_close, reason = cal.should_close_position_eod()
if should_close:
    print(f"Close positions: {reason}")
```

## Integration with Trading System

### Example: Order Execution Validation

```python
from core.market_calendar import get_market_calendar

def execute_order(symbol, side, quantity):
    cal = get_market_calendar()
    
    # Validate market is open
    if not cal.is_market_open_now():
        session = cal.get_trading_session()
        if session == 'closed':
            next_open = cal.get_next_market_open()
            raise ValueError(f"Market is closed. Next open: {next_open}")
        elif session == 'premarket':
            print("Warning: Executing in pre-market hours")
        elif session == 'afterhours':
            print("Warning: Executing in after-hours")
    
    # Check for early close
    from datetime import datetime
    if cal.is_early_close(datetime.now()):
        print("Warning: Market closes early today")
    
    # Execute order...
    pass
```

### Example: Swing Trade Detection

```python
from core.market_calendar import get_market_calendar
from datetime import datetime, timedelta

def should_hold_overnight(current_time):
    cal = get_market_calendar()
    
    # Check if tomorrow is a holiday
    tomorrow = current_time + timedelta(days=1)
    if cal.is_holiday(tomorrow):
        return False, f"Tomorrow is a holiday: {tomorrow.strftime('%Y-%m-%d')}"
    
    # Check if today is early close
    if cal.is_early_close(current_time):
        return False, "Early close today - avoid overnight risk"
    
    return True, "Safe to hold overnight"
```

## Features

- ✅ **Holiday Detection**: Automatically detects all NASDAQ holidays (Thanksgiving, Christmas, etc.)
- ✅ **Early Close Detection**: Identifies days with early market close (1:00 PM ET)
- ✅ **Trading Sessions**: Classifies time as premarket, regular, afterhours, or closed
- ✅ **Future-Proof**: Works for all years (2025-2099) with automatic rule-based calculation
- ✅ **Timezone Aware**: All times in Eastern Time (ET)

## NASDAQ Holidays (Annual)

- New Year's Day
- Martin Luther King Jr. Day
- Presidents' Day
- Good Friday
- Memorial Day
- Independence Day
- Labor Day
- Thanksgiving
- Christmas

## Early Close Days

- Day after Thanksgiving (1:00 PM ET close)
- Christmas Eve (if on weekday, 1:00 PM ET close)

## Performance Note

The first time you use the calendar, it may take 10-20 seconds to download calendar data. Subsequent uses are instant.
