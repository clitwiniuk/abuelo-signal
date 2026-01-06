#!/usr/bin/env python3
"""
Script para analizar los datos reales en la base de datos y compararlos con Analytics
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

def analyze_database():
    """Analizar datos en la base de datos de trading"""
    print("🔍 ANÁLISIS DE BASE DE DATOS")
    print("=" * 50)
    
    # Buscar archivos de base de datos
    db_files = [
        "trading_data.db",
        "data/trading_history.db", 
        "logs/trading_data.db"
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"\n📁 Analizando: {db_file}")
            analyze_db_file(db_file)
        else:
            print(f"❌ No encontrado: {db_file}")

def analyze_db_file(db_path):
    """Analizar un archivo específico de base de datos"""
    try:
        with sqlite3.connect(db_path) as conn:
            # 1. Ver qué tablas existen
            tables = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table'
            """, conn)
            
            print(f"📊 Tablas encontradas: {list(tables['name'])}")
            
            # 2. Si existe tabla 'trades', analizarla
            if 'trades' in tables['name'].values:
                print("\n🔍 ANÁLISIS DE TABLA 'trades':")
                
                # Contar total de trades
                total_trades = pd.read_sql_query("SELECT COUNT(*) as total FROM trades", conn)
                print(f"   Total trades en DB: {total_trades['total'].iloc[0]}")
                
                # Trades por estado
                status_counts = pd.read_sql_query("""
                    SELECT status, COUNT(*) as count 
                    FROM trades 
                    GROUP BY status
                """, conn)
                print("   Trades por estado:")
                for _, row in status_counts.iterrows():
                    print(f"     {row['status']}: {row['count']}")
                
                # Trades de hoy
                today_trades = pd.read_sql_query("""
                    SELECT COUNT(*) as today_count 
                    FROM trades 
                    WHERE date(entry_time) = date('now')
                """, conn)
                print(f"   Trades de HOY: {today_trades['today_count'].iloc[0]}")
                
                # Últimos 7 días
                week_trades = pd.read_sql_query("""
                    SELECT COUNT(*) as week_count 
                    FROM trades 
                    WHERE date(entry_time) >= date('now', '-7 days')
                """, conn)
                print(f"   Trades últimos 7 días: {week_trades['week_count'].iloc[0]}")
                
                # Performance por estrategia (como en Analytics)
                strategy_perf = pd.read_sql_query("""
                    SELECT 
                        strategy,
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        ROUND(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END) * 100, 2) as win_rate,
                        ROUND(SUM(pnl), 2) as total_pnl,
                        ROUND(AVG(pnl), 2) as avg_pnl,
                        ROUND(MAX(pnl), 2) as best_trade,
                        ROUND(MIN(pnl), 2) as worst_trade
                    FROM trades
                    WHERE date(entry_time) >= date('now', '-1 days')
                        AND status = 'CLOSED'
                    GROUP BY strategy
                    ORDER BY total_pnl DESC
                """, conn)
                
                if not strategy_perf.empty:
                    print("\n📊 PERFORMANCE POR ESTRATEGIA (últimas 24h):")
                    print(strategy_perf.to_string(index=False))
                else:
                    print("\n⚠️ No hay trades cerrados en las últimas 24 horas")
                
                # Fechas de trades más recientes
                recent_trades = pd.read_sql_query("""
                    SELECT symbol, strategy, entry_time, exit_time, status, pnl
                    FROM trades 
                    ORDER BY entry_time DESC 
                    LIMIT 10
                """, conn)
                
                if not recent_trades.empty:
                    print("\n📋 ÚLTIMOS 10 TRADES:")
                    print(recent_trades.to_string(index=False))
                else:
                    print("\n⚠️ No hay trades en la base de datos")
                    
            else:
                print("❌ No se encontró tabla 'trades'")
                
            # 3. Ver estructura de la tabla trades si existe
            if 'trades' in tables['name'].values:
                schema = pd.read_sql_query("PRAGMA table_info(trades)", conn)
                print(f"\n🏗️ ESTRUCTURA DE TABLA 'trades':")
                for _, col in schema.iterrows():
                    print(f"   {col['name']}: {col['type']}")
                    
    except Exception as e:
        print(f"❌ Error analizando {db_path}: {e}")

def compare_with_analytics():
    """Comparar con los datos mostrados en Analytics"""
    print("\n" + "=" * 50)
    print("🔍 COMPARACIÓN CON DATOS DE ANALYTICS")
    print("=" * 50)
    
    print("Datos reportados en Analytics:")
    analytics_data = [
        ("orb", 555, 266, 47.93, 2703.51),
        ("macdv_smallcaps", 636, 286, 44.97, 1945.37),
        ("gap_go", 535, 260, 48.60, 860.98),
        ("volume_breakout", 548, 250, 45.62, 625.15)
    ]
    
    print("Estrategia | Trades | Wins | Win Rate | Total PnL")
    print("-" * 50)
    for strategy, trades, wins, win_rate, pnl in analytics_data:
        print(f"{strategy:<15} | {trades:>6} | {wins:>4} | {win_rate:>8.2f}% | ${pnl:>8.2f}")
    
    print("\n🚨 PROBLEMAS IDENTIFICADOS:")
    print("1. Volumen de trades (555-636) parece irreal para un día")
    print("2. Datos probablemente son históricos acumulados")
    print("3. Desconexión entre sistema ML y base de datos")
    print("4. Analytics no muestra datos reales de hoy")

if __name__ == "__main__":
    analyze_database()
    compare_with_analytics()
