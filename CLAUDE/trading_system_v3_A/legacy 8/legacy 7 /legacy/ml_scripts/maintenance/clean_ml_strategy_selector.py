#!/usr/bin/env python3
"""
Limpiar modelos ML Strategy Selector anteriores y hacer backup antes de optimización
Siguiente paso en la optimización completa del sistema ML
"""

import os
import shutil
import glob
from datetime import datetime

def clean_ml_strategy_selector():
    """
    Limpia modelos ML Strategy Selector anteriores con backup de seguridad
    """
    print("🗑️  LIMPIEZA DE MODELOS ML STRATEGY SELECTOR")
    print("=" * 55)
    
    # Crear directorio de backup
    backup_dir = f"backup_strategy_selector_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"📦 Creando backup en: {backup_dir}")
    
    # 1. Backup y limpiar archivos JSON de strategy selector
    strategy_selector_files = [
        "data/ml_models/strategy_selector.json",
        "data/ml_models/hybrid_strategy_selector.json", 
        "data/ml_models/test_trader_strategy_selector.json",
        "data/ml_models/trader_strategy_selector.json"
    ]
    
    print(f"\n🔍 Procesando archivos de ML Strategy Selector...")
    
    for file_path in strategy_selector_files:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            backup_path = os.path.join(backup_dir, filename)
            
            # Obtener tamaño del archivo
            size = os.path.getsize(file_path) / 1024  # KB
            
            print(f"   📦 Backup: {filename} ({size:.1f} KB)")
            shutil.copy2(file_path, backup_path)
            
            print(f"   🗑️  Remove: {filename}")
            os.remove(file_path)
    
    # 2. Buscar archivos residuales relacionados con Strategy Selector
    print(f"\n🔍 Buscando archivos residuales de ML Strategy Selector...")
    
    # Patrones de archivos relacionados
    patterns = [
        "**/*strategy*selector*.pkl",
        "**/*strategy*selector*.joblib", 
        "**/*strategy*selector*.model",
        "**/*thompson*sampling*.json",
        "**/*bandit*.json"
    ]
    
    residual_files = []
    for pattern in patterns:
        files = glob.glob(pattern, recursive=True)
        for file in files:
            # Skip si es backup, test o cache
            if ("backup_" in file or 
                "test_" in file or 
                ".git" in file or
                "__pycache__" in file):
                continue
            
            if os.path.exists(file):
                residual_files.append(file)
    
    # Eliminar duplicados
    residual_files = list(set(residual_files))
    
    if residual_files:
        for file_path in residual_files:
            filename = os.path.basename(file_path)
            backup_path = os.path.join(backup_dir, f"residual_{filename}")
            
            print(f"   📦 Backup residual: {filename}")
            shutil.copy2(file_path, backup_path)
            
            print(f"   🗑️  Remove residual: {filename}")
            os.remove(file_path)
    else:
        print("   ✅ No se encontraron archivos residuales")
    
    # 3. Limpiar cache relacionado
    print(f"\n🔍 Limpiando cache de ML Strategy Selector...")
    
    cache_patterns = [
        "strategies/__pycache__/*strategy*selector*",
        "**/*strategy*selector*.pyc"
    ]
    
    cache_cleaned = 0
    for pattern in cache_patterns:
        files = glob.glob(pattern, recursive=True)
        for file in files:
            if os.path.exists(file) and "backup_" not in file:
                print(f"   🗑️  Cache: {os.path.basename(file)}")
                os.remove(file)
                cache_cleaned += 1
    
    if cache_cleaned == 0:
        print("   ✅ No se encontraron archivos de cache")
    
    # 4. Resumen
    backup_files = []
    for root, dirs, files in os.walk(backup_dir):
        for file in files:
            backup_files.append(os.path.join(root, file))
    
    print(f"\n✅ LIMPIEZA ML STRATEGY SELECTOR COMPLETADA")
    print(f"📦 {len(backup_files)} archivos respaldados en {backup_dir}")
    print(f"🗑️  Modelos anteriores eliminados")
    print(f"🚀 Listo para reentrenar con database_quality.db y 7 estrategias")
    
    return backup_dir

def verify_strategy_selector_cleanup():
    """
    Verifica que la limpieza del ML Strategy Selector fue exitosa
    """
    print(f"\n🔍 VERIFICANDO LIMPIEZA ML STRATEGY SELECTOR...")
    
    # Verificar que no quedan modelos de strategy selector
    selector_files = []
    
    # Archivos principales
    main_files = [
        "data/ml_models/strategy_selector.json",
        "data/ml_models/hybrid_strategy_selector.json",
        "data/ml_models/test_trader_strategy_selector.json", 
        "data/ml_models/trader_strategy_selector.json"
    ]
    
    for file in main_files:
        if os.path.exists(file):
            selector_files.append(file)
    
    # Buscar archivos residuales
    patterns_to_check = [
        "**/*strategy*selector*.pkl",
        "**/*strategy*selector*.json",
        "**/*thompson*sampling*"
    ]
    
    for pattern in patterns_to_check:
        files = glob.glob(pattern, recursive=True)
        for file in files:
            if ("backup_" not in file and 
                "test_" not in file and
                ".git" not in file and
                os.path.exists(file)):
                selector_files.append(file)
    
    if selector_files:
        print(f"⚠️  Archivos residuales encontrados:")
        for file in selector_files:
            print(f"   - {file}")
        return False
    else:
        print(f"✅ Limpieza verificada - No quedan modelos ML Strategy Selector antiguos")
        return True

if __name__ == "__main__":
    print("🚀 LIMPIADOR DE MODELOS ML STRATEGY SELECTOR")
    print("=" * 65)
    
    backup_dir = clean_ml_strategy_selector()
    cleanup_success = verify_strategy_selector_cleanup()
    
    if cleanup_success:
        print(f"\n🎯 SIGUIENTE PASO:")
        print(f"Actualizar ML Strategy Selector para usar database_quality.db")
        print(f"Solo 7 estrategias habilitadas + Thompson Sampling conservador")
        print(f"Modelos anteriores respaldados en: {backup_dir}")
    else:
        print(f"\n⚠️  Revisar archivos residuales antes de continuar")