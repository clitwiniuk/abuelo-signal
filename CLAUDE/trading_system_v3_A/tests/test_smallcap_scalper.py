#!/usr/bin/env python3
"""
Quick test for Smallcap Momentum Scalper Worker
"""

import sys
import asyncio
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, '.')

from strategies.workers.smallcap_momentum_scalper_logic import SmallcapMomentumScalperLogic
from configparser import ConfigParser


async def test_worker():
    """Test worker initialization and basic functionality"""

    print("\n" + "="*80)
    print("🧪 TESTING SMALLCAP MOMENTUM SCALPER WORKER")
    print("="*80 + "\n")

    # Load config
    config = ConfigParser()
    config.read('../config.ini')

    # Initialize worker
    worker = SmallcapMomentumScalperLogic(config=config)

    print("\n✅ Worker initialized successfully\n")

    # Test with fake opportunity
    ny_tz = pytz.timezone('US/Eastern')
    now = datetime.now(ny_tz)

    # Create test bars (simulating real market data)
    test_bars = []
    for i in range(25):
        bar = {
            'timestamp': now,
            'open': 5.0 + (i * 0.1),
            'high': 5.1 + (i * 0.1),
            'low': 4.9 + (i * 0.1),
            'close': 5.0 + (i * 0.1),
            'volume': 10000 * (i + 1)  # Increasing volume
        }
        test_bars.append(bar)

    # Test opportunity 1: Good setup (should pass)
    print("📊 Test 1: Good Setup (Volume explosion, breakout, RSI good)")
    print("-" * 80)

    opportunity1 = {
        'symbol': 'TEST',
        'price': 7.50,  # Current price (breaking high)
        'bars': test_bars
    }

    result1 = await worker.should_enter(opportunity1)
    print(f"Result: {'✅ ENTRY SIGNAL' if result1 else '❌ REJECTED'}\n")

    # Test opportunity 2: Price too low
    print("📊 Test 2: Price Too Low (should reject)")
    print("-" * 80)

    opportunity2 = {
        'symbol': 'PENNY',
        'price': 0.25,  # Below min_price (0.50)
        'bars': test_bars
    }

    result2 = await worker.should_enter(opportunity2)
    print(f"Result: {'✅ ENTRY SIGNAL' if result2 else '❌ REJECTED (Expected)'}\n")

    # Test opportunity 3: Low volume
    print("📊 Test 3: Low Volume (should reject)")
    print("-" * 80)

    # Create bars with low volume
    low_vol_bars = []
    for i in range(25):
        bar = {
            'timestamp': now,
            'open': 5.0,
            'high': 5.1,
            'low': 4.9,
            'close': 5.0,
            'volume': 1000  # Constant low volume (no explosion)
        }
        low_vol_bars.append(bar)

    opportunity3 = {
        'symbol': 'LOWVOL',
        'price': 5.10,
        'bars': low_vol_bars
    }

    result3 = await worker.should_enter(opportunity3)
    print(f"Result: {'✅ ENTRY SIGNAL' if result3 else '❌ REJECTED (Expected)'}\n")

    # Test anti-overtrading
    print("📊 Test 4: Anti-Overtrading (same symbol twice)")
    print("-" * 80)

    if result1:
        # Simulate position opened
        await worker.on_position_opened('TEST', 7.50, 100)

        # Try again (should reject - already traded)
        result4 = await worker.should_enter(opportunity1)
        print(f"Result: {'⚠️ UNEXPECTED ENTRY' if result4 else '✅ REJECTED (Expected - already traded today)'}\n")

    # Test stop prices
    print("📊 Test 5: Stop Prices Calculation")
    print("-" * 80)

    entry_price = 5.00
    stops = worker.get_stop_prices(entry_price, 'BUY')

    print(f"Entry Price: ${entry_price:.2f}")
    print(f"Stop Loss:   ${stops['stop_loss']:.2f} (-{((entry_price - stops['stop_loss']) / entry_price * 100):.1f}%)")
    print(f"Take Profit: ${stops['take_profit']:.2f} (+{((stops['take_profit'] - entry_price) / entry_price * 100):.1f}%)")
    print(f"Risk/Reward: 1:{(stops['take_profit'] - entry_price) / (entry_price - stops['stop_loss']):.2f}\n")

    print("="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(test_worker())
