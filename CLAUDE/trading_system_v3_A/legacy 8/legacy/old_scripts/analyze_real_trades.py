#!/usr/bin/env python3
"""
Análisis de Trades Reales - trading_data.db
Identifica patrones en trades perdedores para proponer mejoras específicas
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import numpy as np

def analyze_real_trades():
    """Análisis completo de trades reales de la base de datos"""

    print("🔍 ANÁLISIS DE TRADES REALES - trading_data.db")
    print("=" * 60)

    # Conectar a la base de datos
    conn = sqlite3.connect('trading_data.db')

    # Cargar todos los trades cerrados
    query = """
    SELECT
        trade_id, symbol, strategy, side, quantity,
        entry_price, exit_price, entry_time, exit_time,
        duration_minutes, pnl, confidence,
        recent_high_5d, recent_low_5d, recent_avg_price,
        price_momentum, volume_trend, relative_position,
        symbol_strength, market_context,
        actual_pnl, entry_slippage_pct, exit_slippage_pct
    FROM trades
    WHERE status = 'CLOSED'
    ORDER BY entry_time DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"📊 Total trades analizados: {len(df)}")
    print(f"📅 Período: {df['entry_time'].min()} a {df['entry_time'].max()}")
    print()

    # Clasificar trades
    winners = df[df['pnl'] > 0]
    losers = df[df['pnl'] <= 0]

    print("🏆 RESUMEN GENERAL:")
    print(f"   Trades ganadores: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"   Trades perdedores: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")
    print(f"   P&L promedio ganadores: ${winners['pnl'].mean():.2f}")
    print(f"   P&L promedio perdedores: ${losers['pnl'].mean():.2f}")
    print(f"   P&L total: ${df['pnl'].sum():.2f}")
    print()

    # ANÁLISIS 1: Patrones por duración
    print("⏱️  ANÁLISIS 1: PATRONES POR DURACIÓN")
    print("-" * 40)

    duration_analysis = analyze_duration_patterns(df, winners, losers)
    print()

    # ANÁLISIS 2: Patrones por estrategia
    print("📈 ANÁLISIS 2: PATRONES POR ESTRATEGIA")
    print("-" * 40)

    strategy_analysis = analyze_strategy_patterns(df)
    print()

    # ANÁLISIS 3: Patrones por confidence
    print("🎯 ANÁLISIS 3: PATRONES POR CONFIDENCE")
    print("-" * 40)

    confidence_analysis = analyze_confidence_patterns(df, winners, losers)
    print()

    # ANÁLISIS 4: Patrones por market context
    print("🌍 ANÁLISIS 4: PATRONES POR MARKET CONTEXT")
    print("-" * 40)

    market_analysis = analyze_market_context_patterns(df, winners, losers)
    print()

    # ANÁLISIS 5: Top pérdidas - casos específicos
    print("💸 ANÁLISIS 5: TOP 10 PEORES TRADES")
    print("-" * 40)

    worst_trades = analyze_worst_trades(df)
    print()

    # ANÁLISIS 6: Mejores trades para comparar
    print("🏆 ANÁLISIS 6: TOP 10 MEJORES TRADES")
    print("-" * 40)

    best_trades = analyze_best_trades(df)
    print()

    # ANÁLISIS 7: Patrones temporales
    print("📅 ANÁLISIS 7: PATRONES TEMPORALES")
    print("-" * 40)

    temporal_analysis = analyze_temporal_patterns(df)
    print()

    # RECOMENDACIONES FINALES
    print("🎯 RECOMENDACIONES ESPECÍFICAS BASADAS EN DATOS REALES")
    print("=" * 60)

    generate_recommendations(df, winners, losers, duration_analysis,
                           confidence_analysis, market_analysis,
                           worst_trades, temporal_analysis)

def analyze_duration_patterns(df, winners, losers):
    """Analizar patrones de duración"""

    # Categorizar por duración
    df['duration_category'] = pd.cut(df['duration_minutes'],
                                   bins=[0, 30, 120, 240, float('inf')],
                                   labels=['Rápido(≤30min)', 'Medio(30-120min)',
                                          'Lento(120-240min)', 'MuyLento(>240min)'])

    duration_stats = df.groupby('duration_category').agg({
        'pnl': ['count', 'mean', lambda x: (x > 0).sum()],
        'confidence': 'mean'
    }).round(2)

    duration_stats.columns = ['Trades', 'Avg_PnL', 'Wins', 'Avg_Confidence']
    duration_stats['Win_Rate'] = (duration_stats['Wins'] / duration_stats['Trades'] * 100).round(1)

    print("Rendimiento por duración:")
    print(duration_stats)

    # Identificar duración óptima
    best_duration = duration_stats.loc[duration_stats['Avg_PnL'].idxmax()]
    worst_duration = duration_stats.loc[duration_stats['Avg_PnL'].idxmin()]

    print(f"\n✅ Mejor duración: {best_duration.name} - ${best_duration['Avg_PnL']:.2f} promedio")
    print(f"❌ Peor duración: {worst_duration.name} - ${worst_duration['Avg_PnL']:.2f} promedio")

    return duration_stats

def analyze_strategy_patterns(df):
    """Analizar patrones por estrategia"""

    strategy_stats = df.groupby('strategy').agg({
        'pnl': ['count', 'mean', 'sum', lambda x: (x > 0).sum()],
        'confidence': 'mean',
        'duration_minutes': 'mean'
    }).round(2)

    strategy_stats.columns = ['Trades', 'Avg_PnL', 'Total_PnL', 'Wins', 'Avg_Confidence', 'Avg_Duration']
    strategy_stats['Win_Rate'] = (strategy_stats['Wins'] / strategy_stats['Trades'] * 100).round(1)

    print("Rendimiento por estrategia:")
    print(strategy_stats)

    return strategy_stats

def analyze_confidence_patterns(df, winners, losers):
    """Analizar relación entre confidence y resultados"""

    # Categorizar por confidence
    df['confidence_category'] = pd.cut(df['confidence'],
                                     bins=[0, 20, 40, 60, 80, 100],
                                     labels=['Muy_Bajo', 'Bajo', 'Medio', 'Alto', 'Muy_Alto'])

    confidence_stats = df.groupby('confidence_category').agg({
        'pnl': ['count', 'mean', lambda x: (x > 0).sum()],
    }).round(2)

    confidence_stats.columns = ['Trades', 'Avg_PnL', 'Wins']
    confidence_stats['Win_Rate'] = (confidence_stats['Wins'] / confidence_stats['Trades'] * 100).round(1)

    print("Rendimiento por nivel de confidence:")
    print(confidence_stats)

    # Correlación directa
    correlation = df['confidence'].corr(df['pnl'])
    print(f"\n📊 Correlación confidence vs P&L: {correlation:.3f}")

    if correlation < 0.1:
        print("⚠️  PROBLEMA: Confidence no predice resultados (correlación baja)")

    return confidence_stats

def analyze_market_context_patterns(df, winners, losers):
    """Analizar patrones por contexto de mercado"""

    market_stats = df.groupby('market_context').agg({
        'pnl': ['count', 'mean', lambda x: (x > 0).sum()],
    }).round(2)

    market_stats.columns = ['Trades', 'Avg_PnL', 'Wins']
    market_stats['Win_Rate'] = (market_stats['Wins'] / market_stats['Trades'] * 100).round(1)

    print("Rendimiento por contexto de mercado:")
    print(market_stats)

    return market_stats

def analyze_worst_trades(df):
    """Analizar los 10 peores trades en detalle"""

    worst = df.nsmallest(10, 'pnl')[['symbol', 'strategy', 'entry_time', 'duration_minutes',
                                    'pnl', 'confidence', 'market_context', 'price_momentum']]

    print("Top 10 peores trades:")
    for i, (_, trade) in enumerate(worst.iterrows(), 1):
        print(f"{i:2d}. {trade['symbol']:6} | {trade['strategy']:12} | ${trade['pnl']:6.2f} | "
              f"{trade['duration_minutes']:3.0f}min | conf:{trade['confidence']:4.1f} | {trade['market_context']}")

    # Buscar patrones comunes
    print("\n🔍 Patrones en peores trades:")
    print(f"   Estrategia más común: {worst['strategy'].mode().iloc[0]}")
    print(f"   Duración promedio: {worst['duration_minutes'].mean():.0f} min")
    print(f"   Confidence promedio: {worst['confidence'].mean():.1f}")
    print(f"   Market context más común: {worst['market_context'].mode().iloc[0]}")

    return worst

def analyze_best_trades(df):
    """Analizar los 10 mejores trades"""

    best = df.nlargest(10, 'pnl')[['symbol', 'strategy', 'entry_time', 'duration_minutes',
                                  'pnl', 'confidence', 'market_context', 'price_momentum']]

    print("Top 10 mejores trades:")
    for i, (_, trade) in enumerate(best.iterrows(), 1):
        print(f"{i:2d}. {trade['symbol']:6} | {trade['strategy']:12} | ${trade['pnl']:6.2f} | "
              f"{trade['duration_minutes']:3.0f}min | conf:{trade['confidence']:4.1f} | {trade['market_context']}")

    print("\n🔍 Patrones en mejores trades:")
    print(f"   Estrategia más común: {best['strategy'].mode().iloc[0]}")
    print(f"   Duración promedio: {best['duration_minutes'].mean():.0f} min")
    print(f"   Confidence promedio: {best['confidence'].mean():.1f}")
    print(f"   Market context más común: {best['market_context'].mode().iloc[0]}")

    return best

def analyze_temporal_patterns(df):
    """Analizar patrones temporales"""

    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['hour'] = df['entry_time'].dt.hour
    df['day_of_week'] = df['entry_time'].dt.day_name()

    # Por hora del día
    hourly_stats = df.groupby('hour').agg({
        'pnl': ['count', 'mean', lambda x: (x > 0).sum()]
    }).round(2)
    hourly_stats.columns = ['Trades', 'Avg_PnL', 'Wins']
    hourly_stats['Win_Rate'] = (hourly_stats['Wins'] / hourly_stats['Trades'] * 100).round(1)

    print("Rendimiento por hora del día:")
    best_hours = hourly_stats.nlargest(3, 'Avg_PnL')
    worst_hours = hourly_stats.nsmallest(3, 'Avg_PnL')

    print("🏆 Mejores horas:")
    print(best_hours)
    print("\n💸 Peores horas:")
    print(worst_hours)

    return {'hourly': hourly_stats}

def generate_recommendations(df, winners, losers, duration_analysis,
                           confidence_analysis, market_analysis,
                           worst_trades, temporal_analysis):
    """Generar recomendaciones específicas basadas en análisis"""

    recommendations = []

    # 1. Recomendaciones de duración
    best_duration = duration_analysis['Avg_PnL'].idxmax()
    worst_duration = duration_analysis['Avg_PnL'].idxmin()

    recommendations.append(f"1. 🎯 OPTIMIZAR DURACIÓN:")
    recommendations.append(f"   ✅ Favorecer trades de duración: {best_duration}")
    recommendations.append(f"   ❌ Evitar trades de duración: {worst_duration}")

    # 2. Recomendaciones de confidence
    if df['confidence'].corr(df['pnl']) < 0.1:
        recommendations.append(f"2. 🎯 CALIBRAR CONFIDENCE:")
        recommendations.append(f"   ⚠️  Sistema de confidence no es predictivo")
        recommendations.append(f"   💡 Revisar cálculo de confidence en estrategias")

    # 3. Recomendaciones temporales
    best_hour = temporal_analysis['hourly']['Avg_PnL'].idxmax()
    worst_hour = temporal_analysis['hourly']['Avg_PnL'].idxmin()

    recommendations.append(f"3. 🎯 OPTIMIZAR HORARIOS:")
    recommendations.append(f"   ✅ Mejor hora para operar: {best_hour}:00")
    recommendations.append(f"   ❌ Evitar hora: {worst_hour}:00")

    # 4. Análisis de patrones en peores trades
    worst_strategy = worst_trades['strategy'].mode().iloc[0]
    worst_context = worst_trades['market_context'].mode().iloc[0]

    recommendations.append(f"4. 🎯 FILTROS ESPECÍFICOS:")
    recommendations.append(f"   ⚠️  Revisar {worst_strategy} en contexto {worst_context}")
    recommendations.append(f"   💡 Añadir filtros para trades con duración <{worst_trades['duration_minutes'].mean():.0f}min")

    # 5. Win rate general
    overall_wr = len(winners) / len(df) * 100
    if overall_wr < 50:
        recommendations.append(f"5. 🎯 MEJORAR WIN RATE ({overall_wr:.1f}%):")
        recommendations.append(f"   💡 Aumentar selectividad en entrada")
        recommendations.append(f"   💡 Mejorar gestión de salidas")

    print("\n".join(recommendations))

    # Guardar recomendaciones
    with open('real_trade_recommendations.txt', 'w') as f:
        f.write("RECOMENDACIONES BASADAS EN ANÁLISIS DE TRADES REALES\n")
        f.write("=" * 60 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Trades analizados: {len(df)}\n\n")
        f.write("\n".join(recommendations))

    print(f"\n📁 Recomendaciones guardadas en: real_trade_recommendations.txt")

if __name__ == "__main__":
    analyze_real_trades()