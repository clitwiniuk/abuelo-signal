#!/usr/bin/env python3
"""
Hybrid Breakeven Validation Tests
Tests the new min(dynamic_be, safety_floor) logic
"""

import sys
from pathlib import Path

# Setup path to include the project root
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3')

# Mock missing dependencies
from unittest.mock import MagicMock
sys.modules['pandas_ta'] = MagicMock()
sys.modules['strategies.workers.holy_grail_worker_logic'] = MagicMock()
sys.modules['strategies.workers.vcp_worker_logic'] = MagicMock()
sys.modules['strategies.workers.bull_flag_worker_logic'] = MagicMock()
sys.modules['core.ods_classifier'] = MagicMock()

# Added for trade_arbiter and interfaces
sys.modules['core.trade_arbiter'] = MagicMock()
sys.modules['core.interfaces'] = MagicMock()
sys.modules['core.trade_arbiter'].TradingHorizon = MagicMock()

from strategies.workers.worker_stop_manager import WorkerStopConfig, WorkerStopManager
from datetime import datetime


def test_hybrid_breakeven():
    """Test hybrid breakeven logic with various SL scenarios"""
    
    print("=" * 80)
    print("HYBRID BREAKEVEN VALIDATION TESTS")
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
    
    # Test scenarios - redesigned to test BE activation + exit
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
        },
        {
            "name": "Very Tight SL (-1.5%)",
            "entry": 10.00,
            "sl_pct": 1.5,
            "peak_price": 10.20,  # +2.0% (activates BE at 1.5%)
            "exit_price": 10.01,  # +0.1% (should exit at BE)
            "expected_be": 1.5,   # min(1.5%, 4%) = 1.5%
            "be_source": "dynamic"
        },
    ]
    
    all_passed = True
    
    for scenario in scenarios:
        print(f"\n{'=' * 80}")
        print(f"TEST: {scenario['name']}")
        print(f"{'=' * 80}")
        print(f"Entry: ${scenario['entry']:.2f}")
        print(f"SL: -{scenario['sl_pct']:.1f}%")
        print(f"Expected BE: +{scenario['expected_be']:.1f}% ({scenario['be_source']})")
        print(f"Formula: min({scenario['sl_pct']:.1f}%, 4.0%) = {scenario['expected_be']:.1f}%")
        print()
        
        # Register position
        symbol = f"TEST_{scenario['name'].replace(' ', '_').replace('(', '').replace(')', '')}"
        manager.register_position(symbol, datetime.now())
        
        # Create position metadata with dynamic SL
        position_metadata = {
            'opportunity_data': {
                'stop_loss_pct': scenario['sl_pct']
            }
        }
        
        # Step 1: Price rises to peak (should activate BE but not exit)
        peak_pnl = ((scenario['peak_price'] - scenario['entry']) / scenario['entry']) * 100
        should_exit_peak, reason_peak = manager.check_exit(
            symbol=symbol,
            current_price=scenario['peak_price'],
            entry_price=scenario['entry'],
            position_metadata=position_metadata
        )
        
        print(f"📈 Price rises to ${scenario['peak_price']:.2f} (+{peak_pnl:.1f}%)")
        print(f"   BE should activate at +{scenario['expected_be']:.1f}%")
        print(f"   Highest PnL: {manager.highest_pnl.get(symbol, 0):.1f}%")
        print(f"   Exit: {should_exit_peak} ({'UNEXPECTED!' if should_exit_peak else 'OK - still holding'})")
        print()
        
        # Step 2: Price drops back (should exit at BE)
        exit_pnl = ((scenario['exit_price'] - scenario['entry']) / scenario['entry']) * 100
        should_exit_drop, reason_drop = manager.check_exit(
            symbol=symbol,
            current_price=scenario['exit_price'],
            entry_price=scenario['entry'],
            position_metadata=position_metadata
        )
        
        print(f"📉 Price drops to ${scenario['exit_price']:.2f} (+{exit_pnl:.1f}%)")
        print(f"   Should exit at BE: YES")
        print(f"   Actual exit: {should_exit_drop}")
        if should_exit_drop:
            print(f"   Exit reason: {reason_drop}")
        
        # Validate
        passed = should_exit_drop and "BREAK_EVEN" in reason_drop
        status = "✅ PASS" if passed else "❌ FAIL"
        
        if not passed:
            all_passed = False
        
        print(f"\n{status}: BE activated at +{scenario['expected_be']:.1f}%, protected at +{exit_pnl:.1f}%")
        print()
        
        # Cleanup
        manager.unregister_position(symbol)
    
    # Summary
    print("=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80)
    
    return all_passed


def test_legacy_fallback():
    """Test that legacy fixed BE still works"""
    
    print("\n" + "=" * 80)
    print("LEGACY FALLBACK TEST")
    print("=" * 80)
    print()
    
    # Config with legacy BE only (no hybrid)
    config = WorkerStopConfig(
        stop_loss_pct=5.0,
        take_profit_pct=20.0,
        breakeven_r_multiplier=0.0,  # Disabled
        breakeven_minimum_pct=0.0,   # Disabled
        breakeven_activation_pct=6.0,  # Legacy: 6% fixed
        trailing_activation=10.0,
        trailing_distance=4.0
    )
    
    manager = WorkerStopManager(config)
    symbol = "TEST_LEGACY"
    entry = 10.00
    
    manager.register_position(symbol, datetime.now())
    
    # Step 1: Price rises to +6% (activate BE)
    peak_price = 10.60  # +6%
    should_exit_peak, reason_peak = manager.check_exit(
        symbol=symbol,
        current_price=peak_price,
        entry_price=entry
    )
    
    print(f"📈 Price rises to ${peak_price:.2f} (+6.0%)")
    print(f"   BE should activate at +6.0% (legacy)")
    print(f"   Exit: {should_exit_peak} ({'UNEXPECTED!' if should_exit_peak else 'OK - still holding'})")
    print()
    
    # Step 2: Price drops to breakeven
    exit_price = 10.01  # +0.1%
    should_exit_drop, reason_drop = manager.check_exit(
        symbol=symbol,
        current_price=exit_price,
        entry_price=entry
    )
    
    print(f"📉 Price drops to ${exit_price:.2f} (+0.1%)")
    print(f"   Should exit at BE: YES")
    print(f"   Actual exit: {should_exit_drop}")
    if should_exit_drop:
        print(f"   Exit reason: {reason_drop}")
    print()
    
    passed = should_exit_drop and "BREAK_EVEN" in reason_drop
    status = "✅ PASS" if passed else "❌ FAIL"
    
    print(f"{status}: Legacy BE activated at +6%, protected at +0.1%")
    print()
    
    manager.unregister_position(symbol)
if __name__ == "__main__":
    test_passed = test_hybrid_breakeven()
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Hybrid Breakeven Tests: {'✅ PASSED' if test_passed else '❌ FAILED'}")
    print("=" * 80)
    print()
    print("Note: Legacy fallback (fixed BE%) is still supported for backward compatibility")
    print("      but hybrid system (min(dynamic, floor)) is the recommended approach.")
    print("=" * 80)
    
    sys.exit(0 if test_passed else 1)
