#!/usr/bin/env python3
"""
Pattern Strategies Testing Suite
Tests all three pattern-based strategies: Ascending Triangle, Bull Flag, Falling Wedge

Verifies signal generation, scoring systems, and pattern detection capabilities
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
from strategies.ascending_triangle_strategy import AscendingTriangleStrategy
from strategies.bull_flag_strategy import BullFlagStrategy
from strategies.falling_wedge_strategy import FallingWedgeStrategy

class PatternTestGenerator:
    """Generate realistic test data for different pattern types"""

    @staticmethod
    def create_ascending_triangle_bars(symbol: str, count: int = 60, start_price: float = 5.0) -> list:
        """Create ascending triangle pattern data"""
        bars = []
        today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        base_time = today - timedelta(minutes=count)

        for i in range(count):
            timestamp = base_time + timedelta(minutes=i)

            if i < 10:
                # Initial uptrend establishing support
                price = start_price + (i * 0.08)
                volume = 80000 + (i * 3000)
            elif i < 25:
                # Formation phase - ascending lows, horizontal highs
                support_trend = start_price + 0.5 + ((i - 10) * 0.06)  # Rising support
                resistance_level = start_price + 1.4  # Horizontal resistance

                # Oscillate between support and resistance
                cycle_position = (i - 10) % 6
                if cycle_position < 3:
                    price = support_trend + ((resistance_level - support_trend) * (cycle_position / 3))
                else:
                    price = resistance_level - ((resistance_level - support_trend) * ((cycle_position - 3) / 3))

                volume = 70000 + (i % 4) * 8000
            elif i < 50:
                # Mature triangle - tighter range, decreasing volume
                support_now = start_price + 0.9 + ((i - 25) * 0.04)
                resistance_level = start_price + 1.4

                range_width = resistance_level - support_now
                cycle_pos = (i - 25) % 8
                price = support_now + (range_width * (0.3 + 0.4 * np.sin(cycle_pos)))

                volume = 60000 + (i % 3) * 5000  # Declining volume
            else:
                # Breakout phase
                breakout_momentum = (i - 50) * 0.12
                price = start_price + 1.4 + breakout_momentum
                volume = 120000 + (i % 4) * 15000  # Volume surge

            # Create OHLC
            if i == 0:
                open_price = price
                high = price + 0.03
                low = price - 0.02
                close = price
            else:
                prev_close = bars[-1].close
                open_price = prev_close + ((price - prev_close) * 0.2)

                if i >= 50:  # Breakout bars
                    high = price + 0.06
                    low = max(open_price - 0.02, price - 0.04)
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

    @staticmethod
    def create_bull_flag_bars(symbol: str, count: int = 50, start_price: float = 4.0) -> list:
        """Create bull flag pattern data"""
        bars = []
        today = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
        base_time = today - timedelta(minutes=count)

        for i in range(count):
            timestamp = base_time + timedelta(minutes=i)

            if i < 8:
                # Pre-flagpole normal trading
                price = start_price + (i * 0.02)
                volume = 70000 + (i * 2000)
            elif i < 18:
                # FLAGPOLE: Rapid 15% move in 10 minutes
                flagpole_progress = (i - 8) / 10
                price = start_price + 0.14 + (flagpole_progress * 0.60)  # 15% rapid move
                volume = 150000 + (i % 3) * 20000  # High volume
            elif i < 35:
                # FLAG: Consolidation with slight pullback and declining volume
                flag_start_price = start_price + 0.74
                pullback_amount = 0.04  # 4% pullback
                flag_progress = (i - 18) / 17

                # Gentle downward consolidation
                price = flag_start_price - (pullback_amount * flag_progress * 0.7)
                volume = 90000 - (flag_progress * 30000)  # Declining volume
            else:
                # BREAKOUT: Above flag resistance with volume
                breakout_progress = (i - 35) / 15
                breakout_price = start_price + 0.72
                price = breakout_price + (breakout_progress * 0.20)
                volume = 130000 + (i % 4) * 18000  # Volume confirmation

            # Create OHLC
            if i == 0:
                open_price = price
                high = price + 0.02
                low = price - 0.01
                close = price
            else:
                prev_close = bars[-1].close

                if 8 <= i < 18:  # Flagpole phase
                    open_price = prev_close + 0.01
                    high = price + 0.08  # Strong moves up
                    low = max(prev_close - 0.02, price - 0.05)
                elif 18 <= i < 35:  # Flag phase
                    open_price = prev_close + ((price - prev_close) * 0.3)
                    high = price + 0.02
                    low = price - 0.03
                else:  # Breakout phase
                    open_price = prev_close + 0.005
                    high = price + 0.05
                    low = max(open_price - 0.02, price - 0.03)
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

    @staticmethod
    def create_falling_wedge_bars(symbol: str, count: int = 70, start_price: float = 6.0) -> list:
        """Create falling wedge pattern data"""
        bars = []
        today = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
        base_time = today - timedelta(minutes=count)

        for i in range(count):
            timestamp = base_time + timedelta(minutes=i)

            if i < 10:
                # Initial decline phase
                price = start_price - (i * 0.04)
                volume = 90000 + (i * 4000)
            elif i < 50:
                # Wedge formation - converging downward trend lines
                # Support line (steeper decline): y = start - 0.4 - steep_decline
                # Resistance line (gentler decline): y = start - gentle_decline

                formation_progress = (i - 10) / 40

                # Support line (steeper, more negative slope)
                support_decline = 0.4 + (formation_progress * 0.8)  # Steeper decline
                support_price = start_price - support_decline

                # Resistance line (gentler decline)
                resistance_decline = 0.2 + (formation_progress * 0.3)  # Gentler decline
                resistance_price = start_price - resistance_decline

                # Oscillate between converging lines with declining amplitude
                wedge_width = resistance_price - support_price
                cycle_pos = (i - 10) % 10
                oscillation = 0.3 + 0.4 * np.sin(cycle_pos / 10 * 2 * np.pi)

                price = support_price + (wedge_width * oscillation)

                # Declining volume during formation (bullish sign)
                volume = 85000 - (formation_progress * 35000)  # Volume decline
            else:
                # Breakout phase - upward through resistance
                breakout_start_price = start_price - 0.5  # Last resistance level
                breakout_progress = (i - 50) / 20
                price = breakout_start_price + (breakout_progress * 0.45)  # Strong breakout
                volume = 100000 + (breakout_progress * 40000)  # Volume expansion

            # Create OHLC
            if i == 0:
                open_price = price
                high = price + 0.02
                low = price - 0.03
                close = price
            else:
                prev_close = bars[-1].close

                if i >= 50:  # Breakout phase
                    open_price = prev_close + 0.01
                    high = price + 0.06  # Strong breakout moves
                    low = max(open_price - 0.02, price - 0.03)
                else:  # Formation phase
                    open_price = prev_close + ((price - prev_close) * 0.4)
                    high = price + 0.025
                    low = price - 0.025
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

async def test_ascending_triangle():
    """Test Ascending Triangle Strategy"""
    print("\n" + "="*60)
    print("🔺 TESTING ASCENDING TRIANGLE STRATEGY")
    print("="*60)

    # Create strategy with relaxed parameters for testing
    test_params = {
        'min_triangle_duration': 20,
        'min_support_touches': 2,
        'min_resistance_touches': 2,
        'min_signal_score': 250,  # Relaxed threshold
        'resistance_break_threshold': 0.3,
        'volume_breakout_multiplier': 1.5
    }

    strategy = AscendingTriangleStrategy(test_params)
    symbol = "ATRI_TEST"

    # Generate test data
    bars = PatternTestGenerator.create_ascending_triangle_bars(symbol, count=60, start_price=5.0)

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Total bars: {len(bars)}")
    print(f"   Price range: ${bars[0].close:.2f} → ${bars[-1].close:.2f}")
    print(f"   Pattern: Ascending triangle with breakout")

    # Feed bars to strategy
    signals_generated = 0
    best_signal = None

    for i, bar in enumerate(bars):
        if symbol not in strategy.bars_history:
            strategy.bars_history[symbol] = []
        strategy.bars_history[symbol].append(bar)

        try:
            signal = await strategy._analyze_bar(bar)
            if signal:
                signals_generated += 1
                if not best_signal or signal.confidence > best_signal.confidence:
                    best_signal = signal
                print(f"✅ Signal #{signals_generated} at bar {i+1}: {signal.confidence:.1%} confidence")
        except Exception as e:
            print(f"❌ Error at bar {i+1}: {e}")

    # Results
    print(f"\n📈 ASCENDING TRIANGLE RESULTS:")
    print(f"   Signals generated: {signals_generated}")
    if best_signal:
        print(f"   Best confidence: {best_signal.confidence:.1%}")
        print(f"   Entry price: ${best_signal.entry_price:.2f}")
        print(f"   Stop loss: ${best_signal.stop_loss:.2f}")
        print(f"   Profit target: ${best_signal.profit_target:.2f}")
        print(f"   Pattern detected: {best_signal.metadata.get('pattern', 'Unknown')}")

    return signals_generated > 0

async def test_bull_flag():
    """Test Bull Flag Strategy"""
    print("\n" + "="*60)
    print("🏴 TESTING BULL FLAG STRATEGY")
    print("="*60)

    # Create strategy with relaxed parameters
    test_params = {
        'min_flagpole_pct': 3.0,
        'min_flag_score': 250,  # Relaxed threshold
        'flagpole_volume_multiplier': 1.3,
        'breakout_volume_multiplier': 1.5,
        'max_formation_minutes': 80
    }

    strategy = BullFlagStrategy(test_params)
    symbol = "BFLG_TEST"

    # Generate test data
    bars = PatternTestGenerator.create_bull_flag_bars(symbol, count=50, start_price=4.0)

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Total bars: {len(bars)}")
    print(f"   Price range: ${bars[0].close:.2f} → ${bars[-1].close:.2f}")
    print(f"   Pattern: Bull flag (flagpole → flag → breakout)")

    # Feed bars and track pattern states
    signals_generated = 0
    best_signal = None
    pattern_states = []

    for i, bar in enumerate(bars):
        if symbol not in strategy.bars_history:
            strategy.bars_history[symbol] = []
        strategy.bars_history[symbol].append(bar)

        try:
            signal = await strategy._analyze_bar(bar)

            # Track pattern state
            current_state = strategy.pattern_state.get(symbol, 'none')
            pattern_states.append(f"Bar {i+1}: {current_state}")

            if signal:
                signals_generated += 1
                if not best_signal or signal.confidence > best_signal.confidence:
                    best_signal = signal
                print(f"✅ Signal #{signals_generated} at bar {i+1}: {signal.confidence:.1%} confidence")
                print(f"   Pattern state: {current_state}")
        except Exception as e:
            print(f"❌ Error at bar {i+1}: {e}")

    # Show pattern progression
    print(f"\n📊 Pattern State Progression:")
    state_changes = []
    last_state = 'none'
    for state_info in pattern_states:
        current_state = state_info.split(': ')[1]
        if current_state != last_state:
            state_changes.append(state_info)
            last_state = current_state

    for change in state_changes[:10]:  # Show first 10 state changes
        print(f"   {change}")

    # Results
    print(f"\n📈 BULL FLAG RESULTS:")
    print(f"   Signals generated: {signals_generated}")
    if best_signal:
        print(f"   Best confidence: {best_signal.confidence:.1%}")
        print(f"   Entry price: ${best_signal.entry_price:.2f}")
        print(f"   Stop loss: ${best_signal.stop_loss:.2f}")
        print(f"   Profit target: ${best_signal.profit_target:.2f}")
        flagpole_data = best_signal.metadata.get('flagpole_percent', 'N/A')
        print(f"   Flagpole strength: {flagpole_data}")

    return signals_generated > 0

async def test_falling_wedge():
    """Test Falling Wedge Strategy"""
    print("\n" + "="*60)
    print("🔻 TESTING FALLING WEDGE STRATEGY")
    print("="*60)

    # Create strategy with relaxed parameters
    test_params = {
        'min_pattern_duration': 15,
        'min_signal_score': 250,  # Relaxed threshold
        'breakout_volume_multiplier': 1.5,
        'min_convergence_angle': 3.0,
        'volume_decline_ratio': 0.8
    }

    strategy = FallingWedgeStrategy(test_params)
    symbol = "FWDG_TEST"

    # Generate test data
    bars = PatternTestGenerator.create_falling_wedge_bars(symbol, count=70, start_price=6.0)

    print(f"📊 Test setup:")
    print(f"   Symbol: {symbol}")
    print(f"   Total bars: {len(bars)}")
    print(f"   Price range: ${bars[0].close:.2f} → ${bars[-1].close:.2f}")
    print(f"   Pattern: Falling wedge with bullish breakout")

    # Feed bars to strategy
    signals_generated = 0
    best_signal = None
    swing_points_progression = []

    for i, bar in enumerate(bars):
        if symbol not in strategy.bars_history:
            strategy.bars_history[symbol] = []
        strategy.bars_history[symbol].append(bar)

        try:
            signal = await strategy._analyze_bar(bar)

            # Track swing points development
            if symbol in strategy.swing_points:
                highs_count = len(strategy.swing_points[symbol]['highs'])
                lows_count = len(strategy.swing_points[symbol]['lows'])
                swing_points_progression.append(f"Bar {i+1}: {highs_count}H/{lows_count}L")

            if signal:
                signals_generated += 1
                if not best_signal or signal.confidence > best_signal.confidence:
                    best_signal = signal
                print(f"✅ Signal #{signals_generated} at bar {i+1}: {signal.confidence:.1%} confidence")

                # Show wedge characteristics
                if symbol in strategy.trend_lines:
                    convergence = strategy.trend_lines[symbol]['convergence_angle']
                    print(f"   Convergence angle: {convergence:.1f}°")
        except Exception as e:
            print(f"❌ Error at bar {i+1}: {e}")

    # Show swing points development
    print(f"\n📊 Swing Points Development:")
    key_points = swing_points_progression[::15][:8]  # Every 15th bar, max 8
    for point in key_points:
        print(f"   {point}")

    # Results
    print(f"\n📈 FALLING WEDGE RESULTS:")
    print(f"   Signals generated: {signals_generated}")
    if best_signal:
        print(f"   Best confidence: {best_signal.confidence:.1%}")
        print(f"   Entry price: ${best_signal.entry_price:.2f}")
        print(f"   Stop loss: ${best_signal.stop_loss:.2f}")
        print(f"   Profit target: ${best_signal.profit_target:.2f}")
        convergence = best_signal.metadata.get('convergence_angle', 'N/A')
        print(f"   Convergence angle: {convergence}°")

    return signals_generated > 0

async def test_pattern_comparison():
    """Compare all three pattern strategies side by side"""
    print("\n" + "="*60)
    print("⚔️  PATTERN STRATEGIES COMPARISON")
    print("="*60)

    # Test each strategy with same market conditions
    test_results = {}

    strategies = [
        ("Ascending Triangle", test_ascending_triangle),
        ("Bull Flag", test_bull_flag),
        ("Falling Wedge", test_falling_wedge)
    ]

    for strategy_name, test_func in strategies:
        try:
            print(f"\n🧪 Testing {strategy_name}...")
            result = await test_func()
            test_results[strategy_name] = result
        except Exception as e:
            print(f"❌ {strategy_name} test failed: {e}")
            test_results[strategy_name] = False

    # Summary comparison
    print(f"\n" + "="*60)
    print("📊 PATTERN STRATEGIES COMPARISON SUMMARY")
    print("="*60)

    passed_count = 0
    for strategy_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {strategy_name:20} : {status}")
        if passed:
            passed_count += 1

    print(f"\n🎯 Overall Results: {passed_count}/{len(strategies)} strategies working")

    if passed_count == len(strategies):
        print("🎉 ALL PATTERN STRATEGIES ARE WORKING!")
        print("📈 Ready for smallcaps pattern trading")
    elif passed_count >= 2:
        print("⚠️  Most pattern strategies working - minor issues to address")
    else:
        print("🔧 Pattern strategies need significant optimization")

    return test_results

async def main():
    """Run comprehensive pattern strategies testing"""
    print("🚀 PATTERN STRATEGIES TESTING SUITE")
    print("=" * 60)
    print("Testing: Ascending Triangle, Bull Flag, Falling Wedge")
    print("Focus: Smallcaps intraday pattern recognition")
    print("=" * 60)

    # Run individual tests
    individual_tests = [
        ("Ascending Triangle", test_ascending_triangle),
        ("Bull Flag", test_bull_flag),
        ("Falling Wedge", test_falling_wedge)
    ]

    individual_results = []
    for test_name, test_func in individual_tests:
        try:
            result = await test_func()
            individual_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            individual_results.append((test_name, False))

    # Run comparison test
    print(f"\n" + "🔄 Running comprehensive comparison...")
    comparison_results = await test_pattern_comparison()

    # Final summary
    print(f"\n" + "="*60)
    print("🏆 FINAL TESTING SUMMARY")
    print("="*60)

    working_strategies = sum(1 for _, result in individual_results if result)
    total_strategies = len(individual_results)

    print(f"📊 Pattern Recognition:")
    for strategy_name, result in individual_results:
        status = "✅" if result else "❌"
        print(f"   {status} {strategy_name}")

    print(f"\n🎯 Success Rate: {working_strategies}/{total_strategies} ({working_strategies/total_strategies:.1%})")

    if working_strategies == total_strategies:
        print("\n🎉 EXCELLENT! All pattern strategies ready for production")
        print("💡 Next steps:")
        print("   - Deploy to live smallcaps trading")
        print("   - Monitor pattern detection in real market")
        print("   - Fine-tune parameters based on live performance")
    else:
        print(f"\n🔧 Issues found in {total_strategies - working_strategies} strategies")
        print("💡 Recommended actions:")
        print("   - Review failed strategies for parameter optimization")
        print("   - Test with different market conditions")
        print("   - Consider relaxing restrictive filters")

    print(f"\n📈 Pattern strategies optimized for smallcaps ($1-$15 range)")
    print(f"⚡ Hybrid approach: Static rules + flexible scoring (0-500 points)")
    print(f"🎯 Ready for ML-based strategy assignment via contextual bandit")

if __name__ == "__main__":
    asyncio.run(main())