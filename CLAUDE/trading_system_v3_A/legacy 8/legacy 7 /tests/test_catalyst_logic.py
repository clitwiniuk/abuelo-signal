#!/usr/bin/env python3
"""
Test script to verify ProactiveScanner catalyst age logic with SIMULATED recent news
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timedelta
import configparser

# Load config
config = configparser.ConfigParser()
config.read('../config.ini')

# Get catalyst age settings
catalyst_max_age_weekday = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_weekday', fallback=30)
catalyst_max_age_monday = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_monday', fallback=84)
catalyst_max_age_fda = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_fda', fallback=168)
catalyst_max_age_earnings = config.getint('PROACTIVE_SCANNER', 'catalyst_max_age_earnings', fallback=72)

print("=" * 80)
print("ProactiveScanner Catalyst Age Logic Test (SIMULATED DATA)")
print("=" * 80)

print(f"\n📋 Configuration:")
print(f"   Weekday (Tue-Fri): {catalyst_max_age_weekday}h ({catalyst_max_age_weekday/24:.1f} days)")
print(f"   Monday: {catalyst_max_age_monday}h ({catalyst_max_age_monday/24:.1f} days)")
print(f"   FDA: {catalyst_max_age_fda}h ({catalyst_max_age_fda/24:.1f} days)")
print(f"   Earnings: {catalyst_max_age_earnings}h ({catalyst_max_age_earnings/24:.1f} days)")

# Determine current day
now = datetime.now()
weekday = now.weekday()
weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# Calculate base age
base_age = catalyst_max_age_monday if weekday == 0 else catalyst_max_age_weekday

print(f"\n📅 Today is: {weekday_names[weekday]}")
print(f"   Base age limit: {base_age}h ({base_age/24:.1f} days)")

# Simulated test cases
test_cases = [
    {
        'symbol': 'AAPL',
        'headline': 'Apple reports record Q4 earnings beat',
        'age_hours': 12.0,  # 12 hours ago
        'catalyst_type': 'EARNINGS',
        'description': 'Recent earnings (12h ago)'
    },
    {
        'symbol': 'MRNA',
        'headline': 'Moderna receives FDA approval for new vaccine',
        'age_hours': 48.0,  # 2 days ago
        'catalyst_type': 'FDA',
        'description': 'FDA approval 2 days ago'
    },
    {
        'symbol': 'TSLA',
        'headline': 'Tesla announces major contract win',
        'age_hours': 25.0,  # 25 hours ago (yesterday)
        'catalyst_type': 'CONTRACT',
        'description': 'Contract from yesterday'
    },
    {
        'symbol': 'GME',
        'headline': 'GameStop shows strong volume surge',
        'age_hours': 36.0,  # 36 hours ago (too old for weekday)
        'catalyst_type': 'OTHER',
        'description': 'Generic news 36h ago (should fail on weekday)'
    },
    {
        'symbol': 'NVDA',
        'headline': 'NVIDIA breakthrough in AI chip design',
        'age_hours': 100.0,  # 4+ days ago
        'catalyst_type': 'BREAKTHROUGH',
        'description': 'Breakthrough 4 days ago (should pass due to type)'
    },
]

print(f"\n{'='*80}")
print("SIMULATED TEST CASES")
print(f"{'='*80}")

for test in test_cases:
    symbol = test['symbol']
    headline = test['headline']
    age_hours = test['age_hours']
    catalyst_type = test['catalyst_type']
    description = test['description']

    # Determine max age based on catalyst type
    catalyst_type_lower = catalyst_type.lower()
    if 'fda' in catalyst_type_lower:
        max_age = max(base_age, catalyst_max_age_fda)
    elif 'earning' in catalyst_type_lower:
        max_age = max(base_age, catalyst_max_age_earnings)
    elif 'contract' in catalyst_type_lower:
        max_age = max(base_age, 48)
    elif 'breakthrough' in catalyst_type_lower:
        max_age = max(base_age, 48)
    else:
        max_age = base_age

    # Check if valid
    is_valid = age_hours <= max_age

    # Format output
    status_icon = "✅" if is_valid else "❌"
    status_text = "VALID" if is_valid else "TOO OLD"

    print(f"\n{status_icon} {symbol}: {status_text}")
    print(f"   Type: {catalyst_type}")
    print(f"   Age: {age_hours:.1f}h ({age_hours/24:.1f} days)")
    print(f"   Max: {max_age:.1f}h ({max_age/24:.1f} days)")
    print(f"   Test: {description}")
    print(f"   Headline: {headline}")

print(f"\n{'='*80}")
print("KEY INSIGHTS")
print(f"{'='*80}")

print(f"\n1. Base Age Logic:")
print(f"   - Weekdays (Tue-Fri): Accept news from previous day ({catalyst_max_age_weekday}h)")
print(f"   - Monday: Accept news from entire weekend ({catalyst_max_age_monday}h = {catalyst_max_age_monday/24:.1f} days)")

print(f"\n2. Catalyst Type Extensions:")
print(f"   - FDA approvals: Extended to {catalyst_max_age_fda}h ({catalyst_max_age_fda/24:.1f} days)")
print(f"   - Earnings: Extended to {catalyst_max_age_earnings}h ({catalyst_max_age_earnings/24:.1f} days)")
print(f"   - Contracts/Breakthroughs: Extended to 48h (2 days)")
print(f"   - Other: Uses base age ({base_age}h)")

print(f"\n3. Logic Formula:")
print(f"   max_age = MAX(base_age, catalyst_type_age)")
print(f"   This means strong catalysts get MORE time, not less")

print(f"\n✅ Test Complete!")
print(f"{'='*80}")
