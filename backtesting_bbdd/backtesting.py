import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')
from ibapi.order_state import OrderState

class Backtester:
    def __init__(self, db_path, initial_capital=1000, commission=0.001, risk_per_trade=0.01):
        """
        Initialize the backtester with database connection and parameters.
        
        Args:
            db_path (str): Path to SQLite database
            initial_capital (float): Starting capital for backtest
            commission (float): Commission per trade (percentage)
            risk_per_trade (float): Risk per trade as percentage of capital
        """
        self.conn = sqlite3.connect(db_path)
        self.initial_capital = initial_capital
        self.commission = commission
        self.risk_per_trade = risk_per_trade
        self.results = None
        self.trade_log = None
        
    def get_trading_days(self):
        """Get all distinct trading days from the database"""
        query = """
        SELECT DISTINCT DATE(timestamp) as trading_date 
        FROM ScannerEvents 
        ORDER BY trading_date
        """
        return pd.read_sql(query, self.conn)['trading_date'].tolist()
    
    def get_tickers_for_date(self, date):
        """Get all tickers that were scanned on a specific date"""
        query = """
        SELECT se.ticker, sd.*, ohlc.*, kf.*
        FROM ScannerEvents se
        JOIN ScannerData sd ON se.id_event = sd.id_event
        JOIN OHLCData ohlc ON se.id_event = ohlc.id_event
        LEFT JOIN KeyFactors kf ON se.id_event = kf.id_event
        WHERE DATE(se.timestamp) = ?
        """
        df = pd.read_sql(query, self.conn, params=(date,))
        return df
    
    def calculate_position_size(self, entry_price, stop_loss_price, current_capital):
        """
        Calculate position size based on risk management rules.
        
        Args:
            entry_price (float): Entry price of the trade
            stop_loss_price (float): Stop loss price
            current_capital (float): Current available capital
            
        Returns:
            int: Number of shares to trade
        """
        risk_amount = current_capital * self.risk_per_trade
        risk_per_share = entry_price - stop_loss_price
        if risk_per_share <= 0:
            return 0
        return int(risk_amount / risk_per_share)
    
    def run_backtest(self, strategy_function, start_date=None, end_date=None):
        """
        Run the backtest using the provided strategy function.
        
        Args:
            strategy_function (function): Function that implements the trading strategy
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            
        Returns:
            dict: Backtest results
        """
        trading_days = self.get_trading_days()
        
        # Filter dates if specified
        if start_date:
            trading_days = [d for d in trading_days if d >= start_date]
        if end_date:
            trading_days = [d for d in trading_days if d <= end_date]
        
        capital = self.initial_capital
        portfolio_value = [capital]
        trade_log = []
        
        print(f"Running backtest from {trading_days[0]} to {trading_days[-1]}")
        
        for day in tqdm(trading_days, desc="Processing days"):
            day_data = self.get_tickers_for_date(day)
            if day_data.empty:
                portfolio_value.append(capital)
                continue

            tickers = day_data['ticker'].unique()
            for ticker in tickers:
                ticker_data = day_data[day_data['ticker'] == ticker]
                if ticker_data.empty:
                    continue
                print(f"{day} {ticker}: datos de entrada = {len(ticker_data)} filas")
                print(ticker_data.head())
                signals = strategy_function(ticker_data)
                print(f"{day} {ticker}: señales generadas = {len(signals)}")
                for _, signal in signals.iterrows():
                    if capital <= 0:
                        break
                    entry_price = signal['entry_price']
                    stop_loss = signal['stop_loss']
                    take_profit = signal.get('take_profit', None)
                    position_size = self.calculate_position_size(entry_price, stop_loss, capital)
                    if position_size <= 0:
                        continue
                    trade_value = position_size * entry_price
                    commission_cost = trade_value * self.commission
                    exit_price = take_profit if take_profit else entry_price * 1.02
                    exit_reason = 'TP' if take_profit else '2% Default'
                    if signal['low'] <= stop_loss:
                        exit_price = stop_loss
                        exit_reason = 'SL'
                    pnl = position_size * (exit_price - entry_price) - (2 * commission_cost)
                    capital += pnl
                    trade_log.append({
                        'date': day,
                        'ticker': signal['ticker'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'position_size': position_size,
                        'pnl': pnl,
                        'pnl_pct': pnl / (position_size * entry_price),
                        'exit_reason': exit_reason,
                        'capital': capital
                    })
            portfolio_value.append(capital)

        
        # Prepare results
        self.trade_log = pd.DataFrame(trade_log)
        self.results = {
            'final_capital': capital,
            'total_return': (capital - self.initial_capital) / self.initial_capital * 100,
            'max_drawdown': self.calculate_max_drawdown(portfolio_value),
            'sharpe_ratio': self.calculate_sharpe_ratio(portfolio_value),
            'win_rate': self.calculate_win_rate(),
            'profit_factor': self.calculate_profit_factor(),
            'portfolio_values': portfolio_value,
            'num_trades': len(trade_log)
        }
        
        return self.results
    
    def calculate_max_drawdown(self, portfolio_values):
        """Calculate maximum drawdown"""
        peak = portfolio_values[0]
        max_dd = 0
        for value in portfolio_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100  # as percentage
    
    def calculate_sharpe_ratio(self, portfolio_values):
        """Calculate annualized Sharpe ratio"""
        returns = np.diff(portfolio_values) / portfolio_values[:-1]
        if len(returns) == 0:
            return 0
        return np.sqrt(252) * np.mean(returns) / np.std(returns)
    
    def calculate_win_rate(self):
        """Calculate win rate percentage"""
        if self.trade_log is None or self.trade_log.empty:
            return 0
        wins = len(self.trade_log[self.trade_log['pnl'] > 0])
        return wins / len(self.trade_log) * 100
    
    def calculate_profit_factor(self):
        """Calculate profit factor (gross profits / gross losses)"""
        if self.trade_log is None or self.trade_log.empty:
            return 0
        gross_profit = self.trade_log[self.trade_log['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(self.trade_log[self.trade_log['pnl'] < 0]['pnl'].sum())
        if gross_loss == 0:
            return float('inf')
        return gross_profit / gross_loss
    
    def generate_report(self):
        """Generate a comprehensive backtest report"""
        if self.results is None:
            print("No backtest results available. Run backtest first.")
            return
        
        print("\n=== BACKTEST REPORT ===")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${self.results['final_capital']:,.2f}")
        print(f"Total Return: {self.results['total_return']:.2f}%")
        print(f"Number of Trades: {self.results['num_trades']}")
        print(f"Win Rate: {self.results['win_rate']:.2f}%")
        print(f"Profit Factor: {self.results['profit_factor']:.2f}")
        print(f"Max Drawdown: {self.results['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio: {self.results['sharpe_ratio']:.2f}")
        
        # Plot equity curve
        plt.figure(figsize=(12, 6))
        plt.plot(self.results['portfolio_values'])
        plt.title("Equity Curve")
        plt.xlabel("Day")
        plt.ylabel("Portfolio Value ($)")
        plt.grid(True)
        plt.show()
        
        # Plot daily returns distribution
        if len(self.results['portfolio_values']) > 1:
            daily_returns = np.diff(self.results['portfolio_values']) / self.results['portfolio_values'][:-1]
            plt.figure(figsize=(12, 6))
            sns.histplot(daily_returns, bins=50, kde=True)
            plt.title("Daily Returns Distribution")
            plt.xlabel("Daily Return")
            plt.ylabel("Frequency")
            plt.show()
        
        # Show top 5 winning and losing trades
        if self.trade_log is not None and not self.trade_log.empty:
            print("\nTop 5 Winning Trades:")
            print(self.trade_log.nlargest(5, 'pnl')[['date', 'ticker', 'pnl', 'pnl_pct']])
            
            print("\nTop 5 Losing Trades:")
            print(self.trade_log.nsmallest(5, 'pnl')[['date', 'ticker', 'pnl', 'pnl_pct']])


# Example Strategy Implementation
def example_strategy(data):
    """
    Example strategy that looks for stocks with:
    - Price > $5
    - Volume > 100k
    - Premarket range > 2%
    - Opening within 50% of premarket range
    """
    signals = []
    
    # Filter stocks
    filtered = data[
        (data['precio'] > 5) & 
        (data['volumen'] > 100000) & 
        (data['percent_var'] > 2) &
        (data['ratio_vol'] > 1.5)
    ].copy()
    
    if filtered.empty:
        return pd.DataFrame()
    
    # Calculate premarket range
    filtered['premarket_range'] = filtered['max_premarket'] - filtered['min_premarket']
    filtered['open_in_range'] = (filtered['open'] - filtered['min_premarket']) / filtered['premarket_range']
    
    # Select stocks that opened in the middle of premarket range
    filtered = filtered[(filtered['open_in_range'] > 0.3) & (filtered['open_in_range'] < 0.7)]
    
    # Generate signals
    for _, row in filtered.iterrows():
        entry_price = row['open']
        stop_loss = row['min_premarket']
        take_profit = entry_price + (entry_price - stop_loss) * 2  # 1:2 risk-reward
        
        signals.append({
            'ticker': row['ticker'],
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        })
    
    return pd.DataFrame(signals)


if __name__ == "__main__":
    # Initialize backtester
    backtester = Backtester('database.db', initial_capital=1000)
    
    # Run backtest with example strategy
    results = backtester.run_backtest(example_strategy, start_date='2025-01-01', end_date='2025-04-1')
    
    # Generate report
    backtester.generate_report()