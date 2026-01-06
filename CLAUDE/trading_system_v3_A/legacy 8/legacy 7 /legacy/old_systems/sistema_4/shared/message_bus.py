# shared/message_bus.py
"""
Sistema_4 Message Bus - Redis communication between components
"""

import asyncio
import redis.asyncio as redis
import json
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageBus:
    """
    Redis message bus for Sistema_4 communication
    Handles pub/sub between scanner, workers, and coordinator
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.logger = logging.getLogger(f"{__name__}.MessageBus")

        self.redis_client = None
        self.pubsub = None
        self.subscribers = {}  # channel -> callback mapping
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()
            self.is_connected = True

            self.logger.info(f"✅ Connected to Redis: {self.redis_host}:{self.redis_port}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Redis connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Redis"""
        try:
            if self.pubsub:
                await self.pubsub.close()

            if self.redis_client:
                await self.redis_client.close()

            self.is_connected = False
            self.logger.info("✅ Disconnected from Redis")

        except Exception as e:
            self.logger.error(f"Error disconnecting from Redis: {e}")

    async def publish_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Publish opportunity to scanner_opportunities channel"""
        try:
            if not self.is_connected:
                return False

            # Add timestamp
            opportunity['timestamp'] = datetime.now().isoformat()

            message = json.dumps(opportunity)
            await self.redis_client.publish("scanner_opportunities", message)

            self.logger.debug(f"📡 Published opportunity: {opportunity['symbol']} ({opportunity['opportunity_type']})")
            return True

        except Exception as e:
            self.logger.error(f"Error publishing opportunity: {e}")
            return False

    async def publish_execution_result(self, result: Dict[str, Any]) -> bool:
        """Publish execution result to execution_results channel"""
        try:
            if not self.is_connected:
                return False

            result['timestamp'] = datetime.now().isoformat()
            message = json.dumps(result)
            await self.redis_client.publish("execution_results", message)

            self.logger.debug(f"📡 Published execution result: {result.get('symbol', 'Unknown')}")
            return True

        except Exception as e:
            self.logger.error(f"Error publishing execution result: {e}")
            return False

    async def subscribe_to_opportunities(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to scanner opportunities"""
        await self._subscribe_to_channel("scanner_opportunities", callback)

    async def subscribe_to_execution_results(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to execution results"""
        await self._subscribe_to_channel("execution_results", callback)

    async def _subscribe_to_channel(self, channel: str, callback: Callable[[Dict[str, Any]], None]):
        """Generic channel subscription"""
        try:
            if not self.is_connected:
                await self.connect()

            if not self.pubsub:
                self.pubsub = self.redis_client.pubsub()

            await self.pubsub.subscribe(channel)
            self.subscribers[channel] = callback

            self.logger.info(f"📻 Subscribed to channel: {channel}")

        except Exception as e:
            self.logger.error(f"Error subscribing to {channel}: {e}")

    async def start_listening(self):
        """Start listening for messages"""
        if not self.pubsub:
            self.logger.warning("No subscriptions active")
            return

        try:
            self.logger.info("👂 Starting message listener...")

            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        # Parse message
                        data = json.loads(message['data'])
                        channel = message['channel']

                        # Call appropriate callback
                        if channel in self.subscribers:
                            callback = self.subscribers[channel]
                            await self._safe_callback(callback, data)

                    except json.JSONDecodeError as e:
                        self.logger.error(f"Invalid JSON in message: {e}")
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")

        except Exception as e:
            self.logger.error(f"Error in message listener: {e}")

    async def _safe_callback(self, callback: Callable, data: Dict[str, Any]):
        """Safely execute callback"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            self.logger.error(f"Error in callback: {e}")

    async def get_channel_info(self) -> Dict[str, Any]:
        """Get information about Redis channels"""
        try:
            info = {}

            # Get number of subscribers for each channel
            channels = ["scanner_opportunities", "execution_results"]
            for channel in channels:
                result = await self.redis_client.pubsub_numsub(channel)
                info[channel] = result[channel] if result else 0

            return info

        except Exception as e:
            self.logger.error(f"Error getting channel info: {e}")
            return {}

# Convenience class for scanner communication
class ScannerMessageBus(MessageBus):
    """Specialized message bus for scanner component"""

    async def publish_opportunities(self, opportunities: list) -> bool:
        """Publish multiple opportunities"""
        success_count = 0
        for opportunity in opportunities:
            if await self.publish_opportunity(opportunity):
                success_count += 1

        if success_count > 0:
            self.logger.info(f"📡 Published {success_count}/{len(opportunities)} opportunities")

        return success_count == len(opportunities)

# Convenience class for worker communication
class WorkerMessageBus(MessageBus):
    """Specialized message bus for worker components"""

    def __init__(self, worker_id: str, **kwargs):
        super().__init__(**kwargs)
        self.worker_id = worker_id

    async def publish_trade_request(self, trade_request: Dict[str, Any]) -> bool:
        """Publish trade request to execution engine"""
        try:
            trade_request['worker_id'] = self.worker_id
            trade_request['timestamp'] = datetime.now().isoformat()

            message = json.dumps(trade_request)
            await self.redis_client.publish("trade_requests", message)

            self.logger.info(f"📡 Trade request published: {trade_request['symbol']} by {self.worker_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error publishing trade request: {e}")
            return False

    async def subscribe_to_trade_responses(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to trade responses for this worker"""
        channel = f"trade_responses_{self.worker_id}"
        await self._subscribe_to_channel(channel, callback)