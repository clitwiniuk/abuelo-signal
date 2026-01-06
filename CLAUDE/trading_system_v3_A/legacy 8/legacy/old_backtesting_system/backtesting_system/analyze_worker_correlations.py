import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

# Add paths
root_path = str(Path(__file__).parent.parent)
sys.path.insert(0, root_path) # Insert at beginning to prioritize
sys.path.append(str(Path(__file__).parent))

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
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger = logging.getLogger("CorrelationAnalysis")

def create_bars(pattern_type: str, base_price: float = 5.0) -> List[Dict]:
    """Create specific bar patterns for testing"""
    bars = []
    
    # Set base time to today at 10:30 AM ET (16:30 Spain) to ensure we are in trading hours
    import pytz
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern).replace(hour=10, minute=30, second=0, microsecond=0)
    # Convert back to local time for timestamp string
    now = now_et.astimezone()
    
    if pattern_type == "random_noise":
        # Just noise, no trend
        import random
        price = base_price
        for i in range(50):
            change = random.uniform(-0.01, 0.01)
            price *= (1 + change)
            bars.append({
                'timestamp': (now - pd.Timedelta(minutes=50-i)).isoformat(),
                'open': price,
                'high': price * 1.005,
                'low': price * 0.995,
                'close': price * (1 + random.uniform(-0.005, 0.005)),
                'volume': 10000
            })
            
    elif pattern_type == "strong_uptrend_volume":
        # Strong uptrend with increasing volume
        price = base_price
        for i in range(50):
            change = 0.005 # 0.5% up per bar
            price *= (1 + change)
            bars.append({
                'timestamp': (now - pd.Timedelta(minutes=50-i)).isoformat(),
                'open': price * 0.998,
                'high': price * 1.002,
                'low': price * 0.998,
                'close': price,
                'volume': 50000 + (i * 1000) # Increasing volume
            })
            
    elif pattern_type == "accumulation_breakout":
        # Consolidation then breakout
        price = base_price
        # 40 bars consolidation
        for i in range(40):
            import random
            current_price = base_price * (1 + random.uniform(-0.01, 0.01))
            bars.append({
                'timestamp': (now - pd.Timedelta(minutes=50-i)).isoformat(),
                'open': current_price,
                'high': current_price * 1.01,
                'low': current_price * 0.99,
                'close': current_price,
                'volume': 20000
            })
        # 10 bars breakout
        for i in range(40, 50):
            price = base_price * (1.02 + (i-40)*0.01) # Breakout
            bars.append({
                'timestamp': (now - pd.Timedelta(minutes=50-i)).isoformat(),
                'open': price * 0.99,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': 100000 # High volume
            })
            
    elif pattern_type == "bearish_trend":
        # Downtrend
        price = base_price
        for i in range(50):
            change = -0.005 # 0.5% down per bar
            price *= (1 + change)
            bars.append({
                'timestamp': (now - pd.Timedelta(minutes=50-i)).isoformat(),
                'open': price * 1.002,
                'high': price * 1.002,
                'low': price * 0.998,
                'close': price,
                'volume': 30000
            })
            
    return bars

async def run_analysis():
    logger.info("🚀 Starting Worker Correlation Analysis")
    
    workers_to_test = [
        'smallcaps_long',
        'volume_absorption',
        'macdv',
        'daily_plays',
        'vcp_smallcap'
    ]
    
    testers = {}
    
    # Initialize testers
    for name in workers_to_test:
        try:
            tester = RealWorkerTester(name)
            await tester.load_real_worker()
            
            # Monkeypatch trading hours check
            if tester.worker:
                tester.worker._is_trading_hours = lambda x: True
                # Disable surveillance mode if present
                if hasattr(tester.worker, 'surveillance_mode_enabled'):
                    tester.worker.surveillance_mode_enabled = False
                
            testers[name] = tester
            logger.info(f"✅ Loaded {name}")
        except Exception as e:
            logger.error(f"❌ Failed to load {name}: {e}")

    # Define Scenarios
    scenarios = [
        {
            "name": "1. Weak Signal",
            "data": {
                "symbol": "WEAK",
                "current_price": 5.0,
                "volume_ratio": 1.2,
                "gap_percentage": 1.0,
                "quality_score": 40,
                "bars": create_bars("random_noise", 5.0),
                "bars_history": create_bars("random_noise", 5.0)
            }
        },
        {
            "name": "2. Momentum",
            "data": {
                "symbol": "MOMO",
                "current_price": 5.5,
                "volume_ratio": 3.5,
                "gap_percentage": 5.0,
                "quality_score": 80,
                "bars": create_bars("strong_uptrend_volume", 5.0),
                "bars_history": create_bars("strong_uptrend_volume", 5.0)
            }
        },
        {
            "name": "3. Accumulation",
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
            "name": "4. Bearish Trap",
            "data": {
                "symbol": "TRAP",
                "current_price": 4.0,
                "volume_ratio": 4.0,
                "gap_percentage": -5.0,
                "quality_score": 30,
                "bars": create_bars("bearish_trend", 5.0),
                "bars_history": create_bars("bearish_trend", 5.0)
            }
        },
        {
            "name": "5. Penny Stock",
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
    
    # Run Tests
    results_matrix = {scenario['name']: {} for scenario in scenarios}
    
    print("\n🥊 WORKER CORRELATION MATRIX")
    print("=" * 100)
    
    header = f"{'SCENARIO':<20} | " + " | ".join([f"{w[:10]:<10}" for w in workers_to_test])
    print(header)
    print("-" * 100)
    
    for scenario in scenarios:
        row_str = f"{scenario['name']:<20} | "
        
        for worker_name in workers_to_test:
            tester = testers.get(worker_name)
            if not tester or not tester.worker:
                res_str = "⚠️ ERR"
                results_matrix[scenario['name']][worker_name] = 0
            else:
                res = await tester.test_opportunity(scenario['data'])
                if res['success']:
                    decision = res['decision']
                    res_str = "✅ BUY" if decision else "❌ SKIP"
                    results_matrix[scenario['name']][worker_name] = 1 if decision else 0
                else:
                    res_str = "⚠️ ERR"
                    results_matrix[scenario['name']][worker_name] = 0
                    if worker_name == 'gap_go':
                        print(f"\nDEBUG GAP_GO ERROR: {res.get('error')}\n")
            
            row_str += f"{res_str:<10} | "
        
        print(row_str)
        
    # Calculate Correlations (Jaccard Similarity) with Smallcaps Long
    print("\n📊 CORRELATION WITH SMALLCAPS_LONG")
    print("=" * 50)
    base_worker = 'smallcaps_long'
    base_decisions = [results_matrix[s['name']][base_worker] for s in scenarios]
    
    for worker_name in workers_to_test:
        if worker_name == base_worker: continue
        
        other_decisions = [results_matrix[s['name']][worker_name] for s in scenarios]
        
        # Calculate overlap
        matches = sum(1 for i in range(len(scenarios)) if base_decisions[i] == other_decisions[i])
        similarity = matches / len(scenarios)
        
        # Calculate if they buy the same things (Positive Correlation)
        both_buy = sum(1 for i in range(len(scenarios)) if base_decisions[i] == 1 and other_decisions[i] == 1)
        
        print(f"{worker_name:<20}: {similarity:.0%} Similarity (Both Buy: {both_buy})")

if __name__ == "__main__":
    asyncio.run(run_analysis())
