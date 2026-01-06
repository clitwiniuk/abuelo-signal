#!/usr/bin/env python3
"""
Script de prueba DEMO para la estrategia OUTLIER_PENNY_STOCK_EXTREME

Este script ejecuta un backtest rápido de la estrategia en modo DEMO
para validar que el worker está funcionando correctamente.

Uso:
    python test_outlier_penny_extreme.py

Estrategia:
- OUTLIER_PENNY_STOCK_EXTREME
- Edge esperado: +11.69% (backtest real en 163 eventos)
- Win rate: 54.6%
- Avg win: +31.43% | Avg loss: -12.05%
- Position size: 1% MAX del capital
- Stop loss: 15% | Take profit: 50%
"""

import sys
import os
import logging
from datetime import datetime, timedelta
import backtrader as bt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.outlier_penny_extreme_bt_strategy import OutlierPennyExtremeStrategy


def run_demo_backtest():
    """
    Ejecutar backtest DEMO de OUTLIER_PENNY_STOCK_EXTREME

    Configuración:
    - Capital inicial: $10,000
    - Periodo: Últimos 60 días de datos disponibles
    - Símbolos: Penny stocks en market_data.db
    - Commission: 0.1% por trade
    """

    logger.info("="*80)
    logger.info("OUTLIER PENNY EXTREME - DEMO BACKTEST")
    logger.info("="*80)

    # Create cerebro instance
    cerebro = bt.Cerebro()

    # Add strategy
    cerebro.addstrategy(
        OutlierPennyExtremeStrategy,
        max_position_size=0.01,  # 1% del capital por posición
        max_price=5.0,           # Penny stocks < $5
        min_pm_range=3.0,        # Premarket range > 3%
        min_volume_ratio=1.5,    # Volume > 1.5x
        take_profit_pct=50.0,    # Take profit 50%
        stop_loss_pct=15.0,      # Stop loss 15%
        trailing_stop_pct=30.0,  # Trailing activation 30%
        max_concurrent=2,        # Max 2 positions
    )

    # Load data from market_data.db
    logger.info("Loading data from market_data.db...")

    try:
        import sqlite3
        import pandas as pd

        conn = sqlite3.connect('market_data.db')

        # Get list of penny stocks (< $5)
        query_symbols = """
            SELECT DISTINCT symbol
            FROM market_data
            WHERE close < 5.0
            AND volume > 100000
            ORDER BY symbol
            LIMIT 20
        """

        symbols = pd.read_sql_query(query_symbols, conn)['symbol'].tolist()
        logger.info(f"Found {len(symbols)} penny stocks in database")

        if not symbols:
            logger.error("No penny stocks found in database!")
            conn.close()
            return

        # Load data for each symbol
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)

        loaded_count = 0
        for symbol in symbols[:10]:  # Limit to 10 symbols for demo
            query_data = f"""
                SELECT
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM market_data
                WHERE symbol = '{symbol}'
                AND timestamp >= '{start_date.strftime("%Y-%m-%d")}'
                AND timestamp <= '{end_date.strftime("%Y-%m-%d")}'
                ORDER BY timestamp
            """

            df = pd.read_sql_query(query_data, conn)

            if len(df) < 20:  # Need minimum data
                continue

            # Convert to backtrader format
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            # Create data feed
            data = bt.feeds.PandasData(
                dataname=df,
                name=symbol,
                datetime=None,
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume',
                openinterest=-1
            )

            cerebro.adddata(data)
            loaded_count += 1
            logger.info(f"  ✅ Loaded {symbol}: {len(df)} bars")

        conn.close()

        if loaded_count == 0:
            logger.error("No data loaded! Cannot run backtest.")
            return

        logger.info(f"✅ Total symbols loaded: {loaded_count}")

    except Exception as e:
        logger.error(f"Error loading data: {e}", exc_info=True)
        return

    # Set initial cash
    initial_cash = 10000.0
    cerebro.broker.setcash(initial_cash)

    # Set commission
    cerebro.broker.setcommission(commission=0.001)  # 0.1%

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    # Run backtest
    logger.info("="*80)
    logger.info("STARTING BACKTEST...")
    logger.info(f"Initial Cash: ${initial_cash:,.2f}")
    logger.info("="*80)

    results = cerebro.run()
    strat = results[0]

    # Get final value
    final_value = cerebro.broker.getvalue()
    total_return = ((final_value - initial_cash) / initial_cash) * 100

    # Print results
    logger.info("="*80)
    logger.info("BACKTEST RESULTS - OUTLIER PENNY EXTREME")
    logger.info("="*80)
    logger.info(f"Initial Cash:    ${initial_cash:,.2f}")
    logger.info(f"Final Value:     ${final_value:,.2f}")
    logger.info(f"Total Return:    {total_return:+.2f}%")
    logger.info("")

    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    logger.info(f"Sharpe Ratio:    {sharpe.get('sharperatio', 0):.2f}")

    # Drawdown
    drawdown = strat.analyzers.drawdown.get_analysis()
    logger.info(f"Max Drawdown:    {drawdown.get('max', {}).get('drawdown', 0):.2f}%")

    # Trades
    trades = strat.analyzers.trades.get_analysis()
    total_trades = trades.get('total', {}).get('total', 0)
    won_trades = trades.get('won', {}).get('total', 0)
    lost_trades = trades.get('lost', {}).get('total', 0)

    logger.info(f"Total Trades:    {total_trades}")
    if total_trades > 0:
        win_rate = (won_trades / total_trades) * 100
        logger.info(f"Win Rate:        {win_rate:.1f}% ({won_trades}W / {lost_trades}L)")

        avg_win = trades.get('won', {}).get('pnl', {}).get('average', 0)
        avg_loss = trades.get('lost', {}).get('pnl', {}).get('average', 0)
        logger.info(f"Avg Win:         ${avg_win:.2f}")
        logger.info(f"Avg Loss:        ${avg_loss:.2f}")

    logger.info("="*80)
    logger.info("EXPECTED PERFORMANCE (from backtest validation):")
    logger.info("  - Edge: +11.69%")
    logger.info("  - Win Rate: 54.6%")
    logger.info("  - Avg Win: +31.43%")
    logger.info("  - Avg Loss: -12.05%")
    logger.info("  - Sample Size: 163 historical events")
    logger.info("="*80)
    logger.info("")
    logger.info("⚠️  WARNINGS:")
    logger.info("  - This is DEMO mode with limited data")
    logger.info("  - EXTREME RISK strategy - use 1% position size MAX")
    logger.info("  - Requires active monitoring and fast execution")
    logger.info("  - Paper trade extensively before going live")
    logger.info("="*80)


if __name__ == "__main__":
    try:
        run_demo_backtest()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Backtest interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error running backtest: {e}", exc_info=True)
