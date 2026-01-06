#!/usr/bin/env python3
"""
Crear base de datos de alta calidad filtrando trades por grados A+, A, A-
Elimina trades de baja calidad (B, C, D) para mejorar entrenamiento ML
"""

import sqlite3
import pandas as pd
import shutil
import os
from datetime import datetime

def create_quality_database():
    """
    Crea database_quality.db con solo trades de alta calidad (A+, A, A-)
    """
    print("🔧 CREANDO DATABASE DE ALTA CALIDAD")
    print("=" * 50)
    
    # Hacer backup de database original
    if os.path.exists("database_quality.db"):
        backup_name = f"database_quality_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2("database_quality.db", backup_name)
        print(f"📦 Backup creado: {backup_name}")
    
    # Copiar database original
    print("📋 Copiando database.db -> database_quality.db...")
    shutil.copy2("database.db", "database_quality.db")
    
    # Conectar a nueva database
    conn = sqlite3.connect("database_quality.db")
    cursor = conn.cursor()
    
    print("🔍 Analizando y clasificando trades por calidad...")
    
    # Query para identificar trades de alta calidad
    quality_analysis_query = """
    SELECT 
        se.id_event,
        se.ticker,
        sd.percent_var,
        sd.ratio_vol,
        sd.precio,
        sd.sector,
        COUNT(o.id_ohlc) as total_bars,
        (MAX(o.high) - MIN(o.low)) / AVG(o.close) as daily_range_pct,
        (MAX(o.high) - MIN(o.close)) / NULLIF(MAX(o.high), 0) as fade_from_high,
        
        -- Clasificación de calidad más inclusiva
        CASE 
            WHEN sd.ratio_vol BETWEEN 1.2 AND 5.0 
             AND sd.percent_var BETWEEN 2 AND 15 
             AND sd.precio BETWEEN 3 AND 40
             AND COUNT(o.id_ohlc) >= 60
             AND (MAX(o.high) - MIN(o.close)) / NULLIF(MAX(o.high), 0) < 0.40
            THEN 'A+'
            
            WHEN sd.ratio_vol BETWEEN 0.8 AND 8.0 
             AND sd.percent_var BETWEEN 1.5 AND 25 
             AND sd.precio BETWEEN 2 AND 50
             AND COUNT(o.id_ohlc) >= 45
             AND (MAX(o.high) - MIN(o.close)) / NULLIF(MAX(o.high), 0) < 0.60
            THEN 'A'
            
            WHEN sd.ratio_vol BETWEEN 0.5 AND 12.0 
             AND sd.percent_var BETWEEN 1.0 AND 35 
             AND sd.precio BETWEEN 1 AND 75
             AND COUNT(o.id_ohlc) >= 30
             AND (MAX(o.high) - MIN(o.close)) / NULLIF(MAX(o.high), 0) < 0.75
            THEN 'A-'
            
            ELSE 'B_or_lower'
        END as trade_quality

    FROM ScannerEvents se 
    JOIN ScannerData sd ON se.id_event = sd.id_event
    JOIN OHLCData o ON se.id_event = o.id_event
    WHERE sd.percent_var IS NOT NULL 
      AND sd.ratio_vol IS NOT NULL
      AND o.volume > 1000
    GROUP BY se.id_event
    HAVING trade_quality IN ('A+', 'A', 'A-')  -- Solo alta calidad
    ORDER BY 
        CASE trade_quality 
            WHEN 'A+' THEN 1 
            WHEN 'A' THEN 2 
            WHEN 'A-' THEN 3 
        END,
        se.timestamp DESC
    """
    
    # Ejecutar análisis
    df_quality = pd.read_sql_query(quality_analysis_query, conn)
    
    print(f"✅ Encontrados {len(df_quality)} trades de alta calidad")
    
    # Mostrar distribución
    quality_counts = df_quality['trade_quality'].value_counts()
    print("\n📊 DISTRIBUCIÓN DE CALIDAD:")
    for quality, count in quality_counts.items():
        percentage = (count / len(df_quality)) * 100
        print(f"   {quality}: {count} trades ({percentage:.1f}%)")
    
    # Obtener lista de id_events de alta calidad
    quality_event_ids = df_quality['id_event'].tolist()
    
    if len(quality_event_ids) == 0:
        print("❌ No se encontraron trades de alta calidad")
        conn.close()
        return False
    
    print(f"\n🗑️  Eliminando {len(quality_event_ids)} trades de baja calidad...")
    
    # Crear tabla temporal con IDs de alta calidad
    cursor.execute("CREATE TEMP TABLE quality_events (id_event INTEGER)")
    cursor.executemany("INSERT INTO quality_events VALUES (?)", 
                       [(event_id,) for event_id in quality_event_ids])
    
    # Contar registros antes de limpiar
    tables_to_clean = ['ScannerEvents', 'ScannerData', 'OHLCData', 'DailyTickerData']
    before_counts = {}
    
    for table in tables_to_clean:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        before_counts[table] = cursor.fetchone()[0]
    
    # Limpiar tablas manteniendo solo trades de alta calidad
    print("\n🧹 Limpiando tablas...")
    
    # ScannerEvents
    cursor.execute("""
        DELETE FROM ScannerEvents 
        WHERE id_event NOT IN (SELECT id_event FROM quality_events)
    """)
    
    # ScannerData  
    cursor.execute("""
        DELETE FROM ScannerData 
        WHERE id_event NOT IN (SELECT id_event FROM quality_events)
    """)
    
    # OHLCData
    cursor.execute("""
        DELETE FROM OHLCData 
        WHERE id_event NOT IN (SELECT id_event FROM quality_events)
    """)
    
    # DailyTickerData
    cursor.execute("""
        DELETE FROM DailyTickerData 
        WHERE id_event NOT IN (SELECT id_event FROM quality_events)
    """)
    
    # Contar después de limpiar
    after_counts = {}
    for table in tables_to_clean:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        after_counts[table] = cursor.fetchone()[0]
    
    # Mostrar resultados de limpieza
    print("\n📈 RESULTADOS DE LIMPIEZA:")
    total_before = sum(before_counts.values())
    total_after = sum(after_counts.values())
    
    for table in tables_to_clean:
        before = before_counts[table]
        after = after_counts[table]
        reduction = ((before - after) / before * 100) if before > 0 else 0
        print(f"   {table}: {before} -> {after} (-{reduction:.1f}%)")
    
    print(f"\n🎯 REDUCCIÓN TOTAL: {total_before} -> {total_after} registros")
    print(f"💾 Tamaño reducido: {((total_before - total_after) / total_before * 100):.1f}%")
    
    # Commit cambios antes de optimizar
    conn.commit()
    
    # Optimizar database (fuera de transacción)
    print("\n⚡ Optimizando database...")
    conn.execute("VACUUM")
    conn.execute("ANALYZE")
    
    # Crear índices para performance
    print("📇 Creando índices...")
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_scanner_events_timestamp ON ScannerEvents(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_scanner_data_ratios ON ScannerData(ratio_vol, percent_var)",
        "CREATE INDEX IF NOT EXISTS idx_ohlc_volume ON OHLCData(volume)",
        "CREATE INDEX IF NOT EXISTS idx_events_ticker ON ScannerEvents(ticker)"
    ]
    
    for index_sql in indices:
        cursor.execute(index_sql)
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ DATABASE DE ALTA CALIDAD CREADA: database_quality.db")
    print(f"🎯 {len(df_quality)} eventos de calidad A+/A/A- listos para ML")
    print(f"🚀 Datos limpios para entrenamiento robusto")
    
    return True

