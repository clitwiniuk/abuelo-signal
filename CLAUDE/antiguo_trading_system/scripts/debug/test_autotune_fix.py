#!/usr/bin/env python3
"""
Simple test to verify the auto-tune volatility fix is working
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from strategies.macdv_strategy import MACDVStrategy
from adapters.mock_ibkr_adapter import MockIBKRAdapter
from adapters.csv_data_provider import CSVDataProvider
from core.interfaces import MarketData

async def test_autotune_volatility():
    """Test that auto-tune is now propagating volatility thresholds"""
    
    print("🔧 TESTING AUTO-TUNE VOLATILITY FIX")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize components (no config manager needed for this test)
        
        # Create mock adapter and data provider
        broker = MockIBKRAdapter()
        data_provider = CSVDataProvider()
        
        await broker.connect()
        await data_provider.connect()
        
        # Create multi-strategy engine
        engine = MultiStrategyEngine()
        await engine.initialize()
        
        # Get MACDV strategy
        macdv_strategy = None
        for name, strategy in engine.strategies.items():
            if isinstance(strategy, MACDVStrategy):
                macdv_strategy = strategy
                break
        
        if not macdv_strategy:
            print("❌ MACDV strategy not found!")
            return
        
        print(f"✅ Found MACDV strategy: {macdv_strategy}")
        
        # Check initial volatility threshold
        initial_min_atr = macdv_strategy._parameters.get('min_atr_pct', 0.0)
        print(f"📊 Initial min_atr_pct: {initial_min_atr} ({initial_min_atr*100:.1f}%)")
        
        # Check engine initial thresholds
        print(f"📊 Engine dynamic_vol_min: {engine.dynamic_vol_min}%")
        print(f"📊 Engine dynamic_vol_max: {engine.dynamic_vol_max}%")
        
        # Simulate some bars to trigger auto-tune (force no signals to trigger reduction)
        print("\n🔄 Simulating bars to trigger auto-tune...")
        
        # Get some XXII data
        bars = await data_provider.get_historical_bars("XXII", "1 min", 200)
        if not bars:
            print("❌ No XXII data available")
            return
        
        print(f"📊 Got {len(bars)} bars for XXII")
        
        # Process first 100 bars to build up no-signal counter
        signal_count = 0
        for i, bar in enumerate(bars[:100]):
            if i % 20 == 0:  # Check every 20 bars
                signal = await engine.process_bar(bar)
                if signal:
                    signal_count += 1
                    print(f"✅ Signal {signal_count} at bar {i}: {signal}")
                else:
                    # Check if thresholds were updated
                    current_min_atr = macdv_strategy._parameters.get('min_atr_pct', 0.0)
                    if current_min_atr != initial_min_atr:
                        print(f"🔧 Auto-tune updated min_atr_pct: {initial_min_atr*100:.1f}% → {current_min_atr*100:.1f}%")
        
        # Check final state
        final_min_atr = macdv_strategy._parameters.get('min_atr_pct', 0.0)
        print(f"\n📈 FINAL RESULTS:")
        print(f"   Initial min_atr_pct: {initial_min_atr*100:.1f}%")
        print(f"   Final min_atr_pct: {final_min_atr*100:.1f}%")
        print(f"   Engine dynamic_vol_min: {engine.dynamic_vol_min}%")
        print(f"   Signals generated: {signal_count}")
        print(f"   No-signal counter: {engine._no_signal_counter}")
        
        if final_min_atr < initial_min_atr:
            print("✅ AUTO-TUNE FIX WORKING: Volatility thresholds were reduced!")
        elif signal_count > 0:
            print("✅ SIGNALS GENERATED: System is working!")
        else:
            print("⚠️  No threshold reduction yet - may need more bars or different conditions")
        
        await broker.disconnect()
        await data_provider.disconnect()
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_autotune_volatility())