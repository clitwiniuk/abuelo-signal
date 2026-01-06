#!/usr/bin/env python3
"""
Test script for the new thread-safe IBKR adapter
"""

import asyncio
import logging
from adapters.thread_safe_ibkr_adapter import ThreadSafeIBKRAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_adapter():
    """Test the thread-safe adapter"""
    print("Testing Thread-Safe IBKR Adapter...")
    
    # Create adapter
    adapter = ThreadSafeIBKRAdapter(
        host="127.0.0.1",
        port=7497,
        client_id=9999  # Test client ID
    )
    
    try:
        # Test connection
        print("1. Testing connection...")
        connected = await adapter.connect()
        print(f"   Connected: {connected}")
        
        if connected:
            # Test is_connected
            print("2. Testing is_connected...")
            is_conn = adapter.is_connected()
            print(f"   Is connected: {is_conn}")
            
            # Test get_bars
            print("3. Testing get_bars...")
            bars = await adapter.get_bars("AAPL", "1 min", 5)
            print(f"   Got {len(bars)} bars for AAPL")
            
            # Test get_current_price
            print("4. Testing get_current_price...")
            price = await adapter.get_current_price("AAPL")
            print(f"   AAPL price: ${price}")
            
            # Test get_positions
            print("5. Testing get_positions...")
            positions = await adapter.get_positions()
            print(f"   Got {len(positions)} positions")
            
        # Test disconnect
        print("6. Testing disconnect...")
        await adapter.disconnect()
        print("   Disconnected")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_adapter())