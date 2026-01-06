
import vectorbt as vbt
import numpy as np
import pandas as pd
import sqlite3
import json
import argparse
from pathlib import Path
from datetime import datetime
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'trading_data.db'

def load_snapshots(limit=50):
    """Load recent OHLCV snapshots from DB"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT symbol, trading_date, intraday_bars 
    FROM trade_ohlc_snapshots 
    ORDER BY created_at DESC 
    LIMIT ?
    """
    cursor = conn.cursor()
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    datasets = []
    for r in rows:
        symbol, date, data_json = r
        if not data_json: continue
        
        try:
            bars = json.loads(data_json)
            if not bars: continue
            
            df = pd.DataFrame(bars)
            # Ensure columns are correct
            # Map known keys if necessary
            if 'c' in df.columns:
                 df = df.rename(columns={'o':'Open', 'h':'High', 'l':'Low', 'c':'Close', 'v':'Volume', 't':'Timestamp'})
            elif 'close' in df.columns:
                 df = df.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume', 'timestamp':'Timestamp'})
            else:
                 # Standardize to Capitalized
                 df.columns = [c.capitalize() for c in df.columns]
            
            # Convert to numeric
            cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            for c in cols:
                df[c] = pd.to_numeric(df[c])
            
            # Index by timestamp? Not strictly necessary for VBT if simple array, but good practice
            # VBT likes DatetimeIndex
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df.set_index('Timestamp', inplace=True)
            
            datasets.append({
                'symbol': symbol,
                'date': date,
                'df': df
            })
        except Exception as e:
            # print(f"Error loading {symbol}: {e}")
            continue
            
    return datasets

# --- SIGNAL LOGIC (VWAP PROXY) ---
# We define a function that generates signals based on parameters
def vwap_breakout_signals(close, volume, high, low, vwap_window, vol_window, vol_ratio):
    # Calculate VWAP (Approximate using Typical Price and Volume)
    # VBT has vbt.indicators.VWAP but let's do manual for speed/control or use pandas
    # Simple VWAP: cumsum(price*vol) / cumsum(vol) reset daily? 
    # Here we have 1-day snapshots, so simple cumsum is correct.
    
    tp = (high + low + close) / 3
    cum_pv = (tp * volume).cumsum()
    cum_vol = volume.cumsum()
    vwap = cum_pv / cum_vol
    
    # Volume MA
    # Using simple rolling mean
    vol_ma = vbt.MA.run(volume, vol_window).ma
    
    # Conditions
    # 1. Price Cross Above VWAP (or Close > VWAP)
    # 2. Volume > MA * ratio
    
    # We want ENTRY when Close > VWAP AND Volume Spike
    # And maybe we want to catch the CROSS specifically?
    # Let's say: Close > VWAP and PrevClose < VWAP (Crossover)
    
    # VectorBT logic:
    # entries = (close > vwap) & (volume > vol_ma * vol_ratio)
    
    # But strictly speaking, VWAP strategy usually waits for a breakout.
    # Let's define it as: Close > VWAP * 1.0 (at least equal)
    
    entries = (close > vwap) & (volume > (vol_ma * vol_ratio))
    
    # Exits: Fixed pct? Or Cross under?
    # Let's use simple Fixed Stop/Target for research
    return entries

