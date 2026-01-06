#!/usr/bin/env python3
# production/monitoring_dashboard.py
"""
Dashboard de Monitoreo Simple
Aprovecha PerformanceMonitor existente
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def display_dashboard():
    """Display simple dashboard"""
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        
        print("📊 SMALLCAP PRODUCTION DASHBOARD")
        print("=" * 50)
        print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Read status from logs or status file
        try:
            status_file = project_root / "production" / "status.json"
            if status_file.exists():
                with open(status_file) as f:
                    status = json.load(f)
                
                print("🚀 ESTADO DEL SISTEMA:")
                print(f"   Running: {status.get('is_running', 'Unknown')}")
                print(f"   Scans: {status.get('scan_count', 0)}")
                print(f"   Plays encontrados: {status.get('total_plays_found', 0)}")
                print(f"   Último scan: {status.get('last_scan_time', 'Never')}")
                print(f"   IBKR conectado: {status.get('ibkr_connected', False)}")
                print(f"   ML Engine activo: {status.get('ml_engine_enabled', False)}")
            else:
                print("⚠️ Status file not found")
        
        except Exception as e:
            print(f"❌ Error reading status: {e}")
        
        print()
        print("📈 MÉTRICAS CLAVE:")
        print("   [Implementar métricas específicas]")
        print()
        print("Press Ctrl+C to exit")
        
        time.sleep(10)  # Update every 10 seconds

if __name__ == "__main__":
    try:
        display_dashboard()
    except KeyboardInterrupt:
        print("\n👋 Dashboard cerrado")
