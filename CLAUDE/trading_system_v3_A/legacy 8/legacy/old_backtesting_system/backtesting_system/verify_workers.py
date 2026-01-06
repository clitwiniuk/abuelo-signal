#!/usr/bin/env python3
"""
Verificación de Workers
======================

CLI simplificado para verificar si los workers están funcionando correctamente
SIN necesidad de backtesting.
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Agregar directorios al path
sys.path.append(str(Path(__file__).parent))

from testing.worker_verification_suite import verify_all_workers
from testing.worker_debugger import WorkerDebugger


async def main():
    """CLI principal para verificación de workers"""
    
    parser = argparse.ArgumentParser(
        description="Verificación de Workers - Sin Backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  1. Verificar todos los workers:
     python verify_workers.py --verify-all

  2. Debuggear un worker específico:
     python verify_workers.py --debug macdv

  3. Probar oportunidad personalizada:
     python verify_workers.py --test-custom

  4. Debuggear oportunidad real:
     python verify_workers.py --debug-real

  5. Ver workers disponibles:
     python verify_workers.py --list-workers
        """
    )
    
    # Argumentos
    parser.add_argument('--verify-all', action='store_true',
                       help='Ejecutar verificación completa de todos los workers')
    parser.add_argument('--debug', type=str, metavar='WORKER_NAME',
                       help='Debuggear decisiones de un worker específico')
    parser.add_argument('--test-custom', action='store_true',
                       help='Probar con oportunidad personalizada')
    parser.add_argument('--debug-real', action='store_true',
                       help='Debuggear con oportunidades reales')
    parser.add_argument('--list-workers', action='store_true',
                       help='Listar workers disponibles')
    
    args = parser.parse_args()
    
    # Si no se especifica nada, mostrar ayuda
    if not any([args.verify_all, args.debug, args.test_custom, 
                args.debug_real, args.list_workers]):
        parser.print_help()
        return
    
    try:
        if args.verify_all:
            await verify_all_workers_cli()
        elif args.debug:
            await debug_worker_cli(args.debug)
        elif args.test_custom:
            await test_custom_opportunity_cli()
        elif args.debug_real:
            await debug_real_opportunities_cli()
        elif args.list_workers:
            list_workers()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


async def verify_all_workers_cli():
    """Ejecutar verificación completa de workers"""
    
    print("🧪 VERIFICACIÓN COMPLETA DE WORKERS")
    print("="*50)
    print()
    print("✅ VERIFICANDO: Que los workers tomen decisiones correctas")
    print("   (Basado en casos de prueba conocidos)")
    print()
    
    results = await verify_all_workers()
    
    print("\n📊 REPORTE DE VERIFICACIÓN")
    print("="*50)
    
    total_workers = len(results)
    passed_workers = 0
    
    for worker_name, result in results.items():
        if 'error' in result:
            print(f"\n❌ {worker_name}: ERROR - {result['error']}")
        else:
            success_rate = result['success_rate']
            status = "✅" if success_rate >= 0.8 else "⚠️" if success_rate >= 0.5 else "❌"
            
            print(f"\n{status} {worker_name}:")
            print(f"   Tests pasados: {result['passed_tests']}/{result['total_tests']} ({success_rate:.1%})")
            
            if success_rate >= 0.8:
                passed_workers += 1
                print(f"   🎉 ¡Worker funcionando correctamente!")
            elif success_rate >= 0.5:
                print(f"   ⚠️ Worker funciona parcialmente - revisar casos fallidos")
            else:
                print(f"   ❌ Worker tiene problemas serios - necesita corrección")
            
            if result['failed_tests'] > 0:
                print(f"   📝 Tests fallidos: {result['failed_tests']}")
    
    print(f"\n📊 RESUMEN: {passed_workers}/{total_workers} workers funcionando correctamente")
    
    if passed_workers == total_workers:
        print("🎉 ¡TODOS LOS WORKERS ESTÁN FUNCIONANDO CORRECTAMENTE!")
    else:
        print("⚠️ Algunos workers necesitan atención")


async def debug_worker_cli(worker_name: str):
    """Debuggear un worker específico"""
    
    print(f"🔍 DEBUGGEANDO WORKER: {worker_name.upper()}")
    print("="*50)
    print()
    
    debugger = WorkerDebugger(worker_name)
    
    # Crear oportunidad de prueba
    test_opportunity = {
        'symbol': 'TEST_STOCK',
        'gap_percentage': 3.5,
        'volume_ratio': 1.8,
        'current_price': 9.25,
        'quality_score': 72,
        'catalyst_type': 'FDA',
        'pattern_type': 'breakout',
        'bars': []
    }
    
    print("🧪 Analizando oportunidad de prueba:")
    print("-" * 40)
    await debugger.debug_opportunity(test_opportunity)


async def test_custom_opportunity_cli():
    """Probar con oportunidad personalizada"""
    
    print("🔍 TESTING CON OPORTUNIDAD PERSONALIZADA")
    print("="*50)
    print()
    
    # Crear oportunidad personalizada
    custom_opportunity = {
        'symbol': 'MY_TEST_STOCK',
        'gap_percentage': 4.2,
        'volume_ratio': 2.1,
        'current_price': 7.85,
        'quality_score': 68,
        'catalyst_type': 'ANALYST_UPGRADE',
        'pattern_type': 'breakout',
        'bars': []
    }
    
    print("📊 Oportunidad personalizada:")
    print(f"   Símbolo: {custom_opportunity['symbol']}")
    print(f"   Gap: {custom_opportunity['gap_percentage']}%")
    print(f"   Volumen: {custom_opportunity['volume_ratio']}x")
    print(f"   Precio: ${custom_opportunity['current_price']}")
    print(f"   Quality: {custom_opportunity['quality_score']}")
    print(f"   Catalyst: {custom_opportunity['catalyst_type']}")
    print()
    
    # Probar con diferentes workers
    workers = ['macdv', 'daily_plays', 'vwap']
    
    for worker_name in workers:
        print(f"🧪 WORKER: {worker_name.upper()}")
        print("-" * 30)
        
        debugger = WorkerDebugger(worker_name)
        await debugger.debug_opportunity(custom_opportunity)
        print()


async def debug_real_opportunities_cli():
    """Debuggear oportunidades reales"""
    
    print("🔍 DEBUGGEANDO OPORTUNIDADES REALES")
    print("="*50)
    print()
    print("📊 Analizando oportunidades desde market_data.db...")
    print()
    
    try:
        from testing.worker_debugger import debug_real_opportunities
        await debug_real_opportunities()
    except Exception as e:
        print(f"❌ Error: {e}")


def list_workers():
    """Listar workers disponibles"""
    
    print("📋 WORKERS DISPONIBLES PARA VERIFICACIÓN")
    print("="*50)
    
    workers_info = {
        'macdv': 'MACD Divergence Strategy - Gaps pequeños, smallcaps',
        'daily_plays': 'Daily Catalyst Plays - Requiere catalysts fuertes',
        'vwap': 'VWAP Strategy - Breakouts cerca de VWAP',
        'momentum_breakout': 'Momentum Breakout - Alto volumen, fuerte momentum',
        'bull_flag': 'Bull Flag - Patrones de continuación',
        'gap_go': 'Gap Go - Gaps grandes con volumen'
    }
    
    for worker_name, description in workers_info.items():
        print(f"✅ {worker_name:<20}: {description}")
    
    print()
    print("💡 Para verificar un worker:")
    print(f"   python verify_workers.py --debug {list(workers_info.keys())[0]}")


if __name__ == "__main__":
    asyncio.run(main())