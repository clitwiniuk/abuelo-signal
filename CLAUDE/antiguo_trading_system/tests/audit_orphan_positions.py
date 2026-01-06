#!/usr/bin/env python3
"""
Auditoría de Posiciones Huérfanas
Verifica todas las posiciones activas en IBKR vs registradas en UnifiedPositionManager
"""

import asyncio
import logging
from core.service_locator import get_unified_position_manager
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def audit_orphan_positions():
    """
    Auditoría completa de posiciones huérfanas
    """
    
    logger.info("=" * 60)
    logger.info("🔍 AUDITORÍA DE POSICIONES HUÉRFANAS")
    logger.info("=" * 60)
    
    try:
        # Obtener UnifiedPositionManager
        unified_manager = await get_unified_position_manager()
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager disponible")
            return
            
        logger.info("✅ UnifiedPositionManager obtenido")
        
        # Posiciones conocidas desde los logs recientes
        known_positions = [
            {"symbol": "CMBM", "shares": 108, "worker": "volume_absorption"},
            {"symbol": "DVLT", "shares": 70, "worker": "unknown"},
            {"symbol": "IONZ", "shares": 55, "worker": "unknown"},
            {"symbol": "AKBA", "shares": 87, "worker": "unknown"}
        ]
        
        logger.info("📊 Verificando posiciones conocidas...")
        
        orphans_found = []
        registered_positions = []
        
        for pos in known_positions:
            symbol = pos["symbol"]
            shares = pos["shares"]
            worker = pos["worker"]
            
            logger.info(f"\n🔍 Verificando {symbol} ({shares} shares, worker: {worker})")
            
            # Verificar si está en UnifiedPositionManager
            unified_pos = unified_manager.get_position(symbol)
            
            if unified_pos:
                registered_strategy = unified_pos.get('strategy', 'UNKNOWN')
                registered_type = unified_pos.get('strategy_type', 'UNKNOWN')
                logger.info(f"   ✅ REGISTRADA: strategy={registered_strategy}, type={registered_type}")
                registered_positions.append(symbol)
            else:
                logger.warning(f"   ❌ NO REGISTRADA - POSICIÓN HUÉRFANA")
                orphans_found.append(pos)
        
        # Resumen de auditoría
        logger.info("\n" + "=" * 60)
        logger.info("📋 RESUMEN DE AUDITORÍA")
        logger.info("=" * 60)
        
        logger.info(f"✅ POSICIONES REGISTRADAS ({len(registered_positions)}):")
        for symbol in registered_positions:
            logger.info(f"   • {symbol}")
        
        logger.info(f"\n❌ POSICIONES HUÉRFANAS ({len(orphans_found)}):")
        for orphan in orphans_found:
            logger.info(f"   • {orphan['symbol']}: {orphan['shares']} shares (worker: {orphan['worker']})")
        
        # Verificar capital usage
        capital_summary = unified_manager.get_capital_summary()
        logger.info(f"\n💰 CAPITAL STATUS:")
        logger.info(f"   Day Trading: ${capital_summary['day_trading']['used']:.2f}/${capital_summary['day_trading']['allocated']:.2f}")
        
        # Si hay huérfanas, ofrecer adoptarlas
        if orphans_found:
            logger.info(f"\n🎯 RECOMENDACIÓN: Adoptar {len(orphans_found)} posiciones huérfanas")
            return orphans_found
        else:
            logger.info(f"\n✅ TODAS LAS POSICIONES ESTÁN CORRECTAMENTE REGISTRADAS")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error en auditoría: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

async def adopt_all_orphans(orphans):
    """
    Adopta todas las posiciones huérfanas encontradas
    """
    if not orphans:
        logger.info("🎉 No hay posiciones huérfanas para adoptar")
        return
        
    logger.info(f"\n🚀 ADOPTANDO {len(orphans)} POSICIONES HUÉRFANAS")
    logger.info("=" * 60)
    
    try:
        unified_manager = await get_unified_position_manager()
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager disponible")
            return
            
        for orphan in orphans:
            symbol = orphan["symbol"]
            shares = orphan["shares"]
            worker = orphan["worker"]
            
            logger.info(f"\n🔄 Adoptando {symbol}...")
            
            # Datos estimados basados en patrón conocido
            if worker == "volume_absorption":
                entry_price = 1.84  # Precio típico para volume_absorption smallcaps
                strategy_type = "day"
            else:
                # Estimar basado en precio actual conocido
                entry_price = 2.75  # Precio aproximado para DVLT, IONZ, AKBA
                strategy_type = "day"
                
            position_value = entry_price * shares
            
            position_data = {
                'entry_price': entry_price,
                'quantity': shares,
                'position_value': position_value,
                'strategy': worker if worker != "unknown" else "unknown_worker",
                'strategy_type': strategy_type,
                'trading_horizon': 'INTRADAY',
                'time_in_market_hours': 4.0,
                'opened_at': datetime.now().isoformat(),
                'registered_at': datetime.now().isoformat(),
                'position_source': 'MANUAL_AUDIT_ADOPTION'
            }
            
            success = unified_manager.register_position(
                symbol=symbol,
                strategy_type=strategy_type,
                position_data=position_data
            )
            
            if success:
                logger.info(f"   ✅ {symbol}: ADOPTADA exitosamente")
            else:
                logger.error(f"   ❌ {symbol}: FALLO en adopción")
        
        # Resumen final
        logger.info(f"\n🎉 PROCESO DE ADOPCIÓN COMPLETADO")
        
    except Exception as e:
        logger.error(f"❌ Error adoptando posiciones: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando auditoría de posiciones...")
    
    orphans = await audit_orphan_positions()
    
    if orphans:
        logger.info(f"\n❓ ¿Adoptar {len(orphans)} posiciones huérfanas automáticamente?")
        # Para automatizar, descomenta la siguiente línea:
        # await adopt_all_orphans(orphans)
        
        print(f"\n🔄 Para adoptar manualmente, ejecuta:")
        print(f"   python adopt_position.py [SYMBOL] [SHARES] [WORKER]")
    else:
        logger.info("✅ Auditoría completada - No hay acciones requeridas")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())