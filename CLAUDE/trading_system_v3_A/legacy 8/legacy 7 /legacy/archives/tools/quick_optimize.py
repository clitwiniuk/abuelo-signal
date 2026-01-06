#!/usr/bin/env python3
"""
Quick Optimization - Shortened version
======================================

Versión corta del optimizador para ver solo resultados finales
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def quick_optimize():
    print("🔬 QUICK PARAMETER OPTIMIZATION")
    print("=" * 60)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    # Configuraciones a probar
    configs = [
        {
            'name': 'Ultra Conservative',
            'params': {
                'volume_threshold': 4.0,
                'momentum_threshold': 0.015,
                'min_volume_absolute': 50000,
                'max_daily_signals': 3,
                'cooldown_minutes': 30,
            }
        },
        {
            'name': 'Conservative',
            'params': {
                'volume_threshold': 3.0,
                'momentum_threshold': 0.012,
                'min_volume_absolute': 25000,
                'max_daily_signals': 5,
                'cooldown_minutes': 20,
            }
        },
        {
            'name': 'Balanced',
            'params': {
                'volume_threshold': 2.0,
                'momentum_threshold': 0.010,
                'min_volume_absolute': 15000,
                'max_daily_signals': 6,
                'cooldown_minutes': 15,
            }
        },
        {
            'name': 'Aggressive',
            'params': {
                'volume_threshold': 1.8,
                'momentum_threshold': 0.008,
                'min_volume_absolute': 10000,
                'max_daily_signals': 10,
                'cooldown_minutes': 10,
            }
        }
    ]
    
    results = []
    
    for config in configs:
        print(f"\n📊 TESTING: {config['name']}")
        print("-" * 40)
        
        success = await backtester.run_mass_backtest(
            'ImprovedSimpleExplosionStrategy',
            max_events=25,  # Reducido para ser más rápido
            strategy_params=config['params']
        )
        
        if success:
            stats = backtester.analyze_results()
            
            result = {
                'config_name': config['name'],
                'params': config['params'],
                'total_trades': stats.get('total_trades', 0),
                'win_rate': stats.get('win_rate', 0),
                'total_return_pct': stats.get('total_return_pct', 0),
                'completion_rate': stats.get('completion_rate', 0),
                'profit_factor': stats.get('profit_factor', 0),
            }
            
            results.append(result)
            
            print(f"   ✅ Trades: {result['total_trades']}")
            print(f"   📈 Win Rate: {result['win_rate']:.1f}%")
            print(f"   💰 Return: {result['total_return_pct']:+.2f}%")
            print(f"   🎯 Profit Factor: {result['profit_factor']:.2f}")
        else:
            print(f"   ❌ Failed")
    
    # Mostrar resumen
    print(f"\n📊 OPTIMIZATION SUMMARY")
    print("=" * 60)
    print(f"{'Config':<20} {'Trades':<7} {'WR%':<6} {'Ret%':<8} {'PF':<6}")
    print("-" * 60)
    
    for result in results:
        print(f"{result['config_name']:<20} "
              f"{result['total_trades']:<7} "
              f"{result['win_rate']:<6.1f} "
              f"{result['total_return_pct']:<+8.2f} "
              f"{result['profit_factor']:<6.2f}")
    
    # Encontrar mejor configuración
    if results:
        best_config = max(results, key=lambda x: (
            x['total_return_pct'] > 0,
            x['win_rate'],
            x['profit_factor'],
            x['total_trades']
        ))
        
        print(f"\n🏆 BEST CONFIGURATION: {best_config['config_name']}")
        print("=" * 40)
        print(f"   📊 Trades: {best_config['total_trades']}")
        print(f"   📈 Win Rate: {best_config['win_rate']:.1f}%")
        print(f"   💰 Return: {best_config['total_return_pct']:+.2f}%")
        print(f"   🎯 Profit Factor: {best_config['profit_factor']:.2f}")
        
        if best_config['total_return_pct'] > 0:
            print(f"\n🎉 ¡FOUND PROFITABLE CONFIG!")
        else:
            print(f"\n⚠️  None of the configs are profitable.")
            print(f"   🔍 Consider different approach or more data.")

if __name__ == "__main__":
    asyncio.run(quick_optimize())