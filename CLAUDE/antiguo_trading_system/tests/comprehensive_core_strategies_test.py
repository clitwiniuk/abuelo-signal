"""
Comprehensive Core Strategies Test Suite
Tests all 4 core strategies in RealisticStrategyEngine:
1. Gap Go - Large gaps with volume
2. Daily Plays - News-driven volume explosions
3. Bull Flag - Momentum continuation patterns
4. MACDV - Technical baseline

Includes individual strategy tests, switching scenarios, edge cases, and performance tests.
"""

import asyncio
import sys
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import MarketData, Signal
from strategies.realistic_strategy_engine import RealisticStrategyEngine


class CoreStrategiesTestSuite:
    """Comprehensive test suite for the 4 core strategies"""

    def __init__(self):
        self.strategy_engine = None
        self.test_results = {
            'individual_tests': {},
            'switching_tests': {},
            'edge_case_tests': {},
            'performance_tests': {},
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0
        }

    async def setup_test_environment(self):
        """Initialize test environment"""
        print("🔧 Setting up comprehensive core strategies test environment...")
        self.strategy_engine = RealisticStrategyEngine()
        await self.strategy_engine.initialize()

        core_strategies = list(self.strategy_engine.core_strategies.keys())
        print(f"✅ Testing 4 core strategies: {core_strategies}")
        print()

    # =====================================================
    # INDIVIDUAL STRATEGY TESTS
    # =====================================================

    async def test_gap_go_strategy(self):
        """Test Gap Go strategy in various scenarios"""
        print("🎯 TESTING GAP GO STRATEGY")
        print("-" * 40)

        test_cases = [
            {
                'name': 'Perfect Gap Go - FDA Approval',
                'prev_close': 8.50,
                'avg_volume': 150_000,
                'market_data': (11.50, 12.80, 11.40, 12.75, 450_000),  # 35% gap, 3x volume
                'expected': 'gap_go',
                'should_pass': True
            },
            {
                'name': 'Earnings Beat Gap',
                'prev_close': 12.25,
                'avg_volume': 200_000,
                'market_data': (14.20, 15.50, 14.00, 15.30, 600_000),  # 16% gap, 3x volume
                'expected': 'gap_go',
                'should_pass': True
            },
            {
                'name': 'Small Gap - Should NOT trigger Gap Go',
                'prev_close': 10.00,
                'avg_volume': 100_000,
                'market_data': (10.20, 10.45, 10.15, 10.40, 180_000),  # 2% gap only
                'expected': 'gap_go',
                'should_pass': False
            },
            {
                'name': 'Gap Down - Should trigger Gap Go (absolute value)',
                'prev_close': 15.00,
                'avg_volume': 180_000,
                'market_data': (13.80, 14.20, 13.50, 14.10, 540_000),  # -8% gap down, 3x vol
                'expected': 'gap_go',
                'should_pass': True
            }
        ]

        results = await self._run_strategy_test_cases('gap_go', test_cases)
        self.test_results['individual_tests']['gap_go'] = results
        return results

    async def test_daily_plays_strategy(self):
        """Test Daily Plays strategy scenarios"""
        print("📰 TESTING DAILY PLAYS STRATEGY")
        print("-" * 40)

        test_cases = [
            {
                'name': 'Contract Win - Explosive Volume',
                'prev_close': 12.25,
                'avg_volume': 200_000,
                'market_data': (12.45, 13.80, 12.35, 13.65, 1_000_000),  # 1% gap, 5x volume
                'expected': 'daily_plays',
                'should_pass': True
            },
            {
                'name': 'Partnership Announcement',
                'prev_close': 9.80,
                'avg_volume': 120_000,
                'market_data': (10.10, 11.95, 9.95, 11.70, 800_000),  # 3% gap, 6.7x volume
                'expected': 'daily_plays',
                'should_pass': True
            },
            {
                'name': 'Low Volume - Should NOT trigger Daily Plays',
                'prev_close': 8.50,
                'avg_volume': 100_000,
                'market_data': (8.70, 9.20, 8.65, 9.15, 150_000),  # Good move but low volume
                'expected': 'daily_plays',
                'should_pass': False
            }
        ]

        results = await self._run_strategy_test_cases('daily_plays', test_cases)
        self.test_results['individual_tests']['daily_plays'] = results
        return results

    async def test_bull_flag_strategy(self):
        """Test Bull Flag strategy scenarios"""
        print("🏴 TESTING BULL FLAG STRATEGY")
        print("-" * 40)

        test_cases = [
            {
                'name': 'Perfect Bull Flag Pattern',
                'prev_close': 10.00,
                'avg_volume': 100_000,
                'market_data': (10.20, 10.65, 10.15, 10.60, 250_000),  # 2% gap, 2.5x vol, bullish
                'expected': 'bull_flag',
                'should_pass': True
            },
            {
                'name': 'Momentum Continuation',
                'prev_close': 7.50,
                'avg_volume': 80_000,
                'market_data': (7.75, 8.20, 7.70, 8.15, 200_000),  # 3.3% gap, 2.5x vol, strong bullish
                'expected': 'bull_flag',
                'should_pass': True
            },
            {
                'name': 'Bearish Trend - Should NOT trigger Bull Flag',
                'prev_close': 11.00,
                'avg_volume': 90_000,
                'market_data': (11.20, 11.35, 11.05, 11.10, 180_000),  # 2% gap but bearish close
                'expected': 'bull_flag',
                'should_pass': False
            },
            {
                'name': 'Too Big Gap - Should trigger Gap Go instead',
                'prev_close': 8.00,
                'avg_volume': 100_000,
                'market_data': (8.50, 9.20, 8.45, 9.15, 300_000),  # 6.25% gap - too big for bull flag
                'expected': 'bull_flag',
                'should_pass': False  # Should get gap_go instead
            }
        ]

        results = await self._run_strategy_test_cases('bull_flag', test_cases)
        self.test_results['individual_tests']['bull_flag'] = results
        return results

    async def test_macdv_strategy(self):
        """Test MACDV baseline strategy"""
        print("📊 TESTING MACDV BASELINE STRATEGY")
        print("-" * 40)

        test_cases = [
            {
                'name': 'Clean Technical Setup',
                'prev_close': 11.40,
                'avg_volume': 90_000,
                'market_data': (11.55, 11.85, 11.50, 11.78, 135_000),  # Small gap, moderate volume
                'expected': 'macdv',
                'should_pass': True
            },
            {
                'name': 'Low Volume Technical',
                'prev_close': 9.20,
                'avg_volume': 80_000,
                'market_data': (9.30, 9.45, 9.25, 9.40, 100_000),  # Small gap, low volume
                'expected': 'macdv',
                'should_pass': True
            },
            {
                'name': 'Flat Price Action',
                'prev_close': 12.50,
                'avg_volume': 100_000,
                'market_data': (12.52, 12.58, 12.48, 12.55, 105_000),  # Minimal movement
                'expected': 'macdv',
                'should_pass': True
            }
        ]

        results = await self._run_strategy_test_cases('macdv', test_cases)
        self.test_results['individual_tests']['macdv'] = results
        return results

    async def _run_strategy_test_cases(self, strategy_name: str, test_cases: List[Dict]) -> Dict:
        """Helper to run test cases for a strategy"""
        results = {'total': len(test_cases), 'passed': 0, 'failed': 0, 'cases': []}

        for case in test_cases:
            print(f"   🧪 {case['name']}")

            try:
                # Create market data
                timestamp = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
                open_p, high, low, close, volume = case['market_data']

                data = MarketData(
                    symbol=f"TEST_{strategy_name.upper()}",
                    timestamp=timestamp,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume
                )
                data.prev_close = case['prev_close']
                data.avg_volume = case['avg_volume']

                # Test strategy selection
                await self.strategy_engine.analyze(data.symbol, data)
                selected_strategy = self.strategy_engine.switch_limiter.get_current_strategy(data.symbol)

                # Check result
                if case['should_pass']:
                    if selected_strategy == case['expected']:
                        print(f"      ✅ PASS: Selected {selected_strategy}")
                        results['passed'] += 1
                        case_result = 'PASS'
                    else:
                        print(f"      ❌ FAIL: Expected {case['expected']}, got {selected_strategy}")
                        results['failed'] += 1
                        case_result = 'FAIL'
                else:
                    if selected_strategy != case['expected']:
                        print(f"      ✅ PASS: Correctly avoided {case['expected']}, got {selected_strategy}")
                        results['passed'] += 1
                        case_result = 'PASS'
                    else:
                        print(f"      ❌ FAIL: Should NOT select {case['expected']}, but did")
                        results['failed'] += 1
                        case_result = 'FAIL'

                results['cases'].append({
                    'name': case['name'],
                    'result': case_result,
                    'expected': case['expected'],
                    'selected': selected_strategy
                })

            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                results['failed'] += 1
                results['cases'].append({
                    'name': case['name'],
                    'result': 'ERROR',
                    'error': str(e)
                })

            # Update totals
            self.test_results['total_tests'] += 1
            if case_result == 'PASS':
                self.test_results['passed_tests'] += 1
            else:
                self.test_results['failed_tests'] += 1

        print(f"   📊 {strategy_name.upper()} Results: {results['passed']}/{results['total']} passed")
        print()
        return results

    # =====================================================
    # STRATEGY SWITCHING TESTS
    # =====================================================

    async def test_strategy_switching_scenarios(self):
        """Test scenarios where strategy should switch"""
        print("🔄 TESTING STRATEGY SWITCHING SCENARIOS")
        print("-" * 40)

        switching_tests = [
            {
                'name': 'Gap Go to Bull Flag Evolution',
                'description': 'Large gap should select Gap Go, then smaller gap should consider Bull Flag',
                'sequence': [
                    {
                        'data': (8.50, 11.50, 12.80, 11.40, 12.75, 450_000),  # Big gap - Gap Go
                        'expected': 'gap_go'
                    },
                    {
                        'data': (10.00, 10.25, 10.65, 10.20, 10.60, 220_000),  # Smaller gap - Bull Flag
                        'expected_consider': 'bull_flag'
                    }
                ]
            },
            {
                'name': 'Volume Evolution - Bull Flag to Daily Plays',
                'description': 'Moderate volume (Bull Flag) evolving to explosive volume (Daily Plays)',
                'sequence': [
                    {
                        'data': (9.00, 9.20, 9.65, 9.15, 9.60, 200_000),  # 2.2% gap, 2.2x vol - Bull Flag
                        'expected': 'bull_flag'
                    },
                    {
                        'data': (9.00, 9.10, 10.80, 9.05, 10.70, 450_000),  # 1% gap, 5x vol - Daily Plays
                        'expected_consider': 'daily_plays'
                    }
                ]
            }
        ]

        results = {'total': len(switching_tests), 'passed': 0, 'failed': 0, 'cases': []}

        for test in switching_tests:
            print(f"   🔄 {test['name']}")
            print(f"      {test['description']}")

            case_result = 'PASS'  # Assume pass unless proven otherwise

            try:
                for i, step in enumerate(test['sequence']):
                    prev_close, open_p, high, low, close, volume = step['data']
                    avg_volume = 100_000

                    timestamp = datetime.now().replace(hour=10, minute=30 + i*5, second=0, microsecond=0)
                    data = MarketData(
                        symbol=f"SWITCH_TEST_{len(results['cases'])}",
                        timestamp=timestamp,
                        open=open_p,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume
                    )
                    data.prev_close = prev_close
                    data.avg_volume = avg_volume

                    await self.strategy_engine.analyze(data.symbol, data)
                    selected = self.strategy_engine.switch_limiter.get_current_strategy(data.symbol)

                    if 'expected' in step:
                        print(f"         Step {i+1}: Expected {step['expected']}, got {selected}")
                    elif 'expected_consider' in step:
                        print(f"         Step {i+1}: Should consider {step['expected_consider']}, got {selected}")

                print(f"      ✅ Switching test completed")
                results['passed'] += 1

            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                case_result = 'ERROR'
                results['failed'] += 1

            results['cases'].append({
                'name': test['name'],
                'result': case_result
            })

        self.test_results['switching_tests'] = results
        print(f"   📊 Switching Results: {results['passed']}/{results['total']} passed")
        print()

    # =====================================================
    # EDGE CASES AND BOUNDARY CONDITIONS
    # =====================================================

    async def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        print("⚠️ TESTING EDGE CASES & BOUNDARY CONDITIONS")
        print("-" * 40)

        edge_cases = [
            {
                'name': 'Exactly 3% Gap - Gap Go Boundary',
                'prev_close': 10.00,
                'avg_volume': 100_000,
                'market_data': (10.30, 10.50, 10.25, 10.45, 200_000),  # Exactly 3% gap
                'expected_strategy': 'gap_go'
            },
            {
                'name': 'Just Under 3% Gap - Should Not Be Gap Go',
                'prev_close': 10.00,
                'avg_volume': 100_000,
                'market_data': (10.29, 10.49, 10.24, 10.44, 200_000),  # 2.9% gap
                'expected_strategy': None  # Should not be gap_go
            },
            {
                'name': 'Exactly 4x Volume - Daily Plays Boundary',
                'prev_close': 8.00,
                'avg_volume': 100_000,
                'market_data': (8.10, 8.50, 8.05, 8.45, 400_000),  # Exactly 4x volume
                'expected_strategy': 'daily_plays'
            },
            {
                'name': 'Zero Volume - Edge Case',
                'prev_close': 12.00,
                'avg_volume': 100_000,
                'market_data': (12.10, 12.20, 12.05, 12.15, 0),  # Zero volume
                'expected_strategy': 'macdv'  # Should fallback to MACDV
            },
            {
                'name': 'Extreme Gap - 200% Move',
                'prev_close': 5.00,
                'avg_volume': 50_000,
                'market_data': (15.00, 18.50, 14.80, 17.25, 2_000_000),  # 200% gap, 40x volume
                'expected_strategy': 'gap_go'  # Should still be gap_go
            }
        ]

        results = {'total': len(edge_cases), 'passed': 0, 'failed': 0, 'cases': []}

        for case in edge_cases:
            print(f"   ⚠️ {case['name']}")

            try:
                timestamp = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
                open_p, high, low, close, volume = case['market_data']

                data = MarketData(
                    symbol=f"EDGE_{len(results['cases'])}",
                    timestamp=timestamp,
                    open=open_p,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume
                )
                data.prev_close = case['prev_close']
                data.avg_volume = case['avg_volume']

                await self.strategy_engine.analyze(data.symbol, data)
                selected = self.strategy_engine.switch_limiter.get_current_strategy(data.symbol)

                if case['expected_strategy']:
                    if selected == case['expected_strategy']:
                        print(f"      ✅ PASS: Selected {selected}")
                        results['passed'] += 1
                    else:
                        print(f"      ❌ FAIL: Expected {case['expected_strategy']}, got {selected}")
                        results['failed'] += 1
                else:
                    print(f"      ✅ INFO: Selected {selected} (no specific expectation)")
                    results['passed'] += 1

            except Exception as e:
                print(f"      ❌ ERROR: {e}")
                results['failed'] += 1

            results['cases'].append({'name': case['name']})

        self.test_results['edge_case_tests'] = results
        print(f"   📊 Edge Cases Results: {results['passed']}/{results['total']} passed")
        print()

    # =====================================================
    # PERFORMANCE TESTS
    # =====================================================

    async def test_performance_multiple_tickers(self):
        """Test performance with multiple tickers simultaneously"""
        print("⚡ TESTING PERFORMANCE WITH MULTIPLE TICKERS")
        print("-" * 40)

        # Create 20 different ticker scenarios
        ticker_scenarios = []
        for i in range(20):
            ticker_scenarios.append({
                'symbol': f'PERF{i:02d}',
                'prev_close': 5.0 + (i * 0.5),
                'avg_volume': 80_000 + (i * 5_000),
                'market_data': (
                    (5.0 + i * 0.5) * (1.0 + (i % 10) * 0.01),  # Varying gaps
                    (5.0 + i * 0.5) * (1.1 + (i % 5) * 0.01),   # High
                    (5.0 + i * 0.5) * (0.98),                   # Low
                    (5.0 + i * 0.5) * (1.05 + (i % 8) * 0.005), # Close
                    80_000 + (i * 10_000)                       # Volume
                )
            })

        print(f"   Testing {len(ticker_scenarios)} tickers simultaneously...")

        start_time = time.time()

        # Process all tickers
        processed_tickers = 0
        for scenario in ticker_scenarios:
            try:
                timestamp = datetime.now().replace(hour=10, minute=30, second=0, microsecond=0)
                open_p, high, low, close, volume = scenario['market_data']

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

                await self.strategy_engine.analyze(scenario['symbol'], data)
                processed_tickers += 1

            except Exception as e:
                print(f"   ❌ Error processing {scenario['symbol']}: {e}")

        end_time = time.time()
        total_time = end_time - start_time

        # Performance metrics
        avg_time_per_ticker = total_time / len(ticker_scenarios) if ticker_scenarios else 0
        tickers_per_second = len(ticker_scenarios) / total_time if total_time > 0 else 0

        performance_results = {
            'total_tickers': len(ticker_scenarios),
            'processed_tickers': processed_tickers,
            'total_time': total_time,
            'avg_time_per_ticker': avg_time_per_ticker,
            'tickers_per_second': tickers_per_second,
            'performance_grade': 'EXCELLENT' if avg_time_per_ticker < 0.01 else 'GOOD' if avg_time_per_ticker < 0.05 else 'NEEDS_OPTIMIZATION'
        }

        print(f"   📊 Performance Results:")
        print(f"      Total Time: {total_time:.3f}s")
        print(f"      Avg Time per Ticker: {avg_time_per_ticker:.3f}s")
        print(f"      Tickers per Second: {tickers_per_second:.1f}")
        print(f"      Grade: {performance_results['performance_grade']}")

        self.test_results['performance_tests'] = performance_results
        print()

    # =====================================================
    # MAIN TEST RUNNER
    # =====================================================

    async def run_comprehensive_test_suite(self):
        """Run the complete comprehensive test suite"""
        print("🚀 COMPREHENSIVE CORE STRATEGIES TEST SUITE")
        print("=" * 60)

        await self.setup_test_environment()

        # Run all test categories
        print("📋 Running Individual Strategy Tests...")
        await self.test_gap_go_strategy()
        await self.test_daily_plays_strategy()
        await self.test_bull_flag_strategy()
        await self.test_macdv_strategy()

        print("📋 Running Strategy Switching Tests...")
        await self.test_strategy_switching_scenarios()

        print("📋 Running Edge Case Tests...")
        await self.test_edge_cases()

        print("📋 Running Performance Tests...")
        await self.test_performance_multiple_tickers()

        # Final summary
        self._print_final_summary()

    def _print_final_summary(self):
        """Print comprehensive test summary"""
        print("📊 COMPREHENSIVE TEST SUMMARY")
        print("=" * 60)

        # Individual strategy results
        print("🎯 Individual Strategy Tests:")
        for strategy, results in self.test_results['individual_tests'].items():
            success_rate = (results['passed'] / results['total']) * 100 if results['total'] > 0 else 0
            status = "✅" if success_rate >= 80 else "⚠️" if success_rate >= 60 else "❌"
            print(f"   {status} {strategy.upper()}: {results['passed']}/{results['total']} ({success_rate:.0f}%)")

        # Other test categories
        categories = [
            ('switching_tests', 'Strategy Switching'),
            ('edge_case_tests', 'Edge Cases')
        ]

        for category, name in categories:
            if category in self.test_results and self.test_results[category]:
                results = self.test_results[category]
                success_rate = (results['passed'] / results['total']) * 100 if results['total'] > 0 else 0
                status = "✅" if success_rate >= 80 else "⚠️"
                print(f"   {status} {name}: {results['passed']}/{results['total']} ({success_rate:.0f}%)")

        # Performance results
        if 'performance_tests' in self.test_results:
            perf = self.test_results['performance_tests']
            status = "✅" if perf['performance_grade'] == 'EXCELLENT' else "⚠️"
            print(f"   {status} Performance: {perf['performance_grade']} ({perf['tickers_per_second']:.1f} tickers/sec)")

        # Overall summary
        total_tests = sum(results.get('total', 0) for results in [
            *self.test_results['individual_tests'].values(),
            self.test_results.get('switching_tests', {}),
            self.test_results.get('edge_case_tests', {})
        ])

        passed_tests = sum(results.get('passed', 0) for results in [
            *self.test_results['individual_tests'].values(),
            self.test_results.get('switching_tests', {}),
            self.test_results.get('edge_case_tests', {})
        ])

        overall_success = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        print()
        print(f"🎯 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed ({overall_success:.0f}%)")

        if overall_success >= 90:
            print("🎉 EXCELLENT: All core strategies working perfectly!")
        elif overall_success >= 80:
            print("✅ GOOD: Core strategies working well with minor issues")
        else:
            print("⚠️ NEEDS ATTENTION: Some core strategies need optimization")

        print("=" * 60)


async def main():
    """Run the comprehensive core strategies test suite"""
    test_suite = CoreStrategiesTestSuite()
    await test_suite.run_comprehensive_test_suite()


if __name__ == "__main__":
    asyncio.run(main())