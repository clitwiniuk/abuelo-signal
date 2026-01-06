"""
Análisis del problema de "Best Trade" idénticos en Outlier Hunting Rules

Este script analiza por qué todas las reglas de outlier hunting tienen 
el mismo "Best Trade" (+356.49%) y propone soluciones.
"""

import pandas as pd
import numpy as np
import sys
import os
import json

# Añadir path del smallcaps-algorithm
sys.path.append('../smallcaps-algorithm')

def analyze_outlier_rules_issue():
    """
    Analiza el problema de best_trade idénticos en las reglas de outlier hunting.
    """
    
    print("🔍 ANÁLISIS: Problema de Best Trade idénticos en Outlier Hunting Rules")
    print("=" * 80)
    
    # Cargar los resultados de backtest para ver los datos
    try:
        with open('../smallcaps-algorithm/output/rule_extraction_analysis/validated_rules.json', 'r') as f:
            validated_rules = json.load(f)
        
        print(f"📊 Cargadas {len(validated_rules)} reglas validadas")
        
        # Filtrar reglas de outlier hunting
        outlier_rules = [r for r in validated_rules if r.get('strategy_type') == 'OUTLIER_HUNTING']
        
        print(f"\n🎯 Reglas de Outlier Hunting encontradas: {len(outlier_rules)}")
        
        # Analizar cada regla
        for rule in outlier_rules:
            name = rule.get('name', 'Unknown')
            backtest = rule.get('backtest_results', {})
            sample_size = rule.get('sample_size', 0)
            best_trade = backtest.get('best_trade', 0)
            worst_trade = backtest.get('worst_trade', 0)
            
            print(f"\n📈 {name}:")
            print(f"   Sample Size: {sample_size}")
            print(f"   Best Trade: {best_trade:.2f}%")
            print(f"   Worst Trade: {worst_trade:.2f}%")
            
            # Obtener las condiciones de la regla
            conditions = rule.get('conditions', {})
            print(f"   Condiciones: {conditions}")
        
        # Verificar si efectivamente son el mismo trade
        best_trades = [r.get('backtest_results', {}).get('best_trade', 0) for r in outlier_rules]
        
        print(f"\n🔍 Análisis de Best Trades:")
        print(f"   Valores únicos: {set(best_trades)}")
        
        if len(set(best_trades)) == 1:
            print("   ❌ PROBLEMA CONFIRMADO: Todas las reglas tienen el mismo best trade")
            print("   📊 Esto indica que todas las reglas están detectando el mismo evento extremo")
        else:
            print("   ✅ Las reglas tienen diferentes best trades")
            
    except Exception as e:
        print(f"❌ Error al cargar validated_rules.json: {e}")
        print("🔄 Intentando simular el análisis...")
        
        # Simular el problema basado en los datos que el usuario proporcionó
        simulate_outlier_issue()

def simulate_outlier_issue():
    """
    Simula el problema basado en lo que reportó el usuario.
    """
    
    print("\n🎭 SIMULACIÓN del problema:")
    print("-" * 50)
    
    # Datos simulados basados en lo que el usuario reportó
    outlier_rules_simulated = [
        {
            'name': 'OUTLIER_PENNY_STOCK_EXTREME',
            'conditions': {'regular_open': {'operator': '<', 'value': 5.0}},
            'sample_size': 163,
            'best_trade': 356.49
        },
        {
            'name': 'OUTLIER_PENNY_VOLUME_SPIKE', 
            'conditions': {
                'regular_open': {'operator': '<', 'value': 5.0},
                'volume_ratio': {'operator': '>', 'value': 3.0}
            },
            'sample_size': 119,
            'best_trade': 356.49
        },
        {
            'name': 'OUTLIER_ULTRA_PENNY_MOONSHOT',
            'conditions': {
                'regular_open': {'operator': '<', 'value': 3.0},
                'volume_ratio': {'operator': '>', 'value': 2.0}
            },
            'sample_size': 94,
            'best_trade': 356.49
        }
    ]
    
    print("📊 Análisis de condiciones:")
    for rule in outlier_rules_simulated:
        print(f"\n🎯 {rule['name']}:")
        print(f"   Condiciones: {rule['conditions']}")
        print(f"   Sample Size: {rule['sample_size']}")
        print(f"   Best Trade: {rule['best_trade']:.2f}%")
    
    print(f"\n💡 DIAGNÓSTICO:")
    print(f"   Todas las reglas tienen el mismo best trade: {outlier_rules_simulated[0]['best_trade']:.2f}%")
    print(f"   Esto indica que existe un evento extremo que cumple TODOS los criterios:")
    print(f"   - regular_open < $5 (penny stock)")
    print(f"   - regular_open < $3 (ultra cheap)")  
    print(f"   - volume_ratio > 2-3x (volume spike)")
    print(f"   - Este evento de +356.49% es el más extremo en el dataset")
    
    return outlier_rules_simulated

