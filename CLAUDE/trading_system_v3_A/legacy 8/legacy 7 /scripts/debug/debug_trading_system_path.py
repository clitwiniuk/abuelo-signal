#!/usr/bin/env python3
"""
Debug script that replicates exactly what the trading system does when adding symbols
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from adapters.ibkr_adapter import IBKRAdapter
from core.interfaces import TradingConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_trading_system_path():
    """Debug the exact path the trading system takes when adding symbols"""
    
    test_symbols = ['OTRK', 'AAPL']
    
    print("🔍 Debugging trading system exact path for symbol validation...")
    
    # Create config matching the trading system
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        broker_host="127.0.0.1",
        broker_port=7497,
        broker_client_id=157,  # Same as config.ini
        strategy_name="macdv",
        timeframe="1 min",  # Same as config.ini
        log_level="INFO",
        log_file="trading_system.log"
    )
    
    # Create IBKR adapter exactly like trading system does
    print("🔌 Creating IBKR adapter...")
    adapter = IBKRAdapter(
        host=config.broker_host,
        port=config.broker_port,
        client_id=config.broker_client_id,
        config=config
    )
    
    try:
        print("🔌 Connecting to IBKR...")
        await adapter.connect()
        print("✅ Connected to IBKR")
        
        for symbol in test_symbols:
            print(f"\n" + "="*50)
            print(f"📊 TESTING SYMBOL: {symbol}")
            print("="*50)
            
            # Replicate EXACTLY what add_symbol does
            print(f"Step 1: Calling get_bars('{symbol}', '{config.timeframe}', 10)")
            try:
                data = await asyncio.wait_for(
                    adapter.get_bars(symbol, config.timeframe, 10),
                    timeout=10.0
                )
                
                if not data:
                    print(f"   ❌ No data available for {symbol} (empty list)")
                else:
                    print(f"   ✅ Got {len(data)} bars for {symbol}")
                    if data:
                        latest = data[-1]
                        print(f"      Latest bar: {latest.timestamp} - O:{latest.open} H:{latest.high} L:{latest.low} C:{latest.close} V:{latest.volume}")
                        
            except asyncio.TimeoutError:
                print(f"   ⏰ Timeout getting data for {symbol} after 10 seconds")
            except Exception as e:
                print(f"   ❌ Error getting data for {symbol}: {e}")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        
    finally:
        if adapter.is_connected():
            await adapter.disconnect()
            print("🔌 Disconnected from IBKR")

if __name__ == "__main__":
    asyncio.run(debug_trading_system_path())