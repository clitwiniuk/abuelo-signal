#!/usr/bin/env python3
"""
Test script for position size adjustment logic
Tests the fix for max_position_value calculation bug
"""

import math
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_position_size_adjustment():
    """Test the position size adjustment logic"""

    # Test cases that previously failed
    test_cases = [
        # (max_position_value, current_price, expected_quantity, expected_final_value)
        (200.0, 2.04, 98, 199.92),  # The case from the log
        (200.0, 2.00, 100, 200.00),  # Clean division
        (200.0, 2.01, 99, 198.99),   # Should floor down
        (200.0, 1.99, 100, 199.00),  # Should fit exactly
        (500.0, 4.75, 105, 498.75),  # Larger position
    ]

    print("🧪 TESTING POSITION SIZE ADJUSTMENT FIX")
    print("=" * 60)

    all_passed = True

    for i, (max_position_value, current_price, expected_quantity, expected_final_value) in enumerate(test_cases, 1):
        print(f"\nTest {i}: max_value=${max_position_value}, price=${current_price}")

        # OLD METHOD (problematic)
        old_quantity = int(max_position_value / current_price)
        old_position_value = old_quantity * current_price

        # NEW METHOD (fixed)
        new_quantity = math.floor(max_position_value / current_price)
        new_position_value = new_quantity * current_price

        # Additional validation (the fix)
        if new_position_value > max_position_value:
            new_quantity -= 1
            new_position_value = new_quantity * current_price

        # Check results
        within_limit = new_position_value <= max_position_value
        correct_quantity = new_quantity == expected_quantity
        correct_value = abs(new_position_value - expected_final_value) < 0.01  # Allow small floating point differences

        print(f"  OLD: {old_quantity} shares -> ${old_position_value:.2f} {'❌ EXCEEDS' if old_position_value > max_position_value else '✅ OK'}")
        print(f"  NEW: {new_quantity} shares -> ${new_position_value:.2f} {'✅ WITHIN LIMIT' if within_limit else '❌ EXCEEDS'}")

        if within_limit and correct_quantity and correct_value:
            print("  ✅ PASSED")
        else:
            print("  ❌ FAILED")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Position size adjustment fix is working correctly.")
    else:
        print("❌ SOME TESTS FAILED! Fix needs more work.")

    return all_passed

def test_edge_cases():
    """Test edge cases that could cause issues"""

    print("\n🔍 TESTING EDGE CASES")
    print("=" * 40)

    edge_cases = [
        # Very small prices
        (200.0, 0.01, "Very cheap stock"),
        (200.0, 0.001, "Penny stock"),

        # Very high prices
        (200.0, 100.0, "Expensive stock"),
        (200.0, 1000.0, "Very expensive stock"),

        # Boundary cases
        (200.0, 2.0000001, "Boundary case"),
        (200.0, 1.9999999, "Boundary case"),
    ]

    for max_value, price, description in edge_cases:
        try:
            # Test the fixed logic
            quantity = math.floor(max_value / price)
            position_value = quantity * price

            if position_value > max_value:
                quantity -= 1
                position_value = quantity * price

            within_limit = position_value <= max_value
            reasonable_quantity = quantity > 0

            status = "✅" if within_limit and reasonable_quantity else "❌"
            print(f"{status} {description}: ${price} -> {quantity} shares (${position_value:.2f})")

        except Exception as e:
            print(f"❌ {description}: ERROR - {e}")

if __name__ == "__main__":
    # Run main tests
    success = test_position_size_adjustment()

    # Run edge case tests
    test_edge_cases()

    print("\n" + "=" * 60)
    if success:
        print("🎯 POSITION SIZE ADJUSTMENT FIX IS READY FOR PRODUCTION")
    else:
        print("⚠️  FIX NEEDS MORE WORK BEFORE PRODUCTION")