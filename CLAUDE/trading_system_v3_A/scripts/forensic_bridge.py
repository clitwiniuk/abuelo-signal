#!/usr/bin/env python3
import sys
import json
import argparse
import asyncio
import re
from datetime import datetime, timedelta, timezone
import pandas as pd
from collections import defaultdict
from ib_insync import *
import shutil
import time

# Ensure we have an event loop
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Configuration
import random
import os

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TRADER_LOG = os.path.join(PROJECT_ROOT, "logs", "trader.log")
WORKER_LOG_PATTERN = os.path.join(PROJECT_ROOT, "logs", "worker_{}.log")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data_cache", "market_data")
IB_HOST = '127.0.0.1'
IB_PORT = 7497
IB_CLIENT_ID = random.randint(8000, 8999)  # Random ID for forensic tool to avoid conflicts

class SmartCache:
    """
    Smart Caching System for Market Data
    - Reads from local JSON cache if correct file exists
    - Writes to cache after fetch
    - Cleans up files older than 15 days
    """
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # Run cleanup on init
        self._cleanup_old_files()

    def _cleanup_old_files(self, days=15):
        """Delete files not accessed/modified in > X days"""
        now = time.time()
        cutoff = now - (days * 86400)
        
        try:
            for f in os.listdir(self.cache_dir):
                f_path = os.path.join(self.cache_dir, f)
                if os.path.isfile(f_path):
                    if os.stat(f_path).st_mtime < cutoff:
                        os.remove(f_path)
            # Remove empty dirs? Optional
        except Exception as e:
            sys.stderr.write(f"Cache Cleanup Warning: {e}\n")

    def get_cache_path(self, ticker, date_str):
        return os.path.join(self.cache_dir, f"{ticker}_{date_str}.json")

    def read(self, ticker, date_str):
        """Read 1-min bars from cache"""
        path = self.get_cache_path(ticker, date_str)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    sys.stderr.write(f"DEBUG: Cache HIT for {ticker} on {date_str}\n")
                    return data
            except:
                pass
        return None

    def write(self, ticker, date_str, data):
        """Write 1-min bars to cache"""
        if not data: return
        path = self.get_cache_path(ticker, date_str)
        try:
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            sys.stderr.write(f"Cache Write Error: {e}\n")


def parse_logs(ticker, target_date=None, limit_lines=None):
    """Parse trader and worker logs for specific ticker and date."""
    # Get timezone offset for adjusting event timestamps
    # With new "Fake UTC" logic, we just treat naive log timestamps as UTC
    events = []
    
    # helper to read file efficiently - if target_date provided, only look for that date
    # we can't easily jump to date without scanning, so parsing line-by-line is safest
    # for typical log sizes.
    
    # 1. Parse Trader Log (Opportunities)
    try:
        with open(TRADER_LOG, 'r') as f:
            for line in f:
                if target_date and not line.startswith(target_date):
                    continue
                if ticker in line:
                    # Extract timestamp
                    time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not time_match: continue
                    timestamp = time_match.group(1)
                    
                    if f"Opportunity {ticker}" in line or f"{ticker} routing" in line:
                        event_type = "INFO"
                        if "ENTERED POSITION" in line or "Opportunity executed" in line: event_type = "BUY"
                        elif "ACCEPTED" in line or "✅" in line: event_type = "ACCEPTED"
                        elif "REJECTED" in line or "🚫" in line: event_type = "REJECTED"
                        elif "DEBUG Opportunity" in line or "routing to" in line: event_type = "SIGNAL"
                        
                        # Extract metrics if available
                        metrics = {}
                        if 'gap=' in line:
                            m = re.search(r'gap=([-\d.]+)%', line)
                            if m: metrics['gap'] = float(m.group(1))
                        if 'vol=' in line:
                            m = re.search(r'vol=([\d.]+)x', line)
                            if m: metrics['volume_ratio'] = float(m.group(1))
                        
                        # Calculate chart_time (Fake UTC for chart alignment)
                        # Parse timestamp string as naive (implies local), treat as UTC for chart
                        dt_log = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        dt_log = dt_log.replace(tzinfo=timezone.utc)
                        chart_time = int(dt_log.timestamp())
    
                        events.append({
                            "timestamp": timestamp,
                            "chart_time": chart_time,
                            "source": "TRADER",
                            "type": event_type,
                            "message": line.strip(),
                            "metrics": metrics
                        })
    except Exception as e:
        sys.stderr.write(f"Error reading trader log: {e}\n")

    # 2. Parse Worker Logs
    workers = ['daily_plays', 'buy_and_hold', 'orb_breakout', 'macdv', 
               'vcp_smallcap', 'momentum_breakout']
               
    for worker in workers:
        try:
            log_path = WORKER_LOG_PATTERN.format(worker)
            with open(log_path, 'r') as f:
                for line in f:
                    if target_date and not line.startswith(target_date):
                        continue
                    if ticker in line:
                        time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if not time_match: continue
                        timestamp = time_match.group(1)
                        
                        event_type = "INFO"
                        if "ENTERED POSITION" in line or "Opportunity executed" in line or "Position opened" in line: event_type = "BUY"
                        elif "BUY" in line or "market_buy" in line: event_type = "BUY"
                        elif "SELL" in line or "market_sell" in line or "Position closed" in line or "Exiting" in line or "PAPER ORDER PLACED: SELL" in line: event_type = "SELL"
                        elif "ACCEPTED" in line or "✅" in line: event_type = "ACCEPTED"
                        elif "REJECTED" in line or "🚫" in line: event_type = "REJECTED"
                        
                        # Calculate chart_time
                        dt_log = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        dt_log = dt_log.replace(tzinfo=timezone.utc)
                        chart_time = int(dt_log.timestamp())
                        
                        events.append({
                            "timestamp": timestamp,
                            "chart_time": chart_time,
                            "source": f"WORKER:{worker}",
                            "type": event_type,
                            "message": line.strip()
                        })
        except FileNotFoundError:
            continue
            
    # Sort events by timestamp
    return sorted(events, key=lambda x: x['timestamp'])

