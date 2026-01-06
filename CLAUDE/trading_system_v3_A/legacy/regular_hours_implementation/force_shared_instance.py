#!/usr/bin/env python3
"""
Forzar uso de la misma instancia del trader principal
"""

import asyncio
import logging
from core.service_locator import get_service_locator
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def force_shared_unified_position_manager():
    """
    Forzar el uso de la misma instancia que el trader principal
    """
    
    logger.info("=" * 60)
    logger.info("🔗 FORZANDO INSTANCIA COMPARTIDA DEL TRADER")
    logger.info("=" * 60)
    
    try:
        # Obtener ServiceLocator del sistema
        service_locator = get_service_locator()
        
        logger.info(f"🔍 ServiceLocator ID: {id(service_locator)}")
        logger.info(f"🔍 Services registradas: {list(service_locator._services.keys())}")
        
        # Verificar si ya existe unified_position_manager
        existing_manager = service_locator.get_service('unified_position_manager')
        
        if existing_manager:
            logger.info("✅ UnifiedPositionManager YA EXISTE en ServiceLocator")
            logger.info(f"📊 Day positions count: {len(existing_manager.day_positions)}")
            logger.info(f"📊 Swing positions count: {len(existing_manager.swing_positions)}")
            
            # Mostrar posiciones existentes
            for symbol, data in existing_manager.day_positions.items():
                logger.info(f"   📈 {symbol}: ${data.get('position_value', 0):.2f} ({data.get('strategy', 'UNKNOWN')})")
            
            for symbol, data in existing_manager.swing_positions.items():
                logger.info(f"   📈 {symbol}: ${data.get('position_value', 0):.2f} ({data.get('strategy', 'UNKNOWN')})")
                
            return existing_manager
        else:
            logger.info("⚠️ No hay UnifiedPositionManager registrado - Creando uno nuevo...")
            
            # Crear el UnifiedPositionManager usando ServiceLocator
            manager = await service_locator.get_or_create_unified_position_manager()
            
            logger.info("✅ UnifiedPositionManager creado via ServiceLocator")
            return manager
            
    except Exception as e:
        logger.error(f"❌ Error accediendo a ServiceLocator compartido: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def adopt_with_shared_instance():
    """
    Adoptar posiciones usando la instancia compartida
    """
    
    manager = await force_shared_unified_position_manager()
    
    if not manager:
        logger.error("❌ No se pudo obtener UnifiedPositionManager compartido")
        return
        
    # Verificar si ya hay posiciones registradas
    existing_symbols = list(manager.day_positions.keys()) + list(manager.swing_positions.keys())
    
    if existing_symbols:
        logger.info(f"⚠️ Posiciones ya existen: {', '.join(existing_symbols)}")
        logger.info("🛑 NO adoptando - las posiciones ya están registradas")
        return
    
    # Datos para adoptar (solo si no existen)
    positions_to_adopt = [
        {"symbol": "CMBM", "shares": 108, "entry_price": 1.84, "worker": "volume_absorption"},
        {"symbol": "DVLT", "shares": 70, "entry_price": 2.84, "worker": "daily_plays"},
        {"symbol": "IONZ", "shares": 55, "entry_price": 3.65, "worker": "daily_plays"},
        {"symbol": "AKBA", "shares": 87, "entry_price": 2.29, "worker": "daily_plays"}
    ]
    
    logger.info(f"\n🚀 Adoptando {len(positions_to_adopt)} posiciones en INSTANCIA COMPARTIDA...")
    
    for pos in positions_to_adopt:
        symbol = pos["symbol"]
        shares = pos["shares"]
        entry_price = pos["entry_price"]
        worker = pos["worker"]
        
        position_value = entry_price * shares
        strategy_type = "day"
        
        position_data = {
            'entry_price': entry_price,
            'quantity': shares,
            'position_value': position_value,
            'strategy': worker,
            'strategy_type': strategy_type,
            'trading_horizon': 'INTRADAY',
            'time_in_market_hours': 4.0,
            'opened_at': "2025-10-29T16:34:34",
            'registered_at': datetime.now().isoformat(),
            'position_source': 'SHARED_INSTANCE_ADOPTION'
        }
        
        logger.info(f"📝 Registrando {symbol} en instancia compartida...")
        
        success = manager.register_position(
            symbol=symbol,
            strategy_type=strategy_type,
            position_data=position_data
        )
        
        if success:
            logger.info(f"   ✅ {symbol}: Registrada exitosamente en trader principal")
        else:
            logger.error(f"   ❌ {symbol}: FALLO en registro")

async def main():
    """Función principal"""
    logger.info("🚀 Forzando uso de instancia compartida...")
    
    await adopt_with_shared_instance()
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())