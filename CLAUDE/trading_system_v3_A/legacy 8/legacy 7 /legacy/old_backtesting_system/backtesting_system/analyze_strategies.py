#!/usr/bin/env python3
"""
Análisis Avanzado de Estrategias con Métricas Profesionales

Este script ejecuta backtests completos para todas las estrategias
y genera métricas profesionales como Sharpe, Calmar, drawdown, etc.
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any
import pandas as pd
import numpy as np

# Agregar directorio del backtesting system al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.backtest_engine import BacktestEngine
from config.backtest_config import BACKTEST_CONFIG, STRATEGY_CONFIGS
from data.ibkr_data_feed import DataManager


def setup_logging():
    """Configurar logging para el análisis"""
    # Crear directorio de logs si no existe
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'strategy_analysis.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def calculate_advanced_metrics(returns: pd.Series) -> Dict[str, float]:
    """
    Calcular métricas profesionales de rendimiento

    Args:
        returns: Serie de retornos diarios

    Returns:
        Diccionario con métricas calculadas
    """
    try:
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

        # Sharpe Ratio (asumiendo 2% risk-free rate)
        risk_free_rate = 0.02
        if annual_vol > 0:
            sharpe_ratio = (annual_return - risk_free_rate) / annual_vol
        else:
            sharpe_ratio = 0

        # Sortino Ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_vol = downside_returns.std() * np.sqrt(252)
            if downside_vol > 0:
                sortino_ratio = (annual_return - risk_free_rate) / downside_vol
            else:
                sortino_ratio = 0
        else:
            sortino_ratio = float('inf') if annual_return > risk_free_rate else 0

        # Maximum Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # Calmar Ratio
        if max_drawdown < 0:
            calmar_ratio = annual_return / abs(max_drawdown)
        else:
            calmar_ratio = 0

        # Win Rate (días positivos)
        win_rate = (returns > 0).mean()

        # Profit Factor
        gross_profit = returns[returns > 0].sum()
        gross_loss = abs(returns[returns < 0].sum())
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = float('inf')

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_days': days
        }

    except Exception as e:
        logging.error(f"Error calculating advanced metrics: {e}")
        return {}


def analyze_strategy_performance(strategy_name: str, symbols: List[str] = None) -> Dict[str, Any]:
    """
    Analizar rendimiento completo de una estrategia

    Args:
        strategy_name: Nombre de la estrategia
        symbols: Lista de símbolos (opcional)

    Returns:
        Diccionario con análisis completo
    """
    try:
        logging.info(f"🔍 Analyzing strategy: {strategy_name}")

        # Crear motor de backtesting
        engine = BacktestEngine()

        # Agregar estrategia con parámetros correctos
        if strategy_name == 'daily_plays':
            engine.add_strategy(strategy_name,
                               buy_threshold=6.50,
                               sell_threshold=7.00,
                               max_position_size=0.05)
        elif strategy_name == 'macdv':
            # MACDV necesita parámetros específicos
            engine.add_strategy(strategy_name,
                               fast_period=12,
                               slow_period=26,
                               signal_period=9)
        elif strategy_name == 'momentum_breakout':
            # Momentum breakout parámetros
            engine.add_strategy(strategy_name,
                               lookback_period=20,
                               breakout_threshold=2.0)
        elif strategy_name == 'vwap_breakout':
            # VWAP breakout parámetros
            engine.add_strategy(strategy_name,
                               enable_buy_the_dip=True,
                               dip_pullback_min_pct=0.30)
        else:
            # Para otras estrategias, usar configuración por defecto
            engine.add_strategy(strategy_name)

        # Usar símbolos disponibles o por defecto
        if symbols is None:
            symbols = BACKTEST_CONFIG.small_cap_universe[:10]  # Top 10

        # Cargar datos
        engine.load_data(symbols)

        # Ejecutar backtest
        results = engine.run_backtest()

        # Obtener datos de trades desde la DB para análisis adicional
        try:
            data_manager = DataManager()
            with data_manager:
                trades_df = data_manager.get_trades_data(
                    strategy_filter=[strategy_name],
                    start_date=BACKTEST_CONFIG.start_date,
                    end_date=BACKTEST_CONFIG.end_date
                )
        except Exception as db_error:
            logging.warning(f"Could not connect to database for {strategy_name}: {db_error}")
            trades_df = pd.DataFrame()  # DataFrame vacío

        # Calcular métricas avanzadas si hay datos
        advanced_metrics = {}
        if not trades_df.empty:
            # Convertir a retornos diarios (simplificado)
            trades_df['entry_date'] = pd.to_datetime(trades_df['entry_time']).dt.date
            daily_pnl = trades_df.groupby('entry_date')['pnl'].sum()

            if not daily_pnl.empty:
                # Calcular retornos diarios
                daily_returns = daily_pnl / BACKTEST_CONFIG.initial_capital
                advanced_metrics = calculate_advanced_metrics(daily_returns)

        # Análisis por símbolo
        symbol_performance = {}
        if not trades_df.empty:
            for symbol in symbols:
                try:
                    symbol_trades = trades_df[trades_df['symbol'] == symbol]

                    if not symbol_trades.empty:
                        symbol_performance[symbol] = {
                            'total_trades': len(symbol_trades),
                            'total_pnl': symbol_trades['pnl'].sum(),
                            'avg_pnl': symbol_trades['pnl'].mean(),
                            'win_rate': (symbol_trades['pnl'] > 0).mean(),
                            'best_trade': symbol_trades['pnl'].max(),
                            'worst_trade': symbol_trades['pnl'].min()
                        }
                except Exception as symbol_error:
                    logging.warning(f"Error analyzing symbol {symbol}: {symbol_error}")

        return {
            'strategy_name': strategy_name,
            'backtest_results': results,
            'advanced_metrics': advanced_metrics,
            'symbol_performance': symbol_performance,
            'total_trades_db': len(trades_df) if not trades_df.empty else 0,
            'analysis_timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logging.error(f"Error analyzing strategy {strategy_name}: {e}")
        return {'strategy_name': strategy_name, 'error': str(e)}


def generate_comprehensive_report(all_results: Dict[str, Dict]) -> str:
    """
    Generar reporte completo de todas las estrategias

    Args:
        all_results: Resultados de todas las estrategias

    Returns:
        String con reporte completo
    """
    try:
        report = []
        report.append("=" * 80)
        report.append("📊 ANÁLISIS COMPLETO DE ESTRATEGIAS - MÉTRICAS PROFESIONALES")
        report.append("=" * 80)
        report.append("")

        # Resumen ejecutivo
        report.append("🎯 RESUMEN EJECUTIVO")
        report.append("-" * 50)

        strategy_summary = []
        for strategy_name, results in all_results.items():
            if 'error' in results:
                continue

            metrics = results.get('advanced_metrics', {})
            backtest = results.get('backtest_results', {})

            strategy_summary.append({
                'name': strategy_name,
                'total_return': metrics.get('total_return', 0),
                'sharpe': metrics.get('sharpe_ratio', 0),
                'max_dd': metrics.get('max_drawdown', 0),
                'win_rate': metrics.get('win_rate', 0),
                'total_trades': results.get('total_trades_db', 0)
            })

        # Ordenar por retorno total
        strategy_summary.sort(key=lambda x: x['total_return'], reverse=True)

        for strat in strategy_summary:
            report.append("2.1f"
                         "2.2f"
                         "2.1f"
                         "2.1f")

        report.append("")

        # Análisis detallado por estrategia
        for strategy_name, results in all_results.items():
            if 'error' in results:
                report.append(f"❌ {strategy_name}: Error - {results['error']}")
                continue

            report.append(f"📈 ESTRATEGIA: {strategy_name.upper()}")
            report.append("-" * 50)

            # Métricas avanzadas
            metrics = results.get('advanced_metrics', {})
            if metrics:
                report.append("MÉTRICAS PROFESIONALES:")
                report.append("2.1f")
                report.append("2.1f")
                report.append("2.2f")
                report.append("2.2f")
                report.append("2.2f")
                report.append("2.2f")
                report.append("2.1f")
                report.append("2.2f")
                report.append(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
                report.append(f"  Total Days: {metrics.get('total_days', 0)}")
                report.append("")

            # Resultados del backtest
            backtest = results.get('backtest_results', {})
            if backtest:
                report.append("RESULTADOS BACKTEST:")
                report.append("2.0f")
                report.append("2.0f")
                report.append("2.2f")
                report.append("")

            # Performance por símbolo
            symbol_perf = results.get('symbol_performance', {})
            if symbol_perf:
                report.append("PERFORMANCE POR SÍMBOLO:")
                # Ordenar por PnL total
                sorted_symbols = sorted(symbol_perf.items(),
                                      key=lambda x: x[1]['total_pnl'], reverse=True)

                for symbol, perf in sorted_symbols[:5]:  # Top 5
                    report.append("2.0f"
                                 "2.2f"
                                 "2.1f")
                report.append("")

        # Recomendaciones
        report.append("🎯 RECOMENDACIONES")
        report.append("-" * 30)

        if strategy_summary:
            best_strategy = strategy_summary[0]
            report.append(f"✅ Mejor estrategia: {best_strategy['name'].upper()}")
            report.append(f"   Retorno total: {best_strategy['total_return']:.1%}")
            report.append(f"   Sharpe Ratio: {best_strategy['sharpe']:.2f}")

            # Estrategias con buen Sharpe (>1.0)
            good_sharpe = [s for s in strategy_summary if s['sharpe'] > 1.0]
            if good_sharpe:
                report.append(f"✅ Estrategias con buen Sharpe (>1.0): {len(good_sharpe)}")
                for strat in good_sharpe:
                    report.append(f"   - {strat['name']}: Sharpe {strat['sharpe']:.2f}")

            # Estrategias con alto drawdown (riesgo)
            high_dd = [s for s in strategy_summary if abs(s['max_dd']) > 0.15]  # >15%
            if high_dd:
                report.append(f"⚠️ Estrategias con alto drawdown (>15%): {len(high_dd)}")
                for strat in high_dd:
                    report.append(f"   - {strat['name']}: Drawdown {strat['max_dd']:.1%}")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    except Exception as e:
        logging.error(f"Error generating comprehensive report: {e}")
        return f"Error generating report: {e}"


def main():
    """Función principal"""
    print("🚀 Iniciando Análisis Completo de Estrategias")
    print("=" * 60)

    setup_logging()

    try:
        # Estrategias a analizar - todas las disponibles
        strategies_to_analyze = ['daily_plays', 'macdv', 'momentum_breakout', 'vwap_breakout']

        # Símbolos disponibles (filtrar los que tienen datos)
        available_symbols = ['HIVE', 'ABAT', 'ACHV', 'AIIO', 'AIRE', 'AMDL']

        all_results = {}

        # Analizar cada estrategia
        for strategy in strategies_to_analyze:
            print(f"📊 Analizando estrategia: {strategy}")
            results = analyze_strategy_performance(strategy, available_symbols)
            all_results[strategy] = results

        # Generar reporte completo
        print("📋 Generando reporte completo...")
        report = generate_comprehensive_report(all_results)

        # Guardar reporte
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, 'strategy_analysis_report.txt')

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        # Mostrar reporte
        print("\n" + "=" * 60)
        print("📋 REPORTE DE ANÁLISIS COMPLETO")
        print("=" * 60)
        print(report)

        print("\n✅ Análisis completado exitosamente!")
        print(f"📄 Reporte guardado en: {report_file}")

    except Exception as e:
        print(f"❌ Error durante el análisis: {e}")
        logging.exception("Analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()