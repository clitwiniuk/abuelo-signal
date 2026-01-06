import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from core.database_manager import DatabaseManager

class TestScannerWatchlistIntegration(unittest.TestCase):
    """Test scanner's watchlist loading"""
    
    def setUp(self):
        self.db = DatabaseManager()
        import sqlite3
        self.conn = sqlite3.connect(self.db.db_path)
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        
        # Create mock scanner
        self.scanner = SmallcapDailyScanner.__new__(SmallcapDailyScanner)
        self.scanner.logger = MagicMock()
        
    def tearDown(self):
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        self.conn.close()
        
    def _insert_candidate(self, symbol, days_ago, status='WATCHING'):
        """Helper to insert candidate"""
        detection_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status)
            VALUES (?, ?, 'GREEN_DAY_1', ?)
        """, (symbol, detection_date, status))
        self.conn.commit()
        
    def test_load_active_candidates(self):
        """Test loading WATCHING and TRIGGERED candidates"""
        self._insert_candidate('WATCH1', 2, 'WATCHING')
        self._insert_candidate('WATCH2', 5, 'TRIGGERED')
        self._insert_candidate('EXPIRED', 3, 'EXPIRED')
        
        watchlist = self.scanner._load_proactive_watchlist()
        
        self.assertIn('WATCH1', watchlist)
        self.assertIn('WATCH2', watchlist)
        self.assertNotIn('EXPIRED', watchlist, "EXPIRED status should be filtered")
        
    def test_7_day_window(self):
        """Test 7-day tracking window"""
        self._insert_candidate('DAY_0', 0)
        self._insert_candidate('DAY_7', 7)
        self._insert_candidate('DAY_8', 8)
        
        watchlist = self.scanner._load_proactive_watchlist()
        
        self.assertIn('DAY_0', watchlist)
        self.assertIn('DAY_7', watchlist)
        self.assertNotIn('DAY_8', watchlist, "Day 8 should be expired")
        
    def test_empty_watchlist(self):
        """Test behavior with empty watchlist"""
        watchlist = self.scanner._load_proactive_watchlist()
        self.assertEqual(len(watchlist), 0, "Should return empty list")

if __name__ == '__main__':
    unittest.main()
