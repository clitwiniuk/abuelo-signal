#!/usr/bin/env python3
"""
Ejecutor Principal - Tests de Optimización News Aging

Script para ejecutar todos los tests de optimización de news aging
con reporting completo y métricas de performance.
"""

import subprocess
import sys
import os
import time
from datetime import datetime
import json


class NewsAgingTestRunner:
    """Test runner for news aging optimization"""
    
    def __init__(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(self.test_dir)))
        self.results = {}
        
    def run_test_file(self, test_file: str) -> dict:
        """Run a single test file and return results"""
        
        print(f"\\n{'='*60}")
        print(f"🧪 EJECUTANDO: {test_file}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Run pytest with verbose output
        cmd = [
            sys.executable, "-m", "pytest", 
            os.path.join(self.test_dir, test_file),
            "-v", "--tb=short", "--no-header", "--color=yes"
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                cwd=self.project_root,
                timeout=300  # 5 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            success = result.returncode == 0
            output = result.stdout
            error = result.stderr
            
            # Count tests
            passed_count = output.count(" PASSED")
            failed_count = output.count(" FAILED")
            skipped_count = output.count(" SKIPPED")
            
            print(output)
            if error:
                print(f"\\n❌ STDERR:\\n{error}")
            
            result_data = {
                'file': test_file,
                'success': success,
                'duration': duration,
                'passed': passed_count,
                'failed': failed_count,
                'skipped': skipped_count,
                'output': output,
                'error': error
            }
            
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"\\n🏁 {test_file}: {status}")
            print(f"   ⏱️  Duration: {duration:.2f}s")
            print(f"   📊 Tests: {passed_count} passed, {failed_count} failed, {skipped_count} skipped")
            
            return result_data
            
        except subprocess.TimeoutExpired:
            print(f"❌ TIMEOUT: {test_file} exceeded 5 minute limit")
            return {
                'file': test_file,
                'success': False,
                'duration': 300.0,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'output': '',
                'error': 'Test timeout'
            }
        
        except Exception as e:
            print(f"❌ ERROR running {test_file}: {e}")
            return {
                'file': test_file,
                'success': False,
                'duration': 0.0,
                'passed': 0,
                'failed': 1,
                'skipped': 0,
                'output': '',
                'error': str(e)
            }
    
    def run_all_tests(self):
        """Run all news aging optimization tests"""
        
        print("🚀 INICIANDO SUITE DE TESTS - OPTIMIZACIÓN NEWS AGING")
        print(f"📁 Directorio: {self.test_dir}")
        print(f"🕒 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        test_files = [
            "test_catalyst_analyzer_aging.py",
            "test_smallcap_scanner_filters.py", 
            "test_time_decay_multipliers.py",
            "test_session_based_filtering.py",
            "test_end_to_end_integration.py"
        ]
        
        total_start_time = time.time()
        
        # Run each test file
        for test_file in test_files:
            self.results[test_file] = self.run_test_file(test_file)
        
        total_duration = time.time() - total_start_time
        
        # Generate summary report
        self.generate_summary_report(total_duration)
        
        # Save detailed results
        self.save_results()
        
        return self.results
    
    def generate_summary_report(self, total_duration: float):
        """Generate comprehensive summary report"""
        
        print(f"\\n{'='*80}")
        print("📋 RESUMEN COMPLETO - OPTIMIZACIÓN NEWS AGING")
        print(f"{'='*80}")
        
        # Calculate totals
        total_files = len(self.results)
        successful_files = sum(1 for r in self.results.values() if r['success'])
        total_passed = sum(r['passed'] for r in self.results.values())
        total_failed = sum(r['failed'] for r in self.results.values())
        total_skipped = sum(r['skipped'] for r in self.results.values())
        total_tests = total_passed + total_failed + total_skipped
        
        print(f"\\n📊 ESTADÍSTICAS GENERALES:")
        print(f"   🗂️  Archivos de test: {successful_files}/{total_files}")
        print(f"   🧪 Tests ejecutados: {total_tests}")
        print(f"   ✅ Tests pasados: {total_passed}")
        print(f"   ❌ Tests fallidos: {total_failed}")
        print(f"   ⏭️  Tests omitidos: {total_skipped}")
        print(f"   ⏱️  Tiempo total: {total_duration:.2f}s")
        print(f"   📈 Tasa de éxito: {(total_passed/max(total_tests,1)):.1%}")
        
        print(f"\\n📋 RESULTADOS POR ARCHIVO:")
        print(f"{'Archivo':<35} {'Estado':<8} {'Pasados':<8} {'Fallidos':<9} {'Tiempo':<8}")
        print("-" * 75)
        
        for file_name, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{file_name:<35} {status:<8} {result['passed']:<8} {result['failed']:<9} {result['duration']:<8.2f}s")
        
        # Detailed analysis per test category
        print(f"\\n🔍 ANÁLISIS POR CATEGORÍA:")
        
        categories = {
            "test_catalyst_analyzer_aging.py": "🧬 CatalystAnalyzer - Aging Diferenciado",
            "test_smallcap_scanner_filters.py": "🔍 Scanner - Filtros Optimizados", 
            "test_time_decay_multipliers.py": "⏰ Time Decay - Multipliers Agresivos",
            "test_session_based_filtering.py": "🕐 Session-Based - Filtrado Inteligente",
            "test_end_to_end_integration.py": "🔗 End-to-End - Integración Completa"
        }
        
        for file_name, description in categories.items():
            if file_name in self.results:
                result = self.results[file_name]
                status = "✅" if result['success'] else "❌"
                print(f"   {status} {description}")
                if not result['success'] and result['error']:
                    print(f"      🚨 Error: {result['error'][:100]}...")
        
        # Performance metrics
        avg_duration = total_duration / max(total_files, 1)
        tests_per_second = total_tests / max(total_duration, 1)
        
        print(f"\\n⚡ MÉTRICAS DE PERFORMANCE:")
        print(f"   📊 Tests por segundo: {tests_per_second:.1f}")
        print(f"   ⏱️  Tiempo promedio por archivo: {avg_duration:.2f}s")
        print(f"   🎯 Coverage estimado: {min(100.0, total_passed * 2):.0f}%")
        
        # Overall assessment
        print(f"\\n🎯 EVALUACIÓN GENERAL:")
        
        if total_failed == 0 and successful_files == total_files:
            print("   🏆 ¡EXCELENTE! Todos los tests pasaron correctamente")
            print("   ✨ La optimización de news aging está funcionando perfectamente")
        elif total_failed <= 2:
            print("   ✅ BUENO: Mayoría de tests pasaron, revisar fallos menores")
        else:
            print("   ⚠️  ATENCIÓN: Múltiples fallos detectados, revisar implementación")
        
        # Recommendations
        print(f"\\n💡 RECOMENDACIONES:")
        
        if total_failed > 0:
            print("   🔧 Revisar tests fallidos y corregir implementación")
            
        if total_duration > 60:
            print("   ⚡ Considerar optimización de performance de tests")
            
        if total_skipped > 0:
            print(f"   ⏭️  Revisar {total_skipped} tests omitidos")
        
        print("   📈 Ejecutar regularmente para validar regresiones")
        print("   🧪 Agregar tests adicionales para edge cases")
    
    def save_results(self):
        """Save detailed results to JSON file"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(self.test_dir, f"test_results_{timestamp}.json")
        
        # Prepare results for JSON serialization
        json_results = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_files': len(self.results),
                'successful_files': sum(1 for r in self.results.values() if r['success']),
                'total_passed': sum(r['passed'] for r in self.results.values()),
                'total_failed': sum(r['failed'] for r in self.results.values()),
                'total_skipped': sum(r['skipped'] for r in self.results.values()),
                'total_duration': sum(r['duration'] for r in self.results.values())
            },
            'detailed_results': self.results
        }
        
        try:
            with open(results_file, 'w') as f:
                json.dump(json_results, f, indent=2)
            print(f"\\n💾 Resultados guardados en: {results_file}")
        except Exception as e:
            print(f"\\n❌ Error guardando resultados: {e}")


def main():
    """Main execution function"""
    
    runner = NewsAgingTestRunner()
    
    try:
        results = runner.run_all_tests()
        
        # Return appropriate exit code
        all_success = all(r['success'] for r in results.values())
        sys.exit(0 if all_success else 1)
        
    except KeyboardInterrupt:
        print("\\n\\n⚠️  Tests interrumpidos por usuario")
        sys.exit(130)
        
    except Exception as e:
        print(f"\\n\\n❌ Error ejecutando tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()