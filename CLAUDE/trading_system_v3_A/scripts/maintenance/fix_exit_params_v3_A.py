#!/usr/bin/env python3
"""
Fix Exit Params Schema for Trading System V3 A
Adds missing columns for persistent SL/TP/Trailing stops
"""

import sqlite3
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3_A/trading_data.db"

def add_column_if_not_exists(conn, table, column, col_type):
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info[1] for info in cursor.fetchall()]
        
        if column not in columns:
            logger.info(f"➕ Adding column {column} ({col_type}) to {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            return True
        else:
            logger.debug(f"ℹ️ Column {column} already exists in {table}")
            return False
    except Exception as e:
        logger.error(f"❌ Error adding column {column}: {e}")
        return False

def fix_schema():
    if not Path(DB_PATH).exists():
        logger.error(f"❌ Database not found at {DB_PATH}")
        return False

    logger.info(f"🔧 Connecting to database: {DB_PATH}")
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # list of new columns to add
            new_columns = [
                ('stop_loss_pct', 'REAL'),
                ('take_profit_pct', 'REAL'),
                ('trailing_activation_pct', 'REAL'),
                ('trailing_distance_pct', 'REAL'),
                ('stop_loss_price', 'REAL'),
                ('take_profit_price', 'REAL')
            ]
            
            added_count = 0
            for col_name, col_type in new_columns:
                if add_column_if_not_exists(conn, 'trades', col_name, col_type):
                    added_count += 1
            
            conn.commit()
            
            if added_count > 0:
                logger.info(f"✅ Successfully added {added_count} new columns to 'trades' table")
            else:
                logger.info("✅ Schema is already up to date")
                
            return True
            
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting Schema Fix for V3_A...")
    if fix_schema():
        logger.info("✅ Schema update completed successfully")
    else:
        logger.error("❌ Schema update failed")
        sys.exit(1)
