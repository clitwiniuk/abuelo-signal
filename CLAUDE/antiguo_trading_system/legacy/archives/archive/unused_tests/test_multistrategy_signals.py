#!/usr/bin/env python3
"""
Test específico para verificar que MultiStrategy capture strategy names
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from core.interfaces import OrderSide, OrderType, SignalType
from core.interfaces import MarketData

# Mock signal from MultiStrategy
class MultiStrategySignal:
    def __init__(self, strategy_name, signal_type):
        self.strategy_name = strategy_name  # This should be captured
        self.signal_type = signal_type
        self.metadata = {
            'strategy': strategy_name, 
            'confidence': 0.8,
            'position_size': 100
        }
        self.confidence = 0.8
        self.price = 150.0
        self.timestamp = datetime.now()

async def test_multistrategy_signals():
    """Test that MultiStrategy signals are captured correctly"""
    
    print("🧪 Testing MultiStrategy signal capture...")
    
    # Initialize mock broker
    broker = MockIBKRAdapter()
    await broker.connect()
    
    # Test with different sub-strategies from MultiStrategy
    strategies_to_test = [
        ("MACDV_Smallcaps", SignalType.LONG),
        ("EOD_Momentum", SignalType.LONG),  
        ("ORB_Strategy", SignalType.LONG),
        ("Volume_Breakout", SignalType.LONG),
        ("Gap_Go", SignalType.LONG)
    ]
    
    print(f"\n📋 Testing {len(strategies_to_test)} different MultiStrategy sub-strategies...")
    
    for i, (strategy_name, signal_type) in enumerate(strategies_to_test, 1):
        # Create signal
        signal = MultiStrategySignal(strategy_name, signal_type)
        
        print(f"\n[{i}/{len(strategies_to_test)}] Testing {strategy_name}...")
        
        # Execute BUY order
        await broker.place_order(
            symbol=f"TEST{i}",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            price=150.00 + i,
            signal=signal
        )
        
        # Execute SELL order to close
        exit_signal = MultiStrategySignal(f"{strategy_name}_Exit", SignalType.EXIT_LONG)
        await broker.place_order(
            symbol=f"TEST{i}",
            side=OrderSide.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
            price=155.00 + i,
            signal=exit_signal
        )
        
        print(f"✅ {strategy_name} trade completed")
    
    print("\n" + "="*80)
    print("📊 DETAILED TRADE REPORT WITH STRATEGY NAMES")
    print("="*80)
    
    # Show the detailed report - should show all strategy names
    broker.print_detailed_trade_report()
    
    print("\n🎯 Expected result: Each trade should show the correct strategy name")
    print("🔍 Check the 'Estrategia' column in the report above")

if __name__ == "__main__":
    asyncio.run(test_multistrategy_signals())