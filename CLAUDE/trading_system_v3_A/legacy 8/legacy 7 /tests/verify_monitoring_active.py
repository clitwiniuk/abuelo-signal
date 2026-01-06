#!/usr/bin/env python3
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
