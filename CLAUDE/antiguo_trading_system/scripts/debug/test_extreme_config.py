#!/usr/bin/env python3
"""
Test con configuración EXTREMA para verificar que los parámetros SÍ afectan
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

async def test_extreme_config():
    """Test con configuración extrema para ver si ahora sí cambian los resultados"""
    
    print("🔥 TEST EXTREMO - CONFIGURACIÓN ULTRA PERMISIVA")
    print("=" * 60)
    
    # Backup config
    shutil.copy('config.ini', 'config.ini.backup')
    
    # Crear configuración EXTREMA
    extreme_config = {
        "macdv_volume_threshold": 0.01,      # Súper bajo  
        "macdv_volume_spike_threshold": 0.01, # Súper bajo
        "macdv_min_conditions": 1,           # Mínimo
        "dynamic_vol_min": 0.01,             # NUEVO: Súper bajo
        "dynamic_vol_max": 50.0,             # NUEVO: Súper alto
        "gap_go_min_gap_percent": 0.1,       # Casi cualquier gap
        "gap_go_volume_multiplier": 0.01,    # Casi sin volumen
        "orb_volume_spike_threshold": 0.01,  # Súper bajo
        "orb_min_conditions": 1,             # Mínimo
        "pmh_min_premarket_volume": 100,     # Súper bajo
        "pmh_breakout_volume_multiplier": 0.01, # Súper bajo
        "multi_strategy_default_confidence_threshold": 0.001  # Acepta todo
    }
    
    print("📋 CONFIGURACIÓN EXTREMA:")
    for key, value in extreme_config.items():
        print(f"   {key}: {value}")
    
    # Update config
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    for key, value in extreme_config.items():
        config.set('TESTING_PROFILE', key, str(value))
    
    with open('config.ini', 'w') as f:
        config.write(f)
    
    try:
        # Test with extreme config
        print(f"\n🧪 TESTING CON CONFIGURACIÓN EXTREMA...")
        
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        event_bus = AsyncEventBus()
        
        await broker.connect()
        await data_provider.connect()
        
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        # Check what volatility values were loaded
        print(f"   📊 Volatilidad cargada: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 200)  # Menos barras para test rápido
        if not bars:
            print("❌ No data")
            return
        
        signals_generated = 0
        
        # Process bars
        for i, bar in enumerate(bars):
            signal = await engine.on_bar(bar)
            if signal:
                signals_generated += 1
                if signals_generated <= 5:  # Show first 5 signals
                    print(f"   ✅ Signal {signals_generated}: {signal.signal_type} @ ${bar.close:.2f}")
        
        print(f"\n📊 RESULTADO EXTREMO: {signals_generated} señales generadas")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
        return signals_generated
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        # Restore config
        if Path('config.ini.backup').exists():
            shutil.move('config.ini.backup', 'config.ini')

async def main():
    print("🔍 VERIFICANDO SI ARREGLO DE PARÁMETROS HARDCODEADOS FUNCIONÓ")
    
    # Test extreme config
    extreme_signals = await test_extreme_config()
    
    print(f"\n📊 RESULTADO FINAL:")
    print(f"   Señales con config extrema: {extreme_signals}")
    
    if extreme_signals > 3:
        print("   ✅ ¡EXCELENTE! Los parámetros SÍ afectan los resultados ahora")
        print("   El arreglo de hardcoded values funcionó correctamente")
    elif extreme_signals == 3:
        print("   ⚠️  Mismo resultado que antes. Puede que haya más hardcoded values")
    else:
        print("   ❌ Menos señales que antes. Hay algún problema")

if __name__ == "__main__":
    asyncio.run(main())