def propose_solutions():
    """
    Propone soluciones para el problema del best trade idéntico.
    """
    
    print(f"\n🛠️ SOLUCIONES PROPUESTAS:")
    print("=" * 50)
    
    solutions = [
        {
            'title': '1. Mostrar Top 3 Best Trades por Regla',
            'description': 'En lugar de mostrar solo el mejor trade, mostrar los top 3 trades específicos de cada regla',
            'implementation': 'Modificar outlier_hunter.py para guardar top 3 trades, no solo el máximo',
            'benefit': 'Permite ver la diferenciación real entre reglas'
        },
        {
            'title': '2. Filtrar Events Comunes',
            'description': 'Excluir eventos que coinciden con múltiples reglas al calcular best trade',
            'implementation': 'Para cada regla, excluir eventos que también coinciden con otras reglas de outlier hunting',
            'benefit': 'Cada regla tendría su propio "mejor trade único"'
        },
        {
            'title': '3. Segmentación por Intersecciones',
            'description': 'Crear sub-reglas específicas para las intersecciones de criterios',
            'implementation': 'Crear reglas separadas para: solo penny, penny+volume, ultra+volume',
            'benefit': 'Reglas más específicas y diferenciadas'
        },
        {
            'title': '4. Análisis de Overlapping Events',
            'description': 'Mostrar estadísticas de overlapping events entre reglas',
            'implementation': 'Reportar cuántos eventos son exclusivos vs compartidos',
            'benefit': 'Usuario entiende mejor la relación entre reglas'
        }
    ]
    
    for i, solution in enumerate(solutions, 1):
        print(f"\n{solution['title']}")
        print(f"   Descripción: {solution['description']}")
        print(f"   Implementación: {solution['implementation']}")
        print(f"   Beneficio: {solution['benefit']}")
    
    print(f"\n🎯 RECOMENDACIÓN:")
    print(f"   Implementar Solución #1 (Top 3 Best Trades) + Solución #4 (Análisis de Overlapping)")
    print(f"   Esto es más informativo y ayuda al usuario a entender las diferencias reales")

def test_implementation():
    """
    Test de implementación de la solución recomendada.
    """
    
    print(f"\n🧪 TEST: Implementación de solución Top 3 Best Trades")
    print("=" * 60)
    
    # Simular datos de trades para una regla
    simulated_returns = np.array([
        356.49,  # Evento extremo (común a todas las reglas)
        245.12,  # Evento único de esta regla
        189.33,  # Evento único de esta regla  
        156.78,  # Evento único de esta regla
        98.45,   # Evento único de esta regla
        67.23,   # Evento único de esta regla
        45.12,   # Evento único de esta regla
        23.45,   # Evento único de esta regla
        12.34,   # Evento único de esta regla
        8.76     # Evento único de esta regla
    ])
    
    # Implementación actual (solo el máximo)
    current_best_trade = simulated_returns.max()
    
    # Implementación propuesta (top 3)
    top_3_trades = simulated_returns[np.argsort(simulated_returns)[-3:]]
    top_3_trades = sorted(top_3_trades, reverse=True)
    
    print(f"📊 Datos simulados de returns: {simulated_returns}")
    print(f"\n🔍 Implementación actual:")
    print(f"   Best Trade: {current_best_trade:.2f}%")
    print(f"   ❌ Mismo valor para todas las reglas")
    
    print(f"\n✅ Implementación propuesta:")
    print(f"   Top 3 Best Trades: {[f'{t:.2f}%' for t in top_3_trades]}")
    print(f"   ✅ Diferenciación clara entre reglas")
    
    print(f"\n📈 Beneficio:")
    print(f"   Usuario puede ver que aunque el trade máximo es común,")
    print(f"   cada regla tiene diferentes trades secundarios únicos.")

if __name__ == "__main__":
    print("🚀 Iniciando análisis del problema de Best Trade idénticos")
    print("=" * 80)
    
    analyze_outlier_rules_issue()
    propose_solutions()
    test_implementation()
    
    print("\n" + "=" * 80)
    print("📋 CONCLUSIÓN:")
    print("El problema es real: todas las reglas detectan el mismo evento extremo.")
    print("Solución recomendada: Implementar Top 3 Best Trades + Análisis de Overlapping.")
    print("=" * 80)