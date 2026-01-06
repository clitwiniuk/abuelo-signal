#!/usr/bin/env python3
"""
Smallcaps Worker Comparison Tool
================================

Compares 'smallcaps_long' vs 'volume_absorption' workers
running them against the same set of scenarios.
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add paths
root_path = str(Path(__file__).parent.parent)
sys.path.insert(0, root_path) # Insert at beginning to prioritize
sys.path.append(str(Path(__file__).parent))

print(f"DEBUG: sys.path[0] = {sys.path[0]}")
try:
    import core
    print("DEBUG: core imported successfully")
    import strategies.base
    print("DEBUG: strategies.base imported successfully")
except ImportError as e:
    print(f"DEBUG: Import failed: {e}")

from testing.real_worker_tester import RealWorkerTester, MockBar
from unittest.mock import MagicMock

# Mock Service Locator dependencies to prevent hangs
import core.service_locator

async def mock_get_unified_manager():
    mock = MagicMock()
    mock.is_symbol_blocked.return_value = False
    return mock

core.service_locator.get_unified_position_manager = mock_get_unified_manager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger("Comparison")

def create_bars(pattern_type: str, base_price: float = 5.0) -> List[Dict]:
    """Create specific bar patterns for testing"""
    bars = []
    
    # Set base time to today at 10:30 AM ET (16:30 Spain) to ensure we are in trading hours
    # Workers check for 9:45 AM - 4:00 PM ET
    import pytz
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern).replace(hour=10, minute=30, second=0, microsecond=0)
    # Convert back to local time for timestamp string (simulating what system expects)
    now = now_et.astimezone()
    
    if pattern_type == "random_noise":
        # Just noise, no trend
        for i in range(50):
            bars.append({
                'timestamp': (now - timedelta(minutes=50-i)).isoformat(),
                'open': base_price,
                'high': base_price * 1.01,
                'low': base_price * 0.99,
                'close': base_price,
                'volume': 10000
            })
            
    elif pattern_type == "strong_uptrend_volume":
        # Strong uptrend with increasing volume
        price = base_price
        for i in range(50):
            price *= 1.005 # 0.5% up per bar
            bars.append({
                'timestamp': (now - timedelta(minutes=50-i)).isoformat(),
                'open': price * 0.99,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': 50000 * (1 + (i/10)) # Increasing volume
            })
            
    elif pattern_type == "accumulation_breakout":
        # Consolidation then breakout
        price = base_price
        # 40 bars consolidation
        for i in range(40):
            bars.append({
                'timestamp': (now - timedelta(minutes=50-i)).isoformat(),
                'open': price,
                'high': price * 1.002,
                'low': price * 0.998,
                'close': price,
                'volume': 200000 # High volume consolidation (accumulation)
            })
        # 10 bars breakout
        for i in range(10):
            price *= 1.01
            bars.append({
                'timestamp': (now - timedelta(minutes=10-i)).isoformat(),
                'open': price * 0.99,
                'high': price * 1.02, # High close
                'low': price * 0.99,
                'close': price * 1.015,
                'volume': 500000 # Huge volume breakout
            })
            
    elif pattern_type == "bearish_trend":
        # Downtrend
        price = base_price
        for i in range(50):
            price *= 0.995
            bars.append({
                'timestamp': (now - timedelta(minutes=50-i)).isoformat(),
                'open': price * 1.01,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': 20000
            })
            
    return bars

async def run_comparison():
    print("\n🥊 WORKER COMPARISON: smallcaps_long vs volume_absorption")
    print("="*60)
    
    # Initialize testers
    tester_sc = RealWorkerTester('smallcaps_long')
    tester_va = RealWorkerTester('volume_absorption')
    
    await tester_sc.load_real_worker()
    await tester_va.load_real_worker()
    
    # Monkeypatch trading hours check for Smallcaps Long to avoid rejection
    # This is necessary because synthetic bars might have timestamps that don't match "now"
    if tester_sc.worker:
        tester_sc.worker._is_trading_hours = lambda x: True
        print("DEBUG: Monkeypatched smallcaps_long._is_trading_hours")

    # Disable surveillance mode for Volume Absorption to prevent hangs/complexity
    if tester_va.worker:
        tester_va.worker.surveillance_mode_enabled = False
        print("DEBUG: Disabled volume_absorption.surveillance_mode_enabled")

    # Define Scenarios
    scenarios = [
        {
            "name": "1. Weak Signal (Low Vol, Noise)",
            "data": {
                "symbol": "WEAK",
                "current_price": 5.0,
                "volume_ratio": 1.2,
                "gap_percentage": 1.0,
                "quality_score": 40,
                "bars": create_bars("random_noise", 5.0),
                "bars_history": create_bars("random_noise", 5.0) # Required by BaseWorkerLogic
            }
        },
        {
            "name": "2. High Volume Momentum (Simple)",
            "data": {
                "symbol": "MOMO",
                "current_price": 5.5, # Price up from 5.0 base
                "volume_ratio": 3.5, # High volume
                "gap_percentage": 5.0,
                "quality_score": 80,
                "bars": create_bars("strong_uptrend_volume", 5.0),
                "bars_history": create_bars("strong_uptrend_volume", 5.0)
            }
        },
        {
            "name": "3. Accumulation & Breakout (Complex)",
            "data": {
                "symbol": "ACCUM",
                "current_price": 5.5,
                "volume_ratio": 2.5,
                "gap_percentage": 2.0,
                "quality_score": 90,
                "bars": create_bars("accumulation_breakout", 5.0),
                "bars_history": create_bars("accumulation_breakout", 5.0)
            }
        },
        {
            "name": "4. Bearish Trend (Trap)",
            "data": {
                "symbol": "TRAP",
                "current_price": 4.0,
                "volume_ratio": 4.0, # High volume selling
                "gap_percentage": -5.0,
                "quality_score": 30,
                "bars": create_bars("bearish_trend", 5.0),
                "bars_history": create_bars("bearish_trend", 5.0)
            }
        },
        {
            "name": "5. Penny Stock (< $1)",
            "data": {
                "symbol": "PENNY",
                "current_price": 0.80,
                "volume_ratio": 5.0,
                "gap_percentage": 10.0,
                "quality_score": 75,
                "bars": create_bars("strong_uptrend_volume", 0.60),
                "bars_history": create_bars("strong_uptrend_volume", 0.60)
            }
        }
    ]
    
    print(f"{'SCENARIO':<35} | {'SMALLCAPS_LONG':<15} | {'VOLUME_ABSORPTION':<15}")
    print("-" * 75)
    
    for scenario in scenarios:
        name = scenario["name"]
        data = scenario["data"]
        
        # Test Smallcaps Long
        res_sc = await tester_sc.test_opportunity(data)
        if res_sc['success']:
            dec_sc = "✅ BUY" if res_sc['decision'] else "❌ SKIP"
        else:
            dec_sc = f"⚠️ ERR: {res_sc.get('error', 'Unknown')[:15]}"

        # Test Volume Absorption
        res_va = await tester_va.test_opportunity(data)
        if res_va['success']:
            dec_va = "✅ BUY" if res_va['decision'] else "❌ SKIP"
        else:
            dec_va = f"⚠️ ERR: {res_va.get('error', 'Unknown')[:15]}"
        
        print(f"{name:<35} | {dec_sc:<20} | {dec_va:<20}")
        
        if not res_sc['success']: print(f"  SC Error: {res_sc.get('error')}")
        if not res_va['success']: print(f"  VA Error: {res_va.get('error')}")

if __name__ == "__main__":
    asyncio.run(run_comparison())
