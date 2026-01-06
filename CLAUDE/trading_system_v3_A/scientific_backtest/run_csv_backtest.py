"""
Run CSV Backtest (Manual Selection)

This script allows running the backtest on a manually curated list of setups provided in a CSV file.
This isolates the strategy execution performance from the automated scanner's detection quality.

Input File: scientific_backtest/custom_setups.csv
Format: Symbol,DaysAgo (or Symbol,Date)
Example:
DKNG, 15  (Means: Test DKNG starting 15 days ago)
SMCI, 2024-12-10 (Means: Test SMCI starting on Dec 10, 2024)

Flow:
1. Parse CSV and determine test windows (Event Date - 2 days to + 20 days).
2. Async Phase: Fetch/Backfill IBKR Intraday Data for these windows.
3. Sync Phase: Run ReplayEngine on these specific setups.
"""

import asyncio
import csv
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
logger = logging.getLogger("CSVBacktest")

CSV_PATH = os.path.join(os.path.dirname(__file__), "custom_setups.csv")

def parse_csv_setups():
    """Reads CSV and returns Dict[DateStr, List[Symbol]]"""
    if not os.path.exists(CSV_PATH):
        logger.error(f"❌ CSV file not found: {CSV_PATH}")
        logger.info("ℹ️  Please create it with format: Symbol, DaysAgo (or Date)")
        return None

    setups_by_date = {} # "YYYY-MM-DD" -> [Symbol, Symbol]
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith('#'): continue
            
            symbol = row[0].strip().upper()
            time_ref = row[1].strip()
            
            target_date = None
            
            # Try parsing as Date
            try:
                target_date = datetime.strptime(time_ref, '%Y-%m-%d')
            except ValueError:
                # Try parsing as Days Ago
                try:
                    days_ago = int(time_ref)
                    target_date = datetime.now() - timedelta(days=days_ago)
                except ValueError:
                    logger.warning(f"⚠️ Skipping invalid row: {row}")
                    continue
            
            if target_date:
                d_str = target_date.strftime('%Y-%m-%d')
                if d_str not in setups_by_date:
                    setups_by_date[d_str] = []
                setups_by_date[d_str].append(symbol)
                
    return setups_by_date

async def fetch_data(setups_by_date):
    """
    Async Phase: Connect to IBKR and fetch/backfill Intraday Data.
    """
    logger.info("🔵 Starting Async Data Fetch Phase (CSV)...")
    
    unique_symbols = set()
    for syms in setups_by_date.values():
        unique_symbols.update(syms)
            
    # Connect to IBKR
    client_id = random.randint(20000, 29000) # Different range
    ibkr = IBKRAdapter(client_id=client_id)
    try:
        await ibkr.connect()
    except Exception as e:
        logger.warning(f"Could not connect to IBKR: {e}. Skipping fetch.")
        return

    logger.info(f"📥 Prefetching Intraday Data for {len(unique_symbols)} symbols...")
    
    # DB Setup
    conn = sqlite3.connect("trading_data.db")
    cursor = conn.cursor()
    
    # Ensure Table Exists
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
    
    for symbol in unique_symbols:
        # Determine strict range for this symbol based on CSV dates
        # We need coverage for: Event Date - 5 days (Ma/Volatility) to Event Date + 30 days (Run)
        
        relevant_event_dates = [datetime.strptime(d, '%Y-%m-%d') for d, syms in setups_by_date.items() if symbol in syms]
        if not relevant_event_dates: continue
        
        sym_start = min(relevant_event_dates) - timedelta(days=10) # 10 days pre-event for MAs
        sym_end = max(relevant_event_dates) + timedelta(days=40)   # 40 days post-event for full swing
        
        # Ensure we don't request future
        if sym_end > datetime.now():
            sym_end = datetime.now()

        logger.info(f"   Fetching {symbol} ({sym_start.date()} -> {sym_end.date()})...")

        current_opt_date = sym_start
        chunk_days = 20
        
        while current_opt_date < sym_end:
            chunk_end = min(current_opt_date + timedelta(days=chunk_days), sym_end)
            
            try:
                days_in_chunk = (chunk_end - current_opt_date).days
                if days_in_chunk < 1: 
                    current_opt_date = chunk_end
                    continue

                # Check cache check? Na, blind fetch is safer for user request
                approx_count = int(days_in_chunk * 80 * 1.5)
                
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
                    # logger.info(f"     ✅ Saved {len(bars)} bars")
                
                await asyncio.sleep(1.2) 
            except Exception as e:
                logger.error(f"     ❌ Failed {symbol}: {e}")
                
            current_opt_date = chunk_end
            
    conn.close()
    await ibkr.disconnect()
    logger.info("🔵 Async Fetch Phase Complete.")


