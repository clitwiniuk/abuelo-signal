import unittest
from unittest.mock import MagicMock, AsyncMock
import logging
from datetime import datetime, timedelta, time
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from configparser import ConfigParser
from strategies.workers.orb_worker_logic import ORBWorkerLogic

# Mock Bar class
class MockBar:
    def __init__(self, timestamp, open_, high, low, close, volume):
        self.timestamp = timestamp
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

class TestORBWorker(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Setup Logger
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        root.setLevel(logging.DEBUG)
        handler = logging.FileHandler('debug_log.txt', mode='w')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root.addHandler(handler)
        
        # Setup Mock Config
        self.config = ConfigParser()
        self.config.add_section('ORB_STRATEGY')
        self.config.set('ORB_STRATEGY', 'orb_start_time', '09:30:00')
        self.config.set('ORB_STRATEGY', 'orb_end_time', '10:00:00')
        self.config.set('ORB_STRATEGY', 'entry_start_time', '09:35:00')
        self.config.set('ORB_STRATEGY', 'entry_end_time', '10:30:00')
        self.config.set('ORB_STRATEGY', 'min_price', '1.0')
        self.config.set('ORB_STRATEGY', 'max_price', '50.0')
        self.config.set('ORB_STRATEGY', 'min_avg_volume', '1000') # Low for testing
        self.config.set('ORB_STRATEGY', 'min_dollar_volume', '1000')
        self.config.set('ORB_STRATEGY', 'min_breakout_volume', '1.2')
        self.config.set('ORB_STRATEGY', 'min_quality_score', '50')
        self.config.set('ORB_STRATEGY', 'max_trades_per_symbol', '10')

        # Mock Dependencies
        self.execution_engine = MagicMock()
        self.execution_engine.is_symbol_blacklisted.return_value = False
        
        self.risk_manager = MagicMock()
        self.risk_manager.check_risk_approval.return_value = True

        # Initialize Worker
        self.worker = ORBWorkerLogic(
            worker_name="test_orb",
            execution_engine=self.execution_engine,
            risk_manager=self.risk_manager,
            config=self.config
        )
        
        # Mock Dependency Injection
        self.worker.check_ods_filters = AsyncMock(return_value=(True, 1.0))
        self.worker.calculate_pattern_completion = AsyncMock(return_value=0.0)
        self.worker._analyze_smallcap_fundamentals = AsyncMock(return_value={
            'is_halt_risk': False,
            'is_high_rotation': False
        })
        self.worker._check_risk_approval = AsyncMock(return_value=True)
        self.worker.should_exit = AsyncMock(return_value=(False, None))
        self.worker._analyze_daily_potential_for_signal = AsyncMock(return_value={
            'is_52_week_high': False
        })
        
        # Bypass unified manager check (mocking service locator is hard)
        # We can mock the method that calls it:
        # Actually ORB calls get_unified_position_manager inside should_enter.
        # We might need to mock core.service_locator.get_unified_position_manager
        
    def generate_bars(self, start_time_str, count, base_price=10.0, volume=10000):
        bars = []
        current_time = datetime.strptime(f"2025-10-20 {start_time_str}", "%Y-%m-%d %H:%M:%S")
        
        for i in range(count):
            # Create a small candle
            bars.append(MockBar(
                timestamp=current_time,
                open_=base_price,
                high=base_price + 0.05,
                low=base_price - 0.05,
                close=base_price,
                volume=volume
            ))
            current_time += timedelta(minutes=1)
        return bars

    async def test_perfect_orb_setup(self):
        print("\n--- TEST: Perfect ORB Setup ---")
        
        # 1. Generate ORB Range (9:30 - 10:00)
        # Price 10.00 - 10.50
        orb_bars = []
        current_time = datetime.strptime("2025-10-20 09:30:00", "%Y-%m-%d %H:%M:%S")
        for i in range(30):
            orb_bars.append(MockBar(
                timestamp=current_time,
                open_=10.0, high=10.5, low=10.0, close=10.2, volume=50000
            ))
            current_time += timedelta(minutes=1)
            
        # 2. Generate Breakout (10:00 - 10:05)
        # Breakout above 10.50 with Volume
        breakout_bars = []
        for i in range(5):
            breakout_bars.append(MockBar(
                timestamp=current_time,
                open_=10.55, high=10.70, low=10.55, close=10.65, volume=100000 # High volume
            ))
            current_time += timedelta(minutes=1)
            
        all_bars = orb_bars + breakout_bars
        
        # Opportunity Data
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.65,
            'timestamp': current_time, # 10:05
            'bars': all_bars,
            'quality_score': 80,
            'gap_percentage': 0.02
        }
        
        # Mock Unified Manager to prevent blocking
        with unittest.mock.patch('core.service_locator.get_unified_position_manager') as mock_get_unified:
             mock_manager = MagicMock()
             mock_manager.is_symbol_blocked.return_value = False
             mock_get_unified.return_value = mock_manager
             
             # Execute
             should_enter = await self.worker.should_enter(opportunity)
             
             print(f"\nDECISION: {should_enter}")
             self.assertTrue(should_enter, "Should enter on perfect setup")

    async def test_low_price_rejection(self):
        print("\n--- TEST: Low Price Rejection ---")
        
        bars = self.generate_bars("09:30:00", 35, base_price=0.20) # Below 1.0/0.5
        opportunity = {
            'symbol': 'PENNY',
            'current_price': 0.20,
            'timestamp': datetime.strptime("2025-10-20 10:05:00", "%Y-%m-%d %H:%M:%S"),
            'bars': bars,
            'quality_score': 80
        }
        
        with unittest.mock.patch('core.service_locator.get_unified_position_manager') as mock_get_unified:
             mock_manager = MagicMock()
             mock_manager.is_symbol_blocked.return_value = False
             mock_get_unified.return_value = mock_manager
             
             should_enter = await self.worker.should_enter(opportunity)
             print(f"\nDECISION: {should_enter}")
             self.assertFalse(should_enter, "Should reject low price")

if __name__ == '__main__':
    unittest.main()
