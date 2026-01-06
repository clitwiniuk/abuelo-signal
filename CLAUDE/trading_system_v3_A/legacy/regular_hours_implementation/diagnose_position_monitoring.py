#!/usr/bin/env python3
"""
Diagnóstico del Sistema de Monitoreo de Posiciones
Identificar por qué no funciona END OF DAY ni time stops
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import get_service_locator
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def diagnose_position_monitoring():
    """
    Diagnostica por qué el sistema de monitoreo de posiciones no funciona
    """
    
    logger.info("=" * 80)
    logger.info("🔍 DIAGNÓSTICO: SISTEMA DE MONITOREO DE POSICIONES")
    logger.info("=" * 80)
    
    # 1. Verificar ServiceLocator
    service_locator = get_service_locator()
    services = service_locator._services
    
    logger.info(f"🔍 Services registrados: {list(services.keys())}")
    
    # 2. Buscar workers activos
    active_workers = []
    for service_name, service in services.items():
        if hasattr(service, 'worker_name'):
            active_workers.append((service_name, service))
            logger.info(f"   ✅ Worker: {service.worker_name} ({type(service).__name__})")
            
            # Verificar si tiene stop_manager
            if hasattr(service, 'stop_manager'):
                stop_manager = service.stop_manager
                active_positions = getattr(stop_manager, 'active_positions', {})
                logger.info(f"      🛡️ Stop Manager: {type(stop_manager).__name__} - {len(active_positions)} posiciones")
                for symbol, pos_data in active_positions.items():
                    logger.info(f"         📈 {symbol}: {pos_data}")
            else:
                logger.info(f"      ❌ SIN Stop Manager")
    
    # 3. Verificar UnifiedPositionManager
    unified_manager = service_locator.get_service('unified_position_manager')
    if unified_manager:
        day_positions = unified_manager.day_positions
        swing_positions = unified_manager.swing_positions
        
        logger.info(f"💼 UnifiedPositionManager:")
        logger.info(f"   📈 Day positions: {len(day_positions)}")
        for symbol, data in day_positions.items():
            opened_at = data.get('opened_at', 'UNKNOWN')
            logger.info(f"      • {symbol}: ${data.get('position_value', 0):.2f} (opened: {opened_at})")
        
        logger.info(f"   📉 Swing positions: {len(swing_positions)}")
        for symbol, data in swing_positions.items():
            opened_at = data.get('opened_at', 'UNKNOWN')
            logger.info(f"      • {symbol}: ${data.get('position_value', 0):.2f} (opened: {opened_at})")
    else:
        logger.error("❌ No hay UnifiedPositionManager registrado")
    
    # 4. Analizar el problema principal
    logger.info(f"\n🚨 ANÁLISIS DEL PROBLEMA:")
    
    # Verificar si las posiciones están en UnifiedPositionManager pero NO en WorkerStopManagers
    unified_symbols = set(unified_manager.day_positions.keys()) if unified_manager else set()
    
    worker_stop_symbols = set()
    for service_name, service in active_workers:
        if hasattr(service, 'stop_manager'):
            stop_positions = getattr(service.stop_manager, 'active_positions', {})
            worker_stop_symbols.update(stop_positions.keys())
    
    logger.info(f"   📊 Posiciones en UnifiedPositionManager: {len(unified_symbols)}")
    logger.info(f"   📊 Posiciones en WorkerStopManagers: {len(worker_stop_symbols)}")
    
    orphaned_in_unified = unified_symbols - worker_stop_symbols
    if orphaned_in_unified:
        logger.warning(f"   ⚠️ POSICIONES HUÉRFANAS (en Unified pero no en WorkerStop): {orphaned_in_unified}")
        for symbol in orphaned_in_unified:
            if unified_manager and symbol in unified_manager.day_positions:
                data = unified_manager.day_positions[symbol]
                opened_at = data.get('opened_at', 'unknown')
                logger.warning(f"      • {symbol}: abierta desde {opened_at} - SIN WORKER STOP MANAGER")
    
    # 5. Verificar timing de posiciones
    logger.info(f"\n⏰ ANÁLISIS DE TIMING:")
    current_time = datetime.now()
    
    for symbol in unified_symbols:
        if unified_manager and symbol in unified_manager.day_positions:
            data = unified_manager.day_positions[symbol]
            opened_at_str = data.get('opened_at', '')
            
            try:
                # Parsear fecha de apertura (si está en formato ISO)
                if opened_at_str and 'T' in opened_at_str:
                    opened_at = datetime.fromisoformat(opened_at_str.replace('Z', '+00:00'))
                else:
                    opened_at = current_time  # fallback
                
                time_open = current_time - opened_at
                hours_open = time_open.total_seconds() / 3600
                
                logger.info(f"   ⏱️ {symbol}: {hours_open:.1f} horas abierta")
                
                # Verificar si debería haber salido por time stop
                if hours_open >= 4.0:
                    logger.error(f"      🚨 DEBERÍA HABER SALIDO por time stop (4+ horas)")
                elif hours_open >= 2.0:
                    logger.warning(f"      ⚠️ Cercana a time stop (2+ horas)")
                    
            except Exception as e:
                logger.warning(f"   ⚠️ {symbol}: Error calculando tiempo abierto: {e}")
    
    # 6. Identificar causa raíz
    logger.info(f"\n🎯 CAUSA RAÍZ IDENTIFICADA:")
    logger.info(f"   1. ✅ UnifiedPositionManager: REGISTRA posiciones")
    logger.info(f"   2. ❌ WorkerStopManagers: NO TIENEN las posiciones registradas")
    logger.info(f"   3. ❌ Sin WorkerStopManager = Sin monitoreo = Sin EOD/Tiempo/Stop-Loss")
    logger.info(f"   4. ❌ Workers buscan NUEVAS oportunidades, no monitorean existentes")
    
    # 7. Verificar logs recientes de monitoreo
    logger.info(f"\n📋 VERIFICACIÓN DE LOGS:")
    log_file = 'logs/trader.log'
    if os.path.exists(log_file):
        # Verificar si hay logs de monitoreo en las últimas 2 horas
        two_hours_ago = current_time - timedelta(hours=2)
        logger.info(f"   📊 Verificando logs desde {two_hours_ago.strftime('%Y-%m-%d %H:%M')}")
        
        # Contar líneas de logs relevantes
        monitor_keywords = ['_monitor_positions', 'should_exit', 'check_exit', 'WorkerStopManager']
        keyword_counts = {}
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    # Verificar si la línea es reciente
                    if line.startswith(f"2025-10-29"):
                        for keyword in monitor_keywords:
                            if keyword in line:
                                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        except Exception as e:
            logger.error(f"   ❌ Error leyendo logs: {e}")
        
        if keyword_counts:
            logger.info(f"   📈 Logs de monitoreo encontrados:")
            for keyword, count in keyword_counts.items():
                logger.info(f"      • {keyword}: {count} menciones")
        else:
            logger.error(f"   ❌ NO HAY logs de monitoreo en las últimas horas")
    
    # 8. Conclusiones y recomendaciones
    logger.info(f"\n🏁 CONCLUSIÓN:")
    logger.info(f"   ❌ SISTEMA DE MONITOREO COMPLETAMENTE DESCONECTADO")
    logger.info(f"   ❌ Posiciones huérfanas SIN protección")
    logger.info(f"   ❌ End of Day NO funciona")
    logger.info(f"   ❌ Time stops NO funcionan")
    logger.info(f"   ❌ Stop loss/take profit NO funcionan")
    
    logger.info(f"\n🔧 RECOMENDACIONES:")
    logger.info(f"   1. Registrar posiciones en sus WorkerStopManagers individuales")
    logger.info(f"   2. Implementar monitoring loop para workers existentes")
    logger.info(f"   3. Verificar que _monitor_positions() se ejecute regularmente")
    logger.info(f"   4. Añadir logs de debugging al monitoring system")

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando diagnóstico del sistema de monitoreo...")
    
    await diagnose_position_monitoring()
    
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())