#!/usr/bin/env python3
"""
Quick test to verify ProactiveScanner config loading
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config_manager import ConfigManager
from scanner.smallcap.proactive_scanner import ProactiveScanner
from datetime import datetime

def test_config_loading():
    """Test that ProactiveScanner loads config correctly"""

    # Load config
    config_manager = ConfigManager()
    config = config_manager.config

    print("=" * 80)
    print("ProactiveScanner Configuration Test")
    print("=" * 80)

    # Check if PROACTIVE_SCANNER section exists
    if 'PROACTIVE_SCANNER' in config:
        print("\n✅ [PROACTIVE_SCANNER] section found in config.ini")
        print("\nConfiguration values:")
        for key, value in config['PROACTIVE_SCANNER'].items():
            print(f"  {key} = {value}")
    else:
        print("\n❌ [PROACTIVE_SCANNER] section NOT found in config.ini")
        return False

    # Try to instantiate ProactiveScanner
    print("\n" + "=" * 80)
    print("Testing ProactiveScanner Initialization")
    print("=" * 80)

    try:
        scanner = ProactiveScanner(ibkr_adapter=None, config=config)
        print("\n✅ ProactiveScanner initialized successfully!")

        # Check loaded values
        print("\nLoaded configuration:")
        print(f"  catalyst_required: {scanner.catalyst_required}")
        print(f"  min_quality_score: {scanner.min_quality_score}")
        print(f"  min_quality_score_no_catalyst: {scanner.min_quality_score_no_catalyst}")
        print(f"  catalyst_max_age_weekday: {scanner.catalyst_max_age_weekday}h")
        print(f"  catalyst_max_age_monday: {scanner.catalyst_max_age_monday}h")

        # Test catalyst age logic
        print("\n" + "=" * 80)
        print("Testing Catalyst Age Logic")
        print("=" * 80)

        now = datetime.now()
        weekday = now.weekday()
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        print(f"\nToday is: {weekday_names[weekday]}")

        # Test different catalyst types
        catalyst_types = [None, 'FDA', 'EARNINGS', 'M&A', 'CONTRACT', 'OTHER']

        for catalyst_type in catalyst_types:
            max_age = scanner._get_max_catalyst_age_hours(catalyst_type)
            print(f"  Max age for {catalyst_type or 'GENERIC':15s}: {max_age:6.1f}h ({max_age/24:.1f} days)")

        print("\n✅ All tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Error initializing ProactiveScanner: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_config_loading()
    sys.exit(0 if success else 1)
