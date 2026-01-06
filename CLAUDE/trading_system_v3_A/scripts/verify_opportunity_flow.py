
import asyncio
import logging
import sys
import os
import sqlite3
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager

# --- Mock Infrastructure ---
class MockExecutionEngine:
    def __init__(self):
        self.broker = MockBroker()
        
class MockBroker:
    async def get_short_data(self, symbol):
        return {'short_status': 'HTB', 'shortable_shares': 500}

class MockRiskManager:
    async def check_risk(self, *args, **kwargs):
        return True
        
class MockConfig:
    def getfloat(self, section, option, fallback=None):
        return fallback
    def get(self, section, option, fallback=None):
        return fallback

# --- Test Script ---
async def run_verification():
    print("🚀 Starting Scanner-Worker Integration Verification...")
    
    # 1. Setup Database (In-Memory or Temp File)
    db_path = "trading_data.db" # Use real DB for Schema compatibility, but be careful
    print(f"📂 Using Database: {db_path}")
    
    # 2. Initialize Worker
    execution_engine = MockExecutionEngine()
    risk_manager = MockRiskManager()
    config = MockConfig()
    worker = ShortSqueezeWorkerLogic(execution_engine, risk_manager, config)
    
    # Override helpers to avoid full DB dependencies or network calls if possible
    # But for "Integration" we want to test the DB read part specifically.
    
    # 3. Define Test Scenarios
    scenarios = [
        {
            "name": "Correct FAKE_BREAKDOWN Setup",
            "symbol": "TEST_FB_WIN",
            "metrics": {"rel_vol": 5.0, "close": 10.00},
            "key_levels": {"reclaimed_support": 9.50, "resistance": 10.20, "day1_high": 10.20},
            "pattern_type": "FAKE_BREAKDOWN",
            "market_data": {
                "current_price": 10.25, # BREAKOUT > 10.20
                "vwap": 10.10
            },
            "expected_decision": True
        },
        {
            "name": "Failed FAKE_BREAKDOWN (Price below trap)",
            "symbol": "TEST_FB_LOSS",
            "metrics": {"rel_vol": 5.0, "close": 9.00},
            "key_levels": {"reclaimed_support": 9.50, "resistance": 10.00, "day1_high": 10.00},
            "pattern_type": "FAKE_BREAKDOWN",
            "market_data": {
                "current_price": 9.20, # Below 9.50 support
                "vwap": 9.40
            },
            "expected_decision": False
        },
        {
            "name": "Generic Breakout (Day 0)",
            "symbol": "TEST_BREAKOUT",
            "metrics": {"rel_vol": 8.0, "close": 5.00},
            "key_levels": {"resistance": 5.50, "day1_high": 5.50, "daily_structure": "BREAKOUT"},
            "pattern_type": "PARABOLIC", # or generic
            "market_data": {
                "current_price": 5.52, # Breakout confirmed
                "vwap": 5.40
            },
            "expected_decision": True
        }
    ]
    
    # 4. execution Loop
    with sqlite3.connect(db_path) as conn:
        for scenario in scenarios:
            print(f"\n🧪 Testing Scenario: {scenario['name']}")
            symbol = scenario['symbol']
            
            # Clean up previous test data
            conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
            
            # Seed Database (Simulating Scanner)
            conn.execute("""
                INSERT INTO proactive_candidates (symbol, detection_date, pattern_type, status, metrics, key_levels, days_since_detection, last_check_time)
                VALUES (?, date('now'), ?, 'WATCHING', ?, ?, 1, CURRENT_TIMESTAMP)
            """, (
                symbol, 
                scenario['pattern_type'], 
                json.dumps(scenario['metrics']), 
                json.dumps(scenario['key_levels'])
            ))
            conn.commit()
            print(f"   ✅ Seeded DB for {symbol}")
            
            # Construct Opportunity (Simulating Replay/Scanner Loop)
            # Worker needs bars to calc VWAP. We must inject a fake bar method or pass pre-calc data if supported.
            # ShortSqueezeWorker calls `get_bars_from_opportunity` and `calculate_vwap_from_bars`
            
            # We will Monkey Patch `get_bars_from_opportunity` and `calculate_vwap_from_bars` on the instance
            # to return what we want without complex DataFrame construction
            worker.get_bars_from_opportunity = lambda opp: [{'timestamp': 'fake'}] # Dummy
            worker.calculate_vwap_from_bars = lambda bars: scenario['market_data']['vwap']
            
            opportunity = {
                'symbol': symbol,
                'current_price': scenario['market_data']['current_price'],
                'timestamp': datetime.now()
            }
            
            # Execute
            decision = await worker.should_enter(opportunity)
            
            # Verify
            status = "✅ PASS" if decision == scenario['expected_decision'] else f"❌ FAIL (Expected {scenario['expected_decision']}, Got {decision})"
            print(f"   👉 Decision: {decision}")
            print(f"   📝 Status: {status}")
            
            if decision != scenario['expected_decision']:
                 print(f"      Details: Price={opportunity['current_price']}, VWAP={scenario['market_data']['vwap']}, Levels={scenario['key_levels']}")

    print("\n🏁 Verification Complete.")

if __name__ == "__main__":
    # Setup Logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    # Suppress internal logs
    logging.getLogger('strategies.workers.short_squeeze_worker_logic').setLevel(logging.INFO) 
    
    asyncio.run(run_verification())
