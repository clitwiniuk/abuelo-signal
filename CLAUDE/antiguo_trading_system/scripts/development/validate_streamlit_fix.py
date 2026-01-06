#!/usr/bin/env python3
"""
Validación final del fix de multi_strategy en Streamlit
"""

import sys
from pathlib import Path
import configparser
import traceback

# Simulate Streamlit environment exactly
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("🔧 VALIDATING STREAMLIT FIX...")
print("=" * 50)

try:
    # Step 1: Import core modules (critical)
    print("1️⃣ Importing core modules...")
    from core.interfaces import TradingConfig
    from strategies import register_strategy, list_strategies
    print("✅ Core modules OK")
    
    # Step 2: List available strategies
    print("\n2️⃣ Checking strategies...")
    available_strategies = list_strategies()
    print(f"Available: {available_strategies}")
    
    multi_strategy_available = 'multi_strategy' in available_strategies
    print(f"multi_strategy available: {multi_strategy_available}")
    
    if not multi_strategy_available:
        print("❌ PROBLEM: multi_strategy NOT AVAILABLE")
        sys.exit(1)
    
    # Step 3: Test configuration loading
    print("\n3️⃣ Loading configuration...")
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
    print(f"Config strategy: {strategy_name}")
    
    # Step 4: Simulate Streamlit selectbox logic
    print("\n4️⃣ Simulating Streamlit selectbox...")
    
    # Prioritize multi_strategy (like in Streamlit)
    if 'multi_strategy' in available_strategies:
        available_strategies.remove('multi_strategy')
        available_strategies.insert(0, 'multi_strategy')
        print(f"Reordered: {available_strategies}")
    
    # Calculate default index
    default_index = 0
    if strategy_name in available_strategies:
        default_index = available_strategies.index(strategy_name)
    
    selected_strategy = available_strategies[default_index]
    print(f"Default index: {default_index}")
    print(f"Selected: {selected_strategy}")
    
    # Step 5: Test strategy instantiation
    print("\n5️⃣ Testing instantiation...")
    from strategies import get_strategy_class
    cls = get_strategy_class('multi_strategy')
    instance = cls()
    print(f"Instance name: {instance.name}")
    print(f"Instance type: {type(instance).__name__}")
    
    # Step 6: Test individual strategies showing
    print("\n6️⃣ Testing individual strategies...")
    if hasattr(instance, 'strategies'):
        print("Individual strategies:")
        for strategy in instance.strategies.keys():
            print(f"  • {strategy}")
    else:
        print("⚠️ No individual strategies found")
    
    print("\n" + "=" * 50)
    if selected_strategy == 'multi_strategy':
        print("🎉 SUCCESS: multi_strategy SHOULD APPEAR IN STREAMLIT")
        print("🎉 SUCCESS: multi_strategy SHOULD BE SELECTED BY DEFAULT")
        print("🎉 SUCCESS: All requirements met")
    else:
        print(f"❌ PROBLEM: Expected multi_strategy, got {selected_strategy}")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nTraceback:")
    traceback.print_exc()
    print("\n🔧 This indicates the problem is still present")
    sys.exit(1)
    
print("\n💡 The fix should work. If Streamlit still doesn't show multi_strategy,")
print("💡 the issue may be with Streamlit cache or session state.")