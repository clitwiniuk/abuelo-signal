#!/usr/bin/env python3
"""
Sistema_4 Main Coordinator
Orchestrates scanner, workers, and execution engine
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Dict, Any, List
from datetime import datetime
import subprocess
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared.database import Sistema4Database
from shared.message_bus import MessageBus
from execution.execution_engine import ExecutionEngine
from utils.log_config import setup_logging
from shared.config_reader import Sistema4Config
from notifications import telegram_client

class Sistema4Coordinator:
    """
    Main coordinator for Sistema_4
    Orchestrates all components of the distributed trading system
    """

    def __init__(self):
        setup_logging(level="INFO", log_file="logs/sistema4_main.log")
        self.logger = logging.getLogger("Sistema4Main")

        # Load configuration
        self.config = Sistema4Config()

        # Initialize components
        self.database = Sistema4Database()
        self.message_bus = MessageBus()
        self.execution_engine = ExecutionEngine()

        # Process management
        self.scanner_process = None
        self.worker_processes = {}
        self.background_tasks = []
        self.shutdown_event = asyncio.Event()

        # Auto-restart tracking
        self.restart_counts = {}  # Process name -> restart count

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self.max_restarts = 3     # Maximum restarts before giving up
        self.restart_delay = 30   # Seconds to wait before restart

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info("🚀 Sistema_4 Coordinator initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals (SIGINT/SIGTERM)"""
        if not self.shutdown_requested:
            self.shutdown_requested = True
            self.logger.info(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()

    async def start(self):
        """Start Sistema_4 coordinator and all components"""
        try:
            self.logger.info("🎯 Starting Sistema_4 Distributed Trading System...")

            # 1. Initialize database and cleanup
            self._cleanup_database()

            # 2. Start execution engine (centralized)
            if not await self.execution_engine.start():
                self.logger.error("❌ Failed to start execution engine")
                return False

            self.logger.info("✅ Execution Engine started")

            # 3. Start scanner process
            if not await self._start_scanner():
                self.logger.error("❌ Failed to start scanner")
                return False

            # 4. Start worker processes
            if not await self._start_workers():
                self.logger.error("❌ Failed to start workers")
                return False

            # 5. Start execution engine listener as background task
            self._start_execution_listener()

            # 6. Start background monitoring tasks
            self._start_background_tasks()

            self.is_running = True
            self.logger.info("🎉 Sistema_4 started successfully!")
            self.logger.info("   📊 Scanner: Running")
            self.logger.info(f"   👥 Workers: {len(self.worker_processes)} active")
            self.logger.info("   ⚙️ Execution Engine: Running")
            self.logger.info("   💾 Database: Ready")

            # Start Telegram notifications
            self._start_telegram_notifications()

            # Print system status
            await self._print_system_status()

            # Main monitoring loop
            await self._monitoring_loop()

        except Exception as e:
            self.logger.error(f"❌ Error starting Sistema_4: {e}")
            return False

    def _cleanup_database(self):
        """Clean up old data from database"""
        try:
            self.database.cleanup_old_data(hours=24)
            stats = self.database.get_stats()
            self.logger.info(f"📊 Database stats: {stats}")
        except Exception as e:
            self.logger.error(f"Error cleaning database: {e}")

    async def _start_scanner(self) -> bool:
        """Start scanner process"""
        try:
            scanner_cmd = [sys.executable, "scanner_central.py"]
            self.scanner_process = subprocess.Popen(
                scanner_cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Give scanner time to start
            await asyncio.sleep(3)

            if self.scanner_process.poll() is None:
                self.logger.info(f"✅ Scanner started (PID: {self.scanner_process.pid})")
                return True
            else:
                self.logger.error("❌ Scanner process failed to start")
                return False

        except Exception as e:
            self.logger.error(f"Error starting scanner: {e}")
            return False

    async def _start_workers(self) -> bool:
        """Start all worker processes"""
        try:
            workers = [
                {'name': 'gap_go', 'module': 'workers.gap_go_worker'},
                {'name': 'daily_plays', 'module': 'workers.daily_plays_worker'},
                {'name': 'macdv', 'module': 'workers.macdv_worker'},
                {'name': 'bull_flag', 'module': 'workers.bull_flag_worker'}
            ]

            for worker_config in workers:
                if await self._start_worker(worker_config):
                    self.logger.info(f"✅ {worker_config['name']} worker started")
                else:
                    self.logger.error(f"❌ Failed to start {worker_config['name']} worker")
                    return False

                # Stagger worker starts
                await asyncio.sleep(1)

            return True

        except Exception as e:
            self.logger.error(f"Error starting workers: {e}")
            return False

    async def _start_worker(self, worker_config: Dict[str, str]) -> bool:
        """Start individual worker process"""
        try:
            worker_name = worker_config['name']
            worker_file = f"workers/{worker_name}_worker.py"

            if not os.path.exists(worker_file):
                self.logger.error(f"Worker file not found: {worker_file}")
                return False

            worker_cmd = [sys.executable, worker_file]
            process = subprocess.Popen(
                worker_cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Give worker time to start
            await asyncio.sleep(2)

            if process.poll() is None:
                self.worker_processes[worker_name] = process
                return True
            else:
                self.logger.error(f"Worker {worker_name} failed to start")
                return False

        except Exception as e:
            self.logger.error(f"Error starting worker {worker_config['name']}: {e}")
            return False

    def _start_execution_listener(self):
        """Start execution engine listener as background task"""
        try:
            listener_task = asyncio.create_task(self.execution_engine.start_listening())
            self.background_tasks.append(listener_task)
            self.logger.info("✅ Execution Engine listener started as background task")
        except Exception as e:
            self.logger.error(f"❌ Error starting execution listener: {e}")

    def _start_background_tasks(self):
        """Start background monitoring tasks"""
        # Database cleanup task
        cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self.background_tasks.append(cleanup_task)

        # System monitoring task
        monitor_task = asyncio.create_task(self._system_monitor())
        self.background_tasks.append(monitor_task)

        self.logger.info("✅ Background tasks started")

    def _start_telegram_notifications(self):
        """Start Telegram notification system"""
        try:
            if telegram_client.is_enabled():
                # Start command listener
                if telegram_client.start_command_listener():
                    self.logger.info("✅ Telegram notifications started")
                    # Send startup notification
                    telegram_client.notify_system_startup()
                else:
                    self.logger.warning("⚠️ Telegram command listener failed to start")
            else:
                self.logger.info("📱 Telegram notifications disabled in config")
        except Exception as e:
            self.logger.error(f"❌ Error starting Telegram notifications: {e}")

    async def _periodic_cleanup(self):
        """Periodic database cleanup"""
        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(3600)  # Every hour
                self.database.cleanup_old_data(hours=24)
                self.logger.debug("🧹 Database cleanup completed")
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {e}")

    async def _system_monitor(self):
        """Monitor system health"""
        while self.is_running and not self.shutdown_requested:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Check worker processes
                dead_workers = []
                for worker_name, process in self.worker_processes.items():
                    if process.poll() is not None:
                        dead_workers.append(worker_name)

                if dead_workers:
                    self.logger.warning(f"⚠️ Dead workers detected: {dead_workers}")

                # Check scanner process
                if self.scanner_process and self.scanner_process.poll() is not None:
                    self.logger.warning("⚠️ Scanner process died")

                # Log system stats
                stats = self.database.get_stats()
                self.logger.info(f"📊 System stats: {stats}")

            except Exception as e:
                self.logger.error(f"Error in system monitor: {e}")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running and not self.shutdown_requested:
            try:
                # Wait for shutdown signal or timeout
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=10.0)
                    # Shutdown requested
                    break
                except asyncio.TimeoutError:
                    # Continue monitoring
                    pass

                # Just keep the coordinator alive and responsive
                # Actual work is done by background tasks and external processes

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                break

    async def _print_system_status(self):
        """Print current system status"""
        try:
            stats = self.database.get_stats()
            exec_stats = await self.execution_engine.get_execution_stats()
            trade_stats = self.database.get_trade_stats(days=30)

            status = f"""
🎯 SISTEMA_4 STATUS
==================
📊 Database Stats:
   • Active Positions: {stats.get('active_positions', 0)}
   • Active Reservations: {stats.get('active_reservations', 0)}
   • Unprocessed Opportunities: {stats.get('unprocessed_opportunities', 0)}
   • Open Trades: {stats.get('open_trades', 0)}
   • Completed Trades: {stats.get('completed_trades', 0)}

⚙️ Execution Engine:
   • IBKR Connected: {exec_stats.get('ibkr_connected', False)}
   • Pending Orders: {exec_stats.get('pending_orders', 0)}

📈 Trade Performance (30d):
   • Total Trades: {trade_stats.get('total_trades', 0)}
   • Win Rate: {trade_stats.get('win_rate', 0.0):.1f}%
   • Total P&L: ${trade_stats.get('total_pnl', 0.0):.2f}
   • Avg Trade: ${trade_stats.get('avg_pnl', 0.0):.2f}
   • Best Trade: ${trade_stats.get('best_trade', 0.0):.2f}
   • Worst Trade: ${trade_stats.get('worst_trade', 0.0):.2f}

👥 Workers: {len(self.worker_processes)} active
📡 Scanner: {'Running' if self.scanner_process and self.scanner_process.poll() is None else 'Stopped'}
"""
            self.logger.info(status)

        except Exception as e:
            self.logger.error(f"Error printing system status: {e}")

    async def stop(self):
        """Stop Sistema_4 coordinator and all components"""
        try:
            self.logger.info("🛑 Stopping Sistema_4...")
            self.is_running = False
            self.shutdown_requested = True

            # Stop background tasks
            for task in self.background_tasks:
                task.cancel()

            # Stop Telegram notifications
            try:
                telegram_client.stop_command_listener()
                self.logger.info("✅ Telegram notifications stopped")
            except Exception as e:
                self.logger.error(f"Error stopping Telegram: {e}")

            # Stop execution engine
            await self.execution_engine.stop()

            # Stop worker processes
            self.logger.info(f"🛑 Stopping {len(self.worker_processes)} workers...")
            for worker_name, process in self.worker_processes.items():
                try:
                    self.logger.info(f"   Terminating {worker_name} (PID: {process.pid})...")
                    process.terminate()

                    # Wait up to 5 seconds for graceful shutdown
                    for _ in range(10):
                        if process.poll() is not None:
                            break
                        time.sleep(0.5)

                    # Force kill if still running
                    if process.poll() is None:
                        self.logger.warning(f"   Force killing {worker_name}...")
                        process.kill()
                        time.sleep(0.5)

                    self.logger.info(f"✅ {worker_name} stopped")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping {worker_name}: {e}")

            # Stop scanner process
            if self.scanner_process:
                try:
                    self.logger.info(f"🛑 Stopping scanner (PID: {self.scanner_process.pid})...")
                    self.scanner_process.terminate()

                    # Wait up to 5 seconds for graceful shutdown
                    for _ in range(10):
                        if self.scanner_process.poll() is not None:
                            break
                        time.sleep(0.5)

                    # Force kill if still running
                    if self.scanner_process.poll() is None:
                        self.logger.warning("   Force killing scanner...")
                        self.scanner_process.kill()
                        time.sleep(0.5)

                    self.logger.info("✅ Scanner stopped")
                except Exception as e:
                    self.logger.error(f"❌ Error stopping scanner: {e}")

            self.logger.info("🛑 Sistema_4 stopped successfully")

        except Exception as e:
            self.logger.error(f"❌ Error stopping Sistema_4: {e}")

async def main():
    """Main function for Sistema_4"""
    coordinator = Sistema4Coordinator()

    print("🎯 SISTEMA_4 - DISTRIBUTED TRADING SYSTEM")
    print("   📊 Scanner: Detects opportunities")
    print("   👥 Workers: Specialized strategy analysis")
    print("   ⚙️ Engine: Centralized execution & risk")
    print("   💾 Database: Coordination & tracking")
    print()

    try:
        await coordinator.start()
        # After monitoring loop exits (due to shutdown signal)
        await coordinator.stop()
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Sistema_4 interrupted by user")
        await coordinator.stop()
        return 0
    except Exception as e:
        print(f"❌ Sistema_4 failed: {e}")
        coordinator.logger.error(f"Sistema_4 exception: {e}")
        await coordinator.stop()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)