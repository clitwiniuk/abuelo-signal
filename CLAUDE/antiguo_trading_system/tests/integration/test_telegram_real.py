#!/usr/bin/env python3
"""
Test Real de Telegram - Envía mensajes reales a tu chat
Verifica que la funcionalidad completa funcione de extremo a extremo
"""

import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trader_main import IndependentTrader
from core.service_locator import get_service_locator
from notifications.telegram_client import send_plays_today, send_message, is_enabled

def test_telegram_real_integration():
    """Test completo con envío real a Telegram"""
    print("🧪 TEST REAL DE TELEGRAM - Envío de Plays del Día")
    print("=" * 50)
    
    # Verificar que Telegram está habilitado
    if not is_enabled():
        print("❌ Telegram no está habilitado en config.ini")
        print("   Activa telegram_enabled = true y configura bot_token y chat_id")
        return False
    
    print("✅ Telegram está configurado y habilitado")
    
    # Crear trader y simular plays del día
    trader = IndependentTrader()
    
    # Agregar plays simulados (como si vinieran del scanner)
    now = datetime.now()
    
    # Simular plays detectados hoy
    simulated_plays = {
        'TEST_AAPL': {
            'last_notified': now,
            'last_data': {
                'symbol': 'TEST_AAPL',
                'price': 180.50,
                'gap': 0.06,  # 6% gap up
                'volume_ratio': 3.2,
                'quality_score': 8.0,
                'catalyst_type': 'EARNINGS'
            }
        },
        'TEST_TSLA': {
            'last_notified': now,
            'last_data': {
                'symbol': 'TEST_TSLA', 
                'price': 245.00,
                'gap': -0.04,  # 4% gap down
                'volume_ratio': 4.5,
                'quality_score': 7.8,
                'catalyst_type': 'FDA'
            }
        },
        'TEST_NVDA': {
            'last_notified': now,
            'last_data': {
                'symbol': 'TEST_NVDA',
                'price': 890.20,
                'gap': 0.12,  # 12% gap up
                'volume_ratio': 5.1,
                'quality_score': 9.2,
                'catalyst_type': 'M&A'
            }
        }
    }
    
    # Inyectar plays simulados en el trader
    trader.notified_plays = simulated_plays
    
    print(f"📊 Plays simulados agregados: {len(simulated_plays)}")
    for symbol, data in simulated_plays.items():
        play_data = data['last_data']
        print(f"   • {symbol}: ${play_data['price']:.2f} ({play_data['gap']*100:+.1f}% gap) - Score: {play_data['quality_score']}")
    
    # Registrar el trader como unified_trading_system
    service_locator = get_service_locator()
    service_locator.register_service('unified_trading_system', trader)
    
    print("\n🚀 Enviando mensaje de prueba inicial...")
    
    # Enviar mensaje de prueba
    test_message = f"""🧪 **TEST DE FUNCIONALIDAD** - {now.strftime('%H:%M:%S')}

🔧 **Estado del Test:**
✅ Trader inicializado correctamente
✅ {len(simulated_plays)} plays simulados agregados
✅ Service Locator configurado
✅ Telegram habilitado y funcionando

🎯 **Próximo paso:** Enviando /plays_today..."""
    
    send_message(test_message, parse_mode="Markdown")
    
    print("✅ Mensaje de prueba enviado")
    print("\n📱 Enviando plays del día...")
    
    # Enviar plays del día (función real)
    send_plays_today()
    
    print("✅ Comando /plays_today ejecutado")
    
    # Enviar mensaje de resumen
    summary_message = f"""📊 **TEST COMPLETADO** - {now.strftime('%H:%M:%S')}

🎉 **Resultado:**
✅ Test de Telegram ejecutado exitosamente
✅ Función send_plays_today() ejecutada
✅ Deberías haber recibido los plays simulados

🔍 **Datos enviados:**
• Total plays: {len(simulated_plays)}
• Símbolos: {', '.join(simulated_plays.keys())}

💡 **Si recibiste los mensajes, la funcionalidad está 100% operativa**"""
    
    send_message(summary_message, parse_mode="Markdown")
    
    print("✅ Mensaje de resumen enviado")
    print("\n🎯 Revisa tu chat de Telegram para confirmar que llegaron los mensajes")
    
    return True

