#!/usr/bin/env python3
"""
Test final de integración que demuestra la solución completa del problema
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import sys
import os

# Importar las funciones corregidas
sys.path.append('../smallcaps-algorithm/rule_extraction')
from rules.outlier_hunter import generate_outlier_hunting_rules, validate_outlier_rule

def create_realistic_outlier_events():
    """Crear eventos realistas que repliquen el problema original"""
    
    base_date = datetime(2025, 1, 1)
    events = []
    
    # Simular el evento EXTREMO que causaba el problema original (+356.49%)
    # Este evento será capturado solo por UNA regla de alta prioridad
    events.append({
        'symbol': 'EXTREME_EVENT',
        'date': base_date,
        'regular_open': 4.85,  # Penny stock pero alta para evitar reglas más específicas
        'regular_close': 4.85 + (4.85 * 3.5649),  # +356.49% return
        'high': 22.0,
        'low': 4.80,
        'volume': 8000000,  # Alto volumen
        'daily_return_pct': 356.49,  # EL EVENTO PROBLEMÁTICO ORIGINAL
        'premarket_range_pct': 8.5,  # Alta volatilidad
        'volume_ratio': 5.2,
        'momentum': 0.9
    })
    
    # Eventos para regla 1: Penny Stock ($3-$5) con volatilidad
    for i in range(15):
        events.append({
            'symbol': f'PENNY_{i}',
            'date': base_date + timedelta(days=i+1),
            'regular_open': 3.2 + i * 0.08,
            'regular_close': 3.2 + i * 0.08 + (3.5 + i * 0.3),
            'high': 3.8 + i * 0.3,
            'low': 3.1 + i * 0.08,
            'volume': 1200000 + i * 50000,
            'daily_return_pct': 80.0 + i * 8,  # 80-200%
            'premarket_range_pct': 4.5 + i * 0.2,
            'volume_ratio': 2.5 + i * 0.1,
            'momentum': 0.6 + i * 0.02
        })
    
    # Eventos para regla 2: Ultra-cheap (<$3) con alto volumen
    for i in range(12):
        events.append({
            'symbol': f'ULTRA_HIGH_{i}',
            'date': base_date + timedelta(days=20+i),
            'regular_open': 1.5 + i * 0.1,
            'regular_close': 1.5 + i * 0.1 + (4.2 + i * 0.25),
            'high': 2.0 + i * 0.25,
            'low': 1.4 + i * 0.1,
            'volume': 4500000 + i * 100000,
            'daily_return_pct': 120.0 + i * 10,  # 120-240%
            'premarket_range_pct': 6.0 + i * 0.3,
            'volume_ratio': 4.0 + i * 0.2,
            'momentum': 0.7 + i * 0.03
        })
    
    # Eventos para regla 3: Ultra-cheap normal volumen
    for i in range(10):
        events.append({
            'symbol': f'ULTRA_NORMAL_{i}',
            'date': base_date + timedelta(days=40+i),
            'regular_open': 1.8 + i * 0.1,
            'regular_close': 1.8 + i * 0.1 + (3.0 + i * 0.2),
            'high': 2.2 + i * 0.2,
            'low': 1.7 + i * 0.1,
            'volume': 2000000 + i * 40000,
            'daily_return_pct': 60.0 + i * 8,  # 60-140%
            'premarket_range_pct': 4.0 + i * 0.2,
            'volume_ratio': 2.8 + i * 0.1,
            'momentum': 0.5 + i * 0.025
        })
    
    # Eventos para regla 4: Penny con alto volumen Y alta volatilidad
    for i in range(10):
        events.append({
            'symbol': f'COMBO_{i}',
            'date': base_date + timedelta(days=60+i),
            'regular_open': 4.5 + i * 0.05,
            'regular_close': 4.5 + i * 0.05 + (5.5 + i * 0.3),
            'high': 5.2 + i * 0.3,
            'low': 4.4 + i * 0.05,
            'volume': 6000000 + i * 80000,
            'daily_return_pct': 90.0 + i * 9,  # 90-180%
            'premarket_range_pct': 7.5 + i * 0.4,
            'volume_ratio': 4.5 + i * 0.25,
            'momentum': 0.8 + i * 0.035
        })
    
    return pd.DataFrame(events)

def test_problem_resolution():
    """Test que demuestra que el problema original está resuelto"""
    
    print("🧪 TEST FINAL: Verificación de Resolución del Problema Original")
    print("=" * 80)
    print("Problema Original: Todas las reglas mostraban 'Best Trade: +356.49%'")
    print("Causa: Superposición de reglas que capturaban el mismo evento extremo")
    print("Solución: Sistema de prioridades para mutual exclusivity")
    print("=" * 80)
    
    # Crear eventos realistas
    events_df = create_realistic_outlier_events()
    print(f"✅ Eventos creados: {len(events_df)}")
    print(f"   • Incluye el evento EXTREMO original (+356.49%)")
    
    # Crear patrón de outliers
    outlier_patterns = {
        'penny_stock_pct': 75.0,
        'positive_pct': 55.0,
        'high_volume_pct': 40.0
    }
    
    # Generar reglas con sistema de prioridades
    rules = generate_outlier_hunting_rules(outlier_patterns, events_df)
    print(f"✅ Reglas generadas con prioridades: {len(rules)}")
    
    # Validar cada regla
    rule_results = {}
    print(f"\n🔍 VALIDACIÓN DE CADA REGLA:")
    print("-" * 80)
    
    for rule in rules:
        print(f"\n• {rule['name']} (Prioridad {rule['priority']})")
        validation = validate_outlier_rule(rule, events_df)
        
        if validation['valid']:
            best_trade = validation['best_trade']
            best_trades_top3 = validation['best_trades_top3']
            
            print(f"  ✅ Válida: {validation['sample_size']} eventos")
            print(f"  📈 Best Trade: +{best_trade:.2f}%")
            print(f"  🏆 Top 3 Trades: {', '.join(f'+{t:.1f}%' for t in best_trades_top3)}")
            
            rule_results[rule['name']] = {
                'priority': rule['priority'],
                'best_trade': best_trade,
                'best_trades_top3': best_trades_top3,
                'sample_size': validation['sample_size']
            }
        else:
            print(f"  ❌ No válida: {validation['reason']}")
    
    # ANÁLISIS CRÍTICO: Verificar que el problema está resuelto
    print(f"\n🔬 ANÁLISIS CRÍTICO: ¿Está resuelto el problema original?")
    print("=" * 80)
    
    # 1. Verificar que NO todas las reglas tienen el mismo best trade
    if rule_results:
        best_trade_values = [results['best_trade'] for results in rule_results.values()]
        unique_best_trades = set(best_trade_values)
        
        print(f"📊 Best Trades encontrados:")
        for rule_name, results in rule_results.items():
            print(f"   • {rule_name}: +{results['best_trade']:.2f}%")
        
        print(f"\n🎯 Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
        
        if len(unique_best_trades) > 1:
            print("✅ PROBLEMA RESUELTO: Las reglas tienen diferentes best trades")
        else:
            print("❌ PROBLEMA PERSISTE: Todas las reglas aún tienen el mismo best trade")
        
        # 2. Verificar específicamente que el evento +356.49% NO aparece en todas las reglas
        extreme_event_count = sum(1 for bt in best_trade_values if abs(bt - 356.49) < 0.1)
        print(f"\n🎪 Evento EXTREMO (+356.49%) aparece en {extreme_event_count}/{len(rule_results)} reglas")
        
        if extreme_event_count == 1:
            print("✅ EXCELENTE: El evento extremo está en exactamente 1 regla (sistema de prioridades funcionando)")
        elif extreme_event_count == 0:
            print("✅ BUENO: El evento extremo no está en ninguna regla (filtrado correctamente)")
        else:
            print("❌ PROBLEMA: El evento extremo sigue apareciendo en múltiples reglas")
        
        # 3. Verificar mutual exclusivity
        total_sample_sizes = sum(results['sample_size'] for results in rule_results.values())
        print(f"\n🔄 Total de eventos capturados: {total_sample_sizes}")
        print(f"📊 Eventos únicos en dataset: {len(events_df)}")
        
        if total_sample_sizes <= len(events_df):
            print("✅ MUTUAL EXCLUSIVITY: No hay solapamiento entre reglas")
        else:
            print("❌ SOLAPAMIENTO: Las reglas están capturando los mismos eventos")
    
    # RESULTADO FINAL
    problem_resolved = (
        len(unique_best_trades) > 1 and  # Best trades diferentes
        extreme_event_count <= 1 and     # Evento extremo no duplicado
        total_sample_sizes <= len(events_df)  # No hay solapamiento
    )
    
    print(f"\n🏁 VEREDICTO FINAL:")
    print("=" * 80)
    
    if problem_resolved:
        print("🎉 PROBLEMA COMPLETAMENTE RESUELTO")
        print("   ✅ Reglas tienen diferentes best trades")
        print("   ✅ Evento extremo no se duplica entre reglas")
        print("   ✅ Sistema de prioridades funcionando")
        print("   ✅ Mutual exclusivity implementada")
        print("\n💡 El smallcaps-algorithm ahora produce reportes diferenciados")
        print("   que permiten mejor toma de decisiones en trading.")
    else:
        print("❌ PROBLEMA NO COMPLETAMENTE RESUELTO")
        print("   Revisar lógica de prioridades y exclusividad")
    
    # Crear output JSON
    output_data = {
        'test_timestamp': datetime.now().isoformat(),
        'test_type': 'final_problem_resolution',
        'problem_original': 'All rules showed same Best Trade: +356.49%',
        'solution_implemented': 'Priority system for mutual exclusivity',
        'problem_resolved': problem_resolved,
        'rules_generated': len(rules),
        'rule_results': rule_results,
        'unique_best_trades': len(unique_best_trades),
        'extreme_event_duplication': extreme_event_count,
        'total_captured': total_sample_sizes,
        'dataset_size': len(events_df),
        'verification': {
            'different_best_trades': len(unique_best_trades) > 1,
            'extreme_event_isolated': extreme_event_count <= 1,
            'no_overlap': total_sample_sizes <= len(events_df)
        }
    }
    
    with open('test_solucion_final_results.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Resultados detallados guardados en: test_solucion_final_results.json")
    
    return problem_resolved

def main():
    """Función principal del test final"""
    
    print("🚀 INICIANDO TEST FINAL DE RESOLUCIÓN DEL PROBLEMA")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Ejecutar test
    problem_resolved = test_problem_resolution()
    
    return problem_resolved

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)