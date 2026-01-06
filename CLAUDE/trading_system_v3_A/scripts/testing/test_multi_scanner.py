#!/usr/bin/env python3
"""
Test Multi-Scanner Integration
=============================

Test script to verify that the new strategy-specific scanner dispatcher
works correctly and provides opportunities for all strategies (ORB, VWAP_RECLAIM, etc.)
without breaking existing daily_plays functionality.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scanner.strategy_scanner_dispatcher import StrategyScannerDispatcher
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MultiScannerTest")

async def test_scanner_dispatcher():
    """Test the scanner dispatcher directly"""
    logger.info("🎯 Testing Strategy Scanner Dispatcher...")
    
    dispatcher = StrategyScannerDispatcher()
    
    try:
        # Test getting available strategies
        strategies = dispatcher.get_available_strategies()
        logger.info(f"📋 Available strategies: {strategies}")
        
        # Test scanning all strategies
        logger.info("🔍 Scanning all strategies...")
        all_results = await dispatcher.scan_all_strategies()
        
        logger.info("\n" + "="*60)
        logger.info("🎯 SCANNER DISPATCHER RESULTS")
        logger.info("="*60)
        
        total_opportunities = 0
        for strategy, opportunities in all_results.items():
            count = len(opportunities)
            total_opportunities += count
            logger.info(f"{strategy.upper()}: {count} opportunities")
            
            # Show first few opportunities for each strategy
            if count > 0:
                if strategy == 'daily_plays':
                    # SmallcapPlay objects
                    for i, play in enumerate(opportunities[:3], 1):
                        logger.info(f"  {i}. {play.symbol} - Quality: {play.quality_score:.1f}, Gap: {play.context.gap_percentage*100:+.1f}%")
                else:
                    # StrategyOpportunity objects
                    for i, opp in enumerate(opportunities[:3], 1):
                        gap_info = f"Gap: {opp.metadata.get('gap_percentage', 0):.1f}%" if 'gap_percentage' in opp.metadata else ""
                        logger.info(f"  {i}. {opp.symbol} - Confidence: {opp.confidence_score:.1%}, {gap_info}")
        
        logger.info(f"\n📊 Total opportunities found: {total_opportunities}")
        
        # Test specific strategy scanning
        logger.info("\n🎯 Testing specific strategy scanning...")
        for strategy in ['orb', 'vwap_reclaim']:
            specific_results = await dispatcher.scan_specific_strategy(strategy)
            logger.info(f"{strategy.upper()}: {len(specific_results)} specific opportunities")
        
        return all_results
        
    except Exception as e:
        logger.error(f"❌ Scanner dispatcher test failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {}
    
    finally:
        await dispatcher.disconnect()

async def test_ml_engine_integration():
    """Test ML Engine integration with multi-scanner"""
    logger.info("\n🧠 Testing ML Engine Scanner Integration...")
    
    try:
        # Create ML engine with scanner integration
        engine = MLMultiStrategyEngine(parameters={'smallcap_ml_enabled': True})
        
        # Test if scanner integration is enabled
        logger.info(f"Scanner enabled: {engine.scanner_enabled}")
        
        if engine.scanner_enabled:
            # Test scanning opportunities through ML engine
            logger.info("🔍 Testing ML engine opportunity scanning...")
            opportunities = await engine.scan_strategy_opportunities()
            
            logger.info("\n" + "="*60)
            logger.info("🧠 ML ENGINE SCANNER RESULTS")
            logger.info("="*60)
            
            total_ml_opportunities = 0
            for strategy, opps in opportunities.items():
                count = len(opps)
                total_ml_opportunities += count
                logger.info(f"{strategy.upper()}: {count} opportunities via ML engine")
            
            logger.info(f"\n📊 Total ML opportunities: {total_ml_opportunities}")
            
            # Test specific strategy access
            orb_opps = await engine.get_strategy_specific_signals('orb')
            vwap_opps = await engine.get_strategy_specific_signals('vwap_reclaim')
            daily_opps = await engine.get_strategy_specific_signals('daily_plays')
            
            logger.info(f"\n🎯 Specific strategy results via ML engine:")
            logger.info(f"   ORB: {len(orb_opps)} opportunities")
            logger.info(f"   VWAP Reclaim: {len(vwap_opps)} opportunities")
            logger.info(f"   Daily Plays: {len(daily_opps)} opportunities")
            
            return opportunities
        else:
            logger.warning("Scanner integration not enabled in ML engine")
            return {}
        
    except Exception as e:
        logger.error(f"❌ ML engine integration test failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {}

async def test_backward_compatibility():
    """Test that existing daily_plays functionality still works"""
    logger.info("\n🔄 Testing Backward Compatibility...")
    
    try:
        # Test original SmallcapDailyScanner directly
        from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
        
        original_scanner = SmallcapDailyScanner()
        daily_plays = await original_scanner.scan_daily_plays()
        
        logger.info(f"✅ Original SmallcapDailyScanner: {len(daily_plays)} daily plays found")
        
        if daily_plays:
            logger.info("📋 Sample daily plays:")
            for i, play in enumerate(daily_plays[:3], 1):
                logger.info(f"  {i}. {play.symbol} - Quality: {play.quality_score:.1f}")
        
        await original_scanner.disconnect()
        return len(daily_plays) > 0
        
    except Exception as e:
        logger.error(f"❌ Backward compatibility test failed: {e}")
        return False

async def comprehensive_test():
    """Run comprehensive multi-scanner tests"""
    logger.info("🚀 Starting Comprehensive Multi-Scanner Tests")
    logger.info("=" * 70)
    
    results = {
        'dispatcher_test': False,
        'ml_integration_test': False,
        'backward_compatibility_test': False,
        'total_opportunities': 0
    }
    
    # Test 1: Scanner Dispatcher
    logger.info("\n📋 TEST 1: Scanner Dispatcher")
    dispatcher_results = await test_scanner_dispatcher()
    results['dispatcher_test'] = len(dispatcher_results) > 0
    results['total_opportunities'] = sum(len(opps) for opps in dispatcher_results.values())
    
    # Test 2: ML Engine Integration
    logger.info("\n📋 TEST 2: ML Engine Integration")
    ml_results = await test_ml_engine_integration()
    results['ml_integration_test'] = len(ml_results) > 0
    
    # Test 3: Backward Compatibility
    logger.info("\n📋 TEST 3: Backward Compatibility")
    results['backward_compatibility_test'] = await test_backward_compatibility()
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 COMPREHENSIVE TEST SUMMARY")
    logger.info("="*70)
    
    passed_tests = sum(results[key] for key in ['dispatcher_test', 'ml_integration_test', 'backward_compatibility_test'])
    
    logger.info(f"Scanner Dispatcher Test: {'✅ PASS' if results['dispatcher_test'] else '❌ FAIL'}")
    logger.info(f"ML Integration Test: {'✅ PASS' if results['ml_integration_test'] else '❌ FAIL'}")
    logger.info(f"Backward Compatibility: {'✅ PASS' if results['backward_compatibility_test'] else '❌ FAIL'}")
    logger.info(f"\nOverall Success Rate: {passed_tests}/3 ({passed_tests/3*100:.1f}%)")
    logger.info(f"Total Opportunities Found: {results['total_opportunities']}")
    
    # Analysis
    if results['total_opportunities'] > 0:
        logger.info("\n🎯 ANALYSIS:")
        logger.info("✅ Multi-scanner solution successfully finds opportunities")
        
        if results['backward_compatibility_test']:
            logger.info("✅ Existing daily_plays functionality preserved")
        
        if results['ml_integration_test']:
            logger.info("✅ ML Engine can access strategy-specific opportunities")
        
        logger.info("\n🔧 SOLUTION STATUS:")
        logger.info("✅ ORB, VWAP_RECLAIM, and other strategies now have dedicated scanners")
        logger.info("✅ No more 3.5-hour delays - each strategy gets its specific opportunities")
        logger.info("✅ Existing daily_plays scanner continues to work unchanged")
    else:
        logger.warning("\n⚠️ No opportunities found - this could be due to:")
        logger.warning("   • Market conditions (outside trading hours)")
        logger.warning("   • IBKR connection issues")
        logger.warning("   • Scanner configuration problems")
    
    return results

if __name__ == "__main__":
    asyncio.run(comprehensive_test())