#!/usr/bin/env python3
"""
Análisis de Requerimientos de Datos para ML - Qué datos necesita cada algoritmo
Ubicación: scripts/analysis/ (estructura organizada)
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def analyze_ml_data_requirements():
    """Analiza qué datos necesita cada algoritmo ML"""
    print("📊 ANÁLISIS DE REQUERIMIENTOS DE DATOS PARA ML")
    print("=" * 60)
    print("📍 Desde: scripts/analysis/analyze_ml_data_requirements.py")
    print("=" * 60)
    
    print("\n1️⃣ DATOS ACTUALES EN database_quality.db")
    analyze_current_data()
    
    print("\n2️⃣ REQUERIMIENTOS POR ALGORITMO ML")
    analyze_ml_requirements()
    
    print("\n3️⃣ DATOS FALTANTES Y RECOMENDACIONES")
    recommend_data_improvements()

def analyze_current_data():
    """Analizar datos actuales en database_quality.db"""
    db_path = "database_quality.db"
    
    if os.path.exists(db_path):
        print("✅ database_quality.db encontrada")
        
        conn = sqlite3.connect(db_path)
        
        # Obtener tablas
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
        print(f"📊 Tablas disponibles: {len(tables)} tablas")
        
        for table in tables['name']:
            try:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                count_result = pd.read_sql_query(count_query, conn)
                count = count_result['count'].iloc[0]
                
                print(f"   📋 {table}: {count:,} registros")
                
                # Para tablas principales, mostrar estructura
                if table in ['ScannerEvents', 'ScannerData', 'OHLCData', 'advanced_trading_results']:
                    columns_query = f"PRAGMA table_info({table})"
                    columns_result = pd.read_sql_query(columns_query, conn)
                    columns = columns_result['name'].tolist()
                    print(f"      Columnas: {columns[:8]}..." if len(columns) > 8 else f"      Columnas: {columns}")
                    
            except Exception as e:
                print(f"   ❌ Error en {table}: {e}")
        
        # Análisis de calidad de datos
        print(f"\n🔍 ANÁLISIS DE CALIDAD DE DATOS:")
        try:
            # Check ScannerEvents con datos completos
            quality_query = """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN se.ticker IS NOT NULL AND 
                              sd.percent_var IS NOT NULL AND 
                              sd.ratio_vol IS NOT NULL 
                              THEN 1 END) as complete_records
            FROM ScannerEvents se
            LEFT JOIN ScannerData sd ON se.id_event = sd.id_event
            """
            quality_result = pd.read_sql_query(quality_query, conn)
            
            total = quality_result['total'].iloc[0]
            complete = quality_result['complete_records'].iloc[0]
            quality_pct = (complete / max(total, 1)) * 100
            
            print(f"   📊 Registros totales: {total:,}")
            print(f"   ✅ Registros completos: {complete:,} ({quality_pct:.1f}%)")
            
        except Exception as e:
            print(f"   ❌ Error análisis calidad: {e}")
        
        conn.close()
    else:
        print("❌ database_quality.db no encontrada")

def analyze_ml_requirements():
    """Analizar requerimientos específicos de cada ML"""
    
    print("🧠 ML STRATEGY SELECTOR (Contextual Bandit):")
    print("   📊 Datos necesarios:")
    print("      - Eventos de scanner con ticker, timestamp")
    print("      - Métricas: percent_var, ratio_vol, precio, sector") 
    print("      - Resultado: ¿qué estrategia fue exitosa?")
    print("      - Context: hora, día semana, market cap, volumen")
    print("   🎯 Mínimo recomendado: 1,000+ eventos con outcome conocido")
    print("   📈 Para mejor performance: 5,000+ eventos")
    
    print("\n🔊 ML VOLUME ENGINE:")
    print("   📊 Datos necesarios:")
    print("      - ScannerEvents + ScannerData (market context)")
    print("      - OHLC data (price action, volumen real)")
    print("      - Sector information") 
    print("      - Market conditions (VIX proxy, stress indicators)")
    print("      - TARGET: volumen requerido óptimo por estrategia")
    print("   🎯 Features específicos:")
    print("      - time_of_day, day_of_week")
    print("      - log_market_cap, log_avg_volume, log_float_shares")  
    print("      - sector_encoded, recent_performance")
    print("      - market_stress, volume_trend, log_price")
    print("   📈 Mínimo: 500+ eventos por estrategia")
    
    print("\n🚪 ML EXIT ENGINE:")
    print("   📊 Datos necesarios:")
    print("      - Trade entries (precio entrada, tiempo)")
    print("      - Trade exits (precio salida, tiempo, PnL)")
    print("      - Market conditions durante el trade")
    print("      - Volume profile, price action")
    print("   🎯 Features:")
    print("      - entry_price, current_price, pnl_pct")
    print("      - time_held, volume_ratio")
    print("      - market conditions, volatility")
    print("   📈 Mínimo: 200+ trades completados con buenos outcomes")
    
    print("\n🧠 CONTINUOUS LEARNING ENGINE:")
    print("   📊 Datos necesarios:")
    print("      - Feedback de trades reales ejecutados")
    print("      - Volume requirements usados vs actuales")
    print("      - Success/failure de cada trade")
    print("      - Market context cuando se ejecutó")
    print("   🎯 Input: TradeResult objects con:")
    print("      - strategy, volume_requirement_used, actual_volume_ratio")
    print("      - pnl, success, duration_minutes, market_context")
    print("   📈 Mínimo: 50+ trades por estrategia para aprendizaje")

def recommend_data_improvements():
    """Recomendar mejoras en los datos"""
    print("💡 RECOMENDACIONES PARA MEJORAR database_quality.db")
    print("-" * 60)
    
    print("\n🎯 DATOS CRÍTICOS FALTANTES:")
    
    print("\n   1️⃣ OUTCOMES DE ESTRATEGIAS:")
    print("      ❌ Falta: ¿Qué estrategia fue exitosa en cada evento?")
    print("      💡 Agregar: tabla 'strategy_outcomes'")
    print("         - id_event, strategy_name, success (0/1)")
    print("         - pnl_if_executed, duration_minutes")
    print("         - exit_reason (profit_target, stop_loss, time_exit)")
    
    print("\n   2️⃣ TRADE SIMULATION RESULTS:")
    print("      ❌ Falta: Resultados de trades simulados")  
    print("      💡 Agregar: tabla 'simulated_trades'")
    print("         - id_event, strategy, entry_price, exit_price")
    print("         - pnl_pct, success, hold_time_minutes")
    print("         - volume_requirement_used, actual_volume")
    
    print("\n   3️⃣ MARKET CONTEXT ENRICHMENT:")
    print("      ❌ Falta: Datos de contexto de mercado")
    print("      💡 Agregar columnas a ScannerData:")
    print("         - market_stress (VIX proxy)")
    print("         - sector_performance_5d")
    print("         - market_cap (calculated)")
    print("         - float_shares (from screener)")
    
    print("\n   4️⃣ VOLUME ANALYSIS:")
    print("      ❌ Falta: Análisis detallado de volumen")
    print("      💡 Agregar: tabla 'volume_analysis'")
    print("         - id_event, volume_trend_5d")
    print("         - volume_vs_sma20, volume_vs_sma50") 
    print("         - volume_breakout_strength")
    
    print("\n🛠️ PASOS PARA IMPLEMENTAR:")
    
    print("\n   📋 PASO 1: Crear tablas adicionales")
    print("      - Ejecutar SQL para crear nuevas tablas")
    print("      - Establecer relaciones con id_event")
    
    print("\n   📋 PASO 2: Enriquecer eventos existentes") 
    print("      - Calcular outcomes simulados para eventos históricos")
    print("      - Usar backtesting para generar strategy_outcomes")
    print("      - Calcular market_context para cada evento")
    
    print("\n   📋 PASO 3: Pipeline de datos continuo")
    print("      - Modificar scanner para capturar más context")
    print("      - Agregar post-procesamiento para calcular outcomes")
    print("      - Implementar feedback loop de trading real")
    
    print("\n💾 SCRIPTS RECOMENDADOS PARA CREAR:")
    print("   📝 scripts/maintenance/enrich_quality_database.py")
    print("   📝 scripts/maintenance/calculate_strategy_outcomes.py")
    print("   📝 scripts/maintenance/add_market_context.py")
    
    print("\n🎯 RESULTADO ESPERADO:")
    print("   Con estos datos adicionales:")
    print("   ✅ ML Strategy Selector: 90%+ accuracy")
    print("   ✅ ML Volume Engine: R² > 0.6 para todas las estrategias") 
    print("   ✅ ML Exit Engine: 80%+ precision en exit timing")
    print("   ✅ Continuous Learning: Mejora continua >5% mensual")

def generate_sql_schema():
    """Generar schema SQL para las tablas adicionales"""
    print("\n📝 SCHEMA SQL PARA NUEVAS TABLAS:")
    print("=" * 40)
    
    sql_schema = """
