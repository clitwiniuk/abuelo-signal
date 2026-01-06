#!/usr/bin/env python3
"""
Direct test of counter and auto-tune
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.events import AsyncEventBus

async def test_counter_directly():
    """Test the counter and auto-tune directly"""
    
    print("🔧 TESTING COUNTER AND AUTO-TUNE DIRECTLY")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(name)s - %(levelname)s - %(message)s'
    )
    
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
        print(f"📊 Initial counter: {engine._no_signal_counter}")
        print(f"📊 Initial volatility: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 150)
        if not bars:
            print("❌ No XXII data available")
            return
        
        print(f"📊 Got {len(bars)} bars for XXII")
        
        # Process bars and watch the counter
        for i, bar in enumerate(bars[:120]):  # Process 120 bars
            if i % 10 == 0:
                print(f"\n🔄 Processing bar {i+1}/120: ${bar.close:.2f}")
            
            signal = await engine.on_bar(bar)
            
            # Check counter after each bar
            if i % 10 == 9:  # Every 10 bars
                print(f"   Counter after bar {i+1}: {engine._no_signal_counter}")
                print(f"   Volatility range: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
                
                if engine._no_signal_counter >= 100:
                    print(f"   🎯 Counter reached {engine._no_signal_counter}! Auto-tune should have triggered!")
            
            if signal:
                print(f"✅ SIGNAL at bar {i+1}: {signal}")
                break
        
        print(f"\n📊 FINAL STATE:")
        print(f"   Final counter: {engine._no_signal_counter}")
        print(f"   Final volatility: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_counter_directly())