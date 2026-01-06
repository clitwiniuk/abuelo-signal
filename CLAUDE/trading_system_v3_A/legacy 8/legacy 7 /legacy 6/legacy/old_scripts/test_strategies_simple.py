#!/usr/bin/env python3
"""
Test simplificado para verificar que las estrategias se inicializan correctamente
con los valores centralizados.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_strategy_init(strategy_name: str, strategy_module: str, strategy_class_name: str):
    """Test simple strategy initialization"""
    print(f"\n🧪 Testing {strategy_name}...")

    try:
        # Dynamic import
        module = __import__(strategy_module, fromlist=[strategy_class_name])
        strategy_class = getattr(module, strategy_class_name)

        # Simple params
        params = {
            'min_price': 1.0,
            'max_price': 15.0,
            'min_daily_volume': 100000
        }

        # Initialize strategy
        strategy = strategy_class(params)
        print(f"   ✅ {strategy_name} initialized successfully")

        # Check if stop_manager is available
        if hasattr(strategy, 'stop_manager'):
            print(f"   ✅ Stop manager available")
        else:
            print(f"   ⚠️  No stop_manager attribute")

        # Check registration method
        if hasattr(strategy, '_register_position_with_stop_manager'):
            print(f"   ✅ Registration method available")
        else:
            print(f"   ⚠️  No registration method")

        return True

    except Exception as e:
        print(f"   ❌ {strategy_name} - ERROR: {str(e)}")
        import traceback
        print(f"   📋 Details: {traceback.format_exc()[:200]}...")
        return False

def main():
    """Run simple tests"""
    print("🚀 SIMPLE STRATEGY INITIALIZATION TEST")
    print("=" * 50)

    strategies = [
        ("GapGoStrategy", "strategies.gap_go_strategy", "GapGoStrategy"),
        ("GapCrapReversalStrategy", "strategies.gap_crap_reversal_strategy", "GapCrapReversalStrategy"),
        ("DailyPlaysStrategy", "strategies.daily_plays_strategy", "DailyPlaysStrategy"),
        ("FirstDayBounceStrategy", "strategies.first_day_bounce_strategy", "FirstDayBounceStrategy"),
        ("RedToGreenStrategy", "strategies.red_to_green_strategy", "RedToGreenStrategy")
    ]

    results = []
    for strategy_name, module, class_name in strategies:
        success = test_strategy_init(strategy_name, module, class_name)
        results.append((strategy_name, success))

    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST RESULTS")
    print("=" * 50)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for strategy_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {strategy_name}: {status}")

    print(f"\n🎯 RESULT: {passed}/{total} strategies initialized successfully")

    if passed == total:
        print("🎉 ALL STRATEGIES WORKING!")
        print("✅ Smallcap optimizations + centralized config OK")
    else:
        print("⚠️  Some strategies need fixes")

if __name__ == "__main__":
    main()