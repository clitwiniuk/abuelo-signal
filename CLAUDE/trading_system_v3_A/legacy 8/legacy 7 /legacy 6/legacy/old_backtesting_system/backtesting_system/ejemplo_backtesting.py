#!/usr/bin/env python3
"""
Ejemplo de Uso del Sistema de Backtesting
========================================

Script de ejemplo que demuestra todas las funcionalidades del sistema
de backtesting para workers de trading.
"""

import asyncio
import logging
from datetime import datetime

# Importar el sistema de backtesting
import sys
import os
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS')
sys.path.append('/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/tests')
from run_backtest_intraday import BacktestRunner

# Importar módulos de testing
try:
    from tests.pattern_generator import PatternGenerator
    from tests.worker_tester import WorkerTester
    from tests.metrics_calculator import MetricsCalculator
    from tests.visualization_utils import VisualizationUtils
except ImportError as e:
    print(f"⚠️ Error importando módulos de testing: {e}")
    print("   Algunas funcionalidades pueden no estar disponibles")
    # Crear mocks simples para evitar errores
    PatternGenerator = None
    WorkerTester = None
    MetricsCalculator = None
    VisualizationUtils = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def ejemplo_basico():
    """Ejemplo básico de uso del sistema"""
    print("🚀 EJEMPLO BÁSICO - Testing de Worker Individual")
    print("="*60)
    
    # Crear runner
    runner = BacktestRunner()
    
    # Listar workers disponibles
    print("\n📋 Workers disponibles:")
    runner.list_available_workers()
    
    # Probar un worker específico con pocos patrones para demo rápido
    print("\n🧪 Probando worker MACDV con 20 patrones...")
    metrics = await runner.run_single_worker_test(
        worker_name="macdv",
        num_patterns=20,  # Pocos patrones para demo rápido
        visualize=False,  # Sin visualización en demo
        detailed=True     # Mostrar detalles
    )
    
    # Mostrar resultados principales
    print(f"\n📊 Resultados MACDV Worker:")
    print(f"   Win Rate: {metrics.get('win_rate', 0):.1%}")
    print(f"   Average Return: {metrics.get('avg_return', 0):+.2f}%")
    print(f"   Profit Factor: {metrics.get('profit_factor', 0):.2f}")
    print(f"   Total Trades: {metrics.get('total_trades', 0)}")
    
    return metrics


async def ejemplo_comparacion():
    """Ejemplo de comparación entre workers"""
    print("\n\n🏁 EJEMPLO COMPARACIÓN - Múltiples Workers")
    print("="*60)
    
    runner = BacktestRunner()
    
    # Probar múltiples workers en paralelo
    workers_para_comparar = ["macdv", "daily_plays", "vwap"]
    
    print(f"🔄 Comparando {len(workers_para_comparar)} workers con 15 patrones cada uno...")
    
    results = await runner.run_multi_worker_comparison(
        worker_names=workers_para_comparar,
        num_patterns=15,  # Pocos patrones para demo rápido
        visualize=False   # Sin visualización en demo
    )
    
    # Mostrar comparación
    print("\n📊 Resultados de la Comparación:")
    for worker_name, metrics in results.items():
        if 'error' not in metrics:
            print(f"   {worker_name:<15}: Win Rate {metrics.get('win_rate', 0):.1%}, "
                  f"Avg Return {metrics.get('avg_return', 0):+.2f}%")
        else:
            print(f"   {worker_name:<15}: ERROR - {metrics['error']}")
    
    return results


async def ejemplo_patrones_personalizados():
    """Ejemplo con patrones sintéticos personalizados"""
    print("\n\n🎯 EJEMPLO PATRONES PERSONALIZADOS")
    print("="*60)
    
    if PatternGenerator is None:
        print("⚠️ PatternGenerator no disponible - saltando ejemplo")
        return None
    
    # Crear generador de patrones personalizado
    generator = PatternGenerator(seed=123)  # Seed para reproducibilidad
    
    # Generar patrones específicos
    print("📊 Generando patrones sintéticos...")
    
    # Solo patrones Gap-Go
    gap_go_patterns = generator.generate_patterns_by_type('gap_go', 10)
    print(f"   Gap-Go patterns: {len(gap_go_patterns)}")
    
    # Mezcla de patrones
    mixed_patterns = generator.generate_mixed_patterns(20)
    print(f"   Mixed patterns: {len(mixed_patterns)}")
    
    # Resumen de patrones generados
    summary = generator.get_pattern_summary(mixed_patterns)
    print(f"\n📈 Resumen de Patrones:")
    print(f"   Total: {summary['total_patterns']}")
    print(f"   Quality promedio: {summary['quality_stats']['mean']:.1f}")
    print(f"   Gap promedio: {summary['gap_stats']['mean']:.1f}%")
    
    # Probar worker específico con estos patrones
    tester = WorkerTester("macdv", None)  # Usar mock worker
    print(f"\n🧪 Testing con patrones personalizados...")
    
    results = await tester.run_comprehensive_test(mixed_patterns, detailed=False)
    
    print(f"   Tests ejecutados: {results.successful_tests}")
    print(f"   Trades realizados: {results.trades_executed}")
    print(f"   Win rate: {results.winning_trades / max(1, results.trades_executed):.1%}")
    
    return results


