#!/usr/bin/env python3
"""
Smart Game Plan Analysis & Improvement Identification
=====================================================

Deep analysis of the Smart Game Plan Manager to identify:
1. Performance bottlenecks
2. Decision accuracy issues  
3. Context utilization gaps
4. Strategy selection problems
5. Specific improvement opportunities

Author: Claude Code
Date: 2025-08-28
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_game_plan_manager import (
    SmartGamePlanManager, SmartGamePlanEntry, StrategyType, 
    MarketPhase, MarketSentiment, MarketContext
)

class SmartGamePlanAnalyzer:
    
    def __init__(self):
        print("🔍 Smart Game Plan Deep Analysis")
        print("=" * 50)
        
        # Create manager for analysis
        self.config = Mock()
        self.logger = Mock()
        self.sgp = SmartGamePlanManager(self.config, None, self.logger)
        
        # Test scenarios for comprehensive analysis
        self.test_scenarios = self._create_test_scenarios()
        
        # Analysis results
        self.analysis_results = {
            'strategy_selection': {},
            'context_utilization': {},
            'performance_issues': [],
            'improvement_opportunities': []
        }
        
    def _create_test_scenarios(self) -> List[Dict[str, Any]]:
        """Create comprehensive test scenarios for analysis"""
        return [
            # High-quality FDA play
            {
                'name': 'FDA_HIGH_QUALITY',
                'market_context': self._create_market_context(
                    phase=MarketPhase.OPENING,
                    sentiment=MarketSentiment.BULLISH,
                    volatility='NORMAL'
                ),
                'opportunity': {
                    'symbol': 'BIOTEST1',
                    'catalyst_type': 'FDA',
                    'gap_percentage': 0.15,
                    'volume_ratio': 5.2,
                    'current_price': 4.50
                },
                'expected_strategy': StrategyType.FDA_CATALYST,
                'expected_confidence_range': (0.80, 0.95)
            },
            
            # Neutral sentiment volume play
            {
                'name': 'NEUTRAL_VOLUME_PLAY',
                'market_context': self._create_market_context(
                    phase=MarketPhase.AFTERNOON,
                    sentiment=MarketSentiment.NEUTRAL,
                    volatility='NORMAL'
                ),
                'opportunity': {
                    'symbol': 'VOLTEST1',
                    'catalyst_type': 'OTHER',
                    'gap_percentage': 0.05,
                    'volume_ratio': 3.8,
                    'current_price': 6.25
                },
                'expected_strategy': StrategyType.VOLUME_BREAKOUT,
                'expected_confidence_range': (0.60, 0.75)
            },
            
            # Gap fade scenario
            {
                'name': 'GAP_FADE_OPPORTUNITY',
                'market_context': self._create_market_context(
                    phase=MarketPhase.MID_MORNING,
                    sentiment=MarketSentiment.BEARISH,
                    volatility='HIGH'
                ),
                'opportunity': {
                    'symbol': 'FADETEST1',
                    'catalyst_type': 'OTHER',
                    'gap_percentage': 0.22,  # 22% gap up
                    'volume_ratio': 4.1,
                    'current_price': 8.90
                },
                'expected_strategy': StrategyType.FADE_GAP,
                'expected_confidence_range': (0.60, 0.80)
            },
            
            # Reversal play - should only work with extreme sentiment
            {
                'name': 'REVERSAL_EXTREME_SENTIMENT',
                'market_context': self._create_market_context(
                    phase=MarketPhase.POWER_HOUR,
                    sentiment=MarketSentiment.VERY_BEARISH,
                    volatility='HIGH'
                ),
                'opportunity': {
                    'symbol': 'REVTEST1',
                    'catalyst_type': 'OVERSOLD',
                    'gap_percentage': -0.12,  # -12% gap down
                    'volume_ratio': 3.5,
                    'current_price': 3.20
                },
                'expected_strategy': StrategyType.REVERSAL_PLAY,
                'expected_confidence_range': (0.70, 0.90)
            },
            
            # Reversal play - should NOT work with neutral sentiment
            {
                'name': 'REVERSAL_NEUTRAL_SENTIMENT',
                'market_context': self._create_market_context(
                    phase=MarketPhase.AFTERNOON,
                    sentiment=MarketSentiment.NEUTRAL,
                    volatility='NORMAL'
                ),
                'opportunity': {
                    'symbol': 'REVTEST2',
                    'catalyst_type': 'OVERSOLD',
                    'gap_percentage': -0.10,  # -10% gap down
                    'volume_ratio': 2.8,
                    'current_price': 4.15
                },
                'expected_strategy': StrategyType.VOLUME_BREAKOUT,  # Should fallback
                'expected_confidence_range': (0.50, 0.70)
            },
            
            # Edge case: Very low volume
            {
                'name': 'LOW_VOLUME_EDGE_CASE',
                'market_context': self._create_market_context(
                    phase=MarketPhase.LUNCH,
                    sentiment=MarketSentiment.NEUTRAL,
                    volatility='LOW'
                ),
                'opportunity': {
                    'symbol': 'LOWVOL1',
                    'catalyst_type': 'CONTRACT',
                    'gap_percentage': 0.08,
                    'volume_ratio': 1.2,  # Very low volume
                    'current_price': 5.50
                },
                'expected_strategy': StrategyType.VOLUME_BREAKOUT,  # Fallback
                'expected_confidence_range': (0.40, 0.60)
            }
        ]
    
    def _create_market_context(self, phase: MarketPhase, sentiment: MarketSentiment, 
                              volatility: str) -> MarketContext:
        """Create market context for testing"""
        return MarketContext(
            current_phase=phase,
            time_in_phase=timedelta(minutes=30),
            next_phase_in=timedelta(minutes=90),
            market_sentiment=sentiment,
            spy_change_pct=0.01 if sentiment == MarketSentiment.BULLISH else -0.01,
            vix_level=18.0 if volatility == 'NORMAL' else 28.0,
            sector_rotation={},
            overall_volume_ratio=0.9,
            volatility_regime=volatility,
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
    
    def analyze_strategy_selection_accuracy(self):
        """Analyze strategy selection logic accuracy"""
        print("\n📊 Strategy Selection Analysis")
        print("-" * 40)
        
        correct_predictions = 0
        total_tests = len(self.test_scenarios)
        
        for scenario in self.test_scenarios:
            # Set market context
            self.sgp.market_context = scenario['market_context']
            
            # Test strategy selection
            selected_strategy, confidence = self.sgp._select_optimal_strategy_with_context(
                scenario['opportunity']
            )
            
            expected_strategy = scenario['expected_strategy']
            expected_range = scenario['expected_confidence_range']
            
            # Check accuracy
            strategy_correct = selected_strategy == expected_strategy
            confidence_in_range = expected_range[0] <= confidence <= expected_range[1]
            
            if strategy_correct:
                correct_predictions += 1
            
            # Log results
            status = "✅" if strategy_correct else "❌"
            conf_status = "✅" if confidence_in_range else "⚠️"
            
            print(f"{status} {scenario['name']}:")
            print(f"   Expected: {expected_strategy.value} | Got: {selected_strategy.value}")
            print(f"   {conf_status} Confidence: {confidence:.2f} (expected: {expected_range[0]:.2f}-{expected_range[1]:.2f})")
            
            # Store detailed results
            self.analysis_results['strategy_selection'][scenario['name']] = {
                'expected_strategy': expected_strategy.value,
                'actual_strategy': selected_strategy.value,
                'strategy_correct': strategy_correct,
                'expected_confidence_range': expected_range,
                'actual_confidence': confidence,
                'confidence_in_range': confidence_in_range
            }
        
        accuracy = (correct_predictions / total_tests) * 100
        print(f"\n📈 Strategy Selection Accuracy: {accuracy:.1f}% ({correct_predictions}/{total_tests})")
        
        return accuracy
    
    def analyze_context_utilization(self):
        """Analyze how well context is being used"""
        print("\n🧠 Context Utilization Analysis")
        print("-" * 40)
        
        # Test context sensitivity
        base_opportunity = {
            'symbol': 'CONTEXT_TEST',
            'catalyst_type': 'OTHER',
            'gap_percentage': 0.08,
            'volume_ratio': 2.5,
            'current_price': 5.00
        }
        
        # Test different market contexts
        contexts = [
            ('Bullish Morning', MarketPhase.OPENING, MarketSentiment.BULLISH),
            ('Bearish Afternoon', MarketPhase.AFTERNOON, MarketSentiment.BEARISH),
            ('Neutral Lunch', MarketPhase.LUNCH, MarketSentiment.NEUTRAL),
            ('Very Bearish Power Hour', MarketPhase.POWER_HOUR, MarketSentiment.VERY_BEARISH)
        ]
        
        results = {}
        for name, phase, sentiment in contexts:
            context = self._create_market_context(phase, sentiment, 'NORMAL')
            self.sgp.market_context = context
            
            strategy, confidence = self.sgp._select_optimal_strategy_with_context(base_opportunity)
            results[name] = (strategy, confidence)
            
            print(f"📊 {name}: {strategy.value} (conf: {confidence:.2f})")
        
        # Analyze context sensitivity
        unique_strategies = len(set(result[0] for result in results.values()))
        confidence_variance = max(r[1] for r in results.values()) - min(r[1] for r in results.values())
        
        print(f"\n🎯 Context Sensitivity:")
        print(f"   Unique strategies across contexts: {unique_strategies}/{len(contexts)}")
        print(f"   Confidence variance: {confidence_variance:.2f}")
        
        if unique_strategies >= 3:
            print("   ✅ Good context adaptation")
        else:
            print("   ⚠️ Limited context adaptation")
            self.analysis_results['improvement_opportunities'].append(
                "Improve context sensitivity - strategy selection too static"
            )
        
        return unique_strategies, confidence_variance
    
    def analyze_performance_bottlenecks(self):
        """Identify performance bottlenecks"""
        print("\n⚡ Performance Analysis")
        print("-" * 40)
        
        import time
        
        # Test decision speed
        test_data = {
            'symbol': 'SPEED_TEST',
            'gap_percentage': 0.10,
            'volume_ratio': 3.0,
            'current_price': 4.00,
            'catalyst_type': 'OTHER'
        }
        
        # Strategy selection speed
        start_time = time.time()
        for _ in range(100):
            self.sgp._select_optimal_strategy_with_context(test_data)
        strategy_time = (time.time() - start_time) * 1000  # ms
        
        # Context creation speed (if needed)
        start_time = time.time()
        for _ in range(100):
            self._create_market_context(MarketPhase.OPENING, MarketSentiment.NEUTRAL, 'NORMAL')
        context_time = (time.time() - start_time) * 1000  # ms
        
        print(f"⏱️ Strategy Selection: {strategy_time:.2f}ms per 100 calls ({strategy_time/100:.3f}ms each)")
        print(f"⏱️ Context Creation: {context_time:.2f}ms per 100 calls ({context_time/100:.3f}ms each)")
        
        # Performance thresholds
        if strategy_time > 50:  # >0.5ms per call
            self.analysis_results['performance_issues'].append(
                f"Strategy selection slow: {strategy_time/100:.3f}ms per call"
            )
        
        return strategy_time, context_time
    
    def analyze_edge_cases(self):
        """Analyze edge case handling"""
        print("\n🔍 Edge Case Analysis")
        print("-" * 40)
        
        edge_cases = [
            # Missing data
            {'symbol': 'MISSING1', 'gap_percentage': 0.0, 'volume_ratio': 0.0},
            # Extreme values
            {'symbol': 'EXTREME1', 'gap_percentage': 2.5, 'volume_ratio': 50.0},
            # Negative values
            {'symbol': 'NEGATIVE1', 'gap_percentage': -0.8, 'volume_ratio': -1.0}
        ]
        
        for case in edge_cases:
            try:
                strategy, confidence = self.sgp._select_optimal_strategy_with_context(case)
                print(f"✅ {case['symbol']}: {strategy.value} (conf: {confidence:.2f})")
            except Exception as e:
                print(f"❌ {case['symbol']}: ERROR - {str(e)}")
                self.analysis_results['performance_issues'].append(
                    f"Edge case error for {case['symbol']}: {str(e)}"
                )
    
    def identify_specific_improvements(self):
        """Identify specific areas for improvement"""
        print("\n💡 Specific Improvement Opportunities")
        print("-" * 50)
        
        improvements = []
        
        # Analyze strategy selection accuracy
        strategy_accuracy = sum(
            1 for result in self.analysis_results['strategy_selection'].values()
            if result['strategy_correct']
        ) / len(self.analysis_results['strategy_selection']) * 100
        
        if strategy_accuracy < 90:
            improvements.append({
                'priority': 'HIGH',
                'area': 'Strategy Selection Logic',
                'issue': f'Accuracy only {strategy_accuracy:.1f}%',
                'recommendation': 'Review and refine strategy selection criteria'
            })
        
        # Check for missing strategies
        used_strategies = set()
        for result in self.analysis_results['strategy_selection'].values():
            used_strategies.add(result['actual_strategy'])
        
        all_strategies = set(strategy.value for strategy in StrategyType)
        unused_strategies = all_strategies - used_strategies
        
        if unused_strategies:
            improvements.append({
                'priority': 'MEDIUM',
                'area': 'Strategy Coverage',
                'issue': f'Strategies never selected: {unused_strategies}',
                'recommendation': 'Review if unused strategies are needed or criteria too restrictive'
            })
        
        # Performance issues
        for issue in self.analysis_results['performance_issues']:
            improvements.append({
                'priority': 'MEDIUM',
                'area': 'Performance',
                'issue': issue,
                'recommendation': 'Optimize slow operations'
            })
        
        # Context utilization
        improvements.append({
            'priority': 'HIGH',
            'area': 'Context Enhancement',
            'issue': 'Market context could be used more effectively',
            'recommendation': 'Add real-time market data integration and dynamic thresholds'
        })
        
        # Display improvements
        for i, improvement in enumerate(improvements, 1):
            priority_icon = "🚨" if improvement['priority'] == 'HIGH' else "⚠️"
            print(f"{priority_icon} {i}. {improvement['area']} ({improvement['priority']} Priority)")
            print(f"   Issue: {improvement['issue']}")
            print(f"   Recommendation: {improvement['recommendation']}")
            print()
        
        return improvements
    
    def generate_improvement_plan(self, improvements: List[Dict]):
        """Generate actionable improvement plan"""
        print("🎯 Recommended Improvement Plan")
        print("=" * 50)
        
        high_priority = [imp for imp in improvements if imp['priority'] == 'HIGH']
        medium_priority = [imp for imp in improvements if imp['priority'] == 'MEDIUM']
        
        print("Phase 1 - High Priority (Immediate):")
        for i, imp in enumerate(high_priority, 1):
            print(f"   {i}. {imp['area']}: {imp['recommendation']}")
        
        print("\nPhase 2 - Medium Priority (Next):")
        for i, imp in enumerate(medium_priority, 1):
            print(f"   {i}. {imp['area']}: {imp['recommendation']}")
        
        print("\n🔧 Specific Implementation Suggestions:")
        print("1. Add real-time SPY/VIX data feed for dynamic sentiment")
        print("2. Implement strategy performance tracking and auto-adjustment")
        print("3. Add pre-market and after-hours context handling")
        print("4. Create strategy backtesting framework")
        print("5. Add position size optimization based on volatility")
        
    def run_comprehensive_analysis(self):
        """Run complete Smart Game Plan analysis"""
        print("Starting comprehensive Smart Game Plan analysis...")
        
        # Run all analyses
        accuracy = self.analyze_strategy_selection_accuracy()
        context_sensitivity = self.analyze_context_utilization()
        performance = self.analyze_performance_bottlenecks()
        self.analyze_edge_cases()
        improvements = self.identify_specific_improvements()
        self.generate_improvement_plan(improvements)
        
        print("\n" + "="*50)
        print("📋 ANALYSIS SUMMARY")
        print("="*50)
        print(f"Strategy Selection Accuracy: {accuracy:.1f}%")
        print(f"Context Sensitivity Score: {context_sensitivity[0]}/4")
        print(f"Performance: {performance[0]/100:.2f}ms per decision")
        print(f"Identified Issues: {len(self.analysis_results['performance_issues'])}")
        print(f"Improvement Opportunities: {len(improvements)}")
        
        overall_score = (
            (accuracy / 100 * 40) +  # 40% weight on accuracy
            (context_sensitivity[0] / 4 * 30) +  # 30% weight on context sensitivity
            (min(1.0, 1.0 / (performance[0]/100)) * 20) +  # 20% weight on speed
            (max(0, 1.0 - len(self.analysis_results['performance_issues'])/10) * 10)  # 10% weight on issues
        )
        
        print(f"\n🎯 Overall SGP Quality Score: {overall_score:.1f}/100")
        
        if overall_score >= 80:
            print("✅ Smart Game Plan is in good shape - minor optimizations recommended")
        elif overall_score >= 60:
            print("⚠️ Smart Game Plan needs improvements - several issues identified")
        else:
            print("🚨 Smart Game Plan needs significant improvements")
        
        return overall_score


if __name__ == "__main__":
    analyzer = SmartGamePlanAnalyzer()
    analyzer.run_comprehensive_analysis()