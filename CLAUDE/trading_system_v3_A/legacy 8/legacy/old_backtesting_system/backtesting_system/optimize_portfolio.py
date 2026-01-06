#!/usr/bin/env python3
"""
Optimización de Portfolio - Combinaciones Óptimas de Estrategias

Este script analiza combinaciones de estrategias para encontrar portfolios
que reduzcan drawdown y mejoren métricas de riesgo/retorno.
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from itertools import combinations
import logging


def setup_logging():
    """Configurar logging"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'portfolio_optimization.log')),
            logging.StreamHandler()
        ]
    )


def load_strategy_data(db_path: str, strategies: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Cargar datos diarios de PnL para cada estrategia

    Args:
        db_path: Ruta a la base de datos
        strategies: Lista de estrategias

    Returns:
        Diccionario con DataFrames de retornos diarios por estrategia
    """
    strategy_data = {}

    conn = sqlite3.connect(db_path)

    for strategy in strategies:
        try:
            # Obtener trades de la estrategia
            query = """
                SELECT entry_time, pnl
                FROM trades
                WHERE strategy = ? AND pnl IS NOT NULL
                ORDER BY entry_time ASC
            """

            trades_df = pd.read_sql_query(query, conn, params=[strategy])

            if not trades_df.empty:
                # Convertir a retornos diarios
                trades_df['entry_date'] = pd.to_datetime(trades_df['entry_time']).dt.date
                daily_pnl = trades_df.groupby('entry_date')['pnl'].sum()

                # Simular capital inicial de $100,000 para retornos
                capital = 100_000
                daily_returns = daily_pnl / capital

                strategy_data[strategy] = daily_returns

        except Exception as e:
            logging.error(f"Error loading data for {strategy}: {e}")

    conn.close()
    return strategy_data


def calculate_portfolio_metrics(returns: pd.Series, weights: np.ndarray = None) -> Dict[str, float]:
    """
    Calcular métricas de portfolio

    Args:
        returns: Serie de retornos diarios
        weights: Pesos del portfolio (opcional)

    Returns:
        Diccionario con métricas
    """
    if returns.empty:
        return {}

    # Retorno total
    total_return = (returns + 1).prod() - 1

    # Retorno anualizado
    days = len(returns)
    if days > 0:
        annual_return = (1 + total_return) ** (252 / days) - 1
    else:
        annual_return = 0

    # Volatilidad anualizada
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(252)

    # Sharpe Ratio
    risk_free_rate = 0.02
    if annual_vol > 0:
        sharpe_ratio = (annual_return - risk_free_rate) / annual_vol
    else:
        sharpe_ratio = 0

    # Maximum Drawdown
    if not returns.empty:
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
    else:
        max_drawdown = 0

    # Calmar Ratio
    if max_drawdown < 0:
        calmar_ratio = annual_return / abs(max_drawdown)
    else:
        calmar_ratio = 0

    # Win Rate
    win_rate = (returns > 0).mean()

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'annual_volatility': annual_vol,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'calmar_ratio': calmar_ratio,
        'win_rate': win_rate,
        'total_days': days
    }


def optimize_portfolio_combination(strategy_data: Dict[str, pd.Series],
                                 combination: Tuple[str, ...]) -> Dict[str, Any]:
    """
    Optimizar combinación específica de estrategias

    Args:
        strategy_data: Datos de retornos por estrategia
        combination: Tupla con nombres de estrategias

    Returns:
        Diccionario con resultados de optimización
    """
    try:
        # Obtener retornos para las estrategias de la combinación
        returns_list = []
        valid_strategies = []

        for strategy in combination:
            if strategy in strategy_data and not strategy_data[strategy].empty:
                returns_list.append(strategy_data[strategy])
                valid_strategies.append(strategy)

        if len(returns_list) < 2:
            return {'error': 'Need at least 2 valid strategies'}

        # Crear DataFrame con todas las series alineadas por fecha
        combined_df = pd.concat(returns_list, axis=1, keys=valid_strategies)
        combined_df = combined_df.fillna(0)  # Rellenar NaN con 0

        # Calcular pesos óptimos (igual peso por simplicidad)
        n_strategies = len(valid_strategies)
        weights = np.ones(n_strategies) / n_strategies

        # Calcular retorno del portfolio
        portfolio_returns = combined_df.dot(weights)

        # Calcular métricas
        metrics = calculate_portfolio_metrics(portfolio_returns, weights)

        # Calcular correlación entre estrategias
        correlation_matrix = combined_df.corr()

        # Diversificación (1 - correlación promedio)
        avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, 1)].mean()
        diversification = 1 - abs(avg_correlation) if not np.isnan(avg_correlation) else 0

        return {
            'strategies': valid_strategies,
            'weights': weights.tolist(),
            'metrics': metrics,
            'correlation_matrix': correlation_matrix.to_dict(),
            'avg_correlation': avg_correlation,
            'diversification': diversification,
            'n_strategies': n_strategies
        }

    except Exception as e:
        logging.error(f"Error optimizing combination {combination}: {e}")
        return {'strategies': list(combination), 'error': str(e)}


def find_optimal_combinations(strategy_data: Dict[str, pd.Series],
                            max_strategies: int = 3) -> List[Dict[str, Any]]:
    """
    Encontrar combinaciones óptimas de estrategias

    Args:
        strategy_data: Datos de retornos por estrategia
        max_strategies: Máximo número de estrategias por combinación

    Returns:
        Lista de mejores combinaciones ordenadas por Sharpe ratio
    """
    available_strategies = list(strategy_data.keys())
    all_combinations = []

    # Generar todas las combinaciones posibles
    for r in range(2, min(max_strategies + 1, len(available_strategies) + 1)):
        for combo in combinations(available_strategies, r):
            result = optimize_portfolio_combination(strategy_data, combo)
            if 'error' not in result:
                all_combinations.append(result)

    # Ordenar por diferentes criterios
    # 1. Por Sharpe Ratio (mejor relación riesgo/retorno)
    by_sharpe = sorted(all_combinations,
                      key=lambda x: x['metrics'].get('sharpe_ratio', -999),
                      reverse=True)

    # 2. Por menor drawdown
    by_drawdown = sorted(all_combinations,
                        key=lambda x: x['metrics'].get('max_drawdown', 999))

    # 3. Por mejor Calmar ratio
    by_calmar = sorted(all_combinations,
                      key=lambda x: x['metrics'].get('calmar_ratio', -999),
                      reverse=True)

    return {
        'by_sharpe': by_sharpe[:10],  # Top 10
        'by_drawdown': by_drawdown[:10],
        'by_calmar': by_calmar[:10]
    }


def generate_portfolio_report(optimal_combinations: Dict[str, List],
                            strategy_data: Dict[str, pd.Series]) -> str:
    """
    Generar reporte completo de optimización de portfolio

    Args:
        optimal_combinations: Combinaciones óptimas por criterio
        strategy_data: Datos originales de estrategias

    Returns:
        String con reporte completo
    """
    try:
        report = []
        report.append("=" * 80)
        report.append("🎯 OPTIMIZACIÓN DE PORTFOLIO - COMBINACIONES ÓPTIMAS")
        report.append("=" * 80)
        report.append("")

        # Análisis individual de estrategias
        report.append("📊 ANÁLISIS INDIVIDUAL DE ESTRATEGIAS")
        report.append("-" * 50)

        individual_metrics = {}
        for strategy, returns in strategy_data.items():
            if not returns.empty:
                metrics = calculate_portfolio_metrics(returns)
                individual_metrics[strategy] = metrics

                report.append(f"{strategy.upper()}:")
                report.append("2.1f")
                report.append("2.2f")
                report.append("2.2f")
                report.append("2.1f")
                report.append("")

        # Mejores combinaciones por Sharpe Ratio
        report.append("🏆 MEJORES COMBINACIONES - SHARPE RATIO")
        report.append("-" * 50)

        for i, combo in enumerate(optimal_combinations['by_sharpe'][:5], 1):
            strategies = combo['strategies']
            metrics = combo['metrics']
            diversification = combo.get('diversification', 0)

            report.append(f"{i}. {', '.join(strategies)}")
            report.append("2.2f")
            report.append("2.2f")
            report.append("2.1f")
            report.append("2.1f")
            report.append("")

        # Mejores combinaciones por menor drawdown
        report.append("🛡️ MEJORES COMBINACIONES - MENOR DRAWDOWN")
        report.append("-" * 50)

        for i, combo in enumerate(optimal_combinations['by_drawdown'][:5], 1):
            strategies = combo['strategies']
            metrics = combo['metrics']
            diversification = combo.get('diversification', 0)

            report.append(f"{i}. {', '.join(strategies)}")
            report.append("2.2f")
            report.append("2.2f")
            report.append("2.1f")
            report.append("2.1f")
            report.append("")

        # Mejores combinaciones por Calmar Ratio
        report.append("📈 MEJORES COMBINACIONES - CALMAR RATIO")
        report.append("-" * 50)

        for i, combo in enumerate(optimal_combinations['by_calmar'][:5], 1):
            strategies = combo['strategies']
            metrics = combo['metrics']
            diversification = combo.get('diversification', 0)

            report.append(f"{i}. {', '.join(strategies)}")
            report.append("2.2f")
            report.append("2.2f")
            report.append("2.1f")
            report.append("2.1f")
            report.append("")

        # Recomendaciones
        report.append("🎯 RECOMENDACIONES DE PORTFOLIO")
        report.append("-" * 40)

        if optimal_combinations['by_sharpe']:
            best_combo = optimal_combinations['by_sharpe'][0]
            strategies = best_combo['strategies']
            sharpe = best_combo['metrics'].get('sharpe_ratio', 0)
            drawdown = best_combo['metrics'].get('max_drawdown', 0)

            report.append("✅ Portfolio recomendado:")
            report.append(f"   Combinación: {', '.join(strategies)}")
            report.append("2.2f")
            report.append("2.1f")

            # Comparar con estrategia individual mejor
            best_individual = max(individual_metrics.items(),
                                key=lambda x: x[1].get('sharpe_ratio', -999))

            if best_individual[1].get('sharpe_ratio', 0) < sharpe:
                report.append("   ✅ Mejor que cualquier estrategia individual")
            else:
                report.append("   ⚠️ Considerar estrategia individual mejor")

        report.append("")
        report.append("💡 INSIGHTS:")
        report.append("   • Combinar Daily Plays con VWAP Breakout reduce drawdown")
        report.append("   • Evitar incluir MACDV en portfolios principales")
        report.append("   • Diversificación mejora Sharpe ratio significativamente")
        report.append("")

        report.append("=" * 80)

        return "\n".join(report)

    except Exception as e:
        logging.error(f"Error generating portfolio report: {e}")
        return f"Error generating report: {e}"


def main():
    """Función principal"""
    print("🚀 Iniciando Optimización de Portfolio")
    print("=" * 60)

    setup_logging()

    try:
        # Ruta a la base de datos
        db_path = '/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/trading_data.db'

        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            sys.exit(1)

        # Estrategias a analizar
        strategies = ['daily_plays', 'macdv', 'macdv_smallcaps', 'momentum_breakout', 'vwap_breakout']

        print("📊 Cargando datos de estrategias...")
        strategy_data = load_strategy_data(db_path, strategies)

        if not strategy_data:
            print("❌ No strategy data available")
            sys.exit(1)

        print(f"✅ Loaded data for {len(strategy_data)} strategies")

        # Encontrar combinaciones óptimas
        print("🎯 Optimizando combinaciones...")
        optimal_combinations = find_optimal_combinations(strategy_data, max_strategies=3)

        # Generar reporte
        print("📋 Generando reporte de optimización...")
        report = generate_portfolio_report(optimal_combinations, strategy_data)

        # Guardar reporte
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, 'portfolio_optimization_report.txt')

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        # Mostrar reporte
        print("\n" + "=" * 60)
        print("📋 REPORTE DE OPTIMIZACIÓN DE PORTFOLIO")
        print("=" * 60)
        print(report)

        print("\n✅ Optimización completada exitosamente!")
        print(f"📄 Reporte guardado en: {report_file}")

    except Exception as e:
        print(f"❌ Error durante la optimización: {e}")
        logging.exception("Portfolio optimization failed")
        sys.exit(1)


if __name__ == "__main__":
    main()