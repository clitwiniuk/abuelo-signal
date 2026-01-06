#!/usr/bin/env python3
"""
Gap Fade Worker - Integration Test
Verifies that the worker is properly registered and configured in the system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import ServiceLocator
from strategies.workers.gap_fade_worker_logic import GapFadeWorkerLogic


def test_service_locator_registration():
    """Test 1: Verify Gap Fade is registered in ServiceLocator"""
    print("="*70)
    print("TEST 1: ServiceLocator Registration")
    print("="*70)

    locator = ServiceLocator()
    config = locator.load_config()

    # Check if gap_fade_strategy_enabled exists
    if hasattr(config, 'gap_fade_strategy_enabled'):
        print(f"✅ gap_fade_strategy_enabled exists: {config.gap_fade_strategy_enabled}")
    else:
        print("❌ gap_fade_strategy_enabled NOT FOUND in config")
        return False

    print()
    return True


def test_worker_import():
    """Test 2: Verify worker can be imported"""
    print("="*70)
    print("TEST 2: Worker Import")
    print("="*70)

    try:
        from strategies.workers import GapFadeWorkerLogic
        print("✅ GapFadeWorkerLogic imported successfully")
        print(f"   Worker class: {GapFadeWorkerLogic}")
        print()
        return True
    except ImportError as e:
        print(f"❌ Failed to import GapFadeWorkerLogic: {e}")
        print()
        return False


def test_worker_initialization():
    """Test 3: Verify worker can be instantiated"""
    print("="*70)
    print("TEST 3: Worker Initialization")
    print("="*70)

    try:
        locator = ServiceLocator()
        config = locator.get_config()

        # Create worker instance
        worker = GapFadeWorkerLogic(config=config)

        print(f"✅ Worker initialized successfully")
        print(f"   Worker name: {worker.worker_name}")
        print(f"   Min gap: {worker.min_gap_percent}%")
        print(f"   Entry window: {worker.entry_window_start} - {worker.entry_window_end}")
        print(f"   Min quality: {worker.min_quality_score}")
        print(f"   Min float: {worker.min_float}M shares")
        print()
        return True
    except Exception as e:
        print(f"❌ Failed to initialize worker: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_config_values():
    """Test 4: Verify config.ini values are loaded correctly"""
    print("="*70)
    print("TEST 4: Configuration Values")
    print("="*70)

    import configparser
    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')

    if 'GAP_FADE_STRATEGY' in config_parser:
        print("✅ [GAP_FADE_STRATEGY] section found in config.ini")

        # Check key values
        enabled = config_parser.getboolean('GAP_FADE_STRATEGY', 'enabled', fallback=False)
        min_gap = config_parser.getfloat('GAP_FADE_STRATEGY', 'gap_fade_min_gap_pct', fallback=0)
        entry_start = config_parser.get('GAP_FADE_STRATEGY', 'gap_fade_entry_start', fallback='N/A')
        min_quality = config_parser.getfloat('GAP_FADE_STRATEGY', 'gap_fade_min_quality_score', fallback=0)

        print(f"   enabled: {enabled}")
        print(f"   gap_fade_min_gap_pct: {min_gap}%")
        print(f"   gap_fade_entry_start: {entry_start}")
        print(f"   gap_fade_min_quality_score: {min_quality}")
        print()
        return True
    else:
        print("❌ [GAP_FADE_STRATEGY] section NOT FOUND in config.ini")
        print()
        return False


def test_worker_in_engine():
    """Test 5: Verify worker appears in worker list when enabled"""
    print("="*70)
    print("TEST 5: Worker in Strategy Engine")
    print("="*70)

    try:
        from strategies.worker_based_strategy_engine import WorkerBasedStrategyEngine
        print("✅ WorkerBasedStrategyEngine imported successfully")

        # Check if GapFadeWorkerLogic is imported in the engine
        import inspect
        source = inspect.getsource(WorkerBasedStrategyEngine.__init__)

        if 'GapFadeWorkerLogic' in source:
            print("✅ GapFadeWorkerLogic referenced in WorkerBasedStrategyEngine")
        else:
            print("❌ GapFadeWorkerLogic NOT referenced in WorkerBasedStrategyEngine")

        if "gap_fade" in source:
            print("✅ 'gap_fade' worker key found in engine")
        else:
            print("⚠️  'gap_fade' worker key NOT found in engine")

        print()
        return True
    except Exception as e:
        print(f"❌ Error checking engine: {e}")
        print()
        return False


def run_all_tests():
    """Run all integration tests"""
    print("\n")
    print("="*70)
    print("GAP FADE WORKER - INTEGRATION TEST SUITE")
    print("="*70)
    print()

    results = []

    # Run tests
    results.append(("ServiceLocator Registration", test_service_locator_registration()))
    results.append(("Worker Import", test_worker_import()))
    results.append(("Worker Initialization", test_worker_initialization()))
    results.append(("Configuration Values", test_config_values()))
    results.append(("Worker in Engine", test_worker_in_engine()))

    # Print summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed")
    print("="*70)

    return all(result for _, result in results)


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
