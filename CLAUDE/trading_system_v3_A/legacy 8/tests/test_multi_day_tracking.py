
import unittest
import sqlite3
import logging
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_manager import DatabaseManager
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MultiDayTest")

class TestMultiDayTracking(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager()
        self.conn = sqlite3.connect(self.db.db_path)
        
        # Clean proactive table
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        
        # Create a mock scanner to access the method
        # We don't need full init, just the method
        self.scanner = SmallcapDailyScanner.__new__(SmallcapDailyScanner)
        self.scanner.logger = logger
        
    def tearDown(self):
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        self.conn.close()
        
    def insert_candidate(self, symbol, days_ago):
        detection_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status, created_at, updated_at)
            VALUES (?, ?, 'GREEN_DAY_1', 'WATCHING', datetime('now'), datetime('now'))
        """, (symbol, detection_date))
        self.conn.commit()

    def test_tracking_window(self):
        logger.info("📅 Testing 7-Day Tracking Window...")
        
        # 1. Insert candidates at various ages
        self.insert_candidate("TICKER_DAY_0", 0)  # Today
        self.insert_candidate("TICKER_DAY_3", 3)  # Mid-week
        self.insert_candidate("TICKER_DAY_7", 7)  # Last valid day
        self.insert_candidate("TICKER_DAY_8", 8)  # Expired
        self.insert_candidate("TICKER_DAY_30", 30) # Very Expired
        
        # 2. Load Watchlist
        watchlist = self.scanner._load_proactive_watchlist()
        
        logger.info(f"📋 Watchlist Returned: {watchlist}")
        
        # 3. Assertions
        self.assertIn("TICKER_DAY_0", watchlist, "Day 0 should be tracked")
        self.assertIn("TICKER_DAY_3", watchlist, "Day 3 should be tracked")
        self.assertIn("TICKER_DAY_7", watchlist, "Day 7 should be tracked")
        
        self.assertNotIn("TICKER_DAY_8", watchlist, "Day 8 should be EXPIRED")
        self.assertNotIn("TICKER_DAY_30", watchlist, "Day 30 should be EXPIRED")
        
        logger.info("✅ Multi-Day Tracking Logic Verified!")

if __name__ == '__main__':
    unittest.main()
