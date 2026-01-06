#!/usr/bin/env python3
"""
Ejecutar todos los tests de validación del sistema en orden
"""

import subprocess
import sys
import os
from datetime import datetime

def run_test(test_file, script_dir):
    """Ejecutar un test individual y reportar resultado"""
    print(f"\n{'='*60}")
    print(f"🧪 EJECUTANDO: {test_file}")
    print(f"{'='*60}")
    
    try:
        # Change to project root directory  
        project_root = os.path.dirname(os.path.dirname(script_dir))
        
        # Run the test from project root
        result = subprocess.run([
            sys.executable, f"tests/system_validation/{os.path.basename(test_file)}"
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            print(f"✅ {test_file} - EXITOSO")
            return True
        else:
            print(f"❌ {test_file} - FALLÓ")
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
            print("STDERR:", result.stderr[-500:])
            return False
            
    except Exception as e:
        print(f"❌ {test_file} - ERROR: {e}")
        return False

def main():
    """Ejecutar todos los tests de validación"""
    print("🚀 SISTEMA DE VALIDACIÓN - TESTS COMPLETOS")
    print(f"Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # List of tests in order
    tests = [
        "test_unified_components.py",
        "test_scanner_mock.py", 
        "test_notifications.py",
        "test_integration_final.py",
        "test_sistema_final.py"
    ]
    
    results = {}
    
    # Run each test
    for test in tests:
        test_path = os.path.join(script_dir, test)
        if os.path.exists(test_path):
            results[test] = run_test(test, script_dir)  # Pass filename and script_dir
        else:
            print(f"⚠️  Test no encontrado: {test}")
            results[test] = False
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 RESUMEN FINAL DE VALIDACIÓN")
    print(f"{'='*60}")
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test, success in results.items():
        status = "✅ EXITOSO" if success else "❌ FALLÓ"
        print(f"{test:<40} {status}")
    
    print(f"\n📈 RESULTADO GENERAL:")
    print(f"   Tests ejecutados: {total}")
    print(f"   Tests exitosos: {passed}")
    print(f"   Tests fallidos: {total - passed}")
    print(f"   Tasa de éxito: {passed/total*100:.1f}%")
    
    if passed == total:
        print(f"\n🎉 ¡TODOS LOS TESTS EXITOSOS!")
        print(f"✅ Sistema completamente validado")
        print(f"🚀 Listo para ejecutar: python main.py")
        return 0
    else:
        print(f"\n⚠️  ALGUNOS TESTS FALLARON")
        print(f"🔧 Revisar errores antes de usar en producción")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)