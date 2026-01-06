#!/usr/bin/env python3
"""
Redis Message Bus for Sistema III
Handles communication between scanner, coordinator, and workers
"""

import asyncio
import logging
import json
import sys
import os
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import redis.asyncio as redis

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.service_locator import get_config

class MessageBus:
    """
    Redis-based message bus for Sistema III communication
    """

    def __init__(self):
        self.logger = logging.getLogger("MessageBus")
        self.config = get_config()

        # Redis configuration
        self.redis_host = self.config.get('COMMUNICATION', 'redis_host', fallback='localhost')
        self.redis_port = self.config.getint('COMMUNICATION', 'redis_port', fallback=6379)
        self.redis_db = self.config.getint('COMMUNICATION', 'redis_db', fallback=0)
        self.redis_password = self.config.get('COMMUNICATION', 'redis_password', fallback=None)

        # Channel names from config
        self.scanner_channel = self.config.get('COMMUNICATION', 'scanner_channel', fallback='scanner_opportunities')
        self.execution_channel = self.config.get('COMMUNICATION', 'execution_channel', fallback='execution_commands')
        self.workers_status_channel = self.config.get('COMMUNICATION', 'workers_status_channel', fallback='workers_status')

        # Message timeouts
        self.message_timeout = self.config.getint('COMMUNICATION', 'message_timeout_seconds', fallback=10)

        # Redis connections
        self.redis_client = None
        self.pubsub = None

        # Subscription handlers
        self.opportunity_handlers = []
        self.execution_handlers = []
        self.status_handlers = []

        # Connection status
        self._connected = False
        self._shutting_down = False

        # Background tasks
        self._opportunity_task = None

    async def connect(self) -> bool:
        """Connect to Redis message bus"""
        try:
            # Create Redis connection
            redis_url = f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
            if self.redis_password:
                redis_url = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

            self.redis_client = redis.from_url(redis_url, decode_responses=True)

            # Test connection
            await self.redis_client.ping()

            # Create pubsub instance
            self.pubsub = self.redis_client.pubsub()

            self._connected = True
            self.logger.info(f"✅ Connected to Redis: {self.redis_host}:{self.redis_port}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Redis connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Redis message bus"""
        try:
            # Set shutdown flag to stop message processing gracefully
            self._shutting_down = True

            # Cancel opportunity processing task if running
            if self._opportunity_task and not self._opportunity_task.done():
                self._opportunity_task.cancel()
                try:
                    await self._opportunity_task
                except asyncio.CancelledError:
                    pass  # Expected

            if self.pubsub:
                await self.pubsub.close()

            if self.redis_client:
                await self.redis_client.close()

            self._connected = False
            self.logger.info("✅ Disconnected from Redis")

        except Exception as e:
            self.logger.error(f"❌ Error disconnecting from Redis: {e}")

    async def is_connected(self) -> bool:
        """Check if connected to Redis"""
        try:
            if not self._connected or not self.redis_client:
                return False

            await self.redis_client.ping()
            return True

        except Exception:
            self._connected = False
            return False

    # === OPPORTUNITY PUBLISHING (Scanner -> Coordinator) ===

    async def publish_opportunities(self, opportunities: List[Dict]) -> bool:
        """Publish opportunities from scanner to coordinator"""
        try:
            if not await self.is_connected():
                self.logger.error("❌ Cannot publish - Redis not connected")
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'opportunities',
                'count': len(opportunities),
                'opportunities': opportunities
            }

            await self.redis_client.publish(self.scanner_channel, json.dumps(message))
            self.logger.debug(f"📡 Published {len(opportunities)} opportunities")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing opportunities: {e}")
            return False

    async def subscribe_to_opportunities(self, handler: Callable[[Dict], None]) -> bool:
        """Subscribe to opportunities from scanner"""
        try:
            if not await self.is_connected():
                return False

            self.opportunity_handlers.append(handler)
            await self.pubsub.subscribe(self.scanner_channel)

            # Start message processing task
            if not self._opportunity_task:
                self._opportunity_task = asyncio.create_task(self._process_opportunity_messages())

            self.logger.info(f"✅ Subscribed to opportunities on {self.scanner_channel}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error subscribing to opportunities: {e}")
            return False

    async def _process_opportunity_messages(self):
        """Process incoming opportunity messages"""
        try:
            async for message in self.pubsub.listen():
                # Check for shutdown signal
                if self._shutting_down:
                    self.logger.info("🛑 Opportunity message processing stopped (shutdown)")
                    break

                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        if data.get('type') == 'opportunities':
                            opportunities = data.get('opportunities', [])

                            # Call all registered handlers
                            for handler in self.opportunity_handlers:
                                for opportunity in opportunities:
                                    try:
                                        await handler(opportunity)
                                    except Exception as e:
                                        self.logger.error(f"❌ Error in opportunity handler: {e}")

                    except Exception as e:
                        self.logger.error(f"❌ Error processing opportunity message: {e}")

        except asyncio.CancelledError:
            self.logger.info("📨 Opportunity message processing cancelled")
        except ConnectionError:
            # Expected during shutdown when Redis closes connection
            if not self._shutting_down:
                self.logger.error("❌ Redis connection lost during message processing")
        except Exception as e:
            # Only log as error if not shutting down
            if not self._shutting_down:
                self.logger.error(f"❌ Error in opportunity message processing: {e}")
            else:
                self.logger.debug(f"Expected error during shutdown: {e}")

    # === EXECUTION RESULT PUBLISHING ===

    async def publish_execution_result(self, result: Dict) -> bool:
        """Publish execution result for monitoring"""
        try:
            if not await self.is_connected():
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'execution_result',
                'result': result
            }

            await self.redis_client.publish(self.execution_channel, json.dumps(message))
            self.logger.debug(f"📡 Published execution result: {result.get('symbol', 'unknown')}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing execution result: {e}")
            return False

    async def subscribe_to_execution_results(self, handler: Callable[[Dict], None]) -> bool:
        """Subscribe to execution results"""
        try:
            if not await self.is_connected():
                return False

            self.execution_handlers.append(handler)
            await self.pubsub.subscribe(self.execution_channel)

            # Start processing if not already running
            if not hasattr(self, '_execution_task_started'):
                asyncio.create_task(self._process_execution_messages())
                self._execution_task_started = True

            self.logger.info(f"✅ Subscribed to execution results on {self.execution_channel}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error subscribing to execution results: {e}")
            return False

    async def _process_execution_messages(self):
        """Process incoming execution messages"""
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message' and message['channel'] == self.execution_channel:
                    try:
                        data = json.loads(message['data'])
                        if data.get('type') == 'execution_result':
                            result = data.get('result', {})

                            # Call all registered handlers
                            for handler in self.execution_handlers:
                                try:
                                    await handler(result)
                                except Exception as e:
                                    self.logger.error(f"❌ Error in execution handler: {e}")

                    except Exception as e:
                        self.logger.error(f"❌ Error processing execution message: {e}")

        except Exception as e:
            self.logger.error(f"❌ Error in execution message processing: {e}")

    # === POSITION UPDATES ===

    async def publish_position_updates(self, updates: List[Dict]) -> bool:
        """Publish position monitoring updates"""
        try:
            if not await self.is_connected():
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'position_updates',
                'count': len(updates),
                'updates': updates
            }

            await self.redis_client.publish(self.workers_status_channel, json.dumps(message))
            self.logger.debug(f"📡 Published {len(updates)} position updates")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing position updates: {e}")
            return False

    # === WORKER STATUS ===

    async def publish_worker_status(self, worker_id: str, status: Dict) -> bool:
        """Publish worker status for monitoring"""
        try:
            if not await self.is_connected():
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'worker_status',
                'worker_id': worker_id,
                'status': status
            }

            await self.redis_client.publish(self.workers_status_channel, json.dumps(message))
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing worker status: {e}")
            return False

    # === HEARTBEAT ===

    async def publish_heartbeat(self, heartbeat_data: Dict) -> bool:
        """Publish system heartbeat"""
        try:
            if not await self.is_connected():
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'heartbeat',
                'data': heartbeat_data
            }

            # Use a dedicated heartbeat channel or workers status
            await self.redis_client.publish('system_heartbeat', json.dumps(message))
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing heartbeat: {e}")
            return False

    # === EMERGENCY COMMANDS ===

    async def publish_emergency_stop(self, reason: str = "EMERGENCY") -> bool:
        """Publish emergency stop command to all components"""
        try:
            if not await self.is_connected():
                return False

            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'emergency_stop',
                'reason': reason,
                'command': 'STOP_ALL_TRADING'
            }

            # Publish to all channels
            channels = [self.scanner_channel, self.execution_channel, self.workers_status_channel]

            for channel in channels:
                await self.redis_client.publish(channel, json.dumps(message))

            self.logger.warning(f"🚨 Emergency stop published: {reason}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error publishing emergency stop: {e}")
            return False

    # === UTILITY METHODS ===

    async def get_channel_info(self) -> Dict[str, Any]:
        """Get information about active channels"""
        try:
            if not await self.is_connected():
                return {}

            info = {
                'scanner_channel': self.scanner_channel,
                'execution_channel': self.execution_channel,
                'workers_status_channel': self.workers_status_channel,
                'connected': self._connected,
                'opportunity_handlers': len(self.opportunity_handlers),
                'execution_handlers': len(self.execution_handlers),
                'status_handlers': len(self.status_handlers)
            }

            return info

        except Exception as e:
            self.logger.error(f"❌ Error getting channel info: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on message bus"""
        try:
            start_time = datetime.now()

            if not await self.is_connected():
                return {
                    'status': 'disconnected',
                    'error': 'Not connected to Redis'
                }

            # Test publish/subscribe
            test_channel = 'health_check'
            test_message = {'test': True, 'timestamp': start_time.isoformat()}

            await self.redis_client.publish(test_channel, json.dumps(test_message))

            response_time = (datetime.now() - start_time).total_seconds()

            return {
                'status': 'healthy',
                'response_time_seconds': response_time,
                'redis_host': self.redis_host,
                'redis_port': self.redis_port,
                'channels': {
                    'scanner': self.scanner_channel,
                    'execution': self.execution_channel,
                    'workers_status': self.workers_status_channel
                }
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    async def clear_all_channels(self):
        """Clear all messages from channels (for testing/reset)"""
        try:
            if not await self.is_connected():
                return False

            # Note: Redis pub/sub doesn't queue messages, so this is mainly for cleanup
            # We could implement a message queue using Redis lists if needed
            self.logger.info("🧹 Message bus channels cleared")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error clearing channels: {e}")
            return False