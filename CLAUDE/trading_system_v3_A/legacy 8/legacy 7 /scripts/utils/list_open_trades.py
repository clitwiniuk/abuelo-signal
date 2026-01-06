
import sqlite3
import pandas as pd
import os

db_path = "trading_data.db"
conn = sqlite3.connect(db_path)
query = "SELECT symbol, strategy, entry_time FROM trades WHERE status = 'OPEN'"
try:
    df = pd.read_sql_query(query, conn)
    print(f"Total OPEN trades: {len(df)}")
    print(df.to_string())
except Exception as e:
    print(f"Error: {e}")
conn.close()
