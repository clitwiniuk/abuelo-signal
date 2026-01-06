#!/usr/bin/env python3
"""
Test específico para el error de position_check en MACDVStrategy
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from strategies.macdv_strategy import MACDVStrategy
from core.interfaces import MarketData
from datetime import datetime, timezone

print("🔧 TESTING MACDV POSITION_CHECK ERROR...")
print("=" * 50)

try:
    # 1. Create MACDV strategy instance
    print("1️⃣ Creating MACDVStrategy instance...")
    strategy = MACDVStrategy({
        'allow_pyramiding': False,
        'max_pyramid_levels': 2,
        'min_price': 1.0,
        'max_price': 25.0
    })
    print(f"✅ Strategy created: {strategy.name}")
    
    # 2. Test if method exists
    print("\n2️⃣ Checking _can_open_new_position method...")
    has_method = hasattr(strategy, '_can_open_new_position')
    print(f"Method exists: {has_method}")
    
    if has_method:
        print("✅ Method found in strategy")
        
        # 3. Test method call
        print("\n3️⃣ Testing method call...")
        result = strategy._can_open_new_position('TEST', 10.0, 'long')
        print(f"✅ Method call successful: {result}")
    else:
        print("❌ Method NOT found - checking inheritance")
        print(f"MRO: {[cls.__name__ for cls in MACDVStrategy.__mro__]}")
    
    # 4. Create fake market data and test the problematic code path
    print("\n4️⃣ Testing with fake market data...")
    
    # Initialize strategy attributes that might be missing
    strategy.bars_history = {'FDMT': []}
    strategy.last_macd_values = {}
    strategy.entry_signals = {}
    strategy.positions = {}
    
    # Create fake market data
    fake_bar = MarketData(
        symbol='FDMT',
        timestamp=datetime.now(timezone.utc),
        open=10.0,
        high=10.5,
        low=9.8,
        close=10.2,
        volume=100000
    )
    
    # Add some history
    for i in range(50):
        bar = MarketData(
            symbol='FDMT',
            timestamp=datetime.now(timezone.utc),
            open=10.0 + i * 0.01,
            high=10.5 + i * 0.01,
            low=9.8 + i * 0.01,
            close=10.2 + i * 0.01,
            volume=100000
        )
        strategy.bars_history['FDMT'].append(bar)
    
    print("✅ Fake data prepared")
    
    # 5. Test the exact line that's failing
    print("\n5️⃣ Testing exact failing line...")
    symbol = 'FDMT'
    current_price = 10.2
    
    try:
        position_check = strategy._can_open_new_position(symbol, current_price, 'long')
        print(f"✅ position_check successful: {position_check}")
    except Exception as e:
        print(f"❌ position_check FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🎯 CONCLUSION:")
    print("If we reach here without errors, the problem is not with the method itself,")
    print("but possibly with the execution context or strategy initialization.")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()