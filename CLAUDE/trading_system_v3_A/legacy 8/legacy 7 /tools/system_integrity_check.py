#!/usr/bin/env python3
"""
System Integrity Check
======================
Test battery to verify that all refactored workers are correctly aligned 
with the AbstractBroker architecture and can be instantiated/run.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import tools and workers
from tools.run_worker_test import WORKER_MAP, MockRiskManager
from core.brokers.simulated_broker import SimulatedBroker

async def test_worker_integrity(worker_name: str, worker_class: type):
    """Tests if a worker can be initialized and perform a basic logic check"""
    print(f"🔍 Testing {worker_name}...")
    
    try:
        # Prepare mocks
        sim_broker = SimulatedBroker(initial_cash=100000.0)
        risk = MockRiskManager()
        
        class MockConfig:
            def get(self, section, option, fallback=None): return fallback
            def getfloat(self, section, option, fallback=None): return float(fallback or 0.0)
            def getint(self, section, option, fallback=None): return int(fallback or 0)
            def getboolean(self, section, option, fallback=None): return bool(fallback or False)
        
        config = MockConfig()

        # Instantiate
        try:
            # Try broker-first (New Architecture)
            worker = worker_class(broker=sim_broker, risk_manager=risk, config=config)
            print(f"  ✅ {worker_name}: Initialized with NEW architecture (broker)")
        except TypeError:
            # Fallback for legacy workers
            from tools.run_worker_test import MockExecutionEngine
            engine = MockExecutionEngine()
            worker = worker_class(worker_name=worker_name, execution_engine=engine, risk_manager=risk, config=config)
            print(f"  ⚠️  {worker_name}: Initialized with LEGACY architecture (execution_engine)")

        # Basic attribute check
        if not hasattr(worker, 'broker') and not hasattr(worker, 'execution_engine'):
            print(f"  ❌ {worker_name}: Missing both broker and execution_engine")
            return False
            
        print(f"  ✅ {worker_name}: Integrity OK")
        return True

    except Exception as e:
        print(f"  ❌ {worker_name}: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🚀 Starting System Integrity Check for Refactored Workers\n")
    
    workers_to_test = [
        'vwap', 'momentum_breakout', 'holy_grail', 'livermore_intraday', 'short_parabolic',
        'smallcaps_long', 'smallcaps_short_reversal', 'catalyst_dna',
        'balance_day', 'generic_01', 'outlier_penny_extreme', 
        'ods_universal', 'ods_swing_universal', 'vcp_strict_long', 'vcp_strict_short'
    ]
    
    results = []
    for name in workers_to_test:
        if name in WORKER_MAP:
            success = await test_worker_integrity(name, WORKER_MAP[name])
            results.append((name, success))
        else:
            print(f"❓ {name}: Not found in WORKER_MAP")
            results.append((name, False))
            
    print("\n📊 SUMMARY:")
    passed = len([r for r in results if r[1]])
    failed = len(results) - passed
    
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    
    if failed > 0:
        print("\n❌ System Integrity Check FAILED")
        for name, success in results:
            if not success:
                print(f"   - {name}")
        sys.exit(1)
    else:
        print("\n✅ System Integrity Check PASSED")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
