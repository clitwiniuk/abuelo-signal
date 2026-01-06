"""
TradeTally Auto-Sync with WebSocket
====================================

Monitorea SQLite en tiempo real y sincroniza automáticamente via WebSocket.
NO requiere sincronización manual!

Arquitectura:
1. Watchdog monitorea trading_data.db
2. Detecta nuevos trades o cambios
3. Envía via WebSocket a TradeTally
4. TradeTally guarda metadata en PostgreSQL
5. ✅ Todo automático!
"""

import sqlite3
import logging
import time
import socketio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class TradeTallyAutoSync:
    """Auto-sync con WebSocket y file watcher"""

    def __init__(self, api_key: str, base_url: str, db_path: str):
        """
        Initialize auto-sync

        Args:
            api_key: TradeTally API key
            base_url: Base URL (e.g., http://localhost:8001)
            db_path: Path to SQLite database
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.db_path = db_path

        # WebSocket client
        self.sio = socketio.Client(
            logger=False,
            engineio_logger=False
        )

        # Connection state
        self.connected = False
        self.authenticated = False
        self.last_sync_time = datetime.now()

        # Stats
        self.stats = {
            'synced': 0,
            'errors': 0,
            'last_trade_id': None
        }

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup WebSocket event handlers"""

        @self.sio.event
        def connect():
            logger.info("🔌 Connected to TradeTally WebSocket")
            self.connected = True
            # Authenticate immediately
            self.sio.emit('authenticate', {'api_key': self.api_key})

        @self.sio.event
        def authenticated(data):
            logger.info(f"✅ Authenticated as {data.get('username')}")
            self.authenticated = True
            # Sync existing trades on connect
            self._sync_all_existing_trades()

        @self.sio.event
        def auth_error(data):
            logger.error(f"❌ Auth error: {data.get('error')}")
            self.authenticated = False

        @self.sio.event
        def sync_success(data):
            self.stats['synced'] += 1
            self.stats['last_trade_id'] = data.get('trade_id')
            logger.info(f"✅ Synced: {data.get('trade_id')}")

        @self.sio.event
        def sync_error(data):
            self.stats['errors'] += 1
            logger.error(f"❌ Sync error: {data.get('error')}")

        @self.sio.event
        def bulk_sync_success(data):
            synced = data.get('synced', 0)
            errors = data.get('errors', 0)
            self.stats['synced'] += synced
            self.stats['errors'] += errors
            logger.info(f"✅ Bulk synced: {synced} trades, {errors} errors")

        @self.sio.event
        def disconnect():
            logger.warning("🔌 Disconnected from TradeTally")
            self.connected = False
            self.authenticated = False

        @self.sio.event
        def pong(data):
            # Keep-alive response
            pass

    def connect(self):
        """Connect to WebSocket server"""
        try:
            ws_url = self.base_url
            logger.info(f"Connecting to {ws_url}...")
            self.sio.connect(ws_url, socketio_path='/ws/sync', wait_timeout=10)

            # Wait for authentication
            timeout = 10
            start = time.time()
            while not self.authenticated and (time.time() - start) < timeout:
                time.sleep(0.1)

            if not self.authenticated:
                raise Exception("Authentication timeout")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from WebSocket"""
        if self.connected:
            self.sio.disconnect()

    def _get_trades_from_db(self, since: Optional[datetime] = None):
        """Get trades from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if since:
                # FIX: Use entry_time OR updated_at to catch new trades (handles timezone issues)
                query = """
                    SELECT * FROM trades
                    WHERE (entry_time > ? OR updated_at > ?)
                    AND (deleted IS NULL OR deleted = 0)
                    ORDER BY COALESCE(updated_at, entry_time) DESC
                """
                cursor.execute(query, (since.isoformat(), since.isoformat()))
            else:
                query = "SELECT * FROM trades WHERE (deleted IS NULL OR deleted = 0) ORDER BY COALESCE(updated_at, entry_time) DESC"
                cursor.execute(query)

            rows = cursor.fetchall()
            trades = [dict(row) for row in rows]
            conn.close()

            return trades

        except Exception as e:
            logger.error(f"Error reading from SQLite: {e}")
            return []

    def _sync_all_existing_trades(self):
        """Sync all existing trades on initial connect"""
        logger.info("📊 Syncing all existing trades...")

        trades = self._get_trades_from_db()

        if not trades:
            logger.info("No trades to sync")
            return

        # Prepare metadata
        metadata_list = []
        for trade in trades:
            metadata = {
                'trade_id': str(trade.get('trade_id')),
                'is_public': False,
                'notes': trade.get('notes'),
                'tags': [],
                # Include metrics for display
                'strategy_confidence': trade.get('strategy_confidence'),
                'market_context_score': trade.get('market_context_score'),
                'trade_session': trade.get('trade_session'),
                'confidence': trade.get('confidence')
            }
            metadata_list.append(metadata)

        # Send in batches of 100
        batch_size = 100
        for i in range(0, len(metadata_list), batch_size):
            batch = metadata_list[i:i + batch_size]
            self.sio.emit('sync-trades-bulk', {'trades': batch})
            time.sleep(0.1)  # Small delay between batches

        logger.info(f"📤 Sent {len(metadata_list)} trades for sync")

    def sync_trade(self, trade_id: str, notes: Optional[str] = None, tags: Optional[list] = None, metrics: Optional[Dict] = None):
        """
        Sync single trade

        Args:
            trade_id: Trade ID
            notes: Trade notes
            tags: Trade tags
            metrics: Dictionary of trade metrics (confidence, context, etc.)
        """
        if not self.authenticated:
            logger.warning("Not authenticated, skipping sync")
            return False

        payload = {
            'trade_id': trade_id,
            'is_public': False,
            'notes': notes,
            'tags': tags or []
        }
        
        # Merge metrics if provided
        if metrics:
            payload.update(metrics)

        self.sio.emit('sync-trade', payload)

        return True

    def sync_recent_trades(self, minutes: int = 5):
        """Sync trades from last N minutes"""
        since = datetime.now()
        # Subtract minutes
        since = datetime.fromtimestamp(since.timestamp() - minutes * 60)

        trades = self._get_trades_from_db(since=since)

        for trade in trades:
            self.sync_trade(
                trade_id=str(trade.get('trade_id')),
                notes=trade.get('notes'),
                tags=[],
                metrics={
                    'strategy_confidence': trade.get('strategy_confidence'),
                    'market_context_score': trade.get('market_context_score'),
                    'trade_session': trade.get('trade_session'),
                    'confidence': trade.get('confidence')
                }
            )

        logger.info(f"Synced {len(trades)} recent trades")

    def get_stats(self) -> Dict[str, Any]:
        """Get sync statistics"""
        return {
            'connected': self.connected,
            'authenticated': self.authenticated,
            'synced': self.stats['synced'],
            'errors': self.stats['errors'],
            'last_trade_id': self.stats['last_trade_id'],
            'last_sync_time': self.last_sync_time.isoformat()
        }

    def keep_alive(self):
        """Send keep-alive ping"""
        if self.connected:
            self.sio.emit('ping')


