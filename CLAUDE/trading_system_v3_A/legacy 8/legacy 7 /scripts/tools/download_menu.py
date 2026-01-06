#!/usr/bin/env python3
"""
Menú interactivo para descargar datos usando la lógica simple del script original.
Descarga datos completos sin filtrado excesivo.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
import pandas as pd
import time
from pathlib import Path

# Import the working simple downloader
sys.path.insert(0, str(Path(__file__).parent))
from simple_polygon_downloader import SimplePolygonDownloader

def simple_download_symbol(symbol: str, api_key: str, start_date_str: str = None, end_date_str: str = None, days: int = 10) -> bool:
    """Use the working simple downloader"""
    try:
        downloader = SimplePolygonDownloader(api_key)
        if start_date_str and end_date_str:
            return downloader.download_symbol(symbol, start_date_str, end_date_str)
        else:
            return downloader.download_symbol(symbol, days=days)
    except Exception as e:
        print(f"❌ {symbol}: Error - {str(e)}")
        return False

def simple_download_multiple(symbols: list, api_key: str, days: int = 10) -> dict:
    """Download multiple symbols using simple logic"""
    results = {}
    
    print(f"🚀 Downloading {len(symbols)} symbols...")
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] ", end="")
        results[symbol] = simple_download_symbol(symbol, api_key, days=days)
        
        # Small delay between requests (main rate limiting handled by SimplePolygonDownloader)
        if i < len(symbols):
            time.sleep(0.5)  # Small delay
    
    return results

def load_env_file():
    """Carga el archivo .env si existe"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip('"').strip("'")
                    os.environ[key.strip()] = value
        print("✅ Archivo .env cargado")
    else:
        print("⚠️ No se encontró archivo .env")

def mostrar_menu():
    """Muestra el menú de opciones"""
    print("🚀 POLYGON DATA DOWNLOADER - LÓGICA ORIGINAL")
    print("=" * 60)
    print("📋 Opciones disponibles:")
    print("   1. Descargar ticker específico")
    print("   2. Descargar lista personalizada") 
    print("   3. Descargar smallcaps sugeridos")
    print("   4. Descargar growth stocks sugeridos")
    print("   5. Actualizar datos existentes")
    print("   6. Ver datos disponibles")
    print("   7. Forzar re-descarga (ignorar caché)")
    print("   0. Salir")
    print("=" * 60)

def get_smallcap_suggestions():
    """Lista de smallcaps sugeridos"""
    return [
        'PLTR', 'BB', 'GME', 'MVIS', 'SNDL',
        'CLOV', 'SPCE', 'WKHS',
        'LAZR', 'BLNK', 'PLUG', 'FCEL',
        'RIOT', 'MARA', 'CAN', 'SOS', 'XPEV', 'NIO',
        'SOFI', 'HOOD', 'RBLX', 'COIN', 'PATH'
    ]

def get_growth_suggestions():
    """Lista de growth stocks sugeridos"""
    return [
        'NVDA', 'AMD', 'CRM', 'SNOW', 'CRWD', 'ZS', 'DDOG',
        'OKTA', 'NET', 'FSLY', 'TEAM', 'ZM', 'DOCU', 'TWLO',
        'TSLA', 'RIVN', 'LCID', 'QS', 'CHPT', 'BLNK',
        'MRNA', 'BNTX', 'NVAX', 'VXRT', 'INO', 'OCGN', 'GEVO',
        'SQ', 'PYPL', 'AFRM', 'UPST', 'SOFI', 'COIN', 'HOOD',
        'AI', 'C3AI', 'RBLX', 'U', 'PATH'
    ]

def get_user_input(prompt):
    """Get user input with error handling"""
    try:
        return input(prompt).strip()
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")
        exit(0)

