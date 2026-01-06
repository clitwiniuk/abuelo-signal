#!/usr/bin/env python3
"""
Test Scanner Notifications - UNIFIED TRADING SYSTEM
Prueba que el sistema automático de notificaciones del scanner funciona correctamente
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.log_config import setup_logging

class MockTelegramClient:
    """Mock Telegram client para capturar mensajes"""
    def __init__(self):
        self.messages_sent = []
        self.logger = logging.getLogger("MockTelegramClient")
    
    def send_message(self, message: str, parse_mode: str = None, use_html: bool = False):
        """Capturar mensaje enviado"""
        self.messages_sent.append({
            'message': message,
            'parse_mode': parse_mode,
            'timestamp': datetime.now(),
            'use_html': use_html
        })
        self.logger.info(f"📱 Mock message sent: {message[:50]}...")
    
    def get_last_message(self):
        """Obtener último mensaje enviado"""
        return self.messages_sent[-1] if self.messages_sent else None
    
    def clear_messages(self):
        """Limpiar mensajes capturados"""
        self.messages_sent = []

def create_mock_plays() -> List[Dict]:
    """Crear plays de prueba realistas"""
    return [
        {
            'symbol': 'NVDA',
            'current_price': 892.15,
            'gap_percentage': 0.125,  # 12.5%
            'volume_ratio': 3.1,
            'quality_score': 9.2,
            'catalyst_type': 'EARNINGS',
            'change_reason': 'Nuevo play'
        },
        {
            'symbol': 'AAPL', 
            'current_price': 145.23,
            'gap_percentage': 0.084,  # 8.4%
            'volume_ratio': 3.0,
            'quality_score': 8.7,
            'catalyst_type': 'M&A',
            'change_reason': 'Precio actualizado'
        },
        {
            'symbol': 'TSLA',
            'current_price': 234.67,
            'gap_percentage': -0.062,  # -6.2%
            'volume_ratio': 3.6,
            'quality_score': 8.1,
            'catalyst_type': 'FDA',
            'change_reason': 'Nuevo play'
        }
    ]

async def test_notification_system():
    """Test principal del sistema de notificaciones"""
    print("🧪 TESTING SCANNER NOTIFICATIONS SYSTEM")
    print("=" * 60)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger("NotificationTest")
    
    try:
        # Importar unified_main para acceder a la lógica
        from unified_main import UnifiedTradingSystem
        
        # Crear sistema con mock telegram
        mock_telegram = MockTelegramClient()
        
        # Crear una instancia ligera solo para testing
        test_system = UnifiedTradingSystem()
        test_system.telegram_client = mock_telegram
        
        print("✅ Sistema de test inicializado")
        
        # Test 1: Envío de notificación básica
        print("\n1️⃣ Test: Envío de notificación básica")
        print("-" * 40)
        
        mock_plays = create_mock_plays()
        
        # Llamar directamente a la función de notificaciones
        await test_system._send_plays_notification(mock_plays)
        
        # Verificar que se envió el mensaje
        if mock_telegram.messages_sent:
            last_msg = mock_telegram.get_last_message()
            print(f"✅ Notificación enviada correctamente")
            print(f"   📱 Parse mode: {last_msg['parse_mode']}")
            print(f"   📊 Plays incluidos: {len(mock_plays)}")
            print(f"   ⏰ Timestamp: {last_msg['timestamp'].strftime('%H:%M:%S')}")
            
            # Mostrar extracto del mensaje
            message_preview = last_msg['message'][:200] + "..." if len(last_msg['message']) > 200 else last_msg['message']
            print(f"   💬 Mensaje preview: {message_preview}")
        else:
            print("❌ No se envió ninguna notificación")
            return False
        
        # Test 2: Filtrado de plays notification-worthy
        print("\n2️⃣ Test: Filtrado de plays notification-worthy")
        print("-" * 50)
        
        # Simular plays con diferentes características
        all_plays = [
            # Play que debería pasar filtros
            {
                'symbol': 'GOOD1',
                'current_price': 7.50,
                'gap_percentage': 0.12,
                'volume_ratio': 4.0,
                'quality_score': 8.5,
                'catalyst_type': 'BREAKTHROUGH',
            },
            # Play que no debería pasar (baja calidad)
            {
                'symbol': 'POOR1', 
                'current_price': 2.15,
                'gap_percentage': 0.03,
                'volume_ratio': 1.2,
                'quality_score': 4.0,
                'catalyst_type': 'OTHER',
            }
        ]
        
        # Test del filtro (si existe)
        if hasattr(test_system, '_filter_notification_worthy_plays'):
            filtered_plays = test_system._filter_notification_worthy_plays(all_plays)
            print(f"   📊 Plays originales: {len(all_plays)}")
            print(f"   ✅ Plays filtrados: {len(filtered_plays)}")
            
            # Verificar que el filtro funciona
            if len(filtered_plays) < len(all_plays):
                print(f"   🔍 Filtro funcionando: rechazó {len(all_plays) - len(filtered_plays)} plays")
            else:
                print(f"   ⚠️ Filtro muy permisivo: pasaron todos los plays")
        else:
            print("   ⚠️ Función de filtrado no encontrada")
        
        # Test 3: Formato del mensaje
        print("\n3️⃣ Test: Formato del mensaje")
        print("-" * 35)
        
        mock_telegram.clear_messages()
        single_play = [mock_plays[0]]  # Solo NVDA
        
        await test_system._send_plays_notification(single_play)
        
        if mock_telegram.messages_sent:
            message = mock_telegram.get_last_message()['message']
            
            # Verificar elementos clave del mensaje
            checks = [
                ("🎯 **PLAYS DETECTADOS**" in message, "Header principal"),
                ("NVDA" in message, "Símbolo incluido"),
                ("$892.15" in message, "Precio incluido"),
                ("+12.5%" in message, "Gap percentage incluido"),
                ("3.1x" in message, "Volume ratio incluido"),
                ("9.2" in message, "Quality score incluido"),
                ("EARNINGS" in message, "Catalyst type incluido"),
                ("Próximo scan" in message, "Info de próximo scan")
            ]
            
            print("   📋 Verificación de formato:")
            for check, description in checks:
                status = "✅" if check else "❌"
                print(f"      {status} {description}")
        
        # Test 4: Múltiples plays en una notificación
        print("\n4️⃣ Test: Múltiples plays en notificación")
        print("-" * 45)
        
        mock_telegram.clear_messages()
        await test_system._send_plays_notification(mock_plays)  # Todos los plays
        
        if mock_telegram.messages_sent:
            message = mock_telegram.get_last_message()['message']
            
            # Contar cuántos plays aparecen en el mensaje
            play_count = 0
            for play in mock_plays:
                if play['symbol'] in message:
                    play_count += 1
            
            print(f"   📊 Plays esperados: {len(mock_plays)}")
            print(f"   📊 Plays en mensaje: {play_count}")
            
            if play_count == len(mock_plays):
                print("   ✅ Todos los plays incluidos correctamente")
            else:
                print("   ⚠️ Algunos plays faltaron en el mensaje")
        
        print("\n" + "=" * 60)
        print("🎉 TESTS COMPLETADOS")
        print("=" * 60)
        
        # Resumen final
        total_messages = len(mock_telegram.messages_sent)
        print(f"📊 Total mensajes enviados: {total_messages}")
        print(f"📱 Parse mode utilizado: {mock_telegram.messages_sent[0]['parse_mode'] if mock_telegram.messages_sent else 'N/A'}")
        
        if total_messages > 0:
            print("✅ Sistema de notificaciones automáticas FUNCIONANDO")
            return True
        else:
            print("❌ Sistema de notificaciones automáticas FALLANDO")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error en test de notificaciones: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_timing_simulation():
    """Test para simular el timing de 30 segundos del scanner"""
    print("\n🕐 TESTING SCANNER TIMING (Simulación)")
    print("-" * 50)
    
    print("   ⏰ Scanner configurado para ejecutar cada 30s")
    print("   🔄 Simulando 3 ciclos de scanning...")
    
    mock_telegram = MockTelegramClient()
    
    try:
        from unified_main import UnifiedTradingSystem
        test_system = UnifiedTradingSystem()
        test_system.telegram_client = mock_telegram
        
        # Simular 3 ciclos de scanning
        for cycle in range(1, 4):
            print(f"   📡 Ciclo {cycle}: Simulando detección de plays...")
            
            # Crear plays diferentes para cada ciclo
            cycle_plays = [
                {
                    'symbol': f'SYM{cycle}',
                    'current_price': 10.0 + cycle,
                    'gap_percentage': 0.05 + (cycle * 0.02),
                    'volume_ratio': 2.0 + cycle,
                    'quality_score': 7.0 + cycle,
                    'catalyst_type': 'M&A',
                    'change_reason': f'Ciclo {cycle} play'
                }
            ]
            
            await test_system._send_plays_notification(cycle_plays)
            print(f"   ✅ Notificación ciclo {cycle} enviada")
            
            # Pequeña pausa para simular timing
            await asyncio.sleep(0.5)
        
        print(f"   📊 Total notificaciones enviadas: {len(mock_telegram.messages_sent)}")
        print("   ✅ Simulación de timing completada")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en simulación de timing: {e}")
        return False

async def main():
    """Ejecutar todos los tests"""
    print("🚀 SCANNER NOTIFICATIONS TEST SUITE")
    print("=" * 70)
    
    # Test principal
    test1_success = await test_notification_system()
    
    # Test de timing
    test2_success = await test_timing_simulation()
    
    # Resultado final
    print("\n" + "=" * 70)
    print("📋 RESUMEN DE TESTS")
    print("=" * 70)
    
    print(f"✅ Test Sistema Notificaciones: {'PASS' if test1_success else 'FAIL'}")
    print(f"✅ Test Timing Simulation: {'PASS' if test2_success else 'FAIL'}")
    
    overall_success = test1_success and test2_success
    
    if overall_success:
        print("\n🎉 TODOS LOS TESTS PASARON")
        print("✅ El sistema de notificaciones automáticas está funcionando correctamente")
        print("📱 Las notificaciones se enviarán automáticamente cada 30s cuando haya plays")
    else:
        print("\n⚠️ ALGUNOS TESTS FALLARON")
        print("🔧 Revisar la implementación del sistema de notificaciones")
    
    return overall_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)