def fetch_market_data(ticker, date_str=None, use_cache=False):
    """Fetch market data for a ticker on a specific date (1 min bars)."""
    
    # 0. Initialize Cache
    cache = SmartCache() if use_cache else None

    # 1. Try DB first (Offline Mode)
    # ALWAYS try DB first regardless of cache flag? Usually yes, DB is supreme source of truth for "what happened"
    db_bars = fetch_data_from_db(ticker, date_str)
    if db_bars:
         sys.stderr.write(f"DEBUG: Found {len(db_bars)} bars in DB for {ticker}\n")
         return db_bars

    # 2. Try Cache (if enabled)
    if cache:
        cached_bars = cache.read(ticker, date_str)
        if cached_bars:
            return cached_bars

    # 3. Fetch from IBKR
    sys.stderr.write(f"DEBUG: Connecting to IBKR for {ticker}...\n")
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        
        contract = Stock(ticker, 'SMART', 'USD')
        
        # Define end datetime (end of the specific day)
        # date_str is YYYY-MM-DD
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        endDateTime = dt.replace(hour=23, minute=59, second=59).strftime('%Y%m%d %H:%M:%S')
        
        sys.stderr.write(f"DEBUG: Fetching data for date {date_str} (End: {endDateTime})\n")
        
        # Request data
        bars = ib.reqHistoricalData(
            contract,
            endDateTime=endDateTime,
            durationStr='1 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )
        
        sys.stderr.write(f"DEBUG: Received {len(bars) if bars else 0} bars from IBKR\n")
        
        data = []
        if bars:
            for bar in bars:
                # FORCE CHART TO DISPLAY LOCAL TIME:
                # 1. Convert ET (IBKR) to Local System Time (e.g. CET)
                # 2. Treat that Local Time as if it were UTC (replace tzinfo=utc)
                # 3. This generates a timestamp that, when interpreted as UTC by the chart, displays Local Time.
                local_time_obj = bar.date.astimezone() # Auto-detects system local timezone
                fake_utc_obj = local_time_obj.replace(tzinfo=timezone.utc)
                
                data.append({
                    "time": int(fake_utc_obj.timestamp()),
                    "timestamp": fake_utc_obj.isoformat(), # Use our fake UTC iso for consistency
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume
                })
                
        ib.disconnect()

        # 4. Save to Cache (if enabled)
        if cache and data:
            cache.write(ticker, date_str, data)

        return data
        
    except Exception as e:
        if ib.isConnected():
            ib.disconnect()
        sys.stderr.write(f"IBKR Error: {e}\n")
        return []

def fetch_daily_data(ticker):
    """Fetch daily bars for a ticker (last 60 days)."""
    # Try DB first if we store daily? Assuming DB is mostly intraday for now.
    # For daily, usually safer to go to IB or just return specific daily table if exists.
    # Let's skip DB check for daily unless we implemented daily storage.
    
    sys.stderr.write(f"DEBUG: Connecting to IBKR for Daily Bars {ticker}...\n")
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID + 1) # Use different ID
        
        contract = Stock(ticker, 'SMART', 'USD')
        
        # End now
        endDateTime = datetime.now().strftime('%Y%m%d %H:%M:%S')
        
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='60 D', # 60 days history
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True, 
            formatDate=1
        )
        
        sys.stderr.write(f"DEBUG: Received {len(bars) if bars else 0} daily bars from IBKR\n")
        
        data = []
        if bars:
            for bar in bars:
                data.append({
                    "timestamp": bar.date.isoformat(), # date object for daily bars
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume
                })
                
        ib.disconnect()
        return data
        
    except Exception as e:
        if ib.isConnected():
            ib.disconnect()
        sys.stderr.write(f"IBKR Daily Error: {e}\n")
        return []

