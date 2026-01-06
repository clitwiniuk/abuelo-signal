#!/usr/bin/env python3
"""
Simple Backtesting Runner
Runs backtesting on symbols with existing CSV data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine

async def run_backtest():
    """Run backtesting on available symbols"""
    print("🎯 MACDV STRATEGY BACKTESTING")
    print("=" * 40)
    
    # Check if data directory exists
    data_dir = Path("data/backtesting_csv")
    if not data_dir.exists():
        print("❌ No backtesting data found!")
        print("💡 Run 'python download_trading_data.py' first to download data")
        return
    
    # Count available CSV files
    csv_files = list(data_dir.glob("*_1_min.csv"))
    if not csv_files:
        print("❌ No CSV files found in data/backtesting_csv/")
        print("💡 Run 'python download_trading_data.py' first to download data")
        return
    
    print(f"📊 Found {len(csv_files)} CSV files with trading data")
    
    # Initialize backtesting engine
    engine = MacdvBacktestEngine(
        position_size=200.0,      # $200 per position
        trailing_stop_pct=0.05,   # 5% trailing stop
        max_hold_minutes=240,     # 4 hours max hold
        debug=False               # Reduce log verbosity
    )
    
    # Initialize
    if not await engine.initialize():
        print("❌ Failed to initialize backtesting engine")
        return
    
    # Run backtest on available symbols (limit to first 10 for speed)
    print(f"\n🚀 Starting backtesting...")
    results = await engine.run_backtest(
        symbols=None,        # Use all available symbols  
        max_symbols=10,      # Limit to 10 symbols for faster testing
        days_back=30         # Test last 30 days
    )
    
    # Save results
    if results:
        filename = engine.save_results_to_csv()
        print(f"\n📁 Detailed results saved to: {filename}")
        
        # Show quick summary
        print(f"\n📊 QUICK SUMMARY:")
        total_trades = sum(r.total_trades for r in results.values())
        total_pnl = sum(r.total_pnl for r in results.values())
        symbols_with_trades = len([r for r in results.values() if r.total_trades > 0])
        
        print(f"   🎯 Symbols tested: {len(results)}")
        print(f"   📈 Symbols with trades: {symbols_with_trades}")
        print(f"   🔢 Total trades: {total_trades}")
        print(f"   💰 Total P&L: ${total_pnl:.2f}")
        
        if total_trades > 0:
            avg_pnl = total_pnl / total_trades
            print(f"   📊 Average P&L per trade: ${avg_pnl:.2f}")
    else:
        print("❌ No results generated")

if __name__ == "__main__":
    asyncio.run(run_backtest())