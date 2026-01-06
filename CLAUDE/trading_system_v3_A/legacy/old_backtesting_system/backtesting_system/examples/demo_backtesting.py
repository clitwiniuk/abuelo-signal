#!/usr/bin/env python3
"""
Professional Backtesting Demo
=============================

Ejemplo completo y demostración del sistema de backtesting profesional.
Utiliza la estructura reorganizada del directorio backtesting_system/.
"""

import asyncio
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Importar el sistema profesional
from backtesting_system.core.backtest_runner import BacktestRunner


async def main():
    """Función principal que ejecuta todos los ejemplos"""
    print("🎯 DEMO COMPLETO - Professional Backtesting System")
    print("="*70)
    
    try:
        # Crear runner con configuración profesional
        runner = BacktestRunner(output_dir="results")
        
        print("\n✅ Sistema inicializado correctamente")
        print("📁 Directorio de resultados:", runner.output_dir)
        
        # 1. Listar workers disponibles
        print("\n1️⃣ LISTANDO WORKERS DISPONIBLES")
        runner.list_available_workers()
        
        # 2. Test individual rápido
        print("\n2️⃣ TEST INDIVIDUAL - MACDV WORKER")
        print("🧪 Probando worker MACDV con 10 patrones...")
        
        macdv_metrics = await runner.run_single_worker_test(
            worker_name="macdv",
            num_patterns=10,
            visualize=True,
            detailed=True
        )
        
        print(f"\n📊 Resultados MACDV Worker:")
        print(f"   Win Rate: {macdv_metrics.get('win_rate', 0):.1%}")
        print(f"   Average Return: {macdv_metrics.get('avg_return', 0):+.2f}%")
        print(f"   Profit Factor: {macdv_metrics.get('profit_factor', 0):.2f}")
        print(f"   Total Trades: {macdv_metrics.get('total_trades', 0)}")
        
        # 3. Comparación multi-worker
        print("\n3️⃣ COMPARACIÓN MULTI-WORKER")
        workers_para_comparar = ["macdv", "daily_plays", "vwap"]
        
        print(f"🔄 Comparando {len(workers_para_comparar)} workers con 8 patrones cada uno...")
        
        results = await runner.run_multi_worker_comparison(
            worker_names=workers_para_comparar,
            num_patterns=8,
            visualize=True
        )
        
        # 4. Benchmark ejecutivo
        print("\n4️⃣ BENCHMARK EJECUTIVO")
        print("🚀 Ejecutando benchmark completo...")
        
        benchmark_report = await runner.run_benchmark(
            worker_names=["macdv", "daily_plays", "vwap"],
            num_patterns=15
        )
        
        if 'error' not in benchmark_report:
            summary = benchmark_report.get('summary', {})
            print(f"\n📊 Resumen del Benchmark:")
            print(f"   Workers testados: {benchmark_report['workers_tested']}")
            print(f"   Duración: {benchmark_report['duration_seconds']:.1f} segundos")
            print(f"   Win Rate promedio: {summary.get('aggregate_win_rate', 0):.1%}")
            print(f"   Mejor performer: {summary.get('best_performer', 'N/A')}")
        
        print("\n" + "="*70)
        print("✅ DEMO PROFESIONAL COMPLETADO EXITOSAMENTE")
        print("="*70)
        print("\n💡 Para uso directo del sistema:")
        print("   python CLAUDE/trading_system_v3/backtesting_system/main.py --list-workers")
        print("   python CLAUDE/trading_system_v3/backtesting_system/main.py --worker macdv --patterns 50")
        print("   python CLAUDE/trading_system_v3/backtesting_system/main.py --benchmark --all-workers")
        print("\n📚 Ver documentación completa en el directorio backtesting_system/")
        
    except Exception as e:
        print(f"\n❌ Error ejecutando demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Configurar event loop para Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar demo
    asyncio.run(main())