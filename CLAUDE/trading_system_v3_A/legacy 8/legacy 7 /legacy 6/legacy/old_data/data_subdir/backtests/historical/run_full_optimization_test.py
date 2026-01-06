#!/usr/bin/env python3
"""
Full Optimization Test
Tests optimizations on ALL available symbols and compares with original
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine
from backtesting.optimized_backtest_engine import OptimizedMacdvBacktestEngine, OptimizationConfig

async def run_full_optimization_test():
    """Run optimization test on ALL symbols"""
    
    print("🎯 FULL OPTIMIZATION TEST")
    print("Testing on ALL available symbols")
    print("=" * 50)
    
    # Test parameters
    test_params = {
        'position_size': 200.0,
        'debug': False
    }
    
    print("\n1️⃣  Running ORIGINAL backtest (ALL symbols)...")
    
    # Original engine
    original_engine = MacdvBacktestEngine(
        trailing_stop_pct=0.05,  # Original 5%
        max_hold_minutes=240,
        **test_params
    )
    
    if not await original_engine.initialize():
        print("❌ Failed to initialize original engine")
        return
        
    original_results = await original_engine.run_backtest(
        symbols=None,        # ALL symbols
        max_symbols=None,    # No limit
        days_back=30
    )
    
    print("\n2️⃣  Running OPTIMIZED backtest (ALL symbols)...")
    
    # Optimized engine - conservative optimizations with corrected timezone
    opt_config = OptimizationConfig(
        trailing_stop_pct=0.08,           # 8% instead of 5%
        blocked_hours=[],                 # No blocked hours - data now in correct ET
        preferred_hours=[10, 11, 12, 13, 14, 15], # All regular market hours ET
        enable_symbol_filtering=False,    # IMPORTANT: NO symbol filtering
        use_atr_stops=True,              # Dynamic ATR-based stops
        extended_hold_multiplier=1.5     # Extend hold for trends
    )
    
    optimized_engine = OptimizedMacdvBacktestEngine(
        optimization_config=opt_config,
        **test_params
    )
    
    if not await optimized_engine.initialize():
        print("❌ Failed to initialize optimized engine")
        return
        
    optimized_results = await optimized_engine.run_optimized_backtest(
        symbols=None,        # ALL symbols
        max_symbols=None,    # No limit
        days_back=30
    )
    
    # Compare and save results
    print(f"\n📊 COMPARISON RESULTS:")
    print("=" * 50)
    
    if original_results and optimized_results:
        # Calculate metrics
        orig_trades = sum(r.total_trades for r in original_results.values())
        orig_pnl = sum(r.total_pnl for r in original_results.values())
        orig_symbols = len([r for r in original_results.values() if r.total_trades > 0])
        
        opt_trades = sum(r.total_trades for r in optimized_results.values())
        opt_pnl = sum(r.total_pnl for r in optimized_results.values())
        opt_symbols = len([r for r in optimized_results.values() if r.total_trades > 0])
        
        # Changes
        pnl_change = opt_pnl - orig_pnl
        trade_change = opt_trades - orig_trades
        symbol_change = opt_symbols - orig_symbols
        
        print(f"📈 ORIGINAL RESULTS:")
        print(f"   🎯 Symbols with trades: {orig_symbols}")
        print(f"   🔢 Total trades: {orig_trades}")
        print(f"   💰 Total P&L: ${orig_pnl:.2f}")
        if orig_trades > 0:
            print(f"   📊 Avg P&L/trade: ${orig_pnl/orig_trades:.2f}")
            
        print(f"\n🚀 OPTIMIZED RESULTS:")
        print(f"   🎯 Symbols with trades: {opt_symbols}")
        print(f"   🔢 Total trades: {opt_trades}")
        print(f"   💰 Total P&L: ${opt_pnl:.2f}")
        if opt_trades > 0:
            print(f"   📊 Avg P&L/trade: ${opt_pnl/opt_trades:.2f}")
            
        print(f"\n💡 OPTIMIZATION IMPACT:")
        print(f"   📊 P&L Change: {'+' if pnl_change >= 0 else ''}${pnl_change:.2f}")
        print(f"   🔢 Trade Change: {'+' if trade_change >= 0 else ''}{trade_change}")
        print(f"   🎯 Symbol Change: {'+' if symbol_change >= 0 else ''}{symbol_change}")
        
        if orig_pnl != 0:
            improvement_pct = (pnl_change / abs(orig_pnl)) * 100
            print(f"   📈 Improvement: {'+' if improvement_pct >= 0 else ''}{improvement_pct:.1f}%")
            
        # Save results with clear naming
        orig_file = original_engine.save_results_to_csv(suffix="_original_full")
        opt_file = optimized_engine.save_results_to_csv(suffix="_optimized_full")
        
        print(f"\n📁 DETAILED RESULTS SAVED:")
        print(f"   📄 Original: {orig_file}")
        print(f"   🚀 Optimized: {opt_file}")
        
        print(f"\n💡 RECOMMENDATION:")
        if pnl_change > 0:
            print("   ✅ Optimizations IMPROVED performance!")
            print("   🎯 Consider implementing these changes in live system")
        elif pnl_change == 0:
            print("   ⚖️  Optimizations had NEUTRAL impact")
            print("   🤔 Further analysis needed")
        else:
            print("   ❌ Optimizations REDUCED performance")
            print("   🔍 Review optimization parameters")
            
    else:
        print("❌ Failed to generate results for comparison")

if __name__ == "__main__":
    asyncio.run(run_full_optimization_test())