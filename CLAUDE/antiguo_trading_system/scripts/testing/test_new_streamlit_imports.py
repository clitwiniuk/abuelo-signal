#!/usr/bin/env python3
"""
Test del nuevo sistema de imports robustos de Streamlit
"""

import sys
from pathlib import Path
import configparser
import traceback

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("🔄 TESTING NEW ROBUST STREAMLIT IMPORTS...")
print("=" * 60)

# Step 1: Import core modules first (most critical)
try:
    from core.interfaces import TradingConfig
    from strategies import register_strategy, list_strategies
    print("✅ Core modules imported successfully")
    core_success = True
except ImportError as e:
    print(f"❌ Error importing critical modules: {e}")
    core_success = False

if not core_success:
    print("💀 CRITICAL FAILURE - Cannot continue")
    sys.exit(1)

# Step 2: Import strategies (less critical - can work without some)
try:
    from strategies.macdv_strategy import MACDVStrategy
    from strategies.gap_go_strategy import GapGoStrategy  
    from strategies.orb_strategy import ORBStrategy
    from strategies.volume_momentum_strategy import VolumeMomentumStrategy
    from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
    from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    print("✅ Individual strategies imported successfully")
    strategies_success = True
except ImportError as e:
    print(f"⚠️ Warning importing individual strategies: {e}")
    strategies_success = False

# Step 3: Import main module (optional - only needed for full system)
TradingSystemManager = None
try:
    from main import TradingSystemManager
    print("✅ TradingSystemManager imported successfully")
    main_success = True
except ImportError as e:
    print(f"⚠️ TradingSystemManager not available (requires ib_insync): {e}")
    main_success = False

print("\n" + "=" * 60)
print("📊 IMPORT RESULTS:")
print(f"✅ Core modules: {'SUCCESS' if core_success else 'FAILED'}")
print(f"✅ Individual strategies: {'SUCCESS' if strategies_success else 'FAILED'}")
print(f"✅ TradingSystemManager: {'SUCCESS' if main_success else 'FAILED (expected)'}")

print("\n🎯 STRATEGY AVAILABILITY TEST:")
try:
    available_strategies = list_strategies()
    print(f"✅ Available strategies: {available_strategies}")
    print(f"✅ multi_strategy present: {'multi_strategy' in available_strategies}")
    
    if 'multi_strategy' in available_strategies:
        # Test configuration loading
        config_parser = configparser.ConfigParser()
        config_parser.read('config.ini')
        strategy_name = config_parser.get('TRADING', 'strategy', fallback='macdv')
        print(f"✅ Config strategy: {strategy_name}")
        
        # Simulate selectbox logic
        if 'multi_strategy' in available_strategies:
            available_strategies.remove('multi_strategy')
            available_strategies.insert(0, 'multi_strategy')
        
        default_index = 0
        if strategy_name in available_strategies:
            default_index = available_strategies.index(strategy_name)
        
        print(f"✅ Reordered strategies: {available_strategies}")
        print(f"✅ Default index: {default_index}")
        print(f"✅ Selected strategy: {available_strategies[default_index]}")
        
        if strategy_name == 'multi_strategy':
            print("✅ SHOULD show: 'Multi-strategy configurada por defecto'")
        
        print("\n🎉 STREAMLIT SHOULD NOW WORK WITH multi_strategy!")
        
    else:
        print("❌ multi_strategy NOT AVAILABLE")
        
except Exception as e:
    print(f"❌ Error testing strategies: {e}")
    traceback.print_exc()