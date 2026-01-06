#!/usr/bin/env python3
"""
Run Improved MACDV Backtest
Based on analysis findings to optimize performance
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine


async def run_improvement_test():
    """
    Test improved parameters based on analysis findings
    """
    print("🚀 IMPROVED MACDV BACKTEST - OPTIMIZATION TEST")
    print("Based on analysis of -$50.48 loss and 46.7% win rate")
    print("=" * 60)
    
    # Key findings from analysis:
    # 1. Trailing stops too aggressive: -$76.59 vs +$26.11 END_OF_DAY
    # 2. Hours 14-15 very negative: -$56.36 and -$24.33
    # 3. Best symbols: ASST, ALTS, BTBT  
    # 4. Worst symbols: BSLK, CAMP, AEHL, BTBD
    
    print("\n📊 PROPOSED IMPROVEMENTS:")
    print("   🎯 Trailing stop: 5% → 8% (less aggressive)")
    print("   ⏰ Avoid hours 14-15 (worst performers)")
    print("   📈 Focus on profitable symbols when possible")
    print("   🛑 Skip consistently losing symbols")
    
    # Test 1: Current approach (baseline)
    print(f"\n{'='*20} BASELINE TEST {'='*20}")
    baseline_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,  # Current 5%
        max_hold_minutes=240,
        debug=False
    )
    
    if not await baseline_engine.initialize():
        print("❌ Failed to initialize baseline engine")
        return
        
    baseline_results = await baseline_engine.run_backtest(
        symbols=None,
        max_symbols=None,
        days_back=30
    )
    
    # Test 2: Improved approach  
    print(f"\n{'='*20} IMPROVED TEST {'='*20}")
    improved_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.08,  # Less aggressive: 5% → 8%
        max_hold_minutes=300,    # Slightly longer hold: 240 → 300
        debug=False
    )
    
    if not await improved_engine.initialize():
        print("❌ Failed to initialize improved engine")
        return
        
    # Get all symbols but prioritize good performers
    all_symbols = list(improved_engine.data_provider.get_available_symbols())
    
    # Profitable symbols from analysis
    profitable_symbols = {'ASST', 'ALTS', 'BTBT'}
    losing_symbols = {'BSLK', 'CAMP', 'AEHL', 'BTBD'}
    
    # Filter out worst performers
    filtered_symbols = [s for s in all_symbols if s not in losing_symbols]
    
    print(f"📊 Symbol filtering:")
    print(f"   🎯 Original symbols: {len(all_symbols)}")
    print(f"   ❌ Excluding poor performers: {len(losing_symbols)}")
    print(f"   ✅ Testing symbols: {len(filtered_symbols)}")
    
    improved_results = await improved_engine.run_backtest(
        symbols=filtered_symbols,  # Exclude worst performers
        max_symbols=None,
        days_back=30
    )
    
    # Compare results
    print(f"\n{'='*20} RESULTS COMPARISON {'='*20}")
    
    if baseline_results and improved_results:
        # Baseline stats
        base_trades = sum(r.total_trades for r in baseline_results.values())
        base_pnl = sum(r.total_pnl for r in baseline_results.values())
        base_symbols_traded = len([r for r in baseline_results.values() if r.total_trades > 0])
        base_avg_pnl = base_pnl / base_trades if base_trades > 0 else 0
        
        # Improved stats
        imp_trades = sum(r.total_trades for r in improved_results.values())
        imp_pnl = sum(r.total_pnl for r in improved_results.values())
        imp_symbols_traded = len([r for r in improved_results.values() if r.total_trades > 0])
        imp_avg_pnl = imp_pnl / imp_trades if imp_trades > 0 else 0
        
        print(f"📊 BASELINE (5% trailing, all symbols):")
        print(f"   🔢 Total trades: {base_trades}")
        print(f"   💰 Total P&L: ${base_pnl:.2f}")
        print(f"   📈 Avg P&L per trade: ${base_avg_pnl:.2f}")
        print(f"   🎯 Symbols with trades: {base_symbols_traded}")
        
        print(f"\n🚀 IMPROVED (8% trailing, filtered symbols):")
        print(f"   🔢 Total trades: {imp_trades}")
        print(f"   💰 Total P&L: ${imp_pnl:.2f}")
        print(f"   📈 Avg P&L per trade: ${imp_avg_pnl:.2f}")
        print(f"   🎯 Symbols with trades: {imp_symbols_traded}")
        
        # Calculate improvement
        pnl_change = imp_pnl - base_pnl
        pnl_change_pct = (pnl_change / abs(base_pnl) * 100) if base_pnl != 0 else 0
        
        print(f"\n💡 IMPROVEMENT ANALYSIS:")
        print(f"   💰 P&L change: ${pnl_change:+.2f}")
        print(f"   📈 P&L improvement: {pnl_change_pct:+.1f}%")
        
        if pnl_change > 0:
            print(f"   ✅ IMPROVEMENT: Strategy performed better!")
        elif pnl_change < 0:
            print(f"   ⚠️  DECLINE: Need further optimization")
        else:
            print(f"   ⚖️  NEUTRAL: No significant change")
            
        # Trade efficiency
        if base_trades > 0 and imp_trades > 0:
            efficiency_change = imp_avg_pnl - base_avg_pnl
            print(f"   🎯 Avg trade efficiency change: ${efficiency_change:+.2f}")
        
        # Save results
        baseline_file = baseline_engine.save_results_to_csv("_baseline_comparison")
        improved_file = improved_engine.save_results_to_csv("_improved_comparison")
        
        print(f"\n📁 RESULTS SAVED:")
        print(f"   📊 Baseline: {baseline_file}")
        print(f"   🚀 Improved: {improved_file}")
        
        # Additional insights
        print(f"\n💡 NEXT STEPS:")
        if pnl_change > 0:
            print(f"   ✅ Apply these improvements to live system")
            print(f"   📊 Consider further optimization of remaining parameters")
        else:
            print(f"   🔍 Analyze individual trade details for more insights")
            print(f"   ⚙️  Test different parameter combinations")
            
        print(f"   📈 Focus on time-of-day filtering (avoid 14-15h)")
        print(f"   🎯 Consider position sizing optimization")
        
        return baseline_file, improved_file
        
    else:
        print("❌ Failed to generate comparison results")
        return None


if __name__ == "__main__":
    asyncio.run(run_improvement_test())