#!/usr/bin/env python3
"""
Test Completo - Todas las 10 Estrategias en Contextos Optimales
=================================================================

Simula diferentes fases de mercado y condiciones para verificar que
todas las estrategias funcionan correctamente en sus contextos ideales.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List

# Setup básico
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.smart_game_plan_manager import (
    SmartGamePlanManager, 
    StrategyType, 
    MarketPhase, 
    MarketSentiment,
    SmartGamePlanEntry,
    MarketContext
)

def setup_test_logging():
    """Setup de logging para test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("ComprehensiveTest")

class TestScenario:
    """Escenario de test con contexto específico"""
    def __init__(self, name: str, market_phase: MarketPhase, sentiment: MarketSentiment, 
                 opportunities: List[Dict]):
        self.name = name
        self.market_phase = market_phase
        self.sentiment = sentiment
        self.opportunities = opportunities

def create_test_scenarios() -> List[TestScenario]:
    """Crear escenarios de test para diferentes contextos"""
    
    scenarios = []
    
    # ESCENARIO 1: Opening Hour - Bullish Market (Gap&Go + ORB optimal)
    scenarios.append(TestScenario(
        name="🌅 OPENING BULLISH",
        market_phase=MarketPhase.OPENING,
        sentiment=MarketSentiment.BULLISH,
        opportunities=[
            # Gap and Go - Perfect conditions
            {
                'symbol': 'GAPGO1',
                'gap_percentage': 0.15,  # 15% gap up
                'volume_ratio': 5.5,
                'catalyst_type': 'BREAKTHROUGH',
                'current_price': 25.50,
                'quality_score': 8.2
            },
            # Opening Range Breakout - Small gap, good volume
            {
                'symbol': 'ORB1',
                'gap_percentage': 0.04,  # Small 4% gap
                'volume_ratio': 2.8,
                'catalyst_type': 'BREAKOUT',
                'current_price': 21.40,
                'quality_score': 7.8
            }
        ]
    ))
    
    # ESCENARIO 2: Pre-market - FDA + Gap conditions
    scenarios.append(TestScenario(
        name="🌄 PRE-MARKET FDA",
        market_phase=MarketPhase.PRE_MARKET,
        sentiment=MarketSentiment.NEUTRAL,
        opportunities=[
            # FDA Catalyst - Always high priority
            {
                'symbol': 'FDA1',
                'gap_percentage': 0.18,
                'volume_ratio': 4.1,
                'catalyst_type': 'FDA',
                'current_price': 32.10,
                'quality_score': 9.2
            },
            # Strong Gap for Gap&Go in pre-market
            {
                'symbol': 'PREGAP1',
                'gap_percentage': 0.20,  # 20% gap
                'volume_ratio': 6.0,
                'catalyst_type': 'BREAKTHROUGH',
                'current_price': 18.75,
                'quality_score': 8.5
            }
        ]
    ))
    
    # ESCENARIO 3: Mid-Morning - Fade + Momentum Continuation
    scenarios.append(TestScenario(
        name="🌞 MID-MORNING FADES",
        market_phase=MarketPhase.MID_MORNING,
        sentiment=MarketSentiment.BEARISH,
        opportunities=[
            # Fade Gap - Large gap in bearish market
            {
                'symbol': 'FADE1',
                'gap_percentage': 0.28,  # 28% extreme gap
                'volume_ratio': 4.0,
                'catalyst_type': 'OVERREACTION',
                'current_price': 45.20,
                'quality_score': 7.1
            },
            # Momentum Continuation in mid-morning
            {
                'symbol': 'MOMENTUM1',
                'gap_percentage': 0.08,
                'volume_ratio': 5.2,
                'catalyst_type': 'CONTINUATION',
                'current_price': 19.65,
                'quality_score': 8.0
            }
        ]
    ))
    
    # ESCENARIO 4: Afternoon - News Momentum + Volume Breakouts
    scenarios.append(TestScenario(
        name="🌅 AFTERNOON NEWS",
        market_phase=MarketPhase.AFTERNOON,
        sentiment=MarketSentiment.BULLISH,
        opportunities=[
            # News Momentum - M&A in afternoon (optimal)
            {
                'symbol': 'MA1',
                'gap_percentage': 0.12,
                'volume_ratio': 7.5,
                'catalyst_type': 'M&A',
                'current_price': 28.90,
                'quality_score': 8.9
            },
            # Earnings Surprise
            {
                'symbol': 'EARN1',
                'gap_percentage': 0.16,  # 16% earnings gap
                'volume_ratio': 4.0,
                'catalyst_type': 'EARNINGS',
                'current_price': 33.40,
                'quality_score': 8.7
            },
            # Volume Breakout
            {
                'symbol': 'VOL1',
                'gap_percentage': 0.06,
                'volume_ratio': 15.0,  # Massive volume
                'catalyst_type': 'VOLUME',
                'current_price': 23.80,
                'quality_score': 8.3
            }
        ]
    ))
    
    # ESCENARIO 5: Power Hour - Reversals + End of Day
    scenarios.append(TestScenario(
        name="⚡ POWER HOUR REVERSALS",
        market_phase=MarketPhase.POWER_HOUR,
        sentiment=MarketSentiment.VERY_BEARISH,
        opportunities=[
            # Reversal Play - Perfect conditions (extreme sentiment + power hour)
            {
                'symbol': 'REV1',
                'gap_percentage': -0.22,  # 22% gap DOWN
                'volume_ratio': 5.5,
                'catalyst_type': 'OVERSOLD',
                'current_price': 16.30,
                'quality_score': 7.5
            },
            # End of Day - Institutional flow
            {
                'symbol': 'EOD1',
                'gap_percentage': 0.05,
                'volume_ratio': 3.8,
                'catalyst_type': 'INSTITUTIONAL',
                'current_price': 31.25,
                'quality_score': 7.9
            }
        ]
    ))
    
    return scenarios

