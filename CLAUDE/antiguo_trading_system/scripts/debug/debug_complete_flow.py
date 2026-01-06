#!/usr/bin/env python3
"""
Debug script - añadir logs específicos al flujo completo para rastrear dónde se pierde la señal.
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

async def debug_complete_flow():
    """Debug completo del flujo Signal → Order → Trade"""
    
    print("🔍 DEBUG: FLUJO COMPLETO SIGNAL → ORDER → TRADE")
    print("=" * 70)
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,  # FULL debug
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
        
        print("🧪 Debug completo con 50 barras - rastrear cada paso...")
        
        # INTERCEPTAR test_strategy_on_symbol para añadir logs
        original_test = simulation_manager.test_strategy_on_symbol
        
        async def debug_test_strategy(*args, **kwargs):
            print(f"\n🎯 INTERCEPTED test_strategy_on_symbol:")
            print(f"    Args: {args}")
            print(f"    Kwargs: {kwargs}")
            
            # Patchear la función para añadir más logs
            result = await original_test(*args, **kwargs)
            print(f"    Result from test_strategy: {result}")
            return result
        
        # Patch
        simulation_manager.test_strategy_on_symbol = debug_test_strategy
        
        # Test más pequeño para rastrear mejor
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=50,
            strategy_name="multi_strategy"
        )
        
        print(f"\n📊 RESULTADO FINAL:")
        print(f"   📈 Señales generadas: {result.get('signals_generated', 0)}")
        print(f"   💼 Trades ejecutados: {result.get('trades_executed', 0)}")
        
        # Verificar estado interno
        print(f"\n🔧 ESTADO INTERNO:")
        print(f"   🏦 Broker orders: {getattr(sim_env['broker'], '_orders', {})}")
        print(f"   🏦 Broker trades: {getattr(sim_env['broker'], '_trades', [])}")
        
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
    asyncio.run(debug_complete_flow())