
import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock pandas_ta before importing system modules
sys.modules['pandas_ta'] = MagicMock()

from datetime import datetime
import asyncio

# Import target
from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidCapWorkerLogic

class TestMidCapWorkerLogic(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_adapter = MagicMock()
        self.mock_risk_manager = MagicMock()
        self.worker = DailyPlaysMidCapWorkerLogic(self.mock_adapter, self.mock_risk_manager)
        
        # Mock Config Loading
        # The worker sets self.config_section = 'DAILY_PLAYS_MIDCAP_STRATEGY'
        self.worker.min_price = 10.0
        self.worker.max_price = 100.0 # Reverted to 100.0 per user request
        self.worker.max_position_hours = 120.0
        
        # Mock Opportunity
        self.opportunity = {
            'symbol': 'AMD',
            'current_price': 150.0,
            'catalyst_type': 'EARNINGS',
            'catalyst_strength': 8,
            'quality_score': 85,
            'avg_volume': 1000000,
            'volume_ratio': 2.0,
            'bars_history': [], # Mock empty bars
            'gap_percentage': 6.0
        }
    
    async def test_section_name(self):
        """Verify worker uses correct config section"""
        self.assertEqual(self.worker.config_section, 'DAILY_PLAYS_MIDCAP_STRATEGY')

    @patch('strategies.workers.daily_plays_worker_logic.DailyPlaysWorkerLogic.should_enter')
    async def test_should_enter_swing_override(self, mock_super_should_enter):
        """Test that should_enter sets EOD_safe and overrides super logic"""
        # Logic is:
        # 1. Override self.opportunity params
        # 2. Call super().should_enter()
        
        # Mock super to return True (and be awaitable/async)
        # Since logic is async, return_value should be a future or result if awaited?
        # If super().should_enter is async, mock needs to handle await
        # But wait, is super().should_enter async? If so, we mock it as AsyncMock would be better,
        # or set return_value to True and be mindful.
        # Let's assume it is async based on warning.
        
        f = asyncio.Future()
        f.set_result(True)
        mock_super_should_enter.return_value = f
        
        # Run
        decision = await self.worker.should_enter(self.opportunity)
        
        # Assertions
        # 1. Check opportunity modifications
        self.assertTrue(self.opportunity['EOD_safe'])
        self.assertEqual(self.opportunity['trading_horizon'], 'SWING')
        
        # 2. Check Decision
        self.assertTrue(decision)

    async def test_catalyst_validation(self):
        """Test Catalyst logic filtering (inherited but configured)"""
        # If catalyst is weak, should reject?
        # MidCap worker relies on super's logic but sets strong_catalysts.
        # Let's verify strong_catalysts list includes 'FDA' etc.
        self.assertIn('FDA', self.worker.strong_catalysts)
        self.assertIn('EARNINGS', self.worker.strong_catalysts)
        self.assertIn('M&A', self.worker.strong_catalysts)

if __name__ == '__main__':
    unittest.main()
