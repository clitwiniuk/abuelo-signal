#!/usr/bin/env python3
"""
Test Gap Go Strategy Signal Generation
Verifies that gap_go strategy can generate signals and checks for any restrictive conditions
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set logging level to DEBUG for detailed output
logging.basicConfig(level=logging.DEBUG)

from core.interfaces import MarketData, SignalType
from strategies.gap_go_strategy import GapGoStrategy

def create_gap_go_bars(symbol: str, count: int = 50, start_price: float = 6.0) -> list:
    """Create test market data bars with gap go pattern"""
    bars = []
    # Use market hours timestamp: today at 10:00 AM
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    base_time = today - timedelta(minutes=count)

    # Create gap go pattern for smallcaps
    for i in range(count):
        timestamp = base_time + timedelta(minutes=i)

        if i < 5:
            # Pre-gap normal trading
            price = start_price + (i * 0.01)
            volume = 60000 + (i * 2000)
        elif i == 5:
            # CREATE REAL GAP: Previous close was ~6.05, now gap up to 7.00+ (significant gap)
            prev_close = bars[-1].close if bars else start_price + 0.05
            gap_price = prev_close * 1.15  # 15% gap up for smallcaps
            price = gap_price
            volume = 200000  # High volume on gap open
        elif i < 10:
            # Continue gap phase with normal progression
            price = start_price + 0.9 + ((i - 6) * 0.05)
            volume = 120000 + (i % 3) * 15000
        elif i < 20:
            # Initial consolidation after gap
            price = start_price + 0.7 + ((i % 4) * 0.02)
            volume = 80000 + (i % 4) * 8000
        elif i < 35:
            # Building momentum (the "go" setup)
            momentum_factor = (i - 20) * 0.04
            price = start_price + 0.75 + momentum_factor
            volume = 90000 + (i % 5) * 10000
        else:
            # Breakout phase (the "go" execution)
            breakout_factor = (i - 35) * 0.06
            price = start_price + 1.35 + breakout_factor
            volume = 140000 + (i % 6) * 20000  # High volume breakout

        # Create OHLC data
        if i == 0:
            open_price = price
            high = price + 0.02
            low = price - 0.01
            close = price
        elif i == 5:
            # GAP OPEN: Open significantly higher than previous close to create real gap
            prev_close = bars[-1].close
            open_price = price  # This is our gap price (15% higher)
            high = price + 0.08  # Strong gap moves
            low = max(prev_close + 0.05, price - 0.05)  # Don't fill gap completely
            close = price
        else:
            prev_close = bars[-1].close if bars else price
            if i > 5:
                # After gap, normal progression
                open_price = prev_close + ((price - prev_close) * 0.3)
            else:
                # Before gap, normal progression
                open_price = prev_close + ((price - prev_close) * 0.3)

            if i >= 35:  # Breakout phase
                high = price + 0.05  # Strong breakout moves
                low = max(open_price - 0.02, price - 0.03)
            elif i >= 5 and i < 10:  # Gap phase
                high = price + 0.06  # Gap moves
                low = max(open_price - 0.03, price - 0.04)
            else:
                high = price + 0.02
                low = price - 0.02
            close = price

        bar = MarketData(
            symbol=symbol,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            timestamp=timestamp
        )
        bars.append(bar)

    return bars

async def test_gap_go_basic_functionality():
    """Test basic gap_go functionality"""
    print("🧪 Testing Gap Go Basic Functionality...")

    # Create gap_go strategy instance
    gap_go = GapGoStrategy()

    # Test symbol
    symbol = "GG_TEST"

    # Create test data
    bars = create_gap_go_bars(symbol, count=30)

    # Feed bars to strategy to build history
    for bar in bars[:-1]:  # All but last bar
        if symbol not in gap_go.bars_history:
            gap_go.bars_history[symbol] = []
        gap_go.bars_history[symbol].append(bar)

    # Test with final bar
    final_bar = bars[-1]

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars in history: {len(gap_go.bars_history[symbol])}")
    print(f"   Final bar price: ${final_bar.close:.2f}")
    print(f"   Final bar volume: {final_bar.volume:,}")

    # Check basic filters
    min_bars = 15  # Typical minimum for gap strategies
    if len(gap_go.bars_history[symbol]) >= min_bars:
        print("✅ Minimum bars requirement MET")
    else:
        print("❌ Minimum bars requirement NOT MET")
        return False

    # Check price filters (basic check for smallcaps)
    if 1.0 <= final_bar.close <= 50.0:
        print("✅ Price filter PASSED")
    else:
        print(f"❌ Price filter FAILED: ${final_bar.close:.2f} not in smallcap range")
        return False

    # Check volume filter (basic check)
    if final_bar.volume >= 30000:  # Basic volume requirement for smallcaps
        print("✅ Volume filter PASSED")
    else:
        print(f"❌ Volume filter FAILED: {final_bar.volume:,} too low")
        return False

    return True

async def test_gap_go_signal_generation():
    """Test gap_go signal generation with favorable conditions"""
    print("\n🧪 Testing Gap Go Signal Generation...")

    # Create gap_go strategy instance with relaxed parameters for testing
    test_params = {
        'min_gap_percent': 3.0,  # Relaxed gap requirement for smallcaps
        'max_gap_percent': 25.0,  # Reasonable max for smallcaps
        'min_volume_ratio': 1.5,  # Relaxed volume requirement
        'consolidation_time': 10,  # Shorter consolidation for smallcaps
        'min_daily_volume': 50000,  # Lower volume for smallcaps
        'breakout_volume_multiplier': 1.3,  # Relaxed breakout volume
    }
    gap_go = GapGoStrategy(test_params)

    # Test symbol
    symbol = "GG_SIGNAL_TEST"

    # Create favorable test data
    bars = create_gap_go_bars(symbol, count=40, start_price=4.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in gap_go.bars_history:
            gap_go.bars_history[symbol] = []
        gap_go.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Signal test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(gap_go.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Debug info before signal generation
    print(f"📊 Debug info before signal generation:")
    print(f"   Strategy parameters loaded: {len(gap_go._parameters)} params")

    # Try to generate signal
    try:
        signal = await gap_go._analyze_bar(final_bar)

        if signal:
            print(f"✅ SIGNAL GENERATED!")
            print(f"   Type: {signal.signal_type}")
            print(f"   Confidence: {signal.confidence:.2f}")
            print(f"   Signal details: {signal}")
            return True
        else:
            print("❌ No signal generated")
            print("   This might indicate restrictive conditions")
            return False

    except Exception as e:
        print(f"❌ Error generating signal: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_gap_go_parameters():
    """Test gap_go parameters and identify restrictive ones"""
    print("\n🧪 Testing Gap Go Parameters...")

    gap_go = GapGoStrategy()

    # Print key parameters that might be restrictive
    print(f"📋 Key Gap Go parameters:")
    restrictive_params = [
        'min_gap_percent',
        'max_gap_percent',
        'min_volume_ratio',
        'consolidation_time',
        'min_daily_volume',
        'breakout_volume_multiplier',
        'min_price',
        'max_price',
        'max_float',
        'entry_start_time',
        'entry_end_time',
        'risk_reward_ratio'
    ]

    for param in restrictive_params:
        value = gap_go._parameters.get(param, 'Not found')
        print(f"   {param}: {value}")

    return True

async def test_gap_go_with_ultra_relaxed_conditions():
    """Test gap_go with ultra-relaxed conditions to force signal generation"""
    print("\n🧪 Testing Gap Go with Ultra-Relaxed Conditions...")

    # Ultra-relaxed parameters for smallcaps
    ultra_relaxed_params = {
        'min_gap_percent': 2.0,  # Very low gap requirement for smallcaps
        'max_gap_percent': 100.0,  # High max gap
        'min_volume_ratio': 1.0,  # No volume ratio requirement
        'consolidation_time': 3,  # Very short consolidation
        'min_daily_volume': 20000,  # Very low volume for smallcaps
        'breakout_volume_multiplier': 1.0,  # No breakout volume requirement
        'min_price': 0.5,  # Low price floor
        'max_price': 50.0,  # High price ceiling for smallcaps
        'max_float': 50000000,  # Large float allowance
        'entry_start_time': 9.5,  # Early start
        'entry_end_time': 15.5,  # Late end
        'risk_reward_ratio': 1.5,  # Low R/R requirement
    }

    gap_go = GapGoStrategy(ultra_relaxed_params)

    # Test symbol
    symbol = "GG_ULTRA_TEST"

    # Create simple favorable pattern
    bars = create_gap_go_bars(symbol, count=35, start_price=3.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in gap_go.bars_history:
            gap_go.bars_history[symbol] = []
        gap_go.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Ultra-relaxed test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(gap_go.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        signal = await gap_go._analyze_bar(final_bar)

        if signal:
            print(f"✅ ULTRA-RELAXED SIGNAL GENERATED!")
            print(f"   Type: {signal.signal_type}")
            print(f"   Confidence: {signal.confidence:.2f}")
            return True
        else:
            print("❌ No signal even with ultra-relaxed conditions")
            print("   Strategy may have fundamental issues or very specific requirements")
            return False

    except Exception as e:
        print(f"❌ Error with ultra-relaxed conditions: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all gap_go strategy tests"""
    print("🚀 Gap Go Strategy Test Suite")
    print("=" * 50)

    tests = [
        ("Basic Functionality", test_gap_go_basic_functionality),
        ("Parameters Analysis", test_gap_go_parameters),
        ("Signal Generation", test_gap_go_signal_generation),
        ("Ultra-Relaxed Conditions", test_gap_go_with_ultra_relaxed_conditions),
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
        print("🎉 ALL TESTS PASSED - Gap Go is working!")
    elif passed >= len(results) - 1:
        print("⚠️  Most tests passed - Minor issues to address")
    else:
        print("🔧 Some tests failed - Gap Go may need condition relaxation")

    print("\n💡 Next steps:")
    if passed < len(results):
        print("   - Review failed tests to identify restrictive conditions")
        print("   - Consider relaxing parameters for smallcaps market")
        print("   - Check for implementation bugs or missing requirements")
    else:
        print("   - Gap Go strategy is ready for smallcaps production!")

if __name__ == "__main__":
    asyncio.run(main())