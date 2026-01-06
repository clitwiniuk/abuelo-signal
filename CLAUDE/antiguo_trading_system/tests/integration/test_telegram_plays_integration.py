#!/usr/bin/env python3
"""
Test de Integración - Telegram y Plays del Día
Simula el flujo completo desde scanner hasta Telegram
"""

import asyncio
import sys
import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from trader_main import IndependentTrader
from core.service_locator import get_service_locator

class TestTelegramPlaysIntegration(unittest.TestCase):
    """Test completo del flujo Scanner -> Trader -> Telegram"""
    
    def setUp(self):
        """Setup antes de cada test"""
        self.trader = None
        
    async def async_setUp(self):
        """Setup asíncrono"""
        # Crear trader instance
        self.trader = IndependentTrader()
        
        # Mock de componentes para testing
        self.mock_telegram_client = Mock()
        self.mock_telegram_client.send_message = Mock()
        self.mock_telegram_client.is_enabled = Mock(return_value=True)
        
        # Mock mayordomo
        self.mock_mayordomo = Mock()
        
        # Mock broker positions (posiciones vacías)
        self.mock_risk_manager = Mock()
        self.mock_risk_manager.broker_positions = {}
        
        # Inyectar mocks
        self.trader.telegram_client = self.mock_telegram_client
        self.trader.mayordomo = self.mock_mayordomo
        self.trader.risk_manager = self.mock_risk_manager
        
        print("✅ Test setup completado")
        
    def test_1_notified_plays_storage(self):
        """Test 1: Verificar que se almacenan los plays recibidos"""
        print("\n🧪 Test 1: Almacenamiento de plays")
        
        # Simular oportunidades del scanner
        mock_opportunities = [
            {
                'symbol': 'TSLA',
                'current_price': 245.50,
                'gap_percentage': 0.08,  # 8% gap
                'volume_ratio': 4.2,
                'quality_score': 8.5,
                'catalyst_type': 'EARNINGS'
            },
            {
                'symbol': 'NVDA', 
                'current_price': 890.20,
                'gap_percentage': -0.05,  # -5% gap
                'volume_ratio': 3.8,
                'quality_score': 7.2,
                'catalyst_type': 'FDA'
            }
        ]
        
        # Ejecutar handler de oportunidades
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._async_test_storage(mock_opportunities))
        finally:
            loop.close()
            
    async def _async_test_storage(self, opportunities):
        """Parte asíncrona del test de almacenamiento"""
        await self.async_setUp()
        
        # Configurar mayordomo para rechazar todo (para testing de storage)
        self.mock_mayordomo.evaluate_position_rotation.return_value = {
            'action': 'REJECT',
            'reason': 'Test rejection - storage test'
        }
        
        # Procesar oportunidades
        await self.trader._handle_scanner_opportunities(opportunities)
        
        # Verificar que se almacenaron los plays
        self.assertEqual(len(self.trader.notified_plays), 2)
        self.assertIn('TSLA', self.trader.notified_plays)
        self.assertIn('NVDA', self.trader.notified_plays)
        
        # Verificar datos de TSLA
        tsla_data = self.trader.notified_plays['TSLA']['last_data']
        self.assertEqual(tsla_data['symbol'], 'TSLA')
        self.assertEqual(tsla_data['price'], 245.50)
        self.assertEqual(tsla_data['quality_score'], 8.5)
        
        print("✅ Plays almacenados correctamente en notified_plays")
        
    def test_2_telegram_integration_mock(self):
        """Test 2: Verificar integración con Telegram (mock)"""
        print("\n🧪 Test 2: Integración Telegram con datos simulados")
        
        # Setup de datos simulados
        service_locator = get_service_locator()
        
        # Crear mock de unified_trading_system con plays
        mock_unified_system = Mock()
        mock_unified_system.notified_plays = {
            'AAPL': {
                'last_notified': datetime.now(),
                'last_data': {
                    'symbol': 'AAPL',
                    'price': 180.50,
                    'gap': 0.06,
                    'volume_ratio': 3.2,
                    'quality_score': 8.0,
                    'catalyst_type': 'EARNINGS'
                }
            },
            'GOOGL': {
                'last_notified': datetime.now(), 
                'last_data': {
                    'symbol': 'GOOGL',
                    'price': 2650.00,
                    'gap': -0.03,
                    'volume_ratio': 2.8,
                    'quality_score': 7.5,
                    'catalyst_type': 'M&A'
                }
            }
        }
        
        # Registrar en service locator
        service_locator.register_service('unified_trading_system', mock_unified_system)
        
        # Importar y testear funciones de telegram
        try:
            from notifications.telegram_client import send_plays_today, is_enabled
            
            # Mock de is_enabled para evitar verificar configuración real
            with patch('notifications.telegram_client.is_enabled', return_value=True):
                with patch('notifications.telegram_client.send_message') as mock_send:
                    # Ejecutar función
                    send_plays_today()
                    
                    # Verificar que se llamó send_message
                    self.assertTrue(mock_send.called)
                    
                    # Verificar contenido del mensaje
                    call_args = mock_send.call_args
                    message_content = call_args[0][0]  # Primer argumento
                    
                    self.assertIn('PLAYS DE HOY', message_content)
                    self.assertIn('AAPL', message_content)
                    self.assertIn('GOOGL', message_content)
                    self.assertIn('Total plays detectados: 2', message_content)
                    
                    print("✅ Función send_plays_today ejecutada correctamente")
                    print(f"📱 Mensaje generado: {len(message_content)} caracteres")
                    
        except Exception as e:
            print(f"❌ Error en test Telegram: {e}")
            raise
            
    def test_3_mayordomo_position_calculation(self):
        """Test 3: Verificar que Mayordomo cuenta posiciones correctamente"""
        print("\n🧪 Test 3: Cálculo de posiciones del Mayordomo")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._async_test_mayordomo())
        finally:
            loop.close()
            
    async def _async_test_mayordomo(self):
        """Parte asíncrona del test de Mayordomo"""
        await self.async_setUp()
        
        # Test con portfolio vacío
        self.mock_risk_manager.broker_positions = {}
        
        # Crear opportunity con score alto
        opportunity = {
            'symbol': 'TEST',
            'quality_score': 8.0,
            'current_price': 100.0,
            'gap_percentage': 0.10
        }
        
        # Mock de mayordomo real para este test
        from core.risk_manager import SmallcapMayordomo
        
        # Crear instancia real de mayordomo
        real_mayordomo = SmallcapMayordomo(
            config=Mock(),
            broker=Mock(),
            logger=logging.getLogger("TestMayordomo")
        )
        
        # Simular broker positions vacío
        real_mayordomo.broker_positions = {}
        real_mayordomo.active_daily_plays = {'FAKE_OLD_PLAY': {}}  # Esto NO debería contar
        
        # Evaluar oportunidad
        decision = real_mayordomo.evaluate_position_rotation(opportunity)
        
        # Verificar que NO fue rechazado por "posiciones existentes"
        reason = decision.get('reason', '')
        self.assertNotIn('open position', reason.lower())
        
        print(f"✅ Decisión Mayordomo: {decision['action']} - {decision.get('reason', 'No reason')}")
        
    def test_4_integration_flow(self):
        """Test 4: Flujo completo de integración"""
        print("\n🧪 Test 4: Flujo completo Scanner -> Trader -> Telegram")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._async_test_integration())
        finally:
            loop.close()
            
    async def _async_test_integration(self):
        """Test completo de flujo"""
        await self.async_setUp()
        
        # 1. Simular oportunidad que SÍ debería pasar
        good_opportunity = {
            'symbol': 'WINNER',
            'current_price': 50.0,
            'gap_percentage': 0.15,  # 15% gap
            'volume_ratio': 5.0,     # 5x volume
            'quality_score': 9.0,    # Score alto
            'catalyst_type': 'FDA'
        }
        
        # 2. Configurar mayordomo para ACEPTAR
        self.mock_mayordomo.evaluate_position_rotation.return_value = {
            'action': 'EXECUTE', 
            'reason': 'Good opportunity - test acceptance',
            'confidence': 0.90
        }
        
        # 3. Mock trading engine
        mock_trading_engine = Mock()
        mock_trading_engine.add_symbol = Mock(return_value=True)
        self.trader.trading_engine = mock_trading_engine
        
        # 4. Procesar oportunidad
        await self.trader._handle_scanner_opportunities([good_opportunity])
        
        # 5. Verificar almacenamiento
        self.assertIn('WINNER', self.trader.notified_plays)
        
        # 6. Verificar que se intentó agregar al trading engine
        mock_trading_engine.add_symbol.assert_called_once_with('WINNER', skip_validation=True)
        
        # 7. Verificar que se envió notificación Telegram
        self.mock_telegram_client.send_message.assert_called_once()
        
        # 8. Verificar contenido de la notificación
        call_args = self.mock_telegram_client.send_message.call_args
        notification = call_args[0][0]  # Primer argumento
        
        self.assertIn('NEW OPPORTUNITY ADDED', notification)
        self.assertIn('WINNER', notification)
        self.assertIn('Quality Score: 9.0', notification)
        
        print("✅ Flujo completo ejecutado correctamente")
        print(f"📱 Notificación enviada: {notification}")


def run_tests():
    """Ejecutar todos los tests"""
    print("🚀 INICIANDO TESTS DE INTEGRACIÓN TELEGRAM + PLAYS DEL DÍA")
    print("=" * 60)
    
    # Configurar logging para tests
    logging.basicConfig(level=logging.WARNING)
    
    # Crear suite de tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTelegramPlaysIntegration)
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 ¡TODOS LOS TESTS PASARON EXITOSAMENTE!")
        print("✅ El sistema de Telegram y plays del día está funcionando correctamente")
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        print(f"Errores: {len(result.errors)}")
        print(f"Fallas: {len(result.failures)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)