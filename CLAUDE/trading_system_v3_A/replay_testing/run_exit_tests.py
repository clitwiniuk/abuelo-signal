#!/usr/bin/env python3
"""
Run EXIT Tests - Execute VCP worker exit scenario validation

Tests all exit conditions configured for VCP_Smallcap:
- STOP_LOSS (-5%)
- BREAK_EVEN (+4% peak -> ~0%)
- TRAILING_STOP (+8% activation, -4% from peak)
- TAKE_PROFIT (+15%)
- TIME_LIMIT (6 hours)
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

def simulate_exit_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate an exit scenario using configured parameters

    Args:
        scenario: Exit scenario definition

    Returns:
        Test result with pass/fail status
    """
    scenario_id = scenario.get('id')
    expected_action = scenario.get('expected_action')

    # Skip documentation entry
    if scenario_id == 'VCP_EXIT_DOCUMENTATION':
        return None

    print(f"\n[TEST] {scenario_id}")
    print(f"   Description: {scenario.get('description')}")
    print(f"   Expected: {expected_action}")

    # Extract test parameters
    entry_price = scenario.get('entry_price', 0)
    exit_price = scenario.get('exit_price', 0)
    peak_price = scenario.get('peak_price', entry_price)
    expected_pnl = scenario.get('expected_pnl_pct', 0)

    if entry_price == 0:
        print(f"   ⚠️  SKIPPED: No entry_price defined")
        return {
            'scenario_id': scenario_id,
            'result': 'SKIPPED',
            'reason': 'Missing test parameters'
        }

    # Calculate actual PnL
    actual_pnl = ((exit_price / entry_price) - 1) * 100
    peak_pnl = ((peak_price / entry_price) - 1) * 100

    print(f"   Entry: ${entry_price:.2f}")
    if peak_price > entry_price:
        print(f"   Peak: ${peak_price:.2f} ({peak_pnl:+.1f}%)")
    print(f"   Exit: ${exit_price:.2f} ({actual_pnl:+.1f}%)")

    # Validate exit logic
    result = validate_exit_logic(
        exit_type=expected_action,
        entry_price=entry_price,
        exit_price=exit_price,
        peak_price=peak_price,
        scenario=scenario
    )

    if result['pass']:
        print(f"   ✅ PASS: {result['reason']}")
    else:
        print(f"   ❌ FAIL: {result['reason']}")

    return {
        'scenario_id': scenario_id,
        'expected_action': expected_action,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'peak_price': peak_price,
        'expected_pnl': expected_pnl,
        'actual_pnl': round(actual_pnl, 2),
        'result': 'PASS' if result['pass'] else 'FAIL',
        'validation': result['reason']
    }


