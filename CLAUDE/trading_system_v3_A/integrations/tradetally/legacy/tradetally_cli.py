#!/usr/bin/env python3
"""
TradeTally CLI - Herramienta de línea de comandos para sincronización
"""

import argparse
import json
import sys
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.append(str(Path(__file__).parent.parent))

from integrations.tradetally_sync import TradeTallyIntegration
from integrations.tradetally.config.tradetally_config import config

def setup_api_key():
    """Configurar API key interactivamente"""
    print("🔧 Configuración de TradeTally API Key")
    print("=" * 50)
    
    api_key = input("Introduce tu API Key de TradeTally (tt_live_xxx): ").strip()
    
    if not config.validate_api_key(api_key):
        print("❌ API Key inválida. Debe empezar con 'tt_live_' y tener al menos 20 caracteres.")
        return False
    
    if config.save_api_key(api_key):
        print("✅ API Key guardada correctamente")
        return True
    else:
        print("❌ Error guardando API Key")
        return False

def show_status():
    """Mostrar estado de configuración y sincronización"""
    print("📊 Estado de TradeTally Integration")
    print("=" * 50)
    
    # Estado de configuración
    print(f"🔑 API Key configurada: {'✅' if config.is_configured() else '❌'}")
    print(f"🌐 URL base: {config.base_url}")
    print(f"💾 Base de datos: {config.db_path}")
    print()
    
    if not config.is_configured():
        print("⚠️  Ejecuta 'python tradetally_cli.py setup' para configurar tu API Key")
        return
    
    # Estado de sincronización
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        status = sync.get_sync_status()
        
        print("📈 Estado de Sincronización:")
        print(f"   Última sincronización: {status['last_sync'] or 'Nunca'}")
        print(f"   Trades sincronizados: {status['total_synced']}")
        print(f"   Sincronizaciones fallidas: {status['failed_syncs']}")
        print()
        
        # Trades pendientes
        pending_trades = sync.get_local_trades(only_new=True)
        print(f"⏳ Trades pendientes: {len(pending_trades)}")
        
    except Exception as e:
        print(f"❌ Error obteniendo estado: {e}")

def test_connection():
    """Probar conexión con TradeTally"""
    print("🔍 Probando conexión con TradeTally...")
    print("=" * 50)
    
    if not config.is_configured():
        print("❌ API Key no configurada. Ejecuta 'setup' primero.")
        return False
    
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        success = sync.test_connection()
        
        if success:
            print("✅ Conexión exitosa con TradeTally API")
            return True
        else:
            print("❌ Error de conexión")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def sync_trades(dry_run=False):
    """Sincronizar trades con TradeTally"""
    if dry_run:
        print("🧪 MODO DRY RUN - Simulación de sincronización")
    else:
        print("🚀 Sincronizando trades con TradeTally...")
    
    print("=" * 50)
    
    if not config.is_configured():
        print("❌ API Key no configurada. Ejecuta 'setup' primero.")
        return False
    
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        
        if dry_run:
            # Solo mostrar qué se sincronizaría
            trades = sync.get_local_trades(only_new=True)
            print(f"📊 Se sincronizarían {len(trades)} trades:")
            
            for i, trade in enumerate(trades[:10], 1):  # Mostrar solo los primeros 10
                print(f"   {i}. {trade.symbol} - {trade.side} - {trade.entry_time}")
            
            if len(trades) > 10:
                print(f"   ... y {len(trades) - 10} más")
            
            return True
        
        else:
            # Sincronización real
            result = sync.sync_all_trades(
                batch_size=config.batch_size,
                delay=config.request_delay
            )
            
            print("\n📋 RESULTADO DE SINCRONIZACIÓN:")
            print(f"✅ Trades sincronizados: {result['synced']}")
            print(f"❌ Trades fallidos: {result['failed']}")
            print(f"📊 Total procesados: {result.get('total', 0)}")
            
            if result['failed'] > 0:
                print(f"\n🔍 Errores encontrados:")
                for error in result.get('errors', [])[:5]:  # Mostrar solo los primeros 5
                    print(f"   - {error}")
            
            return result['success']
            
    except Exception as e:
        print(f"❌ Error durante sincronización: {e}")
        return False

def retry_failed():
    """Reintentar trades fallidos"""
    print("🔄 Reintentando trades fallidos...")
    print("=" * 50)
    
    if not config.is_configured():
        print("❌ API Key no configurada. Ejecuta 'setup' primero.")
        return False
    
    try:
        sync = TradeTallyIntegration(config.api_key, config.base_url, config.db_path)
        result = sync.retry_failed_syncs()
        
        print(f"✅ Trades reintentados exitosamente: {result['synced']}")
        print(f"❌ Trades que siguen fallando: {result['failed']}")
        print(f"📊 Total procesados: {result['total']}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Error durante reintento: {e}")
        return False

def show_config():
    """Mostrar configuración actual"""
    print("⚙️  Configuración de TradeTally")
    print("=" * 50)
    
    config_dict = config.get_config_dict()
    
    for key, value in config_dict.items():
        if key == 'api_key' and value:
            # Mostrar solo los primeros y últimos caracteres del API key
            masked_key = f"{value[:12]}...{value[-8:]}" if len(value) > 20 else value
            print(f"{key}: {masked_key}")
        else:
            print(f"{key}: {value}")

def main():
    """Función principal del CLI"""
    parser = argparse.ArgumentParser(
        description="TradeTally Integration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python tradetally_cli.py setup          # Configurar API Key
  python tradetally_cli.py status         # Ver estado actual
  python tradetally_cli.py test           # Probar conexión
  python tradetally_cli.py sync           # Sincronizar trades
  python tradetally_cli.py sync --dry-run # Simular sincronización
  python tradetally_cli.py retry          # Reintentar trades fallidos
  python tradetally_cli.py config         # Ver configuración
        """
    )
    
    parser.add_argument(
        'command',
        choices=['setup', 'status', 'test', 'sync', 'retry', 'config'],
        help='Comando a ejecutar'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular sincronización sin enviar datos'
    )
    
    args = parser.parse_args()
    
    # Banner
    print("""
████████╗██████╗  █████╗ ██████╗ ███████╗████████╗ █████╗ ██╗     ██╗     ██╗   ██╗
╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██║     ██║     ╚██╗ ██╔╝
   ██║   ██████╔╝███████║██║  ██║█████╗     ██║   ███████║██║     ██║      ╚████╔╝ 
   ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝     ██║   ██╔══██║██║     ██║       ╚██╔╝  
   ██║   ██║  ██║██║  ██║██████╔╝███████╗   ██║   ██║  ██║███████╗███████╗   ██║   
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   
                                                                                    
                            🔗 Trading System v3 Integration
    """)
    
    # Ejecutar comando
    success = False
    
    try:
        if args.command == 'setup':
            success = setup_api_key()
        elif args.command == 'status':
            show_status()
            success = True
        elif args.command == 'test':
            success = test_connection()
        elif args.command == 'sync':
            success = sync_trades(dry_run=args.dry_run)
        elif args.command == 'retry':
            success = retry_failed()
        elif args.command == 'config':
            show_config()
            success = True
            
    except KeyboardInterrupt:
        print("\n⚠️ Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
    
    print()
    if success:
        print("🎉 Operación completada exitosamente")
        sys.exit(0)
    else:
        print("💥 Operación fallida")
        sys.exit(1)

if __name__ == "__main__":
    main()