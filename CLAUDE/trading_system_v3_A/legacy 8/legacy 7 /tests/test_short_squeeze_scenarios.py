
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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ScenarioTest")

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

# Helper to create mock bars
def create_mock_bars(price_start, price_end, count=50):
    bars = []
    current_time = datetime.now()
    step = (price_end - price_start) / count
    for i in range(count):
        p = price_start + (i * step)
        bars.append({
            'timestamp': current_time,
            'open': p,
            'high': p + 0.05,
            'low': p - 0.05,
            'close': p + 0.02,
            'volume': 100000 
        })
    return bars

async def setup_worker():
    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()
    config = MockConfigParser()
    worker = ShortSqueezeWorkerLogic(execution_engine, risk_manager, config)
    return worker, DatabaseManager().db_path

async def run_scenario(name, symbol, db_data, opportunity_data, expected_entry):
    logger.info(f"\n🧪 RUNNING SCENARIO: {name}")
    
    worker, db_path = await setup_worker()
    
    # 1. Seed DB
    if db_data:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
            conn.execute("""
                INSERT INTO proactive_candidates 
                (symbol, detection_date, pattern_type, status, metrics, key_levels, created_at, updated_at)
                VALUES (?, date('now'), ?, 'WATCHING', ?, ?, datetime('now'), datetime('now'))
            """, (
                symbol,
                db_data.get('pattern', 'GREEN_DAY_1'),
                json.dumps(db_data.get('metrics', {})),
                json.dumps(db_data.get('levels', {}))
            ))
            conn.commit()
    else:
        # Ensure it's empty for negative test
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
            conn.commit()

    # 2. Add bars if missing
    if 'bars' not in opportunity_data:
        # Default bars match price trend
        price = opportunity_data.get('current_price', 10.0)
        opportunity_data['bars'] = create_mock_bars(price*0.95, price) # Uptrend to current
        opportunity_data['bars_history'] = opportunity_data['bars']

    # 3. Execute
    try:
        should_enter = await worker.should_enter(opportunity_data)
        
        result_str = "✅ ENTRY" if should_enter else "❌ NO ENTRY"
        expected_str = "✅ ENTRY" if expected_entry else "❌ NO ENTRY"
        
        if should_enter == expected_entry:
            logger.info(f"✨ RESULT MATCHED expectation: {result_str}")
        else:
            logger.error(f"💀 RESULT FAILED: Expected {expected_str}, got {result_str}")
            
    except Exception as e:
        logger.error(f"💥 EXCEPTION in scenario: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))

async def main():
    logger.info("🚀 Starting Comprehensive Scenario Tests")
    
    # SCENARIO 1: The PERFECT Setup
    # - In DB
    # - Price > VWAP
    # - High Volume
    await run_scenario(
        name="Perfect Short Squeeze Setup",
        symbol="TEST_PERFECT",
        db_data={'pattern': 'GREEN_DAY_1'},
        opportunity_data={
            'symbol': 'TEST_PERFECT',
            'current_price': 10.50,
            'gap_percentage': 5.0,
            'volume_ratio': 3.5,
            'vwap': 10.00 # Price > VWAP
        },
        expected_entry=True
    )

    # SCENARIO 2: Metric Failure (Price < VWAP)
    # - In DB
    # - Price < VWAP (Shorts are comfortable)
    # - High Volume (doesn't matter if trend is weak)
    await run_scenario(
        name="Failure: Price Below VWAP",
        symbol="TEST_WEAK",
        db_data={'pattern': 'GREEN_DAY_1'},
        opportunity_data={
            'symbol': 'TEST_WEAK',
            'current_price': 9.50,
            'gap_percentage': 2.0,
            'volume_ratio': 3.5,
            'vwap': 10.00 # Price < VWAP
        },
        expected_entry=False
    )

    # SCENARIO 3: Not in Watchlist
    # - Not in DB
    # - Perfect metrics otherwise
    await run_scenario(
        name="Failure: Not in Watchlist",
        symbol="TEST_UNKNOWN",
        db_data=None, # Not in DB
        opportunity_data={
            'symbol': 'TEST_UNKNOWN',
            'current_price': 10.50,
            'gap_percentage': 5.0,
            'volume_ratio': 3.5,
            'vwap': 10.00
        },
        expected_entry=False
    )
    
    # SCENARIO 4: Quiet Rise (Low Volume but High Gap)
    # - In DB
    # - Low Volume (< 2.0)
    # - High Gap (> 5.0%) -> Should trigger "Quiet Rise" heuristic
    await run_scenario(
        name="Edge Case: Quiet Rise (Low Vol, High Gap)",
        symbol="TEST_QUIET",
        db_data={'pattern': 'FAKE_BREAKDOWN'},
        opportunity_data={
            'symbol': 'TEST_QUIET',
            'current_price': 10.50,
            'gap_percentage': 6.0, # > 5%
            'volume_ratio': 1.5,   # Low volume
            'vwap': 10.00
        },
        expected_entry=True
    )

    # SCENARIO 5: Low Volume Failure (No Quiet Rise)
    # - In DB
    # - Low Volume (< 2.0)
    # - Low Gap (< 5.0%) -> Nothing special
    await run_scenario(
        name="Failure: Low Volume and No Momentum",
        symbol="TEST_BORING",
        db_data={'pattern': 'GREEN_DAY_1'},
        opportunity_data={
            'symbol': 'TEST_BORING',
            'current_price': 10.20,
            'gap_percentage': 1.0, # Low gap
            'volume_ratio': 1.1,   # Low volume
            'vwap': 10.00
        },
        expected_entry=False
    )

if __name__ == "__main__":
    asyncio.run(main())
