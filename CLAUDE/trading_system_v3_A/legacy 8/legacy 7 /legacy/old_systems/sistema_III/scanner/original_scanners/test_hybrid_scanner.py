# scanner/test_hybrid_scanner.py
"""
Quick test script for Hybrid Scanner (IBKR + Tiingo)
Use this to test the scanner without Streamlit
"""

import asyncio
import logging
from typing import Optional

from hybrid_scanner import HybridScanner, DataSource
from tiingo_data_provider import TiingoDataProvider, test_tiingo_scanner

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_tiingo_only(api_key: str):
    """Test Tiingo scanner only"""
    print("🧪 Testing Tiingo Scanner Only...")
    
    try:
        results = await test_tiingo_scanner(api_key)
        print(f"✅ Tiingo test completed: {len(results)} results")
        return True
    except Exception as e:
        print(f"❌ Tiingo test failed: {e}")
        return False

async def test_hybrid_scanner_tiingo_only(api_key: str):
    """Test hybrid scanner with Tiingo only (no IBKR)"""
    print("🧪 Testing Hybrid Scanner (Tiingo Only)...")
    
    try:
        # Initialize scanner without IBKR
        scanner = HybridScanner(
            ibkr_adapter=None,  # No IBKR
            tiingo_api_key=api_key
        )
        
        # Run scan
        results = await scanner.scan_daily_plays(
            min_gap_percent=0.05,  # 5% for testing
            min_volume_ratio=1.5,  # Lower threshold for testing
            max_results=10
        )
        
        if results:
            print(f"✅ Hybrid scan completed: {len(results)} results")
            print("\n" + scanner.format_results(results))
            
            # Check data sources
            tiingo_count = sum(1 for r in results if r.primary_source == DataSource.TIINGO)
            print(f"📡 Tiingo results: {tiingo_count}")
            
        else:
            print("⚠️ No results found (market may be closed)")
        
        return True
        
    except Exception as e:
        print(f"❌ Hybrid scanner test failed: {e}")
        logger.error(f"Hybrid scanner test error: {e}", exc_info=True)
        return False

async def test_without_api_key():
    """Test scanner behavior without API keys"""
    print("🧪 Testing Scanner Without API Keys...")
    
    try:
        scanner = HybridScanner(
            ibkr_adapter=None,
            tiingo_api_key=None
        )
        
        results = await scanner.scan_daily_plays()
        print(f"Result with no API keys: {len(results)} results (should be empty)")
        
        return True
        
    except Exception as e:
        print(f"❌ No-API test failed: {e}")
        return False

def run_tests():
    """Run all tests"""
    print("🔍 HYBRID SCANNER TESTING SUITE")
    print("=" * 50)
    
    # Check for Tiingo API key
    tiingo_key = input("Enter your Tiingo API key (or press Enter to skip Tiingo tests): ").strip()
    
    if not tiingo_key:
        print("⚠️ No Tiingo API key provided - testing without external APIs only")
        
        # Test without API key
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(test_without_api_key())
        finally:
            loop.close()
    
    else:
        print(f"🔑 Using Tiingo API key: {tiingo_key[:8]}...")
        
        # Run tests with API key
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Test 1: Tiingo only
            print("\n" + "="*30)
            success1 = loop.run_until_complete(test_tiingo_only(tiingo_key))
            
            # Test 2: Hybrid scanner (Tiingo only)
            print("\n" + "="*30)
            success2 = loop.run_until_complete(test_hybrid_scanner_tiingo_only(tiingo_key))
            
            # Test 3: No API key
            print("\n" + "="*30)
            success3 = loop.run_until_complete(test_without_api_key())
            
            # Summary
            print("\n" + "="*50)
            print("🏁 TEST SUMMARY:")
            print(f"   Tiingo Only: {'✅' if success1 else '❌'}")
            print(f"   Hybrid (Tiingo): {'✅' if success2 else '❌'}")
            print(f"   No API Keys: {'✅' if success3 else '❌'}")
            
        finally:
            loop.close()
    
    print("\n🎯 Testing complete!")
    print("💡 Next steps:")
    print("   1. Get Tiingo API key at https://www.tiingo.com/")
    print("   2. Configure API key in Streamlit interface")
    print("   3. Run hybrid scanner in Streamlit app")

if __name__ == "__main__":
    run_tests()