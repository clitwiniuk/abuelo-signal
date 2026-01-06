#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug Test - Verificar por qué las estrategias no generan señales
================================================================

Este script debuggea por qué las estrategias no están generando señales
y verifica si eliminamos correctamente la lógica de pullback.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import numpy as np

# Add current directory to path  
sys.path.insert(0, os.getcwd())

from strategies.orb_strategy import ORBStrategy
from strategies.macdv_strategy import MACDVStrategy
from strategies.gap_go_strategy import GapGoStrategy
from strategies.vwap_strategy import VWAPSmallcapsStrategy
from core.interfaces import Signal, SignalType, MarketData

async def debug_orb_strategy():
    """Debug ORB strategy specifically"""
    print("\n" + "="*50)
    print("🔍 DEBUGGING ORB STRATEGY")
    print("="*50)
    
    strategy = ORBStrategy()
    await strategy._initialize_strategy()
    
    symbol = 'DEBUG_STOCK'
    base_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    base_price = 5.00  # Price in ORB range ($2-$15)
    
    print(f"📊 Creating ORB scenario for {symbol}...")
    print(f"   Base price: ${base_price:.2f}")
    print(f"   Opening range: 15 minutes")
    
    # Create opening range (first 15 minutes)
    print(f"\n📈 Creating opening range (9:30-9:45)...")
    range_high = base_price
    range_low = base_price
    
    for minute in range(15):
        timestamp = base_time + timedelta(minutes=minute)
        
        # Random price movement within range
        price_variation = np.random.uniform(-0.02, 0.02)
        current_price = base_price * (1 + price_variation)
        
        range_high = max(range_high, current_price)
        range_low = min(range_low, current_price)
        
        bar = MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=current_price * 0.999,
            high=current_price * 1.001,
            low=current_price * 0.999,
            close=current_price,
            volume=50000 + int(np.random.uniform(0, 20000)),  # Good volume
            vwap=current_price
        )
        
        if symbol not in strategy.bars_history:
            strategy.bars_history[symbol] = []
        strategy.bars_history[symbol].append(bar)
        
        # Try to analyze (should not generate signal during range definition)
        signal = await strategy._analyze_bar(bar)
        if signal:
            print(f"   ⚠️  Unexpected signal during range definition at {timestamp}")
    
    print(f"   Range defined: ${range_low:.2f} - ${range_high:.2f}")
    range_size = (range_high - range_low) / range_low
    print(f"   Range size: {range_size*100:.1f}%")
    
    # Create breakout bar (minute 16)
    breakout_time = base_time + timedelta(minutes=16)
    breakout_price = range_high * 1.015  # 1.5% above range high
    
    print(f"\n🚀 Creating breakout bar at 9:46...")
    print(f"   Breakout price: ${breakout_price:.2f} (+{((breakout_price/range_high)-1)*100:.1f}%)")
    
    breakout_bar = MarketData(
        symbol=symbol,
        timestamp=breakout_time,
        open=range_high * 1.005,
        high=breakout_price * 1.002,
        low=range_high * 1.001,
        close=breakout_price,
        volume=200000,  # High breakout volume
        vwap=breakout_price
    )
    
    strategy.bars_history[symbol].append(breakout_bar)
    
    # This should generate a signal now
    print(f"\n🎯 Testing breakout analysis...")
    signal = await strategy._analyze_bar(breakout_bar)
    
    if signal:
        print(f"   ✅ SIGNAL GENERATED!")
        print(f"      Type: {signal.signal_type.value}")
        print(f"      Price: ${signal.price:.2f}")
        print(f"      Strength: {signal.strength:.2f}")
        print(f"      Time: {signal.timestamp.strftime('%H:%M')}")
        return True
    else:
        print(f"   ❌ NO SIGNAL GENERATED")
        print(f"   🔍 Checking conditions...")
        
        # Check opening range
        if symbol in strategy.opening_ranges:
            or_data = strategy.opening_ranges[symbol]
            print(f"      Opening range defined: {or_data.get('range_defined', False)}")
            print(f"      Range size: {or_data.get('range_size', 0)*100:.1f}%")
            print(f"      Data quality score: {or_data.get('data_quality_score', 0)}")
        else:
            print(f"      ❌ No opening range data found")
        
        return False

