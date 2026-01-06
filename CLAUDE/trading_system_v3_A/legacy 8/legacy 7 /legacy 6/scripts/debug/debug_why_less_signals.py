#!/usr/bin/env python3
"""
Investigar por qué configuración extrema da MENOS señales
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

async def debug_signal_reduction():
    """Comparar config normal vs extrema para ver por qué da menos señales"""
    
    print("🔍 DEBUGGING: ¿Por qué config extrema da MENOS señales?")
    print("=" * 60)
    
    # Test 1: Config normal (restaurada)  
    print("1️⃣ TESTING CONFIG NORMAL:")
    signals_normal = await test_config("NORMAL", {})
    
    # Test 2: Config extrema
    print("\n2️⃣ TESTING CONFIG EXTREMA:")
    extreme_config = {
        "macdv_volume_threshold": 0.01,
        "dynamic_vol_min": 0.01, 
        "dynamic_vol_max": 50.0,
        "multi_strategy_default_confidence_threshold": 0.001
    }
    signals_extreme = await test_config("EXTREME", extreme_config)
    
    # Comparar
    print(f"\n📊 COMPARACIÓN:")
    print(f"   Config normal: {signals_normal} señales")
    print(f"   Config extrema: {signals_extreme} señales")
    
    if signals_extreme < signals_normal:
        print(f"\n❌ PROBLEMA: Config extrema da MENOS señales")
        print(f"   Posibles causas:")
        print(f"   - Thresholds muy bajos causan falsos negativos")
        print(f"   - Lógica interna que bloquea valores extremos")
        print(f"   - Interdependencias entre parámetros")
        print(f"   - Bugs en validaciones internas")
    else:
        print(f"\n✅ Config extrema funciona correctamente")

async def test_config(name: str, params: dict):
    """Test una configuración y contar señales"""
    
    # Backup and update config si hay parámetros
    if params:
        shutil.copy('config.ini', 'config.ini.backup')
        
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        for key, value in params.items():
            config.set('TESTING_PROFILE', key, str(value))
        
        with open('config.ini', 'w') as f:
            config.write(f)
    
    try:
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        event_bus = AsyncEventBus()
        
        await broker.connect()
        await data_provider.connect()
        
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        # Debug parameters loaded
        print(f"   Volatilidad: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
        if hasattr(engine, 'strategies') and 'macdv_smallcaps' in engine.strategies:
            macdv_params = engine.strategies['macdv_smallcaps']._parameters
            print(f"   MACDV vol_threshold: {macdv_params.get('volume_threshold', 'N/A')}")
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 100)  # Menos barras para debug rápido
        if not bars:
            return 0
        
        signals_count = 0
        
        # Process bars y contar señales 
        for i, bar in enumerate(bars):
            signal = await engine.on_bar(bar)
            if signal:
                signals_count += 1
                print(f"     Signal {signals_count} @ bar {i+1}: {signal.signal_type}")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
        print(f"   Total: {signals_count} señales")
        return signals_count
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0
    finally:
        # Restore config si había backup
        if params and Path('config.ini.backup').exists():
            shutil.move('config.ini.backup', 'config.ini')

if __name__ == "__main__":
    asyncio.run(debug_signal_reduction())