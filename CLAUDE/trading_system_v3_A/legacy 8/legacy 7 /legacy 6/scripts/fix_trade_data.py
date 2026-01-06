#!/usr/bin/env python3
"""
Fix Trade Data Script
Updates existing trades in trading_data.db that have NULL values for:
- confidence (sets to 70.0)
- market_context (sets to 'NEUTRAL')
- trade_session (infers from entry_time)
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from core.extended_hours_manager import ExtendedHoursManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FixTradeData")

def get_trade_session(entry_time_str):
    """Infer trade session from entry time string"""
    try:
        # Handle different formats
        if 'T' in entry_time_str:
            dt = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S.%f")
            
        # Simple hour check (assuming ET or converting roughly)
        # This is a rough approximation for repair
        hour = dt.hour + dt.minute / 60.0
        
        if hour < 9.5: return 'PRE_MARKET'
        if 9.5 <= hour < 16.0: return 'REGULAR'
        return 'AFTER_HOURS'
    except Exception as e:
        return 'REGULAR'

def fix_trade_data():
    db_path = project_root / "trading_data.db"
    
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Fix Confidence
        logger.info("Checking for NULL confidence...")
        cursor.execute("UPDATE trades SET confidence = 70.0 WHERE confidence IS NULL")
        if cursor.rowcount > 0:
            logger.info(f"✅ Fixed {cursor.rowcount} trades with NULL confidence")
            
        # 2. Fix Market Context
        logger.info("Checking for NULL market_context...")
        cursor.execute("UPDATE trades SET market_context = 'NEUTRAL' WHERE market_context IS NULL")
        if cursor.rowcount > 0:
            logger.info(f"✅ Fixed {cursor.rowcount} trades with NULL market_context")
            
        # 3. Fix Trade Session
        logger.info("Checking for NULL trade_session...")
        # Get trades with NULL session
        cursor.execute("SELECT trade_id, entry_time FROM trades WHERE trade_session IS NULL")
        rows = cursor.fetchall()
        
        fixed_sessions = 0
        for row in rows:
            session = get_trade_session(row['entry_time'])
            cursor.execute(
                "UPDATE trades SET trade_session = ? WHERE trade_id = ?", 
                (session, row['trade_id'])
            )
            fixed_sessions += 1
            
        if fixed_sessions > 0:
            logger.info(f"✅ Fixed {fixed_sessions} trades with NULL trade_session")
            
        # 4. Fix missing market_context_score based on market_context
        logger.info("Checking for NULL market_context_score...")
        cursor.execute("SELECT count(*) FROM trades WHERE market_context_score IS NULL AND market_context IS NOT NULL")
        count_score = cursor.fetchone()[0]
        
        if count_score > 0:
            logger.info(f"Found {count_score} trades with NULL market_context_score but valid context. Inferring scores...")
            
            # Mapping context text to default scores
            context_scores = {
                'NEUTRAL': 50.0,
                'TRENDING': 80.0,
                'CHOPPY': 30.0,
                'VOLATILE': 40.0,
                'BREAKOUT': 85.0,
                'REVERSAL': 75.0
            }
            
            for context, score in context_scores.items():
                cursor.execute("""
                    UPDATE trades 
                    SET market_context_score = ? 
                    WHERE market_context_score IS NULL AND market_context = ?
                """, (score, context))
                
            # Default for any others
            cursor.execute("""
                UPDATE trades 
                SET market_context_score = 50.0 
                WHERE market_context_score IS NULL AND market_context IS NOT NULL
            """)
            
            logger.info("✅ Fixed missing market_context_score values")
        else:
            logger.info("No trades found with NULL market_context_score and valid context")

        conn.commit()
        conn.close()
        logger.info("🎉 Trade data repair completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error repairing trade data: {e}")

if __name__ == "__main__":
    fix_trade_data()
