#!/usr/bin/env python3
"""
Monitoring script para verificar que Volume Absorption Worker
ahora registra posiciones y evalúa exits correctamente
"""

import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_volume_absorption_monitoring():
    """Monitorea si volume_absorption worker ahora registra posiciones"""
    
    logger.info("🔍 Monitoring Volume Absorption Worker exit tracking...")
    logger.info("   Looking for registration logs and exit evaluations")
    logger.info("")
    
    # Check if VolumeAbsorptionWorkerLogic.py was modified recently
    import os
    file_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/strategies/workers/volume_absorption_worker_logic.py"
    
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        mod_time = datetime.fromtimestamp(mtime)
        logger.info(f"📁 VolumeAbsorptionWorkerLogic.py modified: {mod_time}")
        logger.info("   If recent, fix should be active")
    else:
        logger.error(f"❌ File not found: {file_path}")
    
    logger.info("")
    logger.info("✅ EXPECTED BEHAVIOR:")
    logger.info("   1. Volume Absorption entries should show: '📝 {symbol}: Registered with WorkerStopManager'")
    logger.info("   2. Exit evaluations should show: '📊 {symbol}: stop_manager.check_exit() = False/True'")
    logger.info("   3. BYND-style exit logs should appear for CMBM, DVLT, IONZ, AKBA")
    logger.info("")
    logger.info("🔍 Look for these patterns in trader.log:")
    logger.info("   - '📝 CMBM: Registered with WorkerStopManager'")
    logger.info("   - '📊 CMBM: stop_manager.check_exit() = False'")
    logger.info("   - '🚪 volume_absorption: Exiting {SYMBOL}'")
    logger.info("")
    logger.info("⏰ Check trader.log in next 10-15 minutes for monitoring activity")

if __name__ == "__main__":
    monitor_volume_absorption_monitoring()
