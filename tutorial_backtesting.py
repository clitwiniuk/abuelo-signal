#!/usr/bin/env python3
"""
🚀 Tutorial Rápido - Sistema de Backtesting
=========================================

Script de demostración para verificar que el sistema de backtesting funciona correctamente
en la nueva rama feature/backtesting-system.
"""

import asyncio
import sys
import os

# Agregar el directorio del sistema de backtesting al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backtesting_system'))

async def tutorial_basico():
    """Tutorial básico para verificar funcionalidad"""
    print("🚀 TUTORIAL RÁPIDO - Sistema de Backtesting")
    print("=" * 60)
    print("📍 Rama: feature/backtesting-system")
    print("📅 Fecha:", "2025-11-01")
    print("=" * 60)
    
    try:
        # Intentar importar el sistema
        print("\n1️⃣ Verificando importación del sistema...")
        from backtesting_system.core.backtest_runner import BacktestRunner
        print("   ✅ BacktestRunner importado correctamente")
        
        # Crear runner
        print("\n2️⃣ Creando runner del sistema...")
        runner = BacktestRunner(output_dir="tutorial_results")
        print("   ✅ Runner creado exitosamente")
        
        # Listar workers disponibles
        print("\n3️⃣ Obteniendo lista de workers disponibles...")
        workers = runner.get_available_workers()
        print(f"   ✅ Workers encontrados: {len(workers)}")
        for i, worker_name in enumerate(workers[:5], 1):  # Mostrar solo los primeros 5
            print(f"      {i}. {worker_name}")
        if len(workers) > 5:
            print(f"      ... y {len(workers) - 5} más")
        
        # Test rápido con un worker
        print(f"\n4️⃣ Ejecutando test rápido con 'macdv'...")
        print(f"   📊 Patrones a generar: 10 (para demo rápida)")
        print(f"   🎯 Worker: macdv")
        print(f"   📈 Visualización: Deshabilitada para demo")
        
        # Ejecutar test
        metrics = await runner.run_single_worker_test(
            worker_name="macdv",
            num_patterns=10,  # Pocos patrones para demo rápida
            visualize=False   # Sin visualización para demo
        )
        
        # Mostrar resultados
        print(f"\n5️⃣ Resultados del test:")
        print(f"   📊 Win Rate: {metrics.get('win_rate', 0):.1%}")
        print(f"   💰 Average Return: {metrics.get('avg_return', 0):+.2f}%")
        print(f"   📈 Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        print(f"   🎯 Total Trades: {metrics.get('total_trades', 0)}")
        print(f"   ⚡ Success Rate: {metrics.get('execution_rate', 0):.1%}")
        
        # Verificar archivos generados
        print(f"\n6️⃣ Verificando archivos de resultado...")
        results_dir = "tutorial_results"
        if os.path.exists(results_dir):
            print(f"   📁 Directorio de resultados: {results_dir}")
            # Listar archivos de resultados
            results_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
            if results_files:
                print(f"   📄 Archivos JSON generados: {len(results_files)}")
                for file in results_files[:3]:  # Mostrar solo los primeros 3
                    print(f"      • {file}")
            else:
                print(f"   ⚠️ No se encontraron archivos JSON (normal en demo rápida)")
        else:
            print(f"   📁 Directorio no encontrado: {results_dir}")
        
        print(f"\n✅ TUTORIAL COMPLETADO EXITOSAMENTE")
        print(f"🎯 El sistema de backtesting está funcionando correctamente")
        print(f"🚀 Puedes usar cualquiera de estos métodos:")
        print(f"   1. python backtesting_system/menu_principal.py (FÁCIL)")
        print(f"   2. python backtesting_system/main.py --list-workers (CLI)")
        print(f"   3. Programaticamente con BacktestRunner()")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Error de importación: {e}")
        print(f"   💡 Verifica que el sistema esté correctamente instalado")
        return False
        
    except Exception as e:
        print(f"   ❌ Error ejecutando tutorial: {e}")
        print(f"   💡 Verifica las dependencias del sistema")
        return False


async def tutorial_avanzado():
    """Tutorial más avanzado con comparación multi-worker"""
    print(f"\n\n🚀 TUTORIAL AVANZADO - Comparación Multi-Worker")
    print("=" * 60)
    
    try:
        from backtesting_system.core.backtest_runner import BacktestRunner
        
        runner = BacktestRunner(output_dir="tutorial_comparison")
        
        # Comparar 3 workers
        workers_to_compare = ["macdv", "daily_plays", "vwap"]
        
        print(f"🔄 Comparando {len(workers_to_compare)} workers con 8 patrones cada uno...")
        
        results = await runner.run_multi_worker_comparison(
            worker_names=workers_to_compare,
            num_patterns=8,  # Pocos patrones para demo
            visualize=False  # Sin visualización
        )
        
        print(f"\n📊 Resultados de la comparación:")
        print(f"{'Worker':<15} {'Win Rate':<10} {'Avg Return':<12} {'Status':<10}")
        print("-" * 55)
        
        for worker_name, metrics in results.items():
            if 'error' not in metrics:
                win_rate = metrics.get('win_rate', 0) * 100
                avg_return = metrics.get('avg_return', 0) * 100
                status = "✅ OK"
            else:
                win_rate = 0
                avg_return = 0
                status = f"❌ {metrics['error'][:15]}..."
            
            print(f"{worker_name:<15} {win_rate:<10.1f}% {avg_return:<12.2f}% {status:<10}")
        
        print(f"\n✅ Tutorial avanzado completado")
        return True
        
    except Exception as e:
        print(f"❌ Error en tutorial avanzado: {e}")
        return False


async def main():
    """Función principal del tutorial"""
    print(f"🏗️ RAMA: feature/backtesting-system")
    print(f"📂 Sistema de backtesting profesional para workers de trading")
    print(f"=" * 80)
    
    # Tutorial básico
    success_basic = await tutorial_basico()
    
    if success_basic:
        # Tutorial avanzado
        await tutorial_avanzado()
        
        print(f"\n" + "=" * 80)
        print(f"🎉 TODOS LOS TUTORIALES COMPLETADOS")
        print(f"=" * 80)
        print(f"📚 Para más información, consulta:")
        print(f"   • BACKTESTING_SYSTEM_README.md (esta rama)")
        print(f"   • backtesting_system/README.md (sistema completo)")
        print(f"   • backtesting_system/EJECUTAR_SISTEMA.md (guía paso a paso)")
        
    else:
        print(f"\n❌ Tutorial básico falló. Revisa la instalación del sistema.")


if __name__ == "__main__":
    # Configurar event loop para compatibilidad
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar tutorial
    asyncio.run(main())