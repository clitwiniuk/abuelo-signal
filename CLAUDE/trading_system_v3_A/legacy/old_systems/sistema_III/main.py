#!/usr/bin/env python3
"""
Sistema III - Main Coordinator
Orchestrates scanner, workers, and execution engine
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import get_config
from utils.log_config import setup_logging
from adapters.ibkr_adapter import IBKRAdapter
from execution.execution_engine import ExecutionEngine
from execution.recovery_manager import RecoveryManager
from shared.database import Database
from shared.message_bus import MessageBus
from notifications.telegram_client import get_telegram_client
from notifications.sistema_iii_commands import SistemaIIICommands

class SistemaIIICoordinator:
    """
    Main coordinator for Sistema III trading system
    Manages scanner, workers, execution engine and coordination
    """

    def __init__(self):
        # Initialize logging first
        setup_logging(level="INFO", log_file="logs/main.log")
        self.logger = logging.getLogger("SistemaIII")

        # Load configuration
        self.config = get_config()

        # System components
        self.execution_ibkr = None
        self.execution_engine = None
        self.database = Database()
        self.message_bus = MessageBus()
        self.recovery_manager = None

        # Notifications
        self.telegram_client = get_telegram_client()
        self.telegram_commands = SistemaIIICommands(coordinator=self)

        # Control flags
        self.is_running = False
        self.shutdown_requested = False

        # Monitoring
        self.last_heartbeat = datetime.now()
        self.opportunities_processed = 0
        self.executions_completed = 0

        self.logger.info("🚀 Sistema III Coordinator initialized")

    async def initialize(self):
        """Initialize all system components"""
        try:
            self.logger.info("🔧 Initializing Sistema III components...")

            # 1. Initialize database
            await self.database.initialize()
            self.logger.info("✅ Database initialized")

            # 2. Initialize message bus
            connected = await self.message_bus.connect()
            if not connected:
                self.logger.error("❌ Failed to connect to Redis message bus")
                return False
            self.logger.info("✅ Message bus connected")

            # 3. Initialize IBKR connection for execution
            execution_client_id = self.config.getint('IBKR', 'client_id_execution', fallback=1010)
            self.execution_ibkr = IBKRAdapter(
                host=self.config.get('IBKR', 'host', fallback='127.0.0.1'),
                port=self.config.getint('IBKR', 'port', fallback=7497),
                client_id=execution_client_id
            )

            await self.execution_ibkr.connect()
            self.logger.info(f"✅ Execution IBKR connected (client_id: {execution_client_id})")

            # 4. Initialize execution engine
            self.execution_engine = ExecutionEngine(self.execution_ibkr)
            self.logger.info("✅ Execution engine initialized")

            # 5. Initialize recovery manager and run startup recovery
            self.recovery_manager = RecoveryManager(self.database, self.execution_ibkr)

            # Check if startup recovery is enabled
            enable_startup_recovery = self.config.getboolean('EXECUTION_ENGINE', 'enable_startup_recovery', fallback=True)
            if enable_startup_recovery:
                self.logger.info("🔄 Running startup recovery...")
                recovery_success = await self.recovery_manager.startup_recovery()
                if recovery_success:
                    self.logger.info("✅ Startup recovery completed")
                else:
                    self.logger.warning("⚠️ Startup recovery had issues")
            else:
                self.logger.info("ℹ️ Startup recovery disabled")

            # 6. Subscribe to scanner opportunities
            await self.message_bus.subscribe_to_opportunities(self._handle_opportunity)
            self.logger.info("✅ Subscribed to scanner opportunities")

            # 6. Setup Telegram commands and start listener
            if self.telegram_client.is_enabled():
                # Register Sistema III specific commands
                self.telegram_commands.register_commands(self.telegram_client)

                # Start listener
                self.telegram_client.start_listener()
                self.logger.info("✅ Telegram listener started")

                # Send startup notification
                # TODO: Implement notify_system_status method
                # await self.telegram_client.notify_system_status({
                #     'status': 'running',
                #     'message': 'Sistema III está funcionando correctamente'
                # })

            return True

        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            return False

    async def start(self):
        """Start the main coordination loop"""
        if not await self.initialize():
            return False

        self.logger.info("🚀 Starting Sistema III main coordinator...")
        self.is_running = True

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.logger.info(f"📡 Signal {signum} received - initiating graceful shutdown")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start monitoring tasks
        monitor_task = asyncio.create_task(self._monitoring_loop())
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start recovery sync task if recovery manager is available
        recovery_task = None
        if self.recovery_manager:
            recovery_task = asyncio.create_task(self.recovery_manager.start_continuous_sync())

        try:
            # Main coordination loop
            while self.is_running and not self.shutdown_requested:
                try:
                    # Check system health
                    await self._health_check()

                    # Process any pending database cleanup
                    await self.database.cleanup_old_records()

                    # Monitor execution engine
                    if self.execution_engine:
                        portfolio_status = await self.execution_engine.get_portfolio_status()
                        self.logger.debug(f"📊 Portfolio: {portfolio_status.get('active_positions', 0)} positions")

                    # Wait before next cycle
                    await asyncio.sleep(30)

                except Exception as e:
                    self.logger.error(f"❌ Error in main loop: {e}")
                    await asyncio.sleep(60)  # Longer wait on error

            self.logger.info("🛑 Main coordination loop ended")

        finally:
            # Cancel monitoring tasks
            monitor_task.cancel()
            heartbeat_task.cancel()

            # Cancel recovery task if it exists
            if recovery_task:
                recovery_task.cancel()

            await self.stop()

        return True

    async def _handle_opportunity(self, opportunity: Dict):
        """Handle opportunity received from scanner"""
        try:
            self.opportunities_processed += 1
            symbol = opportunity.get('symbol', 'UNKNOWN')
            strategy = opportunity.get('opportunity_type', 'UNKNOWN')

            self.logger.info(f"🎯 New opportunity: {symbol} ({strategy})")

            # Send Telegram opportunity notification
            try:
                await self.telegram_client.notify_opportunity(opportunity)
            except Exception as e:
                self.logger.error(f"❌ Error sending Telegram opportunity notification: {e}")

            # Log opportunity to database
            await self.database.log_opportunity(opportunity)

            # Execute opportunity via execution engine
            if self.execution_engine:
                execution_result = await self.execution_engine.execute_opportunity(opportunity)

                if execution_result['status'] == 'executed':
                    self.executions_completed += 1
                    self.logger.info(f"✅ Executed: {symbol} - {execution_result['status']}")
                else:
                    self.logger.info(f"❌ Rejected: {symbol} - {execution_result.get('reason', 'Unknown')}")

                # Publish execution result for monitoring
                await self.message_bus.publish_execution_result(execution_result)

        except Exception as e:
            self.logger.error(f"❌ Error handling opportunity: {e}")
            # Send error notification
            try:
                await self.telegram_client.notify_error({
                    'type': 'OPPORTUNITY_PROCESSING_ERROR',
                    'message': f'Error processing opportunity {symbol}: {str(e)}'
                })
            except:
                pass  # Don't fail on notification error

    async def _monitoring_loop(self):
        """Background monitoring of positions and system health"""
        try:
            while self.is_running and not self.shutdown_requested:
                try:
                    if self.execution_engine:
                        # Monitor active positions
                        position_updates = await self.execution_engine.monitor_active_positions()

                        if position_updates:
                            self.logger.info(f"📊 Position updates: {len(position_updates)}")

                    # Get system statistics
                    stats = await self._get_system_stats()
                    if stats:
                        self.logger.debug(f"📈 Stats: {stats['opportunities_processed']} opps, {stats['executions_completed']} execs")

                except Exception as e:
                    self.logger.error(f"❌ Error in monitoring: {e}")

                await asyncio.sleep(60)  # Monitor every minute

        except asyncio.CancelledError:
            self.logger.info("📊 Monitoring loop cancelled")

    async def _heartbeat_loop(self):
        """Send periodic heartbeat for health monitoring"""
        try:
            while self.is_running and not self.shutdown_requested:
                try:
                    self.last_heartbeat = datetime.now()

                    heartbeat_data = {
                        'timestamp': self.last_heartbeat.isoformat(),
                        'system': 'sistema_iii_coordinator',
                        'status': 'running',
                        'opportunities_processed': self.opportunities_processed,
                        'executions_completed': self.executions_completed,
                        'active_positions': len(self.execution_engine.active_executions) if self.execution_engine else 0
                    }

                    await self.message_bus.publish_heartbeat(heartbeat_data)

                except Exception as e:
                    self.logger.error(f"❌ Error sending heartbeat: {e}")

                # Heartbeat interval from config
                interval = self.config.getint('COMMUNICATION', 'heartbeat_interval_seconds', fallback=30)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            self.logger.info("💓 Heartbeat loop cancelled")

    async def _health_check(self):
        """Perform system health checks"""
        try:
            issues = []

            # Check IBKR connection
            if not self.execution_ibkr or not self.execution_ibkr.is_connected():
                issues.append("IBKR execution connection lost")

            # Check message bus
            if not self.message_bus or not await self.message_bus.is_connected():
                issues.append("Redis message bus disconnected")

            # Check database
            if not self.database or not await self.database.health_check():
                issues.append("Database connection issues")

            # Check execution engine
            if not self.execution_engine:
                issues.append("Execution engine not initialized")

            if issues:
                self.logger.warning(f"⚠️ Health issues detected: {', '.join(issues)}")
                # Could trigger automatic recovery procedures here
            else:
                self.logger.debug("✅ Health check passed")

        except Exception as e:
            self.logger.error(f"❌ Error in health check: {e}")

    async def _get_system_stats(self) -> Dict:
        """Get current system statistics"""
        try:
            stats = {
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': (datetime.now() - self.last_heartbeat).total_seconds() if self.last_heartbeat else 0,
                'opportunities_processed': self.opportunities_processed,
                'executions_completed': self.executions_completed,
                'active_positions': len(self.execution_engine.active_executions) if self.execution_engine else 0,
                'system_status': 'running' if self.is_running else 'stopped'
            }

            # Add execution engine stats if available
            if self.execution_engine:
                portfolio_status = await self.execution_engine.get_portfolio_status()
                stats.update(portfolio_status)

            return stats

        except Exception as e:
            self.logger.error(f"❌ Error getting system stats: {e}")
            return {}

    async def emergency_shutdown(self, reason: str = "EMERGENCY"):
        """Emergency shutdown with position closure"""
        try:
            self.logger.warning(f"🚨 EMERGENCY SHUTDOWN: {reason}")

            # Close all positions immediately
            if self.execution_engine:
                closed_positions = await self.execution_engine.emergency_close_all(reason)
                self.logger.warning(f"🚨 Emergency closed {len(closed_positions)} positions")

            # Stop system
            self.shutdown_requested = True
            await self.stop()

        except Exception as e:
            self.logger.error(f"❌ Error in emergency shutdown: {e}")

    async def stop(self):
        """Stop the coordinator and cleanup resources"""
        try:
            self.logger.info("🛑 Stopping Sistema III coordinator...")
            self.is_running = False

            # Send shutdown notification
            if self.telegram_client.is_enabled():
                # TODO: Implement notify_system_status method
                # await self.telegram_client.notify_system_status({
                #     'status': 'stopped',
                #     'message': 'Sistema III se ha detenido'
                # })
                self.telegram_client.stop_listener()
                self.logger.info("✅ Telegram listener stopped")

            # Stop recovery manager
            if self.recovery_manager:
                self.recovery_manager.stop_continuous_sync()
                self.logger.info("✅ Recovery manager stopped")

            # Cleanup execution engine
            if self.execution_engine:
                await self.execution_engine.cleanup()

            # Disconnect IBKR
            if self.execution_ibkr:
                await self.execution_ibkr.disconnect()
                self.logger.info("✅ IBKR disconnected")

            # Cleanup database
            if self.database:
                await self.database.close()
                self.logger.info("✅ Database closed")

            # Disconnect message bus
            if self.message_bus:
                await self.message_bus.disconnect()
                self.logger.info("✅ Message bus disconnected")

            self.logger.info("✅ Sistema III coordinator stopped cleanly")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")
            # Try to send error notification
            try:
                if self.telegram_client.is_enabled():
                    await self.telegram_client.notify_error({
                        'type': 'SHUTDOWN_ERROR',
                        'message': f'Error during system shutdown: {str(e)}'
                    })
            except:
                pass

async def main():
    """Main entry point"""
    coordinator = SistemaIIICoordinator()

    print("🚀 SISTEMA III - TRADING SYSTEM")
    print("   📊 Coordinated scanner + execution")
    print("   🔄 Multi-strategy workers")
    print("   🛡️ Risk management")
    print("   📡 Redis communication")
    print("   💾 SQLite coordination")
    print()

    try:
        success = await coordinator.start()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n🛑 Sistema III interrupted by user")
        await coordinator.stop()
        return 0

    except Exception as e:
        print(f"❌ Sistema III failed: {e}")
        coordinator.logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)