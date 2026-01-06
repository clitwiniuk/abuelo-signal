#!/usr/bin/env python3
"""
Comprehensive ML Exit System Tests
=================================

Tests completos para verificar integridad, fiabilidad y funcionamiento
del sistema ML Exit dinámico para smallcap trading.
"""

import asyncio
import logging
import sys
import os
import unittest
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from typing import Dict, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class MLExitSystemTests:
    """Comprehensive tests for ML Exit System"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.test_results = {}
        self.performance_metrics = {}
        
    async def run_all_tests(self):
        """Execute all test suites"""
        self.logger.info("🧪 Starting Comprehensive ML Exit System Tests")
        print("=" * 80)
        print("🧪 COMPREHENSIVE ML EXIT SYSTEM TESTS")
        print("=" * 80)
        
        test_suites = [
            ("Integration Tests", self._run_integration_tests),
            ("ML Learning Tests", self._run_ml_learning_tests),
            ("Smallcap Pattern Tests", self._run_smallcap_pattern_tests),
            ("Performance Tests", self._run_performance_tests),
            ("Reliability Tests", self._run_reliability_tests),
            ("Edge Case Tests", self._run_edge_case_tests),
            ("Continuous Learning Tests", self._run_continuous_learning_tests)
        ]
        
        total_tests = 0
        passed_tests = 0
        
        for suite_name, test_func in test_suites:
            self.logger.info(f"📋 Running {suite_name}...")
            print(f"\n📋 {suite_name}")
            print("-" * 60)
            
            try:
                suite_results = await test_func()
                suite_passed = sum(1 for result in suite_results.values() if result['passed'])
                suite_total = len(suite_results)
                
                total_tests += suite_total
                passed_tests += suite_passed
                
                self.test_results[suite_name] = suite_results
                
                print(f"✅ {suite_name}: {suite_passed}/{suite_total} tests passed")
                
                # Show individual test results
                for test_name, result in suite_results.items():
                    status = "✅" if result['passed'] else "❌"
                    print(f"   {status} {test_name}")
                    if not result['passed']:
                        print(f"      Error: {result['error']}")
                        
            except Exception as e:
                self.logger.error(f"❌ {suite_name} failed: {e}")
                print(f"❌ {suite_name} failed: {e}")
        
        # Final summary
        print("\n" + "=" * 80)
        print("📊 FINAL TEST SUMMARY")
        print("=" * 80)
        print(f"🎯 Overall: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
        
        if passed_tests == total_tests:
            print("\n🚀 ALL TESTS PASSED! ML Exit System is fully functional and reliable.")
        else:
            print(f"\n⚠️ {total_tests - passed_tests} tests failed. Review errors above.")
        
        return passed_tests == total_tests
    
    async def _run_integration_tests(self) -> Dict:
        """Test system integration components"""
        results = {}
        
        # Test 1: MLExitEngine initialization
        try:
            from core.ml_exit_engine import MLExitEngine, get_global_ml_exit_engine
            
            ml_engine = get_global_ml_exit_engine()
            
            # Verify initialization
            assert ml_engine is not None, "ML engine not initialized"
            assert hasattr(ml_engine, 'should_exit'), "Missing should_exit method"
            assert hasattr(ml_engine, 'smallcap_learning_enabled'), "Missing smallcap learning flag"
            assert ml_engine.smallcap_learning_enabled == True, "Smallcap learning not enabled"
            
            results['ml_engine_initialization'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['ml_engine_initialization'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Continuous Learning integration
        try:
            from core.continuous_learning_engine import get_global_learning_engine, record_trade_exit_feedback
            
            learning_engine = get_global_learning_engine()
            
            # Check if ml_exit_engine exists (it may be None initially)
            if not hasattr(learning_engine, 'ml_exit_engine') or learning_engine.ml_exit_engine is None:
                # Try to initialize it
                learning_engine._retrain_models_with_feedback()
            
            assert hasattr(learning_engine, 'ml_exit_engine'), "ML exit engine not integrated"
            
            # Test feedback recording
            test_features = {
                'entry_price': 10.0,
                'current_price': 10.5,
                'current_pnl_pct': 0.05,
                'time_in_position_minutes': 30,
                'entry_volume_ratio': 2.5,
                'current_volume_ratio': 3.0,
                'rsi': 65,
                'price_vs_vwap': 1.02,
                'fomo_score': 0.3,
                'time_of_day': 0.6,
                'market_stress': 0.03
            }
            
            record_trade_exit_feedback(
                "TEST", "test_strategy", "test_123", 10.5, "ML_TEST", 0.05, test_features, 0.85
            )
            
            results['continuous_learning_integration'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['continuous_learning_integration'] = {'passed': False, 'error': str(e)}
        
        # Test 3: BaseStrategy integration
        try:
            from strategies.base import BaseStrategy
            from core.interfaces import Position, MarketData
            
            # Test that BaseStrategy has ML exit methods
            assert hasattr(BaseStrategy, 'should_exit_position'), "BaseStrategy missing ML exit method"
            
            results['base_strategy_integration'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['base_strategy_integration'] = {'passed': False, 'error': str(e)}
        
        # Test 4: Database tables exist
        try:
            import sqlite3
            with sqlite3.connect('trading_data.db') as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['exit_feedback', 'exit_model_performance']
                for table in required_tables:
                    assert table in tables, f"Missing table: {table}"
            
            results['database_tables'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['database_tables'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_ml_learning_tests(self) -> Dict:
        """Test ML learning capabilities"""
        results = {}
        
        # Test 1: Feature extraction
        try:
            from core.ml_exit_engine import get_global_ml_exit_engine
            from core.interfaces import Position, MarketData
            
            ml_engine = get_global_ml_exit_engine()
            
            # Create test position and market data
            test_position = Position(
                symbol="TEST",
                quantity=100,
                avg_price=5.50,  # Smallcap price
                strategy="catalyst_momentum"
            )
            
            test_market_data = MarketData(
                symbol="TEST",
                timestamp=datetime.now(timezone.utc),
                open=5.40,
                high=5.80,
                low=5.30,
                close=5.75,
                volume=250000
            )
            
            bars_history = [test_market_data for _ in range(15)]  # Simulate history
            
            # Test feature extraction
            features = ml_engine._extract_exit_features(test_position, test_market_data, bars_history)
            
            assert features is not None, "Feature extraction failed"
            assert hasattr(features, 'current_pnl_pct'), "Missing PnL feature"
            assert hasattr(features, 'strategy'), "Missing strategy feature"
            
            # Test smallcap learning features in vector conversion
            feature_vector = ml_engine._features_to_vector(features)
            assert len(feature_vector) > 13, "Missing smallcap learning features"
            
            results['feature_extraction'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['feature_extraction'] = {'passed': False, 'error': str(e)}
        
        # Test 2: ML decision making
        try:
            decision = ml_engine.should_exit(test_position, test_market_data, bars_history)
            
            assert 'should_exit' in decision, "Missing exit decision"
            assert isinstance(decision['should_exit'], bool), "Exit decision not boolean"
            
            if decision['should_exit']:
                assert 'exit_type' in decision, "Missing exit type"
                assert 'confidence' in decision, "Missing confidence"
            
            results['ml_decision_making'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['ml_decision_making'] = {'passed': False, 'error': str(e)}
        
        # Test 3: Heuristic fallback
        try:
            from core.ml_exit_engine import ExitFeatures
            
            test_features = ExitFeatures(
                entry_price=5.50,
                current_price=5.75,
                current_pnl_pct=0.045,
                time_in_position_minutes=45,
                entry_volume_ratio=2.0,
                current_volume_ratio=3.0,
                rsi=65,
                price_vs_vwap=1.02,
                fomo_score=0.3,
                time_of_day=0.6,
                market_stress=0.03,
                strategy="test_strategy"
            )
            
            should_exit, confidence, profit_5min, profit_15min = ml_engine._heuristic_exit_decision(test_features)
            
            assert isinstance(should_exit, bool), "Heuristic decision not boolean"
            assert 0 <= confidence <= 1, "Invalid confidence range"
            
            results['heuristic_fallback'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['heuristic_fallback'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_smallcap_pattern_tests(self) -> Dict:
        """Test smallcap pattern learning capabilities"""
        results = {}
        
        # Test 1: Smallcap price detection
        try:
            from core.ml_exit_engine import get_global_ml_exit_engine
            from core.ml_exit_engine import ExitFeatures
            
            ml_engine = get_global_ml_exit_engine()
            
            # Test smallcap price ranges
            smallcap_features = ExitFeatures(
                entry_price=3.25,
                current_price=3.50,
                current_pnl_pct=0.077,
                time_in_position_minutes=30,
                entry_volume_ratio=4.0,
                current_volume_ratio=5.5,
                rsi=72,
                price_vs_vwap=1.05,
                fomo_score=0.4,
                time_of_day=0.58,  # 2:00 PM
                market_stress=0.045,
                strategy="catalyst_momentum"
            )
            
            feature_vector = ml_engine._features_to_vector(smallcap_features)
            
            # Check that smallcap flag is correctly set (feature index for is_smallcap_price)
            is_smallcap_flag = feature_vector[14]  # Based on feature order
            assert is_smallcap_flag == 1.0, "Smallcap not detected correctly"
            
            results['smallcap_detection'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['smallcap_detection'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Volatility per minute calculation
        try:
            volatile_features = ExitFeatures(
                entry_price=2.00,
                current_price=2.50,  # 25% move
                current_pnl_pct=0.25,
                time_in_position_minutes=15,  # High volatility per minute
                entry_volume_ratio=8.0,
                current_volume_ratio=12.0,
                rsi=85,
                price_vs_vwap=1.15,
                fomo_score=0.8,
                time_of_day=0.65,
                market_stress=0.08,
                strategy="volume_breakout"
            )
            
            feature_vector = ml_engine._features_to_vector(volatile_features)
            volatility_per_minute = feature_vector[15]  # volatility_per_minute feature
            
            # Should detect high volatility
            assert volatility_per_minute > 0.01, "High volatility not detected"
            
            results['volatility_detection'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['volatility_detection'] = {'passed': False, 'error': str(e)}
        
        # Test 3: Market timing features
        try:
            lunch_time_features = ExitFeatures(
                entry_price=8.00,
                current_price=8.20,
                current_pnl_pct=0.025,
                time_in_position_minutes=90,
                entry_volume_ratio=1.5,
                current_volume_ratio=1.2,
                rsi=55,
                price_vs_vwap=1.01,
                fomo_score=0.2,
                time_of_day=0.55,  # 1:12 PM (lunch time)
                market_stress=0.02,
                strategy="daily_plays"
            )
            
            feature_vector = ml_engine._features_to_vector(lunch_time_features)
            is_lunch_time = feature_vector[17]  # is_lunch_time feature
            
            # Should detect lunch time
            assert is_lunch_time == 1.0, "Lunch time not detected"
            
            results['market_timing_features'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['market_timing_features'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_performance_tests(self) -> Dict:
        """Test system performance and efficiency"""
        results = {}
        
        # Test 1: Response time
        try:
            import time
            from core.ml_exit_engine import get_global_ml_exit_engine
            from core.interfaces import Position, MarketData
            
            ml_engine = get_global_ml_exit_engine()
            
            test_position = Position(symbol="PERF", quantity=100, avg_price=4.25, strategy="test")
            test_data = MarketData(
                symbol="PERF", timestamp=datetime.now(timezone.utc),
                open=4.20, high=4.35, low=4.15, close=4.30, volume=150000
            )
            bars_history = [test_data for _ in range(20)]
            
            # Measure response time
            start_time = time.time()
            for _ in range(10):  # Run 10 decisions
                decision = ml_engine.should_exit(test_position, test_data, bars_history)
            end_time = time.time()
            
            avg_response_time = (end_time - start_time) / 10
            
            # Should be fast enough for real-time trading
            assert avg_response_time < 0.1, f"Too slow: {avg_response_time:.3f}s per decision"
            
            self.performance_metrics['avg_response_time'] = avg_response_time
            results['response_time'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['response_time'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Memory usage stability
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # Run many decisions to test memory leaks
            for i in range(100):
                test_position.symbol = f"MEM_{i}"
                decision = ml_engine.should_exit(test_position, test_data, bars_history)
            
            gc.collect()  # Force garbage collection
            final_memory = process.memory_info().rss
            memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB
            
            # Memory increase should be minimal
            assert memory_increase < 50, f"Memory leak detected: {memory_increase:.1f}MB increase"
            
            self.performance_metrics['memory_increase_mb'] = memory_increase
            results['memory_stability'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['memory_stability'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_reliability_tests(self) -> Dict:
        """Test system reliability and error handling"""
        results = {}
        
        # Test 1: Invalid data handling
        try:
            from core.ml_exit_engine import get_global_ml_exit_engine
            from core.interfaces import Position, MarketData
            
            ml_engine = get_global_ml_exit_engine()
            
            # Test with invalid position
            invalid_position = Position(symbol="INVALID", quantity=0, avg_price=0)
            test_data = MarketData(
                symbol="INVALID", timestamp=datetime.now(timezone.utc),
                open=1.0, high=1.0, low=1.0, close=1.0, volume=0
            )
            
            decision = ml_engine.should_exit(invalid_position, test_data, [])
            
            # Should handle gracefully, not crash
            assert 'should_exit' in decision, "System should handle invalid data gracefully"
            
            results['invalid_data_handling'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['invalid_data_handling'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Edge case values
        try:
            extreme_position = Position(symbol="EXTREME", quantity=100, avg_price=0.01, strategy="test")
            extreme_data = MarketData(
                symbol="EXTREME", timestamp=datetime.now(timezone.utc),
                open=0.01, high=100.0, low=0.01, close=50.0, volume=1000000000
            )
            
            decision = ml_engine.should_exit(extreme_position, extreme_data, [extreme_data])
            
            assert isinstance(decision['should_exit'], bool), "Should handle extreme values"
            
            results['edge_case_values'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['edge_case_values'] = {'passed': False, 'error': str(e)}
        
        # Test 3: Concurrent access
        try:
            import threading
            import time
            
            results_list = []
            errors_list = []
            
            def concurrent_test():
                try:
                    for i in range(20):
                        test_pos = Position(symbol=f"CONC_{i}", quantity=100, avg_price=5.0, strategy="test")
                        test_data = MarketData(
                            symbol=f"CONC_{i}", timestamp=datetime.now(timezone.utc),
                            open=5.0, high=5.1, low=4.9, close=5.05, volume=100000
                        )
                        decision = ml_engine.should_exit(test_pos, test_data, [test_data])
                        results_list.append(decision)
                except Exception as e:
                    errors_list.append(str(e))
            
            # Run concurrent tests
            threads = []
            for _ in range(5):  # 5 concurrent threads
                thread = threading.Thread(target=concurrent_test)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            assert len(errors_list) == 0, f"Concurrent access errors: {errors_list}"
            assert len(results_list) == 100, "Not all concurrent operations completed"
            
            results['concurrent_access'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['concurrent_access'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_edge_case_tests(self) -> Dict:
        """Test edge cases and boundary conditions"""
        results = {}
        
        # Test 1: Zero holding time
        try:
            from core.ml_exit_engine import get_global_ml_exit_engine
            from core.interfaces import Position, MarketData
            
            ml_engine = get_global_ml_exit_engine()
            
            current_time = datetime.now(timezone.utc)
            zero_time_position = Position(
                symbol="ZERO_TIME", 
                quantity=100, 
                avg_price=10.0, 
                strategy="test",
                entry_time=current_time  # Same as current time
            )
            
            test_data = MarketData(
                symbol="ZERO_TIME", timestamp=current_time,
                open=10.0, high=10.1, low=9.9, close=10.05, volume=50000
            )
            
            decision = ml_engine.should_exit(zero_time_position, test_data, [test_data])
            
            # Should handle zero holding time
            assert 'should_exit' in decision, "Should handle zero holding time"
            
            results['zero_holding_time'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['zero_holding_time'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Extreme profit/loss scenarios
        try:
            # Extreme profit scenario
            extreme_profit_position = Position(
                symbol="BIG_WIN", 
                quantity=100, 
                avg_price=1.0,  # Bought at $1
                strategy="test"
            )
            
            extreme_profit_data = MarketData(
                symbol="BIG_WIN", timestamp=datetime.now(timezone.utc),
                open=5.0, high=5.2, low=4.8, close=5.0,  # Now at $5 (400% gain)
                volume=1000000
            )
            
            decision = ml_engine.should_exit(extreme_profit_position, extreme_profit_data, [extreme_profit_data])
            
            # System should handle extreme profits
            assert isinstance(decision['should_exit'], bool), "Should handle extreme profits"
            
            results['extreme_scenarios'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['extreme_scenarios'] = {'passed': False, 'error': str(e)}
        
        # Test 3: Missing bars history
        try:
            test_position = Position(symbol="NO_HIST", quantity=100, avg_price=5.0, strategy="test")
            test_data = MarketData(
                symbol="NO_HIST", timestamp=datetime.now(timezone.utc),
                open=5.0, high=5.1, low=4.9, close=5.02, volume=25000
            )
            
            # Test with empty history
            decision = ml_engine.should_exit(test_position, test_data, [])
            
            assert 'should_exit' in decision, "Should handle missing bars history"
            
            results['missing_bars_history'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['missing_bars_history'] = {'passed': False, 'error': str(e)}
        
        return results
    
    async def _run_continuous_learning_tests(self) -> Dict:
        """Test continuous learning functionality"""
        results = {}
        
        # Test 1: Feedback recording
        try:
            from core.continuous_learning_engine import record_trade_exit_feedback
            
            test_features = {
                'entry_price': 7.50,
                'current_price': 8.25,
                'current_pnl_pct': 0.10,
                'time_in_position_minutes': 60,
                'entry_volume_ratio': 3.0,
                'current_volume_ratio': 2.5,
                'rsi': 70,
                'price_vs_vwap': 1.08,
                'fomo_score': 0.6,
                'time_of_day': 0.7,
                'market_stress': 0.04,
                'strategy': 'catalyst_momentum'
            }
            
            # Record feedback (should not raise exception)
            record_trade_exit_feedback(
                "LEARNING_TEST", "catalyst_momentum", "learn_123",
                8.25, "ML_PROFIT_TARGET", 0.10, test_features, 0.90
            )
            
            results['feedback_recording'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['feedback_recording'] = {'passed': False, 'error': str(e)}
        
        # Test 2: Model training trigger
        try:
            from core.continuous_learning_engine import get_global_learning_engine
            
            learning_engine = get_global_learning_engine()
            
            # Check that learning engine has ML exit engine
            assert hasattr(learning_engine, 'ml_exit_engine'), "ML exit engine not integrated"
            
            # Test force retrain (should not crash)
            if hasattr(learning_engine, 'force_retrain'):
                learning_engine.force_retrain()
            
            results['model_training'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['model_training'] = {'passed': False, 'error': str(e)}
        
        # Test 3: Learning metrics
        try:
            learning_engine = get_global_learning_engine()
            
            if hasattr(learning_engine, 'get_learning_metrics'):
                metrics = learning_engine.get_learning_metrics()
                assert hasattr(metrics, 'total_feedback_samples'), "Missing learning metrics"
            
            results['learning_metrics'] = {'passed': True, 'error': None}
            
        except Exception as e:
            results['learning_metrics'] = {'passed': False, 'error': str(e)}
        
        return results

async def main():
    """Run comprehensive tests"""
    print("🧪 Starting Comprehensive ML Exit System Tests...")
    
    test_suite = MLExitSystemTests()
    success = await test_suite.run_all_tests()
    
    # Performance metrics summary
    if test_suite.performance_metrics:
        print("\n📊 PERFORMANCE METRICS:")
        for metric, value in test_suite.performance_metrics.items():
            print(f"   • {metric}: {value}")
    
    if success:
        print("\n✅ ALL TESTS PASSED! System is production-ready.")
        print("\n🎯 Next Steps:")
        print("   • Deploy to production trading environment")
        print("   • Monitor ML learning progress after 50+ trades")
        print("   • Review exit decision logs for optimization")
        return 0
    else:
        print("\n❌ Some tests failed. Review and fix issues before production deployment.")
        return 1

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)