#!/usr/bin/env python3
"""
Menú Principal - Sistema de Backtesting
======================================

Menú interactivo simple para el sistema de backtesting.
Fácil de usar sin memorizar comandos CLI.
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Importar el sistema
from backtesting_system.core.backtest_runner import BacktestRunner


class BacktestingMenu:
    """Menú principal del sistema de backtesting"""
    
    def __init__(self):
        self.runner = None
        self.workers_info = {
            'macdv': 'MACD Divergence Strategy',
            'daily_plays': 'Daily Catalyst Plays', 
            'vwap': 'VWAP Strategy',
            'momentum_breakout': 'Momentum Breakout Strategy',
            'vcp_smallcap': 'VCP Smallcap Strategy',
            'volume_absorption': 'Volume Absorption Strategy',
            'generic_01': 'Generic Worker Strategy'
        }
        self.use_real_data = True  # Siempre usar datos reales

    def print_header(self):
        """Muestra el header del menú"""
        print("=" * 60)
        print("🎯 SISTEMA DE BACKTESTING PROFESIONAL")
        print("=" * 60)
        print("🎮 MENÚ INTERACTIVO - SISTEMA REORGANIZADO")
        print("📁 Directorio: CLAUDE/trading_system_v3/backtesting_system/")
        print("=" * 60)

    def print_main_menu(self):
        """Muestra el menú principal"""
        print("\n📋 OPCIONES DISPONIBLES:")
        print("=" * 50)
        print("1️⃣  Listar Workers Disponibles")
        print("    📄 Ver todos los robots traders disponibles")
        print("")
        print("2️⃣  Test Individual de Worker")
        print("    🧪 Probar UN robot específico (ej: macdv)")
        print("    📊 Genera estadísticas: win rate, profit factor, etc.")
        print("")
        print("3️⃣  Comparación Multi-Worker")
        print("    🏁 Comparar VARIOS robots para ver cuál es mejor")
        print("    📈 Gráficos comparativos y ranking")
        print("")
        print("4️⃣  Benchmark Completo")
        print("    🚀 Probar TODOS los workers del sistema")
        print("    📋 Reporte completo con recomendaciones")
        print("")
        print("5️⃣  Ver Resultados Generados")
        print("    📁 Revisar archivos JSON y gráficos generados")
        print("")
        print("6️⃣  Ver Base de Datos")
        print("    📊 Información de market_data.db (235K+ barras)")
        print("")
        print("7️⃣  Ejecutar Demo Completo")
        print("    🎯 Demo automático de todas las funcionalidades")
        print("")
        print("0️⃣  Salir")
        print("=" * 50)
        
        # Mostrar fuente de datos
        print(f"\n📊 FUENTE DE DATOS: REALES (market_data.db)")
        print(f"📊 {self.get_database_summary()}")
        print("=" * 50)

    def get_user_choice(self, prompt="Selecciona una opción: "):
        """Obtiene la elección del usuario"""
        while True:
            try:
                choice = input(f"\n{prompt}").strip()
                if choice.isdigit():
                    return int(choice)
                elif choice.lower() == 'q':
                    print("\n\n👋 Saliendo del sistema...")
                    sys.exit(0)
                else:
                    print("❌ Por favor ingresa un número válido.")
                    continue
            except KeyboardInterrupt:
                print("\n\n👋 Saliendo del sistema...")
                sys.exit(0)
            except EOFError:
                print("\n\n⚠️ Input terminado. Saliendo...")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Error: {e}")
                continue

    def list_workers(self):
        """Lista todos los workers disponibles"""
        print("\n📋 WORKERS DISPONIBLES PARA BACKTESTING:")
        print("=" * 50)
        
        for i, (worker_name, description) in enumerate(self.workers_info.items(), 1):
            print(f"  {i}. {worker_name:<20}: {description}")
        
        print(f"\n💡 Total: {len(self.workers_info)} workers disponibles")
        print("📝 Sistema configurado con workers reales del directorio /strategies/workers/")

    def select_worker(self):
        """Permite al usuario seleccionar un worker"""
        workers_list = list(self.workers_info.keys())
        
        print("\n👇 SELECCIONA UN WORKER:")
        print("=" * 30)
        for i, worker_name in enumerate(workers_list, 1):
            print(f"  {i}. {worker_name}")
        print(f"  0. Cancelar")
        print("=" * 30)
        
        choice = self.get_user_choice("Número del worker: ")
        
        if choice == 0:
            return None
        elif 1 <= choice <= len(workers_list):
            return workers_list[choice - 1]
        else:
            print("❌ Selección inválida.")
            return None

    async def test_individual_worker(self):
        """Test individual de un worker"""
        print("\n🧪 TEST INDIVIDUAL DE WORKER")
        print("=" * 40)
        
        # Seleccionar worker
        worker_name = self.select_worker()
        if not worker_name:
            return
        
        # Obtener número de patrones
        try:
            patterns = int(input(f"\nNúmero de patrones a generar (default 50): ").strip() or "50")
            if patterns < 1 or patterns > 1000:
                print("❌ Número de patrones debe estar entre 1 y 1000.")
                return
        except ValueError:
            print("❌ Número inválido. Usando 50 patrones por defecto.")
            patterns = 50
        
        # Preguntar sobre visualizaciones
        visualize = input("\n¿Generar gráficos? (s/n, default s): ").strip().lower()
        if visualize not in ['n', 'no', 'false']:
            visualize = True
        else:
            visualize = False
        
        print(f"\n🚀 Iniciando test para worker: {worker_name}")
        print(f"   Patrones: {patterns}")
        print(f"   Visualizaciones: {'Sí' if visualize else 'No'}")
        
        try:
            # Ejecutar test
            metrics = await self.runner.run_single_worker_test(
                worker_name=worker_name,
                num_patterns=patterns,
                visualize=visualize,
                detailed=True
            )
            
            # Mostrar resultados
            if 'error' not in metrics:
                print(f"\n✅ Test completado exitosamente!")
                print(f"\n📊 RESULTADOS PARA {worker_name.upper()}:")
                print("-" * 40)
                print(f"   Win Rate: {metrics.get('win_rate', 0):.1%}")
                print(f"   Average Return: {metrics.get('avg_return', 0):+.2f}%")
                print(f"   Profit Factor: {metrics.get('profit_factor', 0):.2f}")
                print(f"   Total Trades: {metrics.get('total_trades', 0)}")
                print(f"   Execution Rate: {metrics.get('execution_rate', 0):.1%}")
            else:
                print(f"❌ Error en el test: {metrics['error']}")
                
        except Exception as e:
            print(f"❌ Error ejecutando test: {e}")

    async def compare_workers(self):
        """Comparación entre múltiples workers"""
        print("\n🏁 COMPARACIÓN MULTI-WORKER")
        print("=" * 40)
        
        print("👇 Selecciona workers para comparar (máximo 5):")
        workers_list = list(self.workers_info.keys())
        selected_workers = []
        
        for i, worker_name in enumerate(workers_list, 1):
            print(f"  {i}. {worker_name}")
        
        print("\nIngresa números separados por comas (ej: 1,3,5)")
        print("Presiona Enter para continuar cuando termines")
        print("Escribe 0 para cancelar")
        
        try:
            while len(selected_workers) < 5:
                choice = input(f"\nWorker {len(selected_workers)+1} (0 para terminar): ").strip()
                
                if choice == "0" or not choice:
                    break
                    
                try:
                    num = int(choice)
                    if 1 <= num <= len(workers_list):
                        worker_name = workers_list[num - 1]
                        if worker_name not in selected_workers:
                            selected_workers.append(worker_name)
                            print(f"   ✅ {worker_name} añadido")
                        else:
                            print(f"   ⚠️ {worker_name} ya está seleccionado")
                    else:
                        print(f"   ❌ Número inválido (1-{len(workers_list)})")
                except ValueError:
                    print("   ❌ Ingresa un número válido")
        except KeyboardInterrupt:
            return
        
        if len(selected_workers) < 2:
            print("❌ Se necesitan al menos 2 workers para comparar.")
            return
        
        # Obtener parámetros
        try:
            patterns = int(input(f"\nPatrones por worker (default 30): ").strip() or "30")
            visualize = input("\n¿Generar gráficos de comparación? (s/n, default s): ").strip().lower()
            if visualize not in ['n', 'no', 'false']:
                visualize = True
            else:
                visualize = False
        except:
            patterns = 30
            visualize = True
        
        print(f"\n🚀 Ejecutando comparación:")
        print(f"   Workers: {', '.join(selected_workers)}")
        print(f"   Patrones por worker: {patterns}")
        print(f"   Visualizaciones: {'Sí' if visualize else 'No'}")
        
        try:
            results = await self.runner.run_multi_worker_comparison(
                worker_names=selected_workers,
                num_patterns=patterns,
                visualize=visualize
            )
            
            print(f"\n✅ Comparación completada!")
            print(f"\n📊 RESUMEN DE COMPARACIÓN:")
            print("=" * 50)
            
            # Ordenar por win rate
            valid_results = {k: v for k, v in results.items() if 'error' not in v}
            if valid_results:
                sorted_results = sorted(valid_results.items(), 
                                      key=lambda x: x[1].get('win_rate', 0), reverse=True)
                
                for i, (worker_name, metrics) in enumerate(sorted_results, 1):
                    print(f"{i}. {worker_name:<15}: Win Rate {metrics.get('win_rate', 0):.1%}, "
                          f"Return {metrics.get('avg_return', 0):+.2f}%, "
                          f"PF {metrics.get('profit_factor', 0):.2f}")
            
        except Exception as e:
            print(f"❌ Error en comparación: {e}")

    async def run_benchmark(self):
        """Ejecutar benchmark completo"""
        print("\n🚀 BENCHMARK COMPLETO DEL SISTEMA")
        print("=" * 40)
        
        print("Selecciona qué workers incluir:")
        print("1. Todos los workers disponibles")
        print("2. Workers principales (macdv, daily_plays, vwap)")
        print("3. Seleccionar workers manualmente")
        
        choice = self.get_user_choice("Opción (1-3): ")
        
        if choice == 1:
            worker_names = list(self.workers_info.keys())
            print(f"✅ Incluyendo todos los {len(worker_names)} workers")
        elif choice == 2:
            worker_names = ['macdv', 'daily_plays', 'vwap']
            print("✅ Incluyendo workers principales")
        elif choice == 3:
            # Selección manual similar a compare_workers
            print("👇 Selecciona workers para benchmark:")
            worker_names = []
            workers_list = list(self.workers_info.keys())
            
            # [Implementación similar a compare_workers]
            print("Funcionalidad de selección manual disponible en próxima versión")
            worker_names = ['macdv', 'daily_plays', 'vwap']  # Fallback
        else:
            print("❌ Opción inválida.")
            return
        
        # Parámetros
        try:
            patterns = int(input(f"\nPatrones por worker (default 50): ").strip() or "50")
        except:
            patterns = 50
        
        print(f"\n🚀 Iniciando benchmark completo...")
        print(f"   Workers: {len(worker_names)}")
        print(f"   Patrones por worker: {patterns}")
        print("   Esto puede tomar varios minutos...")
        
        try:
            benchmark_report = await self.runner.run_benchmark(
                worker_names=worker_names,
                num_patterns=patterns
            )
            
            if 'error' not in benchmark_report:
                summary = benchmark_report.get('summary', {})
                print(f"\n✅ Benchmark completado!")
                print(f"\n📊 RESUMEN DEL BENCHMARK:")
                print("=" * 50)
                print(f"   Workers testados: {benchmark_report['workers_tested']}")
                print(f"   Duración: {benchmark_report['duration_seconds']:.1f} segundos")
                print(f"   Win Rate promedio: {summary.get('aggregate_win_rate', 0):.1%}")
                print(f"   Avg Return promedio: {summary.get('aggregate_avg_return', 0):+.2f}%")
                print(f"   Mejor performer: {summary.get('best_performer', 'N/A')}")
            else:
                print(f"❌ Error en benchmark: {benchmark_report['error']}")
                
        except Exception as e:
            print(f"❌ Error ejecutando benchmark: {e}")

    def view_results(self):
        """Mostrar resultados generados"""
        results_dir = os.path.join(os.path.dirname(__file__), "results", "results")
        charts_dir = os.path.join(os.path.dirname(__file__), "results", "charts")
        
        print("\n📁 RESULTADOS GENERADOS")
        print("=" * 40)
        
        if not os.path.exists(results_dir):
            print("❌ No hay resultados disponibles aún.")
            return
        
        # Listar archivos JSON
        json_files = []
        if os.path.exists(results_dir):
            json_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
        
        if json_files:
            print("📊 Archivos de métricas:")
            for i, file in enumerate(json_files, 1):
                file_path = os.path.join(results_dir, file)
                size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"  {i}. {file}")
                print(f"     Tamaño: {size} bytes | Modificado: {mtime.strftime('%Y-%m-%d %H:%M')}")
        
        # Listar gráficos
        chart_files = []
        if os.path.exists(charts_dir):
            chart_files = [f for f in os.listdir(charts_dir) if f.endswith('.png')]
        
        if chart_files:
            print(f"\n📈 Gráficos generados:")
            for i, file in enumerate(chart_files, 1):
                file_path = os.path.join(charts_dir, file)
                size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"  {i}. {file}")
                print(f"     Tamaño: {size} bytes | Modificado: {mtime.strftime('%Y-%m-%d %H:%M')}")
        
        if not json_files and not chart_files:
            print("❌ No se encontraron archivos de resultados.")

    def get_database_summary(self) -> str:
        """Obtener resumen de la base de datos"""
        try:
            from core.data_loader_real import DataLoaderReal
            data_loader = DataLoaderReal()
            summary = data_loader.get_database_summary()
            
            total_symbols = summary.get('total_symbols', 0)
            total_bars = summary.get('total_bars', 0)
            
            if total_symbols > 0:
                return f"{total_symbols} símbolos, {total_bars:,} barras"
            else:
                return "Base de datos no disponible"
                
        except Exception as e:
            return f"Error cargando base de datos: {str(e)[:50]}"
    
    async def show_database_info(self):
        """Mostrar información detallada de la base de datos"""
        print("\n📊 INFORMACIÓN DE LA BASE DE DATOS")
        print("=" * 40)
        
        try:
            from core.data_loader_real import DataLoaderReal
            data_loader = DataLoaderReal()
            
            # Resumen general
            summary = data_loader.get_database_summary()
            print(f"\n📈 Resumen General:")
            print(f"   Total barras: {summary.get('total_bars', 0):,}")
            print(f"   Símbolos: {summary.get('total_symbols', 0)}")
            print(f"   Período: {summary.get('date_range', {}).get('first', 'N/A')[:10]} a {summary.get('date_range', {}).get('last', 'N/A')[:10]}")
            print(f"   Rango de precios: ${summary.get('price_range', {}).get('min', 0):.2f} - ${summary.get('price_range', {}).get('max', 0):.2f}")
            print(f"   Volumen promedio: {summary.get('avg_volume', 0):,.0f}")
            
            # Símbolos principales
            top_symbols = summary.get('top_symbols', [])
            if top_symbols:
                print(f"\n🏆 Top Símbolos:")
                for symbol in top_symbols[:5]:
                    print(f"   {symbol['symbol']}: {symbol['bars']:,} barras")
            
            # Oportunidades disponibles
            print(f"\n🎯 Analizando oportunidades disponibles...")
            opportunities = data_loader.load_real_opportunities(
                symbols=None,
                start_date=None,
                end_date=None,
                min_volume=10000,
                pattern_type='all'
            )
            
            print(f"   Oportunidades encontradas: {len(opportunities):,}")
            
            # Distribución por tipo
            if opportunities:
                pattern_counts = {}
                for opp in opportunities:
                    pattern_type = opp.get('pattern_type', 'unknown')
                    pattern_counts[pattern_type] = pattern_counts.get(pattern_type, 0) + 1
                
                print(f"\n📊 Distribución por Patrón:")
                for pattern, count in sorted(pattern_counts.items()):
                    print(f"   {pattern}: {count:,} oportunidades")
                
                # Calidad promedio
                avg_quality = sum(opp.get('quality_score', 50) for opp in opportunities) / len(opportunities)
                print(f"\n⭐ Calidad promedio: {avg_quality:.1f}/100")
            
        except Exception as e:
            print(f"❌ Error cargando información de la base de datos: {e}")
        
        input("\nPresiona Enter para continuar...")

    async def run_demo(self):
        """Ejecutar demo completo"""
        print("\n🎯 EJECUTANDO DEMO COMPLETO")
        print("=" * 40)
        print("🚀 Esto ejecutará un test completo con todos los workers...")
        print("📊 Usando datos reales de market_data.db")
        print("⏱️  Tiempo estimado: 2-3 minutos")
        print("📊 Se generarán gráficos y reportes completos")
        
        confirm = input("\n¿Continuar con el demo completo? (s/n): ").strip().lower()
        if confirm in ['n', 'no', 'false']:
            return
        
        try:
            # Importar y ejecutar demo
            from examples.demo_backtesting import main as demo_main
            
            print("\n🎯 Iniciando demo completo...")
            await demo_main()
            
        except Exception as e:
            print(f"❌ Error ejecutando demo: {e}")

    async def run(self):
        """Ejecutar el menú principal"""
        # Inicializar runner
        try:
            self.runner = BacktestRunner(output_dir="results")
        except Exception as e:
            print(f"❌ Error inicializando sistema: {e}")
            return
        
        while True:
            try:
                self.print_header()
                self.print_main_menu()
                
                choice = self.get_user_choice()
                
                if choice == 0:
                    print("\n👋 ¡Gracias por usar el Sistema de Backtesting!")
                    break
                elif choice == 1:
                    self.list_workers()
                elif choice == 2:
                    await self.test_individual_worker()
                elif choice == 3:
                    await self.compare_workers()
                elif choice == 4:
                    await self.run_benchmark()
                elif choice == 5:
                    self.view_results()
                elif choice == 6:
                    await self.show_database_info()
                elif choice == 7:
                    await self.run_demo()
                else:
                    print("❌ Opción no válida.")
                
                # Pausa antes de continuar
                input("\n📱 Presiona Enter para continuar...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Saliendo del sistema...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("📱 Presiona Enter para continuar...")


async def main():
    """Función principal"""
    menu = BacktestingMenu()
    await menu.run()


if __name__ == "__main__":
    # Configurar event loop para Windows compatibility
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ejecutar menú
    asyncio.run(main())