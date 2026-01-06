#!/usr/bin/env python3
# production/start_smallcap_production.py
"""
STARTUP Script para Smallcaps Intraday Production
Auto-generado por deployment script - USA CONFIG.INI + HYBRID EXTENSIONS
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from production.smallcap_production_runner import SmallcapProductionRunner

async def main():
    """Startup principal del sistema de producción"""
    print("🚀 INICIANDO SISTEMA SMALLCAPS INTRADAY PRODUCTION")
    print("=" * 60)
    print("📋 Configuración: config.ini + extensiones híbridas")
    
    # Verificar SOLO variables de entorno que NO están en config.ini
    required_vars = ["IBKR_ACCOUNT", "TIINGO_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {missing_vars}")
        print("💡 Configurar antes de ejecutar:")
        for var in missing_vars:
            print(f"   export {var}=<tu_valor>")
        print()
        print("ℹ️  NOTA: IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID se leen desde config.ini")
        return
    
    print("✅ Variables de entorno configuradas")
    print("✅ config.ini será leído automáticamente")
    
    # Inicializar y ejecutar runner (usa HybridConfigManager internamente)
    runner = SmallcapProductionRunner()
    
    try:
        await runner.initialize()
        await runner.run_production_scanning()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown manual iniciado...")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await runner.shutdown()
        print("✅ Sistema detenido correctamente")

if __name__ == "__main__":
    # Configurar event loop para compatibilidad
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
