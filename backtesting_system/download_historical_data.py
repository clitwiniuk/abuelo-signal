#!/usr/bin/env python3
"""
Script de Descarga de Datos Históricos para Backtesting

Descarga datos históricos desde Polygon.io SOLO para los días específicos
en que el scanner detectó oportunidades (symbol-date combinations).

Uso:
    # Descargar datos para últimas 10 oportunidades detectadas (DEFAULT)
    python download_historical_data.py

    # Descargar TODAS las oportunidades detectadas
    python download_historical_data.py --all

    # Limitar a 20 oportunidades
    python download_historical_data.py --limit 20

    # Modo legacy: descargar símbolo específico con rango de fechas
    python download_historical_data.py --mode range --symbols AAPL --start 2024-01-01 --end 2024-12-31
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Agregar path al backtesting system
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.polygon_data_downloader import PolygonDataDownloader


def parse_args():
    """Parsear argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description='Descargar datos históricos desde Polygon.io para backtesting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Descargar datos para últimas 10 oportunidades detectadas por el scanner
  python download_historical_data.py

  # Descargar todas las oportunidades
  python download_historical_data.py --all

  # Limitar a 50 oportunidades
  python download_historical_data.py --limit 50

  # Modo legacy: descargar símbolos con rango de fechas
  python download_historical_data.py --mode range --symbols AAPL,TSLA --start 2024-01-01 --end 2024-12-31
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
        choices=['opportunities', 'range'],
        default='opportunities',
        help='Modo de descarga: opportunities (días detectados por scanner, DEFAULT), range (rango de fechas)'
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

    # Argumentos para modo 'range'
    parser.add_argument(
        '--symbols',
        type=str,
        help='Símbolos separados por coma (ej: AAPL,TSLA,NVDA). Solo para --mode range'
    )

    parser.add_argument(
        '--start',
        type=str,
        help='Fecha de inicio (YYYY-MM-DD). Solo para --mode range'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='Fecha de fin (YYYY-MM-DD). Solo para --mode range'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Número de días hacia atrás. Solo para --mode range (default: 30)'
    )

    return parser.parse_args()


def download_opportunities_mode(downloader: PolygonDataDownloader, args):
    """Modo de descarga por oportunidades del scanner"""
    print("\n🎯 MODO: Scanner Opportunities")
    print("   Descargará datos SOLO para días específicos detectados por el scanner\n")

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

    # Estimación
    total_calls = len(opportunities_to_download)
    estimated_time_minutes = total_calls / downloader.calls_per_minute

    print(f"\n⏱️  Estimado:")
    print(f"   - Oportunidades a descargar: {total_calls}")
    print(f"   - Llamadas API: ~{total_calls}")
    print(f"   - Tiempo estimado: ~{estimated_time_minutes:.1f} minutos")

    # Confirmar - auto-confirmar si no hay input disponible (ej: ejecución no interactiva)
    try:
        response = input(f"\n¿Continuar con la descarga? (y/N): ")
        if response.lower() not in ['y', 'yes', 'si', 's']:
            print("❌ Descarga cancelada")
            sys.exit(0)
    except EOFError:
        print("⚠️  Modo no interactivo detectado - continuando automáticamente...")
        print("   Para cancelar, usa Ctrl+C o ejecuta en terminal interactiva")

    # Ejecutar descarga
    print(f"\n⚡ Iniciando descarga de oportunidades...")
    print("=" * 60)

    stats = downloader.download_scanner_opportunities(limit=limit)

    print("\n" + "=" * 60)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 60)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades totales: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras totales: {stats['total_bars']:,}")


def download_range_mode(downloader: PolygonDataDownloader, args):
    """Modo de descarga por rango de fechas (legacy)"""
    print("\n📅 MODO: Range Download")
    print("   Descargará datos para símbolos en un rango de fechas\n")

    # Validar parámetros
    if not args.symbols:
        print("❌ ERROR: --symbols es requerido para --mode range")
        print("   Ejemplo: --symbols AAPL,TSLA,NVDA")
        sys.exit(1)

    # Parsear símbolos
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    print(f"📊 Símbolos: {symbols}")

    # Determinar rango de fechas
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=args.days)

    print(f"📅 Rango de fechas: {start_date.date()} a {end_date.date()}")
    print(f"   ({(end_date - start_date).days} días)")

    # Estimación
    trading_days = sum(1 for i in range((end_date - start_date).days + 1)
                       if (start_date + timedelta(days=i)).weekday() < 5)
    total_calls = len(symbols) * trading_days
    estimated_time_minutes = total_calls / downloader.calls_per_minute

    print(f"\n⏱️  Estimado:")
    print(f"   - Días de mercado: ~{trading_days}")
    print(f"   - Llamadas API totales: ~{total_calls}")
    print(f"   - Tiempo estimado: ~{estimated_time_minutes:.1f} minutos")

    # Confirmar - auto-confirmar si no hay input disponible (ej: ejecución no interactiva)
    try:
        response = input(f"\n¿Continuar con la descarga? (y/N): ")
        if response.lower() not in ['y', 'yes', 'si', 's']:
            print("❌ Descarga cancelada")
            sys.exit(0)
    except EOFError:
        print("⚠️  Modo no interactivo detectado - continuando automáticamente...")
        print("   Para cancelar, usa Ctrl+C o ejecuta en terminal interactiva")

    # Ejecutar descarga
    print(f"\n⚡ Iniciando descarga...")
    print("=" * 60)

    downloader.download_multiple_symbols(symbols, start_date, end_date)


def main():
    """Función principal"""
    args = parse_args()

    print("=" * 60)
    print("🚀 POLYGON HISTORICAL DATA DOWNLOADER")
    print("=" * 60)
    print(f"📦 Base de datos: market_data.db (separada de trading_data.db)")

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
    print(f"\n📡 Inicializando downloader...")
    downloader = PolygonDataDownloader(api_key=args.api_key)

    try:
        # Ejecutar modo correspondiente
        if args.mode == 'opportunities':
            download_opportunities_mode(downloader, args)
        else:
            download_range_mode(downloader, args)

        print("\n📊 Los datos están ahora disponibles en market_data.db")
        print("   Puedes ejecutar backtests con datos completos de mercado")

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
