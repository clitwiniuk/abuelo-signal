import unittest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
import numpy as np
from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic

class MockBar:
    def __init__(self, high):
        self.high = high

class TestShortParabolicSynthetic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create Mocks for dependencies
        self.mock_execution_engine = MagicMock()
        self.mock_risk_manager = MagicMock()
        
        # Initialize worker with dependencies
        self.worker = ShortParabolicWorkerLogic(
            "short_parabolic", 
            self.mock_execution_engine,
            self.mock_risk_manager
        )
        
        # Ensure execution engine broker is mocked for ETB
        self.worker.execution_engine.broker = MagicMock()
        
        # Mock get_short_data to return ETB=True
        future = asyncio.Future()
        future.set_result({'is_etb': True, 'shortable_shares': 50000, 'short_status': 'Available'})
        self.worker.execution_engine.broker.get_short_data = MagicMock(return_value=future)
        
        # Mock Logger to avoid clutter
        self.worker.logger = MagicMock()

    async def test_perfect_short_setup(self):
        print("\n🧪 Testing Perfect Short Setup (Synthetic Data)...")
        
        symbol = 'FAKE_WINNER'
        
        # 1. Create Parabolic Data manually (LATE stage, Exhausted)
        parabolic_data = {
            'is_parabolic': True,
            'stage': 'LATE',
            'exhaustion_score': 0.95,
            'vertical_score': 0.8,
            'short_entry_opportunity': True  # CRITICAL: Signal Confirmation
        }
        
        # 2. Mock History Bars (for HOD calculation)
        # Ramping up to 12.00 then dropping to 11.50
        # HOD = 12.00. Current Price = 11.50. 
        # Stop = 12.00 * 1.02 = 12.24. Risk = 12.24 - 11.50 = 0.74
        # Target = 11.50 * 0.85 = 9.77. Reward = 11.50 - 9.77 = 1.73
        # R:R = 1.73 / 0.74 = 2.33 (> 2.0 required) -> SHOULD PASS
        pk_high = 12.00
        bars_history = [MockBar(high=10 + i*0.1) for i in range(20)] # up to 12.0
        
        opportunity = {
            'symbol': symbol,
            'current_price': 11.50, # Dropping
            'volume': 1_000_000,   # > 500k Requirement
            'parabolic_data': parabolic_data,
            'bars_history': bars_history,
            'time': datetime(2025, 12, 17, 10, 30)
        }
        
        # 3. Execute
        should_enter = await self.worker.should_enter(opportunity)
        
        # 4. Verify
        if should_enter:
            print(f"✅ Trade ACCEPTED for {symbol}!")
            print(f"   Reason: Late Stage Parabolic + High R:R + ETB Available")
        else:
            print(f"❌ Trade REJECTED for {symbol}")
            # Print calls to logger to debug
            for call in self.worker.logger.debug.call_args_list:
                print(f"   Log: {call}")
            for call in self.worker.logger.warning.call_args_list:
                print(f"   Log: {call}")

        self.assertTrue(should_enter, "Worker should accept this perfect setup")

if __name__ == '__main__':
    unittest.main()
