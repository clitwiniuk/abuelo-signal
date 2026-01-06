#!/usr/bin/env python3
"""
Simple Candlestick Viewer usando mplfinance
==========================================

Visualizador simple y eficiente para velas japonesas usando mplfinance.
Lee archivos CSV de synthetic_data/ y los muestra correctamente.

Ventajas:
- Eje temporal correcto automáticamente
- Velas japonesas perfectas
- Volumen integrado
- Promedio móvil opcional
- Mucho más simple que matplotlib manual
"""

import pandas as pd
import mplfinance as mpf
import os
import sys
from typing import List, Tuple, Optional

def get_csv_files_from_synthetic_data() -> List[Tuple[str, str]]:
    """
    Obtener lista de archivos CSV de synthetic_data/
    
    Returns:
        Lista de tuplas (ruta_completa, nombre_archivo)
    """
    synthetic_data_dir = 'synthetic_data'
    csv_files = []
    
    if os.path.exists(synthetic_data_dir):
        files = [f for f in os.listdir(synthetic_data_dir) if f.endswith('.csv')]
        files.sort()  # Ordenar alfabéticamente: AAAA.csv, AAAB.csv...
        
        for filename in files:
            full_path = os.path.join(synthetic_data_dir, filename)
            csv_files.append((full_path, filename))
    
    return csv_files

def load_csv_for_candlestick(csv_path: str) -> Optional[pd.DataFrame]:
    """
    Cargar CSV y prepararlo para mplfinance
    
    Args:
        csv_path: Ruta al archivo CSV
        
    Returns:
        DataFrame preparado o None si hay error
    """
    try:
        # Cargar CSV
        df = pd.read_csv(csv_path)
        
        # Verificar columnas requeridas
        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
            print(f"❌ Archivo {csv_path} no tiene las columnas requeridas: {required_cols}")
            return None
        
        # Configurar index como Date (requerido por mplfinance)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        
        # Renombrar columnas al formato estándar de mplfinance (minúsculas)
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        # Asegurar tipos numéricos
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Eliminar filas con NaN
        df_clean = df.dropna()
        
        print(f"✅ {os.path.basename(csv_path)}: {len(df_clean)} barras cargadas")
        print(f"   📅 Período: {df_clean.index.min()} a {df_clean.index.max()}")
        print(f"   💰 Precio: ${df_clean['Close'].iloc[0]:.2f} → ${df_clean['Close'].iloc[-1]:.2f}")
        
        return df_clean
        
    except Exception as e:
        print(f"❌ Error cargando {csv_path}: {e}")
        return None

def plot_candlestick_chart(df: pd.DataFrame, title: str = "Velas Japonesas", 
                          show_volume: bool = True):
    """
    Crear gráfico de velas japonesas usando mplfinance
    
    Args:
        df: DataFrame con datos OHLCV
        title: Título del gráfico
        show_volume: Mostrar volumen
    """
    try:
        # Configuración del estilo (sin promedios móviles)
        style_config = {
            'type': 'candle',
            'style': 'binance',  # Estilo moderno
            'title': title,
            'volume': show_volume,
            'show_nontrading': False,  # No mostrar períodos sin trading
            'tight_layout': True
        }
        
        # Crear gráfico
        mpf.plot(df, **style_config)
        
    except Exception as e:
        print(f"❌ Error creando gráfico: {e}")

def main():
    """Interfaz principal"""
    
    print("🕯️ SIMPLE CANDLESTICK VIEWER")
    print("=" * 40)
    print("Visualizador simple usando mplfinance")
    print()
    
    # 1. Buscar archivos CSV
    csv_files = get_csv_files_from_synthetic_data()
    
    if not csv_files:
        print("❌ No se encontraron archivos CSV en synthetic_data/")
        print("💡 Ejecuta primero extract_full_trading_days.py para generar datos")
        return
    
    print(f"📁 ARCHIVOS ENCONTRADOS EN synthetic_data/:")
    print("-" * 50)
    
    for i, (full_path, filename) in enumerate(csv_files, 1):
        file_size = os.path.getsize(full_path) / 1024  # KB
        print(f"   {i:2d}. {filename:<12} ({file_size:5.1f} KB)")
    
    # 2. Selección de archivo
    try:
        choice = input(f"\n🎯 Selecciona archivo (1-{len(csv_files)}) o 'all' para todos: ").strip()
        
        if choice.lower() == 'all':
            # Mostrar todos los archivos (limitado a primeros 5 para no saturar)
            max_files = min(5, len(csv_files))
            print(f"\n📊 Mostrando primeros {max_files} archivos...")
            
            for i in range(max_files):
                full_path, filename = csv_files[i]
                print(f"\n🕯️ Procesando {filename}...")
                
                df = load_csv_for_candlestick(full_path)
                if df is not None:
                    plot_candlestick_chart(df, f"Velas Japonesas - {filename}")
                    input("Presiona Enter para continuar al siguiente archivo...")
        
        else:
            # Mostrar archivo individual
            file_number = int(choice)
            if file_number < 1 or file_number > len(csv_files):
                print(f"❌ Selección inválida. Debe estar entre 1 y {len(csv_files)}")
                return
            
            full_path, filename = csv_files[file_number - 1]
            
            print(f"\n🕯️ Cargando {filename}...")
            
            # 3. Cargar datos
            df = load_csv_for_candlestick(full_path)
            if df is None:
                return
            
            # 4. Opciones de visualización
            print(f"\n⚙️ OPCIONES DE VISUALIZACIÓN:")
            show_volume = input("📊 ¿Mostrar volumen? (y/n, default=y): ").strip().lower()
            show_volume = show_volume != 'n'
            
            # 5. Crear gráfico
            print(f"\n🎨 Generando gráfico de velas japonesas...")
            plot_candlestick_chart(df, f"Velas Japonesas - {filename}", show_volume)
            
    except ValueError:
        print("❌ Entrada inválida. Debe ser un número o 'all'")
    except KeyboardInterrupt:
        print("\n👋 Cancelado por el usuario")
    except Exception as e:
        print(f"❌ Error: {e}")

def quick_view(csv_filename: str):
    """
    Vista rápida de un archivo específico (para uso programático)
    
    Args:
        csv_filename: Nombre del archivo en synthetic_data/
    """
    csv_path = os.path.join('synthetic_data', csv_filename)
    
    if not os.path.exists(csv_path):
        print(f"❌ Archivo no encontrado: {csv_path}")
        return
    
    print(f"🕯️ Vista rápida: {csv_filename}")
    
    df = load_csv_for_candlestick(csv_path)
    if df is not None:
        plot_candlestick_chart(df, f"Vista Rápida - {csv_filename}")

if __name__ == "__main__":
    # Verificar si se especifica un archivo como argumento
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        if not filename.endswith('.csv'):
            filename += '.csv'
        quick_view(filename)
    else:
        main()