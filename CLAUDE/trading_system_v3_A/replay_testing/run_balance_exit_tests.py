#!/usr/bin/env python3
"""
Run EXIT Tests - Execute Balance Day worker exit scenario validation

Tests all exit conditions configured for Balance Day:
- STOP_LOSS (-2%)
- TRAILING_STOP (+3% activation, -1.5% from peak)
- TAKE_PROFIT (+4%)
- TIME_LIMIT (1 hour)
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
    Validate that exit scenario follows Balance Day exit logic

    Exit Parameters:
    - stop_loss_pct = 2.0
    - breakeven_activation_pct = 2.5
    - trailing_activation = 3.0
    - trailing_distance = 1.5
    - take_profit_pct = 4.0
    - max_hold_hours = 1.0
    """
    pnl = ((exit_price / entry_price) - 1) * 100
    peak_pnl = ((peak_price / entry_price) - 1) * 100

    if exit_type == 'EXIT_STOP_LOSS':
        # Should hit -2% stop loss
        if pnl <= -1.8 and pnl >= -2.2:  # Allow 0.2% tolerance
            return {'pass': True, 'reason': f'Stop loss triggered at {pnl:.1f}% (target: -2%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in SL range [-2.2%, -1.8%]'}

    elif exit_type == 'EXIT_BREAK_EVEN':
        # Should have peaked at +2.5%, then exit near 0%
        if peak_pnl < 2.3:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate BE (need +2.5%)'}
        if pnl < -1.0:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% is loss (BE should protect)'}
        if pnl >= 0 and pnl <= 1.0:
            return {'pass': True, 'reason': f'BE protected: peaked {peak_pnl:.1f}%, exited {pnl:.1f}%'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not near break-even'}

    elif exit_type == 'EXIT_TRAILING_STOP':
        # Should have peaked at +3%+, then dropped 1.5% from peak
        if peak_pnl < 3.0:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate trailing (need +3%)'}

        # Calculate expected trailing trigger (peak - 1.5%)
        expected_trigger = peak_pnl - 1.5

        if abs(pnl - expected_trigger) <= 0.5:  # 0.5% tolerance
            return {'pass': True, 'reason': f'Trailing triggered: peak {peak_pnl:.1f}%, exit {pnl:.1f}% (expected ~{expected_trigger:.1f}%)'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not near trailing trigger {expected_trigger:.1f}%'}

    elif exit_type == 'EXIT_TAKE_PROFIT':
        # Should hit +4% take profit
        if pnl >= 3.8 and pnl <= 4.2:  # Allow 0.2% tolerance
            return {'pass': True, 'reason': f'Take profit hit at {pnl:.1f}% (target: +4%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in TP range [3.8%, 4.2%]'}

    elif exit_type == 'EXIT_TIME_LIMIT':
        # Should be held for 1 hour
        # Check mock_position expected_hold_hours
        mock_pos = scenario.get('mock_position', {})
        hold_hours = mock_pos.get('expected_hold_hours', 1.0)
        
        # Calculate hold time from timestamps
        entry_time = datetime.fromisoformat(mock_pos.get('entry_time'))
        current_time = datetime.fromisoformat(scenario.get('current_market_data', {}).get('timestamp'))
        
        hold_duration = (current_time - entry_time).total_seconds() / 3600
        
        if hold_duration >= hold_hours:
            return {'pass': True, 'reason': f'Time limit reached: {hold_duration:.1f}h >= {hold_hours}h'}
        else:
            return {'pass': False, 'reason': f'Hold time {hold_duration:.1f}h < {hold_hours}h limit'}

    return {'pass': False, 'reason': f'Unknown exit type: {exit_type}'}

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run Balance Day Exit Tests')
    parser.add_argument('--scenarios', required=True, help='Path to scenarios JSON file')
    args = parser.parse_args()

    try:
        with open(args.scenarios, 'r') as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Error loading scenarios: {e}")
        sys.exit(1)

    print("="*80)
    print("🧪 EXIT TESTS - Balance Day Worker")
    print(f"📊 Testing {len(scenarios)} exit scenarios")
    print("🎯 Validating: SL (2%), TS (3%/1.5%), TP (4%), Time Limit (1h)")
    print("="*80)

    results = []
    passed = 0
    failed = 0
    skipped = 0

    for scenario in scenarios:
        result = simulate_exit_scenario(scenario)
        if result:
            results.append(result)
            if result['result'] == 'PASS':
                passed += 1
            elif result['result'] == 'FAIL':
                failed += 1
            else:
                skipped += 1

    print("\n" + "="*80)
    print("🏁 EXIT TESTS COMPLETE")
    print("="*80)
    print(f"Total Scenarios: {len(scenarios)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    
    pass_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
    print(f"\n✅ Pass Rate: {pass_rate:.1f}% (target: 100%)")

    # Save results
    output_file = 'replay_testing/test_results/balance_day_exit_test_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
    
    print(f"\n📄 Results saved to: {output_file}")

    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
