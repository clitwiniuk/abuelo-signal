#!/usr/bin/env python3
"""
Script Maestro Organizado para Ejecutar TODOS los Tests del Sistema de Trading
Con estructura organizada por categorías y reportes comprehensivos
"""

import os
import sys
import subprocess
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

def setup_argument_parser():
    """Configurar parser de argumentos"""
    parser = argparse.ArgumentParser(
        description="Ejecutar suite completa de tests organizados del sistema de trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python run_all_tests_organized.py                    # Ejecutar todos los tests
  python run_all_tests_organized.py --category basic   # Solo tests básicos
  python run_all_tests_organized.py --quick            # Solo tests críticos
  python run_all_tests_organized.py --performance      # Solo tests de performance
  python run_all_tests_organized.py --security         # Solo tests de seguridad
  python run_all_tests_organized.py --timeout 900      # Timeout personalizado (15 min)
  python run_all_tests_organized.py --report-only      # Solo generar reporte
        """
    )
    
    parser.add_argument(
        '--category', 
        choices=['basic', 'advanced', 'performance', 'security', 'integration', 
                'simulation', 'recovery', 'configuration', 'network'],
        help='Ejecutar solo tests de una categoría específica'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Ejecutar solo tests críticos (básicos, seguridad, configuración)'
    )
    
    parser.add_argument(
        '--performance',
        action='store_true',
        help='Ejecutar solo tests de performance y rendimiento'
    )
    
    parser.add_argument(
        '--security',
        action='store_true',
        help='Ejecutar solo tests de seguridad y robustez'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Timeout en segundos para cada test individual (default: 600)'
    )
    
    parser.add_argument(
        '--report-only',
        action='store_true',
        help='Solo generar reporte final sin ejecutar tests'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Modo silencioso - solo mostrar resumen'
    )
    
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='No limpiar datos de test después de la ejecución'
    )
    
    return parser

class TestExecutor:
    """Ejecutor principal de tests organizados"""
    
    def __init__(self, args):
        self.args = args
        self.base_path = Path(__file__).parent
        self.results = []
        self.start_time = time.time()
        
        # Definir estructura completa de tests organizados
        self.test_categories = {
            'basic': {
                'name': 'Tests Básicos',
                'description': 'Funcionalidad fundamental del sistema',
                'priority': 'CRITICAL',
                'tests': [
                    {
                        'script': 'basic/test_trades_history.py',
                        'name': 'Validación Básica de Trades',
                        'timeout': 120,
                        'critical': True
                    }
                ]
            },
            'advanced': {
                'name': 'Tests Avanzados',
                'description': 'Características avanzadas y optimizaciones',
                'priority': 'HIGH',
                'tests': [
                    {
                        'script': 'advanced/test_trades_advanced.py',
                        'name': 'Tests Avanzados y Rendimiento',
                        'timeout': 300,
                        'critical': False
                    },
                    {
                        'script': 'advanced/test_trades_migration.py',
                        'name': 'Tests de Migración y Mantenimiento',
                        'timeout': 180,
                        'critical': False
                    }
                ]
            },
            'performance': {
                'name': 'Tests de Performance',
                'description': 'Evaluación de límites y capacidad',
                'priority': 'MEDIUM',
                'tests': [
                    {
                        'script': 'performance/test_stress_limits.py',
                        'name': 'Tests de Stress y Límites',
                        'timeout': 600,
                        'critical': False
                    }
                ]
            },
            'security': {
                'name': 'Tests de Seguridad',
                'description': 'Identificación de vulnerabilidades',
                'priority': 'CRITICAL',
                'tests': [
                    {
                        'script': 'security/test_security_robustness.py',
                        'name': 'Tests de Seguridad y Robustez',
                        'timeout': 300,
                        'critical': True
                    }
                ]
            },
            'integration': {
                'name': 'Tests de Integración',
                'description': 'Compatibilidad con componentes externos',
                'priority': 'HIGH',
                'tests': [
                    {
                        'script': 'integration/test_streamlit_integration.py',
                        'name': 'Tests de Integración Streamlit',
                        'timeout': 180,
                        'critical': False
                    }
                ]
            },
            'simulation': {
                'name': 'Tests de Simulación',
                'description': 'Comportamiento bajo condiciones realistas',
                'priority': 'MEDIUM',
                'tests': [
                    {
                        'script': 'simulation/test_trading_simulation.py',
                        'name': 'Tests de Simulación Trading',
                        'timeout': 420,
                        'critical': False
                    }
                ]
            },
            'recovery': {
                'name': 'Tests de Recuperación',
                'description': 'Capacidad de recuperación ante fallos',
                'priority': 'HIGH',
                'tests': [
                    {
                        'script': 'recovery/test_system_recovery.py',
                        'name': 'Tests de Recuperación del Sistema',
                        'timeout': 360,
                        'critical': False
                    }
                ]
            },
            'configuration': {
                'name': 'Tests de Configuración',
                'description': 'Validación de parámetros y settings',
                'priority': 'CRITICAL',
                'tests': [
                    {
                        'script': 'configuration/test_configuration_validation.py',
                        'name': 'Validación de Configuración',
                        'timeout': 180,
                        'critical': True
                    }
                ]
            },
            'network': {
                'name': 'Tests de Red',
                'description': 'Resiliencia ante problemas de conectividad',
                'priority': 'MEDIUM',
                'tests': [
                    {
                        'script': 'network/test_network_resilience.py',
                        'name': 'Tests de Resiliencia de Red',
                        'timeout': 300,
                        'critical': False
                    }
                ]
            }
        }
    
    def run_all_tests(self):
        """Ejecutar todos los tests según los argumentos"""
        if not self.args.quiet:
            self.print_header()
        
        if self.args.report_only:
            return self.generate_final_report_only()
        
        # Determinar qué tests ejecutar
        tests_to_run = self.determine_tests_to_run()
        
        if not tests_to_run:
            print("❌ No hay tests para ejecutar según los criterios especificados")
            return 1
        
        if not self.args.quiet:
            print(f"📊 Tests programados para ejecución: {len(tests_to_run)}")
            self.print_execution_plan(tests_to_run)
        
        # Ejecutar tests
        for category_name, category_info, test_info in tests_to_run:
            result = self.run_single_test(category_name, category_info, test_info)
            self.results.append(result)
            
            if not self.args.quiet:
                self.print_test_result(result)
        
        # Generar reporte final
        return self.generate_final_report()
    
    def print_header(self):
        """Imprimir header del sistema"""
        print("🧪 SISTEMA DE TESTS ORGANIZADOS - TRADING SYSTEM V3")
        print("=" * 70)
        print(f"🕐 Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Modo: {self.get_execution_mode()}")
        print("=" * 70)
    
    def get_execution_mode(self) -> str:
        """Obtener modo de ejecución"""
        if self.args.quick:
            return "TESTS CRÍTICOS ÚNICAMENTE"
        elif self.args.performance:
            return "TESTS DE PERFORMANCE"
        elif self.args.security:
            return "TESTS DE SEGURIDAD"
        elif self.args.category:
            return f"CATEGORÍA: {self.args.category.upper()}"
        else:
            return "SUITE COMPLETA"
    
    def determine_tests_to_run(self) -> List:
        """Determinar qué tests ejecutar según los argumentos"""
        tests_to_run = []
        
        for category_name, category_info in self.test_categories.items():
            # Filtrar por argumentos
            if self.args.category and self.args.category != category_name:
                continue
            
            if self.args.quick and category_info['priority'] != 'CRITICAL':
                continue
            
            if self.args.performance and category_name not in ['performance', 'advanced', 'simulation']:
                continue
            
            if self.args.security and category_name not in ['security', 'configuration', 'recovery', 'network']:
                continue
            
            # Agregar tests de la categoría
            for test_info in category_info['tests']:
                tests_to_run.append((category_name, category_info, test_info))
        
        return tests_to_run
    
    def print_execution_plan(self, tests_to_run: List):
        """Imprimir plan de ejecución"""
        print(f"\n📋 PLAN DE EJECUCIÓN:")
        
        categories_summary = {}
        for category_name, category_info, test_info in tests_to_run:
            if category_name not in categories_summary:
                categories_summary[category_name] = {
                    'name': category_info['name'],
                    'priority': category_info['priority'],
                    'count': 0,
                    'estimated_time': 0
                }
            categories_summary[category_name]['count'] += 1
            categories_summary[category_name]['estimated_time'] += test_info['timeout']
        
        for category_name, summary in categories_summary.items():
            priority_emoji = "🚨" if summary['priority'] == 'CRITICAL' else "⚡" if summary['priority'] == 'HIGH' else "📊"
            print(f"   {priority_emoji} {summary['name']}: {summary['count']} tests (~{summary['estimated_time']/60:.1f}min)")
        
        total_estimated_time = sum(summary['estimated_time'] for summary in categories_summary.values())
        print(f"\n⏱️  Tiempo estimado total: {total_estimated_time/60:.1f} minutos")
    
    def run_single_test(self, category_name: str, category_info: Dict, test_info: Dict) -> Dict:
        """Ejecutar un test individual"""
        if not self.args.quiet:
            print(f"\n{'='*80}")
            print(f"🧪 EJECUTANDO: {test_info['name']}")
            print(f"📂 Categoría: {category_info['name']} ({category_info['priority']})")
            print(f"📝 Script: {test_info['script']}")
            print(f"{'='*80}")
        
        start_time = time.time()
        script_path = self.base_path / test_info['script']
        
        result = {
            'category': category_name,
            'category_name': category_info['name'],
            'priority': category_info['priority'],
            'test_name': test_info['name'],
            'script': test_info['script'],
            'critical': test_info.get('critical', False),
            'success': False,
            'execution_time': 0,
            'output': '',
            'error': '',
            'metrics': {}
        }
        
        try:
            # Verificar que el script existe
            if not script_path.exists():
                result['error'] = f"Script no encontrado: {test_info['script']}"
                result['execution_time'] = time.time() - start_time
                return result
            
            # Ejecutar test con timeout personalizable
            timeout = self.args.timeout if hasattr(self.args, 'timeout') else test_info['timeout']
            
            process_result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, timeout=timeout)
            
            result['execution_time'] = time.time() - start_time
            result['success'] = process_result.returncode == 0
            result['output'] = process_result.stdout
            result['error'] = process_result.stderr
            result['return_code'] = process_result.returncode
            
            # Extraer métricas del output
            result['metrics'] = self.extract_test_metrics(process_result.stdout, category_name)
            
            # Mostrar output si no está en modo silencioso
            if not self.args.quiet and process_result.stdout:
                print(process_result.stdout)
            
            if process_result.stderr and process_result.returncode != 0:
                if not self.args.quiet:
                    print(f"❌ ERRORES:\n{process_result.stderr}")
            
        except subprocess.TimeoutExpired:
            result['execution_time'] = time.time() - start_time
            result['error'] = f"Timeout después de {timeout/60:.1f} minutos"
            if not self.args.quiet:
                print(f"\n⏰ TIMEOUT: Test excedió {timeout/60:.1f} minutos")
        
        except Exception as e:
            result['execution_time'] = time.time() - start_time
            result['error'] = str(e)
            if not self.args.quiet:
                print(f"\n❌ ERROR: {e}")
        
        return result
    
    def print_test_result(self, result: Dict):
        """Imprimir resultado de un test individual"""
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        critical_marker = "🚨" if result['critical'] else ""
        
        print(f"\n{status} {critical_marker} {result['test_name']}")
        print(f"   ⏱️  Tiempo: {result['execution_time']:.1f}s")
        
        if result['metrics']:
            self.print_test_metrics(result['metrics'], result['category'])
        
        if not result['success']:
            print(f"   ❌ Error: {result['error'][:100]}..." if len(result['error']) > 100 else f"   ❌ Error: {result['error']}")
    
    def print_test_metrics(self, metrics: Dict, category: str):
        """Imprimir métricas específicas del test"""
        if 'trades_per_second' in metrics:
            print(f"   🚀 Velocidad: {metrics['trades_per_second']:.0f} trades/seg")
        
        if 'total_trades_processed' in metrics:
            print(f"   📊 Trades: {metrics['total_trades_processed']:,}")
        
        if 'success_rate' in metrics:
            print(f"   📈 Éxito: {metrics['success_rate']*100:.1f}%")
        
        if 'peak_memory_mb' in metrics:
            print(f"   💾 Memoria: {metrics['peak_memory_mb']:.1f}MB")
    
    def extract_test_metrics(self, output: str, category: str) -> Dict:
        """Extraer métricas del output del test"""
        metrics = {}
        
        if not output:
            return metrics
        
        lines = output.split('\n')
        
        for line in lines:
            # Trades per second
            if 'trades/segundo' in line:
                try:
                    import re
                    match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*trades/segundo', line)
                    if match:
                        metrics['trades_per_second'] = float(match.group(1).replace(',', ''))
                except:
                    pass
            
            # Success rate
            if 'resultado final:' in line.lower():
                try:
                    import re
                    match = re.search(r'(\d+)/(\d+)', line)
                    if match:
                        passed = int(match.group(1))
                        total = int(match.group(2))
                        metrics['success_rate'] = passed / total if total > 0 else 0
                        metrics['tests_passed'] = passed
                        metrics['tests_total'] = total
                except:
                    pass
            
            # Memory usage
            if 'memoria' in line.lower() or 'memory' in line.lower():
                try:
                    import re
                    match = re.search(r'(\d+(?:\.\d+)?)\s*mb', line.lower())
                    if match:
                        metrics['peak_memory_mb'] = float(match.group(1))
                except:
                    pass
            
            # Total trades
            if 'trades' in line.lower() and any(word in line.lower() for word in ['procesados', 'insertados', 'total']):
                try:
                    import re
                    match = re.search(r'(\d+(?:,\d+)*)', line)
                    if match:
                        metrics['total_trades_processed'] = int(match.group(1).replace(',', ''))
                except:
                    pass
        
        return metrics
    
    def generate_final_report(self) -> int:
        """Generar reporte final"""
        total_time = time.time() - self.start_time
        
        print(f"\n{'='*80}")
        print("📊 REPORTE FINAL DE EJECUCIÓN")
        print(f"{'='*80}")
        
        # Estadísticas generales
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        critical_tests = [r for r in self.results if r['critical']]
        critical_passed = sum(1 for r in critical_tests if r['success'])
        
        print(f"⏱️  Tiempo total de ejecución: {total_time/60:.1f} minutos")
        print(f"📊 Tests ejecutados: {total_tests}")
        print(f"✅ Tests exitosos: {successful_tests}")
        print(f"❌ Tests fallidos: {total_tests - successful_tests}")
        print(f"🚨 Tests críticos: {len(critical_tests)} (✅ {critical_passed} ❌ {len(critical_tests) - critical_passed})")
        print(f"📈 Tasa de éxito general: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
        
        # Resultados por categoría
        self.print_category_summary()
        
        # Tests fallidos
        failed_tests = [r for r in self.results if not r['success']]
        if failed_tests:
            self.print_failed_tests_summary(failed_tests)
        
        # Evaluación final
        final_evaluation = self.evaluate_final_results(
            successful_tests, total_tests, critical_passed, len(critical_tests)
        )
        
        print(f"\n{final_evaluation['status_message']}")
        print(final_evaluation['description'])
        print(final_evaluation['recommendation'])
        
        # Guardar reporte detallado
        self.save_detailed_report(total_time, final_evaluation)
        
        return final_evaluation['exit_code']
    
    def print_category_summary(self):
        """Imprimir resumen por categoría"""
        print(f"\n📋 RESULTADOS POR CATEGORÍA:")
        
        category_stats = {}
        for result in self.results:
            cat = result['category']
            if cat not in category_stats:
                category_stats[cat] = {
                    'name': result['category_name'],
                    'priority': result['priority'],
                    'total': 0,
                    'passed': 0,
                    'avg_time': 0,
                    'total_time': 0
                }
            
            category_stats[cat]['total'] += 1
            category_stats[cat]['total_time'] += result['execution_time']
            if result['success']:
                category_stats[cat]['passed'] += 1
        
        # Calcular promedios y mostrar
        for cat_name, stats in category_stats.items():
            stats['avg_time'] = stats['total_time'] / stats['total'] if stats['total'] > 0 else 0
            
            status = "✅ PASS" if stats['passed'] == stats['total'] else "❌ FAIL"
            priority_emoji = "🚨" if stats['priority'] == 'CRITICAL' else "⚡" if stats['priority'] == 'HIGH' else "📊"
            
            print(f"   {priority_emoji} {stats['name']}: {status} ({stats['passed']}/{stats['total']}) - {stats['avg_time']:.1f}s promedio")
    
    def print_failed_tests_summary(self, failed_tests: List[Dict]):
        """Imprimir resumen de tests fallidos"""
        print(f"\n🚨 TESTS FALLIDOS ({len(failed_tests)}):")
        
        for test in failed_tests:
            critical_marker = "🚨 CRÍTICO" if test['critical'] else "⚠️  NORMAL"
            print(f"   ❌ [{test['category_name']}] {test['test_name']} ({critical_marker})")
            print(f"      Error: {test['error'][:80]}..." if len(test['error']) > 80 else f"      Error: {test['error']}")
    
    def evaluate_final_results(self, successful: int, total: int, critical_passed: int, critical_total: int) -> Dict:
        """Evaluar resultados finales"""
        success_rate = successful / total if total > 0 else 0
        critical_success_rate = critical_passed / critical_total if critical_total > 0 else 1
        
        if success_rate == 1.0:
            return {
                'status_message': "🏆 ¡TODOS LOS TESTS PASARON EXITOSAMENTE!",
                'description': "✅ Sistema completamente validado y listo para producción",
                'recommendation': "🚀 Proceder con confianza - todos los aspectos validados",
                'exit_code': 0
            }
        elif critical_success_rate == 1.0 and success_rate >= 0.8:
            return {
                'status_message': "👍 SISTEMA MAYORMENTE VALIDADO",
                'description': "✅ Funciones críticas operativas, algunas optimizaciones pendientes",
                'recommendation': "🔧 Revisar tests fallidos no críticos antes de producción",
                'exit_code': 0
            }
        elif critical_success_rate == 1.0:
            return {
                'status_message': "⚠️  SISTEMA FUNCIONAL CON LIMITACIONES",
                'description': "✅ Core funcional, pero múltiples áreas necesitan mejoras",
                'recommendation': "🔧 Mejoras importantes requeridas antes de producción",
                'exit_code': 1
            }
        else:
            return {
                'status_message': "🚨 SISTEMA REQUIERE ATENCIÓN CRÍTICA",
                'description': "❌ Fallas en funciones críticas detectadas",
                'recommendation': "🛑 NO usar en producción hasta corregir tests críticos",
                'exit_code': 2
            }
    
    def save_detailed_report(self, total_time: float, final_evaluation: Dict):
        """Guardar reporte detallado en JSON"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'execution_mode': self.get_execution_mode(),
                'execution_time_minutes': total_time / 60,
                'summary': {
                    'total_tests': len(self.results),
                    'successful_tests': sum(1 for r in self.results if r['success']),
                    'failed_tests': sum(1 for r in self.results if not r['success']),
                    'critical_tests_total': sum(1 for r in self.results if r['critical']),
                    'critical_tests_passed': sum(1 for r in self.results if r['critical'] and r['success']),
                    'overall_success_rate': sum(1 for r in self.results if r['success']) / len(self.results) if self.results else 0
                },
                'final_evaluation': final_evaluation,
                'detailed_results': self.results,
                'execution_args': vars(self.args)
            }
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"organized_test_report_{timestamp}.json"
            report_path = self.base_path / report_filename
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"\n📄 Reporte detallado guardado: {report_filename}")
            
        except Exception as e:
            print(f"\n⚠️  No se pudo guardar el reporte detallado: {e}")
    
    def generate_final_report_only(self) -> int:
        """Generar solo reporte sin ejecutar tests"""
        print("📄 MODO REPORTE - Sin ejecución de tests")
        print("=" * 50)
        
        # Buscar reportes recientes
        report_files = list(self.base_path.glob("organized_test_report_*.json"))
        report_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not report_files:
            print("❌ No se encontraron reportes anteriores")
            return 1
        
        latest_report = report_files[0]
        print(f"📊 Mostrando último reporte: {latest_report.name}")
        
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            # Mostrar resumen del reporte
            summary = report_data.get('summary', {})
            print(f"\n📈 RESUMEN:")
            print(f"   Tests ejecutados: {summary.get('total_tests', 0)}")
            print(f"   Tests exitosos: {summary.get('successful_tests', 0)}")
            print(f"   Tasa de éxito: {summary.get('overall_success_rate', 0)*100:.1f}%")
            print(f"   Tiempo de ejecución: {report_data.get('execution_time_minutes', 0):.1f} min")
            
            evaluation = report_data.get('final_evaluation', {})
            print(f"\n{evaluation.get('status_message', 'Estado desconocido')}")
            
            return evaluation.get('exit_code', 0)
            
        except Exception as e:
            print(f"❌ Error leyendo reporte: {e}")
            return 1

def main():
    """Función principal"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    executor = TestExecutor(args)
    exit_code = executor.run_all_tests()
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()