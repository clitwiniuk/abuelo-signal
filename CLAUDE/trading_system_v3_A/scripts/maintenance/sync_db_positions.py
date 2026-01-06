
import sqlite3
import pandas as pd
import os
from datetime import datetime

db_path = "trading_data.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- STARTING DB SYNC ---")
    
    # 1. Re-open RPTX
    # FIND the last CLOSED trade for RPTX
    cursor.execute("SELECT id, entry_time FROM trades WHERE symbol = 'RPTX' AND status = 'CLOSED' ORDER BY entry_time DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        trade_id = row[0]
        print(f"Found CLOSED RPTX trade (ID: {trade_id}, Entry: {row[1]}). Re-opening...")
        cursor.execute("""
            UPDATE trades 
            SET status = 'OPEN', 
                exit_time = NULL, 
                exit_price = NULL, 
                actual_exit_price = NULL, 
                actual_pnl = NULL,
                pnl = NULL
            WHERE id = ?
        """, (trade_id,))
        print("✅ RPTX marked as OPEN.")
    else:
        print("⚠️ No CLOSED RPTX trade found to re-open.")

    # 2. Close MSTX
    # FIND the OPEN trade for MSTX
    cursor.execute("SELECT id, entry_time FROM trades WHERE symbol = 'MSTX' AND status = 'OPEN' LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        trade_id = row[0]
        print(f"Found OPEN MSTX trade (ID: {trade_id}, Entry: {row[1]}). Closing...")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            UPDATE trades 
            SET status = 'CLOSED', 
                exit_time = ?
            WHERE id = ?
        """, (now_str, trade_id))
        print("✅ MSTX marked as CLOSED.")
    else:
        print("⚠️ No OPEN MSTX trade found to close.")

    conn.commit()
    conn.close()
    print("--- DB SYNC COMPLETE ---")

except Exception as e:
    print(f"❌ Error during DB sync: {e}")
