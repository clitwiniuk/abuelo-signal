#!/usr/bin/env python3
"""
Test Structural Exit Calculator

Demuestra cómo funciona el sistema universal de exits con diferentes scenarios.

Author: Trading System
Date: 2025-11-10
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.structural_exit_calculator import get_structural_exit_calculator


def test_scenario_1_good_setup():
    """
    Scenario 1: Setup A+ con resistencia clara y soporte definido

    Expected: APPROVED with good R:R and high EV
    """
    print("\n" + "=" * 80)
    print("SCENARIO 1: A+ Setup - Resistencia clara, soporte definido")
    print("=" * 80)

    calculator = get_structural_exit_calculator()

    opportunity = {
        'symbol': 'AAPL',
        'current_price': 150.00,
        'quality_score': 88,  # A+
        'catalyst_type': 'news',
        'atr': 3.00,  # 2% ATR

        # Intraday structure
        'intraday_structure': {
            'high_of_day': 152.50,  # Resistencia cercana
            'low_of_day': 147.00,
            'opening_range_high': 151.00,
            'opening_range_low': 148.50,
            'vwap': 149.00
        },

        # ODS data
        'ods_data': {
            'classification': 'STRONG_BULLISH',
            'strength': 0.85,
            'invalidation_price': 148.00  # Pattern invalidation
        },

        # Daily potential
        'daily_potential': {
            'previous_high': 153.00,
            'previous_low': 146.50,
            'distance_to_resistance': 3.3  # 3.3% a resistencia
        }
    }

    result = calculator.calculate_exits(opportunity)

    if result:
        print(f"\n✅ Trade APPROVED")
        print(f"   Entry: ${opportunity['current_price']:.2f}")
        print(f"   TP: ${result['tp_price']:.2f} ({result['tp_pct']:.1f}%) - {result['tp_source']}")
        print(f"   SL: ${result['sl_price']:.2f} ({result['sl_pct']:.1f}%) - {result['sl_source']}")
        print(f"   R:R: {result['risk_reward']:.2f}:1")
        print(f"   EV: {result['expected_value_pct']:.2f}% (Win prob: {result['win_probability']*100:.1f}%)")
        print(f"\n   Reasoning:")
        for reason in result['reasoning']:
            print(f"     • {reason}")
    else:
        print("\n❌ Trade REJECTED")

    return result


def test_scenario_2_resistance_too_close():
    """
    Scenario 2: Resistencia MUY cercana (como ELDN case)

    Expected: REJECTED due to low R:R or low EV
    """
    print("\n" + "=" * 80)
    print("SCENARIO 2: Resistencia MUY cercana - Similar a ELDN")
    print("=" * 80)

    calculator = get_structural_exit_calculator()

    opportunity = {
        'symbol': 'ELDN',
        'current_price': 5.00,
        'quality_score': 88,  # A+ pero...
        'catalyst_type': 'news',
        'atr': 0.25,  # 5% ATR

        'intraday_structure': {
            'high_of_day': 5.12,  # Solo 2.4% arriba!
            'low_of_day': 4.75,
            'vwap': 4.90
        },

        'ods_data': {
            'classification': 'STRONG_BULLISH',
            'strength': 0.85,
            'invalidation_price': None
        },

        'daily_potential': {
            'previous_high': 5.15,  # Resistencia muy cerca
            'previous_low': 4.70,
            'distance_to_resistance': 2.4  # Solo 2.4%!
        }
    }

    result = calculator.calculate_exits(opportunity)

    if result and result.get('approved'):
        print(f"\n✅ Trade APPROVED (unexpected)")
        print(f"   TP: ${result['tp_price']:.2f} ({result['tp_pct']:.1f}%)")
        print(f"   SL: ${result['sl_price']:.2f} ({result['sl_pct']:.1f}%)")
        print(f"   R:R: {result['risk_reward']:.2f}:1")
        print(f"   EV: {result['expected_value_pct']:.2f}%")
    else:
        print(f"\n❌ Trade REJECTED (expected)")
        if result:
            print(f"   Reason: {result.get('rejection_reason', 'Unknown')}")
            if 'risk_reward' in result:
                print(f"   R:R: {result['risk_reward']:.2f}:1 (min: 2.0)")
            if 'expected_value_pct' in result:
                print(f"   EV: {result['expected_value_pct']:.2f}% (min: 2.0%)")

    return result


def test_scenario_3_orb_breakout():
    """
    Scenario 3: ORB Breakout - estructura clara

    Expected: APPROVED - SL en OR low, TP en previous high
    """
    print("\n" + "=" * 80)
    print("SCENARIO 3: ORB Breakout - Estructura clara")
    print("=" * 80)

    calculator = get_structural_exit_calculator()

    opportunity = {
        'symbol': 'TSLA',
        'current_price': 255.00,  # Breakout de OR
        'quality_score': 75,
        'catalyst_type': 'NONE',
        'atr': 5.00,  # 2% ATR

        'intraday_structure': {
            'high_of_day': 256.00,
            'low_of_day': 250.00,
            'opening_range_high': 253.00,  # Acaba de romper
            'opening_range_low': 250.50,  # SL aquí
            'vwap': 252.00
        },

        'ods_data': {
            'classification': 'MODERATE_BULLISH',
            'strength': 0.72
        },

        'daily_potential': {
            'previous_high': 262.00,  # Target claro
            'previous_low': 248.00
        }
    }

    result = calculator.calculate_exits(opportunity)

    if result and result.get('approved'):
        print(f"\n✅ Trade APPROVED")
        print(f"   Entry: ${opportunity['current_price']:.2f} (OR breakout)")
        print(f"   TP: ${result['tp_price']:.2f} ({result['tp_pct']:.1f}%) - {result['tp_source']}")
        print(f"   SL: ${result['sl_price']:.2f} ({result['sl_pct']:.1f}%) - {result['sl_source']}")
        print(f"   R:R: {result['risk_reward']:.2f}:1")
        print(f"   EV: {result['expected_value_pct']:.2f}%")
    else:
        print(f"\n❌ Trade REJECTED")
        if result:
            print(f"   Reason: {result.get('rejection_reason')}")

    return result


def test_scenario_4_penny_stock_high_volatility():
    """
    Scenario 4: Penny stock con alta volatilidad - ATR amplio

    Expected: SL debe ser más amplio por ATR, validar EV
    """
    print("\n" + "=" * 80)
    print("SCENARIO 4: Penny Stock - Alta volatilidad")
    print("=" * 80)

    calculator = get_structural_exit_calculator()

    opportunity = {
        'symbol': 'PENNY',
        'current_price': 2.50,
        'quality_score': 82,
        'catalyst_type': 'FDA',  # Strong catalyst
        'atr': 0.20,  # 8% ATR (alto)

        'intraday_structure': {
            'high_of_day': 2.65,
            'low_of_day': 2.30,
            'vwap': 2.40
        },

        'ods_data': {
            'classification': 'STRONG_BULLISH',
            'strength': 0.88
        },

        'daily_potential': {
            'previous_high': 2.80,  # 12% arriba
            'previous_low': 2.20
        }
    }

    result = calculator.calculate_exits(opportunity)

    if result and result.get('approved'):
        print(f"\n✅ Trade APPROVED")
        print(f"   Entry: ${opportunity['current_price']:.2f}")
        print(f"   TP: ${result['tp_price']:.2f} ({result['tp_pct']:.1f}%)")
        print(f"   SL: ${result['sl_price']:.2f} ({result['sl_pct']:.1f}%)")
        print(f"   R:R: {result['risk_reward']:.2f}:1")
        print(f"   EV: {result['expected_value_pct']:.2f}% (Win prob: {result['win_probability']*100:.1f}%)")
    else:
        print(f"\n❌ Trade REJECTED")
        if result:
            print(f"   Reason: {result.get('rejection_reason')}")

    return result


def main():
    """Run all test scenarios"""
    print("\n" + "=" * 80)
    print("STRUCTURAL EXIT CALCULATOR - TEST SCENARIOS")
    print("=" * 80)

    # Run scenarios
    results = []
    results.append(("Good Setup A+", test_scenario_1_good_setup()))
    results.append(("Resistance Too Close", test_scenario_2_resistance_too_close()))
    results.append(("ORB Breakout", test_scenario_3_orb_breakout()))
    results.append(("Penny Stock High Vol", test_scenario_4_penny_stock_high_volatility()))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    approved = sum(1 for _, r in results if r and r.get('approved', False))
    rejected = len(results) - approved

    print(f"\nApproved: {approved}/{len(results)}")
    print(f"Rejected: {rejected}/{len(results)}")

    print("\nResults by scenario:")
    for name, result in results:
        if result and result.get('approved'):
            print(f"  ✅ {name}: R:R={result['risk_reward']:.2f}, EV={result['expected_value_pct']:.2f}%")
        elif result:
            print(f"  ❌ {name}: {result.get('rejection_reason', 'Unknown')}")
        else:
            print(f"  ❌ {name}: Error calculating")

    print("\n" + "=" * 80)
    print()


if __name__ == "__main__":
    main()
