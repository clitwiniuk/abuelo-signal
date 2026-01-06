#!/usr/bin/env python3
"""
Test Fill Model - Deterministic Fill Simulation

Verifica que:
1. Fill price considera spread, impact, y volatilidad
2. Slippage es determinístico (mismo bar → mismo fill)
3. BUY paga más, SELL recibe menos
4. Fill está dentro del rango de la barra
5. Large orders tienen mayor slippage que small orders
6. Limit orders se ejecutan correctamente

Este test valida la solución al Problema #4 (Fill Model)
que causa diferencias entre live y replay fills.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.fill_model import FillModel, BarData


def test_basic_market_buy():
    """Test 1: Market buy order básico"""

    print("\n" + "="*70)
    print("TEST 1: Basic Market BUY Order")
    print("="*70)

    fill_model = FillModel()

    bar = BarData(
        symbol='CMBM',
        timestamp=datetime(2026, 1, 5, 9, 31),
        open=5.20,
        high=5.35,
        low=5.18,
        close=5.28,
        volume=50000,
        bar_duration_seconds=60
    )

    # Small order (500 shares = 1% of volume)
    fill = fill_model.simulate_market_order(
        order_type='BUY',
        shares=500,
        bar=bar,
        entry_price=5.28
    )

    print(f"\nBar: CMBM @ {bar.close} (range: {bar.low}-{bar.high})")
    print(f"Order: BUY 500 shares")
    print(f"Fill price: ${fill.filled_price:.2f}")
    print(f"Slippage: {fill.slippage_bps:.1f} bps ({fill.slippage_reason})")
    print(f"Fill time: {fill.fill_time}")

    # Validations
    assert fill.filled_price >= bar.close, "BUY should pay >= close"
    assert fill.filled_price <= bar.high, "Fill should be within bar range"
    assert fill.slippage_bps > 0, "Slippage should be positive"
    assert fill.filled_shares == 500, "Should fill completely"
    assert not fill.partial_fill, "Small order should fill completely"

    print("\n✅ TEST 1 PASSED")
    return True


def test_basic_market_sell():
    """Test 2: Market sell order básico"""

    print("\n" + "="*70)
    print("TEST 2: Basic Market SELL Order")
    print("="*70)

    fill_model = FillModel()

    bar = BarData(
        symbol='KALA',
        timestamp=datetime(2026, 1, 5, 10, 15),
        open=3.50,
        high=3.65,
        low=3.45,
        close=3.58,
        volume=80000,
        bar_duration_seconds=60
    )

    fill = fill_model.simulate_market_order(
        order_type='SELL',
        shares=1000,
        bar=bar,
        entry_price=3.58
    )

    print(f"\nBar: KALA @ {bar.close} (range: {bar.low}-{bar.high})")
    print(f"Order: SELL 1000 shares")
    print(f"Fill price: ${fill.filled_price:.2f}")
    print(f"Slippage: {fill.slippage_bps:.1f} bps ({fill.slippage_reason})")

    # Validations
    assert fill.filled_price <= bar.close, "SELL should receive <= close"
    assert fill.filled_price >= bar.low, "Fill should be within bar range"
    assert fill.slippage_bps > 0, "Slippage should be positive"

    print("\n✅ TEST 2 PASSED")
    return True


def test_large_order_impact():
    """Test 3: Large order tiene mayor slippage por market impact"""

    print("\n" + "="*70)
    print("TEST 3: Large Order Market Impact")
    print("="*70)

    fill_model = FillModel()

    bar = BarData(
        symbol='FOXX',
        timestamp=datetime(2026, 1, 5, 11, 0),
        open=2.10,
        high=2.25,
        low=2.08,
        close=2.18,
        volume=20000,  # Low volume
        bar_duration_seconds=60
    )

    # Small order
    small_fill = fill_model.simulate_market_order(
        order_type='BUY',
        shares=200,  # 1% of volume
        bar=bar,
        entry_price=2.18
    )

    # Large order
    large_fill = fill_model.simulate_market_order(
        order_type='BUY',
        shares=5000,  # 25% of volume - HUGE impact
        bar=bar,
        entry_price=2.18
    )

    print(f"\nBar: FOXX @ {bar.close}, Volume: {bar.volume}")
    print(f"\nSmall order (200sh, 1% vol):")
    print(f"  Fill: ${small_fill.filled_price:.2f}")
    print(f"  Slippage: {small_fill.slippage_bps:.1f} bps")

    print(f"\nLarge order (5000sh, 25% vol):")
    print(f"  Fill: ${large_fill.filled_price:.2f}")
    print(f"  Slippage: {large_fill.slippage_bps:.1f} bps")
    print(f"  Partial fill: {large_fill.partial_fill}")

    # Validations
    assert large_fill.slippage_bps > small_fill.slippage_bps, \
        "Large order should have more slippage"

    assert large_fill.partial_fill, \
        "Large order (25% volume) should be partial fill"

    print(f"\n📊 Slippage difference: {large_fill.slippage_bps - small_fill.slippage_bps:.1f} bps")
    print("✅ TEST 3 PASSED")
    return True


def test_high_volatility_slippage():
    """Test 4: High volatility bar tiene mayor slippage"""

    print("\n" + "="*70)
    print("TEST 4: Volatility Slippage")
    print("="*70)

    fill_model = FillModel()

    # Low volatility bar
    calm_bar = BarData(
        symbol='TEST',
        timestamp=datetime(2026, 1, 5, 12, 0),
        open=10.00,
        high=10.05,  # 0.5% range
        low=9.98,
        close=10.02,
        volume=50000,
        bar_duration_seconds=60
    )

    # High volatility bar
    volatile_bar = BarData(
        symbol='TEST',
        timestamp=datetime(2026, 1, 5, 12, 1),
        open=10.00,
        high=10.50,  # 5% range
        low=9.50,
        close=10.02,
        volume=50000,
        bar_duration_seconds=60
    )

    calm_fill = fill_model.simulate_market_order(
        order_type='BUY', shares=500, bar=calm_bar, entry_price=10.02
    )

    volatile_fill = fill_model.simulate_market_order(
        order_type='BUY', shares=500, bar=volatile_bar, entry_price=10.02
    )

    print(f"\nCalm bar (0.5% range):")
    print(f"  Fill: ${calm_fill.filled_price:.2f}")
    print(f"  Slippage: {calm_fill.slippage_bps:.1f} bps")

    print(f"\nVolatile bar (5% range):")
    print(f"  Fill: ${volatile_fill.filled_price:.2f}")
    print(f"  Slippage: {volatile_fill.slippage_bps:.1f} bps")

    # Validations
    assert volatile_fill.slippage_bps > calm_fill.slippage_bps, \
        "Volatile bar should have more slippage"

    print(f"\n📊 Volatility premium: {volatile_fill.slippage_bps - calm_fill.slippage_bps:.1f} bps")
    print("✅ TEST 4 PASSED")
    return True


def test_determinism():
    """Test 5: Same inputs → same outputs (determinístico)"""

    print("\n" + "="*70)
    print("TEST 5: Determinism Test")
    print("="*70)

    fill_model = FillModel()

    bar = BarData(
        symbol='DET',
        timestamp=datetime(2026, 1, 5, 13, 0),
        open=7.50,
        high=7.68,
        low=7.45,
        close=7.60,
        volume=30000,
        bar_duration_seconds=60
    )

    # Run 100 times with same inputs
    results = []

    for i in range(100):
        fill = fill_model.simulate_market_order(
            order_type='BUY',
            shares=1000,
            bar=bar,
            entry_price=7.60
        )
        results.append((fill.filled_price, fill.slippage_bps, fill.slippage_reason))

    # All results should be identical
    unique_results = set(results)

    print(f"\n100 runs with identical inputs:")
    print(f"Unique results: {len(unique_results)}")
    print(f"Fill price: ${results[0][0]:.2f}")
    print(f"Slippage: {results[0][1]:.1f} bps")

    assert len(unique_results) == 1, \
        f"Should be deterministic, got {len(unique_results)} different results"

    print("\n✅ Completely deterministic (100/100 identical)")
    print("✅ TEST 5 PASSED")
    return True


def test_limit_order_execution():
    """Test 6: Limit orders se ejecutan correctamente"""

    print("\n" + "="*70)
    print("TEST 6: Limit Order Execution")
    print("="*70)

    fill_model = FillModel()

    bar = BarData(
        symbol='LIM',
        timestamp=datetime(2026, 1, 5, 14, 0),
        open=15.00,
        high=15.20,
        low=14.80,
        close=15.10,
        volume=40000,
        bar_duration_seconds=60
    )

    # BUY limit @ 14.90 - should execute (low=14.80)
    buy_fill = fill_model.simulate_limit_order(
        order_type='BUY',
        shares=500,
        limit_price=14.90,
        bar=bar
    )

    # BUY limit @ 14.70 - should NOT execute (low=14.80)
    buy_no_fill = fill_model.simulate_limit_order(
        order_type='BUY',
        shares=500,
        limit_price=14.70,
        bar=bar
    )

    # SELL limit @ 15.15 - should execute (high=15.20)
    sell_fill = fill_model.simulate_limit_order(
        order_type='SELL',
        shares=500,
        limit_price=15.15,
        bar=bar
    )

    # SELL limit @ 15.25 - should NOT execute (high=15.20)
    sell_no_fill = fill_model.simulate_limit_order(
        order_type='SELL',
        shares=500,
        limit_price=15.25,
        bar=bar
    )

    print(f"\nBar: {bar.symbol} @ {bar.close} (range: {bar.low}-{bar.high})")

    print(f"\nBUY limit @ 14.90:")
    if buy_fill:
        print(f"  ✅ Executed @ ${buy_fill.filled_price:.2f}")
    else:
        print(f"  ❌ Not executed")

    print(f"\nBUY limit @ 14.70:")
    if buy_no_fill:
        print(f"  ❌ Should NOT execute")
    else:
        print(f"  ✅ Correctly not executed")

    print(f"\nSELL limit @ 15.15:")
    if sell_fill:
        print(f"  ✅ Executed @ ${sell_fill.filled_price:.2f}")
    else:
        print(f"  ❌ Not executed")

    print(f"\nSELL limit @ 15.25:")
    if sell_no_fill:
        print(f"  ❌ Should NOT execute")
    else:
        print(f"  ✅ Correctly not executed")

    # Validations
    assert buy_fill is not None, "BUY limit @ 14.90 should execute"
    assert buy_no_fill is None, "BUY limit @ 14.70 should NOT execute"
    assert sell_fill is not None, "SELL limit @ 15.15 should execute"
    assert sell_no_fill is None, "SELL limit @ 15.25 should NOT execute"

    print("\n✅ TEST 6 PASSED")
    return True


def main():
    """Run all tests"""

    print("\n" + "="*70)
    print("FILL MODEL - DETERMINISM VALIDATION")
    print("="*70)
    print("\nThese tests validate the solution to Problem #4:")
    print("Fill Model Non-Deterministic (Impact: -5-10% reproducibility)")
    print("="*70)

    tests = [
        ("Basic Market BUY", test_basic_market_buy),
        ("Basic Market SELL", test_basic_market_sell),
        ("Large Order Impact", test_large_order_impact),
        ("Volatility Slippage", test_high_volatility_slippage),
        ("Determinism", test_determinism),
        ("Limit Order Execution", test_limit_order_execution),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Fill model is deterministic")
        print("\nKey features:")
        print("  - ✅ Spread cost calculation (volatility-based)")
        print("  - ✅ Market impact (volume-based)")
        print("  - ✅ Volatility slippage (range-based)")
        print("  - ✅ Deterministic (same bar → same fill)")
        print("  - ✅ Realistic for small caps (wide spreads, impact)")
        print("\nExpected improvement:")
        print("  - Reproducibility: +5-10%")
        print("  - Live vs replay fill match: 95%+")
        return 0
    else:
        print("\n⚠️ SOME TESTS FAILED - Check implementation")
        return 1


if __name__ == '__main__':
    exit(main())
