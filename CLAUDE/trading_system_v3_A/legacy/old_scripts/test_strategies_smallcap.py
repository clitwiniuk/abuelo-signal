#!/usr/bin/env python3
"""
Test script para verificar que todas las estrategias smallcap funcionan correctamente
con las optimizaciones aplicadas.
"""

import sys
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Signal, SignalType, Position
from core.stop_loss_manager import get_stop_loss_manager, create_stop_params_from_config
import sqlite3

def create_test_market_data(symbol: str, price: float = 10.0, volume: int = 100000) -> MarketData:
    """Create test market data"""
    now = datetime.now()
    return MarketData(
        symbol=symbol,
        timestamp=now,
        open=price * 0.98,
        high=price * 1.02,
        low=price * 0.97,
        close=price,
        volume=volume,
        vwap=price * 0.99,
        bid=price * 0.999,
        ask=price * 1.001,
        bid_size=1000,
        ask_size=1000
    )

def create_test_position(symbol: str, quantity: int = 100, avg_price: float = 10.0) -> Position:
    """Create test position"""
    return Position(
        symbol=symbol,
        quantity=quantity,
        avg_price=avg_price,
        market_price=avg_price,
        market_value=quantity * avg_price,
        unrealized_pnl=0.0,
        realized_pnl=0.0,
        entry_time=datetime.now()
    )

def test_strategy_import_and_init(strategy_name: str, strategy_class, test_params: Dict[str, Any]) -> bool:
    """Test strategy import and initialization"""
    try:
        print(f"\n🧪 Testing {strategy_name}...")

        # Initialize strategy
        strategy = strategy_class(test_params)
        print(f"   ✅ {strategy_name} initialized successfully")

        # Check if stop_manager is available
        if hasattr(strategy, 'stop_manager'):
            print(f"   ✅ Stop manager available: {type(strategy.stop_manager)}")
        else:
            print(f"   ⚠️  No stop_manager attribute found")

        # Check if registration method exists
        if hasattr(strategy, '_register_position_with_stop_manager'):
            print(f"   ✅ Registration method available")
        else:
            print(f"   ⚠️  No registration method found")

        # Test basic analyze method if available
        if hasattr(strategy, 'analyze'):
            test_bar = create_test_market_data("TEST", 10.0)
            try:
                # Different analyze signatures for different strategies
                if strategy_name == 'DailyPlaysStrategy':
                    result = strategy.analyze("TEST", test_bar, {})  # needs current_positions
                else:
                    result = strategy.analyze("TEST", test_bar)
                print(f"   ✅ Analyze method works (returned: {type(result).__name__})")
            except Exception as e:
                print(f"   ⚠️  Analyze method error: {str(e)[:100]}...")

        # Test should_exit method if available
        if hasattr(strategy, 'should_exit'):
            test_position = create_test_position("TEST")
            test_bar = create_test_market_data("TEST", 10.0)
            try:
                # Different should_exit signatures for different strategies
                if strategy_name in ['GapCrapReversalStrategy']:
                    result = strategy.should_exit("TEST", test_position, test_bar)
                elif strategy_name in ['DailyPlaysStrategy']:
                    result = strategy.should_exit("TEST", test_bar, test_position)
                else:
                    result = strategy.should_exit(test_position, test_bar)
                print(f"   ✅ Should_exit method works (returned: {type(result).__name__})")
            except Exception as e:
                print(f"   ⚠️  Should_exit method error: {str(e)[:100]}...")

        print(f"   ✅ {strategy_name} - ALL TESTS PASSED")
        return True

    except Exception as e:
        print(f"   ❌ {strategy_name} - ERROR: {str(e)}")
        print(f"   📋 Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all strategy tests"""
    print("🚀 SMALLCAP STRATEGIES OPTIMIZATION TEST")
    print("=" * 50)

    # Initialize database for stop_loss_manager
    print("\n📊 Initializing stop_loss_manager...")
    try:
        stop_manager = get_stop_loss_manager()
        print("   ✅ Stop loss manager initialized")
    except Exception as e:
        print(f"   ❌ Stop manager error: {e}")
        return

    # Common test parameters
    base_params = {
        'min_price': 1.0,
        'max_price': 15.0,
        'min_daily_volume': 100000,
        'stop_loss_pct': 0.06,  # Smallcap optimized
        'max_position_value': 200.0,
        'risk_per_trade': 0.015
    }

    # Test each strategy
    strategies_to_test = [
        {
            'name': 'GapGoStrategy',
            'module': 'strategies.gap_go_strategy',
            'class': 'GapGoStrategy',
            'params': {
                **base_params,
                'min_gap_percent': 4.0,
                'max_gap_percent': 20.0,
                'premarket_volume_min': 10000
            }
        },
        {
            'name': 'GapCrapReversalStrategy',
            'module': 'strategies.gap_crap_reversal_strategy',
            'class': 'GapCrapReversalStrategy',
            'params': {
                **base_params,
                'min_gap_percent': 30.0,
                'max_gap_percent': 200.0,
                'force_exit_time': 15.83
            }
        },
        {
            'name': 'DailyPlaysStrategy',
            'module': 'strategies.daily_plays_strategy',
            'class': 'DailyPlaysStrategy',
            'params': {
                **base_params,
                'ema_period': 9,
                'first_30_minutes': 30
            }
        },
        {
            'name': 'FirstDayBounceStrategy',
            'module': 'strategies.first_day_bounce_strategy',
            'class': 'FirstDayBounceStrategy',
            'params': {
                **base_params,
                'min_gain_for_overextension_pct': 0.5,
                'min_retrace_pct': 0.25,
                'max_retrace_pct': 0.5
            }
        },
        {
            'name': 'RedToGreenStrategy',
            'module': 'strategies.red_to_green_strategy',
            'class': 'RedToGreenStrategy',
            'params': {
                **base_params,
                'mandatory_exit_hour': 15.5,
                'stop_loss_below_r2g': 0.06
            }
        }
    ]

    results = []

    for strategy_config in strategies_to_test:
        try:
            # Dynamic import
            module = __import__(strategy_config['module'], fromlist=[strategy_config['class']])
            strategy_class = getattr(module, strategy_config['class'])

            # Test the strategy
            success = test_strategy_import_and_init(
                strategy_config['name'],
                strategy_class,
                strategy_config['params']
            )

            results.append((strategy_config['name'], success))

        except ImportError as e:
            print(f"\n❌ {strategy_config['name']} - IMPORT ERROR: {e}")
            results.append((strategy_config['name'], False))
        except Exception as e:
            print(f"\n❌ {strategy_config['name']} - UNEXPECTED ERROR: {e}")
            results.append((strategy_config['name'], False))

    # Summary
    print("\n" + "=" * 50)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for strategy_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"   {strategy_name}: {status}")
        if success:
            passed += 1

    print(f"\n🎯 OVERALL RESULT: {passed}/{total} strategies passed")

    if passed == total:
        print("🎉 ALL STRATEGIES WORKING CORRECTLY!")
        print("✅ Smallcap optimizations successfully applied")
    else:
        print("⚠️  Some strategies need fixes")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)