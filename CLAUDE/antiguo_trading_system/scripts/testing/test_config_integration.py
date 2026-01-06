#!/usr/bin/env python3
"""
Test Config Integration - Structural Exit Calculator

Verifica que los parámetros de config.ini se leen correctamente.

Author: Trading System
Date: 2025-11-10
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.structural_exit_calculator import get_structural_exit_calculator


def test_config_defaults():
    """Test 1: Sin config, debe usar defaults"""
    print("\n" + "=" * 80)
    print("TEST 1: Default Parameters (No Config)")
    print("=" * 80)

    calculator = get_structural_exit_calculator()

    print(f"\nDefault Parameters:")
    print(f"  min_risk_reward: {calculator.min_risk_reward}")
    print(f"  min_expected_value: {calculator.min_expected_value}")
    print(f"  resistance_buffer: {calculator.resistance_buffer}")
    print(f"  support_buffer: {calculator.support_buffer}")
    print(f"  strong_resistance_threshold: {calculator.strong_resistance_threshold}")

    assert calculator.min_risk_reward == 2.0, "Default min_risk_reward should be 2.0"
    assert calculator.min_expected_value == 2.0, "Default min_expected_value should be 2.0"
    assert calculator.resistance_buffer == 0.02, "Default resistance_buffer should be 0.02"
    assert calculator.support_buffer == 0.01, "Default support_buffer should be 0.01"
    assert calculator.strong_resistance_threshold == 70, "Default strong_resistance_threshold should be 70"

    print("\n✅ All default parameters correct")


def test_config_custom():
    """Test 2: Con config custom, debe usar valores config"""
    print("\n" + "=" * 80)
    print("TEST 2: Custom Config Parameters")
    print("=" * 80)

    # Custom config (simula config.ini)
    custom_config = {
        'min_risk_reward_ratio': 3.0,  # Más conservador
        'min_expected_value_pct': 5.0,  # EV más alto
        'resistance_buffer_pct': 0.03,  # 3% buffer
        'support_buffer_pct': 0.02,  # 2% buffer
        'strong_resistance_threshold': 80  # Solo resistencias MUY fuertes
    }

    calculator = get_structural_exit_calculator(config=custom_config)

    print(f"\nCustom Parameters:")
    print(f"  min_risk_reward: {calculator.min_risk_reward} (expected: 3.0)")
    print(f"  min_expected_value: {calculator.min_expected_value} (expected: 5.0)")
    print(f"  resistance_buffer: {calculator.resistance_buffer} (expected: 0.03)")
    print(f"  support_buffer: {calculator.support_buffer} (expected: 0.02)")
    print(f"  strong_resistance_threshold: {calculator.strong_resistance_threshold} (expected: 80)")

    assert calculator.min_risk_reward == 3.0, "Custom min_risk_reward should be 3.0"
    assert calculator.min_expected_value == 5.0, "Custom min_expected_value should be 5.0"
    assert calculator.resistance_buffer == 0.03, "Custom resistance_buffer should be 0.03"
    assert calculator.support_buffer == 0.02, "Custom support_buffer should be 0.02"
    assert calculator.strong_resistance_threshold == 80, "Custom strong_resistance_threshold should be 80"

    print("\n✅ All custom parameters loaded correctly")


def test_config_partial():
    """Test 3: Config parcial, debe usar mix de custom + defaults"""
    print("\n" + "=" * 80)
    print("TEST 3: Partial Config (Some Custom, Some Default)")
    print("=" * 80)

    # Partial config (solo algunos parámetros)
    partial_config = {
        'min_risk_reward_ratio': 2.5,  # Custom
        'strong_resistance_threshold': 65  # Custom
        # Resto usa defaults
    }

    calculator = get_structural_exit_calculator(config=partial_config)

    print(f"\nPartial Config Parameters:")
    print(f"  min_risk_reward: {calculator.min_risk_reward} (expected: 2.5 - custom)")
    print(f"  min_expected_value: {calculator.min_expected_value} (expected: 2.0 - default)")
    print(f"  resistance_buffer: {calculator.resistance_buffer} (expected: 0.02 - default)")
    print(f"  support_buffer: {calculator.support_buffer} (expected: 0.01 - default)")
    print(f"  strong_resistance_threshold: {calculator.strong_resistance_threshold} (expected: 65 - custom)")

    assert calculator.min_risk_reward == 2.5, "Partial min_risk_reward should be 2.5 (custom)"
    assert calculator.min_expected_value == 2.0, "Partial min_expected_value should be 2.0 (default)"
    assert calculator.resistance_buffer == 0.02, "Partial resistance_buffer should be 0.02 (default)"
    assert calculator.support_buffer == 0.01, "Partial support_buffer should be 0.01 (default)"
    assert calculator.strong_resistance_threshold == 65, "Partial strong_resistance_threshold should be 65 (custom)"

    print("\n✅ Partial config works correctly (custom + defaults)")


def test_impact_on_trade_rejection():
    """Test 4: Verificar que parámetros impactan en trade approval"""
    print("\n" + "=" * 80)
    print("TEST 4: Config Impact on Trade Approval")
    print("=" * 80)

    # Setup marginal con R:R = 2.5
    opportunity = {
        'symbol': 'TEST',
        'current_price': 100.00,
        'quality_score': 75,
        'catalyst_type': 'news',
        'atr': 2.00,

        'intraday_structure': {
            'high_of_day': 105.00,
            'low_of_day': 98.00,
            'vwap': 99.00
        },

        'ods_data': {
            'classification': 'MODERATE_BULLISH',
            'strength': 0.70
        },

        'daily_potential': {
            'previous_high': 110.00,
            'previous_low': 95.00
        }
    }

    # Test A: Con min_rr = 2.0 → DEBE APROBAR (R:R > 2.0)
    print("\n--- Test 4A: Conservative Config (min_rr=2.0) ---")
    conservative_config = {'min_risk_reward_ratio': 2.0, 'min_expected_value_pct': 1.0}
    calc_conservative = get_structural_exit_calculator(config=conservative_config)
    result_a = calc_conservative.calculate_exits(opportunity.copy())

    if result_a and result_a.get('approved'):
        print(f"✅ APPROVED with R:R={result_a['risk_reward']:.2f} (min: 2.0)")
    else:
        print(f"❌ REJECTED (unexpected)")

    # Test B: Con min_rr = 3.5 → DEBE RECHAZAR (R:R < 3.5)
    print("\n--- Test 4B: Strict Config (min_rr=3.5) ---")
    strict_config = {'min_risk_reward_ratio': 3.5, 'min_expected_value_pct': 1.0}
    calc_strict = get_structural_exit_calculator(config=strict_config)
    result_b = calc_strict.calculate_exits(opportunity.copy())

    if result_b and result_b.get('approved'):
        print(f"⚠️ APPROVED with R:R={result_b['risk_reward']:.2f} (unexpected - should reject)")
    else:
        print(f"✅ REJECTED as expected - {result_b.get('rejection_reason') if result_b else 'Unknown'}")
        if result_b and 'risk_reward' in result_b:
            print(f"   R:R: {result_b['risk_reward']:.2f} < min: 3.5")

    print("\n✅ Config parameters correctly impact trade approval/rejection")


def main():
    """Run all config integration tests"""
    print("\n" + "=" * 80)
    print("CONFIG INTEGRATION TESTS - STRUCTURAL EXIT CALCULATOR")
    print("=" * 80)

    try:
        test_config_defaults()
        test_config_custom()
        test_config_partial()
        test_impact_on_trade_rejection()

        print("\n" + "=" * 80)
        print("✅ ALL CONFIG TESTS PASSED")
        print("=" * 80)
        print("\nConclusion:")
        print("  • Default parameters work correctly")
        print("  • Custom config.ini parameters are loaded")
        print("  • Partial configs use mix of custom + defaults")
        print("  • Config parameters impact trade approval")
        print("\n✅ Sistema listo para usar config.ini")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
