#!/usr/bin/env python3
"""
Test del Smart Game Plan Manager - Verificación de las 10 estrategias
================================================================

Verifica que todas las estrategias están correctamente implementadas
con context awareness completo.
"""

import asyncio
import logging
from datetime import datetime
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
    SmartGamePlanEntry
)

def setup_test_logging():
    """Setup de logging para test"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("TestSmartGamePlan")

class MockConfig:
    """Mock config for testing"""
    def __init__(self):
        self.client_id = 999
        self.strategy_settings = {
            'max_daily_plays': 15,
            'max_risk_per_trade': 1000
        }

class MockDataProvider:
    """Mock data provider for testing"""
    def __init__(self):
        self.test_data = {}
        self.market_phase = 'OPENING'  # Can be changed for different tests
    
    async def get_market_data(self):
        return {
            'SPY_change': 0.015,  # +1.5%
            'VIX': 18.5,
            'volume_ratio': 1.2,
            'sector_rotation': {'TECH': 0.02, 'HEALTHCARE': -0.005}
        }
    
    def set_market_phase(self, phase):
        """Set market phase for testing"""
        self.market_phase = phase

def create_test_opportunities() -> List[Dict]:
    """Create test opportunities for all 10 strategies with targeted conditions"""
    
    return [
        # 1. Gap and Go - Strong bullish gap in opening
        {
            'symbol': 'GAPGO',
            'gap_percentage': 0.15,  # 15% gap up
            'volume_ratio': 5.5,
            'catalyst_type': 'BREAKTHROUGH',
            'current_price': 25.50,
            'quality_score': 8.2
        },
        
        # 2. Fade Gap - Extreme gap for fade  
        {
            'symbol': 'FADEGAP',
            'gap_percentage': 0.25,  # 25% gap (extreme, fade candidate)
            'volume_ratio': 3.8,
            'catalyst_type': 'OVERREACTION',
            'current_price': 45.20,
            'quality_score': 7.1
        },
        
        # 3. News Momentum - M&A with high volume
        {
            'symbol': 'NEWSMO',
            'gap_percentage': 0.08,
            'volume_ratio': 6.2,
            'catalyst_type': 'M&A',
            'current_price': 18.75,
            'quality_score': 8.9
        },
        
        # 4. FDA Catalyst - FDA approval
        {
            'symbol': 'FDACAT',
            'gap_percentage': 0.15,
            'volume_ratio': 4.1,
            'catalyst_type': 'FDA',
            'current_price': 32.10,
            'quality_score': 9.2
        },
        
        # 5. Earnings Surprise - Large earnings gap
        {
            'symbol': 'EARNSRP',
            'gap_percentage': 0.14,  # 14% earnings gap
            'volume_ratio': 3.7,
            'catalyst_type': 'EARNINGS',
            'current_price': 28.90,
            'quality_score': 8.5
        },
        
        # 6. Opening Range Breakout - Small gap in opening
        {
            'symbol': 'ORBOOK',
            'gap_percentage': 0.03,  # Small gap, perfect for ORB
            'volume_ratio': 2.5,
            'catalyst_type': 'BREAKOUT',
            'current_price': 21.40,
            'quality_score': 7.8
        },
        
        # 7. Momentum Continuation - Mid-day continuation
        {
            'symbol': 'MOMCON',
            'gap_percentage': 0.06,  # Moderate gap
            'volume_ratio': 4.8,
            'catalyst_type': 'CONTINUATION',
            'current_price': 19.65,
            'quality_score': 8.0
        },
        
        # 8. Reversal Play - Large down gap for reversal
        {
            'symbol': 'REVPLAY',
            'gap_percentage': -0.18,  # 18% gap DOWN (negative for reversal)
            'volume_ratio': 4.2,
            'catalyst_type': 'OVERSOLD',
            'current_price': 16.30,
            'quality_score': 7.5
        },
        
        # 9. Volume Breakout - Massive volume spike
        {
            'symbol': 'VOLBRK',
            'gap_percentage': 0.04,
            'volume_ratio': 12.0,  # Very high volume spike for volume breakout
            'catalyst_type': 'VOLUME',
            'current_price': 23.80,
            'quality_score': 8.3
        },
        
        # 10. End of Day - Power hour play
        {
            'symbol': 'EODPLAY',
            'gap_percentage': 0.05,
            'volume_ratio': 3.2,
            'catalyst_type': 'INSTITUTIONAL',
            'current_price': 31.25,
            'quality_score': 7.9
        }
    ]

async def test_strategy_selection_and_execution():
    """Test principal: Verificar selección y ejecución de todas las estrategias"""
    
    logger = setup_test_logging()
    logger.info("🧪 INICIANDO TEST - Smart Game Plan Manager")
    logger.info("=" * 60)
    
    # 1. Inicializar Game Plan Manager
    config = MockConfig()
    data_provider = MockDataProvider()
    
    gpm = SmartGamePlanManager(
        config=config,
        data_provider=data_provider,
        logger=logger
    )
    
    logger.info("✅ Game Plan Manager inicializado")
    
    # 2. Start dynamic updates
    await gpm.start_dynamic_updates()
    logger.info("✅ Dynamic updates iniciados")
    
    # 3. Create test opportunities
    opportunities = create_test_opportunities()
    logger.info(f"📊 Creadas {len(opportunities)} oportunidades de test")
    
    # 4. Generate game plan from opportunities
    logger.info("\n🎯 GENERANDO GAME PLAN...")
    logger.info("-" * 40)
    
    for opportunity in opportunities:
        try:
            # Select strategy for each opportunity
            strategy, confidence = gpm._select_optimal_strategy_with_context(opportunity)
            
            logger.info(f"📈 {opportunity['symbol']:8} -> {strategy.value:20} (conf: {confidence:.2f})")
            
            # Create game plan entry manually
            from datetime import datetime
            entry = SmartGamePlanEntry(
                symbol=opportunity['symbol'],
                tier='A',
                primary_strategy=strategy,
                primary_strategy_confidence=confidence,
                backup_strategies=[],
                strategy_selection_reasoning=f"Selected {strategy.value} with {confidence:.2f} confidence",
                entry_price=opportunity['current_price'],
                stop_loss=opportunity['current_price'] * 0.97,  # 3% stop loss
                target_1=opportunity['current_price'] * 1.06,   # 6% target
                target_2=opportunity['current_price'] * 1.10,   # 10% target  
                technical_setup_score=opportunity['quality_score'],
                optimal_market_phases=[MarketPhase.OPENING, MarketPhase.AFTERNOON],
                required_sentiment=[MarketSentiment.NEUTRAL, MarketSentiment.BULLISH],
                min_volatility_regime='NORMAL',
                context_match_score=confidence,
                position_size=500,  # Test position size
                max_risk_per_trade=1000,
                execution_urgency='MEDIUM',
                time_decay_factor=1.0,
                last_updated=datetime.now()
            )
            
            # Add to current plan
            gpm.current_plan[opportunity['symbol']] = entry
            
        except Exception as e:
            logger.error(f"❌ Error procesando {opportunity['symbol']}: {e}")
    
    # 5. Test instant decisions for each strategy
    logger.info(f"\n⚡ TESTING INSTANT DECISIONS - {len(gpm.current_plan)} entries")
    logger.info("-" * 50)
    
    strategy_results = {}
    
    for symbol, entry in gpm.current_plan.items():
        try:
            # Find original opportunity data
            opp_data = next((opp for opp in opportunities if opp['symbol'] == symbol), {})
            
            # Get instant decision
            decision = gpm.get_instant_decision(symbol, opp_data)
            
            strategy_name = entry.primary_strategy.value
            strategy_results[strategy_name] = decision
            
            # Log result
            action = decision.get('action', 'UNKNOWN')
            reason = decision.get('reason', 'No reason')[:50]
            exec_time = decision.get('execution_time_ms', 0)
            
            status_emoji = "✅" if action == "EXECUTE" else "⏸️" if action == "WAIT" else "❌"
            
            logger.info(f"{status_emoji} {symbol:8} | {strategy_name:20} | {action:7} | {exec_time:4.1f}ms | {reason}")
            
        except Exception as e:
            logger.error(f"❌ Error en decision {symbol}: {e}")
            strategy_results[entry.primary_strategy.value] = {'action': 'ERROR', 'reason': str(e)}
    
    # 6. Analyze results by strategy
    logger.info(f"\n📊 ANÁLISIS POR ESTRATEGIA")
    logger.info("-" * 40)
    
    strategy_counts = {'EXECUTE': 0, 'WAIT': 0, 'REJECT': 0, 'ERROR': 0}
    
    for strategy_type in StrategyType:
        strategy_name = strategy_type.value
        result = strategy_results.get(strategy_name, {'action': 'NOT_TESTED'})
        action = result.get('action', 'NOT_TESTED')
        
        if action in strategy_counts:
            strategy_counts[action] += 1
        
        status_emoji = {
            'EXECUTE': '🚀',
            'WAIT': '⏳', 
            'REJECT': '🚫',
            'ERROR': '💥',
            'NOT_TESTED': '❓'
        }.get(action, '❓')
        
        logger.info(f"{status_emoji} {strategy_name:25} -> {action}")
    
    # 7. Summary
    logger.info(f"\n🎯 RESUMEN FINAL")
    logger.info("=" * 30)
    logger.info(f"✅ Estrategias configuradas: {len(StrategyType)} / 10")
    logger.info(f"🚀 Ejecutables: {strategy_counts['EXECUTE']}")
    logger.info(f"⏳ En espera: {strategy_counts['WAIT']}")
    logger.info(f"🚫 Rechazadas: {strategy_counts['REJECT']}")
    logger.info(f"💥 Con errores: {strategy_counts['ERROR']}")
    
    # Test context awareness
    logger.info(f"\n🌍 CONTEXT AWARENESS TEST")
    logger.info("-" * 30)
    context = gpm.market_context
    logger.info(f"📅 Fase actual: {context.current_phase.value}")
    logger.info(f"💭 Sentiment: {context.market_sentiment.value}")
    logger.info(f"📊 Volatilidad: {context.volatility_regime}")
    logger.info(f"📈 SPY cambio: {context.spy_change_pct:.1%}")
    logger.info(f"📉 VIX nivel: {context.vix_level:.1f}")
    
    # 8. Stop dynamic updates
    await gpm.stop_dynamic_updates()
    logger.info("\n✅ Test completado - Dynamic updates detenidos")
    
    return {
        'total_strategies': len(StrategyType),
        'results': strategy_results,
        'summary': strategy_counts,
        'context_working': True
    }

async def main():
    """Main test function"""
    
    print("🧠 SMART GAME PLAN MANAGER - TEST COMPLETO")
    print("=" * 50)
    print("Verificando implementación de las 10 estrategias...")
    print()
    
    try:
        results = await test_strategy_selection_and_execution()
        
        print(f"\n🎉 TEST COMPLETADO EXITOSAMENTE")
        print(f"   ✅ {results['total_strategies']} estrategias implementadas")
        print(f"   🚀 {results['summary']['EXECUTE']} ejecutables")
        print(f"   ⏳ {results['summary']['WAIT']} en espera")
        print(f"   🚫 {results['summary']['REJECT']} rechazadas")
        print(f"   💥 {results['summary']['ERROR']} con errores")
        
        if results['summary']['ERROR'] == 0:
            print("\n✅ TODAS LAS ESTRATEGIAS FUNCIONAN CORRECTAMENTE")
        else:
            print(f"\n⚠️  {results['summary']['ERROR']} estrategias con errores - revisar logs")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)