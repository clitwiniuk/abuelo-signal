
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import pandas as pd

from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic
from core.parabolic_extension_detector import ParabolicSignal, ParabolicState

class TestShortParabolicWorkerLogic(unittest.TestCase):
    def setUp(self):
        self.mock_risk_manager = MagicMock()
        self.mock_risk_manager.can_open_position.return_value = (True, "Risk OK")
        
        self.worker = ShortParabolicWorkerLogic(
            worker_name="short_parabolic_test",
            symbol="TEST",
            account_id="DU12345",
            risk_manager=self.mock_risk_manager
        )
        # Mock logger to avoid clutter
        self.worker.logger = MagicMock()

    def test_entry_logic_valid_setup(self):
        """Test a perfect setup for short entry"""
        # 1. Setup Mock Bar Data (Parabolic exhaustion)
        bars = [
            MagicMock(close=10.0, high=10.2, low=9.8, volume=100000),
            MagicMock(close=11.0, high=11.2, low=10.8, volume=200000), # Spike
            MagicMock(close=12.0, high=12.5, low=11.8, volume=500000), # Climax
            MagicMock(close=11.5, high=12.6, low=11.4, volume=300000), # Reversal/Pullback
        ]
        
        # 2. Setup Detector Signal
        signal = ParabolicSignal(
            symbol="TEST",
            is_parabolic=True,
            stage="LATE", # Critical
            exhaustion_score=0.8, # Critical
            strength_score=0.5,
            direction="UP",
            short_entry_opportunity=True, # Critical
            metadata={'stop_loss': 12.7}
        )
        
        # 3. Inject Mock Components
        self.worker.detector.detect_parabolic_extension = MagicMock(return_value=signal)
        self.worker.risk_manager.check_risk_reward = MagicMock(return_value=True)

        # 4. Run should_enter
        # Mock current price slightly below the breakdown (confirming weakness)
        current_price = 11.5
        
        should_enter, reason, stop, target = self.worker.should_enter(bars, current_price)
        
        self.assertTrue(should_enter)
        self.assertIn("LATE stage", reason)
        self.assertIn("Exhaustion", reason)
        self.assertGreater(stop, current_price) # Stop for short is above price
        self.assertLess(target, current_price) # Target for short is below price

    def test_entry_logic_rejected_early_stage(self):
        """Test rejection when parabolic move is still early/strong"""
        bars = [MagicMock(close=10.0), MagicMock(close=11.0)]
        
        signal = ParabolicSignal(
            symbol="TEST",
            is_parabolic=True,
            stage="EARLY", # Rejected
            exhaustion_score=0.1,
            strength_score=0.8,
            direction="UP",
            short_entry_opportunity=False,
            metadata={}
        )
        
        self.worker.detector.detect_parabolic_extension = MagicMock(return_value=signal)
        
        should_enter, reason, _, _ = self.worker.should_enter(bars, 11.0)
        
        self.assertFalse(should_enter)
        self.assertEqual(reason, "Not a short opportunity")

    def test_risk_reward_calculation(self):
        """Test R:R logic specifically"""
        # Price 10.0, Stop 10.5 (Risk 0.5), Target 9.0 (Reward 1.0) -> R:R 2.0 (OK)
        
        signal = ParabolicSignal(
            symbol="TEST",
            is_parabolic=True,
            stage="LATE",
            exhaustion_score=0.8,
            strength_score=0.5,
            direction="UP",
            short_entry_opportunity=True,
            metadata={'stop_loss': 10.5, 'target_price': 8.0} # 2.5 Reward / 0.5 Risk = 5R
        )
        self.worker.detector.detect_parabolic_extension = MagicMock(return_value=signal)
        
        should_enter, _, stop, target = self.worker.should_enter([], 10.0)
        
        self.assertTrue(should_enter)
        self.assertEqual(stop, 10.5)
        
        # Now fail R:R
        # Price 10.0, Stop 10.5 (Risk 0.5), Target 9.8 (Reward 0.2) -> R:R 0.4 (Fail)
        signal.metadata['target_price'] = 9.8
        
        # Need to verify R:R inside worker. calculate_risk_reward is internal or part of check
        # Assuming worker logic recalculates or validates it
        
        # In the actual implementation, should_enter calculates R:R. 
        # Let's see if the worker relies on detector's targets or calculates its own.
        # Based on my view of valid worker code, it usually calculates R:R.
        
