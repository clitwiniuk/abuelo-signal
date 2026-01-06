#!/usr/bin/env python3
"""
Script para debuggear el error 'price' en MACDVStrategy.
"""

import asyncio
import logging
import sys
import traceback
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def debug_price_error():
    """Debug para capturar el stack trace completo del error 'price'"""
    
    print("🐛 DEBUG: RASTREANDO ERROR 'PRICE'")
    print("=" * 50)
    
    # Setup logging con más detalle
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Setup
        sim_env = setup_simulation_environment()
        simulation_manager = sim_env['simulation_manager']
        
        # Initialize
        await simulation_manager.initialize(create_sample_data=False)
        await sim_env['broker'].connect()
        await sim_env['data_provider'].connect()
        
        print("🧪 Test con XXII (20 barras) para capturar error...")
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=20,  # Pocas barras para capturar rápido
            strategy_name="multi_strategy"
        )
        
        print(f"\n📊 RESULTADO:")
        print(f"   ✅ Test completado (puede tener errores en logs)")
        
    except Exception as e:
        print(f"❌ Error capturado: {e}")
        print(f"📋 Stack trace completo:")
        traceback.print_exc()
    
    finally:
        try:
            if 'sim_env' in locals():
                await sim_env['broker'].disconnect()
                await sim_env['data_provider'].disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_price_error())