def run_vwap_optimization(datasets):
    print(f"Loaded {len(datasets)} datasets. Running Vector Signal Tuning...")
    
    # PARAMETER RANGES to Test
    vol_ratios = np.arange(0.5, 3.0, 0.5) # 0.5, 1.0, 1.5, 2.0, 2.5
    # We can also verify Stop Loss ranges here
    stop_losses = np.arange(0.01, 0.10, 0.02) # 1%, 3%, 5%, 7%, 9%
    
    results = []
    
    for ds in datasets:
        df = ds['df']
        sym = ds['symbol']
        
        # Run Indicator Factory? Or manual iteration?
        # Manual iteration is easier to read for prototype.
        
        # Calculate Base Indicators ONCE per dataset
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        vol_ma = df['Volume'].rolling(window=20).mean() # Fixed 20-bar avg
        
        # Test Vol Ratios
        for vr in vol_ratios:
            entries = (df['Close'] > vwap) & (df['Volume'] > (vol_ma * vr))
            exits = entries & False # No explicit exit signal, use SL/TP
            
            # Run Simulation for each SL/TP combo
            # vectorbt Portfolio.from_signals can take 2D arrays for entries/sl/tp
            # But let's loop strictly for clarity first.
            
            for sl in stop_losses:
                 tp_pct = sl * 2.0 # Fixed Risk Reward 1:2
                 
                 pf = vbt.Portfolio.from_signals(
                     df['Close'],
                     entries,
                     exits,
                     sl_stop=sl,
                     tp_stop=tp_pct,
                     freq='1m' # Assumption
                 )
                 
                 res_pnl = pf.total_profit()
                 res_trades = pf.trades.count()
                 
                 if res_trades > 0:
                     results.append({
                         'symbol': sym,
                         'vol_ratio': float(vr),
                         'stop_loss': float(sl),
                         'pnl': float(res_pnl),
                         'trades': int(res_trades)
                     })

    # AGGREGATE RESULTS
    # We want to find the "Best Vol Ratio" across ALL symbols
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print(json.dumps({'error': 'No trades generated in any simulation'}))
        return

    # Group by Parameters
    grouped = df_res.groupby(['vol_ratio', 'stop_loss']).agg({
        'pnl': 'sum',
        'trades': 'sum'
    }).reset_index()
    
    # Sort by PnL
    best = grouped.sort_values('pnl', ascending=False).head(5)
    
    output = {
        'best_configs': best.to_dict(orient='records'),
        'total_simulations': len(datasets) * len(vol_ratios) * len(stop_losses)
    }
    
    print(json.dumps(output, indent=2))

def run_daily_plays_optimization(datasets):
    print(f"Loaded {len(datasets)} datasets. Running Daily Plays Optimization...")
    
    # PARAMETER RANGES
    vol_ratios = np.arange(1.0, 5.0, 0.5)
    rsi_thresholds = np.arange(20, 50, 5) # For reversal logic
    stop_losses = np.arange(0.03, 0.15, 0.02)
    
    results = []
    
    for ds in datasets:
        df = ds['df']
        if len(df) < 50: continue # Need history for RSI/MA
        
        sym = ds['symbol']
        
        # INDICATORS
        # Volume MA
        vol_ma = df['Volume'].rolling(window=20).mean()
        
        # RSI (using vectorbt or simple pandas approx)
        # Using VBT for speed/accuracy if available, else pandas
        try:
            rsi = vbt.RSI.run(df['Close'], window=14).rsi
        except:
             # Fallback to simple RSI calculation if vbt fails setup
             delta = df['Close'].diff()
             gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
             loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
             rs = gain / loss
             rsi = 100 - (100 / (1 + rs))

        for vr in vol_ratios:
             # Basic Criteria: Volume Spike + Green Candle
             vol_ok = df['Volume'] > (vol_ma * vr)
             green = df['Close'] > df['Open']
             
             for rsi_thresh in rsi_thresholds:
                  # Strategy: Reversal (Oversold) OR Momentum (Breakout)
                  # Let's verify Reversal first as requested
                  reversal = (rsi < rsi_thresh) & vol_ok & green
                  
                  # Entry signal
                  entries = reversal
                  exits = entries & False
                  
                  for sl in stop_losses:
                       tp_pct = sl * 2.5 # Risk Reward 1:2.5 for Daily Plays
                       
                       # Use VBT Portfolio
                       pf = vbt.Portfolio.from_signals(
                           df['Close'],
                           entries,
                           exits,
                           sl_stop=sl,
                           tp_stop=tp_pct,
                           freq='1m'
                       )
                       
                       res_pnl = pf.total_profit()
                       res_trades = pf.trades.count()
                       
                       if res_trades > 0:
                           results.append({
                               'symbol': sym,
                               'min_volume_ratio': float(vr),
                               'reversal_min_rsi': int(rsi_thresh),
                               'stop_loss': float(sl),
                               'pnl': float(res_pnl),
                               'trades': int(res_trades)
                           })

    # AGGREGATE
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print(json.dumps({'error': 'No trades generated in Daily Plays simulations'}))
        return

    grouped = df_res.groupby(['min_volume_ratio', 'reversal_min_rsi', 'stop_loss']).agg({
        'pnl': 'sum',
        'trades': 'sum'
    }).reset_index()
    
    best = grouped.sort_values('pnl', ascending=False).head(5)
    
    output = {
        'best_configs': best.to_dict(orient='records'),
        'total_simulations': len(datasets) * len(vol_ratios) * len(rsi_thresholds) * len(stop_losses)
    }
    
    print(json.dumps(output, indent=2))

