#!/usr/bin/env python3
"""
Optimize Pullback Strategy Parameters
=====================================

Script para optimizar los parámetros de VolumeExplosionPullbackStrategy
y hacerla funcional con los datos reales de explosiones.
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def test_parameter_combinations():
    print("🔧 OPTIMIZING VOLUME EXPLOSION PULLBACK STRATEGY")
    print("=" * 70)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    # Configuraciones a probar (de restrictiva a permisiva)
    test_configs = [
        {
            'name': 'Original (muy restrictiva)',
            'params': {
                'volume_explosion_threshold': 2.5,
                'price_move_threshold': 0.015,
                'pullback_entry_pct': 0.97,
                'volume_confirmation': 1.8,
                'min_history_bars': 15
            }
        },
        {
            'name': 'Menos restrictiva',
            'params': {
                'volume_explosion_threshold': 2.0,    # Menos restrictivo
                'price_move_threshold': 0.01,         # 1% en lugar de 1.5%
                'pullback_entry_pct': 0.98,           # Pullback menor
                'volume_confirmation': 1.5,           # Menos confirmación
                'min_history_bars': 10                # Menos historial requerido
            }
        },
        {
            'name': 'Agresiva',
            'params': {
                'volume_explosion_threshold': 1.8,    # Muy permisivo
                'price_move_threshold': 0.008,        # 0.8%
                'pullback_entry_pct': 0.99,           # Pullback mínimo
                'volume_confirmation': 1.3,           # Confirmación mínima
                'min_history_bars': 8                 # Historial mínimo
            }
        },
        {
            'name': 'Muy agresiva (captura máximo)',
            'params': {
                'volume_explosion_threshold': 1.5,    # Super permisivo
                'price_move_threshold': 0.005,        # 0.5%
                'pullback_entry_pct': 0.995,          # Casi sin pullback
                'volume_confirmation': 1.2,           # Confirmación mínima
                'min_history_bars': 5                 # Historial muy reducido
            }
        }
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n📊 TESTING: {config['name']}")
        print("-" * 50)
        
        # Ejecutar backtest con estos parámetros
        success = await backtester.run_mass_backtest(
            'VolumeExplosionPullbackStrategy',
            max_events=25,
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
                'completion_rate': stats.get('completion_rate', 0)
            }
            
            results.append(result)
            
            print(f"   ✅ Trades: {result['total_trades']}")
            print(f"   ✅ Win Rate: {result['win_rate']:.1f}%")
            print(f"   ✅ Return: {result['total_return_pct']:+.2f}%")
            print(f"   ✅ Completion: {result['completion_rate']:.1f}%")
        else:
            print(f"   ❌ Failed to run backtest")
    
    # Mostrar resumen
    print(f"\n📊 RESUMEN DE OPTIMIZACIÓN")
    print("=" * 70)
    print(f"{'Config':<25} {'Trades':<8} {'WR%':<8} {'Ret%':<10} {'Comp%':<8}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['config_name']:<25} "
              f"{result['total_trades']:<8} "
              f"{result['win_rate']:<8.1f} "
              f"{result['total_return_pct']:<+10.2f} "
              f"{result['completion_rate']:<8.1f}")
    
    # Recomendar mejor configuración
    if results:
        best_config = max(results, key=lambda x: x['total_trades'])
        
        print(f"\n🏆 MEJOR CONFIGURACIÓN: {best_config['config_name']}")
        print("=" * 50)
        print("Parámetros recomendados:")
        for param, value in best_config['params'].items():
            print(f"   {param}: {value}")
        
        print(f"\nResultados:")
        print(f"   📊 Trades generados: {best_config['total_trades']}")
        print(f"   📈 Win Rate: {best_config['win_rate']:.1f}%")
        print(f"   💰 Return: {best_config['total_return_pct']:+.2f}%")
        print(f"   ✅ Completion Rate: {best_config['completion_rate']:.1f}%")

if __name__ == "__main__":
    asyncio.run(test_parameter_combinations())