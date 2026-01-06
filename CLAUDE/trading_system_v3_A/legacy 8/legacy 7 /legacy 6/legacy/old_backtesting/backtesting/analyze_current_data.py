#!/usr/bin/env python3
"""
Analyze Current 21 Symbol Data with Correct Timezone
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine

async def analyze_current_data():
    """Analyze the current 21 symbols with correct timezone"""
    
    print("📊 ANALYSIS OF CURRENT DATA (21 SYMBOLS)")
    print("With corrected ET timezone conversion")
    print("=" * 50)
    
    # Original engine
    original_engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,  # 5%
        max_hold_minutes=240,
        debug=False
    )
    
    if not await original_engine.initialize():
        print("❌ Failed to initialize engine")
        return
        
    # Run backtest on available symbols
    results = await original_engine.run_backtest(
        symbols=None,        # Use available symbols
        max_symbols=None,    # No limit
        days_back=30
    )
    
    if results:
        # Save results
        filename = original_engine.save_results_to_csv(suffix="_current_21_symbols")
        print(f"\n📁 Results saved to: {filename}")
        
        # Quick summary
        total_trades = sum(r.total_trades for r in results.values())
        total_pnl = sum(r.total_pnl for r in results.values())
        symbols_with_trades = len([r for r in results.values() if r.total_trades > 0])
        
        print(f"\n📊 CURRENT DATA SUMMARY:")
        print(f"   🎯 Symbols available: {len(results)}")
        print(f"   📈 Symbols with trades: {symbols_with_trades}")
        print(f"   🔢 Total trades: {total_trades}")
        print(f"   💰 Total P&L: ${total_pnl:.2f}")
        
        if total_trades > 0:
            avg_pnl = total_pnl / total_trades
            win_rate = sum(1 for r in results.values() for t in r.trades if t.pnl > 0) / total_trades * 100
            print(f"   📊 Average P&L per trade: ${avg_pnl:.2f}")
            print(f"   📈 Approximate win rate: {win_rate:.1f}%")
            
        # Symbol breakdown
        print(f"\n🎯 SYMBOL BREAKDOWN:")
        for symbol, result in results.items():
            if result.total_trades > 0:
                print(f"   {symbol}: {result.total_trades} trades, ${result.total_pnl:.2f}")
                
        return filename
    else:
        print("❌ No results generated")

if __name__ == "__main__":
    asyncio.run(analyze_current_data())