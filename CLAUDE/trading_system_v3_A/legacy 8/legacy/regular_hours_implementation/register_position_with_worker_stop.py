#!/usr/bin/env python3
"""
Registrar posiciones huérfanas en sus WorkerStopManager individuales
Para CMBM y otras posiciones adoptadas
"""

import asyncio
import logging
from core.service_locator import get_service_locator
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def register_with_worker_stop_manager():
    """
    Registrar CMBM en su WorkerStopManager individual
    """
    
    logger.info("=" * 60)
    logger.info("🛡️ REGISTRANDO POSICIONES EN WORKER STOP MANAGERS")
    logger.info("=" * 60)
    
    try:
        # Verificar ServiceLocator y sus services
        service_locator = get_service_locator()
        services = service_locator._services
        
        logger.info(f"🔍 Services registrados: {list(services.keys())}")
        
        # Buscar el volume_absorption worker
        volume_absorption_worker = None
        for service_name, service in services.items():
            if service_name and hasattr(service, 'worker_name'):
                if service.worker_name == 'volume_absorption':
                    volume_absorption_worker = service
                    break
        
        if volume_absorption_worker:
            logger.info("✅ Volume Absorption Worker encontrado")
            
            # Verificar su stop_manager
            if hasattr(volume_absorption_worker, 'stop_manager'):
                stop_manager = volume_absorption_worker.stop_manager
                logger.info(f"✅ Stop Manager encontrado: {type(stop_manager).__name__}")
                
                # Verificar posiciones activas en el stop_manager
                active_positions = getattr(stop_manager, 'active_positions', {})
                logger.info(f"📊 Posiciones activas en stop_manager: {list(active_positions.keys())}")
                
                # Registrar CMBM si no está ya registrada
                if 'CMBM' not in active_positions:
                    logger.info("📝 Registrando CMBM en Volume Absorption Worker Stop Manager...")
                    
                    # Datos de CMBM
                    entry_time = datetime(2025, 10, 29, 16, 34, 34)
                    
                    # Registrar en el stop_manager individual
                    stop_manager.register_position('CMBM', entry_time)
                    
                    logger.info("✅ CMBM registrada exitosamente en WorkerStopManager")
                    logger.info("🛡️ WorkerStopManager ahora monitoreará CMBM para:")
                    logger.info("   - Stop Loss: 5% (alrededor de $1.75)")
                    logger.info("   - Take Profit: 8-30% (alrededor de $1.99-$2.39)")
                    logger.info("   - Trailing Stop: 2% después de 6% ganancia")
                    logger.info("   - Time Stop: 4 horas máximo")
                    
                else:
                    logger.info("⚠️ CMBM ya está registrada en WorkerStopManager")
            else:
                logger.error("❌ Volume Absorption Worker no tiene stop_manager")
        else:
            logger.error("❌ Volume Absorption Worker no encontrado")
            
        # Verificar Daily Plays Workers
        daily_plays_workers = []
        for service_name, service in services.items():
            if service_name and hasattr(service, 'worker_name'):
                if service.worker_name == 'daily_plays':
                    daily_plays_workers.append(service)
        
        if daily_plays_workers:
            logger.info(f"✅ {len(daily_plays_workers)} Daily Plays Workers encontrados")
            
            for i, worker in enumerate(daily_plays_workers):
                if hasattr(worker, 'stop_manager'):
                    stop_manager = worker.stop_manager
                    active_positions = getattr(stop_manager, 'active_positions', {})
                    
                    logger.info(f"   Worker {i+1}: {list(active_positions.keys())}")
                    
                    # DVLT, IONZ, AKBA deberían estar aquí
                    expected_symbols = ['DVLT', 'IONZ', 'AKBA']
                    for symbol in expected_symbols:
                        if symbol not in active_positions:
                            logger.info(f"   📝 Registrando {symbol} en Daily Plays Worker...")
                            
                            entry_time = {
                                'DVLT': datetime(2025, 10, 29, 15, 52, 7),
                                'IONZ': datetime(2025, 10, 29, 17, 7, 58),
                                'AKBA': datetime(2025, 10, 29, 18, 35, 45)
                            }.get(symbol, datetime.now())
                            
                            stop_manager.register_position(symbol, entry_time)
                            logger.info(f"   ✅ {symbol} registrada en WorkerStopManager")
                            
        else:
            logger.error("❌ No se encontraron Daily Plays Workers")
            
        logger.info(f"\n🎉 REGISTRO COMPLETADO")
        logger.info(f"🛡️ WorkerStopManagers ahora monitorean las posiciones")
        logger.info(f"⏰ Próxima evaluación: Dentro de 2-5 minutos")
            
    except Exception as e:
        logger.error(f"❌ Error registrando en WorkerStopManager: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Función principal"""
    logger.info("🚀 Registrando posiciones en WorkerStopManager...")
    
    await register_with_worker_stop_manager()
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())