#!/usr/bin/env python3
"""
Test script to verify the symbol addition fixes work correctly
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from adapters.ibkr_adapter import IBKRAdapter
from engine.trading_engine import TradingEngine
from core.interfaces import TradingConfig
from core.risk_manager import RiskManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_symbol_fixes():
    """Test that our symbol addition fixes work"""
    
    test_symbols = ['OTRK', 'AAPL']
    
    print("🧪 Testing symbol addition fixes...")
    
    # Create config
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        broker_host="127.0.0.1",
        broker_port=7497,
        broker_client_id=158,  # Different client ID to avoid conflicts
        strategy_name="macdv",
        timeframe="1 min",
        log_level="INFO",
        log_file="trading_system.log"
    )
    
    # Create adapters
    print("🔌 Creating IBKR adapter...")
    data_provider = IBKRAdapter(
        host=config.broker_host,
        port=config.broker_port,
        client_id=config.broker_client_id,
        config=config
    )
    broker = data_provider  # Same instance for both
    
    # Create minimal trading engine setup
    from strategies.macdv_strategy import MACDVStrategy
    
    strategy_params = {
        'max_position_value': 100.0,
        'max_portfolio_exposure': 1000.0,
        'macd_fast': 5,
        'macd_slow': 13,
        'macd_signal': 3,
        'volume_threshold': 1.2,
        'stop_loss_pct': 0.08,
        'take_profit_pct': 0.15,
    }
    strategy = MACDVStrategy(strategy_params)
    risk_manager = RiskManager(config)
    
    engine = TradingEngine(
        config=config,
        data_provider=data_provider,
        broker=broker,
        strategy=strategy,
        risk_manager=risk_manager,
        filters=[]
    )
    
    try:
        print("🔌 Connecting to IBKR...")
        await data_provider.connect()
        print("✅ Connected to IBKR")
        
        # Initialize the engine
        await engine.initialize()
        
        for symbol in test_symbols:
            print(f"\n" + "="*50)
            print(f"📊 TESTING SYMBOL ADDITION: {symbol}")
            print("="*50)
            
            # Test adding symbol with validation
            print(f"🔍 Adding {symbol} with validation...")
            result = await engine.add_symbol(symbol, skip_validation=False)
            
            if result:
                print(f"   ✅ Successfully added {symbol}")
                print(f"   📈 Monitored symbols: {engine.monitored_symbols}")
            else:
                print(f"   ❌ Failed to add {symbol}")
                
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if data_provider.is_connected():
            await data_provider.disconnect()
            print("🔌 Disconnected from IBKR")

if __name__ == "__main__":
    asyncio.run(test_symbol_fixes())