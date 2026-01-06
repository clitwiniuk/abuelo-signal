#!/usr/bin/env python3
"""
Quick Backtesting with Downloaded Symbols
Tests the MACDV strategy on symbols we already have data for
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backtesting.macdv_backtest_engine import MacdvBacktestEngine

async def quick_backtest():
    """Run quick backtest with downloaded symbols only"""
    print("🚀 QUICK BACKTESTING WITH EXISTING DATA")
    print("=" * 50)
    
    # Symbols we know have been downloaded
    downloaded_symbols = [
        'DLTH', 'NUKK', 'NEXT', 'ASST', 'HOUR', 
        'HUDI', 'SHFS', 'BBLG', 'CRWG', 'REVB', 'BTBD'
    ]
    
    print(f"📊 Testing {len(downloaded_symbols)} symbols with existing data")
    print(f"   Symbols: {', '.join(downloaded_symbols)}")
    
    # Initialize backtesting engine
    engine = MacdvBacktestEngine(
        position_size=200.0,
        trailing_stop_pct=0.05,
        max_hold_minutes=240,
        debug=False  # Reduce verbosity
    )
    
    # Disable auto-download to use only existing data
    engine.data_provider = None  # We'll set this manually
    
    if not await engine.initialize():
        print("❌ Failed to initialize backtesting engine")
        return
    
    # Disable auto-download
    engine.data_provider.auto_download = False
    
    # Run backtest on specific symbols
    print(f"\n🎯 Starting backtest...")
    results = await engine.run_backtest(
        symbols=downloaded_symbols,
        max_symbols=len(downloaded_symbols),
        days_back=14  # Shorter period for faster testing
    )
    
    # Save results to CSV
    if results:
        filename = engine.save_results_to_csv()
        print(f"\n📁 Results saved to: {filename}")
    
    return results

if __name__ == "__main__":
    asyncio.run(quick_backtest())