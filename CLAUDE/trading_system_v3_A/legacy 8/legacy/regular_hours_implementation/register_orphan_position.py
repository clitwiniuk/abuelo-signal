#!/usr/bin/env python3
"""
Registro Manual de Posición Huérfana
Adopta posiciones existentes en IBKR que no están registradas en UnifiedPositionManager
"""

import asyncio
import logging
from datetime import datetime
from core.service_locator import get_unified_position_manager

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def register_orphan_position():
    """
    Registra manualmente una posición que existe en IBKR pero no en UnifiedPositionManager
    """
    
    # Datos de la posición CMBM (desde los logs)
    symbol = "CMBM"
    entry_price = 1.84  # Del log: "CMBM @ $1.84 x 108 shares"
    quantity = 108
    entry_time = datetime(2025, 10, 29, 16, 34, 34)  # Del log de entrada
    strategy = "volume_absorption"  # Worker que abrió la posición
    strategy_type = "day"  # volume_absorption es day trading
    
    # Calcular datos derivados
    position_value = entry_price * quantity
    time_in_market_hours = 4.0  # INTRADAY horizon
    
    logger.info("=" * 60)
    logger.info("🎯 REGISTRO MANUAL DE POSICIÓN HUÉRFANA")
    logger.info("=" * 60)
    logger.info(f"📊 Symbol: {symbol}")
    logger.info(f"💰 Entry: ${entry_price:.2f} x {quantity} shares = ${position_value:.2f}")
    logger.info(f"📅 Entry Time: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🤖 Strategy: {strategy} ({strategy_type})")
    logger.info(f"⏰ Time in Market: {time_in_market_hours}h")
    
    try:
        # Obtener UnifiedPositionManager
        unified_manager = await get_unified_position_manager()
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager disponible")
            return False
            
        logger.info("✅ UnifiedPositionManager obtenido")
        
        # PASO 1: Verificar si ya está registrada
        existing_position = unified_manager.get_position(symbol)
        if existing_position:
            existing_strategy = existing_position.get('strategy', 'UNKNOWN')
            logger.info(f"🔍 {symbol} ya registrada con strategy: {existing_strategy}")
            
            if existing_strategy != 'UNKNOWN':
                logger.warning(f"⚠️ {symbol} ya tiene owner válido ({existing_strategy}) - NO es huérfana")
                return False
            else:
                logger.info(f"✅ {symbol} encontrada como posición UNKNOWN - adoptando...")
        
        # PASO 2: Preparar datos de posición
        position_data = {
            'entry_price': entry_price,
            'quantity': quantity,
            'position_value': position_value,
            'strategy': strategy,  # Actual worker owner
            'strategy_type': strategy_type,
            'trading_horizon': 'INTRADAY',
            'time_in_market_hours': time_in_market_hours,
            'opened_at': entry_time.isoformat(),
            'registered_at': datetime.now().isoformat(),
            'position_source': 'MANUAL_REGISTRATION_ORPHAN_ADOPTION'
        }
        
        logger.info("📋 Datos preparados:")
        for key, value in position_data.items():
            logger.info(f"   {key}: {value}")
        
        # PASO 3: Registrar posición (esto incluirá capital tracking)
        logger.info("🔄 Registrando posición...")
        success = unified_manager.register_position(
            symbol=symbol,
            strategy_type=strategy_type,
            position_data=position_data
        )
        
        if success:
            logger.info(f"✅ {symbol}: REGISTRADA EXITOSAMENTE EN UNIFIED POSITION MANAGER!")
            logger.info(f"🛡️ WorkerStopManager AHORA ACTIVO para {symbol}")
            logger.info(f"   - Stop Loss: 5% (${entry_price * 0.95:.2f})")
            logger.info(f"   - Take Profit: 10-30% según quality")
            logger.info(f"   - Trailing Stop: 3% después de 6% ganancia")
            logger.info(f"   - Time Stop: 4 horas")
            
            # Mostrar resumen del capital
            capital_summary = unified_manager.get_capital_summary()
            logger.info("💼 Capital Status:")
            logger.info(f"   Day Trading: ${capital_summary['day_trading']['used']:.2f}/${capital_summary['day_trading']['allocated']:.2f} usado")
            
            return True
        else:
            logger.error(f"❌ {symbol}: Fallo en registro")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error registrando posición {symbol}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando registro de posición huérfana...")
    
    success = await register_orphan_position()
    
    if success:
        logger.info("🎉 POSICIÓN ADOPTADA - CMBM ahora protegida con WorkerStopManager")
    else:
        logger.error("💥 FALLO en adopción de posición")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())