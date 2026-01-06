#!/usr/bin/env python3
"""
Script de Inicialización Mínima para market_data.db
Solo agrega event_id a intraday_bars y crea daily_ohlcv_history
"""

import sqlite3
import os
from datetime import datetime

def init_market_database_minimal(db_path: str = "market_data.db"):
    """
    Inicializar modificaciones mínimas en market_data.db existente
    
    Args:
        db_path: Ruta al archivo de base de datos
    """
    print(f"🚀 Inicializando modificaciones mínimas: {db_path}")
    
    # Crear backup
    if os.path.exists(db_path):
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"📦 Backup creado: {backup_path}")
    
    # Conectar a base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1.1 MODIFICACIÓN MÍNIMA: Agregar event_id a intraday_bars (SI NO EXISTE)
        cursor.execute("PRAGMA table_info(intraday_bars)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'event_id' not in columns:
            print("📊 Agregando event_id a tabla intraday_bars...")
            cursor.execute("ALTER TABLE intraday_bars ADD COLUMN event_id INTEGER")
        else:
            print("✅ event_id ya existe en intraday_bars")
        
        # 1.2 Nueva Tabla: daily_ohlcv_history (estructura mínima)
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='daily_ohlcv_history'
        """)
        
        if not cursor.fetchall():
            print("📈 Creando tabla daily_ohlcv_history...")
            cursor.execute("""
                CREATE TABLE daily_ohlcv_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,       -- Link al evento
                    symbol TEXT NOT NULL,
                    history_date DATE NOT NULL,      -- Fecha del dato histórico
                    days_before_event INTEGER,       -- 1, 2, 3, ... 60
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    catalyst_type TEXT,              -- Dato adicional que puede ayudar
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            print("✅ daily_ohlcv_history ya existe")
        
        # Crear índices (solo si no existen)
        print("⚡ Creando índices...")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_event_id ON daily_ohlcv_history(event_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON daily_ohlcv_history(symbol, history_date)")
        except Exception as e:
            print(f"   Índices ya existen: {e}")
        
        conn.commit()
        
        # Verificar estructura
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        # Verificar que intraday_bars tiene event_id
        cursor.execute("PRAGMA table_info(intraday_bars)")
        columns = cursor.fetchall()
        event_id_exists = any(col[1] == 'event_id' for col in columns)
        
        # Verificar daily_ohlcv_history
        cursor.execute("SELECT COUNT(*) FROM daily_ohlcv_history")
        history_count = cursor.fetchone()[0]
        
        print("\n✅ Base de datos verificada exitosamente!")
        print(f"📁 Archivo: {db_path}")
        print(f"📋 Tablas: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
            
        print(f"   - event_id en intraday_bars: {'✅' if event_id_exists else '❌'}")
        print(f"   - daily_ohlcv_history registros: {history_count}")
        
        if event_id_exists and history_count >= 0:
            print(f"\n🎉 ¡Perfecto! La base de datos está lista para el nuevo sistema expandido")
            print("   Puedes usar: python backtesting_system/data/polygon_data_downloader_minimal.py")
            
        return True
        
    except Exception as e:
        print(f"❌ Error modificando base de datos: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    # Crear modificaciones mínimas
    if init_market_database_minimal():
        print(f"\n🎉 ¡Listo! market_data.db con modificaciones mínimas")
        print("   - intraday_bars tiene event_id")
        print("   - Nueva tabla daily_ohlcv_history")
    else:
        print("❌ Falló la modificación de la base de datos")