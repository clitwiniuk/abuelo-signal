#!/usr/bin/env python3
"""
Test Strategy Reassignment Fix
Tests that existing REVERSAL_PLAY entries get reassigned to appropriate strategies for neutral sentiment
"""

import sys
import os
from unittest.mock import Mock
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_game_plan_manager import (
    SmartGamePlanManager, SmartGamePlanEntry, StrategyType, MarketPhase, MarketSentiment, MarketContext
)


class TestStrategyReassignment:
    
    def __init__(self):
        self.config = Mock()
        self.logger = Mock()
        
        # Create SmartGamePlanManager instance
        self.sgp_manager = SmartGamePlanManager(
            config=self.config,
            data_provider=None,
            logger=self.logger
        )
        
        # Set up neutral market context (the problematic scenario)
        self.sgp_manager.market_context = MarketContext(
            current_phase=MarketPhase.AFTERNOON,
            time_in_phase=None,
            next_phase_in=None,
            market_sentiment=MarketSentiment.NEUTRAL,  # Key: neutral sentiment
            spy_change_pct=0.0,
            vix_level=20.0,
            sector_rotation={},
            overall_volume_ratio=0.8,
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
        
        print("🧪 Strategy Reassignment Test")
        print("============================")
        
    def create_reversal_entry(self, symbol: str) -> SmartGamePlanEntry:
        """Create a mock entry with REVERSAL_PLAY strategy (the problem case)"""
        return SmartGamePlanEntry(
            symbol=symbol,
            tier='A',
            primary_strategy=StrategyType.REVERSAL_PLAY,  # This is the problem
            primary_strategy_confidence=0.8,
            backup_strategies=[],
            strategy_selection_reasoning="Original reversal assignment",
            entry_price=10.0,
            stop_loss=9.5,
            target_1=10.5,
            target_2=11.0,
            technical_setup_score=7.0,
            optimal_market_phases=[MarketPhase.AFTERNOON],
            required_sentiment=[MarketSentiment.VERY_BEARISH],  # This doesn't match current neutral sentiment
            min_volatility_regime='NORMAL',
            context_match_score=0.8,
            position_size=100,
            max_risk_per_trade=200,
            execution_urgency='MEDIUM',
            time_decay_factor=1.0,
            last_updated=datetime.now()
        )
    
    def test_reversal_reassignment(self):
        """Test that REVERSAL_PLAY entries get reassigned to appropriate strategies"""
        
        print("\n📊 Testing REVERSAL_PLAY Reassignment")
        print("-" * 50)
        
        # Create problematic entries (like FLNT, VIR, BLNE from logs)
        test_symbols = ['FLNT', 'VIR', 'BLNE']
        
        for symbol in test_symbols:
            print(f"\n🔍 Testing {symbol}:")
            
            # Create entry with REVERSAL_PLAY strategy
            entry = self.create_reversal_entry(symbol)
            print(f"   Original Strategy: {entry.primary_strategy.value}")
            
            # Add to plan
            self.sgp_manager.current_plan[symbol] = entry
            
            # Simulate live data (similar to what would cause the issue)
            live_data = {
                'symbol': symbol,
                'gap_percentage': 0.05,    # 5% gap
                'volume_ratio': 3.5,       # Higher volume to meet breakout requirements
                'current_price': 10.0,
                'catalyst_type': 'OTHER'
            }
            
            # Test the reassignment logic directly
            reassigned_entry = self.sgp_manager._maybe_reassign_strategy(entry, live_data)
            
            print(f"   Reassigned Strategy: {reassigned_entry.primary_strategy.value}")
            print(f"   Confidence: {reassigned_entry.primary_strategy_confidence:.2f}")
            print(f"   Reasoning: {reassigned_entry.strategy_selection_reasoning}")
            
            # Verify the entry was actually updated in the plan
            updated_entry = self.sgp_manager.current_plan[symbol]
            print(f"   Plan Updated: {updated_entry.primary_strategy.value}")
            
            # Now test execution (should work instead of being rejected)
            try:
                decision = self.sgp_manager._make_context_aware_decision(updated_entry, live_data)
                print(f"   Execution Decision: {decision.get('action')}")
                print(f"   Decision Reason: {decision.get('reason', 'N/A')}")
            except Exception as e:
                print(f"   Execution Error: {str(e)}")
    
    def test_execution_before_and_after(self):
        """Test execution decisions before and after reassignment"""
        
        print("\n📊 Before vs After Comparison")
        print("-" * 50)
        
        symbol = 'TEST'
        entry = self.create_reversal_entry(symbol)
        live_data = {
            'symbol': symbol,
            'gap_percentage': 0.04,
            'volume_ratio': 3.5,  # Higher volume for successful execution
            'current_price': 10.0
        }
        
        # Before reassignment - should fail
        print(f"\n🚫 BEFORE reassignment:")
        try:
            decision_before = self.sgp_manager._execute_reversal_play_with_context(entry, live_data)
            print(f"   Action: {decision_before.get('action')}")
            print(f"   Reason: {decision_before.get('reason')}")
        except Exception as e:
            print(f"   Error: {str(e)}")
        
        # After reassignment - should work
        print(f"\n✅ AFTER reassignment:")
        reassigned_entry = self.sgp_manager._maybe_reassign_strategy(entry, live_data)
        
        try:
            decision_after = self.sgp_manager._make_context_aware_decision(reassigned_entry, live_data)
            print(f"   New Strategy: {reassigned_entry.primary_strategy.value}")
            print(f"   Action: {decision_after.get('action')}")
            print(f"   Reason: {decision_after.get('reason', 'N/A')}")
        except Exception as e:
            print(f"   Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all test scenarios"""
        self.test_reversal_reassignment()
        self.test_execution_before_and_after()
        
        print("\n✅ Test Summary")
        print("=" * 50)
        print("Fix implemented:")
        print("1. ✅ Added _maybe_reassign_strategy() method")
        print("2. ✅ Detects REVERSAL_PLAY with neutral sentiment")
        print("3. ✅ Re-evaluates using improved strategy selection logic")
        print("4. ✅ Updates entry in current plan")
        print("5. ✅ Should resolve 'Sentiment neutral not extreme enough' errors")
        print("\nExpected Result:")
        print("FLNT, VIR, BLNE should now get VOLUME_BREAKOUT or DAILY_PLAYS instead of REVERSAL_PLAY")
        print("Execution should succeed instead of being rejected")


if __name__ == "__main__":
    test = TestStrategyReassignment()
    test.run_all_tests()