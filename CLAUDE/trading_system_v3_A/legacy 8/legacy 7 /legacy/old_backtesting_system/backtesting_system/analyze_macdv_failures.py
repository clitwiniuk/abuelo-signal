#!/usr/bin/env python3
"""
Análisis de Fallos MACDV - Por qué falla y cómo mejorarlo

Este script analiza en detalle por qué MACDV tiene rendimientos negativos
y proporciona recomendaciones específicas para mejorarlo.
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import logging


def setup_logging():
    """Configurar logging"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'macdv_analysis.log')),
            logging.StreamHandler()
        ]
    )


def load_macdv_trades(db_path: str) -> pd.DataFrame:
    """
    Cargar todos los trades de MACDV desde la base de datos

    Args:
        db_path: Ruta a la base de datos

    Returns:
        DataFrame con todos los trades MACDV
    """
    conn = sqlite3.connect(db_path)

    query = """
        SELECT * FROM trades
        WHERE strategy LIKE '%macdv%' AND pnl IS NOT NULL
        ORDER BY entry_time ASC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def analyze_macdv_performance(trades_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Análisis detallado del performance de MACDV

    Args:
        trades_df: DataFrame con trades MACDV

    Returns:
        Diccionario con análisis detallado
    """
    analysis = {}

    # Estadísticas básicas
    analysis['total_trades'] = len(trades_df)
    analysis['total_pnl'] = trades_df['pnl'].sum()
    analysis['avg_pnl'] = trades_df['pnl'].mean()
    analysis['win_rate'] = (trades_df['pnl'] > 0).mean()
    analysis['best_trade'] = trades_df['pnl'].max()
    analysis['worst_trade'] = trades_df['pnl'].min()

    # Análisis por estrategia
    strategy_performance = {}
    for strategy in trades_df['strategy'].unique():
        strategy_trades = trades_df[trades_df['strategy'] == strategy]
        strategy_performance[strategy] = {
            'trades': len(strategy_trades),
            'total_pnl': strategy_trades['pnl'].sum(),
            'avg_pnl': strategy_trades['pnl'].mean(),
            'win_rate': (strategy_trades['pnl'] > 0).mean(),
            'best_trade': strategy_trades['pnl'].max(),
            'worst_trade': strategy_trades['pnl'].min()
        }

    analysis['strategy_performance'] = strategy_performance

    # Análisis temporal
    trades_df['entry_date'] = pd.to_datetime(trades_df['entry_time']).dt.date
    daily_pnl = trades_df.groupby('entry_date')['pnl'].sum()

    analysis['daily_stats'] = {
        'total_days': len(daily_pnl),
        'profitable_days': (daily_pnl > 0).sum(),
        'daily_win_rate': (daily_pnl > 0).mean(),
        'avg_daily_pnl': daily_pnl.mean(),
        'best_day': daily_pnl.max(),
        'worst_day': daily_pnl.min()
    }

    # Análisis por símbolo
    symbol_performance = {}
    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol]
        symbol_performance[symbol] = {
            'trades': len(symbol_trades),
            'total_pnl': symbol_trades['pnl'].sum(),
            'avg_pnl': symbol_trades['pnl'].mean(),
            'win_rate': (symbol_trades['pnl'] > 0).mean()
        }

    # Top 10 símbolos por PnL
    top_symbols = sorted(symbol_performance.items(),
                        key=lambda x: x[1]['total_pnl'], reverse=True)[:10]
    analysis['top_symbols'] = dict(top_symbols)

    # Bottom 10 símbolos por PnL
    bottom_symbols = sorted(symbol_performance.items(),
                           key=lambda x: x[1]['total_pnl'])[:10]
    analysis['bottom_symbols'] = dict(bottom_symbols)

    # Análisis de frecuencia de trading
    trades_df['entry_hour'] = pd.to_datetime(trades_df['entry_time']).dt.hour
    hourly_distribution = trades_df.groupby('entry_hour').size()
    analysis['hourly_distribution'] = hourly_distribution.to_dict()

    # Análisis de tamaño de posición
    analysis['position_sizes'] = {
        'avg_quantity': trades_df['quantity'].mean(),
        'min_quantity': trades_df['quantity'].min(),
        'max_quantity': trades_df['quantity'].max(),
        'median_quantity': trades_df['quantity'].median()
    }

    return analysis


