#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick Test Runner - Scanner + Strategies Morning Session
========================================================

Ejecuta pruebas rápidas para verificar que el scanner + estrategias 
funcionan correctamente en las primeras horas de mercado SIN esperar pullback.

Usage:
    python run_morning_test.py
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta, time

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    # Import strategies
    from strategies.orb_strategy import ORBStrategy
    from strategies.macdv_strategy import MACDVStrategy
    from strategies.gap_go_strategy import GapGoStrategy
    from strategies.vwap_strategy import VWAPSmallcapsStrategy
    from core.interfaces import Signal, SignalType, MarketData
    import numpy as np
    
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

async def quick_test():
    """Quick test to verify strategies work without pullback"""
    
    print("\n" + "="*60)
    print("🚀 QUICK SCANNER + STRATEGIES TEST")
    print("="*60)
    
    # Test configuration
    symbol = 'TEST_STOCK'
    test_start = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    
    # Initialize strategies
    print("\n📋 Initializing strategies...")
    strategies = [
        ('ORB', ORBStrategy()),
        ('MACDV', MACDVStrategy()),
        ('Gap&Go', GapGoStrategy()),
        ('VWAP', VWAPSmallcapsStrategy())
    ]
    
    for name, strategy in strategies:
        await strategy._initialize_strategy()
        print(f"  ✅ {name} Strategy initialized")
    
    # Create breakout scenario
    print(f"\n📊 Creating breakout scenario for {symbol}...")
    bars = []
    base_price = 10.0
    
    # Generate 20 bars with breakout at bar 10
    for i in range(20):
        timestamp = test_start + timedelta(minutes=i)
        
        if i == 10:  # Breakout moment
            current_price = base_price * 1.06  # 6% breakout
            volume = 500000  # High volume
            print(f"  📈 Breakout bar created: +6% @ {timestamp.strftime('%H:%M')}")
        elif i > 10:
            # Continue momentum (no pullback)
            current_price = base_price * 1.04  # Maintain most gains
            volume = 200000
        else:
            current_price = base_price
            volume = 100000
        
        # Create realistic OHLC
        bar = MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=current_price * 0.999,
            high=current_price * 1.002,
            low=current_price * 0.998,
            close=current_price,
            volume=volume,
            vwap=current_price
        )
        bars.append(bar)
        base_price = current_price
    
    # Test each strategy
    print(f"\n🎯 Testing strategies with breakout data...")
    results = {}
    
    for strategy_name, strategy in strategies:
        print(f"\n--- Testing {strategy_name} Strategy ---")
        
        signals_count = 0
        first_signal_bar = None
        
        for i, bar in enumerate(bars):
            # Add bar to strategy history
            if symbol not in strategy.bars_history:
                strategy.bars_history[symbol] = []
            strategy.bars_history[symbol].append(bar)
            
            # Analyze bar
            try:
                signal = await strategy._analyze_bar(bar)
                
                if signal:
                    signals_count += 1
                    if first_signal_bar is None:
                        first_signal_bar = i
                    
                    print(f"  ✅ Signal #{signals_count}: {signal.signal_type.value} @ ${signal.price:.2f}")
                    print(f"     Bar #{i}, Time: {bar.timestamp.strftime('%H:%M')}")
                    
                    # Check if signal is immediate (not waiting for pullback)
                    if i <= 12:  # Should signal within 2 bars of breakout
                        print(f"     🚀 IMMEDIATE ENTRY - No pullback wait!")
                    
            except Exception as e:
                print(f"  ⚠️  Error analyzing bar {i}: {e}")
        
        results[strategy_name] = {
            'signals': signals_count,
            'first_signal_bar': first_signal_bar,
            'immediate_entry': first_signal_bar is not None and first_signal_bar <= 12
        }
        
        if signals_count == 0:
            print(f"  ❌ No signals generated")
        else:
            print(f"  📊 Total signals: {signals_count}")
    
    # Summary
    print("\n" + "="*60)
    print("📋 TEST RESULTS SUMMARY")
    print("="*60)
    
    successful_strategies = 0
    immediate_entry_strategies = 0
    
    for strategy_name, result in results.items():
        status = "✅" if result['signals'] > 0 else "❌"
        immediate = "🚀" if result['immediate_entry'] else "⏳"
        
        print(f"{status} {strategy_name}: {result['signals']} signals")
        
        if result['first_signal_bar'] is not None:
            print(f"   {immediate} First signal at bar #{result['first_signal_bar']}")
            
        if result['signals'] > 0:
            successful_strategies += 1
            
        if result['immediate_entry']:
            immediate_entry_strategies += 1
    
    print(f"\n📊 OVERALL RESULTS:")
    print(f"   ✅ Strategies working: {successful_strategies}/{len(strategies)}")
    print(f"   🚀 Immediate entry: {immediate_entry_strategies}/{len(strategies)}")
    
    if immediate_entry_strategies >= len(strategies) * 0.75:  # 75% success rate
        print(f"\n🎉 SUCCESS: Scanner + Strategies working correctly!")
        print(f"   - Strategies generate signals WITHOUT waiting for pullback")
        print(f"   - Fast execution during morning breakouts")
        return True
    else:
        print(f"\n⚠️  NEEDS ATTENTION: Some strategies may still wait for pullback")
        return False

def main():
    """Main test runner"""
    print("Scanner + Strategies Morning Test Runner")
    print("Testing immediate entry (no pullback wait)...")
    
    try:
        success = asyncio.run(quick_test())
        
        if success:
            print(f"\n✅ Test completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Test completed with issues!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()