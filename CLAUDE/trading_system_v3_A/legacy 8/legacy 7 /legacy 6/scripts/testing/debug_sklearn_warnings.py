#!/usr/bin/env python3
"""
Debug de advertencias sklearn - Diagnóstico de warnings sobre nombres de features
Ubicación: scripts/testing/ (estructura organizada)
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def capture_sklearn_warnings():
    """Captura y analiza las advertencias de sklearn"""
    print("🔍 DIAGNÓSTICO DE ADVERTENCIAS SKLEARN")
    print("=" * 50)
    print("📍 Desde: scripts/testing/debug_sklearn_warnings.py")
    print("=" * 50)
    
    # Configurar captura de warnings
    warnings.filterwarnings('error', category=UserWarning, module='sklearn')
    
    print("\n1️⃣ TESTING ML VOLUME ENGINE")
    test_ml_volume_engine_warnings()
    
    print("\n2️⃣ TESTING ML EXIT ENGINE")  
    test_ml_exit_engine_warnings()
    
    print("\n3️⃣ SOLUCIONES SUGERIDAS")
    suggest_solutions()

def test_ml_volume_engine_warnings():
    """Test específico de advertencias en ML Volume Engine"""
    try:
        from core.ml_volume_engine import MLVolumeEngine, MarketContext
        
        engine = MLVolumeEngine()
        if engine.load_models():
            print(f"✅ Modelos cargados: {len(engine.models)}")
            
            # Crear contexto de prueba
            test_context = MarketContext(
                time_of_day=0.4,
                day_of_week=1, 
                market_cap=50_000_000,
                avg_volume=200_000,
                float_shares=10_000_000,
                sector="Technology",
                recent_performance=3.5,
                market_stress=0.5,
                volume_trend=1.8,
                price_level=8.50
            )
            
            print("\n🧪 Ejecutando predicciones para capturar warnings...")
            
            # Test con cada estrategia para ver cuáles generan warnings
            for strategy in list(engine.models.keys())[:3]:
                print(f"\n   📊 Testing {strategy}:")
                try:
                    volume_req = engine.predict_volume_requirement(strategy, test_context)
                    print(f"      ✅ Predicción: {volume_req:.2f}x (sin warning)")
                except UserWarning as w:
                    print(f"      ⚠️ WARNING capturado: {w}")
                    print(f"      💡 Modelo: {strategy}")
                except Exception as e:
                    print(f"      ❌ Error: {e}")
        else:
            print("❌ No se pudieron cargar modelos")
            
    except Exception as e:
        print(f"❌ Error general: {e}")

def test_ml_exit_engine_warnings():
    """Test específico de advertencias en ML Exit Engine"""
    try:
        print("📋 Verificando modelos ML Exit Engine...")
        
        # Verificar que los archivos existen
        model_files = [
            'core/models/exit_models/smallcap_exit/exit_classifier.pkl',
            'core/models/exit_models/smallcap_exit/profit_regressor.pkl',
            'core/models/exit_models/smallcap_exit/scaler.pkl'
        ]
        
        for file in model_files:
            if os.path.exists(file):
                print(f"   ✅ {os.path.basename(file)}")
            else:
                print(f"   ❌ {os.path.basename(file)} - FALTA")
        
        # Intentar cargar y usar los modelos si están disponibles
        try:
            import joblib
            
            # Test del scaler específicamente (es el que más warnings genera)
            scaler_path = 'core/models/exit_models/smallcap_exit/scaler.pkl'
            if os.path.exists(scaler_path):
                print(f"\n🔍 Testing scaler...")
                
                scaler = joblib.load(scaler_path)
                
                # Crear datos de prueba como array (sin nombres)
                test_data_array = np.array([[10.0, 15.0, 5.0, 30, 0.05]])
                
                print(f"   📊 Datos de prueba (array): {test_data_array.shape}")
                
                try:
                    scaled = scaler.transform(test_data_array)
                    print(f"   ✅ Transformación exitosa (sin warning)")
                except UserWarning as w:
                    print(f"   ⚠️ WARNING capturado: {w}")
                    print(f"   💡 Causa: Scaler entrenado con DataFrame, usando array numpy")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    
                # Test con DataFrame (con nombres)
                print(f"\n   🧪 Testing con DataFrame...")
                try:
                    # Intentar crear DataFrame con nombres estimados
                    feature_names = ['entry_price', 'current_price', 'pnl_pct', 'time_held', 'volume_ratio']
                    test_df = pd.DataFrame(test_data_array, columns=feature_names)
                    
                    scaled_df = scaler.transform(test_df)
                    print(f"   ✅ Transformación con DataFrame exitosa")
                except UserWarning as w:
                    print(f"   ⚠️ WARNING con DataFrame: {w}")
                except Exception as e:
                    print(f"   ❌ Error con DataFrame: {e}")
                    
        except ImportError:
            print("⚠️ joblib no disponible para test directo")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def suggest_solutions():
    """Sugiere soluciones para los warnings"""
    print("💡 SOLUCIONES SUGERIDAS PARA LOS WARNINGS:")
    print("-" * 50)
    
    print("\n🔧 CAUSA DEL PROBLEMA:")
    print("   Los modelos sklearn fueron entrenados con DataFrames (con nombres de columnas)")
    print("   pero están recibiendo arrays numpy (sin nombres) durante predicción")
    
    print("\n🛠️ SOLUCIONES POSIBLES:")
    
    print("\n   1️⃣ SOLUCIÓN INMEDIATA (Suprimir warnings):")
    print("      - Agregar filtro de warnings específico")
    print("      - No afecta funcionalidad, solo limpia output")
    
    print("\n   2️⃣ SOLUCIÓN CORRECTA (Usar nombres correctos):")
    print("      - Pasar DataFrames con nombres de columnas en lugar de arrays")
    print("      - Modificar código para mantener feature names")
    
    print("\n   3️⃣ SOLUCIÓN REENTRENAMIENTO:")
    print("      - Reentrenar modelos con arrays directamente (sin nombres)")
    print("      - Más trabajo pero elimina dependencia de nombres")
    
    print("\n🎯 RECOMENDACIÓN:")
    print("   Como el sistema funciona perfectamente (100% tests),")
    print("   la SOLUCIÓN 1 es suficiente para producción.")
    
    print("\n📝 CÓDIGO PARA SUPRIMIR WARNINGS:")
    print("   ```python")
    print("   import warnings")
    print("   warnings.filterwarnings('ignore', ")
    print("                          message='X does not have valid feature names',")
    print("                          category=UserWarning)")
    print("   ```")

def main():
    """Función principal"""
    print("🔍 Iniciando diagnóstico de advertencias sklearn")
    
    # Primero, configurar warnings para mostrar todos
    warnings.resetwarnings()
    warnings.filterwarnings('always', category=UserWarning, module='sklearn')
    
    capture_sklearn_warnings()
    
    print("\n" + "=" * 50)
    print("✅ Diagnóstico completado")
    print("💡 Revisar soluciones sugeridas arriba")

if __name__ == "__main__":
    main()