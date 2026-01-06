#!/usr/bin/env python3
"""
Test script for fixed real strategy backtester
"""

import asyncio
from fixed_real_strategy_backtester import FixedRealStrategyBacktester

async def test_fixed_backtester():
    print("🎯 TESTING FIXED REAL STRATEGY BACKTESTER")
    print("=" * 60)
    
    backtester = FixedRealStrategyBacktester()
    
    if not backtester.load_events_metadata():
        print("❌ No se pudieron cargar metadatos")
        return
    
    # Test con MACDVStrategy
    print("\n📊 Testing MACDVStrategy...")
    success = await backtester.run_mass_backtest('MACDVStrategy', max_events=10)
    
    if success:
        stats = backtester.analyze_results()
        backtester.print_performance_report(stats)
    
    print("\n" + "="*60)
    
    # Test con VolumeBreakoutStrategy
    print("\n📊 Testing VolumeBreakoutStrategy...")
    success2 = await backtester.run_mass_backtest('VolumeBreakoutStrategy', max_events=10)
    
    if success2:
        stats2 = backtester.analyze_results()
        backtester.print_performance_report(stats2)

if __name__ == "__main__":
    asyncio.run(test_fixed_backtester())