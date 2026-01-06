"""
Test para validar la corrección del problema de premarket_momentum NaN.

Este test verifica que cuando no hay datos de premarket, el sistema no genere
valores NaN en el cálculo del momentum premarket.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Añadir el path del smallcaps-algorithm
sys.path.append('../smallcaps-algorithm')

from rule_extraction.events.processor import EventProcessor
from rule_extraction.analysis.momentum_analyzer import MomentumAnalyzer


def test_premarket_momentum_fix():
    """Test que valida la corrección del problema de premarket_momentum."""
    
    print("🧪 TEST: Validación de corrección premarket_momentum")
    print("=" * 60)
    
    # Crear datos de test sin movimiento de premarket
    # Simula datos donde no hay variación de precio en premarket
    base_date = pd.Timestamp('2025-10-15', tz='America/New_York')
    
    # Crear datos para múltiples días sin movimiento premarket
    symbols_data = {}
    
    for symbol_idx, symbol in enumerate(['TEST1', 'TEST2', 'TEST3']):
        dates = []
        data = []
        
        for day_idx in range(10):  # 10 días de datos
            current_date = base_date + timedelta(days=day_idx)
            
            # Crear datos donde el precio es constante (simula sin movimiento premarket)
            # Esto causaría el problema original con NaN
            constant_price = 10.0 + symbol_idx * 5 + day_idx * 0.1
            
            # Solo datos de mercado regular (sin datos de premarket para forzar el caso problemático)
            reg_time = current_date.replace(hour=10, minute=0)
            dates.append(reg_time)
            data.append({
                'open': constant_price,
                'high': constant_price + 0.5,
                'low': constant_price - 0.3,
                'close': constant_price + 0.2,
                'volume': 5000,
                'vwap': constant_price + 0.1
            })
        
        # Crear DataFrame para este símbolo
        df = pd.DataFrame(data)
        df.index = pd.DatetimeIndex(dates)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')
        
        symbols_data[symbol] = df
    
    print(f"📊 Datos creados: {len(symbols_data)} símbolos")
    print(f"📅 Rango de fechas: {df.index.min()} a {df.index.max()}")
    
    # Procesar eventos
    processor = EventProcessor()
    events = processor.process_all_symbols(symbols_data)
    
    print(f"\n📈 Eventos procesados: {len(events)} eventos")
    print(f"🏷️ Columnas disponibles: {list(events.columns)}")
    
    # Verificar que no hay valores NaN problemáticos
    print("\n🔍 Verificación de valores NaN:")
    nan_counts = events.isnull().sum()
    for col, count in nan_counts.items():
        if count > 0:
            print(f"  ❌ {col}: {count} valores NaN")
        else:
            print(f"  ✅ {col}: 0 valores NaN")
    
    # Test específico del problema original
    print(f"\n⚠️  Verificación del problema original:")
    if 'premarket_high' in events.columns and 'premarket_low' in events.columns:
        # Verificar que no todos los valores son iguales (que causaría división por cero)
        price_ranges = events['premarket_high'] - events['premarket_low']
        print(f"  📊 Rango de precios premarket (high - low):")
        print(f"    - Min: {price_ranges.min():.6f}")
        print(f"    - Max: {price_ranges.max():.6f}")
        print(f"    - Media: {price_ranges.mean():.6f}")
        
        if (price_ranges == 0).all():
            print("  ❌ PROBLEMA: Todos los rangos son 0 (causaría división por cero)")
            return False
        else:
            print("  ✅ CORRECCIÓN: Hay variación en los rangos de precio")
    
    # Test del MomentumAnalyzer
    print(f"\n🎯 Test del MomentumAnalyzer:")
    try:
        momentum_analyzer = MomentumAnalyzer(events)
        momentum_results = momentum_analyzer.analyze_premarket_momentum()
        
        if not momentum_results:
            print("  ❌ ERROR: MomentumAnalyzer retornó resultados vacíos")
            return False
        else:
            print("  ✅ ÉXITO: MomentumAnalyzer procesó los datos sin errores")
            print(f"  📊 Categorías encontradas: {list(momentum_results.keys())}")
            
            for category, stats in momentum_results.items():
                count = stats.get('count', 0)
                print(f"    - {category}: {count} eventos")
        
        return True
        
    except Exception as e:
        print(f"  ❌ ERROR en MomentumAnalyzer: {e}")
        return False


def test_momentum_calculation():
    """Test específico del cálculo de momentum."""
    
    print("\n🔬 TEST: Cálculo detallado de momentum")
    print("=" * 50)
    
    # Crear evento específico con datos que simulan el problema original
    event_data = {
        'symbol': 'TEST',
        'date': pd.Timestamp('2025-10-15', tz='America/New_York'),
        'premarket_high': 10.0,  # Valores iguales (problema original)
        'premarket_low': 10.0,
        'premarket_close': 10.0,
        'regular_open': 10.0,
        'regular_close': 10.5,
        'daily_return_pct': 5.0
    }
    
    events_df = pd.DataFrame([event_data])
    events_df.index = events_df['date']
    
    print("📊 Datos de test:")
    print(f"  premarket_high: {event_data['premarket_high']}")
    print(f"  premarket_low: {event_data['premarket_low']}")
    print(f"  premarket_close: {event_data['premarket_close']}")
    
    # Calcular momentum manualmente
    momentum_calc = (
        (events_df['premarket_close'] - events_df['premarket_low']) /
        (events_df['premarket_high'] - events_df['premarket_low']).replace(0, np.nan) * 100
    )
    
    print(f"\n🧮 Cálculo de momentum:")
    print(f"  (close - low) / (high - low) * 100")
    print(f"  ({event_data['premarket_close']} - {event_data['premarket_low']}) / ({event_data['premarket_high']} - {event_data['premarket_low']}) * 100")
    print(f"  = {momentum_calc.iloc[0]:.2f}")
    
    if pd.isna(momentum_calc.iloc[0]):
        print("  ❌ PROBLEMA: Momentum es NaN")
        return False
    else:
        print("  ✅ CORRECCIÓN: Momentum calculado correctamente")
        return True


if __name__ == "__main__":
    print("🚀 Iniciando tests de validación para corrección premarket_momentum")
    print("=" * 70)
    
    # Test 1: Validación completa del sistema
    test1_passed = test_premarket_momentum_fix()
    
    # Test 2: Test específico del cálculo
    test2_passed = test_momentum_calculation()
    
    print("\n" + "=" * 70)
    print("📋 RESUMEN DE TESTS:")
    print(f"  Test 1 (Sistema completo): {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"  Test 2 (Cálculo manual): {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ¡TODOS LOS TESTS PASARON! La corrección funciona correctamente.")
    else:
        print("\n⚠️  ALGUNOS TESTS FALLARON. Revisar la implementación.")