import backtrader as bt
import logging
from datetime import datetime
from data.market_data_feed import create_data_feed
from config.backtest_config import BACKTEST_CONFIG, DATA_CONFIG
import importlib
import sys
import os

class BacktestRunner:
    """
    Ejecutor de backtests para estrategias de Backtrader
    """

    def __init__(self, strategy_name, event_id, start_date=None, end_date=None):
        self.strategy_name = strategy_name
        self.event_id = event_id
        self.start_date = start_date
        self.end_date = end_date

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def load_strategy(self):
        """Cargar dinámicamente la estrategia"""
        try:
            # Importar módulo de estrategias
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'strategies'))

            strategy_module = importlib.import_module(f'{self.strategy_name}')
            strategy_class = getattr(strategy_module, self.strategy_name)

            self.logger.info(f"Estrategia {self.strategy_name} cargada exitosamente")
            return strategy_class

        except Exception as e:
            self.logger.error(f"Error cargando estrategia {self.strategy_name}: {e}")
            raise

    def run_backtest(self):
        """Ejecutar el backtest"""
        try:
            # Crear cerebro
            cerebro = bt.Cerebro()

            # Configurar cerebro
            cerebro.broker.setcash(BACKTEST_CONFIG['initial_cash'])
            cerebro.broker.setcommission(commission=BACKTEST_CONFIG['commission'])

            # Cargar estrategia
            strategy_class = self.load_strategy()
            cerebro.addstrategy(strategy_class, position_size=BACKTEST_CONFIG['position_size'])

            # Cargar datos
            data_feed = create_data_feed(
                event_id=self.event_id,
                start_date=self.start_date,
                end_date=self.end_date
            )

            # Verificar que hay datos antes de continuar
            if hasattr(data_feed, 'p') and hasattr(data_feed.p, 'dataname'):
                if data_feed.p.dataname is None or (hasattr(data_feed.p.dataname, 'empty') and data_feed.p.dataname.empty):
                    raise ValueError(f"No hay datos disponibles para event_id {self.event_id} en el período especificado")

            cerebro.adddata(data_feed, name=f"event_{self.event_id}")

            # Agregar analizadores
            cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

            # Ejecutar backtest
            self.logger.info(f"Iniciando backtest para {self.strategy_name} con event_id {self.event_id}")
            self.logger.info(f"Capital inicial: ${BACKTEST_CONFIG['initial_cash']}")

            results = cerebro.run()
            strategy = results[0]

            # Obtener resultados
            final_value = cerebro.broker.getvalue()
            total_return = (final_value - BACKTEST_CONFIG['initial_cash']) / BACKTEST_CONFIG['initial_cash'] * 100

            # Mostrar resultados
            self.print_results(cerebro, strategy, final_value, total_return)

            return {
                'final_value': final_value,
                'total_return': total_return,
                'sharpe_ratio': strategy.analyzers.sharpe.get_analysis(),
                'max_drawdown': strategy.analyzers.drawdown.get_analysis(),
                'trade_analysis': strategy.analyzers.trades.get_analysis()
            }

        except ValueError as e:
            # ValueError esperado cuando no hay datos - no loguear como error
            if "No hay datos disponibles" in str(e):
                raise  # Re-lanzar sin loguear
            else:
                self.logger.error(f"Error ejecutando backtest: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Error ejecutando backtest: {e}")
            raise

    def print_results(self, cerebro, strategy, final_value, total_return):
        """Imprimir resultados del backtest"""
        print("\n" + "="*60)
        print(f"RESULTADOS BACKTEST - {self.strategy_name} - event_{self.event_id}")
        print("="*60)
        print(f"Capital inicial: ${BACKTEST_CONFIG['initial_cash']:.2f}")
        print(f"Capital final: ${final_value:.2f}")
        print(f"Retorno total: {total_return:.2f}%")

        # Sharpe Ratio
        sharpe = strategy.analyzers.sharpe.get_analysis()
        if 'sharperatio' in sharpe and sharpe['sharperatio'] is not None:
            print(f"Sharpe Ratio: {sharpe['sharperatio']:.3f}")

        # Drawdown máximo
        drawdown = strategy.analyzers.drawdown.get_analysis()
        if 'max' in drawdown and 'drawdown' in drawdown['max'] and drawdown['max']['drawdown'] is not None:
            print(f"Max Drawdown: {drawdown['max']['drawdown']:.2f}%")

        # Análisis de trades
        trades = strategy.analyzers.trades.get_analysis()
        if 'total' in trades:
            total_trades = trades['total']['total']
            won_trades = trades['won']['total'] if 'won' in trades else 0
            lost_trades = trades['lost']['total'] if 'lost' in trades else 0

            win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
            print(f"Total trades: {total_trades}")
            print(f"Win rate: {win_rate:.1f}%")

            if 'pnl' in trades:
                avg_win = trades['pnl']['won']['average'] if 'won' in trades['pnl'] else 0
                avg_loss = trades['pnl']['lost']['average'] if 'lost' in trades['pnl'] else 0
                print(f"Avg Win: ${avg_win:.2f}")
                print(f"Avg Loss: ${avg_loss:.2f}")

        print("="*60)

def run_single_backtest(strategy_name, symbol, start_date=None, end_date=None):
    """
    Función helper para ejecutar un backtest individual
    """
    runner = BacktestRunner(strategy_name, symbol, start_date, end_date)
    return runner.run_backtest()

if __name__ == "__main__":
    # Ejemplo de uso
    result = run_single_backtest('BreakoutStrategy', 'AAPL', '2024-01-01', '2024-01-31')
    print("Backtest completado!")