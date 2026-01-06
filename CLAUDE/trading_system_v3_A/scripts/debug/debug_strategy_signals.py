#!/usr/bin/env python3
"""
Debug why strategies are not generating signals for XXII
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

async def debug_signal_generation():
    """Debug why XXII is not generating signals"""
    
    print("🔍 DEBUGGING SIGNAL GENERATION FOR XXII")
    print("=" * 50)
    
    # Setup debug logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize components
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        event_bus = AsyncEventBus()
        
        await broker.connect()
        await data_provider.connect()
        
        # Create multi-strategy engine with event bus
        engine = MultiStrategyEngine()
        await engine.initialize(event_bus)
        
        print(f"✅ Engine initialized with strategies: {list(engine.strategies.keys())}")
        print(f"📊 Initial volatility range: {engine.dynamic_vol_min}% - {engine.dynamic_vol_max}%")
        
        # Get XXII data
        bars = await data_provider.get_bars("XXII", "1 min", 50)
        if not bars:
            print("❌ No XXII data available")
            return
        
        print(f"📊 Got {len(bars)} bars for XXII")
        
        # Process first few bars with detailed logging
        for i, bar in enumerate(bars[:10]):
            print(f"\n🔄 Processing bar {i+1}: ${bar.close:.2f} | Volume: {bar.volume:,}")
            
            # Enable debug logging for this bar
            logging.getLogger("Strategy.MultiStrategy_Engine").setLevel(logging.DEBUG)
            logging.getLogger("Strategy.MACDV_Smallcaps").setLevel(logging.DEBUG)
            logging.getLogger("Strategy.ORB").setLevel(logging.DEBUG)
            
            signal = await engine.process_bar(bar)
            if signal:
                print(f"✅ SIGNAL GENERATED: {signal}")
                break
            else:
                print(f"❌ No signal for bar {i+1}")
        
        # Check strategy states
        print(f"\n📊 FINAL ENGINE STATE:")
        print(f"   Dynamic vol min: {engine.dynamic_vol_min}%")
        print(f"   Dynamic vol max: {engine.dynamic_vol_max}%")
        print(f"   No signal counter: {engine._no_signal_counter}")
        
        # Check individual strategy parameters
        for name, strategy in engine.strategies.items():
            if hasattr(strategy, '_parameters'):
                min_atr = strategy._parameters.get('min_atr_pct', 'N/A')
                print(f"   {name} min_atr_pct: {min_atr}")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
    except Exception as e:
        print(f"❌ Error in debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_signal_generation())