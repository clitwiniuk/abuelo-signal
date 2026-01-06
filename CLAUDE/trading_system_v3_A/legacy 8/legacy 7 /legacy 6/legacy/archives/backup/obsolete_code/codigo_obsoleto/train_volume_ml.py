#!/usr/bin/env python3
"""
Script para entrenar el sistema ML de volumen dinámico
Ejecutar una vez para generar los modelos iniciales
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.ml_volume_engine import MLVolumeEngine

def setup_logging():
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

async def main():
    logger = setup_logging()
    
    print("🧠 ENTRENAMIENTO ML DE VOLUMEN DINÁMICO")
    print("=" * 60)
    print("Entrenando modelos para requerimientos óptimos de volumen")
    print("=" * 60)
    
    try:
        # Inicializar engine con base de datos correcta
        logger.info("🔧 Inicializando MLVolumeEngine...")
        ml_engine = MLVolumeEngine(db_path="database_quality.db")
        
        # Verificar base de datos
        if not os.path.exists("database_quality.db"):
            logger.error("❌ Base de datos no encontrada: database_quality.db")
            return False
        
        # Limpiar modelos anteriores
        logger.info("🧹 Limpiando modelos anteriores...")
        if os.path.exists(ml_engine.model_dir):
            import shutil
            shutil.rmtree(ml_engine.model_dir)
            os.makedirs(ml_engine.model_dir, exist_ok=True)
            print("✅ Modelos anteriores eliminados")
        
        # Entrenar modelos desde cero
        logger.info("🎯 Iniciando entrenamiento de modelos desde cero...")
        results = ml_engine.train_models()
        
        # Mostrar resultados
        print("\n" + "=" * 60)
        print("📊 RESULTADOS DEL ENTRENAMIENTO")
        print("=" * 60)
        
        total_strategies = len(results)
        good_models = 0
        
        for strategy, metrics in results.items():
            mae = metrics['mae']
            r2 = metrics['r2']
            
            # Criterio de calidad: R² > 0.3 y MAE < 0.5
            quality = "✅ BUENO" if r2 > 0.3 and mae < 0.5 else "⚠️ REGULAR" if r2 > 0.1 else "❌ POBRE"
            if r2 > 0.3 and mae < 0.5:
                good_models += 1
            
            print(f"{quality} {strategy:20} | R²: {r2:.3f} | MAE: {mae:.3f}")
        
        # Estadísticas generales
        success_rate = (good_models / total_strategies) * 100
        print(f"\n🎯 RESUMEN: {good_models}/{total_strategies} modelos de calidad ({success_rate:.1f}%)")
        
        if success_rate >= 70:
            print("✅ Entrenamiento exitoso - Modelos listos para producción")
            print("💡 Los modelos reemplazarán los valores hardcodeados de volumen")
        elif success_rate >= 40:
            print("⚠️ Entrenamiento parcial - Algunos modelos necesitan más datos")
        else:
            print("❌ Entrenamiento insuficiente - Se usarán valores fallback")
        
        # Información de deployment
        print(f"\n📁 Modelos guardados en: {ml_engine.model_dir}")
        print("🔄 Para usar en producción, ejecutar ml_engine.load_models()")
        
        # Test de carga
        logger.info("🧪 Probando carga de modelos...")
        if ml_engine.load_models():
            print("✅ Modelos cargados correctamente")
        else:
            print("❌ Error cargando modelos")
        
        print("=" * 60)
        
        return success_rate >= 40
        
    except Exception as e:
        logger.error(f"❌ Error durante entrenamiento: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)