#!/usr/bin/env python3
"""
Script para resetear el estado de sincronización de TradeTally
Esto permitirá re-enviar todos los trades con los campos actualizados
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reset_sync_state():
    """Resetea el estado de sincronización para forzar re-envío de todos los trades"""

    sync_file = Path("tradetally_sync_state.json")

    if not sync_file.exists():
        logger.info("📄 Archivo de estado no existe, creando nuevo...")
        new_state = {
            'last_sync_timestamp': None,
            'synced_trade_ids': [],
            'failed_syncs': []
        }
    else:
        logger.info("🔄 Reseteando estado de sincronización existente...")

        # Leer estado actual
        with open(sync_file, 'r') as f:
            current_state = json.load(f)

        logger.info(f"📊 Estado actual: {len(current_state.get('synced_trade_ids', []))} trades sincronizados")

        # Crear nuevo estado vacío
        new_state = {
            'last_sync_timestamp': None,
            'synced_trade_ids': [],  # Vacío para forzar re-sync
            'failed_syncs': []  # Limpiar fallos también
        }

    # Guardar nuevo estado
    with open(sync_file, 'w') as f:
        json.dump(new_state, f, indent=2)

    logger.info("✅ Estado de sincronización reseteado")
    logger.info("🔄 Ahora puedes ejecutar la sincronización completa con campos actualizados")

def main():
    """Función principal"""
    print("🔄 RESETEO DE ESTADO DE SINCRONIZACIÓN TRADETALLY")
    print("=" * 50)
    print()
    print("⚠️  ATENCIÓN: Esto eliminará el registro de trades sincronizados")
    print("📤 Los próximos trades se enviarán TODOS nuevamente a TradeTally")
    print("🔄 Útil para actualizar campos en trades ya existentes")
    print()

    confirm = input("¿Continuar? (yes/no): ").lower().strip()

    if confirm in ['yes', 'y', 'si', 's']:
        reset_sync_state()
        print()
        print("🚀 Para sincronizar con campos actualizados:")
        print("   export TRADETALLY_API_KEY='tu_api_key'")
        print("   export TRADETALLY_BASE_URL='tu_dominio'")
        print("   python integrations/tradetally/core/tradetally_sync.py")
    else:
        print("❌ Operación cancelada")

if __name__ == "__main__":
    main()