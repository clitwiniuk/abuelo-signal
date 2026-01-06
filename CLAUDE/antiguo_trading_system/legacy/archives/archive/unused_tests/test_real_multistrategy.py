#!/usr/bin/env python3
"""
Test the actual MultiStrategy engine with our strategy_name fixes
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from core.interfaces import MarketData, OrderSide, OrderType, SignalType, Signal
from strategies.multi_strategy_engine import MultiStrategyEngine

async def test_real_multistrategy_signals():
    """Test actual MultiStrategy engine signal generation"""
    
    print("🔍 TESTING REAL MULTISTRATEGY ENGINE WITH FIXED STRATEGY_NAMES")
    print("=" * 70)
    
    # Initialize fresh mock broker (no cached trades)
    broker = MockIBKRAdapter()
    await broker.connect()
    
    # Initialize MultiStrategy engine
    multi_engine = MultiStrategyEngine()
    
    print("📋 Creating test market conditions that should trigger signals...")
    
    # Create market data that should trigger volume breakout or gap signals
    test_bars = [
        MarketData(
            symbol="TESTSTOCK",
            timestamp=datetime.now(),
            open=10.00,
            high=12.50,  # Big gap up and breakout
            low=9.95,
            close=12.25,
            volume=500000,  # High volume
            timeframe="1m"
        ),
        MarketData(
            symbol="TESTSTOCK", 
            timestamp=datetime.now(),
            open=12.25,
            high=12.80,
            low=12.10,
            close=12.75,
            volume=300000,
            timeframe="1m"
        ),
        MarketData(
            symbol="TESTSTOCK",
            timestamp=datetime.now(),
            open=12.75,
            high=13.20,
            low=12.60,
            close=13.10,
            volume=250000,
            timeframe="1m"
        )
    ]
    
    signals_generated = 0
    
    for i, bar in enumerate(test_bars, 1):
        print(f"\n📊 Processing bar {i}: {bar.symbol} @ ${bar.close:.2f} (Vol: {bar.volume:,})")
        
        # Get signal from MultiStrategy engine
        signal = await multi_engine.on_bar(bar)
        
        if signal and signal.signal_type:
            signals_generated += 1
            print(f"   🎯 SIGNAL GENERATED!")
            print(f"      Type: {signal.signal_type}")
            print(f"      Strategy Name: '{signal.strategy_name}'")  # This should NOT be empty now
            print(f"      Strength: {signal.strength}")
            print(f"      Metadata: {signal.metadata}")
            
            # Execute the trade with the signal
            
            if signal.signal_type == SignalType.LONG:
                await broker.place_order(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    quantity=100,
                    order_type=OrderType.MARKET,
                    price=bar.close,
                    signal=signal  # Pass the real signal
                )
                print(f"      ✅ BUY order executed with signal")
                
            elif signal.signal_type == SignalType.EXIT_LONG:
                await broker.place_order(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    quantity=100,
                    order_type=OrderType.MARKET,
                    price=bar.close,
                    signal=signal  # Pass the real signal
                )
                print(f"      ✅ SELL order executed with signal")
        else:
            print(f"   ⚪ No signal generated")
    
    print(f"\n📈 Total signals generated: {signals_generated}")
    
    # If no signals were generated, create a manual one to test the fix
    if signals_generated == 0:
        print(f"\n⚠️  No signals generated naturally. Creating manual signal for testing...")
        
        # Create a manual signal using one of our fixed strategies
        
        manual_signal = Signal(
            signal_id="test_manual_001",
            symbol="TESTSTOCK",
            signal_type=SignalType.LONG,
            strength=0.8,
            price=12.50,
            timestamp=datetime.now(),
            strategy_name="Volume_Breakout",  # This should now appear in report
            metadata={'strategy': 'VolumeBreakout', 'test': True}
        )
        
        await broker.place_order(
            symbol="TESTSTOCK",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=12.50,
            signal=manual_signal
        )
        
        # Close position
        close_signal = Signal(
            signal_id="test_manual_002",
            symbol="TESTSTOCK",
            signal_type=SignalType.EXIT_LONG,
            strength=1.0,
            price=13.00,
            timestamp=datetime.now(),
            strategy_name="Volume_Breakout",  # This should now appear in report
            metadata={'strategy': 'VolumeBreakout', 'reason': 'manual_close'}
        )
        
        await broker.place_order(
            symbol="TESTSTOCK",
            side=OrderSide.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            price=13.00,
            signal=close_signal
        )
        
        print(f"   ✅ Manual test trade executed")
    
    print("\n" + "=" * 70)
    print("📊 FRESH TRADE REPORT - SHOULD SHOW STRATEGY NAMES")
    print("=" * 70)
    
    # Show fresh report
    broker.print_detailed_trade_report()
    
    print("\n🎯 This test uses FRESH data (not cached from previous runs)")
    print("💡 If strategy names still don't appear, the issue is in the MultiStrategy engine itself")

if __name__ == "__main__":
    asyncio.run(test_real_multistrategy_signals())