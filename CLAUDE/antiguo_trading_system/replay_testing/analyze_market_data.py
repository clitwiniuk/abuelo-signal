#!/usr/bin/env python3
"""
Análisis Completo de Datos de Mercado para Replay Testing
Análisis enfocado exclusivamente en market_data.db
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any
import argparse

def analyze_market_data_comprehensive(
    market_db_path: str,
    date: str,
    output_file: str = None
) -> str:
    """
    Análisis completo de datos de mercado para entender el replay testing
    
    Args:
        market_db_path: Path to market_data.db
        date: Date to analyze (YYYY-MM-DD)
        output_file: Optional output file path
    
    Returns:
        Complete analysis report as string
    """
    
    report = []
    report.append("=" * 80)
    report.append("📊 ANÁLISIS COMPLETO DE DATOS DE MERCADO - REPLAY TESTING")
    report.append("=" * 80)
    report.append(f"Fecha analizada: {date}")
    report.append(f"Base de datos: {market_db_path}")
    report.append("")
    
    try:
        conn = sqlite3.connect(market_db_path)
        
        # 1. VERIFICAR ESTRUCTURA DE LA BASE DE DATOS
        report.append("🗄️ ESTRUCTURA DE LA BASE DE DATOS")
        report.append("-" * 50)
        
        # Verificar tablas disponibles
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)['name'].tolist()
        report.append(f"Tablas disponibles: {tables}")
        report.append("")
        
        # Verificar esquema de intraday_bars
        schema_query = "SELECT sql FROM sqlite_master WHERE name='intraday_bars';"
        schema = pd.read_sql_query(schema_query, conn)
        if not schema.empty:
            report.append("Esquema de intraday_bars:")
            report.append(schema.iloc[0]['sql'])
            report.append("")
        
        # 2. ANÁLISIS DE DATOS DEL DÍA ESPECÍFICO
        report.append(f"📈 DATOS DEL DÍA: {date}")
        report.append("-" * 50)
        
        # Query básico para el día específico
        day_query = """
        SELECT 
            symbol,
            COUNT(*) as total_bars,
            MIN(bar_timestamp) as first_bar,
            MAX(bar_timestamp) as last_bar,
            MIN(open_price) as min_open,
            MAX(open_price) as max_open,
            MIN(close_price) as min_close,
            MAX(close_price) as max_close,
            MIN(high_price) as min_high,
            MAX(high_price) as max_high,
            MIN(low_price) as min_low,
            MAX(low_price) as max_low,
            SUM(volume) as total_volume,
            AVG(volume) as avg_volume,
            AVG(vwap) as avg_vwap
        FROM intraday_bars 
        WHERE DATE(bar_timestamp) = ?
        GROUP BY symbol
        ORDER BY symbol
        """
        
        df_day = pd.read_sql_query(day_query, conn, params=[date])
        
        if df_day.empty:
            report.append("❌ No se encontraron datos para esta fecha")
            return "\n".join(report)
        
        report.append(f"✅ Símbolos encontrados: {len(df_day)}")
        report.append("")
        
        # Estadísticas detalladas por símbolo
        report.append("📊 DETALLE POR SÍMBOLO:")
        for _, row in df_day.iterrows():
            symbol = row['symbol']
            bars_count = row['total_bars']
            first_bar = row['first_bar']
            last_bar = row['last_bar']
            price_range = f"${row['min_close']:.2f} - ${row['max_close']:.2f}"
            total_volume = row['total_volume']
            avg_volume = row['avg_volume']
            
            report.append(f"  🔹 {symbol}:")
            report.append(f"     Barras: {bars_count}")
            report.append(f"     Rango temporal: {first_bar} → {last_bar}")
            report.append(f"     Rango de precios: {price_range}")
            report.append(f"     Volumen total: {total_volume:,}")
            report.append(f"     Volumen promedio: {avg_volume:,.0f}")
            report.append("")
        
        # 3. ANÁLISIS TEMPORAL DETALLADO
        report.append("⏰ ANÁLISIS TEMPORAL")
        report.append("-" * 50)
        
        # Obtener muestras de datos por símbolo para verificar integridad temporal
        for symbol in df_day['symbol'].head(3):  # Analizar solo los primeros 3 para no saturar
            symbol_query = """
            SELECT 
                bar_timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                vwap
            FROM intraday_bars 
            WHERE DATE(bar_timestamp) = ? AND symbol = ?
            ORDER BY bar_timestamp
            LIMIT 10
            """
            
            sample_data = pd.read_sql_query(symbol_query, conn, params=[date, symbol])
            
            if not sample_data.empty:
                report.append(f"Ejemplo de datos para {symbol} (primeras 10 barras):")
                for _, row in sample_data.iterrows():
                    report.append(f"  {row['bar_timestamp']}: O=${row['open_price']:.2f} "
                                f"H=${row['high_price']:.2f} L=${row['low_price']:.2f} "
                                f"C=${row['close_price']:.2f} V={row['volume']:,}")
                report.append("")
        
        # 4. ANÁLISIS DE INTEGRIDAD DE DATOS
        report.append("🔍 ANÁLISIS DE INTEGRIDAD")
        report.append("-" * 50)
        
        # Verificar gaps en los datos
        gaps_analysis = []
        for symbol in df_day['symbol']:
            symbol_query = """
            SELECT bar_timestamp FROM intraday_bars 
            WHERE DATE(bar_timestamp) = ? AND symbol = ?
            ORDER BY bar_timestamp
            """
            
            timestamps = pd.read_sql_query(symbol_query, conn, params=[date, symbol])['bar_timestamp']
            
            if len(timestamps) > 1:
                gaps = 0
                for i in range(1, len(timestamps)):
                    prev_time = pd.to_datetime(timestamps.iloc[i-1])
                    curr_time = pd.to_datetime(timestamps.iloc[i])
                    gap_minutes = (curr_time - prev_time).total_seconds() / 60
                    
                    if gap_minutes > 6:  # Más de 6 minutos entre barras
                        gaps += 1
                
                gaps_analysis.append({'symbol': symbol, 'gaps': gaps})
        
        report.append("Gaps temporales detectados:")
        for gap_info in gaps_analysis:
            if gap_info['gaps'] > 0:
                report.append(f"  {gap_info['symbol']}: {gap_info['gaps']} gaps")
            else:
                report.append(f"  {gap_info['symbol']}: Sin gaps")
        
        report.append("")
        
        # 5. COMPARACIÓN CON SEMANAS ANTERIORES
        report.append("📅 COMPARACIÓN CON DÍAS ANTERIORES")
        report.append("-" * 50)
        
        # Analizar días anteriores para contexto
        prev_date = (pd.to_datetime(date) - timedelta(days=1)).strftime('%Y-%m-%d')
        prev2_date = (pd.to_datetime(date) - timedelta(days=2)).strftime('%Y-%m-%d')
        
        for check_date in [prev_date, prev2_date]:
            check_query = """
            SELECT COUNT(*) as symbol_count, COUNT(*) * 78 as total_bars_estimated
            FROM (
                SELECT symbol, COUNT(*) as bars 
                FROM intraday_bars 
                WHERE DATE(bar_timestamp) = ?
                GROUP BY symbol
            )
            """
            
            try:
                check_data = pd.read_sql_query(check_query, conn, params=[check_date])
                if not check_data.empty:
                    symbol_count = check_data.iloc[0]['symbol_count']
                    bars_estimate = check_data.iloc[0]['total_bars_estimated']
                    report.append(f"{check_date}: {symbol_count} símbolos "
                                f"(aprox. {bars_estimate} barras)")
                else:
                    report.append(f"{check_date}: Sin datos")
            except:
                report.append(f"{check_date}: Sin datos")
        
        report.append("")
        
        # 6. VERIFICAR EL PROBLEMA DEL REPLAY ENGINE
        report.append("🐛 DIAGNÓSTICO DEL PROBLEMA DEL REPLAY ENGINE")
        report.append("-" * 50)
        
        report.append("🚨 POSIBLE CAUSA: El replay engine dice 'Loaded data for 0 symbols'")
        report.append("pero claramente hay datos disponibles en la base de datos.")
        report.append("")
        
        # Simular la query que usa el replay engine
        replay_query = """
        SELECT symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume, vwap
        FROM intraday_bars 
        WHERE DATE(bar_timestamp) = ?
        ORDER BY symbol, bar_timestamp
        LIMIT 10
        """
        
        try:
            replay_test = pd.read_sql_query(replay_query, conn, params=[date])
            if not replay_test.empty:
                report.append("✅ La query del replay engine SÍ devuelve datos:")
                report.append(f"   Total de registros: {len(replay_test)}")
                report.append(f"   Símbolos únicos: {replay_test['symbol'].nunique()}")
                report.append(f"   Símbolos: {replay_test['symbol'].unique()}")
                
                # Mostrar primera muestra
                report.append("   Primera muestra:")
                for _, row in replay_test.head(3).iterrows():
                    report.append(f"     {row['symbol']}: {row['bar_timestamp']} "
                                f"O=${row['open_price']:.2f} C=${row['close_price']:.2f}")
            else:
                report.append("❌ La query del replay engine NO devuelve datos")
        
        except Exception as e:
            report.append(f"❌ Error en la query del replay engine: {e}")
        
        report.append("")
        
        # 7. RECOMENDACIONES
        report.append("💡 RECOMENDACIONES PARA SOLUCIONAR EL REPLAY TESTING")
        report.append("-" * 50)
        
        report.append("1. 🔍 Verificar la ruta de la base de datos:")
        report.append("   - El replay engine puede estar buscando la DB en un directorio diferente")
        report.append("   - Verificar que market_data.db esté en la ruta correcta")
        report.append("")
        
        report.append("2. 📋 Revisar la lógica de procesamiento:")
        report.append("   - Verificar el método load_market_data() en replay_engine.py")
        report.append("   - Asegurar que el DataFrame no esté vacío después de load_market_data()")
        report.append("   - Revisar el log 'DEBUG: DataFrame shape' y 'DEBUG: DataFrame head'")
        report.append("")
        
        report.append("3. 🧪 Verificar en modo debug:")
        report.append("   - Ejecutar el replay con --verbose para ver todos los logs")
        report.append("   - Revisar si hay errores silenciosos en el procesamiento")
        report.append("   - Verificar que la variable bars_by_symbol se llene correctamente")
        report.append("")
        
        report.append("4. ⚙️ Verificar configuración de paths:")
        report.append("   - Confirmar que el working directory sea correcto")
        report.append("   - Verificar que el parámetro --market-db apunte al archivo correcto")
        report.append("   - Revisar permisos de lectura de la base de datos")
        report.append("")
        
        # 8. RESUMEN EJECUTIVO
        report.append("📊 RESUMEN EJECUTIVO")
        report.append("-" * 50)
        
        total_symbols = len(df_day)
        total_bars = df_day['total_bars'].sum()
        avg_volume = df_day['avg_volume'].mean()
        total_volume = df_day['total_volume'].sum()
        
        report.append(f"✅ Datos de mercado disponibles para {date}:")
        report.append(f"   • Símbolos: {total_symbols}")
        report.append(f"   • Barras totales: {total_bars:,}")
        report.append(f"   • Volumen promedio: {avg_volume:,.0f}")
        report.append(f"   • Volumen total: {total_volume:,}")
        report.append("")
        
        report.append("🎯 CONCLUSIÓN:")
        report.append("Los datos de mercado están completamente disponibles en")
        report.append(f"market_data.db para el día {date}. El problema del replay")
        report.append("engine que reporta '0 symbols' se debe a un error en la")
        report.append("lógica de procesamiento o configuración de paths, no a")
        report.append("falta de datos.")
        report.append("")
        report.append("El sistema de replay testing debe funcionar correctamente")
        report.append("una vez que se solucione el problema de procesamiento.")
        
    except Exception as e:
        report.append(f"❌ Error durante el análisis: {e}")
        import traceback
        report.append(f"Detalles: {traceback.format_exc()}")
    
    finally:
        conn.close()
    
    report.append("")
    report.append("=" * 80)
    report.append("Fin del análisis")
    report.append("=" * 80)
    
    analysis_text = "\n".join(report)
    
    # Guardar en archivo si se especificó
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(analysis_text)
        print(f"📄 Análisis guardado en: {output_file}")
    
    return analysis_text

def main():
    parser = argparse.ArgumentParser(description='Análisis completo de datos de mercado para replay testing')
    parser.add_argument('--date', required=True, help='Fecha a analizar (YYYY-MM-DD)')
    parser.add_argument('--market-db', default='market_data.db', help='Base de datos de mercado')
    parser.add_argument('--output', help='Archivo de salida para el análisis')
    
    args = parser.parse_args()
    
    analysis = analyze_market_data_comprehensive(
        market_db_path=args.market_db,
        date=args.date,
        output_file=args.output
    )
    
    print(analysis)

if __name__ == "__main__":
    main()