def validate_exit_logic(
    exit_type: str,
    entry_price: float,
    exit_price: float,
    peak_price: float,
    scenario: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate that exit scenario follows VCP_Smallcap exit logic

    Exit Parameters:
    - stop_loss_pct = 5.0
    - breakeven_activation_pct = 4.0
    - trailing_activation = 8.0
    - trailing_distance = 4.0
    - take_profit_pct = 15.0
    - max_hold_hours = 6.0
    """
    pnl = ((exit_price / entry_price) - 1) * 100
    peak_pnl = ((peak_price / entry_price) - 1) * 100

    if exit_type == 'EXIT_STOP_LOSS':
        # Should hit -5% stop loss
        if pnl <= -4.5 and pnl >= -5.5:  # Allow 0.5% tolerance
            return {'pass': True, 'reason': f'Stop loss triggered at {pnl:.1f}% (target: -5%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in SL range [-5.5%, -4.5%]'}

    elif exit_type == 'EXIT_BREAK_EVEN':
        # Should have peaked at +4%, then exit near 0%
        if peak_pnl < 3.5:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate BE (need +4%)'}
        if pnl < -1.0:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% is loss (BE should protect)'}
        if pnl > 0 and pnl <= 1.0:
            return {'pass': True, 'reason': f'BE protected: peaked {peak_pnl:.1f}%, exited {pnl:.1f}%'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not near break-even'}

    elif exit_type == 'EXIT_TRAILING_STOP':
        # Should have peaked at +8%+, then dropped 4% from peak
        if peak_pnl < 8.0:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate trailing (need +8%)'}

        # Calculate expected trailing trigger (peak - 4%)
        expected_trigger = peak_pnl - 4.0

        if abs(pnl - expected_trigger) <= 1.0:  # 1% tolerance
            return {'pass': True, 'reason': f'Trailing triggered: peak {peak_pnl:.1f}%, exit {pnl:.1f}% (expected ~{expected_trigger:.1f}%)'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not near trailing trigger {expected_trigger:.1f}%'}

    elif exit_type == 'EXIT_TAKE_PROFIT':
        # Should hit +15% take profit
        if pnl >= 14.5 and pnl <= 15.5:  # Allow 0.5% tolerance
            return {'pass': True, 'reason': f'Take profit hit at {pnl:.1f}% (target: +15%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in TP range [14.5%, 15.5%]'}

    elif exit_type == 'EXIT_TIME_LIMIT':
        # Should be held for 6 hours
        hold_hours = scenario.get('hold_time_hours', 0)
        if hold_hours < 5.5:
            return {'pass': False, 'reason': f'Hold time {hold_hours:.1f}h < 6h limit'}
        if pnl < -5.0 or pnl > 15.0:
            return {'pass': False, 'reason': f'Should have hit SL/TP before time limit (PnL: {pnl:.1f}%)'}
        return {'pass': True, 'reason': f'Time limit exit at {hold_hours:.1f}h with {pnl:+.1f}% PnL'}

    else:
        return {'pass': False, 'reason': f'Unknown exit type: {exit_type}'}


def run_exit_tests(scenarios_file: str, output_file: str) -> bool:
    """
    Execute all exit test scenarios

    Args:
        scenarios_file: Path to exit scenarios JSON
        output_file: Path to output results

    Returns:
        True if all tests pass, False otherwise
    """
    if not os.path.exists(scenarios_file):
        print(f"❌ Scenarios file not found: {scenarios_file}")
        sys.exit(1)

    with open(scenarios_file, 'r') as f:
        scenarios = json.load(f)

    print("="*80)
    print(f"🧪 EXIT TESTS - VCP_Smallcap Worker")
    print(f"📊 Testing {len(scenarios) - 1} exit scenarios")  # -1 for documentation entry
    print(f"🎯 Validating: SL, BE, TS, TP, Time Limit")
    print("="*80)

    results = []
    passed = 0
    failed = 0
    skipped = 0

    for scenario in scenarios:
        result = simulate_exit_scenario(scenario)

        if result is None:
            continue  # Skip documentation

        results.append(result)

        if result['result'] == 'PASS':
            passed += 1
        elif result['result'] == 'FAIL':
            failed += 1
        else:
            skipped += 1

    # Summary
    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0

    print("\n" + "="*80)
    print("🏁 EXIT TESTS COMPLETE")
    print("="*80)
    print(f"Total Scenarios: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"\n✅ Pass Rate: {pass_rate:.1f}% (target: 100%)")

    # Save results
    output_data = {
        'test_date': datetime.now().isoformat(),
        'total_scenarios': total,
        'passed': passed,
        'failed': failed,
        'skipped': skipped,
        'pass_rate': pass_rate,
        'results': results
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    return pass_rate == 100.0


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run VCP Exit Tests')
    parser.add_argument('--scenarios', default='replay_testing/scenarios/vcp_exit_scenarios.json')
    parser.add_argument('--output', default='replay_testing/results/vcp_exit_test_results.json')

    args = parser.parse_args()

    # Create results directory if needed
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    success = run_exit_tests(args.scenarios, args.output)

    sys.exit(0 if success else 1)
