"""
Bull Flag Strategy Integration Test
Tests the integration of Bull Flag as 4th core strategy in RealisticStrategyEngine
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import MarketData
from strategies.realistic_strategy_engine import RealisticStrategyEngine


async def test_bull_flag_selection():
    """Test that Bull Flag strategy is selected correctly"""
    print("🏴 Testing Bull Flag Integration in RealisticStrategyEngine")
    print("=" * 60)

    # Initialize strategy engine
    engine = RealisticStrategyEngine()
    await engine.initialize()

    print(f"✅ Core strategies: {list(engine.core_strategies.keys())}")
    print()

    # Test scenarios for Bull Flag selection
    test_scenarios = [
        {
            'name': 'PERFECT_BULL_FLAG',
            'symbol': 'FLAGTEST',
            'prev_close': 10.00,
            'avg_volume': 100_000,
            'data': (10.20, 10.45, 10.15, 10.45, 180_000),  # 2% gap, 1.8x volume, bullish close
            'expected': 'bull_flag',
            'reason': '2% gap + 1.8x volume + bullish trend should trigger Bull Flag'
        },
        {
            'name': 'BIG_GAP_GO',
            'symbol': 'GAPTEST',
            'prev_close': 8.50,
            'avg_volume': 150_000,
            'data': (11.50, 11.80, 11.40, 11.75, 450_000),  # 35% gap, 3x volume
            'expected': 'gap_go',
            'reason': 'Large gap should trigger Gap Go, not Bull Flag'
        },
        {
            'name': 'NEWS_EXPLOSION',
            'symbol': 'NEWSTEST',
            'prev_close': 12.25,
            'avg_volume': 200_000,
            'data': (12.45, 13.80, 12.35, 13.65, 1_000_000),  # 1% gap, 5x volume
            'expected': 'daily_plays',
            'reason': 'Explosive volume should trigger Daily Plays'
        },
        {
            'name': 'SMALL_GAP_FLAG',
            'symbol': 'SMALLFLAG',
            'prev_close': 7.50,
            'avg_volume': 80_000,
            'data': (7.65, 7.85, 7.60, 7.85, 200_000),  # 1.7% gap, 2.5x volume, strong bullish close
            'expected': 'bull_flag',
            'reason': 'Small gap with good volume should trigger Bull Flag'
        },
        {
            'name': 'LOW_VOLUME_TECHNICAL',
            'symbol': 'TECHTEST',
            'prev_close': 11.40,
            'avg_volume': 90_000,
            'data': (11.55, 11.85, 11.50, 11.78, 110_000),  # 1.3% gap, 1.2x volume
            'expected': 'macdv',
            'reason': 'Low volume should fall back to MACDV'
        }
    ]

    for scenario in test_scenarios:
        print(f"🧪 Testing: {scenario['name']}")
        print(f"   Expected: {scenario['expected']}")
        print(f"   Reason: {scenario['reason']}")

        # Create market data
        timestamp = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        open_p, high, low, close, volume = scenario['data']

        data = MarketData(
            symbol=scenario['symbol'],
            timestamp=timestamp,
            open=open_p,
            high=high,
            low=low,
            close=close,
            volume=volume
        )
        data.prev_close = scenario['prev_close']
        data.avg_volume = scenario['avg_volume']

        # Test strategy selection
        try:
            signals = await engine.analyze(scenario['symbol'], data)
            selected_strategy = engine.switch_limiter.get_current_strategy(scenario['symbol'])

            if selected_strategy == scenario['expected']:
                print(f"   ✅ PASS: Selected {selected_strategy}")
            else:
                print(f"   ❌ FAIL: Expected {scenario['expected']}, got {selected_strategy}")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        print()

    print("🏴 Bull Flag Integration Test Complete")


async def test_bull_flag_priority():
    """Test Bull Flag priority in strategy selection"""
    print("🎯 Testing Bull Flag Priority Rules")
    print("=" * 40)

    engine = RealisticStrategyEngine()
    await engine.initialize()

    # Test priority scenarios
    priority_tests = [
        {
            'gap': 4.0, 'volume': 2.5,
            'expected': 'gap_go',
            'reason': 'Gap Go has priority over Bull Flag for gaps >=3%'
        },
        {
            'gap': 2.5, 'volume': 4.0,
            'expected': 'bull_flag',  # Should be bull_flag due to 1.5-3% range
            'reason': 'Bull Flag should trigger for moderate gaps with good volume'
        },
        {
            'gap': 1.0, 'volume': 3.5,
            'expected': 'daily_plays',
            'reason': 'Daily Plays has priority for explosive volume >=3x'
        }
    ]

    for i, test in enumerate(priority_tests):
        print(f"Priority Test {i+1}: Gap {test['gap']}%, Volume {test['volume']}x")
        print(f"   Expected: {test['expected']}")
        print(f"   Reason: {test['reason']}")

        # Create test data
        prev_close = 10.0
        open_price = prev_close * (1 + test['gap']/100)
        close_price = open_price * 1.02  # Small bullish move
        volume = int(100_000 * test['volume'])

        timestamp = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        data = MarketData(
            symbol=f"PRIORITY{i+1}",
            timestamp=timestamp,
            open=open_price,
            high=close_price * 1.01,
            low=open_price * 0.99,
            close=close_price,
            volume=volume
        )
        data.prev_close = prev_close
        data.avg_volume = 100_000

        try:
            await engine.analyze(f"PRIORITY{i+1}", data)
            selected = engine.switch_limiter.get_current_strategy(f"PRIORITY{i+1}")

            if selected == test['expected']:
                print(f"   ✅ CORRECT: {selected}")
            else:
                print(f"   ⚠️ DIFFERENT: Expected {test['expected']}, got {selected}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        print()


async def main():
    """Run Bull Flag integration tests"""
    await test_bull_flag_selection()
    print()
    await test_bull_flag_priority()

    print("🎉 All Bull Flag integration tests completed!")


if __name__ == "__main__":
    asyncio.run(main())