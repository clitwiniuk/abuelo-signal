#!/usr/bin/env python3
"""
Separated Trading System Orchestrator
Launches scanner and trader as independent processes
"""

import os
import sys
import subprocess
import signal
import time
import logging
from datetime import datetime
from typing import Optional

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/orchestrator.log')
        ]
    )
    return logging.getLogger("Orchestrator")

class SeparatedTradingSystem:
    """
    Orchestrates scanner and trader as separate processes
    """
    
    def __init__(self):
        self.logger = setup_logging()
        self.scanner_process: Optional[subprocess.Popen] = None
        self.trader_process: Optional[subprocess.Popen] = None
        self.shutdown_requested = False
        
    def start(self):
        """Start both scanner and trader processes"""
        try:
            self.logger.info("🚀 Starting Separated Trading System...")
            
            # Setup signal handling
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Start trader first (so it's ready to receive opportunities)
            self.logger.info("⚡ Starting trader process...")
            self.trader_process = subprocess.Popen([
                sys.executable, "trader_main.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Give trader time to initialize
            time.sleep(3)
            
            # Start scanner
            self.logger.info("🔍 Starting scanner process...")
            self.scanner_process = subprocess.Popen([
                sys.executable, "scanner_main.py"  
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            self.logger.info("✅ Both processes started successfully")
            print("=" * 60)
            print("🤖 SEPARATED TRADING SYSTEM")
            print("=" * 60) 
            print("🔍 Scanner Process: Finding opportunities (Redis pub)")
            print("⚡ Trader Process: Executing trades (Redis sub)")
            print("📡 Communication: Redis pub/sub")
            print("=" * 60)
            print("📊 Activity Monitor (updates every 10s):")
            print("Press Ctrl+C to stop both processes")
            print()
            
            # Monitor both processes
            self._monitor_processes()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start separated system: {e}")
            self.stop()
            return False
            
        return True
    
    def _monitor_processes(self):
        """Monitor both processes and show activity summary"""
        scanner_cycles = 0
        trader_receptions = 0
        last_scanner_count = 0
        last_trader_count = 0
        
        while not self.shutdown_requested:
            try:
                # Check process health
                if self.trader_process and self.trader_process.poll() is not None:
                    self.logger.warning("⚠️ Trader process died, restarting...")
                    self.trader_process = subprocess.Popen([
                        sys.executable, "trader_main.py"
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if self.scanner_process and self.scanner_process.poll() is not None:
                    self.logger.warning("⚠️ Scanner process died, restarting...")
                    self.scanner_process = subprocess.Popen([
                        sys.executable, "scanner_main.py"
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor activity by checking log files
                try:
                    # Count scanner cycles
                    with open("logs/scanner.log", "r") as f:
                        scanner_content = f.read()
                        scanner_cycles = scanner_content.count("📡 Published") 
                    
                    # Count trader receptions
                    with open("logs/trader.log", "r") as f:
                        trader_content = f.read()
                        trader_receptions = trader_content.count("📡 Received")
                    
                    # Show activity if there's new activity
                    if scanner_cycles > last_scanner_count or trader_receptions > last_trader_count:
                        current_time = datetime.now().strftime("%H:%M:%S")
                        print(f"[{current_time}] 🔍 Scanner: {scanner_cycles} cycles | ⚡ Trader: {trader_receptions} receptions")
                        last_scanner_count = scanner_cycles
                        last_trader_count = trader_receptions
                        
                except Exception:
                    pass  # Ignore file read errors
                
                time.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"❌ Error monitoring processes: {e}")
                time.sleep(5)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"📡 Received signal {signum} - shutting down...")
        self.shutdown_requested = True
        self.stop()
    
    def stop(self):
        """Stop both processes gracefully"""
        try:
            self.logger.info("🛑 Stopping separated trading system...")
            
            # Stop scanner process
            if self.scanner_process:
                self.logger.info("🔍 Stopping scanner process...")
                self.scanner_process.terminate()
                try:
                    self.scanner_process.wait(timeout=10)
                    self.logger.info("✅ Scanner process stopped")
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Scanner process didn't stop gracefully, killing...")
                    self.scanner_process.kill()
            
            # Stop trader process
            if self.trader_process:
                self.logger.info("⚡ Stopping trader process...")
                self.trader_process.terminate()
                try:
                    self.trader_process.wait(timeout=10)
                    self.logger.info("✅ Trader process stopped")
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Trader process didn't stop gracefully, killing...")
                    self.trader_process.kill()
            
            self.logger.info("🛑 Separated trading system stopped")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping processes: {e}")

def main():
    """Main orchestrator function"""
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    system = SeparatedTradingSystem()
    
    try:
        success = system.start()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\\n🛑 Orchestrator interrupted")
        system.stop()
        return 0
    except Exception as e:
        print(f"❌ Orchestrator failed: {e}")
        system.stop()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)