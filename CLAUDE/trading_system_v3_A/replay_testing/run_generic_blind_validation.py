#!/usr/bin/env python3
"""
Generic_01 Blind Test - Logical Validation

Validates Generic_01 worker filters against edge case parameters without requiring historical data.

Tests all safety filters:
- Price range: $2.00 - $50.00
- Volume: < 2.0x
- Daily return: > 0%
- Gap: <= 8%
- Quality: >= 40
"""

import json
import sys
from typing import Dict, Any

# Generic_01 Configuration
GENERIC_01_CONFIG = {
    'min_price': 2.00,
    'max_price': 50.00,
    'max_volume_ratio': 2.0,
    'min_daily_return': 0.0,
    'max_gap': 8.0,
    'min_quality_score': 40.0
}

def validate_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that a scenario would be correctly handled by Generic_01 worker filters"""
    scenario_id = scenario.get('id')
    expected_action = scenario.get('expected_action')
    
    print(f"\n[TEST] {scenario_id}")
    print(f"   Description: {scenario.get('description')}")
    print(f"   Expected: {expected_action}")
    
    scanner_data = scenario.get('mock_scanner_data', {})
    
    # Extract relevant fields
    current_price = scanner_data.get('current_price', 0)
    volume_ratio = scanner_data.get('volume_ratio', 0)
    daily_return_pct = scanner_data.get('daily_return_pct', 0)
    gap_percentage = scanner_data.get('gap_percentage', 0)
    quality_score = scanner_data.get('quality_score', 0)
    
    # Run through Generic_01 filters in order
    rejection_reason = None
    
    # Filter 1: Price range
    if current_price < GENERIC_01_CONFIG['min_price']:
        rejection_reason = f"Price ${current_price:.2f} < min ${GENERIC_01_CONFIG['min_price']:.2f}"
    elif current_price > GENERIC_01_CONFIG['max_price']:
        rejection_reason = f"Price ${current_price:.2f} > max ${GENERIC_01_CONFIG['max_price']:.2f}"
    
    # Filter 2: Volume (must be LOW, not high)
    elif volume_ratio >= GENERIC_01_CONFIG['max_volume_ratio']:
        rejection_reason = f"Volume {volume_ratio:.2f}x >= max {GENERIC_01_CONFIG['max_volume_ratio']:.2f}x (FOMO indicator)"
    
    # Filter 3: Daily return (must be positive)
    elif daily_return_pct <= GENERIC_01_CONFIG['min_daily_return']:
        rejection_reason = f"Daily return {daily_return_pct:.1f}% <= min {GENERIC_01_CONFIG['min_daily_return']:.1f}% (no momentum)"
    
    # Filter 4: Gap limit
    elif gap_percentage > GENERIC_01_CONFIG['max_gap']:
        rejection_reason = f"Gap {gap_percentage:.1f}% > max {GENERIC_01_CONFIG['max_gap']:.1f}% (parabolic)"
    
    # Filter 5: Quality score
    elif quality_score < GENERIC_01_CONFIG['min_quality_score']:
        rejection_reason = f"Quality {quality_score:.1f} < min {GENERIC_01_CONFIG['min_quality_score']:.1f}"
    
    # Determine result
    if expected_action == 'NO_ENTRY':
        if rejection_reason:
            print(f"   ✅ PASS: Would be rejected by Generic_01 worker")
            print(f"   Reason: {rejection_reason}")
            return {
                'scenario_id': scenario_id,
                'result': 'PASS',
                'reason': rejection_reason
            }
        else:
            print(f"   ❌ FAIL: Would NOT be rejected (filters passed)")
            return {
                'scenario_id': scenario_id,
                'result': 'FAIL',
                'reason': 'All filters passed unexpectedly'
            }
    else:  # ENTRY expected
        if rejection_reason:
            print(f"   ❌ FAIL: Would be rejected (expected entry)")
            print(f"   Reason: {rejection_reason}")
            return {
                'scenario_id': scenario_id,
                'result': 'FAIL',
                'reason': rejection_reason
            }
        else:
            print(f"   ✅ PASS: Would be accepted by Generic_01 worker")
            return {
                'scenario_id': scenario_id,
                'result': 'PASS',
                'reason': 'All filters passed as expected'
            }

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run Generic_01 Blind Test Logical Validation')
    parser.add_argument('--scenarios', required=True, help='Path to scenarios JSON file')
    args = parser.parse_args()
    
    try:
        with open(args.scenarios, 'r') as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Error loading scenarios: {e}")
        sys.exit(1)
    
    print("="*80)
    print("🧪 GENERIC_01 BLIND TEST - Logical Validation")
    print(f"📊 Testing {len(scenarios)} edge case scenarios")
    print("🎯 Validating: Price, Volume, Momentum, Gap, Quality")
    print("="*80)
    
    results = []
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        result = validate_scenario(scenario)
        results.append(result)
        
        if result['result'] == 'PASS':
            passed += 1
        else:
            failed += 1
    
    print("\n" + "="*80)
    print("🏁 GENERIC_01 BLIND TEST COMPLETE")
    print("="*80)
    print(f"Total Scenarios: {len(scenarios)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    pass_rate = (passed / len(scenarios)) * 100 if scenarios else 0
    print(f"\n✅ Pass Rate: {pass_rate:.1f}% (target: 100%)")
    
    # Save results
    import os
    output_file = 'replay_testing/test_results/generic_01_blind_validation_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
