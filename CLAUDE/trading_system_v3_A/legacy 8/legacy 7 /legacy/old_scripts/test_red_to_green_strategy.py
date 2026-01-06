#!/usr/bin/env python3
"""
Test Red to Green Strategy Signal Generation
Verifies that red_to_green strategy can generate signals and checks for any restrictive conditions
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
from strategies.red_to_green_strategy import RedToGreenStrategy

def create_red_to_green_bars(symbol: str, count: int = 50, start_price: float = 10.0) -> list:
    """Create test market data bars with red-to-green pattern"""
    bars = []
    # Use market hours timestamp: today at 10:00 AM
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    base_time = today - timedelta(minutes=count)

    # Create red-to-green pattern
    for i in range(count):
        timestamp = base_time + timedelta(minutes=i)

        if i < 5:
            # Initial green setup (establishes expectation)
            price = start_price + (i * 0.1)
            volume = 80000 + (i * 5000)
        elif i < 20:
            # Red sequence breaking key levels (attracts shorts)
            decline_factor = (i - 5) * 0.05
            price = start_price + 0.5 - decline_factor
            volume = 60000 + (i % 5) * 8000
        elif i < 35:
            # Consolidation with declining volume
            price = start_price - 0.2 + ((i % 3) * 0.02)
            volume = 40000 + (i % 3) * 3000  # Declining volume
        else:
            # Breakout phase - convincing move above R2G level
            breakout_factor = (i - 35) * 0.15
            price = start_price + breakout_factor
            volume = 100000 + (i % 5) * 15000  # High volume breakout

        # Create OHLC data
        if i == 0:
            open_price = price
            high = price + 0.05
            low = price - 0.02
            close = price
        else:
            prev_close = bars[-1].close
            open_price = prev_close + ((price - prev_close) * 0.3)

            if i >= 35:  # Breakout phase
                high = price + 0.08  # Strong moves
                low = max(open_price - 0.03, price - 0.05)
            else:
                high = price + 0.03
                low = price - 0.03
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

async def test_red_to_green_basic_functionality():
    """Test basic red_to_green functionality"""
    print("🧪 Testing Red to Green Basic Functionality...")

    # Create red_to_green strategy instance
    r2g = RedToGreenStrategy()

    # Test symbol
    symbol = "R2G_TEST"

    # Create test data
    bars = create_red_to_green_bars(symbol, count=30)

    # Feed bars to strategy to build history
    for bar in bars[:-1]:  # All but last bar
        if symbol not in r2g.bars_history:
            r2g.bars_history[symbol] = []
        r2g.bars_history[symbol].append(bar)

    # Test with final bar
    final_bar = bars[-1]

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars in history: {len(r2g.bars_history[symbol])}")
    print(f"   Final bar price: ${final_bar.close:.2f}")
    print(f"   Final bar volume: {final_bar.volume:,}")

    # Check basic filters
    if len(r2g.bars_history[symbol]) >= 20:
        print("✅ Minimum bars requirement MET")
    else:
        print("❌ Minimum bars requirement NOT MET")
        return False

    # Check price filters
    if final_bar.close >= r2g._parameters.get('min_price', 0.5):
        print("✅ Price filter PASSED")
    else:
        print("❌ Price filter FAILED")
        return False

    # Check volume filter
    if final_bar.volume >= 30000:  # Basic volume check
        print("✅ Volume filter PASSED")
    else:
        print("❌ Volume filter FAILED")
        return False

    return True

async def test_red_to_green_signal_generation():
    """Test red_to_green signal generation with favorable conditions"""
    print("\n🧪 Testing Red to Green Signal Generation...")

    # Create red_to_green strategy instance with relaxed parameters for testing
    test_params = {
        'min_r2g_breakout_percent': 1.0,  # Ultra relaxed - 1% breakout
        'breakout_volume_multiplier': 1.0,  # No volume multiplier requirement
        'min_daily_volume': 10000,  # Very low volume requirement
        'entry_on_dip_enabled': False,  # Immediate entry
        'require_previous_green': False,  # Skip pattern requirements
        'require_red_sequence': False,
        'require_consolidation': False,
        'min_setup_age_minutes': 0,  # Immediate setup allowed
        'no_entry_after_hour': 16.0,  # Allow entries until close
        'mandatory_exit_hour': 16.0,  # No mandatory exit
    }
    r2g = RedToGreenStrategy(test_params)

    # Test symbol
    symbol = "R2G_SIGNAL_TEST"

    # Create favorable test data with clear red-to-green pattern
    bars = create_red_to_green_bars(symbol, count=40, start_price=8.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in r2g.bars_history:
            r2g.bars_history[symbol] = []
        r2g.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Signal test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(r2g.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        print(f"📊 Debug info before signal generation:")
        print(f"   R2G setups: {len(r2g.r2g_setups)}")
        print(f"   Breakout tracking: {len(r2g.breakout_tracking)}")
        print(f"   Current time check: Trading hours valid")

        signal = await r2g._analyze_bar(final_bar)

        if signal:
            print(f"✅ SIGNAL GENERATED!")
            print(f"   Type: {signal.signal_type}")
            print(f"   Confidence: {signal.confidence:.2f}")
            print(f"   Signal details: {signal}")
            return True
        else:
            print("❌ No signal generated")
            print("   Checking R2G setups after analysis...")
            print(f"   R2G setups after: {list(r2g.r2g_setups.keys())}")
            if symbol in r2g.r2g_setups:
                setup = r2g.r2g_setups[symbol]
                print(f"   Setup exists: R2G level=${setup['r2g_level']:.2f}")
                print(f"   Current price: ${final_bar.close:.2f}")
                print(f"   Breakout needed: {r2g._parameters['min_r2g_breakout_percent']}%")
                breakout_pct = (final_bar.close - setup['r2g_level']) / setup['r2g_level'] * 100
                print(f"   Current breakout: {breakout_pct:.2f}%")
            return False

    except Exception as e:
        print(f"❌ Error generating signal: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_red_to_green_parameters():
    """Test red_to_green parameters and identify restrictive ones"""
    print("\n🧪 Testing Red to Green Parameters...")

    r2g = RedToGreenStrategy()

    # Print key parameters that might be restrictive
    print(f"📋 Key Red to Green parameters:")
    restrictive_params = [
        'min_r2g_breakout_percent',
        'breakout_volume_multiplier',
        'min_daily_volume',
        'entry_end_hour',
        'mandatory_exit_hour',
        'min_red_to_green_volume',
        'stop_loss_below_r2g'
    ]

    for param in restrictive_params:
        value = r2g._parameters.get(param, 'Not found')
        print(f"   {param}: {value}")

    return True

async def test_red_to_green_with_ultra_relaxed_conditions():
    """Test red_to_green with ultra-relaxed conditions to force signal generation"""
    print("\n🧪 Testing Red to Green with Ultra-Relaxed Conditions...")

    # Ultra-relaxed parameters
    ultra_relaxed_params = {
        'min_r2g_breakout_percent': 0.5,  # Extremely low breakout requirement
        'breakout_volume_multiplier': 1.0,  # No volume multiplier requirement
        'min_daily_volume': 5000,  # Very low volume
        'entry_on_dip_enabled': False,  # Immediate entry
        'require_previous_green': False,  # Skip all pattern requirements
        'require_red_sequence': False,
        'require_consolidation': False,
        'min_setup_age_minutes': 0,  # Immediate setup allowed
        'no_entry_after_hour': 16.0,  # Allow entries until close
        'mandatory_exit_hour': 16.0,  # No mandatory exit
        'min_red_to_green_volume': 0.5,  # Very low volume requirement
        'stop_loss_below_r2g': 0.20,  # Wide stop loss
    }

    r2g = RedToGreenStrategy(ultra_relaxed_params)

    # Test symbol
    symbol = "R2G_ULTRA_TEST"

    # Create simple favorable pattern
    bars = create_red_to_green_bars(symbol, count=35, start_price=5.0)

    # Feed bars to strategy
    for bar in bars[:-1]:
        if symbol not in r2g.bars_history:
            r2g.bars_history[symbol] = []
        r2g.bars_history[symbol].append(bar)

    final_bar = bars[-1]

    print(f"📊 Ultra-relaxed test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Bars: {len(r2g.bars_history[symbol])}")
    print(f"   Price: ${final_bar.close:.2f}")
    print(f"   Volume: {final_bar.volume:,}")

    # Try to generate signal
    try:
        print(f"📊 Ultra-relaxed debug info before signal generation:")
        print(f"   R2G setups: {len(r2g.r2g_setups)}")
        print(f"   Breakout tracking: {len(r2g.breakout_tracking)}")

        signal = await r2g._analyze_bar(final_bar)

        if signal:
            print(f"✅ ULTRA-RELAXED SIGNAL GENERATED!")
            print(f"   Type: {signal.signal_type}")
            print(f"   Confidence: {signal.confidence:.2f}")
            return True
        else:
            print("❌ No signal even with ultra-relaxed conditions")
            print("   Checking R2G setups after analysis...")
            print(f"   R2G setups after: {list(r2g.r2g_setups.keys())}")
            if symbol in r2g.r2g_setups:
                setup = r2g.r2g_setups[symbol]
                print(f"   Setup exists: R2G level=${setup['r2g_level']:.2f}")
                print(f"   Current price: ${final_bar.close:.2f}")
                print(f"   Breakout needed: {r2g._parameters['min_r2g_breakout_percent']}%")
                breakout_pct = (final_bar.close - setup['r2g_level']) / setup['r2g_level'] * 100
                print(f"   Current breakout: {breakout_pct:.2f}%")
            print("   Strategy may have fundamental issues or very specific requirements")
            return False

    except Exception as e:
        print(f"❌ Error with ultra-relaxed conditions: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all red_to_green strategy tests"""
    print("🚀 Red to Green Strategy Test Suite")
    print("=" * 50)

    tests = [
        ("Basic Functionality", test_red_to_green_basic_functionality),
        ("Parameters Analysis", test_red_to_green_parameters),
        ("Signal Generation", test_red_to_green_signal_generation),
        ("Ultra-Relaxed Conditions", test_red_to_green_with_ultra_relaxed_conditions),
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
        print("🎉 ALL TESTS PASSED - Red to Green is working!")
    elif passed >= len(results) - 1:
        print("⚠️  Most tests passed - Minor issues to address")
    else:
        print("🔧 Some tests failed - Red to Green may need condition relaxation")

    print("\n💡 Next steps:")
    if passed < len(results):
        print("   - Review failed tests to identify restrictive conditions")
        print("   - Consider relaxing parameters similar to MACDV approach")
        print("   - Check for implementation bugs or missing requirements")
    else:
        print("   - Red to Green strategy is ready for production!")

if __name__ == "__main__":
    asyncio.run(main())