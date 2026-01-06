#!/usr/bin/env python3
"""
Análisis de Timing Proactivo - Detectar señales tempranas
Identifica qué condiciones previas tenían los trades exitosos vs fallidos
para construir un sistema de timing proactivo en lugar de reactivo
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

def analyze_timing_patterns():
    """Analizar patrones de timing para detectar señales tempranas"""

    print("🎯 ANÁLISIS DE TIMING PROACTIVO")
    print("=" * 60)
    print("Objetivo: Encontrar señales ANTES del movimiento, no después")
    print()

    # Conectar a la base de datos
    conn = sqlite3.connect('trading_data.db')

    # Cargar trades con más detalle de market data
    query = """
    SELECT
        trade_id, symbol, strategy, entry_time, exit_time,
        duration_minutes, pnl, confidence,
        entry_price, exit_price,
        recent_high_5d, recent_low_5d, recent_avg_price,
        price_momentum, volume_trend, relative_position,
        symbol_strength, market_context,
        actual_entry_price, entry_slippage_pct
    FROM trades
    WHERE status = 'CLOSED'
    AND duration_minutes IS NOT NULL
    ORDER BY entry_time DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    print(f"📊 Analizando {len(df)} trades para patrones de timing")

    # Clasificar trades por éxito y timing
    df['success_category'] = pd.cut(df['pnl'],
                                   bins=[-float('inf'), -10, 0, 10, float('inf')],
                                   labels=['Gran_Pérdida', 'Pérdida_Pequeña', 'Ganancia_Pequeña', 'Gran_Ganancia'])

    df['timing_category'] = pd.cut(df['duration_minutes'],
                                  bins=[0, 30, 120, 240, float('inf')],
                                  labels=['Rápido_Malo', 'Medio', 'Lento_Bueno', 'Muy_Lento'])

    print("\n🔍 ANÁLISIS 1: CONDICIONES DE ENTRADA PRE-TRADE")
    print("-" * 50)

    analyze_pre_entry_conditions(df)

    print("\n🔍 ANÁLISIS 2: RELATIVE POSITION PATTERNS")
    print("-" * 50)

    analyze_relative_position_timing(df)

    print("\n🔍 ANÁLISIS 3: VOLUME MOMENTUM PATTERNS")
    print("-" * 50)

    analyze_volume_momentum_timing(df)

    print("\n🔍 ANÁLISIS 4: PRICE ACTION SETUP ANALYSIS")
    print("-" * 50)

    analyze_price_action_setups(df)

    print("\n🔍 ANÁLISIS 5: SÍNTESIS - SEÑALES TEMPRANAS GANADORAS")
    print("-" * 50)

    synthesize_early_signals(df)

def analyze_pre_entry_conditions(df):
    """Analizar condiciones antes de la entrada"""

    # Trades exitosos vs fallidos - condiciones de entrada
    winners = df[df['pnl'] > 10]  # Ganancias significativas
    losers = df[df['pnl'] < -10]  # Pérdidas significativas

    print(f"🏆 Trades exitosos (P&L > $10): {len(winners)}")
    print(f"💸 Trades fallidos (P&L < -$10): {len(losers)}")

    # Comparar condiciones de entrada
    conditions = ['price_momentum', 'volume_trend', 'relative_position', 'symbol_strength']

    print("\n📊 CONDICIONES DE ENTRADA - Promedio:")
    print("Condición          | Ganadores | Perdedores | Diferencia")
    print("-" * 55)

    insights = []
    for condition in conditions:
        if condition in df.columns:
            winner_avg = winners[condition].mean()
            loser_avg = losers[condition].mean()
            diff = winner_avg - loser_avg

            print(f"{condition:18} | {winner_avg:8.3f} | {loser_avg:9.3f} | {diff:+8.3f}")

            # Identificar diferencias significativas
            if abs(diff) > 0.1:  # Umbral de significancia
                direction = "MAYOR" if diff > 0 else "MENOR"
                insights.append(f"   ✅ Trades exitosos tienen {condition} {direction} ({diff:+.3f})")

    if insights:
        print("\n🎯 INSIGHTS DE TIMING:")
        for insight in insights:
            print(insight)
    else:
        print("\n⚠️  No se encontraron diferencias significativas en condiciones básicas")

