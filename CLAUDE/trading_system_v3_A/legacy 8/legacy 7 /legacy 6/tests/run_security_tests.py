#!/usr/bin/env python3
"""
Ejecutor Especializado de Tests de Seguridad
Ejecuta únicamente tests relacionados con seguridad y robustez
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
import json

def run_security_test_suite():
    """Ejecutar suite completa de tests de seguridad"""
    print("🛡️  EJECUTANDO TESTS DE SEGURIDAD Y ROBUSTEZ")
    print("=" * 55)
    print(f"🕐 Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    
    # Tests relacionados con seguridad
    security_tests = [
        {
            'category': 'SECURITY_CORE',
            'script': 'security/test_security_robustness.py',
            'name': 'Tests de Seguridad Principal',
            'description': 'SQL injection, datos malformados, ataques concurrentes',
            'timeout': 300,  # 5 minutos
            'priority': 'CRITICAL'
        },
        {
            'category': 'NETWORK_SECURITY',
            'script': 'network/test_network_resilience.py',
            'name': 'Tests de Resiliencia de Red',
            'description': 'Timeouts, latencia, pool exhaustion',
            'timeout': 300,  # 5 minutos
            'priority': 'HIGH'
        },
        {
            'category': 'RECOVERY_SECURITY',
            'script': 'recovery/test_system_recovery.py',
            'name': 'Tests de Recuperación ante Fallos',
            'description': 'Corrupción BD, fallos concurrentes, continuidad',
            'timeout': 360,  # 6 minutos
            'priority': 'HIGH'
        },
        {
            'category': 'CONFIG_SECURITY',
            'script': 'configuration/test_configuration_validation.py',
            'name': 'Validación Segura de Configuración',
            'description': 'Parámetros inválidos, variables de entorno',
            'timeout': 180,  # 3 minutos
            'priority': 'HIGH'
        }
    ]
    
    results = []
    start_time = time.time()
    security_issues_found = []
    
    for test in security_tests:
        print(f"\n{'='*70}")
        print(f"🔍 EJECUTANDO: {test['name']}")
        print(f"📂 Categoría: {test['category']}")
        print(f"🎯 Descripción: {test['description']}")
        print(f"⚡ Prioridad: {test['priority']}")
        print(f"📝 Script: {test['script']}")
        print(f"{'='*70}")
        
        test_start = time.time()
        
        try:
            # Verificar que el script existe
            script_path = Path(__file__).parent / test['script']
            if not script_path.exists():
                print(f"❌ ERROR: Script no encontrado: {test['script']}")
                results.append({
                    'name': test['name'],
                    'category': test['category'],
                    'priority': test['priority'],
                    'success': False,
                    'error': f"Script no encontrado: {test['script']}",
                    'execution_time': 0,
                    'security_issues': []
                })
                continue
            
            # Ejecutar test de seguridad
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, timeout=test['timeout'])
            
            execution_time = time.time() - test_start
            
            # Mostrar output
            if result.stdout:
                print(result.stdout)
            
            # Analizar output en busca de problemas de seguridad
            security_issues = analyze_security_output(result.stdout, test['category'])
            
            if result.stderr and result.returncode != 0:
                print(f"❌ ERRORES:\n{result.stderr}")
            
            success = result.returncode == 0
            
            result_data = {
                'name': test['name'],
                'category': test['category'],
                'priority': test['priority'],
                'success': success,
                'execution_time': execution_time,
                'return_code': result.returncode,
                'security_issues': security_issues
            }
            
            results.append(result_data)
            
            # Agregar issues encontrados a la lista global
            security_issues_found.extend(security_issues)
            
            # Status específico para tests de seguridad
            if success and len(security_issues) == 0:
                print(f"\n✅ {test['name']}: SEGURO - Sin vulnerabilidades detectadas")
            elif success and len(security_issues) > 0:
                print(f"\n⚠️  {test['name']}: ADVERTENCIAS - {len(security_issues)} problemas menores")
            else:
                print(f"\n❌ {test['name']}: FALLÓ - Posibles vulnerabilidades críticas")
            
            print(f"⏱️  Tiempo de ejecución: {execution_time:.1f}s")
            
            # Mostrar issues específicos si los hay
            if security_issues:
                print(f"🔍 Problemas de seguridad detectados:")
                for issue in security_issues:
                    severity_emoji = "🚨" if issue['severity'] == 'CRITICAL' else "⚠️" if issue['severity'] == 'HIGH' else "ℹ️"
                    print(f"   {severity_emoji} {issue['type']}: {issue['description']}")
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - test_start
            print(f"\n⏰ TIMEOUT: {test['name']} excedió {test['timeout']/60:.1f} minutos")
            
            # Timeout en tests de seguridad puede indicar DoS vulnerability
            security_issues_found.append({
                'type': 'TIMEOUT_VULNERABILITY',
                'description': f'Test de seguridad excedió timeout - posible DoS vulnerability',
                'severity': 'HIGH',
                'category': test['category']
            })
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'priority': test['priority'],
                'success': False,
                'error': f"Timeout después de {test['timeout']/60:.1f} minutos",
                'execution_time': execution_time,
                'security_issues': []
            })
            
        except Exception as e:
            execution_time = time.time() - test_start
            print(f"\n❌ ERROR ejecutando {test['name']}: {e}")
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'priority': test['priority'],
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'security_issues': []
            })
    
    # Análisis de seguridad final
    total_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    print("🛡️  ANÁLISIS DE SEGURIDAD COMPLETADO")
    print(f"{'='*70}")
    
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    critical_failed = sum(1 for r in results if not r['success'] and r['priority'] == 'CRITICAL')
    
    print(f"⏱️  Tiempo total: {total_time/60:.1f} minutos")
    print(f"📊 Tests de seguridad ejecutados: {total_tests}")
    print(f"✅ Tests exitosos: {successful_tests}")
    print(f"❌ Tests fallidos: {total_tests - successful_tests}")
    print(f"🚨 Tests críticos fallidos: {critical_failed}")
    print(f"📈 Tasa de éxito: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
    
    # Resumen de problemas de seguridad
    print(f"\n🔍 ANÁLISIS DE VULNERABILIDADES:")
    
    if not security_issues_found:
        print("✅ No se detectaron vulnerabilidades")
    else:
        # Agrupar por severidad
        critical_issues = [i for i in security_issues_found if i['severity'] == 'CRITICAL']
        high_issues = [i for i in security_issues_found if i['severity'] == 'HIGH']
        medium_issues = [i for i in security_issues_found if i['severity'] == 'MEDIUM']
        low_issues = [i for i in security_issues_found if i['severity'] == 'LOW']
        
        print(f"🚨 Vulnerabilidades CRÍTICAS: {len(critical_issues)}")
        print(f"⚠️  Vulnerabilidades ALTAS: {len(high_issues)}")
        print(f"🔶 Vulnerabilidades MEDIAS: {len(medium_issues)}")
        print(f"ℹ️  Vulnerabilidades BAJAS: {len(low_issues)}")
        
        # Mostrar vulnerabilidades críticas y altas
        if critical_issues or high_issues:
            print(f"\n🚨 VULNERABILIDADES CRÍTICAS Y ALTAS:")
            for issue in critical_issues + high_issues:
                severity_emoji = "🚨" if issue['severity'] == 'CRITICAL' else "⚠️"
                print(f"   {severity_emoji} [{issue['category']}] {issue['type']}: {issue['description']}")
    
    # Evaluación de seguridad
    print(f"\n🛡️  EVALUACIÓN DE SEGURIDAD:")
    
    security_score = calculate_security_score(results, security_issues_found)
    
    if security_score >= 90:
        print("🏆 SEGURIDAD EXCELENTE")
        print("✅ Sistema altamente seguro")
        print("🚀 Apropiado para producción")
        risk_level = "BAJO"
    elif security_score >= 75:
        print("👍 SEGURIDAD BUENA")
        print("⚠️  Algunas vulnerabilidades menores")
        print("🔧 Revisar antes de producción")
        risk_level = "MEDIO"
    elif security_score >= 50:
        print("⚠️  SEGURIDAD MODERADA")
        print("🔧 Vulnerabilidades significativas detectadas")
        print("🚫 No recomendado para producción")
        risk_level = "ALTO"
    else:
        print("🚨 SEGURIDAD CRÍTICA")
        print("❌ Múltiples vulnerabilidades graves")
        print("🛑 NO usar en producción")
        risk_level = "CRÍTICO"
    
    print(f"📊 Puntuación de seguridad: {security_score:.1f}/100")
    print(f"🎯 Nivel de riesgo: {risk_level}")
    
    # Recomendaciones de seguridad
    print(f"\n💡 RECOMENDACIONES DE SEGURIDAD:")
    
    if critical_failed > 0:
        print("🚨 URGENTE: Corregir tests de seguridad críticos fallidos")
    
    if len(critical_issues) > 0:
        print("🛡️  PRIORIDAD MÁXIMA: Corregir vulnerabilidades críticas")
    
    if len(high_issues) > 0:
        print("🔒 PRIORIDAD ALTA: Resolver vulnerabilidades de alta severidad")
    
    # Recomendaciones específicas por categoría
    for result in results:
        if not result['success']:
            category = result['category']
            if category == 'SECURITY_CORE':
                print("🔐 Implementar better input validation y parametrized queries")
            elif category == 'NETWORK_SECURITY':
                print("🌐 Fortalecer timeout handling y connection pooling")
            elif category == 'RECOVERY_SECURITY':
                print("🔧 Mejorar backup procedures y recovery mechanisms")
            elif category == 'CONFIG_SECURITY':
                print("⚙️  Validar y sanitizar todos los parámetros de configuración")
    
    # Generar reporte de seguridad
    try:
        security_report = {
            'timestamp': datetime.now().isoformat(),
            'execution_time_minutes': total_time / 60,
            'security_score': security_score,
            'risk_level': risk_level,
            'tests_summary': {
                'total': total_tests,
                'passed': successful_tests,
                'failed': total_tests - successful_tests,
                'critical_failed': critical_failed
            },
            'vulnerabilities': {
                'total': len(security_issues_found),
                'critical': len(critical_issues),
                'high': len(high_issues),
                'medium': len(medium_issues),
                'low': len(low_issues)
            },
            'detailed_results': results,
            'security_issues': security_issues_found
        }
        
        report_filename = f"security_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = Path(__file__).parent / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(security_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte de seguridad guardado: {report_filename}")
        
    except Exception as e:
        print(f"⚠️  No se pudo guardar el reporte de seguridad: {e}")
    
    # Determinar exit code
    if critical_failed > 0 or len(critical_issues) > 0:
        exit_code = 2  # Critical security issues
    elif successful_tests < total_tests or len(high_issues) > 0:
        exit_code = 1  # Some security concerns
    else:
        exit_code = 0  # All good
    
    print(f"\n🏁 Análisis de seguridad completado en {total_time/60:.1f} minutos")
    
    return exit_code

def analyze_security_output(output: str, category: str) -> list:
    """Analizar output en busca de problemas de seguridad"""
    issues = []
    
    if not output:
        return issues
    
    output_lower = output.lower()
    
    # Patrones que indican problemas de seguridad
    security_patterns = [
        {
            'pattern': 'sql injection',
            'type': 'SQL_INJECTION_VULNERABILITY',
            'severity': 'CRITICAL',
            'description': 'Vulnerability to SQL injection attacks detected'
        },
        {
            'pattern': 'successful injections',
            'type': 'INJECTION_SUCCESS',
            'severity': 'CRITICAL',
            'description': 'SQL injection attempts were successful'
        },
        {
            'pattern': 'system crashes',
            'type': 'SYSTEM_STABILITY',
            'severity': 'HIGH',
            'description': 'System crashes detected under load'
        },
        {
            'pattern': 'information leaks detected',
            'type': 'INFORMATION_DISCLOSURE',
            'severity': 'HIGH',
            'description': 'Sensitive information disclosure in error messages'
        },
        {
            'pattern': 'deadlocks detected',
            'type': 'DEADLOCK_VULNERABILITY',
            'severity': 'MEDIUM',
            'description': 'Database deadlocks detected under concurrent load'
        },
        {
            'pattern': 'vulnerabilidades',
            'type': 'GENERAL_VULNERABILITY',
            'severity': 'MEDIUM',
            'description': 'General security vulnerabilities detected'
        }
    ]
    
    for pattern_info in security_patterns:
        if pattern_info['pattern'] in output_lower:
            issues.append({
                'type': pattern_info['type'],
                'description': pattern_info['description'],
                'severity': pattern_info['severity'],
                'category': category
            })
    
    return issues

def calculate_security_score(results: list, security_issues: list) -> float:
    """Calcular puntuación de seguridad"""
    base_score = 100.0
    
    # Penalizar por tests fallidos
    failed_tests = sum(1 for r in results if not r['success'])
    total_tests = len(results)
    
    if total_tests > 0:
        test_penalty = (failed_tests / total_tests) * 30  # Hasta -30 puntos
        base_score -= test_penalty
    
    # Penalizar por vulnerabilidades encontradas
    critical_issues = sum(1 for i in security_issues if i['severity'] == 'CRITICAL')
    high_issues = sum(1 for i in security_issues if i['severity'] == 'HIGH')
    medium_issues = sum(1 for i in security_issues if i['severity'] == 'MEDIUM')
    low_issues = sum(1 for i in security_issues if i['severity'] == 'LOW')
    
    # Penalizaciones por severidad
    base_score -= critical_issues * 25  # -25 por cada crítica
    base_score -= high_issues * 15      # -15 por cada alta
    base_score -= medium_issues * 8     # -8 por cada media
    base_score -= low_issues * 3        # -3 por cada baja
    
    # Asegurar que no sea negativa
    return max(0.0, base_score)

if __name__ == "__main__":
    exit_code = run_security_test_suite()
    sys.exit(exit_code)