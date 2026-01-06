
import asyncio
import logging
import sqlite3
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestProactiveMonitor")

async def test_proactive_monitoring():
    """
    Test that _monitor_watchlist pick ups a candidate and triggers entry logic.
    """
    db_path = "test_proactive_monitor.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # 1. Setup Mock DB
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proactive_candidates (
            symbol TEXT PRIMARY KEY,
            detection_date DATETIME,
            setup_type TEXT,
            pattern_type TEXT,
            status TEXT,
            priority_score REAL,
            data_json TEXT,
            key_levels TEXT,
            updated_at DATETIME
        )
    """)
    
    # Insert a WATCHING candidate
    # Level: Resistance $10.00. We will mock price $10.05
    import json
    key_levels = json.dumps({
        "resistance": 10.00,
        "day1_high": 10.00,
        "daily_structure": "BREAKOUT"
    })
    
    conn.execute("""
        INSERT INTO proactive_candidates (symbol, pattern_type, status, key_levels, detection_date)
        VALUES (?, ?, ?, ?, ?)
    """, ('TEST_SQZ', 'BREAKOUT_OPEN', 'WATCHING', key_levels, datetime.now()))
    conn.commit()
    conn.close()

    # 2. Mock Infrastructure
    mock_engine = MagicMock()
    mock_risk = MagicMock()
    
    # Mock Broker for Snapshots
    mock_broker = MagicMock()
    mock_ticker = MagicMock()
    mock_ticker.marketPrice = MagicMock(return_value=10.05) # Breakout!
    mock_ticker.volume = 500000
    
    # Sync mock for get_ticker (AsyncMock creates a coroutine that returns return_value)
    # mock_broker.get_ticker = AsyncMock(return_value=mock_ticker) # Simple return

    # HOWEVER, the code does: ticker = await ...get_ticker()
    # If using AsyncMock(return_value=mock_ticker), await returns mock_ticker. CORRECT.
    mock_broker.get_ticker = AsyncMock(return_value=mock_ticker)
    
    mock_broker.get_short_data = AsyncMock(return_value={'short_status': 'HTB'})
    
    mock_engine.broker = mock_broker
    
    # 3. Init Worker
    worker = ShortSqueezeWorkerLogic(mock_engine, mock_risk)
    worker.db_manager.db_path = db_path # Override DB path
    worker.is_running = True # Enable running state
    
    # Inject Logger
    # Force stdout logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    worker.logger = logger
    worker.logger.handlers = [console_handler] # Replace existing handlers
    
    # Debug info
    logger.info(f"DB Path: {db_path}")
    logger.info(f"Worker DB Path: {worker.db_manager.db_path}")

    # Mock methods to isolate monitoring logic
    # We want to verified _monitor_watchlist calls _fetch_candidate_snapshots -> should_enter -> _execute_entry
    
    # We will let _fetch_candidate_snapshots run (it uses mocked broker)
    # We will let should_enter run (it checks DB)
    # We mock _execute_entry to verify success
    worker._execute_entry = AsyncMock(return_value=True)
    
    # Also need to mock get_bars_from_opportunity because should_enter calls it
    # and we don't want to rely on external data
    # Create a simple bar object
    class MockBar:
        def __init__(self, c, v):
            self.close = c
            self.open = c * 0.99
            self.high = c * 1.01
            self.low = c * 0.98
            self.volume = v
            self.timestamp = datetime.now()
            
    bars = [MockBar(10.05, 10000) for _ in range(20)]
    worker.get_bars_from_opportunity = MagicMock(return_value=bars)
    
    # 4. Run Monitor
    logger.info("--- Starting Monitor Loop Check ---")
    try:
        await worker._monitor_watchlist()
    except Exception as e:
        logger.error(f"EXCEPTION in monitor_watchlist: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Verify Results
    
    # A. Did we fetch snapshots?
    # Indirectly verified if should_enter was called with current price
    
    # B. Did we trigger execute_entry?
    if worker._execute_entry.called:
        args = worker._execute_entry.call_args[0][0] # First arg (opportunity)
        logger.info("✅ SUCCESS: _execute_entry called!")
        logger.info(f"   Symbol: {args['symbol']}")
        logger.info(f"   Trigger Price: {args['current_price']}")
        logger.info(f"   Source: {args.get('source')}")
        
        # Verify status update in DB
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT status FROM proactive_candidates WHERE symbol='TEST_SQZ'").fetchone()
        status = row[0]
        logger.info(f"   DB Status: {status}")
        if status == 'TRIGGERED':
             logger.info("✅ DB Status updated to TRIGGERED")
        else:
             logger.error(f"❌ DB Status NOT updated (Got {status})")
    else:
        logger.error("❌ FAILURE: _execute_entry was NOT called.")
        
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(test_proactive_monitoring())
