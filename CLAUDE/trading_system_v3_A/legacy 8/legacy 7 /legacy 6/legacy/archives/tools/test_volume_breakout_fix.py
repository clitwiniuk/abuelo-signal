#!/usr/bin/env python3
"""
Test VolumeBreakoutStrategy Fix
===============================

Quick test to verify VolumeBreakoutStrategy works with the backtesting system
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def test_volume_breakout_strategy():
    print("🔧 TESTING VOLUME BREAKOUT STRATEGY FIX")
    print("=" * 60)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    print(f"📊 Testing VolumeBreakoutStrategy with fixed initialization...")
    print("-" * 50)
    
    # Test with None parameters (should use defaults)
    success = await backtester.run_mass_backtest(
        'VolumeBreakoutStrategy',
        max_events=3,  # Test with just a few events
        strategy_params=None  # This should work now
    )
    
    if success:
        stats = backtester.analyze_results()
        
        print(f"\n✅ VOLUME BREAKOUT STRATEGY RESULTS:")
        print(f"   📊 Total trades: {stats.get('total_trades', 0)}")
        print(f"   📈 Win rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   💰 Total return: {stats.get('total_return_pct', 0):+.2f}%")
        print(f"   ✅ Completion rate: {stats.get('completion_rate', 0):.1f}%")
        
        if stats.get('total_trades', 0) > 0:
            print(f"\n🎉 SUCCESS: Strategy generated {stats['total_trades']} signals!")
        else:
            print(f"\n⚠️  Strategy generated 0 trades (but didn't crash!)")
    else:
        print("❌ Failed to run backtest")
    
    print(f"\n" + "="*60)
    print(f"🏁 VOLUME BREAKOUT STRATEGY TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_volume_breakout_strategy())