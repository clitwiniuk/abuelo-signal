#!/usr/bin/env python3
"""
Ejemplo completo de cómo ejecutar el sistema de trading con el mock adapter.
Este script muestra cómo:
1. Configurar el entorno de simulación
2. Ejecutar estrategias de trading
3. Monitorear el rendimiento
4. Realizar backtesting
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.interfaces import OrderSide, OrderType
from strategies.macdv_strategy import MACDVStrategy

async def main():
    """Ejecuta un ejemplo completo del trading system con mock"""
    
    print("🚀 TRADING SYSTEM CON MOCK ADAPTER - EJEMPLO COMPLETO")
    print("=" * 70)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Crear adapters
    broker = MockIBKRAdapter(data_path="data/csv", simulation_mode=True)
    data_provider = CSVDataProvider(data_path="data/csv", auto_load=True)
    
    try:
        # 1. Conectar
        print("🔌 1. CONECTANDO AL SISTEMA...")
        await broker.connect()
        await data_provider.connect()
        
        print(f"   ✅ Broker: {broker.is_connected()}")
        print(f"   ✅ Data Provider: {data_provider.is_connected()}")
        
        # 2. Obtener símbolos disponibles
        symbols = data_provider.get_available_symbols()
        trading_symbols = ["PLTR", "TSLA", "NVDA", "AMD"] if all(s in symbols for s in ["PLTR", "TSLA", "NVDA", "AMD"]) else symbols[:4]
        
        print(f"📊 2. SÍMBOLOS PARA TRADING:")
        print(f"   Total disponibles: {len(symbols)}")
        print(f"   Seleccionados: {trading_symbols}")
        
        # 3. Configurar estrategia
        print(f"\n📈 3. CONFIGURANDO ESTRATEGIA MACDV...")
        strategy = MACDVStrategy({
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.5,
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.06,
            'max_position_value': 2000.0
        })
        
        # 4. Ejecutar simulación de trading
        print(f"\n🎮 4. INICIANDO SIMULACIÓN DE TRADING...")
        await run_trading_simulation(broker, data_provider, strategy, trading_symbols)
        
        # 5. Mostrar resultados
        print(f"\n📊 5. RESULTADOS FINALES:")
        await show_trading_results(broker)
        
        # 6. Ejemplo de backtest
        print(f"\n🔍 6. EJECUTANDO BACKTEST...")
        await run_simple_backtest(broker, data_provider, strategy, "PLTR")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Error en ejemplo: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await broker.disconnect()
            await data_provider.disconnect()
            print("🔌 Conexiones cerradas")
        except:
            pass

async def run_trading_simulation(broker, data_provider, strategy, symbols):
    """Ejecuta una simulación de trading con múltiples símbolos"""
    
    total_trades = 0
    
    for symbol in symbols:
        print(f"\n   🎯 Analizando {symbol}...")
        
        try:
            # Obtener datos históricos
            bars = await data_provider.get_bars(symbol, "1 min", 100)
            
            if not bars or len(bars) < 50:
                print(f"      ❌ Datos insuficientes para {symbol}")
                continue
            
            # Analizar con estrategia
            signal = await strategy.analyze(symbol, bars, {})
            
            if signal and signal.action in ["BUY", "SELL"]:
                print(f"      📈 Señal detectada: {signal.action} {symbol}")
                print(f"         Confianza: {signal.confidence:.2f}")
                print(f"         Precio: ${signal.price:.2f}")
                
                # Ejecutar trade si la confianza es alta
                if signal.confidence > 0.6:  # 60% confianza mínima
                    order_id = await broker.place_order(
                        symbol=symbol,
                        side=OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL,
                        quantity=signal.quantity,
                        order_type=OrderType.MARKET
                    )
                    
                    print(f"      ✅ Orden ejecutada: {order_id}")
                    total_trades += 1
                    
                    # Esperar un poco para la ejecución
                    await asyncio.sleep(0.2)
                else:
                    print(f"      ⚠️ Confianza baja, no se ejecuta trade")
            else:
                print(f"      ➖ No hay señal para {symbol}")
                
        except Exception as e:
            print(f"      ❌ Error analizando {symbol}: {e}")
    
    print(f"\n   📊 Total de trades ejecutados: {total_trades}")

async def show_trading_results(broker):
    """Muestra los resultados del trading"""
    
    try:
        # Información de cuenta
        account = await broker.get_account_info()
        print(f"   💰 Balance: ${account.get('cash', 0):.2f}")
        print(f"   💎 Valor Total: ${account.get('total_value', 0):.2f}")
        print(f"   📈 P&L Total: ${account.get('total_value', 10000) - 10000:.2f}")
        
        # Posiciones actuales
        positions = await broker.get_positions()
        print(f"   📊 Posiciones Abiertas: {len(positions)}")
        
        if positions:
            print(f"   💼 Detalle de Posiciones:")
            for symbol, pos in positions.items():
                pnl_emoji = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
                print(f"      {symbol}: {pos.quantity} @ ${pos.avg_price:.2f} {pnl_emoji} ${pos.unrealized_pnl:.2f}")
        
        # Estadísticas de performance
        stats = broker.get_performance_stats()
        print(f"   ✅ Trades Totales: {stats.get('trades_executed', 0)}")
        print(f"   🎯 Win Rate: {stats.get('win_rate', 0):.1%}")
        
    except Exception as e:
        print(f"   ❌ Error obteniendo resultados: {e}")

async def run_simple_backtest(broker, data_provider, strategy, symbol):
    """Ejecuta un backtest simple en un símbolo"""
    
    print(f"   🔍 Backtesting {symbol}...")
    
    try:
        # Reset del broker para backtest limpio
        await broker.reset_simulation()
        
        # Obtener más datos históricos para backtest
        bars = await data_provider.get_bars(symbol, "1 min", 500)
        
        if not bars or len(bars) < 100:
            print(f"      ❌ Datos insuficientes para backtest de {symbol}")
            return
        
        print(f"      📊 Usando {len(bars)} barras de datos")
        
        trades_executed = 0
        signals_found = 0
        
        # Simular trading paso a paso
        for i in range(50, len(bars)):  # Empezar desde barra 50 para tener historial
            current_bars = bars[max(0, i-50):i+1]  # Usar últimas 50 barras
            
            try:
                signal = await strategy.analyze(symbol, current_bars, {})
                
                if signal and signal.action in ["BUY", "SELL"]:
                    signals_found += 1
                    
                    if signal.confidence > 0.7:  # Mayor confianza para backtest
                        # Simular orden en precio de la barra actual
                        order_id = await broker.place_order(
                            symbol=symbol,
                            side=OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL,
                            quantity=min(signal.quantity, 100),  # Limitar cantidad
                            order_type=OrderType.MARKET
                        )
                        trades_executed += 1
                        
                        # Simular algo de tiempo entre trades
                        await asyncio.sleep(0.01)
                        
            except Exception as e:
                continue  # Ignorar errores menores en backtest
        
        # Resultados del backtest
        final_account = await broker.get_account_info()
        final_pnl = final_account.get('total_value', 10000) - 10000
        
        print(f"      📊 RESULTADOS DEL BACKTEST:")
        print(f"         🔍 Señales Encontradas: {signals_found}")
        print(f"         ✅ Trades Ejecutados: {trades_executed}")
        print(f"         💰 P&L Final: ${final_pnl:.2f}")
        print(f"         📈 Return: {(final_pnl/10000)*100:.2f}%")
        
        if trades_executed > 0:
            avg_trade = final_pnl / trades_executed
            print(f"         📊 P&L Promedio por Trade: ${avg_trade:.2f}")
        
    except Exception as e:
        print(f"      ❌ Error en backtest: {e}")

if __name__ == "__main__":
    asyncio.run(main())