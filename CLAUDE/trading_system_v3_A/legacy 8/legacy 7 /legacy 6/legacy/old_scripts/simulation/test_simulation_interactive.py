#!/usr/bin/env python3
"""
Script de prueba interactivo para mostrar cómo funciona el sistema con el mock.
Ejecuta automáticamente varias pruebas para demostrar el funcionamiento.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio padre al path para imports
sys.path.append(str(Path(__file__).parent.parent))

from config.simulation_config import setup_simulation_environment

async def main():
    """Ejecuta varias pruebas automáticas del sistema"""
    
    print("🚀 DEMO AUTOMATIZADA DEL TRADING SYSTEM CON MOCK")
    print("=" * 70)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 1. Setup entorno de simulación
        print("📋 1. Configurando entorno de simulación...")
        sim_env = setup_simulation_environment()
        
        broker = sim_env['broker']
        data_provider = sim_env['data_provider']
        simulation_manager = sim_env['simulation_manager']
        
        # 2. Inicializar simulación
        print("🔧 2. Inicializando simulación...")
        await simulation_manager.initialize(create_sample_data=False)
        
        # 2.1. Conectar adapters explícitamente
        await broker.connect()
        await data_provider.connect()
        
        # 3. Verificar conexiones
        print(f"✅ 3. Verificación de conexiones:")
        print(f"   - Broker conectado: {broker.is_connected()}")
        print(f"   - Data provider conectado: {data_provider.is_connected()}")
        
        # 4. Ver símbolos disponibles
        available_symbols = data_provider.get_available_symbols()
        print(f"📊 4. Datos disponibles: {len(available_symbols)} símbolos")
        print(f"   Símbolos: {available_symbols[:10]}...")
        
        # 5. Test básico con PLTR
        print(f"\n🎯 5. TEST BÁSICO CON PLTR")
        print("-" * 50)
        await test_pltr_basic(broker, data_provider)
        
        # 6. Test de órdenes
        print(f"\n🛒 6. TEST DE ÓRDENES")
        print("-" * 50)
        await test_orders(broker)
        
        # 7. Test de estrategia
        print(f"\n📈 7. TEST DE ESTRATEGIA")
        print("-" * 50)
        await test_strategy(simulation_manager)
        
        # 8. Estadísticas finales
        print(f"\n📊 8. ESTADÍSTICAS FINALES")
        print("-" * 50)
        show_final_stats(broker)
        
        print(f"\n✅ DEMO COMPLETADA EXITOSAMENTE!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Error en demo: {e}")
    
    finally:
        # Cleanup connections
        try:
            if 'broker' in locals():
                await broker.disconnect()
            if 'data_provider' in locals():
                await data_provider.disconnect()
            print("🔌 Conexiones cerradas")
        except:
            pass

async def test_pltr_basic(broker, data_provider):
    """Test básico con PLTR"""
    symbol = "PLTR"
    
    try:
        # Obtener datos históricos
        print(f"📊 Obteniendo datos históricos de {symbol}...")
        bars = await data_provider.get_bars(symbol, "1 min", 10)
        
        if bars and len(bars) > 0:
            print(f"✅ Obtenidos {len(bars)} barras de {symbol}")
            last_bar = bars[-1]
            print(f"   Última barra: OHLC = ${last_bar.open:.2f}/${last_bar.high:.2f}/${last_bar.low:.2f}/${last_bar.close:.2f}")
            print(f"   Volumen: {last_bar.volume:,}")
            
            # Obtener precio actual
            price = await broker.get_current_price(symbol)
            print(f"💰 Precio actual de {symbol}: ${price:.2f}")
        else:
            print(f"❌ No se pudieron obtener datos de {symbol}")
            
    except Exception as e:
        print(f"❌ Error en test básico: {e}")

async def test_orders(broker):
    """Test de colocación de órdenes"""
    symbol = "PLTR"
    
    try:
        from core.interfaces import OrderSide, OrderType
        
        # Test orden de compra
        print(f"🛒 Colocando orden de compra de 100 {symbol}...")
        order_id = await broker.place_order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        print(f"✅ Orden de compra colocada: ID {order_id}")
        
        # Esperar un poco para simulación
        await asyncio.sleep(0.5)
        
        # Ver posiciones
        positions = await broker.get_positions()
        if symbol in positions:
            pos = positions[symbol]
            print(f"📊 Posición: {pos.quantity} acciones @ ${pos.avg_price:.2f}")
            print(f"💰 Valor: ${pos.market_value:.2f}")
            print(f"📈 P&L: ${pos.unrealized_pnl:.2f}")
        
        # Test orden de venta
        print(f"💸 Colocando orden de venta de 50 {symbol}...")
        sell_order_id = await broker.place_order(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=50,
            order_type=OrderType.MARKET
        )
        print(f"✅ Orden de venta colocada: ID {sell_order_id}")
        
        await asyncio.sleep(0.5)
        
        # Ver posiciones actualizadas
        positions = await broker.get_positions()
        if symbol in positions:
            pos = positions[symbol]
            print(f"📊 Posición actualizada: {pos.quantity} acciones @ ${pos.avg_price:.2f}")
        
    except Exception as e:
        print(f"❌ Error en test de órdenes: {e}")

async def test_strategy(simulation_manager):
    """Test de estrategia en simulación"""
    
    try:
        print(f"🎯 Ejecutando test de estrategia SIMPLE en PLTR...")
        print(f"    📋 Estrategia: Compra cada 40 barras, vende cada 40 barras (offset +20)")
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol="PLTR",
            timeframe="1 min",
            bars_count=200,  # Aproximadamente 3.5 horas de datos
            strategy_name="simple"  # Usar estrategia simple que sí ejecuta trades
        )
        
        print(f"📊 RESULTADOS DE ESTRATEGIA:")
        print(f"   ✅ Trades ejecutados: {result.get('trades_executed', 0)}")
        
        final_stats = result.get('final_stats', {})
        print(f"   💰 P&L Total: ${final_stats.get('total_pnl', 0):.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.1%}")
        print(f"   📉 Max Drawdown: ${final_stats.get('max_drawdown', 0):.2f}")
        print(f"   ⏱️ Duración: {result.get('test_duration', 'N/A')}")
        
        trades = final_stats.get('trades', [])
        if trades:
            print(f"   📋 Ejemplo de trade:")
            trade = trades[0]
            print(f"      {trade.get('symbol', 'N/A')} - {trade.get('side', 'N/A')} {trade.get('quantity', 0)} @ ${trade.get('price', 0):.2f}")
        
    except Exception as e:
        print(f"❌ Error en test de estrategia: {e}")

def show_final_stats(broker):
    """Muestra estadísticas finales del broker"""
    
    try:
        stats = broker.get_performance_stats()
        
        print(f"📊 ESTADÍSTICAS FINALES DEL BROKER MOCK:")
        print(f"   💰 P&L Total: ${stats.get('total_pnl', 0):.2f}")
        print(f"   ✅ Trades Ejecutados: {stats.get('trades_executed', 0)}")
        print(f"   💵 Balance Actual: ${stats.get('current_balance', 10000):.2f}")
        print(f"   🎯 Win Rate: {stats.get('win_rate', 0):.1%}")
        
        # Posiciones finales
        positions = getattr(broker, '_positions', {})
        print(f"   📊 Posiciones Abiertas: {len(positions)}")
        
        if positions:
            print(f"   💼 Detalle:")
            for symbol, pos in positions.items():
                pnl_emoji = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
                print(f"      {symbol}: {pos.quantity} @ ${pos.avg_price:.2f} {pnl_emoji} ${pos.unrealized_pnl:.2f}")
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")

if __name__ == "__main__":
    asyncio.run(main())