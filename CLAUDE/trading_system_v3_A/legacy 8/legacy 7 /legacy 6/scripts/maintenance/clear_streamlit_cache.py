#!/usr/bin/env python3
"""
Script para limpiar el cache de Streamlit si es necesario
"""

import os
import shutil
import sys
from pathlib import Path

def clear_streamlit_cache():
    """Limpiar todos los caches de Streamlit"""
    
    print("🧹 LIMPIANDO CACHE DE STREAMLIT")
    print("=" * 40)
    
    # Directorios de cache comunes de Streamlit
    cache_dirs = [
        Path.home() / ".streamlit" / "cache",
        Path.cwd() / ".streamlit" / "cache", 
        Path("/tmp/streamlit"),
        Path.cwd() / "__pycache__",
        Path.cwd() / "**/__pycache__"
    ]
    
    cleaned = 0
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                if cache_dir.is_dir():
                    shutil.rmtree(cache_dir)
                    print(f"✅ Eliminado: {cache_dir}")
                    cleaned += 1
            except Exception as e:
                print(f"⚠️ No se pudo eliminar {cache_dir}: {e}")
    
    # Limpiar archivos .pyc recursivamente  
    for pyc_file in Path.cwd().rglob("*.pyc"):
        try:
            pyc_file.unlink()
            cleaned += 1
        except:
            pass
    
    print(f"\n🎯 Cache limpiado: {cleaned} items eliminados")
    print("💡 Ahora ejecuta: streamlit run streamlit_app_v4.py")
    print("✅ El cache estará completamente limpio")

if __name__ == "__main__":
    clear_streamlit_cache()