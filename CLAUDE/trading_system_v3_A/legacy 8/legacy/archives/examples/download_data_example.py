# examples/download_data_example.py
"""
Ejemplo de cómo usar el Polygon Downloader para descargar cualquier ticker.
"""

import asyncio
import os
from adapters.polygon_downloader import (
    download_single_symbol, 
    download_any_symbols,
    download_smallcap_suggestions,
    download_growth_suggestions,
    PolygonDownloader
)

async def main():
    """Ejemplos de uso del Polygon Downloader"""
    
    # Configura tu API key (puedes ponerla en .env también)
    # os.environ['POLYGON_API_KEY'] = 'tu_api_key_aqui'
    
    print("🚀 Ejemplos de Polygon Downloader")
    print("=" * 50)
    
    # Ejemplo 1: Descargar un ticker específico que te interese
    print("\n📥 Ejemplo 1: Descarga un ticker específico")
    success = await download_single_symbol('PLTR', days=10)
    print(f"✅ PLTR descargado: {success}")
    
    # Ejemplo 2: Descargar tu lista personalizada de tickers
    print("\n📥 Ejemplo 2: Tu lista personalizada de tickers")
    my_favorite_tickers = [
        'NVDA',    # GPU/AI leader
        'TSLA',    # EV leader
        'PLTR',    # Data analytics
        'AMD',     # Semiconductors
        'MVIS',    # Smallcap tech
        'BB',      # Cybersecurity
        'SOFI',    # Fintech
        'COIN'     # Crypto
    ]
    
    results = await download_any_symbols(my_favorite_tickers, days=10)
    print("Resultados de descarga:")
    for symbol, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {symbol}")
    
    # Ejemplo 3: Usar las sugerencias predefinidas
    print("\n📥 Ejemplo 3: Sugerencias de smallcaps")
    smallcap_results = await download_smallcap_suggestions(days=10)
    successful = sum(smallcap_results.values())
    print(f"✅ Smallcaps descargados: {successful}/{len(smallcap_results)}")
    
    # Ejemplo 4: Información detallada de un ticker
    print("\n📊 Ejemplo 4: Información de data descargada")
    async with PolygonDownloader.from_env() as downloader:
        info = downloader.get_data_info('PLTR')
        if info['exists']:
            print(f"PLTR data info:")
            print(f"  📊 Bars: {info['bars_count']}")
            print(f"  📅 Desde: {info['start_date']}")
            print(f"  📅 Hasta: {info['end_date']}")
            print(f"  💾 Tamaño: {info['file_size_mb']:.2f} MB")
        
        # Ver todos los símbolos disponibles
        available = downloader.get_available_data()
        print(f"\n📂 Símbolos disponibles: {len(available)}")
        print(f"Primeros 10: {available[:10]}")

if __name__ == "__main__":
    # Asegúrate de tener tu API key configurada
    if not os.getenv('POLYGON_API_KEY'):
        print("⚠️ Configura tu POLYGON_API_KEY en variables de entorno")
        print("   export POLYGON_API_KEY='tu_api_key'")
    else:
        asyncio.run(main())