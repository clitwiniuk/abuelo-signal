#!/usr/bin/env python3
"""
Test para validar las reglas mutuamente excluyentes del outlier_hunter
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import sys
import os

# Importar las funciones corregidas del outlier_hunter
sys.path.append('../smallcaps-algorithm/rule_extraction')
from rules.outlier_hunter import generate_outlier_hunting_rules, validate_outlier_rule

def create_diverse_test_events():
    """Crear eventos de test diversos para validar reglas mutuamente excluyentes"""
    
    base_date = datetime(2025, 1, 1)
    events = []
    
    # REGLA 1: Penny Stock ($3-$5) con volatilidad premarket
    for i in range(12):
        events.append({
            'symbol': f'PENNY{i}',
            'date': base_date + timedelta(days=i),
            'regular_open': 3.5 + i * 0.1,  # 3.5-4.6 para $3-$5
            'regular_close': 3.5 + i * 0.1 + (4.2 + i * 0.3),  # Retorno variable
            'high': 4.5 + i * 0.3,
            'low': 3.4 + i * 0.1,
            'volume': 1000000 + i * 100000,
            'daily_return_pct': 120.0 + i * 15,  # 120-285%
            'premarket_range_pct': 4.0 + i * 0.5,  # > 3% volatilidad
            'volume_ratio': 2.0 + i * 0.2,  # < 3x para evitar regla 4
            'momentum': 0.6 + i * 0.03
        })
    
    # REGLA 2: Ultra-cheap (<$3) con alto volumen >3x
    for i in range(10):
        events.append({
            'symbol': f'ULTRA_HIGH{i}',
            'date': base_date + timedelta(days=20+i),
            'regular_open': 1.8 + i * 0.1,  # < $3
            'regular_close': 1.8 + i * 0.1 + (5.1 + i * 0.4),  # Retorno muy alto
            'high': 2.2 + i * 0.4,
            'low': 1.7 + i * 0.1,
            'volume': 5000000 + i * 200000,  # Alto volumen
            'daily_return_pct': 180.0 + i * 20,  # 180-380%
            'premarket_range_pct': 6.0 + i * 0.4,
            'volume_ratio': 4.0 + i * 0.3,  # > 3x
            'momentum': 0.7 + i * 0.04
        })
    
    # REGLA 3: Ultra-cheap (<$3) con volumen normal <=3x
    for i in range(8):
        events.append({
            'symbol': f'ULTRA_NORMAL{i}',
            'date': base_date + timedelta(days=40+i),
            'regular_open': 1.5 + i * 0.15,  # < $3
            'regular_close': 1.5 + i * 0.15 + (3.2 + i * 0.2),  # Retorno moderado
            'high': 1.9 + i * 0.2,
            'low': 1.4 + i * 0.15,
            'volume': 2000000 + i * 50000,  # Volumen normal
            'daily_return_pct': 90.0 + i * 12,  # 90-186%
            'premarket_range_pct': 3.5 + i * 0.3,
            'volume_ratio': 2.5 + i * 0.1,  # <= 3x
            'momentum': 0.5 + i * 0.03
        })
    
    # REGLA 4: Penny ($3-$5) con alto volumen >3x Y alta volatilidad premarket >5%
    for i in range(8):
        events.append({
            'symbol': f'COMBO{i}',
            'date': base_date + timedelta(days=60+i),
            'regular_open': 4.0 + i * 0.15,  # $3-$5
            'regular_close': 4.0 + i * 0.15 + (6.5 + i * 0.5),  # Retorno muy alto
            'high': 4.8 + i * 0.5,
            'low': 3.8 + i * 0.15,
            'volume': 6000000 + i * 150000,  # Alto volumen
            'daily_return_pct': 140.0 + i * 18,  # 140-284%
            'premarket_range_pct': 6.5 + i * 0.6,  # > 5% para cumplir regla
            'volume_ratio': 4.5 + i * 0.4,  # > 3x
            'momentum': 0.8 + i * 0.05
        })
    
    return pd.DataFrame(events)

def test_mutually_exclusive_rules():
    """Test de reglas mutuamente excluyentes"""
    
    print("🧪 TEST: Validación de reglas mutuamente excluyentes")
    print("=" * 70)
    
    # Crear eventos de test
    events_df = create_diverse_test_events()
    print(f"✅ Eventos creados: {len(events_df)}")
    
    # Crear patrón de outliers simulado
    outlier_patterns = {
        'penny_stock_pct': 75.0,
        'positive_pct': 55.0,
        'high_volume_pct': 40.0
    }
    
    # Generar reglas mutuamente excluyentes
    rules = generate_outlier_hunting_rules(outlier_patterns, events_df)
    print(f"✅ Reglas generadas: {len(rules)}")
    
    # Validar cada regla
    rule_results = {}
    captured_events = []
    
    print(f"\n🔍 Validando cada regla:")
    print("-" * 70)
    
    for i, rule in enumerate(rules, 1):
        print(f"\n{i}. {rule['name']}")
        print(f"   📋 Descripción: {rule['description']}")
        print(f"   🎯 Condiciones: {rule['conditions']}")
        
        validation = validate_outlier_rule(rule, events_df)
        
        if validation['valid']:
            best_trade = validation['best_trade']
            best_trades_top3 = validation['best_trades_top3']
            
            print(f"   ✅ Válida: {validation['sample_size']} eventos")
            print(f"   📈 Best Trade: +{best_trade:.1f}%")
            print(f"   🏆 Top 3 Trades: {', '.join(f'+{t:.1f}%' for t in best_trades_top3)}")
            print(f"   💪 Win Rate: {validation['win_rate']:.1%}")
            
            # Guardar símbolos de eventos capturados
            mask = pd.Series([True] * len(events_df), index=events_df.index)
            for field, condition in rule['conditions'].items():
                if field in events_df.columns:
                    operator = condition['operator']
                    value = condition['value']
                    if operator == '<':
                        mask &= events_df[field] < value
                    elif operator == '>':
                        mask &= events_df[field] > value
                    elif operator == '>=':
                        mask &= events_df[field] >= value
                    elif operator == '<=':
                        mask &= events_df[field] <= value
            
            captured_symbols = events_df[mask]['symbol'].tolist()
            captured_events.extend(captured_symbols)
            
            rule_results[rule['name']] = {
                'sample_size': validation['sample_size'],
                'best_trade': best_trade,
                'best_trades_top3': best_trades_top3,
                'captured_symbols': captured_symbols
            }
        else:
            print(f"   ❌ No válida: {validation['reason']}")
    
    # Verificar mutual exclusivity
    print(f"\n🔬 VERIFICACIÓN DE MUTUAL EXCLUSIVITY:")
    print("=" * 70)
    
    total_captured = len(captured_events)
    unique_captured = len(set(captured_events))
    
    print(f"Total eventos capturados: {total_captured}")
    print(f"Eventos únicos capturados: {unique_captured}")
    
    if total_captured == unique_captured:
        print("✅ ÉXITO: Reglas son mutuamente excluyentes (no hay solapamiento)")
    else:
        print("❌ PROBLEMA: Hay solapamiento entre reglas")
        overlapping = [symbol for symbol in set(captured_events) if captured_events.count(symbol) > 1]
        print(f"   Símbolos solapados: {overlapping}")
    
    # Verificar diferenciación de best trades
    print(f"\n📊 ANÁLISIS DE DIFERENCIACIÓN:")
    print("-" * 70)
    
    best_trade_values = [results['best_trade'] for results in rule_results.values()]
    unique_best_trades = set(best_trade_values)
    
    if len(unique_best_trades) == len(best_trade_values):
        print("✅ ÉXITO: Todas las reglas tienen diferentes best trades")
        print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
        for rule_name, results in rule_results.items():
            print(f"   • {rule_name}: +{results['best_trade']:.1f}%")
    else:
        print("❌ PROBLEMA: Algunas reglas aún tienen best trades idénticos")
        print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
        for rule_name, results in rule_results.items():
            print(f"   • {rule_name}: +{results['best_trade']:.1f}%")
    
    # Crear JSON output para análisis
    output_data = {
        'test_timestamp': datetime.now().isoformat(),
        'test_events_count': len(events_df),
        'rules_generated': len(rules),
        'mutually_exclusive': total_captured == unique_captured,
        'unique_best_trades': len(unique_best_trades) == len(best_trade_values),
        'total_captured': total_captured,
        'unique_captured': unique_captured,
        'overlapping_symbols': [symbol for symbol in set(captured_events) if captured_events.count(symbol) > 1],
        'rule_results': rule_results,
        'best_trade_values': best_trade_values,
        'test_status': 'PASSED' if (total_captured == unique_captured and len(unique_best_trades) == len(best_trade_values)) else 'FAILED'
    }
    
    with open('test_mutually_exclusive_results.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Resultados guardados en: test_mutually_exclusive_results.json")
    print(f"📋 Status del Test: {output_data['test_status']}")
    
    return output_data['test_status'] == 'PASSED'

def main():
    """Función principal del test"""
    
    print("🚀 INICIANDO TEST DE REGLAS MUTUAMENTE EXCLUSIVAS")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Ejecutar test
    test_passed = test_mutually_exclusive_rules()
    
    # Resultado final
    print(f"\n🏁 RESULTADO FINAL:")
    print("=" * 80)
    if test_passed:
        print("✅ TODOS LOS TESTS PASARON - Reglas mutuamente excluyentes funcionando correctamente")
    else:
        print("❌ ALGUNOS TESTS FALLARON - Revisar solapamiento o diferenciación")
    
    return test_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)