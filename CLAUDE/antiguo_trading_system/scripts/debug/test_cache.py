#!/usr/bin/env python3
"""
Test del sistema de caché para verificar que funciona correctamente.
"""

import asyncio
import os
from pathlib import Path
from datetime import datetime
from adapters.polygon_downloader import PolygonDownloader

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

async def test_cache_system():
    """Test del sistema de caché"""
    
    load_env_file()
    
    print("🧪 TESTING SISTEMA DE CACHÉ")
    print("=" * 50)
    
    async with PolygonDownloader.from_env() as downloader:
        existing = downloader.get_available_data()
        
        if existing:
            print(f"📊 Datos existentes ({len(existing)} símbolos):")
            print("-" * 50)
            
            for symbol in existing:
                info = downloader.get_data_info(symbol)
                if info.get('exists'):
                    bars_count = info.get('bars_count', 'N/A')
                    end_date = info.get('end_date', 'N/A')
                    size_mb = info.get('file_size_mb', 0)
                    
                    # Calcular antigüedad
                    if isinstance(info.get('end_date'), datetime):
                        days_old = (datetime.now() - info['end_date'].replace(tzinfo=None)).days
                        age_status = "🟢 ACTUAL" if days_old <= 2 else "🟡 1 SEMANA" if days_old <= 7 else "🔴 ANTIGUO"
                    else:
                        age_status = "❓ DESCONOCIDO"
                        days_old = "N/A"
                    
                    if hasattr(end_date, 'date'):
                        end_date_str = end_date.date()
                    else:
                        end_date_str = end_date
                    
                    print(f"📈 {symbol}:")
                    print(f"   📊 Barras: {bars_count}")
                    print(f"   📅 Hasta: {end_date_str}")
                    print(f"   💾 Tamaño: {size_mb:.1f} MB")
                    print(f"   ⏰ Estado: {age_status} ({days_old} días)")
                    print()
            
            print("🧠 ANÁLISIS DE CACHÉ:")
            print("-" * 30)
            
            # Analizar qué necesita actualización
            current_symbols = []
            outdated_symbols = []
            
            for symbol in existing[:5]:  # Solo los primeros 5 para el test
                info = downloader.get_data_info(symbol)
                if info.get('exists'):
                    end_date = info.get('end_date')
                    if isinstance(end_date, datetime):
                        days_old = (datetime.now() - end_date.replace(tzinfo=None)).days
                        if days_old <= 2:
                            current_symbols.append(symbol)
                        else:
                            outdated_symbols.append(symbol)
            
            print(f"✅ Símbolos actuales (≤2 días): {current_symbols}")
            print(f"🔄 Símbolos para actualizar (>2 días): {outdated_symbols}")
            
            if current_symbols:
                print(f"\n💡 El caché evitaría descargar: {len(current_symbols)} símbolos")
            if outdated_symbols:
                print(f"🔄 Solo necesita actualizar: {len(outdated_symbols)} símbolos")
                
        else:
            print("📂 No hay datos descargados aún")
            print("💡 El caché detectaría que necesitas descargar todo")

if __name__ == "__main__":
    asyncio.run(test_cache_system())