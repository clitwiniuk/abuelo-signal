#!/usr/bin/env python3
"""
USO DEL SISTEMA EXPANDIDO - Versión Simple
Para descargas diarias sin problemas de rate limits
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar path
sys.path.append('backtesting_system/data')

from simple_expanded_test import SimpleExpandedDownloader

def download_expanded_daily(symbol: str, date_str: str = None):
    """
    Descargar datos expandidos para un símbolo y fecha
    
    Args:
        symbol: Símbolo a descargar (ej: 'AAPL', 'TSLA')
        date_str: Fecha en formato YYYY-MM-DD (por defecto hoy-1)
    """
    if not date_str:
        # Usar fecha de ayer (que siempre tiene datos)
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    print(f"📈 Descargando datos expandidos para {symbol} el {date_str}")
    
    API_KEY = os.environ.get('POLYGON_API_KEY')
    if not API_KEY:
        print("❌ API key no encontrada")
        return False
    
    downloader = SimpleExpandedDownloader(API_KEY)
    
    # Configurar BBDD expandida
    downloader.setup_expanded_db()
    
    # Crear event_id
    import hashlib
    event_key = f"{symbol}_{date_str}"
    event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
    
    print(f"🎯 Event ID: {event_id}")
    
    # Descargar datos
    try:
        aggs = list(downloader.client.list_aggs(
            ticker=symbol,
            multiplier=1,
            timespan='day',
            from_=date_str,
            to=date_str,
            limit=1
        ))
        
        if aggs:
            agg = aggs[0]
            print(f"✅ Datos obtenidos: O=${agg.open}, H=${agg.high}, L=${agg.low}, C=${agg.close}")
            
            # Insertar con event_id
            success = downloader._insert_simple_data(symbol, event_id, date_str, agg)
            if success:
                print(f"✅ ¡Descarga expandida completada!")
                print(f"   📊 Datos guardados con event_id {event_id}")
                return True
            else:
                print(f"❌ Error insertando datos")
                return False
        else:
            print(f"⚠️ No se encontraron datos para {symbol} en {date_str}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def download_multiple_symbols_expanded(symbols: list, date_str: str = None):
    """
    Descargar múltiples símbolos expandidos
    """
    if not date_str:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")
    
    print(f"📈 Descargando datos expandidos para {len(symbols)} símbolos el {date_str}")
    print("=" * 60)
    
    success_count = 0
    for symbol in symbols:
        print(f"\n🔄 Procesando {symbol}...")
        if download_expanded_daily(symbol, date_str):
            success_count += 1
    
    print(f"\n🎯 Resumen:")
    print(f"   📊 Símbolos procesados: {len(symbols)}")
    print(f"   ✅ Descargas exitosas: {success_count}")
    print(f"   ❌ Fallos: {len(symbols) - success_count}")
    
    return success_count > 0

# Ejemplos de uso
if __name__ == "__main__":
    print("🚀 SISTEMA EXPANDIDO - CASOS DE USO")
    print("=" * 50)
    
    # Ejemplo 1: Un solo símbolo
    print("\n📊 Ejemplo 1: Un solo símbolo")
    download_expanded_daily("AAPL")
    
    # Ejemplo 2: Múltiples símbolos
    print("\n📊 Ejemplo 2: Múltiples símbolos")
    symbols = ["TSLA", "GOOGL", "MSFT"]
    download_multiple_symbols_expanded(symbols)
    
    print(f"\n🎉 ¡Sistema expandido listo para uso!")