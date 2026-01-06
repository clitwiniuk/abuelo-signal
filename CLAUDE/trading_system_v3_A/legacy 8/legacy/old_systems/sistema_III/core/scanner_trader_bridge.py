# core/scanner_trader_bridge.py
"""
Scanner-Trader Communication Bridge - Redis Pub/Sub
Simple 20-30 line implementation for real-time communication between scanner and trader
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable

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
    Minimal Redis pub/sub bridge for scanner-trader communication
    Scanner publishes opportunities -> Trader subscribes and processes
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.subscriber = None
        self.is_running = False
        
        # Channel names
        self.SCANNER_CHANNEL = "scanner:opportunities"
        self.TRADER_CHANNEL = "trader:signals"
        
        # Callbacks
        self.opportunity_callback: Optional[Callable] = None
        self.signal_callback: Optional[Callable] = None
        
    async def connect(self):
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis library not installed - using direct communication fallback")
            return False
            
        try:
            self.redis_client = await aioredis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("✅ Scanner-Trader Bridge connected to Redis")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}")
            return False
    
    async def publish_opportunities(self, opportunities: List[Dict[str, Any]]):
        """Scanner publishes opportunities"""
        if not self.redis_client:
            return
            
        try:
            message = {
                "type": "opportunities",
                "timestamp": asyncio.get_event_loop().time(),
                "data": opportunities
            }
            await self.redis_client.publish(self.SCANNER_CHANNEL, json.dumps(message))
            logger.info(f"📡 Published {len(opportunities)} opportunities to trader")
        except Exception as e:
            logger.error(f"❌ Error publishing opportunities: {e}")
    
    async def subscribe_to_opportunities(self, callback: Callable):
        """Trader subscribes to scanner opportunities"""
        if not self.redis_client:
            return
            
        self.opportunity_callback = callback
        self.is_running = True
        
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(self.SCANNER_CHANNEL)
            
            logger.info("🔊 Trader subscribed to scanner opportunities")
            
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
                    logger.error(f"❌ Error processing opportunity: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in opportunity subscription: {e}")
    
    async def disconnect(self):
        """Cleanup connections"""
        self.is_running = False
        if self.redis_client:
            await self.redis_client.close()
            logger.info("🔌 Scanner-Trader Bridge disconnected")