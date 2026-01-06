#!/usr/bin/env python3
"""
Ejecutor Especializado de Tests de Performance y Rendimiento
Ejecuta tests de stress, límites y optimización de performance
"""

import os
import sys
import subprocess
import time
import psutil
from datetime import datetime
from pathlib import Path
import json
import threading

class PerformanceMonitor:
    """Monitor de performance durante la ejecución de tests"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'peak_memory_mb': 0,
            'avg_cpu_percent': 0
        }
    
    def start_monitoring(self):
        """Iniciar monitoreo de recursos"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Detener monitoreo de recursos"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1)
        
        # Calcular métricas finales
        if self.metrics['cpu_usage']:
            self.metrics['avg_cpu_percent'] = sum(self.metrics['cpu_usage']) / len(self.metrics['cpu_usage'])
        
        if self.metrics['memory_usage']:
            self.metrics['peak_memory_mb'] = max(self.metrics['memory_usage'])
    
    def _monitor_resources(self):
        """Monitorear recursos del sistema"""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = process.cpu_percent()
                self.metrics['cpu_usage'].append(cpu_percent)
                
                # Memory usage
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
                self.metrics['memory_usage'].append(memory_mb)
                
                time.sleep(1)  # Monitor every second
                
            except Exception:
                # Process might have ended
                break

