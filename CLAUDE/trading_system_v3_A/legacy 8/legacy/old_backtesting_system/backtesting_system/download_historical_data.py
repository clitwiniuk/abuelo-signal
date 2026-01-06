#!/usr/bin/env python3
"""
Script de Descarga de Datos Históricos para Backtesting - SOLO 1 MINUTO

Descarga datos intradía REALES a 1 minuto desde Polygon.io SOLO para los días específicos
en que el scanner detectó oportunidades (symbol-date combinations).

Modificaciones realizadas:
- SOLO descarga datos de 1 minuto (sin datos diarios)
- Sin event_id ni estructuras complejas
- Sin contexto histórico de 60 días
- Base de datos simple y limpia

Uso:
    # Descargar datos para últimas 10 oportunidades detectadas (DEFAULT)
    python download_historical_data.py

    # Descargar TODAS las oportunidades detectadas
    python download_historical_data.py --all

    # Limitar a 20 oportunidades
    python download_historical_data.py --limit 20
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Agregar path al backtesting system
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.polygon_data_downloader_minute_only import PolygonDataDownloaderMinuteOnly


def parse_args():
    """Parsear argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description='Descargar datos de 1 minuto desde Polygon.io para backtesting (sistema simplificado)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Descargar datos de 1 minuto para últimas 10 oportunidades detectadas por el scanner
  python download_historical_data.py

  # Descargar datos de 1 minuto para todas las oportunidades
  python download_historical_data.py --all

  # Limitar a 50 oportunidades
  python download_historical_data.py --limit 50

