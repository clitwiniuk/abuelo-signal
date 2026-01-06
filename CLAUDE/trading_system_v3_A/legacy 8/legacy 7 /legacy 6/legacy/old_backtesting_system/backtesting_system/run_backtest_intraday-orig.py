#!/usr/bin/env python3
"""
Script para Ejecutar Backtests INTRADAY

Ejecuta backtests usando datos intraday (1min) desde tabla trade_intraday_bars
con datos reales de trading_data.db
"""

import sys
import os
import logging
from datetime import datetime

# Agregar directorio del backtesting system al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.backtest_engine import BacktestEngine
from config.backtest_config import BACKTEST_CONFIG


def main():
    """Función principal"""
    print("🚀 Iniciando Sistema de Backtesting INTRADAY (1min)")
    print("=" * 60)

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    try:
        # Crear motor de backtesting
        engine = BacktestEngine()

        # Agregar estrategia Daily Plays
        print("📊 Agregando estrategia Daily Plays...")
        engine.add_strategy('daily_plays',
                           buy_threshold=6.00,  # Ajustado para datos reales
                           sell_threshold=6.80,  # Ajustado para datos reales
                           max_position_size=0.05)

        # Símbolos con datos intraday disponibles
        symbols = ['LAES', 'HIVE', 'NUAI', 'RR', 'IONZ']
        print(f"📈 Cargando datos INTRADAY para: {symbols}")

        # IMPORTANTE: Cargar datos con data_type='intraday'
        engine.load_data(symbols, data_type='intraday')

        # Ejecutar backtest
        print("⚡ Ejecutando backtest INTRADAY...")
        start_time = datetime.now()

        results = engine.run_backtest()

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Generar y mostrar reporte
        print("\n" + "=" * 60)
        print("📋 RESULTADOS DEL BACKTEST INTRADAY")
        print("=" * 60)

        report = engine.generate_report(results)
        print(report)

        print(f"\n⏱️  Tiempo de ejecución: {execution_time:.2f} segundos")
        print("✅ Backtest INTRADAY completado exitosamente!")

        # Mostrar resultados detallados
        print(f"\n📊 RESULTADOS DETALLADOS:")
        print(f"   Capital Inicial: ${results.get('initial_capital', 0):,.0f}")
        print(f"   Valor Final: ${results.get('final_value', 0):,.0f}")
        print(f"   Retorno Total: ${results.get('total_return', 0):,.2f}")
        print(f"   Retorno %: {results.get('total_return_pct', 0):.2f}%")

        # Mostrar resultados por estrategia
        strategy_results = results.get('strategy_results', [])
        if strategy_results:
            print(f"\n📈 RESULTADOS POR ESTRATEGIA:")
            for strat in strategy_results:
                print(f"   {strat.get('strategy_name', 'Unknown')}:")
                print(f"     Trades: {strat.get('total_trades', 0)}")
                print(f"     Win Rate: {strat.get('win_rate', 0):.1f}%")
                print(f"     PnL Total: ${strat.get('total_pnl', 0):.2f}")
                print(f"     PnL Promedio: ${strat.get('avg_pnl', 0):.2f}")

    except Exception as e:
        print(f"❌ Error durante el backtest INTRADAY: {e}")
        logging.exception("Backtest failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