async def check_cache_status(symbols, max_age_days=2):
    """
    Verifica el estado del caché para una lista de símbolos.
    Retorna diccionario con estado de cada símbolo.
    """
    async with PolygonDownloader.from_env() as downloader:
        cache_status = {}
        
        for symbol in symbols:
            info = downloader.get_data_info(symbol)
            
            if not info.get('exists'):
                cache_status[symbol] = {
                    'status': 'missing',
                    'action': 'download',
                    'reason': 'No existe'
                }
            else:
                # Verificar antigüedad de los datos
                end_date = info.get('end_date')
                if end_date:
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    
                    days_old = (datetime.now() - end_date.replace(tzinfo=None)).days
                    
                    if days_old <= max_age_days:
                        cache_status[symbol] = {
                            'status': 'current',
                            'action': 'skip',
                            'reason': f'Actual ({days_old} días)',
                            'bars': info.get('bars_count', 0),
                            'last_date': end_date.date()
                        }
                    else:
                        cache_status[symbol] = {
                            'status': 'outdated',
                            'action': 'update',
                            'reason': f'Desactualizado ({days_old} días)',
                            'bars': info.get('bars_count', 0),
                            'last_date': end_date.date()
                        }
                else:
                    cache_status[symbol] = {
                        'status': 'invalid',
                        'action': 'download',
                        'reason': 'Datos inválidos'
                    }
        
        return cache_status

def smart_download(symbols, days=15, force=False):
    """
    Descarga usando la lógica simple del script original.
    """
    print(f"\n🚀 DESCARGA CON LÓGICA ORIGINAL")
    
    # Get API key
    api_key = os.getenv('POLYGON_API_KEY')
    if not api_key:
        print("❌ No se encontró POLYGON_API_KEY")
        return {}
    
    if not force:
        # Simple cache check - just check if files exist
        existing_files = []
        missing_files = []
        
        data_path = Path("data/csv")
        
        for symbol in symbols:
            filepath = data_path / f"{symbol}_1_min.csv"
            if filepath.exists():
                existing_files.append(symbol)
                print(f"✅ {symbol}: Archivo existe")
            else:
                missing_files.append(symbol)
                print(f"📥 {symbol}: Falta archivo")
        
        if missing_files:
            print(f"\n🚀 Descargando {len(missing_files)} símbolos faltantes...")
            symbols = missing_files
        else:
            print("\n🎉 ¡Todos los archivos existen!")
            return {symbol: True for symbol in existing_files}
    else:
        print("\n🚨 FORZANDO RE-DESCARGA")
    
    # Realizar descarga con lógica simple
    print(f"\n📥 Descargando {len(symbols)} símbolos...")
    print(f"📋 Lista: {', '.join(symbols)}")
    
    results = simple_download_multiple(symbols, api_key, days=days)
    
    # Mostrar resultados
    print("\n" + "=" * 50)
    print("📊 RESULTADOS DE DESCARGA")
    print("=" * 50)
    
    exitosos = []
    fallidos = []
    
    for ticker, success in results.items():
        if success:
            print(f"✅ {ticker} - Descargado correctamente")
            exitosos.append(ticker)
        else:
            print(f"❌ {ticker} - Error en descarga")
            fallidos.append(ticker)
    
    print(f"\n📈 RESUMEN FINAL:")
    print(f"   ✅ Exitosos: {len(exitosos)}/{len(symbols)}")
    print(f"   ❌ Fallidos: {len(fallidos)}")
    
    if exitosos:
        print(f"\n🎯 Nuevos datos disponibles: {', '.join(exitosos)}")
        print(f"📂 Ubicación: data/csv/")
    
    if fallidos:
        print(f"\n⚠️ Símbolos con problemas: {', '.join(fallidos)}")
    
    return results

