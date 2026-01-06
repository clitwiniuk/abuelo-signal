#!/usr/bin/env python3
"""
Debug Red to Green Scanner Timing
Check what values the scanner is actually using
"""

import sys
import os
import pytz
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_r2g_timing():
    """Debug R2G scanner timing parameters and current time"""
    print("🔴➡️🟢 Red to Green Timing Debug")
    print("=" * 50)

    try:
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner

        # Create scanner instance
        scanner = RedToGreenScanner(ibkr_adapter=None)

        # Show configured parameters
        print("📋 Configured Parameters:")
        print(f"   scan_start_hour: {scanner.scan_params.get('scan_start_hour', 'NOT_SET')}")
        print(f"   scan_end_hour: {scanner.scan_params.get('scan_end_hour', 'NOT_SET')}")
        print(f"   skip_scanning_outside_hours: {scanner.scan_params.get('skip_scanning_outside_hours', 'NOT_SET')}")

        # Show current times
        print("\n🕐 Current Times:")

        # Local time (Spain)
        local_time = datetime.now()
        local_hour = local_time.hour + local_time.minute / 60.0
        print(f"   Local (Spain): {local_time.strftime('%H:%M:%S %Z')} = {local_hour:.2f}")

        # US Eastern time
        try:
            eastern = pytz.timezone('US/Eastern')
            eastern_time = datetime.now(eastern)
            eastern_hour = eastern_time.hour + eastern_time.minute / 60.0
            print(f"   US Eastern: {eastern_time.strftime('%H:%M:%S %Z')} = {eastern_hour:.2f}")
        except Exception as e:
            print(f"   US Eastern: ERROR - {e}")

        # Test should_scan_now
        print("\n🔍 Scanner Logic Test:")
        should_scan = scanner._should_scan_now()
        print(f"   should_scan_now(): {should_scan}")

        # Manual calculation
        scan_start = scanner.scan_params.get('scan_start_hour', 9.0)
        scan_end = scanner.scan_params.get('scan_end_hour', 14.0)

        try:
            eastern = pytz.timezone('US/Eastern')
            current_time = datetime.now(eastern)
            current_hour = current_time.hour + current_time.minute / 60.0
            is_weekday = current_time.weekday() < 5
            is_within_hours = scan_start <= current_hour <= scan_end

            print(f"   Manual calculation:")
            print(f"     Current hour (Eastern): {current_hour:.2f}")
            print(f"     Scan window: {scan_start} - {scan_end}")
            print(f"     Within hours: {is_within_hours}")
            print(f"     Is weekday: {is_weekday}")
            print(f"     Should scan: {is_within_hours and is_weekday}")

        except Exception as e:
            print(f"   Manual calculation ERROR: {e}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    debug_r2g_timing()