
import sqlite3
import pandas as pd
import os

db_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/trading_data.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        
        print("--- RPTX Status ---")
        query_rptx = "SELECT symbol, status, entry_time, exit_time, side, quantity, strategy FROM trades WHERE symbol = 'RPTX' ORDER BY entry_time DESC LIMIT 5"
        try:
            df_rptx = pd.read_sql_query(query_rptx, conn)
            if df_rptx.empty:
                print("RPTX not found in trades table.")
            else:
                print(df_rptx.to_string())
        except Exception as e:
            print(f"Error querying RPTX: {e}")

        print("\n--- MSTX Status ---")
        query_mstx = "SELECT symbol, status, entry_time, exit_time, side, quantity, strategy FROM trades WHERE symbol = 'MSTX' ORDER BY entry_time DESC LIMIT 5"
        try:
            df_mstx = pd.read_sql_query(query_mstx, conn)
            if df_mstx.empty:
                print("MSTX not found in trades table.")
            else:
                print(df_mstx.to_string())
        except Exception as e:
            print(f"Error querying MSTX: {e}")
            
        conn.close()
    except Exception as e:
        print(f"Error opening database: {e}")
