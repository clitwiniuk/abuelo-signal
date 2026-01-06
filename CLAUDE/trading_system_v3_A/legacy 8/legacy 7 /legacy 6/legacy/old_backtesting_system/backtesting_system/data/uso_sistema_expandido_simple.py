#!/usr/bin/env python3
"""
Script de uso del sistema expandido
Para descargar datos con event_id y contexto histórico
"""

# Import simple direct
import os
import sys
from datetime import datetime, timedelta

# Configurar path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importar clase
from simple_expanded_test import SimpleExpandedDownloader

def descargar_simbolo_expandido(simbolo, fecha_str=None):
    """Descargar datos expandidos para un símbolo"""
    if not fecha_str:
        # Usar ayer
        ayer = datetime.now() - timedelta(days=1)
        fecha_str = ayer.strftime("%Y-%m-%d")
    
    print(f"\n📊 DESCARGANDO: {simbolo} para {fecha_str}")
    
    # API Key
    api_key = os.environ.get('POLYGON_API_KEY')
    if not api_key:
        print("❌ API key no encontrada en .env.local")
        return False
    
    # Crear downloader
    downloader = SimpleExpandedDownloader(api_key)
    
    # Configurar BBDD
    downloader.setup_expanded_db()
    
    # Event ID
    import hashlib
    event_key = f"{simbolo}_{fecha_str}"
    event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
    print(f"🎯 Event ID: {event_id}")
    
    # Descargar
    try:
        aggs = list(downloader.client.list_aggs(
            ticker=simbolo,
            multiplier=1,
            timespan='day',
            from_=fecha_str,
            to=fecha_str,
            limit=1
        ))
        
        if aggs:
            agg = aggs[0]
            print(f"✅ Datos: O=${agg.open:.2f}, H=${agg.high:.2f}, L=${agg.low:.2f}, C=${agg.close:.2f}")
            
            # Insertar
            success = downloader._insert_simple_data(simbolo, event_id, fecha_str, agg)
            if success:
                print(f"✅ ¡Completado con event_id {event_id}!")
                return True
            else:
                print("❌ Error insertando")
                return False
        else:
            print("⚠️ No hay datos")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def descargar_multiples_simbolos(simbolos):
    """Descargar múltiples símbolos"""
    print(f"\n🚀 DESCARGANDO {len(simbolos)} SÍMBOLOS")
    print("=" * 50)
    
    exitosos = 0
    for simbolo in simbolos:
        if descargar_simbolo_expandido(simbolo):
            exitosos += 1
    
    print(f"\n📊 RESUMEN:")
    print(f"   - Procesados: {len(simbolos)}")
    print(f"   - Exitosos: {exitosos}")
    print(f"   - Fallos: {len(simbolos) - exitosos}")
    
    return exitosos > 0

# Ejemplos de uso
if __name__ == "__main__":
    print("🎯 SISTEMA EXPANDIDO - EJEMPLOS DE USO")
    print("=" * 50)
    
    # Un símbolo
    print("\n📈 Ejemplo 1: Un símbolo")
    descargar_simbolo_expandido("TSLA")
    
    # Múltiples símbolos
    print("\n📈 Ejemplo 2: Múltiples símbolos")  
    simbolos = ["GOOGL", "MSFT", "AMZN"]
    descargar_multiples_simbolos(simbolos)
    
    print("\n🎉 ¡Listo para uso!")