def analyze_relative_position_timing(df):
    """Analizar timing basado en posición relativa del precio"""

    # relative_position: 0 = en mínimos, 0.5 = medio, 1 = en máximos

    # Categorizar por relative_position
    df['position_category'] = pd.cut(df['relative_position'],
                                    bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0],
                                    labels=['Muy_Bajo', 'Bajo', 'Medio', 'Alto', 'Muy_Alto'])

    position_analysis = df.groupby('position_category').agg({
        'pnl': ['count', 'mean'],
        'duration_minutes': 'mean'
    }).round(2)

    position_analysis.columns = ['Trades', 'Avg_PnL', 'Avg_Duration']
    position_analysis = position_analysis.dropna()

    print("Rendimiento por posición relativa en rango:")
    print(position_analysis)

    # Identificar el sweet spot
    if not position_analysis.empty:
        best_position = position_analysis['Avg_PnL'].idxmax()
        worst_position = position_analysis['Avg_PnL'].idxmin()

        print(f"\n🎯 TIMING INSIGHT:")
        print(f"   ✅ Mejor timing: Entrar cuando precio está en posición {best_position}")
        print(f"   ❌ Peor timing: Evitar entrar cuando precio está en posición {worst_position}")

        # Análisis específico de trades exitosos largos
        long_winners = df[(df['pnl'] > 5) & (df['duration_minutes'] > 120)]
        if len(long_winners) > 0:
            avg_rel_pos = long_winners['relative_position'].mean()
            print(f"   📊 Trades largos exitosos: posición relativa promedio = {avg_rel_pos:.3f}")

def analyze_volume_momentum_timing(df):
    """Analizar timing basado en momentum de volumen"""

    # volume_trend: >1 = volumen creciente, <1 = volumen decreciente

    # Categorizar volume trend
    df['volume_category'] = pd.cut(df['volume_trend'],
                                  bins=[0, 0.8, 1.0, 1.2, 1.5, float('inf')],
                                  labels=['Muy_Bajo', 'Bajo', 'Normal', 'Alto', 'Muy_Alto'])

    volume_analysis = df.groupby('volume_category').agg({
        'pnl': ['count', 'mean'],
        'duration_minutes': 'mean'
    }).round(2)

    volume_analysis.columns = ['Trades', 'Avg_PnL', 'Avg_Duration']
    volume_analysis = volume_analysis.dropna()

    print("Rendimiento por momentum de volumen:")
    print(volume_analysis)

    # Correlación directa volume_trend vs pnl
    correlation = df['volume_trend'].corr(df['pnl'])
    print(f"\n📊 Correlación volume_trend vs P&L: {correlation:.3f}")

    if correlation > 0.1:
        print("   ✅ Volume momentum predice resultados positivamente")
    elif correlation < -0.1:
        print("   ❌ Volume momentum alta es mala señal")
    else:
        print("   ⚠️  Volume momentum no es predictivo")

def analyze_price_action_setups(df):
    """Analizar setups de price action"""

    # Crear métricas de setup basadas en datos disponibles
    df['setup_score'] = 0

    # Setup 1: Precio cerca de soporte (relative_position baja) con volume creciente
    setup1 = (df['relative_position'] < 0.3) & (df['volume_trend'] > 1.1)
    df.loc[setup1, 'setup_score'] += 1

    # Setup 2: Momentum ALTA (CORREGIDO basado en datos reales)
    setup2 = df['price_momentum'] > 0.871  # Threshold desde análisis de timing
    df.loc[setup2, 'setup_score'] += 1

    # Setup 3: Symbol strength BAJA (CORREGIDO basado en datos reales)
    setup3 = df['symbol_strength'] < 0.111  # Threshold desde análisis de timing
    df.loc[setup3, 'setup_score'] += 1

    # Setup 4: Precio cerca del promedio (no extendido)
    df['price_vs_avg'] = (df['entry_price'] - df['recent_avg_price']) / df['recent_avg_price']
    setup4 = abs(df['price_vs_avg']) < 0.02  # Dentro del 2% del promedio
    df.loc[setup4, 'setup_score'] += 1

    setup_analysis = df.groupby('setup_score').agg({
        'pnl': ['count', 'mean'],
        'duration_minutes': 'mean'
    }).round(2)

    setup_analysis.columns = ['Trades', 'Avg_PnL', 'Avg_Duration']

    print("Rendimiento por score de setup:")
    print(setup_analysis)

    # Encontrar el setup score óptimo
    if len(setup_analysis) > 1:
        best_setup = setup_analysis['Avg_PnL'].idxmax()
        print(f"\n🎯 SETUP ÓPTIMO:")
        print(f"   ✅ Score de setup: {best_setup}")
        print(f"   📊 P&L promedio: ${setup_analysis.loc[best_setup, 'Avg_PnL']:.2f}")

        # Desglose del mejor setup
        best_trades = df[df['setup_score'] == best_setup]
        print(f"\n🔍 Características del setup {best_setup}:")
        print(f"   • Posición relativa promedio: {best_trades['relative_position'].mean():.3f}")
        print(f"   • Volume trend promedio: {best_trades['volume_trend'].mean():.3f}")
        print(f"   • Price momentum promedio: {best_trades['price_momentum'].mean():.3f}")

