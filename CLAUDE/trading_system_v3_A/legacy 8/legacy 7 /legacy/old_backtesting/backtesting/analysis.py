# backtesting/analysis.py
"""
Analysis and reporting tools for backtest results.
"""

import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime


class BacktestAnalyzer:
    """Comprehensive analysis of backtest results"""
    
    def __init__(self, results):
        self.results = results
        self.trades_df = self._create_trades_dataframe()
    
    def _create_trades_dataframe(self) -> pd.DataFrame:
        """Convert trades to DataFrame for analysis"""
        trade_data = []
        for trade in self.results.trades:
            if trade.exit_time:  # Only completed trades
                trade_data.append({
                    'trade_id': trade.trade_id,
                    'symbol': trade.symbol,
                    'side': trade.side.value,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'pnl': trade.pnl,
                    'pnl_pct': trade.pnl_pct,
                    'commission': trade.commission,
                    'holding_period_hours': trade.holding_period.total_seconds() / 3600,
                    'exit_reason': trade.exit_reason
                })
        
        return pd.DataFrame(trade_data)
    
    def print_summary_report(self):
        """Print comprehensive summary report"""
        r = self.results
        
        print("=" * 80)
        print("BACKTEST SUMMARY REPORT")
        print("=" * 80)
        
        # Period and Return
        print(f"\nPERIOD: {r.start_date.strftime('%Y-%m-%d')} to {r.end_date.strftime('%Y-%m-%d')}")
        print(f"Duration: {r.duration.days} days")
        print(f"Initial Capital: ${r.initial_capital:,.2f}")
        print(f"Final Capital: ${r.final_capital:,.2f}")
        print(f"Total Return: ${r.total_return:,.2f} ({r.total_return_pct:.2f}%)")
        print(f"CAGR: {r.cagr:.2f}%")
        
        # Risk Metrics
        print(f"\nRISK METRICS:")
        print(f"Max Drawdown: ${r.max_drawdown:,.2f} ({r.max_drawdown_pct:.2f}%)")
        print(f"Sharpe Ratio: {r.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {r.sortino_ratio:.2f}")
        print(f"Calmar Ratio: {r.calmar_ratio:.2f}")
        
        # Trading Metrics
        print(f"\nTRADING METRICS:")
        print(f"Total Trades: {r.total_trades}")
        print(f"Winning Trades: {r.winning_trades}")
        print(f"Losing Trades: {r.losing_trades}")
        print(f"Win Rate: {r.win_rate:.2f}%")
        print(f"Profit Factor: {r.profit_factor:.2f}")
        
        # PnL Analysis
        print(f"\nPNL ANALYSIS:")
        print(f"Gross Profit: ${r.gross_profit:,.2f}")
        print(f"Gross Loss: ${r.gross_loss:,.2f}")
        print(f"Average Win: ${r.avg_win:.2f}")
        print(f"Average Loss: ${r.avg_loss:.2f}")
        print(f"Largest Win: ${r.largest_win:.2f}")
        print(f"Largest Loss: ${r.largest_loss:.2f}")
        
        # Portfolio Metrics
        print(f"\nPORTFOLIO METRICS:")
        print(f"Max Concurrent Positions: {r.max_concurrent_positions}")
        print(f"Average Capital Utilization: {r.avg_capital_utilization:.1f}%")
        print(f"Average Holding Period: {r.avg_holding_period}")
        print(f"Max Holding Period: {r.max_holding_period}")
        
        # Trade Analysis by Symbol
        if not self.trades_df.empty:
            print(f"\nTRADES BY SYMBOL:")
            symbol_stats = self.trades_df.groupby('symbol').agg({
                'pnl': ['count', 'sum', 'mean'],
                'pnl_pct': 'mean'
            }).round(2)
            symbol_stats.columns = ['Trades', 'Total PnL', 'Avg PnL', 'Avg PnL %']
            print(symbol_stats)
            
            # Exit Reasons
            print(f"\nEXIT REASONS:")
            exit_reasons = self.trades_df['exit_reason'].value_counts()
            for reason, count in exit_reasons.items():
                pct = (count / len(self.trades_df)) * 100
                print(f"{reason}: {count} ({pct:.1f}%)")
    
    def plot_equity_curve(self, save_path: str = None):
        """Plot equity curve and drawdown"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        
        # Equity curve
        equity_pct = (self.results.equity_curve / self.results.initial_capital - 1) * 100
        ax1.plot(equity_pct.index, equity_pct.values, linewidth=2, color='blue')
        ax1.set_ylabel('Return (%)')
        ax1.set_title('Equity Curve')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        
        # Drawdown
        drawdown_pct = (self.results.drawdown_curve / self.results.initial_capital) * 100
        ax2.fill_between(drawdown_pct.index, drawdown_pct.values, 0, 
                        color='red', alpha=0.3)
        ax2.plot(drawdown_pct.index, drawdown_pct.values, color='red', linewidth=1)
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.set_title('Drawdown')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()
    
    def plot_trade_analysis(self, save_path: str = None):
        """Plot trade analysis charts"""
        if self.trades_df.empty:
            print("No completed trades to analyze")
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # PnL Distribution
        ax1.hist(self.trades_df['pnl'], bins=20, alpha=0.7, edgecolor='black')
        ax1.axvline(x=0, color='red', linestyle='--', alpha=0.7)
        ax1.set_xlabel('PnL ($)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('PnL Distribution')
        ax1.grid(True, alpha=0.3)
        
        # PnL by Holding Period
        ax2.scatter(self.trades_df['holding_period_hours'], self.trades_df['pnl'], 
                   alpha=0.6, c=self.trades_df['pnl'], cmap='RdYlGn')
        ax2.set_xlabel('Holding Period (hours)')
        ax2.set_ylabel('PnL ($)')
        ax2.set_title('PnL vs Holding Period')
        ax2.grid(True, alpha=0.3)
        
        # Cumulative PnL
        cumulative_pnl = self.trades_df['pnl'].cumsum()
        ax3.plot(range(len(cumulative_pnl)), cumulative_pnl, linewidth=2)
        ax3.set_xlabel('Trade Number')
        ax3.set_ylabel('Cumulative PnL ($)')
        ax3.set_title('Cumulative PnL by Trade')
        ax3.grid(True, alpha=0.3)
        ax3.axhline(y=0, color='red', linestyle='--', alpha=0.7)
        
        # Win/Loss by Symbol
        symbol_pnl = self.trades_df.groupby('symbol')['pnl'].sum().sort_values(ascending=True)
        colors = ['red' if x < 0 else 'green' for x in symbol_pnl.values]
        ax4.barh(range(len(symbol_pnl)), symbol_pnl.values, color=colors, alpha=0.7)
        ax4.set_yticks(range(len(symbol_pnl)))
        ax4.set_yticklabels(symbol_pnl.index)
        ax4.set_xlabel('Total PnL ($)')
        ax4.set_title('PnL by Symbol')
        ax4.grid(True, alpha=0.3)
        ax4.axvline(x=0, color='black', linestyle='-', alpha=0.5)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()
    
    def plot_monthly_heatmap(self, save_path: str = None):
        """Plot monthly returns heatmap"""
        monthly_returns = self.results.daily_returns.resample('M').apply(
            lambda x: (1 + x).prod() - 1
        ) * 100
        
        # Create monthly pivot table
        monthly_data = []
        for date, ret in monthly_returns.items():
            monthly_data.append({
                'year': date.year,
                'month': date.month,
                'return': ret
            })
        
        monthly_df = pd.DataFrame(monthly_data)
        
        if not monthly_df.empty:
            pivot_table = monthly_df.pivot(index='year', columns='month', values='return')
            
            plt.figure(figsize=(12, 8))
            sns.heatmap(pivot_table, annot=True, fmt='.1f', cmap='RdYlGn', 
                       center=0, cbar_kws={'label': 'Monthly Return (%)'})
            plt.title('Monthly Returns Heatmap')
            plt.xlabel('Month')
            plt.ylabel('Year')
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
    
    def get_monthly_returns(self) -> pd.DataFrame:
        """Calculate monthly returns"""
        monthly_returns = self.results.daily_returns.resample('M').apply(
            lambda x: (1 + x).prod() - 1
        ) * 100
        
        monthly_df = pd.DataFrame(monthly_returns)
        monthly_df.columns = ['Return (%)']
        monthly_df.index = monthly_df.index.strftime('%Y-%m')
        
        return monthly_df
    
    def calculate_trade_streaks(self) -> Dict:
        """Calculate winning and losing streaks"""
        if self.trades_df.empty:
            return {'max_win_streak': 0, 'max_loss_streak': 0}
        
        # Create win/loss series
        wins_losses = (self.trades_df['pnl'] > 0).astype(int)
        
        # Calculate streaks
        streaks = []
        current_streak = 1
        current_type = wins_losses.iloc[0]
        
        for i in range(1, len(wins_losses)):
            if wins_losses.iloc[i] == current_type:
                current_streak += 1
            else:
                streaks.append((current_type, current_streak))
                current_streak = 1
                current_type = wins_losses.iloc[i]
        
        # Add final streak
        streaks.append((current_type, current_streak))
        
        # Find max streaks
        win_streaks = [length for type_, length in streaks if type_ == 1]
        loss_streaks = [length for type_, length in streaks if type_ == 0]
        
        return {
            'max_win_streak': max(win_streaks) if win_streaks else 0,
            'max_loss_streak': max(loss_streaks) if loss_streaks else 0,
            'current_streak_type': 'win' if current_type == 1 else 'loss',
            'current_streak_length': current_streak
        }
    
    def analyze_trade_timing(self) -> Dict:
        """Analyze trade timing patterns"""
        if self.trades_df.empty:
            return {}
        
        # Add time components
        df = self.trades_df.copy()
        df['entry_hour'] = df['entry_time'].dt.hour
        df['entry_day_of_week'] = df['entry_time'].dt.dayofweek
        df['entry_month'] = df['entry_time'].dt.month
        
        analysis = {
            'hourly_pnl': df.groupby('entry_hour')['pnl'].mean().to_dict(),
            'daily_pnl': df.groupby('entry_day_of_week')['pnl'].mean().to_dict(),
            'monthly_pnl': df.groupby('entry_month')['pnl'].mean().to_dict(),
            'best_hour': df.groupby('entry_hour')['pnl'].mean().idxmax(),
            'worst_hour': df.groupby('entry_hour')['pnl'].mean().idxmin(),
            'best_day': df.groupby('entry_day_of_week')['pnl'].mean().idxmax(),
            'worst_day': df.groupby('entry_day_of_week')['pnl'].mean().idxmin()
        }
        
        return analysis
    
    def export_results_to_excel(self, filename: str):
        """Export comprehensive results to Excel file"""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': [
                    'Initial Capital', 'Final Capital', 'Total Return', 'Total Return %',
                    'CAGR', 'Max Drawdown', 'Max Drawdown %', 'Sharpe Ratio',
                    'Sortino Ratio', 'Total Trades', 'Win Rate', 'Profit Factor'
                ],
                'Value': [
                    self.results.initial_capital, self.results.final_capital,
                    self.results.total_return, self.results.total_return_pct,
                    self.results.cagr, self.results.max_drawdown, self.results.max_drawdown_pct,
                    self.results.sharpe_ratio, self.results.sortino_ratio,
                    self.results.total_trades, self.results.win_rate, self.results.profit_factor
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
            
            # Trades sheet
            if not self.trades_df.empty:
                self.trades_df.to_excel(writer, sheet_name='Trades', index=False)
            
            # Monthly returns
            monthly_returns = self.get_monthly_returns()
            monthly_returns.to_excel(writer, sheet_name='Monthly Returns')
            
            # Equity curve
            equity_data = pd.DataFrame({
                'Date': self.results.equity_curve.index,
                'Equity': self.results.equity_curve.values,
                'Drawdown': self.results.drawdown_curve.values
            })
            equity_data.to_excel(writer, sheet_name='Equity Curve', index=False)
        
        print(f"Results exported to {filename}")