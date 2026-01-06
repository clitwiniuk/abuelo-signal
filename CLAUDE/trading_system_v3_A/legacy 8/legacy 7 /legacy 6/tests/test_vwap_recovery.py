"""
Test for _detect_vwap_recovery method in DailyPlaysWorkerLogic
Verifies that the method correctly returns Tuple[bool, str, float]
"""

import unittest
from unittest.mock import Mock, MagicMock
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic


class TestVWAPRecovery(unittest.TestCase):
    """Test cases for _detect_vwap_recovery method"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock execution engine and risk manager
        self.mock_execution_engine = Mock()
        self.mock_risk_manager = Mock()
        
        # Create worker instance without config (uses defaults)
        self.worker = DailyPlaysWorkerLogic(
            execution_engine=self.mock_execution_engine,
            risk_manager=self.mock_risk_manager,
            config=None
        )

    def _create_mock_bar(self, high, low, close, volume):
        """Helper to create mock bar objects"""
        bar = Mock()
        bar.high = high
        bar.low = low
        bar.close = close
        bar.volume = volume
        return bar

    def test_insufficient_bars(self):
        """Test with insufficient bars (< 5)"""
        bars = [
            self._create_mock_bar(10.5, 10.0, 10.2, 1000),
            self._create_mock_bar(10.6, 10.1, 10.3, 1100),
        ]
        
        vwap_price = 10.0
        current_price = 10.5
        symbol = "TEST"
        
        # Call method
        recovery_detected, details, support_level = self.worker._detect_vwap_recovery(
            bars, vwap_price, current_price, symbol
        )
        
        # Assertions
        self.assertIsInstance(recovery_detected, bool)
        self.assertIsInstance(details, str)
        self.assertIsInstance(support_level, float)
        self.assertFalse(recovery_detected)
        self.assertEqual(support_level, 0.0)
        self.assertIn("Insufficient bars", details)

    def test_current_price_below_vwap(self):
        """Test when current price is still below VWAP (no recovery)"""
        bars = [
            self._create_mock_bar(10.5, 9.5, 10.0, 1000),
            self._create_mock_bar(10.2, 9.3, 9.8, 1100),
            self._create_mock_bar(10.0, 9.2, 9.5, 1200),
            self._create_mock_bar(9.8, 9.0, 9.3, 1300),
            self._create_mock_bar(9.7, 9.1, 9.4, 1400),
        ]
        
        vwap_price = 10.0
        current_price = 9.5  # Below VWAP
        symbol = "TEST"
        
        # Call method
        recovery_detected, details, support_level = self.worker._detect_vwap_recovery(
            bars, vwap_price, current_price, symbol
        )
        
        # Assertions
        self.assertIsInstance(recovery_detected, bool)
        self.assertIsInstance(details, str)
        self.assertIsInstance(support_level, float)
        self.assertFalse(recovery_detected)
        self.assertEqual(support_level, 0.0)
        self.assertIn("still below VWAP", details)

    def test_vwap_recovery_detected(self):
        """Test successful VWAP recovery detection"""
        bars = [
            self._create_mock_bar(10.5, 10.0, 10.2, 1000),
            self._create_mock_bar(10.2, 9.5, 9.8, 1100),   # Dip below VWAP
            self._create_mock_bar(10.0, 9.3, 9.5, 1200),   # Lower low
            self._create_mock_bar(10.5, 9.5, 10.0, 1300),  # Recovery starts
            self._create_mock_bar(11.0, 10.2, 10.8, 1400), # Above VWAP
        ]
        
        vwap_price = 10.0
        current_price = 10.8  # Above VWAP (recovery confirmed)
        symbol = "TEST"
        
        # Call method
        recovery_detected, details, support_level = self.worker._detect_vwap_recovery(
            bars, vwap_price, current_price, symbol
        )
        
        # Assertions
        self.assertIsInstance(recovery_detected, bool)
        self.assertIsInstance(details, str)
        self.assertIsInstance(support_level, float)
        self.assertTrue(recovery_detected)
        self.assertGreater(support_level, 0.0)
        self.assertIn("VWAP Reclaim", details)
        # Support level should be the recent low (9.3)
        self.assertEqual(support_level, 9.3)

    def test_strong_vwap_recovery(self):
        """Test strong VWAP recovery (min price close to VWAP)"""
        bars = [
            self._create_mock_bar(10.5, 10.0, 10.2, 1000),
            self._create_mock_bar(10.2, 9.9, 10.0, 1100),  # Slight dip near VWAP
            self._create_mock_bar(10.3, 9.95, 10.1, 1200), # Stays near VWAP
            self._create_mock_bar(10.5, 10.1, 10.3, 1300), # Recovery
            self._create_mock_bar(11.0, 10.3, 10.8, 1400), # Strong move up
        ]
        
        vwap_price = 10.0
        current_price = 10.8
        symbol = "TEST"
        
        # Call method
        recovery_detected, details, support_level = self.worker._detect_vwap_recovery(
            bars, vwap_price, current_price, symbol
        )
        
        # Assertions
        self.assertTrue(recovery_detected)
        self.assertIn("strong", details.lower())
        # Support level should be min price (9.9)
        self.assertAlmostEqual(support_level, 9.9, places=2)

    def test_return_types(self):
        """Test that return types are always correct regardless of scenario"""
        test_cases = [
            # (bars_count, vwap, current_price)
            (3, 10.0, 10.5),   # Insufficient bars
            (5, 10.0, 9.5),    # Below VWAP
            (5, 10.0, 10.5),   # Above VWAP
        ]
        
        for bars_count, vwap, current_price in test_cases:
            bars = [
                self._create_mock_bar(10.0 + i*0.1, 9.0 + i*0.1, 9.5 + i*0.1, 1000)
                for i in range(bars_count)
            ]
            
            result = self.worker._detect_vwap_recovery(bars, vwap, current_price, "TEST")
            
            # Verify tuple with 3 elements
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 3)
            
            # Verify types
            recovery_detected, details, support_level = result
            self.assertIsInstance(recovery_detected, bool)
            self.assertIsInstance(details, str)
            self.assertIsInstance(support_level, float)


if __name__ == '__main__':
    unittest.main()
