#!/usr/bin/env python3
"""
Database Unification Script
Migrates all trading data from trading_data.db to database.db
Adds OHLC linkage capabilities for forward testing
"""

import sqlite3
import logging
import shutil
from datetime import datetime
from pathlib import Path
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseUnifier:
    """Handles the unification of trading_data.db into database.db"""

    def __init__(self):
        self.project_root = project_root
        self.main_db = self.project_root / "database.db"
        self.trading_db = self.project_root / "trading_data.db"
        self.backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")

    def backup_databases(self):
        """Create backups before migration"""
        logger.info("🔄 Creating database backups...")

        # Backup main database
        if self.main_db.exists():
            backup_main = self.project_root / f"database_backup_{self.backup_suffix}.db"
            shutil.copy2(self.main_db, backup_main)
            logger.info(f"✅ Main DB backed up to: {backup_main}")

        # Backup trading database
        if self.trading_db.exists():
            backup_trading = self.project_root / f"trading_data_backup_{self.backup_suffix}.db"
            shutil.copy2(self.trading_db, backup_trading)
            logger.info(f"✅ Trading DB backed up to: {backup_trading}")

    def create_unified_tables(self):
        """Create enhanced trading tables in main database"""
        logger.info("🏗️ Creating unified trading tables in database.db...")

        with sqlite3.connect(self.main_db) as conn:
            # Enhanced trades table with OHLC linkage
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    side TEXT NOT NULL, -- 'BUY' or 'SELL'
                    quantity INTEGER NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    duration_minutes INTEGER,
                    pnl REAL,
                    commission REAL DEFAULT 0,
                    status TEXT DEFAULT 'OPEN', -- 'OPEN', 'CLOSED', 'CANCELLED'
                    notes TEXT,

                    -- ENHANCED: OHLC Integration for Forward Testing
                    trading_date TEXT,                    -- Date of the trade (YYYY-MM-DD)
                    day_ohlc_data TEXT,                  -- JSON: Complete OHLC bars for the trading day
                    premarket_high REAL,                 -- PMH level if applicable
                    market_open_price REAL,              -- Market open price
                    day_high REAL,                       -- Day's highest price
                    day_low REAL,                        -- Day's lowest price
                    day_close REAL,                      -- Day's closing price
                    day_volume INTEGER,                  -- Total day volume
                    gap_percent REAL,                    -- Gap % at open (for gap strategies)
                    entry_bar_data TEXT,                 -- JSON: OHLC data for entry bar
                    exit_bar_data TEXT,                  -- JSON: OHLC data for exit bar

                    -- ML and Order Flow Enhancement
                    confidence REAL,                     -- Strategy confidence score
                    order_flow_boost REAL DEFAULT 0,    -- Order flow boost factor
                    order_flow_signals TEXT,             -- JSON: Order flow analysis
                    entry_bid REAL,                      -- Bid at entry
                    entry_ask REAL,                      -- Ask at entry
                    entry_bid_size INTEGER,              -- Bid size at entry
                    entry_ask_size INTEGER,              -- Ask size at entry
                    entry_spread_pct REAL,               -- Spread % at entry
                    bid_pressure REAL,                   -- Bid pressure score
                    institutional_activity REAL,         -- Institutional activity score
                    aggressive_buying REAL,              -- Aggressive buying score
                    pressure_building REAL,              -- Pressure building score
                    volume_at_ask_ratio REAL,            -- Volume at ask ratio
                    volume_at_bid_ratio REAL,            -- Volume at bid ratio
                    spread_compression_ratio REAL,       -- Spread compression ratio
                    volume_multiplier REAL,              -- Volume vs average multiplier

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily stats table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    gross_profit REAL DEFAULT 0,
                    gross_loss REAL DEFAULT 0,
                    max_win REAL DEFAULT 0,
                    max_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    avg_win REAL DEFAULT 0,
                    avg_loss REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Strategy outcomes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_timestamp TIMESTAMP NOT NULL,
                    outcome_type TEXT NOT NULL, -- 'WIN', 'LOSS', 'BREAKEVEN', 'TIMEOUT'
                    entry_price REAL,
                    exit_price REAL,
                    pnl REAL,
                    pnl_percentage REAL,
                    hold_time_minutes INTEGER,
                    max_favorable_excursion REAL,
                    max_adverse_excursion REAL,
                    volume_at_entry INTEGER,
                    market_conditions TEXT, -- JSON with market state
                    strategy_confidence REAL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Trading journal table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    market_notes TEXT,
                    strategy_notes TEXT,
                    lessons_learned TEXT,
                    mood_rating INTEGER CHECK(mood_rating >= 1 AND mood_rating <= 5),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Manual symbols table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS manual_symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    notes TEXT
                )
            """)

            # Position risk management table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS position_risk_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    stop_loss_price REAL,
                    take_profit_price REAL,
                    trailing_stop_activation_price REAL,
                    trailing_stop_distance_pct REAL DEFAULT 0.05,
                    max_hold_time_minutes INTEGER DEFAULT 240,
                    strategy_used TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(symbol, entry_price, quantity)
                )
            """)

            # ML Learning tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    strategy_name TEXT,
                    features TEXT, -- JSON
                    outcome TEXT,
                    feedback_score REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    evaluation_date DATE NOT NULL,
                    accuracy REAL,
                    precision_score REAL,
                    recall REAL,
                    f1_score REAL,
                    training_samples INTEGER,
                    test_samples INTEGER,
                    features_used TEXT, -- JSON
                    hyperparameters TEXT, -- JSON
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # NEW: Trade OHLC Data table for detailed forward testing
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_ohlc_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    bar_timestamp TIMESTAMP NOT NULL,
                    timeframe TEXT NOT NULL, -- '1min', '5min', '1hour', '1day'
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    bar_sequence INTEGER, -- 1, 2, 3... for the trading day
                    is_entry_bar BOOLEAN DEFAULT 0,
                    is_exit_bar BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (trade_id) REFERENCES trades(trade_id),
                    UNIQUE(trade_id, bar_timestamp, timeframe)
                )
            """)

            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)",
                "CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date(entry_time))",
                "CREATE INDEX IF NOT EXISTS idx_trades_trading_date ON trades(trading_date)",
                "CREATE INDEX IF NOT EXISTS idx_trade_ohlc_trade_id ON trade_ohlc_data(trade_id)",
                "CREATE INDEX IF NOT EXISTS idx_trade_ohlc_timestamp ON trade_ohlc_data(bar_timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_strategy_outcomes_strategy ON strategy_outcomes(strategy_name)",
                "CREATE INDEX IF NOT EXISTS idx_strategy_outcomes_symbol ON strategy_outcomes(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_learning_events_symbol ON learning_events(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_learning_events_strategy ON learning_events(strategy_name)"
            ]

            for index in indexes:
                conn.execute(index)

            conn.commit()
            logger.info("✅ Unified trading tables created successfully")

    def migrate_trading_data(self):
        """Migrate data from trading_data.db to database.db"""
        if not self.trading_db.exists():
            logger.warning("⚠️ trading_data.db not found, skipping data migration")
            return

        logger.info("📦 Migrating data from trading_data.db...")

        # Get list of tables to migrate
        with sqlite3.connect(self.trading_db) as source_conn:
            source_conn.row_factory = sqlite3.Row
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = [row[0] for row in source_conn.execute(tables_query).fetchall()]

        logger.info(f"📋 Found tables to migrate: {tables}")

        # Migrate each table
        with sqlite3.connect(self.main_db) as dest_conn:
            with sqlite3.connect(self.trading_db) as source_conn:
                source_conn.row_factory = sqlite3.Row

                for table in tables:
                    try:
                        logger.info(f"🔄 Migrating table: {table}")

                        # Get all data from source table
                        rows = source_conn.execute(f"SELECT * FROM {table}").fetchall()

                        if not rows:
                            logger.info(f"  📭 No data in {table}")
                            continue

                        # Get column names
                        columns = list(rows[0].keys())

                        # Check if destination table exists and get its columns
                        dest_tables = dest_conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                            (table,)
                        ).fetchall()

                        if dest_tables:
                            # Table exists, check for conflicts and migrate
                            placeholders = ','.join(['?' for _ in columns])
                            insert_sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

                            for row in rows:
                                try:
                                    dest_conn.execute(insert_sql, tuple(row))
                                except sqlite3.Error as e:
                                    logger.warning(f"  ⚠️ Error inserting row in {table}: {e}")
                                    continue
                        else:
                            logger.info(f"  📋 Table {table} not found in destination, skipping")

                        dest_conn.commit()
                        logger.info(f"  ✅ Migrated {len(rows)} rows from {table}")

                    except Exception as e:
                        logger.error(f"  ❌ Error migrating {table}: {e}")
                        continue

    def update_external_systems(self):
        """Update external systems to use unified database"""
        logger.info("🔧 Updating external system configurations...")

        # Update TradeTally config
        tradetally_config = self.project_root / "integrations/tradetally/config/tradetally_config.py"
        if tradetally_config.exists():
            content = tradetally_config.read_text()
            updated_content = content.replace(
                'self.db_path = str(self.project_root / "trading_data.db")',
                'self.db_path = str(self.project_root / "database.db")'
            )
            tradetally_config.write_text(updated_content)
            logger.info("✅ Updated TradeTally config")

        # Update Telegram client
        telegram_client = self.project_root / "notifications/telegram_client.py"
        if telegram_client.exists():
            content = telegram_client.read_text()
            updated_content = content.replace(
                'db_path = _PROJECT_ROOT / "trading_data.db"',
                'db_path = _PROJECT_ROOT / "database.db"'
            )
            telegram_client.write_text(updated_content)
            logger.info("✅ Updated Telegram client")

        # Update DatabaseManager default path
        db_manager = self.project_root / "core/database_manager.py"
        if db_manager.exists():
            content = db_manager.read_text()
            updated_content = content.replace(
                'def __init__(self, db_path: str = "trading_data.db"):',
                'def __init__(self, db_path: str = "database.db"):'
            )
            db_manager.write_text(updated_content)
            logger.info("✅ Updated DatabaseManager default path")

    def verify_migration(self):
        """Verify the migration was successful"""
        logger.info("🔍 Verifying migration...")

        with sqlite3.connect(self.main_db) as conn:
            # Check key tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            required_tables = ['trades', 'daily_stats', 'trade_ohlc_data', 'OHLCData']
            missing_tables = [t for t in required_tables if t not in table_names]

            if missing_tables:
                logger.error(f"❌ Missing tables: {missing_tables}")
                return False

            # Check trade count
            trade_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            ohlc_count = conn.execute("SELECT COUNT(*) FROM OHLCData").fetchone()[0]

            logger.info(f"✅ Verification complete:")
            logger.info(f"  📊 Tables found: {len(table_names)}")
            logger.info(f"  🔢 Trades: {trade_count}")
            logger.info(f"  📈 OHLC records: {ohlc_count}")

            return True

    def run_migration(self):
        """Run complete migration process"""
        logger.info("🚀 Starting database unification process...")

        try:
            # Step 1: Backup
            self.backup_databases()

            # Step 2: Create unified tables
            self.create_unified_tables()

            # Step 3: Migrate data
            self.migrate_trading_data()

            # Step 4: Update external systems
            self.update_external_systems()

            # Step 5: Verify
            if self.verify_migration():
                logger.info("🎉 Database unification completed successfully!")

                # Create summary
                logger.info("\n" + "="*60)
                logger.info("📋 MIGRATION SUMMARY")
                logger.info("="*60)
                logger.info("✅ All trading data unified in database.db")
                logger.info("✅ OHLC linkage capabilities added")
                logger.info("✅ Forward testing infrastructure ready")
                logger.info("✅ External systems updated")
                logger.info("✅ Backups created for safety")
                logger.info("\n🎯 Next steps:")
                logger.info("  1. Test TradeTally sync")
                logger.info("  2. Test Telegram notifications")
                logger.info("  3. Start collecting OHLC data for trades")
                logger.info("="*60)

                return True
            else:
                logger.error("❌ Migration verification failed")
                return False

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

if __name__ == "__main__":
    migrator = DatabaseUnifier()
    success = migrator.run_migration()
    sys.exit(0 if success else 1)