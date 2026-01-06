#!/usr/bin/env python3
"""
Test script for the consolidated exit fix in ExecutionTracker
Tests the STI scenario: 2 separate BUY trades, 1 consolidated SELL
"""

import sys
import sqlite3
from datetime import datetime
from pathlib import Path
import logging

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

from core.execution_tracker import ExecutionTracker

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_database(db_path: str):
    """Create test database with STI scenario"""
    
    # Remove existing test db
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create trades table with enhanced schema
    cursor.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            strategy TEXT,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            entry_time TIMESTAMP NOT NULL,
            exit_time TIMESTAMP,
            duration_minutes INTEGER,
            pnl REAL,
            commission REAL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confidence REAL,
            -- Enhanced execution tracking columns
            actual_entry_price REAL,
            actual_exit_price REAL,
            actual_entry_time TIMESTAMP,
            actual_exit_time TIMESTAMP,
            entry_slippage REAL,
            exit_slippage REAL,
            entry_slippage_pct REAL,
            exit_slippage_pct REAL,
            total_slippage_impact REAL,
            planned_pnl REAL,
            actual_pnl REAL,
            entry_filled BOOLEAN DEFAULT 0,
            exit_filled BOOLEAN DEFAULT 0,
            broker_order_id_entry TEXT,
            broker_order_id_exit TEXT
        )
    """)
    
    # Insert the two STI trades from the real scenario
    trades_data = [
        # Trade 1: 33 shares @ $5.93 (earlier)
        ('STI_20250903_195442_466bf7ae', 'STI', 'volume_breakout', 'BUY', 33, 5.93, 
         '2025-09-03 19:54:42.289485', 0.35, 'OPEN', 
         'Test trade 1 - 33 shares @ $5.93', '2025-09-03 17:54:42'),
        
        # Trade 2: 30 shares @ $6.63 (later) 
        ('STI_20250903_200910_a4376e56', 'STI', 'volume_breakout', 'BUY', 30, 6.63,
         '2025-09-03 20:09:10.805030', 0.36, 'OPEN',
         'Test trade 2 - 30 shares @ $6.63', '2025-09-03 18:09:10')
    ]
    
    for trade_data in trades_data:
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, strategy, side, quantity, entry_price,
                entry_time, commission, status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, trade_data)
    
    conn.commit()
    conn.close()
    
    logger.info("✅ Test database created with STI scenario")

def verify_initial_state(db_path: str):
    """Verify the initial state matches our scenario"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT trade_id, symbol, quantity, entry_price, status FROM trades WHERE symbol = 'STI' ORDER BY entry_time")
    trades = cursor.fetchall()
    
    logger.info("📊 Initial state:")
    for trade in trades:
        logger.info(f"  {trade[0]}: {trade[2]} shares @ ${trade[3]} - {trade[4]}")
    
    conn.close()
    return trades

def test_consolidated_exit(db_path: str):
    """Test the consolidated exit functionality"""
    
    # Initialize ExecutionTracker
    tracker = ExecutionTracker(db_path)
    
    # Simulate the broker execution: SELL 63@$6.93
    execution_time = datetime.fromisoformat('2025-09-03 21:55:31')
    
    logger.info("\n🔄 Testing consolidated exit...")
    logger.info("Simulating broker execution: STI SELL 63@$6.93")
    
    # This should trigger the consolidated exit logic
    success = tracker.record_execution(
        symbol='STI',
        side='SELL', 
        executed_price=6.93,
        executed_quantity=63,
        execution_time=execution_time,
        broker_order_id='2339'
    )
    
    return success

def verify_final_state(db_path: str):
    """Verify the final state after consolidated exit"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT trade_id, symbol, quantity, entry_price, exit_price, 
               status, pnl, actual_pnl 
        FROM trades WHERE symbol = 'STI' 
        ORDER BY entry_time
    """)
    
    trades = cursor.fetchall()
    
    logger.info("\n📊 Final state after consolidated exit:")
    total_pnl = 0
    for trade in trades:
        pnl = trade[6] or trade[7] or 0  # pnl or actual_pnl
        total_pnl += pnl
        logger.info(f"  {trade[0]}: {trade[2]} shares @ ${trade[3]} -> ${trade[4] or 'N/A'} - {trade[5]} (P&L: ${pnl:.2f})")
    
    logger.info(f"\n💰 Total P&L: ${total_pnl:.2f}")
    
    # Calculate expected P&L for comparison
    expected_cost = (33 * 5.93) + (30 * 6.63)  # $195.69 + $198.90 = $394.59
    expected_revenue = 63 * 6.93  # $436.59
    expected_gross_pnl = expected_revenue - expected_cost  # $42.00
    commission = 0.35 + 0.36  # Total commission
    expected_net_pnl = expected_gross_pnl - commission  # ~$41.29
    
    logger.info(f"📈 Expected P&L calculation:")
    logger.info(f"  Cost basis: ${expected_cost:.2f}")
    logger.info(f"  Revenue: ${expected_revenue:.2f}")
    logger.info(f"  Gross P&L: ${expected_gross_pnl:.2f}")
    logger.info(f"  Commission: ${commission:.2f}")
    logger.info(f"  Expected Net P&L: ${expected_net_pnl:.2f}")
    
    # Check if all trades are closed
    open_trades = [t for t in trades if t[5] == 'OPEN']
    if open_trades:
        logger.error(f"❌ ERROR: {len(open_trades)} trades still OPEN!")
        return False
    else:
        logger.info("✅ All trades properly closed")
        return True
    
    conn.close()

def main():
    """Run the test"""
    test_db_path = "test_consolidated_exit.db"
    
    logger.info("🧪 Testing Consolidated Exit Fix")
    logger.info("=" * 50)
    
    try:
        # Step 1: Create test database
        create_test_database(test_db_path)
        
        # Step 2: Verify initial state
        initial_trades = verify_initial_state(test_db_path)
        
        # Step 3: Test consolidated exit
        success = test_consolidated_exit(test_db_path)
        
        if not success:
            logger.error("❌ Consolidated exit failed!")
            return False
        
        # Step 4: Verify final state
        success = verify_final_state(test_db_path)
        
        if success:
            logger.info("\n🎉 TEST PASSED! Consolidated exit fix working correctly.")
        else:
            logger.error("\n❌ TEST FAILED! Issues found in final state.")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        return False
    
    finally:
        # Cleanup
        if Path(test_db_path).exists():
            Path(test_db_path).unlink()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)