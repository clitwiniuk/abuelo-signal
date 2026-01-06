import sqlite3
import pandas as pd

db_path = 'trading_data.db'
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables found:", [t[0] for t in tables])
    
    # Check for likely OHLC tables
    target_tables = ['trade_ohlc_snapshots', 'market_data_1min', 'ohlc_1min', 'bars']
    found_table = None
    for t in target_tables:
        if t in [tbl[0] for tbl in tables]:
            found_table = t
            break
            
    if found_table == 'trade_ohlc_snapshots':
        print(f"\nListing available snapshots in {found_table}:")
        query = "SELECT id, symbol, trading_date, gap_percent, day_volume FROM trade_ohlc_snapshots ORDER BY id DESC LIMIT 20"
        df = pd.read_sql_query(query, conn)
        print(df)
        
        # Check if we have specific tickers
        runners = ['HOLO', 'CNSP', 'LIVR']
        for r in runners:
            res = pd.read_sql_query(f"SELECT id, symbol, trading_date FROM trade_ohlc_snapshots WHERE symbol='{r}'", conn)
            if not res.empty:
                print(f"\nFound {r}:")
                print(res)

    conn.close()
except Exception as e:
    print(f"Error: {e}")
