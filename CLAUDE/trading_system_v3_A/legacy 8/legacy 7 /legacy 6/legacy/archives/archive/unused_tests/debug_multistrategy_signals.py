#!/usr/bin/env python3
"""
Debug why MultiStrategy engine isn't generating signals for GV despite good conditions
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from core.interfaces import MarketData
from strategies.multi_strategy_engine import MultiStrategyEngine

async def debug_multistrategy_signals():
    """Debug MultiStrategy signal generation for GV-like conditions"""
    
    print("🔍 DEBUGGING MULTISTRATEGY SIGNAL GENERATION")
    print("=" * 60)
    
    # Setup detailed logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Initialize fresh components
    broker = MockIBKRAdapter()
    await broker.connect()
    
    multi_engine = MultiStrategyEngine()
    
    print("📋 Simulating GV market conditions from your log:")
    print("   Price: $1.96 -> $2.04 (+2.48% change)")
    print("   Volume: 65,917 (3.0x average ratio)")
    print("   Active strategies: explosive_volume, eod_momentum, eod_overnight_smallcaps")
    
    # Create realistic market data sequence that should trigger signals
    # This simulates the explosive volume condition mentioned in your log
    
    # First, establish baseline with normal volume
    baseline_bars = []
    for i in range(10):
        bar = MarketData(
            symbol="GV",
            timestamp=datetime.now().replace(hour=15, minute=30+i),  # During market hours
            open=1.95 + i*0.001,
            high=1.96 + i*0.001,
            low=1.94 + i*0.001,
            close=1.95 + i*0.001,
            volume=20000,  # Normal baseline volume
            timeframe="1m"
        )
        baseline_bars.append(bar)
    
    print(f"\n🏗️  Establishing baseline with {len(baseline_bars)} normal volume bars...")
    
    # Process baseline bars to establish volume averages
    for i, bar in enumerate(baseline_bars):
        signal = await multi_engine.on_bar(bar)
        if signal:
            print(f"   ⚡ Baseline bar {i+1}: Signal generated! {signal.signal_type}")
        else:
            print(f"   ⚪ Baseline bar {i+1}: No signal (expected)")
    
    print(f"\n🚀 Now creating explosive volume conditions...")
    
    # Now create the explosive volume scenario similar to your log
    explosive_bar = MarketData(
        symbol="GV",
        timestamp=datetime.now().replace(hour=15, minute=44),  # 15:44 like in your log
        open=1.96,
        high=2.08,  # Big spike
        low=1.95,
        close=2.04,  # +2.48% from previous close of ~1.99
        volume=65917,  # 3.0x+ volume from your log
        timeframe="1m"
    )
    
    print(f"📊 Processing explosive volume bar:")
    print(f"   Time: {explosive_bar.timestamp.strftime('%H:%M:%S')}")
    print(f"   Price: ${explosive_bar.close:.2f} (High: ${explosive_bar.high:.2f})")
    print(f"   Volume: {explosive_bar.volume:,}")
    print(f"   Expected: Should trigger explosive_volume strategy")
    
    # This should generate a signal
    signal = await multi_engine.on_bar(explosive_bar)
    
    if signal:
        print(f"   🎯 SUCCESS! Signal generated:")
        print(f"      Strategy Name: '{signal.strategy_name}'")
        print(f"      Signal Type: {signal.signal_type}")
        print(f"      Strength: {signal.strength}")
        print(f"      Price: ${signal.price:.2f}")
        print(f"      Metadata: {signal.metadata}")
        
        # Execute the trade with the signal
        from core.interfaces import OrderSide, OrderType, SignalType
        
        if signal.signal_type == SignalType.LONG:
            await broker.place_order(
                symbol="GV",
                side=OrderSide.BUY,
                quantity=515,  # Same quantity from your log
                order_type=OrderType.MARKET,
                price=signal.price,
                signal=signal
            )
            print(f"      ✅ Trade executed with strategy name: {signal.strategy_name}")
    else:
        print(f"   ❌ PROBLEM: No signal generated despite explosive conditions!")
        print(f"      This indicates an issue with:")
        print(f"      1. Strategy timing restrictions")
        print(f"      2. Insufficient market history")
        print(f"      3. Cooldown periods")
        print(f"      4. Parameter thresholds too high")
        print(f"      5. Filtering logic rejecting the signal")
    
    # Test with different timing (during EOD window)
    print(f"\n🕒 Testing during EOD strategy window (14:30 ET)...")
    
    eod_bar = MarketData(
        symbol="GV",
        timestamp=datetime.now().replace(hour=14, minute=30),  # During EOD window
        open=2.04,
        high=2.12,
        low=2.01,
        close=2.08,
        volume=45000,  # Good volume
        timeframe="1m"
    )
    
    signal = await multi_engine.on_bar(eod_bar)
    
    if signal:
        print(f"   🎯 EOD Signal generated: {signal.strategy_name} - {signal.signal_type}")
    else:
        print(f"   ⚪ No EOD signal generated")
    
    # Show any trades that were executed
    print(f"\n" + "=" * 60)
    print(f"📊 TRADE REPORT - TESTING STRATEGY NAME CAPTURE")
    print(f"=" * 60)
    
    broker.print_detailed_trade_report()
    
    print(f"\n💡 KEY INSIGHTS:")
    print(f"   - If no signals generated: Check timing, history, or thresholds")
    print(f"   - If signals generated but no strategy name: Signal creation bug")
    print(f"   - If strategy name appears: Fix is working correctly")

if __name__ == "__main__":
    asyncio.run(debug_multistrategy_signals())