async def ejemplo_metricas_avanzadas():
    """Ejemplo de análisis detallado de métricas"""
    print("\n\n📊 EJEMPLO MÉTRICAS AVANZADAS")
    print("="*60)
    
    if MetricsCalculator is None:
        print("⚠️ MetricsCalculator no disponible - saltando ejemplo")
        return None
    
    # Crear calculadora de métricas
    calculator = MetricsCalculator()
    
    # Simular datos de trades para análisis detallado
    trades_data = []
    import random
    random.seed(42)
    
    # Generar 50 trades simulados
    for i in range(50):
        pnl = random.normalvariate(0.08, 0.15)  # 8% promedio, 15% std
        hold_time = random.uniform(30, 180)     # 30 min a 3 horas
        exit_reason = random.choice(['profit_target', 'stop_loss', 'time_limit'])
        
        trades_data.append({
            'trade_id': i,
            'pnl': pnl,
            'hold_time': hold_time,
            'exit_reason': exit_reason,
            'pattern_type': random.choice(['gap_go', 'bull_flag', 'macdv'])
        })
    
    # Calcular estadísticas detalladas
    stats = calculator.calculate_trade_statistics(trades_data)
    
    print(f"📈 Análisis de {len(trades_data)} Trades:")
    print(f"   Win Rate: {stats['win_rate']:.1%}")
    print(f"   PnL Promedio: {stats['avg_pnl']:+.2f}%")
    print(f"   PnL Mediano: {stats['median_pnl']:+.2f}%")
    print(f"   Mejor Trade: {stats['max_pnl']:+.2f}%")
    print(f"   Peor Trade: {stats['min_pnl']:+.2f}%")
    print(f"   Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
    print(f"   VaR (95%): {stats['var_95']:+.2f}%")
    
    print(f"\n⏰ Tiempos de Operación:")
    print(f"   Hold Time Promedio: {stats['avg_hold_time']:.1f} minutos")
    print(f"   Hold Time Mediano: {stats['median_hold_time']:.1f} minutos")
    
    print(f"\n🚪 Razones de Salida:")
    for reason, count in stats['exit_reason_distribution'].items():
        print(f"   {reason}: {count} trades ({count/len(trades_data)*100:.1f}%)")
    
    # Generar reporte textual
    sample_metrics = {
        'win_rate': stats['win_rate'],
        'avg_return': stats['avg_pnl'],
        'profit_factor': 1.5,  # Simulado
        'total_trades': len(trades_data),
        'avg_signal_quality': 70.0,  # Simulado
        'avg_response_time': 0.05,   # Simulado
        'benchmark_worker': 'macdv',
        'win_rate_vs_benchmark': 0.02,
        'benchmark_performance': 'above'
    }
    
    report = calculator.generate_performance_report(sample_metrics, "DemoWorker")
    print(f"\n📄 Reporte Generado:")
    print(report)
    
    return stats


async def ejemplo_visualizacion():
    """Ejemplo de generación de visualizaciones"""
    print("\n\n📊 EJEMPLO VISUALIZACIÓN")
    print("="*60)
    
    if VisualizationUtils is None:
        print("⚠️ VisualizationUtils no disponible - saltando ejemplo")
        return None
    
    # Crear visualizador
    visualizer = VisualizationUtils(output_dir="demo_charts")
    
    # Simular datos para visualización
    class MockResults:
        def __init__(self):
            self.response_times = [0.05, 0.08, 0.03, 0.12, 0.07] * 4
            self.pattern_type_results = {
                'gap_go': {'count': 20, 'wins': 12, 'total_pnl': 2.5},
                'bull_flag': {'count': 15, 'wins': 9, 'total_pnl': 1.8},
                'macdv': {'count': 18, 'wins': 11, 'total_pnl': 2.1}
            }
    
    mock_results = MockResults()
    mock_metrics = {
        'win_rate': 0.62,
        'avg_return': 0.08,
        'profit_factor': 1.4,
        'total_trades': 53,
        'avg_signal_quality': 72.5,
        'execution_rate': 0.85
    }
    
    print("🎨 Generando gráficos de análisis para worker...")
    
    try:
        await visualizer.create_worker_analysis_charts("demo_worker", mock_results, mock_metrics)
        print("✅ Gráficos generados exitosamente")
        print(f"   Directorio: {visualizer.output_dir}")
    except Exception as e:
        print(f"⚠️ Error generando gráficos: {e}")
        print("   (Nota: Esto es normal si matplotlib no está disponible)")
    
    # Crear comparación
    comparison_data = {
        'worker_a': {'win_rate': 0.68, 'avg_return': 0.09, 'profit_factor': 1.5},
        'worker_b': {'win_rate': 0.62, 'avg_return': 0.08, 'profit_factor': 1.3},
        'worker_c': {'win_rate': 0.65, 'avg_return': 0.07, 'profit_factor': 1.4}
    }
    
    print("\n🎨 Generando gráficos de comparación...")
    try:
        await visualizer.create_worker_comparison_charts(comparison_data)
        print("✅ Gráficos de comparación generados")
    except Exception as e:
        print(f"⚠️ Error generando comparación: {e}")
    
    # Crear dashboard resumen
    dashboard = visualizer.create_summary_dashboard(comparison_data)
    print(f"\n📋 Dashboard Resumen:")
    print(dashboard)


async def ejemplo_benchmark():
    """Ejemplo de benchmark completo"""
    print("\n\n🚀 EJEMPLO BENCHMARK COMPLETO")
    print("="*60)
    
    runner = BacktestRunner()
    
    # Ejecutar benchmark con workers principales
    workers_benchmark = ["macdv", "daily_plays", "vwap"]
    
    print(f"📊 Ejecutando benchmark con {len(workers_benchmark)} workers")
    print(f"   Workers: {', '.join(workers_benchmark)}")
    print(f"   Patrones por worker: 25")
    
    try:
        benchmark_report = await runner.run_benchmark(
            worker_names=workers_benchmark,
            num_patterns=25
        )
        
        print(f"\n✅ Benchmark completado en {benchmark_report['duration_seconds']:.1f} segundos")
        print(f"📄 Reporte guardado en archivo JSON")
        
        # Mostrar resumen del benchmark
        results = benchmark_report['results']
        print(f"\n📊 Resultados del Benchmark:")
        for worker_name, metrics in results.items():
            if 'error' not in metrics:
                print(f"   {worker_name:<15}: Win {metrics.get('win_rate', 0):.1%}, "
                      f"Return {metrics.get('avg_return', 0):+.2f}%, "
                      f"PF {metrics.get('profit_factor', 0):.2f}")
            else:
                print(f"   {worker_name:<15}: ERROR")
        
        return benchmark_report
        
    except Exception as e:
        print(f"❌ Error ejecutando benchmark: {e}")
        return None


async def main():
    """Función principal que ejecuta todos los ejemplos"""
    print("🎯 DEMO COMPLETO - Sistema de Backtesting para Workers")
    print("="*70)
    print(f"⏰ Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        # 1. Ejemplo básico (siempre disponible)
        await ejemplo_basico()
        
        # 2. Comparación de workers (siempre disponible)
        await ejemplo_comparacion()
        
        # 3. Patrones personalizados (requiere PatternGenerator)
        result = await ejemplo_patrones_personalizados()
        if result is not None:
            print("✅ Patrones personalizados completados")
        
        # 4. Métricas avanzadas (requiere MetricsCalculator)
        result = await ejemplo_metricas_avanzadas()
        if result is not None:
            print("✅ Métricas avanzadas completadas")
        
        # 5. Visualizaciones (requiere VisualizationUtils)
        result = await ejemplo_visualizacion()
        if result is not None:
            print("✅ Visualizaciones completadas")
        
        # 6. Benchmark completo (siempre disponible)
        await ejemplo_benchmark()
        
        print("\n\n" + "="*70)
        print("✅ DEMO COMPLETADO EXITOSAMENTE")
        print("="*70)
        print("\n💡 Para usar en producción:")
        print("   1. cd tests && python run_backtest_intraday.py --worker macdv --patterns 100")
        print("   2. cd tests && python run_backtest_intraday.py --benchmark --all-workers")
        print("   3. cd tests && python run_backtest_intraday.py --workers macdv,daily_plays --visualize")
        print("\n📚 Ver README_backtesting.md para documentación completa")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error ejecutando demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Configurar event loop para Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar demo
    asyncio.run(main())