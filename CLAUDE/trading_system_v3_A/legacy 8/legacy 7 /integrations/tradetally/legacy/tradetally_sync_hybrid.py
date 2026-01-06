"""
TradeTally Hybrid Sync - Simplified
Sincroniza SOLO metadata mínima (trade_id, user_id, is_public) a PostgreSQL
Los datos completos permanecen en SQLite (trading_data.db) como fuente de verdad
"""

import sqlite3
import psycopg2
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TradeTallyHybridSync:
    """Sincronización híbrida simplificada: SQLite -> PostgreSQL (solo metadata)"""

    def __init__(self, sqlite_db_path: str, pg_config: Dict[str, str], user_id: str):
        """
        Inicializar sincronización híbrida

        Args:
            sqlite_db_path: Ruta a trading_data.db
            pg_config: Configuración de PostgreSQL {host, port, database, user, password}
            user_id: UUID del usuario en PostgreSQL
        """
        self.sqlite_db_path = sqlite_db_path
        self.pg_config = pg_config
        self.user_id = user_id

        logger.info(f"✅ TradeTally Hybrid Sync initialized")
        logger.info(f"   SQLite DB: {sqlite_db_path}")
        logger.info(f"   PostgreSQL: {pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
        logger.info(f"   User ID: {user_id}")

    def get_closed_trades_from_sqlite(self) -> List[str]:
        """Obtener lista de trade_ids cerrados de SQLite"""
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()

            query = """
                SELECT trade_id
                FROM trades
                WHERE status = 'CLOSED'
                ORDER BY entry_time DESC
            """

            cursor.execute(query)
            trade_ids = [row[0] for row in cursor.fetchall()]

            conn.close()
            logger.info(f"📊 Found {len(trade_ids)} closed trades in SQLite")
            return trade_ids

        except Exception as e:
            logger.error(f"❌ Error reading SQLite: {e}")
            return []

    def get_synced_trade_ids_from_pg(self) -> List[str]:
        """Obtener lista de trade_ids ya sincronizados en PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.pg_config)
            cursor = conn.cursor()

            query = """
                SELECT trade_id
                FROM trade_metadata
                WHERE user_id = %s
            """

            cursor.execute(query, (self.user_id,))
            trade_ids = [row[0] for row in cursor.fetchall()]

            conn.close()
            logger.info(f"📊 Found {len(trade_ids)} trades already synced in PostgreSQL")
            return trade_ids

        except Exception as e:
            logger.error(f"❌ Error reading PostgreSQL: {e}")
            return []

    def sync_trade_metadata(self, trade_id: str, is_public: bool = False) -> bool:
        """
        Sincronizar metadata de un trade a PostgreSQL

        Args:
            trade_id: ID del trade desde SQLite
            is_public: Si el trade debe ser público (default: False)

        Returns:
            True si se sincronizó exitosamente
        """
        try:
            conn = psycopg2.connect(**self.pg_config)
            cursor = conn.cursor()

            # Upsert metadata
            query = """
                INSERT INTO trade_metadata (trade_id, user_id, is_public, notes, tags)
                VALUES (%s, %s, %s, NULL, ARRAY[]::TEXT[])
                ON CONFLICT (trade_id)
                DO UPDATE SET
                    updated_at = NOW()
                RETURNING id
            """

            cursor.execute(query, (trade_id, self.user_id, is_public))
            result = cursor.fetchone()

            conn.commit()
            conn.close()

            if result:
                logger.info(f"✅ Synced metadata for trade {trade_id}")
                return True
            else:
                logger.warning(f"⚠️  No result for trade {trade_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error syncing trade {trade_id}: {e}")
            return False

    def sync_all_trades(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Sincronizar todos los trades cerrados que no están en PostgreSQL

        Args:
            dry_run: Si True, solo reporta sin sincronizar

        Returns:
            Dict con estadísticas: {total, synced, skipped, errors}
        """
        stats = {
            'total': 0,
            'synced': 0,
            'skipped': 0,
            'errors': 0
        }

        logger.info("🚀 Starting hybrid sync...")

        # 1. Get all closed trades from SQLite
        sqlite_trades = self.get_closed_trades_from_sqlite()
        stats['total'] = len(sqlite_trades)

        if stats['total'] == 0:
            logger.info("ℹ️  No closed trades found in SQLite")
            return stats

        # 2. Get already synced trades from PostgreSQL
        pg_trades = set(self.get_synced_trade_ids_from_pg())

        # 3. Find trades that need syncing
        trades_to_sync = [tid for tid in sqlite_trades if tid not in pg_trades]

        logger.info(f"📋 Summary:")
        logger.info(f"   Total trades in SQLite: {stats['total']}")
        logger.info(f"   Already synced: {len(pg_trades)}")
        logger.info(f"   Need syncing: {len(trades_to_sync)}")

        if dry_run:
            logger.info("🔍 DRY RUN - No changes will be made")
            logger.info(f"   Would sync {len(trades_to_sync)} trades:")
            for tid in trades_to_sync[:10]:  # Show first 10
                logger.info(f"     - {tid}")
            if len(trades_to_sync) > 10:
                logger.info(f"     ... and {len(trades_to_sync) - 10} more")
            return stats

        # 4. Sync new trades
        for trade_id in trades_to_sync:
            success = self.sync_trade_metadata(trade_id, is_public=False)
            if success:
                stats['synced'] += 1
            else:
                stats['errors'] += 1

        stats['skipped'] = len(pg_trades)

        logger.info("✅ Sync completed!")
        logger.info(f"   Total: {stats['total']}")
        logger.info(f"   Synced: {stats['synced']}")
        logger.info(f"   Skipped (already synced): {stats['skipped']}")
        logger.info(f"   Errors: {stats['errors']}")

        return stats

    def test_connections(self) -> bool:
        """Probar conexiones a SQLite y PostgreSQL"""
        logger.info("🔍 Testing connections...")

        # Test SQLite
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]
            conn.close()
            logger.info(f"✅ SQLite connection OK - {count} trades")
        except Exception as e:
            logger.error(f"❌ SQLite connection failed: {e}")
            return False

        # Test PostgreSQL
        try:
            conn = psycopg2.connect(**self.pg_config)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_metadata WHERE user_id = %s", (self.user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            logger.info(f"✅ PostgreSQL connection OK - {count} metadata records")
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}")
            return False

        return True


