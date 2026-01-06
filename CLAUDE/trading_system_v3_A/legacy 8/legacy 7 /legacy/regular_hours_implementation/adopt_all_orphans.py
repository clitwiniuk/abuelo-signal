#!/usr/bin/env python3
"""
Adopción Automática de Posiciones Huérfanas
Con datos reales obtenidos de los logs
"""

import asyncio
import logging
from core.service_locator import get_unified_position_manager
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def adopt_all_orphan_positions():
    """
    Adopta todas las posiciones huérfanas con datos reales
    """
    
    logger.info("=" * 60)
    logger.info("🚀 ADOPTANDO TODAS LAS POSICIONES HUÉRFANAS")
    logger.info("=" * 60)
    
    try:
        unified_manager = await get_unified_position_manager()
        if not unified_manager:
            logger.error("❌ No UnifiedPositionManager disponible")
            return
            
        # Datos reales de los logs
        orphan_positions = [
            {
                "symbol": "CMBM",
                "shares": 108,
                "entry_price": 1.84,
                "worker": "volume_absorption",
                "logged_entry": "Oct 29 16:34:34"
            },
            {
                "symbol": "DVLT", 
                "shares": 70,
                "entry_price": 2.84,
                "worker": "daily_plays",
                "logged_entry": "Oct 29 15:52:07"
            },
            {
                "symbol": "IONZ",
                "shares": 55,
                "entry_price": 3.65,
                "worker": "daily_plays", 
                "logged_entry": "Oct 29 17:07:58"
            },
            {
                "symbol": "AKBA",
                "shares": 87,
                "entry_price": 2.29,
                "worker": "daily_plays",
                "logged_entry": "Oct 29 18:35:45"
            }
        ]
        
        total_value = 0
        adopted_count = 0
        
        for pos in orphan_positions:
            symbol = pos["symbol"]
            shares = pos["shares"]
            entry_price = pos["entry_price"]
            worker = pos["worker"]
            logged_entry = pos["logged_entry"]
            
            position_value = entry_price * shares
            total_value += position_value
            
            logger.info(f"\n🔄 Adoptando {symbol}...")
            logger.info(f"   📊 Datos: {shares} shares @ ${entry_price:.2f} = ${position_value:.2f}")
            logger.info(f"   👤 Worker: {worker}")
            logger.info(f"   📅 Entrada: {logged_entry}")
            
            # Determinar strategy_type basado en worker
            strategy_type = "day"  # Todos los workers actuales son day trading
            
            position_data = {
                'entry_price': entry_price,
                'quantity': shares,
                'position_value': position_value,
                'strategy': worker,
                'strategy_type': strategy_type,
                'trading_horizon': 'INTRADAY',
                'time_in_market_hours': 4.0,
                'opened_at': "2025-10-29T16:34:34",  # Hora real aproximada
                'registered_at': datetime.now().isoformat(),
                'position_source': 'MANUAL_ADOPTION_AUDIT',
                'original_log_entry': logged_entry
            }
            
            success = unified_manager.register_position(
                symbol=symbol,
                strategy_type=strategy_type,
                position_data=position_data
            )
            
            if success:
                logger.info(f"   ✅ {symbol}: ADOPTADA exitosamente")
                adopted_count += 1
            else:
                logger.error(f"   ❌ {symbol}: FALLO en adopción")
        
        # Resumen final
        logger.info(f"\n" + "=" * 60)
        logger.info("🎉 PROCESO DE ADOPCIÓN COMPLETADO")
        logger.info("=" * 60)
        logger.info(f"✅ Posiciones adoptadas: {adopted_count}/4")
        logger.info(f"💰 Total valor registrado: ${total_value:.2f}")
        
        # Verificar capital usage
        capital_summary = unified_manager.get_capital_summary()
        logger.info(f"\n💰 CAPITAL STATUS ACTUALIZADO:")
        logger.info(f"   Day Trading: ${capital_summary['day_trading']['used']:.2f}/${capital_summary['day_trading']['allocated']:.2f}")
        logger.info(f"   Utilización: {capital_summary['day_trading']['utilization_pct']:.1f}%")
        
        # Mostrar posiciones registradas
        day_positions = capital_summary.get('day_trading', {}).get('positions', [])
        if day_positions:
            logger.info(f"\n📊 POSICIONES REGISTRADAS:")
            for position in day_positions:
                symbol = position.get('symbol', 'N/A')
                value = position.get('position_value', 0)
                logger.info(f"   • {symbol}: ${value:.2f}")
        
        logger.info(f"\n🛡️ WorkerStopManager activará MONITOREO AUTOMÁTICO en próximo ciclo")
        
    except Exception as e:
        logger.error(f"❌ Error adoptando posiciones: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando adopción masiva de posiciones huérfanas...")
    
    await adopt_all_orphan_positions()
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())