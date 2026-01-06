#!/usr/bin/env python3
"""
Massive Backtest Optimizer
==========================
Runs batch simulations for multiple workers across historical data to identify the best strategy.
"""

import sys
import json
import logging
import argparse
import asyncio
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import os

# Set suppression flag BEFORE importing anything else that might setup logging
os.environ['SUPPRESS_WORKER_STDOUT'] = 'true'

from datetime import datetime, date, time, timedelta

# Import simulation logic from existing tool
from run_worker_test import run_worker_simulation, calculate_advanced_metrics

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'trading_data.db'

def get_recent_snapshots(limit=50):
    """Fetch recent N unique symbol/date pairs from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get distinct pairs, ordered by date desc
    query = """
        SELECT DISTINCT symbol, trading_date 
        FROM trade_ohlc_snapshots 
        ORDER BY trading_date DESC, symbol ASC
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    # Return as list of dicts
    return [{'symbol': r[0], 'date': r[1]} for r in rows]

import os
import contextlib

@contextlib.contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

async def run_optimizer(workers, limit, sort_by='total_pnl', overrides=None, pos_value=None, pos_size=None, timeframe='1min'):
    """
    Run simulations for all specified workers against the recent N snapshots.
    """
    overrides = overrides or {}
    snapshots = get_recent_snapshots(limit)
    
    if not snapshots:
        return {'error': 'No data found in trade_ohlc_snapshots'}

    # Use original stderr for progress logging to avoid suppression
    print(f"🚀 Starting Optimization: {len(workers)} workers x {len(snapshots)} events = {len(workers)*len(snapshots)} simulations...", file=sys.__stderr__)
    
    # Structure to hold aggregated results per worker
    worker_results = {w: {
        'total_pnl': 0.0,
        'gross_pnl': 0.0, 
        'commission': 0.0,
        'trades': 0,
        'wins': 0,
        'losses': 0,
        'equity_curve': [], # Aggregate equity curve
        'all_trades': [],    # List of all trade records
        'snap_count': 0
    } for w in workers}
    
    # Semaphore to limit concurrency (don't kill the CPU/DB)
    sem = asyncio.Semaphore(10) # 10 concurrent sims
    
    async def run_single_sim(worker, snap):
        async with sem:
            try:
                # Get overrides for this specific worker if they exist
                worker_overrides = overrides.get(worker)
                
                # Run simulation (Do NOT suppress stdout globally as it breaks async loop stdout restoration)
                res = await run_worker_simulation(
                    worker_name=worker,
                    symbol=snap['symbol'],
                    date_str=snap['date'],
                    extended_hours=False,
                    config_overrides=worker_overrides,
                    pos_value=pos_value,
                    pos_size=pos_size,
                    timeframe=timeframe
                )
                return worker, res
            except Exception as e:
                # Return basic error structure to prevent crash
                return worker, {'status': 'error', 'error': str(e)}

    # Create tasks
    tasks = []
    for worker in workers:
        for snap in snapshots:
            tasks.append(run_single_sim(worker, snap))
            
    # Run all
    results = await asyncio.gather(*tasks)
    
    # Process Results
    for worker_name, res in results:
        w_stats = worker_results[worker_name]
        w_stats['snap_count'] += 1
        
        if res.get('status') == 'success':
            summ = res.get('summary', {})
            trades = res.get('completed_trades', [])
            
            # Aggregate PnL
            w_stats['total_pnl'] += summ.get('total_pnl', 0.0)
            w_stats['gross_pnl'] += summ.get('gross_pnl', 0.0)
            w_stats['commission'] += summ.get('total_commission', 0.0)
            
            # Aggregate Counts
            w_stats['trades'] += summ.get('trades_count', 0)
            w_stats['wins'] += summ.get('winning_trades', 0)
            w_stats['losses'] += summ.get('losing_trades', 0)
            
            # Collect trades for global metrics
            w_stats['all_trades'].extend(trades)

    # Calculate Global Metrics for each worker
    final_report = []
    
    for worker, stats in worker_results.items():
        # Avoid division by zero
        start_capital = 100000.0 # Virtual starting capital for "Portfolio"
        
        # Calculate Equity Curve (Portfolio simulation)
        # Sort all trades by exit_time
        all_trades = sorted(stats['all_trades'], key=lambda x: x['exit_time'])
        
        current_equity = start_capital
        equity_curve = [{'timestamp': 'START', 'equity': start_capital}]
        peak_equity = start_capital
        max_dd = 0.0
        
        for t in all_trades:
            current_equity += t['pnl']
            equity_curve.append({
                'timestamp': t['exit_time'],
                'equity': current_equity
            })
            
            # Drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
            else:
                dd = ((peak_equity - current_equity) / peak_equity) * 100
                max_dd = max(max_dd, dd)
        
        # Calculate Advanced Metrics on the GLOBAL trade list
        advanced = calculate_advanced_metrics(all_trades, max_dd, start_capital)
        
        report_item = {
            'worker': worker,
            'overrides': overrides.get(worker, {}), # Include the parameters used
            'summary': {
                'total_pnl': round(stats['total_pnl'], 2),
                'gross_pnl': round(stats['gross_pnl'], 2),
                'commission': round(stats['commission'], 2),
                'trades': stats['trades'],
                **advanced # Include all advanced metrics (Win Rate, Expectancy, Recovery, etc.)
            },
            'equity_curve': equity_curve # For plotting overlay
        }
        final_report.append(report_item)
        
    # Sort
    sort_key_map = {
        'total_pnl': lambda x: x['summary']['total_pnl'],
        'sharpe_ratio': lambda x: x['summary']['sharpe_ratio'],
        'win_rate': lambda x: x['summary']['win_rate']
    }
    key_func = sort_key_map.get(sort_by, sort_key_map['total_pnl'])
    final_report.sort(key=key_func, reverse=True)
    
    return {
        'status': 'success',
        'report': final_report,
        'scanned_events': len(snapshots)
    }


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON Encoder for DateTime and NumPy types"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(DateTimeEncoder, self).default(obj)

