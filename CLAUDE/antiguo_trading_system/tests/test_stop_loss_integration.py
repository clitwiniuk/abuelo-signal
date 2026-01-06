#!/usr/bin/env python3
"""
Test StopLoss Integration - Verificar que el sistema usa config.ini correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.stop_loss_manager import create_stop_params_from_config, get_stop_loss_manager
from core.interfaces import MarketData, Position, SignalType
from datetime import datetime, timezone
import configparser

def test_config_integration():
    """Test 1: Verificar que create_stop_params_from_config lee config.ini"""
    print("🧪 TEST 1: Verificando integración con config.ini")
    
    # Read config.ini directly
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    expected_stop_loss = config.getfloat('GLOBAL', 'fallback_stop_loss_pct', fallback=0.06)
    expected_take_profit = config.getfloat('GLOBAL', 'fallback_take_profit_pct', fallback=0.12)
    expected_trailing_activation = config.getfloat('GLOBAL', 'default_trailing_activation', fallback=0.03)
    expected_trailing_distance = config.getfloat('GLOBAL', 'default_trailing_stop_pct', fallback=0.06)
    
    print(f"   📋 Valores esperados desde config.ini:")
    print(f"      Stop Loss: {expected_stop_loss:.2%}")
    print(f"      Take Profit: {expected_take_profit:.2%}")
    print(f"      Trailing Activation: {expected_trailing_activation:.2%}")
    print(f"      Trailing Distance: {expected_trailing_distance:.2%}")
    
    # Create stop params with empty config (should use fallbacks)
    stop_params = create_stop_params_from_config({})
    
    print(f"   🔍 Valores obtenidos del StopLossManager:")
    print(f"      Stop Loss: {stop_params.stop_loss_pct:.2%}")
    print(f"      Take Profit: {stop_params.profit_target:.2%}")
    print(f"      Trailing Activation: {stop_params.trailing_stop_activation:.2%}")
    print(f"      Trailing Distance: {stop_params.trailing_stop_distance:.2%}")
    
    # Verify values match
    assert abs(stop_params.stop_loss_pct - expected_stop_loss) < 0.001, f"Stop loss mismatch: {stop_params.stop_loss_pct} != {expected_stop_loss}"
    assert abs(stop_params.profit_target - expected_take_profit) < 0.001, f"Take profit mismatch: {stop_params.profit_target} != {expected_take_profit}"
    assert abs(stop_params.trailing_stop_activation - expected_trailing_activation) < 0.001, f"Trailing activation mismatch"
    assert abs(stop_params.trailing_stop_distance - expected_trailing_distance) < 0.001, f"Trailing distance mismatch"
    
    print("   ✅ Test 1 PASSED: StopLossManager lee correctamente config.ini")

def test_stop_loss_functionality():
    """Test 2: Verificar funcionalidad básica de stop loss"""
    print("\n🧪 TEST 2: Verificando funcionalidad de Stop Loss")
    
    stop_manager = get_stop_loss_manager()
    
    # Clear any existing positions
    stop_manager.clear_all_positions()
    
    # Create stop params from config
    stop_params = create_stop_params_from_config({})
    
    # Register a test position
    symbol = "TEST"
    entry_price = 10.00
    entry_time = datetime.now(timezone.utc)
    
    stop_manager.register_position(
        symbol=symbol,
        entry_price=entry_price,
        entry_time=entry_time,
        side='bullish',
        strategy_name='test_strategy',
        stop_params=stop_params
    )
    
    print(f"   📊 Position registered: {symbol} @ ${entry_price}")
    print(f"      Stop Loss at: ${entry_price * (1 - stop_params.stop_loss_pct):.2f} ({-stop_params.stop_loss_pct:.1%})")
    print(f"      Take Profit at: ${entry_price * (1 + stop_params.profit_target):.2f} ({stop_params.profit_target:.1%})")
    
    # Test stop loss trigger
    stop_loss_price = entry_price * (1 - stop_params.stop_loss_pct - 0.001)  # Slightly below stop
    test_bar = MarketData(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        open=stop_loss_price,
        high=stop_loss_price,
        low=stop_loss_price,
        close=stop_loss_price,
        volume=10000
    )
    
    exit_signal = stop_manager.check_exit_conditions(symbol, test_bar)
    
    if exit_signal:
        print(f"   🛑 Stop Loss triggered at ${stop_loss_price:.2f}")
        print(f"      Exit reason: {exit_signal.metadata.get('exit_reason', 'Unknown')}")
        print("   ✅ Test 2 PASSED: Stop Loss funciona correctamente")
    else:
        print("   ❌ Test 2 FAILED: Stop Loss no se activó")
        return False
    
    return True

def test_take_profit_functionality():
    """Test 3: Verificar funcionalidad de take profit"""
    print("\n🧪 TEST 3: Verificando funcionalidad de Take Profit")
    
    stop_manager = get_stop_loss_manager()
    stop_manager.clear_all_positions()
    
    stop_params = create_stop_params_from_config({})
    
    # Register another test position
    symbol = "TEST2"
    entry_price = 10.00
    entry_time = datetime.now(timezone.utc)
    
    stop_manager.register_position(
        symbol=symbol,
        entry_price=entry_price,
        entry_time=entry_time,
        side='bullish',
        strategy_name='test_strategy',
        stop_params=stop_params
    )
    
    # Test take profit trigger
    take_profit_price = entry_price * (1 + stop_params.profit_target + 0.001)  # Slightly above target
    test_bar = MarketData(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        open=take_profit_price,
        high=take_profit_price,
        low=take_profit_price,
        close=take_profit_price,
        volume=10000
    )
    
    exit_signal = stop_manager.check_exit_conditions(symbol, test_bar)
    
    if exit_signal:
        print(f"   🎯 Take Profit triggered at ${take_profit_price:.2f}")
        print(f"      Exit reason: {exit_signal.metadata.get('exit_reason', 'Unknown')}")
        print("   ✅ Test 3 PASSED: Take Profit funciona correctamente")
        return True
    else:
        print("   ❌ Test 3 FAILED: Take Profit no se activó")
        return False

def test_end_of_day_exit():
    """Test 4: Verificar exit al final del día"""
    print("\n🧪 TEST 4: Verificando End of Day Exit")
    
    # Check if end_of_day_exit is enabled in config
    stop_params = create_stop_params_from_config({})
    print(f"   ⏰ End of day exit enabled: {stop_params.end_of_day_exit}")
    print(f"   ⏰ Max hold minutes: {stop_params.max_hold_minutes}")
    
    if stop_params.end_of_day_exit:
        print("   ✅ Test 4 PASSED: End of Day Exit está habilitado")
        return True
    else:
        print("   ❌ Test 4 FAILED: End of Day Exit está deshabilitado")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO TESTS DEL SISTEMA DE STOP LOSS")
    print("=" * 50)
    
    try:
        # Run all tests
        test_config_integration()
        
        test_2_passed = test_stop_loss_functionality()
        test_3_passed = test_take_profit_functionality()
        test_4_passed = test_end_of_day_exit()
        
        print("\n" + "=" * 50)
        print("📊 RESUMEN DE TESTS:")
        print("✅ Test 1: Integración config.ini - PASSED")
        print(f"{'✅' if test_2_passed else '❌'} Test 2: Stop Loss - {'PASSED' if test_2_passed else 'FAILED'}")
        print(f"{'✅' if test_3_passed else '❌'} Test 3: Take Profit - {'PASSED' if test_3_passed else 'FAILED'}")
        print(f"{'✅' if test_4_passed else '❌'} Test 4: End of Day Exit - {'PASSED' if test_4_passed else 'FAILED'}")
        
        if all([test_2_passed, test_3_passed, test_4_passed]):
            print("\n🎉 TODOS LOS TESTS PASSED - Sistema funcionando correctamente")
        else:
            print("\n⚠️ ALGUNOS TESTS FALLARON - Revisar configuración")
            
    except Exception as e:
        print(f"\n❌ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()