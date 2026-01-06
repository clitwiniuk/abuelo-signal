#!/usr/bin/env python3
"""
Test script for new VolumeExplosionPullbackStrategy
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester
from improved_strategy_backtester import ImprovedStrategyBacktester
from strategy_optimizer import StrategyOptimizer

async def test_new_strategy():
    print("🎯 TESTING NEW VOLUME EXPLOSION PULLBACK STRATEGY")
    print("=" * 70)
    
    # Test 1: Backtest real strategy
    print("\n📊 STEP 1: Testing real strategy implementation...")
    real_backtester = FixedRealStrategyBacktester()
    
    if not real_backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    success = await real_backtester.run_mass_backtest(
        'VolumeExplosionPullbackStrategy', 
        max_events=20
    )
    
    if success:
        real_stats = real_backtester.analyze_results()
        real_backtester.print_performance_report(real_stats)
    
    print("\n" + "="*70)
    
    # Test 2: Compare with optimizer
    print("\n📊 STEP 2: Comparing with simulated potential...")
    optimizer = StrategyOptimizer()
    
    if await optimizer.initialize():
        comparison = await optimizer.compare_strategy_performance(
            'VolumeExplosionPullbackStrategy', 
            max_events=20
        )
        optimizer.print_comparison_report(comparison)
    
    print("\n" + "="*70)
    print("🏁 TEST COMPLETED - Analysis ready!")

if __name__ == "__main__":
    asyncio.run(test_new_strategy())