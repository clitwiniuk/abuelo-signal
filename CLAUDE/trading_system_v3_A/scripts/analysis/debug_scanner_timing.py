#!/usr/bin/env python3
"""
Debug scanner timing in real-time
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import logging

def debug_timing():
    """Debug the timing logic with real scanner data"""
    print("🕐 Scanner Timing Debug")
    print("=" * 50)
    
    # Parse the log timestamp when tickers were processed
    processed_time = datetime.strptime("2025-08-28 14:58:21", "%Y-%m-%d %H:%M:%S")
    current_time = datetime.now()
    
    print(f"Processed time: {processed_time}")
    print(f"Current time:   {current_time}")
    
    time_diff_minutes = (current_time - processed_time).total_seconds() / 60
    print(f"Time difference: {time_diff_minutes:.2f} minutes")
    
    # Test cooldown logic
    cooldown_minutes = 20
    print(f"Required cooldown: {cooldown_minutes} minutes")
    
    if time_diff_minutes >= cooldown_minutes:
        print("✅ Should be READY for re-analysis")
    else:
        remaining = cooldown_minutes - time_diff_minutes
        print(f"⏱️ Still in cooldown ({remaining:.1f} minutes left)")
    
    print("\n🔍 Testing edge cases:")
    # Test with slightly different times
    test_times = [
        datetime.strptime("2025-08-28 14:58:21", "%Y-%m-%d %H:%M:%S"),
        datetime.strptime("2025-08-28 15:17:05", "%Y-%m-%d %H:%M:%S"),
        datetime.strptime("2025-08-28 15:18:19", "%Y-%m-%d %H:%M:%S"),
    ]
    
    for i, test_time in enumerate(test_times, 1):
        diff = (test_time - processed_time).total_seconds() / 60
        status = "✅ READY" if diff >= cooldown_minutes else f"⏱️ COOLDOWN ({cooldown_minutes - diff:.1f}min left)"
        print(f"  Test {i} ({test_time.strftime('%H:%M:%S')}): {diff:.2f}min - {status}")

if __name__ == "__main__":
    debug_timing()