def run_replay(setups_by_date):
    """
    Sync Phase: Run Replay Engine.
    """
    logger.info("🚀 Starting Replay Phase (CSV Manual Mode)...")
    
    # Prepare Mock Discovery Results for Adapter
    # Dict[DateStr, List[Dict]]
    discovery_results_mock = {}
    for d_str, symbols in setups_by_date.items():
        discovery_results_mock[d_str] = []
        for s in symbols:
            # Create a mock "Hit" object compatible with what Scanner produces
            discovery_results_mock[d_str].append({
                'symbol': s,
                'breakout_data': {
                    'resistance': 100.0, # Dummy, Worker will calc from bars or use this
                    'support': 95.0,
                    'atr': 2.0,
                    'quality_score': 100 # Force acceptance if filtering uses score
                }
            })

    # Setup Scanner Adapter
    scanner = HistoricalScannerAdapter(None) 
    scanner.load_results(discovery_results_mock)
    
    # Define Custom Replay Engine
    class ManualReplayEngine(ReplayEngine):
        def _load_worker(self, worker_name: str, config_path: str = None):
            if worker_name == "BreakoutWorker":
                config = {
                    "name": "BreakoutWorker",
                    "risk_per_trade": 0.01,
                    "max_positions": 5,
                    "parameters": {"min_gain_pct": 10}
                }
                try:
                    return BreakoutWorker(worker_name)
                except:
                    return BreakoutWorker(worker_name, None, config)
            return super()._load_worker(worker_name, config_path)

    # Initialize Engine
    engine = ManualReplayEngine("trading_data.db", "trading_data.db")
    
    # Determine Date Range
    all_dates = sorted([datetime.strptime(d, '%Y-%m-%d') for d in setups_by_date.keys()])
    if not all_dates: return
    
    start_date = all_dates[0]
    end_date = all_dates[-1] + timedelta(days=40) # Run for 40 days after last setup to allow trade to play out
    if end_date > datetime.now(): end_date = datetime.now()
    
    current = start_date
    while current <= end_date:
        if current.weekday() < 5: 
            date_str = current.strftime('%Y-%m-%d')
            day_hits = discovery_results_mock.get(date_str, [])
            day_symbols = [h['symbol'] for h in day_hits] if day_hits else []
            
            # Note: We Replay EVERY DAY so existing positions are managed
            # We only pass 'symbols' to replay_day if we want to TRIGGER new checks?
            # ReplayEngine usually iterates ALL active tickers or provided list.
            # If we pass symbol list, it only processes those?
            # Yes. But for Day 1 we pass [NVDA]. For Day 2 (NVDA active), we must pass [NVDA] or empty?
            # If we pass empty, ReplayEngine iterates "Active Positions".
            # So passing specific symbols allows NEW entries.
            
            try:
                if day_symbols:
                   logger.info(f"   ▶️ {date_str}: Triggering {day_symbols}")
                   
                engine.replay_day(
                    date_str, 
                    worker_names=['BreakoutWorker'], 
                    symbols=day_symbols, # Only trigger logic for setups of this day
                    scanner_adapter=scanner
                )
            except Exception as e:
                logger.error(f"Error replaying {date_str}: {e}")

        current += timedelta(days=1)
        
    logger.info("✅ CSV Backtest Complete")


if __name__ == "__main__":
    # 1. Parse CSV
    setups = parse_csv_setups()
    if not setups:
        sys.exit(1)

    logger.info(f"🎯 Loaded {sum(len(v) for v in setups.values())} setups from CSV")

    # 2. Run Async Fetch
    try:
        asyncio.run(fetch_data(setups))
    except Exception as e:
        logger.error(f"Fetch failed: {e}")

    # 3. Run Sync Replay
    run_replay(setups)
