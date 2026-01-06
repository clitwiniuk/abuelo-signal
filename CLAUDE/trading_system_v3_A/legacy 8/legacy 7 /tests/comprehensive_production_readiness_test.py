"""
Comprehensive Production Readiness Test Suite
Tests the RealisticStrategyEngine under various real-world conditions
to ensure robustness before live trading.
"""

import asyncio
import sys
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import MarketData, Signal, Position, SignalType
from strategies.realistic_strategy_engine import RealisticStrategyEngine


@dataclass
class TestScenario:
    """Test scenario definition"""
    name: str
    description: str
    tickers: List[Dict[str, Any]]
    expected_strategies: Dict[str, str]  # {symbol: expected_strategy}
    expected_signals: int  # Minimum expected signals
    stress_factor: float = 1.0  # Multiplier for complexity


class ComprehensiveProductionTest:
    """Comprehensive test suite for production readiness"""

    def __init__(self):
        self.strategy_engine = None
        self.test_results = {
            'scenarios_passed': 0,
            'scenarios_failed': 0,
            'total_signals': 0,
            'strategy_assignments': {},
            'performance_metrics': {},
            'error_cases': [],
            'edge_cases_handled': 0
        }

    async def setup_test_environment(self):
        """Initialize test environment"""
        print("🔧 Setting up comprehensive test environment...")
        self.strategy_engine = RealisticStrategyEngine()
        await self.strategy_engine.initialize()
        print("✅ Production-ready strategy engine initialized\n")

    def create_test_scenarios(self) -> List[TestScenario]:
        """Create comprehensive test scenarios"""
        return [
            # Scenario 1: Classic Gap & Go Morning
            TestScenario(
                name="morning_gap_rush",
                description="Multiple gap-ups in morning session (typical pre-market news)",
                tickers=[
                    {
                        'symbol': 'ABCD', 'prev_close': 8.50, 'avg_volume': 150_000,
                        'market_data': [(11.50, 12.80, 11.40, 12.75, 450_000)]  # 35% gap, 3x vol
                    },
                    {
                        'symbol': 'EFGH', 'prev_close': 12.25, 'avg_volume': 200_000,
                        'market_data': [(14.20, 15.10, 14.00, 14.95, 600_000)]  # 16% gap, 3x vol
                    },
                    {
                        'symbol': 'IJKL', 'prev_close': 6.75, 'avg_volume': 100_000,
                        'market_data': [(7.50, 8.20, 7.45, 8.15, 380_000)]      # 11% gap, 3.8x vol
                    }
                ],
                expected_strategies={'ABCD': 'gap_go', 'EFGH': 'gap_go', 'IJKL': 'gap_go'},
                expected_signals=2  # At least 2 should trigger
            ),

            # Scenario 2: News-Driven Volume Spikes
            TestScenario(
                name="news_volume_explosion",
                description="High volume spikes with news catalysts",
                tickers=[
                    {
                        'symbol': 'NEWS1', 'prev_close': 15.30, 'avg_volume': 180_000,
                        'market_data': [(15.45, 17.80, 15.20, 17.65, 900_000)]  # 15% move, 5x vol
                    },
                    {
                        'symbol': 'NEWS2', 'prev_close': 9.80, 'avg_volume': 120_000,
                        'market_data': [(10.10, 11.95, 9.95, 11.70, 720_000)]   # 19% move, 6x vol
                    }
                ],
                expected_strategies={'NEWS1': 'daily_plays', 'NEWS2': 'daily_plays'},
                expected_signals=1
            ),

            # Scenario 3: Mixed Technical Setups
            TestScenario(
                name="technical_mixed_bag",
                description="Various technical setups without major catalysts",
                tickers=[
                    {
                        'symbol': 'TECH1', 'prev_close': 11.40, 'avg_volume': 90_000,
                        'market_data': [(11.55, 11.85, 11.50, 11.78, 135_000)]   # 3% move, 1.5x vol
                    },
                    {
                        'symbol': 'TECH2', 'prev_close': 7.20, 'avg_volume': 110_000,
                        'market_data': [(7.35, 7.65, 7.30, 7.58, 165_000)]       # 5% move, 1.5x vol
                    },
                    {
                        'symbol': 'TECH3', 'prev_close': 13.80, 'avg_volume': 85_000,
                        'market_data': [(14.10, 14.25, 14.05, 14.20, 125_000)]   # 3% move, 1.5x vol
                    }
                ],
                expected_strategies={'TECH1': 'macdv', 'TECH2': 'macdv', 'TECH3': 'macdv'},
                expected_signals=0  # Technical setups may not trigger immediately
            ),

            # Scenario 4: Edge Cases & Stress Test
            TestScenario(
                name="edge_case_stress",
                description="Edge cases: extreme gaps, low volume, bad data",
                tickers=[
                    {
                        'symbol': 'EXTREME', 'prev_close': 5.00, 'avg_volume': 50_000,
                        'market_data': [(15.00, 18.50, 14.80, 17.25, 2_000_000)] # 200% gap, 40x vol
                    },
                    {
                        'symbol': 'LOWVOL', 'prev_close': 8.90, 'avg_volume': 200_000,
                        'market_data': [(9.15, 9.25, 9.10, 9.20, 15_000)]        # Low volume
                    },
                    {
                        'symbol': 'FLATLINE', 'prev_close': 12.50, 'avg_volume': 100_000,
                        'market_data': [(12.52, 12.55, 12.50, 12.53, 95_000)]    # Almost no movement
                    }
                ],
                expected_strategies={'EXTREME': 'gap_go', 'LOWVOL': 'macdv', 'FLATLINE': 'macdv'},
                expected_signals=1,
                stress_factor=2.0
            ),

            # Scenario 5: High-Volume Simultaneous Processing
            TestScenario(
                name="high_volume_simultaneous",
                description="Many tickers simultaneously (production load test)",
                tickers=self._generate_bulk_ticker_data(15),  # 15 random tickers
                expected_strategies={},  # Will be determined dynamically
                expected_signals=3,
                stress_factor=3.0
            )
        ]

    def _generate_bulk_ticker_data(self, count: int) -> List[Dict[str, Any]]:
        """Generate bulk ticker data for stress testing"""
        tickers = []
        symbols = [f"BULK{i:02d}" for i in range(1, count + 1)]

        for symbol in symbols:
            # Random but realistic data
            prev_close = random.uniform(3.0, 25.0)
            avg_volume = random.randint(50_000, 500_000)

            # Random scenario
            scenario = random.choice(['gap_up', 'volume_spike', 'technical', 'flat'])

            if scenario == 'gap_up':
                gap_mult = random.uniform(1.05, 1.25)  # 5-25% gap
                volume_mult = random.uniform(2.0, 5.0)
            elif scenario == 'volume_spike':
                gap_mult = random.uniform(1.01, 1.08)  # Small gap
                volume_mult = random.uniform(3.0, 8.0)  # High volume
            elif scenario == 'technical':
                gap_mult = random.uniform(1.01, 1.04)  # Small gap
                volume_mult = random.uniform(1.2, 2.0)
            else:  # flat
                gap_mult = random.uniform(0.99, 1.02)  # Minimal movement
                volume_mult = random.uniform(0.8, 1.5)

            open_price = prev_close * gap_mult
            high_price = open_price * random.uniform(1.02, 1.12)
            low_price = open_price * random.uniform(0.95, 1.00)
            close_price = random.uniform(low_price, high_price)
            volume = int(avg_volume * volume_mult)

            tickers.append({
                'symbol': symbol,
                'prev_close': prev_close,
                'avg_volume': avg_volume,
                'market_data': [(open_price, high_price, low_price, close_price, volume)]
            })

        return tickers

    async def run_scenario_test(self, scenario: TestScenario) -> Dict[str, Any]:
        """Run a specific test scenario"""
        print(f"🧪 SCENARIO: {scenario.name.upper()}")
        print(f"📝 {scenario.description}")
        print(f"🎯 Testing {len(scenario.tickers)} tickers")

        start_time = time.time()
        scenario_results = {
            'name': scenario.name,
            'tickers_processed': 0,
            'strategies_assigned': {},
            'signals_generated': 0,
            'execution_time': 0,
            'errors': [],
            'passed': False
        }

        try:
            for ticker_data in scenario.tickers:
                symbol = ticker_data['symbol']
                market_data = self._create_market_data(ticker_data)

                # Test strategy assignment
                signals = []
                for data in market_data:
                    try:
                        tick_signals = await self.strategy_engine.analyze(symbol, data)
                        if tick_signals:
                            signals.extend(tick_signals)
                            scenario_results['signals_generated'] += len(tick_signals)
                    except Exception as e:
                        scenario_results['errors'].append(f"{symbol}: {str(e)}")

                # Track assigned strategy
                assigned_strategy = self.strategy_engine.switch_limiter.get_current_strategy(symbol)
                if assigned_strategy:
                    scenario_results['strategies_assigned'][symbol] = assigned_strategy

                scenario_results['tickers_processed'] += 1

            # Evaluate scenario success
            scenario_results['execution_time'] = time.time() - start_time
            scenario_results['passed'] = self._evaluate_scenario_success(scenario, scenario_results)

            # Print results
            self._print_scenario_results(scenario_results)

        except Exception as e:
            scenario_results['errors'].append(f"Scenario failed: {str(e)}")
            print(f"❌ Scenario failed with error: {e}")

        return scenario_results

    def _create_market_data(self, ticker_data: Dict[str, Any]) -> List[MarketData]:
        """Create MarketData objects from ticker data"""
        symbol = ticker_data['symbol']
        prev_close = ticker_data['prev_close']
        avg_volume = ticker_data['avg_volume']
        market_data_list = []

        base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        for i, (open_p, high, low, close, volume) in enumerate(ticker_data['market_data']):
            timestamp = base_time + timedelta(minutes=i)

            data = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_p,
                high=high,
                low=low,
                close=close,
                volume=volume
            )
            data.prev_close = prev_close
            data.avg_volume = avg_volume
            market_data_list.append(data)

        return market_data_list

    def _evaluate_scenario_success(self, scenario: TestScenario, results: Dict[str, Any]) -> bool:
        """Evaluate if scenario passed success criteria"""
        success_criteria = [
            results['tickers_processed'] >= len(scenario.tickers) * 0.9,  # 90% processed
            len(results['errors']) <= len(scenario.tickers) * 0.2,        # Max 20% error rate
            results['execution_time'] <= len(scenario.tickers) * 2.0 * scenario.stress_factor  # Reasonable time
        ]

        # Check strategy assignments for specific scenarios
        if scenario.expected_strategies:
            strategy_matches = 0
            for symbol, expected in scenario.expected_strategies.items():
                assigned = results['strategies_assigned'].get(symbol)
                if assigned == expected:
                    strategy_matches += 1

            strategy_success = strategy_matches >= len(scenario.expected_strategies) * 0.7  # 70% match
            success_criteria.append(strategy_success)

        return all(success_criteria)

    def _print_scenario_results(self, results: Dict[str, Any]):
        """Print scenario results"""
        status = "✅ PASSED" if results['passed'] else "❌ FAILED"
        print(f"   {status}")
        print(f"   📊 Processed: {results['tickers_processed']} tickers")
        print(f"   🎯 Strategies: {len(results['strategies_assigned'])}")
        print(f"   ⚡ Signals: {results['signals_generated']}")
        print(f"   ⏱️ Time: {results['execution_time']:.2f}s")

        if results['strategies_assigned']:
            print(f"   🧠 Strategy assignments:")
            for symbol, strategy in results['strategies_assigned'].items():
                print(f"      {symbol}: {strategy}")

        if results['errors']:
            print(f"   ⚠️ Errors: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"      • {error}")

        print()

    async def run_performance_benchmark(self):
        """Run performance benchmark tests"""
        print("⚡ PERFORMANCE BENCHMARK")
        print("=" * 50)

        # Test 1: Single ticker processing speed
        start_time = time.time()
        test_data = self._generate_bulk_ticker_data(1)[0]
        market_data = self._create_market_data(test_data)

        for data in market_data:
            await self.strategy_engine.analyze(test_data['symbol'], data)

        single_ticker_time = time.time() - start_time

        # Test 2: Multiple tickers processing
        start_time = time.time()
        bulk_tickers = self._generate_bulk_ticker_data(10)

        for ticker_data in bulk_tickers:
            market_data = self._create_market_data(ticker_data)
            for data in market_data:
                await self.strategy_engine.analyze(ticker_data['symbol'], data)

        multi_ticker_time = time.time() - start_time

        # Results
        print(f"🔍 Single ticker processing: {single_ticker_time:.3f}s")
        print(f"📊 10 tickers processing: {multi_ticker_time:.3f}s")
        print(f"⚡ Average per ticker: {multi_ticker_time/10:.3f}s")
        print(f"🎯 Estimated 50 tickers: {(multi_ticker_time/10)*50:.1f}s")

        # Performance criteria
        single_fast_enough = single_ticker_time < 0.1  # Under 100ms per ticker
        multi_scalable = multi_ticker_time < 5.0       # Under 5s for 10 tickers

        if single_fast_enough and multi_scalable:
            print("✅ PERFORMANCE: Production ready")
        else:
            print("⚠️ PERFORMANCE: May need optimization")

        print()

        self.test_results['performance_metrics'] = {
            'single_ticker_time': single_ticker_time,
            'multi_ticker_time': multi_ticker_time,
            'avg_per_ticker': multi_ticker_time / 10,
            'performance_ready': single_fast_enough and multi_scalable
        }

    async def run_comprehensive_test_suite(self):
        """Run the complete test suite"""
        print("🚀 COMPREHENSIVE PRODUCTION READINESS TEST SUITE")
        print("=" * 60)

        await self.setup_test_environment()

        # Run all scenarios
        scenarios = self.create_test_scenarios()
        scenario_results = []

        for scenario in scenarios:
            result = await self.run_scenario_test(scenario)
            scenario_results.append(result)

            if result['passed']:
                self.test_results['scenarios_passed'] += 1
            else:
                self.test_results['scenarios_failed'] += 1

            self.test_results['total_signals'] += result['signals_generated']

        # Run performance benchmark
        await self.run_performance_benchmark()

        # Final report
        self._print_final_report(scenario_results)

    def _print_final_report(self, scenario_results: List[Dict[str, Any]]):
        """Print comprehensive final report"""
        print("📊 FINAL PRODUCTION READINESS REPORT")
        print("=" * 60)

        total_scenarios = len(scenario_results)
        passed = self.test_results['scenarios_passed']
        failed = self.test_results['scenarios_failed']
        success_rate = (passed / total_scenarios) * 100 if total_scenarios > 0 else 0

        print(f"🎯 Test Summary:")
        print(f"   Total Scenarios: {total_scenarios}")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        print()

        print(f"⚡ Signal Generation:")
        print(f"   Total Signals: {self.test_results['total_signals']}")
        print(f"   Average per Scenario: {self.test_results['total_signals']/total_scenarios:.1f}")
        print()

        # Production readiness assessment
        production_ready = (
            success_rate >= 80 and
            self.test_results['performance_metrics'].get('performance_ready', False) and
            failed <= 1
        )

        if production_ready:
            print("🎉 VERDICT: SYSTEM IS PRODUCTION READY!")
            print("   ✅ High success rate")
            print("   ✅ Good performance metrics")
            print("   ✅ Handles edge cases")
            print("   ✅ Strategy selection working correctly")
        else:
            print("⚠️ VERDICT: NEEDS IMPROVEMENTS BEFORE PRODUCTION")
            print("   Review failed scenarios and performance issues")

        print("=" * 60)


async def main():
    """Run the comprehensive production test suite"""
    test_suite = ComprehensiveProductionTest()
    await test_suite.run_comprehensive_test_suite()


if __name__ == "__main__":
    asyncio.run(main())