#!/usr/bin/env python3
"""
Test SimpleVolumeExplosionStrategy
==================================

Test the simplified direct entry strategy with the backtesting system
to verify it generates signals where the pullback version failed.
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def test_simple_explosion_strategy():
    print("🎯 TESTING SIMPLE VOLUME EXPLOSION STRATEGY")
    print("=" * 70)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    print(f"📊 Testing SimpleVolumeExplosionStrategy with direct entry approach...")
    print("-" * 50)
    
    # Test with default parameters first
    success = await backtester.run_mass_backtest(
        'SimpleVolumeExplosionStrategy',
        max_events=25,
        strategy_params=None  # Use defaults
    )
    
    if success:
        stats = backtester.analyze_results()
        
        print(f"\n✅ RESULTS WITH DEFAULT PARAMETERS:")
        print(f"   📊 Total trades: {stats.get('total_trades', 0)}")
        print(f"   📈 Win rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   💰 Total return: {stats.get('total_return_pct', 0):+.2f}%")
        print(f"   ✅ Completion rate: {stats.get('completion_rate', 0):.1f}%")
        
        if stats.get('total_trades', 0) > 0:
            print(f"\n🎉 SUCCESS: Strategy generated {stats['total_trades']} signals!")
            print(f"This is a major improvement over the pullback version which generated 0 signals.")
        else:
            print(f"\n⚠️  Strategy still generated 0 trades. Let's try more aggressive parameters...")
            
            # Test with more aggressive parameters
            aggressive_params = {
                'volume_threshold': 1.2,        # Very permissive
                'momentum_threshold': 0.002,    # 0.2% momentum
                'momentum_bars': 1,             # Only 1 bar lookback
                'min_history_bars': 3,          # Minimal history
                'max_daily_signals': 25         # Allow many signals
            }
            
            print(f"\n🔥 TESTING WITH AGGRESSIVE PARAMETERS:")
            print(f"   Volume threshold: {aggressive_params['volume_threshold']:.1f}x")
            print(f"   Momentum threshold: {aggressive_params['momentum_threshold']:.1f}%")
            print(f"   Momentum bars: {aggressive_params['momentum_bars']}")
            
            success2 = await backtester.run_mass_backtest(
                'SimpleVolumeExplosionStrategy',
                max_events=25,
                strategy_params=aggressive_params
            )
            
            if success2:
                stats2 = backtester.analyze_results()
                print(f"\n✅ AGGRESSIVE RESULTS:")
                print(f"   📊 Total trades: {stats2.get('total_trades', 0)}")
                print(f"   📈 Win rate: {stats2.get('win_rate', 0):.1f}%")
                print(f"   💰 Total return: {stats2.get('total_return_pct', 0):+.2f}%")
                print(f"   ✅ Completion rate: {stats2.get('completion_rate', 0):.1f}%")
    else:
        print("❌ Failed to run backtest")
    
    print(f"\n" + "="*70)
    print(f"🏁 SIMPLE STRATEGY TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_simple_explosion_strategy())