def synthesize_early_signals(df):
    """Sintetizar señales tempranas para sistema proactivo"""

    # Definir trades realmente exitosos (largo plazo + profit)
    excellent_trades = df[(df['pnl'] > 15) & (df['duration_minutes'] > 120)]
    poor_trades = df[(df['pnl'] < -10) & (df['duration_minutes'] < 60)]

    print(f"🏆 Trades excelentes: {len(excellent_trades)} (P&L > $15, duración > 120min)")
    print(f"💸 Trades pobres: {len(poor_trades)} (P&L < -$10, duración < 60min)")

    if len(excellent_trades) > 0 and len(poor_trades) > 0:
        print("\n📊 PERFIL DE TRADES EXCELENTES vs POBRES:")
        print("Métrica               | Excelentes | Pobres    | Diferencia")
        print("-" * 60)

        metrics = ['relative_position', 'volume_trend', 'price_momentum', 'symbol_strength']
        early_signals = []

        for metric in metrics:
            if metric in df.columns:
                excellent_avg = excellent_trades[metric].mean()
                poor_avg = poor_trades[metric].mean()
                diff = excellent_avg - poor_avg

                print(f"{metric:20} | {excellent_avg:9.3f} | {poor_avg:8.3f} | {diff:+9.3f}")

                if abs(diff) > 0.15:  # Diferencia significativa
                    direction = "ALTA" if diff > 0 else "BAJA"
                    early_signals.append((metric, direction, diff))

        print("\n🎯 SEÑALES TEMPRANAS IDENTIFICADAS:")
        for signal, direction, strength in early_signals:
            print(f"   ✅ {signal}: Buscar valor {direction} (diferencia: {strength:+.3f})")

        # Crear regla de filtrado proactivo
        print("\n🔧 REGLA DE TIMING PROACTIVO PROPUESTA:")
        print("   Entrar SOLO cuando:")

        for signal, direction, strength in early_signals:
            if direction == "ALTA":
                threshold = poor_trades[signal].mean() + abs(strength) * 0.7
                print(f"   • {signal} > {threshold:.3f}")
            else:
                threshold = poor_trades[signal].mean() - abs(strength) * 0.7
                print(f"   • {signal} < {threshold:.3f}")

        # Verificar efectividad de la regla
        test_rule_effectiveness(df, early_signals, poor_trades)

def test_rule_effectiveness(df, early_signals, poor_trades):
    """Probar efectividad de las reglas identificadas"""

    if not early_signals:
        print("\n⚠️  No se encontraron señales tempranas significativas")
        return

    # Aplicar filtros basados en señales tempranas
    mask = pd.Series([True] * len(df), index=df.index)

    for signal, direction, strength in early_signals:
        if direction == "ALTA":
            threshold = poor_trades[signal].mean() + abs(strength) * 0.7
            mask &= (df[signal] > threshold)
        else:
            threshold = poor_trades[signal].mean() - abs(strength) * 0.7
            mask &= (df[signal] < threshold)

    filtered_trades = df[mask]

    if len(filtered_trades) > 0:
        original_wr = (df['pnl'] > 0).mean() * 100
        filtered_wr = (filtered_trades['pnl'] > 0).mean() * 100
        original_avg_pnl = df['pnl'].mean()
        filtered_avg_pnl = filtered_trades['pnl'].mean()

        print(f"\n🧪 EFECTIVIDAD DEL FILTRO PROACTIVO:")
        print(f"   📊 Trades originales: {len(df)} | Win rate: {original_wr:.1f}% | Avg P&L: ${original_avg_pnl:.2f}")
        print(f"   ✅ Trades filtrados: {len(filtered_trades)} | Win rate: {filtered_wr:.1f}% | Avg P&L: ${filtered_avg_pnl:.2f}")
        print(f"   📈 Mejora win rate: {filtered_wr - original_wr:+.1f}%")
        print(f"   💰 Mejora P&L: ${filtered_avg_pnl - original_avg_pnl:+.2f}")

        if filtered_wr > original_wr + 5:  # Mejora significativa
            print(f"\n🎉 FILTRO PROACTIVO EFECTIVO!")
            print(f"   ✅ Rechaza trades malos y mejora resultados")
        else:
            print(f"\n⚠️  Filtro necesita refinamiento")
    else:
        print(f"\n❌ Filtro demasiado estricto - no quedan trades")

if __name__ == "__main__":
    analyze_timing_patterns()