#!/usr/bin/env python3
"""
Limpiar modelos ML anteriores y hacer backup antes de reentrenar con database_quality.db
"""

import os
import shutil
import glob
from datetime import datetime

def clean_old_ml_models():
    """
    Limpia modelos ML anteriores con backup de seguridad
    """
    print("🗑️  LIMPIEZA DE MODELOS ML ANTERIORES")
    print("=" * 50)
    
    # Crear directorio de backup
    backup_dir = f"backup_models_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"📦 Creando backup en: {backup_dir}")
    
    # 1. Backup y limpiar modelos de volumen en core/models/volume_models/
    volume_models_dir = "core/models/volume_models"
    
    if os.path.exists(volume_models_dir):
        print(f"\n🔍 Procesando {volume_models_dir}")
        
        # Crear subdirectorio en backup
        backup_volume_dir = os.path.join(backup_dir, "volume_models")
        os.makedirs(backup_volume_dir, exist_ok=True)
        
        # Mover todos los archivos a backup
        volume_files = glob.glob(os.path.join(volume_models_dir, "*"))
        
        for file_path in volume_files:
            if os.path.isfile(file_path):
                filename = os.path.basename(file_path)
                backup_path = os.path.join(backup_volume_dir, filename)
                
                print(f"   📦 Backup: {filename}")
                shutil.copy2(file_path, backup_path)
                
                print(f"   🗑️  Remove: {filename}")
                os.remove(file_path)
        
        # Eliminar directorio vacío
        if os.path.exists(volume_models_dir) and not os.listdir(volume_models_dir):
            os.rmdir(volume_models_dir)
            print(f"   📁 Directorio eliminado: {volume_models_dir}")
    
    # 2. Backup específico de continuous learning (es grande)
    continuous_learning_pkl = "data/ml_models/continuous_learning_engine.pkl"
    
    if os.path.exists(continuous_learning_pkl):
        print(f"\n🔍 Procesando continuous learning engine...")
        
        backup_path = os.path.join(backup_dir, "continuous_learning_engine.pkl")
        print(f"   📦 Backup: continuous_learning_engine.pkl (1.5MB)")
        shutil.copy2(continuous_learning_pkl, backup_path)
        
        print(f"   🗑️  Remove: continuous_learning_engine.pkl")
        os.remove(continuous_learning_pkl)
    
    # 3. Limpiar cualquier scaler o modelo residual
    print(f"\n🔍 Buscando archivos residuales...")
    
    # Buscar archivos que contengan "volume", "model", "scaler" 
    patterns = [
        "**/*volume*.pkl",
        "**/*scaler*.pkl", 
        "**/*model*.pkl"
    ]
    
    residual_files = []
    for pattern in patterns:
        residual_files.extend(glob.glob(pattern, recursive=True))
    
    # Filtrar archivos ya procesados y duplicados
    residual_files = [f for f in residual_files if os.path.exists(f)]
    residual_files = list(set(residual_files))  # Remove duplicates
    
    for file_path in residual_files:
        # Skip si ya fue procesado o no es relevante
        if "backup_models_" in file_path or "database" in file_path:
            continue
            
        filename = os.path.basename(file_path)
        backup_path = os.path.join(backup_dir, f"residual_{filename}")
        
        print(f"   📦 Backup residual: {filename}")
        shutil.copy2(file_path, backup_path)
        
        print(f"   🗑️  Remove residual: {filename}")
        os.remove(file_path)
    
    # 4. Limpiar directorios vacíos
    print(f"\n🧹 Limpiando directorios vacíos...")
    
    dirs_to_check = ["core/models", "core/models/volume_models"]
    
    for dir_path in dirs_to_check:
        if os.path.exists(dir_path) and not os.listdir(dir_path):
            os.rmdir(dir_path)
            print(f"   📁 Directorio vacío eliminado: {dir_path}")
    
    # 5. Resumen
    backup_files = glob.glob(os.path.join(backup_dir, "**/*"), recursive=True)
    backup_files = [f for f in backup_files if os.path.isfile(f)]
    
    print(f"\n✅ LIMPIEZA COMPLETADA")
    print(f"📦 {len(backup_files)} archivos respaldados en {backup_dir}")
    print(f"🗑️  Modelos antiguos eliminados")
    print(f"🚀 Listo para reentrenar con database_quality.db")
    
    return backup_dir

def verify_cleanup():
    """
    Verifica que la limpieza fue exitosa
    """
    print(f"\n🔍 VERIFICANDO LIMPIEZA...")
    
    # Verificar que no quedan modelos de volumen
    volume_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pkl') and ('volume' in file.lower() or 'scaler' in file.lower()):
                if 'backup_models_' not in root:  # Ignore backups
                    volume_files.append(os.path.join(root, file))
    
    if volume_files:
        print(f"⚠️  Archivos residuales encontrados:")
        for file in volume_files:
            print(f"   - {file}")
    else:
        print(f"✅ Limpieza verificada - No quedan modelos antiguos")
    
    # Verificar que core/models está limpio
    models_dir = "core/models"
    if os.path.exists(models_dir):
        remaining = os.listdir(models_dir)
        if remaining:
            print(f"⚠️  Archivos en core/models: {remaining}")
        else:
            print(f"✅ core/models limpio")
    else:
        print(f"✅ core/models eliminado")

if __name__ == "__main__":
    print("🚀 LIMPIADOR DE MODELOS ML ANTERIORES")
    print("=" * 60)
    
    backup_dir = clean_old_ml_models()
    verify_cleanup()
    
    print(f"\n🎯 SIGUIENTE PASO:")
    print(f"Reentrenar ML Volume Engine con database_quality.db")
    print(f"Modelos anteriores respaldados en: {backup_dir}")