-- Tabla para outcomes de estrategias
CREATE TABLE IF NOT EXISTS strategy_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_event INTEGER,
    strategy_name TEXT NOT NULL,
    success INTEGER NOT NULL, -- 0 or 1
    pnl_pct REAL,
    duration_minutes INTEGER,
    exit_reason TEXT, -- 'profit', 'stop', 'time', 'manual'
    volume_requirement_used REAL,
    timestamp_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_event) REFERENCES ScannerEvents(id_event)
);

-- Tabla para análisis de volumen
CREATE TABLE IF NOT EXISTS volume_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_event INTEGER,
    volume_trend_5d REAL,
    volume_vs_sma20 REAL,
    volume_vs_sma50 REAL,
    volume_breakout_strength REAL,
    avg_volume_20d INTEGER,
    timestamp_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_event) REFERENCES ScannerEvents(id_event)
);

-- Tabla para contexto de mercado enriquecido
CREATE TABLE IF NOT EXISTS market_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_event INTEGER,
    market_stress REAL, -- VIX proxy
    sector_performance_5d REAL,
    market_cap REAL,
    float_shares INTEGER,
    price_vs_sma20 REAL,
    price_vs_sma50 REAL,
    timestamp_calculated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_event) REFERENCES ScannerEvents(id_event)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_strategy_outcomes_event ON strategy_outcomes(id_event);
CREATE INDEX IF NOT EXISTS idx_volume_analysis_event ON volume_analysis(id_event);
CREATE INDEX IF NOT EXISTS idx_market_context_event ON market_context(id_event);
"""
    
    print(sql_schema)
    return sql_schema

def main():
    """Función principal"""
    print("📊 Iniciando análisis de requerimientos de datos ML")
    
    analyze_ml_data_requirements()
    
    generate_sql_schema()
    
    print("\n" + "=" * 60)
    print("✅ Análisis completado")
    print("💡 Revisar recomendaciones para mejorar database_quality.db")

if __name__ == "__main__":
    main()