
import sqlite3
import pandas as pd

db_path = "trading_data.db"
conn = sqlite3.connect(db_path)
query = "SELECT * FROM trades WHERE symbol = 'SIDU' ORDER BY entry_time DESC LIMIT 1"
try:
    df = pd.read_sql_query(query, conn)
    # Print all columns to check for stop_loss and take_profit
    print(df.T.to_string())
except Exception as e:
    print(f"Error: {e}")
conn.close()
