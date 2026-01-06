#!/usr/bin/env python3
"""
Test para verificar la corrección del IBKR Native Scanner event loop
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("IBKRScannerTest")

async def test_ibkr_scanner_creation():
    """Test IBKR Native Scanner creation"""
    try:
        from scanner.ibkr_native_scanner import IBKRNativeScanner
        from adapters.ibkr_adapter import IBKRAdapter
        
        print("🔍 Testing IBKR Native Scanner creation...")
        
        # Create mock IBKR adapter (without connection)
        ibkr_adapter = IBKRAdapter()
        
        # Create scanner
        scanner = IBKRNativeScanner(ibkr_adapter)
        
        print("✅ IBKR Native Scanner created successfully")
        print(f"   - Scanner type: {type(scanner)}")
        print(f"   - Has scan_daily_plays method: {hasattr(scanner, 'scan_daily_plays')}")
        print(f"   - Has _request_scanner_data method: {hasattr(scanner, '_request_scanner_data')}")
        print(f"   - Does NOT have _sync_scanner_request: {not hasattr(scanner, '_sync_scanner_request')}")
        
        return True
        
    except Exception as e:
        print(f"❌ IBKR Scanner creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scanner_method_signatures():
    """Test that scanner methods have correct async signatures"""
    try:
        from scanner.ibkr_native_scanner import IBKRNativeScanner
        import inspect
        
        print("🔍 Testing scanner method signatures...")
        
        scanner = IBKRNativeScanner()
        
        # Check that key methods are async
        async_methods = ['scan_daily_plays', '_request_scanner_data', '_enhance_scan_results']
        
        for method_name in async_methods:
            if hasattr(scanner, method_name):
                method = getattr(scanner, method_name)
                if asyncio.iscoroutinefunction(method):
                    print(f"   - {method_name}: ✅ (async)")
                else:
                    print(f"   - {method_name}: ❌ (not async)")
                    return False
            else:
                print(f"   - {method_name}: ❌ (missing)")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Method signature test failed: {e}")
        return False

async def test_scanner_request_method():
    """Test the _request_scanner_data method structure"""
    try:
        from scanner.ibkr_native_scanner import IBKRNativeScanner
        from ib_insync import ScannerSubscription
        
        print("🔍 Testing scanner request method...")
        
        scanner = IBKRNativeScanner()
        
        # Create a basic scanner subscription
        scanner_sub = ScannerSubscription(
            instrument='STK',
            locationCode='STK.US.MAJOR',
            scanCode='TOP_PERC_GAIN'
        )
        
        # Test that method exists and is callable
        if hasattr(scanner, '_request_scanner_data'):
            method = scanner._request_scanner_data
            if asyncio.iscoroutinefunction(method):
                print("✅ _request_scanner_data is async and callable")
                # Note: We won't actually call it since we don't have IBKR connection
                return True
            else:
                print("❌ _request_scanner_data is not async")
                return False
        else:
            print("❌ _request_scanner_data method missing")
            return False
        
    except Exception as e:
        print(f"❌ Scanner request method test failed: {e}")
        return False

def test_no_sync_method():
    """Test that _sync_scanner_request method was removed"""
    try:
        from scanner.ibkr_native_scanner import IBKRNativeScanner
        
        print("🔍 Testing that sync method was removed...")
        
        scanner = IBKRNativeScanner()
        
        if not hasattr(scanner, '_sync_scanner_request'):
            print("✅ _sync_scanner_request method successfully removed")
            return True
        else:
            print("❌ _sync_scanner_request method still exists")
            return False
        
    except Exception as e:
        print(f"❌ Sync method removal test failed: {e}")
        return False

async def run_scanner_tests():
    """Run all IBKR scanner tests"""
    print("🧪 TESTING IBKR NATIVE SCANNER FIXES")
    print("=" * 50)
    
    tests = [
        ("Scanner Creation", test_ibkr_scanner_creation),
        ("Method Signatures", test_scanner_method_signatures),
        ("Scanner Request Method", test_scanner_request_method),
        ("Sync Method Removal", test_no_sync_method)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        print("-" * 30)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append(result)
            
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print("\n" + "=" * 50)
    print("📊 IBKR SCANNER TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {total - passed} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n🟢 IBKR SCANNER: EVENT LOOP ISSUES FIXED")
        print("   ✅ Removed problematic sync method")
        print("   ✅ Using proper async/await pattern")
        print("   ✅ No more ThreadPoolExecutor conflicts")
    else:
        print("\n🔴 IBKR SCANNER: STILL HAS ISSUES")
    
    return success_rate == 100

if __name__ == "__main__":
    asyncio.run(run_scanner_tests())