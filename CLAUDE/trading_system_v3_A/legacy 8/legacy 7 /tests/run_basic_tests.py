#!/usr/bin/env python3
"""
Ejecutor de Tests Básicos y Críticos
Ejecuta únicamente los tests esenciales que deben pasar siempre
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

def run_basic_test_suite():
    """Ejecutar suite de tests básicos y críticos"""
    print("🧪 EJECUTANDO TESTS BÁSICOS Y CRÍTICOS")
    print("=" * 50)
    print(f"🕐 Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Tests críticos que DEBEN pasar siempre
    critical_tests = [
        {
            'category': 'BASIC',
            'script': 'basic/test_trades_history.py',
            'name': 'Tests Básicos de Trades',
            'timeout': 120,  # 2 minutos
            'critical': True
        },
        {
            'category': 'SECURITY',
            'script': 'security/test_security_robustness.py',
            'name': 'Tests de Seguridad',
            'timeout': 240,  # 4 minutos
            'critical': True
        },
        {
            'category': 'CONFIG',
            'script': 'configuration/test_configuration_validation.py',
            'name': 'Validación de Configuración',
            'timeout': 180,  # 3 minutos
            'critical': True
        }
    ]
    
    results = []
    start_time = time.time()
    
    for test in critical_tests:
        print(f"\n{'='*60}")
        print(f"🔍 EJECUTANDO: {test['name']}")
        print(f"📂 Categoría: {test['category']}")
        print(f"📝 Script: {test['script']}")
        print(f"{'='*60}")
        
        test_start = time.time()
        
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
                    'execution_time': 0
                })
                continue
            
            # Ejecutar test
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, timeout=test['timeout'])
            
            execution_time = time.time() - test_start
            
            # Mostrar output
            if result.stdout:
                print(result.stdout)
            
            if result.stderr and result.returncode != 0:
                print(f"❌ ERRORES:\n{result.stderr}")
            
            success = result.returncode == 0
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'success': success,
                'execution_time': execution_time,
                'return_code': result.returncode
            })
            
            if success:
                print(f"\n✅ {test['name']}: COMPLETADO EXITOSAMENTE")
            else:
                print(f"\n❌ {test['name']}: FALLÓ (código: {result.returncode})")
            
            print(f"⏱️  Tiempo de ejecución: {execution_time:.1f}s")
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - test_start
            print(f"\n⏰ TIMEOUT: {test['name']} excedió {test['timeout']/60:.1f} minutos")
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'success': False,
                'error': f"Timeout después de {test['timeout']/60:.1f} minutos",
                'execution_time': execution_time
            })
            
        except Exception as e:
            execution_time = time.time() - test_start
            print(f"\n❌ ERROR ejecutando {test['name']}: {e}")
            
            results.append({
                'name': test['name'],
                'category': test['category'],
                'success': False,
                'error': str(e),
                'execution_time': execution_time
            })
    
    # Resumen final
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print("📊 RESUMEN DE TESTS BÁSICOS Y CRÍTICOS")
    print(f"{'='*60}")
    
    successful_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    failed_tests = [r for r in results if not r['success']]
    
    print(f"⏱️  Tiempo total: {total_time/60:.1f} minutos")
    print(f"📊 Tests ejecutados: {total_tests}")
    print(f"✅ Tests exitosos: {successful_tests}")
    print(f"❌ Tests fallidos: {len(failed_tests)}")
    print(f"📈 Tasa de éxito: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
    
    # Detalle de resultados por categoría
    print(f"\n📋 RESULTADOS POR CATEGORÍA:")
    categories = {}
    for result in results:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'passed': 0, 'total': 0}
        categories[cat]['total'] += 1
        if result['success']:
            categories[cat]['passed'] += 1
    
    for category, stats in categories.items():
        status = "✅ PASS" if stats['passed'] == stats['total'] else "❌ FAIL"
        print(f"   {category}: {status} ({stats['passed']}/{stats['total']})")
    
    # Mostrar tests fallidos
    if failed_tests:
        print(f"\n🚨 TESTS FALLIDOS:")
        for test in failed_tests:
            print(f"   ❌ {test['name']} ({test['category']})")
            if 'error' in test:
                print(f"      Error: {test['error']}")
    
    # Evaluación final
    print(f"\n{'='*60}")
    if successful_tests == total_tests:
        print("🎉 ¡TODOS LOS TESTS CRÍTICOS PASARON!")
        print("✅ Sistema listo para operación básica")
        print("🚀 Funcionalidad core validada")
        exit_code = 0
    elif successful_tests >= total_tests * 0.8:
        print("⚠️  LA MAYORÍA DE TESTS CRÍTICOS PASARON")
        print(f"🔧 {len(failed_tests)} test(s) requieren atención")
        print("📋 Revisar fallos antes de continuar")
        exit_code = 1
    else:
        print("🚨 MÚLTIPLES TESTS CRÍTICOS FALLARON")
        print("❌ Sistema NO LISTO para operación")
        print("🛑 Correcciones URGENTES requeridas")
        exit_code = 2
    
    # Recomendaciones específicas
    print(f"\n💡 RECOMENDACIONES:")
    
    basic_failed = any(r['category'] == 'BASIC' and not r['success'] for r in results)
    security_failed = any(r['category'] == 'SECURITY' and not r['success'] for r in results)
    config_failed = any(r['category'] == 'CONFIG' and not r['success'] for r in results)
    
    if basic_failed:
        print("🔧 PRIORIDAD MÁXIMA: Corregir funcionalidad básica de trades")
    if security_failed:
        print("🛡️  PRIORIDAD ALTA: Resolver vulnerabilidades de seguridad")
    if config_failed:
        print("⚙️  PRIORIDAD ALTA: Validar configuración del sistema")
    
    if successful_tests == total_tests:
        print("🎯 Proceder con tests avanzados: python tests/run_all_tests_extended.py")
    
    print(f"\n🏁 Ejecución completada en {total_time/60:.1f} minutos")
    
    return exit_code

if __name__ == "__main__":
    exit_code = run_basic_test_suite()
    sys.exit(exit_code)