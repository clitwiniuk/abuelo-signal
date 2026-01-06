#!/usr/bin/env python3
"""
Test completo para validar la solución del problema Best Trade idénticos
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# Importar las funciones corregidas del outlier_hunter
import sys
import os
sys.path.append('../smallcaps-algorithm/rule_extraction')
from rules.outlier_hunter import validate_outlier_rule, generate_outlier_hunting_rules, get_outlier_hunting_summary
from events.processor import EventProcessor

def create_test_events_with_different_best_trades():
    """Crear eventos de test que produzcan diferentes best trades"""
    
    base_date = datetime(2025, 1, 1)
    events = []
    
    # EVENTOS ÚNICOS para OUTLIER_PENNY_STOCK_EXTREME (Best trade: +600%)
    # Estos eventos SOLO cumplen el primer criterio (regular_open < 5.0, premarket_range_pct > 3.0)
    for i in range(8):
        events.append({
            'symbol': f'PENNY{i}',
            'date': base_date + timedelta(days=i),
            'regular_open': 4.50 + i * 0.1,  # 4.5-5.2 para cumplir < 5.0 pero NO < 3.0
            'regular_close': 4.50 + i * 0.1 + (6.00 + i * 0.2),  # Alto retorno relativo
            'high': 5.00 + i * 0.2,
            'low': 4.40 + i * 0.1,
            'volume': 1000000 + i * 50000,
            'daily_return_pct': 600.0 + i * 5,  # Los mejores retornos (600%+)
            'premarket_range_pct': 4.0 + i * 0.3,  # > 3% pero NO > 5%
            'volume_ratio': 2.5 + i * 0.1,  # > 2x pero NO > 3x
            'momentum': 0.6 + i * 0.03
        })
    
    # EVENTOS ÚNICOS para OUTLIER_PENNY_VOLUME_SPIKE (Best trade: +450%)
    # Estos eventos SOLO cumplen el segundo criterio (regular_open < 5.0, volume_ratio > 3.0, premarket_range_pct > 5.0)
    for i in range(8):
        events.append({
            'symbol': f'SPIKE{i}',
            'date': base_date + timedelta(days=10+i),
            'regular_open': 3.00 + i * 0.2,  # 3.0-4.4 para cumplir < 5.0
            'regular_close': 3.00 + i * 0.2 + (4.50 + i * 0.15),  # Retorno medio
            'high': 3.50 + i * 0.15,
            'low': 2.90 + i * 0.2,
            'volume': 6000000 + i * 100000,  # Volume muy alto
            'daily_return_pct': 450.0 + i * 8,  # Retornos medios (450%+)
            'premarket_range_pct': 6.0 + i * 0.4,  # > 5% para cumplir el segundo criterio
            'volume_ratio': 4.0 + i * 0.2,  # > 3x para cumplir el segundo criterio
            'momentum': 0.5 + i * 0.04
        })
    
    # EVENTOS ÚNICOS para OUTLIER_ULTRA_PENNY_MOONSHOT (Best trade: +350%)
    # Estos eventos SOLO cumplen el tercer criterio (regular_open < 3.0, volume_ratio > 2.0)
    for i in range(8):
        events.append({
            'symbol': f'ULTRA{i}',
            'date': base_date + timedelta(days=20+i),
            'regular_open': 1.50 + i * 0.15,  # 1.5-2.55 para cumplir < 3.0
            'regular_close': 1.50 + i * 0.15 + (3.50 + i * 0.1),  # Retorno más conservador
            'high': 2.00 + i * 0.1,
            'low': 1.40 + i * 0.15,
            'volume': 3000000 + i * 75000,  # Volume medio
            'daily_return_pct': 350.0 + i * 12,  # Retornos menores pero consistentes (350%+)
            'premarket_range_pct': 3.5 + i * 0.2,  # < 5% para NO cumplir segundo criterio
            'volume_ratio': 2.5 + i * 0.1,  # > 2x pero < 3x para NO cumplir segundo criterio
            'momentum': 0.7 + i * 0.02
        })
    
    return pd.DataFrame(events)

def test_outlier_rules_with_different_best_trades():
    """Test que valida que cada regla outlier detecta diferentes best trades"""
    
    print("🧪 TEST: Validación de reglas outlier hunting con diferentes best trades")
    print("=" * 70)
    
    # Crear eventos de test
    events_df = create_test_events_with_different_best_trades()
    print(f"✅ Eventos creados: {len(events_df)}")
    
    # Definir las 3 reglas de outlier hunting (usar formato correcto con 'operator')
    test_rules = [
        {
            'name': 'OUTLIER_PENNY_STOCK_EXTREME_TEST',
            'conditions': {
                'regular_open': {'operator': '<', 'value': 5.0},
                'premarket_range_pct': {'operator': '>', 'value': 3.0}
            },
            'description': 'Test rule for penny stocks with extreme premarket gaps'
        },
        {
            'name': 'OUTLIER_PENNY_VOLUME_SPIKE_TEST',
            'conditions': {
                'regular_open': {'operator': '<', 'value': 5.0},
                'volume_ratio': {'operator': '>', 'value': 3.0},
                'premarket_range_pct': {'operator': '>', 'value': 5.0}
            },
            'description': 'Test rule for penny stocks with volume spikes'
        },
        {
            'name': 'OUTLIER_ULTRA_PENNY_MOONSHOT_TEST',
            'conditions': {
                'regular_open': {'operator': '<', 'value': 3.0},
                'volume_ratio': {'operator': '>', 'value': 2.0}
            },
            'description': 'Test rule for ultra cheap penny stocks'
        }
    ]
    
    best_trades_results = {}
    
    # Validar cada regla y verificar que tengan diferentes best trades
    for rule in test_rules:
        print(f"\n🔍 Validando regla: {rule['name']}")
        
        validation_results = validate_outlier_rule(rule, events_df)
        
        if validation_results['valid']:
            best_trade = validation_results['best_trade']
            best_trades_top3 = validation_results['best_trades_top3']
            
            print(f"   ✅ Best Trade: +{best_trade:.2f}%")
            print(f"   📊 Top 3 Trades: {', '.join(f'+{t:.2f}%' for t in best_trades_top3)}")
            print(f"   📈 Sample Size: {validation_results['sample_size']} eventos")
            print(f"   🎯 Win Rate: {validation_results['win_rate']:.1%}")
            
            # Guardar para comparación
            best_trades_results[rule['name']] = {
                'best_trade': best_trade,
                'best_trades_top3': best_trades_top3,
                'sample_size': validation_results['sample_size']
            }
        else:
            print(f"   ❌ Regla no válida: {validation_results['reason']}")
    
    # Verificar que las reglas tienen diferentes best trades
    print(f"\n🔬 ANÁLISIS DE DIFERENCIACIÓN:")
    print("=" * 70)
    
    best_trade_values = [results['best_trade'] for results in best_trades_results.values()]
    unique_best_trades = set(best_trade_values)
    
    if len(unique_best_trades) == len(best_trade_values):
        print("✅ ÉXITO: Todas las reglas tienen diferentes best trades")
        print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
        for rule_name, results in best_trades_results.items():
            print(f"   • {rule_name}: +{results['best_trade']:.2f}%")
    else:
        print("❌ FALLO: Algunas reglas aún tienen best trades idénticos")
        print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
        for rule_name, results in best_trades_results.items():
            print(f"   • {rule_name}: +{results['best_trade']:.2f}%")
    
    # Verificar que top 3 trades también sean diferentes
    print(f"\n📊 ANÁLISIS TOP 3 TRADES:")
    top_3_summaries = []
    for rule_name, results in best_trades_results.items():
        top_3_summary = f"{rule_name}: " + "/".join(f"+{t:.1f}%" for t in results['best_trades_top3'])
        top_3_summaries.append(top_3_summary)
        print(f"   {top_3_summary}")
    
    # Crear JSON output para inspección
    output_data = {
        'test_timestamp': datetime.now().isoformat(),
        'test_events_count': len(events_df),
        'rules_tested': len(test_rules),
        'unique_best_trades': len(unique_best_trades),
        'best_trade_values': best_trade_values,
        'detailed_results': best_trades_results,
        'top_3_summaries': top_3_summaries,
        'test_status': 'PASSED' if len(unique_best_trades) == len(best_trade_values) else 'FAILED'
    }
    
    with open('test_best_trade_solucion_results.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Resultados guardados en: test_best_trade_solucion_results.json")
    print(f"📋 Status del Test: {output_data['test_status']}")
    
    return output_data['test_status'] == 'PASSED'

def test_backwards_compatibility():
    """Test de compatibilidad hacia atrás"""
    
    print("\n🔄 TEST: Compatibilidad hacia atrás")
    print("=" * 70)
    
    events_df = create_test_events_with_different_best_trades()
    
    # Test con regla simple
    simple_rule = {
        'name': 'SIMPLE_TEST_RULE',
        'conditions': {'regular_open': {'operator': '<', 'value': 5.0}},
        'description': 'Simple test rule'
    }
    
    validation_results = validate_outlier_rule(simple_rule, events_df)
    
    # Verificar que tiene los campos esperados
    expected_fields = ['valid', 'sample_size', 'avg_return', 'win_rate', 'expectancy', 'best_trade', 'best_trades_top3']
    
    for field in expected_fields:
        if field in validation_results:
            print(f"   ✅ Campo '{field}': {validation_results[field]}")
        else:
            print(f"   ❌ Campo '{field}' faltante")
    
    # Verificar que best_trade es compatible con el old format
    if 'best_trade' in validation_results:
        print(f"\n🔗 Best Trade (backward compatible): +{validation_results['best_trade']:.2f}%")
        print(f"📊 Top 3 Best Trades (new format): {validation_results['best_trades_top3']}")
        
        # El best_trade debe ser igual al primer elemento del top 3
        if validation_results['best_trades_top3']:
            if abs(validation_results['best_trade'] - validation_results['best_trades_top3'][0]) < 0.001:
                print("✅ Best Trade es consistente con Top 3 trades")
                return True
            else:
                print("❌ Best Trade NO es consistente con Top 3 trades")
                return False
    else:
        print("❌ Campo 'best_trade' faltante")
        return False

def main():
    """Función principal del test"""
    
    print("🚀 INICIANDO TEST COMPLETO DE LA SOLUCIÓN BEST TRADE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test 1: Diferenciación de best trades
    test1_passed = test_outlier_rules_with_different_best_trades()
    
    # Test 2: Compatibilidad hacia atrás
    test2_passed = test_backwards_compatibility()
    
    # Resultado final
    print(f"\n🏁 RESUMEN FINAL DE TESTS")
    print("=" * 80)
    print(f"Test 1 (Diferenciación Best Trades): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Backward Compatibility): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    overall_result = test1_passed and test2_passed
    print(f"\n🎯 RESULTADO GENERAL: {'✅ TODOS LOS TESTS PASARON' if overall_result else '❌ ALGUNOS TESTS FALLARON'}")
    
    return overall_result

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)