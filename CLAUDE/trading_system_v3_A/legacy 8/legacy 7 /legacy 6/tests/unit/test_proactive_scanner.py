"""
Unit Tests for ProactiveScanner
Tests pattern detection logic in isolation
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.proactive_scanner import ProactiveScanner

class TestProactiveScannerPatterns(unittest.IsolatedAsyncioTestCase):
    """Test pattern detection methods"""
    
    @patch('scanner.smallcap.proactive_scanner.MultiSourceNewsChecker')
    @patch('scanner.smallcap.proactive_scanner.IBKRAdapter')
    def setUp(self, mock_adapter, mock_news):
        self.scanner = ProactiveScanner(ibkr_adapter=mock_adapter)
        self.scanner.logger = MagicMock()
        
    def test_green_day_1_detection(self):
        """Test Green Day 1 pattern detection"""
        # Create mock daily bars: 3 red days, then 1 green day
        # Today needs > 20% gain and > 50% retention
        bars = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=4),
            'open': [10.0, 9.5, 9.0, 8.5],
            'high': [10.2, 9.7, 9.2, 11.0], # High 11.0
            'low': [9.5, 9.0, 8.5, 8.5],
            'close': [9.5, 9.0, 8.5, 10.5], # PrevClose 8.5, High 11.0, Close 10.5
            # Gain = (10.5 - 8.5)/8.5 = 23.5% (PASS)
            # Retention = (10.5 - 8.5) / (11.0 - 8.5) = 2.0 / 2.5 = 80% (PASS)
            'volume': [100000, 100000, 100000, 300000] # Vol surge 3x
        })
        
        # We need to mock _calculate_daily_rel_vol because it might return 1.0 for short history
        self.scanner._calculate_daily_rel_vol = MagicMock(return_value=3.0)
        
        result = self.scanner._is_green_day_1(bars)
        self.assertTrue(result, "Should detect Green Day 1 pattern with 20% gain")

    async def test_analyze_structure_integration(self):
        """Test the full analysis pipeline with mocks"""
        result_mock = MagicMock(symbol='TEST')
        
        # Mock bars for _analyze_daily_structure (internal call to self.ibkr_adapter.get_bars)
        bars_mock = [MagicMock(date=datetime.now(), open=8.5, high=11.0, low=8.5, close=10.5, volume=300000) for _ in range(10)]
        self.scanner.ibkr_adapter.get_bars = AsyncMock(return_value=bars_mock)
        
        # Mock patterns
        self.scanner._is_green_day_1 = MagicMock(return_value=True)
        self.scanner._is_fake_breakdown = MagicMock(return_value=False)
        self.scanner._calculate_daily_rel_vol = MagicMock(return_value=3.0)
        self.scanner._find_resistance = MagicMock(return_value=12.0)
        
        # Mock catalyst and borrows
        self.scanner._check_news_catalyst = AsyncMock(return_value=True)
        self.scanner._check_ibkr_borrows = AsyncMock(return_value=(True, 'NORMAL'))
        
        # Run
        pattern = await self.scanner._analyze_daily_structure(result_mock)
        
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern['pattern_type'], 'GREEN_DAY_1')
        self.assertEqual(pattern['symbol'], 'TEST')
        
    async def test_etb_success(self):
        """Test that ETB (Easy to Borrow) candidates are ACCEPTED"""
        result_mock = MagicMock(symbol='TEST_ETB')
        self.scanner.ibkr_adapter.get_bars = AsyncMock(return_value=[MagicMock(date=datetime.now(), open=8.5, high=11.0, low=8.5, close=10.5, volume=300000)] * 10)
        self.scanner._is_green_day_1 = MagicMock(return_value=True)
        self.scanner._calculate_daily_rel_vol = MagicMock(return_value=3.0)
        self.scanner._find_resistance = MagicMock(return_value=12.0)
        self.scanner._check_news_catalyst = AsyncMock(return_value=True)
        
        # Mock ETB response
        self.scanner.ibkr_adapter.get_short_data = AsyncMock(return_value={'is_etb': True, 'short_status': 'ETB', 'shortable_shares': 10000})
        
        # Test the check directly first
        can_borrow, quality = await self.scanner._check_ibkr_borrows('TEST_ETB')
        self.assertTrue(can_borrow)
        self.assertEqual(quality, 'NORMAL')

    async def test_htb_success(self):
        """Test that HTB (Hard to Borrow) candidates are ACCEPTED (Ideal for Squeeze)"""
        # Mock HTB response from adapter
        self.scanner.ibkr_adapter.get_short_data = AsyncMock(return_value={'is_etb': False, 'short_status': 'HTB', 'shortable_shares': 500})
        
        # Test the check directly
        can_borrow, quality = await self.scanner._check_ibkr_borrows('TEST_HTB')
        self.assertTrue(can_borrow, "Should accept HTB candidates as they fuel the squeeze")
        self.assertEqual(quality, 'IDEAL')
        self.scanner.logger.info.assert_any_call("🔥 TEST_HTB: IDEAL Squeeze Potential - Hard to Borrow")

    async def test_ultimate_squeeze_rejection(self):
        """Actually, it's not rejection anymore, it's ULTIMATE acceptance"""
        result_mock = MagicMock(symbol='TEST_ULTIMATE')
        self.scanner.ibkr_adapter.get_bars = AsyncMock(return_value=[MagicMock(date=datetime.now(), open=8.5, high=11.0, low=8.5, close=10.5, volume=300000)] * 10)
        self.scanner._is_green_day_1 = MagicMock(return_value=True)
        self.scanner._calculate_daily_rel_vol = MagicMock(return_value=3.0)
        self.scanner._find_resistance = MagicMock(return_value=12.0)
        self.scanner._check_news_catalyst = AsyncMock(return_value=True)
        
        # Mock ZERO borrows
        self.scanner.ibkr_adapter.get_short_data = AsyncMock(return_value={'is_etb': False, 'short_status': 'NONE', 'shortable_shares': 0})
        
        # Run
        pattern = await self.scanner._analyze_daily_structure(result_mock)
        
        self.assertIsNotNone(pattern, "Should ACCEPT zero borrows as ULTIMATE signal")
        self.scanner.logger.info.assert_any_call("💎 TEST_ULTIMATE: ULTIMATE Squeeze Potential - Zero borrows available")

    def test_fake_breakdown_detection(self):
        """Test Fake Breakdown pattern detection"""
        # Create bars: support at 10.0
        # Today breaks below 10.0 (low 9.5) but reclaims (close 10.5)
        bars = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=10),
            'open': [10.5] * 9 + [9.8],
            'high': [11.0] * 9 + [10.6],
            'low': [10.0] * 5 + [10.1, 10.2, 10.1, 10.2, 9.5], # Today breaks prev min(low)=10.0
            'close': [10.5] * 9 + [10.5], # Reclaimed 10.0
            'volume': [100000] * 10
        })
        
        result = self.scanner._is_fake_breakdown(bars)
        self.assertTrue(result, "Should detect Fake Breakdown pattern")

if __name__ == '__main__':
    # Use nested async for tests if needed, but standard unittest.main is fine for sync tests
    unittest.main()

if __name__ == '__main__':
    unittest.main()
