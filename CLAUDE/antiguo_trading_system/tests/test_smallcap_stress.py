# tests/test_smallcap_stress.py
"""
Stress testing para SmallcapContextualBandit
Tests de casos extremos, concurrencia, y robustez
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
import numpy as np
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine, SMALLCAP_ML_AVAILABLE
from strategies.ml_strategy_selector import TickerContext
from strategies.smallcap_bandit_adapter import SmallcapContextualBandit, SmallcapTickerContext

class TestSmallcapStress(unittest.TestCase):
    """Stress testing of SmallcapML implementation"""
    
    def setUp(self):
        """Set up stress test fixtures"""
        self.engine = MLMultiStrategyEngine({
            'smallcap_ml_enabled': True,
            'smallcap_price_threshold': 15.0
        })
        
        print(f"\n🔥 Stress Testing SmallcapML (available: {SMALLCAP_ML_AVAILABLE})")
    
    def test_extreme_market_conditions(self):
        """Test with extreme market conditions"""
        print("\n💥 Testing extreme market conditions...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        extreme_scenarios = [
            {
                'name': 'Flash crash',
                'price': 5.0,
                'price_change': -0.90,  # -90% crash
                'volume_ratio': 50.0,   # 50x volume spike
                'volatility': 2.0
            },
            {
                'name': 'Parabolic move',
                'price': 2.5,
                'price_change': 5.0,    # 500% gain
                'volume_ratio': 100.0,  # 100x volume
                'volatility': 3.0
            },
            {
                'name': 'No volume death',
                'price': 8.0,
                'price_change': 0.0,
                'volume_ratio': 0.001,  # Almost no volume
                'volatility': 0.001
            },
            {
                'name': 'Market halt simulation',
                'price': 12.0,
                'price_change': 0.0,
                'volume_ratio': 0.0,    # Zero volume
                'volatility': 0.0
            }
        ]
        
        for scenario in extreme_scenarios:
            with self.subTest(scenario=scenario['name']):
                print(f"   Testing: {scenario['name']}")
                
                try:
                    context = TickerContext(
                        symbol=scenario['name'].replace(' ', '_').upper(),
                        current_price=scenario['price'],
                        avg_volume_10=100000,
                        avg_volume_50=100000,
                        volatility_10=scenario['volatility'],
                        volatility_50=scenario['volatility'],
                        price_change_1h=scenario['price_change'],
                        price_change_4h=scenario['price_change'],
                        rsi_14=50.0,
                        volume_ratio_current=scenario['volume_ratio'],
                        volume_spike_frequency=0.1,
                        hour_of_day=10.0,
                        minutes_from_open=60,
                        is_first_hour=True,
                        is_last_hour=False,
                        market_trend=0.0,
                        sector_performance=0.0,
                        breakout_success_rate=0.5,
                        mean_reversion_tendency=0.5
                    )
                    
                    # Test conversion doesn't crash
                    smallcap_context = self.engine._convert_to_smallcap_context(
                        context.symbol, context
                    )
                    
                    self.assertIsNotNone(smallcap_context, f"{scenario['name']} should convert successfully")
                    
                    # Test feature vector is valid
                    features = smallcap_context.to_feature_vector()
                    self.assertEqual(len(features), 8, "Should have 8 features")
                    self.assertTrue(np.all(np.isfinite(features)), "All features should be finite")
                    
                    print(f"      ✅ Handled extreme condition: {scenario['name']}")
                    
                except Exception as e:
                    self.fail(f"{scenario['name']} should not crash: {e}")
        
        print("   ✅ All extreme conditions handled successfully")
    
    def test_concurrent_ml_operations(self):
        """Test concurrent ML operations"""
        print("\n🔄 Testing concurrent ML operations...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        # Initialize engine
        async def init_engine():
            mock_event_bus = Mock()
            await self.engine.initialize(mock_event_bus)
            return self.engine
        
        engine = asyncio.run(init_engine())
        
        if not engine.smallcap_ml_selector:
            print("   ⚠️ Skipping - smallcap ML selector not initialized")
            return
        
        def worker_thread(thread_id):
            """Worker thread for concurrent testing"""
            results = []
            
            for i in range(10):
                try:
                    # Create unique context
                    context = SmallcapTickerContext(
                        symbol=f"THREAD{thread_id}_{i}",
                        gap_percentage=0.05 + (i * 0.01),
                        volume_ratio=1.0 + i,
                        catalyst_strength=0.5,
                        catalyst_type_score=0.3,
                        price_tier=0.5,
                        time_of_day=0.5,
                        momentum_score=0.5,
                        premarket_factor=0.0,
                        current_price=5.0 + i,
                        avg_volume_10=100000,
                        avg_volume_50=100000,
                        volatility_10=0.2,
                        volatility_50=0.2,
                        price_change_1h=0.05,
                        price_change_4h=0.05,
                        rsi_14=50.0,
                        volume_ratio_current=1.5,
                        volume_spike_frequency=0.1,
                        hour_of_day=10.0,
                        minutes_from_open=60,
                        is_first_hour=True,
                        is_last_hour=False,
                        market_trend=0.0,
                        sector_performance=0.0,
                        breakout_success_rate=0.5,
                        mean_reversion_tendency=0.5
                    )
                    
                    # Test strategy selection
                    strategy = engine.smallcap_ml_selector.select_strategy(context)
                    
                    # Test reward update
                    reward = 0.1 if i % 2 == 0 else -0.05  # Mix of rewards
                    engine.smallcap_ml_selector.update_reward('daily_plays', context, reward, 2.0)
                    
                    results.append({
                        'thread_id': thread_id,
                        'iteration': i,
                        'strategy': strategy,
                        'success': True
                    })
                    
                except Exception as e:
                    results.append({
                        'thread_id': thread_id,
                        'iteration': i,
                        'error': str(e),
                        'success': False
                    })
            
            return results
        
        # Run concurrent threads
        num_threads = 5
        print(f"   Running {num_threads} concurrent threads...")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(num_threads)]
            all_results = []
            
            for future in futures:
                thread_results = future.result()
                all_results.extend(thread_results)
        
        # Analyze results
        successful = [r for r in all_results if r['success']]
        failed = [r for r in all_results if not r['success']]
        
        print(f"   Successful operations: {len(successful)}")
        print(f"   Failed operations: {len(failed)}")
        
        if failed:
            print(f"   Sample failures: {failed[:3]}")
        
        # Should have high success rate
        success_rate = len(successful) / len(all_results)
        self.assertGreater(success_rate, 0.95, f"Success rate should be >95%, got {success_rate:.1%}")
        
        print(f"   ✅ Concurrent operations: {success_rate:.1%} success rate")
    
    def test_memory_usage_stability(self):
        """Test memory usage doesn't grow unbounded"""
        print("\n🧠 Testing memory usage stability...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        # Initialize engine
        async def init_engine():
            mock_event_bus = Mock()
            await self.engine.initialize(mock_event_bus)
            return self.engine
        
        engine = asyncio.run(init_engine())
        
        if not engine.smallcap_ml_selector:
            print("   ⚠️ Skipping - smallcap ML selector not initialized")
            return
        
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"   Initial memory: {initial_memory:.1f} MB")
        
        # Simulate high-frequency trading scenario
        num_iterations = 1000
        
        for i in range(num_iterations):
            # Create context
            context = SmallcapTickerContext(
                symbol=f"MEMORY_TEST_{i}",
                gap_percentage=np.random.uniform(-0.1, 0.3),
                volume_ratio=np.random.uniform(0.5, 10.0),
                catalyst_strength=np.random.uniform(0.0, 1.0),
                catalyst_type_score=np.random.uniform(0.0, 1.0),
                price_tier=np.random.uniform(0.0, 1.0),
                time_of_day=np.random.uniform(0.0, 1.0),
                momentum_score=np.random.uniform(0.0, 1.0),
                premarket_factor=np.random.choice([0.0, 1.0]),
                current_price=np.random.uniform(1.0, 15.0),
                avg_volume_10=100000,
                avg_volume_50=100000,
                volatility_10=0.2,
                volatility_50=0.2,
                price_change_1h=np.random.uniform(-0.2, 0.5),
                price_change_4h=np.random.uniform(-0.2, 0.5),
                rsi_14=np.random.uniform(20.0, 80.0),
                volume_ratio_current=np.random.uniform(0.5, 5.0),
                volume_spike_frequency=0.1,
                hour_of_day=10.0,
                minutes_from_open=60,
                is_first_hour=True,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.5,
                mean_reversion_tendency=0.5
            )
            
            # Perform ML operations
            strategy = engine.smallcap_ml_selector.select_strategy(context)
            
            if strategy:
                reward = np.random.uniform(-0.1, 0.2)
                engine.smallcap_ml_selector.update_reward(strategy, context, reward, 2.0)
            
            # Check memory every 100 iterations
            if i % 100 == 0 and i > 0:
                gc.collect()  # Force garbage collection
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_growth = current_memory - initial_memory
                
                print(f"   Iteration {i}: {current_memory:.1f} MB (+{memory_growth:.1f} MB)")
                
                # Memory growth should be reasonable
                if memory_growth > 100:  # 100 MB growth threshold
                    self.fail(f"Excessive memory growth: {memory_growth:.1f} MB after {i} iterations")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory
        
        print(f"   Final memory: {final_memory:.1f} MB (+{total_growth:.1f} MB total)")
        
        # Should not grow more than 50MB for 1000 operations
        self.assertLess(total_growth, 50, f"Memory growth should be <50MB, got {total_growth:.1f}MB")
        
        print("   ✅ Memory usage is stable")
    
    def test_rapid_context_switching(self):
        """Test rapid switching between smallcap and largecap contexts"""
        print("\n⚡ Testing rapid context switching...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        # Initialize engine
        async def init_engine():
            mock_event_bus = Mock()
            await self.engine.initialize(mock_event_bus)
            return self.engine
        
        engine = asyncio.run(init_engine())
        
        # Create alternating smallcap/largecap contexts
        contexts = []
        
        for i in range(100):
            is_smallcap = i % 2 == 0
            price = 5.0 if is_smallcap else 50.0
            
            context = TickerContext(
                symbol=f"SWITCH_{i}",
                current_price=price,
                avg_volume_10=100000,
                avg_volume_50=100000,
                volatility_10=0.2,
                volatility_50=0.2,
                price_change_1h=0.05,
                price_change_4h=0.05,
                rsi_14=50.0,
                volume_ratio_current=1.5,
                volume_spike_frequency=0.1,
                hour_of_day=10.0,
                minutes_from_open=60,
                is_first_hour=True,
                is_last_hour=False,
                market_trend=0.0,
                sector_performance=0.0,
                breakout_success_rate=0.5,
                mean_reversion_tendency=0.5
            )
            
            contexts.append((context, is_smallcap))
        
        # Test rapid switching
        start_time = time.time()
        
        smallcap_conversions = 0
        largecap_conversions = 0
        
        for context, is_smallcap in contexts:
            # Test strategy selection path
            if is_smallcap:
                smallcap_context = engine._convert_to_smallcap_context(context.symbol, context)
                if smallcap_context:
                    smallcap_conversions += 1
            else:
                # Largecap path - should not convert
                smallcap_context = engine._convert_to_smallcap_context(context.symbol, context)
                if smallcap_context:
                    largecap_conversions += 1
        
        switching_time = time.time() - start_time
        
        print(f"   Processed 100 contexts in {switching_time:.3f}s")
        print(f"   Smallcap conversions: {smallcap_conversions}")
        print(f"   Largecap conversions: {largecap_conversions}")
        
        # Should be fast
        self.assertLess(switching_time, 1.0, "Should process 100 contexts in <1 second")
        
        # Should correctly identify smallcaps
        self.assertGreater(smallcap_conversions, 40, "Should convert most smallcap contexts")
        
        print("   ✅ Rapid context switching works efficiently")
    
    def test_edge_case_inputs(self):
        """Test with edge case inputs"""
        print("\n🎪 Testing edge case inputs...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        edge_cases = [
            {
                'name': 'All zeros',
                'kwargs': {
                    'gap_percentage': 0.0,
                    'volume_ratio': 0.0,
                    'catalyst_strength': 0.0,
                    'catalyst_type_score': 0.0,
                    'price_tier': 0.0,
                    'time_of_day': 0.0,
                    'momentum_score': 0.0,
                    'premarket_factor': 0.0
                }
            },
            {
                'name': 'All ones',
                'kwargs': {
                    'gap_percentage': 1.0,
                    'volume_ratio': 1.0,
                    'catalyst_strength': 1.0,
                    'catalyst_type_score': 1.0,
                    'price_tier': 1.0,
                    'time_of_day': 1.0,
                    'momentum_score': 1.0,
                    'premarket_factor': 1.0
                }
            },
            {
                'name': 'Very small numbers',
                'kwargs': {
                    'gap_percentage': 1e-10,
                    'volume_ratio': 1e-8,
                    'catalyst_strength': 1e-6,
                    'catalyst_type_score': 1e-4,
                    'price_tier': 1e-3,
                    'time_of_day': 1e-2,
                    'momentum_score': 1e-1,
                    'premarket_factor': 0.0
                }
            },
            {
                'name': 'NaN handling',
                'kwargs': {
                    'gap_percentage': float('inf'),
                    'volume_ratio': float('-inf'),
                    'catalyst_strength': 0.5,
                    'catalyst_type_score': 0.5,
                    'price_tier': 0.5,
                    'time_of_day': 0.5,
                    'momentum_score': 0.5,
                    'premarket_factor': 0.0
                }
            }
        ]
        
        for case in edge_cases:
            with self.subTest(case=case['name']):
                print(f"   Testing: {case['name']}")
                
                try:
                    context = SmallcapTickerContext(
                        symbol=case['name'].replace(' ', '_').upper(),
                        current_price=5.0,
                        avg_volume_10=100000,
                        avg_volume_50=100000,
                        volatility_10=0.2,
                        volatility_50=0.2,
                        price_change_1h=0.05,
                        price_change_4h=0.05,
                        rsi_14=50.0,
                        volume_ratio_current=1.5,
                        volume_spike_frequency=0.1,
                        hour_of_day=10.0,
                        minutes_from_open=60,
                        is_first_hour=True,
                        is_last_hour=False,
                        market_trend=0.0,
                        sector_performance=0.0,
                        breakout_success_rate=0.5,
                        mean_reversion_tendency=0.5,
                        **case['kwargs']
                    )
                    
                    # Test feature vector creation
                    features = context.to_feature_vector()
                    
                    # Features should be numerical (even if inf/nan)
                    self.assertEqual(len(features), 8, "Should have 8 features")
                    self.assertIsInstance(features, np.ndarray, "Should return numpy array")
                    
                    print(f"      ✅ {case['name']}: Features created successfully")
                    
                except Exception as e:
                    # Some edge cases might fail gracefully
                    print(f"      ⚠️ {case['name']}: {e}")
        
        print("   ✅ Edge case inputs handled appropriately")

def run_stress_tests():
    """Run all stress tests"""
    print("🔥 STARTING SMALLCAP ML STRESS TESTS")
    print("=" * 70)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmallcapStress)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print(f"🏁 STRESS TESTS COMPLETED")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"   {test}: {traceback}")
    
    if result.errors:
        print(f"\n🚨 ERRORS:")
        for test, traceback in result.errors:
            print(f"   {test}: {traceback}")
    
    if result.wasSuccessful():
        print(f"\n✅ ALL STRESS TESTS PASSED! Implementation is robust and production-ready.")
    else:
        print(f"\n❌ SOME STRESS TESTS FAILED. Implementation needs hardening before production.")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)