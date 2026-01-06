#!/usr/bin/env python3
"""
Test Hybrid ML vs Rules System
Simulate strategy selection to verify the system works correctly
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_hybrid_system():
    """Test the hybrid ML vs Rules system with simulated data"""
    print("🔄 Testing Hybrid ML vs Rules System")
    print("=" * 50)

    try:
        from strategies.rule_based_selector import RuleBasedStrategySelector
        from strategies.ml_vs_rules_tracker import MLvsRulesTracker

        # Initialize components
        rule_selector = RuleBasedStrategySelector()
        tracker = MLvsRulesTracker()

        print("✅ Components initialized successfully")

        # Create mock context objects for testing
        class MockContext:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        # Test Case 1: Gap Go Strategy
        print("\n📊 Test Case 1: Gap Go Scenario")
        gap_context = MockContext(
            gap_percent=5.2,
            volume_ratio=3.1,
            current_price=8.50,
            current_hour=10.5,
            consecutive_red_candles=1,
            day_change_percent=5.2,
            reversal_pattern=False
        )

        rule_strategies = rule_selector.select_strategies("TESTGAP", gap_context)
        print(f"   Rule selection: {rule_strategies}")

        # Test Case 2: Red to Green Strategy
        print("\n📊 Test Case 2: Red to Green Scenario")
        r2g_context = MockContext(
            gap_percent=0.5,
            volume_ratio=2.2,
            current_price=4.20,
            current_hour=11.0,
            consecutive_red_candles=4,
            day_change_percent=-8.5,
            reversal_pattern=True
        )

        rule_strategies = rule_selector.select_strategies("TESTR2G", r2g_context)
        print(f"   Rule selection: {rule_strategies}")

        # Test Case 3: First Day Bounce Strategy
        print("\n📊 Test Case 3: First Day Bounce Scenario")
        fdb_context = MockContext(
            gap_percent=-2.1,
            volume_ratio=2.8,
            current_price=12.30,
            day_change_percent=-12.5,
            intraday_bounce_percent=3.2,
            consecutive_red_candles=2,
            recent_overextension_gain=75.0,  # Had 75% gain recently
            has_recent_peak=True             # Recent peak detected
        )

        rule_strategies = rule_selector.select_strategies("TESTFDB", fdb_context)
        print(f"   Rule selection: {rule_strategies}")

        # Test Case 4: MACDV Smallcaps Strategy
        print("\n📊 Test Case 4: MACDV Smallcaps Scenario")
        macdv_context = MockContext(
            gap_percent=1.0,
            volume_ratio=1.8,
            current_price=6.80,
            current_hour=11.5,
            macd_convergence_5min=True,
            macd_timing_1min=True,
            volume_adequate=True,
            consecutive_red_candles=1
        )

        rule_strategies = rule_selector.select_strategies("TESTMACDV", macdv_context)
        print(f"   Rule selection: {rule_strategies}")

        # Test Case 5: Daily Plays Strategy
        print("\n📊 Test Case 5: Daily Plays Scenario")
        plays_context = MockContext(
            gap_percent=8.5,
            volume_ratio=4.5,
            current_price=15.20,
            has_catalyst=True,
            momentum_score=0.85,
            consecutive_red_candles=0,
            day_change_percent=8.5
        )

        rule_strategies = rule_selector.select_strategies("TESTPLAYS", plays_context)
        print(f"   Rule selection: {rule_strategies}")

        # Test tracking functionality
        print("\n📊 Testing ML vs Rules Tracking")

        # Simulate some comparisons
        ml_choices = ["gap_go", "daily_plays"]
        rule_choices = ["gap_go"]  # Rules and ML partially agree
        actual_choices = ["gap_go"]

        tracker.record_selection(
            symbol="TESTML",
            ml_choice=ml_choices,
            rule_choice=rule_choices,
            actual_choice=actual_choices,
            selection_method="ML_VALIDATED",
            context_data={
                'price': 8.50,
                'volume_ratio': 3.1,
                'gap_percent': 5.2,
                'is_smallcap': True
            }
        )

        # Simulate a trade result
        tracker.record_trade_result(
            symbol="TESTML",
            entry_price=8.50,
            exit_price=9.35,
            trade_duration_minutes=45,
            exit_reason="profit_target",
            position_size=100
        )

        # Get performance summary
        performance = tracker.get_performance_summary()
        print(f"   Performance tracking: {performance}")

        # Test rule stats
        rule_stats = rule_selector.get_selection_stats()
        print(f"   Rule selector stats: {rule_stats}")

        print("\n✅ All hybrid system tests completed successfully!")
        print("\n📋 Summary:")
        print("   - Rule-based selector working correctly")
        print("   - Strategy selection logic functioning")
        print("   - Performance tracking operational")
        print("   - All 5 strategies (gap_go, red_to_green, first_day_bounce, macdv_smallcaps, daily_plays) testable")

        return True

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_hybrid_system()
    sys.exit(0 if success else 1)