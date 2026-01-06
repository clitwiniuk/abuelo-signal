#!/usr/bin/env python3
"""
Simple direct test of the auto-tune volatility propagation fix
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from strategies.multi_strategy_engine import MultiStrategyEngine
from strategies.macdv_strategy import MACDVStrategy

def test_volatility_propagation():
    """Test that volatility thresholds are properly propagated"""
    
    print("🔧 TESTING VOLATILITY THRESHOLD PROPAGATION")
    print("=" * 50)
    
    # Create engine (without full initialization)
    engine = MultiStrategyEngine()
    
    # Create MACDV strategy directly
    macdv = MACDVStrategy()
    
    # Add it to engine's strategies dict
    engine.strategies = {'macdv_smallcaps': macdv}
    
    # Check initial values
    initial_min_atr = macdv._parameters.get('min_atr_pct', 0.0)
    print(f"📊 Initial MACDV min_atr_pct: {initial_min_atr} ({initial_min_atr*100:.1f}%)")
    
    # Set engine's dynamic volatility values
    engine.dynamic_vol_min = 0.8  # 0.8%
    engine.dynamic_vol_max = 8.0  # 8.0%
    
    print(f"📊 Engine dynamic_vol_min: {engine.dynamic_vol_min}%")
    print(f"📊 Engine dynamic_vol_max: {engine.dynamic_vol_max}%")
    
    # Call the propagation method
    print("\n🔄 Calling _propagate_dynamic_thresholds()...")
    engine._propagate_dynamic_thresholds()
    
    # Check final values
    final_min_atr = macdv._parameters.get('min_atr_pct', 0.0)
    print(f"\n📈 RESULTS:")
    print(f"   Initial MACDV min_atr_pct: {initial_min_atr} ({initial_min_atr*100:.1f}%)")
    print(f"   Final MACDV min_atr_pct: {final_min_atr} ({final_min_atr*100:.1f}%)")
    print(f"   Expected: {engine.dynamic_vol_min/100} ({engine.dynamic_vol_min}%)")
    
    # Test the fix
    expected_value = engine.dynamic_vol_min / 100  # Convert 0.8% to 0.008
    if abs(final_min_atr - expected_value) < 0.0001:
        print("✅ SUCCESS: Volatility threshold propagation is working!")
        print(f"   The MACDV strategy will now accept volatility as low as {final_min_atr*100:.1f}%")
        return True
    else:
        print("❌ FAILED: Volatility threshold was not updated correctly")
        print(f"   Expected: {expected_value} ({expected_value*100:.1f}%)")
        print(f"   Got: {final_min_atr} ({final_min_atr*100:.1f}%)")
        return False

if __name__ == "__main__":
    success = test_volatility_propagation()
    if success:
        print("\n🎉 The auto-tune fix should now allow trades when volatility is 0.8%!")
        print("   Previously it required 1.0%, now it will reduce to 0.8% or lower.")
    else:
        print("\n⚠️  The fix needs more work.")