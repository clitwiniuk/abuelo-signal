# core/scanner_trader_bridge.py
"""
Scanner-Trader Communication Bridge - Redis Pub/Sub with Fallback
Enhanced implementation with direct database fallback for high availability
"""

import asyncio
import json
import logging
import sqlite3
import os
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

# Optional Redis import with fallback
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None

logger = logging.getLogger(__name__)

class ScannerTraderBridge:
    """
    Enhanced Redis pub/sub bridge with database fallback for high availability
    Scanner publishes opportunities -> Trader subscribes and processes
    Falls back to SQLite database if Redis is unavailable
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", db_path: str = None):
        self.redis_url = redis_url
        self.redis_client = None
        self.subscriber = None
        self.is_running = False

        # Database fallback
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), '..', 'trading_data.db')
        self.db_connection = None
        self._use_redis = True  # Flag to track if Redis is being used

        # Channel names
        self.SCANNER_CHANNEL = "scanner:opportunities"
        self.TRADER_CHANNEL = "trader:signals"

        # Fallback table name
        self.FALLBACK_TABLE = "scanner_opportunities_fallback"

        # Callbacks
        self.opportunity_callback: Optional[Callable] = None
        self.signal_callback: Optional[Callable] = None
        
    async def connect(self):
        """Connect to Redis with database fallback"""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis library not installed - using database fallback")
            self._use_redis = False
            return await self._setup_database_fallback()

        try:
            self.redis_client = await aioredis.from_url(self.redis_url)
            await self.redis_client.ping()
            self._use_redis = True
            logger.info("✅ Scanner-Trader Bridge connected to Redis")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Redis not available ({e}) - falling back to database")
            self._use_redis = False
            return await self._setup_database_fallback()

    async def _setup_database_fallback(self):
        """Setup SQLite database fallback"""
        try:
            # Ensure database exists and create fallback table
            self.db_connection = sqlite3.connect(self.db_path)
            cursor = self.db_connection.cursor()

            # Create fallback table if it doesn't exist
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.FALLBACK_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    processed INTEGER DEFAULT 0
                )
            """)

            # Create index for efficient queries
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.FALLBACK_TABLE}_channel_timestamp
                ON {self.FALLBACK_TABLE}(channel, timestamp)
            """)

            self.db_connection.commit()
            logger.info("✅ Database fallback initialized")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup database fallback: {e}")
            return False
    
    async def publish_opportunities(self, opportunities: List[Dict[str, Any]]):
        """Scanner publishes opportunities with fallback"""
        message = {
            "type": "opportunities",
            "timestamp": asyncio.get_event_loop().time(),
            "data": opportunities
        }

        if self._use_redis and self.redis_client:
            # Try Redis first
            try:
                await self.redis_client.publish(self.SCANNER_CHANNEL, json.dumps(message))
                logger.info(f"📡 Redis: Published {len(opportunities)} opportunities to trader")
                return
            except Exception as e:
                logger.warning(f"⚠️ Redis publish failed: {e} - falling back to database")

        # Database fallback
        await self._publish_to_database(self.SCANNER_CHANNEL, message)
        logger.info(f"💾 Database: Stored {len(opportunities)} opportunities for trader")

    async def _publish_to_database(self, channel: str, message: Dict[str, Any]):
        """Store message in database fallback"""
        if not self.db_connection:
            logger.error("❌ Database fallback not available")
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(f"""
                INSERT INTO {self.FALLBACK_TABLE} (channel, message, timestamp, processed)
                VALUES (?, ?, ?, 0)
            """, (channel, json.dumps(message), message["timestamp"]))

            self.db_connection.commit()
            logger.debug(f"💾 Stored message in database fallback: {channel}")
        except Exception as e:
            logger.error(f"❌ Error storing in database fallback: {e}")
    
    async def subscribe_to_opportunities(self, callback: Callable):
        """Trader subscribes to scanner opportunities with fallback"""
        self.opportunity_callback = callback
        self.is_running = True

        # Start both Redis subscription and database polling
        redis_task = None
        database_task = None

        if self._use_redis and self.redis_client:
            redis_task = asyncio.create_task(self._subscribe_redis(callback))

        database_task = asyncio.create_task(self._poll_database(callback))

        # Wait for either task to complete (they run indefinitely until stopped)
        try:
            if redis_task:
                await redis_task
            if database_task:
                await database_task
        except Exception as e:
            logger.error(f"❌ Error in subscription tasks: {e}")

    async def _subscribe_redis(self, callback: Callable):
        """Redis subscription task"""
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(self.SCANNER_CHANNEL)

            logger.info("🔊 Trader subscribed to Redis scanner opportunities")

            while self.is_running:
                try:
                    message = await pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        data = json.loads(message["data"])
                        if data.get("type") == "opportunities":
                            await callback(data["data"])
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"❌ Redis subscription error: {e}")
                    break

        except Exception as e:
            logger.error(f"❌ Redis subscription failed: {e}")

    async def _poll_database(self, callback: Callable):
        """Database polling task for fallback messages"""
        logger.info("🔄 Database polling started for fallback messages")

        while self.is_running:
            try:
                if self.db_connection:
                    cursor = self.db_connection.cursor()
                    # Get unprocessed messages
                    cursor.execute(f"""
                        SELECT id, message FROM {self.FALLBACK_TABLE}
                        WHERE channel = ? AND processed = 0
                        ORDER BY timestamp ASC
                    """, (self.SCANNER_CHANNEL,))

                    messages = cursor.fetchall()

                    for msg_id, message_json in messages:
                        try:
                            data = json.loads(message_json)
                            if data.get("type") == "opportunities":
                                await callback(data["data"])

                                # Mark as processed
                                cursor.execute(f"""
                                    UPDATE {self.FALLBACK_TABLE}
                                    SET processed = 1
                                    WHERE id = ?
                                """, (msg_id,))

                        except Exception as e:
                            logger.error(f"❌ Error processing database message {msg_id}: {e}")

                    self.db_connection.commit()

                # Poll every 5 seconds
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"❌ Database polling error: {e}")
                await asyncio.sleep(5)
    
    async def disconnect(self):
        """Cleanup connections"""
        self.is_running = False

        if self.redis_client:
            await self.redis_client.close()
            logger.info("🔌 Redis connection closed")

        if self.db_connection:
            self.db_connection.close()
            logger.info("🔌 Database connection closed")

        logger.info("🔌 Scanner-Trader Bridge fully disconnected")

    def get_status(self) -> Dict[str, Any]:
        """Get bridge status for monitoring"""
        return {
            "redis_available": self._use_redis and self.redis_client is not None,
            "database_fallback": self.db_connection is not None,
            "is_running": self.is_running,
            "fallback_messages_pending": self._get_pending_fallback_messages()
        }

    def _get_pending_fallback_messages(self) -> int:
        """Get count of pending fallback messages"""
        if not self.db_connection:
            return 0

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(f"""
                SELECT COUNT(*) FROM {self.FALLBACK_TABLE}
                WHERE processed = 0
            """)
            return cursor.fetchone()[0]
        except Exception:
            return 0