def run_performance_test_suite():
    """Ejecutar suite completa de tests de performance"""
    print("⚡ EJECUTANDO TESTS DE PERFORMANCE Y RENDIMIENTO")
    print("=" * 60)
    print(f"🕐 Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Tests de performance ordenados por intensidad
    performance_tests = [
        {
            'category': 'ADVANCED_PERFORMANCE',
            'script': 'advanced/test_trades_advanced.py',
            'name': 'Tests Avanzados de Performance',
            'description': 'Concurrencia, queries complejas, rendimiento básico',
            'timeout': 300,  # 5 minutos
            'intensity': 'MEDIUM',
            'expected_metrics': {
                'min_trades_per_second': 1000,
                'max_memory_mb': 300,
                'max_duration_minutes': 5
            }
        },
        {
            'category': 'STRESS_TESTING',
            'script': 'performance/test_stress_limits.py',
            'name': 'Tests de Stress y Límites',
            'description': 'Stress testing, memory leaks, límites del sistema',
            'timeout': 600,  # 10 minutos
            'intensity': 'HIGH',
            'expected_metrics': {
                'min_trades_processed': 10000,
                'max_memory_mb': 500,
                'max_duration_minutes': 10
            }
        },
        {
            'category': 'SIMULATION_PERFORMANCE',
            'script': 'simulation/test_trading_simulation.py',
            'name': 'Performance de Simulación de Trading',
            'description': 'Simulación realista, múltiples estrategias',
            'timeout': 420,  # 7 minutos
            'intensity': 'HIGH',
            'expected_metrics': {
                'min_trades_simulated': 100,
                'max_memory_mb': 400,
                'max_duration_minutes': 7
            }
        },
        {
            'category': 'NETWORK_PERFORMANCE',
            'script': 'network/test_network_resilience.py',
            'name': 'Performance de Red y Conectividad',
            'description': 'Latencia, timeouts, pool de conexiones',
            'timeout': 300,  # 5 minutos
            'intensity': 'MEDIUM',
            'expected_metrics': {
                'max_latency_adaptation_time': 2.0,
                'min_concurrent_connections': 15,
                'max_duration_minutes': 5
            }
        }
    ]
    
    results = []
    start_time = time.time()
    overall_metrics = {
        'total_trades_processed': 0,
        'peak_memory_usage_mb': 0,
        'total_cpu_time': 0,
        'performance_issues': []
    }
    
    # Monitor general del sistema
    system_monitor = PerformanceMonitor()
    system_monitor.start_monitoring()
    
    for test in performance_tests:
        print(f"\n{'='*80}")
        print(f"🚀 EJECUTANDO: {test['name']}")
        print(f"📂 Categoría: {test['category']}")
        print(f"🎯 Descripción: {test['description']}")
        print(f"⚡ Intensidad: {test['intensity']}")
        print(f"📝 Script: {test['script']}")
        print(f"⏱️  Timeout: {test['timeout']/60:.1f} minutos")
        print(f"{'='*80}")
        
        test_start = time.time()
        test_monitor = PerformanceMonitor()
        test_monitor.start_monitoring()
        
        try:
            # Verificar que el script existe
            script_path = Path(__file__).parent / test['script']
            if not script_path.exists():
                print(f"❌ ERROR: Script no encontrado: {test['script']}")
                results.append({
                    'name': test['name'],
                    'category': test['category'],
                    'success': False,
                    'error': f"Script no encontrado: {test['script']}",
                    'execution_time': 0,
                    'performance_metrics': {},
                    'meets_expectations': False
                })
                continue
            
            # Ejecutar test de performance
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, timeout=test['timeout'])
            
            execution_time = time.time() - test_start
            test_monitor.stop_monitoring()
            
            # Mostrar output
            if result.stdout:
                print(result.stdout)
            
            # Extraer métricas de performance del output
            performance_metrics = extract_performance_metrics(result.stdout, test['category'])
            
            # Agregar métricas de monitoreo
            performance_metrics.update({
                'execution_time_minutes': execution_time / 60,
                'peak_memory_mb': test_monitor.metrics['peak_memory_mb'],
                'avg_cpu_percent': test_monitor.metrics['avg_cpu_percent']
            })
            
            if result.stderr and result.returncode != 0:
                print(f"❌ ERRORES:\n{result.stderr}")
            
            success = result.returncode == 0
            
            # Evaluar si cumple expectativas de performance
            meets_expectations = evaluate_performance_expectations(
                performance_metrics, 
                test['expected_metrics']
            )
            
            result_data = {
                'name': test['name'],
                'category': test['category'],
                'intensity': test['intensity'],
                'success': success,
                'execution_time': execution_time,
                'return_code': result.returncode,
                'performance_metrics': performance_metrics,
                'meets_expectations': meets_expectations,
                'expected_metrics': test['expected_metrics']
            }
            
            results.append(result_data)
            
            # Actualizar métricas generales
            overall_metrics['peak_memory_usage_mb'] = max(
                overall_metrics['peak_memory_usage_mb'],
                performance_metrics.get('peak_memory_mb', 0)
            )
            
            overall_metrics['total_trades_processed'] += performance_metrics.get('trades_processed', 0)
            overall_metrics['total_cpu_time'] += performance_metrics.get('avg_cpu_percent', 0) * execution_time
            
            # Status específico para tests de performance
            if success and meets_expectations:
                print(f"\n🎯 {test['name']}: EXCELENTE PERFORMANCE")
                print(f"✅ Cumple todas las expectativas de rendimiento")
            elif success and not meets_expectations:
                print(f"\n⚠️  {test['name']}: PERFORMANCE SUBÓPTIMA")
                print(f"⚠️  No cumple algunas expectativas de rendimiento")
                overall_metrics['performance_issues'].append(f"Suboptimal performance in {test['name']}")
            else:
                print(f"\n❌ {test['name']}: FALLÓ - Performance crítica comprometida")
                overall_metrics['performance_issues'].append(f"Critical failure in {test['name']}")
            
            print(f"⏱️  Tiempo de ejecución: {execution_time/60:.1f} minutos")
            print(f"💾 Memoria pico: {performance_metrics.get('peak_memory_mb', 0):.1f} MB")
            
            # Mostrar métricas específicas importantes
            show_key_metrics(performance_metrics, test['category'])
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - test_start
            test_monitor.stop_monitoring()
            
            print(f"\n⏰ TIMEOUT: {test['name']} excedió {test['timeout']/60:.1f} minutos")
            print(f"⚠️  Performance crítica: Test muy lento")
            
            overall_metrics['performance_issues'].append(f"Timeout in {test['name']} - performance critical")
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'intensity': test['intensity'],
                'success': False,
                'error': f"Timeout después de {test['timeout']/60:.1f} minutos",
                'execution_time': execution_time,
                'performance_metrics': {
                    'execution_time_minutes': execution_time / 60,
                    'peak_memory_mb': test_monitor.metrics['peak_memory_mb']
                },
                'meets_expectations': False
            })
            
        except Exception as e:
            execution_time = time.time() - test_start
            test_monitor.stop_monitoring()
            
            print(f"\n❌ ERROR ejecutando {test['name']}: {e}")
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'intensity': test['intensity'],
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'performance_metrics': {},
                'meets_expectations': False
            })
    
    # Detener monitor general
    system_monitor.stop_monitoring()
    total_time = time.time() - start_time
    
    # Análisis final de performance
    print(f"\n{'='*80}")
    print("⚡ ANÁLISIS DE PERFORMANCE COMPLETADO")
    print(f"{'='*80}")
    
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    performance_compliant = sum(1 for r in results if r.get('meets_expectations', False))
    
    print(f"⏱️  Tiempo total: {total_time/60:.1f} minutos")
    print(f"📊 Tests de performance ejecutados: {total_tests}")
    print(f"✅ Tests exitosos: {successful_tests}")
    print(f"🎯 Tests con performance óptima: {performance_compliant}")
    print(f"❌ Tests fallidos: {total_tests - successful_tests}")
    print(f"📈 Tasa de éxito: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
    print(f"🚀 Tasa de performance óptima: {performance_compliant/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
    
    # Métricas generales de performance
    print(f"\n📊 MÉTRICAS GENERALES DE PERFORMANCE:")
    print(f"💾 Memoria pico del sistema: {system_monitor.metrics['peak_memory_mb']:.1f} MB")
    print(f"🔢 Total trades procesados: {overall_metrics['total_trades_processed']:,}")
    print(f"⚠️  Problemas de performance detectados: {len(overall_metrics['performance_issues'])}")
    
    # Detalles por categoría
    print(f"\n📋 PERFORMANCE POR CATEGORÍA:")
    for result in results:
        metrics = result['performance_metrics']
        expectations = result.get('meets_expectations', False)
        
        status_emoji = "🎯" if expectations else ("⚠️" if result['success'] else "❌")
        performance_status = "ÓPTIMA" if expectations else ("SUBÓPTIMA" if result['success'] else "CRÍTICA")
        
        print(f"   {status_emoji} {result['category']}: {performance_status}")
        
        # Mostrar métricas clave
        if 'execution_time_minutes' in metrics:
            print(f"      ⏱️  Tiempo: {metrics['execution_time_minutes']:.1f}min")
        if 'peak_memory_mb' in metrics:
            print(f"      💾 Memoria: {metrics['peak_memory_mb']:.1f}MB")
        
        # Mostrar métricas específicas por categoría
        if result['category'] == 'ADVANCED_PERFORMANCE':
            trades_per_sec = metrics.get('trades_per_second', 0)
            if trades_per_sec > 0:
                print(f"      🚀 Velocidad: {trades_per_sec:.0f} trades/seg")
        
        elif result['category'] == 'STRESS_TESTING':
            trades_processed = metrics.get('total_trades_processed', 0)
            if trades_processed > 0:
                print(f"      📈 Trades procesados: {trades_processed:,}")
    
    # Evaluación final de performance
    overall_performance_score = calculate_performance_score(results, overall_metrics)
    
    print(f"\n⚡ EVALUACIÓN FINAL DE PERFORMANCE:")
    print(f"📊 Puntuación de performance: {overall_performance_score:.1f}/100")
    
    if overall_performance_score >= 90:
        print("🏆 PERFORMANCE EXCELENTE")
        print("✅ Sistema altamente optimizado")
        print("🚀 Listo para cargas de trabajo intensivas")
        performance_grade = "A+"
    elif overall_performance_score >= 80:
        print("👍 PERFORMANCE BUENA")
        print("✅ Sistema bien optimizado")
        print("📊 Algunas optimizaciones menores recomendadas")
        performance_grade = "A"
    elif overall_performance_score >= 70:
        print("⚠️  PERFORMANCE MODERADA")
        print("🔧 Necesita optimizaciones")
        print("📉 Performance puede afectar UX bajo carga")
        performance_grade = "B"
    elif overall_performance_score >= 50:
        print("📉 PERFORMANCE BAJA")
        print("🔧 Optimizaciones críticas requeridas")
        print("⚠️  Sistema lento bajo carga normal")
        performance_grade = "C"
    else:
        print("🚨 PERFORMANCE CRÍTICA")
        print("❌ Sistema severamente lento")
        print("🛑 NO apto para uso en producción")
        performance_grade = "F"
    
    # Recomendaciones específicas de performance
    print(f"\n💡 RECOMENDACIONES DE OPTIMIZACIÓN:")
    
    if overall_metrics['peak_memory_usage_mb'] > 400:
        print("💾 Optimizar uso de memoria - implementar memory pooling")
    
    slow_tests = [r for r in results if r['performance_metrics'].get('execution_time_minutes', 0) > 3]
    if slow_tests:
        print("⏱️  Optimizar tests lentos - implementar caching o paralelización")
    
    low_throughput_tests = [r for r in results if r['performance_metrics'].get('trades_per_second', float('inf')) < 500]
    if low_throughput_tests:
        print("🚀 Optimizar throughput de base de datos - revisar queries e índices")
    
    if len(overall_metrics['performance_issues']) > 0:
        print("🔧 Investigar y resolver problemas específicos de performance")
        for issue in overall_metrics['performance_issues'][:3]:  # Top 3 issues
            print(f"   • {issue}")
    
    # Generar reporte de performance
    try:
        performance_report = {
            'timestamp': datetime.now().isoformat(),
            'execution_time_minutes': total_time / 60,
            'performance_score': overall_performance_score,
            'performance_grade': performance_grade,
            'system_metrics': {
                'peak_memory_mb': system_monitor.metrics['peak_memory_mb'],
                'avg_cpu_percent': system_monitor.metrics['avg_cpu_percent'],
                'total_trades_processed': overall_metrics['total_trades_processed']
            },
            'tests_summary': {
                'total': total_tests,
                'passed': successful_tests,
                'performance_compliant': performance_compliant,
                'failed': total_tests - successful_tests
            },
            'performance_issues': overall_metrics['performance_issues'],
            'detailed_results': results
        }
        
        report_filename = f"performance_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = Path(__file__).parent / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(performance_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte de performance guardado: {report_filename}")
        
    except Exception as e:
        print(f"⚠️  No se pudo guardar el reporte de performance: {e}")
    
    # Determinar exit code
    if overall_performance_score >= 70 and successful_tests == total_tests:
        exit_code = 0  # Good performance
    elif overall_performance_score >= 50 and successful_tests >= total_tests * 0.75:
        exit_code = 1  # Acceptable performance with improvements needed
    else:
        exit_code = 2  # Poor performance or critical failures
    
    print(f"\n🏁 Análisis de performance completado en {total_time/60:.1f} minutos")
    
    return exit_code

def extract_performance_metrics(output: str, category: str) -> dict:
    """Extraer métricas de performance del output"""
    metrics = {}
    
    if not output:
        return metrics
    
    lines = output.split('\n')
    
    for line in lines:
        # Trades per second
        if 'trades/segundo' in line:
            try:
                parts = line.split()
                for i, part in enumerate(parts):
                    if 'trades/segundo' in part and i > 0:
                        speed = float(parts[i-1].replace(',', '').replace(':', ''))
                        metrics['trades_per_second'] = speed
                        break
            except:
                pass
        
        # Total trades processed
        if 'trades' in line.lower() and any(word in line.lower() for word in ['procesados', 'insertados', 'generados']):
            try:
                import re
                numbers = re.findall(r'(\d+(?:,\d+)*)', line)
                if numbers:
                    trades_count = int(numbers[0].replace(',', ''))
                    metrics['trades_processed'] = trades_count
            except:
                pass
        
        # Memory usage
        if 'mb' in line.lower() and any(word in line.lower() for word in ['memoria', 'memory', 'pico', 'peak']):
            try:
                import re
                mb_matches = re.findall(r'(\d+\.?\d*)\s*mb', line.lower())
                if mb_matches:
                    metrics['peak_memory_test_mb'] = float(mb_matches[0])
            except:
                pass
        
        # Success rates
        if 'resultado final:' in line.lower() or 'tests pasaron' in line.lower():
            try:
                import re
                match = re.search(r'(\d+)/(\d+)', line)
                if match:
                    passed = int(match.group(1))
                    total = int(match.group(2))
                    metrics['test_success_rate'] = passed / total if total > 0 else 0
            except:
                pass
    
    return metrics

def show_key_metrics(metrics: dict, category: str):
    """Mostrar métricas clave según la categoría"""
    if category == 'ADVANCED_PERFORMANCE':
        if 'trades_per_second' in metrics:
            speed = metrics['trades_per_second']
            if speed >= 1500:
                print(f"🚀 Velocidad excelente: {speed:.0f} trades/segundo")
            elif speed >= 1000:
                print(f"👍 Velocidad buena: {speed:.0f} trades/segundo")
            else:
                print(f"⚠️  Velocidad baja: {speed:.0f} trades/segundo")
    
    elif category == 'STRESS_TESTING':
        if 'trades_processed' in metrics:
            processed = metrics['trades_processed']
            if processed >= 10000:
                print(f"📈 Alto throughput: {processed:,} trades procesados")
            elif processed >= 5000:
                print(f"📊 Throughput moderado: {processed:,} trades procesados")
            else:
                print(f"📉 Bajo throughput: {processed:,} trades procesados")

def evaluate_performance_expectations(metrics: dict, expected: dict) -> bool:
    """Evaluar si las métricas cumplen las expectativas"""
    if not expected:
        return True
    
    checks = []
    
    # Check minimum trades per second
    if 'min_trades_per_second' in expected:
        actual = metrics.get('trades_per_second', 0)
        expected_min = expected['min_trades_per_second']
        checks.append(actual >= expected_min)
    
    # Check maximum memory usage
    if 'max_memory_mb' in expected:
        actual = metrics.get('peak_memory_mb', 0)
        expected_max = expected['max_memory_mb']
        checks.append(actual <= expected_max)
    
    # Check maximum duration
    if 'max_duration_minutes' in expected:
        actual = metrics.get('execution_time_minutes', 0)
        expected_max = expected['max_duration_minutes']
        checks.append(actual <= expected_max)
    
    # Check minimum trades processed
    if 'min_trades_processed' in expected:
        actual = metrics.get('trades_processed', 0)
        expected_min = expected['min_trades_processed']
        checks.append(actual >= expected_min)
    
    # All checks must pass
    return all(checks) if checks else True

def calculate_performance_score(results: list, overall_metrics: dict) -> float:
    """Calcular puntuación de performance"""
    base_score = 100.0
    
    # Penalizar por tests fallidos
    failed_tests = sum(1 for r in results if not r['success'])
    total_tests = len(results)
    
    if total_tests > 0:
        failure_penalty = (failed_tests / total_tests) * 40  # Hasta -40 puntos
        base_score -= failure_penalty
    
    # Penalizar por expectativas no cumplidas
    expectation_failures = sum(1 for r in results if not r.get('meets_expectations', True))
    
    if total_tests > 0:
        expectation_penalty = (expectation_failures / total_tests) * 25  # Hasta -25 puntos
        base_score -= expectation_penalty
    
    # Penalizar por problemas específicos de performance
    performance_issues = len(overall_metrics.get('performance_issues', []))
    performance_penalty = min(performance_issues * 10, 30)  # Hasta -30 puntos
    base_score -= performance_penalty
    
    # Bonus por alta performance
    high_performance_tests = sum(1 for r in results if r.get('meets_expectations', False) and r['success'])
    if total_tests > 0 and high_performance_tests == total_tests:
        base_score += 10  # Bonus por performance perfecta
    
    return max(0.0, base_score)

if __name__ == "__main__":
    exit_code = run_performance_test_suite()
    sys.exit(exit_code)