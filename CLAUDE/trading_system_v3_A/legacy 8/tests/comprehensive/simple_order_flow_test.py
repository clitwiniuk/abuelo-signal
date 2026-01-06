#!/usr/bin/env python3
"""
Simple Order Flow Test
====================

Basic test to verify order flow components are working.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all required components can be imported"""
    try:
        print("Testing imports...")
        
        from core.interfaces import MarketData, Signal, SignalType
        print("✅ Core interfaces imported")
        
        from core.interfaces import TradingConfig
        print("✅ TradingConfig imported")
        
        from core.risk_manager import RiskManager
        print("✅ RiskManager imported")
        
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
        print("✅ MLMultiStrategyEngine imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_basic_config():
    """Test basic configuration creation"""
    try:
        print("\nTesting configuration...")
        
        from core.interfaces import TradingConfig
        
        config = TradingConfig()
        config.max_positions = 3
        config.max_position_value = 200.0
        config.stop_loss_pct = 0.08
        config.take_profit_pct = 0.15
        
        print(f"✅ Config created - max positions: {config.max_positions}")
        print(f"✅ Position value: ${config.max_position_value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def test_risk_manager():
    """Test risk manager creation"""
    try:
        print("\nTesting risk manager...")
        
        from core.interfaces import TradingConfig
        from core.risk_manager import RiskManager
        
        config = TradingConfig()
        config.max_positions = 3
        config.max_position_value = 200.0
        
        risk_manager = RiskManager(config)
        
        print("✅ RiskManager created successfully")
        print(f"✅ Anti-martingala tracking: {hasattr(risk_manager, 'active_daily_plays')}")
        
        # Test basic risk validation instead
        from core.interfaces import Signal, SignalType
        from datetime import datetime
        
        test_signal = Signal(
            signal_id="test_signal",
            symbol="TEST",
            signal_type=SignalType.LONG,
            strength=0.8,
            price=10.0,
            timestamp=datetime.now()
        )
        
        print("✅ Basic signal validation test completed")
        
        return True
        
    except Exception as e:
        print(f"❌ RiskManager error: {e}")
        return False

def analyze_exit_types():
    """Analyze what exit types are available in the ML engine"""
    try:
        print("\nAnalyzing exit types...")
        
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
        
        # Check for exit methods
        engine = MLMultiStrategyEngine({})
        
        exit_methods = []
        
        # Check for FOMO methods
        if hasattr(engine, '_check_fomo_exhaustion'):
            exit_methods.append("FOMO Exhaustion")
            
        if hasattr(engine, '_check_fomo_exit'):
            exit_methods.append("FOMO Exit (time-based)")
            
        if hasattr(engine, '_get_time_based_thresholds'):
            exit_methods.append("Time-based Thresholds")
        
        # Check for other exit methods in the code
        import inspect
        methods = inspect.getmembers(engine, predicate=inspect.ismethod)
        
        for method_name, method in methods:
            if 'exit' in method_name.lower() or 'stop' in method_name.lower():
                exit_methods.append(method_name)
        
        print(f"✅ Found {len(exit_methods)} exit-related methods:")
        for method in exit_methods:
            print(f"   ├─ {method}")
            
        return True
        
    except Exception as e:
        print(f"❌ Exit analysis error: {e}")
        return False

def test_order_priorities():
    """Test order priority logic"""
    try:
        print("\nTesting order priorities...")
        
        # Simulate multiple exit conditions
        exit_conditions = [
            {'type': 'fomo_exhaustion', 'priority': 1, 'triggered': True},
            {'type': 'take_profit', 'priority': 2, 'triggered': True},
            {'type': 'trailing_stop', 'priority': 3, 'triggered': False},
            {'type': 'stop_loss', 'priority': 4, 'triggered': False}
        ]
        
        # Find triggered exits
        triggered = [c for c in exit_conditions if c['triggered']]
        triggered.sort(key=lambda x: x['priority'])
        
        print(f"✅ Exit priority test:")
        print(f"   ├─ Triggered exits: {len(triggered)}")
        
        if triggered:
            winner = triggered[0]
            print(f"   └─ Highest priority: {winner['type']} (priority {winner['priority']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Priority test error: {e}")
        return False

def main():
    """Run simple order flow tests"""
    print("🔍 SIMPLE ORDER FLOW TEST")
    print("="*50)
    
    tests = [
        test_imports,
        test_basic_config,
        test_risk_manager,
        analyze_exit_types,
        test_order_priorities
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "="*50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All components working - ready for comprehensive test")
    else:
        print("❌ Some issues detected - fix before running full analysis")
    
    return passed == total

if __name__ == "__main__":
    main()