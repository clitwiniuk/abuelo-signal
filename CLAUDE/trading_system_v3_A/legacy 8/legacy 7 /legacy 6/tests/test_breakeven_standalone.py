import sys
import os
from unittest.mock import MagicMock
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

# Setup path
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

# We'll import the classes directly from the file to avoid __init__.py side effects
import importlib.util
spec = importlib.util.spec_from_file_location("worker_stop_manager", "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/worker_stop_manager.py")
wsm_module = importlib.util.module_from_spec(spec)
# Add to sys.modules so it can find things if needed
sys.modules["strategies.workers.worker_stop_manager"] = wsm_module
spec.loader.exec_module(wsm_module)

WorkerStopConfig = wsm_module.WorkerStopConfig
WorkerStopManager = wsm_module.WorkerStopManager

def test_hybrid_breakeven():
    """Test hybrid breakeven logic with various SL scenarios"""
    
    print("=" * 80)
    print("HYBRID BREAKEVEN STANDALONE VALIDATION")
    print("=" * 80)
    print()
    
    # Test configuration: 1R multiplier, 4% floor
    config = WorkerStopConfig(
        stop_loss_pct=5.0,  # Default (will be overridden by dynamic)
        take_profit_pct=20.0,
        breakeven_r_multiplier=1.0,  # 1R
        breakeven_minimum_pct=4.0,   # 4% floor
        trailing_activation=10.0,
        trailing_distance=4.0
    )
    
    manager = WorkerStopManager(config)
    
    # Test scenarios
    scenarios = [
        {
            "name": "Tight SL (-2%)",
            "entry": 10.00,
            "sl_pct": 2.0,
            "peak_price": 10.25,  # +2.5% (activates BE at 2%)
            "exit_price": 10.01,  # +0.1% (should exit at BE)
            "expected_be": 2.0,   # min(2%, 4%) = 2%
            "be_source": "dynamic"
        },
        {
            "name": "Medium SL (-5%)",
            "entry": 10.00,
            "sl_pct": 5.0,
            "peak_price": 10.50,  # +5.0% (activates BE at 4%)
            "exit_price": 10.01,  # +0.1% (should exit at BE)
            "expected_be": 4.0,   # min(5%, 4%) = 4%
            "be_source": "floor"
        },
        {
            "name": "Wide SL (-12%)",
            "entry": 10.00,
            "sl_pct": 12.0,
            "peak_price": 10.60,  # +6.0% (activates BE at 4%)
            "exit_price": 10.01,  # +0.1% (should exit at BE)
            "expected_be": 4.0,   # min(12%, 4%) = 4%
            "be_source": "floor"
        }
    ]
    
    all_passed = True
    
    for scenario in scenarios:
        print(f"TEST: {scenario['name']}")
        
        # Register position
        symbol = f"TEST_{scenario['name'].replace(' ', '_')}"
        manager.register_position(symbol, datetime.now())
        
        # position metadata with dynamic SL
        position_metadata = {
            'opportunity_data': {
                'stop_loss_pct': scenario['sl_pct']
            }
        }
        
        # Step 1: Price rises to peak
        should_exit_peak, reason_peak = manager.check_exit(
            symbol=symbol,
            current_price=scenario['peak_price'],
            entry_price=scenario['entry'],
            position_metadata=position_metadata
        )
        
        print(f"  📈 Peak: ${scenario['peak_price']:.2f} (+{((scenario['peak_price']/scenario['entry'])-1)*100:.1f}%)")
        
        # Step 2: Price drops back
        should_exit_drop, reason_drop = manager.check_exit(
            symbol=symbol,
            current_price=scenario['exit_price'],
            entry_price=scenario['entry'],
            position_metadata=position_metadata
        )
        
        print(f"  📉 Back: ${scenario['exit_price']:.2f}")
        print(f"  Exit: {should_exit_drop} - {reason_drop}")
        
        # Validate
        passed = should_exit_drop and "BREAK_EVEN" in reason_drop
        if not passed:
            all_passed = False
            print(f"  ❌ FAILED: Expected BREAK_EVEN exit")
        else:
            print(f"  ✅ PASSED")
        print()
    
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    
    return all_passed

if __name__ == "__main__":
    test_hybrid_breakeven()
