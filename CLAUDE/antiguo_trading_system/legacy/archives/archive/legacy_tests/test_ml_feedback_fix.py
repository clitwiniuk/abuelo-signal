#!/usr/bin/env python3
"""
Test script para verificar que el ML feedback fix funciona
Simula el cierre de una posición y verifica que el evento llega al ML Engine
"""

import asyncio
import logging
import sys
from datetime import datetime
from core.events import AsyncEventBus, EventTypes
from core.interfaces import Position, Signal, SignalType
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_ml_feedback():
    """Test ML feedback flow"""
    print("🧪 Testing ML Feedback Fix")
    print("=" * 50)
    
    # 1. Create event bus
    event_bus = AsyncEventBus()
    
    # 2. Create ML Engine
    ml_engine = MLMultiStrategyEngine()
    await ml_engine.initialize(event_bus)
    
    # 3. Simulate a position that was opened by ML Engine
    symbol = "TEST"
    entry_price = 10.0
    quantity = 100
    
    # Add to ML Engine's active trades (simulate entry)
    ml_engine.active_trades["test_trade_123"] = {
        'symbol': symbol,
        'strategy': 'gap_go',
        'entry_price': entry_price,
        'entry_time': datetime.now(),
        'context': None,  # Simplified for test
        'signal_confidence': 0.8,
        'trade_opened': True
    }
    
    print(f"✅ Simulated opening position: {symbol} @ ${entry_price}")
    print(f"   Active trades before: {len(ml_engine.active_trades)}")
    
    # 4. Simulate position closure with profit
    exit_price = 12.0  # 20% profit
    pnl = (exit_price - entry_price) * quantity  # $200 profit
    
    # Create position with realized PnL
    position = Position(
        symbol=symbol,
        quantity=quantity,
        avg_price=entry_price,
        market_value=exit_price * quantity,
        realized_pnl=pnl
    )
    
    # 5. Emit position_closed event
    from core.events import create_position_event
    event = create_position_event(position, EventTypes.POSITION_CLOSED)
    
    print(f"📡 Emitting position_closed event...")
    print(f"   Symbol: {symbol}, PnL: ${pnl:.2f}")
    
    # Capture ML Engine response
    original_update_model = ml_engine.ml_selector.update_model if ml_engine.ml_selector else None
    feedback_received = False
    
    def mock_update_model(context, strategy, reward):
        nonlocal feedback_received
        feedback_received = True
        print(f"🤖 ML MODEL UPDATED!")
        print(f"   Strategy: {strategy}")
        print(f"   Reward: {reward:.3f}")
        print(f"   Feedback received: ✅")
        # Call original if exists
        if original_update_model:
            return original_update_model(context, strategy, reward)
    
    if ml_engine.ml_selector:
        ml_engine.ml_selector.update_model = mock_update_model
    
    # 6. Publish the event
    await event_bus.publish(event)
    
    # 7. Wait a bit for async processing
    await asyncio.sleep(0.1)
    
    # 8. Check results
    print(f"\n📊 RESULTS:")
    print(f"   Feedback received: {'✅ YES' if feedback_received else '❌ NO'}")
    print(f"   Active trades after: {len(ml_engine.active_trades)}")
    
    if feedback_received:
        print(f"\n🎉 SUCCESS: ML feedback is now working!")
        print(f"   The ML Engine will learn from this trade's PnL")
        print(f"   Model will be saved periodically for persistence")
    else:
        print(f"\n❌ FAILURE: ML feedback still not working")
        print(f"   Check event handler registration and active trades")
    
    print("=" * 50)
    return feedback_received

async def main():
    try:
        success = await test_ml_feedback()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())