class SQLiteWatcher(FileSystemEventHandler):
    """Watch SQLite database for changes"""

    def __init__(self, autosync: TradeTallyAutoSync):
        self.autosync = autosync
        self.last_modified = time.time()
        self.debounce_seconds = 2  # Wait 2 seconds before syncing

    def on_modified(self, event):
        """Called when SQLite file is modified"""
        if event.src_path.endswith('trading_data.db'):
            current_time = time.time()

            # Debounce: only sync if enough time has passed
            if current_time - self.last_modified > self.debounce_seconds:
                logger.info("📝 Database modified, syncing...")
                self.autosync.sync_recent_trades(minutes=5)
                self.last_modified = current_time


def start_autosync(api_key: str, base_url: str, db_path: str):
    """
    Start auto-sync daemon

    Args:
        api_key: TradeTally API key
        base_url: TradeTally base URL
        db_path: Path to SQLite database

    Example:
        start_autosync(
            api_key="tt_live_xxxxx",
            base_url="http://localhost:8001",
            db_path="trading_data.db"
        )
    """
    logger.info("🚀 Starting TradeTally Auto-Sync...")

    # Create auto-sync instance
    autosync = TradeTallyAutoSync(api_key, base_url, db_path)

    # Connect to WebSocket
    if not autosync.connect():
        logger.error("❌ Failed to connect to TradeTally")
        return None

    # Setup file watcher
    db_dir = str(Path(db_path).parent)
    event_handler = SQLiteWatcher(autosync)
    observer = Observer()
    observer.schedule(event_handler, db_dir, recursive=False)
    observer.start()

    logger.info("✅ Auto-sync started!")
    logger.info(f"   Watching: {db_path}")
    logger.info(f"   WebSocket: {base_url}/ws/sync")
    logger.info("   Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(10)
            # Send keep-alive every 10 seconds
            autosync.keep_alive()

    except KeyboardInterrupt:
        logger.info("\n⏹️ Stopping auto-sync...")
        observer.stop()
        autosync.disconnect()

    observer.join()
    logger.info("👋 Auto-sync stopped")

    return autosync
