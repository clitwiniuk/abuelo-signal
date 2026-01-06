
import asyncio
import sqlite3
import json
import logging
import os
import sys
from datetime import datetime, date
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
project_root = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3"
if project_root not in sys.path:
    sys.path.append(project_root)

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestShortSqueeze")

class MockBar:
    def __init__(self, open, high, low, close, volume, timestamp=None):
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.timestamp = timestamp or datetime.now()

async def run_test():
    test_db = "test_short_squeeze.db"
    
    # Clean up old test db
    if os.path.exists(test_db):
        os.remove(test_db)
        
    # Initialize DB with required table
    db_manager = DatabaseManager(db_path=test_db)
    
    # Mock Broker
    mock_broker = AsyncMock()
    mock_broker.get_short_data.return_value = {'short_status': 'HTB', 'shortable_shares': 500}
    mock_broker.get_current_price.return_value = 10.5
    
    # Mock Config
    mock_config = MagicMock()
    mock_config.getfloat.side_effect = lambda s, k, fallback=None: fallback # Just return fallbacks
    
    # Instantiate Worker
    worker = ShortSqueezeWorkerLogic(broker=mock_broker, config=mock_config)
    worker.db_manager = db_manager # Inject test db manager
    
    symbol = "TEST_SQ"
    
    logger.info("--- SCENARIO 1: PROACTIVE MONITOR ---")
    # Insert candidate into DB
    with sqlite3.connect(test_db) as conn:
        conn.execute("""
            INSERT INTO proactive_candidates (
                symbol, detection_date, pattern_type, status, metrics, key_levels, days_since_detection, last_check_time
            ) VALUES (?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """, (
            symbol, date.today().isoformat(), 'GREEN_DAY_1', 'WATCHING',
            json.dumps({'squeeze_quality': 'IDEAL', 'rel_vol': 4.0}),
            json.dumps({'day1_high': 12.0, 'resistance': 12.0})
        ))
        conn.commit()
    
    # Mock snapshots
    # Snapshot must have 'price', 'volume_ratio'
    mock_snapshots = {
        symbol: {
            'symbol': symbol,
            'price': 10.8,
            'volume_ratio': 3.5,
            'gap_percentage': 16.0,
            'timestamp': datetime.now()
        }
    }
    
    # Patch internal methods to simplify
    with patch.object(worker, '_fetch_candidate_snapshots', return_value=mock_snapshots), \
         patch.object(worker, 'get_bars_from_opportunity') as mock_get_bars, \
         patch.object(worker, '_execute_entry', new_callable=AsyncMock) as mock_exec:
        
        # Create some mock bars with 1min frequency
        mock_bars = [
            MockBar(10.0, 10.1, 9.9, 10.1, 1000), # VWAP will be around 10
            MockBar(10.1, 10.2, 10.0, 10.2, 1000),
            MockBar(10.2, 10.3, 10.1, 10.3, 1000)
        ]
        mock_get_bars.return_value = mock_bars
        
        # Trigger monitor
        logger.info(f"Running _monitor_watchlist for {symbol}...")
        await worker._monitor_watchlist()
        
        if mock_exec.called:
            logger.info("✅ SUCCESS: Entry executed via Proactive Monitor")
        else:
            logger.error("❌ FAILURE: Entry NOT executed via Proactive Monitor")

    logger.info("\n--- SCENARIO 2: DAILY SCANNER SIGNAL ---")
    # New symbol NOT in watchlist
    external_symbol = "EXT_SQ"
    opp = {
        'symbol': external_symbol,
        'current_price': 15.0,
        'volume_ratio': 5.0,
        'gap_percentage': 16.0,
        'timestamp': datetime.now(),
        'source': 'DAILY_SCANNER'
    }
    
    logger.info(f"Evaluating {external_symbol} (NOT in watchlist)...")
    result = await worker.should_enter(opp)
    if not result:
        logger.info(f"✅ SUCCESS: {external_symbol} rejected (as expected, not in watchlist)")
    else:
        logger.error(f"❌ FAILURE: {external_symbol} accepted even though NOT in watchlist")
        
    # Now add it to watchlist
    with sqlite3.connect(test_db) as conn:
        conn.execute("""
            INSERT INTO proactive_candidates (
                symbol, detection_date, pattern_type, status, metrics, key_levels, days_since_detection, last_check_time
            ) VALUES (?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """, (
            external_symbol, date.today().isoformat(), 'GREEN_DAY_1', 'WATCHING',
            json.dumps({'squeeze_quality': 'IDEAL'}),
            json.dumps({'day1_high': 16.0, 'resistance': 16.0})
        ))
        conn.commit()
        
    logger.info(f"Evaluating {external_symbol} (NOW in watchlist)...")
    # Reset internal traded state
    worker.traded_symbols_today.clear()
    
    with patch.object(worker, 'get_bars_from_opportunity') as mock_get_bars:
        mock_get_bars.return_value = mock_bars
        result = await worker.should_enter(opp)
        if result:
            logger.info(f"✅ SUCCESS: {external_symbol} accepted via external signal")
        else:
            logger.error(f"❌ FAILURE: {external_symbol} rejected even though IN watchlist")

    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)

if __name__ == "__main__":
    asyncio.run(run_test())