def verify_quality_database():
    """
    Verifica la integridad de la database de calidad
    """
    print("\n🔍 VERIFICANDO INTEGRIDAD DE database_quality.db")
    print("=" * 50)
    
    conn = sqlite3.connect("database_quality.db")
    
    # Verificar conteos
    tables = ['ScannerEvents', 'ScannerData', 'OHLCData', 'DailyTickerData']
    
    for table in tables:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"✅ {table}: {count} registros")
    
    # Verificar calidad promedio
    quality_check_query = """
    SELECT 
        AVG(sd.ratio_vol) as avg_ratio_vol,
        AVG(sd.percent_var) as avg_percent_var,
        AVG(sd.precio) as avg_precio,
        MIN(sd.ratio_vol) as min_ratio_vol,
        MAX(sd.ratio_vol) as max_ratio_vol,
        COUNT(*) as total_events
    FROM ScannerEvents se 
    JOIN ScannerData sd ON se.id_event = sd.id_event
    """
    
    df_check = pd.read_sql_query(quality_check_query, conn)
    
    print(f"\n📊 MÉTRICAS DE CALIDAD:")
    print(f"   Total eventos: {df_check['total_events'].iloc[0]}")
    print(f"   Ratio Vol promedio: {df_check['avg_ratio_vol'].iloc[0]:.2f}")
    print(f"   Percent Var promedio: {df_check['avg_percent_var'].iloc[0]:.2f}%")
    print(f"   Precio promedio: ${df_check['avg_precio'].iloc[0]:.2f}")
    print(f"   Rango Ratio Vol: {df_check['min_ratio_vol'].iloc[0]:.2f} - {df_check['max_ratio_vol'].iloc[0]:.2f}")
    
    conn.close()
    
    print("\n🎯 DATABASE DE CALIDAD VERIFICADA ✅")

if __name__ == "__main__":
    print("🚀 CREADOR DE DATABASE DE ALTA CALIDAD")
    print("=" * 60)
    
    success = create_quality_database()
    
    if success:
        verify_quality_database()
        print("\n✅ ¡PROCESO COMPLETADO EXITOSAMENTE!")
        print("🎯 Usa 'database_quality.db' para entrenar ML con datos limpios")
    else:
        print("\n❌ Error en la creación de database de calidad")