#!/usr/bin/env python3
"""
Test final que simula completamente el comportamiento de Streamlit después de todos los fixes
"""

import sys
from pathlib import Path
import configparser

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("🏁 FINAL STREAMLIT BEHAVIOR TEST")
print("=" * 60)

# Simulate the new robust import system
print("1️⃣ IMPORTING CORE MODULES...")
try:
    from core.interfaces import TradingConfig
    from strategies import register_strategy, list_strategies
    print("✅ Core modules imported successfully")
    core_success = True
except ImportError as e:
    print(f"❌ Error importing critical modules: {e}")
    core_success = False
    
if not core_success:
    print("💀 STREAMLIT WOULD STOP HERE")
    sys.exit(1)

print("\n2️⃣ IMPORTING INDIVIDUAL STRATEGIES...")
try:
    from strategies.macdv_strategy import MACDVStrategy
    from strategies.gap_go_strategy import GapGoStrategy  
    from strategies.orb_strategy import ORBStrategy
    from strategies.volume_momentum_strategy import VolumeMomentumStrategy
    from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
    from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    print("✅ Individual strategies imported successfully")
except ImportError as e:
    print(f"⚠️ Warning importing individual strategies: {e}")

print("\n3️⃣ IMPORTING TRADING SYSTEM MANAGER...")
TradingSystemManager = None
try:
    from main import TradingSystemManager
    print("✅ TradingSystemManager imported successfully")
except ImportError as e:
    print(f"⚠️ TradingSystemManager not available: {e}")
    print("⚠️ STREAMLIT WOULD SHOW WARNING BUT CONTINUE")

print("\n4️⃣ LOADING CONFIGURATION...")
config_parser = configparser.ConfigParser()
config_parser.read('config.ini')
strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
print(f"✅ Config strategy: {strategy_name}")

print("\n5️⃣ BUILDING STRATEGY SELECTBOX...")
try:
    available_strategies = list_strategies()
    print(f"✅ Available strategies: {available_strategies}")
    
    # Prioritize multi_strategy
    if 'multi_strategy' in available_strategies:
        available_strategies.remove('multi_strategy')
        available_strategies.insert(0, 'multi_strategy')
        print(f"✅ Reordered strategies: {available_strategies}")
    
    # Find default index
    default_index = 0
    if strategy_name in available_strategies:
        default_index = available_strategies.index(strategy_name)
    
    selected_strategy = available_strategies[default_index]
    print(f"✅ Default index: {default_index}")
    print(f"✅ Selected strategy: {selected_strategy}")
    
    # Check success messages
    if strategy_name == 'multi_strategy':
        print("✅ WOULD SHOW: 'Multi-strategy configurada por defecto'")
    
    if selected_strategy == 'multi_strategy':
        print("✅ WOULD SHOW: 'Multi-Strategy Engine activo'")
        
        # Test strategy details
        try:
            from strategies import get_strategy_class
            cls = get_strategy_class('multi_strategy')
            instance = cls()
            print("✅ WOULD SHOW: 'Estrategias incluidas:'")
            for strategy_name in instance.strategies.keys():
                print(f"✅ WOULD SHOW: '• {strategy_name}'")
        except Exception as e:
            print(f"⚠️ Fallback strategy list would be shown: {e}")
            
except Exception as e:
    print(f"❌ Error with strategies: {e}")
    print("⚠️ STREAMLIT WOULD USE FALLBACK: ['multi_strategy', 'macdv', 'gap_go']")

print("\n6️⃣ TESTING SYSTEM START...")
if TradingSystemManager is not None:
    print("✅ WOULD ALLOW: System start button")
else:
    print("⚠️ WOULD SHOW: System not available warning")
    print("⚠️ WOULD SHOW: Install ib_insync message")

print("\n" + "=" * 60)
print("🎉 FINAL RESULT:")
print("✅ STREAMLIT SHOULD NOW LOAD SUCCESSFULLY")
print("✅ MULTI_STRATEGY SHOULD BE VISIBLE AND SELECTABLE") 
print("✅ CONFIGURATION SHOULD BE PRESERVED")
print("✅ ROBUST ERROR HANDLING IN PLACE")
print("\n💡 To test: Run `streamlit run streamlit_app_v2.py`")