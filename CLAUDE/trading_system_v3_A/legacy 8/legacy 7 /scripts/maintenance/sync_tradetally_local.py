#!/usr/bin/env python3
"""
Script para sincronizar trades con TradeTally local
Usa la configuración de config.ini
"""

import asyncio
import json
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.service_locator import get_service_locator

async def sync_tradetally():
    """Sincronizar trades con TradeTally local"""
    try:
        print("🚀 Iniciando sincronización con TradeTally local...")
        
        # Obtener service locator
        sl = get_service_locator()
        
        # Crear servicio TradeTally
        await sl.get_or_create_tradetally_service()
        svc = sl.get_service('tradetally_service')
        
        if svc is None:
            print("❌ Error: No se pudo crear el servicio TradeTally")
            return
        
        # Ejecutar sincronización manual
        result = svc.manual_sync()
        
        # Mostrar resultado
        print("\n📊 RESULTADO DE SINCRONIZACIÓN:")
        print(json.dumps(result, indent=2))
        
        if result.get('success'):
            print(f"\n✅ Sincronización exitosa:")
            print(f"   • Trades sincronizados: {result.get('synced', 0)}")
            print(f"   • Trades fallidos: {result.get('failed', 0)}")
            print(f"   • Total procesados: {result.get('total', 0)}")
        else:
            print(f"\n❌ Error en sincronización: {result.get('error', 'Error desconocido')}")
        
        # Cleanup
        await sl.cleanup()
        
    except Exception as e:
        print(f"❌ Error durante sincronización: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Función principal"""
    print("=" * 50)
    print("🔄 SINCRONIZACIÓN MANUAL TRADETALLY LOCAL")
    print("=" * 50)
    
    # Ejecutar sincronización
    asyncio.run(sync_tradetally())
    
    print("\n✅ Proceso completado")

if __name__ == "__main__":
    main()
