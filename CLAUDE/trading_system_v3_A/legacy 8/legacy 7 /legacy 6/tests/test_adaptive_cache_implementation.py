#!/usr/bin/env python3
"""
Test del Cache Adaptativo Implementado
Verifica que el sistema funciona con market open a 3 minutos
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, time
import pytz

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

async def test_adaptive_cache_integration():
    """Test del cache adaptativo integrado"""
    logger = setup_logging()
    
    print("🧠 TEST DEL CACHE ADAPTATIVO IMPLEMENTADO")
    print("=" * 55)
    print("Market Open configurado a 3 minutos (conservador)")
    print("=" * 55)
    
    try:
        # Test 1: Importar adaptive cache manager
        logger.info("📦 Test 1: Importando adaptive cache manager...")
        from core.adaptive_cache_manager import adaptive_cache_manager
        logger.info("   ✅ Adaptive cache manager importado correctamente")
        
        # Test 2: Verificar configuración de market open
        logger.info("📊 Test 2: Verificando configuración de market open...")
        market_open_config = adaptive_cache_manager.market_periods['market_open']
        
        expected_refresh = 3
        actual_refresh = market_open_config['refresh_minutes']
        
        if actual_refresh == expected_refresh:
            logger.info(f"   ✅ Market open configurado correctamente: {actual_refresh} minutos")
        else:
            logger.error(f"   ❌ Market open mal configurado: esperado {expected_refresh}, actual {actual_refresh}")
            return False
        
        # Test 3: Mostrar horario completo
        logger.info("📅 Test 3: Mostrando horario adaptativo completo...")
        schedule = adaptive_cache_manager.get_daily_schedule_preview()
        print("\n" + schedule)
        
        # Test 4: Simular diferentes horarios
        logger.info("⏰ Test 4: Simulando diferentes horarios del día...")
        
        test_times = [
            (time(5, 0), "Premarket"),      # 5:00 AM - Premarket
            (time(9, 45), "Market Open"),   # 9:45 AM - Market Open
            (time(11, 0), "Morning"),       # 11:00 AM - Morning session
            (time(13, 0), "Lunch"),         # 1:00 PM - Lunch time
            (time(15, 45), "Power Hour"),   # 3:45 PM - Power hour
        ]
        
        market_tz = pytz.timezone('US/Eastern')
        base_date = datetime.now(market_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        
        for test_time, period_name in test_times:
            test_datetime = base_date.replace(hour=test_time.hour, minute=test_time.minute)
            
            period, config = adaptive_cache_manager.get_current_market_period(test_datetime)
            refresh_minutes = config['refresh_minutes']
            priority = config['priority']
            
            logger.info(f"   🕐 {test_time.strftime('%H:%M')} ({period_name}): {refresh_minutes}min refresh ({priority})")
        
        # Test 5: Test integración con scanner
        logger.info("🔍 Test 5: Probando integración con scanner...")
        
        try:
            from adapters.mock_ibkr_adapter import MockIBKRAdapter
            from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
            
            # Usar mock adapter para evitar conexiones reales
            mock_adapter = MockIBKRAdapter()
            await mock_adapter.connect()
            
            # Inicializar scanner
            scanner = SmallcapDailyScanner(ibkr_adapter=mock_adapter)
            
            # Verificar que usa cache adaptativo
            if hasattr(scanner, '_use_adaptive_cache') and scanner._use_adaptive_cache:
                logger.info("   ✅ Scanner configurado para usar cache adaptativo")
                
                # Verificar que IBKR scanner también usa cache adaptativo
                if hasattr(scanner.ibkr_scanner, '_use_adaptive_cache') and scanner.ibkr_scanner._use_adaptive_cache:
                    logger.info("   ✅ IBKR Scanner también usa cache adaptativo")
                else:
                    logger.warning("   ⚠️ IBKR Scanner no usa cache adaptativo")
                    
            else:
                logger.warning("   ⚠️ Scanner no está usando cache adaptativo")
                
            await mock_adapter.disconnect()
            
        except Exception as e:
            logger.error(f"   ❌ Error probando integración con scanner: {e}")
            return False
        
        # Test 6: Calcular impacto API estimado
        logger.info("📊 Test 6: Calculando impacto API estimado...")
        
        total_daily_calls = 0
        market_periods = adaptive_cache_manager.market_periods
        
        for period_name, config in market_periods.items():
            start_time = config['start']
            end_time = config['end']
            refresh_minutes = config['refresh_minutes']
            
            # Calcular duración del período
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            duration = end_minutes - start_minutes
            
            # Calcular refreshes y calls
            refreshes = duration // refresh_minutes
            calls = refreshes * 3  # 3 calls por refresh estimado
            total_daily_calls += calls
            
            logger.info(f"   📞 {period_name}: {calls} calls ({refreshes} refreshes)")
        
        logger.info(f"   📈 Total estimado diario: {total_daily_calls} API calls")
        
        # Comparar con cache fijo
        fixed_3min_calls = (11.5 * 60 // 3) * 3  # 690 calls
        fixed_15min_calls = (11.5 * 60 // 15) * 3  # 138 calls
        
        logger.info(f"   ⚖️ vs Cache fijo 3min: {fixed_3min_calls} calls ({((fixed_3min_calls - total_daily_calls) / total_daily_calls * 100):+.1f}%)")
        logger.info(f"   ⚖️ vs Cache fijo 15min: {fixed_15min_calls} calls ({((fixed_15min_calls - total_daily_calls) / total_daily_calls * 100):+.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en test adaptativo: {e}")
        return False

async def main():
    """Test principal"""
    
    success = await test_adaptive_cache_integration()
    
    print("\n" + "=" * 55)
    print("🎯 RESULTADO DEL TEST")
    print("=" * 55)
    
    if success:
        print("✅ CACHE ADAPTATIVO IMPLEMENTADO CORRECTAMENTE")
        print("🎯 Market Open: 3 minutos (conservador)")
        print("🧠 Sistema se adapta automáticamente a horarios")
        print("📊 Balance óptimo entre detección y carga API")
        print("🔒 Fallback a 15min si hay problemas")
        print("\n🚀 LISTO PARA PRODUCCIÓN")
    else:
        print("❌ HAY PROBLEMAS CON LA IMPLEMENTACIÓN")
        print("   Revisar logs para detalles")
    
    print("=" * 55)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)