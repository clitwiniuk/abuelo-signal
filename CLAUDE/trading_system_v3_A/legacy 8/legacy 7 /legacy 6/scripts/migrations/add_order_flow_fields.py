#!/usr/bin/env python3
"""
Migration Script: Add Order Flow Fields to Trading Database

Adds new fields to store order flow analysis data for posterior analysis.
"""

import sqlite3
import logging
from pathlib import Path

def add_order_flow_fields(db_path: str = "trading_data.db"):
    """Add order flow analysis fields to trades table"""

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("OrderFlowMigration")

    # Order flow fields to add
    new_fields = [
        # Order Flow boost and signals
        ("order_flow_boost", "INTEGER DEFAULT 0", "Order flow confidence boost (0-3)"),
        ("order_flow_signals", "TEXT", "JSON array of order flow signal types detected"),

        # Bid/Ask data at entry
        ("entry_bid", "REAL", "Bid price at entry time"),
        ("entry_ask", "REAL", "Ask price at entry time"),
        ("entry_bid_size", "INTEGER", "Bid size at entry time"),
        ("entry_ask_size", "INTEGER", "Ask size at entry time"),
        ("entry_spread_pct", "REAL", "Bid-ask spread percentage at entry"),

        # Order Flow Analysis Results
        ("bid_pressure", "REAL", "Bid pressure ratio (0.0-1.0) at entry"),
        ("institutional_activity", "BOOLEAN DEFAULT 0", "Spread compression detected"),
        ("aggressive_buying", "BOOLEAN DEFAULT 0", "Aggressive buying detected"),
        ("pressure_building", "BOOLEAN DEFAULT 0", "Volume pressure building detected"),

        # Volume at price levels
        ("volume_at_ask_ratio", "REAL", "Estimated volume hitting ask ratio"),
        ("volume_at_bid_ratio", "REAL", "Estimated volume hitting bid ratio"),

        # Additional predictive indicators
        ("spread_compression_ratio", "REAL", "Current spread vs historical average"),
        ("volume_multiplier", "REAL", "Current volume vs recent average"),
    ]

    try:
        with sqlite3.connect(db_path) as conn:
            # Check if database exists
            if not Path(db_path).exists():
                logger.error(f"Database {db_path} does not exist")
                return False

            # Get current table structure
            cursor = conn.execute("PRAGMA table_info(trades)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            added_count = 0

            for field_name, field_type, description in new_fields:
                if field_name not in existing_columns:
                    try:
                        sql = f"ALTER TABLE trades ADD COLUMN {field_name} {field_type}"
                        conn.execute(sql)
                        logger.info(f"✅ Added field: {field_name} ({description})")
                        added_count += 1
                    except Exception as e:
                        logger.error(f"❌ Error adding {field_name}: {e}")
                else:
                    logger.info(f"⏭️  Field {field_name} already exists")

            conn.commit()

            if added_count > 0:
                logger.info(f"🎯 Migration completed: {added_count} new order flow fields added")
            else:
                logger.info("🔄 No migration needed - all order flow fields already present")

            return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def verify_migration(db_path: str = "trading_data.db"):
    """Verify that order flow fields were added successfully"""

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("OrderFlowVerification")

    expected_fields = [
        "order_flow_boost", "order_flow_signals", "entry_bid", "entry_ask",
        "entry_bid_size", "entry_ask_size", "entry_spread_pct", "bid_pressure",
        "institutional_activity", "aggressive_buying", "pressure_building",
        "volume_at_ask_ratio", "volume_at_bid_ratio", "spread_compression_ratio",
        "volume_multiplier"
    ]

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(trades)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            missing_fields = []
            present_fields = []

            for field in expected_fields:
                if field in existing_columns:
                    present_fields.append(field)
                else:
                    missing_fields.append(field)

            logger.info(f"✅ Order flow fields present: {len(present_fields)}/{len(expected_fields)}")

            if missing_fields:
                logger.warning(f"❌ Missing fields: {missing_fields}")
                return False
            else:
                logger.info("🎯 All order flow fields successfully added!")
                return True

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    # Run migration
    success = add_order_flow_fields()

    if success:
        # Verify migration
        verify_migration()
    else:
        print("❌ Migration failed")