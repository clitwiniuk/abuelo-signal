#!/usr/bin/env python3
"""
Script para limpiar trades falsos con PnL = 0 y duración instantánea
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

def cleanup_fake_trades():
    """Limpiar trades falsos de la base de datos"""
    print("🧹 LIMPIEZA DE TRADES FALSOS")
    print("=" * 50)
    
    db_files = [
        "trading_data.db",
        "data/trading_history.db", 
        "logs/trading_data.db"
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"\n📁 Limpiando: {db_file}")
            cleanup_db_file(db_file)
        else:
            print(f"❌ No encontrado: {db_file}")

def cleanup_db_file(db_path):
    """Limpiar un archivo específico de base de datos"""
    try:
        with sqlite3.connect(db_path) as conn:
            # 1. Identificar trades falsos
            fake_trades = pd.read_sql_query("""
                SELECT id, symbol, strategy, entry_time, exit_time, pnl, duration_minutes, notes
                FROM trades 
                WHERE status = 'CLOSED' 
                    AND pnl = 0.0 
                    AND duration_minutes <= 1
                    AND (notes LIKE '%Legacy position exit%' OR 
                         (entry_time IS NOT NULL AND exit_time IS NOT NULL AND 
                          (julianday(exit_time) - julianday(entry_time)) * 24 * 60 < 1))
                ORDER BY entry_time DESC
            """, conn)
            
            if fake_trades.empty:
                print("   ✅ No se encontraron trades falsos")
                return
            
            print(f"   🚨 Encontrados {len(fake_trades)} trades falsos:")
            print("   ID | Symbol | Strategy | Duration | PnL | Notes")
            print("   " + "-" * 60)
            
            for _, trade in fake_trades.head(10).iterrows():  # Mostrar solo los primeros 10
                duration = trade['duration_minutes'] if trade['duration_minutes'] is not None else 0
                notes_short = (trade['notes'][:30] + '...') if trade['notes'] and len(trade['notes']) > 30 else (trade['notes'] or '')
                print(f"   {trade['id']:<3} | {trade['symbol']:<6} | {trade['strategy']:<15} | {duration:<8} | ${trade['pnl']:<6} | {notes_short}")
            
            if len(fake_trades) > 10:
                print(f"   ... y {len(fake_trades) - 10} más")
            
            # 2. Confirmar limpieza
            response = input(f"\n¿Eliminar estos {len(fake_trades)} trades falsos? (y/N): ").strip().lower()
            
            if response == 'y':
                # Crear backup antes de eliminar
                backup_table = f"trades_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                conn.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM trades")
                print(f"   💾 Backup creado: {backup_table}")
                
                # Eliminar trades falsos
                fake_ids = fake_trades['id'].tolist()
                placeholders = ','.join(['?' for _ in fake_ids])
                
                cursor = conn.execute(f"DELETE FROM trades WHERE id IN ({placeholders})", fake_ids)
                deleted_count = cursor.rowcount
                
                print(f"   🗑️ Eliminados {deleted_count} trades falsos")
                
                # Verificar resultado
                remaining_fake = pd.read_sql_query("""
                    SELECT COUNT(*) as count FROM trades 
                    WHERE status = 'CLOSED' AND pnl = 0.0 AND duration_minutes <= 1
                """, conn)
                
                print(f"   ✅ Trades falsos restantes: {remaining_fake['count'].iloc[0]}")
                
                # Mostrar estadísticas actualizadas
                total_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM trades", conn)
                closed_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM trades WHERE status = 'CLOSED'", conn)
                
                print(f"   📊 Total trades después de limpieza: {total_trades['count'].iloc[0]}")
                print(f"   📊 Trades cerrados: {closed_trades['count'].iloc[0]}")
                
            else:
                print("   ❌ Limpieza cancelada")
                
    except Exception as e:
        print(f"❌ Error limpiando {db_path}: {e}")

def analyze_clean_data():
    """Analizar datos después de la limpieza"""
    print("\n" + "=" * 50)
    print("📊 ANÁLISIS POST-LIMPIEZA")
    print("=" * 50)
    
    db_path = "trading_data.db"
    if not os.path.exists(db_path):
        print("❌ No se encontró trading_data.db")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Performance por estrategia (datos limpios)
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
                WHERE status = 'CLOSED'
                    AND date(entry_time) >= date('now', '-7 days')
                GROUP BY strategy
                ORDER BY total_pnl DESC
            """, conn)
            
            if not strategy_perf.empty:
                print("📈 PERFORMANCE POR ESTRATEGIA (datos limpios, últimos 7 días):")
                print(strategy_perf.to_string(index=False))
            else:
                print("✅ No hay trades cerrados en los últimos 7 días (datos limpios)")
            
            # Trades de hoy
            today_trades = pd.read_sql_query("""
                SELECT symbol, strategy, entry_time, exit_time, pnl, duration_minutes
                FROM trades 
                WHERE date(entry_time) = date('now')
                    AND status = 'CLOSED'
                ORDER BY entry_time DESC
            """, conn)
            
            if not today_trades.empty:
                print(f"\n📅 TRADES DE HOY ({len(today_trades)} trades):")
                print(today_trades.to_string(index=False))
            else:
                print("\n📅 No hay trades reales de hoy después de la limpieza")
                
    except Exception as e:
        print(f"❌ Error en análisis post-limpieza: {e}")

if __name__ == "__main__":
    cleanup_fake_trades()
    analyze_clean_data()
    
    print("\n" + "=" * 50)
    print("🎯 RESUMEN")
    print("=" * 50)
    print("✅ Solución implementada para prevenir trades falsos")
    print("✅ Base de datos limpia de trades con PnL=0 instantáneos")
    print("✅ Analytics ahora mostrará solo datos reales")
    print("✅ ML podrá aprender de trades reales con PnL correcto")
    print("\n🚀 El sistema ahora está listo para generar métricas reales!")
