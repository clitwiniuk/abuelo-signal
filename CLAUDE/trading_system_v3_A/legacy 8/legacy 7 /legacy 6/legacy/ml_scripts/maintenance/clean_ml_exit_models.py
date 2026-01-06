#!/usr/bin/env python3
"""
Limpiar modelos ML Exit Engine anteriores y hacer backup antes de optimización
Similar al proceso que hicimos con ML Volume Engine
"""

import os
import shutil
import glob
from datetime import datetime

def clean_ml_exit_models():
    """
    Limpia modelos ML Exit Engine anteriores con backup de seguridad
    """
    print("🗑️  LIMPIEZA DE MODELOS ML EXIT ENGINE")
    print("=" * 50)
    
    # Crear directorio de backup
    backup_dir = f"backup_exit_models_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"📦 Creando backup en: {backup_dir}")
    
    # 1. Backup y limpiar modelos de exit en core/models/exit_models/
    exit_models_dir = "core/models/exit_models"
    
    if os.path.exists(exit_models_dir):
        print(f"\n🔍 Procesando {exit_models_dir}")
        
        # Crear subdirectorio en backup
        backup_exit_dir = os.path.join(backup_dir, "exit_models")
        
        # Copiar todo el directorio al backup
        print(f"   📦 Backup completo: exit_models/")
        shutil.copytree(exit_models_dir, backup_exit_dir)
        
        # Eliminar directorio original
        print(f"   🗑️  Remove: exit_models/ completo")
        shutil.rmtree(exit_models_dir)
    
    # 2. Buscar archivos residuales relacionados con ML Exit Engine
    print(f"\n🔍 Buscando archivos residuales de ML Exit Engine...")
    
    # Patrones de archivos relacionados con exit
    patterns = [
        "**/*exit*classifier*.pkl",
        "**/*exit*regressor*.pkl", 
        "**/*exit*scaler*.pkl",
        "**/*exit*model*.pkl",
        "**/*exit*metadata*.json"
    ]
    
    residual_files = []
    for pattern in patterns:
        files = glob.glob(pattern, recursive=True)
        for file in files:
            # Skip si es backup o no es relevante
            if ("backup_" in file or 
                "test_" in file or 
                ".git" in file or
                "__pycache__" in file):
                continue
            
            if os.path.exists(file):
                residual_files.append(file)
    
    # Eliminar duplicados
    residual_files = list(set(residual_files))
    
    for file_path in residual_files:
        filename = os.path.basename(file_path)
        backup_path = os.path.join(backup_dir, f"residual_{filename}")
        
        print(f"   📦 Backup residual: {filename}")
        shutil.copy2(file_path, backup_path)
        
        print(f"   🗑️  Remove residual: {filename}")
        os.remove(file_path)
    
    # 3. Buscar y limpiar archivos de cache relacionados
    print(f"\n🔍 Limpiando cache de ML Exit Engine...")
    
    cache_patterns = [
        "core/__pycache__/*ml_exit*",
        "**/*exit*cache*",
        "**/*exit*.pyc"
    ]
    
    for pattern in cache_patterns:
        files = glob.glob(pattern, recursive=True)
        for file in files:
            if os.path.exists(file) and "backup_" not in file:
                print(f"   🗑️  Cache: {file}")
                os.remove(file)
    
    # 4. Resumen
    backup_files = []
    for root, dirs, files in os.walk(backup_dir):
        for file in files:
            backup_files.append(os.path.join(root, file))
    
    print(f"\n✅ LIMPIEZA ML EXIT ENGINE COMPLETADA")
    print(f"📦 {len(backup_files)} archivos respaldados en {backup_dir}")
    print(f"🗑️  Modelos anteriores eliminados")
    print(f"🚀 Listo para reentrenar con database_quality.db")
    
    return backup_dir

def verify_exit_cleanup():
    """
    Verifica que la limpieza del ML Exit Engine fue exitosa
    """
    print(f"\n🔍 VERIFICANDO LIMPIEZA ML EXIT ENGINE...")
    
    # Verificar que no quedan modelos de exit
    exit_files = []
    
    patterns_to_check = [
        "core/models/exit_models",
        "**/*exit*classifier*.pkl",
        "**/*exit*regressor*.pkl"
    ]
    
    for pattern in patterns_to_check:
        if pattern == "core/models/exit_models":
            if os.path.exists(pattern):
                exit_files.append(pattern)
        else:
            files = glob.glob(pattern, recursive=True)
            for file in files:
                if ("backup_" not in file and 
                    "test_" not in file and
                    ".git" not in file):
                    exit_files.append(file)
    
    if exit_files:
        print(f"⚠️  Archivos residuales encontrados:")
        for file in exit_files:
            print(f"   - {file}")
    else:
        print(f"✅ Limpieza verificada - No quedan modelos ML Exit antiguos")
    
    return len(exit_files) == 0

if __name__ == "__main__":
    print("🚀 LIMPIADOR DE MODELOS ML EXIT ENGINE")
    print("=" * 60)
    
    backup_dir = clean_ml_exit_models()
    cleanup_success = verify_exit_cleanup()
    
    if cleanup_success:
        print(f"\n🎯 SIGUIENTE PASO:")
        print(f"Actualizar ML Exit Engine para usar database_quality.db y 7 estrategias")
        print(f"Modelos anteriores respaldados en: {backup_dir}")
    else:
        print(f"\n⚠️  Revisar archivos residuales antes de continuar")