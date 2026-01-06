
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import configparser
from datetime import datetime, time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scanner.smallcap.proactive_scanner import ProactiveScanner

class TestScannerScheduling(unittest.TestCase):
    def setUp(self):
        # Create a mock config
        self.config = configparser.ConfigParser()
        self.config.add_section('PROACTIVE_SCANNER')
        self.config.set('PROACTIVE_SCANNER', 'run_premarket', 'true')
        self.config.set('PROACTIVE_SCANNER', 'run_during_market', 'false') # The key change
        self.config.set('PROACTIVE_SCANNER', 'run_postmarket', 'false')
        
        # Mock adapter
        self.mock_adapter = MagicMock()
        
        # Initialize scanner with mock config
        self.scanner = ProactiveScanner(ibkr_adapter=self.mock_adapter, config=self.config)

    @patch('scanner.smallcap.proactive_scanner.datetime')
    def test_run_premarket(self, mock_datetime):
        # Mock time: 8:00 AM ET (Premarket)
        # We need to handle the timezone awareness in the code under test
        # The code does: now_et = datetime.now(et_tz)
        # So we mock datetime.now to return a timezone-aware datetime
        
        from pytz import timezone
        et_tz = timezone('US/Eastern')
        mock_now = datetime(2025, 12, 27, 8, 0, 0, tzinfo=et_tz)
        
        # Configure the mock to return our time when now(tz) is called
        mock_datetime.now.return_value = mock_now
        
        should_run = self.scanner.should_run_now()
        print(f"Time: 8:00 AM (Pre-market) -> Should Run: {should_run}")
        self.assertTrue(should_run, "Scanner SHOULD run in pre-market")

    @patch('scanner.smallcap.proactive_scanner.datetime')
    def test_run_during_market(self, mock_datetime):
        # Mock time: 10:00 AM ET (Market Open)
        
        from pytz import timezone
        et_tz = timezone('US/Eastern')
        mock_now = datetime(2025, 12, 27, 10, 0, 0, tzinfo=et_tz)
        mock_datetime.now.return_value = mock_now
        
        should_run = self.scanner.should_run_now()
        print(f"Time: 10:00 AM (Market Open) -> Should Run: {should_run}")
        self.assertFalse(should_run, "Scanner SHOULD NOT run during market (config=false)")

    @patch('scanner.smallcap.proactive_scanner.datetime')
    def test_run_postmarket(self, mock_datetime):
        # Mock time: 17:00 PM ET (Post-market)
        
        from pytz import timezone
        et_tz = timezone('US/Eastern')
        mock_now = datetime(2025, 12, 27, 17, 0, 0, tzinfo=et_tz)
        mock_datetime.now.return_value = mock_now
        
        should_run = self.scanner.should_run_now()
        print(f"Time: 5:00 PM (Post-market) -> Should Run: {should_run}")
        self.assertFalse(should_run, "Scanner SHOULD NOT run in post-market (config=false)")

if __name__ == '__main__':
    unittest.main()
