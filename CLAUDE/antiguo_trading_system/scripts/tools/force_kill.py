#!/usr/bin/env python3
"""
EMERGENCY FORCE KILL SCRIPT
Use this when Ctrl+C doesn't work to stop the trading system immediately.
"""

import subprocess
import sys
import os
import signal

def find_trading_processes():
    """Find all trading system processes"""
    try:
        # Find Python processes related to trading
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        trading_processes = []
        for line in lines:
            if any(keyword in line for keyword in ['trading', 'run_trading_system', 'main.py', 'streamlit']):
                if 'python' in line:
                    parts = line.split()
                    pid = parts[1]
                    trading_processes.append((pid, line))
        
        return trading_processes
    except Exception as e:
        print(f"Error finding processes: {e}")
        return []

def force_kill_all():
    """Force kill all trading system processes"""
    processes = find_trading_processes()
    
    if not processes:
        print("❌ No trading system processes found")
        return
    
    print("🔍 Found trading system processes:")
    for pid, line in processes:
        print(f"   PID {pid}: {line}")
    
    print("\n🚨 FORCE KILLING ALL TRADING PROCESSES...")
    
    for pid, _ in processes:
        try:
            # Try graceful kill first
            os.kill(int(pid), signal.SIGTERM)
            print(f"✅ Sent SIGTERM to PID {pid}")
        except:
            pass
    
    import time
    time.sleep(2)  # Wait 2 seconds
    
    # Force kill any remaining processes
    for pid, _ in processes:
        try:
            # Force kill
            os.kill(int(pid), signal.SIGKILL)
            print(f"💀 FORCE KILLED PID {pid}")
        except ProcessLookupError:
            print(f"✅ PID {pid} already terminated")
        except Exception as e:
            print(f"⚠️ Could not kill PID {pid}: {e}")
    
    print("\n✅ FORCE KILL COMPLETED")

if __name__ == "__main__":
    print("🚨 EMERGENCY TRADING SYSTEM FORCE KILL")
    print("=" * 50)
    
    confirm = input("Are you sure you want to FORCE KILL all trading processes? (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y', 'sí', 's']:
        force_kill_all()
    else:
        print("❌ Operation cancelled")