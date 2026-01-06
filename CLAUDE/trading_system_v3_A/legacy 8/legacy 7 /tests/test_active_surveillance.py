
import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.base_worker_logic import BaseWorkerLogic

# Mock Broker
class MockBroker:
    def __init__(self):
        self.prices = {}
        self.orders = []
        self.positions = {}
        self.batch_price_manager = self
        
    def get_price(self, symbol):
        return self.prices.get(symbol, 0.0)
        
    def get_last_price(self, symbol):
        # Async method mock
        async def _get():
            return self.prices.get(symbol, 0.0)
        return _get()
        
    async def place_order(self, order):
        self.orders.append(order)
        print(f"broker: Order placed {order.action} {order.quantity} {order.symbol}")
        if order.action == 'BUY':
             self.positions[order.symbol] = {'quantity': order.quantity, 'entry_price': self.prices.get(order.symbol, 0)}
        elif order.action == 'SELL':
             if order.symbol in self.positions:
                 del self.positions[order.symbol]
        return True

    async def close_position(self, symbol, quantity):
        print(f"broker: Closing position {symbol}")
        if symbol in self.positions:
            del self.positions[symbol]
        return True
        
    async def subscribe_to_positions(self, symbols):
        print(f"broker: Subscribed to {symbols}")
        pass

# Test Worker Implementation
class TestWorkerLogic(BaseWorkerLogic):
    def __init__(self, broker):
        super().__init__(worker_name="test_worker", broker=broker)
        # Manually enable surveillance for test
        self.surveillance_enabled = True
        self.watch_time_minutes = 30
        self.min_quality = 60
        # Config mock
        class Config:
            min_quality_score_for_watch = 60.0
        self.config = Config()

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        price = opportunity.get('current_price', 0)
        # Enter if price > 100
        should = price > 100.0
        print(f"worker: Checking entry.. price={price} > 100? {should}")
        return should

    async def should_exit(self, symbol, position, current_price) -> Tuple[bool, str]:
        # Exit if price < 90
        should = current_price < 90.0
        print(f"worker: Checking exit.. price={current_price} < 90? {should}")
        return should, "TestExit" if should else ""
        
    # Override to avoid complex dependency
    async def _execute_entry(self, opportunity):
        symbol = opportunity.get('symbol')
        print(f"worker: Executing entry for {symbol}")
        # Mimic base logic simplified
        self.active_positions[symbol] = {
            'position': {'quantity': 100, 'symbol': symbol},
            'quantity': 100, # Added top-level quantity
            'opportunity_data': opportunity,
            'entry_time': datetime.now(),
            'entry_price': opportunity['current_price']
        }
        await self.broker.place_order(type('Order', (), {'symbol': symbol, 'action': 'BUY', 'quantity': 100})())
        return True

async def run_test():
    logging.basicConfig(level=logging.INFO)
    print("--- START ACTIVE SURVEILLANCE TEST ---")
    
    broker = MockBroker()
    worker = TestWorkerLogic(broker)
    
    symbol = "TEST_SYM"
    
    # 1. Reject -> Watch
    print("\n[STEP 1] Rejection Test (Price 95, Quality 80)")
    broker.prices[symbol] = 95.0
    opp = {
        'symbol': symbol, 
        'current_price': 95.0, 
        'quality_score': 80.0,
        'gap_percentage': 5.0
    }
    
    await worker.process_opportunity(opp)
    
    if symbol in worker.candidates:
        print("✅ SUCCESS: Symbol added to watchlist after rejection")
    else:
        print("❌ FAILURE: Symbol NOT added to watchlist")
        return

    # 2. Monitor -> No Trigger
    print("\n[STEP 2] Monitor (Price 98 - Still below 100)")
    broker.prices[symbol] = 98.0
    await worker._monitor_candidates()
    
    if symbol in worker.candidates and symbol not in worker.active_positions:
        print("✅ SUCCESS: Symbol remains in watchlist, no entry yet")
    else:
        print("❌ FAILURE: Symbol moved prematurely or lost")
        return

    # 3. Monitor -> Trigger Entry
    print("\n[STEP 3] Monitor (Price 105 - Breakout!)")
    broker.prices[symbol] = 105.0
    await worker._monitor_candidates()
    
    if symbol not in worker.candidates and symbol in worker.active_positions:
        print("✅ SUCCESS: Symbol removed from watchlist and entered active position")
    else:
        print(f"❌ FAILURE: Entry state mismatch. Candidates: {symbol in worker.candidates}, Active: {symbol in worker.active_positions}")
        return
        
    # 4. Exit -> Re-Watch
    print("\n[STEP 4] Exit (Price 85 - Stop Loss)")
    # Trigger exit logic manually or via loop monitor
    # BaseWorker has _monitor_positions loop logic, let's just call _execute_exit directly for isolation
    # as we want to test the *hook* in _execute_exit
    
    await worker._execute_exit(symbol, "Stop Loss Test", 85.0)
    
    if symbol in worker.active_positions:
         print("❌ FAILURE: Symbol still in active positions")
         return
         
    if symbol in worker.candidates:
        print("✅ SUCCESS: Symbol re-added to watchlist after exit (Post-Trade Surveillance)")
    else:
        print("❌ FAILURE: Symbol NOT re-added to watchlist after exit")
        return

    print("\n--- TEST COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    asyncio.run(run_test())
