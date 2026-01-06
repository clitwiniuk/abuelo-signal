
import sqlite3
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor, _tree
import argparse
import json
import sys
import os
from datetime import datetime

def get_args():
    parser = argparse.ArgumentParser(description="Find Profitable Rules using Decision Trees")
    parser.add_argument('--db', required=True, help="Path to SQLite DB")
    parser.add_argument('--min-samples', type=int, default=10, help="Min samples per leaf")
    parser.add_argument('--type', help="Filter by Opportunity Type (e.g. SHORT_SQUEEZE)")
    parser.add_argument('--no-validation', action='store_true', help='Skip validation split and use all data')
    parser.add_argument('--start-date', help="Start Date YYYY-MM-DD")
    parser.add_argument('--end-date', help="End Date YYYY-MM-DD")
    return parser.parse_args()

def encode_time_features(df):

    # Extract Hour and Minute from timestamp
    # Timestamp format: 'YYYY-MM-DD HH:MM:SS'
    df['dt'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['dt'].dt.hour
    df['minute'] = df['dt'].dt.minute
    # Encode as 'minutes from midnight' or 'time of day float' 
    # Let's use minutes from market open (09:30) for better relevance
    # Market Open is 9.5 * 60 = 570 mins
    df['market_mins'] = df['hour'] * 60 + df['minute'] - 570
    return df

def tree_to_rules(tree, feature_names):
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    
    rules = []

    def recurse(node, path_rules):
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_name[node]
            threshold = tree_.threshold[node]
            
            # Left Child (<= threshold)
            recurse(tree_.children_left[node], path_rules + [{"feature": name, "op": "<=", "val": threshold}])
            
            # Right Child (> threshold)
            recurse(tree_.children_right[node], path_rules + [{"feature": name, "op": ">", "val": threshold}])
        else:
            # Leaf
            value = tree_.value[node][0][0] # Regression value
            samples = tree_.n_node_samples[node]
            rules.append({
                "value": float(value),
                "samples": int(samples),
                "path": path_rules
            })

    recurse(0, [])
    return rules

def human_readable_rule(rule_list):
    # Condense multiple rules for same feature
    # e.g. score > 50 AND score > 70 -> score > 70
    limits = {}
    
    for r in rule_list:
        feat = r['feature']
        op = r['op']
        val = r['val']
        
        if feat not in limits: limits[feat] = {'min': -float('inf'), 'max': float('inf')}
        
        if op == '>':
            limits[feat]['min'] = max(limits[feat]['min'], val)
        elif op == '<=':
            limits[feat]['max'] = min(limits[feat]['max'], val)
            
    # Format string
    parts = []
    for feat, lim in limits.items():
        if feat == 'market_mins':
            # Convert back to human time roughly
            # Not exact but helps context. 0 = 9:30
            # Just keep as "minutes from open" or ignore for now if complex
            pass
            
        part = ""
        # Nice formatting
        if lim['min'] > -float('inf') and lim['max'] < float('inf'):
            part = f"{lim['min']:.1f} < {feat} <= {lim['max']:.1f}"
        elif lim['min'] > -float('inf'):
            part = f"{feat} > {lim['min']:.1f}"
        elif lim['max'] < float('inf'):
            part = f"{feat} <= {lim['max']:.1f}"
            
        if part: parts.append(part)
        
    return " AND ".join(parts)

def main():
    args = get_args()
    
    conn = sqlite3.connect(args.db)
    
    base_query = """
    SELECT 
        id,
        symbol,
        quality_score as score,
        volume_ratio,
        timestamp,
        vwap_entry,
        current_price,
        max_gain_pct,
        max_loss_pct
    FROM scanner_opportunities
    WHERE max_gain_pct IS NOT NULL 
    AND vwap_entry IS NOT NULL
    """
    
    params = []
    if args.type and args.type.upper() != 'ALL':
        base_query += " AND UPPER(opportunity_type) = ?"
        params.append(args.type.upper())

    if args.start_date:
        base_query += " AND date(timestamp) >= ?"
        params.append(args.start_date)
        
    if args.end_date:
        base_query += " AND date(timestamp) <= ?"
        params.append(args.end_date)
    
    df = pd.read_sql_query(base_query, conn, params=params)
    
    # CRITICAL FIX: Ensure strictly chronological order for Time Series Split
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # DEDUPLICATION LOGIC (Match UI behavior: 1 Play Per Ticker Per Day)
    # We sort by timestamp to keep the earliest alert (First Entry)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['date_only'] = df['timestamp'].dt.date.astype(str)
    
    initial_len = len(df)
    df = df.drop_duplicates(subset=['symbol', 'date_only'], keep='first')
    deduped_len = len(df)
    
    dedup_info = None
    if initial_len != deduped_len:
        dedup_info = f"Deduplicated {initial_len - deduped_len} repeated alerts to match unique daily plays"

    df = df.sort_values('timestamp').reset_index(drop=True)

    # Ensure we keep ID for downstream simulation
    if 'id' not in df.columns:
        # If ID wasn't selected (it wasn't in previous query), we need to select it.
        # My previous edit removed the full SELECT list or I need to check line 108.
        pass 

    conn.close()
    
    if len(df) < 20:
        print(json.dumps({"error": f"Not enough data for type {args.type if args.type else 'ALL'} (min 20 samples, found {len(df)})"}))
        return

    # Basic Feature Eng
    df = encode_time_features(df)
    
    # Indicator Binary
    # 1 if Above VWAP, 0 if Below
    df['above_vwap'] = (df['current_price'] > df['vwap_entry']).astype(int)
    
    # Features for Model
    # We choose interpretables: Score, Volume, Time, VWAP Status
    feature_cols = ['score', 'volume_ratio', 'above_vwap', 'market_mins'] 
    # Note: market_mins helps find structural edges (e.g. "Morning drives" vs "Power Hour")
    # which tend to be more robust than pure volume spikes.
    
    # Feature cols
    X = df[feature_cols].fillna(0)
    y = df['max_gain_pct'].fillna(0)

    # ----------------------------------------------------
    # WALK FORWARD VALIDATION (Dynamic Split)
    # ----------------------------------------------------
    if args.no_validation:
        split_idx = len(df)
        df_train = df
        df_test = pd.DataFrame(columns=df.columns)
    else:
        # ----------------------------------------------------
        # WALK FORWARD VALIDATION (Dynamic Split - Aggressive for Small Data)
        # ----------------------------------------------------
        # Logic:
        # 1. Big Data (> 1000): 500 Val.
        # 2. Medium Data (> 500): 250 Val.
        # 3. Small/Medium (< 500): 50% Split (Maximize Val chance).
        
        total_len = len(df)
        
        if total_len > 1000:
            val_size = 500
        elif total_len > 500:
            val_size = 250
        else:
            val_size = int(total_len * 0.5) # 50% split for < 500
            
        split_idx = total_len - val_size
    
    df_train = df.iloc[:split_idx]
    df_test = df.iloc[split_idx:]
    
    X_train = df_train[feature_cols].fillna(0)
    y_train = df_train['max_gain_pct'].fillna(0)
    
    # Train Model ONLY on Training Set
    # REDUCE COMPLEXITY: max_depth=2 for small datasets (< 1000 samples) to prevent overfitting
    depth = 2 if len(df) < 1000 else 3
    regr = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=args.min_samples)
    regr.fit(X_train, y_train)
    
    raw_rules = tree_to_rules(regr, feature_cols)
    
    # Global Avg (Baseline) from Train
    global_avg_train = y_train.mean()
    
    interesting_rules = []

    # Helper to apply rule list to DF
    def filter_df_by_rules(dataframe, rule_path):
        # FIX: Initialize mask with same index as dataframe to avoid reindexing warning
        mask = pd.Series([True] * len(dataframe), index=dataframe.index)
        for r in rule_path:
            feat = r['feature']
            op = r['op']
            val = r['val']
            if op == '<=':
                mask = mask & (dataframe[feat] <= val)
            else:
                mask = mask & (dataframe[feat] > val)
        return dataframe[mask]
    
    for r in raw_rules:
        # 1. Stats on TRAIN (In-Sample)
        subset_train = filter_df_by_rules(df_train, r['path'])
        if len(subset_train) == 0: continue
        
        avg_gain_train = subset_train['max_gain_pct'].mean()
        wins_train = subset_train[subset_train['max_gain_pct'] > 1.0]
        win_rate_train = len(wins_train) / len(subset_train) * 100
        
        # 2. Stats on TEST (Out-of-Sample / Walk Forward)
        subset_test = filter_df_by_rules(df_test, r['path'])
        
        if len(subset_test) > 0:
            avg_gain_test = subset_test['max_gain_pct'].mean()
            wins_test = subset_test[subset_test['max_gain_pct'] > 1.0]
            win_rate_test = len(wins_test) / len(subset_test) * 100
        else:
            avg_gain_test = 0
            win_rate_test = 0
            
        # Overall Stats (for display, maybe combine?)
        # Actually, let's return both to show robustness
        
        # Filter: Must be good in TRAIN data to be considered a candidate
        if avg_gain_train > global_avg_train * 1.05 and len(subset_train) >= 5:
            readable = human_readable_rule(r['path'])
            interesting_rules.append({
                "rule": readable,
                "samples": len(subset_train) + len(subset_test),
                
                "avg_gain": avg_gain_train, # Show Train as 'Expected'
                "win_rate": win_rate_train,
                
                "test_avg_gain": avg_gain_test, # Show Test as 'Validation'
                "test_win_rate": win_rate_test,
                "test_samples": len(subset_test),
                
                "avg_loss": subset_train['max_loss_pct'].mean() if 'max_loss_pct' in subset_train.columns else 0,
                
                "uplift": (avg_gain_train - global_avg_train) / abs(global_avg_train) * 100,
                
                # Combine IDs for simulation (User might want to sim all)
                # Or just Sim Test? Let's give all.
                "ids": pd.concat([subset_train['id'], subset_test['id']]).tolist(),
                
                # DISTRIBUTION DATA FOR CHARTS
                # FIX: Convert Timestamp to string for JSON serialization
                "distribution": {
                    "train": subset_train[['timestamp', 'max_gain_pct']].assign(timestamp=lambda x: x['timestamp'].astype(str)).to_dict(orient='records'),
                    "test": subset_test[['timestamp', 'max_gain_pct']].assign(timestamp=lambda x: x['timestamp'].astype(str)).to_dict(orient='records')
                }
            })
            
    # Sort by Score (Win Rate * Avg Gain is a good combo metric)
    interesting_rules.sort(key=lambda x: x['avg_gain'] * x['win_rate'], reverse=True)
    
    # Feature Importance
    importances = dict(zip(feature_cols, regr.feature_importances_))
    importances = {k: float(v) for k, v in sorted(importances.items(), key=lambda item: item[1], reverse=True)}

    output = {
        "global_avg_gain": float(global_avg_train),
        "total_samples": len(df),
        "test_split_date": str(df_test['timestamp'].min()) if len(df_test) > 0 else None,
        "debug_meta": {
             "train_count": len(df_train),
             "test_count": len(df_test),
             "train_range": [str(df_train['timestamp'].min()), str(df_train['timestamp'].max())] if not df_train.empty else [],
             "test_range": [str(df_test['timestamp'].min()), str(df_test['timestamp'].max())] if not df_test.empty else [],
             "deduplication_info": dedup_info
        },
        "feature_importance": importances,
        "rules": interesting_rules
    }
    
    print(json.dumps(output))

if __name__ == "__main__":
    main()
