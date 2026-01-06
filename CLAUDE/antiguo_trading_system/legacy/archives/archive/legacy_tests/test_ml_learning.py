#!/usr/bin/env python3
"""
Script para probar y diagnosticar el aprendizaje del sistema ML
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Agregar el directorio del proyecto al path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from strategies.ml_strategy_selector import create_ml_strategy_selector, ContextualBandit
import numpy as np

def test_ml_learning():
    """Test básico del sistema de aprendizaje ML"""
    print("🔍 DIAGNÓSTICO DEL SISTEMA ML")
    print("=" * 50)
    
    # 1. Verificar si existe el archivo del modelo
    model_path = "data/ml_models/strategy_selector.json"
    print(f"📁 Verificando archivo del modelo: {model_path}")
    
    if os.path.exists(model_path):
        print("✅ Archivo del modelo encontrado!")
        
        # Leer y mostrar contenido
        with open(model_path, 'r') as f:
            model_data = json.load(f)
        
        print(f"📊 Estrategias en el modelo: {model_data.get('strategies', [])}")
        print(f"📈 Estadísticas disponibles: {list(model_data.get('strategy_stats', {}).keys())}")
        print(f"🕐 Última actualización: {model_data.get('timestamp', 'N/A')}")
        
        # Mostrar estadísticas de cada estrategia
        for strategy, stats in model_data.get('strategy_stats', {}).items():
            print(f"   {strategy}: {stats.get('total_trades', 0)} trades, "
                  f"{stats.get('win_rate', 0):.1%} win rate, "
                  f"avg PnL: {stats.get('avg_pnl', 0):.2f}")
    else:
        print("❌ Archivo del modelo NO encontrado")
        print("   Esto significa que el modelo nunca se ha guardado")
        print("   Posibles causas:")
        print("   - No se han completado suficientes trades (necesita 50)")
        print("   - Las posiciones no se están cerrando correctamente")
        print("   - Error en el proceso de guardado")
    
    # 2. Crear un modelo de prueba para verificar funcionalidad
    print("\n🧪 PRUEBA DE FUNCIONALIDAD ML")
    print("-" * 30)
    
    try:
        # Crear selector ML con estrategias de prueba
        test_strategies = ['gap_go', 'momentum', 'reversal', 'breakout']
        selector = create_ml_strategy_selector(test_strategies, model_path)
        
        print(f"✅ ML Selector creado con {len(test_strategies)} estrategias")
        
        # Simular contexto de mercado
        test_context = np.random.rand(10)  # 10 features aleatorias
        
        # Obtener recomendación
        recommendation = selector.select_strategy(test_context)
        print(f"🎯 Recomendación de prueba: {recommendation}")
        
        # Simular feedback de aprendizaje
        print("\n🔄 Simulando aprendizaje...")
        for i in range(5):
            strategy = np.random.choice(test_strategies)
            reward = np.random.uniform(-1, 1)  # Reward aleatorio
            selector.update_model(test_context, strategy, reward)
            print(f"   Actualización {i+1}: {strategy} con reward {reward:.3f}")
        
        # Mostrar estadísticas actualizadas
        print("\n📊 Estadísticas después de la simulación:")
        for strategy, stats in selector.strategy_stats.items():
            if stats.total_trades > 0:
                print(f"   {strategy}: {stats.total_trades} trades, "
                      f"{stats.win_rate:.1%} win rate, "
                      f"avg PnL: {stats.avg_pnl:.2f}")
        
        # Probar guardado
        test_save_path = "data/ml_models/test_model.json"
        selector.save_model(test_save_path)
        
        if os.path.exists(test_save_path):
            print(f"✅ Modelo de prueba guardado exitosamente en {test_save_path}")
            
            # Verificar contenido
            with open(test_save_path, 'r') as f:
                test_data = json.load(f)
            print(f"📁 Archivo contiene {len(test_data)} campos principales")
            
            # Limpiar archivo de prueba
            os.remove(test_save_path)
            print("🧹 Archivo de prueba eliminado")
        else:
            print("❌ Error: No se pudo guardar el modelo de prueba")
            
    except Exception as e:
        print(f"❌ Error en la prueba de funcionalidad: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Verificar logs del sistema
    print("\n📋 VERIFICANDO LOGS DEL SISTEMA")
    print("-" * 30)
    
    log_file = "trading_system.log"
    if os.path.exists(log_file):
        print(f"✅ Archivo de log encontrado: {log_file}")
        
        # Buscar logs relacionados con ML
        ml_logs = []
        with open(log_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if any(keyword in line for keyword in ['🧠 ML', '💾 ML', 'ML Learning', 'ML Tracking']):
                    ml_logs.append((line_num, line.strip()))
        
        if ml_logs:
            print(f"🔍 Encontrados {len(ml_logs)} logs relacionados con ML:")
            for line_num, log_line in ml_logs[-10:]:  # Últimos 10 logs
                print(f"   L{line_num}: {log_line}")
        else:
            print("⚠️ No se encontraron logs relacionados con ML")
            print("   Esto sugiere que el sistema ML no está siendo utilizado activamente")
    else:
        print(f"❌ Archivo de log no encontrado: {log_file}")
    
    print("\n" + "=" * 50)
    print("🏁 DIAGNÓSTICO COMPLETADO")

if __name__ == "__main__":
    test_ml_learning()
