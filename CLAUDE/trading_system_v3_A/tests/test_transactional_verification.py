
import unittest
import sqlite3
import os
import shutil
from datetime import datetime
from core.execution_tracker import ExecutionTracker

class TestTransactionalFills(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_transactional.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        # Initialize DB Schema manually since we are not using DatabaseManager here
        with sqlite3.connect(self.test_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    status TEXT DEFAULT 'OPEN',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        self.tracker = ExecutionTracker(self.test_db)
        
    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_buffer_and_process_fill(self):
        """Verify that a fill arriving before trade creation is buffered and then matched"""
        symbol = "BUFFER_TEST"
        order_id = "oid_123"
        price = 10.50
        qty = 100
        exec_time = datetime.now()
        
        # 1. Simulate Fill arriving BEFORE trade exists
        # This should return False (trade not found) and buffer it
        print("1. Recording execution for non-existent trade...")
        result = self.tracker.record_execution(
            symbol=symbol,
            side="BUY",
            executed_price=price,
            executed_quantity=qty,
            execution_time=exec_time,
            broker_order_id=order_id
        )
        
        self.assertFalse(result, "Should return False when trade not found")
        self.assertIn(symbol, self.tracker._pending_fills, "Symbol should be in pending fills")
        self.assertEqual(len(self.tracker._pending_fills[symbol]), 1, "Should have 1 pending fill")
        
        # 2. Create the trade manually in DB (Simulation of ExecutionEngine creating it)
        print("2. Creating trade in DB...")
        with sqlite3.connect(self.test_db) as conn:
            conn.execute("""
                INSERT INTO trades (
                    trade_id, symbol, strategy, side, quantity, entry_price, 
                    entry_time, status, broker_order_id_entry, entry_filled
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, 0
                )
            """, ("trade_001", symbol, "TEST_STRAT", "BUY", qty, price, exec_time, "OPEN", order_id))
            conn.commit()
            
        # 3. Process pending fills
        print("3. Processing pending fills...")
        self.tracker.process_pending_fills(symbol)
        
        # 4. Verify buffer is clear
        self.assertEqual(len(self.tracker._pending_fills[symbol]), 0, "Buffer should be empty after processing")
        
        # 5. Verify trade in DB is updated
        with sqlite3.connect(self.test_db) as conn:
            row = conn.execute("SELECT entry_filled, actual_entry_price, entry_slippage_pct FROM trades WHERE trade_id = 'trade_001'").fetchone()
            
        self.assertEqual(row[0], 1, "Trade entry_filled should be 1")
        self.assertEqual(row[1], price, "Actual price should match fill price")
        print(f"✅ Verified: Trade updated correctly. Filled: {row[0]}, Price: {row[1]}")

if __name__ == "__main__":
    unittest.main()
