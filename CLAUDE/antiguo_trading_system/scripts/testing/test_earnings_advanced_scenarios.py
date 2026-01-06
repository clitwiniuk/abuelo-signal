#!/usr/bin/env python3
"""
Advanced Earnings Intelligence Test Suite
Comprehensive testing with real-world complex scenarios
"""

import asyncio
import logging
import time
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from core.hybrid_volume_engine import HybridVolumeEngine
from core.earnings_enhanced_engine import EarningsEnhancedEngine, EnhancedVolumeDecision
from core.ml_volume_engine import MarketContext
from core.earnings_context_provider import EarningsContext, earnings_context_provider

@dataclass
class TestResult:
    """Result of a single test scenario"""
    scenario_name: str
    symbol: str
    original_requirement: float
    enhanced_requirement: float
    earnings_multiplier: float
    is_conservative_correct: bool
    execution_time_ms: float
    api_call_success: bool
    reasoning: str

@dataclass 
class PerformanceMetrics:
    """Performance metrics for the test suite"""
    total_scenarios: int
    avg_execution_time_ms: float
    api_success_rate: float
    conservative_accuracy: float
    total_test_time_s: float

class AdvancedEarningsTestSuite:
    """Advanced test suite for earnings intelligence"""
    
    def __init__(self):
        self.original_engine = HybridVolumeEngine()
        self.enhanced_engine = EarningsEnhancedEngine()
        self.test_results: List[TestResult] = []
        self.logger = logging.getLogger(__name__)
    
    async def run_comprehensive_test(self):
        """Run comprehensive advanced test suite"""
        
        print("🚀 ADVANCED EARNINGS INTELLIGENCE TEST SUITE")
        print("=" * 80)
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Testing real-world complex scenarios with performance metrics")
        print("=" * 80)
        print()
        
        start_time = time.time()
        
        # Test categories
        await self._test_real_world_earnings_scenarios()
        await self._test_edge_cases_and_anomalies() 
        await self._test_performance_and_concurrent_requests()
        await self._test_api_integration_with_real_data()
        await self._test_market_condition_combinations()
        
        total_time = time.time() - start_time
        
        # Generate comprehensive report
        await self._generate_performance_report(total_time)
    
    async def _test_real_world_earnings_scenarios(self):
        """Test realistic small caps earnings scenarios"""
        
        print("📊 TEST 1: REAL-WORLD SMALL CAPS EARNINGS SCENARIOS")
        print("=" * 60)
        
        scenarios = [
            {
                "name": "Biotech Clinical Trial Failure",
                "symbol": "BTRX",
                "context": MarketContext(
                    time_of_day=0.25,  # Pre-market
                    day_of_week=2,
                    market_cap=45_000_000,
                    avg_volume=850_000,
                    float_shares=18_000_000,
                    sector="BIOTECH", 
                    recent_performance=-0.45,
                    market_stress=0.65,
                    volume_trend=35.8,  # Panic selling
                    price_level=1.25
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="BTRX",
                    phase="POST_EARNINGS_MISS",
                    days_since_earnings=1,
                    is_earnings_week=True,
                    actual_eps=-0.85,
                    estimated_eps=-0.15,
                    surprise_percent=-466.7,
                    confidence=0.95
                ),
                "expected_conservative": True
            },
            {
                "name": "Penny Stock Fake Earnings Beat",
                "symbol": "PUMP",
                "context": MarketContext(
                    time_of_day=0.6,
                    day_of_week=3,
                    market_cap=15_000_000,
                    avg_volume=2_500_000,
                    float_shares=75_000_000,
                    sector="TECH",
                    recent_performance=1.25,  # Huge gain
                    market_stress=0.35,
                    volume_trend=125.0,  # Extreme volume
                    price_level=0.65
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="PUMP",
                    phase="POST_EARNINGS_SURPRISE",
                    days_since_earnings=1,
                    is_earnings_week=True,
                    actual_eps=0.001,
                    estimated_eps=-0.05,
                    surprise_percent=102.0,
                    confidence=0.7
                ),
                "expected_conservative": True
            },
            {
                "name": "Legitimate Small Cap Growth Beat",
                "symbol": "GROW",
                "context": MarketContext(
                    time_of_day=0.5,
                    day_of_week=4,
                    market_cap=280_000_000,
                    avg_volume=1_200_000,
                    float_shares=45_000_000,
                    sector="TECH",
                    recent_performance=0.18,
                    market_stress=0.25,
                    volume_trend=8.5,  # Healthy volume increase
                    price_level=7.85
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="GROW",
                    phase="POST_EARNINGS_BEAT",
                    days_since_earnings=1,
                    is_earnings_week=True,
                    actual_eps=0.22,
                    estimated_eps=0.15,
                    surprise_percent=46.7,
                    confidence=0.9
                ),
                "expected_conservative": False
            },
            {
                "name": "Pre-Earnings FDA Binary Event",
                "symbol": "FDAW",
                "context": MarketContext(
                    time_of_day=0.7,
                    day_of_week=5,
                    market_cap=120_000_000,
                    avg_volume=650_000,
                    float_shares=28_000_000,
                    sector="BIOTECH",
                    recent_performance=0.08,
                    market_stress=0.45,
                    volume_trend=3.2,  # Quiet before storm
                    price_level=4.15
                ),
                "earnings": EarningsContext(
                    symbol="FDAW",
                    phase="PRE_EARNINGS",
                    days_to_earnings=1,
                    days_since_earnings=None,
                    is_earnings_week=True,
                    actual_eps=None,
                    estimated_eps=-0.25,
                    surprise_percent=None,
                    confidence=0.8
                ),
                "expected_conservative": True
            }
        ]
        
        for scenario in scenarios:
            result = await self._test_single_scenario(scenario)
            self.test_results.append(result)
            self._print_scenario_result(result, scenario["expected_conservative"])
            print()
    
    async def _test_edge_cases_and_anomalies(self):
        """Test edge cases and market anomalies"""
        
        print("⚠️ TEST 2: EDGE CASES & MARKET ANOMALIES")
        print("=" * 60)
        
        edge_cases = [
            {
                "name": "Earnings Data Conflict - API vs Reality",
                "symbol": "CONFLICT",
                "context": MarketContext(
                    time_of_day=0.4,
                    day_of_week=1,
                    market_cap=95_000_000,
                    avg_volume=750_000,
                    float_shares=35_000_000,
                    sector="TECH",
                    recent_performance=0.25,  # Price up but...
                    market_stress=0.3,
                    volume_trend=22.0,  # High volume
                    price_level=3.45
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="CONFLICT",
                    phase="POST_EARNINGS_BEAT",  # API says beat but market acting like miss
                    days_since_earnings=1,
                    is_earnings_week=True,
                    actual_eps=0.08,
                    estimated_eps=0.05,
                    surprise_percent=60.0,
                    confidence=0.6  # Low confidence
                ),
                "expected_conservative": True  # Should be conservative due to low confidence
            },
            {
                "name": "Stale Earnings Data - 6 Months Old",
                "symbol": "STALE",
                "context": MarketContext(
                    time_of_day=0.5,
                    day_of_week=3,
                    market_cap=150_000_000,
                    avg_volume=800_000,
                    float_shares=42_000_000,
                    sector="BIOTECH",
                    recent_performance=0.15,
                    market_stress=0.28,
                    volume_trend=12.5,
                    price_level=5.25
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="STALE", 
                    phase="NORMAL",  # Old earnings, not current
                    days_since_earnings=180,  # 6 months old
                    is_earnings_week=False,
                    actual_eps=0.12,
                    estimated_eps=0.10,
                    surprise_percent=20.0,
                    confidence=0.3  # Very low confidence for old data
                ),
                "expected_conservative": False  # Should default to normal behavior
            },
            {
                "name": "Earnings Restatement Scandal",
                "symbol": "FRAUD",
                "context": MarketContext(
                    time_of_day=0.6,
                    day_of_week=2,
                    market_cap=75_000_000,
                    avg_volume=1_500_000,
                    float_shares=50_000_000,
                    sector="TECH",
                    recent_performance=-0.35,  # Dropping hard
                    market_stress=0.8,  # High stress
                    volume_trend=45.0,  # Massive selling
                    price_level=1.85
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol="FRAUD",
                    phase="POST_EARNINGS_MISS",  # Previously reported beat, now restated as miss
                    days_since_earnings=3,
                    is_earnings_week=True,
                    actual_eps=-0.25,  # Restated 
                    estimated_eps=0.05,
                    surprise_percent=-600.0,  # Massive restatement
                    confidence=0.9  # High confidence in restatement
                ),
                "expected_conservative": True
            }
        ]
        
        for case in edge_cases:
            result = await self._test_single_scenario(case)
            self.test_results.append(result)
            self._print_scenario_result(result, case["expected_conservative"])
            print()
    
    async def _test_performance_and_concurrent_requests(self):
        """Test performance under load"""
        
        print("⚡ TEST 3: PERFORMANCE & CONCURRENT REQUEST HANDLING")
        print("=" * 60)
        
        # Create multiple concurrent scenarios
        concurrent_scenarios = []
        symbols = ["PERF1", "PERF2", "PERF3", "PERF4", "PERF5"]
        
        for i, symbol in enumerate(symbols):
            scenario = {
                "name": f"Concurrent Performance Test {i+1}",
                "symbol": symbol,
                "context": MarketContext(
                    time_of_day=0.5,
                    day_of_week=2,
                    market_cap=100_000_000 + i * 50_000_000,
                    avg_volume=500_000 + i * 200_000,
                    float_shares=30_000_000 + i * 10_000_000,
                    sector="TECH",
                    recent_performance=0.1 + i * 0.05,
                    market_stress=0.3,
                    volume_trend=10.0 + i * 5,
                    price_level=5.0 + i
                ),
                "earnings": EarningsContext(
                    days_to_earnings=None,
                    
                    symbol=symbol,
                    phase="POST_EARNINGS_BEAT",
                    days_since_earnings=1,
                    is_earnings_week=True,
                    actual_eps=0.10 + i * 0.05,
                    estimated_eps=0.08 + i * 0.02,
                    surprise_percent=25.0,
                    confidence=0.9
                ),
                "expected_conservative": False
            }
            concurrent_scenarios.append(scenario)
        
        # Test concurrent execution
        print(f"Testing {len(concurrent_scenarios)} concurrent requests...")
        concurrent_start = time.time()
        
        # Execute all scenarios concurrently
        tasks = [self._test_single_scenario(scenario) for scenario in concurrent_scenarios]
        concurrent_results = await asyncio.gather(*tasks)
        
        concurrent_time = (time.time() - concurrent_start) * 1000
        
        print(f"✅ Concurrent Execution Time: {concurrent_time:.2f}ms")
        print(f"✅ Average Time per Request: {concurrent_time/len(concurrent_scenarios):.2f}ms")
        
        # Add results
        for result in concurrent_results:
            self.test_results.append(result)
            
        # Test sequential vs concurrent performance
        sequential_start = time.time()
        for scenario in concurrent_scenarios[:2]:  # Test 2 sequentially
            await self._test_single_scenario(scenario)
        sequential_time = (time.time() - sequential_start) * 1000
        
        speedup = (sequential_time * len(concurrent_scenarios) / 2) / concurrent_time
        print(f"✅ Performance Speedup: {speedup:.2f}x faster than sequential")
        print()
    
    async def _test_api_integration_with_real_data(self):
        """Test with real Alpha Vantage API (if available)"""
        
        print("🌐 TEST 4: REAL API INTEGRATION TEST")
        print("=" * 60)
        
        # Test with a few real symbols (popular small caps)
        real_symbols = ["SIRI", "PLUG", "CLOV"]  # Real small cap symbols
        
        for symbol in real_symbols:
            print(f"Testing real API data for {symbol}...")
            
            start_time = time.time()
            try:
                # This will make real API call
                real_earnings_context = await earnings_context_provider.get_earnings_context(symbol)
                api_success = True
                execution_time = (time.time() - start_time) * 1000
                
                # Create market context for testing
                test_context = MarketContext(
                    time_of_day=0.5,
                    day_of_week=2,
                    market_cap=500_000_000,  # Estimate
                    avg_volume=10_000_000,
                    float_shares=200_000_000,
                    sector="TECH",
                    recent_performance=0.05,
                    market_stress=0.3,
                    volume_trend=8.5,
                    price_level=5.0
                )
                
                # Test enhanced engine with real data
                enhanced_decision = await self._create_enhanced_decision(
                    test_context, real_earnings_context, symbol
                )
                
                print(f"   ✅ API Response Time: {execution_time:.2f}ms")
                print(f"   📊 Earnings Phase: {real_earnings_context.phase}")
                print(f"   🎯 Confidence: {real_earnings_context.confidence:.2f}")
                if real_earnings_context.is_earnings_week:
                    print(f"   📅 Earnings Week: Yes")
                print(f"   🔧 Enhanced Requirement: {enhanced_decision.final_requirement:.2f}x")
                print(f"   💭 Reasoning: {enhanced_decision.earnings_reasoning}")
                
            except Exception as e:
                api_success = False
                execution_time = (time.time() - start_time) * 1000
                print(f"   ⚠️ API Error: {str(e)[:50]}...")
                print(f"   ⏱️ Error Time: {execution_time:.2f}ms")
            
            print()
            
            # Rate limiting delay
            await asyncio.sleep(1)  # Respect API rate limits
    
    async def _test_market_condition_combinations(self):
        """Test combinations of market conditions with earnings"""
        
        print("🔄 TEST 5: MARKET CONDITION COMBINATIONS")
        print("=" * 60)
        
        combinations = [
            {
                "name": "Earnings Beat + Market Crash",
                "market_stress": 0.8,  # High stress
                "volume_trend": 35.0,  # High volume
                "recent_performance": -0.3,  # Down despite beat
                "earnings_phase": "POST_EARNINGS_BEAT",
                "expected": "Should be more conservative despite beat"
            },
            {
                "name": "Earnings Miss + Bull Market",
                "market_stress": 0.15,  # Low stress
                "volume_trend": 12.0,  # Moderate volume
                "recent_performance": 0.25,  # Up despite miss
                "earnings_phase": "POST_EARNINGS_MISS",
                "expected": "Should still be conservative despite bull market"
            },
            {
                "name": "Pre-Earnings + Volatile Market",
                "market_stress": 0.65,  # High volatility
                "volume_trend": 8.0,  # Normal volume
                "recent_performance": 0.0,  # Flat
                "earnings_phase": "PRE_EARNINGS", 
                "expected": "Should be very conservative"
            }
        ]
        
        for combo in combinations:
            print(f"📊 {combo['name']}")
            
            context = MarketContext(
                time_of_day=0.5,
                day_of_week=3,
                market_cap=150_000_000,
                avg_volume=800_000,
                float_shares=40_000_000,
                sector="TECH",
                recent_performance=combo["recent_performance"],
                market_stress=combo["market_stress"],
                volume_trend=combo["volume_trend"],
                price_level=6.25
            )
            
            earnings_context = EarningsContext(
                    days_to_earnings=None,
                
                    symbol="COMBO",
                phase=combo["earnings_phase"],
                days_since_earnings=1 if "POST" in combo["earnings_phase"] else None,
                days_to_earnings=2 if "PRE" in combo["earnings_phase"] else None,
                is_earnings_week=True,
                actual_eps=0.10 if "BEAT" in combo["earnings_phase"] else -0.05,
                estimated_eps=0.08,
                surprise_percent=25.0 if "BEAT" in combo["earnings_phase"] else -162.5,
                confidence=0.9
            )
            
            # Test the combination
            enhanced_decision = await self._create_enhanced_decision(
                context, earnings_context, "COMBO"
            )
            
            print(f"   Market Stress: {combo['market_stress']:.2f}")
            print(f"   Volume Trend: {combo['volume_trend']:.1f}x")
            print(f"   Recent Perf: {combo['recent_performance']:+.1%}")
            print(f"   Final Requirement: {enhanced_decision.final_requirement:.2f}x")
            print(f"   Expected: {combo['expected']}")
            print()
    
    async def _test_single_scenario(self, scenario: Dict) -> TestResult:
        """Test a single scenario and return results"""
        
        start_time = time.time()
        
        try:
            # Get original decision
            original_decision = self.original_engine.predict_volume_requirement('gap_go', scenario['context'])
            
            # Get enhanced decision
            enhanced_decision = await self._create_enhanced_decision(
                scenario['context'], scenario['earnings'], scenario['symbol']
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            # Determine if conservatism is correct
            is_more_conservative = enhanced_decision.final_requirement > original_decision.requirement * 1.1
            is_conservative_correct = (
                (scenario.get('expected_conservative', False) and is_more_conservative) or
                (not scenario.get('expected_conservative', False) and not is_more_conservative)
            )
            
            return TestResult(
                scenario_name=scenario['name'],
                
                    symbol=scenario['symbol'],
                original_requirement=original_decision.requirement,
                enhanced_requirement=enhanced_decision.final_requirement,
                earnings_multiplier=enhanced_decision.earnings_adjustment,
                is_conservative_correct=is_conservative_correct,
                execution_time_ms=execution_time,
                api_call_success=True,
                reasoning=enhanced_decision.earnings_reasoning
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            return TestResult(
                scenario_name=scenario['name'],
                
                    symbol=scenario['symbol'],
                original_requirement=0.0,
                enhanced_requirement=0.0,
                earnings_multiplier=1.0,
                is_conservative_correct=False,
                execution_time_ms=execution_time,
                api_call_success=False,
                reasoning=f"Error: {str(e)[:50]}"
            )
    
    async def _create_enhanced_decision(self, context: MarketContext, earnings_context: EarningsContext, symbol: str):
        """Create enhanced decision manually to avoid API calls in tests"""
        
        original_decision = self.original_engine.predict_volume_requirement('gap_go', context)
        
        # Use enhanced engine logic
        earnings_multiplier = self.enhanced_engine._get_earnings_multiplier(earnings_context, context)
        final_requirement = original_decision.requirement * earnings_multiplier
        earnings_reasoning = self.enhanced_engine._generate_earnings_reasoning(earnings_context, earnings_multiplier)
        
        from core.earnings_enhanced_engine import EnhancedVolumeDecision
        return EnhancedVolumeDecision(
            original_decision=original_decision,
            earnings_context=earnings_context,
            final_requirement=final_requirement,
            earnings_adjustment=earnings_multiplier,
            earnings_reasoning=earnings_reasoning,
            is_earnings_enhanced=True
        )
    
    def _print_scenario_result(self, result: TestResult, expected_conservative: bool):
        """Print formatted result for a scenario"""
        
        print(f"📊 {result.scenario_name} ({result.symbol})")
        print(f"   Original: {result.original_requirement:.2f}x → Enhanced: {result.enhanced_requirement:.2f}x")
        
        if result.enhanced_requirement > result.original_requirement * 1.1:
            change = f"🔴 +{((result.enhanced_requirement / result.original_requirement - 1) * 100):.1f}% MORE CONSERVATIVE"
        elif result.enhanced_requirement < result.original_requirement * 0.9:
            change = f"🟢 {((1 - result.enhanced_requirement / result.original_requirement) * 100):.1f}% MORE PERMISSIVE"
        else:
            change = "🟡 SIMILAR"
        
        print(f"   Change: {change}")
        print(f"   Reasoning: {result.reasoning}")
        print(f"   Execution: {result.execution_time_ms:.2f}ms")
        
        if result.is_conservative_correct:
            print("   ✅ BEHAVIOR: Correct conservatism level")
        else:
            print("   ❌ BEHAVIOR: Unexpected conservatism level")
    
    async def _generate_performance_report(self, total_time: float):
        """Generate comprehensive performance report"""
        
        print("=" * 80)
        print("📊 COMPREHENSIVE PERFORMANCE REPORT")
        print("=" * 80)
        
        if not self.test_results:
            print("No test results to analyze")
            return
        
        # Calculate metrics
        total_scenarios = len(self.test_results)
        successful_tests = [r for r in self.test_results if r.api_call_success]
        avg_execution_time = statistics.mean([r.execution_time_ms for r in self.test_results])
        api_success_rate = len(successful_tests) / total_scenarios * 100
        conservative_accuracy = len([r for r in self.test_results if r.is_conservative_correct]) / total_scenarios * 100
        
        # Performance metrics
        print(f"⚡ PERFORMANCE METRICS:")
        print(f"   Total Test Time: {total_time:.2f}s")
        print(f"   Total Scenarios: {total_scenarios}")
        print(f"   Average Execution Time: {avg_execution_time:.2f}ms")
        print(f"   Fastest Execution: {min([r.execution_time_ms for r in self.test_results]):.2f}ms")
        print(f"   Slowest Execution: {max([r.execution_time_ms for r in self.test_results]):.2f}ms")
        print()
        
        # Accuracy metrics
        print(f"🎯 ACCURACY METRICS:")
        print(f"   API Success Rate: {api_success_rate:.1f}%")
        print(f"   Conservative Decision Accuracy: {conservative_accuracy:.1f}%")
        print()
        
        # Earnings adjustment analysis
        adjustments = [r.earnings_multiplier for r in successful_tests if r.earnings_multiplier != 1.0]
        if adjustments:
            print(f"📈 EARNINGS ADJUSTMENTS:")
            print(f"   Average Adjustment: {statistics.mean(adjustments):.2f}x")
            print(f"   Most Conservative: {max(adjustments):.2f}x")
            print(f"   Most Permissive: {min(adjustments):.2f}x")
            print()
        
        # Error analysis
        errors = [r for r in self.test_results if not r.api_call_success]
        if errors:
            print(f"❌ ERROR ANALYSIS:")
            print(f"   Failed Tests: {len(errors)}")
            for error in errors[:3]:  # Show first 3 errors
                print(f"   • {error.scenario_name}: {error.reasoning}")
            print()
        
        # Final assessment
        print("🏁 FINAL ASSESSMENT:")
        if conservative_accuracy >= 90 and api_success_rate >= 95:
            print("   🟢 EXCELLENT: System ready for production deployment")
        elif conservative_accuracy >= 80 and api_success_rate >= 90:
            print("   🟡 GOOD: Minor improvements recommended")
        else:
            print("   🔴 NEEDS WORK: Significant improvements required")
        
        print(f"   Average Response Time: {avg_execution_time:.0f}ms")
        if avg_execution_time < 100:
            print("   ⚡ FAST: Excellent response times")
        elif avg_execution_time < 500:
            print("   🟡 MODERATE: Acceptable response times")
        else:
            print("   🔴 SLOW: Response times need optimization")
        
        print()
        print("✅ ADVANCED TESTING COMPLETE!")

async def main():
    """Run advanced earnings test suite"""
    suite = AdvancedEarningsTestSuite()
    await suite.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())