def sanitize_data(data):
    """Recursively replace NaN/Inf with None for JSON compliance"""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple, set)):
        # Convert all sequences to lists to ensure mutability/compatibility
        return [sanitize_data(v) for v in data]
    elif isinstance(data, float):
        if np.isnan(data) or np.isinf(data):
            return None
        return data
    elif isinstance(data, (np.floating, float)): # Catch numpy floats too
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    elif isinstance(data, (np.integer, int)):
        return int(data)
    elif isinstance(data, np.ndarray):
        return sanitize_data(data.tolist())
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Massive Backtest Optimization')
    parser.add_argument('--workers', required=True, help='Comma separated workers list')
    parser.add_argument('--limit', type=int, default=50, help='Number of recent events to test')
    parser.add_argument('--sort', default='total_pnl', help='Metric to sort results by')
    parser.add_argument('--overrides', help='JSON string of per-worker overrides')
    parser.add_argument('--pos-value', type=float, help='Fixed investment amount in dollars')

    parser.add_argument('--pos-size', type=int, help='Fixed share count')
    parser.add_argument('--timeframe', default='1min', choices=['1min', '3min', '5min', '15min', '30min', '1h'], help='Bar interval for simulation')
    
    args = parser.parse_args()
    
    worker_list = [w.strip() for w in args.workers.split(',')]
    
    # Parse overrides if provided
    overrides_dict = {}
    if args.overrides:
        try:
            overrides_dict = json.loads(args.overrides)
        except Exception as e:
            print(f"Error parsing overrides JSON: {e}", file=sys.stderr)
    
    # SILENCE LOGGING TO PREVENT STDOUT POLLUTION
    # This is critical because workers might print INFO/WARN logs to stdout, breaking JSON parsing.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Also silence specific known loggers if necessary
    logging.getLogger('Worker').setLevel(logging.CRITICAL)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    final_output = ""
    try:
        result = loop.run_until_complete(run_optimizer(
            worker_list,
            args.limit,
            args.sort,
            overrides=overrides_dict,
            pos_value=args.pos_value,
            pos_size=args.pos_size,
            timeframe=args.timeframe
        ))
        
        # Buffer output first to catch serialization errors BEFORE printing marker
        # Clean data (remove NaNs which break Node.js JSON.parse)
        clean_result = sanitize_data(result)
        final_output = json.dumps(clean_result, cls=DateTimeEncoder)
        
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        final_output = json.dumps({'status': 'error', 'error': str(e)})
        
    finally:
        loop.close()
        
    # Atomic print to ensure cleaner stream
    print("---JSON_START---")
    print(final_output)