def fetch_data_from_db(ticker, date_str):
    """Fetch 1-min bars from trading_data.db if available."""
    import sqlite3
    db_path = os.path.join(PROJECT_ROOT, 'trading_data.db')
    if not os.path.exists(db_path):
        return None
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Join trades to find trade_id for ticker
        # Then join trade_intraday_bars
        query = """
            SELECT b.bar_timestamp, b.open_price, b.high_price, b.low_price, b.close_price, b.volume 
            FROM trade_intraday_bars b
            JOIN trades t ON b.trade_id = t.trade_id
            WHERE t.symbol = ? AND date(b.bar_timestamp) = ?
            ORDER BY b.bar_timestamp ASC
        """
        cursor.execute(query, (ticker, date_str))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
            
        data = []
        for row in rows:
            # timestamp format: try iso, if fail try others
            ts_str = row[0]
            try:
                dt = datetime.fromisoformat(ts_str)
            except:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S') # Fallback
                
            # Convert to chart timestamp (using same Fake UTC logic if needed, or just standard)
            # Assuming DB stores UTC or Local. Let's assume Local for consistency with IBKR logic
            # Actually, DB usually has ISO strings.
            utc_ts = dt.replace(tzinfo=timezone.utc)
            
            data.append({
                "time": int(utc_ts.timestamp()),
                "timestamp": dt.isoformat(), # Keep original ISO
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5]
            })
        return data
        
    except Exception as e:
        sys.stderr.write(f"DB Error: {e}\n")
        return None

def list_tickers_by_date(date_str):
    """List all unique tickers that had opportunities on a specific date (YYYY-MM-DD)."""
    tickers = set()
    try:
        with open(TRADER_LOG, 'r') as f:
            for line in f:
                # Check if line starts with the date
                if line.startswith(date_str):
                    if "Opportunity" in line or "routing" in line:
                         # Extract ticker logic (simplified)
                         # Assuming format: ... Opportunity TICKER ... or ... TICKER routing ...
                         # A robust regex to find uppercase tickers of 2-5 chars
                         matches = re.findall(r'\b[A-Z]{2,5}\b', line)
                         for m in matches:
                             if m not in ['INFO', 'WARN', 'ERROR', 'DEBUG', 'TRADER', 'WBUY', 'NOT', 'OTHER', 'POM', 'TSDD']:
                                 tickers.add(m)
    except FileNotFoundError:
        sys.stderr.write(f"Log file not found: {TRADER_LOG}\n")
        return []

    return sorted(list(tickers))

def main():
    parser = argparse.ArgumentParser(description='Forensic Analysis Data Fetcher')
    parser.add_argument('ticker', nargs='?', help='Ticker symbol (optional if listing)')
    parser.add_argument('--list-tickers', action='store_true', help='List available tickers for a date')
    parser.add_argument('--date', help='Date filter YYYY-MM-DD', default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--use-cache', action='store_true', help='Enable smart caching for market data')
    
    args = parser.parse_args()
    
    if args.list_tickers:
        tickers = list_tickers_by_date(args.date)
        print(json.dumps({"date": args.date, "tickers": tickers}))
        return

    if not args.ticker:
        sys.stderr.write("Error: Ticker is required unless --list-tickers is used.\n")
        sys.exit(1)
    
    # Existing analysis logic
    result = {
        "ticker": args.ticker,
        "generated_at": datetime.now().isoformat(),
        # Pass date if needed for optimizing fetch, keeping simple for now
        "market_data": fetch_market_data(args.ticker, args.date, use_cache=args.use_cache),
        "market_data_daily": fetch_daily_data(args.ticker),
        "events": parse_logs(args.ticker, args.date)
    }
    
    # Output solely JSON to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
