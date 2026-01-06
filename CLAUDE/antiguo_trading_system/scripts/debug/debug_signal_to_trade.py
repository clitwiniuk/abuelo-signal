#!/usr/bin/env python3
"""
Debug script - interceptar específicamente el momento donde las señales se convierten en trades.
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

async def debug_signal_to_trade():
    """Debug específico: interceptar la conversión Signal → Trade"""
    
    print("🔍 DEBUG: INTERCEPTANDO CONVERSIÓN SIGNAL → TRADE")
    print("=" * 70)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
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
        
        print("🧪 Interceptar test con XXII - 100 barras para debuggear conversión...")
        
        # MODIFICAR el SimulationManager temporal para interceptar
        original_place_order = sim_env['broker'].place_order
        
        order_counter = 0
        async def debug_place_order(*args, **kwargs):
            nonlocal order_counter
            order_counter += 1
            print(f"🎯 INTERCEPTED place_order #{order_counter}:")
            print(f"    Args: {args}")
            print(f"    Kwargs: {kwargs}")
            result = await original_place_order(*args, **kwargs)
            print(f"    Result: {result}")
            return result
        
        # Patch the method
        sim_env['broker'].place_order = debug_place_order
        
        # Test con menos barras para seguir mejor
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=100,  # Menos barras para seguir el debug
            strategy_name="multi_strategy"
        )
        
        print(f"\n📊 RESULTADO DEBUG:")
        print(f"   📈 Señales generadas: {result.get('signals_generated', 0)}")
        print(f"   💼 Trades ejecutados: {result.get('trades_executed', 0)}")
        print(f"   🎯 Órdenes interceptadas: {order_counter}")
        
        if order_counter == 0:
            print(f"\n❌ PROBLEMA: No se ejecutó ninguna orden a pesar de las señales")
            print(f"   Esto significa que el problema está ANTES de place_order()")
            print(f"   Posibles causas:")
            print(f"   1. Las señales no llegan al código de ejecución")
            print(f"   2. Hay una condición que evita la ejecución")
            print(f"   3. Error en el flujo de SimulationManager")
        else:
            print(f"\n✅ ÓRDENES EJECUTADAS: {order_counter}")
        
        # Verificar estado del mock broker
        print(f"\n🏦 ESTADO DEL MOCK BROKER:")
        positions = await sim_env['broker'].get_positions()
        print(f"   📍 Posiciones: {positions}")
        
        orders = getattr(sim_env['broker'], '_orders', {})
        print(f"   📋 Órdenes en broker: {len(orders)}")
        
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
    asyncio.run(debug_signal_to_trade())