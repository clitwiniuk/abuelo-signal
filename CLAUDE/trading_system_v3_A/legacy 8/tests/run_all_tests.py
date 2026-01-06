#!/usr/bin/env python3
"""
Ejecutor de Todos los Tests
===========================

Ejecuta todos los tests de integración y proporciona un resumen completo.
"""

import subprocess
import sys
import time
from pathlib import Path

def run_test(test_file, test_name):
    """Ejecuta un test individual y retorna el resultado"""
    print(f"\n🧪 EJECUTANDO: {test_name}")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=False, 
                              check=True)
        
        duration = time.time() - start_time
        print(f"\n✅ {test_name} - EXITOSO ({duration:.2f}s)")
        return True, duration
        
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        print(f"\n❌ {test_name} - FALLÓ ({duration:.2f}s)")
        return False, duration

def main():
    """Ejecuta todos los tests disponibles"""
    print("🚀 EJECUTANDO SUITE COMPLETA DE TESTS")
    print("=" * 60)
    print("Verificando integración completa del sistema...")
    
    # Tests disponibles
    tests = [
        ("tests/test_quick_integration.py", "Test Rápido de Integración"),
        ("tests/test_integration_complete.py", "Test Completo de Integración"), 
        ("tests/test_streamlit_integration.py", "Test de Integración Streamlit")
    ]
    
    results = []
    total_time = 0
    
    # Ejecutar cada test
    for test_file, test_name in tests:
        if Path(test_file).exists():
            success, duration = run_test(test_file, test_name)
            results.append((test_name, success, duration))
            total_time += duration
        else:
            print(f"⚠️ Test no encontrado: {test_file}")
            results.append((test_name, False, 0))
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success, duration in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"{status:12} | {test_name:35} | {duration:6.2f}s")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"Total: {len(results)} tests | Pasaron: {passed} | Fallaron: {failed}")
    print(f"Tiempo total: {total_time:.2f}s")
    
    # Resultado final
    if failed == 0:
        print("\n🎉 TODOS LOS TESTS PASARON EXITOSAMENTE")
        print("✅ Sistema completamente integrado y funcionando")
        print("✅ Listo para producción")
        
        # Componentes verificados
        print("\n🔧 COMPONENTES VERIFICADOS:")
        print("   • DatabaseManager principal ✅")
        print("   • ScannerIntelligence integrado ✅") 
        print("   • Auto-categorización inteligente ✅")
        print("   • Streamlit integration ✅")
        print("   • ML learning preparado ✅")
        print("   • Flujo completo de datos ✅")
        print("   • Manejo de errores ✅")
        
        return True
    else:
        print(f"\n❌ {failed} TESTS FALLARON")
        print("🔧 Revisar errores antes de usar en producción")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)