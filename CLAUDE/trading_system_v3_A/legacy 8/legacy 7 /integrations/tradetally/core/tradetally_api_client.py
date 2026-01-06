"""
TradeTally API Client
=====================

Pure REST API client for TradeTally integration.
Uses HTTP requests instead of direct PostgreSQL access.

Architecture:
- Trading System SQLite -> TradeTally API -> TradeTally PostgreSQL
- SQLite remains the source of truth for trade data
- PostgreSQL only stores metadata (is_public, notes, tags)
"""

import requests
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import sqlite3

logger = logging.getLogger(__name__)


class TradeTallyAPIClient:
    """REST API client for TradeTally"""

    def __init__(self, api_key: str, base_url: str, db_path: str):
        """
        Initialize TradeTally API client

        Args:
            api_key: TradeTally API key (format: tt_live_xxx)
            base_url: Base URL of TradeTally API (e.g., http://localhost:8001)
            db_path: Path to SQLite database (trading_data.db)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.db_path = db_path
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'TradingSystemV3-APIClient/1.0'
        }

    def test_connection(self) -> bool:
        """
        Test connection to TradeTally API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.base_url}/api/v1/sync-metadata/status"
            logger.info(f"🔍 Testing connection to: {url}")

            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                logger.info("✅ Connection successful")
                data = response.json()
                logger.info(f"📊 Sync status: {data.get('status', {})}")
                return True
            else:
                logger.error(f"❌ Connection failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection error: {e}")
            return False

    def sync_metadata(self, trade_id: str, is_public: bool = False,
                     notes: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sync single trade metadata to TradeTally

        Args:
            trade_id: Trade ID from SQLite
            is_public: Whether trade is public
            notes: Trade notes
            tags: Trade tags

        Returns:
            API response dict
        """
        try:
            url = f"{self.base_url}/api/v1/sync-metadata/metadata"

            payload = {
                'trade_id': trade_id,
                'is_public': is_public,
                'notes': notes,
                'tags': tags or []
            }

            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

            if response.status_code in [200, 201]:
                logger.debug(f"✅ Synced metadata for trade {trade_id}")
                return response.json()
            else:
                logger.error(f"❌ Failed to sync trade {trade_id}: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error syncing trade {trade_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def bulk_sync_metadata(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk sync trade metadata to TradeTally

        Args:
            trades: List of trade metadata dicts with keys:
                   - trade_id (required)
                   - is_public (optional, default: False)
                   - notes (optional)
                   - tags (optional)

        Returns:
            API response with sync results
        """
        try:
            url = f"{self.base_url}/api/v1/sync-metadata/metadata/bulk"

            payload = {
                'trades': trades
            }

            response = requests.post(url, json=payload, headers=self.headers, timeout=120)

            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"✅ Bulk sync completed: {data.get('synced', 0)} synced, {data.get('errors', 0)} errors")
                return data
            else:
                logger.error(f"❌ Bulk sync failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error in bulk sync: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_trades_from_sqlite(self, only_today: bool = False) -> List[Dict[str, Any]]:
        """
        Get trades from SQLite database

        Args:
            only_today: If True, only get today's trades

        Returns:
            List of trade dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM trades"

            if only_today:
                today = datetime.now().date().isoformat()
                query += f" WHERE DATE(entry_time) = '{today}'"

            query += " ORDER BY entry_time DESC"

            cursor.execute(query)
            rows = cursor.fetchall()

            trades = []
            for row in rows:
                trade = dict(row)
                trades.append(trade)

            conn.close()

            logger.info(f"📊 Found {len(trades)} trades in SQLite")
            return trades

        except Exception as e:
            logger.error(f"❌ Error reading from SQLite: {e}")
            return []

    def sync_all_trades(self, only_today: bool = False, batch_size: int = 100) -> Dict[str, Any]:
        """
        Sync all trades metadata from SQLite to TradeTally

        Args:
            only_today: If True, only sync today's trades
            batch_size: Number of trades to sync per batch

        Returns:
            Sync results dict
        """
        logger.info(f"🔄 Starting metadata sync (only_today={only_today})")

        # Get trades from SQLite
        trades = self.get_trades_from_sqlite(only_today=only_today)

        if not trades:
            logger.warning("⚠️ No trades found in SQLite")
            return {
                'success': True,
                'synced': 0,
                'total': 0,
                'errors': 0
            }

        # Prepare metadata for sync
        metadata_list = []
        for trade in trades:
            metadata = {
                'trade_id': trade.get('trade_id'),
                'is_public': False,  # Default to private
                'notes': trade.get('notes'),
                'tags': []  # SQLite doesn't have tags by default
            }
            metadata_list.append(metadata)

        # Sync in batches
        total_synced = 0
        total_errors = 0
        all_errors = []

        for i in range(0, len(metadata_list), batch_size):
            batch = metadata_list[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(metadata_list) + batch_size - 1) // batch_size

            logger.info(f"📦 Syncing batch {batch_num}/{total_batches} ({len(batch)} trades)")

            result = self.bulk_sync_metadata(batch)

            if result.get('success'):
                total_synced += result.get('synced', 0)
                total_errors += result.get('errors', 0)
                if result.get('errors'):
                    all_errors.extend(result.get('errors', []))
            else:
                logger.error(f"❌ Batch {batch_num} failed: {result.get('error')}")
                total_errors += len(batch)

        logger.info(f"✅ Sync completed: {total_synced}/{len(trades)} synced, {total_errors} errors")

        return {
            'success': True,
            'synced': total_synced,
            'total': len(trades),
            'errors': total_errors,
            'error_details': all_errors if all_errors else None
        }

    def delete_metadata(self, trade_id: str) -> bool:
        """
        Delete trade metadata from TradeTally

        Args:
            trade_id: Trade ID

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/api/v1/sync-metadata/metadata/{trade_id}"

            response = requests.delete(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ Deleted metadata for trade {trade_id}")
                return True
            else:
                logger.error(f"❌ Failed to delete trade {trade_id}: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error deleting trade {trade_id}: {e}")
            return False

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get sync status from TradeTally

        Returns:
            Status dict
        """
        try:
            url = f"{self.base_url}/api/v1/sync-metadata/status"

            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Failed to get status: {response.status_code}")
                return {
                    'success': False,
                    'error': response.text
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error getting status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
