#!/usr/bin/env python3
"""
Optuna Parameter Optimizer (Bayesian Optimization)
==================================================
Uses Optuna to intelligently find the best parameters using TPE (Tree-structured Parzen Estimator).
"""

import sys
import json
import argparse
import asyncio
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import os
import contextlib
import optuna
from concurrent.futures import ThreadPoolExecutor

# Import simulation logic from existing tool
from run_worker_test import (
    run_worker_simulation, 
    calculate_advanced_metrics, 
    get_market_bars, 
    get_historical_scanner_data, 
    get_real_trades
)

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

class OptunaSearch:
    def __init__(self, worker, snapshots, data_cache, params_def, extended_hours=False):
        self.worker = worker
        self.snapshots = snapshots
        self.data_cache = data_cache
        self.params_def = params_def
        self.extended_hours = extended_hours
        self.loop = asyncio.new_event_loop() # Create a dedicated loop for simulations

    async def run_backtest_for_params(self, params):
        """Run backtest across all snapshots for a given param set"""
        tasks = []
        for snap in self.snapshots:
            cached = self.data_cache.get((snap['symbol'], snap['date']))
            tasks.append(run_worker_simulation(
                worker_name=self.worker,
                symbol=snap['symbol'],
                date_str=snap['date'],
                extended_hours=self.extended_hours,
                config_overrides=params,
                cached_data=cached
            ))
        
        with suppress_stdout():
            results = await asyncio.gather(*tasks)
        
        total_pnl = 0.0
        all_trades = []
        wins = 0
        losses = 0
        
        for res in results:
            if res.get('status') == 'success':
                summ = res.get('summary', {})
                total_pnl += summ.get('total_pnl', 0.0)
                all_trades.extend(res.get('completed_trades', []))
                wins += summ.get('winning_trades', 0)
                losses += summ.get('losing_trades', 0)
        
        return {
            'total_pnl': total_pnl,
            'all_trades': all_trades,
            'wins': wins,
            'losses': losses,
            'trades_count': len(all_trades)
        }

    def objective(self, trial):
        """Optuna objective function"""
        # Suggest parameters based on definitions
        params = {}
        for p_name, spec in self.params_def.items():
            is_int = float(spec['step']).is_integer() and float(spec['min']).is_integer() and float(spec['max']).is_integer()
            
            if is_int:
                params[p_name] = trial.suggest_int(p_name, int(spec['min']), int(spec['max']), step=int(spec['step']))
            else:
                params[p_name] = trial.suggest_float(p_name, float(spec['min']), float(spec['max']), step=float(spec['step']))

        # Run backtest using the dedicated loop
        try:
            res = self.loop.run_until_complete(self.run_backtest_for_params(params))
        except Exception as e:
            print(f"Error in trial: {e}", file=sys.__stderr__)
            return -2000.0

        # Score calculation
        if res['trades_count'] == 0:
            return -1000.0 
        
        # Calculate Metrics
        start_capital = 100000.0
        all_trades = sorted(res['all_trades'], key=lambda x: x['exit_time'])
        
        current_equity = start_capital
        peak_equity = start_capital
        max_dd = 0.0
        for t in all_trades:
            current_equity += t['pnl']
            if current_equity > peak_equity: peak_equity = current_equity
            else:
                dd = ((peak_equity - current_equity) / peak_equity) * 100
                max_dd = max(max_dd, dd)
        
        advanced = calculate_advanced_metrics(all_trades, max_dd, start_capital)
        sharpe = advanced['sharpe_ratio']
        pnl = res['total_pnl']
        wr = advanced['win_rate'] / 100.0
        
        # Multi-objective score
        score = pnl * 0.5 + sharpe * 100.0 + wr * 1000.0
        
        trial.set_user_attr("summary", {
            'total_pnl': round(pnl, 2),
            'win_rate': advanced['win_rate'],
            'sharpe_ratio': sharpe,
            'trades': res['trades_count'],
            'max_drawdown': advanced['max_drawdown_pct']
        })
        
        return score

def run_optuna_search_sync(worker, limit, params_def, n_trials=50, extended_hours=False):
    """Main search entry point (Synchronous)"""
    log = lambda msg: print(msg, file=sys.__stderr__)
    
    snapshots = get_recent_snapshots(limit)
    if not snapshots:
        return {'error': 'No data found'}
        
    log(f"🧠 Optuna: Pre-loading data for {len(snapshots)} events...")
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
        except: return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_snapshot_data, snapshots))
        
    for res in results:
        if res:
            snap, data = res
            data_cache[(snap['symbol'], snap['date'])] = data
            valid_snapshots.append(snap)
            
    if not valid_snapshots:
        return {'error': 'No valid snapshots loaded'}

    log(f"🚀 Data ready. Starting Optuna Optimization ({n_trials} trials)...")
    
    search = OptunaSearch(worker, valid_snapshots, data_cache, params_def, extended_hours)
    
    try:
        study = optuna.create_study(direction="maximize")
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study.optimize(search.objective, n_trials=n_trials)
    finally:
        search.loop.close()
    
    log(f"✅ Optuna Completed. Best score: {study.best_value}")
    
    final_results = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE: continue
        
        summ = trial.user_attrs.get("summary", {})
        final_results.append({
            'rank': 0,
            'params': trial.params,
            'summary': {
                'total_pnl': summ.get('total_pnl', 0),
                'win_rate': summ.get('win_rate', 0),
                'sharpe_ratio': summ.get('sharpe_ratio', 0),
                'trades': summ.get('trades', 0),
                'max_drawdown': summ.get('max_drawdown', 0),
                'score': trial.value
            }
        })
    
    final_results.sort(key=lambda x: x['summary'].get('score', 0), reverse=True)
    for i, res in enumerate(final_results):
        res['rank'] = i + 1
        
    return {
        'status': 'success',
        'results': final_results,
        'best_params': study.best_params,
        'trials_completed': len(final_results),
        'scanned_events': len(valid_snapshots)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', required=True)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--params', required=True)
    parser.add_argument('--trials', type=int, default=30)
    parser.add_argument('--extended-hours', action='store_true')
    
    args = parser.parse_args()
    
    try:
        params_def = json.loads(args.params)
        
        # Run everything SYNC to avoid asyncio conflict
        result = run_optuna_search_sync(
            args.worker,
            args.limit,
            params_def,
            args.trials,
            args.extended_hours
        )
        
        print("---JSON_START---")
        print(json.dumps(result))
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.__stderr__)
        print("---JSON_START---")
        print(json.dumps({'status': 'error', 'error': str(e)}))
