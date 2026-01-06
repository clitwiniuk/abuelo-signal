#!/usr/bin/env python3
"""
Run Regression - Ejecuta escenarios de prueba para verificar workers
"""

import json
import os
import sys
import subprocess
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core.replay_engine import ReplayEngine

def run_scenario(scenario, market_db_path, trading_db_path, skip_prep=False):
    """Run a single scenario"""
    scenario_id = scenario.get('id')
    symbol = scenario.get('symbol')
    
    # Skip documentation scenarios (they don't have symbol field)
    if not symbol or 'DOCUMENTATION' in scenario_id:
        print(f"▶️ Skipping: {scenario_id} (documentation)")
        return True  # Return True to not count as failure
    
    print(f"\n▶️ Running Scenario: {scenario_id}")
    print(f"   Symbol: {symbol}")
    print(f"   Date: {scenario['date']}")
    print(f"   Expected: {scenario['expected_action']}")
    
    # 1. Prepare DB
    if not skip_prep:
        print("   🔨 Preparing DB...")
        cmd = [
            sys.executable, 
            "scripts/prepare_replay_db.py",
            "--symbol", scenario['symbol'],
            "--date", scenario['date'],
            "--trading-db", trading_db_path,
            "--output-db", market_db_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ DB Preparation Failed: {result.stderr}")
            return False
    else:
        print("   🔨 Using existing DB (skipping preparation)")
        
    # 2. Run Replay
    print("   🔄 Running Replay...")
    engine = ReplayEngine(
        market_data_db_path=market_db_path,
        trading_data_db_path=trading_db_path,
        verbose=True
    )
    
    # Prepare mock metadata
    mock_metadata = {
        scenario['symbol']: scenario.get('mock_scanner_data', {})
    }
    
    # INJECTION: Configure Break-Even for specific test case
    setup_callback = None
    if "BREAKEVEN_TEST" in scenario['id']:
        def setup_workers(workers):
            if 'daily_plays' in workers:
                print("   💉 Injecting Break-Even Config: activation=2.0%")
                workers['daily_plays'].stop_manager.config.breakeven_activation_pct = 2.0
        setup_callback = setup_workers

    # Get worker name from scenario or default to daily_plays
    worker_name = scenario.get('worker_name', 'daily_plays')
    
    session = engine.replay_day(
        date=scenario['date'],
        worker_names=[worker_name],
        symbols=[scenario['symbol']],
        mock_metadata=mock_metadata,
        setup_callback=setup_callback
    )
    
    # 3. Verify Results
    entries = session.entries_approved
    
    # Check for exits if expected action is EXIT_BREAKEVEN
    exit_reason = "NONE"
    expected_action = scenario['expected_action']
    symbol = scenario['symbol']

    if expected_action == "EXIT_BREAKEVEN":
         # Find the exit decision in the engine's session
         if session:
             event = session.get_event(symbol)
             if event:
                 decisions = event.get_all_decisions()
                 for d in decisions:
                     if d.decision_type == 'EXIT':
                         exit_reason = d.exit_reason
                         break
    
    actual_action = "ENTRY" if entries > 0 else "NO_ENTRY"
    
    if session.entries_approved > 0:
        # Check for exit
        if session.exits_triggered:
            # Collect all exit reasons
            exit_reasons = [exit.get('reason', 'UNKNOWN') for exit in session.exits_triggered]
            # Construct a composite actual_action string for validation
            actual_action = f"EXIT_{','.join(exit_reasons)}"
        else:
            actual_action = "ENTRY"
    else:
        actual_action = "NO_ENTRY"

    print(f"   📊 Results: {entries} entries approved")
    
    if expected_action == 'ENTRY':
        if entries > 0:
            print("   ✅ PASS: Entry occurred as expected")
            return True
        else:
            print("   ❌ FAIL: No entry occurred")
            return False
    elif scenario['expected_action'] == 'NO_ENTRY':
        if entries == 0:
            print("   ✅ PASS: No entry occurred as expected")
            return True
        else:
            print(f"   ❌ FAIL: {entries} entries occurred (expected 0)")
            return False

    elif expected_action == 'EXIT_BREAKEVEN':
        if 'BREAK_EVEN' in actual_action:
            print(f"   ✅ PASS: Entry occurred and exited at Break-Even ({actual_action})")
            return True
        else:
            print(f"   ❌ FAIL: Expected EXIT_BREAKEVEN, but got {actual_action}")
            return False

    elif expected_action == 'EXIT_TAKE_PROFIT':
        if 'TAKE_PROFIT' in actual_action or 'EXIT_PROFIT' in actual_action:
            print(f"   ✅ PASS: Entry occurred and exited at Take Profit ({actual_action})")
            return True
        else:
            print(f"   ❌ FAIL: Expected EXIT_TAKE_PROFIT, but got {actual_action}")
            return False

    elif expected_action == 'EXIT_TRAILING_STOP':
        if 'TRAILING_STOP' in actual_action:
            print(f"   ✅ PASS: Entry occurred and exited at Trailing Stop ({actual_action})")
            return True
        else:
            print(f"   ❌ FAIL: Expected EXIT_TRAILING_STOP, but got {actual_action}")
            return False
    
    elif expected_action == 'EXIT_STOP_LOSS':
        if 'STOP_LOSS' in actual_action:
            print(f"   ✅ PASS: Entry occurred and exited at Stop Loss ({actual_action})")
            return True
        else:
            print(f"   ❌ FAIL: Expected EXIT_STOP_LOSS, but got {actual_action}")
            return False
    
    elif expected_action == 'EXIT_TIME_LIMIT':
        if 'EOD_EXIT' in actual_action or 'MAX_HOLD_TIME' in actual_action or 'TIME' in actual_action:
            print(f"   ✅ PASS: Entry occurred and exited at Time Limit ({actual_action})")
            return True
        else:
            print(f"   ❌ FAIL: Expected EXIT_TIME_LIMIT, but got {actual_action}")
            return False
            
    return False

def main():
    parser = argparse.ArgumentParser(description='Run Regression Suite')
    parser.add_argument('--scenarios', default='replay_testing/scenarios/daily_plays_scenarios.json', help='Path to scenarios JSON')
    parser.add_argument('--trading-db', default='trading_data.db', help='Path to trading_data.db')
    parser.add_argument('--market-db', help='Path to existing market_data.db (skips preparation)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.scenarios):
        print(f"❌ Scenarios file not found: {args.scenarios}")
        sys.exit(1)
        
    with open(args.scenarios, 'r') as f:
        scenarios = json.load(f)
        
    print(f"🚀 Starting Regression Suite: {len(scenarios)} scenarios")
    print("="*60)
    
    market_db_path = args.market_db if args.market_db else "regression_market_data.db"
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        # If market_db provided, skip preparation
        skip_prep = args.market_db is not None
        if run_scenario(scenario, market_db_path, args.trading_db, skip_prep=skip_prep):
            passed += 1
        else:
            failed += 1
            
    # Cleanup only if we created it
    if not args.market_db and os.path.exists(market_db_path):
        os.remove(market_db_path)
        
    print("\n" + "="*60)
    print(f"🏁 Regression Complete")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
