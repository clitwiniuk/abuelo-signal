#!/usr/bin/env python3
"""
Debug script - replicar el test del usuario con 500 barras para encontrar por qué no se ejecutan trades.
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

async def debug_500_bars():
    """Replicar exactamente el test del usuario con 500 barras"""
    
    print("🔍 DEBUG: REPLICANDO TEST CON 500 BARRAS")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,  # INFO para ver las señales claramente
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
        
        print("🧪 Test con XXII - 500 barras (replicar el comportamiento del usuario)...")
        print("")
        
        # Test con 500 barras como el usuario
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="XXII",
            timeframe="1 min",
            bars_count=500,  # Igual que el usuario
            strategy_name="multi_strategy"
        )
        
        print(f"\n📊 RESULTADO DETALLADO:")
        print(f"   📈 Señales generadas: {result.get('signals_generated', 0)}")
        print(f"   💼 Trades ejecutados: {result.get('trades_executed', 0)}")
        print(f"   💰 PnL Final: ${result.get('final_stats', {}).get('total_pnl', 0):.2f}")
        
        # Verificar estado del mock broker DETALLADAMENTE
        print(f"\n🏦 ESTADO DETALLADO DEL MOCK BROKER:")
        
        # Posiciones
        positions = await sim_env['broker'].get_positions()
        print(f"   📍 Posiciones activas: {len(positions)}")
        for symbol, position in positions.items():
            print(f"      📄 {symbol}: {position.quantity} shares @ ${position.avg_price:.2f}")
        
        # Órdenes - acceder a los atributos internos del mock broker
        mock_broker = sim_env['broker']
        total_orders = getattr(mock_broker, '_order_counter', 0)
        print(f"   📋 Total órdenes creadas: {total_orders}")
        
        # Órdenes almacenadas
        orders = getattr(mock_broker, '_orders', {})
        print(f"   📦 Órdenes almacenadas: {len(orders)}")
        
        # Si hay órdenes, mostrar detalles
        if orders:
            print(f"   🔍 DETALLES DE ÓRDENES:")
            for order_id, order in list(orders.items())[:5]:  # Mostrar primeras 5
                status = getattr(order, 'status', 'UNKNOWN')
                side = getattr(order, 'side', 'UNKNOWN')
                quantity = getattr(order, 'quantity', 0)
                price = getattr(order, 'fill_price', getattr(order, 'price', 'N/A'))
                print(f"      📄 ID:{order_id} | {order.symbol} {side.value if hasattr(side, 'value') else side} {quantity} @ ${price}")
        
        # Estado interno del broker
        cash = getattr(mock_broker, '_cash', 'Unknown')
        print(f"   💵 Cash disponible: ${cash}")
        
        # Historial de trades
        trades = getattr(mock_broker, '_trades', [])
        print(f"   📈 Trades en historial: {len(trades)}")
        if trades:
            print(f"   🔍 ÚLTIMOS TRADES:")
            for trade in trades[-3:]:  # Mostrar últimos 3
                print(f"      💱 {trade}")
        
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
    asyncio.run(debug_500_bars())