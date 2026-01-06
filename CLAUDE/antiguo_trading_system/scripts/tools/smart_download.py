#!/usr/bin/env python3
"""
Descargador inteligente con caché - versión simplificada.
Uso: python smart_download.py [opciones]
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz del proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from adapters.polygon_downloader import (
    download_any_symbols, download_single_symbol, 
    PolygonDownloader
)

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

def get_smallcap_suggestions():
    """Lista de smallcaps sugeridos"""
    return [
        'PLTR', 'BB', 'AMC', 'GME', 'MVIS', 'SNDL', 'SENS', 'BNGO',
        'CLOV', 'WISH', 'SPCE', 'NKLA', 'RIDE', 'WKHS', 'VLDR',
        'LAZR', 'HYLN', 'BLNK', 'CHPT', 'PLUG', 'FCEL', 'BLDP',
        'RIOT', 'MARA', 'CAN', 'EBON', 'SOS', 'XPEV', 'NIO',
        'SOFI', 'HOOD', 'RBLX', 'COIN', 'PATH'
    ]

def get_growth_suggestions():
    """Lista de growth stocks sugeridos"""
    return [
        'NVDA', 'AMD', 'CRM', 'SNOW', 'CRWD', 'ZS', 'DDOG',
        'OKTA', 'NET', 'FSLY', 'TEAM', 'ZM', 'DOCU', 'TWLO',
        'TSLA', 'RIVN', 'LCID', 'NKLA', 'QS', 'CHPT', 'BLNK',
        'MRNA', 'BNTX', 'NVAX', 'VXRT', 'INO', 'OCGN', 'GEVO',
        'SQ', 'PYPL', 'AFRM', 'UPST', 'SOFI', 'COIN', 'HOOD',
        'AI', 'C3AI', 'RBLX', 'U', 'PATH'
    ]

async def check_cache_status(symbols, max_age_days=2):
    """Verifica el estado del caché para una lista de símbolos"""
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

async def smart_download(symbols, days=15, force=False):
    """Descarga inteligente que usa caché"""
    
    print(f"🧠 DESCARGA INTELIGENTE - {len(symbols)} símbolos")
    print("=" * 50)
    
    if not force:
        print("🔍 Verificando caché...")
        cache_status = await check_cache_status(symbols)
        
        # Separar símbolos por acción necesaria
        to_download = []
        to_update = []
        already_current = []
        
        print("\n📊 ESTADO DEL CACHÉ:")
        
        for symbol, status in cache_status.items():
            action = status['action']
            reason = status['reason']
            
            if action == 'skip':
                already_current.append(symbol)
                bars = status.get('bars', 0)
                last_date = status.get('last_date', 'N/A')
                print(f"✅ {symbol}: {reason} - {bars} bars hasta {last_date}")
                
            elif action == 'update':
                to_update.append(symbol)
                bars = status.get('bars', 0)
                last_date = status.get('last_date', 'N/A')
                print(f"🔄 {symbol}: {reason} - {bars} bars hasta {last_date}")
                
            elif action == 'download':
                to_download.append(symbol)
                print(f"📥 {symbol}: {reason}")
        
        # Mostrar resumen
        print(f"\n📋 RESUMEN:")
        print(f"   ✅ Ya actuales: {len(already_current)}")
        print(f"   🔄 Para actualizar: {len(to_update)}")
        print(f"   📥 Para descargar: {len(to_download)}")
        
        if already_current:
            print(f"\n💡 El caché evitó descargar: {', '.join(already_current)}")
        
        # Solo procesar los que necesitan descarga/actualización
        symbols_to_process = to_download + to_update
        
        if not symbols_to_process:
            print("\n🎉 ¡Todos los datos están actuales! No hay nada que descargar.")
            return {}
        
        print(f"\n🚀 Necesario procesar: {len(symbols_to_process)} símbolos")
        symbols = symbols_to_process
        
    else:
        print("🚨 FORZANDO RE-DESCARGA (ignorando caché)")
    
    # Realizar descarga
    print(f"\n📥 Descargando: {', '.join(symbols)}")
    
    results = await download_any_symbols(symbols=symbols, days=days)
    
    # Mostrar resultados
    print(f"\n📊 RESULTADOS:")
    exitosos = sum(results.values())
    print(f"   ✅ Exitosos: {exitosos}/{len(symbols)}")
    
    for ticker, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {ticker}")
    
    return results

def show_help():
    """Muestra ayuda del comando"""
    print("🚀 SMART DOWNLOAD - Descargador con caché inteligente")
    print("=" * 55)
    print("📋 Uso:")
    print("   python smart_download.py [comando] [tickers]")
    print()
    print("🎯 Comandos disponibles:")
    print("   status           - Ver estado de datos existentes")
    print("   single TICKER    - Descargar un ticker específico")
    print("   custom TICK1,TICK2,... - Descargar lista personalizada")
    print("   smallcaps        - Descargar smallcaps sugeridos")
    print("   growth           - Descargar growth stocks")
    print("   update           - Actualizar datos existentes")
    print("   force TICK1,TICK2,... - Forzar re-descarga")
    print()
    print("💡 Ejemplos:")
    print("   python smart_download.py single PLTR")
    print("   python smart_download.py custom PLTR,TSLA,NVDA")
    print("   python smart_download.py smallcaps")
    print("   python smart_download.py update")
    print("   python smart_download.py status")

async def main():
    """Función principal"""
    
    load_env_file()
    
    # Verificar API key
    if not os.getenv('POLYGON_API_KEY'):
        print("❌ ERROR: No encontré POLYGON_API_KEY")
        print("💡 Agrégala al archivo .env: POLYGON_API_KEY=tu_api_key")
        return
    
    # Procesar argumentos
    if len(sys.argv) < 2:
        show_help()
        return
    
    comando = sys.argv[1].lower()
    
    try:
        if comando == "status":
            # Mostrar estado de datos
            print("📂 ESTADO DE DATOS EXISTENTES")
            print("=" * 40)
            
            async with PolygonDownloader.from_env() as downloader:
                existing = downloader.get_available_data()
                
                if existing:
                    print(f"📊 {len(existing)} símbolos disponibles:")
                    for symbol in existing:
                        info = downloader.get_data_info(symbol)
                        if info.get('exists'):
                            bars = info.get('bars_count', 0)
                            end_date = info.get('end_date')
                            if isinstance(end_date, datetime):
                                days_old = (datetime.now() - end_date.replace(tzinfo=None)).days
                                status = "🟢" if days_old <= 2 else "🟡" if days_old <= 7 else "🔴"
                                date_str = end_date.date()
                            else:
                                status = "❓"
                                date_str = "N/A"
                            
                            print(f"   {status} {symbol}: {bars} bars hasta {date_str}")
                else:
                    print("📂 No hay datos descargados")
        
        elif comando == "single":
            # Descargar ticker específico
            if len(sys.argv) < 3:
                print("❌ Falta especificar el ticker")
                print("💡 Uso: python smart_download.py single PLTR")
                return
            
            ticker = sys.argv[2].upper()
            await smart_download([ticker])
        
        elif comando == "custom":
            # Lista personalizada
            if len(sys.argv) < 3:
                print("❌ Falta especificar los tickers")
                print("💡 Uso: python smart_download.py custom PLTR,TSLA,NVDA")
                return
            
            tickers_str = sys.argv[2].upper()
            tickers = [t.strip() for t in tickers_str.split(',') if t.strip()]
            await smart_download(tickers)
        
        elif comando == "smallcaps":
            # Smallcaps sugeridos
            smallcaps = get_smallcap_suggestions()
            print(f"🔥 SMALLCAPS SUGERIDOS ({len(smallcaps)} símbolos)")
            await smart_download(smallcaps)
        
        elif comando == "growth":
            # Growth stocks
            growth = get_growth_suggestions()
            print(f"📈 GROWTH STOCKS ({len(growth)} símbolos)")
            await smart_download(growth)
        
        elif comando == "update":
            # Actualizar existentes
            async with PolygonDownloader.from_env() as downloader:
                existing = downloader.get_available_data()
            
            if existing:
                print(f"🔄 ACTUALIZANDO {len(existing)} SÍMBOLOS EXISTENTES")
                await smart_download(existing)
            else:
                print("📂 No hay datos existentes para actualizar")
        
        elif comando == "force":
            # Forzar re-descarga
            if len(sys.argv) < 3:
                print("❌ Falta especificar los tickers")
                print("💡 Uso: python smart_download.py force PLTR,TSLA")
                return
            
            tickers_str = sys.argv[2].upper()
            tickers = [t.strip() for t in tickers_str.split(',') if t.strip()]
            print(f"🚨 FORZANDO RE-DESCARGA DE {len(tickers)} SÍMBOLOS")
            await smart_download(tickers, force=True)
        
        else:
            print(f"❌ Comando desconocido: {comando}")
            show_help()
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())