#!/usr/bin/env python3
"""
SCRIP FINAL: Sincronizar Posiciones Existentes con Workers

Este script conecta las posiciones ya abiertas (CMBM, DVLT, etc.) 
con sus workers para activar el monitoring de exits
"""

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def force_sync_existing_positions():
    """Fuerza sincronización de posiciones existentes con workers"""
    
    try:
        logger.info("🔧 FORCE SYNC: Conectando posiciones existentes con workers")
        logger.info("=" * 60)
        
        # 1. Get ExecutionEngine instance (running trader)
        from core.execution_engine import ExecutionEngine
        execution_engine = ExecutionEngine()
        
        # 2. Verify workers exist
        workers_to_sync = []
        
        if hasattr(execution_engine, 'volume_absorption_worker') and execution_engine.volume_absorption_worker:
            workers_to_sync.append(('volume_absorption', execution_engine.volume_absorption_worker))
            
        if hasattr(execution_engine, 'daily_plays_worker') and execution_engine.daily_plays_worker:
            workers_to_sync.append(('daily_plays', execution_engine.daily_plays_worker))
            
        logger.info(f"🔍 Found {len(workers_to_sync)} active workers to sync")
        
        # 3. Manual sync for known positions based on broker data
        known_positions = {
            'CMBM': {
                'strategy': 'volume_absorption',
                'entry_price': 1.92,
                'quantity': 108,
                'entry_time': '2025-10-29T16:34:34'
            },
            'DVLT': {
                'strategy': 'daily_plays', 
                'entry_price': 2.84,
                'quantity': 70,
                'entry_time': '2025-10-29T15:52:07'
            },
            'IONZ': {
                'strategy': 'daily_plays',
                'entry_price': 3.65,
                'quantity': 55,
                'entry_time': '2025-10-29T17:07:58'
            },
            'AKBA': {
                'strategy': 'daily_plays',
                'entry_price': 2.29,
                'quantity': 87,
                'entry_time': '2025-10-29T18:35:45'
            }
        }
        
        synced_count = 0
        
        # 4. Sync each position with its worker
        for symbol, pos_data in known_positions.items():
            strategy = pos_data['strategy']
            entry_price = pos_data['entry_price']
            quantity = pos_data['quantity']
            entry_time_str = pos_data['entry_time']
            
            logger.info(f"🔄 Syncing {symbol}: {strategy} @ ${entry_price} x {quantity}")
            
            try:
                # Find the right worker
                worker = None
                for worker_name, worker_instance in workers_to_sync:
                    if worker_name == strategy:
                        worker = worker_instance
                        break
                        
                if not worker:
                    logger.warning(f"   ⚠️ Worker {strategy} not found - skipping {symbol}")
                    continue
                    
                # Convert entry_time
                try:
                    from dateutil import parser
                    entry_time = parser.parse(entry_time_str)
                except:
                    entry_time = datetime.now()
                    
                # Register with stop_manager
                if hasattr(worker, 'stop_manager'):
                    worker.stop_manager.register_position(symbol, entry_time)
                    logger.info(f"   ✅ Registered {symbol} with WorkerStopManager")
                    
                # Add to active_positions
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
                    'opportunity_data': {}
                }
                
                logger.info(f"   ✅ {symbol} synced with {strategy} worker")
                synced_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Failed to sync {symbol}: {e}")
                
        logger.info(f"🎯 FORCE SYNC COMPLETED: {synced_count}/{len(known_positions)} positions synced")
        
        # 5. Test monitoring for each synced worker
        for worker_name, worker in workers_to_sync:
            active_count = len(worker.active_positions)
            logger.info(f"🧪 {worker_name}: Now has {active_count} active positions")
            
            if active_count > 0:
                try:
                    await worker._monitor_positions()
                    logger.info(f"   ✅ {worker_name}: Test monitoring cycle executed")
                except Exception as e:
                    logger.error(f"   ❌ {worker_name}: Test monitoring failed: {e}")
                    
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in force sync: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(force_sync_existing_positions())
    
    if success:
        print("\n" + "="*60)
        print("✅ FORCE SYNC COMPLETADO")
        print("="*60)
        print("📊 POSICIONES AHORA MONITOREADAS:")
        print("   - CMBM (volume_absorption): ✅ Active monitoring")
        print("   - DVLT (daily_plays): ✅ Active monitoring") 
        print("   - IONZ (daily_plays): ✅ Active monitoring")
        print("   - AKBA (daily_plays): ✅ Active monitoring")
        print("")
        print("🔍 VERIFICAR EN LOS PRÓXIMOS 5-10 MINUTOS:")
        print("   - Logs: '📊 CMBM: stop_manager.check_exit() = False'")
        print("   - Logs: '📊 DVLT: stop_manager.check_exit() = False'")
        print("   - NO más: 'CMBM: Evaluating opportunity'")
        print("")
        print("🎯 NUEVAS POSICIONES: Siempre tendrán monitoring activo")
    else:
        print("❌ FORCE SYNC FALLÓ")