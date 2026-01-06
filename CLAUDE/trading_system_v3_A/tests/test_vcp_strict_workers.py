
import unittest
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from strategies.workers.vcp_strict_long_worker_logic import VCPStrictLongWorkerLogic
from strategies.workers.vcp_strict_short_worker_logic import VCPStrictShortWorkerLogic

# Setup basics
logging.basicConfig(level=logging.INFO)

class MockBar:
    def __init__(self, high, low, close, volume):
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.open = (high + low) / 2

class TestVCPStrictWorkersRobust(unittest.TestCase):
    def setUp(self):
        self.mock_engine = MagicMock()
        self.mock_risk = MagicMock()
        self.mock_config = MagicMock()
        
        # Config values
        self.mock_config.getfloat.side_effect = lambda s, k, fallback=0.0: fallback
        self.mock_config.getint.side_effect = lambda s, k, fallback=0: fallback
        self.mock_config.vcp_strict_min_price = 1.0
        self.mock_config.vcp_strict_max_price = 25.0
        self.mock_config.vcp_strict_min_volume_ratio = 1.0
        self.mock_config.vcp_strict_min_quality_score = 60.0
        self.mock_config.vcp_strict_require_catalyst = False
        self.mock_config.vcp_strict_min_vwap_slope_long = 0.10
        self.mock_config.vcp_strict_max_vwap_slope_short = -0.10
        self.mock_config.vcp_strict_min_contractions = 1
        self.mock_config.vcp_strict_min_expansions = 1 # CRITICAL: Set to int to avoid MagicMock comparison
        self.mock_config.enable_ods_filters = True
        
        # Instantiate
        self.long_worker = VCPStrictLongWorkerLogic(
            execution_engine=self.mock_engine,
            risk_manager=self.mock_risk,
            config=self.mock_config
        )
        
        self.short_worker = VCPStrictShortWorkerLogic(
            execution_engine=self.mock_engine,
            risk_manager=self.mock_risk,
            config=self.mock_config
        )

        # Mock Internals (Sanity Check Mode)
        # Avoid complex pattern math, assume it passes to test FLOW
        self.long_worker._calculate_vcp_completion = AsyncMock(return_value=(100.0, 10.0))
        self.long_worker._detect_contractions = MagicMock(return_value=[1, 2])
        self.long_worker._validate_volume_pattern = MagicMock(return_value=True)
        self.long_worker._detect_vcp_pivot = MagicMock(return_value=(True, "Pivot!", 10.0))
        self.long_worker._analyze_smallcap_fundamentals = AsyncMock(return_value={'is_halt_risk': False})
        self.long_worker._analyze_daily_potential_for_signal = AsyncMock(return_value={'is_52_week_high': False})
        self.long_worker.check_ods_filters = AsyncMock(return_value=(True, 1.0))
        self.long_worker.is_within_entry_hours = MagicMock(return_value=(True, 10.0))

        self.short_worker._detect_expansions = MagicMock(return_value=[1, 2])
        self.short_worker._validate_expansions_increasing = MagicMock(return_value=True)
        self.short_worker._detect_inverse_vcp_pivot = MagicMock(return_value=(True, "Pivot!", 10.0))
        self.short_worker._analyze_smallcap_fundamentals = AsyncMock(return_value={'is_halt_risk': False})
        self.short_worker._analyze_daily_potential_for_signal = AsyncMock(return_value={'is_52_week_high': False})
        self.short_worker.check_ods_filters = AsyncMock(return_value=(True, 1.0))
        self.short_worker.is_within_entry_hours = MagicMock(return_value=(True, 10.0))

    def create_bars(self):
        return [MockBar(10, 9, 9.5, 1000) for _ in range(100)]

    def test_long_entry_pass(self):
        async def run():
            # Patch Service Locator
            with patch('core.service_locator.get_unified_position_manager', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                # Mock Slope PASS
                self.long_worker._determine_vwap_slope = MagicMock(return_value=(0.20, 10.0))
                
                opportunity = {
                    'symbol': 'LONG_PASS', 'current_price': 10.0, 'volume_ratio': 2.0, 
                    'quality_score': 80, 'bars': self.create_bars(), 'timestamp': datetime.now()
                }
                
                result = await self.long_worker.should_enter(opportunity)
                
                self.assertTrue(result, "Should Enter Long")
                self.assertEqual(opportunity.get('trade_direction'), 'LONG')
        
        asyncio.run(run())

    def test_long_entry_fail_slope(self):
        async def run():
            with patch('core.service_locator.get_unified_position_manager', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                # Mock Slope FAIL (<0.10)
                self.long_worker._determine_vwap_slope = MagicMock(return_value=(0.05, 10.0))
                
                opportunity = {
                    'symbol': 'LONG_FAIL', 'current_price': 10.0, 'volume_ratio': 2.0, 
                    'quality_score': 80, 'bars': self.create_bars(), 'timestamp': datetime.now()
                }
                
                result = await self.long_worker.should_enter(opportunity)
                
                self.assertFalse(result, "Should Reject Long due to Slope")
        
        asyncio.run(run())

    def test_short_entry_pass(self):
        async def run():
            with patch('core.service_locator.get_unified_position_manager', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                # Trace
                print("DEBUG: Checking Short Entry")
                
                # Mock Slope PASS (< -0.10)
                def slope_se(b):
                    print("DEBUG: Short Slope Called (-0.20)")
                    return -0.20, 10.0
                self.short_worker._determine_vwap_slope = MagicMock(side_effect=slope_se)
                
                # Mock Expansions
                def exp_se(b):
                    print("DEBUG: Expansions Called")
                    return [1, 2]
                self.short_worker._detect_expansions = MagicMock(side_effect=exp_se)
                
                # Mock Validation
                def val_se(e):
                    print("DEBUG: Validate Called")
                    return True
                self.short_worker._validate_expansions_increasing = MagicMock(side_effect=val_se)
                
                opportunity = {
                    'symbol': 'SHORT_PASS', 'current_price': 10.0, 'volume_ratio': 2.0, 
                    'quality_score': 80, 'bars': self.create_bars(), 'timestamp': datetime.now()
                }
                
                result = await self.short_worker.should_enter(opportunity)
                print(f"DEBUG: Result {result}")
                
                self.assertTrue(result, "Should Enter Short")
                self.assertEqual(opportunity.get('trade_direction'), 'SHORT')
        
        asyncio.run(run())

    def test_short_entry_fail_slope(self):
        async def run():
            with patch('core.service_locator.get_unified_position_manager', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                # Mock Slope FAIL (> -0.10)
                self.short_worker._determine_vwap_slope = MagicMock(return_value=(-0.05, 10.0))
                
                opportunity = {
                    'symbol': 'SHORT_FAIL', 'current_price': 10.0, 'volume_ratio': 2.0, 
                    'quality_score': 80, 'bars': self.create_bars(), 'timestamp': datetime.now()
                }
                
                result = await self.short_worker.should_enter(opportunity)
                
                self.assertFalse(result, "Should Reject Short due to Slope")
        
        asyncio.run(run())

if __name__ == '__main__':
    unittest.main()