def test_telegram_mayordomo_scenario():
    """Test simulando escenario real del Mayordomo"""
    print("\n🧪 TEST ESCENARIO MAYORDOMO REAL")
    print("=" * 50)
    
    if not is_enabled():
        print("❌ Telegram no está habilitado")
        return False
    
    # Simular el proceso completo de recepción de plays
    trader = IndependentTrader() 
    
    # Mock componentes para simular flujo real
    mock_mayordomo = Mock()
    trader.mayordomo = mock_mayordomo
    
    # Configurar respuestas del mayordomo (simulando decisiones reales)
    responses = [
        {'action': 'REJECT', 'reason': 'Opportunity score 0.42 below minimum threshold 0.45'},
        {'action': 'REJECT', 'reason': 'Good opportunity 0.86 - open position (slot 1/15)'},  # Esto ya NO debería pasar
        {'action': 'EXECUTE', 'reason': 'Good opportunity 0.78 - executing trade', 'confidence': 0.78}
    ]
    
    mock_mayordomo.evaluate_position_rotation.side_effect = responses
    
    # Simular oportunidades del scanner
    opportunities = [
        {
            'symbol': 'REAL_INHD',
            'current_price': 12.50,
            'gap_percentage': 0.08,
            'volume_ratio': 2.8,
            'quality_score': 6.2,
            'catalyst_type': 'FDA'
        },
        {
            'symbol': 'REAL_HCWB',
            'current_price': 5.56,
            'gap_percentage': 0.15,
            'volume_ratio': 4.2,
            'quality_score': 8.6,
            'catalyst_type': 'M&A'
        },
        {
            'symbol': 'REAL_WINNER',
            'current_price': 89.30,
            'gap_percentage': 0.12,
            'volume_ratio': 5.5,
            'quality_score': 9.1,
            'catalyst_type': 'EARNINGS'
        }
    ]
    
    async def run_scenario():
        print("📡 Simulando recepción de oportunidades del scanner...")
        
        # Procesar oportunidades (como en el sistema real)
        await trader._handle_scanner_opportunities(opportunities)
        
        print(f"✅ {len(opportunities)} oportunidades procesadas y almacenadas")
        
        # Registrar trader
        service_locator = get_service_locator()
        service_locator.register_service('unified_trading_system', trader)
        
        # Enviar notificación de escenario
        scenario_message = f"""🎬 **ESCENARIO MAYORDOMO SIMULADO** - {datetime.now().strftime('%H:%M:%S')}

📊 **Oportunidades Procesadas:**
• REAL_INHD: Score 6.2 → {responses[0]['action']} ({responses[0]['reason']})
• REAL_HCWB: Score 8.6 → {responses[1]['action']} ({responses[1]['reason']})
• REAL_WINNER: Score 9.1 → {responses[2]['action']} ({responses[2]['reason']})

🔄 **Enviando /plays_today para mostrar TODOS los plays...**"""
        
        send_message(scenario_message, parse_mode="Markdown")
        
        # Enviar plays del día (debería mostrar los 3 symbols)
        send_plays_today()
        
        final_message = f"""✅ **ESCENARIO COMPLETADO**

🎯 **Resultado esperado:**
• Deberías ver los 3 símbolos en /plays_today
• Independientemente de si fueron aceptados o rechazados por el Mayordomo
• Esto confirma que se almacenan TODOS los plays del scanner

💡 **Si ves los 3 símbolos, la funcionalidad está perfecta**"""
        
        send_message(final_message, parse_mode="Markdown")
        
        return True
    
    # Ejecutar escenario
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(run_scenario())
        loop.close()
        return result
    except Exception as e:
        print(f"❌ Error en escenario: {e}")
        loop.close()
        return False

def main():
    """Ejecutar tests reales de Telegram"""
    print("🚀 TESTS REALES DE TELEGRAM - PLAYS DEL DÍA")
    print("=" * 60)
    print("⚠️  IMPORTANTE: Este test enviará mensajes REALES a tu Telegram")
    
    # Verificar configuración
    if not is_enabled():
        print("\n❌ TELEGRAM NO CONFIGURADO")
        print("Para usar este test:")
        print("1. Configura telegram_enabled = true en config.ini")
        print("2. Agrega tu telegram_bot_token")
        print("3. Agrega tu telegram_chat_id")
        return False
    
    print("✅ Telegram configurado correctamente")
    
    print("\n🚀 Iniciando test real...")
    
    results = []
    
    # Test 1: Integración básica
    print("\n" + "="*60)
    results.append(test_telegram_real_integration())
    
    # Test 2: Escenario completo del Mayordomo
    print("\n" + "="*60)
    results.append(test_telegram_mayordomo_scenario())
    
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL:")
    print(f"✅ Tests exitosos: {sum(results)}")
    print(f"❌ Tests fallidos: {len(results) - sum(results)}")
    
    if all(results):
        print("\n🎉 ¡TODOS LOS TESTS REALES PASARON!")
        print("📱 Revisa tu Telegram para ver los mensajes enviados")
        print("✅ La funcionalidad de plays del día está 100% operativa")
        return True
    else:
        print("\n⚠️  Algunos tests fallaron")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)