#!/usr/bin/env python3
"""
Debug script for Healthy High Profits Logic
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import Mock
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Position
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Debug")

async def debug_single_case():
    """Debug a single case to understand what's happening"""
    
    # Create engine
    engine = MLMultiStrategyEngine(parameters={})
    engine.bars_history = {}
    engine.positions = {}
    
    # Test case: 12% profit at 3:35 PM (should exit)
    symbol = "DEBUG"
    entry_price = 10.00
    current_price = 11.20
    profit_pct = 0.12
    test_time = datetime(2025, 9, 4, 15, 35)  # 3:35 PM
    
    logger.info(f"🔍 Debugging case: {profit_pct:.1%} profit at {test_time}")
    
    # Create position
    position = Position(
        symbol=symbol,
        quantity=100,
        avg_price=entry_price,
        market_value=entry_price * 100,
        realized_pnl=0.0
    )
    
    # Create simple price history
    from datetime import timedelta
    bars = []
    for i in range(20):
        bar_time = datetime(2025, 9, 4, 9, 30) + timedelta(minutes=i*5)
        
        bar_price = entry_price + (current_price - entry_price) * (i / 19)
        if i == 17:  # Make a recent high
            bar_price = current_price * 1.015  # 1.5% above current
            
        bar = MarketData(
            symbol=symbol,
            timestamp=bar_time,
            open=bar_price * 0.998,
            high=bar_price * 1.002,
            low=bar_price * 0.995,
            close=bar_price,
            volume=10000 + i * 500,
            last_price=bar_price
        )
        bars.append(bar)
        
    # Current bar
    current_bar = MarketData(
        symbol=symbol,
        timestamp=test_time,
        open=current_price * 0.998,
        high=current_price * 1.002,
        low=current_price * 0.995,
        close=current_price,
        volume=20000,  # 2x average
        last_price=current_price
    )
    
    # Setup engine
    engine.bars_history[symbol] = bars
    engine.positions[symbol] = position
    
    logger.info(f"📊 Setup complete:")
    logger.info(f"   - History bars: {len(bars)}")
    logger.info(f"   - Recent high: ${max(b.close for b in bars[-5:]):.2f}")
    logger.info(f"   - Current price: ${current_price:.2f}")
    logger.info(f"   - Test time: {test_time}")
    
    # Test the function directly with debug logging
    try:
        result = await engine._check_healthy_high_profits(symbol, current_bar, position, profit_pct)
        
        logger.info(f"🎯 Result: {'EXIT' if result else 'HOLD'}")
        if result:
            logger.info(f"   Reason: {result.metadata.get('exit_reason')}")
            logger.info(f"   Strength: {result.strength}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_single_case())