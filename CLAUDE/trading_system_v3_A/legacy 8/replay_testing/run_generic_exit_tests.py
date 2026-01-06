#!/usr/bin/env python3
"""
Generic_01 Exit Tests - Logical Validation

Tests exit scenarios for Generic_01 worker based on defined parameters:
- Stop Loss: 8%
- Take Profit: 15%
- Break-Even: 6% activation
- Trailing Stop: 10% activation, 4% distance
- Time Limit: 6 hours
"""

import json
import sys
from datetime import datetime
from typing import Dict, Any

# Generic_01 Exit Parameters
GENERIC_01_EXIT_PARAMS = {
    'stop_loss_pct': 8.0,
    'take_profit_pct': 15.0,
    'breakeven_activation_pct': 6.0,
    'trailing_activation': 10.0,
    'trailing_distance': 4.0,
    'max_hold_hours': 6.0
}

def validate_exit_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single exit scenario"""
    scenario_id = scenario.get('id')
    expected_action = scenario.get('expected_action')
    entry_price = scenario.get('entry_price', 0)
    exit_price = scenario.get('exit_price', 0)
    peak_price = scenario.get('peak_price', entry_price)
    
    print(f"\n[TEST] {scenario_id}")
    print(f"   Description: {scenario.get('description')}")
    print(f"   Expected: {expected_action}")
    print(f"   Entry: ${entry_price:.2f}")
    if peak_price > entry_price:
        print(f"   Peak: ${peak_price:.2f} (+{((peak_price/entry_price - 1)*100):.1f}%)")
    print(f"   Exit: ${exit_price:.2f} ({((exit_price/entry_price - 1)*100):+.1f}%)")
    
    result = _validate_exit_logic(expected_action, entry_price, exit_price, peak_price, scenario)
    
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
        'expected_pnl': scenario.get('expected_pnl', 0),
        'actual_pnl': round(((exit_price / entry_price) - 1) * 100, 1),
        'result': 'PASS' if result['pass'] else 'FAIL',
        'validation': result['reason']
    }

def _validate_exit_logic(exit_type: str, entry_price: float, exit_price: float, peak_price: float, scenario: Dict) -> Dict:
    """Validate exit logic matches Generic_01 parameters"""
    pnl = ((exit_price / entry_price) - 1) * 100
    peak_pnl = ((peak_price / entry_price) - 1) * 100
    
    if exit_type == 'EXIT_STOP_LOSS':
        # Should hit -8% stop loss
        if pnl <= -7.8 and pnl >= -8.2:
            return {'pass': True, 'reason': f'Stop loss triggered at {pnl:.1f}% (target: -8%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in SL range [-8.2%, -7.8%]'}
    
    elif exit_type == 'EXIT_BREAK_EVEN':
        # Should have peaked at +6%, then exit near 0%
        if peak_pnl < 5.8:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate BE (need +6%)'}
        if pnl < -1.0:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% is loss (BE should protect)'}
        if pnl >= 0 and pnl <= 1.0:
            return {'pass': True, 'reason': f'BE protected: peaked {peak_pnl:.1f}%, exited {pnl:.1f}%'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not near break-even'}
    
    elif exit_type == 'EXIT_TRAILING_STOP':
        # Should have peaked at +10%+, then dropped 4% of peak price
        if peak_pnl < 10.0:
            return {'pass': False, 'reason': f'Peak {peak_pnl:.1f}% did not activate trailing (need +10%)'}
        
        # Calculate expected exit: peak price - 4% of peak price
        expected_exit_price = peak_price * (1 - GENERIC_01_EXIT_PARAMS['trailing_distance'] / 100)
        expected_exit_pnl = ((expected_exit_price / entry_price) - 1) * 100
        
        if abs(pnl - expected_exit_pnl) <= 0.5:
            return {'pass': True, 'reason': f'Trailing triggered: peak {peak_pnl:.1f}%, exit {pnl:.1f}% (expected ~{expected_exit_pnl:.1f}%)'}
        else:
            return {'pass': False, 'reason': f'Exit {pnl:.1f}% not at expected trailing level {expected_exit_pnl:.1f}%'}
    
    elif exit_type == 'EXIT_TAKE_PROFIT':
        # Should hit +15% take profit
        if pnl >= 14.5 and pnl <= 15.5:
            return {'pass': True, 'reason': f'Take profit hit at {pnl:.1f}% (target: +15%)'}
        else:
            return {'pass': False, 'reason': f'PnL {pnl:.1f}% not in TP range [14.5%, 15.5%]'}
    
    elif exit_type == 'EXIT_TIME_LIMIT':
        # Check time limit
        entry_time = datetime.fromisoformat(scenario['mock_position']['entry_time'].replace('Z', '+00:00'))
        exit_time = datetime.fromisoformat(scenario['current_market_data']['timestamp'].replace('Z', '+00:00'))
        hold_hours = (exit_time - entry_time).total_seconds() / 3600
        
        if hold_hours >= GENERIC_01_EXIT_PARAMS['max_hold_hours']:
            return {'pass': True, 'reason': f'Time limit reached: {hold_hours:.1f}h >= {GENERIC_01_EXIT_PARAMS["max_hold_hours"]}h'}
        else:
            return {'pass': False, 'reason': f'Hold time {hold_hours:.1f}h < {GENERIC_01_EXIT_PARAMS["max_hold_hours"]}h limit'}
    
    return {'pass': False, 'reason': f'Unknown exit type: {exit_type}'}

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run Generic_01 Exit Test Validation')
    parser.add_argument('--scenarios', required=True, help='Path to exit scenarios JSON file')
    args = parser.parse_args()
    
    try:
        with open(args.scenarios, 'r') as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Error loading scenarios: {e}")
        sys.exit(1)
    
    print("="*80)
    print("🧪 EXIT TESTS - Generic_01 Worker")
    print(f"📊 Testing {len(scenarios)} exit scenarios")
    print("🎯 Validating: SL (8%), BE (6%), TS (10%/4%), TP (15%), Time (6h)")
    print("="*80)
    
    results = []
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        result = validate_exit_scenario(scenario)
        results.append(result)
        
        if result['result'] == 'PASS':
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*80)
    print("🏁 EXIT TESTS COMPLETE")
    print("="*80)
    print(f"Total Scenarios: {len(scenarios)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: 0")
    
    pass_rate = (passed / len(scenarios)) * 100 if scenarios else 0
    print(f"\n✅ Pass Rate: {pass_rate:.1f}% (target: 100%)")
    
    # Save results
    import os
    output_file = 'replay_testing/test_results/generic_01_exit_test_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'total_scenarios': len(scenarios),
            'passed': passed,
            'failed': failed,
            'skipped': 0,
            'pass_rate': pass_rate,
            'results': results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
