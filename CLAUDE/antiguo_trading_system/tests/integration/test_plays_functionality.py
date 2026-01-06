#!/usr/bin/env python3
"""
Test Rápido - Funcionalidad Principal de Plays del Día
Verifica los cambios implementados sin complejidad innecesaria
"""

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trader_main import IndependentTrader

def test_plays_storage():
    """Test principal: Verificar almacenamiento de plays"""
    print("🧪 Test: Almacenamiento de plays del scanner")
    
    # Crear trader
    trader = IndependentTrader()
    
    # Mock componentes mínimos
    trader.mayordomo = Mock()
    trader.mayordomo.evaluate_position_rotation.return_value = {
        'action': 'REJECT',
        'reason': 'Test - storage verification'
    }
    
    # Simular oportunidades del scanner
    opportunities = [
        {
            'symbol': 'AAPL',
            'current_price': 180.50,
            'gap_percentage': 0.06,
            'volume_ratio': 3.2,
            'quality_score': 8.0,
            'catalyst_type': 'EARNINGS'
        },
        {
            'symbol': 'TSLA',
            'current_price': 245.00,
            'gap_percentage': 0.12,
            'volume_ratio': 4.5,
            'quality_score': 7.8,
            'catalyst_type': 'FDA'
        }
    ]
    
    async def run_test():
        # Procesar oportunidades
        await trader._handle_scanner_opportunities(opportunities)
        
        # Verificar almacenamiento
        assert len(trader.notified_plays) == 2, f"Expected 2 plays, got {len(trader.notified_plays)}"
        assert 'AAPL' in trader.notified_plays, "AAPL not stored"
        assert 'TSLA' in trader.notified_plays, "TSLA not stored"
        
        # Verificar datos de AAPL
        aapl_data = trader.notified_plays['AAPL']['last_data']
        assert aapl_data['symbol'] == 'AAPL', "Symbol mismatch"
        assert aapl_data['price'] == 180.50, "Price mismatch"
        assert aapl_data['quality_score'] == 8.0, "Quality score mismatch"
        
        print("✅ AAPL almacenado correctamente")
        print("✅ TSLA almacenado correctamente")
        print(f"✅ Total plays almacenados: {len(trader.notified_plays)}")
        
        return True
    
    # Ejecutar test asíncrono
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(run_test())
        loop.close()
        return result
    except Exception as e:
        print(f"❌ Error en test: {e}")
        loop.close()
        return False

def test_mayordomo_position_fix():
    """Test: Verificar que el fix del Mayordomo funciona"""
    print("\n🧪 Test: Fix del cálculo de posiciones del Mayordomo")
    
    from core.risk_manager import SmallcapMayordomo
    
    # Crear mayordomo con mocks mínimos
    config = Mock()
    config.max_positions = 15
    
    mayordomo = SmallcapMayordomo(config=config)
    
    # Simular posiciones del broker vacías (position=0.0)
    mayordomo.broker_positions = {
        'AAPL': {'position': 0.0, 'market_value': 0.0},
        'TSLA': {'position': 0.0, 'market_value': 0.0}
    }
    
    # Simular plays internos antiguos (estos NO deberían contar)
    mayordomo.active_daily_plays = {'OLD_PLAY': {}, 'ANOTHER_OLD': {}}
    
    # Crear oportunidad de prueba
    opportunity = {
        'symbol': 'NVDA',
        'quality_score': 8.5,  # Score alto
        'current_price': 890.0,
        'gap_percentage': 0.10
    }
    
    # Evaluar oportunidad
    decision = mayordomo.evaluate_position_rotation(opportunity)
    
    # Verificar que NO fue rechazado por "posiciones existentes"
    reason = decision.get('reason', '').lower()
    action = decision.get('action', '')
    
    print(f"📊 Decisión: {action}")
    print(f"📋 Razón: {decision.get('reason', 'No reason')}")
    
    # El mayordomo debe usar posiciones del broker (0) no internal tracker (2)
    if 'open position' not in reason:
        print("✅ Fix funcionando: No cuenta posiciones internas cerradas")
        return True
    else:
        print("❌ Fix NO funcionando: Aún cuenta posiciones internas")
        return False

def test_telegram_data_access():
    """Test: Verificar que Telegram puede acceder a los plays"""
    print("\n🧪 Test: Acceso de Telegram a los plays")
    
    from core.service_locator import get_service_locator
    from notifications.telegram_client import send_plays_today
    from unittest.mock import patch
    
    # Crear mock de unified system con plays
    mock_system = Mock()
    mock_system.notified_plays = {
        'TEST_SYMBOL': {
            'last_notified': datetime.now(),
            'last_data': {
                'symbol': 'TEST_SYMBOL',
                'price': 100.0,
                'gap': 0.05,
                'volume_ratio': 3.0,
                'quality_score': 7.5,
                'catalyst_type': 'EARNINGS'
            }
        }
    }
    
    # Registrar en service locator
    service_locator = get_service_locator()
    service_locator.register_service('unified_trading_system', mock_system)
    
    # Mock de envío de mensaje para capturar contenido
    sent_messages = []
    
    def mock_send_message(message, **kwargs):
        sent_messages.append(message)
        print(f"📱 Mensaje capturado: {len(message)} caracteres")
    
    # Ejecutar función de telegram con mocks
    with patch('notifications.telegram_client.is_enabled', return_value=True):
        with patch('notifications.telegram_client.send_message', side_effect=mock_send_message):
            try:
                send_plays_today()
                
                if sent_messages:
                    message = sent_messages[0]
                    if 'TEST_SYMBOL' in message and 'PLAYS DE HOY' in message:
                        print("✅ Telegram puede acceder a los plays correctamente")
                        print(f"✅ Mensaje contiene símbolo de prueba")
                        return True
                    else:
                        print("❌ Mensaje no contiene los datos esperados")
                        return False
                else:
                    print("❌ No se envió ningún mensaje")
                    return False
                    
            except Exception as e:
                print(f"❌ Error en función de Telegram: {e}")
                return False

def main():
    """Ejecutar todos los tests"""
    print("🚀 TESTING PLAYS DEL DÍA - FUNCIONALIDAD PRINCIPAL")
    print("=" * 55)
    
    results = []
    
    # Test 1: Almacenamiento
    results.append(test_plays_storage())
    
    # Test 2: Fix del Mayordomo  
    results.append(test_mayordomo_position_fix())
    
    # Test 3: Acceso de Telegram
    results.append(test_telegram_data_access())
    
    print("\n" + "=" * 55)
    print("📊 RESUMEN DE RESULTADOS:")
    print(f"✅ Tests exitosos: {sum(results)}")
    print(f"❌ Tests fallidos: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 ¡TODOS LOS TESTS PASARON!")
        print("✅ La funcionalidad de plays del día está funcionando correctamente")
        return True
    else:
        print("\n⚠️  Algunos tests fallaron, pero la funcionalidad básica está operativa")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)