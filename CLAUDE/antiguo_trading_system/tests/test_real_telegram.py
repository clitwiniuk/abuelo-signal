#!/usr/bin/env python3
"""
Test Real Telegram Notifications
Envía una notificación real a Telegram para verificar configuración
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_telegram_config():
    """Test configuración de Telegram"""
    print("🧪 TESTING REAL TELEGRAM NOTIFICATIONS")
    print("=" * 50)
    
    try:
        # Import telegram client
        from notifications import telegram_client
        
        print("1️⃣ Verificando configuración...")
        
        # Check if enabled
        if not telegram_client.is_enabled():
            print("❌ Telegram no está habilitado en config.ini")
            print("   Verifica [NOTIFICATIONS] enabled = true")
            return False
        
        token = telegram_client.get_token()
        chat_id = telegram_client.get_chat_id()
        
        print(f"   ✅ Telegram habilitado")
        print(f"   🔑 Bot token: {token[:20]}...")
        print(f"   💬 Chat ID: {chat_id}")
        
        print("\n2️⃣ Enviando mensaje de test...")
        
        # Send test message
        test_message = f"""🧪 **TEST DE NOTIFICACIONES**
═══════════════════════════════

🎯 **Sistema:** Trading System v3
⏰ **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 **Estado:** Configuración correcta

**Test Play Simulado:**
• **NVDA 📈**
• $892.15 | Gap: +12.5%  
• Vol: 3.1x | Score: 9.2
• Catalyst: EARNINGS

✅ Si recibes este mensaje, las notificaciones automáticas funcionarán correctamente."""
        
        telegram_client.send_message(test_message, parse_mode="Markdown")
        
        print("   📱 Mensaje enviado!")
        print("   🔍 Verifica tu chat de Telegram")
        
        print("\n3️⃣ Simulando notificación de plays...")
        
        # Simulate a real play notification
        plays_message = f"""🎯 **PLAYS DETECTADOS** - {datetime.now().strftime('%H:%M')}
═══════════════════════════════

**1. AAPL 📈**
• $145.23 | Gap: +8.4%
• Vol: 3.0x | Score: 8.7  
• M&A

**2. TSLA 📉**
• $234.67 | Gap: -6.2%
• Vol: 3.6x | Score: 8.1
• FDA

📊 Plays mostrados: 2
🔄 Próximo scan en ~30s"""
        
        telegram_client.send_message(plays_message, parse_mode="Markdown")
        
        print("   📱 Notificación de plays enviada!")
        
        print("\n" + "=" * 50)
        print("✅ TEST COMPLETADO")
        print("=" * 50)
        print("📱 Si recibiste los mensajes en Telegram:")
        print("   ✅ Las notificaciones automáticas funcionarán")
        print("   ✅ El sistema enviará plays reales cada 30s")
        print("\n❌ Si NO recibiste los mensajes:")
        print("   🔧 Verifica el bot token y chat ID")
        print("   🔧 Asegúrate de haber iniciado chat con el bot")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en test de Telegram: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_telegram_config()
    
    if success:
        print("\n💡 SIGUIENTE PASO:")
        print("   1. Verifica que recibiste los mensajes")
        print("   2. Reinicia el sistema: python main.py")
        print("   3. Las notificaciones automáticas deberían funcionar")
    else:
        print("\n🔧 SOLUCIÓN:")
        print("   1. Verifica config.ini [NOTIFICATIONS]")
        print("   2. Verifica bot token y chat ID")
        print("   3. Asegúrate de haber hablado con el bot primero")
    
    sys.exit(0 if success else 1)