def analyze_macdv_problems(trades_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analizar problemas específicos de MACDV

    Args:
        trades_df: DataFrame con trades MACDV

    Returns:
        Diccionario con problemas identificados
    """
    problems = {}

    # 1. Análisis de consecutivas pérdidas
    trades_df = trades_df.sort_values('entry_time')
    pnl_series = (trades_df['pnl'] > 0).astype(int)

    # Encontrar rachas de pérdidas
    loss_streaks = []
    current_streak = 0

    for pnl in pnl_series:
        if pnl == 0:  # Pérdida
            current_streak += 1
        else:
            if current_streak > 0:
                loss_streaks.append(current_streak)
            current_streak = 0

    if current_streak > 0:
        loss_streaks.append(current_streak)

    problems['loss_streaks'] = {
        'max_streak': max(loss_streaks) if loss_streaks else 0,
        'avg_streak': np.mean(loss_streaks) if loss_streaks else 0,
        'total_streaks': len(loss_streaks)
    }

    # 2. Análisis de recovery (días para recuperar pérdidas)
    trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
    max_drawdown_points = []

    peak = trades_df['cumulative_pnl'].iloc[0]
    for pnl in trades_df['cumulative_pnl']:
        if pnl > peak:
            peak = pnl
        drawdown = peak - pnl
        if drawdown > 0:
            max_drawdown_points.append(drawdown)

    problems['drawdown_analysis'] = {
        'max_drawdown': max(max_drawdown_points) if max_drawdown_points else 0,
        'avg_drawdown': np.mean(max_drawdown_points) if max_drawdown_points else 0,
        'drawdown_periods': len(max_drawdown_points)
    }

    # 3. Análisis por contexto de mercado
    context_performance = {}
    for context in trades_df['market_context'].unique():
        if pd.isna(context):
            continue
        context_trades = trades_df[trades_df['market_context'] == context]
        context_performance[context] = {
            'trades': len(context_trades),
            'win_rate': (context_trades['pnl'] > 0).mean(),
            'avg_pnl': context_trades['pnl'].mean(),
            'total_pnl': context_trades['pnl'].sum()
        }

    problems['context_performance'] = context_performance

    # 4. Análisis de confidence vs performance
    confidence_bins = pd.cut(trades_df['strategy_confidence'],
                           bins=[0, 30, 50, 70, 100],
                           labels=['Very Low', 'Low', 'Medium', 'High'])

    confidence_performance = {}
    for bin_name in confidence_bins.unique():
        bin_trades = trades_df[confidence_bins == bin_name]
        confidence_performance[str(bin_name)] = {
            'trades': len(bin_trades),
            'win_rate': (bin_trades['pnl'] > 0).mean(),
            'avg_pnl': bin_trades['pnl'].mean()
        }

    problems['confidence_performance'] = confidence_performance

    return problems


def generate_macdv_improvements(analysis: Dict[str, Any], problems: Dict[str, Any]) -> List[str]:
    """
    Generar recomendaciones específicas para mejorar MACDV

    Args:
        analysis: Análisis de performance
        problems: Problemas identificados

    Returns:
        Lista de recomendaciones
    """
    improvements = []

    # Basado en win rate bajo
    if analysis['win_rate'] < 0.5:
        improvements.append("🚨 CRÍTICO: Win rate muy bajo (45%). Revisar lógica de entrada.")
        improvements.append("   • Implementar filtros más estrictos de confirmación")
        improvements.append("   • Agregar validación de volumen mínimo")
        improvements.append("   • Mejorar timing de entradas")

    # Basado en drawdown alto
    if problems['drawdown_analysis']['max_drawdown'] > 100:
        improvements.append("⚠️ ALTO DRAWDOWN: Drawdown máximo muy alto.")
        improvements.append("   • Implementar stop losses más agresivos")
        improvements.append("   • Reducir tamaño de posición en señales débiles")
        improvements.append("   • Agregar take profit parcial")

    # Basado en rachas de pérdidas
    if problems['loss_streaks']['max_streak'] > 5:
        improvements.append("🔄 MUCHAS PÉRDIDAS CONSECUTIVAS: Sistema en modo 'perdedor'")
        improvements.append("   • Implementar circuit breaker después de 3 pérdidas")
        improvements.append("   • Reducir exposición después de rachas perdedoras")
        improvements.append("   • Revisar si el setup MACD funciona en small caps")

    # Basado en performance por contexto
    context_perf = problems['context_performance']
    bad_contexts = [ctx for ctx, perf in context_perf.items() if perf['win_rate'] < 0.4]

    if bad_contexts:
        improvements.append(f"📊 MAL PERFORMANCE EN CONTEXTOS: {', '.join(bad_contexts)}")
        improvements.append("   • Evitar operar MACDV en mercados laterales (RANGE)")
        improvements.append("   • Solo operar en TREND contexts con alta convicción")

    # Basado en confidence
    conf_perf = problems['confidence_performance']
    low_conf = [level for level, perf in conf_perf.items() if perf['win_rate'] < 0.4]

    if low_conf:
        improvements.append(f"🎯 BAJA CONFIANZA: Niveles {', '.join(low_conf)} tienen win rate <40%")
        improvements.append("   • No operar señales con confidence <60")
        improvements.append("   • Re-calibrar el sistema de confidence scoring")

    # Recomendaciones generales
    improvements.extend([
        "",
        "🛠️ RECOMENDACIONES GENERALES PARA MACDV:",
        "   1. Comparar con Daily Plays exitoso - ¿qué hace diferente?",
        "   2. Implementar backtesting walk-forward para evitar overfitting",
        "   3. Agregar más indicadores de confirmación (RSI, volumen)",
        "   4. Considerar si MACD es adecuado para small caps volátiles",
        "   5. Implementar money management dinámico basado en racha",
        "   6. Probar diferentes parámetros MACD (12,26,9 vs otros)",
        "   7. Agregar filtro de gap para evitar entradas post-gap",
        "   8. Implementar trailing stops para proteger ganancias"
    ])

    return improvements


def generate_macdv_report(analysis: Dict[str, Any], problems: Dict[str, Any],
                         improvements: List[str]) -> str:
    """
    Generar reporte completo de análisis MACDV

    Args:
        analysis: Análisis de performance
        problems: Problemas identificados
        improvements: Recomendaciones de mejora

    Returns:
        String con reporte completo
    """
    report = []
    report.append("=" * 80)
    report.append("🔍 ANÁLISIS DETALLADO DE FALLOS MACDV")
    report.append("=" * 80)
    report.append("")

    # Resumen ejecutivo
    report.append("📊 RESUMEN EJECUTIVO")
    report.append("-" * 40)
    report.append(f"Total Trades: {analysis['total_trades']}")
    report.append("2.2f")
    report.append("2.2f")
    report.append("2.1f")
    report.append("2.2f")
    report.append("2.2f")
    report.append("")

    # Performance por estrategia
    report.append("📈 PERFORMANCE POR ESTRATEGIA MACDV")
    report.append("-" * 40)

    for strategy, perf in analysis['strategy_performance'].items():
        report.append(f"{strategy.upper()}:")
        report.append(f"  Trades: {perf['trades']}")
        report.append("2.2f")
        report.append("2.2f")
        report.append("2.1f")
        report.append("")

    # Estadísticas diarias
    daily = analysis['daily_stats']
    report.append("📅 ESTADÍSTICAS DIARIAS")
    report.append("-" * 30)
    report.append(f"Días totales: {daily['total_days']}")
    report.append(f"Días profitables: {daily['profitable_days']}")
    report.append("2.1f")
    report.append("2.2f")
    report.append("2.2f")
    report.append("2.2f")
    report.append("")

    # Top símbolos
    report.append("🏆 TOP 5 SÍMBOLOS")
    report.append("-" * 20)

    for i, (symbol, perf) in enumerate(list(analysis['top_symbols'].items())[:5], 1):
        report.append("2.0f"
                     "2.2f"
                     "2.1f")
    report.append("")

    # Bottom símbolos
    report.append("❌ BOTTOM 5 SÍMBOLOS")
    report.append("-" * 22)

    for i, (symbol, perf) in enumerate(list(analysis['bottom_symbols'].items())[:5], 1):
        report.append("2.0f"
                     "2.2f"
                     "2.1f")
    report.append("")

    # Problemas identificados
    report.append("🚨 PROBLEMAS CRÍTICOS IDENTIFICADOS")
    report.append("-" * 40)

    streaks = problems['loss_streaks']
    report.append(f"🔄 Rachas de Pérdidas:")
    report.append(f"   Máxima racha: {streaks['max_streak']} trades")
    report.append("2.1f")
    report.append(f"   Total rachas: {streaks['total_streaks']}")
    report.append("")

    dd = problems['drawdown_analysis']
    report.append(f"📉 Drawdown Analysis:")
    report.append("2.2f")
    report.append("2.2f")
    report.append(f"   Períodos de drawdown: {dd['drawdown_periods']}")
    report.append("")

    # Performance por contexto
    report.append("🌍 PERFORMANCE POR CONTEXTO DE MERCADO")
    report.append("-" * 45)

    for context, perf in problems['context_performance'].items():
        report.append(f"{context}: {perf['trades']} trades")
        report.append("2.1f")
        report.append("2.2f")
        report.append("")

    # Performance por confidence
    report.append("🎯 PERFORMANCE POR NIVEL DE CONFIANZA")
    report.append("-" * 42)

    for level, perf in problems['confidence_performance'].items():
        report.append(f"{level}: {perf['trades']} trades")
        report.append("2.1f")
        report.append("2.2f")
        report.append("")

    # Recomendaciones
    report.append("🛠️ RECOMENDACIONES PARA MEJORAR MACDV")
    report.append("-" * 40)

    for improvement in improvements:
        report.append(improvement)

    report.append("")
    report.append("=" * 80)

    return "\n".join(report)


def main():
    """Función principal"""
    print("🔍 Iniciando Análisis Detallado de Fallos MACDV")
    print("=" * 60)

    setup_logging()

    try:
        # Ruta a la base de datos
        db_path = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/trading_data.db'

        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            sys.exit(1)

        print("📊 Cargando trades MACDV...")
        trades_df = load_macdv_trades(db_path)

        if trades_df.empty:
            print("❌ No MACDV trades found")
            sys.exit(1)

        print(f"✅ Loaded {len(trades_df)} MACDV trades")

        # Análisis de performance
        print("📈 Analizando performance...")
        analysis = analyze_macdv_performance(trades_df)

        # Análisis de problemas
        print("🚨 Identificando problemas...")
        problems = analyze_macdv_problems(trades_df)

        # Generar mejoras
        print("🛠️ Generando recomendaciones...")
        improvements = generate_macdv_improvements(analysis, problems)

        # Generar reporte
        print("📋 Generando reporte completo...")
        report = generate_macdv_report(analysis, problems, improvements)

        # Guardar reporte
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, 'macdv_failure_analysis.txt')

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        # Mostrar reporte
        print("\n" + "=" * 60)
        print("📋 REPORTE DE ANÁLISIS MACDV")
        print("=" * 60)
        print(report)

        print("\n✅ Análisis completado exitosamente!")
        print(f"📄 Reporte guardado en: {report_file}")

    except Exception as e:
        print(f"❌ Error durante el análisis: {e}")
        logging.exception("MACDV analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()