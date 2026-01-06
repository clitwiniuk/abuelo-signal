#!/usr/bin/env python3
"""
Investigar causa raíz de warnings sklearn - Análisis profundo del problema
Ubicación: scripts/testing/ (estructura organizada)
"""

import sys
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def investigate_root_cause():
    """Investigar la causa raíz real de los warnings sklearn"""
    print("🔬 INVESTIGACIÓN CAUSA RAÍZ - WARNINGS SKLEARN")
    print("=" * 60)
    print("📍 Desde: scripts/testing/investigate_sklearn_root_cause.py")
    print("=" * 60)
    
    print("\n1️⃣ ANÁLISIS DE MODELOS ML VOLUME ENGINE")
    investigate_volume_engine_models()
    
    print("\n2️⃣ ANÁLISIS DEL CÓDIGO DE PREDICCIÓN")
    investigate_prediction_code()
    
    print("\n3️⃣ PROPUESTA DE SOLUCIÓN CORRECTA")
    propose_proper_solution()

def investigate_volume_engine_models():
    """Investigar los modelos del ML Volume Engine"""
    print("🔍 Investigando modelos individuales...")
    
    model_dir = "core/models/volume_models"
    if os.path.exists(model_dir):
        model_files = [f for f in os.listdir(model_dir) if f.endswith('.pkl')]
        print(f"📊 Encontrados {len(model_files)} archivos .pkl")
        
        # Analizar algunos modelos específicos
        scaler_files = [f for f in model_files if 'scaler' in f]
        model_files_proper = [f for f in model_files if 'volume_model' in f]
        
        print(f"📊 Scalers: {len(scaler_files)}")
        print(f"📊 Modelos: {len(model_files_proper)}")
        
        # Investigar un scaler específico
        if scaler_files:
            scaler_file = scaler_files[0]  # Tomar el primero
            scaler_path = os.path.join(model_dir, scaler_file)
            
            print(f"\n🔬 ANÁLISIS DETALLADO: {scaler_file}")
            try:
                scaler = joblib.load(scaler_path)
                
                # Verificar si tiene feature_names_in_
                if hasattr(scaler, 'feature_names_in_'):
                    print(f"✅ feature_names_in_ encontrado: {scaler.feature_names_in_}")
                    print(f"📊 Número de features esperadas: {len(scaler.feature_names_in_)}")
                else:
                    print("❌ No tiene feature_names_in_ (entrenado con array)")
                
                # Verificar n_features_in_
                if hasattr(scaler, 'n_features_in_'):
                    print(f"📊 n_features_in_: {scaler.n_features_in_}")
                
                # Verificar otros atributos
                print(f"📊 Tipo de scaler: {type(scaler).__name__}")
                if hasattr(scaler, 'mean_'):
                    print(f"📊 Features entrenadas: {len(scaler.mean_)}")
                
            except Exception as e:
                print(f"❌ Error analizando {scaler_file}: {e}")
        
        # Investigar un modelo específico
        if model_files_proper:
            model_file = model_files_proper[0]
            model_path = os.path.join(model_dir, model_file)
            
            print(f"\n🔬 ANÁLISIS MODELO: {model_file}")
            try:
                model = joblib.load(model_path)
                print(f"📊 Tipo de modelo: {type(model).__name__}")
                
                if hasattr(model, 'feature_names_in_'):
                    print(f"✅ Model feature_names_in_: {model.feature_names_in_}")
                else:
                    print("❌ Modelo sin feature_names_in_")
                    
            except Exception as e:
                print(f"❌ Error analizando modelo: {e}")
    
    else:
        print(f"❌ Directorio no existe: {model_dir}")

