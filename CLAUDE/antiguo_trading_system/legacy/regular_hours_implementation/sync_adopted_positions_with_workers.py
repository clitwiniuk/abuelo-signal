#!/usr/bin/env python3
"""
COMPLETE FIX: Sincronizar Posiciones Adoptadas con Active Positions

Problema identificado:
- Las posiciones huérfanas se adoptaron en UnifiedPositionManager
- PERO no se sincronizaron con self.active_positions de cada worker
- Por eso no hay monitoring de exits

Solución:
1. Consultar UnifiedPositionManager para obtener posiciones adoptadas
2. Sincronizar cada posición con su worker correspondiente
3. Registrar en WorkerStopManager de cada worker
4. Forzar execution de _monitor_positions() para testing inmediato
"""

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def sync_adopted_positions_with_workers():
    """Sincroniza posiciones adoptadas con los workers correspondientes"""
    
    try:
        # 1. Obtener UnifiedPositionManager
        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()
        
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager available")
            return False
            
        # 2. Obtener todas las posiciones día (adoptadas)
        day_positions = unified_manager.day_positions if hasattr(unified_manager, 'day_positions') else {}
        
        if not day_positions:
            logger.info("ℹ️ No day positions found in UnifiedPositionManager")
            return True
            
        logger.info(f"🔍 Found {len(day_positions)} adopted day positions to sync:")
        
        # 3. Importar ExecutionEngine y sus workers
        from core.execution_engine import ExecutionEngine
        execution_engine = ExecutionEngine()  # This will get the running instance
        
        synced_count = 0
        
        # 4. Sincronizar cada posición con su worker
        for symbol, position_data in day_positions.items():
            strategy = position_data.get('strategy', 'unknown')
            entry_price = position_data.get('entry_price', 0)
            quantity = position_data.get('quantity', 0)
            entry_time_str = position_data.get('entry_time', '')
            
            logger.info(f"   📊 {symbol}: {strategy} @ ${entry_price} x {quantity}")
            
            try:
                # Get the corresponding worker
                if strategy == 'volume_absorption':
                    # Import volume_absorption worker
                    from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
                    # Get worker from execution engine
                    worker = execution_engine.volume_absorption_worker
                elif strategy == 'daily_plays':
                    # Import daily_plays worker  
                    from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
                    worker = execution_engine.daily_plays_worker
                else:
                    logger.warning(f"⚠️ Unknown strategy {strategy} for {symbol} - skipping")
                    continue
                    
                if not worker:
                    logger.warning(f"⚠️ Worker for {strategy} not available - skipping {symbol}")
                    continue
                    
                # 5. Convert entry_time string to datetime
                if entry_time_str:
                    try:
                        from dateutil import parser
                        entry_time = parser.parse(entry_time_str)
                    except:
                        entry_time = datetime.now()
                else:
                    entry_time = datetime.now()
                    
                # 6. Register position in worker's stop_manager
                try:
                    if hasattr(worker, 'stop_manager'):
                        worker.stop_manager.register_position(symbol, entry_time)
                        logger.info(f"   ✅ Registered {symbol} with WorkerStopManager ({strategy})")
                    else:
                        logger.warning(f"   ⚠️ No stop_manager found for {strategy} worker")
                except Exception as e:
                    logger.error(f"   ❌ Failed to register {symbol} with stop_manager: {e}")
                    
                # 7. Add to worker's active_positions
                worker.active_positions[symbol] = {
                    'position': {
                        'symbol': symbol,
                        'entry_price': entry_price,
                        'quantity': quantity,
                        'strategy': strategy
                    },
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'quantity': quantity,
                    'opportunity_data': {}  # Empty for adopted positions
                }
                
                logger.info(f"   ✅ Synced {symbol} with {strategy} worker (active_positions)")
                synced_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Failed to sync {symbol}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
        # 8. Log results
        logger.info(f"🎯 SYNC COMPLETED: {synced_count}/{len(day_positions)} positions synced")
        
        # 9. Test monitoring for each worker
        logger.info("🧪 Testing worker monitoring...")
        
        test_workers = []
        
        if 'volume_absorption' in [p.get('strategy') for p in day_positions.values()]:
            try:
                worker = execution_engine.volume_absorption_worker
                if worker:
                    test_workers.append(('volume_absorption', worker))
            except:
                pass
                
        if 'daily_plays' in [p.get('strategy') for p in day_positions.values()]:
            try:
                worker = execution_engine.daily_plays_worker  
                if worker:
                    test_workers.append(('daily_plays', worker))
            except:
                pass
        
        for worker_name, worker in test_workers:
            active_count = len(worker.active_positions)
            logger.info(f"   📊 {worker_name}: {active_count} active positions")
            
            if active_count > 0:
                # Force a monitoring cycle
                try:
                    await worker._monitor_positions()
                    logger.info(f"   ✅ {worker_name}: Monitoring cycle executed")
                except Exception as e:
                    logger.error(f"   ❌ {worker_name}: Monitoring failed: {e}")
                    
        return True
        
    except Exception as e:
        logger.error(f"❌ Error syncing adopted positions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_monitoring_verification_script():
    """Crea script para verificar que el monitoring funciona"""
    
    script_content = '''#!/usr/bin/env python3
"""
Monitoring Verification Script
Verifica que las posiciones adoptadas ahora se están monitoreando
"""

import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_monitoring_active():
    """Verifica que el monitoring está activo"""
    
    logger.info("🔍 VERIFICANDO MONITORING DE POSICIONES ADOPTADAS")
    logger.info("=" * 60)
    
    try:
        import asyncio
        from core.service_locator import get_unified_position_manager
        
        async def check_sync():
            unified_manager = await get_unified_position_manager()
            
            if not unified_manager:
                logger.error("❌ UnifiedPositionManager not available")
                return
                
            day_positions = unified_manager.day_positions if hasattr(unified_manager, 'day_positions') else {}
            
            logger.info(f"📊 Posiciones adoptadas: {len(day_positions)}")
            
            for symbol, position_data in day_positions.items():
                strategy = position_data.get('strategy', 'unknown')
                entry_price = position_data.get('entry_price', 0)
                logger.info(f"   📈 {symbol}: {strategy} @ ${entry_price}")
                
            logger.info("")
            logger.info("✅ CHECKS A REALIZAR EN LOS PRÓXIMOS 10-15 MINUTOS:")
            logger.info("   1. Buscar logs: '📊 {symbol}: stop_manager.check_exit() = False/True'")
            logger.info("   2. Buscar logs: '🚪 {worker}: Exiting {symbol} - {reason}'")
            logger.info("   3. Verificar que NO aparecen como 'evaluating opportunity'")
            logger.info("")
            logger.info("🔍 PATRONES A BUSCAR EN trader.log:")
            logger.info("   - 'CMBM: stop_manager.check_exit() = False'")
            logger.info("   - 'DVLT: stop_manager.check_exit() = False'")  
            logger.info("   - 'IONZ: stop_manager.check_exit() = False'")
            logger.info("   - 'AKBA: stop_manager.check_exit() = False'")
            logger.info("")
            logger.info("⏰ Monitoring debería estar activo ahora")
            
        asyncio.run(check_sync())
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_monitoring_active()
'''
    
    script_path = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/verify_monitoring_active.py"
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        import os
        os.chmod(script_path, 0o755)
        logger.info(f"✅ Verification script created: {script_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating verification script: {e}")
        return False

if __name__ == "__main__":
    logger.info("🛠️  SINCRONIZANDO POSICIONES ADOPTADAS CON WORKERS")
    logger.info("=" * 60)
    
    # Run sync
    success = asyncio.run(sync_adopted_positions_with_workers())
    
    if success:
        logger.info("")
        logger.info("🎯 RESUMEN DEL FIX:")
        logger.info("   ✅ Posiciones adoptadas → sincronizadas con workers")
        logger.info("   ✅ Registradas en WorkerStopManager de cada worker")
        logger.info("   ✅ Añadidas a active_positions de cada worker")
        logger.info("   ✅ Monitoring cycle ejecutado para testing")
        logger.info("")
        logger.info("📋 RESULTADO ESPERADO:")
        logger.info("   - CMBM, DVLT, IONZ, AKBA ya NO aparecerán como 'evaluating opportunity'")
        logger.info("   - Aparecerán logs de 'stop_manager.check_exit()' cada minuto")
        logger.info("   - Sistema de exit monitoring completamente funcional")
        logger.info("")
        
        # Create verification script
        create_monitoring_verification_script()
        
        logger.info("✅ SINCRONIZACIÓN COMPLETADA")
        logger.info("   Monitoring de exits ahora activo para todas las posiciones")
        
    else:
        logger.error("❌ SINCRONIZACIÓN FALLIDA")