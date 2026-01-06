#!/usr/bin/env python3
"""
Test Optimizations
Simple script to test the optimized backtesting engine
"""

import asyncio
from optimized_backtest_engine import OptimizedMacdvBacktestEngine, OptimizationConfig

async def test_optimizations():
    """Test the optimized backtesting engine"""
    
    print("🧪 TESTING OPTIMIZATIONS")
    print("=" * 40)
    
    # Create optimized configuration (ALL SYMBOLS)
    opt_config = OptimizationConfig(
        trailing_stop_pct=0.08,  # 8% instead of 5%
        blocked_hours=[14, 15],  # Avoid worst hours
        preferred_hours=[16, 17, 18],  # Focus on best hours
        enable_symbol_filtering=False,  # TRADE ALL SYMBOLS
        use_atr_stops=True,
        extended_hold_multiplier=1.5  # 50% longer hold for trends
    )
    
    # Initialize optimized engine
    engine = OptimizedMacdvBacktestEngine(
        optimization_config=opt_config,
        position_size=200.0,
        debug=False
    )
    
    # Initialize
    if not await engine.initialize():
        print("❌ Failed to initialize optimized engine")
        return
    
    # Run optimized backtest on ALL available symbols
    results = await engine.run_optimized_backtest(
        symbols=None,    # Use ALL available symbols
        max_symbols=None,  # No limit on symbols
        days_back=30
    )
    
    # Show results
    if results:
        filename = engine.save_results_to_csv(suffix="_optimized_test")
        print(f"\n📁 Results saved to: {filename}")
        
        total_trades = sum(r.total_trades for r in results.values())
        total_pnl = sum(r.total_pnl for r in results.values())
        symbols_tested = len(results)
        
        print(f"\n📊 OPTIMIZED RESULTS:")
        print(f"   🎯 Symbols tested: {symbols_tested}")
        print(f"   🔢 Total trades: {total_trades}")
        print(f"   💰 Total P&L: ${total_pnl:.2f}")
        
        if total_trades > 0:
            avg_pnl = total_pnl / total_trades
            print(f"   📊 Average P&L per trade: ${avg_pnl:.2f}")
            
        print(f"\n💡 Compare this with original results to see improvement!")
    else:
        print("❌ No results generated")

if __name__ == "__main__":
    asyncio.run(test_optimizations())