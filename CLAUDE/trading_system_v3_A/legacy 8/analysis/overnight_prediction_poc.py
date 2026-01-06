import sqlite3
import pandas as pd
from yahooquery import Ticker
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import time

def get_catalyst_data(db_path='trading_data.db'):
    """Fetch catalyst opportunities from the database."""
    print("Fetching catalyst data from database...")
    conn = sqlite3.connect(db_path)
    query = """
        SELECT 
            symbol, 
            date(timestamp) as scan_date,
            catalyst_type, 
            catalyst_strength, 
            gap_percentage, 
            volume_ratio,
            quality_score
        FROM scanner_opportunities 
        WHERE catalyst_type IS NOT NULL 
          AND catalyst_type != 'NONE'
        GROUP BY symbol, date(timestamp)
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"Found {len(df)} catalyst events.")
    return df

def fetch_price_history(df):
    """Fetch daily OHLC data for symbols around the scan date."""
    print("Fetching price history from yahooquery (this may take a while)...")
    
    results = []
    unique_symbols = df['symbol'].unique()
    
    # Process in chunks to be nice to the API
    chunk_size = 50
    for i in range(0, len(unique_symbols), chunk_size):
        chunk = unique_symbols[i:i+chunk_size]
        print(f"Processing chunk {i//chunk_size + 1}/{(len(unique_symbols)-1)//chunk_size + 1}...")
        
        try:
            # Download batch data
            # yahooquery expects a list of symbols or a string separated by spaces
            # It returns a MultiIndex DataFrame (symbol, date)
            t = Ticker(chunk, asynchronous=True)
            data = t.history(period="6mo")
            
            if data.empty:
                continue
                
            # Check if 'symbol' is in index (it should be for valid results)
            if 'symbol' not in data.index.names:
                # Sometimes it returns just date index if single symbol? 
                # But we are passing a list usually.
                # If it failed for all, it might return empty or different structure.
                continue

            for symbol in chunk:
                symbol_events = df[df['symbol'] == symbol]
                
                if symbol not in data.index:
                    continue
                    
                symbol_data = data.loc[symbol]
                
                if symbol_data.empty:
                    continue
                    
                for _, event in symbol_events.iterrows():
                    scan_date = pd.to_datetime(event['scan_date']).tz_localize(None)
                    
                    # Find the row for scan_date
                    try:
                        # Convert scan_date to date object for matching with yahooquery index
                        scan_date_obj = scan_date.date()
                        
                        # Get index location of scan_date
                        # symbol_data index is the date (datetime.date objects)
                        if scan_date_obj not in symbol_data.index:
                            # Try to find nearest previous trading day if exact match fails
                            # But for this POC, let's be strict to ensure data quality
                            continue
                            
                        loc = symbol_data.index.get_loc(scan_date_obj)
                        
                        # We need current day (T) and next 3 days for runner analysis
                        if loc + 3 >= len(symbol_data):
                            continue
                            
                        day_t = symbol_data.iloc[loc]
                        day_t1 = symbol_data.iloc[loc + 1]
                        
                        # Get next 3 days high prices to see if it ran
                        next_3_days = symbol_data.iloc[loc+1 : loc+4]
                        max_price_3d = next_3_days['high'].max()
                        
                        # Calculate returns
                        # Intraday Return: (close - open) / open
                        intraday_return = (day_t['close'] - day_t['open']) / day_t['open']
                        
                        # Overnight Return: (Open_T+1 - Close_T) / Close_T
                        overnight_return = (day_t1['open'] - day_t['close']) / day_t['close']
                        
                        # Max Return next 3 days from Day 0 Close
                        max_return_3d = (max_price_3d - day_t['close']) / day_t['close']
                        
                        results.append({
                            **event.to_dict(),
                            'intraday_return': intraday_return,
                            'overnight_return': overnight_return,
                            'max_return_3d': max_return_3d,
                            'close_price': day_t['close'],
                            'volume': day_t['volume']
                        })
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"Error processing chunk: {e}")
            
    return pd.DataFrame(results)

def fetch_key_stats(df):
    """Fetch Float and Short Interest data."""
    print("Fetching Key Stats (Float, Short Interest)...")
    unique_symbols = df['symbol'].unique()
    stats_data = {}
    
    chunk_size = 100
    for i in range(0, len(unique_symbols), chunk_size):
        chunk = unique_symbols[i:i+chunk_size]
        print(f"Fetching stats chunk {i//chunk_size + 1}...")
        try:
            t = Ticker(chunk, asynchronous=True)
            data = t.get_modules('defaultKeyStatistics summaryDetail')
            
            for symbol in chunk:
                if isinstance(data, dict) and symbol in data:
                    try:
                        s_stats = data[symbol].get('defaultKeyStatistics', {})
                        s_summary = data[symbol].get('summaryDetail', {})
                        
                        if isinstance(s_stats, str) or isinstance(s_summary, str):
                            # Sometimes yahooquery returns error string
                            continue
                            
                        stats_data[symbol] = {
                            'float_shares': s_stats.get('floatShares'),
                            'short_ratio': s_stats.get('shortRatio'),
                            'short_percent': s_stats.get('shortPercentOfFloat')
                        }
                    except:
                        continue
        except Exception as e:
            print(f"Error fetching stats: {e}")
            
    return stats_data

def analyze_and_train(df):
    """Analyze correlations and train a simple model."""
    
    # Fetch and merge stats
    stats_map = fetch_key_stats(df)
    
    # Add stats to DF
    df['float_shares'] = df['symbol'].map(lambda x: stats_map.get(x, {}).get('float_shares'))
    df['short_ratio'] = df['symbol'].map(lambda x: stats_map.get(x, {}).get('short_ratio'))
    df['short_percent'] = df['symbol'].map(lambda x: stats_map.get(x, {}).get('short_percent'))
    
    # Fill missing with median to avoid dropping too many
    df['float_shares'] = df['float_shares'].fillna(df['float_shares'].median())
    df['short_percent'] = df['short_percent'].fillna(0)
    
    print("\n" + "="*50)
    print("MULTI-DAY RUNNER ANALYSIS (WITH SHORT DATA)")
    print("="*50)
    
    print(f"Successfully analyzed {len(df)} events with price data.")
    
    if len(df) < 50:
        print("Not enough data for reliable analysis.")
        return

    # Define a "Runner" as > 20% gain in next 3 days
    RUNNER_THRESHOLD = 0.20
    df['is_runner'] = df['max_return_3d'] > RUNNER_THRESHOLD
    
    runners = df[df['is_runner']]
    non_runners = df[~df['is_runner']]
    
    print(f"\nFound {len(runners)} Multi-Day Runners (>20% in 3 days) out of {len(df)} events.")
    print(f"Runner Rate: {len(runners)/len(df):.2%}")
    
    if len(runners) == 0:
        print("No runners found. Lower the threshold?")
        return

    # Compare Stats
    print("\n--- Runners vs Non-Runners (Mean Values) ---")
    cols = ['catalyst_strength', 'gap_percentage', 'volume_ratio', 'intraday_return', 'float_shares', 'short_percent']
    comparison = df.groupby('is_runner')[cols].mean()
    # Format float for readability
    pd.options.display.float_format = '{:.4f}'.format
    print(comparison)
    
    # 4. Best Setup Identification (Reverse Engineering)
    print("\n--- Potential 'Short Squeeze' Filters ---")
    
    avg_rate = len(runners)/len(df)
    
    # Test Squeeze Filter: Low Float + High Short Interest
    # Float < 20M, Short > 5%
    squeeze_subset = df[
        (df['float_shares'] < 20_000_000) & 
        (df['short_percent'] > 0.05)
    ]
    
    if len(squeeze_subset) > 0:
        squeeze_rate = squeeze_subset['is_runner'].mean()
        print(f"\nFilter: Float < 20M AND Short% > 5%")
        print(f"Sample Size: {len(squeeze_subset)}")
        print(f"Win Rate: {squeeze_rate:.2%} (vs Baseline {avg_rate:.2%})")
    else:
        print("\nNo events matched the Squeeze Filter (Float < 20M, Short > 5%)")

    # Grid Search for best Squeeze Combo
    best_filter = None
    best_rate = 0
    
    for float_cap in [10_000_000, 20_000_000, 50_000_000]:
        for short_floor in [0.05, 0.10, 0.20]:
            subset = df[
                (df['float_shares'] < float_cap) & 
                (df['short_percent'] > short_floor)
            ]
            if len(subset) > 10:
                rate = subset['is_runner'].mean()
                if rate > best_rate:
                    best_rate = rate
                    best_filter = f"Float < {float_cap/1_000_000}M AND Short% > {short_floor:.0%}"
                    
    print(f"\nBest Squeeze Filter Found: {best_filter}")
    print(f"Win Rate: {best_rate:.2%}")
    
if __name__ == "__main__":
    catalyst_df = get_catalyst_data()
    if not catalyst_df.empty:
        full_df = fetch_price_history(catalyst_df)
        if not full_df.empty:
            analyze_and_train(full_df)
            
            # Save results
            full_df.to_csv('analysis/overnight_analysis_results.csv', index=False)
            print("\nDetailed results saved to 'analysis/overnight_analysis_results.csv'")
        else:
            print("Could not fetch price history.")
    else:
        print("No catalyst data found.")
