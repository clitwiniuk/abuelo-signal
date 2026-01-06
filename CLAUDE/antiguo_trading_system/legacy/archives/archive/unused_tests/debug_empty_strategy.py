#!/usr/bin/env python3
"""
Debug específico para investigar por qué aparecen estrategias vacías en el reporte
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

async def test_empty_strategy_issue():
    """Test to debug why strategy names appear empty in trade reports"""
    
    print("🔍 DEBUGGING EMPTY STRATEGY NAMES IN TRADE REPORTS")
    print("=" * 70)
    
    # Initialize mock broker
    broker = MockIBKRAdapter()
    await broker.connect()
    
    print("\n📋 Test 1: Execute trade with NO signal parameter (should show 'Unknown')")
    # Execute order WITHOUT signal parameter
    await broker.place_order(
        symbol="TEST1",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=150.00
        # NO signal parameter
    )
    
    await broker.place_order(
        symbol="TEST1",
        side=OrderSide.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        price=155.00
        # NO signal parameter  
    )
    
    print("\n📋 Test 2: Execute trade with signal=None (should show 'Unknown')")
    # Execute order with signal=None
    await broker.place_order(
        symbol="TEST2",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=150.00,
        signal=None  # Explicitly None
    )
    
    await broker.place_order(
        symbol="TEST2",
        side=OrderSide.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        price=155.00,
        signal=None  # Explicitly None
    )
    
    print("\n📋 Test 3: Execute trade with empty signal object")
    # Empty signal object
    class EmptySignal:
        def __init__(self):
            pass  # No attributes
    
    await broker.place_order(
        symbol="TEST3",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=150.00,
        signal=EmptySignal()
    )
    
    await broker.place_order(
        symbol="TEST3",
        side=OrderSide.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        price=155.00,
        signal=EmptySignal()
    )
    
    print("\n📋 Test 4: Execute trade with signal that has empty strategy_name")
    # Signal with empty strategy_name
    class EmptyStrategySignal:
        def __init__(self):
            self.strategy_name = ""  # Empty string
            self.metadata = {}
    
    await broker.place_order(
        symbol="TEST4",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=150.00,
        signal=EmptyStrategySignal()
    )
    
    await broker.place_order(
        symbol="TEST4",
        side=OrderSide.SELL,
        quantity=100,
        order_type=OrderType.MARKET,
        price=155.00,
        signal=EmptyStrategySignal()
    )
    
    print("\n" + "=" * 70)
    print("📊 DETAILED TRADE REPORT - CHECKING FOR EMPTY STRATEGY NAMES")
    print("=" * 70)
    
    # Show the detailed report
    broker.print_detailed_trade_report()
    
    print("\n🔍 ANALYSIS:")
    print("- Test 1 & 2 should show 'Unknown' in strategy column")
    print("- Test 3 should show 'Unknown' (empty signal object)")  
    print("- Test 4 should show empty string or 'Unknown' (empty strategy_name)")
    print("\n💡 If your real trade shows completely empty strategy column,")
    print("   it suggests the trade was recorded through a different code path")
    print("   or the position tracking system has a bug.")

if __name__ == "__main__":
    asyncio.run(test_empty_strategy_issue())