#!/usr/bin/env python3
"""
Optimize Improved Strategy Parameters
=====================================

Prueba diferentes configuraciones de parámetros para encontrar 
la combinación óptima para la estrategia mejorada.
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def optimize_improved_strategy():
    print("🔬 OPTIMIZING IMPROVED STRATEGY PARAMETERS")
    print("=" * 70)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    # Configuraciones a probar (de conservadora a agresiva)
    test_configs = [
        {
            'name': 'Ultra Conservative (High Quality)',
            'params': {
                'volume_threshold': 4.0,          # Muy alta explosión requerida
                'momentum_threshold': 0.015,       # 1.5% momentum mínimo
                'min_volume_absolute': 50000,      # Alto volumen absoluto
                'max_daily_signals': 3,            # Solo 3 señales por día
                'cooldown_minutes': 30,            # Cooldown largo
            }
        },
        {
            'name': 'Conservative (Quality Focus)',
            'params': {
                'volume_threshold': 3.0,          # Alta explosión
                'momentum_threshold': 0.012,       # 1.2% momentum
                'min_volume_absolute': 25000,      # Alto volumen
                'max_daily_signals': 5,            # 5 señales por día
                'cooldown_minutes': 20,            # Cooldown medio
            }
        },
        {
            'name': 'Balanced (Current + tweaks)',
            'params': {
                'volume_threshold': 2.0,          # Explosión moderada
                'momentum_threshold': 0.010,       # 1.0% momentum
                'min_volume_absolute': 15000,      # Volumen moderado
                'max_daily_signals': 6,            # 6 señales por día
                'cooldown_minutes': 15,            # Cooldown actual
                'trend_confirmation_bars': 3,      # Menos confirmación de tendencia
            }
        },
        {
            'name': 'Slightly Aggressive',
            'params': {
                'volume_threshold': 1.8,          # Explosión menor
                'momentum_threshold': 0.008,       # 0.8% momentum
                'min_volume_absolute': 10000,      # Menos volumen requerido
                'max_daily_signals': 10,           # Más señales
                'cooldown_minutes': 10,            # Cooldown corto
                'trend_confirmation_bars': 3,      
            }
        },
        {
            'name': 'More Aggressive (Catch More)',
            'params': {
                'volume_threshold': 1.5,          # Menor explosión
                'momentum_threshold': 0.006,       # 0.6% momentum
                'min_volume_absolute': 5000,       # Bajo volumen absoluto
                'max_daily_signals': 12,           # Muchas señales
                'cooldown_minutes': 5,             # Cooldown muy corto
                'trend_confirmation_bars': 2,      # Poca confirmación
            }
        }
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n📊 TESTING: {config['name']}")
        print("-" * 50)
        print(f"   Volume threshold: {config['params'].get('volume_threshold', 'default')}")
        print(f"   Momentum threshold: {config['params'].get('momentum_threshold', 'default')}")
        print(f"   Max daily signals: {config['params'].get('max_daily_signals', 'default')}")
        
        success = await backtester.run_mass_backtest(
            'ImprovedSimpleExplosionStrategy',
            max_events=50,
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
            print(f"   ✅ Win Rate: {result['win_rate']:.1f}%")
            print(f"   ✅ Return: {result['total_return_pct']:+.2f}%")
            print(f"   ✅ Profit Factor: {result['profit_factor']:.2f}")
        else:
            print(f"   ❌ Failed to run backtest")
    
    # Mostrar resumen
    print(f"\n📊 OPTIMIZATION SUMMARY")
    print("=" * 70)
    print(f"{'Config':<25} {'Trades':<7} {'WR%':<6} {'Ret%':<8} {'PF':<6} {'Comp%':<6}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['config_name'][:24]:<25} "
              f"{result['total_trades']:<7} "
              f"{result['win_rate']:<6.1f} "
              f"{result['total_return_pct']:<+8.2f} "
              f"{result['profit_factor']:<6.2f} "
              f"{result['completion_rate']:<6.1f}")
    
    # Encontrar mejor configuración
    if results:
        # Priorizar: 1) Return positivo, 2) Win rate alto, 3) Profit factor > 1
        best_config = max(results, key=lambda x: (
            x['total_return_pct'] > 0,          # Prioridad 1: Retorno positivo
            x['win_rate'],                      # Prioridad 2: Win rate
            x['profit_factor'],                 # Prioridad 3: Profit factor
            x['total_trades']                   # Prioridad 4: Actividad
        ))
        
        print(f"\n🏆 BEST CONFIGURATION: {best_config['config_name']}")
        print("=" * 50)
        print("Parámetros recomendados:")
        for param, value in best_config['params'].items():
            print(f"   {param}: {value}")
        
        print(f"\nResultados:")
        print(f"   📊 Trades: {best_config['total_trades']}")
        print(f"   📈 Win Rate: {best_config['win_rate']:.1f}%")
        print(f"   💰 Return: {best_config['total_return_pct']:+.2f}%")
        print(f"   🎯 Profit Factor: {best_config['profit_factor']:.2f}")
        
        # Recomendaciones
        if best_config['total_return_pct'] > 0:
            print(f"\n🎉 ¡FOUND PROFITABLE CONFIG!")
        else:
            print(f"\n⚠️  Still not profitable, but this is the best configuration tested.")
            print(f"   Consider: Different approach or more data needed.")

if __name__ == "__main__":
    asyncio.run(optimize_improved_strategy())