#!/usr/bin/env python3
"""
Simple test script for Parabolic Extension Detector

Tests the detector with synthetic data patterns to validate:
1. Early-stage parabolic detection (ENTRY opportunity)
2. Middle-stage parabolic detection (HOLD)
3. Late-stage parabolic detection (EXIT warning)
"""

import sys
from datetime import datetime, timedelta
from core.parabolic_extension_detector import ParabolicExtensionDetector
from core.interfaces import MarketData


def create_test_bars(pattern_type: str, symbol: str = 'TEST', base_price: float = 10.0):
    """
    Create synthetic bars for testing different parabolic patterns

    Args:
        pattern_type: 'early', 'middle', 'late', 'no_pattern'
        symbol: Symbol name for the bars
        base_price: Starting price

    Returns:
        List of MarketData bars
    """
    bars = []
    timestamp = datetime.now() - timedelta(minutes=30)

    if pattern_type == 'early':
        # EARLY STAGE: Initial acceleration (5% in 3 bars)
        # Perfect for LONG entry
        prices = [
            base_price,
            base_price * 1.01,  # +1%
            base_price * 1.02,  # +2%
            base_price * 1.025, # +2.5%
            base_price * 1.035, # +3.5%
            base_price * 1.05,  # +5% (acceleration starting)
            base_price * 1.06,
            base_price * 1.07,
            base_price * 1.08,
            base_price * 1.09,
            base_price * 1.10,  # +10%
            base_price * 1.11,
            base_price * 1.12,
            base_price * 1.13,
            base_price * 1.14   # Building momentum
        ]
        volumes = [100000] * 5 + [150000] * 10  # Volume increasing

    elif pattern_type == 'middle':
        # MIDDLE STAGE: Established momentum (10% in 5 bars)
        # HOLD with trailing stops
        prices = [
            base_price,
            base_price * 1.02,
            base_price * 1.04,
            base_price * 1.06,
            base_price * 1.08,
            base_price * 1.10,  # +10% established
            base_price * 1.12,
            base_price * 1.14,
            base_price * 1.16,
            base_price * 1.18,
            base_price * 1.20,  # +20% strong momentum
            base_price * 1.22,
            base_price * 1.24,
            base_price * 1.26,
            base_price * 1.28
        ]
        volumes = [100000] * 3 + [200000] * 12  # High volume sustained

    elif pattern_type == 'late':
        # LATE STAGE: Extreme extension (25% in 10 bars)
        # EXIT warning - take profits
        prices = [
            base_price,
            base_price * 1.05,
            base_price * 1.10,
            base_price * 1.15,
            base_price * 1.20,
            base_price * 1.25,  # +25% parabolic
            base_price * 1.30,
            base_price * 1.35,
            base_price * 1.40,
            base_price * 1.45,
            base_price * 1.50,  # +50% extreme
            base_price * 1.52,
            base_price * 1.54,
            base_price * 1.55,  # Slowing down
            base_price * 1.555  # Exhaustion
        ]
        volumes = [100000] * 5 + [300000] * 5 + [400000] * 5  # Volume climax

    else:  # no_pattern
        # NO PATTERN: Sideways/choppy price action
        prices = [
            base_price,
            base_price * 1.01,
            base_price * 0.99,
            base_price * 1.005,
            base_price * 0.995,
            base_price * 1.002,
            base_price * 0.998,
            base_price * 1.003,
            base_price * 0.997,
            base_price * 1.001,
            base_price * 0.999,
            base_price * 1.0,
            base_price * 1.002,
            base_price * 0.998,
            base_price * 1.001
        ]
        volumes = [100000] * 15  # Normal volume

    # Create bars with realistic OHLC (mix of green and red bars)
    for i, (price, volume) in enumerate(zip(prices, volumes)):
        bar_timestamp = timestamp + timedelta(minutes=i)

        # Determine if bar is green or red (mostly green for uptrend, but not all)
        # Add some red bars to avoid triggering exhaustion detection
        is_green = True
        if i % 4 == 0:  # Every 4th bar is red (pullback)
            is_green = False

        if is_green:
            # Green bar: close > open
            open_price = price * 0.997
            close_price = price
            high_price = price * 1.002
            low_price = open_price * 0.999
        else:
            # Red bar: close < open (small pullback)
            open_price = price * 1.001
            close_price = price
            high_price = open_price * 1.002
            low_price = price * 0.998

        bar = MarketData(
            symbol=symbol,
            timestamp=bar_timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        )
        bars.append(bar)

    return bars


def test_detector():
    """Run tests on the parabolic extension detector"""
    print("=" * 80)
    print("🚀 PARABOLIC EXTENSION DETECTOR - TEST SUITE")
    print("=" * 80)
    print()

    # Initialize detector
    detector = ParabolicExtensionDetector()
    print(detector.get_detector_status())
    print()

    # Test cases
    test_cases = [
        ('EARLY_STAGE', 'early', 'Should detect EARLY stage - ENTRY opportunity'),
        ('MIDDLE_STAGE', 'middle', 'Should detect MIDDLE stage - HOLD signal'),
        ('LATE_STAGE', 'late', 'Should detect LATE stage - EXIT warning'),
        ('NO_PATTERN', 'no_pattern', 'Should NOT detect parabolic pattern')
    ]

    results = []

    for symbol, pattern_type, description in test_cases:
        print("-" * 80)
        print(f"TEST: {symbol} ({pattern_type})")
        print(f"Expected: {description}")
        print("-" * 80)

        # Create test bars
        bars = create_test_bars(pattern_type, symbol=symbol, base_price=10.0)

        # Detect
        signal = detector.detect_parabolic_extension(symbol, bars)

        if signal:
            print(f"✅ DETECTED: {signal}")
            print(f"   Stage: {signal.stage}")
            print(f"   Strength: {signal.strength:.2f}")
            print(f"   Acceleration: {signal.acceleration:.2f}")
            print(f"   Exhaustion Score: {signal.exhaustion_score:.2f}")
            print(f"   LONG Entry: {signal.long_entry_opportunity}")
            print(f"   Hold Signal: {signal.hold_signal}")
            print(f"   Exit Warning: {signal.exit_warning}")
            print(f"   Reasons:")
            for reason in signal.reasons[:5]:
                print(f"      - {reason}")

            # Validate expectations
            if pattern_type == 'early':
                success = signal.stage == 'EARLY' and signal.long_entry_opportunity
                results.append(('EARLY_ENTRY', success))
            elif pattern_type == 'middle':
                success = signal.stage == 'MIDDLE' and signal.hold_signal
                results.append(('MIDDLE_HOLD', success))
            elif pattern_type == 'late':
                success = signal.stage == 'LATE' and signal.exit_warning
                results.append(('LATE_EXIT', success))
            else:
                success = False  # Should not detect
                results.append(('NO_PATTERN', success))
        else:
            print("❌ NO DETECTION")
            if pattern_type == 'no_pattern':
                print("   ✅ CORRECT: No parabolic pattern (as expected)")
                results.append(('NO_PATTERN', True))
            else:
                print(f"   ❌ UNEXPECTED: Should have detected {pattern_type} pattern")
                results.append((pattern_type.upper(), False))

        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL TESTS PASSED! Detector is working correctly.")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED. Review detector logic.")
        return 1


if __name__ == "__main__":
    exit_code = test_detector()
    sys.exit(exit_code)
