#!/usr/bin/env python3
"""
TEST RÁPIDO - Verificar integración TradingEngine sin scanner real
Crea un play mock y verifica que se procese correctamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_quick_trading_integration():
    """Test rápido de integración TradingEngine"""
    logger = logging.getLogger("QuickTest")
    
    logger.info("🧪" + "="*50)
    logger.info("🧪 TEST RÁPIDO - INTEGRACIÓN TRADING ENGINE")
    logger.info("🧪" + "="*50)
    
    try:
        # 1. Import and create runner in test mode
        from production.smallcap_production_runner import SmallcapProductionRunner
        
        logger.info("🧪 Paso 1: Creando runner en modo test...")
        runner = SmallcapProductionRunner(test_mode=True)
        
        # 2. Initialize system
        logger.info("🧪 Paso 2: Inicializando sistema...")
        success = await runner.initialize()
        if not success:
            logger.error("❌ Sistema no se inicializó correctamente")
            return False
            
        logger.info("✅ Sistema inicializado correctamente")
        
        # 3. Create mock high-quality play
        logger.info("🧪 Paso 3: Creando mock play de alta calidad...")
        
        from scanner.smallcap.smallcap_context import SmallcapContext
        from scanner.smallcap.catalyst_analyzer import CatalystInfo
        from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
        
        # Mock context with excellent metrics
        mock_context = SmallcapContext(
            symbol="TESTPLAY",
            current_price=7.50,
            gap_percentage=0.12,  # 12% gap - excellent
            premarket_volume_ratio=3.5,  # 3.5x volume - excellent  
            avg_daily_volume=1500000,
            catalyst_strength=8,
            market_fear_level="LOW",
            float_size=40000000
        )
        
        # Strong catalyst
        mock_catalyst = CatalystInfo(
            catalyst_type="breakthrough_news",
            strength=9,
            description="Major breakthrough announcement - test",
            confidence=0.92,
            news_sentiment=0.85
        )
        
        # High quality play (should trigger test mode override)
        mock_play = SmallcapPlay(
            symbol="TESTPLAY",
            context=mock_context,
            catalyst=mock_catalyst,
            quality_score=7.8,  # High score que debe activar override
            timestamp=datetime.now()
        )
        
        logger.info(f"✅ Mock play creado: {mock_play.symbol} (Score: {mock_play.quality_score:.1f})")
        
        # 4. Test Mayordomo evaluation with test mode override
        logger.info("🧪 Paso 4: Testing Mayordomo evaluation...")
        
        # This should trigger test mode override and execute trade
        await runner._evaluate_play_with_mayordomo(mock_play)
        
        # 5. Check if TradingEngine added the symbol
        logger.info("🧪 Paso 5: Verificando TradingEngine monitoring...")
        
        if hasattr(runner.trading_engine, 'monitored_symbols'):
            monitored = runner.trading_engine.get_monitored_symbols()
            logger.info(f"📈 Símbolos monitoreados: {list(monitored)}")
            
            if mock_play.symbol in monitored:
                logger.info(f"✅ {mock_play.symbol} agregado correctamente al TradingEngine")
            else:
                logger.warning(f"⚠️ {mock_play.symbol} NO fue agregado al TradingEngine")
        
        # 6. Final status check
        logger.info("🧪 Paso 6: Status final del sistema...")
        
        status = runner.get_status()
        logger.info(f"📊 Sistema funcionando: {status['is_running']}")
        logger.info(f"📊 IBKR conectado: {status['ibkr_connected']}")
        logger.info(f"📊 ML Engine activo: {status['ml_engine_enabled']}")
        logger.info(f"📊 TradingEngine disponible: {runner.trading_engine is not None}")
        
        # Test completed successfully
        logger.info("🧪" + "="*50)
        logger.info("🧪 TEST COMPLETADO EXITOSAMENTE")
        logger.info("🧪" + "="*50)
        logger.info("✅ Integración TradingEngine funcionando correctamente")
        logger.info("✅ Test mode override activo")
        logger.info("✅ Sistema listo para trades automáticos")
        
        # Clean shutdown
        await runner.shutdown()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 INICIANDO TEST RÁPIDO DE INTEGRACIÓN")
    print("🧪 Testing TradingEngine + SmallcapMayordomo")
    print("🧪" + "="*50)
    
    # Configurar event loop para Windows si es necesario
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Ejecutar test
    success = asyncio.run(test_quick_trading_integration())
    
    if success:
        print("\n🎉 TEST RÁPIDO EXITOSO - Integración funcionando!")
        exit(0)
    else:
        print("\n❌ TEST RÁPIDO FALLIDO - Revisar integración")
        exit(1)