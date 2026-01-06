#!/usr/bin/env python3
"""
Test Volatility Filter for EMA Trailing Stop
This test specifically validates the lateral movement detection feature.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.stop_loss_manager import create_stop_params_from_config, get_stop_loss_manager
from core.stop_loss_manager import VolatilityFilter  # Import the class directly
from core.interfaces import MarketData
from datetime import datetime, timezone

def test_volatility_filter_standalone():
    """Test 1: Test the volatility filter in isolation"""
    print("🧪 TEST 1: Volatility Filter Standalone")
    
    volatility_filter = VolatilityFilter(lookback_periods=10)
    
    # Simulate lateral movement: small ranges, low momentum
    lateral_bars = [
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.02, 9.98, 10.01, 5000),  # 0.4% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.03, 9.99, 10.00, 4800),  # 0.4% range  
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.01, 9.99, 10.01, 4500),  # 0.2% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.02, 9.99, 10.00, 4200),  # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.02, 9.98, 10.02, 3900),  # 0.4% range
        MarketData("TEST", datetime.now(timezone.utc), 10.02, 10.03, 10.00, 10.01, 3800),  # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.02, 9.99, 10.00, 3600),  # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.01, 9.98, 9.99, 3500),   # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 9.99, 10.01, 9.98, 10.01, 3200),   # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.02, 9.99, 10.00, 3000),  # 0.3% range
    ]
    
    for bar in lateral_bars:
        volatility_filter.add_bar(bar)
    
    # Test lateral detection
    is_lateral, analysis = volatility_filter.is_lateral_movement()
    
    print(f"   📊 Lateral Movement Detected: {is_lateral}")
    print(f"   📋 Analysis: {analysis}")
    
    if is_lateral:
        print("   ✅ Lateral movement correctly detected")
        return True
    else:
        print("   ❌ Failed to detect lateral movement")
        return False

def test_volatility_filter_with_ema_trailing():
    """Test 2: Test EMA trailing with volatility filter during lateral movement"""
    print("\n🧪 TEST 2: EMA Trailing with Volatility Filter")
    
    stop_manager = get_stop_loss_manager()
    stop_manager.clear_all_positions()
    
    # Configure EMA trailing with volatility filter
    config_override = {
        'enable_dynamic_ema_trailing': True,
        'ema_trailing_periods': 6,
        'ema_trailing_activation_profit_pct': 0.02,  # 2% activation
        'enable_fixed_stops_fallback': False
    }
    
    stop_params = create_stop_params_from_config(config_override)
    
    # Register position
    symbol = "LATERAL_TEST"
    entry_price = 10.00
    entry_time = datetime.now(timezone.utc)
    
    stop_manager.register_position(
        symbol=symbol,
        entry_price=entry_price,
        entry_time=entry_time,
        side='bullish',
        strategy_name='lateral_test',
        stop_params=stop_params
    )
    
    print(f"   📊 Position registered: {symbol} @ ${entry_price}")
    
    # Phase 1: Move up to activate EMA trailing
    activation_sequence = [
        (10.05, "Move up 0.5%"),
        (10.15, "Move up 1.5%"), 
        (10.25, "Move up 2.5% - SHOULD ACTIVATE EMA")
    ]
    
    for price, description in activation_sequence:
        test_bar = MarketData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            open=price, high=price, low=price, close=price,
            volume=10000
        )
        
        exit_signal = stop_manager.check_exit_conditions(symbol, test_bar)
        profit_pct = (price - entry_price) / entry_price
        print(f"   💹 ${price:.2f} ({profit_pct:+.1%}) - {description}")
        
        if exit_signal:
            print("   ⚠️ Unexpected exit during activation phase")
    
    # Phase 2: Lateral movement (small ranges, low momentum)
    print(f"\n   🔄 Testing lateral movement phase...")
    lateral_sequence = [
        (10.26, 10.27, 10.24, 10.25, 3000, "Lateral bar 1"),
        (10.25, 10.26, 10.23, 10.24, 2800, "Lateral bar 2"),
        (10.24, 10.25, 10.22, 10.23, 2500, "Lateral bar 3"),
        (10.23, 10.24, 10.21, 10.22, 2300, "Lateral bar 4 - price below EMA but LATERAL"),
        (10.22, 10.23, 10.20, 10.21, 2100, "Lateral bar 5 - further below EMA but LATERAL"),
        (10.21, 10.22, 10.19, 10.20, 1900, "Lateral bar 6 - well below EMA but LATERAL")
    ]
    
    exit_during_lateral = False
    for open_p, high_p, low_p, close_p, volume, description in lateral_sequence:
        test_bar = MarketData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            open=open_p, high=high_p, low=low_p, close=close_p,
            volume=volume
        )
        
        exit_signal = stop_manager.check_exit_conditions(symbol, test_bar)
        profit_pct = (close_p - entry_price) / entry_price
        print(f"   📊 ${close_p:.2f} ({profit_pct:+.1%}) - {description}")
        
        if exit_signal:
            exit_during_lateral = True
            print(f"      🚨 EXIT during lateral: {exit_signal.metadata.get('exit_reason')}")
            break
    
    if not exit_during_lateral:
        print("   ✅ No exit during lateral movement - volatility filter working!")
        
        # Phase 3: Now test with real volatility (should trigger exit)
        print(f"\n   🔥 Testing high volatility phase (should trigger exit)...")
        high_vol_bar = MarketData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            open=10.20, high=10.30, low=10.15, close=10.16,  # Large range: 1.5%
            volume=15000  # High volume
        )
        
        exit_signal = stop_manager.check_exit_conditions(symbol, high_vol_bar)
        if exit_signal:
            print(f"      🚨 EXIT after volatility returned: {exit_signal.metadata.get('exit_reason')}")
            print("   ✅ EMA trailing resumed and triggered correctly!")
            return True
        else:
            print("   ⚠️ Expected exit after volatility returned but didn't happen")
            return False
    else:
        print("   ❌ Exit occurred during lateral movement - filter not working")
        return False

def test_volatile_vs_lateral_comparison():
    """Test 3: Compare behavior between volatile and lateral market conditions"""
    print("\n🧪 TEST 3: Volatile vs Lateral Comparison")
    
    volatility_filter = VolatilityFilter(lookback_periods=8)
    
    # Test volatile market first
    print("   📊 Testing VOLATILE market conditions:")
    volatile_bars = [
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.15, 9.85, 10.08, 15000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.08, 10.25, 9.95, 10.20, 18000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.20, 10.35, 10.05, 10.12, 16000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.12, 10.28, 9.98, 10.25, 14000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.25, 10.40, 10.10, 10.35, 17000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.35, 10.50, 10.20, 10.28, 19000),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.28, 10.45, 10.15, 10.18, 15500),  # 3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.18, 10.30, 10.00, 10.22, 16500),  # 3% range
    ]
    
    for bar in volatile_bars:
        volatility_filter.add_bar(bar)
    
    is_lateral_volatile, analysis_volatile = volatility_filter.is_lateral_movement()
    print(f"      Volatile market detected as lateral: {is_lateral_volatile}")
    print(f"      Analysis: Range: {analysis_volatile.get('avg_range_pct', 0):.3f}, "
          f"Volume: {analysis_volatile.get('volume_ratio', 0):.2f}, "
          f"Momentum: {analysis_volatile.get('price_momentum_pct', 0):.3f}")
    
    # Reset and test lateral market
    print("\n   📊 Testing LATERAL market conditions:")
    volatility_filter = VolatilityFilter(lookback_periods=8)
    lateral_bars = [
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.02, 9.98, 10.01, 3000),   # 0.4% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.03, 9.99, 10.00, 2800),   # 0.4% range
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.01, 9.99, 10.01, 2500),   # 0.2% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.02, 9.99, 10.00, 2300),   # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.02, 9.98, 10.02, 2100),   # 0.4% range
        MarketData("TEST", datetime.now(timezone.utc), 10.02, 10.03, 10.00, 10.01, 1900),  # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.01, 10.02, 9.99, 10.00, 1800),   # 0.3% range
        MarketData("TEST", datetime.now(timezone.utc), 10.00, 10.01, 9.98, 9.99, 1700),    # 0.3% range
    ]
    
    for bar in lateral_bars:
        volatility_filter.add_bar(bar)
    
    is_lateral_lateral, analysis_lateral = volatility_filter.is_lateral_movement()
    print(f"      Lateral market detected as lateral: {is_lateral_lateral}")
    print(f"      Analysis: Range: {analysis_lateral.get('avg_range_pct', 0):.3f}, "
          f"Volume: {analysis_lateral.get('volume_ratio', 0):.2f}, "
          f"Momentum: {analysis_lateral.get('price_momentum_pct', 0):.3f}")
    
    # Evaluation
    if not is_lateral_volatile and is_lateral_lateral:
        print("   ✅ Volatility filter correctly distinguishes volatile vs lateral markets!")
        return True
    else:
        print("   ❌ Volatility filter failed to distinguish market conditions")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO TESTS DEL FILTRO DE VOLATILIDAD")
    print("=" * 60)
    
    try:
        test_1 = test_volatility_filter_standalone()
        test_2 = test_volatility_filter_with_ema_trailing()
        test_3 = test_volatile_vs_lateral_comparison()
        
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE TESTS:")
        print(f"{'✅' if test_1 else '❌'} Test 1: Volatility Filter Standalone - {'PASSED' if test_1 else 'FAILED'}")
        print(f"{'✅' if test_2 else '❌'} Test 2: EMA + Volatility Filter - {'PASSED' if test_2 else 'FAILED'}")
        print(f"{'✅' if test_3 else '❌'} Test 3: Market Condition Detection - {'PASSED' if test_3 else 'FAILED'}")
        
        if all([test_1, test_2, test_3]):
            print("\n🎉 TODOS LOS TESTS DEL FILTRO DE VOLATILIDAD PASARON")
            print("📋 El filtro de volatilidad está funcionando correctamente")
            print("💡 Ahora EMA trailing se pausa durante movimientos laterales")
        else:
            print("\n⚠️ ALGUNOS TESTS FALLARON - Revisar implementación del filtro")
            
    except Exception as e:
        print(f"\n❌ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()