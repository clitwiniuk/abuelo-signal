#!/usr/bin/env python3
"""
Sistema III Launcher - CORRECT ORDER
Launches coordinator FIRST, then scanner to fix Redis pub/sub timing
"""

import asyncio
import logging
import subprocess
import sys
import os
import signal
from datetime import datetime

def setup_logging():
    """Setup launcher logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/launcher.log')
        ]
    )

class SistemaIIILauncher:
    """Launches Sistema III components in correct order"""

    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger("SistemaIIILauncher")

        self.coordinator_process = None
        self.scanner_process = None
        self.is_running = False
        self.shutdown_requested = False

    def start_coordinator(self):
        """Start coordinator process FIRST"""
        try:
            self.logger.info("🚀 Starting coordinator FIRST...")

            # Start coordinator in separate process
            self.coordinator_process = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.logger.info(f"✅ Coordinator started (PID: {self.coordinator_process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start coordinator: {e}")
            return False

    def start_scanner(self):
        """Start scanner process AFTER coordinator is ready"""
        try:
            self.logger.info("🔍 Starting scanner AFTER coordinator...")

            # Start scanner in separate process
            self.scanner_process = subprocess.Popen(
                [sys.executable, "scanner/scanner_central.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.logger.info(f"✅ Scanner started (PID: {self.scanner_process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start scanner: {e}")
            return False

    async def monitor_processes(self):
        """Monitor both processes and handle failures"""
        self.logger.info("📊 Starting process monitoring...")

        while self.is_running and not self.shutdown_requested:
            try:
                # Check coordinator
                if self.coordinator_process:
                    coord_status = self.coordinator_process.poll()
                    if coord_status is not None:
                        self.logger.error(f"❌ Coordinator died with exit code: {coord_status}")
                        # Read any error output
                        try:
                            stdout, stderr = self.coordinator_process.communicate(timeout=1)
                            if stderr:
                                self.logger.error(f"Coordinator stderr: {stderr}")
                        except:
                            pass
                        break

                # Check scanner
                if self.scanner_process:
                    scanner_status = self.scanner_process.poll()
                    if scanner_status is not None:
                        self.logger.error(f"❌ Scanner died with exit code: {scanner_status}")
                        # Read any error output
                        try:
                            stdout, stderr = self.scanner_process.communicate(timeout=1)
                            if stderr:
                                self.logger.error(f"Scanner stderr: {stderr}")
                        except:
                            pass
                        break

                # Log health status every 60 seconds
                self.logger.debug("💓 Both processes running healthy")
                await asyncio.sleep(60)

            except Exception as e:
                self.logger.error(f"❌ Error in process monitoring: {e}")
                await asyncio.sleep(30)

    async def start(self):
        """Start Sistema III in correct order"""
        try:
            self.logger.info("🚀 Starting Sistema III with correct initialization order...")

            # 1. Start coordinator FIRST (to subscribe to Redis)
            if not self.start_coordinator():
                return False

            # 2. Wait for coordinator to initialize and subscribe
            self.logger.info("⏱️ Waiting for coordinator to initialize...")
            await asyncio.sleep(10)  # Give coordinator time to subscribe to Redis

            # 3. Start scanner SECOND (to publish to ready subscribers)
            if not self.start_scanner():
                self.stop_coordinator()
                return False

            # 4. Wait for scanner to initialize
            self.logger.info("⏱️ Waiting for scanner to initialize...")
            await asyncio.sleep(5)

            self.is_running = True
            self.logger.info("✅ Sistema III started in correct order!")
            self.logger.info("   1️⃣ Coordinator listening on Redis")
            self.logger.info("   2️⃣ Scanner publishing to Redis")
            self.logger.info("   📡 Communication should work correctly")

            # Setup signal handlers
            def signal_handler(signum, frame):
                self.logger.info(f"📡 Signal {signum} received - shutting down")
                self.shutdown_requested = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Monitor processes
            await self.monitor_processes()

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start Sistema III: {e}")
            return False
        finally:
            await self.stop()

    def stop_coordinator(self):
        """Stop coordinator process"""
        if self.coordinator_process:
            try:
                self.logger.info("🛑 Stopping coordinator...")
                self.coordinator_process.terminate()

                # Wait for graceful shutdown
                try:
                    self.coordinator_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Coordinator didn't stop gracefully, killing...")
                    self.coordinator_process.kill()
                    self.coordinator_process.wait()

                self.logger.info("✅ Coordinator stopped")
                self.coordinator_process = None

            except Exception as e:
                self.logger.error(f"❌ Error stopping coordinator: {e}")

    def stop_scanner(self):
        """Stop scanner process"""
        if self.scanner_process:
            try:
                self.logger.info("🛑 Stopping scanner...")
                self.scanner_process.terminate()

                # Wait for graceful shutdown
                try:
                    self.scanner_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Scanner didn't stop gracefully, killing...")
                    self.scanner_process.kill()
                    self.scanner_process.wait()

                self.logger.info("✅ Scanner stopped")
                self.scanner_process = None

            except Exception as e:
                self.logger.error(f"❌ Error stopping scanner: {e}")

    async def stop(self):
        """Stop all processes"""
        try:
            self.logger.info("🛑 Stopping Sistema III...")
            self.is_running = False

            # Stop scanner first (stops producing data)
            self.stop_scanner()

            # Then stop coordinator (stops consuming data)
            self.stop_coordinator()

            self.logger.info("✅ Sistema III stopped cleanly")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")

async def main():
    """Main launcher function"""
    launcher = SistemaIIILauncher()

    print("🚀 SISTEMA III LAUNCHER - CORRECT ORDER")
    print("   1️⃣ Starts coordinator FIRST (Redis subscriber)")
    print("   2️⃣ Starts scanner SECOND (Redis publisher)")
    print("   📡 Fixes Redis pub/sub timing issue")
    print()

    try:
        success = await launcher.start()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n🛑 Launcher interrupted by user")
        await launcher.stop()
        return 0

    except Exception as e:
        print(f"❌ Launcher failed: {e}")
        launcher.logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)