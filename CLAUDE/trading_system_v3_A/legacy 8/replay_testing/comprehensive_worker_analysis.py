#!/usr/bin/env python3
"""
Análisis Comprensivo de Workers - Comparación Completa
Ejecuta replay testing para TODOS los workers contra TODOS los datos de market_data.db
"""

import sys
import os
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Any
import argparse

def get_available_workers():
    """Obtener lista de workers disponibles"""
    workers = [
        'daily_plays',
        'generic_01',
        'macdv',
        'momentum_breakout',
        'volume_absorption',
        'vwap_breakout'
    ]
    return workers

def get_available_dates(market_db_path: str):
    """Obtener fechas disponibles en market_data.db"""
    import sqlite3

    conn = sqlite3.connect(market_db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT DATE(bar_timestamp) as date
        FROM intraday_bars
        WHERE DATE(bar_timestamp) >= '2025-10-01'
        ORDER BY date
    """)

    dates = [row[0] for row in cursor.fetchall()]
    conn.close()

    return dates

def run_worker_replay(worker: str, date: str, market_db_path: str):
    """Ejecutar replay testing para un worker específico en una fecha específica"""

    cmd = [
        'python', 'replay_testing/run_replay.py',
        '--date', date,
        '--workers', worker,
        '--market-db', market_db_path,
        '--verbose'
    ]

    print(f"\n🔄 Ejecutando: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos timeout
        )

        return {
            'worker': worker,
            'date': date,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            'worker': worker,
            'date': date,
            'success': False,
            'error': 'Timeout after 5 minutes'
        }
    except Exception as e:
        return {
            'worker': worker,
            'date': date,
            'success': False,
            'error': str(e)
        }

def parse_replay_output(output: str):
    """Parsear la salida del replay testing para extraer métricas"""

    metrics = {
        'bars_processed': 0,
        'decisions_made': 0,
        'entries_approved': 0,
        'entries_rejected': 0,
        'exits_executed': 0,
        'simulated_trades': 0,
        'discrepancies': 0,
        'events_summary': {}
    }

    lines = output.split('\n')

    for line in lines:
        line = line.strip()

        # Parse global statistics
        if 'Bars processed:' in line:
            metrics['bars_processed'] = int(line.split(':')[1].strip())
        elif 'Decisions made:' in line:
            metrics['decisions_made'] = int(line.split(':')[1].strip())
        elif 'Entries approved:' in line:
            metrics['entries_approved'] = int(line.split(':')[1].strip())
        elif 'Entries rejected:' in line:
            metrics['entries_rejected'] = int(line.split(':')[1].strip())
        elif 'Exits executed:' in line:
            metrics['exits_executed'] = int(line.split(':')[1].strip())
        elif 'Simulated trades:' in line:
            metrics['simulated_trades'] = int(line.split(':')[1].strip())
        elif 'Total discrepancies:' in line:
            metrics['discrepancies'] = int(line.split(':')[1].strip())

        # Parse events summary
        elif 'decisions,' in line and 'simulated trades,' in line:
            # Example: ASST: 23 decisions, 8 simulated trades, 25 real trades ⚠️ (33 issues)
            parts = line.split(':')
            if len(parts) >= 2:
                symbol = parts[0].strip()
                rest = parts[1].strip()

                # Extract numbers
                import re
                numbers = re.findall(r'\d+', rest)

                if len(numbers) >= 3:
                    decisions = int(numbers[0])
                    simulated = int(numbers[1])
                    real = int(numbers[2])

                    metrics['events_summary'][symbol] = {
                        'decisions': decisions,
                        'simulated_trades': simulated,
                        'real_trades': real
                    }

    return metrics

def generate_comprehensive_report(results: List[Dict], market_db_path: str):
    """Generar reporte completo de análisis"""

    report = []
    report.append("=" * 100)
    report.append("📊 ANÁLISIS COMPREHENSIVO DE WORKERS - market_data.db")
    report.append("=" * 100)
    report.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Base de datos: {market_db_path}")
    report.append("")

    # Resumen ejecutivo
    report.append("📈 RESUMEN EJECUTIVO")
    report.append("-" * 50)

    successful_runs = [r for r in results if r['success']]
    failed_runs = [r for r in results if not r['success']]

    report.append(f"Total de ejecuciones: {len(results)}")
    report.append(f"Ejecuciones exitosas: {len(successful_runs)}")
    report.append(f"Ejecuciones fallidas: {len(failed_runs)}")
    report.append("")

    if failed_runs:
        report.append("❌ Ejecuciones fallidas:")
        for failure in failed_runs:
            report.append(f"   {failure['worker']} @ {failure['date']}: {failure.get('error', 'Unknown error')}")
        report.append("")

    # Análisis por worker
    workers = get_available_workers()
    worker_performance = {}

    for worker in workers:
        worker_results = [r for r in successful_runs if r['worker'] == worker]

        if not worker_results:
            continue

        # Calcular métricas agregadas
        total_simulated_trades = 0
        total_real_trades = 0
        total_decisions = 0
        total_discrepancies = 0
        dates_analyzed = len(worker_results)

        for result in worker_results:
            if 'parsed_metrics' in result:
                metrics = result['parsed_metrics']
                total_simulated_trades += metrics.get('simulated_trades', 0)
                total_decisions += metrics.get('decisions_made', 0)
                total_discrepancies += metrics.get('discrepancies', 0)

                # Contar trades reales de events_summary
                for event_data in metrics.get('events_summary', {}).values():
                    total_real_trades += event_data.get('real_trades', 0)

        worker_performance[worker] = {
            'dates_analyzed': dates_analyzed,
            'total_simulated_trades': total_simulated_trades,
            'total_real_trades': total_real_trades,
            'total_decisions': total_decisions,
            'total_discrepancies': total_discrepancies,
            'avg_trades_per_date': total_simulated_trades / dates_analyzed if dates_analyzed > 0 else 0,
            'selectivity_ratio': total_simulated_trades / total_decisions if total_decisions > 0 else 0
        }

    # Reporte por worker
    report.append("👥 ANÁLISIS POR WORKER")
    report.append("-" * 50)

    for worker, perf in sorted(worker_performance.items(), key=lambda x: x[1]['total_simulated_trades'], reverse=True):
        report.append(f"\n🔹 {worker.upper()}")
        report.append(f"   Fechas analizadas: {perf['dates_analyzed']}")
        report.append(f"   Trades simulados totales: {perf['total_simulated_trades']}")
        report.append(f"   Trades reales totales: {perf['total_real_trades']}")
        report.append(f"   Decisiones tomadas: {perf['total_decisions']}")
        report.append(f"   Discrepancias totales: {perf['total_discrepancies']}")
        report.append(f"   Trades promedio por fecha: {perf['avg_trades_per_date']:.1f}")
        report.append(f"   Ratio de selectividad: {perf['selectivity_ratio']:.3f}")

        # Interpretación
        if perf['selectivity_ratio'] > 0.1:
            report.append("   📈 Muy agresivo - genera muchas entradas")
        elif perf['selectivity_ratio'] > 0.05:
            report.append("   ⚖️ Balanceado - selectividad razonable")
        elif perf['selectivity_ratio'] > 0.01:
            report.append("   🎯 Selectivo - filtra bien las oportunidades")
        else:
            report.append("   🛡️ Muy conservador - pocas entradas")

    # Análisis de patrones
    report.append(f"\n🎯 PATRONES IDENTIFICADOS")
    report.append("-" * 50)

    # Worker más agresivo
    most_aggressive = max(worker_performance.items(), key=lambda x: x[1]['selectivity_ratio'])
    report.append(f"🐂 Worker más agresivo: {most_aggressive[0]} (ratio: {most_aggressive[1]['selectivity_ratio']:.3f})")

    # Worker más selectivo
    most_selective = min(worker_performance.items(), key=lambda x: x[1]['selectivity_ratio'])
    report.append(f"🛡️ Worker más selectivo: {most_selective[0]} (ratio: {most_selective[1]['selectivity_ratio']:.3f})")

    # Worker con más trades
    most_trades = max(worker_performance.items(), key=lambda x: x[1]['total_simulated_trades'])
    report.append(f"📊 Worker con más actividad: {most_trades[0]} ({most_trades[1]['total_simulated_trades']} trades)")

    # Recomendaciones
    report.append(f"\n💡 RECOMENDACIONES DE MEJORA")
    report.append("-" * 50)

    for worker, perf in worker_performance.items():
        report.append(f"\n🔧 {worker.upper()}:")

        selectivity = perf['selectivity_ratio']
        simulated = perf['total_simulated_trades']
        real = perf['total_real_trades']

        if selectivity > 0.1:
            report.append("   ❌ Demasiado agresivo - Aumentar filtros de entrada")
            report.append("   💡 Recomendación: Implementar validación cruzada de señales")
        elif selectivity < 0.01:
            report.append("   ❌ Demasiado conservador - Relajar criterios de entrada")
            report.append("   💡 Recomendación: Revisar umbrales de volumen y momentum")
        else:
            report.append("   ✅ Selectividad balanceada")

        if simulated > real * 2:
            report.append("   ⚠️ Genera muchas entradas falsas - Mejorar calidad de señales")
        elif real > simulated * 2:
            report.append("   ⚠️ Pierde muchas oportunidades - Optimizar criterios")

    report.append(f"\n" + "=" * 100)
    report.append("Fin del análisis comprehensivo")
    report.append("=" * 100)

    return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='Análisis comprehensivo de workers')
    parser.add_argument('--market-db', default='./market_data.db', help='Base de datos de mercado')
    parser.add_argument('--max-dates', type=int, default=5, help='Máximo número de fechas a analizar')
    parser.add_argument('--workers', nargs='+', help='Workers específicos a analizar')
    parser.add_argument('--output', default='replay_testing/reports/comprehensive_analysis.txt', help='Archivo de salida')

    args = parser.parse_args()

    # Obtener workers y fechas disponibles
    workers = args.workers if args.workers else get_available_workers()
    dates = get_available_dates(args.market_db)[:args.max_dates]  # Limitar fechas

    print(f"🔍 Iniciando análisis comprehensivo...")
    print(f"Workers a analizar: {', '.join(workers)}")
    print(f"Fechas disponibles: {len(dates)} (usando primeras {args.max_dates})")
    print(f"Total de ejecuciones: {len(workers) * len(dates)}")

    # Ejecutar análisis para cada combinación worker-fecha
    results = []

    for worker in workers:
        for date in dates:
            result = run_worker_replay(worker, date, args.market_db)

            # Parsear métricas si fue exitoso
            if result['success'] and result['stdout']:
                result['parsed_metrics'] = parse_replay_output(result['stdout'])

            results.append(result)

            # Mostrar progreso
            status = "✅" if result['success'] else "❌"
            print(f"{status} {worker} @ {date}")

    # Generar reporte completo
    report = generate_comprehensive_report(results, args.market_db)

    # Guardar reporte
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📄 Reporte guardado en: {args.output}")
    print(f"📊 Resumen: {len([r for r in results if r['success']])}/{len(results)} ejecuciones exitosas")

    # Mostrar resumen en consola
    print("\n" + "="*50)
    print("RESUMEN EJECUTIVO")
    print("="*50)

    successful_runs = [r for r in results if r['success']]
    if successful_runs:
        # Mostrar top 3 workers por actividad
        worker_stats = {}
        for result in successful_runs:
            worker = result['worker']
            if 'parsed_metrics' in result:
                trades = result['parsed_metrics'].get('simulated_trades', 0)
                worker_stats[worker] = worker_stats.get(worker, 0) + trades

        top_workers = sorted(worker_stats.items(), key=lambda x: x[1], reverse=True)[:3]
        print("🏆 Top 3 workers por actividad:")
        for i, (worker, trades) in enumerate(top_workers, 1):
            print(f"   {i}. {worker}: {trades} trades simulados")

if __name__ == "__main__":
    main()