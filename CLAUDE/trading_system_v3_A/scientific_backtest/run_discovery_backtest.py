"""
Run Discovery Backtest

This script takes the results from 'latest_discovery.json' (Discovery Phase)
and runs a full intraday simulation (Backtest Phase) on those specific setups.

Flow:
1. Load discovered setups.
2. Prefetch 5-minute intraday data for the relevant symbols/dates from IBKR.
3. Run ReplayEngine using HistoricalScannerAdapter (pre-loaded with discovery results).
4. Output performance metrics.
"""

import asyncio
import json
import logging
import os
import sys
import random
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.ibkr_adapter import IBKRAdapter
from scientific_backtest.historical_scanner_adapter import HistoricalScannerAdapter
from replay_testing.core.replay_engine import ReplayEngine
from strategies.swing_workers.breakout_worker import BreakoutWorker

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("DiscoveryBacktest")

async def fetch_data(discovery_results):
    """
    Async Phase: Connect to IBKR and fetch/backfill Intraday Data.
    """
    logger.info("🔵 Starting Async Data Fetch Phase...")
    
    unique_symbols = set()
    for hits in discovery_results.values():
        for hit in hits:
            unique_symbols.add(hit['symbol'])
            
    # Connect to IBKR
    client_id = random.randint(10000, 19000)
    ibkr = IBKRAdapter(client_id=client_id)
    try:
        await ibkr.connect()
    except Exception as e:
        logger.warning(f"Could not connect to IBKR: {e}. Skipping fetch.")
        return

    logger.info("📥 Prefetching Intraday Data (5 mins)...")
    
    # DB Setup
    conn = sqlite3.connect("trading_data.db")
    cursor = conn.cursor()
    
    # Ensure Table Exists (Drop View if legacy)
    try:
        cursor.execute("DROP VIEW IF EXISTS intraday_bars")
    except:
        pass
        
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intraday_bars (
            symbol TEXT,
            bar_timestamp TEXT,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume INTEGER,
            vwap REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, bar_timestamp)
        )
    """)
    conn.commit()
    
    # Fetch Loop
    # Note: Using [] to skip fetching if already done. Restore unique_symbols to fetch.
    # To ensure data for user, we iterate unique_symbols. 
    # If partial data exists, it overwrites (INSERT OR REPLACE).
    # For speed in this specific session context where we backfilled some already:
    # We will fetch everything to be safe.
    
    for symbol in unique_symbols:
        logger.info(f"   Fetching 5m bars for {symbol} (Chunked)...")
        
        # Determine range for this symbol
        symbol_dates = [d for d_str, hits in discovery_results.items() for h in hits 
                       if h['symbol'] == symbol and (d := datetime.strptime(d_str, '%Y-%m-%d'))]
        if not symbol_dates: continue
        
        sym_start = min(symbol_dates) - timedelta(days=2)
        sym_end = max(symbol_dates) + timedelta(days=5) 
        
        current_opt_date = sym_start
        chunk_days = 20 
        
        while current_opt_date < sym_end:
            chunk_end = min(current_opt_date + timedelta(days=chunk_days), sym_end)
            
            try:
                days_in_chunk = (chunk_end - current_opt_date).days
                if days_in_chunk < 1: 
                    current_opt_date = chunk_end
                    continue

                logger.info(f"     📅 Requesting {symbol} -> {chunk_end.date()}")
                approx_count = int(days_in_chunk * 80 * 1.2)
                
                bars = await ibkr.get_bars(
                    symbol, "5 mins", count=approx_count, end_date=chunk_end
                )
                
                if bars:
                    data_to_insert = []
                    for b in bars:
                        vwap = (b.high + b.low + b.close) / 3 if b.close else None
                        data_to_insert.append((
                            symbol, b.timestamp.isoformat(),
                            b.open, b.high, b.low, b.close, int(b.volume), vwap
                        ))
                    
                    cursor.executemany("""
                        INSERT OR REPLACE INTO intraday_bars (symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume, vwap)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, data_to_insert)
                    conn.commit()
                    logger.info(f"     ✅ Saved {len(bars)} bars")
                
                await asyncio.sleep(1.5) 
            except Exception as e:
                logger.error(f"     ❌ Failed {symbol}: {e}")
                
            current_opt_date = chunk_end
            
    conn.close()
    await ibkr.disconnect()
    logger.info("🔵 Async Fetch Phase Complete.")


def run_replay(discovery_results):
    """
    Sync Phase: Run Replay Engine.
    """
    logger.info("🚀 Starting Replay Phase (Sync Mode)...")
    
    # Setup Scanner Adapter (Mock IBKR because we are offline now)
    # We pass None because HistoricalScannerAdapter just needs results loaded.
    scanner = HistoricalScannerAdapter(None) 
    scanner.load_results(discovery_results)
    
    # Define Custom Replay Engine
    class DiscoveryReplayEngine(ReplayEngine):
        def _load_worker(self, worker_name: str, config_path: str = None):
            if worker_name == "BreakoutWorker":
                config = {
                    "name": "BreakoutWorker",
                    "risk_per_trade": 0.01,
                    "max_positions": 5,
                    "parameters": {"min_gain_pct": 10, "max_adr_pct": 10}
                }
                try:
                    return BreakoutWorker(worker_name)
                except:
                    return BreakoutWorker(worker_name, None, config)
            return super()._load_worker(worker_name, config_path)

    # Initialize Engine
    engine = DiscoveryReplayEngine(
        market_data_db_path="trading_data.db",
        trading_data_db_path="trading_data.db"
    )
    
    # Determine Date Range
    all_dates = sorted([datetime.strptime(d, '%Y-%m-%d') for d in discovery_results.keys()])
    if not all_dates: return
    
    current = all_dates[0]
    end_date = all_dates[-1] + timedelta(days=5)
    
    while current <= end_date:
        if current.weekday() < 5: 
            date_str = current.strftime('%Y-%m-%d')
            day_hits = discovery_results.get(date_str, [])
            day_symbols = [h['symbol'] for h in day_hits] if day_hits else []
            
            if day_symbols:
                logger.info(f"   ▶️ Replaying {date_str} for {day_symbols}")
                try:
                    engine.replay_day(
                        date_str, 
                        worker_names=['BreakoutWorker'], 
                        symbols=day_symbols,
                        scanner_adapter=scanner
                    )
                except Exception as e:
                    logger.error(f"Error replaying {date_str}: {e}")
            else:
                # logger.info(f"   (No discovery hits for {date_str})")
                pass
                 
        current += timedelta(days=1)
        
    logger.info("✅ Backtest Complete")


if __name__ == "__main__":
    # 1. Load Discovery Results
    discovery_file = os.path.join(os.path.dirname(__file__), "latest_discovery.json")
    if not os.path.exists(discovery_file):
        logger.error(f"❌ No discovery file found at {discovery_file}.")
        sys.exit(1)

    with open(discovery_file, "r") as f:
        results = json.load(f)

    if not results:
        logger.error("⚠️ No setups found.")
        sys.exit(1)

    # 2. Run Async Fetch
    try:
        asyncio.run(fetch_data(results))
    except Exception as e:
        logger.error(f"Fetch failed: {e}")

    # 3. Run Sync Replay
    # (Event loop is closed now, safe to run sync Replay that internally manages its asyncio if needed, 
    # but ReplayEngine is designed to be sync top-level)
    run_replay(results)
