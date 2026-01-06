#!/usr/bin/env python3
"""
Grid Search Parameter Optimizer
===============================
Runs massive backtests across a grid of parameter combinations to find the optimal configuration.
"""

import sys
import json
import argparse
import asyncio
import itertools
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import os
import contextlib
from concurrent.futures import ThreadPoolExecutor

# Import simulation logic from existing tool
from run_worker_test import run_worker_simulation, calculate_advanced_metrics, get_market_bars, get_historical_scanner_data, get_real_trades

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'trading_data.db'

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

def get_recent_snapshots(limit=50):
    """Fetch recent N unique symbol/date pairs from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT symbol, trading_date 
        FROM trade_ohlc_snapshots 
        ORDER BY trading_date DESC, symbol ASC
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [{'symbol': r[0], 'date': r[1]} for r in rows]

def generate_grid(params_def):
    """
    Generate list of parameter combinations from definition.
    params_def provided as dict: { 'param_name': {'min': 1, 'max': 5, 'step': 1}, ... }
    """
    keys = []
    value_ranges = []
    
    for key, spec in params_def.items():
        keys.append(key)
        start = float(spec['min'])
        end = float(spec['max'])
        step = abs(float(spec['step'])) # Force positive step
        
        if start > end:
            # Auto-swap if user messed up
            start, end = end, start
            
        if step == 0:
            step = 1.0 # Avoid division by zero, though logic below handles it
        
        # Generator range
        # If start == end, arange usually returns [start] if 2nd arg is > start
        # We ensure at least one value
        if start == end:
             value_ranges.append([start])
             continue
             
        # Generate range. Use np.arange for float steps, but be careful with precision
        # Add epsilon to include 'end' if it aligns exactly
        vals = np.arange(start, end + (step/1000.0), step).tolist()
        
        # Round to avoid 0.30000000004
        vals = [round(x, 4) for x in vals]
        value_ranges.append(vals)
        
    # Cartesian product
    product = list(itertools.product(*value_ranges))
    
    combinations = []
    for values in product:
        combinations.append(dict(zip(keys, values)))
        
    return combinations

async def run_grid_search(worker, limit, params_def, extended_hours=False, sort_by='total_pnl'):
    # Helper to print safely to stderr
    def log(msg):
        print(msg, file=sys.__stderr__)

    snapshots = get_recent_snapshots(limit)
    if not snapshots:
        return {'error': 'No data found in trade_ohlc_snapshots'}
        
    combinations = generate_grid(params_def)
    
    if len(combinations) == 0:
        return {'error': 'No parameter combinations generated'}
        
    MAX_COMBINATIONS = 100
    if len(combinations) > MAX_COMBINATIONS:
        # Prevent explosion
        log(f"⚠️ Warning: Too many combinations ({len(combinations)}). Trimming to first {MAX_COMBINATIONS}.")
        combinations = combinations[:MAX_COMBINATIONS]
        
    log(f"🚀 Starting Grid Search: {worker} | {len(combinations)} Configs x {len(snapshots)} Events | ExtHours={extended_hours}")
    
    # Store aggregated results per combination index
    # results[idx] = { ... stats ... }
    comb_results = [
        {
            'params': comb,
            'total_pnl': 0.0,
            'trades_count': 0,
            'wins': 0,
            'losses': 0,
            'all_trades': [],
            'config_id': i,
            'rejection_reasons': {} # Track why trades were skipped
        }
        for i, comb in enumerate(combinations)
    ]
    
    # Concurrency limit
    sem = asyncio.Semaphore(15) 
    
    async def run_sim_for_comb(start_comb_idx, end_comb_idx):
        pass # Unused

    # --- DATA PRE-FETCHING (Performance Optimization) ---
    log(f"🧠 Pre-loading data for {len(snapshots)} events into RAM (Parallel)...")
    data_cache = {}
    valid_snapshots = []
    
    def fetch_snapshot_data(snap):
        sym = snap['symbol']
        dt = snap['date']
        try:
            bars = get_market_bars(sym, dt)
            if not bars: return None
            
            scn = get_historical_scanner_data(sym, dt)
            trd = get_real_trades(sym, dt)
            return (snap, {'bars': bars, 'scanner_data': scn, 'real_trades': trd})
        except Exception as e:
            # log(f"⚠️ Error loading {sym}: {e}")
            return None

    # Use ThreadPool to blast through IO
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_snapshot_data, snapshots))
        
    for res in results:
        if res:
            snap, data = res
            data_cache[(snap['symbol'], snap['date'])] = data
            valid_snapshots.append(snap)

    snapshots = valid_snapshots
    log(f"✅ Data loaded ({len(data_cache)} events ready). Starting Grid...")

    # Flatten tasks: (comb_idx, snapshot)
    tasks = []
    
    total_sims = len(combinations) * len(snapshots)
    completed_sims = 0
    
    async def execute_sim(comb_idx, params, snap):
        nonlocal completed_sims
        async with sem:
            try:
                # Retrieve from Cache
                cached = data_cache.get((snap['symbol'], snap['date']))
                
                with suppress_stdout():
                    res = await run_worker_simulation(
                        worker_name=worker,
                        symbol=snap['symbol'],
                        date_str=snap['date'],
                        extended_hours=extended_hours,
                        config_overrides=params,
                        cached_data=cached # INJECT CACHE
                    )
                
                # Update progress
                completed_sims += 1
                if completed_sims % 25 == 0 or completed_sims == total_sims:
                     pct = int((completed_sims / total_sims) * 100)
                     log(f"⚡ Progress: {completed_sims}/{total_sims} ({pct}%)")

                return comb_idx, res
            except Exception as e:
                completed_sims += 1
                return comb_idx, {'status': 'error', 'error': str(e)}

    for idx, comb in enumerate(combinations):
        for snap in snapshots:
            tasks.append(execute_sim(idx, comb, snap))
            
    # Run all
    results = await asyncio.gather(*tasks)
    
    # Aggregate
    for comb_idx, res in results:
        stats = comb_results[comb_idx]
        
        if res.get('status') == 'error':
            rej = f"CRASH: {res.get('error')}"
            stats['rejection_reasons'][rej] = stats['rejection_reasons'].get(rej, 0) + 1
            continue

        if res.get('status') == 'success':
            summ = res.get('summary', {})
            trades = res.get('completed_trades', [])
            
            stats['total_pnl'] += summ.get('total_pnl', 0.0)
            stats['trades_count'] += summ.get('trades_count', 0)
            stats['wins'] += summ.get('winning_trades', 0)
            stats['losses'] += summ.get('losing_trades', 0)
            stats['all_trades'].extend(trades)
            
            # Aggregate rejection reasons
            rej = summ.get('rejection_reason')
            if summ.get('trades_count', 0) == 0:
                if not rej: rej = "Silent (No Reason)"
                stats['rejection_reasons'][rej] = stats['rejection_reasons'].get(rej, 0) + 1

    # Finalize Metrics
    final_report = []
    
    for stats in comb_results:
        # Global metrics for this config
        all_trades = sorted(stats['all_trades'], key=lambda x: x['exit_time'])
        start_capital = 100000.0
        
        current_equity = start_capital
        peak_equity = start_capital
        max_dd = 0.0
        
        for t in all_trades:
            current_equity += t['pnl']
            if current_equity > peak_equity:
                peak_equity = current_equity
            else:
                dd = ((peak_equity - current_equity) / peak_equity) * 100
                max_dd = max(max_dd, dd)
                
        advanced = calculate_advanced_metrics(all_trades, max_dd, start_capital)
        
        # Determine dominant rejection reason
        top_rejection = "N/A"
        if stats['trades_count'] == 0 and stats['rejection_reasons']:
             # Find max
             top_rejection = max(stats['rejection_reasons'], key=stats['rejection_reasons'].get)
             # Add count info? e.g. "Not ready (50x)"
             count = stats['rejection_reasons'][top_rejection]
             # If string handles count already, just simplify
             if "(" in top_rejection:
                  # It was pre-formatted in single sim result, but we aggregated counts of strings
                  # e.g. "Not ready (3x)" appeared 5 times.
                  # Just take the string as is
                  pass
             else:
                  top_rejection = f"{top_rejection} (Across {count} sims)"
        
        final_report.append({
            'rank': 0, # To be filled
            'params': stats['params'],
            'summary': {
                'total_pnl': round(stats['total_pnl'], 2),
                'win_rate': advanced['win_rate'],
                'profit_factor': advanced['profit_factor'],
                'max_drawdown': advanced['max_drawdown_pct'],
                'sharpe_ratio': advanced['sharpe_ratio'],
                'trades': stats['trades_count'],
                'blocker': top_rejection if stats['trades_count'] == 0 else None
            }
        })
        
    # Sort
    sort_key_map = {
        'total_pnl': lambda x: x['summary']['total_pnl'],
        'sharpe_ratio': lambda x: x['summary']['sharpe_ratio'],
        'win_rate': lambda x: x['summary']['win_rate']
    }
    key_func = sort_key_map.get(sort_by, sort_key_map['total_pnl'])
    final_report.sort(key=key_func, reverse=True)
    
    # Add Rank
    for i, item in enumerate(final_report):
        item['rank'] = i + 1
        
    return {
        'status': 'success',
        'results': final_report,
        'scanned_events': len(snapshots),
        'combinations_tested': len(final_report)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Grid Search Optimization')
    parser.add_argument('--worker', required=True, help='Worker name')
    parser.add_argument('--limit', type=int, default=50, help='Number of recent events')
    parser.add_argument('--params', required=True, help='JSON string of parameter ranges')
    parser.add_argument('--sort', default='total_pnl')
    parser.add_argument('--extended-hours', action='store_true', help='Enable extended hours')
    
    args = parser.parse_args()
    
    try:
        params_def = json.loads(args.params)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(run_grid_search(
            args.worker,
            args.limit,
            params_def,
            args.extended_hours,
            args.sort
        ))
        
        print("---JSON_START---")
        print(json.dumps(result, cls=json.JSONEncoder))
        
    except Exception as e:
        print("---JSON_START---")
        print(json.dumps({'status': 'error', 'error': str(e)}))
    finally:
        if 'loop' in locals():
            loop.close()
