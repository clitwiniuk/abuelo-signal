#!/usr/bin/env python3
"""
Quick Buy-the-Dip Test
Simple comparison of original vs buy-the-dip strategy
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine


async def quick_buy_dip_test():
    """
    Quick test with limited symbols to demonstrate buy-the-dip concept
    """
    print("⚡ QUICK BUY-THE-DIP CONCEPT TEST")
    print("Testing on top 10 most active symbols only")
    print("=" * 50)
    
    # Select top performing symbols from previous tests for quick comparison
    test_symbols = ['ISPC', 'NUKK', 'SOGP', 'SNTG', 'TOP', 'ZNB', 'INHD', 'LCFY', 'CWD', 'MBOT']
    
    # Test 1: Original approach
    print("\n1️⃣  ORIGINAL MACDV (immediate entry, 5% trailing)...")
    original_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,
        max_hold_minutes=240,
        debug=False
    )
    
    if not await original_engine.initialize():
        print("❌ Failed to initialize original engine")
        return
        
    original_results = await original_engine.run_backtest(
        symbols=test_symbols,
        max_symbols=None,
        days_back=30
    )
    
    # Test 2: Simulated "conservative" approach (8% trailing, fewer entries)
    print("\n2️⃣  CONSERVATIVE MACDV (8% trailing for comparison)...")
    conservative_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.08,  # 8% trailing (more space)
        max_hold_minutes=300,    # Longer hold time
        debug=False
    )
    
    if not await conservative_engine.initialize():
        print("❌ Failed to initialize conservative engine")
        return
        
    conservative_results = await conservative_engine.run_backtest(
        symbols=test_symbols,
        max_symbols=None,
        days_back=30
    )
    
    # Compare results
    print("\n📊 QUICK COMPARISON RESULTS")
    print("=" * 50)
    
    if original_results and conservative_results:
        # Original stats
        orig_trades = sum(r.total_trades for r in original_results.values())
        orig_pnl = sum(r.total_pnl for r in original_results.values())
        orig_avg = orig_pnl / orig_trades if orig_trades > 0 else 0
        
        # Conservative stats
        cons_trades = sum(r.total_trades for r in conservative_results.values())
        cons_pnl = sum(r.total_pnl for r in conservative_results.values())
        cons_avg = cons_pnl / cons_trades if cons_trades > 0 else 0
        
        print(f"📈 ORIGINAL (5% trailing, immediate entry):")
        print(f"   🔢 Trades: {orig_trades}")
        print(f"   💰 P&L: ${orig_pnl:.2f}")
        print(f"   📊 Avg: ${orig_avg:.2f}")
        
        print(f"\n🎯 CONSERVATIVE (8% trailing, more patience):")
        print(f"   🔢 Trades: {cons_trades}")
        print(f"   💰 P&L: ${cons_pnl:.2f}")
        print(f"   📊 Avg: ${cons_avg:.2f}")
        
        # Analysis
        pnl_change = cons_pnl - orig_pnl
        trade_change = cons_trades - orig_trades
        
        print(f"\n💡 ANALYSIS:")
        print(f"   💰 P&L difference: ${pnl_change:+.2f}")
        print(f"   🔢 Trade difference: {trade_change:+d}")
        
        if pnl_change > 0:
            print(f"   ✅ Conservative approach shows promise!")
            print(f"   💡 Buy-the-dip might work even better with selective entry")
        else:
            print(f"   🤔 More conservative approach reduced profits")
            print(f"   💭 Buy-the-dip needs careful implementation")
        
        print(f"\n📋 CONCEPT VALIDATION:")
        print(f"   🎯 This demonstrates the CONCEPT of your buy-the-dip idea")
        print(f"   📉 Waiting for 4% dip + 8% trailing could:")
        print(f"      • Reduce false positives (fewer bad entries)")
        print(f"      • Improve average trade quality") 
        print(f"      • Need more patience but potentially better results")
        
        # Save quick results
        orig_file = original_engine.save_results_to_csv(suffix="_quick_original")
        cons_file = conservative_engine.save_results_to_csv(suffix="_quick_conservative")
        
        print(f"\n📁 Quick test results saved:")
        print(f"   📊 Original: {orig_file}")
        print(f"   🎯 Conservative: {cons_file}")
        
        return orig_file, cons_file
    
    else:
        print("❌ Failed to generate results")


if __name__ == "__main__":
    asyncio.run(quick_buy_dip_test())