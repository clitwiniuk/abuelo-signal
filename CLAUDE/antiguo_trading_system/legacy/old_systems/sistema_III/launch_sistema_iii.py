#!/usr/bin/env python3
"""
Sistema III Launcher
Launches both scanner and coordinator in parallel for full automation
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime
import subprocess
import threading
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.log_config import setup_logging

class SistemaIIILauncher:
    """
    Launches and manages both scanner and coordinator processes
    """

    def __init__(self):
        setup_logging(level="INFO", log_file="logs/launcher.log")
        self.logger = logging.getLogger("SistemaIIILauncher")

        # Process tracking
        self.scanner_process = None
        self.coordinator_task = None
        self.running = False
        self.shutdown_requested = False

        # Import coordinator here to avoid circular imports
        from main import SistemaIIICoordinator
        self.coordinator_class = SistemaIIICoordinator

        self.logger.info("🚀 Sistema III Launcher initialized")

    async def start_all(self):
        """Start both scanner and coordinator"""
        try:
            self.running = True
            self.logger.info("🚀 Starting Sistema III - Full Automation Mode")

            # Setup signal handlers
            def signal_handler(signum, frame):
                self.logger.info(f"📡 Signal {signum} received - shutting down all processes")
                self.shutdown_requested = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Start scanner process
            await self._start_scanner()

            # Wait for scanner to initialize completely
            await asyncio.sleep(8)

            # Start coordinator
            await self._start_coordinator()

        except Exception as e:
            self.logger.error(f"❌ Error starting Sistema III: {e}")
            await self.stop_all()

    async def _start_scanner(self):
        """Start scanner process in background"""
        try:
            scanner_script = os.path.join(os.path.dirname(__file__), 'scanner', 'scanner_central.py')

            if not os.path.exists(scanner_script):
                self.logger.error(f"❌ Scanner script not found: {scanner_script}")
                return False

            self.logger.info("🔍 Starting scanner process...")

            # Start scanner as subprocess
            self.scanner_process = subprocess.Popen(
                [sys.executable, scanner_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Monitor scanner output in background thread
            def monitor_scanner():
                try:
                    for line in iter(self.scanner_process.stdout.readline, ''):
                        if line.strip():
                            # Forward scanner logs with prefix
                            self.logger.info(f"[SCANNER] {line.strip()}")
                        if self.shutdown_requested:
                            break
                except Exception as e:
                    self.logger.error(f"❌ Error monitoring scanner: {e}")

            scanner_thread = threading.Thread(target=monitor_scanner, daemon=True)
            scanner_thread.start()

            self.logger.info("✅ Scanner process started")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error starting scanner: {e}")
            return False

    async def _start_coordinator(self):
        """Start coordinator in current async context"""
        try:
            self.logger.info("🎯 Starting coordinator...")

            # Create coordinator instance
            coordinator = self.coordinator_class()

            # Start coordinator (this is async)
            self.coordinator_task = asyncio.create_task(coordinator.start())

            self.logger.info("✅ Coordinator started")

            # Monitor both processes
            await self._monitor_processes()

        except Exception as e:
            self.logger.error(f"❌ Error starting coordinator: {e}")

    async def _monitor_processes(self):
        """Monitor both scanner and coordinator processes"""
        self.logger.info("👁️ Monitoring Sistema III processes...")

        try:
            while self.running and not self.shutdown_requested:
                # Check scanner process
                if self.scanner_process:
                    scanner_status = self.scanner_process.poll()
                    if scanner_status is not None:
                        self.logger.error(f"❌ Scanner process exited with code: {scanner_status}")
                        # Could restart scanner here if needed
                        break

                # Check coordinator task
                if self.coordinator_task and self.coordinator_task.done():
                    try:
                        result = self.coordinator_task.result()
                        self.logger.info(f"✅ Coordinator completed: {result}")
                    except Exception as e:
                        self.logger.error(f"❌ Coordinator error: {e}")
                    break

                # Wait before next check
                await asyncio.sleep(5)

        except Exception as e:
            self.logger.error(f"❌ Error in process monitoring: {e}")

        finally:
            await self.stop_all()

    async def stop_all(self):
        """Stop all processes gracefully"""
        try:
            self.logger.info("🛑 Stopping Sistema III processes...")
            self.running = False

            # Stop coordinator
            if self.coordinator_task and not self.coordinator_task.done():
                self.logger.info("🛑 Stopping coordinator...")
                self.coordinator_task.cancel()
                try:
                    await self.coordinator_task
                except asyncio.CancelledError:
                    self.logger.info("✅ Coordinator stopped")

            # Stop scanner process
            if self.scanner_process:
                self.logger.info("🛑 Stopping scanner...")
                self.scanner_process.terminate()

                # Wait for graceful shutdown
                try:
                    self.scanner_process.wait(timeout=10)
                    self.logger.info("✅ Scanner stopped gracefully")
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Scanner didn't stop gracefully, killing...")
                    self.scanner_process.kill()
                    self.scanner_process.wait()
                    self.logger.info("✅ Scanner killed")

            self.logger.info("✅ All Sistema III processes stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping processes: {e}")

async def main():
    """Main entry point"""
    launcher = SistemaIIILauncher()

    print("🚀 SISTEMA III - FULL AUTOMATION LAUNCHER")
    print("   🔍 Scanner: Detects opportunities automatically")
    print("   🎯 Coordinator: Executes trades automatically")
    print("   🤖 Workers: Multiple strategies running")
    print("   🛡️ Risk Manager: Protects your capital")
    print("   📡 Redis: Real-time communication")
    print("   💾 SQLite: Position tracking")
    print()
    print("   Press Ctrl+C to stop all processes")
    print()

    try:
        await launcher.start_all()
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Sistema III interrupted by user")
        await launcher.stop_all()
        return 0
    except Exception as e:
        print(f"❌ Sistema III launcher failed: {e}")
        launcher.logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)