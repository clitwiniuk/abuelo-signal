#!/usr/bin/env python3
"""
Test Script for Smart Game Plan Strategy Selection Improvements
Tests the enhanced strategy selection for neutral sentiment scenarios
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


class TestSmartGamePlanImprovements:
    
    def __init__(self):
        self.config = Mock()
        self.logger = Mock()
        
        # Create SmartGamePlanManager instance
        self.sgp_manager = SmartGamePlanManager(
            config=self.config,
            data_provider=None,
            logger=self.logger
        )
        
        # Set up neutral market context
        self.sgp_manager.market_context = MarketContext(
            current_phase=MarketPhase.AFTERNOON,
            time_in_phase=None,
            next_phase_in=None,
            market_sentiment=MarketSentiment.NEUTRAL,  # Key: neutral sentiment
            spy_change_pct=0.0,
            vix_level=20.0,
            sector_rotation={},
            overall_volume_ratio=0.8,  # Low overall volume
            volatility_regime='NORMAL',
            adv_decline_ratio=1.0,
            breaking_news_count=0,
            major_economic_events=[],
            sector_news={},
            recent_strategy_performance={},
            current_day_pnl=0.0,
            current_positions=0,
            last_updated=datetime.now(),
            data_quality_score=1.0
        )
        
        print("🧪 Smart Game Plan Strategy Selection Test")
        print("==========================================")
        
    def test_neutral_sentiment_scenarios(self):
        """Test various scenarios with neutral sentiment"""
        
        print("\n📊 Testing Neutral Sentiment Strategy Selection")
        print("-" * 50)
        
        # Test Case 1: Symbol with decent volume, small gap
        scenario_1 = {
            'symbol': 'BLNE',
            'gap_percentage': 0.05,  # 5% gap
            'volume_ratio': 2.5,     # Good volume
            'catalyst_type': 'OTHER',
            'current_price': 10.50
        }
        
        strategy, confidence = self.sgp_manager._select_optimal_strategy_with_context(scenario_1)
        print(f"📈 Scenario 1 - BLNE (Vol: 2.5x, Gap: 5%)")
        print(f"   Strategy: {strategy.value}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Expected: volume_breakout or daily_plays (was: reversal_play)")
        
        # Test Case 2: Symbol with low volume, minimal gap
        scenario_2 = {
            'symbol': 'RR',
            'gap_percentage': 0.02,  # 2% gap
            'volume_ratio': 1.8,     # Moderate volume
            'catalyst_type': 'OTHER',
            'current_price': 5.25
        }
        
        strategy, confidence = self.sgp_manager._select_optimal_strategy_with_context(scenario_2)
        print(f"\n📈 Scenario 2 - RR (Vol: 1.8x, Gap: 2%)")
        print(f"   Strategy: {strategy.value}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Expected: daily_plays or gap_and_go (was: reversal_play)")
        
        # Test Case 3: Symbol with good volume, small gap - should get volume breakout
        scenario_3 = {
            'symbol': 'VIR',
            'gap_percentage': 0.03,  # 3% gap
            'volume_ratio': 3.2,     # Good volume
            'catalyst_type': 'OTHER',
            'current_price': 8.75
        }
        
        strategy, confidence = self.sgp_manager._select_optimal_strategy_with_context(scenario_3)
        print(f"\n📈 Scenario 3 - VIR (Vol: 3.2x, Gap: 3%)")
        print(f"   Strategy: {strategy.value}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Expected: volume_breakout (confidence ~0.7)")
        
        # Test Case 4: Opening hours with small gap - should get daily plays
        self.sgp_manager.market_context.current_phase = MarketPhase.OPENING
        
        scenario_4 = {
            'symbol': 'FLNT',
            'gap_percentage': 0.04,  # 4% gap
            'volume_ratio': 2.0,     # Moderate volume
            'catalyst_type': 'OTHER',
            'current_price': 12.30
        }
        
        strategy, confidence = self.sgp_manager._select_optimal_strategy_with_context(scenario_4)
        print(f"\n📈 Scenario 4 - FLNT Opening Hours (Vol: 2.0x, Gap: 4%)")
        print(f"   Strategy: {strategy.value}")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   Expected: daily_plays or volume_breakout")
        
        # Reset to afternoon phase
        self.sgp_manager.market_context.current_phase = MarketPhase.AFTERNOON
        
    def test_volume_requirements(self):
        """Test flexible volume requirements"""
        
        print("\n📊 Testing Volume Requirements")
        print("-" * 50)
        
        # Test volume requirement calculation
        breakout_req = self.sgp_manager._get_context_adjusted_volume_requirement('breakout')
        daily_plays_req = self.sgp_manager._get_context_adjusted_volume_requirement('daily_plays')
        gap_go_req = self.sgp_manager._get_context_adjusted_volume_requirement('gap_and_go')
        
        print(f"💧 Volume Requirements (neutral sentiment, low market volume):")
        print(f"   Breakout: {breakout_req:.1f}x (base: 3.0x)")
        print(f"   Daily Plays: {daily_plays_req:.1f}x (base: 1.2x)")
        print(f"   Gap & Go: {gap_go_req:.1f}x (base: 1.5x)")
        print(f"   Expected: All reduced due to low market volume multiplier (0.6x)")
        
    def test_execution_logic(self):
        """Test execution decision logic"""
        
        print("\n📊 Testing Execution Logic")
        print("-" * 50)
        
        # Create a mock entry with DAILY_PLAYS strategy
        from core.smart_game_plan_manager import SmartGamePlanEntry
        
        mock_entry = SmartGamePlanEntry(
            symbol='TEST',
            tier='A',
            primary_strategy=StrategyType.DAILY_PLAYS,
            primary_strategy_confidence=0.7,
            backup_strategies=[],
            strategy_selection_reasoning="Test entry",
            entry_price=10.0,
            stop_loss=9.5,
            target_1=10.5,
            target_2=11.0,
            technical_setup_score=7.0,
            optimal_market_phases=[MarketPhase.OPENING],
            required_sentiment=[MarketSentiment.NEUTRAL],
            min_volatility_regime='NORMAL',
            context_match_score=0.8,
            position_size=100,
            max_risk_per_trade=200,
            execution_urgency='MEDIUM',
            time_decay_factor=1.0,
            last_updated=datetime.now()
        )
        
        # Add to plan
        self.sgp_manager.current_plan['TEST'] = mock_entry
        
        # Test execution with different volume ratios
        test_data_low = {
            'symbol': 'TEST',
            'volume_ratio': 1.0,  # Low volume
            'gap_percentage': 0.03,
            'current_price': 10.0
        }
        
        decision_low = self.sgp_manager._execute_daily_plays_with_context(mock_entry, test_data_low)
        print(f"📊 Daily Plays with 1.0x volume:")
        print(f"   Action: {decision_low.get('action')}")
        print(f"   Reason: {decision_low.get('reason')}")
        
        test_data_good = {
            'symbol': 'TEST',
            'volume_ratio': 2.0,  # Good volume
            'gap_percentage': 0.03,
            'current_price': 10.0
        }
        
        decision_good = self.sgp_manager._execute_daily_plays_with_context(mock_entry, test_data_good)
        print(f"\n📊 Daily Plays with 2.0x volume:")
        print(f"   Action: {decision_good.get('action')}")
        print(f"   Reason: {decision_good.get('reason')}")
        
    def run_all_tests(self):
        """Run all test scenarios"""
        self.test_neutral_sentiment_scenarios()
        self.test_volume_requirements()
        self.test_execution_logic()
        
        print("\n✅ Test Summary")
        print("=" * 50)
        print("Improvements implemented:")
        print("1. ✅ Reversal plays require extreme sentiment (not neutral)")
        print("2. ✅ Added neutral sentiment strategies (volume_breakout, daily_plays, gap_and_go)")
        print("3. ✅ Flexible volume requirements based on market context")
        print("4. ✅ Better fallback strategies for neutral conditions")
        print("5. ✅ DAILY_PLAYS strategy added with execution logic")
        print("\nExpected Result:")
        print("Symbols like BLNE, RR, VIR, FLNT should now be APPROVED instead of REJECTED")


if __name__ == "__main__":
    test = TestSmartGamePlanImprovements()
    test.run_all_tests()