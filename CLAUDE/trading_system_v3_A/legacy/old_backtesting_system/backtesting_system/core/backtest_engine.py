"""
Motor Principal de Backtesting

Clase central que coordina la ejecución de backtests usando backtrader
con integración de datos reales y estrategias adaptadas.
"""

import backtrader as bt
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

import sys
import os
import importlib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Forzar recarga de configuración para evitar cache
import config.backtest_config
importlib.reload(config.backtest_config)
from config.backtest_config import BACKTEST_CONFIG, STRATEGY_CONFIGS

from data.ibkr_data_feed import MultiSymbolDataFeed, IBKRIntradayDataFeed
from strategies.daily_plays_bt_strategy import DailyPlaysStrategy
from strategies.macdv_bt_strategy import MacdvStrategy
from strategies.momentum_breakout_bt_strategy import MomentumBreakoutStrategy
from strategies.vwap_breakout_bt_strategy import VWAPBreakoutStrategy
from strategies.rsi_oversold_bt_strategy import RSIOverSoldStrategy
from strategies.ma_crossover_bt_strategy import MACrossoverStrategy
from strategies.volume_price_bt_strategy import VolumePriceStrategy


class BacktestEngine:
    """
    Motor principal para ejecutar backtests

    Coordina la configuración de backtrader, carga de datos,
    estrategias y ejecución de análisis.
    """

    def __init__(self, config=None):
        """
        Inicializar motor de backtesting

        Args:
            config: Configuración personalizada (opcional)
        """
        self.config = config or BACKTEST_CONFIG
        self.logger = logging.getLogger('backtesting.engine')

        # Configurar logging
        self._setup_logging()

        # Inicializar cerebro de backtrader
        self.cerebro = bt.Cerebro()

        # Configurar broker
        self._configure_broker()

        # Feeds de datos
        self.data_feeds = None

        # Resultados
        self.results = None

    def _setup_logging(self):
        """Configurar sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _configure_broker(self):
        """Configurar broker de backtrader"""
        # Capital inicial
        self.cerebro.broker.setcash(self.config.initial_capital)

        # Comisión por acción
        self.cerebro.broker.setcommission(
            commission=self.config.commission_per_share,
            margin=False
        )

        # Slippage
        self.cerebro.broker.set_slippage_perc(self.config.slippage_pct / 100)

        self.logger.info(f"Broker configured: ${self.config.initial_capital:,.0f} capital, "
                        f"${self.config.commission_per_share:.3f}/share commission, "
                        f"{self.config.slippage_pct:.2f}% slippage")

    def add_strategy(self, strategy_name: str, **kwargs):
        """
        Agregar estrategia al backtest

        Args:
            strategy_name: Nombre de la estrategia
            **kwargs: Parámetros adicionales
        """
        strategy_config = None
        for config in STRATEGY_CONFIGS:
            if config.name == strategy_name:
                strategy_config = config
                break

        if not strategy_config or not strategy_config.enabled:
            self.logger.warning(f"Strategy {strategy_name} not found or disabled")
            return

        # Mapear nombres de estrategias a clases
        strategy_classes = {
            'daily_plays': DailyPlaysStrategy,
            'macdv': MacdvStrategy,
            'momentum_breakout': MomentumBreakoutStrategy,
            'vwap_breakout': VWAPBreakoutStrategy,
            'rsi_oversold': RSIOverSoldStrategy,
            'ma_crossover': MACrossoverStrategy,
            'volume_price': VolumePriceStrategy,
        }

        strategy_class = strategy_classes.get(strategy_name)
        if not strategy_class:
            self.logger.error(f"No class found for strategy {strategy_name}")
            return

        # Usar kwargs si se pasan, sino usar configuración por defecto
        if kwargs:
            params = kwargs
        else:
            params = strategy_config.parameters

        self.cerebro.addstrategy(strategy_class, **params)
        self.logger.info(f"Added strategy: {strategy_name} with params: {params}")

    def load_data(self, symbols: List[str] = None, data_type: str = 'intraday'):
        """
        Cargar datos para los símbolos especificados

        Args:
            symbols: Lista de símbolos (usa universo por defecto si None)
            data_type: 'intraday' o 'daily'
        """
        if symbols is None:
            symbols = self.config.small_cap_universe[:5]  # Top 5 para test

        self.logger.info(f"Loading {data_type} data for symbols: {symbols}")

        # Crear multi-symbol data feed
        self.data_feeds = MultiSymbolDataFeed(
            symbols=symbols,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            data_type=data_type
        )

        # Agregar feeds al cerebro
        available_symbols = self.data_feeds.get_available_symbols()

        if not available_symbols:
            self.logger.warning("No data feeds available!")
            return

        for symbol in available_symbols:
            df = self.data_feeds.get_data(symbol)
            if df is not None and not df.empty:
                try:
                    # Crear PandasData feed directamente en el cerebro
                    feed = bt.feeds.PandasData(
                        dataname=df,
                        datetime=None,
                        open='open',
                        high='high',
                        low='low',
                        close='close',
                        volume='volume',
                        openinterest=-1
                    )
                    self.cerebro.adddata(feed, name=symbol)
                    self.logger.info(f"Added {data_type} data feed for {symbol} with {len(df)} rows")
                except Exception as e:
                    self.logger.error(f"Failed to add feed for {symbol}: {e}")
                    continue

    def run_backtest(self) -> Dict[str, Any]:
        """
        Ejecutar el backtest

        Returns:
            Diccionario con resultados del backtest
        """
        try:
            self.logger.info("Starting backtest execution...")

            # Agregar analyzers para métricas
            self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
            self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

            # Ejecutar backtest
            self.results = self.cerebro.run()

            # Recopilar resultados
            results_summary = self._analyze_results()

            self.logger.info("Backtest completed successfully")
            return results_summary

        except Exception as e:
            self.logger.error(f"Error during backtest execution: {e}")
            raise

    def _analyze_results(self) -> Dict[str, Any]:
        """
        Analizar y resumir resultados del backtest usando analyzers

        Returns:
            Diccionario con métricas y análisis
        """
        try:
            # Valor final del portfolio
            final_value = self.cerebro.broker.getvalue()
            initial_value = self.config.initial_capital

            # Retorno total
            total_return = final_value - initial_value
            total_return_pct = (total_return / initial_value) * 100

            # Extraer métricas de analyzers globales (primera estrategia tiene todos los datos)
            max_drawdown = 0.0
            sharpe_ratio = 0.0
            total_trades = 0
            win_rate = 0.0

            if self.results and len(self.results) > 0:
                first_strategy = self.results[0]

                # Drawdown
                if hasattr(first_strategy.analyzers, 'drawdown'):
                    dd_analysis = first_strategy.analyzers.drawdown.get_analysis()
                    max_drawdown = dd_analysis.get('max', {}).get('drawdown', 0.0)

                # Sharpe Ratio
                if hasattr(first_strategy.analyzers, 'sharpe'):
                    sharpe_analysis = first_strategy.analyzers.sharpe.get_analysis()
                    sharpe_ratio = sharpe_analysis.get('sharperatio', 0.0)
                    if sharpe_ratio is None:
                        sharpe_ratio = 0.0

                # Total trades (sumar de todas las estrategias)
                if hasattr(first_strategy.analyzers, 'trades'):
                    trade_analysis = first_strategy.analyzers.trades.get_analysis()
                    total_trades = trade_analysis.get('total', {}).get('closed', 0)

                    # Win rate global
                    total_won = trade_analysis.get('won', {}).get('total', 0)
                    win_rate = (total_won / total_trades * 100) if total_trades > 0 else 0.0

            # Métricas básicas
            summary = {
                'initial_capital': initial_value,
                'final_value': final_value,
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'execution_time': datetime.now().isoformat()
            }

            # Analizar trades por estrategia
            if self.results:
                strategy_results = []
                for strategy_result in self.results:
                    strategy_analysis = self._analyze_strategy(strategy_result)
                    strategy_results.append(strategy_analysis)

                summary['strategy_results'] = strategy_results

            self.logger.info(f"Backtest Summary: ${final_value:,.2f} final value "
                           f"({total_return_pct:.2f}% return)")

            return summary

        except Exception as e:
            self.logger.error(f"Error analyzing results: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _analyze_strategy(self, strategy_result) -> Dict[str, Any]:
        """
        Analizar resultados de una estrategia específica usando analyzers de Backtrader

        Args:
            strategy_result: Resultado de estrategia de backtrader

        Returns:
            Diccionario con análisis de estrategia
        """
        try:
            strategy_name = strategy_result.__class__.__name__

            # Obtener analyzer de trades
            trade_analyzer = None
            if hasattr(strategy_result, 'analyzers') and hasattr(strategy_result.analyzers, 'trades'):
                trade_analyzer = strategy_result.analyzers.trades.get_analysis()

            # Extraer métricas del analyzer
            if trade_analyzer:
                total_closed = trade_analyzer.get('total', {}).get('closed', 0)
                total_won = trade_analyzer.get('won', {}).get('total', 0)
                total_lost = trade_analyzer.get('lost', {}).get('total', 0)

                # PnL
                pnl_net_total = trade_analyzer.get('pnl', {}).get('net', {}).get('total', 0)
                pnl_net_avg = trade_analyzer.get('pnl', {}).get('net', {}).get('average', 0)

                # Largest win/loss
                won_pnl_max = trade_analyzer.get('won', {}).get('pnl', {}).get('max', 0)
                lost_pnl_max = trade_analyzer.get('lost', {}).get('pnl', {}).get('max', 0)

                # Win rate
                win_rate = (total_won / total_closed * 100) if total_closed > 0 else 0

                return {
                    'strategy_name': strategy_name,
                    'total_trades': total_closed,
                    'winning_trades': total_won,
                    'losing_trades': total_lost,
                    'win_rate': win_rate,
                    'total_pnl': pnl_net_total,
                    'avg_pnl': pnl_net_avg,
                    'largest_win': won_pnl_max,
                    'largest_loss': lost_pnl_max
                }
            else:
                # Fallback: usar método manual si no hay analyzer
                return {
                    'strategy_name': strategy_name,
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_pnl': 0.0,
                    'largest_win': 0.0,
                    'largest_loss': 0.0
                }

        except Exception as e:
            self.logger.error(f"Error analyzing strategy {strategy_name if 'strategy_name' in locals() else 'unknown'}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def generate_report(self, results: Dict[str, Any], output_file: str = None) -> str:
        """
        Generar reporte de resultados

        Args:
            results: Resultados del backtest
            output_file: Archivo de salida (opcional)

        Returns:
            String con reporte formateado
        """
        try:
            report = []
            report.append("=" * 70)
            report.append("BACKTESTING SYSTEM REPORT")
            report.append("=" * 70)
            report.append("")

            # Resumen general
            report.append("PORTFOLIO SUMMARY:")
            report.append(f"  Initial Capital:   ${results.get('initial_capital', 0):,.0f}")
            report.append(f"  Final Value:       ${results.get('final_value', 0):,.0f}")
            report.append(f"  Total Return:      ${results.get('total_return', 0):,.2f}")
            report.append(f"  Return %:          {results.get('total_return_pct', 0):.2f}%")
            report.append(f"  Max Drawdown:      {results.get('max_drawdown', 0):.2f}%")
            report.append(f"  Sharpe Ratio:      {results.get('sharpe_ratio', 0):.3f}")
            report.append(f"  Total Trades:      {results.get('total_trades', 0)}")
            report.append(f"  Win Rate:          {results.get('win_rate', 0):.1f}%")
            report.append("")

            # Resultados por estrategia
            strategy_results = results.get('strategy_results', [])
            if strategy_results:
                report.append("STRATEGY PERFORMANCE:")
                report.append("")

                # Ordenar por total_pnl descendente
                sorted_strategies = sorted(strategy_results, key=lambda x: x.get('total_pnl', 0), reverse=True)

                for strat_result in sorted_strategies:
                    strategy_name = strat_result.get('strategy_name', 'Unknown')
                    total_trades = strat_result.get('total_trades', 0)
                    win_rate = strat_result.get('win_rate', 0)
                    total_pnl = strat_result.get('total_pnl', 0)
                    avg_pnl = strat_result.get('avg_pnl', 0)
                    winning_trades = strat_result.get('winning_trades', 0)
                    losing_trades = strat_result.get('losing_trades', 0)
                    largest_win = strat_result.get('largest_win', 0)
                    largest_loss = strat_result.get('largest_loss', 0)

                    # Indicador de performance
                    if total_pnl > 0:
                        performance_icon = "✅"
                    elif total_pnl < 0:
                        performance_icon = "❌"
                    else:
                        performance_icon = "⚪"

                    report.append(f"  {performance_icon} {strategy_name}:")
                    report.append(f"     Trades:         {total_trades} ({winning_trades}W / {losing_trades}L)")
                    report.append(f"     Win Rate:       {win_rate:.1f}%")
                    report.append(f"     Total PnL:      ${total_pnl:,.2f}")
                    report.append(f"     Avg PnL:        ${avg_pnl:,.2f}")
                    report.append(f"     Largest Win:    ${largest_win:,.2f}")
                    report.append(f"     Largest Loss:   ${largest_loss:,.2f}")
                    report.append("")

            report.append("=" * 70)

            final_report = "\n".join(report)

            # Guardar a archivo si se especifica
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(final_report)
                self.logger.info(f"Report saved to {output_file}")

            return final_report

        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            return "Error generating report"