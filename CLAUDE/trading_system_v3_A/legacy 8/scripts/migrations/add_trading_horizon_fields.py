#!/usr/bin/env python3
"""
Database Migration: Add Trading Horizon Fields to Trades Table

Adds missing fields required for the Trading Horizon System:
- trading_horizon: Signal-specific horizon (SCALP, INTRADAY, SWING_SHORT, SWING)
- expected_hold_hours: Expected position hold time in hours
- daily_rsi: Daily RSI value at entry time
- distance_to_resistance_pct: Distance to resistance as percentage
- resistance_price: Nearest resistance price level
- EOD_safe: Boolean flag indicating if position can be held overnight

This migration is SAFE and NON-DESTRUCTIVE - preserves all existing data.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradingHorizonMigration:
    """Handles database migration for trading horizon fields"""

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def check_existing_fields(self, conn: sqlite3.Connection) -> dict:
        """Check which trading horizon fields already exist"""
        cursor = conn.cursor()

        # Get table schema
        cursor.execute("PRAGMA table_info(trades)")
        columns = {row[1]: row for row in cursor.fetchall()}

        existing_fields = {
            'trading_horizon': 'trading_horizon' in columns,
            'expected_hold_hours': 'expected_hold_hours' in columns,
            'daily_rsi': 'daily_rsi' in columns,
            'distance_to_resistance_pct': 'distance_to_resistance_pct' in columns,
            'resistance_price': 'resistance_price' in columns,
            'EOD_safe': 'EOD_safe' in columns,
        }

        return existing_fields

    def add_missing_fields(self, conn: sqlite3.Connection):
        """Add missing trading horizon fields to the trades table"""

        fields_to_add = [
            ("trading_horizon", "TEXT", "DEFAULT 'INTRADAY'"),
            ("expected_hold_hours", "REAL", "DEFAULT 6.0"),
            ("daily_rsi", "REAL", "DEFAULT 50.0"),
            ("distance_to_resistance_pct", "REAL", "DEFAULT 100.0"),
            ("resistance_price", "REAL", "DEFAULT 0.0"),
            ("EOD_safe", "BOOLEAN", "DEFAULT 0"),
        ]

        existing_fields = self.check_existing_fields(conn)

        logger.info("🔍 Checking existing fields...")
        for field_name, exists in existing_fields.items():
            status = "✅ EXISTS" if exists else "❌ MISSING"
            logger.info(f"   {field_name}: {status}")

        # Add missing fields
        added_count = 0
        for field_name, field_type, default_value in fields_to_add:
            if not existing_fields[field_name]:
                try:
                    conn.execute(f"ALTER TABLE trades ADD COLUMN {field_name} {field_type} {default_value}")
                    logger.info(f"✅ Added field: {field_name} ({field_type} {default_value})")
                    added_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to add field {field_name}: {e}")
            else:
                logger.info(f"⏭️ Field {field_name} already exists, skipping")

        return added_count

    def verify_migration(self, conn: sqlite3.Connection) -> bool:
        """Verify that all required fields exist and are accessible"""
        try:
            # Test query with new fields
            cursor = conn.execute("""
                SELECT
                    trading_horizon,
                    expected_hold_hours,
                    daily_rsi,
                    distance_to_resistance_pct,
                    resistance_price,
                    EOD_safe
                FROM trades
                WHERE 1=0  -- Just test schema, don't return data
            """)

            # If we get here without error, the fields exist
            logger.info("✅ Migration verification successful - all fields accessible")
            return True

        except Exception as e:
            logger.error(f"❌ Migration verification failed: {e}")
            return False

    def get_migration_summary(self, conn: sqlite3.Connection) -> dict:
        """Get summary of migration results"""
        try:
            cursor = conn.cursor()

            # Count total trades
            total_trades = cursor.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

            # Count trades with trading horizon data (should be 0 initially)
            horizon_trades = cursor.execute(
                "SELECT COUNT(*) FROM trades WHERE trading_horizon IS NOT NULL"
            ).fetchone()[0]

            # Get sample of recent trades to show default values
            recent_trades = conn.execute("""
                SELECT symbol, strategy, trading_horizon, expected_hold_hours, EOD_safe
                FROM trades
                ORDER BY entry_time DESC
                LIMIT 3
            """).fetchall()

            return {
                'total_trades': total_trades,
                'trades_with_horizon': horizon_trades,
                'recent_trades': recent_trades,
                'migration_complete': True
            }

        except Exception as e:
            logger.error(f"Error getting migration summary: {e}")
            return {'migration_complete': False, 'error': str(e)}

    def run_migration(self) -> dict:
        """Run the complete migration process"""
        logger.info("🚀 Starting Trading Horizon Database Migration...")

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign keys for safety
                conn.execute("PRAGMA foreign_keys = ON")

                # Add missing fields
                added_count = self.add_missing_fields(conn)

                # Verify migration
                verification_success = self.verify_migration(conn)

                # Get summary
                summary = self.get_migration_summary(conn)

                if verification_success and added_count >= 0:
                    logger.info("✅ Migration completed successfully!")
                    logger.info(f"📊 Summary: {summary['total_trades']} total trades, {added_count} fields added")
                else:
                    logger.error("❌ Migration completed with errors")
                    return {'success': False, 'error': 'Verification failed'}

                return {
                    'success': True,
                    'fields_added': added_count,
                    'summary': summary
                }

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return {'success': False, 'error': str(e)}

def main():
    """Main migration function"""
    print("🗄️ Trading Horizon Database Migration")
    print("=" * 50)

    migration = TradingHorizonMigration()
    result = migration.run_migration()

    if result['success']:
        print("✅ Migration completed successfully!")
        print(f"📊 Fields added: {result['fields_added']}")
        print(f"📈 Total trades in DB: {result['summary']['total_trades']}")
    else:
        print(f"❌ Migration failed: {result['error']}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())