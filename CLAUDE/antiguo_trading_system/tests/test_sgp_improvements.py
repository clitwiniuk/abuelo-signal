#!/usr/bin/env python3
"""
Test Smart Game Plan Improvements
================================

Tests the enhanced smallcap-specific context awareness and strategy selection improvements
"""

import sys
import os
from unittest.mock import Mock
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_game_plan_manager import (
    SmartGamePlanManager, StrategyType, MarketPhase, MarketSentiment, MarketContext
)

class TestSGPImprovements:
    
    def __init__(self):
        self.config = Mock()
        self.logger = Mock()
        self.sgp = SmartGamePlanManager(self.config, None, self.logger)
        
        print("🧪 Smart Game Plan Improvements Test")
        print("=" * 50)
        
    def create_market_context(self, phase: MarketPhase, sentiment: MarketSentiment, 
                             vix: float = 20.0, spy_change: float = 0.0) -> MarketContext:
        """Create market context for testing"""
        return MarketContext(
            current_phase=phase,
            time_in_phase=None,
            next_phase_in=None,
            market_sentiment=sentiment,
            spy_change_pct=spy_change,
            vix_level=vix,
            sector_rotation={},
            overall_volume_ratio=0.9,
            volatility_regime='NORMAL' if vix < 25 else 'HIGH',
            adv_decline_ratio=1.2,
            breaking_news_count=1,
            major_economic_events=[],
            sector_news={},
            recent_strategy_performance={},
            current_day_pnl=0.0,
            current_positions=2,
            last_updated=datetime.now(),
            data_quality_score=1.0
        )
    
    def test_smallcap_context_multipliers(self):
        """Test smallcap-specific context multipliers"""
        print("\n📊 Testing Smallcap Context Multipliers")
        print("-" * 40)
        
        # Test different VIX/SPY scenarios
        scenarios = [
            ('Low VIX, SPY Up', 15.0, 0.03),      # Complacent market
            ('Normal Market', 20.0, 0.01),        # Normal conditions
            ('High VIX, SPY Down', 35.0, -0.03),  # Fear + down market
            ('Panic Conditions', 45.0, -0.05)     # Extreme fear
        ]
        
        for name, vix, spy_change in scenarios:
            context = self.create_market_context(
                MarketPhase.OPENING, 
                MarketSentiment.NEUTRAL,
                vix, 
                spy_change
            )
            self.sgp.market_context = context
            
            multipliers = self.sgp._get_smallcap_context_multiplier()
            
            print(f"📈 {name}:")
            print(f"   VIX: {vix}, SPY: {spy_change*100:+.1f}%")
            print(f"   Base Confidence: {multipliers['confidence_base']:.3f}x")
            print(f"   Momentum Favor: {multipliers['momentum_favor']:.3f}x")
            print(f"   Reversal Favor: {multipliers['reversal_favor']:.3f}x")
            print()
        
        # Verify high VIX increases smallcap opportunities
        high_vix_context = self.create_market_context(
            MarketPhase.OPENING, MarketSentiment.VERY_BEARISH, 35.0, -0.03
        )
        self.sgp.market_context = high_vix_context
        high_vix_mult = self.sgp._get_smallcap_context_multiplier()
        
        print("✅ Key Assertions:")
        print(f"   High VIX boosts smallcap confidence: {high_vix_mult['confidence_base'] > 1.0}")
        print(f"   High VIX favors reversals: {high_vix_mult['reversal_favor'] > 1.1}")
        print(f"   Bearish + High VIX = Strong reversal favor: {high_vix_mult['reversal_favor'] > 1.2}")
    
    def test_improved_strategy_selection(self):
        """Test that more strategies are now selected"""
        print("\n🎯 Testing Improved Strategy Selection")
        print("-" * 40)
        
        # Test scenarios that should now trigger previously unused strategies
        test_cases = [
            {
                'name': 'Earnings Play (3% gap)',
                'context': self.create_market_context(MarketPhase.OPENING, MarketSentiment.BULLISH),
                'opportunity': {
                    'symbol': 'EARNINGS_TEST',
                    'catalyst_type': 'EARNINGS',
                    'gap_percentage': 0.04,  # 4% gap (was 5% minimum)
                    'volume_ratio': 3.0,
                    'current_price': 5.50
                },
                'expected_strategy': StrategyType.EARNINGS_SURPRISE
            },
            {
                'name': 'Gap and Go (8% gap)', 
                'context': self.create_market_context(MarketPhase.OPENING, MarketSentiment.NEUTRAL),
                'opportunity': {
                    'symbol': 'GAP_GO_TEST',
                    'catalyst_type': 'OTHER',
                    'gap_percentage': 0.09,  # 9% gap (was 12% minimum)
                    'volume_ratio': 2.2,     # Lower volume requirement
                    'current_price': 4.25
                },
                'expected_strategy': StrategyType.GAP_AND_GO
            },
            {
                'name': 'News Momentum (Contract)',
                'context': self.create_market_context(MarketPhase.AFTERNOON, MarketSentiment.BULLISH),
                'opportunity': {
                    'symbol': 'NEWS_TEST',
                    'catalyst_type': 'CONTRACT',
                    'gap_percentage': 0.06,
                    'volume_ratio': 3.0,     # Lower volume requirement
                    'current_price': 7.80
                },
                'expected_strategy': StrategyType.NEWS_MOMENTUM
            },
            {
                'name': 'Opening Range Breakout',
                'context': self.create_market_context(MarketPhase.OPENING, MarketSentiment.NEUTRAL),
                'opportunity': {
                    'symbol': 'ORB_TEST',
                    'catalyst_type': 'OTHER',
                    'gap_percentage': 0.04,  # Small gap perfect for ORB
                    'volume_ratio': 2.5,
                    'current_price': 6.30
                },
                'expected_strategy': StrategyType.OPENING_RANGE_BREAKOUT
            },
            {
                'name': 'Daily Plays (Neutral)',
                'context': self.create_market_context(MarketPhase.MID_MORNING, MarketSentiment.NEUTRAL),
                'opportunity': {
                    'symbol': 'DAILY_TEST',
                    'catalyst_type': 'OTHER',
                    'gap_percentage': 0.03,  # Small gap
                    'volume_ratio': 2.0,
                    'current_price': 8.15
                },
                'expected_strategy': StrategyType.DAILY_PLAYS
            }
        ]
        
        results = []
        for case in test_cases:
            self.sgp.market_context = case['context']
            
            strategy, confidence = self.sgp._select_optimal_strategy_with_context(case['opportunity'])
            
            success = strategy == case['expected_strategy']
            results.append(success)
            
            status = "✅" if success else "❌"
            print(f"{status} {case['name']}:")
            print(f"   Expected: {case['expected_strategy'].value}")
            print(f"   Got: {strategy.value}")
            print(f"   Confidence: {confidence:.2f}")
            print()
        
        success_rate = sum(results) / len(results) * 100
        print(f"📈 Strategy Selection Success Rate: {success_rate:.1f}%")
        
        return success_rate >= 80  # Expect 80%+ success
    
    def test_context_sensitivity_improvement(self):
        """Test that context now has more impact on decisions"""
        print("\n🧠 Testing Context Sensitivity Improvements")
        print("-" * 40)
        
        base_opportunity = {
            'symbol': 'CONTEXT_TEST',
            'catalyst_type': 'OTHER',
            'gap_percentage': 0.06,
            'volume_ratio': 2.8,
            'current_price': 5.50
        }
        
        # Test different contexts with same opportunity
        contexts = [
            ('High VIX Bearish', MarketPhase.OPENING, MarketSentiment.VERY_BEARISH, 35.0, -0.03),
            ('Low VIX Bullish', MarketPhase.OPENING, MarketSentiment.VERY_BULLISH, 12.0, 0.02),
            ('Normal Neutral', MarketPhase.OPENING, MarketSentiment.NEUTRAL, 20.0, 0.00),
            ('Panic Conditions', MarketPhase.POWER_HOUR, MarketSentiment.PANIC, 50.0, -0.06)
        ]
        
        results = []
        for name, phase, sentiment, vix, spy_change in contexts:
            context = self.create_market_context(phase, sentiment, vix, spy_change)
            self.sgp.market_context = context
            
            strategy, confidence = self.sgp._select_optimal_strategy_with_context(base_opportunity)
            results.append((name, strategy, confidence))
            
            print(f"📊 {name}:")
            print(f"   Strategy: {strategy.value}")
            print(f"   Confidence: {confidence:.2f}")
        
        # Analyze context sensitivity
        unique_strategies = len(set(result[1] for result in results))
        confidence_range = max(r[2] for r in results) - min(r[2] for r in results)
        
        print(f"\n🎯 Context Sensitivity Analysis:")
        print(f"   Unique strategies across contexts: {unique_strategies}/{len(contexts)}")
        print(f"   Confidence range: {confidence_range:.3f}")
        
        # Should have good diversity now
        improvement = unique_strategies >= 3 and confidence_range >= 0.15
        status = "✅ IMPROVED" if improvement else "❌ NEEDS WORK"
        print(f"   {status}")
        
        return improvement
    
    def test_market_conditions_adaptation(self):
        """Test adaptation to different market conditions"""
        print("\n📊 Testing Market Conditions Adaptation")
        print("-" * 40)
        
        # Test bearish market with smallcap reversals
        bearish_context = self.create_market_context(
            MarketPhase.POWER_HOUR, MarketSentiment.VERY_BEARISH, 35.0, -0.04
        )
        self.sgp.market_context = bearish_context
        
        reversal_opportunity = {
            'symbol': 'REVERSAL_TEST',
            'catalyst_type': 'OVERSOLD',
            'gap_percentage': -0.12,  # -12% gap down
            'volume_ratio': 3.5,
            'current_price': 3.80
        }
        
        strategy, confidence = self.sgp._select_optimal_strategy_with_context(reversal_opportunity)
        
        print(f"🔻 Bearish Market Reversal Test:")
        print(f"   Context: VIX 35, SPY -4%, Very Bearish")
        print(f"   Opportunity: -12% gap, 3.5x volume")
        print(f"   Strategy: {strategy.value}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Expected: High confidence reversal play")
        
        reversal_success = (
            strategy == StrategyType.REVERSAL_PLAY and 
            confidence > 0.80
        )
        
        # Test bullish market with momentum
        bullish_context = self.create_market_context(
            MarketPhase.OPENING, MarketSentiment.VERY_BULLISH, 12.0, 0.03
        )
        self.sgp.market_context = bullish_context
        
        momentum_opportunity = {
            'symbol': 'MOMENTUM_TEST',
            'catalyst_type': 'M&A',
            'gap_percentage': 0.18,  # 18% gap up
            'volume_ratio': 8.0,
            'current_price': 7.20
        }
        
        strategy2, confidence2 = self.sgp._select_optimal_strategy_with_context(momentum_opportunity)
        
        print(f"\n📈 Bullish Market Momentum Test:")
        print(f"   Context: VIX 12, SPY +3%, Very Bullish")
        print(f"   Opportunity: +18% gap, M&A catalyst, 8x volume")
        print(f"   Strategy: {strategy2.value}")
        print(f"   Confidence: {confidence2:.2f}")
        print(f"   Expected: High confidence momentum play")
        
        momentum_success = (
            strategy2 in [StrategyType.NEWS_MOMENTUM, StrategyType.GAP_AND_GO] and
            confidence2 > 0.85
        )
        
        overall_success = reversal_success and momentum_success
        status = "✅ SUCCESS" if overall_success else "❌ NEEDS WORK"
        print(f"\n🎯 Market Adaptation: {status}")
        
        return overall_success
    
    def run_all_tests(self):
        """Run all improvement tests"""
        print("Running comprehensive Smart Game Plan improvement tests...")
        
        # Run tests
        self.test_smallcap_context_multipliers()
        strategy_success = self.test_improved_strategy_selection()
        context_success = self.test_context_sensitivity_improvement()
        market_success = self.test_market_conditions_adaptation()
        
        # Summary
        print("\n" + "="*50)
        print("📋 IMPROVEMENT TEST SUMMARY")
        print("="*50)
        
        tests_passed = sum([strategy_success, context_success, market_success])
        total_tests = 3
        
        print(f"Strategy Selection Improvements: {'✅' if strategy_success else '❌'}")
        print(f"Context Sensitivity Improvements: {'✅' if context_success else '❌'}")
        print(f"Market Adaptation Improvements: {'✅' if market_success else '❌'}")
        
        print(f"\n🎯 Overall Success Rate: {tests_passed}/{total_tests} ({tests_passed/total_tests*100:.1f}%)")
        
        if tests_passed == total_tests:
            print("🎉 ALL IMPROVEMENTS SUCCESSFUL!")
            print("✅ Smallcap-specific context awareness implemented")
            print("✅ Previously unused strategies now accessible")
            print("✅ Dynamic confidence adjustment working")
            print("✅ Market conditions properly influence decisions")
        elif tests_passed >= 2:
            print("⚠️ MOSTLY SUCCESSFUL - Minor adjustments needed")
        else:
            print("🚨 IMPROVEMENTS NEED WORK - Review implementation")
        
        return tests_passed / total_tests


if __name__ == "__main__":
    tester = TestSGPImprovements()
    success_rate = tester.run_all_tests()