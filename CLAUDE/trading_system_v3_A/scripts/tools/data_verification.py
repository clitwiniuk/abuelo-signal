#!/usr/bin/env python3
"""
Script para verificar RÁPIDAMENTE si los datos son el problema
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def verify_data_quick():
    """Verificación rápida de datos"""
    data_path = Path("data")
    csv_files = list(data_path.glob("*.csv"))
    
    if not csv_files:
        print("❌ No CSV files found")
        return False
    
    print(f"📁 Found {len(csv_files)} CSV files")
    
    # Test first 3 files
    for i, file in enumerate(csv_files[:3]):
        print(f"\n📊 Testing file {i+1}: {file.name}")
        
        try:
            # Load and check basic structure
            df = pd.read_csv(file)
            print(f"   Rows: {len(df)}")
            print(f"   Columns: {list(df.columns)}")
            
            # Check required columns
            required = ['open', 'high', 'low', 'close', 'volume']
            missing = [col for col in required if col.lower() not in df.columns.str.lower()]
            
            if missing:
                print(f"   ❌ Missing columns: {missing}")
                continue
            
            # Normalize columns
            df.columns = df.columns.str.lower()
            
            # Check date column
            date_cols = ['timestamp', 'datetime', 'date', 'time']
            date_col = None
            for col in date_cols:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                print(f"   📅 Date range: {df[date_col].min()} to {df[date_col].max()}")
            else:
                print(f"   ⚠️  No date column found in {date_cols}")
            
            # Check price range
            print(f"   💰 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
            print(f"   📊 Avg volume: {df['volume'].mean():,.0f}")
            
            # Look for gaps manually
            print(f"   🔍 Checking for gaps...")
            gap_count = 0
            for j in range(1, min(50, len(df))):
                try:
                    prev_close = df.iloc[j-1]['close']
                    current_open = df.iloc[j]['open']
                    gap_pct = abs((current_open - prev_close) / prev_close * 100)
                    
                    if gap_pct > 2.0:  # Gaps > 2%
                        gap_count += 1
                        if gap_count <= 3:  # Show first 3
                            print(f"      Gap {gap_count}: {gap_pct:.1f}% at row {j}")
                except:
                    continue
            
            if gap_count == 0:
                print(f"   ⚠️  No significant gaps found in first 50 bars")
            else:
                print(f"   ✅ Found {gap_count} potential gaps")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return True

def manual_gap_test():
    """Test manual de detección de gaps"""
    print(f"\n🧪 MANUAL GAP DETECTION TEST")
    print("="*50)
    
    # Simular datos con gap obvio
    from core.interfaces import MarketData
    from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
    
    # Crear estrategia
    params = {
        'auto_detect_gaps': True,
        'gap_percent_threshold': 0.5,
        'debug_verbose': True
    }
    
    strategy = OptimizedGapGoStrategy(params)
    
    # Día 1 - Close
    bar1 = MarketData(
        symbol="TEST",
        timestamp=datetime(2025, 4, 1, 15, 59),  # Final del día
        open=10.0, high=10.1, low=9.9, close=10.0, volume=100000
    )
    
    # Día 2 - Open con gap
    bar2 = MarketData(
        symbol="TEST",
        timestamp=datetime(2025, 4, 2, 9, 30),  # Apertura siguiente día
        open=12.0, high=12.5, low=11.8, close=12.1, volume=200000  # 20% gap up
    )
    
    print("Testing gap detection with simulated data...")
    print(f"Day 1: Close = ${bar1.close}")
    print(f"Day 2: Open = ${bar2.open}")
    print(f"Expected gap = {(bar2.open - bar1.close) / bar1.close * 100:.1f}%")
    
    # Test detección
    try:
        # Simular procesamiento
        strategy._auto_detect_gap("TEST", bar1)  # Guardar prev_close
        print(f"✅ Saved prev_close: ${bar1.close}")
        
        strategy._auto_detect_gap("TEST", bar2)  # Detectar gap
        
        if "TEST" in strategy.scanner_gaps:
            gap_data = strategy.scanner_gaps["TEST"]
            print(f"✅ Gap detected: {gap_data['gap_percent']:.1f}%")
            print(f"✅ Direction: {gap_data['direction']}")
            return True
        else:
            print(f"❌ No gap detected in strategy.scanner_gaps")
            print(f"Available gaps: {list(strategy.scanner_gaps.keys())}")
            return False
            
    except Exception as e:
        print(f"❌ Error in gap detection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔍 VERIFICACIÓN RÁPIDA DE DATOS Y GAP DETECTION")
    print("=" * 60)
    
    # Test 1: Verificar archivos de datos
    print("\n1. VERIFICANDO ARCHIVOS DE DATOS...")
    data_ok = verify_data_quick()
    
    # Test 2: Test manual de gap detection
    print("\n2. TESTING GAP DETECTION MANUAL...")
    gap_ok = manual_gap_test()
    
    # Resultado final
    print(f"\n{'='*60}")
    print("📋 RESUMEN DE VERIFICACIÓN:")
    print(f"   Datos OK: {'✅' if data_ok else '❌'}")
    print(f"   Gap Detection OK: {'✅' if gap_ok else '❌'}")
    
    if data_ok and gap_ok:
        print("\n✅ DATOS Y GAP DETECTION FUNCIONAN")
        print("🔧 El problema está en la configuración del backtest")
    elif data_ok and not gap_ok:
        print("\n⚠️  DATOS OK, PERO GAP DETECTION FALLA")
        print("🔧 Necesitas corregir _auto_detect_gap en OptimizedGapGoStrategy")
    elif not data_ok:
        print("\n❌ PROBLEMA CON LOS DATOS")
        print("🔧 Verifica formato y contenido de archivos CSV")
    
    print(f"\n💡 SIGUIENTE PASO:")
    if not gap_ok:
        print("   1. Aplica el fix de _auto_detect_gap_FIXED")
        print("   2. Usa parámetros ultra-permisivos")
        print("   3. Test con 1 solo símbolo primero")
    else:
        print("   1. Aplica adjust_strategy_params_for_debug_FIXED")
        print("   2. Usa DebuggingDiagnosticStrategy")
        print("   3. Reduce a 2-3 símbolos para testing")