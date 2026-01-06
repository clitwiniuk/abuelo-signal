#!/usr/bin/env python3
# production/test_telegram_integration.py
"""
Test rápido de integración de Telegram con el sistema híbrido
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from production.hybrid_config_manager import HybridConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TelegramTest")

async def test_telegram_integration():
    """Test de integración de Telegram"""
    print("🧪 TESTING INTEGRACIÓN TELEGRAM")
    print("=" * 50)
    
    try:
        # 1. Test configuración híbrida para Telegram
        print("📋 Testando configuración híbrida...")
        hybrid_config = HybridConfigManager()
        
        telegram_config = hybrid_config.get_telegram_config()
        print(f"✅ Telegram configurado: {telegram_config}")
        
        # 2. Test si Telegram está habilitado
        from notifications.telegram_client import is_enabled, send_message
        
        if is_enabled():
            print("✅ Telegram habilitado en config.ini")
            
            # 3. Test envío de mensaje
            print("📱 Enviando mensaje de test...")
            send_message("🧪 **TEST INTEGRACIÓN SISTEMA HÍBRIDO**\n\nTelegram integrado correctamente con el sistema smallcaps intraday.", parse_mode="Markdown")
            print("✅ Mensaje de test enviado")
            
        else:
            print("⚠️ Telegram deshabilitado en config.ini")
        
        # 4. Test comandos específicos
        print("🎯 Testando comandos específicos...")
        from production.telegram_smallcap_commands import SmallcapTelegramCommands
        
        # Crear instancia de comandos (sin runner para test)
        commands = SmallcapTelegramCommands()
        
        # Test algunos comandos
        test_commands = ["/smallcap", "/scanner", "/config", "/help"]
        
        for cmd in test_commands:
            handled = commands.handle_smallcap_command(cmd)
            print(f"  • {cmd}: {'✅ Manejado' if handled else '❌ No manejado'}")
        
        # 5. Test configuración completa
        print("\n📊 Configuración completa de Telegram:")
        complete_config = hybrid_config.get_complete_hybrid_config()
        telegram_section = complete_config["production_extensions"]["telegram"]
        
        print(f"  • Enabled: {telegram_section['enabled']}")
        print(f"  • Bot token: {'✅ Configurado' if telegram_section['bot_token'] else '❌ Faltante'}")
        print(f"  • Chat ID: {'✅ Configurado' if telegram_section['chat_id'] else '❌ Faltante'}")
        print(f"  • Alertas smallcaps: {telegram_section['smallcap_alerts']}")
        
        print("\n🎉 INTEGRACIÓN TELEGRAM COMPLETADA")
        print("=" * 50)
        
        print("\n📱 COMANDOS DISPONIBLES:")
        print("  • /smallcap - Status del sistema")
        print("  • /scanner - Estado del scanner")
        print("  • /plays - Plays recientes")
        print("  • /mayordomo - Risk manager status")
        print("  • /config - Configuración actual")
        print("  • /system - System health")
        print("  • /gaps - Análisis de gaps")
        print("  • /volume - Análisis de volumen")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en test de integración: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_telegram_integration())
    if success:
        print("\n✅ TEST EXITOSO - Telegram integrado al sistema híbrido")
    else:
        print("\n❌ TEST FALLIDO - Revisar configuración")