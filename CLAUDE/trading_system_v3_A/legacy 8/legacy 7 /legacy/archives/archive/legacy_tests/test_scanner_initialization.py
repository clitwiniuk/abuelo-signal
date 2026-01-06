#!/usr/bin/env python3
"""
Test específico para SmallcapDailyScanner initialization
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScannerTest")

async def test_scanner_initialization():
    """Test SmallcapDailyScanner initialization"""
    try:
        from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
        
        print("🔍 Testing SmallcapDailyScanner initialization...")
        
        # Try to create scanner
        scanner = SmallcapDailyScanner()
        
        print("✅ SmallcapDailyScanner created successfully")
        print(f"   - Scanner type: {type(scanner)}")
        print(f"   - Has scan_daily_plays method: {hasattr(scanner, 'scan_daily_plays')}")
        
        # Test method existence
        if hasattr(scanner, 'scan_daily_plays'):
            print(f"   - scan_daily_plays is callable: {callable(scanner.scan_daily_plays)}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   - Check if SmallcapDailyScanner exists in scanner/smallcap/")
        return False
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scanner_file_exists():
    """Check if scanner file exists"""
    scanner_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scanner/smallcap/smallcap_daily_scanner.py"
    
    print(f"📁 Checking scanner file: {scanner_path}")
    
    if os.path.exists(scanner_path):
        print("✅ Scanner file exists")
        
        # Check if it's readable
        try:
            with open(scanner_path, 'r') as f:
                content = f.read(100)  # Read first 100 chars
            print(f"✅ Scanner file is readable (first 100 chars): {content[:50]}...")
            return True
        except Exception as e:
            print(f"❌ Scanner file not readable: {e}")
            return False
    else:
        print("❌ Scanner file does not exist")
        
        # Check what files exist in scanner directory
        scanner_dir = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/scanner"
        if os.path.exists(scanner_dir):
            print(f"📂 Files in scanner directory:")
            for item in os.listdir(scanner_dir):
                print(f"   - {item}")
                
            smallcap_dir = os.path.join(scanner_dir, "smallcap")
            if os.path.exists(smallcap_dir):
                print(f"📂 Files in scanner/smallcap directory:")
                for item in os.listdir(smallcap_dir):
                    print(f"   - {item}")
            else:
                print("❌ scanner/smallcap directory does not exist")
        
        return False

async def run_all_tests():
    """Run all scanner tests"""
    print("🧪 TESTING SCANNER INITIALIZATION")
    print("=" * 50)
    
    tests = [
        ("Scanner File Exists", test_scanner_file_exists),
        ("Scanner Initialization", test_scanner_initialization)
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
    print("📊 SCANNER TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {total - passed} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n🟢 SCANNER: READY FOR USE")
    elif success_rate >= 50:
        print("\n🟡 SCANNER: NEEDS ATTENTION")
    else:
        print("\n🔴 SCANNER: CRITICAL ISSUES")
    
    return success_rate == 100

if __name__ == "__main__":
    asyncio.run(run_all_tests())