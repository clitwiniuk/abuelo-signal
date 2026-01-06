
import asyncio
import logging
import sqlite3
import json
from datetime import datetime
import sys
import os
from unittest.mock import MagicMock

# MOCK missing dependencies
sys.modules['pandas_ta'] = MagicMock()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_manager import DatabaseManager
from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic

# Mock classes
class MockExecutionEngine:
    def __init__(self):
        self.config = {}

class MockRiskManager:
    def check_risk(self, *args, **kwargs):
        return True
        
class MockConfigParser:
    def get(self, section, key, fallback=None):
        return fallback
    def getboolean(self, section, key, fallback=None):
        return fallback
    def getfloat(self, section, key, fallback=0.0):
        return fallback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DryRun")

async def run_test():
    db_manager = DatabaseManager()
    db_path = db_manager.db_path
    symbol = "DRYRUN_TEST"
    
    logger.info("🚀 Starting Dry Run: Proactive Short Squeeze System")
    
    # 1. SEED DATABASE
    logger.info(f"🌱 Seeding database with test candidate: {symbol}")
    with sqlite3.connect(db_path) as conn:
        # Clean up previous test
        conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
        
        # Insert test candidate
        conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status, metrics, key_levels, created_at, updated_at)
            VALUES (?, date('now'), 'GREEN_DAY_1', 'WATCHING', ?, ?, datetime('now'), datetime('now'))
        """, (
            symbol,
            json.dumps({'float': 5000000, 'short_interest': 0.20, 'rel_vol': 3.5}),
            json.dumps({'day1_high': 10.50, 'support': 9.80, 'vwap': 10.00})
        ))
        conn.commit()
    
    logger.info("✅ Database seeded.")
    
    # 2. INITIALIZE WORKER
    logger.info("🔧 Initializing ShortSqueezeWorkerLogic...")
    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()
    config = MockConfigParser()
    
    worker = ShortSqueezeWorkerLogic(
        execution_engine=execution_engine,
        risk_manager=risk_manager,
        config=config
    )
    
    # 3. SIMULATE OPPORTUNITY (Data causing a trigger)
    # We construct an opportunity that matches the "Uncomfortable Shorts" criteria:
    # - Price > VWAP (Trading above average price)
    # - GapUp or Green Day
    # - Volume Ratio > 1.2
    
    # Create mock bars (needed for VWAP calc)
    current_time = datetime.now()
    mock_bars = []
    # Create 50 bars, slightly uptrending
    for i in range(50):
        price = 10.0 + (i * 0.02) # Starts at 10.0, ends at 11.0
        mock_bars.append({
            'timestamp': current_time, # Simplified
            'open': price,
            'high': price + 0.05,
            'low': price - 0.05,
            'close': price + 0.02, # Green candles
            'volume': 100000 
        })
        
    opportunity = {
        'symbol': symbol,
        'current_price': 11.00,  # Above Day 1 High (10.50)
        'gap_percentage': 5.0,
        'volume_ratio': 2.5,     # High relative volume
        'vwap': 10.50, # Price (11.00) > VWAP (calculated from bars) -> Bullish
        'quality_score': 85.0,
        'timestamp': datetime.now().isoformat(),
        'bars': mock_bars, # ADDED BARS
        'bars_history': mock_bars # Add both for compatibility
    }
    
    logger.info(f"⚡ Simulating Incoming Opportunity for {symbol}: {opportunity}")
    
    # 4. EXECUTE WORKER CHECK
    logger.info("🧠 Worker analyzing opportunity...")
    
    # We call 'should_enter' directly to test logic (process_opportunity wraps this)
    # Note: process_opportunity in BaseWorkerLogic handles the actual order placement
    # For this dry run, we want to know if the LOGIC triggers an entry signal.
    
    should_enter = await worker.should_enter(opportunity)
    
    if should_enter:
        logger.info(f"✅ SUCCESS: Worker triggered ENTRY signal for {symbol}!")
        logger.info("   Reason: Price > VWAP and Volume > Threshold on a Proactive Candidate.")
    else:
        logger.error(f"❌ FAILURE: Worker rejected the opportunity.")
        
    # 5. VERIFY DATABASE UPDATE
    # The worker logic should theoretically update status to 'TRIGGERED' or similar if implemented
    # Let's check if the logic did that (if implemented in should_enter)
    
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT status FROM proactive_candidates WHERE symbol = ?", (symbol,)).fetchone()
        status = row[0]
        logger.info(f"📊 Final DB Status for {symbol}: {status}")
        
    # Cleanup
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
        logger.info("🧹 Test data cleaned up.")

if __name__ == "__main__":
    asyncio.run(run_test())
