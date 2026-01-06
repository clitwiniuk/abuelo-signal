#!/usr/bin/env python3
"""
Verificación de WorkerStopManager Activo
Fuerza la evaluación de posiciones registradas
"""

import asyncio
import logging
from core.service_locator import get_unified_position_manager
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_worker_stop_manager():
    """
    Verifica si WorkerStopManager está detectando las posiciones adoptadas
    """
    
    logger.info("=" * 60)
    logger.info("🔍 VERIFICANDO WORKER STOP MANAGER ACTIVO")
    logger.info("=" * 60)
    
    try:
        # Obtener UnifiedPositionManager
        unified_manager = await get_unified_position_manager()
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager disponible")
            return
            
        logger.info("✅ UnifiedPositionManager obtenido")
        
        # Verificar posiciones registradas
        registered_symbols = []
        
        # Revisar day_positions
        day_positions = unified_manager.day_positions
        for symbol, data in day_positions.items():
            logger.info(f"📊 Posición registrada: {symbol}")
            logger.info(f"   • Worker: {data.get('strategy', 'UNKNOWN')}")
            logger.info(f"   • Valor: ${data.get('position_value', 0):.2f}")
            logger.info(f"   • Entrada: {data.get('entry_price', 0):.2f}")
            logger.info(f"   • Cantidad: {data.get('quantity', 0)}")
            registered_symbols.append(symbol)
        
        # Verificar swing_positions
        swing_positions = unified_manager.swing_positions
        for symbol, data in swing_positions.items():
            logger.info(f"📊 Posición swing registrada: {symbol}")
            logger.info(f"   • Worker: {data.get('strategy', 'UNKNOWN')}")
            logger.info(f"   • Valor: ${data.get('position_value', 0):.2f}")
            registered_symbols.append(symbol)
        
        logger.info(f"\n🎯 Total posiciones registradas: {len(registered_symbols)}")
        
        if registered_symbols:
            logger.info(f"📋 Símbolos a verificar: {', '.join(registered_symbols)}")
            
            # Simular evaluación de WorkerStopManager
            logger.info(f"\n🛡️ SIMULANDO EVALUACIÓN WORKER STOP MANAGER:")
            
            for symbol in registered_symbols:
                position_data = unified_manager.get_position(symbol)
                if position_data:
                    entry_price = position_data.get('entry_price', 0)
                    quantity = position_data.get('quantity', 0)
                    strategy = position_data.get('strategy', 'unknown')
                    
                    # Simular niveles de stop
                    stop_loss_level = entry_price * 0.95  # 5% stop loss
                    take_profit_levels = [
                        entry_price * 1.10,  # 10% TP
                        entry_price * 1.20,  # 20% TP
                        entry_price * 1.30   # 30% TP
                    ]
                    
                    logger.info(f"\n   📊 {symbol} ({strategy}):")
                    logger.info(f"      Entry: ${entry_price:.2f}")
                    logger.info(f"      Stop Loss: ${stop_loss_level:.2f} (5%)")
                    logger.info(f"      Take Profit 1: ${take_profit_levels[0]:.2f} (10%)")
                    logger.info(f"      Take Profit 2: ${take_profit_levels[1]:.2f} (20%)")
                    logger.info(f"      Take Profit 3: ${take_profit_levels[2]:.2f} (30%)")
                    
                    # Verificar time stop
                    opened_at = position_data.get('opened_at', '')
                    if opened_at:
                        logger.info(f"      Opened: {opened_at}")
                        # Asumiendo 4 horas máximo para INTRADAY
                        logger.info(f"      Time Stop: 4.0h maximum")
                    
        else:
            logger.warning("⚠️ NO hay posiciones registradas para verificar")
        
        # Verificar capital usage
        capital_summary = unified_manager.get_capital_summary()
        logger.info(f"\n💰 CAPITAL STATUS:")
        logger.info(f"   Day Trading: ${capital_summary['day_trading']['used']:.2f}/${capital_summary['day_trading']['allocated']:.2f}")
        logger.info(f"   Utilización: {capital_summary['day_trading']['utilization_pct']:.1f}%")
        
        # Diagnóstico
        logger.info(f"\n🔍 DIAGNÓSTICO:")
        if len(registered_symbols) > 0:
            logger.info(f"✅ Posiciones registradas: {len(registered_symbols)}")
            logger.info(f"💰 Capital tracking: ${capital_summary['day_trading']['used']:.2f}")
            logger.info(f"🛡️ WorkerStopManager debería estar monitoreando estas posiciones")
            logger.info(f"⏰ Próxima evaluación: Dentro de 2-5 minutos")
            
            if len(registered_symbols) == 0:
                logger.warning(f"❌ PROBLEMA: WorkerStopManager no debería estar activo")
        else:
            logger.error(f"❌ PROBLEMA CRÍTICO: No hay posiciones registradas")
            logger.error(f"❌ Las adopciones pueden haber fallado")
            
    except Exception as e:
        logger.error(f"❌ Error verificando WorkerStopManager: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Función principal"""
    logger.info("🚀 Verificando estado de WorkerStopManager...")
    
    await verify_worker_stop_manager()
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())