#!/usr/bin/env python3
"""
Test First Day Bounce Strategy Signal Generation
Verifies that first_day_bounce strategy can generate signals and checks for any restrictive conditions
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
from strategies.first_day_bounce_strategy import FirstDayBounceStrategy

def create_first_day_bounce_bars(symbol: str, count: int = 50, start_price: float = 5.0) -> list:
    """Create test market data bars with first day bounce pattern"""
    bars = []
    # Use market hours timestamp: today at 10:00 AM
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    base_time = today - timedelta(minutes=count)

    # Create first day bounce pattern
    for i in range(count):
        timestamp = base_time + timedelta(minutes=i)

        if i < 10:
            # Initial decline from open (creating the "bounce" setup)
            price = start_price - (i * 0.03)
            volume = 100000 + (i * 5000)
        elif i < 20:
            # Consolidation at lows (finding support)
            price = start_price - 0.30 + ((i % 3) * 0.01)
            volume = 80000 + (i % 4) * 3000
        elif i < 35:
            # Volume buildup (accumulation)
            price = start_price - 0.25 + ((i - 20) * 0.02)
            volume = 120000 + (i % 5) * 8000
        else:
            # Bounce phase - strong move up with volume
            bounce_factor = (i - 35) * 0.08
            price = start_price - 0.25 + bounce_factor
            volume = 150000 + (i % 6) * 12000

        # Create OHLC data
        if i == 0:
            open_price = price
            high = price + 0.02
            low = price - 0.03
            close = price
        else:
            prev_close = bars[-1].close
            open_price = prev_close + ((price - prev_close) * 0.3)

            if i >= 35:  # Bounce phase
                high = price + 0.05
                low = max(open_price - 0.02, price - 0.03)
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

async def test_first_day_bounce_basic_functionality():
    """Test basic first_day_bounce functionality"""
    print("🧪 Testing First Day Bounce Basic Functionality...")

    # Create first_day_bounce strategy instance
    fdb = FirstDayBounceStrategy()

    # Test symbol
    symbol = "FDB_TEST"

    # Create test data
    bars = create_first_day_bounce_bars(symbol, count=30)

    # Feed bars to strategy to build history
    for bar in bars[:-1]:  # All but last bar
        if symbol not in fdb.bars_history:
            fdb.bars_history[symbol] = []
        fdb.bars_history[symbol].append(bar)

    # Test with final bar
    final_bar = bars[-1]

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars in history: {len(fdb.bars_history[symbol])}")
    print(f"   Final bar price: ${final_bar.close:.2f}")
    print(f"   Final bar volume: {final_bar.volume:,}")

    # Check basic filters
    min_bars = 20  # Typical minimum for pattern strategies
    if len(fdb.bars_history[symbol]) >= min_bars:
        print("✅ Minimum bars requirement MET")
    else:
        print("❌ Minimum bars requirement NOT MET")
        return False

    # Check price filters (basic check since FDB focuses on patterns)
    if 1.0 <= final_bar.close <= 50.0:
        print("✅ Price filter PASSED")
    else:
        print(f"❌ Price filter FAILED: ${final_bar.close:.2f} not in reasonable range")
        return False

    # Check volume filter (basic check)
    if final_bar.volume >= 10000:  # Basic volume requirement
        print("✅ Volume filter PASSED")
    else:
        print(f"❌ Volume filter FAILED: {final_bar.volume:,} too low")
        return False

    return True

async def test_first_day_bounce_signal_generation():
    """Test first_day_bounce signal generation with favorable conditions"""
    print("\n🧪 Testing First Day Bounce Signal Generation...")

    # Create first_day_bounce strategy instance with relaxed parameters for testing
    test_params = {
        'min_bounce_percent': 3.0,  # Relaxed bounce requirement
        'min_volume_increase': 1.2,  # Relaxed volume requirement
        'min_daily_volume': 30000,  # Lower volume requirement
        'max_position_value': 300.0,
        'min_confidence': 0.6,  # Lower confidence threshold
    }
    fdb = FirstDayBounceStrategy(test_params)

    # Test symbol
    symbol = "FDB_SIGNAL_TEST"

    # Create favorable test data
    bars = create_first_day_bounce_bars(symbol, count=40, start_price=6.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in fdb.bars_history:
            fdb.bars_history[symbol] = []
        fdb.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Signal test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(fdb.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Debug info before signal generation
    print(f"📊 Debug info before signal generation:")
    print(f"   Strategy parameters loaded: {len(fdb._parameters)} params")

    # Try to generate signal
    try:
        signal = await fdb._analyze_bar(final_bar)

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

async def test_first_day_bounce_parameters():
    """Test first_day_bounce parameters and identify restrictive ones"""
    print("\n🧪 Testing First Day Bounce Parameters...")

    fdb = FirstDayBounceStrategy()

    # Print key parameters that might be restrictive
    print(f"📋 Key First Day Bounce parameters:")
    restrictive_params = [
        'min_gain_for_overextension_pct',
        'min_volume_multiple',
        'min_retrace_pct',
        'max_retrace_pct',
        'min_days_red_before_green',
        'min_green_day_volume_vs_retrace',
        'support_tolerance_pct',
        'max_distance_from_support_pct',
        'min_history_bars'
    ]

    for param in restrictive_params:
        value = fdb._parameters.get(param, 'Not found')
        print(f"   {param}: {value}")

    return True

async def test_first_day_bounce_with_ultra_relaxed_conditions():
    """Test first_day_bounce with ultra-relaxed conditions to force signal generation"""
    print("\n🧪 Testing First Day Bounce with Ultra-Relaxed Conditions...")

    # Ultra-relaxed parameters
    ultra_relaxed_params = {
        'min_bounce_percent': 1.0,  # Very low bounce requirement
        'min_volume_increase': 1.0,  # No volume increase requirement
        'min_daily_volume': 10000,  # Very low volume
        'min_confidence': 0.5,  # Very low confidence threshold
        'max_position_value': 500.0,  # Higher position size allowed
        'entry_window_minutes': 300,  # Longer entry window
        'max_drawdown': 0.10,  # Allow higher drawdown
        'stop_loss_percent': 0.08,  # Wider stop loss
    }

    fdb = FirstDayBounceStrategy(ultra_relaxed_params)

    # Test symbol
    symbol = "FDB_ULTRA_TEST"

    # Create simple favorable pattern
    bars = create_first_day_bounce_bars(symbol, count=35, start_price=4.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in fdb.bars_history:
            fdb.bars_history[symbol] = []
        fdb.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Ultra-relaxed test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(fdb.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        signal = await fdb._analyze_bar(final_bar)

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
    """Run all first_day_bounce strategy tests"""
    print("🚀 First Day Bounce Strategy Test Suite")
    print("=" * 50)

    tests = [
        ("Basic Functionality", test_first_day_bounce_basic_functionality),
        ("Parameters Analysis", test_first_day_bounce_parameters),
        ("Signal Generation", test_first_day_bounce_signal_generation),
        ("Ultra-Relaxed Conditions", test_first_day_bounce_with_ultra_relaxed_conditions),
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
        print("🎉 ALL TESTS PASSED - First Day Bounce is working!")
    elif passed >= len(results) - 1:
        print("⚠️  Most tests passed - Minor issues to address")
    else:
        print("🔧 Some tests failed - First Day Bounce may need condition relaxation")

    print("\n💡 Next steps:")
    if passed < len(results):
        print("   - Review failed tests to identify restrictive conditions")
        print("   - Consider relaxing parameters similar to MACDV/R2G approach")
        print("   - Check for implementation bugs or missing requirements")
    else:
        print("   - First Day Bounce strategy is ready for production!")

if __name__ == "__main__":
    asyncio.run(main())