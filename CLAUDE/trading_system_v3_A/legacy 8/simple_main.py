#!/usr/bin/env python3
"""
Simple Trading System Launcher with Visual Activity
"""

import os
import sys
import subprocess
import time
from datetime import datetime
import signal
import atexit
from core.market_calendar import get_market_calendar

def check_market_status():
    """Check and display detailed market status."""
    cal = get_market_calendar()
    now = datetime.now(cal.et_tz)
    
    print("\n📅 MARKET STATUS CHECK")
    print("-" * 50)
    print(f"Current Time (ET): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Check if it's a valid trading day
    if not cal.is_market_day(now):
        reason = "Holiday" if cal.is_holiday(now) else "Weekend/Closed"
        print(f"❌ MARKET CLOSED TODAY ({reason})")
        print("   System will run in MONITOR mode (no trades expected)")
        return False
        
    # 2. Check for Early Close
    if cal.is_early_close(now):
        print(f"⚠️  HALF TRADING DAY DETECTED")
        print(f"   Market closes early at {cal.EARLY_CLOSE.strftime('%I:%M %p')} ET")
    else:
        print("✅ Full Trading Day")
        
    # 3. Check Current Session
    session = cal.get_trading_session(now)
    print(f"🕒 Current Session: {session.upper()}")
    
    if session == 'closed':
        print("   (Market is currently outside trading hours)")
    elif session == 'premarket':
        print("   (Pre-market session active)")
    elif session == 'regular':
        print("   (Regular trading session active)")
    elif session == 'afterhours':
        print("   (After-hours session active)")
        
    print("-" * 50)
    return True

def main():
    print("🚀 STARTING SEPARATED TRADING SYSTEM...")
    print("=" * 50)
    
    # Check market status
    check_market_status()


    # Log startup to trader.log
    try:
        with open("logs/trader.log", "a") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"SYSTEM STARTUP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*50}\n")
    except Exception as e:
        print(f"⚠️  Could not write to trader.log: {e}")

    print("=" * 50)
    
    # Start trader
    print("⚡ Starting trader process...")
    trader_process = subprocess.Popen([
        sys.executable, "trader_main.py"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(3)  # Wait for trader to start
    
    # Start scanner  
    print("🔍 Starting scanner process...")
    scanner_process = subprocess.Popen([
        sys.executable, "scanner_main.py"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("✅ Both processes started!")
    print("=" * 50)
    print("📊 LIVE ACTIVITY MONITOR")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    # Register cleanup function to ensure processes are killed on exit
    def cleanup():
        print("\n🛑 Stopping processes...")
        
        # Terminate scanner
        if scanner_process.poll() is None:
            try:
                scanner_process.terminate()
            except:
                pass
                
        # Terminate trader
        if trader_process.poll() is None:
            try:
                trader_process.terminate()
            except:
                pass
                
        # Wait with timeout
        try:
            scanner_process.wait(timeout=2)
            trader_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Force kill if needed
            if scanner_process.poll() is None:
                scanner_process.kill()
            if trader_process.poll() is None:
                trader_process.kill()
                
        print("✅ All processes stopped")

    # Register cleanup for normal exit and signals
    atexit.register(cleanup)
    
    # Handle SIGTERM (kill command) gracefully
    def signal_handler(sig, frame):
        sys.exit(0) # This will trigger atexit
        
    signal.signal(signal.SIGTERM, signal_handler)
    
    last_scanner_count = 0
    last_trader_count = 0
    
    try:
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            try:
                # Count scanner activity
                with open("logs/scanner.log", "r") as f:
                    scanner_content = f.read()
                    scanner_count = scanner_content.count("📡 Published")
                
                # Count trader activity  
                with open("logs/trader.log", "r") as f:
                    trader_content = f.read()
                    trader_count = trader_content.count("📡 Received")
                
                # Show activity
                current_time = datetime.now().strftime("%H:%M:%S")
                if scanner_count > last_scanner_count or trader_count > last_trader_count:
                    print(f"[{current_time}] 🔍 Scanner: {scanner_count} cycles -> ⚡ Trader: {trader_count} received")
                    last_scanner_count = scanner_count
                    last_trader_count = trader_count
                else:
                    print(f"[{current_time}] 💤 Waiting for activity... (S:{scanner_count} T:{trader_count})")
                    
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Error reading logs: {e}")
                
    except KeyboardInterrupt:
        # atexit will handle cleanup
        print("\n👋 Interrupted by user")

if __name__ == "__main__":
    main()