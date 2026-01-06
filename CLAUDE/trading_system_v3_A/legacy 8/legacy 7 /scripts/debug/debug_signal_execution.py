#!/usr/bin/env python3
"""
Debug script para analizar por qué las señales no se ejecutan como trades.
"""

import asyncio
import logging
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def debug_signal_execution():
    """Debug específico para rastrear la ejecución de señales"""
    
    print("🔍 DEBUG: RASTREANDO EJECUCIÓN DE SEÑALES")
    print("=" * 60)
    
    # Setup logging más detallado
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
        
        print("🧪 Test ESPECÍFICO con XXII para rastrear la cadena Signal -> Trade...")
        print("")
        
        # Test con pocas barras para seguir la ejecución paso a paso
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=50,  # Pocas barras para debugging
            strategy_name="multi_strategy"
        )
        
        print(f"\n📊 RESULTADO DETALLADO:")
        print(f"   ✅ Resultado completo: {result}")
        
        # Verificar estado del mock broker
        print(f"\n🏦 ESTADO DEL MOCK BROKER:")
        positions = await sim_env['broker'].get_positions()
        print(f"   📍 Posiciones: {positions}")
        
        orders = getattr(sim_env['broker'], '_orders', {})
        print(f"   📋 Órdenes: {len(orders)}")
        
        # Verificar si hay órdenes ejecutadas
        executed_orders = [order for order in orders.values() if getattr(order, 'status', '') == 'FILLED']
        print(f"   ✅ Órdenes ejecutadas: {len(executed_orders)}")
        
        if executed_orders:
            for order in executed_orders[:3]:  # Mostrar las primeras 3
                print(f"      📄 Orden: {order.symbol} {order.side.value} {order.quantity}@{getattr(order, 'fill_price', 'N/A')}")
        
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
    asyncio.run(debug_signal_execution())