#!/usr/bin/env python3
"""
Test Red to Green Timing Optimization
Verify that R2G scanner respects trading hours for resource optimization
"""

import sys
import os
import asyncio
from datetime import datetime, time
from unittest.mock import patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_r2g_timing_logic():
    """Test R2G scanner timing optimization logic"""
    print("⏰ Testing Red to Green Timing Optimization...")

    try:
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner

        # Create scanner instance
        scanner = RedToGreenScanner(ibkr_adapter=None)  # Mock adapter

        print("✅ R2G Scanner instantiated successfully")

        # Test different times
        test_cases = [
            # (hour, minute, weekday, should_scan, description)
            (8, 30, 1, False, "Before market hours (8:30 AM Tuesday)"),
            (9, 0, 1, True, "Market pre-open (9:00 AM Tuesday)"),
            (10, 30, 1, True, "Optimal window (10:30 AM Tuesday)"),
            (12, 0, 1, True, "Midday (12:00 PM Tuesday)"),
            (14, 0, 1, True, "End of scan window (2:00 PM Tuesday)"),
            (15, 30, 1, False, "After scan window (3:30 PM Tuesday)"),
            (20, 0, 1, False, "Evening (8:00 PM Tuesday)"),
            (10, 30, 5, False, "Weekend (10:30 AM Saturday)"),
            (10, 30, 6, False, "Weekend (10:30 AM Sunday)"),
        ]

        passed = 0
        failed = 0

        for hour, minute, weekday, expected, description in test_cases:
            # Mock datetime to test different times
            mock_datetime = datetime(2024, 1, 1 + weekday, hour, minute)  # 2024-01-01 is Monday

            with patch('scanner.red_to_green.red_to_green_scanner.datetime') as mock_dt:
                mock_dt.now.return_value = mock_datetime

                # Test the timing logic
                result = scanner._should_scan_now()

                status = "✅ PASS" if result == expected else "❌ FAIL"
                print(f"   {status} - {description}: Expected {expected}, Got {result}")

                if result == expected:
                    passed += 1
                else:
                    failed += 1

        print(f"\n📊 Timing Tests: {passed} passed, {failed} failed")
        return failed == 0

    except Exception as e:
        print(f"❌ Error testing timing logic: {e}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        return False

async def test_scan_optimization():
    """Test that scan skips when outside hours"""
    print("\n🔍 Testing Scan Optimization...")

    try:
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner

        # Create scanner instance
        scanner = RedToGreenScanner(ibkr_adapter=None)

        # Test scanning outside hours (should return empty list immediately)
        mock_datetime = datetime(2024, 1, 1, 20, 0)  # 8:00 PM Monday

        with patch('scanner.red_to_green.red_to_green_scanner.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime

            # This should return empty list without processing symbols
            result = await scanner.scan_r2g_candidates(['AAPL', 'TSLA', 'NVDA'])

            if len(result) == 0:
                print("✅ Scanner correctly skipped processing outside hours")
                return True
            else:
                print(f"❌ Scanner processed {len(result)} results when it should have skipped")
                return False

    except Exception as e:
        print(f"❌ Error testing scan optimization: {e}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        return False

def test_configuration_override():
    """Test that timing optimization can be disabled"""
    print("\n⚙️ Testing Configuration Override...")

    try:
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner

        # Create scanner with optimization disabled
        scanner = RedToGreenScanner(ibkr_adapter=None)
        scanner.scan_params['skip_scanning_outside_hours'] = False

        # Test scanning outside hours with optimization disabled
        mock_datetime = datetime(2024, 1, 1, 20, 0)  # 8:00 PM Monday

        with patch('scanner.red_to_green.red_to_green_scanner.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime

            # Should return True even outside hours when optimization disabled
            result = scanner._should_scan_now()

            if result:
                print("✅ Scanner correctly ignores timing when optimization disabled")
                return True
            else:
                print("❌ Scanner still respects timing when optimization should be disabled")
                return False

    except Exception as e:
        print(f"❌ Error testing configuration override: {e}")
        return False

def show_current_timing_status():
    """Show current timing status for debugging"""
    print("\n📅 Current Timing Status:")

    try:
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner

        scanner = RedToGreenScanner(ibkr_adapter=None)

        current_time = datetime.now()
        current_hour = current_time.hour + current_time.minute / 60.0
        is_weekday = current_time.weekday() < 5
        should_scan = scanner._should_scan_now()

        print(f"   Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Decimal Hour: {current_hour:.2f}")
        print(f"   Weekday: {is_weekday}")
        print(f"   Scan Window: {scanner.scan_params['scan_start_hour']:.1f} - {scanner.scan_params['scan_end_hour']:.1f}")
        print(f"   Should Scan: {should_scan}")

        return True

    except Exception as e:
        print(f"❌ Error showing timing status: {e}")
        return False

async def main():
    """Run all R2G timing optimization tests"""
    print("🚀 Red to Green Timing Optimization Test Suite")
    print("=" * 60)

    tests = [
        ("Timing Logic Test", test_r2g_timing_logic),
        ("Scan Optimization Test", test_scan_optimization),
        ("Configuration Override Test", test_configuration_override),
        ("Current Status Check", show_current_timing_status),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")

    passed = 0
    failed = 0

    for test_name, result in results:
        if test_name == "Current Status Check":
            continue  # Skip in summary as it's informational

        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n🎯 Total: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All timing optimization tests PASSED!")
        print("⏰ R2G Scanner will optimize resource usage by respecting trading hours!")
    else:
        print("⚠️ Some tests failed. Please check the timing implementation.")

    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)