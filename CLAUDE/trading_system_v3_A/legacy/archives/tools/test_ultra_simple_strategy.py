#!/usr/bin/env python3
"""
Test UltraSimpleExplosionStrategy
================================

Test the ultra permissive strategy to see if we can generate any signals at all
"""

import asyncio
import logging
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

# Enable debug logging
logging.basicConfig(level=logging.INFO)

async def test_ultra_simple_strategy():
    print("🔥 TESTING ULTRA SIMPLE EXPLOSION STRATEGY")
    print("=" * 70)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    print(f"📊 Testing UltraSimpleExplosionStrategy with maximum permissive settings...")
    print("-" * 50)
    
    # Test with ultra permissive parameters
    ultra_params = {
        'volume_threshold': 1.0,        # ANY volume increase
        'momentum_threshold': 0.0,      # ANY momentum (even 0%)
        'min_history_bars': 1,          # Only 1 bar needed
        'cooldown_minutes': 0,          # No cooldown
        'max_daily_signals': 100        # Many signals
    }
    
    success = await backtester.run_mass_backtest(
        'UltraSimpleExplosionStrategy',
        max_events=1,  # Test only 1 event for detailed debugging
        strategy_params=ultra_params
    )
    
    if success:
        stats = backtester.analyze_results()
        
        print(f"\n✅ ULTRA PERMISSIVE RESULTS:")
        print(f"   📊 Total trades: {stats.get('total_trades', 0)}")
        print(f"   📈 Win rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   💰 Total return: {stats.get('total_return_pct', 0):+.2f}%")
        print(f"   ✅ Completion rate: {stats.get('completion_rate', 0):.1f}%")
        
        if stats.get('total_trades', 0) > 0:
            print(f"\n🎉 SUCCESS: Ultra strategy generated {stats['total_trades']} signals!")
        else:
            print(f"\n❌ Even ultra permissive strategy generated 0 trades.")
            print(f"This suggests a fundamental issue with the data or strategy interface.")
    else:
        print("❌ Failed to run backtest")
    
    print(f"\n" + "="*70)
    print(f"🏁 ULTRA STRATEGY TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_ultra_simple_strategy())