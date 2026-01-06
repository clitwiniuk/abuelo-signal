#!/usr/bin/env python3
"""
Data Manager - Coordinador entre backtesting y descargas de Polygon.io
Gestiona la descarga y verificación de datos para backtesting óptimo.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def check_polygon_handler():
    """Verificar si polygon_csv_handler está disponible"""
    try:
        import polygon_csv_handler
        return True
    except ImportError:
        return False

def check_backtest_loader():
    """Verificar si BacktestDataLoader está disponible"""
    try:
        from backtesting.data_loader import BacktestDataLoader
        return True
    except ImportError:
        return False

class DataManager:
    """
    Gestor principal de datos para el sistema de backtesting.
    Coordina descargas de Polygon.io y verificación de datos.
    """
    
    def __init__(self, data_directory: str = "data"):
        self.data_directory = data_directory
        self.polygon_handler = None
        self.backtest_loader = None
        
        # Crear directorio si no existe
        os.makedirs(data_directory, exist_ok=True)
        
        # Inicializar componentes
        self._initialize_components()
    
    def _initialize_components(self):
        """Inicializar polygon handler y backtest loader"""
        # Inicializar Polygon handler
        if check_polygon_handler():
            try:
                from polygon_csv_handler import load_existing_config, setup_polygon_integration
                
                self.polygon_handler = load_existing_config()
                if not self.polygon_handler:
                    print("⚠️  Polygon.io no configurado. Usa opción 1 para configurar.")
                else:
                    print("✅ Polygon.io configurado y listo")
            except Exception as e:
                print(f"❌ Error inicializando Polygon handler: {e}")
        else:
            print("❌ polygon_csv_handler.py no encontrado")
        
        # Inicializar Backtest loader
        if check_backtest_loader():
            try:
                from backtesting.data_loader import BacktestDataLoader
                self.backtest_loader = BacktestDataLoader()
                print("✅ BacktestDataLoader inicializado")
            except Exception as e:
                print(f"❌ Error inicializando BacktestDataLoader: {e}")
        else:
            print("❌ BacktestDataLoader no encontrado")
    
    def show_main_menu(self):
        """Mostrar menú principal"""
        while True:
            print("\n" + "=" * 60)
            print("🎯 DATA MANAGER - Sistema de Gestión de Datos")
            print("=" * 60)
            print("📊 Estado actual:")
            
            # Estado de componentes
            polygon_status = "✅ Configurado" if self.polygon_handler else "❌ No configurado"
            loader_status = "✅ Disponible" if self.backtest_loader else "❌ No disponible"
            
            print(f"   Polygon.io: {polygon_status}")
            print(f"   Data Loader: {loader_status}")
            
            # Estado de datos
            if self.backtest_loader:
                symbols = self.backtest_loader.get_available_symbols(self.data_directory)
                print(f"   Símbolos disponibles: {len(symbols)}")
            else:
                print(f"   Símbolos disponibles: No se puede verificar")
            
            print("\n📋 OPCIONES DISPONIBLES:")
            print("1. 🔧 Configurar Polygon.io")
            print("2. 📥 Descargar datos (recomendado: 1 minuto)")
            print("3. 📊 Verificar datos existentes")
            print("4. 🔄 Convertir timeframes")
            print("5. 🧹 Limpiar y organizar datos")
            print("6. 📈 Preparar para backtesting")
            print("7. ❌ Salir")
            
            choice = input("\n👉 Selecciona opción (1-7): ").strip()
            
            if choice == "1":
                self._setup_polygon()
            elif choice == "2":
                self._download_data_menu()
            elif choice == "3":
                self._verify_data()
            elif choice == "4":
                self._convert_timeframes_menu()
            elif choice == "5":
                self._clean_data()
            elif choice == "6":
                self._prepare_for_backtest()
            elif choice == "7":
                print("👋 ¡Hasta luego!")
                break
            else:
                print("❌ Opción inválida")
    
    def _setup_polygon(self):
        """Configurar Polygon.io"""
        print("\n🔧 CONFIGURACIÓN DE POLYGON.IO")
        print("-" * 40)
        
        if not check_polygon_handler():
            print("❌ polygon_csv_handler.py no encontrado")
            print("   Asegúrate de que el archivo esté en el directorio del proyecto")
            return
        
        try:
            from polygon_csv_handler import setup_polygon_integration
            
            print("🚀 Iniciando configuración de Polygon.io...")
            handler = setup_polygon_integration()
            
            if handler:
                self.polygon_handler = handler
                print("✅ Configuración completada exitosamente")
            else:
                print("❌ Error en la configuración")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _download_data_menu(self):
        """Menú de descarga de datos"""
        print("\n📥 DESCARGA DE DATOS")
        print("-" * 30)
        
        if not self.polygon_handler:
            print("❌ Polygon.io no configurado")
            print("   Usa la opción 1 para configurar primero")
            return
        
        print("📊 RECOMENDACIONES PARA BACKTESTING:")
        print("   • Timeframe: 1 minuto (máxima flexibilidad)")
        print("   • Sesión: Completa (premarket + regular + afterhours)")
        print("   • Período: 60-90 días para estrategias intradiarias")
        print("   • Mínimo requerido: 30 días")
        print("   • Para estrategias Gap & Go: Mínimo 60 días recomendados")
        print()
        
        print("Opciones de descarga:")
        print("1. 📈 Descargar símbolos recomendados (smallcaps)")
        print("2. 📝 Descargar símbolos personalizados")
        print("3. 🔄 Actualizar datos existentes")
        print("4. ⬅️  Volver al menú principal")
        
        choice = input("\n👉 Selecciona opción (1-4): ").strip()
        
        if choice == "1":
            self._download_recommended_symbols()
        elif choice == "2":
            self._download_custom_symbols()
        elif choice == "3":
            self._update_existing_data()
        elif choice == "4":
            return
        else:
            print("❌ Opción inválida")
    
    def _download_recommended_symbols(self):
        """Descargar símbolos recomendados"""
        print("\n📈 DESCARGA DE SÍMBOLOS RECOMENDADOS")
        print("-" * 45)
        
        try:
            # Llamar al menú interactivo de polygon_csv_handler
            print("🚀 Iniciando descargador de Polygon.io...")
            self.polygon_handler.interactive_download_menu()
            
            print("\n✅ Descarga completada")
            print("   Usa la opción 3 para verificar los datos descargados")
            
        except Exception as e:
            print(f"❌ Error durante la descarga: {e}")
    
    def _download_custom_symbols(self):
        """Descargar símbolos personalizados"""
        print("\n📝 DESCARGA PERSONALIZADA")
        print("-" * 30)
        
        # Obtener símbolos del usuario
        symbols_input = input("👉 Ingresa símbolos separados por comas: ").strip()
        if not symbols_input:
            print("❌ No se ingresaron símbolos")
            return
        
        symbols = [s.strip().upper() for s in symbols_input.split(',')]
        
        # Configurar período
        print("\n📅 CONFIGURACIÓN DE PERÍODO")
        print("1. Usar días hacia atrás (predeterminado: 60 días)")
        print("2. Especificar rango de fechas")
        date_choice = input("👉 Seleccione opción (1-2, default=1): ").strip() or "1"
        
        if date_choice == "2":
            # Opción 2: Rango de fechas personalizado
            while True:
                try:
                    default_end = datetime.now().strftime('%Y-%m-%d')
                    default_start = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
                    
                    start_str = input(f"Fecha de inicio (YYYY-MM-DD, default={default_start}): ").strip() or default_start
                    end_str = input(f"Fecha de fin (YYYY-MM-DD, default={default_end}): ").strip() or default_end
                    
                    start_date = datetime.strptime(start_str, '%Y-%m-%d')
                    end_date = datetime.strptime(end_str, '%Y-%m-%d')
                    
                    if start_date >= end_date:
                        print("⚠️  La fecha de inicio debe ser anterior a la fecha de fin")
                        continue
                        
                    days = (end_date - start_date).days
                    break
                    
                except ValueError:
                    print("⚠️  Formato de fecha inválido. Use YYYY-MM-DD")
        else:
            # Opción 1: Días hacia atrás (mínimo 30 días)
            days_input = input("👉 Días hacia atrás (mínimo 30, default 60, max 90): ").strip()
            try:
                days = min(max(int(days_input) if days_input else 60, 30), 90)  # Mínimo 30, máximo 90
            except:
                days = 60  # Valor por defecto si hay error
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        print(f"\n📊 Período seleccionado: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')} ({days} días)")
        if days > 30:
            print("⚠️  Nota: Períodos largos pueden requerir más tiempo de descarga")
        
        # Confirmar timeframe
        print("\n⚠️  IMPORTANTE: Para backtesting óptimo se recomienda 1 minuto")
        timeframe_input = input("👉 Timeframe (1min/5min, default 1min): ").strip()
        timeframe = timeframe_input if timeframe_input in ["1min", "5min"] else "1min"
        
        # Asegurar que end_date sea la fecha actual
        end_date = datetime.now()
        if 'start_date' not in locals():
            start_date = end_date - timedelta(days=days)
        
        # Mostrar resumen antes de confirmar
        print(f"\n📋 Resumen de la descarga:")
        print(f"   • Símbolos: {', '.join(symbols)}")
        print(f"   • Período: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')} ({days} días)")
        print(f"   • Timeframe: {timeframe}")
        
        confirm = input("\n¿Continuar con la descarga? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Descarga cancelada")
            return
        
        print(f"\n📋 Configuración:")
        print(f"   Símbolos: {', '.join(symbols)}")
        print(f"   Período: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
        print(f"   Timeframe: {timeframe}")
        
        confirm = input("\n¿Continuar? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        try:
            # Descargar cada símbolo
            print(f"\n🚀 Descargando {len(symbols)} símbolos...")
            
            for i, symbol in enumerate(symbols, 1):
                print(f"[{i}/{len(symbols)}] Descargando {symbol}...")
                
                # Configurar intervalo para Polygon (1min o 5min)
                interval = "1" if timeframe == "1min" else "5"
                
                df = self.polygon_handler.downloader.get_ticker_data(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    self.data_directory
                )
                
                if not df.empty:
                    print(f"   ✅ {symbol}: {len(df)} registros descargados")
                else:
                    print(f"   ❌ {symbol}: Sin datos")
            
            print("\n✅ Descarga personalizada completada")
            
        except Exception as e:
            print(f"❌ Error durante la descarga: {e}")
    
    def _update_existing_data(self):
        """Actualizar datos existentes"""
        print("\n🔄 ACTUALIZAR DATOS EXISTENTES")
        print("-" * 35)
        
        if not self.backtest_loader:
            print("❌ BacktestDataLoader no disponible")
            return
        
        symbols = self.backtest_loader.get_available_symbols(self.data_directory)
        
        if not symbols:
            print("📁 No hay símbolos existentes para actualizar")
            return
        
        print(f"📊 Símbolos existentes: {len(symbols)}")
        print(f"   {', '.join(symbols[:10])}")
        if len(symbols) > 10:
            print(f"   ... y {len(symbols) - 10} más")
        
        # Configurar período de actualización
        print("\n📅 CONFIGURACIÓN DE PERÍODO")
        print("1. Usar días hacia atrás (predeterminado: 7 días)")
        print("2. Especificar rango de fechas")
        date_choice = input("👉 Seleccione opción (1-2, default=1): ").strip() or "1"
        
        if date_choice == "2":
            # Opción 2: Rango de fechas personalizado
            while True:
                try:
                    default_end = datetime.now().strftime('%Y-%m-%d')
                    default_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    
                    start_str = input(f"Fecha de inicio (YYYY-MM-DD, default={default_start}): ").strip() or default_start
                    end_str = input(f"Fecha de fin (YYYY-MM-DD, default={default_end}): ").strip() or default_end
                    
                    start_date = datetime.strptime(start_str, '%Y-%m-%d')
                    end_date = datetime.strptime(end_str, '%Y-%m-%d')
                    
                    if start_date >= end_date:
                        print("⚠️  La fecha de inicio debe ser anterior a la fecha de fin")
                        continue
                        
                    days = (end_date - start_date).days
                    break
                    
                except ValueError:
                    print("⚠️  Formato de fecha inválido. Use YYYY-MM-DD")
        else:
            # Opción 1: Días hacia atrás (mínimo 30 días)
            days_input = input("👉 Días de datos a descargar (mínimo 30, default 60, max 90): ").strip()
            try:
                days = min(max(int(days_input) if days_input else 60, 30), 90)  # Mínimo 30, máximo 90
            except:
                days = 60  # Valor por defecto si hay error
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        print(f"\n📊 Período seleccionado: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')} ({days} días)")
        if days > 30:
            print("⚠️  Nota: Períodos largos pueden requerir más tiempo de descarga")
        
        print(f"\n📅 Actualizando desde {start_date.strftime('%Y-%m-%d')} hasta hoy")
        
        confirm = input("¿Continuar? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        try:
            successful_updates = 0
            
            for i, symbol in enumerate(symbols, 1):
                print(f"[{i}/{len(symbols)}] Actualizando {symbol}...")
                
                df = self.polygon_handler.downloader.get_ticker_data(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    self.data_directory
                )
                
                if not df.empty:
                    successful_updates += 1
                    print(f"   ✅ {symbol}: {len(df)} nuevos registros")
                else:
                    print(f"   ⚠️  {symbol}: Sin datos nuevos")
            
            print(f"\n✅ Actualización completada: {successful_updates}/{len(symbols)} símbolos")
            
        except Exception as e:
            print(f"❌ Error durante la actualización: {e}")
    
    def _verify_data(self):
        """Verificar datos existentes"""
        print("\n📊 VERIFICACIÓN DE DATOS")
        print("-" * 30)
        
        if not self.backtest_loader:
            print("❌ BacktestDataLoader no disponible")
            return
        
        symbols = self.backtest_loader.get_available_symbols(self.data_directory)
        
        if not symbols:
            print("📁 No hay datos para verificar")
            print("\n🔧 Para obtener datos:")
            print("   1. Usa la opción 2 (Descargar datos)")
            print("   2. O ejecuta: python polygon_csv_handler.py")
            return
        
        print(f"📈 Analizando {len(symbols)} símbolos...")
        
        try:
            # Exportar inventario completo
            inventory_df = self.backtest_loader.export_data_inventory(
                self.data_directory, "data_verification_report.xlsx"
            )
            
            if inventory_df is not None and not inventory_df.empty:
                print("\n📊 RESUMEN DE VERIFICACIÓN:")
                print("-" * 40)
                
                # Análisis por timeframe
                if 'Timeframe' in inventory_df.columns:
                    timeframe_counts = inventory_df['Timeframe'].value_counts()
                    print("📅 Datos por timeframe:")
                    for tf, count in timeframe_counts.items():
                        print(f"   {tf:8}: {count:3} archivos")
                
                # Análisis de sesiones
                if 'Regular Hours' in inventory_df.columns:
                    total_files = len(inventory_df)
                    with_regular = (inventory_df['Regular Hours'].astype(str) != '0').sum()
                    with_premarket = (inventory_df['Premarket'].astype(str) != '0').sum() if 'Premarket' in inventory_df.columns else 0
                    with_afterhours = (inventory_df['Afterhours'].astype(str) != '0').sum() if 'Afterhours' in inventory_df.columns else 0
                    
                    print(f"\n📊 Cobertura de sesiones:")
                    print(f"   Regular hours:  {with_regular:3}/{total_files} archivos ({with_regular/total_files*100:.1f}%)")
                    print(f"   Premarket:      {with_premarket:3}/{total_files} archivos ({with_premarket/total_files*100:.1f}%)")
                    print(f"   After hours:    {with_afterhours:3}/{total_files} archivos ({with_afterhours/total_files*100:.1f}%)")
                
                # Recomendaciones
                print(f"\n💡 RECOMENDACIONES:")
                
                min_data = (inventory_df['Timeframe'] == '1min').sum() if 'Timeframe' in inventory_df.columns else 0
                if min_data > 0:
                    print(f"   ✅ Tienes {min_data} archivos de 1min (óptimo para backtesting)")
                else:
                    print(f"   ⚠️  No hay datos de 1min - considera descargar para mayor flexibilidad")
                
                if total_files >= 10:
                    print(f"   ✅ Suficientes símbolos para backtesting robusto ({total_files})")
                else:
                    print(f"   ⚠️  Pocos símbolos ({total_files}) - considera descargar más")
                
                if with_premarket > total_files * 0.5:
                    print(f"   ✅ Buena cobertura de premarket para estrategias gap")
                else:
                    print(f"   ⚠️  Poca cobertura de premarket - útil para estrategias de gap")
            
            print(f"\n📋 Reporte detallado guardado en: data_verification_report.xlsx")
            
        except Exception as e:
            print(f"❌ Error durante la verificación: {e}")
    
    def _convert_timeframes_menu(self):
        """Menú de conversión de timeframes"""
        print("\n🔄 CONVERSIÓN DE TIMEFRAMES")
        print("-" * 35)
        
        if not self.backtest_loader:
            print("❌ BacktestDataLoader no disponible")
            return
        
        print("📊 Conversiones disponibles:")
        print("   1min -> 5min, 15min, 30min, 1H, 1D")
        print("   5min -> 15min, 30min, 1H, 1D")
        print("   etc...")
        print()
        print("⚠️  NOTA: Solo se puede convertir a timeframes MAYORES")
        print("   (1min -> 5min ✅, pero 5min -> 1min ❌)")
        print()
        
        # Implementar conversión si es necesario
        print("🚧 Función en desarrollo")
        print("   Por ahora, el sistema convierte automáticamente durante el backtesting")
    
    def _clean_data(self):
        """Limpiar y organizar datos"""
        print("\n🧹 LIMPIEZA Y ORGANIZACIÓN DE DATOS")
        print("-" * 40)
        
        if not self.backtest_loader:
            print("❌ BacktestDataLoader no disponible")
            return
        
        symbols = self.backtest_loader.get_available_symbols(self.data_directory)
        
        if not symbols:
            print("📁 No hay datos para limpiar")
            return
        
        print(f"📊 Analizando {len(symbols)} símbolos para limpieza...")
        
        # Implementar limpieza si es necesario
        print("🚧 Función en desarrollo")
        print("   Funcionalidades planeadas:")
        print("   • Eliminar archivos duplicados")
        print("   • Corregir formatos inconsistentes")
        print("   • Optimizar tamaños de archivo")
        print("   • Validar integridad de datos")
    
    def _prepare_for_backtest(self):
        """Preparar datos para backtesting"""
        print("\n📈 PREPARACIÓN PARA BACKTESTING")
        print("-" * 40)
        
        if not self.backtest_loader:
            print("❌ BacktestDataLoader no disponible")
            return
        
        symbols = self.backtest_loader.get_available_symbols(self.data_directory)
        
        print("🔍 VERIFICACIÓN FINAL...")
        
        # Verificaciones básicas
        checks = {
            "symbols_available": len(symbols) >= 5,
            "data_loader_ready": self.backtest_loader is not None,
            "polygon_configured": self.polygon_handler is not None
        }
        
        print(f"\n📋 Estado del sistema:")
        for check, status in checks.items():
            status_icon = "✅" if status else "❌"
            check_name = check.replace("_", " ").title()
            print(f"   {status_icon} {check_name}")
        
        if all(checks.values()):
            print(f"\n🚀 ¡SISTEMA LISTO PARA BACKTESTING!")
            print("=" * 50)
            
            print("📋 Próximos pasos:")
            print("1. Ejecutar: python run_backtest.py")
            print("2. O usar el sistema programáticamente:")
            print()
            print("   from backtesting.data_loader import BacktestDataLoader")
            print("   from backtesting import BacktestEngine, BacktestConfig")
            print("   ")
            print("   loader = BacktestDataLoader()")
            print("   load_data = loader.create_data_loader_function('data', '5min')")
            print("   engine.set_data_loader(load_data)")
            print()
            
            # Información adicional
            if symbols:
                print(f"📊 Datos disponibles:")
                print(f"   • {len(symbols)} símbolos")
                
                # Check for 1min data
                min_symbols = 0
                for symbol in symbols[:5]:  # Check sample
                    info = self.backtest_loader.get_symbol_info(symbol, self.data_directory)
                    if "1min" in info.get('available_timeframes', []):
                        min_symbols += 1
                
                if min_symbols > 0:
                    print(f"   • Datos de 1min disponibles (óptimo)")
                    print(f"   • Conversión automática a cualquier timeframe")
                
        else:
            print(f"\n⚠️  SISTEMA NO COMPLETAMENTE LISTO")
            print("🔧 Pasos pendientes:")
            
            if not checks["polygon_configured"]:
                print("   1. Configurar Polygon.io (opción 1)")
            
            if not checks["symbols_available"]:
                print("   2. Descargar más símbolos (opción 2)")
                print("      Mínimo recomendado: 5-10 símbolos")
            
            if not checks["data_loader_ready"]:
                print("   3. Verificar instalación de BacktestDataLoader")


def main():
    """Función principal"""
    print("🎯 INICIANDO DATA MANAGER")
    print("=" * 30)
    
    # Verificar dependencias
    missing_deps = []
    
    if not check_polygon_handler():
        missing_deps.append("polygon_csv_handler.py")
    
    if not check_backtest_loader():
        missing_deps.append("backtesting/data_loader.py")
    
    if missing_deps:
        print("❌ DEPENDENCIAS FALTANTES:")
        for dep in missing_deps:
            print(f"   • {dep}")
        print("\nAsegúrate de que todos los archivos estén en el proyecto")
        return
    
    # Inicializar y ejecutar
    try:
        manager = DataManager()
        manager.show_main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Interrumpido por el usuario. ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")


if __name__ == "__main__":
    main()