
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Import classes to test
# Adjust imports based on your actual project structure
import sys
import os

# Add project root to path to ensure imports work
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from scanner.smallcap.implicit_event_detector import ImplicitEventDetector

class MockScanResult:
    def __init__(self, symbol, price, volume, avg_volume, high, low, previous_close=None):
        self.symbol = symbol
        self.last_price = price
        self.volume = volume
        self.avg_volume = avg_volume
        self.high = high
        self.low = low
        self.previous_close = previous_close
        
        # Scanner expects these often
        self.rank = 1
        self.gap_percentage = 0.0
        if previous_close:
             self.gap_percentage = ((price - previous_close) / previous_close) * 100

class TestEventDrivenSystem(unittest.TestCase):

    def setUp(self):
        # Mock configuration
        self.config = {
            'event_driven_config': {
                'enabled': True,
                'enable_implicit_event_detection': True,
                'min_gap_pct': 10.0,
                'min_volume_ratio': 3.0,
                'min_range_percentile': 85,
                'min_event_score': 2,
                'premarket_start_hour': 4  # TESTING PREMARKET CONFIG
            },
            'catalyst_max_age': {'OTHER': 6},
            'min_catalyst_strength': 1,
            'watchlist_db_path': ':memory:', # Use in-memory DB for tests
            
            # Missing keys required by SmallcapDailyScanner
            'min_quality_score': 3.0,
            'max_news_age_hours': 8,
            'max_news_age_premarket': 16,
            'fresh_news_threshold': 2,
            'recent_news_threshold': 6,
            'stale_news_threshold': 12,
            'max_headlines_per_symbol': 5,
            'max_plays_per_scan': 15,
            'max_ibkr_results': 50,
            'newsapi_key': None,
            'finnhub_key': None,
            'polygon_key': None,
            
            'news_age_multipliers': {
                'fresh': 1.0,
                'recent': 0.8,
                'stale': 0.5,
                'expired': 0.0
            }
        }
        
        # Initializing Scanner with mocked dependencies
        self.scanner = SmallcapDailyScanner(config=self.config)
        self.scanner.ibkr_adapter = AsyncMock()
        self.scanner.ibkr_scanner = AsyncMock()
        self.scanner.catalyst_analyzer = MagicMock()
        self.scanner.db_manager = MagicMock()
        self.scanner.logger = MagicMock() # Silence logs

    def test_implicit_detector_initialization(self):
        """Verify detector is initialized when config is enabled"""
        self.assertIsNotNone(self.scanner.implicit_detector)
        self.assertIsInstance(self.scanner.implicit_detector, ImplicitEventDetector)
        print("\n✅ ImplicitEventDetector initialized correctly")

    def test_premarket_configuration(self):
        """Verify EarlyBirdQualifier respects premarket_start_hour"""
        # Default is 8, we configured 4
        start_time = self.scanner.early_bird.premarket_start_time
        self.assertEqual(start_time.hour, 4, f"Should initialize with hour 4, got {start_time.hour}")
        print(f"\n✅ EarlyBird initialized with Correct Start Hour: {start_time}")

    async def async_test_filtering(self):
        # Create a candidate that SHOULD pass (Good Event)
        # Price 5.50, Prev 5.00 (+10% gap), Vol 6000, Avg 1000 (6x), Range 0.5
        good_candidate = MockScanResult(
            symbol="GOOD", 
            price=5.50, 
            volume=6000, 
            avg_volume=1000, 
            high=5.50, 
            low=5.00, 
            previous_close=5.00
        )

        # Create a candidate that SHOULD fail (Weak Event)
        # Price 5.05, Prev 5.00 (+1% gap), Vol 1200, Avg 1000 (1.2x)
        bad_candidate = MockScanResult(
            symbol="WEAK", 
            price=5.05, 
            volume=1200, 
            avg_volume=1000, 
            high=5.10, 
            low=5.00, 
            previous_close=5.00
        )

        candidates = [good_candidate, bad_candidate]

        # Mock _get_daily_bars for historical range calculation protection
        # We'll return empty list to trigger "neutral" historical range behavior
        self.scanner._get_daily_bars = AsyncMock(return_value=[])

        # Execute Filter
        filtered = await self.scanner._filter_by_implicit_events(candidates)

        # Assertions
        passed_symbols = [c.symbol for c in filtered]
        print(f"\n📊 Filter Results: {passed_symbols}")

        self.assertEqual(len(filtered), 1, "Should filter out WEAK candidate")
        self.assertIn("GOOD", passed_symbols)
        self.assertNotIn("WEAK", passed_symbols)
        
        # Verify Implicit Data Attachment
        good_result = next(c for c in filtered if c.symbol == "GOOD")
        self.assertTrue(hasattr(good_result, 'implicit_event'), "Candidate should have implicit_event attr")
        event = good_result.implicit_event
        self.assertIsNotNone(event)
        self.assertEqual(event['symbol'], "GOOD")
        self.assertTrue(event['score'] >= 2)
        print(f"✅ Event Data Captured: Score={event['score']}, Reasons={event['reasons']}")

    def test_e2e_flow(self):
        """Run async test wrapper"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_test_filtering())
        loop.close()

if __name__ == '__main__':
    unittest.main()
