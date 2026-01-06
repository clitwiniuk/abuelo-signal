#!/usr/bin/env python3
"""
Script de inicio principal para el Trading System v3.
Proporciona acceso fácil a todas las funcionalidades principales.
"""

import os
import sys
import subprocess
from pathlib import Path

def mostrar_menu():
    """Muestra el menú principal"""
    print("🚀 TRADING SYSTEM V3 - MENÚ PRINCIPAL")
    print("=" * 60)
    print("📋 Opciones Disponibles:")
    print()
    print("   🎮 SIMULACIÓN Y TESTING")
    print("   1. Test básico del mock adapter")
    print("   2. Demo automatizada del sistema")
    print("   3. Menú interactivo de simulación")
    print()
    print("   📊 GESTIÓN DE DATOS")
    print("   4. Descargar datos de mercado")
    print("   5. Verificar datos existentes")
    print()
    print("   📈 TRADING Y BACKTESTING")
    print("   6. Ejecutar sistema principal")
    print("   7. Ejecutar backtest")
    print("   8. Optimizar parámetros")
    print()
    print("   🎯 DATOS SINTÉTICOS")
    print("   12. Generar datos sintéticos desde DB")
    print("   13. Ejecutar sistema con datos sintéticos")
    print("   14. Backtest mejorado con filtros de calidad")
    print("   15. Backtest CORREGIDO con estrategias reales")
    print()
    print("   🔬 OPTIMIZACIÓN DE ESTRATEGIAS")
    print("   16. Optimizador de estrategias (comparar real vs simulado)")
    print("   17. Analizador de código de estrategias")
    print()
    print("   🔧 HERRAMIENTAS")
    print("   9. Ver estructura del proyecto")
    print("   10. Ver documentación")
    print("   11. Limpiar logs y temporales")
    print()
    print("   0. Salir")
    print("=" * 60)

