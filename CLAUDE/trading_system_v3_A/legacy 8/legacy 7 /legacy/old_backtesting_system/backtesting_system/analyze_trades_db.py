#!/usr/bin/env python3
"""
Análisis Directo de Trades desde Database

Script simplificado que analiza directamente los trades desde trading_data.db
sin necesidad de backtesting framework complejo.
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging


def setup_logging():
    """Configurar logging"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'trade_analysis.log')),
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

        # Sharpe Ratio (asumiendo 2% risk-free rate)
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

    except Exception as e:
        logging.error(f"Error calculating advanced metrics: {e}")
        return {}


def analyze_strategy_from_db(strategy_name: str, db_path: str) -> Dict[str, Any]:
    """
    Analizar estrategia directamente desde la base de datos

    Args:
        strategy_name: Nombre de la estrategia
        db_path: Ruta a la base de datos

    Returns:
        Diccionario con análisis completo
    """
    try:
        logging.info(f"🔍 Analyzing strategy: {strategy_name}")

        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)

        # Obtener trades de la estrategia
        query = """
            SELECT * FROM trades
            WHERE strategy = ? AND pnl IS NOT NULL
            ORDER BY entry_time ASC
        """

        trades_df = pd.read_sql_query(query, conn, params=[strategy_name])

        if trades_df.empty:
            conn.close()
            return {
                'strategy_name': strategy_name,
                'error': f'No trades found for strategy {strategy_name}'
            }

        # Análisis básico
        total_trades = len(trades_df)
        winning_trades = (trades_df['pnl'] > 0).sum()
        losing_trades = (trades_df['pnl'] < 0).sum()
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        total_pnl = trades_df['pnl'].sum()
        avg_pnl = trades_df['pnl'].mean()
        best_trade = trades_df['pnl'].max()
        worst_trade = trades_df['pnl'].min()

        # Análisis por símbolo
        symbol_performance = {}
        for symbol in trades_df['symbol'].unique():
            symbol_trades = trades_df[trades_df['symbol'] == symbol]
            symbol_performance[symbol] = {
                'total_trades': len(symbol_trades),
                'total_pnl': symbol_trades['pnl'].sum(),
                'avg_pnl': symbol_trades['pnl'].mean(),
                'win_rate': (symbol_trades['pnl'] > 0).mean(),
                'best_trade': symbol_trades['pnl'].max(),
                'worst_trade': symbol_trades['pnl'].min()
            }

        # Calcular retornos diarios para métricas avanzadas
        trades_df['entry_date'] = pd.to_datetime(trades_df['entry_time']).dt.date
        daily_pnl = trades_df.groupby('entry_date')['pnl'].sum()

        # Simular capital inicial de $100,000
        capital = 100_000
        daily_returns = daily_pnl / capital

        advanced_metrics = calculate_advanced_metrics(daily_returns)

        conn.close()

        return {
            'strategy_name': strategy_name,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'symbol_performance': symbol_performance,
            'advanced_metrics': advanced_metrics,
            'trades_df': trades_df,  # Agregar DataFrame completo
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
        report.append("📊 ANÁLISIS COMPLETO DE ESTRATEGIAS - BASE DE DATOS")
        report.append("=" * 80)
        report.append("")

        # Resumen ejecutivo
        report.append("🎯 RESUMEN EJECUTIVO")
        report.append("-" * 50)

        strategy_summary = []
        for strategy_name, results in all_results.items():
            if 'error' in results:
                continue

            total_pnl = results.get('total_pnl', 0)
            win_rate = results.get('win_rate', 0)
            total_trades = results.get('total_trades', 0)
            advanced = results.get('advanced_metrics', {})

            strategy_summary.append({
                'name': strategy_name,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'sharpe': advanced.get('sharpe_ratio', 0),
                'max_dd': advanced.get('max_drawdown', 0)
            })

        # Ordenar por PnL total
        strategy_summary.sort(key=lambda x: x['total_pnl'], reverse=True)

        for strat in strategy_summary:
            report.append(f"✅ {strat['name'].upper()}: ${strat['total_pnl']:,.2f} | {strat['win_rate']:.1f}% win | Sharpe: {strat['sharpe']:.2f}")

        report.append("")

        # Análisis detallado por estrategia
        for strategy_name, results in all_results.items():
            if 'error' in results:
                report.append(f"❌ {strategy_name}: Error - {results['error']}")
                continue

            report.append(f"📈 ESTRATEGIA: {strategy_name.upper()}")
            report.append("-" * 50)

            # Estadísticas básicas
            report.append("ESTADÍSTICAS BÁSICAS:")
            report.append(f"  Total Trades: {results.get('total_trades', 0)}")
            report.append(f"  Winning Trades: {results.get('winning_trades', 0)}")
            report.append(f"  Losing Trades: {results.get('losing_trades', 0)}")
            report.append(f"  Win Rate: {results.get('win_rate', 0):.1f}%")
            report.append(f"  Total PnL: ${results.get('total_pnl', 0):.2f}")
            report.append(f"  Avg PnL: ${results.get('avg_pnl', 0):.2f}")
            report.append(f"  Best Trade: ${results.get('best_trade', 0):.2f}")
            report.append(f"  Worst Trade: ${results.get('worst_trade', 0):.2f}")
            report.append("")

            # Métricas avanzadas
            advanced = results.get('advanced_metrics', {})
            if advanced:
                report.append("MÉTRICAS PROFESIONALES:")
                report.append(f"  Total Return: {advanced.get('total_return', 0):.1f}%")
                report.append(f"  Annual Return: {advanced.get('annual_return', 0):.1f}%")
                report.append(f"  Annual Volatility: {advanced.get('annual_volatility', 0):.1f}%")
                report.append(f"  Sharpe Ratio: {advanced.get('sharpe_ratio', 0):.2f}")
                report.append(f"  Max Drawdown: {advanced.get('max_drawdown', 0):.1f}%")
                report.append(f"  Calmar Ratio: {advanced.get('calmar_ratio', 0):.1f}")
                report.append("")

            # Performance por símbolo (top 5)
            symbol_perf = results.get('symbol_performance', {})
            if symbol_perf:
                report.append("TOP 5 SÍMBOLOS:")
                # Ordenar por PnL total
                sorted_symbols = sorted(symbol_perf.items(),
                                      key=lambda x: x[1]['total_pnl'], reverse=True)

                for symbol, perf in sorted_symbols[:5]:
                    report.append(f"  {symbol}: ${perf['total_pnl']:.2f} PnL, {perf['win_rate']:.1f}% win ({perf['total_trades']} trades)")
                report.append("")

            # Lista detallada de trades
            report.append("📋 LISTA COMPLETA DE TRADES:")
            trades_df = results.get('trades_df')
            if trades_df is not None and not trades_df.empty:
                trades_df = trades_df.sort_values('entry_time', ascending=False)
                for _, trade in trades_df.iterrows():
                    entry_time = pd.to_datetime(trade['entry_time']).strftime('%Y-%m-%d %H:%M')
                    exit_time = pd.to_datetime(trade['exit_time']).strftime('%Y-%m-%d %H:%M') if pd.notna(trade['exit_time']) else 'OPEN'
                    pnl_color = "🟢" if trade['pnl'] > 0 else "🔴"
                    report.append(f"  {pnl_color} {trade['symbol']} | ${trade['entry_price']:.2f} -> ${trade['exit_price']:.2f} | "
                                 f"PnL: ${trade['pnl']:.2f} | {entry_time} -> {exit_time}")
            report.append("")

        # Recomendaciones
        report.append("🎯 RECOMENDACIONES")
        report.append("-" * 30)

        if strategy_summary:
            best_strategy = strategy_summary[0]
            report.append(f"✅ Mejor estrategia: {best_strategy['name'].upper()}")
            report.append(f"   Total PnL: ${best_strategy['total_pnl']:.2f}")
            report.append(f"   Win Rate: {best_strategy['win_rate']:.1f}%")

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
    print("🚀 Iniciando Análisis Directo de Trades desde DB")
    print("=" * 60)

    setup_logging()

    try:
        # Ruta a la base de datos
        db_path = os.path.join(os.path.dirname(__file__), '..', 'trading_data.db')

        if not os.path.exists(db_path):
            print(f"❌ Database not found: {db_path}")
            sys.exit(1)

        # Estrategias a analizar (usando los nombres reales de la DB)
        strategies_to_analyze = ["macdv_smallcaps", "macdv", "daily_plays"]

        all_results = {}

        # Analizar cada estrategia
        for strategy in strategies_to_analyze:
            print(f"📊 Analizando estrategia: {strategy}")
            results = analyze_strategy_from_db(strategy, db_path)
            all_results[strategy] = results

        # Generar reporte completo
        print("📋 Generando reporte completo...")
        report = generate_comprehensive_report(all_results)

        # Guardar reporte
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, 'trade_analysis_report.txt')

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