#!/usr/bin/env python3
"""
Test Red to Green Integration
Simple test to verify that Red to Green strategy integration is working correctly
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_red_to_green_imports():
    """Test that Red to Green modules can be imported successfully"""
    print("🔴➡️🟢 Testing Red to Green Integration...")

    try:
        # Test scanner import
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner
        print("✅ Red to Green scanner import successful")

        # Test strategy import
        from strategies.red_to_green_strategy import RedToGreenStrategy
        print("✅ Red to Green strategy import successful")

        # Test ML engine can import R2G strategy
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
        print("✅ ML Multi Strategy Engine import successful")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_red_to_green_instantiation():
    """Test that Red to Green components can be instantiated"""
    print("\n🔧 Testing Red to Green Instantiation...")

    try:
        # Test scanner instantiation
        from scanner.red_to_green.red_to_green_scanner import RedToGreenScanner
        scanner = RedToGreenScanner(ibkr_adapter=None)  # Mock adapter
        print("✅ Red to Green scanner instantiation successful")

        # Test strategy instantiation
        from strategies.red_to_green_strategy import RedToGreenStrategy
        strategy = RedToGreenStrategy()
        print("✅ Red to Green strategy instantiation successful")
        print(f"   Strategy name: {strategy.name}")
        print(f"   Strategy parameters: {len(strategy.parameters)} parameters")

        return True

    except Exception as e:
        print(f"❌ Instantiation error: {e}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        return False

def test_strategy_mapping():
    """Test that R2G strategy is properly mapped in ML engine"""
    print("\n🎯 Testing Strategy Mapping...")

    try:
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

        # Create a mock engine to test mapping
        engine = MLMultiStrategyEngine()

        # Test that red_to_green is in available strategies
        strategy_mapping = engine._get_strategy_mapping()

        if 'red_to_green' in strategy_mapping:
            print("✅ Red to Green found in strategy mapping")
            print(f"   Maps to: {strategy_mapping['red_to_green']}")
        else:
            print("❌ Red to Green NOT found in strategy mapping")
            return False

        return True

    except Exception as e:
        print(f"❌ Strategy mapping error: {e}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        return False

async def test_scanner_integration():
    """Test that R2G scanner integrates with main scanner"""
    print("\n📡 Testing Scanner Integration...")

    try:
        # Import main scanner
        from scanner_main import IndependentScanner

        # Create scanner instance
        scanner_main = IndependentScanner()

        # Check that R2G scanner is initialized
        if hasattr(scanner_main, 'red_to_green_scanner'):
            print("✅ Red to Green scanner attribute exists in main scanner")
        else:
            print("❌ Red to Green scanner attribute NOT found in main scanner")
            return False

        return True

    except Exception as e:
        print(f"❌ Scanner integration error: {e}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        return False

async def main():
    """Run all Red to Green integration tests"""
    print("🚀 Red to Green Integration Test Suite")
    print("=" * 50)

    tests = [
        ("Import Test", test_red_to_green_imports),
        ("Instantiation Test", test_red_to_green_instantiation),
        ("Strategy Mapping Test", test_strategy_mapping),
        ("Scanner Integration Test", test_scanner_integration),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n🎯 Total: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All Red to Green integration tests PASSED!")
        print("🔴➡️🟢 Red to Green strategy is ready for trading!")
    else:
        print("⚠️ Some tests failed. Please check the implementation.")

    return failed == 0

if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise

    # Run tests
    success = asyncio.run(main())
    exit(0 if success else 1)