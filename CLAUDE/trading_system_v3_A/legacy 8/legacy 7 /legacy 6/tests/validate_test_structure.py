#!/usr/bin/env python3
"""
Validador de Estructura de Tests
Script para validar que la estructura organizadas de tests esté correcta
"""

import os
from pathlib import Path
from typing import Dict, List, Set

def validate_test_structure() -> Dict:
    """Validar estructura completa de tests"""
    base_path = Path(__file__).parent
    
    results = {
        'structure_valid': True,
        'missing_categories': [],
        'missing_files': [],
        'unexpected_files': [],
        'category_completeness': {},
        'total_tests_found': 0,
        'recommendations': []
    }
    
    # Estructura esperada
    expected_structure = {
        'basic': {
            'description': 'Tests básicos y fundamentales',
            'required_files': [
                'test_trades_history.py',
                'fix_trades_history.py'
            ],
            'optional_files': []
        },
        'advanced': {
            'description': 'Tests avanzados y específicos',
            'required_files': [
                'test_trades_advanced.py',
                'test_trades_migration.py'
            ],
            'optional_files': []
        },
        'performance': {
            'description': 'Tests de rendimiento',
            'required_files': [
                'test_stress_limits.py'
            ],
            'optional_files': []
        },
        'security': {
            'description': 'Tests de seguridad',
            'required_files': [
                'test_security_robustness.py'
            ],
            'optional_files': []
        },
        'integration': {
            'description': 'Tests de integración',
            'required_files': [
                'test_streamlit_integration.py'
            ],
            'optional_files': []
        },
        'simulation': {
            'description': 'Tests de simulación realista',
            'required_files': [
                'test_trading_simulation.py'
            ],
            'optional_files': []
        },
        'recovery': {
            'description': 'Tests de recuperación',
            'required_files': [
                'test_system_recovery.py'
            ],
            'optional_files': []
        },
        'configuration': {
            'description': 'Tests de configuración',
            'required_files': [
                'test_configuration_validation.py'
            ],
            'optional_files': []
        },
        'network': {
            'description': 'Tests de conectividad',
            'required_files': [
                'test_network_resilience.py'
            ],
            'optional_files': []
        }
    }
    
    # Archivos requeridos en el directorio raíz
    root_required_files = [
        'README.md',
        'run_all_tests_organized.py',
        'run_all_tests_extended.py',
        'run_basic_tests.py',
        'run_security_tests.py',
        'run_performance_tests.py'
    ]
    
    print("🔍 VALIDANDO ESTRUCTURA DE TESTS")
    print("=" * 50)
    
    # Validar directorios de categorías
    for category, info in expected_structure.items():
        category_path = base_path / category
        
        print(f"\n📂 Validando categoría: {category}")
        print(f"   Descripción: {info['description']}")
        
        if not category_path.exists():
            results['missing_categories'].append(category)
            results['structure_valid'] = False
            print(f"   ❌ Directorio faltante: {category}")
            continue
        
        # Verificar archivos requeridos
        category_results = {
            'found_files': 0,
            'missing_files': 0,
            'required_count': len(info['required_files'])
        }
        
        for required_file in info['required_files']:
            file_path = category_path / required_file
            if file_path.exists():
                category_results['found_files'] += 1
                results['total_tests_found'] += 1
                print(f"   ✅ {required_file}")
            else:
                category_results['missing_files'] += 1
                results['missing_files'].append(f"{category}/{required_file}")
                results['structure_valid'] = False
                print(f"   ❌ Faltante: {required_file}")
        
        results['category_completeness'][category] = category_results
    
    # Validar archivos del directorio raíz
    print(f"\n📁 Validando archivos del directorio raíz:")
    for required_file in root_required_files:
        file_path = base_path / required_file
        if file_path.exists():
            print(f"   ✅ {required_file}")
        else:
            results['missing_files'].append(required_file)
            results['structure_valid'] = False
            print(f"   ❌ Faltante: {required_file}")
    
    # Buscar archivos inesperados (legacy tests)
    print(f"\n🔍 Buscando archivos legacy/inesperados:")
    
    # Archivos que deberían estar organizados en categorías
    legacy_patterns = [
        'test_*.py',  # Tests sueltos en el directorio raíz
        'backtest_*.py',  # Backtests
        'conftest.py',  # Config de pytest
        'monkey_tester.py'  # Otros tests
    ]
    
    for file_path in base_path.iterdir():
        if file_path.is_file() and file_path.suffix == '.py':
            filename = file_path.name
            
            # Omitir archivos válidos del directorio raíz
            if filename in [f.name for f in [base_path / f for f in root_required_files + ['validate_test_structure.py']]]:
                continue
            
            # Detectar archivos que no pertenecen a la estructura organizada
            if any(filename.startswith(pattern.replace('*', '')) or filename == pattern.replace('*', '') for pattern in ['test_', 'backtest_', 'conftest.py', 'monkey_tester.py']):
                results['unexpected_files'].append(filename)
                print(f"   ⚠️  Archivo legacy encontrado: {filename}")
    
    # Generar recomendaciones
    print(f"\n📊 RESUMEN DE VALIDACIÓN:")
    print(f"   Estructura válida: {'✅ SÍ' if results['structure_valid'] else '❌ NO'}")
    print(f"   Categorías encontradas: {len(expected_structure) - len(results['missing_categories'])}/{len(expected_structure)}")
    print(f"   Tests organizados: {results['total_tests_found']}")
    print(f"   Archivos faltantes: {len(results['missing_files'])}")
    print(f"   Archivos legacy: {len(results['unexpected_files'])}")
    
    # Generar recomendaciones específicas
    if results['missing_categories']:
        results['recommendations'].append(f"Crear directorios faltantes: {', '.join(results['missing_categories'])}")
    
    if results['missing_files']:
        results['recommendations'].append(f"Crear/mover archivos faltantes: {len(results['missing_files'])} archivos")
    
    if results['unexpected_files']:
        results['recommendations'].append(f"Organizar archivos legacy: {len(results['unexpected_files'])} archivos")
    
    # Mostrar recomendaciones
    if results['recommendations']:
        print(f"\n💡 RECOMENDACIONES:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"   {i}. {rec}")
    
    # Estadísticas detalladas por categoría
    print(f"\n📋 COMPLETITUD POR CATEGORÍA:")
    for category, completeness in results['category_completeness'].items():
        completion_rate = (completeness['found_files'] / completeness['required_count'] * 100) if completeness['required_count'] > 0 else 100
        status = "✅" if completion_rate == 100 else "⚠️" if completion_rate >= 50 else "❌"
        
        print(f"   {status} {category.capitalize()}: {completion_rate:.0f}% ({completeness['found_files']}/{completeness['required_count']})")
    
    return results

def generate_cleanup_script(validation_results: Dict):
    """Generar script de limpieza para archivos legacy"""
    if not validation_results['unexpected_files']:
        print("\n✅ No hay archivos legacy para limpiar")
        return
    
    cleanup_script = "#!/bin/bash\n"
    cleanup_script += "# Script generado automáticamente para limpiar archivos legacy\n"
    cleanup_script += "echo 'Limpiando archivos legacy de tests...'\n\n"
    
    base_path = Path(__file__).parent
    
    for unexpected_file in validation_results['unexpected_files']:
        file_path = base_path / unexpected_file
        
        # Determinar destino apropiado basado en el nombre del archivo
        if unexpected_file.startswith('test_gap_go'):
            destination = "simulation/"
        elif unexpected_file.startswith('test_volume'):
            destination = "simulation/"
        elif unexpected_file.startswith('test_risk'):
            destination = "advanced/"
        elif unexpected_file.startswith('test_position'):
            destination = "advanced/"
        elif unexpected_file.startswith('test_stop'):
            destination = "advanced/"
        elif unexpected_file.startswith('backtest_'):
            destination = "simulation/"
        elif unexpected_file.startswith('test_'):
            destination = "advanced/"  # Por defecto
        else:
            destination = "misc/"
            cleanup_script += f"mkdir -p misc\n"
        
        cleanup_script += f"echo 'Moviendo {unexpected_file} a {destination}'\n"
        cleanup_script += f"mv {unexpected_file} {destination}\n"
    
    cleanup_script += "\necho 'Limpieza completada!'\n"
    
    cleanup_script_path = base_path / "cleanup_legacy_tests.sh"
    
    try:
        with open(cleanup_script_path, 'w') as f:
            f.write(cleanup_script)
        
        os.chmod(cleanup_script_path, 0o755)  # Hacer ejecutable
        
        print(f"\n📝 Script de limpieza generado: {cleanup_script_path.name}")
        print("   Para ejecutar: ./cleanup_legacy_tests.sh")
        
    except Exception as e:
        print(f"\n⚠️  Error generando script de limpieza: {e}")

def main():
    """Función principal"""
    validation_results = validate_test_structure()
    
    if validation_results['structure_valid']:
        print(f"\n🎉 ¡ESTRUCTURA DE TESTS VÁLIDA!")
        print("✅ Todos los tests están organizados correctamente")
        print("🚀 Sistema listo para ejecución de tests organizados")
    else:
        print(f"\n⚠️  ESTRUCTURA REQUIERE ATENCIÓN")
        print(f"🔧 {len(validation_results['missing_files'])} archivos faltantes")
        print(f"📦 {len(validation_results['unexpected_files'])} archivos legacy por organizar")
    
    # Generar script de limpieza si es necesario
    generate_cleanup_script(validation_results)
    
    print(f"\n🏁 Validación completada")
    
    return 0 if validation_results['structure_valid'] else 1

if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)