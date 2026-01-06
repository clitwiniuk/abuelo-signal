#!/usr/bin/env python3
"""
Script para ejecutar el trading system con el mock adapter usando datos CSV existentes.
Este script usa los datos que ya has descargado y simula el trading sin conexión a IBKR.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.simulation_config import setup_simulation_environment

async def main():
    """Ejecuta el sistema de trading en modo simulación"""
    
    print("🚀 INICIANDO TRADING SYSTEM EN MODO SIMULACIÓN")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,  # Cambiar a DEBUG para ver más detalles
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 1. Setup entorno de simulación
        print("📋 Configurando entorno de simulación...")
        sim_env = setup_simulation_environment()
        
        broker = sim_env['broker']
        data_provider = sim_env['data_provider']
        config = sim_env['config']
        simulation_manager = sim_env['simulation_manager']
        
        # 2. Inicializar simulación (sin crear datos sintéticos, usamos los reales)
        print("🔧 Inicializando simulación con datos existentes...")
        await simulation_manager.initialize(create_sample_data=False)
        
        # 2.1. Conectar adapters explícitamente
        await broker.connect()
        await data_provider.connect()
        
        # 3. Verificar conexiones
        print(f"✅ Broker conectado: {broker.is_connected()}")
        print(f"✅ Data provider conectado: {data_provider.is_connected()}")
        
        # 4. Ver qué símbolos tenemos disponibles
        available_symbols = data_provider.get_available_symbols()
        print(f"📊 Símbolos disponibles: {len(available_symbols)}")
        print(f"   {available_symbols[:10]}...")  # Mostrar solo los primeros 10
        
        # 5. Ejecutar menú interactivo
        await run_simulation_menu(simulation_manager, broker, data_provider, available_symbols)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Error en simulación: {e}")
    
    print("👋 Simulación terminada")

async def run_simulation_menu(simulation_manager, broker, data_provider, available_symbols):
    """Menú interactivo para la simulación"""
    
    while True:
        print("\n" + "=" * 60)
        print("🎮 MENÚ DE SIMULACIÓN")
        print("=" * 60)
        print("1. Test rápido con un símbolo")
        print("2. Test de estrategia en símbolo específico")
        print("3. Backtest completo (múltiples símbolos)")
        print("4. Ver estadísticas del broker mock")
        print("5. Probar órdenes manuales")
        print("6. Ver datos disponibles")
        print("0. Salir")
        print("=" * 60)
        
        try:
            opcion = input("🎯 Selecciona una opción (0-6): ").strip()
            
            if opcion == "0":
                break
                
            elif opcion == "1":
                await test_quick_symbol(simulation_manager, available_symbols)
                
            elif opcion == "2":
                await test_specific_symbol(simulation_manager, available_symbols)
                
            elif opcion == "3":
                await run_full_backtest(simulation_manager, available_symbols)
                
            elif opcion == "4":
                await show_broker_stats(broker)
                
            elif opcion == "5":
                await test_manual_orders(broker, available_symbols)
                
            elif opcion == "6":
                show_available_data(data_provider, available_symbols)
                
            else:
                print("❌ Opción no válida")
                
            input("\n📱 Presiona Enter para continuar...")
            
        except KeyboardInterrupt:
            print("\n👋 Saliendo...")
            break
        except EOFError:
            print("\n👋 Saliendo...")
            break

async def test_quick_symbol(simulation_manager, available_symbols):
    """Test rápido con un símbolo aleatorio"""
    if not available_symbols:
        print("❌ No hay símbolos disponibles")
        return
        
    # Usar PLTR si está disponible, sino el primero
    symbol = "PLTR" if "PLTR" in available_symbols else available_symbols[0]
    
    print(f"\n🎯 Test rápido con {symbol}")
    print("⏳ Ejecutando...")
    
    try:
        result = await simulation_manager.test_strategy_on_symbol(
            symbol=symbol,
            timeframe="1 min",
            bars_count=300,  # 5 horas de datos
            strategy_name="multi_strategy"  # Usar multi-estrategia
        )
        
        # Get enhanced stats from the updated broker
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        
        # Extract P&L information 
        total_pnl = final_stats.get('total_pnl', 0)
        realized_pnl = final_stats.get('realized_pnl', 0)
        total_pnl_pct = final_stats.get('total_pnl_pct', 0)
        
        print(f"\n📊 RESULTADOS PARA {symbol}:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        if realized_pnl != 0 or total_pnl != 0:
            print(f"   💰 P&L Total: ${total_pnl:.2f} ({total_pnl_pct:.2f}%)")
            print(f"   💵 P&L Realizado: ${realized_pnl:.2f}")
        else:
            print(f"   💰 P&L Final: $0.00")
            
        print(f"   💼 Portfolio Value: ${final_stats.get('total_value', 10000):.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        print(f"   💸 Comisiones pagadas: ${final_stats.get('total_commissions', 0):.2f}")
        
        # Mostrar reporte detallado de trades si hay trades ejecutados
        if trades_executed > 0:
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO DE TRADES")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
        
    except Exception as e:
        print(f"❌ Error en test: {e}")

async def test_specific_symbol(simulation_manager, available_symbols):
    """Test de estrategia en símbolo específico"""
    if not available_symbols:
        print("❌ No hay símbolos disponibles")
        return
        
    print(f"\n📋 Símbolos disponibles:")
    for i, symbol in enumerate(available_symbols[:20], 1):  # Mostrar solo 20
        print(f"   {i:2d}. {symbol}")
    
    try:
        symbol_input = input("\n📝 Ingresa el símbolo (ej: PLTR): ").strip().upper()
        
        if symbol_input not in available_symbols:
            print(f"❌ {symbol_input} no está disponible en los datos")
            return
            
        days_input = input("📅 Número de días hacia atrás para test (default 7 días): ").strip()
        days_back = int(days_input) if days_input.isdigit() else 7
        # Convertir días a barras aproximadas (390 barras de trading por día)
        bars_count = days_back * 390
        
        print(f"\n🎯 Testando {symbol_input} con {days_back} días de datos ({bars_count} barras aprox)...")
        print("⏳ Ejecutando...")
        
        result = await simulation_manager.test_strategy_on_symbol(
            symbol=symbol_input,
            timeframe="1 min",
            bars_count=bars_count,
            strategy_name="multi_strategy",  # Usar multi-estrategia
            days_back=days_back  # Pasar los días hacia atrás
        )
        
        # Get enhanced stats from the updated broker
        final_stats = result.get('final_stats', {})
        trades_executed = result.get('trades_executed', 0)
        
        # Extract P&L information 
        total_pnl = final_stats.get('total_pnl', 0)
        realized_pnl = final_stats.get('realized_pnl', 0)
        unrealized_pnl = final_stats.get('unrealized_pnl', 0)
        total_pnl_pct = final_stats.get('total_pnl_pct', 0)
        
        print(f"\n📊 RESULTADOS PARA {symbol_input}:")
        print(f"   ✅ Trades ejecutados: {trades_executed}")
        if realized_pnl != 0 or total_pnl != 0:
            print(f"   💰 P&L Total: ${total_pnl:.2f} ({total_pnl_pct:.2f}%)")
            print(f"   💵 P&L Realizado: ${realized_pnl:.2f}")
            print(f"   📊 P&L No Realizado: ${unrealized_pnl:.2f}")
        else:
            print(f"   💰 P&L Final: $0.00")
            
        print(f"   💼 Portfolio Value: ${final_stats.get('total_value', 10000):.2f}")
        print(f"   💵 Cash: ${final_stats.get('cash', 10000):.2f}")
        print(f"   📈 Win Rate: {final_stats.get('win_rate', 0):.2f}%")
        print(f"   📉 Max Drawdown: ${final_stats.get('max_drawdown', 0):.2f}")
        print(f"   💸 Comisiones pagadas: ${final_stats.get('total_commissions', 0):.2f}")
        
        # Mostrar reporte detallado de trades si hay trades ejecutados
        if trades_executed > 0:
            print(f"\n" + "="*80)
            print("📋 REPORTE DETALLADO DE TRADES")
            print("="*80)
            simulation_manager.mock_broker.print_detailed_trade_report()
        
    except ValueError:
        print("❌ Número de días inválido")
    except Exception as e:
        print(f"❌ Error en test: {e}")

async def run_full_backtest(simulation_manager, available_symbols):
    """Backtest completo con múltiples símbolos"""
    if not available_symbols:
        print("❌ No hay símbolos disponibles")
        return
        
    print(f"\n🚀 BACKTEST COMPLETO")
    
    # Seleccionar símbolos para backtest
    suggested_symbols = ["PLTR", "TSLA", "NVDA", "AMD", "MVIS"]
    test_symbols = [s for s in suggested_symbols if s in available_symbols]
    
    if not test_symbols:
        test_symbols = available_symbols[:5]  # Tomar los primeros 5
    
    print(f"📋 Símbolos seleccionados: {test_symbols}")
    
    # Fechas para backtest
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3)  # 3 días de datos
    
    print(f"📅 Período: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
    print("⏳ Ejecutando backtest...")
    
    try:
        results = await simulation_manager.run_backtest(
            symbols=test_symbols,
            start_date=start_date,
            end_date=end_date,
            strategy_config={
                'strategy': 'multi_strategy',
                'timeframe': '1 min'
            }
        )
        
        perf = results.get('performance', {})
        print(f"\n📊 RESULTADOS DEL BACKTEST:")
        print(f"   💰 Total Return: {perf.get('total_return_pct', 0):.2f}%")
        print(f"   📉 Max Drawdown: {perf.get('max_drawdown_pct', 0):.2f}%")
        print(f"   📈 Sharpe Ratio: {perf.get('sharpe_ratio', 0):.2f}")
        print(f"   ✅ Total Trades: {perf.get('total_trades', 0)}")
        print(f"   🎯 Win Rate: {perf.get('win_rate', 0):.1%}")
        
    except Exception as e:
        print(f"❌ Error en backtest: {e}")

async def show_broker_stats(broker):
    """Muestra estadísticas del broker mock"""
    print(f"\n📊 ESTADÍSTICAS DEL BROKER MOCK")
    
    try:
        # Obtener estadísticas básicas
        stats = broker.get_performance_stats()
        
        print(f"   💰 P&L Total: ${stats.get('total_pnl', 0):.2f}")
        print(f"   ✅ Trades Ejecutados: {stats.get('trades_executed', 0)}")
        print(f"   🎯 Win Rate: {stats.get('win_rate', 0):.1%}")
        
        # Balance actual
        balance = stats.get('current_balance') or stats.get('total_value') or stats.get('cash', 0)
        print(f"   💵 Balance Actual: ${balance:.2f}")
        
        # Posiciones actuales
        positions_count = 0
        positions_detail = {}
        
        try:
            if hasattr(broker, 'get_positions'):
                positions_raw = await broker.get_positions()
                
                # Verificación defensiva
                if asyncio.iscoroutine(positions_raw):
                    positions_raw = await positions_raw
                
                if isinstance(positions_raw, dict):
                    positions_count = len(positions_raw)
                    positions_detail = positions_raw
                    
        except Exception as pos_error:
            print(f"   ⚠️  Error obteniendo posiciones: {pos_error}")
            
        print(f"   📊 Posiciones Abiertas: {positions_count}")
        
        # Mostrar detalles de posiciones si las hay
        if positions_detail:
            print("   💼 Detalle de posiciones:")
            for symbol, pos in positions_detail.items():
                try:
                    # Manejar tanto diccionarios como objetos
                    if isinstance(pos, dict):
                        quantity = pos.get('quantity', 0)
                        avg_price = pos.get('avg_price', 0)
                        unrealized_pnl = pos.get('unrealized_pnl', 0)
                    else:
                        quantity = getattr(pos, 'quantity', 0)
                        avg_price = getattr(pos, 'avg_price', 0)
                        unrealized_pnl = getattr(pos, 'unrealized_pnl', 0)
                    
                    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
                    print(f"      {symbol}: {quantity} @ ${avg_price:.2f} {pnl_emoji} ${unrealized_pnl:.2f}")
                except Exception as detail_error:
                    print(f"      {symbol}: Error mostrando detalle - {detail_error}")
                
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        import traceback
        print(f"📝 Traceback: {traceback.format_exc()}")

async def test_manual_orders(broker, available_symbols):
    """Test de órdenes manuales"""
    if not available_symbols:
        print("❌ No hay símbolos disponibles")
        return
        
    symbol = "PLTR" if "PLTR" in available_symbols else available_symbols[0]
    
    print(f"\n🛒 TEST DE ÓRDENES MANUALES CON {symbol}")
    
    try:
        # Obtener precio actual
        price = await broker.get_current_price(symbol)
        print(f"💰 Precio actual de {symbol}: ${price:.2f}")
        
        # Colocar orden de compra
        print(f"🛒 Colocando orden de compra de 100 acciones...")
        from core.interfaces import OrderSide, OrderType
        
        order_id = await broker.place_order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        print(f"✅ Orden colocada con ID: {order_id}")
        
        # Esperar un poco para que se ejecute
        await asyncio.sleep(1)
        
        # Ver posiciones
        positions = await broker.get_positions()
        if symbol in positions:
            pos = positions[symbol]
            print(f"📊 Posición actual: {pos.quantity} @ ${pos.avg_price:.2f}")
        
    except Exception as e:
        print(f"❌ Error en test de órdenes: {e}")

def show_available_data(data_provider, available_symbols):
    """Muestra información de los datos disponibles"""
    print(f"\n📂 DATOS DISPONIBLES")
    print(f"   📊 Total de símbolos: {len(available_symbols)}")
    
    # Mostrar información detallada de algunos símbolos
    sample_symbols = available_symbols[:10]
    print(f"\n📋 Muestra de símbolos disponibles:")
    
    for symbol in sample_symbols:
        try:
            # Intentar obtener algunas barras para ver la información
            bars = data_provider.get_bars_sync(symbol, "1 min", 10)
            if bars:
                last_bar = bars[-1]
                print(f"   {symbol}: {len(bars)} barras, último precio: ${last_bar.close:.2f}")
            else:
                print(f"   {symbol}: No se pudieron cargar datos")
        except Exception as e:
            print(f"   {symbol}: Error - {e}")

if __name__ == "__main__":
    asyncio.run(main())