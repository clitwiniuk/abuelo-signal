#!/usr/bin/env python3
"""
Runner maestro para todos los tests avanzados del sistema de producción
Ejecuta tests de estrés extremo, simulación de mercado y resistencia de red
"""

import asyncio
import logging
import time
import json
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_production_stress_extreme import run_extreme_stress_tests
from test_production_market_simulation import run_market_simulation_tests
from test_production_network_resilience import run_network_resilience_tests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def run_all_advanced_tests():
    """Ejecutar toda la suite de tests avanzados"""
    
    print("🚀 SISTEMA DE TESTS AVANZADOS - SMALLCAP PRODUCTION")
    print("=" * 80)
    print("🎯 Objetivo: Poner a prueba el sistema bajo condiciones extremas")
    print("📊 Tests incluidos:")
    print("   • Tests de Estrés Extremo (1000+ plays concurrentes)")
    print("   • Simulación de Condiciones de Mercado")
    print("   • Tests de Resistencia de Red")
    print("=" * 80)
    
    overall_start_time = time.time()
    all_results = {}
    
    # 1. Tests de Estrés Extremo
    print(f"\n🔥 FASE 1: TESTS DE ESTRÉS EXTREMO")
    print("=" * 60)
    try:
        stress_results = await run_extreme_stress_tests()
        all_results["extreme_stress"] = stress_results
        stress_success = sum(1 for r in stress_results if r.get("success", False))
        print(f"✅ Estrés Extremo: {stress_success}/{len(stress_results)} tests pasados")
    except Exception as e:
        logger.error(f"❌ Error en tests de estrés extremo: {e}")
        all_results["extreme_stress"] = {"error": str(e)}
    
    print("\n" + "⏱️ " * 20)
    await asyncio.sleep(2)  # Brief pause between test suites
    
    # 2. Tests de Simulación de Mercado
    print(f"\n📈 FASE 2: SIMULACIÓN DE CONDICIONES DE MERCADO")
    print("=" * 60)
    try:
        market_results = await run_market_simulation_tests()
        all_results["market_simulation"] = market_results
        market_success = sum(1 for r in market_results if r.get("success", False))
        print(f"✅ Simulación de Mercado: {market_success}/{len(market_results)} tests pasados")
    except Exception as e:
        logger.error(f"❌ Error en tests de simulación de mercado: {e}")
        all_results["market_simulation"] = {"error": str(e)}
    
    print("\n" + "⏱️ " * 20)
    await asyncio.sleep(2)  # Brief pause between test suites
    
    # 3. Tests de Resistencia de Red
    print(f"\n🌐 FASE 3: TESTS DE RESISTENCIA DE RED")
    print("=" * 60)
    try:
        network_results = await run_network_resilience_tests()
        all_results["network_resilience"] = network_results
        network_success = sum(1 for r in network_results if r.get("success", False))
        print(f"✅ Resistencia de Red: {network_success}/{len(network_results)} tests pasados")
    except Exception as e:
        logger.error(f"❌ Error en tests de resistencia de red: {e}")
        all_results["network_resilience"] = {"error": str(e)}
    
    overall_end_time = time.time()
    total_time = overall_end_time - overall_start_time
    
    # Calcular estadísticas generales
    total_tests = 0
    total_successful = 0
    
    for suite_name, suite_results in all_results.items():
        if isinstance(suite_results, list):
            total_tests += len(suite_results)
            total_successful += sum(1 for r in suite_results if r.get("success", False))
    
    # Resumen final
    print("\n" + "=" * 80)
    print("🏆 RESUMEN FINAL - TESTS AVANZADOS")
    print("=" * 80)
    print(f"⏱️  Tiempo total de ejecución: {total_time:.2f} segundos")
    print(f"🧪 Tests totales ejecutados: {total_tests}")
    print(f"✅ Tests exitosos: {total_successful}")
    print(f"❌ Tests fallidos: {total_tests - total_successful}")
    print(f"📊 Tasa de éxito: {total_successful / total_tests * 100:.1f}%" if total_tests > 0 else "📊 Tasa de éxito: N/A")
    
    print(f"\n📋 DESGLOSE POR CATEGORÍA:")
    
    # Estrés Extremo
    if "extreme_stress" in all_results and isinstance(all_results["extreme_stress"], list):
        stress_results = all_results["extreme_stress"]
        stress_success = sum(1 for r in stress_results if r.get("success", False))
        stress_status = "🔥" if stress_success == len(stress_results) else "⚠️" if stress_success >= len(stress_results) * 0.8 else "❌"
        print(f"{stress_status} Estrés Extremo: {stress_success}/{len(stress_results)} ({stress_success/len(stress_results)*100:.1f}%)")
        
        for result in stress_results:
            test_name = result.get("test", "unknown").replace('_', ' ').title()
            status = "✅" if result.get("success", False) else "❌"
            print(f"   {status} {test_name}")
    
    # Simulación de Mercado
    if "market_simulation" in all_results and isinstance(all_results["market_simulation"], list):
        market_results = all_results["market_simulation"]
        market_success = sum(1 for r in market_results if r.get("success", False))
        market_status = "📈" if market_success == len(market_results) else "⚠️" if market_success >= len(market_results) * 0.8 else "❌"
        print(f"{market_status} Simulación de Mercado: {market_success}/{len(market_results)} ({market_success/len(market_results)*100:.1f}%)")
        
        for result in market_results:
            test_name = result.get("test", "unknown").replace('_', ' ').title()
            status = "✅" if result.get("success", False) else "❌"
            print(f"   {status} {test_name}")
    
    # Resistencia de Red
    if "network_resilience" in all_results and isinstance(all_results["network_resilience"], list):
        network_results = all_results["network_resilience"]
        network_success = sum(1 for r in network_results if r.get("success", False))
        network_status = "🌐" if network_success == len(network_results) else "⚠️" if network_success >= len(network_results) * 0.8 else "❌"
        print(f"{network_status} Resistencia de Red: {network_success}/{len(network_results)} ({network_success/len(network_results)*100:.1f}%)")
        
        for result in network_results:
            test_name = result.get("test", "unknown").replace('_', ' ').title()
            status = "✅" if result.get("success", False) else "❌"
            print(f"   {status} {test_name}")
    
    # Evaluación final del sistema
    print(f"\n🎯 EVALUACIÓN FINAL DEL SISTEMA:")
    
    if total_tests > 0:
        success_rate = total_successful / total_tests * 100
        
        if success_rate >= 95:
            print("🏆 SISTEMA EXCEPCIONAL - Pasa todos los tests extremos")
            print("   ✅ Listo para producción bajo cualquier condición")
            print("   ✅ Maneja estrés extremo, volatilidad y fallos de red")
            print("   ✅ Rendimiento y estabilidad excepcionales")
        elif success_rate >= 85:
            print("🥇 SISTEMA ROBUSTO - Excelente rendimiento general")
            print("   ✅ Listo para producción con monitoreo normal")
            print("   ✅ Maneja la mayoría de condiciones extremas")
            print("   ⚠️  Algunos casos extremos necesitan atención")
        elif success_rate >= 70:
            print("🥈 SISTEMA SÓLIDO - Buen rendimiento con algunas debilidades")
            print("   ⚠️  Necesita mejoras antes de producción completa")
            print("   ✅ Funciona bien en condiciones normales")
            print("   ❌ Algunas condiciones extremas causan problemas")
        else:
            print("🥉 SISTEMA NECESITA TRABAJO - Rendimiento insuficiente")
            print("   ❌ NO listo para producción")
            print("   ❌ Múltiples fallos en condiciones extremas")
            print("   🔧 Requiere refactoring significativo")
    
    # Métricas de rendimiento destacadas
    print(f"\n📊 MÉTRICAS DESTACADAS:")
    
    # Buscar métricas interesantes en los resultados
    for suite_name, suite_results in all_results.items():
        if isinstance(suite_results, list):
            for result in suite_results:
                if "plays_per_second" in result and result["plays_per_second"] > 0:
                    print(f"⚡ {result.get('test', 'Test')}: {result['plays_per_second']:.1f} plays/segundo")
                if "total_plays_processed" in result and result["total_plays_processed"] > 1000:
                    print(f"🔥 {result.get('test', 'Test')}: {result['total_plays_processed']:,} plays procesados")
                if "memory_growth_mb" in result:
                    print(f"🧠 {result.get('test', 'Test')}: {result['memory_growth_mb']:.1f} MB crecimiento memoria")
    
    # Guardar resultados completos
    results_file = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/advanced_tests_complete_results.json"
    
    final_summary = {
        "timestamp": datetime.now().isoformat(),
        "execution_time_seconds": total_time,
        "summary": {
            "total_tests": total_tests,
            "successful_tests": total_successful,
            "failed_tests": total_tests - total_successful,
            "success_rate": success_rate if total_tests > 0 else 0
        },
        "detailed_results": all_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(final_summary, f, indent=2)
    
    print(f"\n💾 Resultados completos guardados en: {results_file}")
    
    # Recomendaciones finales
    print(f"\n🎯 RECOMENDACIONES:")
    
    if total_tests > 0 and success_rate >= 95:
        print("✅ Sistema listo para producción inmediata")
        print("✅ Implementar monitoreo básico")
        print("✅ Configurar alertas para métricas clave")
    elif total_tests > 0 and success_rate >= 85:
        print("⚠️  Revisar tests fallidos antes de producción")
        print("✅ Implementar monitoreo avanzado")
        print("✅ Configurar alertas para casos extremos")
    else:
        print("❌ Resolver issues críticos antes de producción")
        print("🔧 Refactorizar componentes problemáticos")
        print("🧪 Re-ejecutar tests después de fixes")
    
    print("\n" + "=" * 80)
    
    return all_results

if __name__ == "__main__":
    asyncio.run(run_all_advanced_tests())
