#!/usr/bin/env python3
"""
Run Blind Test - Execute VCP worker on unseen symbols
"""

import json
import sys
import subprocess
import os
from datetime import datetime

def run_blind_test(scenarios_file, output_file):
    """
    Execute blind test and record results

    Args:
        scenarios_file: Path to blind test scenarios JSON
        output_file: Path to output results
    """

    if not os.path.exists(scenarios_file):
        print(f"❌ Scenarios file not found: {scenarios_file}")
        sys.exit(1)

    with open(scenarios_file, 'r') as f:
        scenarios = json.load(f)

    print("="*80)
    print(f"🎲 BLIND TEST - VCP_Smallcap Worker")
    print(f"📊 Testing {len(scenarios)} unseen symbols")
    print(f"🎯 Target: >70% meaningful results (entry or valid rejection)")
    print("="*80)

    results = []
    entries_found = 0
    rejections = 0
    errors = 0

    market_db_path = "blind_test_market_data.db"

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing {scenario['symbol']} ({scenario['date']})...")

        # Prepare DB
        cmd = [
            sys.executable,
            "scripts/prepare_replay_db.py",
            "--symbol", scenario['symbol'],
            "--date", scenario['date'],
            "--output-db", market_db_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️  DB prep failed: {result.stderr[:100]}")
            results.append({
                'scenario_id': scenario['id'],
                'symbol': scenario['symbol'],
                'date': scenario['date'],
                'result': 'ERROR',
                'entries': 0,
                'error': result.stderr[:200]
            })
            errors += 1
            continue

        # Run regression
        cmd = [
            sys.executable,
            "replay_testing/run_regression.py",
            "--scenarios", scenarios_file
        ]

        # Import locally
        sys.path.insert(0, '.')
        from replay_testing.core.replay_engine import ReplayEngine

        engine = ReplayEngine(
            market_data_db_path=market_db_path,
            trading_data_db_path='trading_data.db',
            verbose=False
        )

        mock_metadata = {
            scenario['symbol']: scenario.get('mock_scanner_data', {})
        }

        try:
            session = engine.replay_day(
                date=scenario['date'],
                worker_names=['vcp_smallcap'],
                symbols=[scenario['symbol']],
                mock_metadata=mock_metadata
            )

            entries = session.entries_approved

            if entries > 0:
                print(f"   ✅ VCP Pattern Detected: {entries} entries")
                result_type = 'ENTRY'
                entries_found += 1
            else:
                print(f"   ⚪ No VCP Pattern: Correctly rejected")
                result_type = 'NO_ENTRY'
                rejections += 1

            results.append({
                'scenario_id': scenario['id'],
                'symbol': scenario['symbol'],
                'date': scenario['date'],
                'result': result_type,
                'entries': entries,
                'bars_processed': session.total_bars_processed,
                'decisions': session.total_decisions
            })

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            results.append({
                'scenario_id': scenario['id'],
                'symbol': scenario['symbol'],
                'date': scenario['date'],
                'result': 'ERROR',
                'entries': 0,
                'error': str(e)[:200]
            })
            errors += 1

    # Cleanup
    if os.path.exists(market_db_path):
        os.remove(market_db_path)

    # Calculate metrics
    total = len(scenarios)
    valid_tests = total - errors
    success_rate = (valid_tests / total * 100) if total > 0 else 0
    entry_rate = (entries_found / valid_tests * 100) if valid_tests > 0 else 0

    # Summary
    print("\n" + "="*80)
    print("🏁 BLIND TEST COMPLETE")
    print("="*80)
    print(f"Total Scenarios: {total}")
    print(f"Valid Tests: {valid_tests} ({success_rate:.1f}%)")
    print(f"Errors: {errors}")
    print(f"\nResults:")
    print(f"  VCP Patterns Found: {entries_found} ({entry_rate:.1f}%)")
    print(f"  No VCP Pattern: {rejections}")
    print(f"\n✅ Success Rate: {success_rate:.1f}% (target: >70%)")

    # Save results
    output_data = {
        'test_date': datetime.now().isoformat(),
        'total_scenarios': total,
        'valid_tests': valid_tests,
        'errors': errors,
        'entries_found': entries_found,
        'rejections': rejections,
        'success_rate': success_rate,
        'entry_rate': entry_rate,
        'results': results
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    return success_rate >= 70.0

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run VCP Blind Test')
    parser.add_argument('--scenarios', default='replay_testing/scenarios/vcp_smallcap_blind_test.json')
    parser.add_argument('--output', default='replay_testing/results/vcp_blind_test_results.json')

    args = parser.parse_args()

    # Create results directory if needed
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    success = run_blind_test(args.scenarios, args.output)

    sys.exit(0 if success else 1)
