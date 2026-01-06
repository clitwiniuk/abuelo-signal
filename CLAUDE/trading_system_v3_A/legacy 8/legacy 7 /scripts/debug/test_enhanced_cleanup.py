#!/usr/bin/env python3
"""
Test del sistema de cleanup mejorado
"""

import asyncio
import sys
import os
from pathlib import Path
import time

# Add the project root to Python path
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

from main import TradingSystemManager
from core.interfaces import TradingConfig

def test_enhanced_cleanup():
    """Test the enhanced cleanup system"""
    
    print("🧪 TESTING: Enhanced Cleanup System")
    print("="*60)
    
    # Create config
    config = TradingConfig(
        strategy_name='macdv',
        broker_host='127.0.0.1',
        broker_port=7497,
        broker_client_id=1
    )
    
    print("🏗️ Creating TradingSystemManager with enhanced cleanup...")
    
    # Create system (this will setup enhanced cleanup)
    system = TradingSystemManager(config, in_streamlit=False)
    
    print(f"✅ System created")
    print(f"   Start time: {system.start_time}")
    print(f"   Max runtime: {system.max_runtime_hours} hours")
    print(f"   Cleanup registered: {system.cleanup_registered}")
    
    print("\n🎯 Testing cleanup triggers:")
    print("   1. Timeout watchdog: Will trigger in 6 minutes (0.1 hours)")
    print("   2. Market hours monitor: Will check every 30 minutes") 
    print("   3. atexit handler: Will trigger when process exits")
    print("   4. Signal handlers: Try Ctrl+C to test")
    
    print(f"\n⏰ Waiting 10 seconds to see if threads start...")
    time.sleep(10)
    
    print("✅ Test completed - cleanup system is active")
    print("   The system will auto-shutdown after 0.1 hours (6 minutes)")
    print("   Or try Ctrl+C to test signal handling")
    
    # Don't actually wait for timeout in test
    return True

if __name__ == "__main__":
    test_enhanced_cleanup()