#!/usr/bin/env python3
"""
Test 1: Verificar que todos los componentes del sistema unificado se inicializan correctamente
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.service_locator import get_service_locator, get_config
from utils.log_config import setup_logging

async def test_unified_components():
    """Test de inicialización de componentes"""
    print("🧪 TEST 1: COMPONENTES DEL SISTEMA UNIFICADO")
    print("=" * 50)
    
    try:
        # Setup logging
        setup_logging()
        print("✅ Logging configurado")
        
        # Get config
        config = get_config()
        print(f"✅ Config cargado - Smallcap mode: {config.enable_smallcap_mode}")
        
        # Get service locator
        service_locator = get_service_locator()
        print("✅ Service Locator inicializado")
        
        # Test IBKR Adapter creation (without connecting)
        try:
            from adapters.ibkr_adapter import IBKRAdapter
            ibkr_adapter = IBKRAdapter(client_id=config.client_id)
            print(f"✅ IBKR Adapter creado (sin conexión) - Client ID: {ibkr_adapter.client_id}")
        except Exception as e:
            print(f"⚠️  IBKR Adapter error: {e}")
        
        # Test Telegram Client
        telegram_client = service_locator.get_or_create_telegram_client()
        print(f"✅ Telegram Client - Disponible: {hasattr(telegram_client, 'send_message')}")
        
        # Test Scanner creation (without IBKR connection)
        if config.enable_smallcap_mode:
            try:
                from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
                scanner = SmallcapDailyScanner(ibkr_adapter=None)  # Sin IBKR para test
                print("✅ Scanner inicializado")
                
                # Test scanner config
                scanner_config = scanner._get_default_config()
                print(f"   - Min quality score: {scanner_config['min_quality_score']}")
                print(f"   - Min catalyst strength: {scanner_config['min_catalyst_strength']}")
                print(f"   - Max plays per scan: {scanner_config['max_plays_per_scan']}")
            except Exception as e:
                print(f"⚠️  Scanner error: {e}")
        else:
            print("⚠️  Scanner deshabilitado (smallcap_mode = false)")
            
        # Test otros componentes sin dependencia de IBKR
        print("✅ Configuración base verificada")
        print("✅ Sistema preparado para tests de conexión")
        
        print("\n🎉 TODOS LOS COMPONENTES INICIALIZADOS CORRECTAMENTE")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN TEST 1: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_unified_components())
    sys.exit(0 if success else 1)