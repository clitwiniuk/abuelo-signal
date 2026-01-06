
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import os

# Connect to DB
DB_PATH = 'trading_data.db'
conn = sqlite3.connect(DB_PATH)

# Rule
# volume_ratio > 1.8 AND score <= 42.1

try:
    # 1. Get ALL Data for Context (and to determine split)
    query_all = """
    SELECT 
        id,
        timestamp,
        quality_score as score,
        volume_ratio,
        max_gain_pct
    FROM scanner_opportunities
    WHERE max_gain_pct IS NOT NULL 
    ORDER BY timestamp ASC
    """
    df_all = pd.read_sql_query(query_all, conn)
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])
    
    # 2. Replicate Split Logic
    total_len = len(df_all)
    if total_len > 1000:
        val_size = 500
    elif total_len > 500:
        val_size = 250
    else:
        val_size = int(total_len * 0.5)
    
    split_idx = total_len - val_size
    train_data = df_all.iloc[:split_idx]
    test_data = df_all.iloc[split_idx:]
    
    split_date = test_data['timestamp'].min() if len(test_data) > 0 else df_all['timestamp'].max()

    print(f"Total Samples: {total_len}")
    print(f"Train Size: {len(train_data)}")
    print(f"Test Size:  {len(test_data)}")
    if len(test_data) > 0:
        print(f"Split Date: {split_date}")

    # 3. Get Rule Matches
    # Rule: volume_ratio > 1.8 AND score <= 42.1
    df_rule = df_all[
        (df_all['volume_ratio'] > 1.8) & 
        (df_all['score'] <= 42.1)
    ]
    
    print(f"\nRule Matches: {len(df_rule)}")
    
    matches_in_train = df_rule[df_rule['timestamp'] < split_date]
    matches_in_test = df_rule[df_rule['timestamp'] >= split_date]
    
    print(f"Matches in Train: {len(matches_in_train)}")
    print(f"Matches in Test:  {len(matches_in_test)}")
    
    # 4. Visualization
    plt.figure(figsize=(12, 6))
    
    # Plot All Opportunities (Background Histogram)
    plt.hist(df_all['timestamp'], bins=50, color='lightgray', label='All Scanner Opps')
    
    # Plot Rule Matches (Scatter)
    # We put them at a fixed height or use max_gain_pct
    # Let's use max_gain_pct to see if they were good
    plt.scatter(
        matches_in_train['timestamp'], 
        [10] * len(matches_in_train), # Fixed height for visibility in histogram view? No, let's overlay on histogram or separate?
        # Actually, let's just plot dots on the X axis, but maybe distinct
        color='blue', label='Rule Match (Train)', s=100, zorder=5, marker='^'
    )
    
    if len(matches_in_test) > 0:
        plt.scatter(
            matches_in_test['timestamp'], 
            [10] * len(matches_in_test),
            color='green', label='Rule Match (Test)', s=100, zorder=5, marker='^'
        )
    
    # Add vertical line for split
    if len(test_data) > 0:
        plt.axvline(x=split_date, color='red', linestyle='--', label='Validation Split')
        # Annotate
        plt.text(split_date, plt.ylim()[1]*0.9, '  Validation Start', color='red')

    plt.title('Distribution of Trades vs Validation Split\nRule: VolRatio > 1.8 AND Score <= 42.1')
    plt.xlabel('Date')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Format Entry
    plt.gcf().autofmt_xdate()
    
    output_path = 'rule_distribution.png'
    plt.savefig(output_path)
    print(f"\nPlot saved to {output_path}")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
