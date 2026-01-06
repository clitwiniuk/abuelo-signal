#!/usr/bin/env python3
"""
FASE 1: Test Simple de Parámetros 
Basado en quick_test_xxii.py que sabemos que funciona
"""

import asyncio
import sys
from pathlib import Path
import configparser
import shutil

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

async def test_config(config_name: str, params: dict):
    """Test una configuración específica"""
    
    print(f"\n🔬 TESTING: {config_name}")
    print(f"📋 Params: vol_th={params['macdv_volume_threshold']}, conf={params['multi_strategy_default_confidence_threshold']}")
    
    # Backup and update config
    shutil.copy('config.ini', 'config.ini.backup')
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Update TESTING_PROFILE
    for key, value in params.items():
        config.set('TESTING_PROFILE', key, str(value))
    
    with open('config.ini', 'w') as f:
        config.write(f)
    
    try:
        # Initialize (same as quick_test_xxii.py)
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        event_bus = AsyncEventBus()
        
        await broker.connect()
        await data_provider.connect()
        
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 1000)
        if not bars:
            return {"error": "No data"}
        
        signals_generated = 0
        
        # Process bars (simplified - just count signals)
        for i, bar in enumerate(bars):
            signal = await engine.on_bar(bar)
            if signal:
                signals_generated += 1
                if signals_generated <= 3:  # Show first 3 signals
                    print(f"   ✅ Signal {signals_generated}: {signal.signal_type} @ ${bar.close:.2f}")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
        result = {
            "config": config_name,
            "signals": signals_generated,
            "params": params
        }
        
        print(f"   📊 Total signals: {signals_generated}")
        return result
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {"error": str(e)}
    finally:
        # Restore config
        if Path('config.ini.backup').exists():
            shutil.move('config.ini.backup', 'config.ini')

async def main():
    print("🚀 FASE 1: TEST SIMPLE DE PARÁMETROS")
    print("🎯 Objetivo: Encontrar configuración que genere MÁS señales")
    print("=" * 60)
    
    # 5 configuraciones de test
    configs = [
        ("ULTRA_PERMISSIVE", {
            "macdv_volume_threshold": 0.1,
            "macdv_volume_spike_threshold": 0.2,
            "macdv_min_conditions": 1,
            "multi_strategy_default_confidence_threshold": 0.1
        }),
        
        ("VERY_PERMISSIVE", {
            "macdv_volume_threshold": 0.3,
            "macdv_volume_spike_threshold": 0.8,
            "macdv_min_conditions": 2,
            "multi_strategy_default_confidence_threshold": 0.2
        }),
        
        ("MODERATE", {
            "macdv_volume_threshold": 0.6,
            "macdv_volume_spike_threshold": 1.2,
            "macdv_min_conditions": 2,
            "multi_strategy_default_confidence_threshold": 0.3
        }),
        
        ("CURRENT", {
            "macdv_volume_threshold": 1.0,
            "macdv_volume_spike_threshold": 1.5,
            "macdv_min_conditions": 3,
            "multi_strategy_default_confidence_threshold": 0.45
        }),
        
        ("CONSERVATIVE", {
            "macdv_volume_threshold": 1.5,
            "macdv_volume_spike_threshold": 2.0,
            "macdv_min_conditions": 4,
            "multi_strategy_default_confidence_threshold": 0.6
        })
    ]
    
    results = []
    
    # Test each configuration
    for config_name, params in configs:
        result = await test_config(config_name, params)
        results.append(result)
        await asyncio.sleep(0.5)  # Small delay
    
    # Analyze results
    print("\n" + "=" * 60)
    print("📊 RESULTADOS FINALES")
    print("=" * 60)
    
    valid_results = [r for r in results if "error" not in r]
    
    if not valid_results:
        print("❌ No valid results")
        return
    
    # Sort by signals generated
    sorted_results = sorted(valid_results, key=lambda x: x['signals'], reverse=True)
    
    print(f"{'Rank':<4} {'Config':<16} {'Signals':<8} {'Vol Threshold':<12} {'Confidence'}")
    print("-" * 60)
    
    for i, result in enumerate(sorted_results):
        config = result['config']
        signals = result['signals']
        vol_th = result['params']['macdv_volume_threshold']
        conf = result['params']['multi_strategy_default_confidence_threshold']
        
        print(f"{i+1:<4} {config:<16} {signals:<8} {vol_th:<12} {conf}")
    
    # Best result
    best = sorted_results[0]
    print(f"\n🏆 GANADOR: {best['config']}")
    print(f"   📊 Señales generadas: {best['signals']}")
    print(f"   ⚙️  Vol threshold: {best['params']['macdv_volume_threshold']}")  
    print(f"   ⚙️  Confidence: {best['params']['multi_strategy_default_confidence_threshold']}")
    
    if best['signals'] > 3:
        print(f"\n✅ EXCELENTE! Esta configuración genera {best['signals']} señales")
        print("   Recomiendo usar estos parámetros.")
    elif best['signals'] > 1:
        print(f"\n✅ BUENO! Esta configuración genera {best['signals']} señales")
        print("   Mejor que la configuración actual.")
    else:
        print(f"\n⚠️  Incluso la mejor configuración solo genera {best['signals']} señal(es)")
        print("   Puede que necesitemos revisar la lógica o usar parámetros aún más permisivos.")

if __name__ == "__main__":
    asyncio.run(main())