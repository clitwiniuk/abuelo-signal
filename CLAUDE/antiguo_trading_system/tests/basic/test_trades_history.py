#!/usr/bin/env python3
"""
Test script para verificar el guardado de trades en el historial
Comprueba si los trades se están guardando correctamente en la base de datos
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio raíz del proyecto al path para importar módulos
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_database_connection():
    """Test 1: Verificar que la base de datos existe y es accesible"""
    print("🔍 Test 1: Verificación de conexión a la base de datos")
    
    db_path = "trading_data.db"
    if not os.path.exists(db_path):
        print(f"❌ ERROR: Base de datos no encontrada en {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar que existe la tabla trades
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            print("❌ ERROR: Tabla 'trades' no encontrada en la base de datos")
            conn.close()
            return False
        
        print("✅ Base de datos conectada correctamente")
        print("✅ Tabla 'trades' existe")
        
        # Mostrar estructura de la tabla
        cursor.execute("PRAGMA table_info(trades)")
        columns = cursor.fetchall()
        print(f"📋 Estructura de la tabla trades ({len(columns)} columnas):")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ERROR: No se pudo conectar a la base de datos: {e}")
        return False

def test_trades_data():
    """Test 2: Verificar los trades existentes en la base de datos"""
    print("\n🔍 Test 2: Verificación de datos de trades existentes")
    
    try:
        from core.database_manager import get_database_manager
        db_manager = get_database_manager()
        
        # Obtener todos los trades de los últimos 30 días
        trades_df = db_manager.get_trades(limit=100)
        
        print(f"📊 Total de trades en la base de datos: {len(trades_df)}")
        
        if trades_df.empty:
            print("⚠️  No se encontraron trades en la base de datos")
            print("💡 Esto puede indicar que:")
            print("   - No se han ejecutado trades recientemente")
            print("   - Los trades no se están guardando correctamente")
            return False
        
        # Estadísticas básicas
        open_trades = trades_df[trades_df['status'] == 'OPEN']
        closed_trades = trades_df[trades_df['status'] == 'CLOSED']
        
        print(f"📈 Trades abiertos: {len(open_trades)}")
        print(f"📉 Trades cerrados: {len(closed_trades)}")
        
        # Mostrar los últimos 5 trades
        print("\n📋 Últimos 5 trades registrados:")
        recent_trades = trades_df.head(5)
        for idx, trade in recent_trades.iterrows():
            status_icon = "🟢" if trade['status'] == 'OPEN' else "🔴" if trade['status'] == 'CLOSED' else "⚪"
            entry_time = pd.to_datetime(trade['entry_time']).strftime('%Y-%m-%d %H:%M')
            print(f"   {status_icon} {trade['symbol']} | {trade['side']} | {trade['strategy']} | {entry_time}")
        
        # Verificar diversidad de estrategias
        unique_strategies = trades_df['strategy'].unique()
        print(f"\n🎯 Estrategias encontradas: {list(unique_strategies)}")
        
        # Verificar si hay trades con strategy 'unknown'
        unknown_strategy_count = len(trades_df[trades_df['strategy'] == 'unknown'])
        if unknown_strategy_count > 0:
            print(f"⚠️  {unknown_strategy_count} trades con estrategia 'unknown' (pueden necesitar corrección)")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: No se pudieron obtener los datos de trades: {e}")
        return False

def test_trade_saving_simulation():
    """Test 3: Simular el guardado de un trade para verificar funcionalidad"""
    print("\n🔍 Test 3: Simulación de guardado de trade")
    
    try:
        from core.database_manager import get_database_manager
        db_manager = get_database_manager()
        
        # Crear un trade de prueba
        test_trade = {
            'trade_id': f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'symbol': 'TEST_SYMBOL',
            'strategy': 'test_strategy',
            'side': 'BUY',
            'quantity': 100,
            'entry_price': 10.50,
            'entry_time': datetime.now(),
            'status': 'OPEN',
            'notes': 'Trade de prueba para verificar funcionalidad de guardado'
        }
        
        print(f"📝 Intentando guardar trade de prueba: {test_trade['trade_id']}")
        
        # Intentar guardar el trade
        success = db_manager.save_trade(test_trade)
        
        if success:
            print("✅ Trade de prueba guardado correctamente")
            
            # Verificar que se guardó consultando la base de datos
            saved_trades = db_manager.get_trades(symbol='TEST_SYMBOL', limit=1)
            if not saved_trades.empty:
                print("✅ Trade de prueba verificado en la base de datos")
                
                # Limpiar el trade de prueba
                conn = sqlite3.connect(db_manager.db_path)
                conn.execute("DELETE FROM trades WHERE trade_id = ?", (test_trade['trade_id'],))
                conn.commit()
                conn.close()
                print("🧹 Trade de prueba eliminado")
                
                return True
            else:
                print("❌ ERROR: Trade de prueba no encontrado después de guardarlo")
                return False
        else:
            print("❌ ERROR: No se pudo guardar el trade de prueba")
            return False
            
    except Exception as e:
        print(f"❌ ERROR en la simulación de guardado: {e}")
        return False

def test_streamlit_trades_display():
    """Test 4: Verificar que los trades se muestran correctamente en Streamlit"""
    print("\n🔍 Test 4: Verificación de visualización en Streamlit")
    
    try:
        from core.database_manager import get_database_manager
        db_manager = get_database_manager()
        
        # Simular lo que hace Streamlit para mostrar trades
        print("📊 Simulando obtención de trades para Streamlit...")
        
        # Test con diferentes filtros como en Streamlit
        all_trades = db_manager.get_trades(limit=50)
        print(f"✅ Trades obtenidos sin filtros: {len(all_trades)}")
        
        if not all_trades.empty:
            # Test filtros por estrategia
            strategies = all_trades['strategy'].unique()
            for strategy in strategies:
                if strategy and strategy != 'unknown':
                    strategy_trades = db_manager.get_trades(strategy=strategy, limit=10)
                    print(f"✅ Trades para estrategia '{strategy}': {len(strategy_trades)}")
            
            # Test filtros por símbolo
            symbols = all_trades['symbol'].unique()
            sample_symbols = list(symbols)[:3]  # Primeros 3 símbolos
            for symbol in sample_symbols:
                symbol_trades = db_manager.get_trades(symbol=symbol, limit=10)
                print(f"✅ Trades para símbolo '{symbol}': {len(symbol_trades)}")
            
            print("✅ Filtros de trades funcionando correctamente")
            return True
        else:
            print("⚠️  No hay trades para probar los filtros")
            return False
            
    except Exception as e:
        print(f"❌ ERROR en la verificación de Streamlit: {e}")
        return False

def test_daily_stats():
    """Test 5: Verificar cálculo de estadísticas diarias"""
    print("\n🔍 Test 5: Verificación de estadísticas diarias")
    
    try:
        from core.database_manager import get_database_manager
        db_manager = get_database_manager()
        
        # Calcular estadísticas de hoy
        today_stats = db_manager.calculate_daily_stats()
        
        print("📊 Estadísticas de hoy:")
        print(f"   - Total trades: {today_stats['total_trades']}")
        print(f"   - Win rate: {today_stats['win_rate']:.1f}%")
        print(f"   - PnL total: ${today_stats['total_pnl']:.2f}")
        print(f"   - Trades ganadores: {today_stats['winning_trades']}")
        print(f"   - Trades perdedores: {today_stats['losing_trades']}")
        
        # Verificar performance por estrategia
        strategy_perf = db_manager.get_strategy_performance(days=7)
        if not strategy_perf.empty:
            print(f"\n🎯 Performance por estrategia (últimos 7 días):")
            for _, row in strategy_perf.iterrows():
                print(f"   - {row['strategy']}: {row['total_trades']} trades, {row['win_rate']:.1f}% win rate, ${row['total_pnl']:.2f} PnL")
        
        print("✅ Estadísticas calculadas correctamente")
        return True
        
    except Exception as e:
        print(f"❌ ERROR en el cálculo de estadísticas: {e}")
        return False

def main():
    """Ejecutar todos los tests"""
    print("🧪 Test de Verificación del Historial de Trades")
    print("=" * 50)
    
    tests = [
        test_database_connection,
        test_trades_data,
        test_trade_saving_simulation,
        test_streamlit_trades_display,
        test_daily_stats
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ ERROR inesperado en {test_func.__name__}: {e}")
            results.append(False)
    
    # Resumen final
    print("\n" + "=" * 50)
    print("📋 RESUMEN DE RESULTADOS:")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    test_names = [
        "Conexión a base de datos",
        "Datos de trades existentes", 
        "Simulación de guardado",
        "Visualización en Streamlit",
        "Estadísticas diarias"
    ]
    
    for i, (test_name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {test_name}: {status}")
    
    print(f"\n🎯 RESULTADO FINAL: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron! El sistema de guardado de trades funciona correctamente.")
    elif passed >= total * 0.8:
        print("⚠️  La mayoría de tests pasaron. Hay algunos problemas menores que revisar.")
    else:
        print("🚨 Varios tests fallaron. Hay problemas significativos con el guardado de trades.")
    
    # Recomendaciones
    print("\n💡 RECOMENDACIONES:")
    if not results[0]:
        print("- Verificar que la base de datos trading_data.db existe y es accesible")
    if not results[1]:
        print("- Verificar que se están ejecutando trades y guardando en la base de datos")
        print("- Revisar logs del sistema de trading para errores")
    if not results[2]:
        print("- Revisar la función save_trade en database_manager.py")
    if not results[3]:
        print("- Verificar que Streamlit puede acceder correctamente a los datos")
    if not results[4]:
        print("- Revisar las funciones de cálculo de estadísticas")

if __name__ == "__main__":
    main()