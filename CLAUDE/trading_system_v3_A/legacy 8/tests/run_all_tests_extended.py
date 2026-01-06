#!/usr/bin/env python3
"""
Script Maestro Extendido para Ejecutar TODOS los Tests del Sistema de Trading
Incluye tests básicos, avanzados, stress, simulación, seguridad e integración Streamlit
"""

import os
import sys
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

def run_test_suite(test_script: str, suite_name: str, timeout: int = 300) -> dict:
    """Ejecutar una suite de tests y capturar resultados"""
    print(f"\n{'='*70}")
    print(f"🧪 EJECUTANDO: {suite_name}")
    print(f"📝 Script: {test_script}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    try:
        # Verificar que el script existe
        script_path = Path(__file__).parent / test_script
        if not script_path.exists():
            return {
                'suite_name': suite_name,
                'script': test_script,
                'success': False,
                'execution_time': 0,
                'stdout': '',
                'stderr': f'Test script not found: {test_script}',
                'return_code': -2
            }
        
        # Ejecutar test con timeout extendido para tests pesados
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True, timeout=timeout)
        
        execution_time = time.time() - start_time
        
        # Analizar resultado
        success = result.returncode == 0
        
        # Mostrar salida
        if result.stdout:
            print(result.stdout)
        
        if result.stderr and not success:
            print(f"❌ ERRORES:\n{result.stderr}")
        
        return {
            'suite_name': suite_name,
            'script': test_script,
            'success': success,
            'execution_time': execution_time,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        print(f"⏰ TIMEOUT: {suite_name} excedió {timeout/60:.1f} minutos")
        return {
            'suite_name': suite_name,
            'script': test_script,
            'success': False,
            'execution_time': execution_time,
            'stdout': '',
            'stderr': f'Test timeout después de {timeout/60:.1f} minutos',
            'return_code': -1
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"❌ ERROR ejecutando {suite_name}: {e}")
        return {
            'suite_name': suite_name,
            'script': test_script,
            'success': False,
            'execution_time': execution_time,
            'stdout': '',
            'stderr': str(e),
            'return_code': -1
        }

def extract_advanced_metrics(output: str, suite_name: str) -> dict:
    """Extraer métricas avanzadas de las suites de test"""
    metrics = {}
    
    try:
        lines = output.split('\n')
        
        # Métricas de rendimiento
        if "trades/segundo" in output:
            for line in lines:
                if "trades/segundo" in line and any(word in line for word in ["Velocidad:", "📊", "📈"]):
                    try:
                        # Buscar números antes de "trades/segundo"
                        parts = line.split("trades/segundo")[0].split()
                        for part in reversed(parts):
                            try:
                                speed = float(part.replace(',', '').replace(':', ''))
                                metrics['trades_per_second'] = speed
                                break
                            except ValueError:
                                continue
                        break
                    except:
                        pass
        
        # Métricas de concurrencia
        if "threads" in output.lower() and "exitosos" in output:
            for line in lines:
                if "threads exitosos" in line.lower():
                    try:
                        parts = line.split(":")[-1].strip().split("/")
                        if len(parts) == 2:
                            successful = int(parts[0])
                            total = int(parts[1])
                            metrics['thread_success_rate'] = successful / total
                    except:
                        pass
        
        # Métricas de memoria
        if "memoria" in output.lower() or "memory" in output.lower():
            for line in lines:
                if "mb" in line.lower() and any(word in line.lower() for word in ["memoria", "memory", "pico", "peak"]):
                    try:
                        import re
                        mb_matches = re.findall(r'(\d+\.?\d*)\s*mb', line.lower())
                        if mb_matches:
                            metrics['peak_memory_mb'] = float(mb_matches[0])
                    except:
                        pass
        
        # Métricas de trades
        if "trades" in output.lower():
            for line in lines:
                if "trades insertados" in line.lower() or "trades generados" in line.lower():
                    try:
                        import re
                        numbers = re.findall(r'(\d+(?:,\d+)*)', line)
                        if numbers:
                            trades_count = int(numbers[0].replace(',', ''))
                            metrics['total_trades_processed'] = trades_count
                    except:
                        pass
        
        # Tasa de éxito general
        if "resultado final:" in output.lower():
            for line in lines:
                if "resultado final:" in line.lower():
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
        
        # Métricas de seguridad
        if "vulnerabilidades" in output.lower() or "security" in output.lower():
            for line in lines:
                if "bloqueados" in line.lower() or "blocked" in line.lower():
                    try:
                        import re
                        match = re.search(r'(\d+)/(\d+)', line)
                        if match:
                            blocked = int(match.group(1))
                            total = int(match.group(2))
                            metrics['security_block_rate'] = blocked / total if total > 0 else 0
                    except:
                        pass
    
    except Exception as e:
        print(f"⚠️  Error extrayendo métricas de {suite_name}: {e}")
    
    return metrics

def generate_comprehensive_report(test_results: list) -> dict:
    """Generar reporte comprehensivo de todos los tests"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_execution_summary': {
            'total_suites': len(test_results),
            'successful_suites': sum(1 for r in test_results if r['success']),
            'failed_suites': sum(1 for r in test_results if not r['success']),
            'total_execution_time': sum(r['execution_time'] for r in test_results),
            'overall_success_rate': 0
        },
        'performance_metrics': {
            'max_trades_per_second': 0,
            'total_trades_processed': 0,
            'peak_memory_usage_mb': 0,
            'best_thread_success_rate': 0
        },
        'security_assessment': {
            'security_tests_passed': 0,
            'vulnerabilities_detected': 0,
            'security_score': 0
        },
        'test_categories': {
            'basic_functionality': {'passed': False, 'critical': True},
            'performance_stress': {'passed': False, 'critical': False},
            'security_robustness': {'passed': False, 'critical': True},
            'integration': {'passed': False, 'critical': False},
            'simulation': {'passed': False, 'critical': False}
        },
        'detailed_results': [],
        'recommendations': [],
        'critical_issues': []
    }
    
    # Calcular tasa de éxito general
    if report['test_execution_summary']['total_suites'] > 0:
        report['test_execution_summary']['overall_success_rate'] = (
            report['test_execution_summary']['successful_suites'] / 
            report['test_execution_summary']['total_suites']
        )
    
    # Procesar cada suite
    for result in test_results:
        suite_info = {
            'name': result['suite_name'],
            'success': result['success'],
            'execution_time': result['execution_time'],
            'return_code': result['return_code'],
            'metrics': extract_advanced_metrics(result['stdout'], result['suite_name'])
        }
        
        # Agregar errores si los hay
        if result['stderr']:
            suite_info['errors'] = result['stderr']
        
        report['detailed_results'].append(suite_info)
        
        # Actualizar métricas de rendimiento
        metrics = suite_info['metrics']
        if 'trades_per_second' in metrics:
            report['performance_metrics']['max_trades_per_second'] = max(
                report['performance_metrics']['max_trades_per_second'],
                metrics['trades_per_second']
            )
        
        if 'total_trades_processed' in metrics:
            report['performance_metrics']['total_trades_processed'] += metrics['total_trades_processed']
        
        if 'peak_memory_mb' in metrics:
            report['performance_metrics']['peak_memory_usage_mb'] = max(
                report['performance_metrics']['peak_memory_usage_mb'],
                metrics['peak_memory_mb']
            )
        
        if 'thread_success_rate' in metrics:
            report['performance_metrics']['best_thread_success_rate'] = max(
                report['performance_metrics']['best_thread_success_rate'],
                metrics['thread_success_rate']
            )
        
        # Categorizar tests
        suite_name_lower = result['suite_name'].lower()
        if 'básico' in suite_name_lower or 'history' in suite_name_lower:
            report['test_categories']['basic_functionality']['passed'] = result['success']
        elif 'stress' in suite_name_lower or 'rendimiento' in suite_name_lower:
            report['test_categories']['performance_stress']['passed'] = result['success']
        elif 'seguridad' in suite_name_lower or 'security' in suite_name_lower:
            report['test_categories']['security_robustness']['passed'] = result['success']
        elif 'streamlit' in suite_name_lower or 'integración' in suite_name_lower:
            report['test_categories']['integration']['passed'] = result['success']
        elif 'simulación' in suite_name_lower or 'trading' in suite_name_lower:
            report['test_categories']['simulation']['passed'] = result['success']
    
    # Evaluación de seguridad
    security_suites = [r for r in test_results if 'seguridad' in r['suite_name'].lower()]
    if security_suites:
        security_passed = sum(1 for s in security_suites if s['success'])
        report['security_assessment']['security_tests_passed'] = security_passed
        report['security_assessment']['security_score'] = security_passed / len(security_suites)
    
    # Generar recomendaciones
    _generate_recommendations(report)
    
    return report

def _generate_recommendations(report: dict):
    """Generar recomendaciones basadas en resultados"""
    recommendations = []
    critical_issues = []
    
    # Evaluación general
    success_rate = report['test_execution_summary']['overall_success_rate']
    
    if success_rate == 1.0:
        recommendations.append("🎉 ¡Excelente! Todos los tests pasaron - Sistema completamente validado")
        recommendations.append("✅ Listo para producción con alta confianza")
    elif success_rate >= 0.8:
        recommendations.append("👍 Sistema robusto con algunas áreas de mejora")
        recommendations.append("🔧 Revisar tests fallidos antes de producción")
    else:
        recommendations.append("⚠️  Sistema necesita mejoras significativas")
        critical_issues.append("Múltiples tests críticos fallaron")
        recommendations.append("🚫 NO recomendado para producción")
    
    # Evaluación por categorías críticas
    categories = report['test_categories']
    
    if not categories['basic_functionality']['passed']:
        critical_issues.append("CRÍTICO: Funcionalidad básica falló")
        recommendations.append("🚨 Prioridad MÁXIMA: Corregir funcionalidad básica")
    
    if not categories['security_robustness']['passed']:
        critical_issues.append("CRÍTICO: Tests de seguridad fallaron")
        recommendations.append("🔒 Prioridad ALTA: Corregir vulnerabilidades de seguridad")
    
    # Evaluación de rendimiento
    perf_metrics = report['performance_metrics']
    
    if perf_metrics['max_trades_per_second'] > 1000:
        recommendations.append(f"🚀 Excelente rendimiento: {perf_metrics['max_trades_per_second']:.0f} trades/segundo")
    elif perf_metrics['max_trades_per_second'] > 500:
        recommendations.append(f"👍 Buen rendimiento: {perf_metrics['max_trades_per_second']:.0f} trades/segundo")
    elif perf_metrics['max_trades_per_second'] > 0:
        recommendations.append(f"⚠️  Rendimiento bajo: {perf_metrics['max_trades_per_second']:.0f} trades/segundo")
        recommendations.append("📊 Considerar optimización de rendimiento")
    
    # Evaluación de memoria
    if perf_metrics['peak_memory_usage_mb'] > 500:
        recommendations.append(f"💾 Alto uso de memoria: {perf_metrics['peak_memory_usage_mb']:.0f} MB")
        recommendations.append("🔧 Considerar optimización de memoria")
    
    # Evaluación de seguridad
    security_score = report['security_assessment']['security_score']
    
    if security_score == 1.0:
        recommendations.append("🛡️  Excelente seguridad: Todos los tests pasaron")
    elif security_score >= 0.8:
        recommendations.append("🔒 Buena seguridad con mejoras menores")
    elif security_score > 0:
        recommendations.append("⚠️  Vulnerabilidades de seguridad detectadas")
        critical_issues.append("Sistema vulnerable a ataques")
    else:
        critical_issues.append("CRÍTICO: Fallas masivas de seguridad")
    
    report['recommendations'] = recommendations
    report['critical_issues'] = critical_issues

def main():
    """Ejecutar suite completa extendida de tests"""
    print("🎯 EJECUCIÓN COMPLETA EXTENDIDA DE TESTS DEL SISTEMA DE TRADING")
    print("🕐 Iniciado:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 80)
    
    # Definir todas las suites de tests organizados (orden por criticidad)
    test_suites = [
        {
            'script': 'basic/test_trades_history.py',
            'name': 'Tests Básicos e Historia',
            'timeout': 120,  # 2 minutos
            'critical': True
        },
        {
            'script': 'advanced/test_trades_advanced.py', 
            'name': 'Tests Avanzados y Rendimiento',
            'timeout': 300,  # 5 minutos
            'critical': False
        },
        {
            'script': 'advanced/test_trades_migration.py',
            'name': 'Tests de Migración y Mantenimiento',
            'timeout': 180,  # 3 minutos
            'critical': False
        },
        {
            'script': 'security/test_security_robustness.py',
            'name': 'Tests de Seguridad y Robustez',
            'timeout': 240,  # 4 minutos
            'critical': True
        },
        {
            'script': 'integration/test_streamlit_integration.py',
            'name': 'Tests de Integración Streamlit',
            'timeout': 180,  # 3 minutos
            'critical': False
        },
        {
            'script': 'configuration/test_configuration_validation.py',
            'name': 'Tests de Validación de Configuración',
            'timeout': 180,  # 3 minutos
            'critical': True
        },
        {
            'script': 'recovery/test_system_recovery.py',
            'name': 'Tests de Recuperación del Sistema',
            'timeout': 360,  # 6 minutos
            'critical': False
        },
        {
            'script': 'network/test_network_resilience.py',
            'name': 'Tests de Resiliencia de Red',
            'timeout': 300,  # 5 minutos
            'critical': False
        },
        # Tests pesados al final
        {
            'script': 'performance/test_stress_limits.py',
            'name': 'Tests de Stress y Límites',
            'timeout': 600,  # 10 minutos
            'critical': False
        },
        {
            'script': 'simulation/test_trading_simulation.py',
            'name': 'Tests de Simulación Trading',
            'timeout': 420,  # 7 minutos
            'critical': False
        }
    ]
    
    # Verificar que todos los scripts existen
    missing_scripts = []
    available_suites = []
    
    base_path = Path(__file__).parent
    for suite in test_suites:
        script_path = base_path / suite['script']
        if script_path.exists():
            available_suites.append(suite)
        else:
            missing_scripts.append(suite['script'])
            print(f"⚠️  Script no encontrado (omitido): {suite['script']}")
    
    if not available_suites:
        print("❌ ERROR: No se encontraron scripts de test")
        return
    
    print(f"📊 Suites disponibles: {len(available_suites)}/{len(test_suites)}")
    
    # Ejecutar todos los tests disponibles
    all_results = []
    start_time = time.time()
    
    for i, suite in enumerate(available_suites, 1):
        print(f"\n🔄 Progreso: {i}/{len(available_suites)}")
        
        result = run_test_suite(
            suite['script'], 
            suite['name'], 
            suite.get('timeout', 300)
        )
        all_results.append(result)
        
        # Pausa corta entre tests pesados
        if suite.get('timeout', 0) > 300:
            print("⏸️  Pausa de recuperación...")
            time.sleep(2)
    
    total_time = time.time() - start_time
    
    # Generar reporte comprehensivo
    print(f"\n{'='*80}")
    print("📊 GENERANDO REPORTE COMPREHENSIVO")
    print(f"{'='*80}")
    
    comprehensive_report = generate_comprehensive_report(all_results)
    comprehensive_report['test_execution_summary']['total_execution_time'] = total_time
    
    # Mostrar resumen ejecutivo
    summary = comprehensive_report['test_execution_summary']
    print(f"\n🎯 RESUMEN EJECUTIVO:")
    print(f"   ⏱️  Tiempo total de ejecución: {total_time/60:.1f} minutos")
    print(f"   📊 Suites ejecutadas: {summary['total_suites']}")
    print(f"   ✅ Suites exitosas: {summary['successful_suites']}")
    print(f"   ❌ Suites fallidas: {summary['failed_suites']}")
    print(f"   📈 Tasa de éxito general: {summary['overall_success_rate']*100:.1f}%")
    
    # Mostrar métricas de rendimiento
    perf = comprehensive_report['performance_metrics']
    print(f"\n🚀 MÉTRICAS DE RENDIMIENTO:")
    if perf['max_trades_per_second'] > 0:
        print(f"   📊 Velocidad máxima: {perf['max_trades_per_second']:.0f} trades/segundo")
    if perf['total_trades_processed'] > 0:
        print(f"   📈 Trades procesados: {perf['total_trades_processed']:,}")
    if perf['peak_memory_usage_mb'] > 0:
        print(f"   💾 Memoria pico: {perf['peak_memory_usage_mb']:.0f} MB")
    if perf['best_thread_success_rate'] > 0:
        print(f"   🔀 Mejor tasa concurrencia: {perf['best_thread_success_rate']*100:.0f}%")
    
    # Evaluación de seguridad
    security = comprehensive_report['security_assessment']
    if security['security_score'] > 0:
        print(f"\n🛡️  EVALUACIÓN DE SEGURIDAD:")
        print(f"   🔒 Puntuación seguridad: {security['security_score']*100:.0f}%")
    
    # Estado por categoría
    print(f"\n📋 ESTADO POR CATEGORÍA:")
    categories = comprehensive_report['test_categories']
    
    for category, info in categories.items():
        status = "✅ PASS" if info['passed'] else "❌ FAIL"
        critical = "🔴 CRÍTICO" if info['critical'] else "🟡 OPCIONAL"
        category_display = category.replace('_', ' ').title()
        print(f"   {category_display}: {status} ({critical})")
    
    # Problemas críticos
    critical_issues = comprehensive_report['critical_issues']
    if critical_issues:
        print(f"\n🚨 PROBLEMAS CRÍTICOS:")
        for issue in critical_issues:
            print(f"   ❗ {issue}")
    
    # Recomendaciones
    recommendations = comprehensive_report['recommendations']
    if recommendations:
        print(f"\n💡 RECOMENDACIONES:")
        for recommendation in recommendations:
            print(f"   {recommendation}")
    
    # Guardar reporte detallado
    report_filename = f"comprehensive_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(comprehensive_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte completo guardado en: {report_filename}")
        
    except Exception as e:
        print(f"⚠️  No se pudo guardar el reporte: {e}")
    
    # Estado final del sistema
    success_rate = summary['overall_success_rate']
    critical_categories_passed = sum(1 for cat, info in categories.items() 
                                   if info['critical'] and info['passed'])
    total_critical_categories = sum(1 for info in categories.values() if info['critical'])
    
    print(f"\n" + "="*80)
    
    if success_rate == 1.0:
        print("🏆 ¡SISTEMA COMPLETAMENTE VALIDADO!")
        print("✅ Todas las suites pasaron exitosamente")
        print("🚀 LISTO PARA PRODUCCIÓN")
        exit_code = 0
    elif critical_categories_passed == total_critical_categories and success_rate >= 0.7:
        print("👍 SISTEMA MAYORMENTE VALIDADO")
        print("✅ Todas las funciones críticas pasan")
        print("🔧 Algunas optimizaciones menores recomendadas")
        exit_code = 0
    elif critical_categories_passed == total_critical_categories:
        print("⚠️  SISTEMA FUNCIONAL CON LIMITACIONES")
        print("✅ Funciones críticas operativas")
        print("🔧 Mejoras importantes recomendadas antes de producción")
        exit_code = 1
    else:
        print("🚨 SISTEMA REQUIERE ATENCIÓN CRÍTICA")
        print("❌ Fallas en funciones críticas detectadas")
        print("🛑 NO USAR EN PRODUCCIÓN")
        exit_code = 2
    
    print(f"\n🏁 Ejecución completada en {total_time/60:.1f} minutos")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()