"""
Unit Tests for Database Integration
Tests proactive_candidates table operations
"""
import unittest
import sqlite3
import json
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database_manager import DatabaseManager

class TestProactiveCandidatesTable(unittest.TestCase):
    """Test database operations for proactive_candidates"""
    
    def setUp(self):
        self.db = DatabaseManager()
        self.conn = sqlite3.connect(self.db.db_path)
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        
    def tearDown(self):
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        self.conn.close()
        
    def test_insert_candidate(self):
        """Test inserting a new candidate"""
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status, metrics, key_levels)
            VALUES (?, date('now'), 'GREEN_DAY_1', 'WATCHING', ?, ?)
        """, (
            'TEST',
            json.dumps({'float': 5000000, 'short_interest': 0.25}),
            json.dumps({'day1_high': 10.50, 'support': 9.80})
        ))
        self.conn.commit()
        
        row = self.conn.execute("SELECT * FROM proactive_candidates WHERE symbol = 'TEST'").fetchone()
        self.assertIsNotNone(row, "Candidate should be inserted")
        
    def test_status_update(self):
        """Test updating candidate status"""
        # Insert
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status)
            VALUES ('TEST', date('now'), 'GREEN_DAY_1', 'WATCHING')
        """)
        self.conn.commit()
        
        # Update
        self.conn.execute("""
            UPDATE proactive_candidates 
            SET status = 'TRIGGERED' 
            WHERE symbol = 'TEST'
        """)
        self.conn.commit()
        
        status = self.conn.execute(
            "SELECT status FROM proactive_candidates WHERE symbol = 'TEST'"
        ).fetchone()[0]
        
        self.assertEqual(status, 'TRIGGERED', "Status should be updated")
        
    def test_date_filtering(self):
        """Test filtering by detection_date"""
        # Insert candidates at different dates
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status)
            VALUES ('OLD', date('now', '-10 days'), 'GREEN_DAY_1', 'WATCHING')
        """)
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status)
            VALUES ('NEW', date('now', '-3 days'), 'GREEN_DAY_1', 'WATCHING')
        """)
        self.conn.commit()
        
        # Query last 7 days
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        rows = self.conn.execute("""
            SELECT symbol FROM proactive_candidates 
            WHERE detection_date >= ?
        """, (cutoff,)).fetchall()
        
        symbols = [r[0] for r in rows]
        self.assertIn('NEW', symbols, "Recent candidate should be included")
        self.assertNotIn('OLD', symbols, "Old candidate should be excluded")

if __name__ == '__main__':
    unittest.main()
