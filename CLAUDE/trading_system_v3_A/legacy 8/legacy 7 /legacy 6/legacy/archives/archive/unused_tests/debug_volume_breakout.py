#!/usr/bin/env python3
"""
Debug VolumeBreakoutStrategy in isolation
"""

import asyncio
import traceback

def test_volume_breakout_creation():
    print("🔧 DEBUG VOLUME BREAKOUT STRATEGY CREATION")
    print("=" * 60)
    
    try:
        print("1. Importing strategy...")
        from strategies.volume_breakout_strategy import VolumeBreakoutStrategy
        print("   ✅ Import successful")
        
        print("2. Creating strategy instance with None parameters...")
        strategy = VolumeBreakoutStrategy(None)
        print("   ✅ Instance creation successful")
        
        print("3. Checking _parameters...")
        print(f"   _parameters type: {type(strategy._parameters)}")
        print(f"   _parameters is None: {strategy._parameters is None}")
        if strategy._parameters:
            print(f"   _parameters length: {len(strategy._parameters)}")
        
        print("4. Testing _initialize_strategy()...")
        asyncio.run(strategy._initialize_strategy())
        print("   ✅ _initialize_strategy() successful")
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"📍 Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    test_volume_breakout_creation()