NOTA: Este sistema SOLO descarga datos de 1 minuto reales. 
No incluye datos diarios, event_id ni contexto histórico.
        """
    )

    parser.add_argument(
        '--api-key',
        type=str,
        default=os.environ.get('POLYGON_API_KEY'),
        help='API key de Polygon.io (default: $POLYGON_API_KEY)'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['opportunities'],  # Removido 'range' - solo modo opportunities
        default='opportunities',
        help='Modo de descarga: opportunities (días detectados por scanner, DEFAULT)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Descargar todas las oportunidades detectadas (solo para --mode opportunities)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Límite de oportunidades si no se especifica --all (default: 10)'
    )

    # Removidos argumentos para modo 'range' - solo modo opportunities

    return parser.parse_args()


def download_opportunities_mode(downloader: PolygonDataDownloaderMinuteOnly, args):
    """Modo de descarga por oportunidades del scanner - SOLO 1 MINUTO"""
    print("\n🎯 MODO: Scanner Opportunities - Solo 1 Minuto")
    print("   Descargará datos REALES de 1 minuto para días específicos detectados por el scanner")
    print("   ❌ Sin datos diarios, sin event_id, sin contexto histórico\n")

    # Obtener oportunidades
    opportunities = downloader.get_scanner_opportunities()

    if not opportunities:
        print("❌ No se encontraron oportunidades en la tabla trades")
        print("   Ejecuta el sistema de trading para generar oportunidades primero")
        sys.exit(1)

    # Aplicar límite
    limit = None if args.all else args.limit
    total_available = len(opportunities)

    if limit and limit < total_available:
        opportunities_to_download = opportunities[:limit]
        print(f"📊 Oportunidades disponibles: {total_available}")
        print(f"   Limitado a: {limit} (usa --all para descargar todas)")
    else:
        opportunities_to_download = opportunities
        print(f"📊 Oportunidades a descargar: {total_available}")

    # Mostrar preview
    print(f"\n📋 Preview de oportunidades (primeras 5):")
    for i, opp in enumerate(opportunities_to_download[:5], 1):
        print(f"   {i}. {opp['symbol']} - {opp['date']} ({opp['strategy']}, {opp['signals_count']} señales)")

    if len(opportunities_to_download) > 5:
        print(f"   ... y {len(opportunities_to_download) - 5} más")

    # Estimación (solo datos de 1 minuto - más rápido)
    total_calls = len(opportunities_to_download)
    estimated_time_minutes = total_calls / downloader.calls_per_minute

    print(f"\n⏱️  Estimado (Sistema Simplificado):")
    print(f"   - Oportunidades a descargar: {total_calls}")
    print(f"   - Llamadas API estimadas: ~{total_calls}")
    print(f"   - Tiempo estimado: ~{estimated_time_minutes:.1f} minutos")
    print(f"   - Solo datos de 1 minuto reales (sin contexto histórico)")

    # Confirmar - auto-confirmar si no hay input disponible (ej: ejecución no interactiva)
    try:
        response = input(f"\n¿Continuar con la descarga de 1 minuto? (y/N): ")
        if response.lower() not in ['y', 'yes', 'si', 's']:
            print("❌ Descarga cancelada")
            sys.exit(0)
    except EOFError:
        print("⚠️  Modo no interactivo detectado - continuando automáticamente...")
        print("   Para cancelar, usa Ctrl+C o ejecuta en terminal interactiva")

    # Ejecutar descarga
    print(f"\n⚡ Iniciando descarga de datos de 1 minuto...")
    print("=" * 60)

    stats = downloader.download_scanner_opportunities_minute_only(limit=limit)

    print("\n" + "=" * 60)
    print("✅ DESCARGA DE 1 MINUTO COMPLETADA")
    print("=" * 60)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades totales: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras de 1 minuto totales: {stats['total_minute_bars']:,}")
    
    print(f"\n🎯 Sistema Simplificado Activo:")
    print(f"   - SOLO datos de 1 minuto reales de Polygon")
    print(f"   - Sin event_id ni estructuras complejas")
    print(f"   - Base de datos simple y limpia")


def main():
    """Función principal"""
    args = parse_args()

    print("=" * 60)
    print("🚀 POLYGON HISTORICAL DATA DOWNLOADER - SOLO 1 MINUTO")
    print("=" * 60)
    print(f"📦 Base de datos: market_data.db (separada de trading_data.db)")
    print(f"⏰ Temporalidad: SOLO 1 minuto (datos intradía reales)")
    print(f"❌ Sin datos diarios, event_id, o contexto histórico")

    # Validar API key - primero intentar desde config.ini
    if not args.api_key:
        try:
            import configparser
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')
            config.read(config_path)
            if 'POLYGON' in config and 'api_key' in config['POLYGON']:
                args.api_key = config['POLYGON']['api_key']
                print(f"📡 API key cargada desde config.ini")
            else:
                print("\n❌ ERROR: API key no configurada")
                print("\nConfigura tu API key de una de estas formas:")
                print("  1. Variable de entorno: export POLYGON_API_KEY='tu_api_key'")
                print("  2. Argumento: --api-key tu_api_key")
                print("  3. En config.ini bajo sección [POLYGON] api_key = tu_api_key")
                print("\nObtén tu API key gratis en: https://polygon.io/")
                sys.exit(1)
        except Exception as e:
            print(f"\n❌ ERROR: No se pudo leer config.ini: {e}")
            print("\nConfigura tu API key de una de estas formas:")
            print("  1. Variable de entorno: export POLYGON_API_KEY='tu_api_key'")
            print("  2. Argumento: --api-key tu_api_key")
            print("\nObtén tu API key gratis en: https://polygon.io/")
            sys.exit(1)

    # Crear downloader
    print(f"\n📡 Inicializando downloader simplificado...")
    downloader = PolygonDataDownloaderMinuteOnly(api_key=args.api_key)

    try:
        # Ejecutar modo correspondiente
        if args.mode == 'opportunities':
            download_opportunities_mode(downloader, args)
        else:
            print("❌ ERROR: Solo modo 'opportunities' disponible en sistema simplificado")
            sys.exit(1)

        print("\n📊 Los datos de 1 minuto están ahora disponibles en market_data.db")
        print("   Puedes ejecutar backtests con datos intradía reales de mercado")

    except KeyboardInterrupt:
        print("\n\n⚠️  Descarga interrumpida por el usuario")
        print("   El progreso se ha guardado. Puedes reanudar más tarde.")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error durante la descarga: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
