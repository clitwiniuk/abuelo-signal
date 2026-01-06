#!/usr/bin/env python3
"""
Test Synthetic Data Integration

Script para probar la integración del modo de datos sintéticos
con el sistema de trading principal.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import TradingConfig
from adapters.csv_data_provider import CSVDataProvider
from main import TradingSystemManager

async def test_synthetic_data_provider():
    """Test synthetic data provider functionality"""
    
    print("🧪 TESTING SYNTHETIC DATA PROVIDER")
    print("=" * 50)
    
    # Test 1: Initialize synthetic data provider
    print("📊 Test 1: Initializing synthetic data provider...")
    provider = CSVDataProvider(use_synthetic_data=True)
    
    # Test connection
    success = await provider.connect()
    if not success:
        print("❌ Failed to connect to synthetic data provider")
        return False
    
    print(f"✅ Connected successfully")
    
    # Test 2: Check available symbols
    print("\n📊 Test 2: Checking available synthetic symbols...")
    symbols = provider.get_available_symbols()
    
    if not symbols:
        print("❌ No synthetic symbols found")
        print("💡 Make sure to run extract_full_trading_days.py first")
        return False
    
    print(f"✅ Found {len(symbols)} synthetic symbols: {symbols[:5]}{'...' if len(symbols) > 5 else ''}")
    
    # Test 3: Load data for a symbol
    print(f"\n📊 Test 3: Loading data for symbol {symbols[0]}...")
    bars = await provider.get_bars(symbols[0], "1 min", 100)
    
    if not bars:
        print(f"❌ No data loaded for {symbols[0]}")
        return False
    
    print(f"✅ Loaded {len(bars)} bars for {symbols[0]}")
    print(f"   📅 Date range: {bars[0].timestamp} to {bars[-1].timestamp}")
    
    # Test 4: Check event metadata
    print(f"\n📊 Test 4: Checking event metadata for {symbols[0]}...")
    event_info = provider.get_event_info_for_symbol(symbols[0])
    
    if event_info:
        print(f"✅ Event metadata found:")
        print(f"   📈 Original ticker: {event_info.get('original_ticker', 'N/A')}")
        print(f"   🚀 Volume ratio: {event_info.get('ratio_vol', 'N/A'):.1f}x")
        print(f"   📅 Event timestamp: {event_info.get('event_timestamp', 'N/A')}")
    else:
        print("⚠️ No event metadata found")
    
    # Test 5: Provider stats
    print(f"\n📊 Test 5: Getting provider statistics...")
    stats = provider.get_stats()
    
    print(f"✅ Provider stats:")
    print(f"   📊 Total symbols: {stats.get('total_symbols', 0)}")
    print(f"   🎯 Synthetic mode: {stats.get('synthetic_mode', False)}")
    print(f"   📋 Events loaded: {stats.get('events_metadata_loaded', False)}")
    print(f"   📈 Total events: {stats.get('total_events', 0)}")
    
    await provider.disconnect()
    print(f"\n✅ Synthetic data provider test completed successfully!")
    return True

async def test_full_system_integration():
    """Test full trading system with synthetic data"""
    
    print("\n\n🚀 TESTING FULL SYSTEM INTEGRATION")
    print("=" * 50)
    
    # Create configuration with synthetic data enabled
    config = TradingConfig(
        max_positions=5,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=20,
        strategy_name="macdv",
        timeframe="1 min",
        log_level="INFO",
        use_synthetic_data=True
    )
    
    print("📊 Test 1: Initializing trading system with synthetic data...")
    system = TradingSystemManager(config, in_streamlit=False)
    
    try:
        # Initialize system
        await system.initialize()
        print("✅ System initialized successfully")
        
        # Check data provider mode
        if hasattr(system.data_provider, 'is_synthetic_mode'):
            is_synthetic = system.data_provider.is_synthetic_mode()
            print(f"🎯 Data provider synthetic mode: {is_synthetic}")
        
        # Get available symbols
        if hasattr(system.data_provider, 'get_available_symbols'):
            symbols = system.data_provider.get_available_symbols()
            print(f"📊 Available symbols: {len(symbols)} found")
            
            if symbols:
                # Test loading data for first symbol
                test_symbol = symbols[0]
                print(f"📈 Testing data loading for: {test_symbol}")
                
                bars = await system.data_provider.get_bars(test_symbol, "1 min", 50)
                if bars:
                    print(f"✅ Loaded {len(bars)} bars for {test_symbol}")
                    print(f"   💰 Price range: ${bars[0].close:.2f} - ${bars[-1].close:.2f}")
                else:
                    print(f"❌ No bars loaded for {test_symbol}")
        
        print("✅ Full system integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during system integration test: {e}")
        return False
    finally:
        try:
            await system.stop()
        except:
            pass

async def main():
    """Main test function"""
    
    print("🎯 SYNTHETIC DATA INTEGRATION TESTS")
    print("=" * 60)
    print("Testing integration between synthetic data and trading system")
    print()
    
    # Check if synthetic data exists
    synthetic_dir = Path("synthetic_data")
    if not synthetic_dir.exists():
        print("❌ Synthetic data directory not found")
        print("💡 Run 'extract_full_trading_days.py' first to generate synthetic data")
        return
    
    metadata_file = synthetic_dir / "events_metadata.csv"
    if not metadata_file.exists():
        print("❌ Events metadata file not found")
        print("💡 Run 'extract_full_trading_days.py' first to generate metadata")
        return
    
    # Run tests
    try:
        # Test 1: Synthetic data provider
        provider_test = await test_synthetic_data_provider()
        
        if provider_test:
            # Test 2: Full system integration
            system_test = await test_full_system_integration()
            
            if system_test:
                print("\n" + "=" * 60)
                print("🎉 ALL TESTS PASSED!")
                print("✅ Synthetic data integration is working correctly")
                print("🚀 Ready to run trading system with synthetic data")
                print()
                print("💡 Next steps:")
                print("   1. Run 'python main.py' to start trading system")
                print("   2. Or run 'python start.py' and select option 6")
                print("   3. System will use synthetic event data automatically")
            else:
                print("\n❌ System integration test failed")
        else:
            print("\n❌ Data provider test failed")
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        logging.exception("Test error details:")

if __name__ == "__main__":
    asyncio.run(main())