#!/usr/bin/env python3
"""
Script Principal para Ejecutar Backtests

Ejecuta backtests usando el sistema híbrido de backtrader
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
from strategies.macdv_bt_strategy import MacdvStrategy
from strategies.momentum_breakout_bt_strategy import MomentumBreakoutStrategy
from strategies.vwap_breakout_bt_strategy import VWAPBreakoutStrategy


def main():
    """Función principal"""
    print("🚀 Iniciando Sistema de Backtesting Híbrido")
    print("=" * 50)

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    try:
        # Crear motor de backtesting
        engine = BacktestEngine()

        # Agregar múltiples estrategias
        print("📊 Agregando estrategias...")
        engine.add_strategy('daily_plays')
        engine.add_strategy('macdv')
        engine.add_strategy('momentum_breakout')
        engine.add_strategy('vwap_breakout')
        engine.add_strategy('rsi_oversold')
        engine.add_strategy('ma_crossover')
        engine.add_strategy('volume_price')

        # Cargar datos para top 5 símbolos
        symbols = BACKTEST_CONFIG.small_cap_universe[:5]
        print(f"📈 Cargando datos para: {symbols}")
        engine.load_data(symbols)

        # Ejecutar backtest
        print("⚡ Ejecutando backtest...")
        start_time = datetime.now()

        results = engine.run_backtest()

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Generar y mostrar reporte
        print("\n" + "=" * 50)
        print("📋 RESULTADOS DEL BACKTEST")
        print("=" * 50)

        report = engine.generate_report(results)
        print(report)

        # Guardar reporte a archivo
        report_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "backtest_report.txt")
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"📄 Reporte guardado en: {report_file}")

        print(f"\n⏱️  Tiempo de ejecución: {execution_time:.2f}s")
        print("✅ Backtest completado exitosamente!")

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
        print(f"❌ Error durante el backtest: {e}")
        logging.exception("Backtest failed")
        sys.exit(1)


if __name__ == "__main__":
    main()