def run_buy_and_hold_optimization(datasets):
    print(f"Loaded {len(datasets)} datasets. Running Buy & Hold Optimization...")
    
    # PARAMETER RANGES
    # Buy & Hold usually has no params, but we can tune Risk Management
    stop_losses = np.arange(0.05, 0.25, 0.05) # 5%, 10%, 15%, 20%
    take_profits = np.arange(0.10, 0.50, 0.10) # 10% to 40% target
    
    results = []
    
    for ds in datasets:
        df = ds['df']
        sym = ds['symbol']
        
        # Simple Logic: Enter on FIRST BAR, hold until exit
        # VectorBT "entries" array: True on first index
        entries = pd.Series(False, index=df.index)
        if len(entries) > 0:
            entries.iloc[0] = True
            
        exits = entries & False # No explicit exits
        
        for sl in stop_losses:
             for tp in take_profits:
                 # VBT Simulation
                 pf = vbt.Portfolio.from_signals(
                     df['Close'],
                     entries,
                     exits,
                     sl_stop=sl,
                     tp_stop=tp,
                     freq='1m'
                 )
                 
                 res_pnl = pf.total_profit()
                 res_trades = pf.trades.count()
                 
                 if res_trades > 0:
                     results.append({
                         'symbol': sym,
                         'stop_loss_pct': float(sl),
                         'take_profit_pct': float(tp),
                         'pnl': float(res_pnl),
                         'trades': int(res_trades)
                     })

    # AGGREGATE
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        # Fallback: simple buy/hold without SL/TP if logic fails (e.g. stops too tight)
        print(json.dumps({'error': 'No trades completed (stops likely too tight)'}))
        return

    grouped = df_res.groupby(['stop_loss_pct', 'take_profit_pct']).agg({
        'pnl': 'sum',
        'trades': 'sum'
    }).reset_index()
    
    best = grouped.sort_values('pnl', ascending=False).head(5)
    
    output = {
        'best_configs': best.to_dict(orient='records'),
        'total_simulations': len(datasets) * len(stop_losses) * len(take_profits)
    }
    
    print(json.dumps(output, indent=2))

