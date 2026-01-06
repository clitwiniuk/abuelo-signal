#!/usr/bin/env python3
"""
Improved Cleanup System - Adds better signal handling and timeout
"""

import signal
import sys
import os
import atexit
import threading
import time
from datetime import datetime, timedelta

class ImprovedCleanup:
    """Enhanced cleanup system with multiple safeguards"""
    
    def __init__(self, timeout_hours=12):
        self.cleanup_functions = []
        self.start_time = datetime.now()
        self.timeout_hours = timeout_hours
        self.shutdown_requested = False
        
        # Register cleanup
        self.setup_cleanup_handlers()
        
    def setup_cleanup_handlers(self):
        """Setup comprehensive cleanup handlers"""
        
        # 1. Atexit handler
        atexit.register(self.cleanup_all)
        
        # 2. Signal handlers (SIGINT, SIGTERM, SIGHUP if available)
        def signal_handler(signum, frame):
            signal_name = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM", 
                signal.SIGHUP: "SIGHUP" if hasattr(signal, 'SIGHUP') else "SIGHUP_LIKE"
            }.get(signum, f"Signal {signum}")
            
            print(f"\n🚨 {signal_name} received - cleaning up...")
            self.shutdown_requested = True
            self.cleanup_all()
            sys.exit(0)
            
        # Register signals (cross-platform)
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            if hasattr(signal, 'SIGHUP'):  # Unix only
                signal.signal(signal.SIGHUP, signal_handler)
        except Exception as e:
            print(f"Warning: Could not setup all signal handlers: {e}")
        
        # 3. Timeout watchdog (background thread)
        timeout_thread = threading.Thread(target=self._timeout_watchdog, daemon=True)
        timeout_thread.start()
        
        # 4. Periodic cleanup checker
        cleanup_thread = threading.Thread(target=self._periodic_check, daemon=True) 
        cleanup_thread.start()
    
    def register_cleanup(self, cleanup_func):
        """Register a cleanup function"""
        self.cleanup_functions.append(cleanup_func)
        
    def _timeout_watchdog(self):
        """Auto-shutdown after timeout"""
        while not self.shutdown_requested:
            time.sleep(300)  # Check every 5 minutes
            
            runtime = datetime.now() - self.start_time
            if runtime > timedelta(hours=self.timeout_hours):
                print(f"\n⏰ TIMEOUT: Process running for {runtime}")
                print(f"   Auto-shutdown after {self.timeout_hours} hours")
                self.cleanup_all()
                os._exit(1)  # Force exit
    
    def _periodic_check(self):
        """Periodic health check"""
        while not self.shutdown_requested:
            time.sleep(1800)  # Check every 30 minutes
            
            # Check if we're outside market hours (simple check)
            now = datetime.now()
            if now.hour < 6 or now.hour > 20:  # Outside 6 AM - 8 PM
                print(f"\n🕐 Outside market hours ({now.hour}:00)")
                print("   Consider stopping the system")
            
    def cleanup_all(self):
        """Execute all cleanup functions"""
        if self.shutdown_requested:
            return  # Already cleaning up
            
        self.shutdown_requested = True
        print("\n🧹 Executing cleanup functions...")
        
        for i, cleanup_func in enumerate(self.cleanup_functions):
            try:
                print(f"   Cleanup {i+1}/{len(self.cleanup_functions)}: {cleanup_func.__name__}")
                cleanup_func()
            except Exception as e:
                print(f"   ❌ Cleanup function failed: {e}")
        
        print("✅ All cleanup functions executed")

# Global instance for easy use
cleanup_manager = ImprovedCleanup()

def register_cleanup(func):
    """Decorator to register cleanup functions"""
    cleanup_manager.register_cleanup(func)
    return func

# Usage example:
if __name__ == "__main__":
    
    @register_cleanup
    def cleanup_example():
        print("🧹 Cleaning up example resources...")
        
    print("🚀 Starting process with improved cleanup...")
    print(f"   Timeout: {cleanup_manager.timeout_hours} hours")
    print("   Press Ctrl+C to test signal handling")
    
    try:
        # Simulate long-running process
        for i in range(10):
            print(f"Working... {i+1}/10")
            time.sleep(2)
    except KeyboardInterrupt:
        print("KeyboardInterrupt caught")
    
    print("Process finished normally")