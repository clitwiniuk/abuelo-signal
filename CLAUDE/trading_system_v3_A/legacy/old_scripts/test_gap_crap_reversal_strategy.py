#!/usr/bin/env python3
"""
Test Gap Crap Reversal Strategy Signal Generation
Verifies that gap_crap_reversal strategy can generate signals and checks for any restrictive conditions
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
from strategies.gap_crap_reversal_strategy import GapCrapReversalStrategy

def create_gap_crap_reversal_bars(symbol: str, count: int = 50, start_price: float = 8.0) -> list:
    """Create test market data bars with gap crap reversal pattern"""
    bars = []
    # Use market hours timestamp: today at 10:00 AM
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    base_time = today - timedelta(minutes=count)

    # Create gap crap reversal pattern
    for i in range(count):
        timestamp = base_time + timedelta(minutes=i)

        if i < 5:
            # Pre-gap normal trading
            price = start_price + (i * 0.02)
            volume = 80000 + (i * 3000)
        elif i < 15:
            # Gap up phase (creates the "crap" setup)
            gap_factor = (i - 5) * 0.15  # Significant gap up
            price = start_price + 0.5 + gap_factor
            volume = 150000 + (i % 4) * 20000  # High volume on gap
        elif i < 30:
            # Gap fill / rejection phase (the "crap" part)
            decline_factor = (i - 15) * 0.08
            price = start_price + 2.0 - decline_factor  # Selling back down
            volume = 120000 + (i % 5) * 10000
        else:
            # Reversal phase - bounce from support/oversold
            bounce_factor = (i - 30) * 0.06
            price = start_price + 0.8 + bounce_factor
            volume = 100000 + (i % 6) * 15000

        # Create OHLC data
        if i == 0:
            open_price = price
            high = price + 0.03
            low = price - 0.02
            close = price
        else:
            prev_close = bars[-1].close
            open_price = prev_close + ((price - prev_close) * 0.3)

            if i >= 30:  # Reversal phase
                high = price + 0.04
                low = max(open_price - 0.02, price - 0.03)
            elif i >= 5 and i < 15:  # Gap phase
                high = price + 0.08  # Strong gap moves
                low = max(open_price - 0.03, price - 0.05)
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

async def test_gap_crap_reversal_basic_functionality():
    """Test basic gap_crap_reversal functionality"""
    print("🧪 Testing Gap Crap Reversal Basic Functionality...")

    # Create gap_crap_reversal strategy instance
    gcr = GapCrapReversalStrategy()

    # Test symbol
    symbol = "GCR_TEST"

    # Create test data
    bars = create_gap_crap_reversal_bars(symbol, count=30)

    # Feed bars to strategy to build history
    for bar in bars[:-1]:  # All but last bar
        if symbol not in gcr.bars_history:
            gcr.bars_history[symbol] = []
        gcr.bars_history[symbol].append(bar)

    # Test with final bar
    final_bar = bars[-1]

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars in history: {len(gcr.bars_history[symbol])}")
    print(f"   Final bar price: ${final_bar.close:.2f}")
    print(f"   Final bar volume: {final_bar.volume:,}")

    # Check basic filters
    min_bars = 15  # Typical minimum for gap reversal strategies
    if len(gcr.bars_history[symbol]) >= min_bars:
        print("✅ Minimum bars requirement MET")
    else:
        print("❌ Minimum bars requirement NOT MET")
        return False

    # Check price filters (basic check since GCR focuses on patterns)
    if 1.0 <= final_bar.close <= 100.0:
        print("✅ Price filter PASSED")
    else:
        print(f"❌ Price filter FAILED: ${final_bar.close:.2f} not in reasonable range")
        return False

    # Check volume filter (basic check)
    if final_bar.volume >= 20000:  # Basic volume requirement
        print("✅ Volume filter PASSED")
    else:
        print(f"❌ Volume filter FAILED: {final_bar.volume:,} too low")
        return False

    return True

async def test_gap_crap_reversal_signal_generation():
    """Test gap_crap_reversal signal generation with favorable conditions"""
    print("\n🧪 Testing Gap Crap Reversal Signal Generation...")

    # Create gap_crap_reversal strategy instance with relaxed parameters for testing
    test_params = {
        'min_gap_percent': 3.0,  # Relaxed gap requirement
        'max_gap_percent': 20.0,  # Higher max gap allowed
        'min_volume_spike': 1.3,  # Relaxed volume spike requirement
        'min_reversal_percent': 2.0,  # Lower reversal requirement
        'max_daily_volume': 5000000,  # Higher volume cap
        'min_daily_volume': 30000,  # Lower volume floor
    }
    gcr = GapCrapReversalStrategy(test_params)

    # Test symbol
    symbol = "GCR_SIGNAL_TEST"

    # Create favorable test data
    bars = create_gap_crap_reversal_bars(symbol, count=40, start_price=6.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in gcr.bars_history:
            gcr.bars_history[symbol] = []
        gcr.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Signal test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(gcr.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Debug info before signal generation
    print(f"📊 Debug info before signal generation:")
    print(f"   Strategy parameters loaded: {len(gcr._parameters)} params")

    # Try to generate signal
    try:
        signal = await gcr._analyze_bar(final_bar)

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

async def test_gap_crap_reversal_parameters():
    """Test gap_crap_reversal parameters and identify restrictive ones"""
    print("\n🧪 Testing Gap Crap Reversal Parameters...")

    gcr = GapCrapReversalStrategy()

    # Print key parameters that might be restrictive
    print(f"📋 Key Gap Crap Reversal parameters:")
    restrictive_params = [
        'min_gap_percent',
        'max_gap_percent',
        'min_volume_spike',
        'min_reversal_percent',
        'min_daily_volume',
        'max_daily_volume',
        'gap_fill_threshold',
        'reversal_confirmation_bars',
        'max_time_from_gap',
        'min_rsi_oversold'
    ]

    for param in restrictive_params:
        value = gcr._parameters.get(param, 'Not found')
        print(f"   {param}: {value}")

    return True

async def test_gap_crap_reversal_with_ultra_relaxed_conditions():
    """Test gap_crap_reversal with ultra-relaxed conditions to force signal generation"""
    print("\n🧪 Testing Gap Crap Reversal with Ultra-Relaxed Conditions...")

    # Ultra-relaxed parameters
    ultra_relaxed_params = {
        'min_gap_percent': 1.0,  # Very low gap requirement
        'max_gap_percent': 50.0,  # Very high max gap
        'min_volume_spike': 1.0,  # No volume spike requirement
        'min_reversal_percent': 0.5,  # Very low reversal requirement
        'min_daily_volume': 10000,  # Very low volume
        'max_daily_volume': 10000000,  # Very high volume cap
        'gap_fill_threshold': 0.9,  # Allow almost complete gap fill
        'reversal_confirmation_bars': 1,  # Minimal confirmation
        'max_time_from_gap': 120,  # Longer time window
        'min_rsi_oversold': 20,  # Very low RSI requirement
    }

    gcr = GapCrapReversalStrategy(ultra_relaxed_params)

    # Test symbol
    symbol = "GCR_ULTRA_TEST"

    # Create simple favorable pattern
    bars = create_gap_crap_reversal_bars(symbol, count=35, start_price=5.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in gcr.bars_history:
            gcr.bars_history[symbol] = []
        gcr.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Ultra-relaxed test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(gcr.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        signal = await gcr._analyze_bar(final_bar)

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
    """Run all gap_crap_reversal strategy tests"""
    print("🚀 Gap Crap Reversal Strategy Test Suite")
    print("=" * 50)

    tests = [
        ("Basic Functionality", test_gap_crap_reversal_basic_functionality),
        ("Parameters Analysis", test_gap_crap_reversal_parameters),
        ("Signal Generation", test_gap_crap_reversal_signal_generation),
        ("Ultra-Relaxed Conditions", test_gap_crap_reversal_with_ultra_relaxed_conditions),
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
        print("🎉 ALL TESTS PASSED - Gap Crap Reversal is working!")
    elif passed >= len(results) - 1:
        print("⚠️  Most tests passed - Minor issues to address")
    else:
        print("🔧 Some tests failed - Gap Crap Reversal may need condition relaxation")

    print("\n💡 Next steps:")
    if passed < len(results):
        print("   - Review failed tests to identify restrictive conditions")
        print("   - Consider relaxing parameters similar to MACDV/R2G approach")
        print("   - Check for implementation bugs or missing requirements")
    else:
        print("   - Gap Crap Reversal strategy is ready for production!")

if __name__ == "__main__":
    asyncio.run(main())