async def debug_macdv_strategy():
    """Debug MACDV strategy"""
    print("\n" + "="*50)
    print("🔍 DEBUGGING MACDV STRATEGY")
    print("="*50)
    
    strategy = MACDVStrategy()
    await strategy._initialize_strategy()
    
    symbol = 'MACDV_DEBUG'
    base_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)  # After first 30min
    base_price = 8.00  # In MACDV range
    
    print(f"📊 Creating MACDV crossover scenario...")
    print(f"   Base price: ${base_price:.2f}")
    print(f"   Need {strategy._parameters['macd_slow']} bars minimum")
    
    # Create enough history for MACD calculation
    min_bars = strategy._parameters['macd_slow'] + 10  # 13 + 10 = 23 bars
    
    for minute in range(min_bars):
        timestamp = base_time + timedelta(minutes=minute)
        
        if minute < min_bars - 5:
            # Downtrend (MACD below signal)
            trend = -0.001
        else:
            # Uptrend starts (should create crossover)
            trend = 0.002
            
        current_price = base_price * (1 + trend * minute)
        
        bar = MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=current_price * 0.999,
            high=current_price * 1.002,
            low=current_price * 0.998,
            close=current_price,
            volume=80000 + int(np.random.uniform(0, 40000)),  # Good volume
            vwap=current_price
        )
        
        if symbol not in strategy.bars_history:
            strategy.bars_history[symbol] = []
        strategy.bars_history[symbol].append(bar)
        
        # Check for signal on last few bars
        if minute >= min_bars - 3:
            signal = await strategy._analyze_bar(bar)
            if signal:
                print(f"   ✅ SIGNAL GENERATED at bar {minute}!")
                print(f"      Type: {signal.signal_type.value}")
                print(f"      Price: ${signal.price:.2f}")
                print(f"      Time: {signal.timestamp.strftime('%H:%M')}")
                return True
    
    print(f"   ❌ NO SIGNAL GENERATED")
    print(f"   🔍 Checking MACD values...")
    
    # Check last MACD calculation
    if symbol in strategy.last_macd_values:
        macd_data = strategy.last_macd_values[symbol]
        print(f"      MACD: {macd_data.get('macd', 0):.4f}")
        print(f"      Signal: {macd_data.get('signal', 0):.4f}")
        print(f"      Histogram: {macd_data.get('histogram', 0):.4f}")
        
        if macd_data.get('macd', 0) > macd_data.get('signal', 0):
            print(f"      ✅ MACD above signal line")
        else:
            print(f"      ❌ MACD below signal line")
    
    return False

async def main():
    """Main debug function"""
    print("🔧 STRATEGY DEBUG TEST")
    print("="*60)
    print("Checking why strategies aren't generating signals...")
    
    results = {}
    
    # Test ORB
    try:
        results['ORB'] = await debug_orb_strategy()
    except Exception as e:
        print(f"❌ ORB Strategy error: {e}")
        results['ORB'] = False
    
    # Test MACDV  
    try:
        results['MACDV'] = await debug_macdv_strategy()
    except Exception as e:
        print(f"❌ MACDV Strategy error: {e}")
        results['MACDV'] = False
    
    # Summary
    print("\n" + "="*60)
    print("🎯 DEBUG RESULTS SUMMARY")
    print("="*60)
    
    working_count = sum(1 for result in results.values() if result)
    
    for strategy_name, working in results.items():
        status = "✅ WORKING" if working else "❌ NOT WORKING"
        print(f"   {strategy_name}: {status}")
    
    print(f"\n📊 Overall: {working_count}/{len(results)} strategies working")
    
    if working_count > 0:
        print(f"\n🎉 SUCCESS: At least some strategies are generating signals!")
        print(f"   - Strategies are NOT waiting for pullback")
        print(f"   - Immediate entry logic is working")
    else:
        print(f"\n⚠️  ISSUE: Strategies need more realistic test data")
        print(f"   - May need more history bars")
        print(f"   - May need better price/volume patterns")
        print(f"   - Filters may be too strict")

if __name__ == '__main__':
    asyncio.run(main())