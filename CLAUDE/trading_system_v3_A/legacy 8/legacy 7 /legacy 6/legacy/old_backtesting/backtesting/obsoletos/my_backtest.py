#!/usr/bin/env python3
"""
MI BACKTESTING PERSONALIZADO
Personaliza este script para tus propios tests
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

async def my_backtest():
    """Tu backtesting personalizado - modifica como quieras"""
    
    print("🚀 MI BACKTESTING PERSONALIZADO")
    print("=" * 50)
    
    # 🔧 PERSONALIZA ESTOS VALORES:
    # ========================================
    symbols_to_test = ["XXII", "SOFI", "SNDL"]  # ← Cambia los símbolos aquí
    bars_per_symbol = 500                        # ← Cambia número de barras
    position_size = 200                          # ← Cambia tamaño de posición ($)
    hold_bars = 15                              # ← Cambia cuánto mantener posición
    # ========================================
    
    print(f"📊 Testing símbolos: {symbols_to_test}")
    print(f"📊 Barras por símbolo: {bars_per_symbol}")
    print(f"💰 Tamaño posición: ${position_size}")
    
    # Initialize system
    broker = MockIBKRAdapter()
    data_provider = CSVDataProvider()
    event_bus = AsyncEventBus()
    
    await broker.connect()
    await data_provider.connect()
    
    # Results
    total_signals = 0
    total_trades = 0
    total_pnl = 0.0
    
    # Test each symbol
    for symbol in symbols_to_test:
        print(f"\n📈 TESTING {symbol}")
        print("-" * 30)
        
        # Fresh engine
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        # Get data
        bars = await data_provider.get_bars(symbol, "1 min", bars_per_symbol)
        if not bars:
            print(f"   ❌ No data for {symbol}")
            continue
        
        print(f"   📊 Processing {len(bars)} bars...")
        
        symbol_signals = 0
        symbol_trades = 0
        symbol_pnl = 0.0
        
        # Process bars
        for i, bar in enumerate(bars):
            signal = await engine.on_bar(bar)
            
            if signal:
                symbol_signals += 1
                print(f"   ✅ Signal {symbol_signals}: {signal.signal_type} @ ${bar.close:.2f}")
                
                # Execute trade
                if 'LONG' in str(signal.signal_type):
                    quantity = int(position_size / bar.close)
                    
                    if quantity > 0:
                        order = await broker.place_order(symbol, quantity, 'BUY', 'MKT')
                        if order:
                            symbol_trades += 1
                            
                            # Exit after specified bars
                            if i + hold_bars < len(bars):
                                exit_bar = bars[i + hold_bars]
                                exit_order = await broker.place_order(symbol, quantity, 'SELL', 'MKT')
                                if exit_order:
                                    trade_pnl = (exit_bar.close - bar.close) * quantity
                                    symbol_pnl += trade_pnl
                                    print(f"      💰 Trade: ${bar.close:.2f} -> ${exit_bar.close:.2f} = ${trade_pnl:.2f}")
        
        # Symbol summary
        print(f"   📊 {symbol} Results: {symbol_signals} signals, {symbol_trades} trades, ${symbol_pnl:.2f} P&L")
        
        total_signals += symbol_signals
        total_trades += symbol_trades
        total_pnl += symbol_pnl
    
    # Final results
    print(f"\n🏆 RESULTADOS FINALES:")
    print(f"   Total señales: {total_signals}")
    print(f"   Total trades: {total_trades}")
    print(f"   P&L total: ${total_pnl:.2f}")
    
    if total_signals > 0:
        print(f"   Promedio señales/símbolo: {total_signals/len(symbols_to_test):.1f}")
    
    await broker.disconnect()
    await data_provider.disconnect()

if __name__ == "__main__":
    asyncio.run(my_backtest())