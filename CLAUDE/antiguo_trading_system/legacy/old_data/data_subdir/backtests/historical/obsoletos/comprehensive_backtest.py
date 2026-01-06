#!/usr/bin/env python3
"""
BACKTESTING COMPLETO - Configuración Optimizada
Test del sistema con parámetros calibrados en múltiples símbolos
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus
from core.interfaces import OrderSide, OrderType

async def comprehensive_backtest():
    """Backtesting completo con parámetros optimizados"""
    
    print("🚀 BACKTESTING COMPLETO - CONFIGURACIÓN OPTIMIZADA")
    print("=" * 60)
    print("📊 Objetivo: Evaluar sistema con parámetros calibrados")
    print("⚙️  Configuración: TESTING profile optimizada")
    print("📈 Símbolos: XXII, PLTR, MVIS (representativos)")
    print("⏱️  Tiempo estimado: 3-5 minutos")
    
    # Test symbols (representative sample)
    test_symbols = ["XXII", "PLTR", "MVIS", "SOFI", "SNDL"]
    bars_per_symbol = 1000
    
    # Initialize components
    broker = MockIBKRAdapter()
    data_provider = CSVDataProvider()
    event_bus = AsyncEventBus()
    
    await broker.connect()
    await data_provider.connect()
    
    print(f"\n✅ Sistema inicializado")
    available_symbols = data_provider.get_available_symbols()
    print(f"📊 Símbolos disponibles: {len(available_symbols)}")
    
    # Results tracking
    total_results = {
        "symbols_tested": 0,
        "total_signals": 0,
        "total_trades": 0,
        "total_pnl": 0.0,
        "successful_symbols": 0,
        "symbol_results": {}
    }
    
    # Test each symbol
    for i, symbol in enumerate(test_symbols):
        print(f"\n📈 TESTING {i+1}/{len(test_symbols)}: {symbol}")
        print("-" * 40)
        
        try:
            # Fresh engine for each symbol
            engine = MultiStrategyEngine()
            await engine.initialize(event_bus)
            
            print(f"   📊 Volatilidad configurada: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
            
            # Get data
            bars = await data_provider.get_bars(symbol, "1 min", bars_per_symbol)
            if not bars:
                print(f"   ❌ No data available for {symbol}")
                continue
            
            print(f"   📊 Processing {len(bars)} bars...")
            
            # Track results for this symbol
            symbol_signals = 0
            symbol_trades = 0
            symbol_pnl = 0.0
            
            # Process bars
            for bar_idx, bar in enumerate(bars):
                signal = await engine.on_bar(bar)
                
                if signal:
                    symbol_signals += 1
                    
                    # Execute simple trade for backtesting
                    if hasattr(signal, 'signal_type') and 'LONG' in str(signal.signal_type):
                        position_value = 300  # $300 per trade
                        quantity = int(position_value / bar.close)
                        
                        if quantity > 0:
                            order = await broker.place_order(symbol, OrderSide.BUY, quantity, OrderType.MARKET)
                            if order:
                                symbol_trades += 1
                                
                                # Simple exit after 20 bars (realistic holding)
                                if bar_idx + 20 < len(bars):
                                    exit_bar = bars[bar_idx + 20]
                                    exit_order = await broker.place_order(symbol, OrderSide.SELL, quantity, OrderType.MARKET)
                                    if exit_order:
                                        trade_pnl = (exit_bar.close - bar.close) * quantity
                                        symbol_pnl += trade_pnl
                                        
                                        if symbol_trades <= 3:  # Show first 3 trades
                                            print(f"     💰 Trade {symbol_trades}: ${bar.close:.2f} → ${exit_bar.close:.2f} = ${trade_pnl:.2f}")
            
            # Symbol results
            print(f"   📊 {symbol} Results:")
            print(f"      Signals: {symbol_signals}")
            print(f"      Trades: {symbol_trades}")
            print(f"      P&L: ${symbol_pnl:.2f}")
            
            # Update totals
            total_results["symbols_tested"] += 1
            total_results["total_signals"] += symbol_signals
            total_results["total_trades"] += symbol_trades
            total_results["total_pnl"] += symbol_pnl
            
            if symbol_signals > 0:
                total_results["successful_symbols"] += 1
            
            total_results["symbol_results"][symbol] = {
                "signals": symbol_signals,
                "trades": symbol_trades,
                "pnl": symbol_pnl
            }
            
        except Exception as e:
            print(f"   ❌ Error testing {symbol}: {e}")
            continue
    
    await broker.disconnect()
    await data_provider.disconnect()
    
    # Final analysis
    print("\n" + "=" * 60)
    print("📊 ANÁLISIS FINAL DEL BACKTESTING")
    print("=" * 60)
    
    print(f"🎯 RESUMEN GENERAL:")
    print(f"   Símbolos probados: {total_results['symbols_tested']}")
    print(f"   Símbolos con señales: {total_results['successful_symbols']}")
    print(f"   Total señales generadas: {total_results['total_signals']}")
    print(f"   Total trades ejecutados: {total_results['total_trades']}")
    print(f"   P&L total: ${total_results['total_pnl']:.2f}")
    
    if total_results["symbols_tested"] > 0:
        avg_signals = total_results["total_signals"] / total_results["symbols_tested"]
        success_rate = (total_results["successful_symbols"] / total_results["symbols_tested"]) * 100
        
        print(f"   Promedio señales/símbolo: {avg_signals:.1f}")
        print(f"   Tasa de éxito: {success_rate:.1f}%")
    
    # Top performers
    print(f"\n🏆 TOP PERFORMERS:")
    sorted_symbols = sorted(total_results["symbol_results"].items(), 
                           key=lambda x: x[1]["signals"], reverse=True)
    
    for i, (symbol, results) in enumerate(sorted_symbols[:3]):
        print(f"   {i+1}. {symbol}: {results['signals']} señales, ${results['pnl']:.2f} P&L")
    
    # Evaluation
    print(f"\n✅ EVALUACIÓN DEL SISTEMA:")
    if total_results["total_signals"] >= 5:
        print("   🟢 EXCELENTE: Sistema genera suficientes señales")
    elif total_results["total_signals"] >= 2:
        print("   🟡 BUENO: Sistema genera señales moderadas")
    else:
        print("   🔴 MEJORABLE: Pocas señales generadas")
    
    if total_results["successful_symbols"] >= 3:
        print("   🟢 ROBUSTO: Funciona en múltiples símbolos")
    elif total_results["successful_symbols"] >= 2:
        print("   🟡 MODERADO: Funciona en algunos símbolos")
    else:
        print("   🔴 LIMITADO: Solo funciona en pocos símbolos")
    
    print(f"\n🎯 CONFIGURACIÓN ACTUAL:")
    print(f"   Profile: TESTING (Extended Hours)")
    print(f"   Volume threshold: 0.1 (ultra permisivo)")
    print(f"   Volatilidad: 0.2% - 4.0% (muy permisiva)")
    print(f"   Confidence threshold: 0.1 (muy permisivo)")
    
    return total_results

async def main():
    try:
        results = await comprehensive_backtest()
        
        print(f"\n✅ BACKTESTING COMPLETADO")
        print(f"📊 {results['total_signals']} señales totales en {results['symbols_tested']} símbolos")
        
    except Exception as e:
        print(f"❌ Error en backtesting: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())