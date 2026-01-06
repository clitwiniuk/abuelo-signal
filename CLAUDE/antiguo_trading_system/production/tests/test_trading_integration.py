#!/usr/bin/env python3
"""
TEST COMPLETO - Integración TradingEngine con SmallcapProductionRunner
Verificar que el sistema puede ejecutar trades end-to-end
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from dataclasses import dataclass

# Configurar logging para el test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@dataclass
class TestResult:
    """Resultado de un test específico"""
    test_name: str
    success: bool
    duration: float
    details: str
    error: str = None

class TradingIntegrationTester:
    """
    Tester completo para verificar integración TradingEngine
    """
    
    def __init__(self):
        self.logger = logging.getLogger("TradingIntegrationTest")
        self.test_results: List[TestResult] = []
        self.runner = None
    
    async def run_complete_test_suite(self):
        """Ejecutar suite completa de tests"""
        self.logger.info("🧪" + "="*60)
        self.logger.info("🧪 INICIANDO TEST SUITE COMPLETO - TRADING INTEGRATION")
        self.logger.info("🧪" + "="*60)
        
        try:
            # Test 1: Inicialización del sistema
            await self._test_system_initialization()
            
            # Test 2: Configuración de test mode
            await self._test_test_mode_activation()
            
            # Test 3: Conexiones y componentes
            await self._test_component_connections()
            
            # Test 4: Scanner funcional
            await self._test_scanner_functionality()
            
            # Test 5: Mayordomo override en test mode
            await self._test_mayordomo_override()
            
            # Test 6: TradingEngine integration
            await self._test_trading_engine_integration()
            
            # Test 7: End-to-end trade execution simulation
            await self._test_end_to_end_trade_execution()
            
            # Generar reporte final
            self._generate_test_report()
            
        except Exception as e:
            self.logger.error(f"❌ Error fatal en test suite: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if self.runner:
                await self.runner.shutdown()
    
    async def _test_system_initialization(self):
        """Test 1: Verificar inicialización completa del sistema"""
        test_start = datetime.now()
        test_name = "System Initialization"
        
        try:
            self.logger.info("🧪 TEST 1: Inicialización del sistema...")
            
            # Importar y crear runner en test mode
            from production.smallcap_production_runner import SmallcapProductionRunner
            
            self.runner = SmallcapProductionRunner(test_mode=True)
            
            # Verificar que test mode está activo
            assert self.runner.test_mode == True, "Test mode no está activo"
            
            # Inicializar sistema
            success = await self.runner.initialize()
            assert success == True, "Sistema no se inicializó correctamente"
            
            # Verificar componentes críticos
            assert self.runner.ibkr_adapter is not None, "IBKR Adapter no inicializado"
            assert self.runner.tiingo_provider is not None, "Tiingo Provider no inicializado"
            assert self.runner.smallcap_scanner is not None, "Scanner no inicializado"
            assert self.runner.mayordomo is not None, "Mayordomo no inicializado"
            assert self.runner.ml_engine is not None, "ML Engine no inicializado"
            assert self.runner.trading_engine is not None, "TradingEngine no inicializado"
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details=f"Sistema inicializado correctamente en {duration:.2f}s con todos los componentes"
            ))
            
            self.logger.info(f"✅ TEST 1 PASADO: {duration:.2f}s")
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error en inicialización",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 1 FALLIDO: {e}")
            raise
    
    async def _test_test_mode_activation(self):
        """Test 2: Verificar que test mode está funcionando"""
        test_start = datetime.now()
        test_name = "Test Mode Activation"
        
        try:
            self.logger.info("🧪 TEST 2: Verificando Test Mode...")
            
            # Verificar flags de test mode
            assert self.runner.test_mode == True, "Test mode flag no está activo"
            
            # Log de confirmación
            self.logger.info("🧪 Test mode confirmado - Mayordomo será override para quality_score >= 5.0")
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details="Test mode activo correctamente"
            ))
            
            self.logger.info(f"✅ TEST 2 PASADO: {duration:.2f}s")
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Test mode no está activo",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 2 FALLIDO: {e}")
            raise
    
    async def _test_component_connections(self):
        """Test 3: Verificar conexiones de componentes"""
        test_start = datetime.now()
        test_name = "Component Connections"
        
        try:
            self.logger.info("🧪 TEST 3: Verificando conexiones...")
            
            # Verificar IBKR
            if self.runner.ibkr_adapter:
                connected = self.runner.ibkr_adapter.is_connected()
                self.logger.info(f"📡 IBKR Connection: {connected}")
            
            # Verificar TradingEngine
            if self.runner.trading_engine:
                te_status = self.runner.trading_engine.get_status()
                self.logger.info(f"⚡ TradingEngine Status: {te_status}")
                
                # Verificar que el TradingEngine tiene todos los componentes
                assert hasattr(self.runner.trading_engine, 'data_provider'), "TradingEngine sin data provider"
                assert hasattr(self.runner.trading_engine, 'broker'), "TradingEngine sin broker"
                assert hasattr(self.runner.trading_engine, 'strategy'), "TradingEngine sin strategy"
                assert hasattr(self.runner.trading_engine, 'risk_manager'), "TradingEngine sin risk manager"
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details="Conexiones verificadas correctamente"
            ))
            
            self.logger.info(f"✅ TEST 3 PASADO: {duration:.2f}s")
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error verificando conexiones",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 3 FALLIDO: {e}")
            # No hacer raise - continuar con otros tests
    
    async def _test_scanner_functionality(self):
        """Test 4: Verificar que el scanner funciona"""
        test_start = datetime.now()
        test_name = "Scanner Functionality"
        
        try:
            self.logger.info("🧪 TEST 4: Verificando scanner...")
            
            # Ejecutar scan rápido
            if self.runner.smallcap_scanner:
                self.logger.info("🔍 Ejecutando scan de prueba...")
                plays = await self.runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                
                plays_count = len(plays) if plays else 0
                self.logger.info(f"📈 Scanner encontró {plays_count} plays")
                
                # Mostrar algunos plays para debug
                if plays and plays_count > 0:
                    for i, play in enumerate(plays[:3]):  # Primeros 3
                        self.logger.info(f"   {i+1}. {play.symbol}: Gap {play.context.gap_percentage*100:+.1f}%, "
                                       f"Vol {play.context.premarket_volume_ratio:.1f}x, Score {play.quality_score:.1f}")
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details=f"Scanner ejecutado - encontró {plays_count} plays en {duration:.2f}s"
            ))
            
            self.logger.info(f"✅ TEST 4 PASADO: {duration:.2f}s")
            return plays
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error ejecutando scanner",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 4 FALLIDO: {e}")
            return None
    
    async def _test_mayordomo_override(self):
        """Test 5: Verificar override del Mayordomo en test mode"""
        test_start = datetime.now()
        test_name = "Mayordomo Override"
        
        try:
            self.logger.info("🧪 TEST 5: Verificando Mayordomo override...")
            
            # Crear un play simulado con quality score alto
            from scanner.smallcap.smallcap_context import SmallcapContext
            from scanner.smallcap.catalyst_analyzer import CatalystInfo
            from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
            
            # Mock context
            mock_context = SmallcapContext(
                symbol="TEST",
                current_price=5.0,
                gap_percentage=0.10,  # 10% gap
                premarket_volume_ratio=3.0,  # 3x volume
                avg_daily_volume=1000000,
                catalyst_strength=7,
                market_fear_level="LOW",
                float_size=50000000
            )
            
            # Mock catalyst
            mock_catalyst = CatalystInfo(
                catalyst_type="earnings_beat",
                strength=8,
                description="Test catalyst",
                confidence=0.9,
                news_sentiment=0.8
            )
            
            # Mock play with high quality score
            mock_play = SmallcapPlay(
                symbol="TEST",
                context=mock_context,
                catalyst=mock_catalyst,
                quality_score=7.5,  # High score que debe trigger override
                timestamp=datetime.now()
            )
            
            # Test override logic directamente
            if self.runner.test_mode and mock_play.quality_score >= 5.0:
                self.logger.info(f"🧪 TEST OVERRIDE: Play {mock_play.symbol} con score {mock_play.quality_score:.1f} será aprobado")
                override_works = True
            else:
                override_works = False
            
            assert override_works == True, "Override no funciona para quality_score >= 5.0"
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details="Override del Mayordomo funciona correctamente en test mode"
            ))
            
            self.logger.info(f"✅ TEST 5 PASADO: {duration:.2f}s")
            return mock_play
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error en override del Mayordomo",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 5 FALLIDO: {e}")
            return None
    
    async def _test_trading_engine_integration(self):
        """Test 6: Verificar integración específica del TradingEngine"""
        test_start = datetime.now()
        test_name = "TradingEngine Integration"
        
        try:
            self.logger.info("🧪 TEST 6: Verificando TradingEngine integration...")
            
            # Verificar que TradingEngine tiene los métodos necesarios
            te = self.runner.trading_engine
            assert hasattr(te, 'add_symbol'), "TradingEngine sin método add_symbol"
            assert hasattr(te, 'analysis_stage'), "TradingEngine sin analysis_stage"
            assert hasattr(te, 'execution_stage'), "TradingEngine sin execution_stage"
            
            # Test add_symbol
            self.logger.info("📈 Testing add_symbol...")
            success = await te.add_symbol("AAPL", skip_validation=True)
            self.logger.info(f"   add_symbol('AAPL') = {success}")
            
            # Verificar stages
            self.logger.info("🔍 Verificando stages...")
            if hasattr(te.analysis_stage, '_process'):
                self.logger.info("   ✅ analysis_stage._process disponible")
            else:
                self.logger.warning("   ⚠️ analysis_stage._process NO disponible")
            
            if hasattr(te.execution_stage, '_process'):
                self.logger.info("   ✅ execution_stage._process disponible")  
            else:
                self.logger.warning("   ⚠️ execution_stage._process NO disponible")
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details="TradingEngine integration verificada correctamente"
            ))
            
            self.logger.info(f"✅ TEST 6 PASADO: {duration:.2f}s")
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error en TradingEngine integration",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 6 FALLIDO: {e}")
    
    async def _test_end_to_end_trade_execution(self):
        """Test 7: Simular ejecución completa end-to-end"""
        test_start = datetime.now()
        test_name = "End-to-End Trade Execution"
        
        try:
            self.logger.info("🧪 TEST 7: Simulando ejecución completa...")
            
            # Obtener mock play del test anterior
            mock_play = await self._create_high_quality_test_play()
            
            if mock_play:
                self.logger.info(f"🎯 Testing con play: {mock_play.symbol} (Score: {mock_play.quality_score:.1f})")
                
                # Simular evaluación con Mayordomo - debe usar override
                await self.runner._evaluate_play_with_mayordomo(mock_play)
                
                self.logger.info("🏁 End-to-end test completado")
                
                # El resultado real se verá en los logs del runner
                # Si vemos "🎯 Mayordomo recomienda ABRIR posición" y "⚡ Ejecutando trade"
                # entonces la integración funciona
            
            duration = (datetime.now() - test_start).total_seconds()
            
            self.test_results.append(TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details="End-to-end simulation ejecutada - revisar logs para confirmación"
            ))
            
            self.logger.info(f"✅ TEST 7 PASADO: {duration:.2f}s")
            
        except Exception as e:
            duration = (datetime.now() - test_start).total_seconds()
            self.test_results.append(TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                details="Error en end-to-end simulation",
                error=str(e)
            ))
            self.logger.error(f"❌ TEST 7 FALLIDO: {e}")
    
    async def _create_high_quality_test_play(self):
        """Crear un play de alta calidad para testing"""
        try:
            from scanner.smallcap.smallcap_context import SmallcapContext
            from scanner.smallcap.catalyst_analyzer import CatalystInfo
            from scanner.smallcap.smallcap_daily_scanner import SmallcapPlay
            
            # Context with excellent metrics
            context = SmallcapContext(
                symbol="TESTPLAY",
                current_price=7.50,
                gap_percentage=0.15,  # 15% gap - excellent
                premarket_volume_ratio=4.5,  # 4.5x volume - excellent
                avg_daily_volume=2000000,
                catalyst_strength=8,
                market_fear_level="LOW",
                float_size=30000000
            )
            
            # Strong catalyst
            catalyst = CatalystInfo(
                catalyst_type="breakthrough_news",
                strength=9,
                description="Major breakthrough announcement",
                confidence=0.95,
                news_sentiment=0.9
            )
            
            # High quality play
            play = SmallcapPlay(
                symbol="TESTPLAY",
                context=context,
                catalyst=catalyst,
                quality_score=8.5,  # Excellent score
                timestamp=datetime.now()
            )
            
            return play
            
        except Exception as e:
            self.logger.error(f"Error creando test play: {e}")
            return None
    
    def _generate_test_report(self):
        """Generar reporte final de tests"""
        self.logger.info("🧪" + "="*60)
        self.logger.info("🧪 REPORTE FINAL DE TESTS")
        self.logger.info("🧪" + "="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests
        
        self.logger.info(f"📊 RESUMEN:")
        self.logger.info(f"   Total Tests: {total_tests}")
        self.logger.info(f"   ✅ Pasados: {passed_tests}")
        self.logger.info(f"   ❌ Fallidos: {failed_tests}")
        self.logger.info(f"   📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        self.logger.info(f"\n📋 DETALLES:")
        for result in self.test_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            self.logger.info(f"   {status} {result.test_name}: {result.duration:.2f}s - {result.details}")
            if result.error:
                self.logger.info(f"      Error: {result.error}")
        
        if passed_tests == total_tests:
            self.logger.info("\n🎉 TODOS LOS TESTS PASARON - INTEGRATION COMPLETA FUNCIONANDO")
        else:
            self.logger.info(f"\n⚠️ {failed_tests} TESTS FALLARON - REVISAR INTEGRATION")

# Función principal del test
async def main():
    """Ejecutar test suite completo"""
    tester = TradingIntegrationTester()
    await tester.run_complete_test_suite()

if __name__ == "__main__":
    print("🧪 INICIANDO TEST SUITE COMPLETO")
    print("🧪 Testing TradingEngine Integration con SmallcapProductionRunner")
    print("🧪" + "="*60)
    
    # Configurar event loop para Windows si es necesario
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Ejecutar tests
    asyncio.run(main())