def ejecutar_script(script_path, descripcion):
    """Ejecuta un script Python y maneja errores"""
    print(f"\n🚀 {descripcion}")
    print("-" * 50)
    
    try:
        # Cambiar al directorio del proyecto
        project_dir = Path(__file__).parent
        os.chdir(project_dir)
        
        # Ejecutar el script
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"✅ {descripcion} completado exitosamente")
        else:
            print(f"❌ Error ejecutando {descripcion}")
            
    except FileNotFoundError:
        print(f"❌ Script no encontrado: {script_path}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    input("\n📱 Presiona Enter para continuar...")

def mostrar_estructura():
    """Muestra la estructura del proyecto"""
    print("\n📁 ESTRUCTURA DEL PROYECTO")
    print("-" * 50)
    
    estructura = """
    trading_system_v3/
    ├── 📋 main.py                    # Sistema principal
    ├── 📋 start.py                   # Este menú
    │
    ├── 🎮 simulation/                # Scripts de simulación
    │   ├── simple_mock_test.py       # Test básico
    │   └── test_simulation_interactive.py  # Demo automatizada
    │
    ├── 📂 scripts/
    │   ├── runners/                  # Scripts principales
    │   │   ├── run_simulation.py     # Menú de simulación
    │   │   ├── run_backtest.py       # Backtesting
    │   │   └── run_trading_system.py # Sistema completo
    │   │
    │   └── tools/                    # Herramientas
    │       ├── download_menu.py      # Descarga de datos
    │       ├── optuna_optimizer.py   # Optimización
    │       └── data_verification.py  # Verificación
    │
    ├── 📊 data/csv/                  # Datos históricos (36 símbolos)
    ├── 📈 results/                   # Resultados de backtests
    ├── 📋 logs/                      # Archivos de log
    └── 🏗️ core/, adapters/, strategies/  # Componentes principales
    """
    
    print(estructura)
    input("\n📱 Presiona Enter para continuar...")

def mostrar_documentacion():
    """Muestra el índice de documentación disponible"""
    print("\n📚 DOCUMENTACIÓN DISPONIBLE")
    print("-" * 50)
    
    docs = """
    📋 DOCUMENTOS PRINCIPALES:
    
    🚀 INICIO RÁPIDO:
    • docs/COMO_EJECUTAR_MOCK.md - Cómo usar el sistema con mock
    • docs/SIMULATION_GUIDE.md - Guía completa de simulación  
    • docs/ESTRUCTURA_ORGANIZADA.md - Nueva organización
    
    🏗️ DESARROLLO:
    • docs/ADD_NEW_STRATEGY.md - Crear nuevas estrategias
    • docs/strategy_selection.md - Configurar estrategias
    • docs/THREAD_SAFE_ADAPTER_README.md - Adapter técnico
    
    📈 TRADING:
    • docs/gap_go_procedure_guide.md - Estrategia Gap & Go
    • docs/README_MULTI_STRATEGY.md - Sistema multi-estrategia
    
    💡 RECOMENDACIÓN:
    Empezar con docs/COMO_EJECUTAR_MOCK.md para primer test
    """
    
    print(docs)
    print("📂 Ubicación: ./docs/")
    print("📋 Índice completo: docs/README_DOCS.md")
    input("\n📱 Presiona Enter para continuar...")

def limpiar_temporales():
    """Limpia archivos temporales y logs antiguos"""
    print("\n🧹 LIMPIANDO ARCHIVOS TEMPORALES")
    print("-" * 50)
    
    project_dir = Path(__file__).parent
    limpiados = 0
    
    # Limpiar archivos temporales
    temp_patterns = ["*.pyc", "*.pyo", "__pycache__", "*.tmp", "*.temp"]
    
    for pattern in temp_patterns:
        for file in project_dir.rglob(pattern):
            try:
                if file.is_file():
                    file.unlink()
                    limpiados += 1
                elif file.is_dir():
                    import shutil
                    shutil.rmtree(file)
                    limpiados += 1
            except:
                pass
    
    print(f"✅ Limpiados {limpiados} archivos/carpetas temporales")
    input("\n📱 Presiona Enter para continuar...")

def ejecutar_sistema_sintetico():
    """Ejecuta el sistema de trading con datos sintéticos"""
    print("\n🎯 EJECUTAR SISTEMA CON DATOS SINTÉTICOS")
    print("-" * 50)
    
    # Verificar que existan los datos sintéticos
    if not os.path.exists("synthetic_data"):
        print("❌ Datos sintéticos no encontrados")
        print("💡 Ejecuta primero la opción 12 para generar los datos")
        input("\n📱 Presiona Enter para continuar...")
        return
    
    if not os.path.exists("synthetic_data/events_metadata.csv"):
        print("❌ Archivo de metadatos no encontrado")
        print("💡 Ejecuta primero la opción 12 para generar los datos")
        input("\n📱 Presiona Enter para continuar...")
        return
    
    # Mostrar información de los datos disponibles
    try:
        import pandas as pd
        metadata = pd.read_csv("synthetic_data/events_metadata.csv")
        csv_files = [f for f in os.listdir("synthetic_data") if f.endswith('.csv') and f != 'events_metadata.csv']
        
        print(f"✅ Datos sintéticos encontrados:")
        print(f"   📊 {len(metadata)} eventos disponibles")
        print(f"   📁 {len(csv_files)} archivos CSV")
        print(f"   📈 Ratio promedio: {metadata['ratio_vol'].mean():.1f}x")
        print()
        
        # Mostrar algunos símbolos de ejemplo
        print("📋 Símbolos sintéticos disponibles:")
        ejemplo_symbols = csv_files[:10]  # Primeros 10
        print(f"   {', '.join([f.replace('.csv', '') for f in ejemplo_symbols])}")
        if len(csv_files) > 10:
            print(f"   ... y {len(csv_files) - 10} más")
        print()
        
    except Exception as e:
        print(f"❌ Error leyendo metadatos: {e}")
    
    # Configurar modo TESTING temporalmente
    print("🔧 Configurando sistema en modo TESTING con datos sintéticos...")
    
    # Guardar config original
    config_backup = None
    if os.path.exists("config.ini"):
        with open("config.ini", 'r') as f:
            config_backup = f.read()
    
    try:
        # Escribir config temporal para modo TESTING
        import configparser
        config = configparser.ConfigParser()
        config['TRADING'] = {
            'active_profile': 'TESTING',
            'default_symbols': 'AAAA,AAAB,AAAC,AAAD,AAAE'
        }
        
        with open("config.ini", 'w') as f:
            config.write(f)
        
        print("✅ Configuración temporal establecida")
        print("📊 Símbolos predeterminados: AAAA, AAAB, AAAC, AAAD, AAAE")
        print()
        print("🚀 Ejecutando sistema principal con datos sintéticos...")
        print("💡 Usa 'add SÍMBOLO' para agregar más símbolos sintéticos")
        print("💡 Usa 'status' para ver el estado del sistema")
        print()
        
        # Ejecutar main_synthetic.py (sistema especializado para datos sintéticos)
        result = subprocess.run([sys.executable, "main_synthetic.py"], 
                              capture_output=False, text=True)
        
        if result.returncode == 0:
            print("✅ Sistema ejecutado exitosamente")
        else:
            print("❌ Error ejecutando el sistema")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Restaurar configuración original
        if config_backup is not None:
            try:
                with open("config.ini", 'w') as f:
                    f.write(config_backup)
                print("🔄 Configuración original restaurada")
            except:
                pass
    
    input("\n📱 Presiona Enter para continuar...")

def main():
    """Función principal del menú"""
    
    while True:
        try:
            mostrar_menu()
            opcion = input("🎯 Selecciona una opción (0-17): ").strip()
            
            if opcion == "0":
                print("👋 ¡Hasta luego!")
                break
                
            elif opcion == "1":
                ejecutar_script("simulation/simple_mock_test.py", 
                              "Test básico del mock adapter")
                
            elif opcion == "2":
                ejecutar_script("simulation/test_simulation_interactive.py", 
                              "Demo automatizada del sistema")
                
            elif opcion == "3":
                ejecutar_script("scripts/runners/run_simulation.py", 
                              "Menú interactivo de simulación")
                
            elif opcion == "4":
                ejecutar_script("scripts/tools/download_menu.py", 
                              "Descarga de datos de mercado")
                
            elif opcion == "5":
                ejecutar_script("scripts/tools/data_verification.py", 
                              "Verificación de datos existentes")
                
            elif opcion == "6":
                ejecutar_script("main.py", 
                              "Sistema principal de trading")
                
            elif opcion == "7":
                ejecutar_script("scripts/runners/run_backtest.py", 
                              "Ejecución de backtest")
                
            elif opcion == "8":
                ejecutar_script("scripts/tools/optuna_optimizer.py", 
                              "Optimización de parámetros")
                
            elif opcion == "9":
                mostrar_estructura()
                
            elif opcion == "10":
                mostrar_documentacion()
                
            elif opcion == "11":
                limpiar_temporales()
                
            elif opcion == "12":
                ejecutar_script("tools/extract_full_trading_days.py", 
                              "Generación de datos sintéticos desde DB")
                
            elif opcion == "13":
                ejecutar_sistema_sintetico()
                
            elif opcion == "14":
                ejecutar_script("tools/improved_strategy_backtester.py", 
                              "Backtest mejorado con filtros de calidad")
                
            elif opcion == "15":
                ejecutar_script("tools/fixed_real_strategy_backtester.py", 
                              "Backtest CORREGIDO con estrategias reales")
                
            elif opcion == "16":
                ejecutar_script("tools/strategy_optimizer.py", 
                              "Optimizador de estrategias (real vs simulado)")
                
            elif opcion == "17":
                ejecutar_script("tools/strategy_code_analyzer.py", 
                              "Analizador de código de estrategias")
                
            else:
                print("❌ Opción no válida. Selecciona 0-17.")
                input("\n📱 Presiona Enter para continuar...")
                
        except KeyboardInterrupt:
            print("\n👋 ¡Hasta luego!")
            break
        except EOFError:
            print("\n👋 ¡Hasta luego!")
            break

if __name__ == "__main__":
    main()