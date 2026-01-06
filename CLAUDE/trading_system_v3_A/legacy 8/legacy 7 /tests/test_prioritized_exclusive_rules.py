#!/usr/bin/env python3
"""
Test para validar el sistema de prioridades en reglas mutuamente excluyentes
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import sys
import os

# Importar las funciones corregidas del outlier_hunter
sys.path.append('../smallcaps-algorithm/rule_extraction')
from rules.outlier_hunter import generate_outlier_hunting_rules

def validate_prioritized_outlier_rule(rule: dict, outlier_events: pd.DataFrame, excluded_indices: set = None) -> dict:
    """
    Validación especializada para reglas con prioridades/exclusividad
    """
    if excluded_indices is None:
        excluded_indices = set()
    
    # Filtrar eventos excluyendo los ya capturados por reglas de mayor prioridad
    filtered_events = outlier_events[~outlier_events.index.isin(excluded_indices)]
    
    if len(filtered_events) == 0:
        return {
            'valid': False,
            'reason': 'No remaining events after exclusions',
            'sample_size': 0
        }
    
    # Aplicar condiciones de la regla
    mask = pd.Series([True] * len(filtered_events), index=filtered_events.index)
    
    for field, condition in rule['conditions'].items():
        if field in filtered_events.columns:
            operator = condition['operator']
            value = condition['value']

            if operator == '<':
                mask &= filtered_events[field] < value
            elif operator == '>':
                mask &= filtered_events[field] > value
            elif operator == '<=':
                mask &= filtered_events[field] <= value
            elif operator == '>=':
                mask &= filtered_events[field] >= value
            elif operator == '==':
                mask &= filtered_events[field] == value

    matching_events = filtered_events[mask]

    if len(matching_events) == 0:
        return {
            'valid': False,
            'reason': 'No matching events found',
            'sample_size': 0
        }

    # Calcular métricas
    returns = matching_events['daily_return_pct']
    wins = returns[returns > 0]
    losses = returns[returns <= 0]

    # Obtener top 3 trades para diferenciación
    sorted_returns = returns.sort_values(ascending=False)
    top_3_trades = sorted_returns.head(3).tolist()

    results = {
        'valid': True,
        'sample_size': len(matching_events),
        'win_rate': len(wins) / len(returns) if len(returns) > 0 else 0,
        'avg_return': returns.mean(),
        'median_return': returns.median(),
        'avg_win': wins.mean() if len(wins) > 0 else 0,
        'avg_loss': losses.mean() if len(losses) > 0 else 0,
        'best_trade': returns.max(),
        'best_trades_top3': top_3_trades,
        'worst_trade': returns.min(),
        'expectancy': (
            (len(wins) / len(returns)) * wins.mean() +
            (len(losses) / len(returns)) * losses.mean()
        ) if len(returns) > 0 else 0
    }

    return results

def create_priority_test_events():
    """Crear eventos de test específicos para validación de prioridades"""
    
    base_date = datetime(2025, 1, 1)
    events = []
    
    # RULE 1: Penny Stock ($3-$5) con volatilidad - 12 eventos únicos para esta regla
    for i in range(12):
        events.append({
            'symbol': f'RULE1_PENNY{i}',
            'date': base_date + timedelta(days=i),
            'regular_open': 3.5 + i * 0.08,  # 3.5-4.36 para $3-$5
            'regular_close': 3.5 + i * 0.08 + (4.0 + i * 0.25),  # Retorno variable
            'high': 4.3 + i * 0.25,
            'low': 3.4 + i * 0.08,
            'volume': 1500000 + i * 80000,
            'daily_return_pct': 100.0 + i * 12,  # 100-232%
            'premarket_range_pct': 4.2 + i * 0.3,  # > 3% volatilidad
            'volume_ratio': 2.2 + i * 0.1,  # < 3x para evitar otras reglas
            'momentum': 0.65 + i * 0.02
        })
    
    # RULE 2: Ultra-cheap (<$3) con alto volumen >3x - 10 eventos únicos
    for i in range(10):
        events.append({
            'symbol': f'RULE2_ULTRA{i}',
            'date': base_date + timedelta(days=20+i),
            'regular_open': 1.8 + i * 0.1,  # < $3
            'regular_close': 1.8 + i * 0.1 + (5.5 + i * 0.35),  # Retorno muy alto
            'high': 2.3 + i * 0.35,
            'low': 1.7 + i * 0.1,
            'volume': 5000000 + i * 150000,  # Alto volumen
            'daily_return_pct': 150.0 + i * 15,  # 150-285%
            'premarket_range_pct': 5.5 + i * 0.4,
            'volume_ratio': 4.2 + i * 0.2,  # > 3x
            'momentum': 0.75 + i * 0.03
        })
    
    # RULE 3: Ultra-cheap (<$3) con volumen normal <=3x - 8 eventos únicos
    for i in range(8):
        events.append({
            'symbol': f'RULE3_NORMAL{i}',
            'date': base_date + timedelta(days=40+i),
            'regular_open': 1.6 + i * 0.12,  # < $3
            'regular_close': 1.6 + i * 0.12 + (3.8 + i * 0.2),  # Retorno moderado
            'high': 2.0 + i * 0.2,
            'low': 1.5 + i * 0.12,
            'volume': 2500000 + i * 60000,  # Volumen normal
            'daily_return_pct': 80.0 + i * 10,  # 80-150%
            'premarket_range_pct': 4.0 + i * 0.25,
            'volume_ratio': 2.8 + i * 0.08,  # <= 3x
            'momentum': 0.55 + i * 0.025
        })
    
    # RULE 4: Penny ($3-$5) con alto volumen Y alta volatilidad - 8 eventos únicos
    for i in range(8):
        events.append({
            'symbol': f'RULE4_COMBO{i}',
            'date': base_date + timedelta(days=60+i),
            'regular_open': 4.2 + i * 0.12,  # $3-$5 (pero alta para evitar rule 1)
            'regular_close': 4.2 + i * 0.12 + (6.8 + i * 0.4),  # Retorno muy alto
            'high': 4.9 + i * 0.4,
            'low': 4.0 + i * 0.12,
            'volume': 6500000 + i * 120000,  # Alto volumen
            'daily_return_pct': 120.0 + i * 14,  # 120-216%
            'premarket_range_pct': 7.2 + i * 0.5,  # > 5% para cumplir regla
            'volume_ratio': 4.8 + i * 0.3,  # > 3x
            'momentum': 0.85 + i * 0.04
        })
    
    return pd.DataFrame(events)

def test_prioritized_exclusive_rules():
    """Test de sistema de prioridades con reglas mutuamente excluyentes"""
    
    print("🧪 TEST: Sistema de prioridades con reglas mutuamente excluyentes")
    print("=" * 80)
    
    # Crear eventos de test
    events_df = create_priority_test_events()
    print(f"✅ Eventos creados: {len(events_df)}")
    
    # Crear patrón de outliers simulado
    outlier_patterns = {
        'penny_stock_pct': 80.0,
        'positive_pct': 60.0,
        'high_volume_pct': 45.0
    }
    
    # Generar reglas con sistema de prioridades
    rules = generate_outlier_hunting_rules(outlier_patterns, events_df)
    print(f"✅ Reglas generadas con prioridades: {len(rules)}")
    
    # Validar cada regla usando el sistema de prioridades
    rule_results = {}
    excluded_indices = set()
    all_captured_indices = []
    
    print(f"\n🔍 Validando reglas por prioridad:")
    print("-" * 80)
    
    for i, rule in enumerate(rules, 1):
        print(f"\n{i}. {rule['name']} (Prioridad {rule['priority']})")
        print(f"   📋 Descripción: {rule['description']}")
        print(f"   🎯 Condiciones: {rule['conditions']}")
        print(f"   🚫 Excluyendo eventos ya capturados por reglas de mayor prioridad: {len(excluded_indices)}")
        
        # Validar regla excluyendo eventos de mayor prioridad
        validation = validate_prioritized_outlier_rule(rule, events_df, excluded_indices)
        
        if validation['valid']:
            best_trade = validation['best_trade']
            best_trades_top3 = validation['best_trades_top3']
            
            print(f"   ✅ Válida: {validation['sample_size']} eventos")
            print(f"   📈 Best Trade: +{best_trade:.1f}%")
            print(f"   🏆 Top 3 Trades: {', '.join(f'+{t:.1f}%' for t in best_trades_top3)}")
            print(f"   💪 Win Rate: {validation['win_rate']:.1%}")
            
            # Actualizar excluciones para la siguiente regla
            if validation['sample_size'] > 0:
                # Obtener índices de eventos capturados por esta regla
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
                
                captured_indices = set(events_df[mask].index)
                excluded_indices.update(captured_indices)
                all_captured_indices.extend(list(captured_indices))
            
            rule_results[rule['name']] = {
                'priority': rule['priority'],
                'sample_size': validation['sample_size'],
                'best_trade': best_trade,
                'best_trades_top3': best_trades_top3,
                'captured_indices': list(captured_indices) if validation['sample_size'] > 0 else []
            }
        else:
            print(f"   ❌ No válida: {validation['reason']}")
            rule_results[rule['name']] = {
                'priority': rule['priority'],
                'sample_size': 0,
                'valid': False
            }
    
    # Verificar mutual exclusivity con prioridades
    print(f"\n🔬 VERIFICACIÓN DE MUTUAL EXCLUSIVITY CON PRIORIDADES:")
    print("=" * 80)
    
    total_captured = len(all_captured_indices)
    unique_captured = len(set(all_captured_indices))
    
    print(f"Total eventos capturados: {total_captured}")
    print(f"Eventos únicos capturados: {unique_captured}")
    
    if total_captured == unique_captured:
        print("✅ ÉXITO: Sistema de prioridades funciona - NO hay solapamiento")
    else:
        print("❌ PROBLEMA: Aún hay solapamiento entre reglas")
        overlapping = [idx for idx in set(all_captured_indices) if all_captured_indices.count(idx) > 1]
        print(f"   Índices solapados: {overlapping}")
    
    # Verificar diferenciación de best trades
    print(f"\n📊 ANÁLISIS DE DIFERENCIACIÓN CON PRIORIDADES:")
    print("-" * 80)
    
    valid_rules = {name: results for name, results in rule_results.items() 
                   if 'best_trade' in results}
    
    if valid_rules:
        best_trade_values = [results['best_trade'] for results in valid_rules.values()]
        unique_best_trades = set(best_trade_values)
        
        if len(unique_best_trades) == len(best_trade_values):
            print("✅ ÉXITO: Todas las reglas tienen diferentes best trades")
            print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
            for rule_name, results in valid_rules.items():
                print(f"   • {rule_name} (Prioridad {results['priority']}): +{results['best_trade']:.1f}%")
        else:
            print("❌ PROBLEMA: Algunas reglas aún tienen best trades idénticos")
            print(f"   Best Trades únicos: {len(unique_best_trades)}/{len(best_trade_values)}")
            for rule_name, results in valid_rules.items():
                print(f"   • {rule_name} (Prioridad {results['priority']}): +{results['best_trade']:.1f}%")
    else:
        print("❌ PROBLEMA: No se pudieron validar las reglas correctamente")
        best_trade_values = []
        unique_best_trades = set()
    
    # Crear JSON output para análisis
    output_data = {
        'test_timestamp': datetime.now().isoformat(),
        'test_type': 'prioritized_exclusive_rules',
        'test_events_count': len(events_df),
        'rules_generated': len(rules),
        'mutually_exclusive': total_captured == unique_captured,
        'unique_best_trades': len(unique_best_trades) == len(best_trade_values) if best_trade_values else False,
        'total_captured': total_captured,
        'unique_captured': unique_captured,
        'overlapping_indices': [idx for idx in set(all_captured_indices) if all_captured_indices.count(idx) > 1],
        'rule_results': rule_results,
        'best_trade_values': best_trade_values,
        'test_status': 'PASSED' if (total_captured == unique_captured and 
                                   len(unique_best_trades) == len(best_trade_values)) else 'FAILED'
    }
    
    with open('test_prioritized_exclusive_results.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Resultados guardados en: test_prioritized_exclusive_results.json")
    print(f"📋 Status del Test: {output_data['test_status']}")
    
    return output_data['test_status'] == 'PASSED'

def main():
    """Función principal del test"""
    
    print("🚀 INICIANDO TEST DE SISTEMA DE PRIORIDADES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Ejecutar test
    test_passed = test_prioritized_exclusive_rules()
    
    # Resultado final
    print(f"\n🏁 RESULTADO FINAL:")
    print("=" * 80)
    if test_passed:
        print("✅ SISTEMA DE PRIORIDADES FUNCIONANDO CORRECTAMENTE")
        print("   • Reglas mutuamente excluyentes")
        print("   • Best trades diferenciados")
        print("   • No hay solapamiento entre reglas")
    else:
        print("❌ SISTEMA DE PRIORIDADES NECESITA REVISIÓN")
        print("   • Revisar lógica de exclusividad")
        print("   • Verificar diferenciación de best trades")
    
    return test_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)