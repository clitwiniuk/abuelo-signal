#!/usr/bin/env python3
"""
Test simple y directo del sistema mock para verificar que todo funciona.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.append(str(Path(__file__).parent.parent))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.interfaces import OrderSide, OrderType

async def main():
    """Test simple del sistema mock"""
    
    print("🚀 TEST SIMPLE DEL SISTEMA MOCK")
    print("=" * 50)
    
    # Setup logging básico
    logging.basicConfig(level=logging.INFO)
    
    try:
        # 1. Crear adapters directamente
        print("📋 1. Creando adapters...")
        
        # Mock broker
        broker = MockIBKRAdapter(data_path="data/csv", simulation_mode=True)
        
        # CSV data provider
        data_provider = CSVDataProvider(data_path="data/csv", auto_load=True)
        
        # 2. Conectar
        print("🔌 2. Conectando...")
        await broker.connect()
        await data_provider.connect()
        
        print(f"   ✅ Broker conectado: {broker.is_connected()}")
        print(f"   ✅ Data provider conectado: {data_provider.is_connected()}")
        
        # 3. Ver símbolos disponibles
        symbols = data_provider.get_available_symbols()
        print(f"📊 3. Símbolos disponibles: {len(symbols)}")
        print(f"   Primeros 10: {symbols[:10]}")
        
        # 4. Test con PLTR
        symbol = "PLTR"
        if symbol in symbols:
            print(f"\n🎯 4. TEST CON {symbol}")
            
            # Obtener datos
            bars = await data_provider.get_bars(symbol, "1 min", 5)
            print(f"   📊 Barras obtenidas: {len(bars)}")
            
            if bars:
                last_bar = bars[-1]
                print(f"   📈 Última barra: ${last_bar.close:.2f} (Vol: {last_bar.volume:,})")
                
                # Obtener precio actual
                price = await broker.get_current_price(symbol)
                print(f"   💰 Precio actual: ${price:.2f}")
                
                # 5. Test de orden
                print(f"\n🛒 5. TEST DE ORDEN")
                order_id = await broker.place_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    quantity=100,
                    order_type=OrderType.MARKET
                )
                print(f"   ✅ Orden colocada: {order_id}")
                
                # Esperar ejecución
                await asyncio.sleep(0.5)
                
                # Ver posiciones
                positions = await broker.get_positions()
                # === Asegurar stop-loss como en ejecución real ===
                from types import SimpleNamespace
                from core.trading_execution_stage import TradingExecutionStage
                stage = TradingExecutionStage(broker=broker, config=SimpleNamespace())
                stage.positions = positions
                await stage.ensure_position_stops()
                
                if symbol in positions:
                    pos = positions[symbol]
                    print(f"   📊 Posición: {pos.quantity} @ ${pos.avg_price:.2f}")
                    print(f"   💰 Valor: ${pos.market_value:.2f}")
                
                # Mostrar órdenes activas con stop
                print("   📑 Órdenes activas:")
                for o in await broker.get_orders():
                    print(f"     - {o.side.name} {o.order_type.name} {o.symbol} @ {o.stop_price or o.price} (status {o.status.name})")
                
                # 6. Estadísticas
                print(f"\n📊 6. ESTADÍSTICAS")
                account = await broker.get_account_info()
                print(f"   💵 Balance: ${account.get('cash', 0):.2f}")
                print(f"   📈 Total Value: ${account.get('total_value', 0):.2f}")
        else:
            print(f"❌ {symbol} no disponible en los datos")
        
        print(f"\n✅ TEST COMPLETADO EXITOSAMENTE!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            if 'broker' in locals():
                await broker.disconnect()
            if 'data_provider' in locals():
                await data_provider.disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())