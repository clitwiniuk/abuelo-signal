#!/usr/bin/env python3
"""
Emergency kill switch para sistemas que no responden a Ctrl+C
"""

import os
import signal
import psutil
import sys

def find_trading_processes():
    """Encuentra procesos relacionados con el trading system"""
    processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            name = proc.info['name'] or ''
            
            # Buscar procesos de Python que contengan trading_system
            if (('python' in name.lower() or 'python3' in name.lower()) and 
                ('trading_system' in cmdline or 'streamlit' in cmdline or 'run_trading' in cmdline)):
                processes.append({
                    'pid': proc.info['pid'],
                    'name': name,
                    'cmdline': cmdline
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes

def kill_processes(processes):
    """Kill processes with escalating force"""
    for proc_info in processes:
        pid = proc_info['pid']
        name = proc_info['name']
        
        try:
            proc = psutil.Process(pid)
            
            print(f"🔫 Killing process: {name} (PID: {pid})")
            
            # Try SIGTERM first (graceful)
            try:
                proc.terminate()
                proc.wait(timeout=2)
                print(f"✅ Process {pid} terminated gracefully")
                continue
            except psutil.TimeoutExpired:
                print(f"⏰ Process {pid} didn't respond to SIGTERM, using SIGKILL...")
            
            # Force kill with SIGKILL
            try:
                proc.kill()
                proc.wait(timeout=1)
                print(f"💀 Process {pid} force killed")
            except psutil.TimeoutExpired:
                print(f"❌ Failed to kill process {pid}")
                
        except psutil.NoSuchProcess:
            print(f"✅ Process {pid} already dead")
        except Exception as e:
            print(f"❌ Error killing process {pid}: {e}")

def main():
    """Main emergency kill function"""
    print("🚨 EMERGENCY KILL SWITCH FOR TRADING SYSTEM")
    print("=" * 50)
    
    # Find trading processes
    processes = find_trading_processes()
    
    if not processes:
        print("✅ No trading system processes found")
        return
    
    print(f"Found {len(processes)} trading system processes:")
    for i, proc in enumerate(processes, 1):
        print(f"  {i}. PID {proc['pid']}: {proc['name']}")
        print(f"     CMD: {proc['cmdline'][:100]}...")
    
    print("\n🔫 Killing all trading system processes...")
    kill_processes(processes)
    
    print("\n✅ Emergency kill completed")
    
    # Double check
    remaining = find_trading_processes()
    if remaining:
        print(f"⚠️ {len(remaining)} processes still running:")
        for proc in remaining:
            print(f"  - PID {proc['pid']}: {proc['name']}")
    else:
        print("✅ All trading system processes terminated")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Emergency kill interrupted")
    except Exception as e:
        print(f"❌ Error in emergency kill: {e}")
        sys.exit(1)