def investigate_prediction_code():
    """Investigar cómo se hace la predicción en el código"""
    print("🔍 Investigando código de predicción...")
    
    try:
        # Leer el archivo ML Volume Engine
        engine_file = "core/ml_volume_engine.py"
        if os.path.exists(engine_file):
            with open(engine_file, 'r') as f:
                content = f.read()
            
            print("📄 Analizando ml_volume_engine.py...")
            
            # Buscar el método predict_volume_requirement
            lines = content.split('\n')
            in_predict_method = False
            predict_lines = []
            
            for i, line in enumerate(lines):
                if 'def predict_volume_requirement' in line:
                    in_predict_method = True
                    predict_lines.append(f"{i+1}: {line}")
                elif in_predict_method:
                    if line.strip().startswith('def ') and 'predict_volume_requirement' not in line:
                        break
                    predict_lines.append(f"{i+1}: {line}")
                    
                    # Buscar líneas específicas problemáticas
                    if 'transform' in line or 'predict' in line:
                        print(f"🎯 LÍNEA CLAVE {i+1}: {line.strip()}")
            
            # Buscar cómo se preparan los datos
            print(f"\n🔍 MÉTODO predict_volume_requirement ({len(predict_lines)} líneas)")
            
            # Buscar específicamente transform o predict calls
            for line in predict_lines[-20:]:  # Últimas 20 líneas del método
                if 'transform' in line.lower() or 'predict' in line.lower():
                    print(f"   📍 {line}")
        
        # Investigar create_market_context también
        print(f"\n🔍 Buscando create_market_context...")
        if 'def create_market_context' in content:
            print("✅ create_market_context encontrado")
            
            # Buscar cómo se crean los features
            create_context_lines = []
            in_create_context = False
            
            for i, line in enumerate(lines):
                if 'def create_market_context' in line:
                    in_create_context = True
                elif in_create_context:
                    if line.strip().startswith('def ') and 'create_market_context' not in line:
                        break
                    create_context_lines.append(f"{i+1}: {line}")
            
            print(f"📊 create_market_context: {len(create_context_lines)} líneas")
            
            # Buscar return statement
            for line in create_context_lines:
                if 'return' in line and '[' in line:
                    print(f"🎯 RETURN: {line}")
                    
    except Exception as e:
        print(f"❌ Error investigando código: {e}")

def propose_proper_solution():
    """Proponer la solución correcta basada en la investigación"""
    print("💡 PROPUESTA DE SOLUCIÓN CORRECTA")
    print("-" * 50)
    
    print("\n🔍 PROBLEMA IDENTIFICADO:")
    print("   Los modelos sklearn fueron entrenados con DataFrames (con nombres de columnas)")
    print("   pero el código de predicción les está pasando arrays numpy (sin nombres)")
    
    print("\n🛠️ SOLUCIONES POSIBLES:")
    
    print("\n   1️⃣ MANTENER NOMBRES DE FEATURES EN PREDICCIÓN:")
    print("      - Modificar predict_volume_requirement para usar DataFrames")
    print("      - Más elegante y correcto desde sklearn perspective")
    print("      - Requiere modificar create_market_context")
    
    print("\n   2️⃣ REENTRENAR MODELOS SIN FEATURE NAMES:")
    print("      - Reentrenar todos los modelos usando arrays numpy directamente") 
    print("      - Elimina la dependencia de nombres de columnas")
    print("      - Más trabajo pero más robusto")
    
    print("\n   3️⃣ HÍBRIDO - CONVERTIR ARRAYS A DATAFRAMES:")
    print("      - Convertir arrays a DataFrames justo antes de la predicción")
    print("      - Mínimo cambio de código")
    print("      - Mantiene compatibilidad")
    
    print("\n🎯 RECOMENDACIÓN:")
    print("   SOLUCIÓN 3 (Híbrido) es la mejor:")
    print("   - Mínimo impacto en código existente")
    print("   - Soluciona el problema raíz") 
    print("   - No requiere reentrenamiento")
    
    print("\n📝 IMPLEMENTACIÓN SUGERIDA:")
    print("   En ml_volume_engine.py, method predict_volume_requirement:")
    print("   - Antes de scaler.transform(features)")
    print("   - Convertir: features_df = pd.DataFrame([features], columns=feature_names)")
    print("   - Usar: scaler.transform(features_df)")

def main():
    """Función principal"""
    print("🔬 Iniciando investigación de causa raíz")
    
    investigate_root_cause()
    
    print("\n" + "=" * 60)
    print("✅ Investigación completada")
    print("💡 Revisar propuesta de solución arriba")

if __name__ == "__main__":
    main()