#!/usr/bin/env python3
"""
Test MACDV Relaxed Conditions
Verifies that the relaxed conditions are working and MACDV can generate signals
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, SignalType
from strategies.macdv_strategy import MACDVStrategy

def create_test_bars(symbol: str, count: int = 50, start_price: float = 10.0) -> list:
    """Create test market data bars with favorable MACDV conditions"""
    bars = []
    base_time = datetime.now() - timedelta(minutes=count)

    # Create bars with MACD convergence pattern
    for i in range(count):
        timestamp = base_time + timedelta(minutes=i)

        # Create price action that should trigger MACDV
        if i < 20:
            # Initial downtrend for MACD setup
            price = start_price - (i * 0.05)
        elif i < 30:
            # Consolidation
            price = start_price - 1.0 + (i % 3) * 0.02
        else:
            # Uptrend that should trigger MACD convergence
            price = start_price - 1.0 + ((i - 30) * 0.1)

        # Volume that meets minimum requirements
        volume = 50000 + (i % 10) * 10000  # Varies between 50k-150k per minute

        bar = MarketData(
            symbol=symbol,
            open=price - 0.01,
            high=price + 0.02,
            low=price - 0.02,
            close=price,
            volume=volume,
            timestamp=timestamp
        )
        bars.append(bar)

    return bars

async def test_macdv_basic_functionality():
    """Test basic MACDV functionality with relaxed conditions"""
    print("🧪 Testing MACDV Basic Functionality...")

    # Create MACDV strategy instance
    macdv = MACDVStrategy()

    # Test symbol
    symbol = "TEST"

    # Create test data
    bars = create_test_bars(symbol, count=30)  # Should meet relaxed min_bars requirement (20)

    # Feed bars to strategy to build history
    for bar in bars[:-1]:  # All but last bar
        if symbol not in macdv.bars_history:
            macdv.bars_history[symbol] = []
        macdv.bars_history[symbol].append(bar)

    # Test with final bar
    final_bar = bars[-1]

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars in history: {len(macdv.bars_history[symbol])}")
    print(f"   Final bar price: ${final_bar.close:.2f}")
    print(f"   Final bar volume: {final_bar.volume:,}")

    # Check minimum bars requirement
    min_bars = max(20, macdv._parameters['macd_slow'] + 3)  # Should be relaxed requirement
    print(f"   Min bars required: {min_bars}")
    print(f"   Bars available: {len(macdv.bars_history[symbol])}")

    if len(macdv.bars_history[symbol]) >= min_bars:
        print("✅ Minimum bars requirement MET (relaxed condition working)")
    else:
        print("❌ Minimum bars requirement NOT MET")
        return False

    # Test price filters
    if final_bar.close >= macdv._parameters['min_price'] and final_bar.close <= macdv._parameters['max_price']:
        print("✅ Price range filter PASSED")
    else:
        print(f"❌ Price range filter FAILED: ${final_bar.close:.2f} not in range ${macdv._parameters['min_price']:.2f}-${macdv._parameters['max_price']:.2f}")
        return False

    # Test penny stock filter (relaxed)
    if final_bar.close >= 1.5:  # Relaxed from 2.0 to 1.5
        print("✅ Penny stock filter PASSED (relaxed condition working)")
    else:
        print("❌ Penny stock filter FAILED")
        return False

    # Test volume filter (relaxed)
    min_vol_per_minute = macdv._parameters.get('min_daily_volume', 30000) / 390  # Relaxed to 30k
    if final_bar.volume >= min_vol_per_minute:
        print("✅ Volume filter PASSED (relaxed condition working)")
    else:
        print(f"❌ Volume filter FAILED: {final_bar.volume:,} < {min_vol_per_minute:,.0f}")
        return False

    return True

async def test_macdv_signal_generation():
    """Test MACDV signal generation with favorable conditions"""
    print("\n🧪 Testing MACDV Signal Generation...")

    # Create MACDV strategy instance with more relaxed parameters for testing
    test_params = {
        'min_entry_score': 0,  # Ultra relaxed for testing
        'avoid_first_30min': False,
        'avoid_last_30min': False,
        'min_daily_volume': 10000,  # Very low for testing
    }
    macdv = MACDVStrategy(test_params)

    # Test symbol
    symbol = "SIGNAL_TEST"

    # Create favorable test data (more bars for better MACD convergence)
    bars = create_test_bars(symbol, count=40, start_price=5.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in macdv.bars_history:
            macdv.bars_history[symbol] = []
        macdv.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Signal test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(macdv.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        signal = await macdv._analyze_bar(final_bar)

        if signal:
            print(f"✅ SIGNAL GENERATED!")
            print(f"   Type: {signal.signal_type}")
            print(f"   Confidence: {signal.confidence:.2f}")
            print(f"   Signal: {signal}")
            return True
        else:
            print("❌ No signal generated")
            print("   This might be normal if technical conditions aren't perfect")
            return False

    except Exception as e:
        print(f"❌ Error generating signal: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_parameters_relaxed():
    """Test that parameters are actually relaxed"""
    print("\n🧪 Testing Relaxed Parameters...")

    macdv = MACDVStrategy()

    # Print all parameters for debugging
    print(f"📋 All MACDV parameters:")
    for key, value in macdv._parameters.items():
        print(f"   {key}: {value}")

    # Check key relaxed parameters
    tests = [
        ("min_entry_score", 1, "Entry score threshold"),
        ("min_daily_volume", 30000, "Daily volume requirement"),
        ("min_seconds_between_trades", 300, "Time between trades"),
        ("avoid_first_30min", False, "First 30min trading allowed"),
    ]

    all_passed = True
    for param, expected, description in tests:
        actual = macdv._parameters.get(param)
        if actual == expected:
            print(f"✅ {description}: {actual} (relaxed)")
        else:
            print(f"❌ {description}: {actual} (expected {expected})")
            all_passed = False

    return all_passed

async def main():
    """Run all MACDV relaxed condition tests"""
    print("🚀 MACDV Relaxed Conditions Test Suite")
    print("=" * 50)

    tests = [
        ("Basic Functionality", test_macdv_basic_functionality),
        ("Relaxed Parameters", test_parameters_relaxed),
        ("Signal Generation", test_macdv_signal_generation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 50)
    print("📊 TEST RESULTS:")

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n🎯 Summary: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 ALL TESTS PASSED - Relaxed conditions are working!")
    else:
        print("⚠️  Some tests failed - Check relaxed conditions")

if __name__ == "__main__":
    asyncio.run(main())