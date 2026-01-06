#!/usr/bin/env python3
"""
Data Downloader for Trading Symbols
Downloads 1-minute data for all traded symbols using Polygon.io
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path (parent of backtesting directory)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapters.traded_symbols_data_provider import TradedSymbolsDataProvider

async def download_trading_data():
    """Download data for all traded symbols"""
    print("📥 TRADING DATA DOWNLOADER")
    print("=" * 40)
    
    # Initialize data provider with auto-download enabled
    data_provider = TradedSymbolsDataProvider(
        db_path="../trading_data.db",
        data_path="../data/backtesting_csv",
        auto_download=True,
        days_history=90
    )
    
    # Connect and download missing data
    success = await data_provider.connect()
    
    if success:
        # Print summary report
        data_provider.print_backtesting_summary()
        print(f"\n✅ Data download completed successfully!")
        print(f"📁 CSV files saved to: ../data/backtesting_csv/")
    else:
        print(f"❌ Data download failed")
    
    await data_provider.disconnect()

if __name__ == "__main__":
    asyncio.run(download_trading_data())