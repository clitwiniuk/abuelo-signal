#!/usr/bin/env python3
"""
Análisis Profundo de Fechas - Identificar Coincidencias Exactas

Este script hace un análisis detallado de qué fechas existen exactamente
en ambas bases de datos para crear coincidencias reales.
"""

import sqlite3
from datetime import datetime


def analyze_all_dates():
    """Análisis completo de fechas en ambas bases"""
    print("🔍 ANÁLISIS PROFUNDO DE FECHAS")
    print("=" * 60)
    
    # Conectar a ambas bases
    trading_conn = sqlite3.connect('../trading_data.db')
    trading_cursor = trading_conn.cursor()
    
    market_conn = sqlite3.connect('market_data.db')
    market_cursor = market_conn.cursor()
    
    # Obtener TODAS las fechas de trading_data
    print("📊 Analizando trading_data.db...")
    trading_cursor.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM scanner_opportunities 
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
    ''')
    trading_dates = trading_cursor.fetchall()
    
    print(f"   Fechas en trading_data: {len(trading_dates)}")
    print("   Últimas 10 fechas:")
    for date, count in trading_dates[:10]:
        print(f"     - {date}: {count:,} oportunidades")
    
    # Obtener TODAS las fechas de market_data
    print(f"\n📈 Analizando market_data.db...")
    market_cursor.execute('''
        SELECT DATE(bar_timestamp) as date, COUNT(*) as count
        FROM intraday_bars 
        GROUP BY DATE(bar_timestamp)
        ORDER BY date DESC
    ''')
    market_dates = market_cursor.fetchall()
    
    print(f"   Fechas en market_data: {len(market_dates)}")
    print("   Últimas 10 fechas:")
    for date, count in market_dates[:10]:
        print(f"     - {date}: {count:,} barras")
    
    # Crear conjuntos de fechas
    trading_date_set = {date for date, count in trading_dates}
    market_date_set = {date for date, count in market_dates}
    
    # Encontrar fechas comunes
    common_dates = trading_date_set & market_date_set
    
    print(f"\n🎯 ANÁLISIS DE COINCIDENCIAS:")
    print(f"   Fechas únicas en trading_data: {len(trading_date_set)}")
    print(f"   Fechas únicas en market_data: {len(market_date_set)}")
    print(f"   Fechas COMUNES: {len(common_dates)}")
    
    if common_dates:
        print(f"\n✅ FECHAS COMUNES ENCONTRADAS:")
        for date in sorted(common_dates, reverse=True):
            # Contar en trading_data
            tr_count = next((count for d, count in trading_dates if d == date), 0)
            # Contar en market_data  
            mk_count = next((count for d, count in market_dates if d == date), 0)
            print(f"   • {date}: {tr_count:,} oportunidades + {mk_count:,} barras")
    else:
        print(f"\n❌ NO HAY FECHAS COMUNES")
        print(f"   Rango trading_data: {min(trading_date_set)} a {max(trading_date_set)}")
        print(f"   Rango market_data: {min(market_date_set)} a {max(market_date_set)}")
    
    trading_conn.close()
    market_conn.close()
    
    return common_dates


def create_test_events_for_common_dates():
    """Crea eventos de prueba usando las fechas comunes encontradas"""
    print(f"\n🛠️  CREANDO EVENTOS DE PRUEBA CON FECHAS COMUNES")
    print("=" * 60)
    
    # Primero obtener las fechas comunes
    trading_conn = sqlite3.connect('../trading_data.db')
    trading_cursor = trading_conn.cursor()
    
    market_conn = sqlite3.connect('market_data.db')
    market_cursor = market_conn.cursor()
    
    # Obtener fechas que existen en ambas
    trading_cursor.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM scanner_opportunities 
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
    ''')
    trading_dates = {date: count for date, count in trading_cursor.fetchall()}
    
    market_cursor.execute('''
        SELECT DATE(bar_timestamp) as date, COUNT(*) as count
        FROM intraday_bars 
        GROUP BY DATE(bar_timestamp)
        ORDER BY date DESC
    ''')
    market_dates = {date: count for date, count in market_cursor.fetchall()}
    
    # Encontrar fechas comunes
    common_dates = set(trading_dates.keys()) & set(market_dates.keys())
    
    if not common_dates:
        print(f"❌ No hay fechas comunes - usando fechas de market_data existentes")
        # Usar las fechas más recientes de market_data
        common_dates = list(market_dates.keys())[:3]
        print(f"   Usando fechas de prueba: {common_dates}")
    
    # Para cada fecha común, encontrar símbolos que existan en ambas
    test_events = []
    
    for date in sorted(common_dates, reverse=True)[:3]:  # Limitar a 3 fechas
        print(f"\n📅 Analizando fecha {date}...")
        
        # Símbolos en trading_data para esta fecha
        trading_cursor.execute('''
            SELECT DISTINCT symbol 
            FROM scanner_opportunities 
            WHERE DATE(timestamp) = ?
        ''', (date,))
        trading_symbols = {row[0] for row in trading_cursor.fetchall()}
        
        # Símbolos en market_data para esta fecha
        market_cursor.execute('''
            SELECT DISTINCT symbol 
            FROM intraday_bars 
            WHERE DATE(bar_timestamp) = ?
        ''', (date,))
        market_symbols = {row[0] for row in market_cursor.fetchall()}
        
        # Símbolos comunes para esta fecha
        common_symbols = trading_symbols & market_symbols
        
        if common_symbols:
            # Tomar 1-2 símbolos para testing
            test_symbols = list(common_symbols)[:2]
            for symbol in test_symbols:
                test_events.append({
                    'symbol': symbol,
                    'date': date,
                    'opportunities': trading_dates.get(date, 0),
                    'bars': market_dates.get(date, 0)
                })
                print(f"   ✅ {symbol}: {trading_dates.get(date, 0)} opps + {market_dates.get(date, 0)} barras")
        else:
            print(f"   ❌ No hay símbolos comunes para {date}")
    
    trading_conn.close()
    market_conn.close()
    
    return test_events


def main():
    """Función principal"""
    print("🚀 ANÁLISIS COMPLETO PARA CORREGIR event_id")
    print("=" * 70)
    
    # 1. Análisis profundo de fechas
    common_dates = analyze_all_dates()
    
    # 2. Crear eventos de prueba
    test_events = create_test_events_for_common_dates()
    
    print(f"\n📋 EVENTOS DE PRUEBA IDENTIFICADOS:")
    for event in test_events:
        print(f"   • {event['symbol']} {event['date']}: {event['bars']:,} barras")
    
    if test_events:
        print(f"\n✅ LISTO PARA PROCESAR {len(test_events)} EVENTOS")
        print(f"   Estos eventos SÍ deberían tener datos en ambas bases")
    else:
        print(f"\n❌ NO SE ENCONTRARON EVENTOS PROCESABLES")
        print(f"   Las bases de datos parecen tener datos de períodos diferentes")
    
    return test_events


if __name__ == "__main__":
    main()