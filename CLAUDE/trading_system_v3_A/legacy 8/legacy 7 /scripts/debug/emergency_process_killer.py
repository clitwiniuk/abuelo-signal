#!/usr/bin/env python3
"""
EMERGENCY PROCESS KILLER - Para detener procesos de trading en emergencia
"""

import subprocess
import sys
import time

def kill_trading_processes():
    """Kill all trading-related processes"""
    
    print("🚨 EMERGENCY: Killing all trading processes...")
    
    # Find processes
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        trading_pids = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['trading', 'main.py', 'start.py', 'streamlit']):
                if 'python' in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        trading_pids.append(pid)
                        print(f"Found trading process: PID {pid}")
                        print(f"  Command: {' '.join(parts[10:])}")
        
        if trading_pids:
            print(f"\n🛑 Killing {len(trading_pids)} processes...")
            
            # Try graceful shutdown first
            for pid in trading_pids:
                try:
                    subprocess.run(['kill', '-15', pid], check=True)
                    print(f"✅ Sent SIGTERM to PID {pid}")
                except subprocess.CalledProcessError:
                    print(f"❌ Failed to send SIGTERM to PID {pid}")
            
            # Wait and check
            time.sleep(3)
            print("\n⏳ Checking if processes stopped...")
            
            still_running = []
            for pid in trading_pids:
                try:
                    subprocess.run(['ps', '-p', pid], check=True, capture_output=True)
                    still_running.append(pid)
                except subprocess.CalledProcessError:
                    print(f"✅ PID {pid} stopped")
            
            # Force kill remaining processes
            if still_running:
                print(f"\n🔨 Force killing {len(still_running)} remaining processes...")
                for pid in still_running:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        print(f"🔨 Force killed PID {pid}")
                    except subprocess.CalledProcessError:
                        print(f"❌ Failed to force kill PID {pid}")
            
            print("\n✅ All trading processes stopped")
        else:
            print("✅ No trading processes found running")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    kill_trading_processes()