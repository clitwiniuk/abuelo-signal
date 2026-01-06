#!/usr/bin/env python3
"""
Test específico de los imports que usa Streamlit
"""

import sys
from pathlib import Path
import traceback

# Simular path de Streamlit
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

print("🧪 TESTING STREAMLIT IMPORTS...")
print("=" * 50)

try:
    print("1️⃣ Testing TradingConfig...")
    from core.interfaces import TradingConfig
    print("✅ TradingConfig OK")
    
    print("2️⃣ Testing strategies module...")
    from strategies import register_strategy, list_strategies
    available_strategies = list_strategies()
    print(f"✅ strategies OK: {available_strategies}")
    print(f"✅ multi_strategy presente: {'multi_strategy' in available_strategies}")
    
    print("3️⃣ Testing individual strategies...")
    from strategies.macdv_strategy import MACDVStrategy
    print("✅ MACDVStrategy OK")
    
    from strategies.gap_go_strategy import GapGoStrategy
    print("✅ GapGoStrategy OK")
    
    from strategies.orb_strategy import ORBStrategy
    print("✅ ORBStrategy OK")
    
    from strategies.volume_momentum_strategy import VolumeMomentumStrategy
    print("✅ VolumeMomentumStrategy OK")
    
    from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
    print("✅ OptimizedGapGoStrategy OK")
    
    from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
    print("✅ VolumeBreakoutStrategy OK")
    
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    print("✅ VWAPSmallcapsStrategy OK")
    
    print("4️⃣ Testing main.py (THIS MIGHT FAIL)...")
    try:
        from main import TradingSystemManager
        print("✅ TradingSystemManager OK")
    except Exception as e:
        print(f"❌ TradingSystemManager FAILED: {e}")
        print("🔧 This is likely the problem!")
        
    print("\n" + "=" * 50)
    print("🎯 RESULTADO:")
    if 'multi_strategy' in available_strategies:
        print("✅ multi_strategy ESTÁ DISPONIBLE")
        print("✅ El problema NO es con multi_strategy")
        print("❓ El problema puede ser con otro import o con Streamlit mismo")
    else:
        print("❌ multi_strategy NO DISPONIBLE")
        
except Exception as e:
    print(f"❌ ERROR CRÍTICO: {e}")
    traceback.print_exc()