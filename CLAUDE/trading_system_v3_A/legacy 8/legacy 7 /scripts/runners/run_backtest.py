#!/usr/bin/env python3
"""
BACKTESTING INTEGRADO ARREGLADO
Versión simplificada que funciona con el menú de start.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

async def integrated_backtest_main():
    """Función principal que reemplaza la rota del sistema integrado"""
    
    print("🚀 BACKTESTING INTEGRADO - VERSIÓN ARREGLADA")
    print("=" * 60)
    print("🎯 Sistema de backtesting con configuración optimizada")
    print("⚙️  Usando parámetros TESTING calibrados")
    
    # Configuración automática (sin inputs manuales)
    config = {
        "strategy": "Multi-Strategy",
        "symbols": ["XXII", "SOFI", "SNDL", "MVIS"],
        "bars_per_symbol": 1000,
        "position_size": 300,
        "hold_periods": 20
    }
    
    print(f"\n📊 CONFIGURACIÓN:")
    print(f"   Estrategia: {config['strategy']}")
    print(f"   Símbolos: {config['symbols']}")
    print(f"   Barras por símbolo: {config['bars_per_symbol']}")
    print(f"   Tamaño posición: ${config['position_size']}")
    
    # Initialize system
    broker = MockIBKRAdapter()
    data_provider = CSVDataProvider()
    event_bus = AsyncEventBus()
    
    await broker.connect()
    await data_provider.connect()
    
    print(f"\n✅ Sistema inicializado")
    print(f"📂 Datos disponibles: {len(data_provider.get_available_symbols())} símbolos")
    
    # Results tracking
    total_results = {
        "symbols_tested": 0,
        "total_signals": 0,
        "total_trades": 0,
        "total_pnl": 0.0,
        "successful_symbols": 0,
        "results_by_symbol": {}
    }
    
    # Test each symbol
    for i, symbol in enumerate(config["symbols"]):
        print(f"\n📈 BACKTESTING {i+1}/{len(config['symbols'])}: {symbol}")
        print("-" * 50)
        
        try:
            # Fresh engine for each symbol
            engine = MultiStrategyEngine()
            await engine.initialize(event_bus)
            
            print(f"   🔧 Config cargada: Vol {engine.dynamic_vol_min}%-{engine.dynamic_vol_max}%")
            
            # Get data
            bars = await data_provider.get_bars(symbol, "1 min", config["bars_per_symbol"])
            if not bars:
                print(f"   ❌ No data for {symbol}")
                continue
                
            print(f"   📊 Procesando {len(bars)} barras...")
            
            # Process and track results
            symbol_signals = 0
            symbol_trades = 0
            symbol_pnl = 0.0
            
            for bar_idx, bar in enumerate(bars):
                signal = await engine.on_bar(bar)
                
                if signal:
                    symbol_signals += 1
                    
                    # Execute trade
                    if hasattr(signal, 'signal_type') and 'LONG' in str(signal.signal_type):
                        quantity = int(config["position_size"] / bar.close)
                        
                        if quantity > 0:
                            order = await broker.place_order(symbol, quantity, 'BUY', 'MKT')
                            if order:
                                symbol_trades += 1
                                
                                # Exit after hold_periods
                                if bar_idx + config["hold_periods"] < len(bars):
                                    exit_bar = bars[bar_idx + config["hold_periods"]]
                                    exit_order = await broker.place_order(symbol, quantity, 'SELL', 'MKT')
                                    if exit_order:
                                        trade_pnl = (exit_bar.close - bar.close) * quantity
                                        symbol_pnl += trade_pnl
                                        
                                        if symbol_trades <= 2:  # Show first 2 trades
                                            print(f"     💰 Trade {symbol_trades}: ${bar.close:.2f}->${exit_bar.close:.2f} = ${trade_pnl:.2f}")
            
            # Symbol results
            print(f"   📊 {symbol}: {symbol_signals} señales, {symbol_trades} trades, ${symbol_pnl:.2f} P&L")
            
            # Update totals
            total_results["symbols_tested"] += 1
            total_results["total_signals"] += symbol_signals
            total_results["total_trades"] += symbol_trades
            total_results["total_pnl"] += symbol_pnl
            
            if symbol_signals > 0:
                total_results["successful_symbols"] += 1
                
            total_results["results_by_symbol"][symbol] = {
                "signals": symbol_signals,
                "trades": symbol_trades,
                "pnl": symbol_pnl
            }
            
        except Exception as e:
            print(f"   ❌ Error con {symbol}: {e}")
            continue
    
    await broker.disconnect()
    await data_provider.disconnect()
    
    # Final analysis - Estilo integrado
    print(f"\n" + "=" * 60)
    print(f"📊 REPORTE FINAL DEL BACKTESTING INTEGRADO")
    print(f"=" * 60)
    
    print(f"🎯 RESUMEN EJECUTIVO:")
    print(f"   Símbolos probados: {total_results['symbols_tested']}")
    print(f"   Símbolos exitosos: {total_results['successful_symbols']}")
    print(f"   Total señales: {total_results['total_signals']}")
    print(f"   Total trades: {total_results['total_trades']}")  
    print(f"   P&L neto: ${total_results['total_pnl']:.2f}")
    
    if total_results["symbols_tested"] > 0:
        success_rate = (total_results["successful_symbols"] / total_results["symbols_tested"]) * 100
        avg_signals = total_results["total_signals"] / total_results["symbols_tested"]
        
        print(f"   Tasa éxito: {success_rate:.1f}%")
        print(f"   Avg señales/símbolo: {avg_signals:.1f}")
    
    # Performance ranking
    print(f"\n🏆 RANKING DE PERFORMANCE:")
    sorted_symbols = sorted(total_results["results_by_symbol"].items(),
                           key=lambda x: x[1]["signals"], reverse=True)
    
    for i, (symbol, results) in enumerate(sorted_symbols[:3]):
        emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else "   "
        print(f"   {emoji} {symbol}: {results['signals']} señales, ${results['pnl']:.2f}")
    
    # System evaluation
    print(f"\n✅ EVALUACIÓN DEL SISTEMA:")
    if total_results["total_signals"] >= 5:
        print("   🟢 EXCELENTE: Alta generación de señales")
    elif total_results["total_signals"] >= 2:
        print("   🟡 BUENO: Generación moderada de señales") 
    else:
        print("   🔴 MEJORABLE: Pocas señales generadas")
        
    print(f"\n🎯 CONFIGURACIÓN UTILIZADA:")
    print(f"   Profile: TESTING (Extended Hours)")
    print(f"   Volume threshold: 0.1 (ultra permisivo)")
    print(f"   Confidence threshold: 0.1 (muy permisivo)")
    print(f"   Volatilidad dinámica: 0.2% - 4.0%")
    
    return total_results

# Función para integrar con start.py
async def main():
    """Main function compatible con el sistema integrado"""
    try:
        results = await integrated_backtest_main()
        print(f"\n✅ BACKTESTING INTEGRADO COMPLETADO")
        print(f"📊 Generadas {results['total_signals']} señales en {results['symbols_tested']} símbolos")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Backtesting interrumpido por usuario")
    except Exception as e:
        print(f"\n❌ Error en backtesting: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())