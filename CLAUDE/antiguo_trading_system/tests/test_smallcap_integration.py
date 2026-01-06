# tests/test_smallcap_integration.py
"""
Test de integración del SmallcapContextualBandit con MLMultiStrategyEngine
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine, SMALLCAP_ML_AVAILABLE
from strategies.ml_strategy_selector import TickerContext
from core.interfaces import MarketData, Signal, SignalType

class TestSmallcapIntegration(unittest.TestCase):
    """Test integration of SmallcapContextualBandit with MLMultiStrategyEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Parameters to enable smallcap ML
        parameters = {
            'smallcap_ml_enabled': True,
            'smallcap_price_threshold': 15.0
        }
        
        # Create ML engine
        self.engine = MLMultiStrategyEngine(parameters)
        
        # Create test data
        self.test_bar_smallcap = MarketData(
            symbol="BIOTECH",
            timestamp=datetime.now(timezone.utc),
            open=5.00,
            high=5.50,
            low=4.90,
            close=5.25,  # Smallcap price
            volume=250000
        )
        
        self.test_bar_largecap = MarketData(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            open=150.00,
            high=155.00,
            low=149.00,
            close=152.50,  # Large cap price
            volume=1000000
        )
        
        print(f"\n🧪 Testing smallcap integration (available: {SMALLCAP_ML_AVAILABLE})")
    
    def test_smallcap_availability(self):
        """Test that smallcap ML components are available"""
        print("\n📦 Testing smallcap ML availability...")
        
        if SMALLCAP_ML_AVAILABLE:
            print("   ✅ SmallcapContextualBandit components available")
            self.assertTrue(self.engine.smallcap_ml_enabled)
            self.assertEqual(self.engine.smallcap_price_threshold, 15.0)
        else:
            print("   ⚠️ SmallcapContextualBandit components not available")
            self.assertFalse(self.engine.smallcap_ml_enabled)
    
    async def test_smallcap_vs_largecap_detection(self):
        """Test that engine correctly identifies smallcap vs largecap"""
        print("\n🔍 Testing smallcap vs largecap detection...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        # Initialize the engine
        mock_event_bus = Mock()
        await self.engine.initialize(mock_event_bus)
        
        # Create contexts
        smallcap_context = TickerContext(
            symbol="BIOTECH",
            current_price=5.25,  # Smallcap
            avg_volume_10=200000,
            avg_volume_50=180000,
            volatility_10=0.3,
            volatility_50=0.25,
            price_change_1h=0.05,
            price_change_4h=0.08,
            rsi_14=60.0,
            volume_ratio_current=1.4,
            volume_spike_frequency=0.15,
            hour_of_day=10.5,
            minutes_from_open=60,
            is_first_hour=True,
            is_last_hour=False,
            market_trend=0.1,
            sector_performance=0.05,
            breakout_success_rate=0.6,
            mean_reversion_tendency=0.3
        )
        
        largecap_context = TickerContext(
            symbol="AAPL",
            current_price=152.50,  # Large cap
            avg_volume_10=50000000,
            avg_volume_50=45000000,
            volatility_10=0.15,
            volatility_50=0.12,
            price_change_1h=0.02,
            price_change_4h=0.03,
            rsi_14=55.0,
            volume_ratio_current=1.1,
            volume_spike_frequency=0.05,
            hour_of_day=10.5,
            minutes_from_open=60,
            is_first_hour=True,
            is_last_hour=False,
            market_trend=0.1,
            sector_performance=0.02,
            breakout_success_rate=0.5,
            mean_reversion_tendency=0.5
        )
        
        # Test strategy selection
        smallcap_strategies = await self.engine._ml_select_strategies("BIOTECH", smallcap_context)
        largecap_strategies = await self.engine._ml_select_strategies("AAPL", largecap_context)
        
        print(f"   Smallcap (${smallcap_context.current_price:.2f}) strategies: {smallcap_strategies}")
        print(f"   Largecap (${largecap_context.current_price:.2f}) strategies: {largecap_strategies}")
        
        # Both should return strategies
        self.assertIsInstance(smallcap_strategies, list)
        self.assertIsInstance(largecap_strategies, list)
        self.assertGreater(len(smallcap_strategies), 0)
        self.assertGreater(len(largecap_strategies), 0)
        
        print("   ✅ Strategy selection works for both smallcap and largecap")
    
    def test_smallcap_context_conversion(self):
        """Test conversion from TickerContext to SmallcapTickerContext"""
        print("\n🔄 Testing context conversion...")
        
        if not SMALLCAP_ML_AVAILABLE:
            print("   ⚠️ Skipping - smallcap ML not available")
            return
        
        # Create test context
        context = TickerContext(
            symbol="BIOTECH",
            current_price=5.25,
            avg_volume_10=200000,
            avg_volume_50=180000,
            volatility_10=0.3,
            volatility_50=0.25,
            price_change_1h=0.08,  # 8% move
            price_change_4h=0.12,
            rsi_14=65.0,
            volume_ratio_current=2.5,  # High volume
            volume_spike_frequency=0.2,
            hour_of_day=10.0,
            minutes_from_open=30,
            is_first_hour=True,
            is_last_hour=False,
            market_trend=0.1,
            sector_performance=0.05,
            breakout_success_rate=0.7,
            mean_reversion_tendency=0.3
        )
        
        # Convert to smallcap context
        smallcap_context = self.engine._convert_to_smallcap_context("BIOTECH", context)
        
        if smallcap_context:
            print(f"   ✅ Conversion successful")
            print(f"   Symbol: {smallcap_context.symbol}")
            print(f"   Gap: {smallcap_context.gap_percentage:.1%}")
            print(f"   Volume: {smallcap_context.volume_ratio:.1f}x")
            print(f"   Price tier: {smallcap_context.price_tier:.2f}")
            print(f"   Momentum: {smallcap_context.momentum_score:.2f}")
            
            # Verify feature vector
            features = smallcap_context.to_feature_vector()
            self.assertEqual(len(features), 8)
            print(f"   Feature vector (8 features): {features}")
            
        else:
            print("   ❌ Conversion failed")
            self.fail("Context conversion should succeed")
    
    def test_strategy_mapping(self):
        """Test strategy mapping functionality"""
        print("\n🗺️ Testing strategy mapping...")
        
        mapping = self.engine._get_strategy_mapping()
        
        print(f"   Strategy mapping entries: {len(mapping)}")
        
        # Test some key mappings
        self.assertEqual(mapping.get('gap_go'), 'gap_go')
        self.assertEqual(mapping.get('optimized_gap_go'), 'gap_go')
        self.assertEqual(mapping.get('volume_breakout'), 'volume_breakout')
        self.assertEqual(mapping.get('daily_plays'), 'daily_plays')
        self.assertEqual(mapping.get('explosive_volume'), 'explosive_volume')
        
        print("   ✅ Strategy mapping working correctly")
    
    def test_statistics_include_smallcap_info(self):
        """Test that statistics include smallcap ML information"""
        print("\n📊 Testing statistics...")
        
        stats = self.engine.get_ml_statistics()
        
        # Should include smallcap info
        self.assertIn('smallcap_ml_enabled', stats)
        self.assertIn('smallcap_price_threshold', stats)
        
        print(f"   Smallcap ML enabled: {stats['smallcap_ml_enabled']}")
        print(f"   Price threshold: ${stats['smallcap_price_threshold']:.2f}")
        
        print("   ✅ Statistics include smallcap information")

async def run_async_tests():
    """Run async tests"""
    test_instance = TestSmallcapIntegration()
    test_instance.setUp()
    
    if SMALLCAP_ML_AVAILABLE:
        await test_instance.test_smallcap_vs_largecap_detection()
    else:
        print("⚠️ Skipping async tests - smallcap ML not available")

def run_smallcap_integration_tests():
    """Run all smallcap integration tests"""
    print("🧪 STARTING SMALLCAP INTEGRATION TESTS")
    print("=" * 60)
    
    # Run sync tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmallcapIntegration)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Run async tests
    print("\n🔄 Running async tests...")
    asyncio.run(run_async_tests())
    
    print("\n" + "=" * 60)
    print(f"🏁 INTEGRATION TESTS COMPLETED")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print(f"\n✅ ALL INTEGRATION TESTS PASSED! Smallcap ML integration working correctly.")
    else:
        print(f"\n❌ SOME TESTS FAILED. Check the output above for details.")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_smallcap_integration_tests()
    sys.exit(0 if success else 1)