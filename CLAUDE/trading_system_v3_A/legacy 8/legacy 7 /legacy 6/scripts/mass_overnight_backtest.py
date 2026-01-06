
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
import numpy as np

DB_PATH = "trading_data.db"
STOP_LOSS_PCT = 5.0

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def run_mass_backtest():
    print(f"🚀 STARTING MULTI-DAY CHAIN ANALYSIS (True Overnight Gap)")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch EVERYTHING
    print("   Fetching all snapshots...")
    query = """
    SELECT 
        s.symbol, 
        s.trading_date, 
        s.intraday_bars,
        sig.catalyst_strength,
        sig.quality_score
    FROM trade_ohlc_snapshots s
    LEFT JOIN signal_events sig 
        ON s.symbol = sig.symbol 
        AND sig.created_at LIKE (s.trading_date || '%')
    WHERE length(s.intraday_bars) > 100
    ORDER BY s.trading_date ASC
    """
    
    try:
        cursor.execute(query)
    except:
        query = "SELECT symbol, trading_date, intraday_bars, 0, 0 FROM trade_ohlc_snapshots WHERE length(intraday_bars) > 100"
        cursor.execute(query)
        
    rows = cursor.fetchall()
    conn.close()
    
    # 2. Organize by Symbol -> Date
    print(f"   Processing {len(rows)} snapshots...")
    market_data = {} # {symbol: {date: {close, open, high, low, strength, quality}}}
    
    for row in rows:
        symbol = row[0]
        date_str = row[1]
        json_data = row[2]
        cat_strength = row[3] if row[3] else 0
        quality = row[4] if row[4] else 0
        
        try:
            bars = json.loads(json_data)
            if isinstance(bars, dict): bars = [bars]
            if not bars: continue
            
            # Simple parsing (assuming sorted or strict structure not guaranteed, so precise extraction)
            # We need: Open (09:30), Close (16:00), High, Low
            
            # Convert to list of dicts with 'close', 'timestamp' etc
            # Optimized for speed: just get high/low/close of the blob
            # Note: This is an approximation if we don't parse dates fully, but good enough for mass stat
            
            opens = [b.get('open', 0) for b in bars if b.get('open')]
            closes = [b.get('close', 0) for b in bars if b.get('close')]
            highs = [b.get('high', 0) for b in bars if b.get('high')]
            lows = [b.get('low', 0) for b in bars if b.get('low')]
            
            if not closes: continue
            
            day_open = opens[0]
            day_close = closes[-1]
            day_high = max(highs)
            day_low = min(lows)
            day_range = day_high - day_low
            
            # EOD Strength
            eod_strength = 0.5
            if day_range > 0:
                eod_strength = (day_close - day_low) / day_range
            
            if symbol not in market_data: market_data[symbol] = {}
            market_data[symbol][date_str] = {
                'date': date_str,
                'close': day_close,
                'open': day_open,
                'high': day_high,
                'low': day_low,
                'eod_strength': eod_strength,
                'cat_strength': cat_strength,
                'quality': quality
            }
            
        except:
            continue
            
    # 3. Chain Days (Find T and T+1)
    results = []
    
    for symbol, dates_map in market_data.items():
        sorted_dates = sorted(dates_map.keys())
        
        for i in range(len(sorted_dates) - 1):
            t_date = sorted_dates[i]
            t1_date = sorted_dates[i+1] # Next available snapshot
            
            # Check if dates are close (max 5 days gap for weekends/holidays)
            d1 = datetime.strptime(t_date, "%Y-%m-%d")
            d2 = datetime.strptime(t1_date, "%Y-%m-%d")
            delta = (d2 - d1).days
            
            if delta > 5: continue # Too far apart, not a valid overnight
            
            data_t = dates_map[t_date]
            data_t1 = dates_map[t1_date]
            
            # Key Metric: Overnight Gap
            # (Open T+1 - Close T) / Close T
            gap_pct = ((data_t1['open'] - data_t['close']) / data_t['close']) * 100
            
            results.append({
                'symbol': symbol,
                'date': t_date,
                'eod_strength': data_t['eod_strength'],
                'cat_strength': data_t['cat_strength'],
                'quality': data_t['quality'],
                'gap_pct': gap_pct
            })
            
    analyze_results(results)

def analyze_results(results):
    if not results:
        print("❌ NO MATCHING OVERNIGHT PAIRS FOUND (Need consecutive daily snapshots)")
        return

    df = pd.DataFrame(results)
    print("\n" + "="*60)
    print("📊 TRUE OVERNIGHT GAP ANALYSIS (Multi-Day Chain)")
    print("="*60)
    print(f"Linked Pairs Found: {len(df)}")
    
    # 1. EOD STRENGTH
    print("\n🔹 EOD STRENGTH CORRELATION")
    bins = [0.0, 0.5, 0.7, 0.8, 1.0]
    labels = ["Weak (<50%)", "Mid (50-70%)", "Strong (70-80%)", "Elite (>80%)"]
    df['strength_bucket'] = pd.cut(df['eod_strength'], bins=bins, labels=labels)
    
    print(df.groupby('strength_bucket', observed=False)['gap_pct'].agg(['count', 'mean', lambda x: (x>0).mean()*100]).to_string())
    
    # 2. CATALYST
    if df['cat_strength'].sum() > 0:
        print("\n🔹 CATALYST CORRELATION")
        df['cat_bucket'] = pd.cut(df['cat_strength'], bins=[-1, 4, 7, 11], labels=["Low", "Med", "High"])
        print(df.groupby('cat_bucket', observed=False)['gap_pct'].agg(['count', 'mean', lambda x: (x>0).mean()*100]).to_string())

    # 3. OPTIMIZATION FINDER
    print("\n🧪 OPTIMIZATION TEST:")
    # Try finding the best combo
    best_combo = df[
        (df['eod_strength'] >= 0.80)
    ]
    
    print(f"Filter: Strength >= 0.80")
    print(f"Matches: {len(best_combo)}")
    if not best_combo.empty:
        wr = (best_combo['gap_pct'] > 0).mean() * 100
        avg = best_combo['gap_pct'].mean()
        print(f"Win Rate: {wr:.1f}% | Avg Gap: {avg:+.2f}%")
        
    print("\nCompare to BASELINE:")
    print(f"Win Rate: {(df['gap_pct']>0).mean()*100:.1f}% | Avg Gap: {df['gap_pct'].mean():+.2f}%")

if __name__ == "__main__":
    run_mass_backtest()