def main():
    """Función principal para ejecutar sincronización"""
    import argparse

    parser = argparse.ArgumentParser(description='TradeTally Hybrid Sync - Sync metadata only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be synced without making changes')
    parser.add_argument('--sqlite-db', type=str, help='Path to trading_data.db')
    parser.add_argument('--user-id', type=str, help='User UUID in PostgreSQL')
    args = parser.parse_args()

    # Configuration from environment variables
    sqlite_db_path = args.sqlite_db or os.getenv('SQLITE_DB_PATH', '../../../trading_data.db')
    user_id = args.user_id or os.getenv('TRADETALLY_USER_ID')

    pg_config = {
        'host': os.getenv('PG_HOST', 'localhost'),
        'port': int(os.getenv('PG_PORT', '5432')),
        'database': os.getenv('PG_DATABASE', 'tradetally'),
        'user': os.getenv('PG_USER', 'postgres'),
        'password': os.getenv('PG_PASSWORD', '')
    }

    if not user_id:
        logger.error("❌ USER_ID is required. Set TRADETALLY_USER_ID env variable or use --user-id")
        return

    # Initialize sync
    sync = TradeTallyHybridSync(sqlite_db_path, pg_config, user_id)

    # Test connections
    if not sync.test_connections():
        logger.error("❌ Connection test failed. Fix configuration and try again.")
        return

    # Run sync
    stats = sync.sync_all_trades(dry_run=args.dry_run)

    logger.info("=" * 60)
    logger.info("📊 FINAL STATS")
    logger.info("=" * 60)
    logger.info(f"Total trades: {stats['total']}")
    logger.info(f"Synced: {stats['synced']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
