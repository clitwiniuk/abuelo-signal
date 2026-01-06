
import asyncio
import unittest
import logging
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

# Adjust path to include project root
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.ibkr_native_scanner import IBKRScanResult
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner

class TestScannerImprovements(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        self.scanner = SmallcapDailyScanner(config={'min_quality_score': 3.0, 'max_headlines_per_symbol': 5, 'catalyst_max_age': {}, 'news_age_multipliers': {}, 'fresh_news_threshold': 2, 'recent_news_threshold': 6, 'stale_news_threshold': 12, 'max_news_age_hours': 8, 'max_news_age_premarket': 16, 'max_plays_per_scan': 15, 'max_ibkr_results': 50})
        self.scanner.logger.setLevel(logging.DEBUG) # Force DEBUG level
        # Mock create_context to just return True (dummy)
        self.scanner._create_context = AsyncMock(return_value=MagicMock())

    def test_steady_gainer_logic(self):
        """Test that a 6% gainer above VWAP is accepted (IMMP scenario)"""
        
        # Mock bars for VWAP calc
        # Price steadily increasing: 10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
        # VWAP will be around 10.3
        # Current price 10.6 > VWAP
        bars = []
        for i in range(10):
            price = 10.0 + (i * 0.1)
            bars.append({'close': price, 'high': price, 'low': price, 'volume': 1000})
            
        result = IBKRScanResult(
            symbol="TEST1",
            contract=None,
            rank=1,
            distance="",
            benchmark="",
            projection="",
            legs="",
            current_price=10.9, # Clearly above VWAP (~10.45)
            volume=300000,
            bars_1min=bars
        )
        # Mock change_percentage (daily gain)
        result.change_percentage = 6.0 # 6% gain (above new 5% threshold)

        # Run analysis
        play = asyncio.run(self.scanner._analyze_intraday_mover_opportunity(result))
        
        # Verify it was accepted
        self.assertIsNotNone(play)
        if play:
            print(f"✅ TEST1 (Steady Gainer): Accepted with score {play.quality_score}")
            self.assertEqual(play.opportunity_type.value, "intraday_mover")

    def test_choppy_stock_logic(self):
        """Test that a 6% gainer BELOW VWAP is rejected (Choppy noise)"""
        
        # Mock bars where price crashed recently
        # Bars: 12, 12, 12, 12... then crash to 10.6
        # VWAP will be high (~12)
        # Current price 10.6 < VWAP
        bars = []
        for i in range(10):
            bars.append({'close': 12.0, 'high': 12.0, 'low': 12.0, 'volume': 1000})
            
        result = IBKRScanResult(
            symbol="TEST2",
            contract=None,
            rank=1,
            distance="",
            benchmark="",
            projection="",
            legs="",
            current_price=10.6, # Below VWAP (~12)
            volume=300000,
            bars_1min=bars
        )
        # Mock change_percentage
        result.change_percentage = 6.0 # 6% gain (still green for day, but fading)

        # Run analysis
        play = asyncio.run(self.scanner._analyze_intraday_mover_opportunity(result))
        
        # Verify it was rejected
        self.assertIsNone(play)
        print("✅ TEST2 (Choppy/Fading): Rejected (Below VWAP)")

    def test_low_volume_rejected(self):
        """Test that low volume is rejected"""
        result = IBKRScanResult(
            symbol="TEST3",
            contract=None,
            rank=1,
            distance="",
            benchmark="",
            projection="",
            legs="",
            current_price=10.6, 
            volume=50000, # < 100k
            bars_1min=[]
        )
        result.change_percentage = 6.0

        play = asyncio.run(self.scanner._analyze_intraday_mover_opportunity(result))
        self.assertIsNone(play)
        print("✅ TEST3 (Low Volume): Rejected")

if __name__ == '__main__':
    unittest.main()