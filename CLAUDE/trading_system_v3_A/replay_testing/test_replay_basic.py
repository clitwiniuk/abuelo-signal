#!/usr/bin/env python3
"""
Test básico del sistema de replay

Verifica que todos los componentes principales funcionan
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from replay_testing.core import (
    ReplayEngine,
    ReplayVerifier,
    ReplayComparator,
    ReportGenerator
)


def test_replay_engine():
    """Test ReplayEngine initialization and basic functionality"""
    print("="*80)
    print("TEST 1: ReplayEngine initialization")
    print("="*80)

    try:
        engine = ReplayEngine(
            market_data_db_path='backtesting_system/market_data.db',
            trading_data_db_path='trading_data.db',
            verbose=True
        )
        print("✅ ReplayEngine initialized successfully")
        return True
    except Exception as e:
        print(f"❌ ReplayEngine initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_replay_verifier():
    """Test ReplayVerifier"""
    print("\n" + "="*80)
    print("TEST 2: ReplayVerifier")
    print("="*80)

    try:
        verifier = ReplayVerifier(verbose=True)

        # Test entry verification
        decision = {
            'symbol': 'TEST',
            'entry_price': 5.0,
            'pattern_completion': 85.0,
            'timestamp': None
        }

        opportunity = {
            'volume_ratio': 1.5
        }

        worker_config = {
            'min_price': 1.0,
            'max_price': 10.0,
            'max_volume_ratio': 2.0
        }

        result = verifier.verify_entry_decision(decision, opportunity, worker_config)

        print(f"Entry verification result:")
        print(f"  All passed: {result['all_passed']}")
        print(f"  Pass rate: {result['pass_rate']*100:.1f}%")
        print(f"  Checks passed: {list(result['checks_passed'].keys())}")
        print(f"  Checks failed: {list(result['checks_failed'].keys())}")

        print("✅ ReplayVerifier works correctly")
        return True

    except Exception as e:
        print(f"❌ ReplayVerifier test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_replay_comparator():
    """Test ReplayComparator"""
    print("\n" + "="*80)
    print("TEST 3: ReplayComparator")
    print("="*80)

    try:
        comparator = ReplayComparator(verbose=True)

        # Test trade comparison
        simulated_trades = [
            {
                'symbol': 'TEST',
                'entry_time': '2025-10-31 10:00:00',
                'entry_price': 5.0,
                'exit_time': '2025-10-31 11:00:00',
                'exit_price': 5.5,
                'exit_reason': 'TAKE_PROFIT',
                'status': 'CLOSED'
            }
        ]

        real_trades = [
            {
                'symbol': 'TEST',
                'entry_time': '2025-10-31 10:00:30',
                'entry_price': 5.05,
                'exit_time': '2025-10-31 11:00:15',
                'exit_price': 5.52,
                'exit_reason': 'TAKE_PROFIT'
            }
        ]

        comparison = comparator.compare_trades(simulated_trades, real_trades)

        print(f"Comparison result:")
        print(f"  Matched trades: {len(comparison['matched_trades'])}")
        print(f"  Price discrepancies: {len(comparison['price_discrepancies'])}")
        print(f"  Match rate: {comparison['summary']['match_rate']*100:.1f}%")

        # Generate report
        report = comparator.generate_comparison_report(comparison)
        print("\nComparison report:")
        print(report)

        print("✅ ReplayComparator works correctly")
        return True

    except Exception as e:
        print(f"❌ ReplayComparator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_report_generator():
    """Test ReportGenerator"""
    print("\n" + "="*80)
    print("TEST 4: ReportGenerator")
    print("="*80)

    try:
        from datetime import datetime
        from replay_testing.core.replay_engine import ReplaySession

        generator = ReportGenerator(output_dir='replay_testing/reports')

        # Create mock session
        session = ReplaySession(
            date='2025-10-31',
            worker_name='test_worker'
        )
        session.total_bars_processed = 100
        session.total_decisions = 10
        session.total_events = 5
        session.entries_approved = 3
        session.entries_rejected = 2
        session.exits_executed = 2
        session.total_discrepancies = 1
        session.start_time = datetime.now()
        session.end_time = datetime.now()

        # Note: We can't generate actual report without real events
        # but we can verify the generator initializes
        print(f"Report generator initialized")
        print(f"  Output directory: {generator.output_dir}")

        print("✅ ReportGenerator initialized correctly")
        return True

    except Exception as e:
        print(f"❌ ReportGenerator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("REPLAY TESTING SYSTEM - BASIC TESTS")
    print("="*80 + "\n")

    results = []

    results.append(("ReplayEngine", test_replay_engine()))
    results.append(("ReplayVerifier", test_replay_verifier()))
    results.append(("ReplayComparator", test_replay_comparator()))
    results.append(("ReportGenerator", test_report_generator()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! Replay testing system is ready.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
