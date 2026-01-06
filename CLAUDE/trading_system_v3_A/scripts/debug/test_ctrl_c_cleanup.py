#!/usr/bin/env python3
"""
Test específico para Ctrl+C cleanup
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# Add the project root to Python path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

from main import TradingSystemManager
from core.interfaces import TradingConfig

def test_ctrl_c_cleanup():
    """Test Ctrl+C cleanup behavior"""
    
    print("🧪 TESTING: Ctrl+C Cleanup Behavior")
    print("="*60)
    
    # Create config
    config = TradingConfig(
        strategy_name='macdv',
        broker_host='127.0.0.1',
        broker_port=7497,
        broker_client_id=1
    )
    
    print("🏗️ Creating TradingSystemManager...")
    system = TradingSystemManager(config, in_streamlit=False)
    
    print(f"✅ System created with enhanced cleanup")
    print(f"   Signal handlers: {'✅ Configured' if hasattr(system, '_setup_signal_handlers') else '❌ Missing'}")
    print(f"   Enhanced cleanup: {'✅ Active' if system.cleanup_registered else '❌ Missing'}")
    
    print(f"\n🎯 **PRESS Ctrl+C TO TEST SIGNAL HANDLING**")
    print(f"   Expected behavior:")
    print(f"   1. 👋 Signal SIGINT message")
    print(f"   2. 🚨 Emergency cleanup activation")
    print(f"   3. 🛑 Trading engine stop (if running)")
    print(f"   4. ✅ Clean exit")
    
    print(f"\n⏰ Waiting for Ctrl+C... (or auto-exit in 30 seconds)")
    
    try:
        # Simulate a long-running process
        for i in range(30):
            print(f"   Working... {i+1}/30 seconds (Press Ctrl+C anytime)", end='\r')
            time.sleep(1)
        
        print(f"\n⏰ 30 seconds elapsed - exiting normally")
        print(f"   (atexit cleanup should still run)")
        
    except KeyboardInterrupt:
        print(f"\n✅ KeyboardInterrupt caught in Python!")
        print(f"   This means Ctrl+C was pressed")
        print(f"   Signal handlers should have run before this")
        
    return True

if __name__ == "__main__":
    test_ctrl_c_cleanup()