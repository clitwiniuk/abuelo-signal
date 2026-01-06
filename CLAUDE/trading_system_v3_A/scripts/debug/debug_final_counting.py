#!/usr/bin/env python3
"""
Debug FINAL - verificar exactamente el contador de trades y señales
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def debug_final_counting():
    """Debug del contador final"""
    
    print("🔍 DEBUG FINAL: CONTADORES DE SIGNALS Y TRADES")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,  # Menos logs para clarity
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
        
        print("✅ Sistema inicializado")
        
        # Test simple con LOBO que sabemos genera señales
        print("\n🎯 Testing LOBO con 100 barras...")
        
        # Verificar estado inicial del broker
        initial_stats = sim_env['broker'].get_performance_stats()
        print(f"📊 Estado inicial broker: {initial_stats['trades_executed']} trades")
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="LOBO",
            timeframe="1 min",
            bars_count=100,
            strategy_name="multi_strategy",
            realistic_timing=False
        )
        
        # Verificar estado final del broker
        final_stats = sim_env['broker'].get_performance_stats()
        print(f"📊 Estado final broker: {final_stats['trades_executed']} trades")
        
        # DEBUG: Verificar si es la misma instancia
        print(f"🔍 Broker sim_env ID: {id(sim_env['broker'])}")
        print(f"🔍 Broker simulation_manager ID: {id(simulation_manager.mock_broker)}")
        print(f"🔍 Are they the same? {sim_env['broker'] is simulation_manager.mock_broker}")
        
        # También verificar directamente las variables internas
        print(f"🔧 Direct broker._trades_executed: {getattr(sim_env['broker'], '_trades_executed', 'NOT_FOUND')}")
        print(f"🔧 Direct broker._orders length: {len(getattr(sim_env['broker'], '_orders', {}))}")
        print(f"🔧 Direct broker._positions length: {len(getattr(sim_env['broker'], '_positions', {}))}")
        
        print(f"\n📊 RESULTADO DEL TEST:")
        print(f"   📈 signals_generated (retornado): {result.get('signals_generated', 'ERROR')}")
        print(f"   💼 trades_executed (retornado): {result.get('trades_executed', 'ERROR')}")
        print(f"   📊 bars_analyzed: {result.get('bars_analyzed', 'ERROR')}")
        
        print(f"\n🏦 BROKER STATS DIRECTOS:")
        broker_stats = sim_env['broker'].get_performance_stats()
        print(f"   💰 trades_executed: {broker_stats.get('trades_executed', 'ERROR')}")
        print(f"   💵 total_value: ${broker_stats.get('total_value', 0):.2f}")
        
        # Verificar órdenes directamente
        orders = getattr(sim_env['broker'], '_orders', {})
        print(f"\n📋 ÓRDENES EN BROKER:")
        print(f"   📝 Total órdenes: {len(orders)}")
        for order_id, order in orders.items():
            print(f"   📄 {order_id}: {order}")
        
        # Si hay discrepancia, investigar más
        returned_trades = result.get('trades_executed', 0)
        broker_trades = broker_stats.get('trades_executed', 0)
        
        if returned_trades != broker_trades:
            print(f"\n❌ DISCREPANCIA ENCONTRADA!")
            print(f"   Resultado retornado: {returned_trades} trades")
            print(f"   Broker real: {broker_trades} trades")
            print(f"   Órdenes en dict: {len(orders)}")
        else:
            print(f"\n✅ CONTADORES COINCIDEN: {returned_trades} trades")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            if 'sim_env' in locals():
                await sim_env['broker'].disconnect()
                await sim_env['data_provider'].disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_final_counting())