def run_trend_surfer_optimization(datasets):
    print(f"Loaded {len(datasets)} datasets. Running Trend Surfer Optimization (Pullback Mode)...")
    
    # PARAMETER RANGES to Test
    adx_thresholds = [15, 20, 25, 30]
    ema_pairs = [(9, 20), (13, 26)] # Fast, Slow
    stop_losses = [0.01, 0.02, 0.03, 0.04] # 1-4%
    
    results = []
    
    for ds in datasets:
        df = ds['df']
        if len(df) < 50: continue
        sym = ds['symbol']
        
        # 1. Base Indicators
        # VWAP
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        vwap = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        
        # ADX (Using simple approximation if pandas_ta/vbt not robust here, 
        # but let's try manual TR/DM calculation for speed without external libs dependence in this minimal script)
        # Simplified ADX approximation or skip if too complex for pure numpy/pandas without ta-lib
        # For prototype, let's use a simpler "Trend Strength" proxy:
        # ABS(Close - SMA(20)) / Close * 100 > Threshold?
        # OR: Just assume ADX is represented by Volume + Price action for now to avoid failing on imports.
        # WAIT, we can do simple ADX in pandas.
        
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # TR
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        
        # DM
        up = high - high.shift()
        down = low.shift() - low
        pos_dm = np.where((up > down) & (up > 0), up, 0)
        neg_dm = np.where((down > up) & (down > 0), down, 0)
        pos_dm_avg = pd.Series(pos_dm, index=df.index).rolling(14).mean()
        neg_dm_avg = pd.Series(neg_dm, index=df.index).rolling(14).mean()
        
        # DI
        pdi = 100 * (pos_dm_avg / atr14)
        ndi = 100 * (neg_dm_avg / atr14)
        dx = 100 * abs(pdi - ndi) / (pdi + ndi)
        adx = dx.rolling(14).mean()
        
        for fast, slow in ema_pairs:
            ema_f = df['Close'].ewm(span=fast, adjust=False).mean()
            ema_s = df['Close'].ewm(span=slow, adjust=False).mean()
            
            # PULLBACK SIGNAL (Mode: Pullback)
            # 1. Trend: Close > VWAP
            trend_ok = df['Close'] > vwap
            
            # 2. Pullback: Low <= EMA_F AND Close > EMA_F (Bounce)
            # OR Low <= EMA_S AND Close > EMA_S
            # Let's check bounce off Fast EMA first
            touch_fast = (df['Low'] <= ema_f) & (df['Close'] > ema_f)
            
            # 3. Green Candle
            green = df['Close'] > df['Open']
            
            for min_adx in adx_thresholds:
                # 4. ADX Filter
                adx_ok = adx > min_adx
                
                entries = trend_ok & touch_fast & green & adx_ok & (df['Volume'] > 0)
                exits = entries & False
                
                for sl in stop_losses:
                    tp = sl * 3.0 # Risk Reward 1:3 for Trend Surfer
                    
                    pf = vbt.Portfolio.from_signals(
                        df['Close'],
                        entries,
                        exits,
                        sl_stop=sl,
                        tp_stop=tp,
                        freq='1m'
                    )
                    
                    if pf.trades.count() > 0:
                        results.append({
                            'symbol': sym,
                            'fast_ema': int(fast),
                            'min_adx': int(min_adx),
                            'stop_loss': float(sl),
                            'pnl': float(pf.total_profit()),
                            'trades': int(pf.trades.count())
                        })

    # AGGREGATE
    df_res = pd.DataFrame(results)
    if df_res.empty:
        print(json.dumps({'error': 'No trades generated in Trend Surfer simulations'}))
        return

    grouped = df_res.groupby(['fast_ema', 'min_adx', 'stop_loss']).agg({
        'pnl': 'sum',
        'trades': 'sum'
    }).reset_index()
    
    best = grouped.sort_values('pnl', ascending=False).head(5)
    
    output = {
        'best_configs': best.to_dict(orient='records'),
        'total_simulations': len(datasets) * len(ema_pairs) * len(adx_thresholds) * len(stop_losses)
    }
    
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', default='vwap')
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    
    data = load_snapshots(args.limit)
    
    worker_clean = args.worker.lower().replace('_worker', '').replace('_strategy', '')
    
    if 'vwap' in worker_clean:
        run_vwap_optimization(data)
    elif 'daily' in worker_clean:
        run_daily_plays_optimization(data)
    elif 'buy' in worker_clean or 'hold' in worker_clean:
        run_buy_and_hold_optimization(data)
    elif 'trend' in worker_clean or 'surfer' in worker_clean:
        run_trend_surfer_optimization(data)
    else:
        print(json.dumps({'error': f'Worker "{args.worker}" not supported yet (only vwap & daily available)'}))
