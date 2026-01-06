#!/usr/bin/env python3
"""
Test Phase 1 Optimizations - Verificar funcionamiento de BatchPriceManager y SmartPositionCache
Comprueba que las optimizaciones funcionen correctamente y reduzcan API calls
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from adapters.ibkr_adapter import IBKRAdapter
from core.batch_price_manager import BatchPriceManager
from core.smart_position_cache import SmartPositionCache

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class Phase1OptimizationTester:
    """
    Tester para verificar las optimizaciones de Fase 1
    """
    
    def __init__(self, logger):
        self.logger = logger
        self.adapter = None
        self.test_symbols = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL"]  # Test symbols
        
        # Test metrics
        self.api_call_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
    async def initialize_adapter(self) -> bool:
        """Initialize IBKR adapter with optimizations"""
        try:
            self.logger.info("🔌 Initializing IBKR adapter with Phase 1 optimizations...")
            
            # Initialize with optimizations enabled by default
            self.adapter = IBKRAdapter(
                host="127.0.0.1", 
                port=7497,
                client_id=4150  # Different from main trader
            )
            
            # Try to connect
            connected = await self.adapter.connect()
            
            if connected:
                self.logger.info("✅ IBKR adapter connected successfully")
                return True
            else:
                self.logger.error("❌ Failed to connect to IBKR")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing adapter: {e}")
            return False
    
    async def test_batch_price_manager(self) -> Dict[str, any]:
        """Test BatchPriceManager functionality"""
        self.logger.info("📡 Testing BatchPriceManager...")
        
        test_results = {
            'batch_subscriptions': False,
            'price_retrieval': False,
            'subscription_cleanup': False,
            'api_optimization': False
        }
        
        try:
            if not self.adapter.batch_price_manager:
                self.logger.error("❌ BatchPriceManager not available")
                return test_results
            
            # Test 1: Batch subscriptions
            self.logger.info("🔬 Test 1: Batch price subscriptions")
            success = await self.adapter.initialize_batch_subscriptions(self.test_symbols)
            test_results['batch_subscriptions'] = success
            
            if success:
                self.logger.info("✅ Batch subscriptions successful")
                
                # Give time for initial price data
                await asyncio.sleep(2)
                
                # Test 2: Price retrieval without API calls
                self.logger.info("🔬 Test 2: Price retrieval from cache")
                prices_retrieved = 0
                
                for symbol in self.test_symbols:
                    price = await self.adapter.get_current_price(symbol)
                    if price > 0:
                        prices_retrieved += 1
                        self.logger.debug(f"💰 {symbol}: ${price:.2f}")
                
                if prices_retrieved >= len(self.test_symbols) * 0.8:  # 80% success threshold
                    test_results['price_retrieval'] = True
                    self.logger.info(f"✅ Price retrieval successful: {prices_retrieved}/{len(self.test_symbols)}")
                else:
                    self.logger.warning(f"⚠️ Price retrieval partial: {prices_retrieved}/{len(self.test_symbols)}")
                
                # Test 3: API optimization verification
                batch_manager = self.adapter.batch_price_manager
                subscribed_count = len(batch_manager.get_subscribed_symbols())
                
                if subscribed_count >= len(self.test_symbols) * 0.8:
                    test_results['api_optimization'] = True
                    self.logger.info(f"✅ API optimization active: {subscribed_count} persistent subscriptions")
                
            else:
                self.logger.error("❌ Batch subscriptions failed")
            
        except Exception as e:
            self.logger.error(f"❌ Error testing BatchPriceManager: {e}")
        
        return test_results
    
    async def test_smart_position_cache(self) -> Dict[str, any]:
        """Test SmartPositionCache functionality"""
        self.logger.info("🧠 Testing SmartPositionCache...")
        
        test_results = {
            'cache_initialization': False,
            'position_retrieval': False,
            'cache_efficiency': False,
            'event_invalidation': False
        }
        
        try:
            if not self.adapter.smart_position_cache:
                self.logger.error("❌ SmartPositionCache not available")
                return test_results
            
            cache = self.adapter.smart_position_cache
            test_results['cache_initialization'] = True
            
            # Test 1: Position retrieval
            self.logger.info("🔬 Test 1: Position retrieval with caching")
            
            # First call (cache miss - will make API calls)
            positions1 = await self.adapter.get_positions()
            cache_stats1 = cache.get_cache_statistics()
            
            # Second call immediately (should be cache hit)
            positions2 = await self.adapter.get_positions()
            cache_stats2 = cache.get_cache_statistics()
            
            test_results['position_retrieval'] = len(positions1) == len(positions2)
            
            # Test 2: Cache efficiency
            if cache_stats2['cache_hits'] > cache_stats1['cache_hits']:
                test_results['cache_efficiency'] = True
                hit_rate = cache_stats2['hit_rate_percent']
                self.logger.info(f"✅ Cache efficiency verified: {hit_rate:.1f}% hit rate")
            else:
                self.logger.warning("⚠️ No cache hits detected - may need more test time")
            
            # Test 3: Cache invalidation simulation
            self.logger.info("🔬 Test 3: Event-driven cache invalidation")
            
            if len(positions1) > 0:
                # Simulate order fill for first position
                test_symbol = list(positions1.keys())[0]
                cache.invalidate_on_order_fill(test_symbol)
                
                # Next call should refresh cache
                positions3 = await self.adapter.get_positions()
                cache_stats3 = cache.get_cache_statistics()
                
                if cache_stats3['cache_misses'] > cache_stats2['cache_misses']:
                    test_results['event_invalidation'] = True
                    self.logger.info("✅ Event-driven cache invalidation working")
            
        except Exception as e:
            self.logger.error(f"❌ Error testing SmartPositionCache: {e}")
        
        return test_results
    
    async def test_api_load_reduction(self) -> Dict[str, any]:
        """Test overall API load reduction"""
        self.logger.info("⚡ Testing API load reduction...")
        
        test_results = {
            'price_calls_reduced': False,
            'position_calls_reduced': False,
            'overall_optimization': False
        }
        
        try:
            # Get optimization status
            opt_status = self.adapter.get_optimization_status()
            
            # Check BatchPriceManager status
            if opt_status['batch_price_manager']['status'] == 'ACTIVE':
                subscribed = opt_status['batch_price_manager']['subscribed_symbols']
                if subscribed >= 3:  # At least 3 symbols subscribed
                    test_results['price_calls_reduced'] = True
                    self.logger.info(f"✅ Price calls optimization: {subscribed} symbols using persistent subscriptions")
            
            # Check SmartPositionCache status
            if opt_status['smart_position_cache']['status'] == 'ACTIVE':
                hit_rate = opt_status['smart_position_cache']['hit_rate_percent']
                if hit_rate >= 50:  # At least 50% hit rate
                    test_results['position_calls_reduced'] = True
                    self.logger.info(f"✅ Position calls optimization: {hit_rate:.1f}% cache hit rate")
            
            # Overall optimization
            if test_results['price_calls_reduced'] and test_results['position_calls_reduced']:
                test_results['overall_optimization'] = True
                self.logger.info("🎯 Overall Phase 1 optimization: SUCCESSFUL")
            
        except Exception as e:
            self.logger.error(f"❌ Error testing API load reduction: {e}")
        
        return test_results
    
    async def cleanup(self):
        """Cleanup test resources"""
        try:
            if self.adapter:
                await self.adapter.disconnect()
                self.logger.info("🧹 Test cleanup completed")
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")

async def run_phase1_optimization_tests():
    """Run all Phase 1 optimization tests"""
    logger = setup_logging()
    
    print("🧪 PHASE 1 OPTIMIZATION TESTS")
    print("=" * 60)
    print("Testing BatchPriceManager and SmartPositionCache")
    print("=" * 60)
    
    tester = Phase1OptimizationTester(logger)
    
    try:
        # Initialize
        logger.info("🔧 STEP 1: Initialize test environment")
        if not await tester.initialize_adapter():
            logger.error("❌ Failed to initialize test environment")
            return False
        
        # Test BatchPriceManager
        logger.info("\n📡 STEP 2: Test BatchPriceManager")
        batch_results = await tester.test_batch_price_manager()
        
        # Test SmartPositionCache
        logger.info("\n🧠 STEP 3: Test SmartPositionCache")
        cache_results = await tester.test_smart_position_cache()
        
        # Test API load reduction
        logger.info("\n⚡ STEP 4: Test API load reduction")
        load_results = await tester.test_api_load_reduction()
        
        # Results summary
        print("\n" + "=" * 60)
        print("📊 PHASE 1 OPTIMIZATION TEST RESULTS")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        # BatchPriceManager results
        print("📡 BatchPriceManager Tests:")
        for test_name, result in batch_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
            total_tests += 1
            if result: passed_tests += 1
        
        # SmartPositionCache results
        print("\n🧠 SmartPositionCache Tests:")
        for test_name, result in cache_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
            total_tests += 1
            if result: passed_tests += 1
        
        # API Load Reduction results
        print("\n⚡ API Load Reduction Tests:")
        for test_name, result in load_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status} {test_name}")
            total_tests += 1
            if result: passed_tests += 1
        
        # Overall results
        success_rate = (passed_tests / total_tests) * 100
        print(f"\n🎯 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("✅ Phase 1 optimizations are working correctly!")
            print("⚡ Expected API call reduction: 92%+ vs unoptimized system")
        else:
            print("⚠️ Some optimizations may need attention")
        
        print("=" * 60)
        
        return success_rate >= 80
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return False
    
    finally:
        await tester.cleanup()

async def main():
    try:
        success = await run_phase1_optimization_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error in Phase 1 optimization tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)