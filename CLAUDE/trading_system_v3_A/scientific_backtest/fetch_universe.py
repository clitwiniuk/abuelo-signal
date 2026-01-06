"""
Fetch Universe from IBKR

This script uses IBKR Scanner to fetch a broad universe of stocks:
1. US Stocks
2. Price > 2.0
3. Sorted by Volume (Most Active) and Top Gainers
4. Saves to 'universe.json'

This "Universe" is then used by discover_setups.py to find historical patterns.
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adapters.ibkr_adapter import IBKRAdapter
from ib_insync import ScannerSubscription, TagValue

async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("UniverseFetcher")
    
    adapter = IBKRAdapter()
    await adapter.connect()
    
    unique_symbols = set()
    
    # Define Scans
    # 1. Most Active (High Volume)
    scan_active = ScannerSubscription(
        instrument='STK', 
        locationCode='STK.US.MAJOR', 
        scanCode='MOST_ACTIVE'
    )
    
    # 2. Top Gainers (Momentum)
    scan_gainers = ScannerSubscription(
        instrument='STK', 
        locationCode='STK.US.MAJOR', 
        scanCode='TOP_PERC_GAIN'
    )
    
    # Filter Price > 5 
    tag_values = [
        TagValue("avgVolumeAbove", "500000"),
        TagValue("priceAbove", "5")
    ]
    
    logger.info("📡 Scanning IBKR for Universe...")
    
    # Fetch Scan 1
    logger.info("   Fetching Most Active...")
    data_active = await adapter.ib.reqScannerSubscriptionAsync(scan_active, [], tag_values)
    for item in data_active:
        symbol = item.contractDetails.contract.symbol
        unique_symbols.add(symbol)
        
    # Fetch Scan 2
    logger.info("   Fetching Top Gainers...")
    data_gainers = await adapter.ib.reqScannerSubscriptionAsync(scan_gainers, [], tag_values)
    for item in data_gainers:
        symbol = item.contractDetails.contract.symbol
        unique_symbols.add(symbol)
        
    logger.info(f"✅ Found {len(unique_symbols)} unique symbols.")
    
    # Save
    universe_list = sorted(list(unique_symbols))
    with open("universe.json", "w") as f:
        json.dump(universe_list, f, indent=2)
        
    logger.info("💾 Saved to universe.json")
    await adapter.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