def main():
    """Menú principal con lógica simple del script original"""
    
    # Cargar .env file
    load_env_file()
    
    # Verificar API key
    if not os.getenv('POLYGON_API_KEY'):
        print("❌ ERROR: No encontré POLYGON_API_KEY")
        print("📋 Opciones:")
        print("   1. export POLYGON_API_KEY='tu_api_key'")
        print("   2. Agrégala al archivo .env: POLYGON_API_KEY=tu_api_key")
        return
    
    while True:
        try:
            mostrar_menu()
            opcion = get_user_input("🎯 Elige una opción (0-7): ")
            
            if opcion == "0":
                print("👋 ¡Hasta luego!")
                break
                
            elif opcion == "1":
                # Ticker específico
                print("\n📊 DESCARGAR TICKER ESPECÍFICO")
                ticker = get_user_input("📝 Ingresa el ticker (ej: AAPL): ").upper()
                if ticker:
                    smart_download([ticker])
                
            elif opcion == "2":
                # Lista personalizada
                print("\n📋 LISTA PERSONALIZADA")
                print("💡 Ingresa tickers separados por comas (ej: PLTR,TSLA,NVDA)")
                tickers_input = get_user_input("📝 Tickers: ").upper()
                if tickers_input:
                    tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]
                    if tickers:
                        smart_download(tickers)
                
            elif opcion == "3":
                # Smallcaps sugeridos
                print("\n🔥 SMALLCAPS SUGERIDOS")
                smallcaps = get_smallcap_suggestions()
                print(f"📋 {len(smallcaps)} smallcaps disponibles:")
                # Mostrar en grupos de 8
                for i in range(0, len(smallcaps), 8):
                    group = smallcaps[i:i+8]
                    print(f"   {', '.join(group)}")
                
                confirmar = get_user_input("\n❓ ¿Procesar lista completa? (s/N): ").lower()
                if confirmar in ['s', 'si', 'yes', 'y']:
                    smart_download(smallcaps)
                
            elif opcion == "4":
                # Growth stocks sugeridos
                print("\n📈 GROWTH STOCKS SUGERIDOS")
                growth_stocks = get_growth_suggestions()
                print(f"📋 {len(growth_stocks)} growth stocks disponibles:")
                # Mostrar en grupos de 8
                for i in range(0, len(growth_stocks), 8):
                    group = growth_stocks[i:i+8]
                    print(f"   {', '.join(group)}")
                
                confirmar = get_user_input("\n❓ ¿Procesar lista completa? (s/N): ").lower()
                if confirmar in ['s', 'si', 'yes', 'y']:
                    smart_download(growth_stocks)
                
            elif opcion == "5":
                # Actualizar datos existentes
                print("\n🔄 ACTUALIZAR DATOS EXISTENTES")
                data_path = Path("data/csv")
                if data_path.exists():
                    existing = [f.stem.replace('_1_min', '') for f in data_path.glob("*_1_min.csv")]
                    
                    if existing:
                        print(f"📂 Datos existentes ({len(existing)} símbolos):")
                        print(f"   {', '.join(existing)}")
                        confirmar = get_user_input("\n❓ ¿Re-descargar todos? (s/N): ").lower()
                        if confirmar in ['s', 'si', 'yes', 'y']:
                            smart_download(existing, force=True)
                    else:
                        print("📂 No hay datos existentes para actualizar")
                else:
                    print("📂 No hay directorio de datos")
                
            elif opcion == "6":
                # Ver datos disponibles
                print("\n📂 DATOS DISPONIBLES")
                data_path = Path("data/csv")
                if data_path.exists():
                    csv_files = list(data_path.glob("*_1_min.csv"))
                    
                    if csv_files:
                        print(f"📊 Archivos disponibles ({len(csv_files)}):")
                        for csv_file in csv_files:
                            try:
                                symbol = csv_file.stem.replace('_1_min', '')
                                df = pd.read_csv(csv_file)
                                bars_count = len(df)
                                size_mb = csv_file.stat().st_size / (1024 * 1024)
                                
                                # Get first and last timestamp
                                first_time = df.iloc[0]['timestamp'] if len(df) > 0 else "N/A"
                                last_time = df.iloc[-1]['timestamp'] if len(df) > 0 else "N/A"
                                
                                print(f"   ✅ {symbol}: {bars_count} bars | {size_mb:.1f}MB")
                                print(f"      📅 {first_time} -> {last_time}")
                            except Exception as e:
                                print(f"   ❌ {csv_file.name}: Error leyendo archivo")
                    else:
                        print("📂 No hay archivos CSV")
                else:
                    print("📂 No existe directorio data/csv/")
                    
            elif opcion == "7":
                # Forzar re-descarga
                print("\n🚨 FORZAR RE-DESCARGA")
                print("⚠️ Esto ignorará el caché y descargará todo de nuevo")
                tickers_input = get_user_input("📝 Tickers a re-descargar (separados por comas): ").upper()
                if tickers_input:
                    tickers = [t.strip() for t in tickers_input.split(',') if t.strip()]
                    if tickers:
                        confirmar = get_user_input(f"\n❓ ¿Forzar descarga de {len(tickers)} símbolos? (s/N): ").lower()
                        if confirmar in ['s', 'si', 'yes', 'y']:
                            smart_download(tickers, force=True)
                    
            else:
                print("❌ Opción no válida. Elige 0-7.")
            
            if opcion != "0":
                input("\n📱 Presiona Enter para continuar...")
                print("\n" * 2)  # Espacio para claridad
                
        except Exception as e:
            print(f"❌ Error: {e}")
            input("\n📱 Presiona Enter para continuar...")

if __name__ == "__main__":
    main()