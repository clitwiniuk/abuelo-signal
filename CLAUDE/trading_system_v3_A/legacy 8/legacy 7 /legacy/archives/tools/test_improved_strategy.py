#!/usr/bin/env python3
"""
Test Improved Simple Explosion Strategy
=======================================

Prueba la nueva estrategia mejorada con filtros de calidad
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def test_improved_strategy():
    print("💎 TESTING IMPROVED SIMPLE EXPLOSION STRATEGY")
    print("=" * 70)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    print(f"📊 Testing ImprovedSimpleExplosionStrategy with quality filters...")
    print("-" * 50)
    
    # Test with default parameters (more selective)
    success = await backtester.run_mass_backtest(
        'ImprovedSimpleExplosionStrategy',
        max_events=50,  # Test with more events
        strategy_params=None  # Use defaults
    )
    
    if success:
        stats = backtester.analyze_results()
        
        print(f"\n✅ IMPROVED STRATEGY RESULTS:")
        print(f"   📊 Total trades: {stats.get('total_trades', 0)}")
        print(f"   📈 Win rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   💰 Total return: {stats.get('total_return_pct', 0):+.2f}%")
        print(f"   ✅ Completion rate: {stats.get('completion_rate', 0):.1f}%")
        
        # Show comparison vs ultra simple
        print(f"\n📊 COMPARISON vs Ultra Simple:")
        print(f"   Expected: FEWER trades but HIGHER quality")
        print(f"   Goal: Win rate > 45% and Profit factor > 1.1")
        
        if stats.get('total_trades', 0) > 0:
            win_rate = stats.get('win_rate', 0)
            if win_rate > 45:
                print(f"   🎉 WIN RATE IMPROVED: {win_rate:.1f}% > 45% target")
            else:
                print(f"   ⚠️  Win rate still low: {win_rate:.1f}%")
        else:
            print(f"   ⚠️  No trades generated (possibly too selective)")
    else:
        print("❌ Failed to run backtest")
    
    print(f"\n" + "="*70)
    print(f"🏁 IMPROVED STRATEGY TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_improved_strategy())