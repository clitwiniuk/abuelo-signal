#!/usr/bin/env python3
"""
Verificación de Workers REALES
==============================

CLI para verificar si los workers REALES de trading_system_v3 
están funcionando correctamente SIN ejecutar órdenes reales.

Usa los workers MacdvWorkerLogic, DailyPlaysWorkerLogic, etc. pero
mockea las dependencias para que puedan ser testados sin ejecutar 
órdenes en IBKR.
"""

import asyncio
import argparse
import sys
import logging
from pathlib import Path

# Agregar directorios al path
sys.path.append(str(Path(__file__).parent))

from testing.real_worker_tester import RealWorkerTester, test_all_real_workers

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """CLI principal para verificación de workers reales"""
    
    parser = argparse.ArgumentParser(
        description="Verificación de Workers REALES - Sin Backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  1. Testear un worker específico:
     python verify_real_workers.py --worker macdv

  2. Testear worker con oportunidad personalizada:
     python verify_real_workers.py --worker macdv --gap 3.5 --price 9.25 --volume 1.8

  3. Testear todos los workers:
     python verify_real_workers.py --all-workers

  4. Testear con oportunidades reales de BD:
     python verify_real_workers.py --worker macdv --real-data

  5. Listar workers disponibles:
     python verify_real_workers.py --list-workers
        """
    )
    
    # Argumentos
    parser.add_argument('--worker', type=str, metavar='WORKER_NAME',
                       help='Worker específico a testear')
    parser.add_argument('--all-workers', action='store_true',
                       help='Testear todos los workers disponibles')
    parser.add_argument('--real-data', action='store_true',
                       help='Usar datos reales de market_data.db')
    parser.add_argument('--list-workers', action='store_true',
                       help='Listar workers disponibles')
    
    # Parámetros de oportunidad personalizada
    parser.add_argument('--symbol', type=str, default='TEST_STOCK',
                       help='Símbolo para testing (default: TEST_STOCK)')
    parser.add_argument('--gap', type=float, default=3.0,
                       help='Gap percentage (default: 3.0)')
    parser.add_argument('--price', type=float, default=8.5,
                       help='Precio actual (default: 8.5)')
    parser.add_argument('--volume', type=float, default=1.5,
                       help='Volume ratio (default: 1.5)')
    parser.add_argument('--quality', type=float, default=70.0,
                       help='Quality score (default: 70.0)')
    parser.add_argument('--catalyst', type=str, default='NEWS',
                       help='Catalyst type (default: NEWS)')
    
    args = parser.parse_args()
    
    # Si no se especifica nada, mostrar ayuda
    if not any([args.worker, args.all_workers, args.list_workers]):
        parser.print_help()
        return
    
    try:
        if args.list_workers:
            list_real_workers()
        elif args.all_workers:
            await test_all_workers_cli()
        elif args.worker:
            await test_single_worker_cli(args)
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)


async def test_single_worker_cli(args):
    """Testear un worker específico"""
    
    worker_name = args.worker
    
    print(f"🧪 TESTEANDO WORKER REAL: {worker_name.upper()}")
    print("="*50)
    print()
    
    try:
        tester = RealWorkerTester(worker_name)
        
        if args.real_data:
            # Testear con datos reales
            print("📊 Usando datos reales de market_data.db...")
            results = await tester.test_real_opportunities()
            
            if not results:
                print("❌ No se pudieron cargar datos reales")
                return
            
            # Mostrar resumen
            approved = sum(1 for r in results if r.get('decision', False))
            total = len(results)
            
            print(f"\n📊 RESULTADOS:")
            print(f"   Total testees: {total}")
            print(f"   Aprobados: {approved}")
            print(f"   Rechazados: {total - approved}")
            print(f"   Tasa aprobación: {(approved/total)*100:.1f}%")
            print()
            
            # Mostrar algunos ejemplos
            print("📝 EJEMPLOS:")
            for i, result in enumerate(results[:5]):  # Primeros 5
                opportunity = result.get('opportunity', {})
                symbol = opportunity.get('symbol', 'N/A')
                decision = "✅ APROBADO" if result.get('decision', False) else "❌ RECHAZADO"
                print(f"   {i+1}. {symbol}: {decision}")
                
                if not result.get('success'):
                    print(f"      ❌ Error: {result.get('error', 'Unknown')}")
        
        else:
            # Testear con oportunidad personalizada
            print("🎯 Usando oportunidad personalizada:")
            print(f"   Símbolo: {args.symbol}")
            print(f"   Gap: {args.gap}%")
            print(f"   Precio: ${args.price}")
            print(f"   Volumen: {args.volume}x")
            print(f"   Calidad: {args.quality}")
            print(f"   Catalyst: {args.catalyst}")
            print()
            
            result = await tester.test_custom_opportunity(
                symbol=args.symbol,
                gap_percentage=args.gap,
                volume_ratio=args.volume,
                current_price=args.price,
                quality_score=args.quality,
                catalyst_type=args.catalyst
            )
            
            # Mostrar resultado
            if result['success']:
                decision = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
                print(f"🎯 RESULTADO: {decision}")
                
                if result['decision']:
                    print("✅ ¡El worker aprobó la oportunidad!")
                else:
                    print("❌ El worker rechazó la oportunidad.")
                    print("   Esto puede ser normal si la oportunidad no cumple sus criterios.")
            else:
                print(f"❌ ERROR: {result['error']}")
                print("   El worker tuvo problemas procesando la oportunidad.")
                
    except Exception as e:
        logger.error(f"❌ Error testeando worker {worker_name}: {e}")
        print(f"❌ Error: {e}")


async def test_all_workers_cli():
    """Testear todos los workers reales"""
    
    print("🧪 TESTING COMPLETO DE WORKERS REALES")
    print("="*50)
    print("⚠️  Testeando con oportunidad personalizada estándar")
    print()
    
    results = await test_all_real_workers()
    
    # Mostrar resumen detallado
    print(f"\n{'='*50}")
    print("📊 RESUMEN DETALLADO")
    print(f"{'='*50}")
    
    success_count = 0
    error_count = 0
    
    for worker_name, result in results.items():
        if result['success']:
            decision = "✅ APROBADO" if result['decision'] else "❌ RECHAZADO"
            status = "FUNCIONANDO" if result['decision'] else "RECHAZANDO"
            success_count += 1
            print(f"{worker_name:<20}: {status} - {decision}")
        else:
            error_count += 1
            print(f"{worker_name:<20}: ❌ ERROR - {result['error']}")
    
    print(f"\n📊 ESTADÍSTICAS:")
    print(f"   Workers funcionando: {success_count}")
    print(f"   Workers con errores: {error_count}")
    print(f"   Total workers: {len(results)}")
    
    if success_count > 0:
        print(f"\n🎉 {success_count}/{len(results)} workers están funcionando correctamente!")
    else:
        print(f"\n⚠️  Todos los workers tuvieron errores")


def list_real_workers():
    """Listar workers reales disponibles"""
    
    print("📋 WORKERS REALES DISPONIBLES")
    print("="*50)
    print()
    
    workers_info = {
        'macdv': {
            'description': 'MACD Divergence Worker Logic',
            'file': 'strategies/workers/macdv_worker_logic.py',
            'lines': '1,515 líneas de código complejo',
            'features': ['Análisis MACD multi-timeframe', 'IBKR integration', 'VWAP validation', 'Position management']
        },
        'daily_plays': {
            'description': 'Daily Plays Worker Logic', 
            'file': 'strategies/workers/daily_plays_worker_logic.py',
            'lines': 'Worker complejo con execution_engine',
            'features': ['Catalyst-driven', 'Risk management', 'Broker integration']
        },
        'vwap': {
            'description': 'VWAP Worker Logic',
            'file': 'strategies/workers/vwap_worker_logic.py', 
            'lines': 'Worker con broker integration',
            'features': ['VWAP analysis', 'Volume confirmation', 'Position management']
        },
        'generic_01': {
            'description': 'Generic Worker Logic 01',
            'file': 'strategies/workers/generic_01_worker_logic.py',
            'lines': 'Worker genérico configurable',
            'features': ['Configurable criteria', 'Risk assessment']
        },
        'volume_absorption': {
            'description': 'Volume Absorption Worker Logic',
            'file': 'strategies/workers/volume_absorption_worker_logic.py',
            'lines': 'Worker especializado en absorción de volumen',
            'features': ['Volume analysis', 'Institutional activity detection']
        },
        'momentum_breakout': {
            'description': 'Momentum Breakout Worker Logic', 
            'file': 'strategies/workers/momentum_breakout_worker_logic.py',
            'lines': 'Worker de momentum y breakouts',
            'features': ['Momentum detection', 'Breakout patterns', 'Volume confirmation']
        },
        'vcp_smallcap': {
            'description': 'VCP Smallcap Worker Logic',
            'file': 'strategies/workers/vcp_smallcap_worker_logic.py',
            'lines': 'Worker especializado en smallcaps VCP',
            'features': ['VCP patterns', 'Smallcap focus', 'Pattern recognition']
        }
    }
    
    for worker_name, info in workers_info.items():
        print(f"✅ {worker_name.upper()}")
        print(f"   Descripción: {info['description']}")
        print(f"   Archivo: {info['file']}")
        print(f"   Complejidad: {info['lines']}")
        print(f"   Características: {', '.join(info['features'])}")
        print()
    
    print("💡 Ejemplos de uso:")
    print(f"   python verify_real_workers.py --worker macdv")
    print(f"   python verify_real_workers.py --worker macdv --gap 3.5 --price 9.25")
    print(f"   python verify_real_workers.py --all-workers")
    print()


if __name__ == "__main__":
    asyncio.run(main())