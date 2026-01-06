#!/usr/bin/env python3
"""
Test 3: Probar sistema de notificaciones con datos simulados
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from unified_main import UnifiedTradingSystem
from utils.log_config import setup_logging

class MockTelegramClient:
    """Mock Telegram Client para testing"""
    def __init__(self):
        self.messages_sent = []
        self.enabled = True
        
    def send_message(self, message, parse_mode=None):
        """Capture sent messages instead of sending to Telegram"""
        print(f"📱 TELEGRAM MESSAGE CAPTURED:")
        print("-" * 40)
        print(message)
        print("-" * 40)
        self.messages_sent.append({
            'message': message,
            'parse_mode': parse_mode,
            'timestamp': datetime.now()
        })
        return True
        
    def is_enabled(self):
        return self.enabled

async def test_notification_system():
    """Test del sistema de notificaciones inteligentes"""
    print("🧪 TEST 3: SISTEMA DE NOTIFICACIONES INTELIGENTES")
    print("=" * 60)
    
    try:
        # Setup logging
        setup_logging()
        print("✅ Logging configurado")
        
        # Create unified system instance (without starting full system)
        system = UnifiedTradingSystem()
        
        # Replace telegram client with mock
        mock_telegram = MockTelegramClient()
        system.telegram_client = mock_telegram
        print("✅ Mock Telegram Client configurado")
        
        # Test 1: New plays notification
        print("\n📋 TEST 3.1: NOTIFICACIÓN DE PLAYS NUEVOS")
        
        new_plays = [
            {
                'symbol': 'NVDA',
                'current_price': 892.15,
                'gap_percentage': 0.125,
                'volume_ratio': 3.1,
                'quality_score': 8.5,
                'catalyst_type': 'Earnings Beat'
            },
            {
                'symbol': 'AAPL', 
                'current_price': 145.23,
                'gap_percentage': 0.084,
                'volume_ratio': 2.8,
                'quality_score': 7.2,
                'catalyst_type': 'News Catalyst'
            }
        ]
        
        await system._send_plays_notification(new_plays)
        print(f"✅ Primera notificación enviada - {len(new_plays)} plays")
        
        # Test 2: Filter duplicate notifications
        print("\n📋 TEST 3.2: FILTRO DE DUPLICADOS (debería evitar spam)")
        
        # Same plays again - should be filtered
        filtered_plays = system._filter_notification_worthy_plays(new_plays)
        print(f"📊 Plays después de filtro: {len(filtered_plays)} (esperado: 0)")
        
        if filtered_plays:
            await system._send_plays_notification(filtered_plays)
            print("⚠️  Se envió notificación duplicada (no esperado)")
        else:
            print("✅ Filtro de duplicados funcionó - no se envió spam")
        
        # Test 3: Significant changes trigger new notification
        print("\n📋 TEST 3.3: CAMBIOS SIGNIFICATIVOS (debería notificar)")
        
        # Simulate significant price change in NVDA (+7% price change)
        import time
        time.sleep(1)  # Ensure different timestamp
        
        changed_plays = [
            {
                'symbol': 'NVDA',
                'current_price': 954.50,  # +7% price increase
                'gap_percentage': 0.125,
                'volume_ratio': 4.5,      # +45% volume increase 
                'quality_score': 9.1,     # +0.6 score increase
                'catalyst_type': 'Earnings Beat'
            }
        ]
        
        # Force cooldown to be expired for this test
        if 'NVDA' in system.notified_plays:
            system.notified_plays['NVDA']['last_notified'] = datetime.now().replace(year=2020)
        
        filtered_changed = system._filter_notification_worthy_plays(changed_plays)
        print(f"📊 Plays con cambios significativos: {len(filtered_changed)}")
        
        if filtered_changed:
            await system._send_plays_notification(filtered_changed)
            print("✅ Notificación de cambios significativos enviada")
        else:
            print("❌ No se detectaron cambios significativos")
        
        # Test 4: New ticker gets notified immediately
        print("\n📋 TEST 3.4: NUEVO TICKER (debería notificar inmediatamente)")
        
        new_ticker_plays = [
            {
                'symbol': 'TSLA',  # New ticker
                'current_price': 234.67,
                'gap_percentage': -0.062,
                'volume_ratio': 3.5,
                'quality_score': 6.8,
                'catalyst_type': 'Volume Surge'
            }
        ]
        
        filtered_new = system._filter_notification_worthy_plays(new_ticker_plays)
        print(f"📊 Nuevos tickers: {len(filtered_new)}")
        
        if filtered_new:
            await system._send_plays_notification(filtered_new)
            print("✅ Notificación de nuevo ticker enviada")
        
        # Test 5: Summary of all messages sent
        print(f"\n📊 RESUMEN DE NOTIFICACIONES:")
        print(f"   Total mensajes enviados: {len(mock_telegram.messages_sent)}")
        print(f"   Estado del cache: {len(system.notified_plays)} tickers en cache")
        
        for symbol in system.notified_plays:
            data = system.notified_plays[symbol]
            print(f"   - {symbol}: última notificación {data['last_notified'].strftime('%H:%M:%S')}")
        
        print(f"\n🎉 SISTEMA DE NOTIFICACIONES TEST COMPLETADO")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN TEST 3: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_notification_system())
    sys.exit(0 if success else 1)