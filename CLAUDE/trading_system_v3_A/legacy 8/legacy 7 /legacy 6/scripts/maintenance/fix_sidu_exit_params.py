
import sqlite3
import logging
from pathlib import Path
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FixSiduExitParams")

DB_PATH = "trading_data.db"

def add_column_if_not_exists(conn, table, column, col_type):
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"✅ Added column '{column}' to '{table}'")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.info(f"ℹ️ Column '{column}' already exists in '{table}'")
        else:
            logger.error(f"❌ Error adding column '{column}': {e}")

def fix_db_schema():
    logger.info("🛠️ Starting DB Schema Migration...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Add columns for persistence of exit parameters
            add_column_if_not_exists(conn, "trades", "stop_loss_pct", "REAL")
            add_column_if_not_exists(conn, "trades", "take_profit_pct", "REAL")
            add_column_if_not_exists(conn, "trades", "trailing_activation_pct", "REAL")
            add_column_if_not_exists(conn, "trades", "trailing_distance_pct", "REAL")
            add_column_if_not_exists(conn, "trades", "stop_loss_price", "REAL")
            add_column_if_not_exists(conn, "trades", "take_profit_price", "REAL")
            
            conn.commit()
    except Exception as e:
        logger.error(f"❌ Schema migration failed: {e}")
        return False
    return True

def fix_sidu_trade():
    logger.info("🔧 Fixing SIDU trade...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find active SIDU trade
            cursor.execute("SELECT * FROM trades WHERE symbol = 'SIDU' AND status = 'OPEN'")
            sidu_trade = cursor.fetchone()
            
            if not sidu_trade:
                logger.warning("⚠️ No active SIDU trade found.")
                return False
                
            entry_price = sidu_trade['entry_price']
            trade_id = sidu_trade['trade_id']
            
            logger.info(f"Found active SIDU trade (ID: {trade_id}, Entry: ${entry_price})")
            
            # Default parameters (Swing Strategy Defaults)
            stop_loss_pct = 0.05      # 5%
            take_profit_pct = 0.30    # 30% ("Objetivo teórico +30%")
            trailing_activation_pct = 0.08 # 8% (Default global, check strategy later if needed)
            trailing_distance_pct = 0.04   # 4%
            
            # Calculate prices
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            take_profit_price = entry_price * (1 + take_profit_pct)
            
            logger.info(f"Applying default parameters: SL {stop_loss_pct*100}%, TP {take_profit_pct*100}%")
            logger.info(f"Calculated Prices: SL ${stop_loss_price:.2f}, TP ${take_profit_price:.2f}")
            
            # Update DB with new columns
            cursor.execute("""
                UPDATE trades 
                SET stop_loss_pct = ?,
                    take_profit_pct = ?,
                    trailing_activation_pct = ?,
                    trailing_distance_pct = ?,
                    stop_loss_price = ?,
                    take_profit_price = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (
                stop_loss_pct, 
                take_profit_pct, 
                trailing_activation_pct, 
                trailing_distance_pct,
                stop_loss_price,
                take_profit_price,
                trade_id
            ))
            
            conn.commit()
            logger.info("✅ SIDU trade updated successfully.")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error fixing SIDU trade: {e}")
        return False

if __name__ == "__main__":
    if fix_db_schema():
        fix_sidu_trade()
