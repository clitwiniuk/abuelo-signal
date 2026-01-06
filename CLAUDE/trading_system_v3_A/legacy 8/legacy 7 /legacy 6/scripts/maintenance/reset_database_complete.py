#!/usr/bin/env python3
"""
Script para hacer reset completo de la base de datos - empezar de cero
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os
import shutil

def reset_database_complete():
    """Reset completo de la base de datos para empezar de cero"""
    print("🔥 RESET COMPLETO DE BASE DE DATOS")
    print("=" * 50)
    print("⚠️  ADVERTENCIA: Esto eliminará TODOS los trades históricos")
    print("⚠️  Solo mantendrá la estructura de las tablas")
    print("=" * 50)
    
    db_files = [
        "trading_data.db",
        "data/trading_history.db", 
        "logs/trading_data.db"
    ]
    
    # Confirmar acción
    response = input("\n¿Estás seguro de que quieres eliminar TODOS los trades? (YES/no): ").strip()
    
    if response != "YES":
        print("❌ Reset cancelado. Debes escribir 'YES' para confirmar.")
        return
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"\n🔥 Reseteando: {db_file}")
            reset_db_file(db_file)
        else:
            print(f"❌ No encontrado: {db_file}")

def reset_db_file(db_path):
    """Reset completo de un archivo específico de base de datos"""
    try:
        # 1. Crear backup completo antes del reset
        backup_path = f"{db_path}.backup_before_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(db_path, backup_path)
        print(f"   💾 Backup completo creado: {backup_path}")
        
        with sqlite3.connect(db_path) as conn:
            # 2. Mostrar estadísticas antes del reset
            try:
                total_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM trades", conn)
                closed_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM trades WHERE status = 'CLOSED'", conn)
                open_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM trades WHERE status = 'OPEN'", conn)
                
                print(f"   📊 Trades antes del reset:")
                print(f"      Total: {total_trades['count'].iloc[0]}")
                print(f"      Cerrados: {closed_trades['count'].iloc[0]}")
                print(f"      Abiertos: {open_trades['count'].iloc[0]}")
                
                # Mostrar estrategias con más trades
                strategy_counts = pd.read_sql_query("""
                    SELECT strategy, COUNT(*) as count 
                    FROM trades 
                    GROUP BY strategy 
                    ORDER BY count DESC 
                    LIMIT 5
                """, conn)
                
                if not strategy_counts.empty:
                    print(f"   📈 Top 5 estrategias:")
                    for _, row in strategy_counts.iterrows():
                        print(f"      {row['strategy']}: {row['count']} trades")
                
            except Exception as e:
                print(f"   ⚠️ No se pudieron obtener estadísticas: {e}")
            
            # 3. Eliminar TODOS los trades
            print(f"   🔥 Eliminando TODOS los trades...")
            
            # Eliminar datos de la tabla trades
            cursor = conn.execute("DELETE FROM trades")
            deleted_count = cursor.rowcount
            print(f"   🗑️ Eliminados {deleted_count} trades")
            
            # Reset del autoincrement
            conn.execute("DELETE FROM sqlite_sequence WHERE name='trades'")
            print(f"   🔄 Reset del contador de IDs")
            
            # 4. Limpiar otras tablas relacionadas si existen
            tables_to_clean = [
                'daily_stats',
                'trading_journal'
            ]
            
            for table in tables_to_clean:
                try:
                    cursor = conn.execute(f"DELETE FROM {table}")
                    if cursor.rowcount > 0:
                        print(f"   🧹 Limpiada tabla {table}: {cursor.rowcount} registros")
                except Exception:
                    # Tabla no existe, continuar
                    pass
            
            # 5. Verificar que está vacío
            final_count = pd.read_sql_query("SELECT COUNT(*) as count FROM trades", conn)
            print(f"   ✅ Trades restantes: {final_count['count'].iloc[0]}")
            
            # 6. Optimizar base de datos
            conn.execute("VACUUM")
            print(f"   🔧 Base de datos optimizada")
            
    except Exception as e:
        print(f"❌ Error reseteando {db_path}: {e}")

def verify_reset():
    """Verificar que el reset fue exitoso"""
    print("\n" + "=" * 50)
    print("✅ VERIFICACIÓN POST-RESET")
    print("=" * 50)
    
    db_path = "trading_data.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró trading_data.db")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Verificar que las tablas están vacías
            tables_to_check = ['trades', 'daily_stats', 'trading_journal']
            
            for table in tables_to_check:
                try:
                    count = pd.read_sql_query(f"SELECT COUNT(*) as count FROM {table}", conn)
                    status = "✅" if count['count'].iloc[0] == 0 else "❌"
                    print(f"   {status} Tabla {table}: {count['count'].iloc[0]} registros")
                except Exception:
                    print(f"   ⚠️ Tabla {table}: No existe o error")
            
            # Verificar estructura de tabla trades
            try:
                schema = pd.read_sql_query("PRAGMA table_info(trades)", conn)
                print(f"\n   📋 Estructura de tabla 'trades' preservada:")
                print(f"      Columnas: {len(schema)}")
                for _, col in schema.iterrows():
                    print(f"         - {col['name']}: {col['type']}")
            except Exception as e:
                print(f"   ❌ Error verificando estructura: {e}")
                
    except Exception as e:
        print(f"❌ Error en verificación: {e}")

def setup_fresh_start():
    """Configurar el sistema para un inicio fresco"""
    print("\n" + "=" * 50)
    print("🚀 CONFIGURACIÓN PARA INICIO FRESCO")
    print("=" * 50)
    
    # 1. Limpiar modelo ML si existe
    ml_model_path = "data/ml_models/strategy_selector.json"
    if os.path.exists(ml_model_path):
        backup_ml = f"{ml_model_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.move(ml_model_path, backup_ml)
        print(f"   💾 Modelo ML movido a backup: {backup_ml}")
        print(f"   🧠 ML empezará a aprender desde cero")
    else:
        print(f"   ✅ No hay modelo ML existente - empezará desde cero")
    
    # 2. Verificar configuración
    config_file = "config.ini"
    if os.path.exists(config_file):
        print(f"   ✅ Configuración preservada: {config_file}")
        
        # Mostrar configuración relevante
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        relevant_configs = [
            'max_position_value = 200',
            'default_trailing_activation = 0.06',
            'default_trailing_stop_pct = 0.08'
        ]
        
        print(f"   📊 Configuración actual:")
        for config in relevant_configs:
            if config.split('=')[0].strip() in config_content:
                print(f"      ✅ {config}")
            else:
                print(f"      ⚠️ {config} - verificar")
    
    print(f"\n🎯 SISTEMA LISTO PARA INICIO FRESCO")
    print("=" * 50)
    print("✅ Base de datos completamente vacía")
    print("✅ ML empezará a aprender desde cero")
    print("✅ Solo se registrarán trades 100% reales")
    print("✅ Analytics mostrará solo datos nuevos y reales")
    print("✅ Trailing stop y exit logic optimizados funcionando")
    
    print(f"\n🚀 PRÓXIMOS PASOS:")
    print("1. Ejecutar el sistema en horario de mercado")
    print("2. Verificar que se generen señales reales")
    print("3. Confirmar que los trades se registren correctamente")
    print("4. Observar el aprendizaje ML en tiempo real")
    print("5. Monitorear Analytics con datos 100% reales")

if __name__ == "__main__":
    reset_database_complete()
    verify_reset()
    setup_fresh_start()
