#!/usr/bin/env python3
"""
Test rápido para verificar que los strategy names aparecen en el reporte de trades
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.mock_ibkr_adapter import MockIBKRAdapter
from core.interfaces import OrderSide, OrderType

# Mock signal class for testing
class MockSignal:
    def __init__(self, strategy_name):
        self.strategy_name = strategy_name
        self.metadata = {'strategy': strategy_name}

async def test_strategy_names():
    """Test that strategy names appear in trade reports"""
    
    print("🧪 Testing strategy names in trade reports...")
    
    # Initialize mock broker
    broker = MockIBKRAdapter()
    await broker.connect()
    
    # Create mock signals with different strategy names
    macdv_signal = MockSignal("MACDV_Smallcaps")
    eod_signal = MockSignal("EOD_Momentum")
    orb_signal = MockSignal("ORB_Strategy")
    
    print("\n📋 Executing test trades with different strategies...")
    
    # Execute some test trades with strategy info
    # Trade 1: MACDV strategy
    await broker.place_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=150.00,
        signal=macdv_signal
    )
    
    # Sell to close position
    await broker.place_order(
        symbol="AAPL", 
        side=OrderSide.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        price=152.50,
        signal=macdv_signal
    )
    
    # Trade 2: EOD strategy 
    await broker.place_order(
        symbol="TSLA",
        side=OrderSide.BUY,
        quantity=50,
        order_type=OrderType.MARKET,
        price=200.00,
        signal=eod_signal
    )
    
    await broker.place_order(
        symbol="TSLA",
        side=OrderSide.SELL, 
        quantity=50,
        order_type=OrderType.MARKET,
        price=205.00,
        signal=eod_signal
    )
    
    # Trade 3: ORB strategy
    await broker.place_order(
        symbol="GV",
        side=OrderSide.BUY,
        quantity=200,
        order_type=OrderType.MARKET,
        price=2.00,
        signal=orb_signal
    )
    
    await broker.place_order(
        symbol="GV",
        side=OrderSide.SELL,
        quantity=200, 
        order_type=OrderType.MARKET,
        price=2.10,
        signal=orb_signal
    )
    
    print("\n✅ Test trades executed!")
    print("📊 Showing detailed trade report with strategy names...")
    
    # Show the detailed report - this should now include strategy names
    broker.print_detailed_trade_report()

if __name__ == "__main__":
    asyncio.run(test_strategy_names())