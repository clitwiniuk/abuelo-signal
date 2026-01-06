#!/usr/bin/env python3
"""
Ejemplo de Uso del Sistema Expandido - Datos Intradiarios + Contexto Histórico

Este script demuestra cómo:
1. Obtener oportunidades del scanner
2. Generar event_id únicos 
3. Agrupar datos intradiarios por evento
4. Agregar contexto histórico de 60 días
5. Preparar datos para smallcaps-algorithm

Uso:
    python example_expanded_usage.py
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
import json


def generate_event_id(symbol, date_str):
    """Genera event_id único basado en símbolo y fecha"""
    event_data = f"{symbol}_{date_str}"
    return int(hashlib.md5(event_data.encode()).hexdigest()[:8], 16)


def get_scanner_opportunities(trading_db_path, limit=10):
    """Obtiene oportunidades recientes del scanner"""
    conn = sqlite3.connect(trading_db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT symbol, DATE(timestamp) as date, 
               opportunity_type, catalyst_type, quality_score
        FROM scanner_opportunities 
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    opportunities = cursor.fetchall()
    conn.close()
    
    return [{
        'symbol': opp[0],
        'date': opp[1],
        'opportunity_type': opp[2],
        'catalyst_type': opp[3],
        'quality_score': opp[4]
    } for opp in opportunities]


def process_event_data(market_db_path, opportunity):
    """Procesa datos para un evento específico"""
    symbol = opportunity['symbol']
    date = opportunity['date']
    event_id = generate_event_id(symbol, date)
    
    conn = sqlite3.connect(market_db_path)
    cursor = conn.cursor()
    
    # 1. Verificar si ya tiene event_id
    cursor.execute('''
        SELECT COUNT(*) FROM intraday_bars 
        WHERE symbol = ? AND DATE(bar_timestamp) = ? AND event_id = ?
    ''', (symbol, date, event_id))
    
    already_processed = cursor.fetchone()[0] > 0
    
    if already_processed:
        print(f"✅ {symbol} {date}: Ya procesado (event_id: {event_id})")
        conn.close()
        return
    
    # 2. Actualizar barras intradiarias con event_id
    cursor.execute('''
        UPDATE intraday_bars 
        SET event_id = ?
        WHERE symbol = ? AND DATE(bar_timestamp) = ?
    ''', (event_id, symbol, date))
    
    updated_bars = cursor.rowcount
    
    # 3. Verificar/crear contexto histórico (últimos 60 días)
    event_date = datetime.strptime(date, '%Y-%m-%d')
    historical_start = event_date - timedelta(days=60)
    
    # Contar días históricos existentes para este evento
    cursor.execute('''
        SELECT COUNT(*) FROM daily_ohlcv_history 
        WHERE event_id = ?
    ''', (event_id,))
    
    existing_history = cursor.fetchone()[0]
    
    if existing_history == 0:
        # Simular datos históricos (en implementación real, descargar de Polygon)
        historical_days = 60
        for i in range(1, historical_days + 1):
            hist_date = event_date - timedelta(days=i)
            
            # Datos simulados (precio base + variación)
            base_price = 10.0
            price_variation = (i * 0.01)  # Variación gradual
            
            cursor.execute('''
                INSERT INTO daily_ohlcv_history 
                (event_id, symbol, history_date, days_before_event,
                 open_price, high_price, low_price, close_price, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_id, symbol, hist_date.strftime('%Y-%m-%d'), i,
                base_price + price_variation, 
                base_price + price_variation + 0.5,
                base_price + price_variation - 0.3,
                base_price + price_variation + 0.2,
                100000 + (i * 1000)  # Volumen variable
            ))
        
        print(f"📊 {symbol} {date}: {updated_bars} barras + {historical_days} días históricos")
    else:
        print(f"📊 {symbol} {date}: {updated_bars} barras + {existing_history} días históricos")
    
    conn.commit()
    conn.close()
    
    return {
        'symbol': symbol,
        'date': date,
        'event_id': event_id,
        'intraday_bars': updated_bars,
        'historical_days': existing_history if existing_history > 0 else 60
    }


def analyze_event_context(market_db_path, event_id):
    """Analiza el contexto de un evento específico"""
    conn = sqlite3.connect(market_db_path)
    cursor = conn.cursor()
    
    # Obtener datos intradiarios del evento
    cursor.execute('''
        SELECT symbol, bar_timestamp, open_price, high_price, 
               low_price, close_price, volume
        FROM intraday_bars 
        WHERE event_id = ?
        ORDER BY bar_timestamp
    ''', (event_id,))
    
    intraday_data = cursor.fetchall()
    
    # Obtener contexto histórico
    cursor.execute('''
        SELECT history_date, days_before_event, close_price, volume
        FROM daily_ohlcv_history 
        WHERE event_id = ?
        ORDER BY days_before_event DESC
        LIMIT 10
    ''', (event_id,))
    
    historical_data = cursor.fetchall()
    
    conn.close()
    
    return {
        'intraday_bars': len(intraday_data),
        'historical_context': len(historical_data),
        'sample_intraday': intraday_data[:3] if intraday_data else [],
        'sample_historical': historical_data[:5] if historical_data else []
    }


def main():
    """Función principal - demostración del sistema expandido"""
    print("🚀 DEMO: SISTEMA EXPANDIDO PARA BACKTESTING")
    print("=" * 60)
    
    # Paths a las bases de datos
    trading_db = '../trading_data.db'
    market_db = 'market_data.db'
    
    # 1. Obtener oportunidades del scanner
    print("\n📊 PASO 1: Obteniendo oportunidades del scanner...")
    opportunities = get_scanner_opportunities(trading_db, limit=5)
    
    print(f"✅ Obtenidas {len(opportunities)} oportunidades:")
    for i, opp in enumerate(opportunities, 1):
        print(f"   {i}. {opp['symbol']} - {opp['date']} ({opp['opportunity_type']})")
    
    # 2. Procesar eventos (agregar event_id y contexto histórico)
    print(f"\n📈 PASO 2: Procesando eventos (agregando event_id y contexto histórico)...")
    processed_events = []
    
    for opportunity in opportunities:
        try:
            result = process_event_data(market_db, opportunity)
            if result:
                processed_events.append(result)
        except Exception as e:
            print(f"❌ Error procesando {opportunity['symbol']}: {e}")
    
    # 3. Analizar contexto de eventos procesados
    print(f"\n🔍 PASO 3: Analizando contexto de eventos...")
    
    for event in processed_events:
        print(f"\n   📊 Evento: {event['symbol']} {event['date']} (ID: {event['event_id']})")
        
        context = analyze_event_context(market_db, event['event_id'])
        
        print(f"      • Barras intradiarias: {context['intraday_bars']}")
        print(f"      • Días de contexto: {context['historical_context']}")
        
        if context['sample_historical']:
            print(f"      • Últimos días históricos:")
            for hist in context['sample_historical'][:3]:
                date, days_before, price, vol = hist
                print(f"        - {date} ({days_before}d antes): ${price:.2f}")
    
    # 4. Resumen final
    print(f"\n✅ RESUMEN DEL PROCESAMIENTO:")
    print(f"   • Eventos procesados: {len(processed_events)}")
    print(f"   • Total barras con event_id: {sum(e['intraday_bars'] for e in processed_events):,}")
    print(f"   • Total días históricos: {sum(e['historical_days'] for e in processed_events):,}")
    
    print(f"\n🎯 DATOS LISTOS PARA:")
    print(f"   • Backtesting con contexto histórico completo")
    print(f"   • Análisis de smallcaps-algorithm")
    print(f"   • Discovery de reglas con 60 días de contexto")
    print(f"   • Optimización de estrategias basada en eventos")
    
    # 5. Ejemplo de consulta para smallcaps-algorithm
    print(f"\n📋 EJEMPLO DE CONSULTA PARA SMALLCAPS-ALGORITHM:")
    print(f"""   SELECT 
        h.symbol,
        h.days_before_event,
        h.close_price as historical_price,
        h.volume as historical_volume,
        i.close_price as event_day_price,
        i.volume as event_day_volume,
        (i.close_price - h.close_price) / h.close_price * 100 as price_change_pct,
        (i.volume - h.volume) / h.volume * 100 as volume_change_pct
    FROM daily_ohlcv_history h
    JOIN intraday_bars i ON h.event_id = i.event_id AND h.symbol = i.symbol
    WHERE h.event_id IN ({','.join(str(e['event_id']) for e in processed_events)})
    ORDER BY h.symbol, h.days_before_event DESC;""")


if __name__ == "__main__":
    main()