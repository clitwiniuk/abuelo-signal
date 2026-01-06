"""
Test to verify End-of-Day exit time is correctly centralized in config.ini
"""

import configparser
import os
from strategies.workers.worker_stop_manager import create_worker_stop_manager


def test_eod_time_centralization():
    """Verify that EOD exit time is read from config.ini correctly"""

    print("\n" + "="*60)
    print("TEST: End-of-Day Exit Time Configuration")
    print("="*60)

    # Read config.ini
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'config.ini'
    )
    config = configparser.ConfigParser()
    config.read(config_path)

    # Get configured EOD time
    eod_time_str = config.get('GLOBAL', 'end_of_day_exit_time', fallback='15:58')
    print(f"\n📋 Config.ini setting:")
    print(f"   end_of_day_exit_time = {eod_time_str}")

    # Convert to decimal
    hours, minutes = map(int, eod_time_str.split(':'))
    expected_decimal = hours + (minutes / 60.0)
    print(f"   Decimal format: {expected_decimal:.4f} hours")
    print(f"   Time in Spain: {hours+6}:{minutes:02d} (ET+6)")

    # Create WorkerStopManager for each day trading worker
    workers = [
        'GAP_GO_STRATEGY',
        'MACDV_STRATEGY',
        'BULL_FLAG_STRATEGY',
        'DAILY_PLAYS_STRATEGY'
    ]

    print(f"\n🔍 Testing {len(workers)} day trading workers:")
    print("-" * 60)

    all_correct = True
    for worker_name in workers:
        stop_manager = create_worker_stop_manager(config, worker_name)
        actual_decimal = stop_manager.config.end_of_day_hour

        is_correct = abs(actual_decimal - expected_decimal) < 0.01
        status = "✅" if is_correct else "❌"

        print(f"{status} {worker_name:25} -> EOD: {actual_decimal:.4f}")

        if not is_correct:
            all_correct = False
            print(f"   ⚠️ Expected: {expected_decimal:.4f}, Got: {actual_decimal:.4f}")

    print("-" * 60)

    # Summary
    print("\n📊 VERIFICATION SUMMARY:")
    print(f"   Config value: {eod_time_str} ({expected_decimal:.4f} decimal)")
    print(f"   Spain time: {hours+6}:{minutes:02d}")
    print(f"   All workers using centralized config: {'✅ YES' if all_correct else '❌ NO'}")

    print("\n" + "="*60)

    if all_correct:
        print("🎉 SUCCESS - All workers use centralized EOD time from config.ini")
    else:
        print("❌ FAILURE - Some workers have hardcoded EOD times")

    print("="*60 + "\n")

    assert all_correct, "Not all workers are using centralized EOD configuration"


if __name__ == "__main__":
    test_eod_time_centralization()
