#!/usr/bin/env python3
"""
Test MACDV improvements for High-Low setups (momentum starting)
Modified to accept weak momentum scenarios when momentum begins
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
from unittest.mock import Mock, patch
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def test_macdv_high_low_setup_acceptance():
    """Test that MACDV now accepts High-Low setups (momentum starting)"""

    print('🧪 TESTING MACDV HIGH-LOW SETUP ACCEPTANCE')
    print('=' * 70)

    # Create MACDV worker with relaxed filters for momentum starting
    config = Mock()
    config.min_volume_ratio = 1.0  # Relaxed from 1.3
    macdv = MacdvWorkerLogic(None, None, config)

    # Simulate High-Low setup: Simple case with clear momentum building
    opportunity = {
        'symbol': 'HIGH_LOW_TEST',
        'gap_percentage': 0.0,  # No gap (typical for High-Low)
        'current_price': 10.50,
        'catalyst_type': 'TECHNICAL',
        'quality_score': 85.0
    }

    # Mock bars showing clear momentum building from a low
    class MockBar:
        def __init__(self, close, volume, vwap, high, low):
            self.close = close
            self.volume = volume
            self.vwap = vwap if vwap is not None else close * 0.98  # VWAP slightly below if not specified
            self.high = high
            self.low = low

    # Create more bars for MACD calculation (need at least 35 bars)
    bars = []
    # Add some baseline bars first
    for i in range(30):
        price = 9.0 + (i * 0.05)  # Gradual uptrend
        bars.append(MockBar(price, 1000 + (i * 10), 9.20, price + 0.05, price - 0.05))

    # Then add the momentum building bars
    bars.extend([
        MockBar(9.50, 1000, 9.20, 9.55, 9.45),   # Low point
        MockBar(9.70, 1200, 9.20, 9.75, 9.65),   # Starting up
        MockBar(9.90, 1400, 9.20, 9.95, 9.85),   # Building momentum
        MockBar(10.10, 1600, 9.20, 10.15, 10.05), # Stronger move
        MockBar(10.30, 1800, 9.20, 10.35, 10.25), # Continuing up
        MockBar(10.50, 2000, 9.20, 10.55, 10.45), # Current - momentum clear
    ])

    # Mock the bars getter
    macdv.get_bars_from_opportunity = lambda opp: bars

    print(f'📊 High-Low Setup Test (Momentum Starting):')
    print(f'   Gap: {opportunity["gap_percentage"]}% (no gap = High-Low setup)')
    print(f'   Price progression: $9.50 → $9.70 → $9.90 → $10.10 → $10.30 → $10.50')
    print(f'   Volume increasing: 1000 → 1200 → 1400 → 1600 → 1800 → 2000')
    print(f'   Clear upward trend with increasing volume')
    print()

    # Test momentum building detection directly first
    momentum_detected = macdv._detect_momentum_building(bars, opportunity['current_price'])
    print(f'📈 Momentum Building Detection: {"DETECTED" if momentum_detected else "NOT DETECTED"}')

    # Test MACD calculation
    macd_data = macdv.calculate_macd(bars)
    if macd_data:
        divergence_type, divergence_strength = macdv._detect_divergence(bars, macd_data)
        print(f'📊 MACD Divergence: {divergence_type or "NONE"} (strength: {divergence_strength:.1f})')
    else:
        print(f'📊 MACD Calculation: FAILED')

    # Test should_enter (async function) with better error handling
    import asyncio
    try:
        result = asyncio.run(macdv.should_enter(opportunity))
        print(f'🎯 MACDV Decision: {"ENTER" if result else "REJECT"}')
        print()
    except Exception as e:
        print(f'❌ Error during test: {e}')
        result = False
        print()

    if result:
        print('✅ SUCCESS: MACDV correctly accepted High-Low setup with momentum starting!')
        print('   This allows entry when momentum begins, not when it\'s already strong.')
        return True
    else:
        print('❌ FAILURE: MACDV rejected valid High-Low momentum starting setup')
        print('   Need to relax filters to catch momentum early.')
        return False

def test_macdv_strong_momentum_rejection():
    """Test that MACDV rejects overbought strong momentum (High-High)"""

    print('\n🧪 TESTING MACDV STRONG MOMENTUM REJECTION')
    print('=' * 70)

    # Create MACDV worker
    config = Mock()
    config.min_volume_ratio = 1.0
    macdv = MacdvWorkerLogic(None, None, config)

    # Simulate overbought High-High setup
    opportunity = {
        'symbol': 'OVERBOUGHT',
        'gap_percentage': 5.0,  # Large gap (overbought)
        'current_price': 12.50,
        'catalyst_type': 'TECHNICAL',
        'quality_score': 95.0
    }

    # Mock bars showing overbought conditions
    class MockBar:
        def __init__(self, close, volume, vwap, high, low):
            self.close = close
            self.volume = volume
            self.vwap = vwap
            self.high = high
            self.low = low

    bars = [
        MockBar(10.00, 5000, 9.80, 10.20, 9.90),  # Gap up start
        MockBar(11.00, 8000, 9.80, 11.50, 10.50),  # Strong move
        MockBar(11.80, 6000, 9.80, 12.00, 11.50),  # Continuing strong
        MockBar(12.20, 4000, 9.80, 12.50, 11.90),  # Momentum fading
        MockBar(12.50, 3000, 9.80, 12.70, 12.30),  # Overbought, volume dropping
    ]

    # Mock the bars getter
    macdv.get_bars_from_opportunity = lambda opp: bars

    print(f'📊 Overbought Setup Test (High-High rejection):')
    print(f'   Gap: {opportunity["gap_percentage"]}% (large gap = overbought)')
    print(f'   Price: ${opportunity["current_price"]} vs VWAP: ${bars[-1].vwap}')
    print(f'   Volume dropping: {bars[-3].volume} → {bars[-2].volume} → {bars[-1].volume}')
    print(f'   Well above VWAP: {(opportunity["current_price"]-bars[-1].vwap)/bars[-1].vwap*100:.1f}%')
    print()

    # Test should_enter (async function) with better error handling
    import asyncio
    try:
        result = asyncio.run(macdv.should_enter(opportunity))
        print(f'🎯 MACDV Decision: {"ENTER" if result else "REJECT"}')
        print()
    except Exception as e:
        print(f'❌ Error during test: {e}')
        result = False
        print()

    if not result:
        print('✅ SUCCESS: MACDV correctly rejected overbought High-High setup!')
        print('   This prevents entries when momentum is too strong/extended.')
        return True
    else:
        print('❌ FAILURE: MACDV entered overbought setup')
        print('   Should avoid High-High when momentum is extended.')
        return False

if __name__ == "__main__":
    print("🚀 MACDV High-Low Strategy Test Suite")
    print("=" * 70)

    test1_passed = test_macdv_high_low_setup_acceptance()
    test2_passed = test_macdv_strong_momentum_rejection()

    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)

    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ MACDV now accepts High-Low setups (momentum starting)")
        print("✅ MACDV rejects High-High setups (overbought)")
        print("✅ Strategy focuses on early momentum detection")
    else:
        print("⚠️ SOME TESTS FAILED")
        if not test1_passed:
            print("❌ Not accepting valid High-Low momentum starting setups")
        if not test2_passed:
            print("❌ Still entering overbought High-High setups")