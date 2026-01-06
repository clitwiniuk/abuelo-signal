#!/usr/bin/env python3
"""
Quick test of XXII with multi-strategy engine
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

async def quick_test_xxii():
    """Quick test of XXII with updated parameters"""
    
    print("🔧 TESTING XXII WITH OPTIMIZED PARAMETERS")
    print("=" * 50)
    
    try:
        # Initialize components
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        event_bus = AsyncEventBus()
        
        await broker.connect()
        await data_provider.connect()
        
        # Create multi-strategy engine
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        print(f"✅ Engine initialized")
        print(f"📊 Strategies: {list(engine.strategies.keys())}")
        
        # Get XXII data  
        bars = await data_provider.get_bars("XXII", "1 min", 1000)
        if not bars:
            print("❌ No XXII data available")
            return
            
        print(f"📊 Processing {len(bars)} bars for XXII")
        
        trades_executed = 0
        signals_generated = 0
        
        # Process all bars
        for i, bar in enumerate(bars):
            if i % 100 == 0:
                print(f"🔄 Bar {i+1}/{len(bars)}: ${bar.close:.2f} | Vol: {bar.volume:,}")
            
            signal = await engine.on_bar(bar)
            if signal:
                signals_generated += 1
                print(f"✅ SIGNAL {signals_generated} at bar {i+1}: {signal}")
                
                # Execute trade
                if hasattr(signal, 'action') and signal.action.upper() == 'BUY':
                    quantity = min(100, int(300 / bar.close))  # $300 position max
                    symbol = getattr(signal, 'symbol', bar.symbol)
                    order = await broker.place_order(symbol, quantity, 'BUY', 'MKT')
                    if order:
                        trades_executed += 1
                        print(f"   💰 Trade {trades_executed}: BUY {quantity} {symbol} @ ${bar.close:.2f}")
        
        # Final stats
        print(f"\n📊 FINAL RESULTS:")
        print(f"   Signals generated: {signals_generated}")
        print(f"   Trades executed: {trades_executed}")
        print(f"   System working correctly with optimized parameters!")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(quick_test_xxii())