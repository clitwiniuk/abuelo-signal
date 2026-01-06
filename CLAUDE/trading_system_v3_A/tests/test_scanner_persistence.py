
import unittest
import os
import sqlite3
import json
from datetime import datetime, date
from dataclasses import dataclass
from enum import Enum

from core.scanner_signal_recorder import ScannerSignalRecorder

# Mocks to simulate SmallcapPlay structure without importing simplified/complex dependencies
class MockOpportunityType(Enum):
    GAP_BREAKOUT = "GAP_BREAKOUT"

@dataclass
class MockCatalyst:
    catalyst_type: str
    strength: int

@dataclass
class MockPlay:
    symbol: str
    scan_timestamp: datetime
    quality_score: float
    opportunity_type: MockOpportunityType
    catalyst: MockCatalyst
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'quality_score': self.quality_score,
            'catalyst_type': self.catalyst.catalyst_type,
            'custom_field': 'persisted_successfully'
        }

class TestScannerPersistence(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_persistence.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        # Initialize DB schema manually
        with sqlite3.connect(self.test_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanner_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_date DATE NOT NULL,
                    scan_time TIMESTAMP NOT NULL,
                    opportunity_type TEXT,
                    quality_score REAL,
                    catalyst_type TEXT,
                    catalyst_strength INTEGER,
                    full_signal_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        self.recorder = ScannerSignalRecorder(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_record_and_retrieve_signal(self):
        """Verify we can record a signal and retrieve it by date and symbol"""
        symbol = "PERSIST_TEST"
        scan_time = datetime(2025, 1, 15, 9, 30, 0)
        
        play = MockPlay(
            symbol=symbol,
            scan_timestamp=scan_time,
            quality_score=8.5,
            opportunity_type=MockOpportunityType.GAP_BREAKOUT,
            catalyst=MockCatalyst("FDA_APPROVAL", 8)
        )
        
        # 1. Record
        success = self.recorder.record_signal(play)
        self.assertTrue(success, "Recording should succeed")
        
        # 2. Retrieve for Replay
        retrieved_json = self.recorder.get_signal_for_replay(symbol, scan_time.date())
        
        self.assertIsNotNone(retrieved_json, "Should retrieve data")
        self.assertEqual(retrieved_json['symbol'], symbol)
        self.assertEqual(retrieved_json['quality_score'], 8.5)
        self.assertEqual(retrieved_json['catalyst_type'], 'FDA_APPROVAL')
        self.assertEqual(retrieved_json['custom_field'], 'persisted_successfully')
        
        print(f"✅ Verified: Recorded {symbol} and retrieved successfully.")

if __name__ == "__main__":
    unittest.main()
