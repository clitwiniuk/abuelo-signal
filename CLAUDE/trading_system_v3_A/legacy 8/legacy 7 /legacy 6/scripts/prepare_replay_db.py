#!/usr/bin/env python3
"""
Prepare Replay DB - Extrae datos de trade_ohlc_snapshots para replay
"""

import sqlite3
import json
import argparse
import os
from datetime import datetime
import sys

def main():
    parser = argparse.ArgumentParser(description='Prepare Replay DB from trade snapshots')
    parser.add_argument('--symbol', required=True, help='Symbol to extract')
    parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    parser.add_argument('--trading-db', default='trading_data.db', help='Path to trading_data.db')
    parser.add_argument('--output-db', default='replay_market_data.db', help='Path to output db')
    
    args = parser.parse_args()
    
    # 1. Connect to trading DB and get data
    if not os.path.exists(args.trading_db):
        print(f"❌ Trading DB not found: {args.trading_db}")
        sys.exit(1)
        
    conn_trading = sqlite3.connect(args.trading_db)
    cursor_trading = conn_trading.cursor()
    
    query = """
        SELECT intraday_bars 
        FROM trade_ohlc_snapshots 
        WHERE symbol = ? AND DATE(trading_date) = ?
        LIMIT 1
    """
    
    cursor_trading.execute(query, (args.symbol, args.date))
    row = cursor_trading.fetchone()
    
    if not row:
        print(f"❌ No snapshot found for {args.symbol} on {args.date}")
        sys.exit(1)
        
    json_data = row[0]
    if not json_data:
        print(f"❌ Snapshot found but intraday_bars is empty")
        sys.exit(1)
        
    try:
        bars = json.loads(json_data)
    except json.JSONDecodeError as e:
        print(f"❌ Error decoding JSON: {e}")
        sys.exit(1)
        
    print(f"✅ Found {len(bars)} bars for {args.symbol}")
    conn_trading.close()
    
    # 2. Create Output DB
    if os.path.exists(args.output_db):
        os.remove(args.output_db)
        
    conn_out = sqlite3.connect(args.output_db)
    cursor_out = conn_out.cursor()
    
    # Create table matching market_data.db schema (simplified for replay)
    cursor_out.execute("""
        CREATE TABLE intraday_bars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            bar_timestamp TIMESTAMP NOT NULL,
            open_price REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            close_price REAL NOT NULL,
            volume INTEGER NOT NULL,
            vwap REAL,
            transactions INTEGER,
            source TEXT DEFAULT 'snapshot',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            event_id INTEGER,
            UNIQUE(symbol, bar_timestamp)
        )
    """)
    
    # 3. Insert data
    print("📥 Inserting bars...")
    count = 0
    for bar in bars:
        # Parse timestamp
        # JSON format: "2025-11-21T15:02:00-05:00"
        # We keep it as string for SQLite
        ts = bar.get('timestamp')
        
        cursor_out.execute("""
            INSERT INTO intraday_bars 
            (symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume, vwap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            args.symbol,
            ts,
            bar.get('open'),
            bar.get('high'),
            bar.get('low'),
            bar.get('close'),
            bar.get('volume'),
            bar.get('vwap') # Might be None
        ))
        count += 1
        
    conn_out.commit()
    conn_out.close()
    
    print(f"✅ Successfully created {args.output_db} with {count} bars")

if __name__ == '__main__':
    main()
