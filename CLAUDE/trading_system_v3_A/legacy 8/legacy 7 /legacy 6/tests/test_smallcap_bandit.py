# tests/test_smallcap_bandit.py
"""
Integration tests for SmallcapContextualBandit
Tests the smallcap ML strategy selector and its integration with existing systems
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime
from strategies.smallcap_bandit_adapter import (
    SmallcapTickerContext, 
    SmallcapContextualBandit,
    create_smallcap_bandit
)

class TestSmallcapContextualBandit(unittest.TestCase):
    """Test smallcap contextual bandit functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Smallcap strategies for testing
        self.strategies = [
            'gap_go',
            'volume_breakout', 
            'daily_plays',
            'explosive_volume',
            'macdv_smallcaps'
        ]
        
        # Create bandit instance
        self.bandit = SmallcapContextualBandit(self.strategies)
        
        # Create sample contexts
        self.fda_context = SmallcapTickerContext(
            symbol="BIOTECH",
            gap_percentage=0.15,        # 15% gap
            volume_ratio=4.5,           # 4.5x volume
            catalyst_strength=0.9,      # Strong FDA catalyst
            catalyst_type_score=1.0,    # FDA = highest score
            price_tier=0.4,            # $0.50-$15 range (~$6.50)
            time_of_day=0.1,           # Early morning
            momentum_score=0.8,        # High momentum
            premarket_factor=1.0,      # Premarket
            current_price=6.50,
            avg_volume_10=100000,
            avg_volume_50=100000,
            volatility_10=0.3,
            volatility_50=0.3,
            price_change_1h=0.15,
            price_change_4h=0.15,
            rsi_14=60.0,
            volume_ratio_current=4.5,
            volume_spike_frequency=0.2,
            hour_of_day=9.75,          # 9:45 AM
            minutes_from_open=15,      # 15 minutes from open
            is_first_hour=True,
            is_last_hour=False,
            market_trend=0.1,
            sector_performance=0.05,
            breakout_success_rate=0.7,
            mean_reversion_tendency=0.3
        )
        
        self.technical_context = SmallcapTickerContext(
            symbol="TECH",
            gap_percentage=0.05,        # 5% gap
            volume_ratio=1.8,           # 1.8x volume
            catalyst_strength=0.3,      # Weak catalyst
            catalyst_type_score=0.1,    # Technical = lowest score
            price_tier=0.2,            # Lower price
            time_of_day=0.6,           # Mid-day
            momentum_score=0.4,        # Lower momentum
            premarket_factor=0.0,      # Regular hours
            current_price=3.25,
            avg_volume_10=50000,
            avg_volume_50=50000,
            volatility_10=0.2,
            volatility_50=0.2,
            price_change_1h=0.05,
            price_change_4h=0.05,
            rsi_14=45.0,
            volume_ratio_current=1.8,
            volume_spike_frequency=0.1,
            hour_of_day=12.5,          # 12:30 PM
            minutes_from_open=180,     # 3 hours from open
            is_first_hour=False,
            is_last_hour=False,
            market_trend=0.0,
            sector_performance=0.0,
            breakout_success_rate=0.4,
            mean_reversion_tendency=0.6
        )
        
        print(f"\n🧪 Testing SmallcapContextualBandit with {len(self.strategies)} strategies")
    
    def test_feature_vector_creation(self):
        """Test SmallcapTickerContext feature vector creation"""
        print("\n📊 Testing feature vector creation...")
        
        # Test FDA context
        fda_features = self.fda_context.to_feature_vector()
        print(f"   FDA context features: {fda_features}")
        
        # Should have 8 features (vs 18+ in original)
        self.assertEqual(len(fda_features), 8)
        
        # Check key features
        self.assertEqual(fda_features[0], 0.15)  # gap_percentage
        self.assertEqual(fda_features[1], 4.5)   # volume_ratio
        self.assertEqual(fda_features[2], 0.9)   # catalyst_strength
        self.assertEqual(fda_features[3], 1.0)   # catalyst_type_score (FDA)
        
        # Test technical context
        tech_features = self.technical_context.to_feature_vector()
        print(f"   Technical context features: {tech_features}")
        
        self.assertEqual(len(tech_features), 8)
        self.assertEqual(tech_features[3], 0.1)  # catalyst_type_score (TECHNICAL)
        
        print("   ✅ Feature vector creation test passed")
    
    def test_strategy_selection_filtering(self):
        """Test smallcap-specific strategy filtering"""
        print("\n🎯 Testing strategy selection filtering...")
        
        # Test FDA context - should prefer daily_plays
        selected_fda = self.bandit.select_strategy(self.fda_context)
        print(f"   FDA context selected: {selected_fda}")
        
        # Run multiple selections to see distribution
        fda_selections = []
        for _ in range(10):
            strategy = self.bandit.select_strategy(self.fda_context)
            fda_selections.append(strategy)
        
        print(f"   FDA selections (10 runs): {set(fda_selections)}")
        
        # Test technical context - should have different preferences
        selected_tech = self.bandit.select_strategy(self.technical_context)
        print(f"   Technical context selected: {selected_tech}")
        
        # Test low volume context - should filter out explosive_volume
        low_volume_context = SmallcapTickerContext(
            symbol="LOWVOL",
            gap_percentage=0.12,
            volume_ratio=1.2,  # Low volume
            catalyst_strength=0.5,
            catalyst_type_score=0.5,
            price_tier=0.5,
            time_of_day=0.3,
            momentum_score=0.3,
            premarket_factor=0.0,
            current_price=4.0,
            avg_volume_10=30000,
            avg_volume_50=30000,
            volatility_10=0.15,
            volatility_50=0.15,
            price_change_1h=0.12,
            price_change_4h=0.12,
            rsi_14=50.0,
            volume_ratio_current=1.2,
            volume_spike_frequency=0.05,
            hour_of_day=11.0,
            minutes_from_open=90,
            is_first_hour=False,
            is_last_hour=False,
            market_trend=0.0,
            sector_performance=0.0,
            breakout_success_rate=0.5,
            mean_reversion_tendency=0.5
        )
        
        # explosive_volume should be filtered out due to low volume
        low_vol_selections = []
        for _ in range(5):
            strategy = self.bandit.select_strategy(low_volume_context)
            low_vol_selections.append(strategy)
        
        print(f"   Low volume selections: {set(low_vol_selections)}")
        self.assertNotIn('explosive_volume', low_vol_selections, 
                        "explosive_volume should be filtered out for low volume")
        
        print("   ✅ Strategy filtering test passed")
    
    def test_reward_update_and_learning(self):
        """Test reward updating and learning mechanism"""
        print("\n📈 Testing reward updates and learning...")
        
        # Simulate trading results
        trades = [
            # FDA play with good results
            (self.fda_context, 'daily_plays', 0.08, 1.5),  # 8% profit in 1.5h
            (self.fda_context, 'daily_plays', 0.12, 2.0),  # 12% profit in 2h
            (self.fda_context, 'gap_go', -0.02, 0.5),      # 2% loss quickly
            
            # Technical play results
            (self.technical_context, 'volume_breakout', 0.03, 4.0),  # 3% profit in 4h
            (self.technical_context, 'gap_go', -0.01, 6.0),         # 1% loss held too long
        ]
        
        for context, strategy, reward, duration in trades:
            print(f"   Updating: {strategy} on {context.symbol} = {reward:.1%} in {duration}h")
            self.bandit.update_reward(strategy, context, reward, duration)
        
        # Check strategy stats
        insights = self.bandit.get_smallcap_strategy_insights()
        print(f"\n   Strategy performance:")
        for strategy, perf in insights['strategy_performance'].items():
            if perf['total_trades'] > 0:
                print(f"      {strategy}: {perf['total_trades']} trades, "
                      f"{perf['win_rate']:.1%} WR, {perf['avg_reward']:.2f} avg")
        
        # daily_plays should show good performance
        if 'daily_plays' in insights['strategy_performance']:
            daily_stats = insights['strategy_performance']['daily_plays']
            self.assertGreater(daily_stats['win_rate'], 0.5, "daily_plays should have >50% win rate")
        
        print("   ✅ Reward update and learning test passed")
    
    def test_time_based_filtering(self):
        """Test time-based strategy filtering"""
        print("\n⏰ Testing time-based filtering...")
        
        # Create late-day context
        late_day_context = SmallcapTickerContext(
            symbol="LATE",
            gap_percentage=0.10,
            volume_ratio=3.0,
            catalyst_strength=0.6,
            catalyst_type_score=0.7,
            price_tier=0.5,
            time_of_day=0.9,  # Late in day (90% through session)
            momentum_score=0.6,
            premarket_factor=0.0,
            current_price=5.0,
            avg_volume_10=80000,
            avg_volume_50=80000,
            volatility_10=0.25,
            volatility_50=0.25,
            price_change_1h=0.10,
            price_change_4h=0.10,
            rsi_14=55.0,
            volume_ratio_current=3.0,
            volume_spike_frequency=0.15,
            hour_of_day=15.5,  # 3:30 PM
            minutes_from_open=360,  # 6 hours from open
            is_first_hour=False,
            is_last_hour=True,
            market_trend=0.05,
            sector_performance=0.02,
            breakout_success_rate=0.6,
            mean_reversion_tendency=0.4
        )
        
        # Run multiple selections
        late_selections = []
        for _ in range(8):
            strategy = self.bandit.select_strategy(late_day_context)
            late_selections.append(strategy)
        
        print(f"   Late day selections: {set(late_selections)}")
        
        # gap_go and explosive_volume should be less likely late in day
        gap_count = late_selections.count('gap_go')
        explosive_count = late_selections.count('explosive_volume')
        
        print(f"   gap_go selected: {gap_count}/8 times")
        print(f"   explosive_volume selected: {explosive_count}/8 times")
        
        # These strategies work better early in the day
        self.assertLessEqual(gap_count, 3, "gap_go should be less common late in day")
        
        print("   ✅ Time-based filtering test passed")
    
    def test_performance_summary(self):
        """Test performance summary formatting"""
        print("\n📊 Testing performance summary...")
        
        # Add some trades to get meaningful stats
        self.bandit.update_reward('daily_plays', self.fda_context, 0.15, 2.0)
        self.bandit.update_reward('gap_go', self.fda_context, 0.08, 1.0)
        self.bandit.update_reward('volume_breakout', self.technical_context, 0.02, 3.0)
        
        # Get formatted summary
        summary = self.bandit.format_performance_summary()
        print(f"\n{summary}")
        
        # Check that summary contains expected elements
        self.assertIn("SMALLCAP CONTEXTUAL BANDIT", summary)
        self.assertIn("Features: 8", summary)
        self.assertIn("STRATEGY PERFORMANCE", summary)
        
        print("   ✅ Performance summary test passed")
    
    def test_factory_function(self):
        """Test factory function for creating bandit"""
        print("\n🏭 Testing factory function...")
        
        # Test with default strategies
        bandit1 = create_smallcap_bandit()
        self.assertIsInstance(bandit1, SmallcapContextualBandit)
        self.assertEqual(len(bandit1.strategies), 5)  # Default strategies
        
        # Test with custom strategies
        custom_strategies = ['gap_go', 'daily_plays']
        bandit2 = create_smallcap_bandit(custom_strategies)
        self.assertEqual(bandit2.strategies, custom_strategies)
        
        print(f"   Default bandit strategies: {bandit1.strategies}")
        print(f"   Custom bandit strategies: {bandit2.strategies}")
        
        print("   ✅ Factory function test passed")
    
    def test_integration_with_original_bandit(self):
        """Test compatibility with original ContextualBandit interface"""
        print("\n🔗 Testing integration with original bandit...")
        
        # Test that SmallcapContextualBandit has same interface as ContextualBandit
        required_methods = [
            'select_strategy',
            'update_reward', 
            'save_model',
            'load_model'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(self.bandit, method), 
                          f"SmallcapContextualBandit missing method: {method}")
        
        # Test select_strategy interface compatibility
        strategy = self.bandit.select_strategy(self.fda_context)
        self.assertIsInstance(strategy, str)
        self.assertIn(strategy, self.strategies)
        
        # Test update_reward interface compatibility  
        self.bandit.update_reward('daily_plays', self.fda_context, 0.10)
        
        print("   ✅ Integration compatibility test passed")
    
    def test_fallback_context_creation(self):
        """Test fallback context creation when imports fail"""
        print("\n🛡️ Testing fallback context creation...")
        
        # Create mock context without smallcap imports
        mock_context = Mock()
        mock_context.symbol = "FALLBACK"
        mock_context.gap_percentage = 0.08
        mock_context.volume_ratio = 2.0
        mock_context.current_price = 4.50
        
        # Test fallback creation
        fallback_context = SmallcapTickerContext._create_fallback_context(mock_context)
        
        print(f"   Fallback context: {fallback_context.symbol}")
        print(f"   Gap: {fallback_context.gap_percentage}")
        print(f"   Volume: {fallback_context.volume_ratio}")
        
        # Should create valid context with defaults
        self.assertEqual(fallback_context.symbol, "FALLBACK")
        self.assertEqual(fallback_context.gap_percentage, 0.08)
        self.assertEqual(fallback_context.volume_ratio, 2.0)
        self.assertEqual(fallback_context.catalyst_strength, 0.5)  # Default
        
        # Should produce valid 8-feature vector
        features = fallback_context.to_feature_vector()
        self.assertEqual(len(features), 8)
        
        print("   ✅ Fallback context test passed")

def run_smallcap_bandit_tests():
    """Run all smallcap bandit tests"""
    print("🧪 STARTING SMALLCAP CONTEXTUAL BANDIT TESTS")
    print("=" * 65)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSmallcapContextualBandit)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    print("\n" + "=" * 65)
    print(f"🏁 TESTS COMPLETED")
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
        print(f"\n✅ ALL TESTS PASSED! SmallcapContextualBandit is working correctly.")
    else:
        print(f"\n❌ SOME TESTS FAILED. Check the output above for details.")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_smallcap_bandit_tests()
    sys.exit(0 if success else 1)