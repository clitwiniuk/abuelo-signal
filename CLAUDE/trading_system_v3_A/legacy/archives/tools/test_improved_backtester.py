#!/usr/bin/env python3
"""
Test script for improved backtester
"""

import asyncio
from improved_strategy_backtester import ImprovedStrategyBacktester

async def test_backtester():
    print("🎯 TESTING IMPROVED STRATEGY BACKTESTER")
    print("=" * 60)
    
    backtester = ImprovedStrategyBacktester()
    
    if not backtester.load_metadata():
        print("❌ No se pudieron cargar eventos de calidad")
        return
    
    # Test con una estrategia
    print("\n📊 Testing Volume_Breakout strategy...")
    stats = await backtester.run_backtest('Volume_Breakout', max_events=20)
    backtester.print_enhanced_results(stats)
    
    print("\n📊 Testing Explosive_Scalp strategy...")  
    stats2 = await backtester.run_backtest('Explosive_Scalp', max_events=20)
    backtester.print_enhanced_results(stats2)

if __name__ == "__main__":
    asyncio.run(test_backtester())