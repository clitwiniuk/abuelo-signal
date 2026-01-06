"""
Discover Breakout Setups (Historical Scanner)

This script demonstrates/implements the "Discovery Mode".
It scans a defined UNIVERSE of stocks over a historical DATE RANGE
to find Qullamaggie Breakout criteria matches.

Usage:
    python discover_setups.py
"""

import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
import json
import os
import sys

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scientific_backtest.historical_scanner_adapter import HistoricalScannerAdapter
from adapters.ibkr_adapter import IBKRAdapter

# 1. Define Universe (The "Haystack")
# Try to load from universe.json, otherwise use default
UNIVERSE = [
    'NVDA', 'AMD', 'TSLA', 'META', 'NFLX', 'AMZN', 'MSFT', 'GOOGL', 'AAPL',
    'PLTR', 'COIN', 'MARA', 'CVNA', 'UPST', 'AFRM', 'DKNG', 'HOOD',
    'SMCI', 'ARM', 'CART'
]

universe_path = os.path.join(os.path.dirname(__file__), "universe.json")
if os.path.exists(universe_path):
    try:
        with open(universe_path, "r") as f:
            loaded_universe = json.load(f)
            if loaded_universe and len(loaded_universe) > 0:
                UNIVERSE = loaded_universe
                print(f"📖 Loaded {len(UNIVERSE)} symbols from universe.json")
    except Exception as e:
        print(f"⚠️ Error loading universe.json: {e}")

async def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger = logging.getLogger("Discovery")
    
    # 2. Connect to IBKR (for data fetching)
    import random
    client_id = random.randint(5000, 9000)
    ibkr = IBKRAdapter(client_id=client_id)
    
    # NOTE: We assume IBKR Gateway/TWS is running or we have data in DB
    # If not connected, this might fail to fetch NEW data, but will read from Cache.
    # For this script we try to connect.
    try:
        await ibkr.connect()
    except:
        logger.warning(f"Could not connect to IBKR (ID {client_id}) - relying on Cached Data only")

    scanner = HistoricalScannerAdapter(ibkr)

    # 3. Setup State Tracking
    PROCESSED_FILE = os.path.join(os.path.dirname(__file__), "processed_symbols.json")
    processed_symbols = set()
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, "r") as f:
                processed_symbols = set(json.load(f))
                logger.info(f"📂 Loaded {len(processed_symbols)} previously processed symbols")
        except:
            pass
            
    # 4. Filter Universe for New Batch
    available_symbols = [s for s in UNIVERSE if s not in processed_symbols]
    
    if not available_symbols:
        logger.warning("⚠️ No new symbols to scan! Reset processed_symbols.json to restart.")
        await ibkr.disconnect()
        return

    BATCH_SIZE = 20
    current_batch = available_symbols[:BATCH_SIZE]
    
    logger.info(f"🔎 STARTING HISTORICAL SCAN - BATCH MODE")
    logger.info(f"   Universe Total: {len(UNIVERSE)}")
    logger.info(f"   Remaining: {len(available_symbols)}")
    logger.info(f"   Current Batch: {len(current_batch)} symbols -> {current_batch}")
    
    # Define Date Range
    # We end scanning 10 days ago to allow for "future" verification (as requested by user)
    end_date = datetime.now() - timedelta(days=10)
    start_date = end_date - timedelta(days=365) # Last year
    logger.info(f"   Range: {start_date.date()} to {end_date.date()}")
    
    # 5. Prefetch Data for Batch
    await scanner.ensure_data_available(current_batch, start_date, end_date)
    
    # 6. Run Scan on Batch
    logger.info("🕵️‍♂️ Scanning daily history...")
    results = await scanner.scan_history(current_batch, start_date, end_date)
    
    # 7. Analyze Results
    total_hits = sum(len(hits) for hits in results.values())
    logger.info(f"✅ BATCH SCAN COMPLETE. Found {total_hits} setups.")
    
    # Save Results (Append or New File?)
    # For now, overwrite/create 'latest_batch_results.json' to avoid huge files
    output_file = "latest_discovery.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"💾 Saved batch results to {output_file}")
    
    # 8. Update Processed State
    processed_symbols.update(current_batch)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed_symbols), f, indent=2)
    logger.info(f"📝 Updated processed list (Total: {len(processed_symbols)})")
    
    # Print Top Finds
    dates = sorted(results.keys())
    for date_str in dates:
        hits = results[date_str]
        for hit in hits:
            print(f"   📅 {date_str} | {hit['symbol']} | Score: {hit['quality_score']} | Setups: {hit['breakout_data']}")

    await ibkr.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