async def test_scenario(scenario: TestScenario, logger: logging.Logger) -> Dict:
    """Test individual scenario"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🧪 SCENARIO: {scenario.name}")
    logger.info(f"   📅 Phase: {scenario.market_phase.value}")
    logger.info(f"   💭 Sentiment: {scenario.sentiment.value}")
    logger.info(f"   📊 Opportunities: {len(scenario.opportunities)}")
    logger.info(f"{'='*60}")
    
    # Mock config
    class MockConfig:
        def __init__(self):
            self.client_id = 999
            self.strategy_settings = {'max_daily_plays': 15, 'max_risk_per_trade': 1000}
    
    # Create Game Plan Manager
    gpm = SmartGamePlanManager(
        config=MockConfig(),
        data_provider=None,
        logger=logger
    )
    
    # Manually set market context for this scenario
    gpm.market_context = MarketContext(
        current_phase=scenario.market_phase,
        time_in_phase=timedelta(minutes=30),
        next_phase_in=timedelta(minutes=30),
        market_sentiment=scenario.sentiment,
        spy_change_pct=0.010 if scenario.sentiment == MarketSentiment.BULLISH else -0.015,
        vix_level=15.0 if scenario.sentiment == MarketSentiment.BULLISH else 28.0,
        sector_rotation={'TECH': 0.02},
        overall_volume_ratio=1.2,
        volatility_regime='NORMAL',
        adv_decline_ratio=1.1,
        breaking_news_count=1,
        major_economic_events=[],
        sector_news={},
        recent_strategy_performance={},
        current_day_pnl=0.0,
        current_positions=0,
        last_updated=datetime.now(),
        data_quality_score=1.0
    )
    
    results = {'strategies_tested': [], 'execute': 0, 'wait': 0, 'reject': 0}
    
    # Process each opportunity
    for opportunity in scenario.opportunities:
        try:
            # Select strategy
            strategy, confidence = gpm._select_optimal_strategy_with_context(opportunity)
            
            # Create entry
            entry = SmartGamePlanEntry(
                symbol=opportunity['symbol'],
                tier='A',
                primary_strategy=strategy,
                primary_strategy_confidence=confidence,
                backup_strategies=[],
                strategy_selection_reasoning=f"Selected {strategy.value} with {confidence:.2f} confidence",
                entry_price=opportunity['current_price'],
                stop_loss=opportunity['current_price'] * 0.97,
                target_1=opportunity['current_price'] * 1.06,
                target_2=opportunity['current_price'] * 1.10,
                technical_setup_score=opportunity['quality_score'],
                optimal_market_phases=[scenario.market_phase],
                required_sentiment=[scenario.sentiment],
                min_volatility_regime='NORMAL',
                context_match_score=confidence,
                position_size=500,
                max_risk_per_trade=1000,
                execution_urgency='MEDIUM',
                time_decay_factor=1.0,
                last_updated=datetime.now()
            )
            
            gpm.current_plan[opportunity['symbol']] = entry
            
            # Get instant decision
            decision = gpm.get_instant_decision(opportunity['symbol'], opportunity)
            action = decision.get('action', 'UNKNOWN')
            reason = decision.get('reason', 'No reason')[:50]
            
            # Track result
            if action == 'EXECUTE':
                results['execute'] += 1
            elif action == 'WAIT':
                results['wait'] += 1
            elif action == 'REJECT':
                results['reject'] += 1
            
            results['strategies_tested'].append(strategy.value)
            
            # Log result
            status_emoji = "✅" if action == "EXECUTE" else "⏸️" if action == "WAIT" else "❌"
            
            logger.info(f"{status_emoji} {opportunity['symbol']:8} | {strategy.value:20} | {action:7} | {confidence:.2f} | {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error in {opportunity['symbol']}: {e}")
            results['reject'] += 1
    
    return results

async def main():
    """Main comprehensive test"""
    
    logger = setup_test_logging()
    
    print("🧠 SMART GAME PLAN MANAGER - TEST COMPREHENSIVO")
    print("=" * 60)
    print("Testing all 10 strategies in optimal contexts...")
    print()
    
    # Create test scenarios
    scenarios = create_test_scenarios()
    
    total_results = {
        'scenarios_tested': 0,
        'strategies_covered': set(),
        'total_execute': 0,
        'total_wait': 0,
        'total_reject': 0
    }
    
    # Test each scenario
    for scenario in scenarios:
        try:
            results = await test_scenario(scenario, logger)
            
            # Aggregate results
            total_results['scenarios_tested'] += 1
            total_results['strategies_covered'].update(results['strategies_tested'])
            total_results['total_execute'] += results['execute']
            total_results['total_wait'] += results['wait']
            total_results['total_reject'] += results['reject']
            
        except Exception as e:
            logger.error(f"❌ Scenario {scenario.name} failed: {e}")
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 RESUMEN FINAL - TEST COMPREHENSIVO")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Escenarios probados: {total_results['scenarios_tested']}")
    logger.info(f"🎛️  Estrategias cubiertas: {len(total_results['strategies_covered'])}/10")
    logger.info(f"🚀 Total ejecutables: {total_results['total_execute']}")
    logger.info(f"⏳ Total en espera: {total_results['total_wait']}")
    logger.info(f"🚫 Total rechazadas: {total_results['total_reject']}")
    logger.info(f"\n📋 Estrategias probadas:")
    for strategy in sorted(total_results['strategies_covered']):
        logger.info(f"   ✅ {strategy}")
    
    missing_strategies = set([s.value for s in StrategyType]) - total_results['strategies_covered']
    if missing_strategies:
        logger.info(f"\n❓ Estrategias NO probadas:")
        for strategy in sorted(missing_strategies):
            logger.info(f"   ❓ {strategy}")
    
    print(f"\n🎉 TEST COMPLETADO")
    print(f"   📊 {total_results['scenarios_tested']} escenarios")
    print(f"   🎯 {len(total_results['strategies_covered'])}/10 estrategias")
    print(f"   ✅ {total_results['total_execute']} ejecutables")
    
    if len(total_results['strategies_covered']) == 10:
        print("\n🏆 ¡TODAS LAS ESTRATEGIAS PROBADAS EXITOSAMENTE!")
        return 0
    else:
        print(f"\n⚠️  {10 - len(total_results['strategies_covered'])} estrategias sin probar")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)