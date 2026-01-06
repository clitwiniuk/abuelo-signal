#!/usr/bin/env python3
"""
Investigar por qué cambios de parámetros no afectan los resultados
"""

import asyncio
import sys
from pathlib import Path
import configparser

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

async def debug_config_loading():
    """Debug how config parameters are loaded and used"""
    
    print("🔍 DEBUGGING CONFIG PARAMETER LOADING")
    print("=" * 60)
    
    # 1. Check current config values
    print("1️⃣ READING CONFIG.INI VALUES:")
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    testing_section = dict(config['TESTING_PROFILE'])
    print(f"   macdv_volume_threshold: {testing_section.get('macdv_volume_threshold', 'NOT FOUND')}")
    print(f"   macdv_min_conditions: {testing_section.get('macdv_min_conditions', 'NOT FOUND')}")
    print(f"   multi_strategy_default_confidence_threshold: {testing_section.get('multi_strategy_default_confidence_threshold', 'NOT FOUND')}")
    
    # 2. Initialize system and check what values are actually used
    print("\n2️⃣ INITIALIZING SYSTEM:")
    
    broker = MockIBKRAdapter()
    data_provider = CSVDataProvider()
    event_bus = AsyncEventBus()
    
    await broker.connect()
    await data_provider.connect()
    
    # Create multi-strategy engine with debug
    engine = MultiStrategyEngine()
    await engine.initialize(event_bus)
    
    print("   ✅ System initialized")
    
    # 3. Check what parameters the strategies actually received
    print("\n3️⃣ CHECKING STRATEGY PARAMETERS:")
    
    for strategy_name, strategy in engine.strategies.items():
        print(f"\n   🎯 {strategy_name.upper()}:")
        
        if hasattr(strategy, '_parameters'):
            params = strategy._parameters
            print(f"      Parameters object exists: {type(params)}")
            
            # Check key parameters
            key_params = ['volume_threshold', 'min_conditions', 'volume_spike_threshold']
            for param in key_params:
                if param in params:
                    print(f"      {param}: {params[param]} ({type(params[param])})")
                else:
                    print(f"      {param}: NOT FOUND")
        else:
            print(f"      ❌ No _parameters attribute found")
        
        # Check if strategy has hardcoded values
        if hasattr(strategy, '__dict__'):
            strategy_attrs = {k: v for k, v in strategy.__dict__.items() 
                            if 'threshold' in str(k).lower() or 'condition' in str(k).lower()}
            if strategy_attrs:
                print(f"      Potential hardcoded values: {strategy_attrs}")
    
    # 4. Check MultiStrategyEngine parameters
    print(f"\n4️⃣ MULTI-STRATEGY ENGINE PARAMETERS:")
    if hasattr(engine, '_parameters'):
        print(f"   Engine parameters: {engine._parameters}")
    
    if hasattr(engine, 'dynamic_vol_min'):
        print(f"   Dynamic vol min: {engine.dynamic_vol_min}")
    if hasattr(engine, 'dynamic_volume_multiplier'):
        print(f"   Dynamic volume multiplier: {engine.dynamic_volume_multiplier}")
    
    # 5. Test with extreme values to see if they have any effect
    print(f"\n5️⃣ TESTING PARAMETER PROPAGATION:")
    
    # Get one bar to test
    bars = await data_provider.get_bars("XXII", "1 min", 10)
    if bars:
        test_bar = bars[0]
        print(f"   Testing with bar: ${test_bar.close:.2f}, Vol: {test_bar.volume}")
        
        # Process bar and see what happens
        signal = await engine.on_bar(test_bar)
        print(f"   Result: {signal}")
        
        # Check internal state after processing
        for strategy_name, strategy in engine.strategies.items():
            if hasattr(strategy, '_last_analysis'):
                print(f"   {strategy_name} last analysis: {getattr(strategy, '_last_analysis', 'N/A')}")
    
    await broker.disconnect()
    await data_provider.disconnect()
    
    print(f"\n6️⃣ RECOMMENDATIONS:")
    print("   - Check if parameters are being read from correct config sections")
    print("   - Look for hardcoded values in strategy files")
    print("   - Verify parameter propagation from engine to strategies")
    print("   - Check if config changes require system restart")

if __name__ == "__main__":
    asyncio.run(debug_config_loading())