#!/usr/bin/env python3
"""
Professional Backtesting System
===============================

Punto de entrada principal para el sistema de backtesting profesional.
Proporciona CLI y funcionalidades programáticas para testing comprehensivo de workers.
"""

import asyncio
import argparse
import logging
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar componentes del sistema
from .core.backtest_runner import BacktestRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_argparse():
    """Configura el parser de argumentos de línea de comandos"""
    parser = argparse.ArgumentParser(
        description="Professional Backtesting System for Trading Workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Listar workers disponibles
  python main.py --list-workers

  # Test individual de un worker
  python main.py --worker macdv --patterns 100 --visualize

  # Comparar múltiples workers
  python main.py --workers macdv,daily_plays,vwap --patterns 50

  # Benchmark completo
  python main.py --benchmark --all-workers --patterns 75

  # Ejecutar ejemplo completo
  python examples/demo_backtesting.py
        """
    )
    
    # Argumentos principales
    parser.add_argument('--list-workers', action='store_true',
                       help='Listar workers disponibles para testing')
    
    parser.add_argument('--worker', type=str,
                       help='Nombre del worker para test individual')
    
    parser.add_argument('--workers', type=str,
                       help='Lista de workers para comparación (separados por comas)')
    
    parser.add_argument('--patterns', type=int, default=50,
                       help='Número de patrones sintéticos a generar (default: 50)')
    
    parser.add_argument('--visualize', action='store_true', default=True,
                       help='Generar visualizaciones (default: True)')
    
    parser.add_argument('--no-visualize', action='store_false', dest='visualize',
                       help='No generar visualizaciones')
    
    parser.add_argument('--benchmark', action='store_true',
                       help='Ejecutar benchmark completo')
    
    parser.add_argument('--all-workers', action='store_true',
                       help='Incluir todos los workers disponibles en benchmark')
    
    parser.add_argument('--detailed', action='store_true', default=True,
                       help='Análisis detallado (default: True)')
    
    parser.add_argument('--output-dir', type=str, default='results',
                       help='Directorio de salida para resultados (default: results)')
    
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Nivel de logging (default: INFO)')
    
    return parser


async def main():
    """Función principal del CLI"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Configurar logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Crear directorio de salida
    output_dir = os.path.join(os.path.dirname(__file__), args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Crear runner
    runner = BacktestRunner(output_dir=output_dir)
    
    try:
        # Listar workers
        if args.list_workers:
            runner.list_available_workers()
            return
        
        # Ejecutar según argumentos
        if args.worker:
            # Test individual
            print(f"\n🧪 Ejecutando test individual para: {args.worker}")
            metrics = await runner.run_single_worker_test(
                worker_name=args.worker,
                num_patterns=args.patterns,
                visualize=args.visualize,
                detailed=args.detailed
            )
            
            if 'error' not in metrics:
                print(f"\n📊 Resultados para {args.worker}:")
                print(f"   Win Rate: {metrics.get('win_rate', 0):.1%}")
                print(f"   Average Return: {metrics.get('avg_return', 0):+.2f}%")
                print(f"   Profit Factor: {metrics.get('profit_factor', 0):.2f}")
                print(f"   Total Trades: {metrics.get('total_trades', 0)}")
            else:
                print(f"❌ Error en test: {metrics['error']}")
        
        elif args.workers:
            # Comparación multi-worker
            worker_names = [w.strip() for w in args.workers.split(',')]
            print(f"\n🏁 Ejecutando comparación: {', '.join(worker_names)}")
            
            results = await runner.run_multi_worker_comparison(
                worker_names=worker_names,
                num_patterns=args.patterns,
                visualize=args.visualize
            )
            
            print(f"\n📊 Resultados de Comparación:")
            for worker_name, metrics in results.items():
                if 'error' not in metrics:
                    print(f"   {worker_name:<15}: Win {metrics.get('win_rate', 0):.1%}, "
                          f"Return {metrics.get('avg_return', 0):+.2f}%, "
                          f"PF {metrics.get('profit_factor', 0):.2f}")
                else:
                    print(f"   {worker_name:<15}: ERROR - {metrics['error']}")
        
        elif args.benchmark:
            # Benchmark completo
            worker_names = None if args.all_workers else ['macdv', 'daily_plays', 'vwap']
            print(f"\n🚀 Ejecutando benchmark completo")
            
            benchmark_report = await runner.run_benchmark(
                worker_names=worker_names,
                num_patterns=args.patterns
            )
            
            if 'error' not in benchmark_report:
                summary = benchmark_report.get('summary', {})
                print(f"\n📊 Resumen del Benchmark:")
                print(f"   Workers testados: {benchmark_report['workers_tested']}")
                print(f"   Duración: {benchmark_report['duration_seconds']:.1f} segundos")
                print(f"   Win Rate promedio: {summary.get('aggregate_win_rate', 0):.1%}")
                print(f"   Mejor performer: {summary.get('best_performer', 'N/A')}")
            else:
                print(f"❌ Error en benchmark: {benchmark_report['error']}")
        
        else:
            # Mostrar ayuda
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Operación interrumpida por el usuario")
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Configurar event loop para Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar CLI
    asyncio.run(main())