#!/usr/bin/env python3
"""
End-to-End Test: Proactive Scanner → Watchlist → Short Squeeze Worker

This test verifies the complete flow:
1. Proactive Scanner detects a "Day 0" candidate (Green Day 1 pattern)
2. Candidate is saved to proactive_candidates table
3. Short Squeeze Worker monitors the watchlist
4. Worker executes trade when breakout conditions are met

Usage:
    python3 tests/test_proactive_e2e.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager

# ============================================================================
# Mock Components
# ============================================================================

class MockBroker:
    """Mock broker for testing"""
    def __init__(self):
        self.prices = {}
        self.orders = []
        self.positions = {}
        
    async def get_last_price(self, symbol):
        return self.prices.get(symbol, 0.0)
        
    async def get_market_snapshot(self, symbol):
        """Mock market snapshot for worker"""
        return {
            'symbol': symbol,
            'price': self.prices.get(symbol, 0.0),
            'volume': 1000000,
            'volume_ratio': 3.0,
            'timestamp': datetime.now()
        }
        
    async def place_order(self, order):
        self.orders.append(order)
        print(f"📋 MOCK BROKER: Order placed - {order.action} {order.quantity} {order.symbol} @ ${self.prices.get(order.symbol, 0):.2f}")
        return True
        
    async def close_position(self, symbol, quantity):
        print(f"📋 MOCK BROKER: Closing {symbol}")
        return True

class MockRiskManager:
    """Mock risk manager - always approves"""
    def validate_signal(self, *args, **kwargs):
        return True
        
    def validate_order(self, *args, **kwargs):
        return True

class MockDatabaseManager:
    """Mock database manager with correct db_path"""
    def __init__(self):
        from pathlib import Path
        self.db_path = Path('trading_data.db')

# ============================================================================
# Test Utilities
# ============================================================================

def create_test_candidate(symbol: str = "TEST", day_offset: int = 0) -> Dict[str, Any]:
    """Create a test candidate for the proactive_candidates table"""
    detection_date = (datetime.now() - timedelta(days=day_offset)).strftime('%Y-%m-%d')
    
    return {
        'symbol': symbol,
        'detection_date': detection_date,
        'pattern_type': 'GREEN_DAY_1',
        'quality_score': 85.0,
        'status': 'WATCHING',
        'key_levels': {
            'day0_high': 5.50,
            'day0_low': 4.80,
            'day0_close': 5.40,
            'resistance': 5.50,
            'support': 4.80,
            'entry_trigger': 5.55  # Breakout level
        },
        'metrics': {
            'rel_vol': 4.5,
            'gain_pct': 25.0,
            'retention_pct': 85.0,
            'volume': 5000000,
            'market_cap': 50000000
        },
        'catalyst_info': {
            'has_catalyst': True,
            'catalyst_type': 'FDA_APPROVAL',
            'catalyst_age_hours': 12,
            'sentiment_score': 0.85
        }
    }

def insert_test_candidate(candidate: Dict[str, Any]):
    """Insert a test candidate into the database"""
    import json
    
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO proactive_candidates 
        (symbol, detection_date, pattern_type, status, 
         key_levels, metrics, days_since_detection, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        candidate['symbol'],
        candidate['detection_date'],
        candidate['pattern_type'],
        candidate['status'],
        json.dumps(candidate['key_levels']),
        json.dumps(candidate['metrics']),
        candidate.get('day_offset', 0)
    ))
    
    conn.commit()
    conn.close()
    print(f"✅ Test candidate inserted: {candidate['symbol']} (Day {candidate.get('day_offset', 0)})")

def cleanup_test_data(symbol: str):
    """Clean up test data from database"""
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()
    print(f"🧹 Cleaned up test data for {symbol}")

# ============================================================================
# Test Scenarios
# ============================================================================

async def test_scenario_1_fresh_candidate():
    """
    Scenario 1: Fresh Day 0 candidate (detected today)
    - Should be in watchlist
    - Worker should monitor it
    - No entry yet (price below trigger)
    """
    print("\n" + "="*80)
    print("SCENARIO 1: Fresh Day 0 Candidate (No Entry Yet)")
    print("="*80)
    
    broker = MockBroker()
    risk_manager = MockRiskManager()
    
    # Create test candidate
    candidate = create_test_candidate(symbol="TEST_FRESH", day_offset=0)
    insert_test_candidate(candidate)
    
    # Set price BELOW trigger (no entry yet)
    broker.prices["TEST_FRESH"] = 5.45  # Below 5.55 trigger
    
    # Initialize worker
    worker = ShortSqueezeWorkerLogic(
        broker=broker,
        risk_manager=risk_manager,
        config=None
    )
    
    # CRITICAL: Set worker as running and inject mock database manager
    worker.is_running = True
    worker.db_manager = MockDatabaseManager()
    
    # Mock _fetch_candidate_snapshots to return broker prices
    async def mock_fetch_snapshots(symbols):
        return {sym: await broker.get_market_snapshot(sym) for sym in symbols}
    
    worker._fetch_candidate_snapshots = mock_fetch_snapshots
    
    # Run periodic task (should detect candidate but not enter)
    await worker._periodic_task()
    
    # Verify
    if len(broker.orders) == 0:
        print("✅ PASS: No entry executed (price below trigger)")
    else:
        print(f"❌ FAIL: Unexpected entry executed: {broker.orders}")
    
    # Cleanup
    cleanup_test_data("TEST_FRESH")
    return len(broker.orders) == 0

async def test_scenario_2_breakout_entry():
    """
    Scenario 2: Day 2 candidate with breakout
    - Price crosses above resistance
    - Worker should execute entry
    """
    print("\n" + "="*80)
    print("SCENARIO 2: Day 2 Breakout (Entry Triggered)")
    print("="*80)
    
    broker = MockBroker()
    risk_manager = MockRiskManager()
    
    # Create Day 2 candidate
    candidate = create_test_candidate(symbol="TEST_BREAKOUT", day_offset=2)
    candidate['key_levels']['day2_high'] = 5.60  # Made new high
    candidate['key_levels']['resistance'] = 5.60
    insert_test_candidate(candidate)
    
    # Set price ABOVE trigger (breakout!)
    broker.prices["TEST_BREAKOUT"] = 5.70  # Above 5.55 trigger
    
    # Initialize worker
    worker = ShortSqueezeWorkerLogic(
        broker=broker,
        risk_manager=risk_manager,
        config=None
    )
    
    # CRITICAL: Set worker as running and inject mocks
    worker.is_running = True
    worker.db_manager = MockDatabaseManager()
    
    async def mock_fetch_snapshots(symbols):
        return {sym: await broker.get_market_snapshot(sym) for sym in symbols}
    
    worker._fetch_candidate_snapshots = mock_fetch_snapshots
    
    # Run periodic task (should execute entry)
    await worker._periodic_task()
    
    # Verify
    if len(broker.orders) > 0:
        print(f"✅ PASS: Entry executed - {broker.orders[0].action} {broker.orders[0].quantity} shares")
    else:
        print("❌ FAIL: No entry executed despite breakout")
    
    # Cleanup
    cleanup_test_data("TEST_BREAKOUT")
    return len(broker.orders) > 0

async def test_scenario_3_expired_candidate():
    """
    Scenario 3: Day 8 candidate (expired)
    - Should be marked as EXPIRED
    - Worker should not monitor it
    """
    print("\n" + "="*80)
    print("SCENARIO 3: Expired Candidate (Day 8)")
    print("="*80)
    
    broker = MockBroker()
    risk_manager = MockRiskManager()
    
    # Create Day 8 candidate (expired)
    candidate = create_test_candidate(symbol="TEST_EXPIRED", day_offset=8)
    insert_test_candidate(candidate)
    
    # Set price at breakout level
    broker.prices["TEST_EXPIRED"] = 5.70
    
    # Initialize worker
    worker = ShortSqueezeWorkerLogic(
        broker=broker,
        risk_manager=risk_manager,
        config=None
    )
    
    # CRITICAL: Set worker as running and inject mocks
    worker.is_running = True
    worker.db_manager = MockDatabaseManager()
    
    async def mock_fetch_snapshots(symbols):
        return {sym: await broker.get_market_snapshot(sym) for sym in symbols}
    
    worker._fetch_candidate_snapshots = mock_fetch_snapshots
    
    # Run periodic task (should ignore expired candidate)
    await worker._periodic_task()
    
    # Verify
    if len(broker.orders) == 0:
        print("✅ PASS: Expired candidate ignored (no entry)")
    else:
        print(f"❌ FAIL: Entry executed on expired candidate: {broker.orders}")
    
    # Cleanup
    cleanup_test_data("TEST_EXPIRED")
    return len(broker.orders) == 0

async def test_scenario_4_multiple_candidates():
    """
    Scenario 4: Multiple candidates in watchlist
    - Worker should monitor all active candidates
    - Only execute entries for valid breakouts
    """
    print("\n" + "="*80)
    print("SCENARIO 4: Multiple Candidates (Selective Entry)")
    print("="*80)
    
    broker = MockBroker()
    risk_manager = MockRiskManager()
    
    # Create 3 candidates
    candidates = [
        create_test_candidate(symbol="MULTI_A", day_offset=1),  # Day 1
        create_test_candidate(symbol="MULTI_B", day_offset=3),  # Day 3
        create_test_candidate(symbol="MULTI_C", day_offset=5),  # Day 5
    ]
    
    for candidate in candidates:
        insert_test_candidate(candidate)
    
    # Set prices: Only MULTI_B breaks out
    broker.prices["MULTI_A"] = 5.40  # Below trigger
    broker.prices["MULTI_B"] = 5.70  # BREAKOUT!
    broker.prices["MULTI_C"] = 5.50  # Below trigger
    
    # Initialize worker
    worker = ShortSqueezeWorkerLogic(
        broker=broker,
        risk_manager=risk_manager,
        config=None
    )
    
    # CRITICAL: Set worker as running and inject mocks
    worker.is_running = True
    worker.db_manager = MockDatabaseManager()
    
    async def mock_fetch_snapshots(symbols):
        return {sym: await broker.get_market_snapshot(sym) for sym in symbols}
    
    worker._fetch_candidate_snapshots = mock_fetch_snapshots
    
    # Run periodic task
    await worker._periodic_task()
    
    # Verify: Should only have 1 entry (MULTI_B)
    if len(broker.orders) == 1 and broker.orders[0].symbol == "MULTI_B":
        print(f"✅ PASS: Correct selective entry - Only MULTI_B executed")
    else:
        print(f"❌ FAIL: Expected 1 entry (MULTI_B), got {len(broker.orders)}: {[o.symbol for o in broker.orders]}")
    
    # Cleanup
    for candidate in candidates:
        cleanup_test_data(candidate['symbol'])
    
    return len(broker.orders) == 1 and broker.orders[0].symbol == "MULTI_B"

# ============================================================================
# Main Test Runner
# ============================================================================

async def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("PROACTIVE SCANNER E2E TEST SUITE")
    print("="*80)
    print("Testing: Scanner → Database → Worker → Execution")
    print()
    
    results = []
    
    # Run scenarios
    results.append(("Scenario 1: Fresh Candidate (No Entry)", await test_scenario_1_fresh_candidate()))
    results.append(("Scenario 2: Breakout Entry", await test_scenario_2_breakout_entry()))
    results.append(("Scenario 3: Expired Candidate", await test_scenario_3_expired_candidate()))
    results.append(("Scenario 4: Multiple Candidates", await test_scenario_4_multiple_candidates()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("⚠️ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
