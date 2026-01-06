#!/usr/bin/env python3
"""
Test Proactive Scanner Logic with REAL historical data from DB.
Uses AEHL bars (ID 576) from trade_ohlc_snapshots.
"""

import sys
import os
import asyncio
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.interfaces import MarketData  # Ensure BarDataWrapper compatibility

# Mock components
class MockBroker:
    def __init__(self):
        self.orders = []
        self.prices = {}

    async def get_last_price(self, symbol): return 2.47
    async def get_market_snapshot(self, symbol): return {}
    async def place_order(self, order): 
        self.orders.append(order)
        return True

class MockRiskManager:
    def validate_signal(self, *args, **kwargs): return True

def get_real_bars():
    """Fetch real AEHL bars from DB"""
    try:
        conn = sqlite3.connect('trading_data.db')
        cursor = conn.cursor()
        # AEHL ID 576
        cursor.execute("SELECT intraday_bars FROM trade_ohlc_snapshots WHERE id=576")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return []
    except Exception as e:
        print(f"❌ Error fetching bars: {e}")
        return []

async def test_real_data_entry():
    print("="*60)
    print("TESTING WORKER WITH REAL MARKET DATA (AEHL)")
    print("="*60)
    
    # 1. Get Real Bars
    bars = get_real_bars()
    if not bars:
        print("❌ FAIL: Could not load bars from DB")
        return False
        
    print(f"✅ Loaded {len(bars)} real bars for AEHL")
    
    # 2. Setup Worker
    broker = MockBroker()
    risk_manager = MockRiskManager()
    worker = ShortSqueezeWorkerLogic(broker, risk_manager, None)
    worker.is_running = True
    
    # Setup Logger
    logging.basicConfig(level=logging.INFO)
    worker.logger = logging.getLogger("TestWorker")
    
    # 3. Construct Opportunity
    # Logic: Breakout of 2.40 resistance (Max High in bars is 2.47)
    # VWAP in bars is ~2.09, so Price > VWAP holds true
    
    opportunity = {
        'symbol': 'AEHL',
        'current_price': 2.47, # At the highs
        'bars_history': bars,  # The REAL data
        'candidate_info': {
            'symbol': 'AEHL',
            'days_since_detection': 1, # Day 1 Breakout
            'pattern_type': 'GREEN_DAY_1',
            'key_levels': {
                'resistance': 2.40,  # Below current price
                'support': 1.60,
                'day1_high': 2.40,
                'daily_structure': 'BREAKOUT'
            }
        }
    }
    
    print(f"📊 Scenario: Price $2.47 vs Resistance $2.40 (Real Bars VWAP ~2.09)")
    
    # 4. Check Entry & Execution
    should_enter = await worker.should_enter(opportunity)
    
    if should_enter:
        print("✅ PASS: Worker approved entry logic!")
        
        # Execute the entry
        await worker._execute_entry(opportunity)
        
        # Verify execution in MockBroker
        if len(broker.orders) > 0:
            last_order = broker.orders[-1]
            print(f"✅ PASS: Order Executed -> {last_order.action} {last_order.quantity} shares of {last_order.symbol} at ${broker.prices.get(last_order.symbol, 0)}")
            return True
        else:
            print("❌ FAIL: Entry approved but NO ORDER placed in broker.")
            return False
            
    else:
        print("❌ FAIL: Worker rejected entry.")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_real_data_entry())
    sys.exit(0 if success else 1)
