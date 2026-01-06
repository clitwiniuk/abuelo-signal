#!/usr/bin/env python3
"""
Backtesting Results Analyzer
Analyzes CSV results from MACDV backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

def analyze_backtest_results(csv_file: str):
    """Analyze backtesting results from CSV file"""
    
    # Load results
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 BACKTEST RESULTS ANALYSIS")
        print(f"📁 File: {csv_file}")
        print("=" * 60)
        
        if df.empty:
            print("❌ No trades found in results file")
            return
        
        # Basic metrics
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        losing_trades = len(df[df['pnl'] <= 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df['pnl'].sum()
        avg_pnl = df['pnl'].mean()
        best_trade = df['pnl'].max()
        worst_trade = df['pnl'].min()
        
        # Duration metrics
        avg_duration = df['duration_minutes'].mean()
        median_duration = df['duration_minutes'].median()
        
        # Print summary
        print(f"🎯 OVERALL PERFORMANCE:")
        print(f"   Total trades: {total_trades}")
        print(f"   Winning trades: {winning_trades} ({win_rate:.1f}%)")
        print(f"   Losing trades: {losing_trades} ({100-win_rate:.1f}%)")
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Average P&L: ${avg_pnl:.2f}")
        print(f"   Best trade: ${best_trade:.2f}")
        print(f"   Worst trade: ${worst_trade:.2f}")
        print(f"   Average duration: {avg_duration:.1f} minutes")
        print(f"   Median duration: {median_duration:.1f} minutes")
        
        # Symbol performance
        print(f"\n📈 PERFORMANCE BY SYMBOL:")
        symbol_stats = df.groupby('symbol').agg({
            'pnl': ['count', 'sum', 'mean'],
            'duration_minutes': 'mean',
            'pnl_pct': 'mean'
        }).round(2)
        
        symbol_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'Avg_Duration', 'Avg_PnL_Pct']
        
        for symbol in symbol_stats.index:
            stats = symbol_stats.loc[symbol]
            symbol_trades = df[df['symbol'] == symbol]
            symbol_wins = len(symbol_trades[symbol_trades['pnl'] > 0])
            symbol_wr = (symbol_wins / stats['Trades']) * 100 if stats['Trades'] > 0 else 0
            
            print(f"   {symbol}: {int(stats['Trades'])} trades, ${stats['Total_PnL']:.2f} PnL, "
                  f"{symbol_wr:.1f}% WR, {stats['Avg_Duration']:.0f}min avg")
        
        # Exit reasons analysis
        print(f"\n🚪 EXIT REASONS:")
        exit_reasons = df['exit_reason'].value_counts()
        for reason, count in exit_reasons.items():
            pct = (count / total_trades) * 100
            reason_pnl = df[df['exit_reason'] == reason]['pnl'].sum()
            print(f"   {reason}: {count} trades ({pct:.1f}%) - P&L: ${reason_pnl:.2f}")
        
        # Trailing stop analysis
        print(f"\n🛑 TRAILING STOP ANALYSIS:")
        trailing_trades = df[df['exit_reason'] == 'TRAILING_STOP']
        if not trailing_trades.empty:
            trailing_pnl = trailing_trades['pnl'].sum()
            trailing_wins = len(trailing_trades[trailing_trades['pnl'] > 0])
            trailing_wr = (trailing_wins / len(trailing_trades)) * 100
            avg_trailing_duration = trailing_trades['duration_minutes'].mean()
            
            print(f"   Trailing stop trades: {len(trailing_trades)}")
            print(f"   Trailing stop P&L: ${trailing_pnl:.2f}")
            print(f"   Trailing stop win rate: {trailing_wr:.1f}%")
            print(f"   Average trailing duration: {avg_trailing_duration:.1f} minutes")
            
            # Max profit vs actual profit analysis
            trailing_trades_copy = trailing_trades.copy()
            trailing_trades_copy['profit_capture_ratio'] = trailing_trades_copy['pnl'] / trailing_trades_copy['max_profit_reached']
            avg_capture_ratio = trailing_trades_copy['profit_capture_ratio'].mean()
            print(f"   Average profit capture ratio: {avg_capture_ratio:.2f} ({avg_capture_ratio*100:.1f}%)")
        
        # Time analysis
        print(f"\n⏰ TIME ANALYSIS:")
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['entry_hour'] = df['entry_time'].dt.hour
        df['entry_minute'] = df['entry_time'].dt.minute
        df['entry_time_decimal'] = df['entry_hour'] + df['entry_minute'] / 60
        
        # Performance by hour
        hourly_stats = df.groupby('entry_hour').agg({
            'pnl': ['count', 'sum', 'mean']
        }).round(2)
        hourly_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL']
        
        print(f"   Performance by entry hour:")
        for hour in sorted(hourly_stats.index):
            stats = hourly_stats.loc[hour]
            print(f"     {hour:02d}:00 - {int(stats['Trades'])} trades, ${stats['Total_PnL']:.2f} total, ${stats['Avg_PnL']:.2f} avg")
        
        # Strategy analysis (if available)
        if 'strategy' in df.columns:
            print(f"\n🎯 STRATEGY PERFORMANCE:")
            strategy_stats = df.groupby('strategy').agg({
                'pnl': ['count', 'sum', 'mean'],
                'duration_minutes': 'mean'
            }).round(2)
            strategy_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'Avg_Duration']
            
            for strategy in strategy_stats.index:
                stats = strategy_stats.loc[strategy]
                strategy_trades = df[df['strategy'] == strategy]
                strategy_wins = len(strategy_trades[strategy_trades['pnl'] > 0])
                strategy_wr = (strategy_wins / stats['Trades']) * 100 if stats['Trades'] > 0 else 0
                
                print(f"   {strategy}: {int(stats['Trades'])} trades, ${stats['Total_PnL']:.2f} PnL, "
                      f"{strategy_wr:.1f}% WR, {stats['Avg_Duration']:.0f}min avg")
        
        # Risk metrics
        print(f"\n⚠️  RISK METRICS:")
        returns = df['pnl_pct'] / 100  # Convert to decimal
        
        if len(returns) > 1:
            volatility = returns.std() * np.sqrt(252)  # Annualized volatility (assuming daily trades)
            sharpe_ratio = (returns.mean() * 252) / volatility if volatility != 0 else 0
            max_drawdown_pct = df['max_drawdown'].min() if 'max_drawdown' in df.columns else 0
            
            print(f"   Average return per trade: {returns.mean()*100:.2f}%")
            print(f"   Return volatility: {returns.std()*100:.2f}%")
            print(f"   Sharpe ratio (annualized): {sharpe_ratio:.2f}")
            print(f"   Largest single loss: ${worst_trade:.2f}")
            
            # Profit factor
            gross_profit = df[df['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
            print(f"   Profit factor: {profit_factor:.2f}")
        
        # Recommendations
        print(f"\n💡 KEY INSIGHTS:")
        
        if win_rate < 50:
            print(f"   ⚠️  Win rate is low ({win_rate:.1f}%) - consider tightening entry criteria")
        
        if avg_duration > 60:
            print(f"   ⏱️  Average hold time is long ({avg_duration:.1f}min) - consider shorter stops")
        
        if total_pnl > 0:
            print(f"   ✅ System is profitable overall (+${total_pnl:.2f})")
        else:
            print(f"   ❌ System is losing money overall (${total_pnl:.2f})")
            
        # Check for best performing symbols
        if not symbol_stats.empty:
            best_symbol = symbol_stats.loc[symbol_stats['Total_PnL'].idxmax()]
            print(f"   🏆 Best performing symbol: {symbol_stats['Total_PnL'].idxmax()} (${best_symbol['Total_PnL']:.2f})")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"   1. Focus on symbols with positive P&L")
        print(f"   2. Analyze why trailing stops are working/not working")
        print(f"   3. Consider optimizing entry times (avoid unprofitable hours)")
        print(f"   4. Test with more historical data")
        print(f"   5. Consider adjusting trailing stop percentage")
        
    except Exception as e:
        print(f"❌ Error analyzing results: {e}")

if __name__ == "__main__":
    # Find most recent backtest results file
    csv_files = list(Path(".").glob("backtest_results_*.csv"))
    if csv_files:
        # Sort by modification time, get most recent
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        analyze_backtest_results(str(latest_file))
    else:
        print("❌ No backtest results files found")
        print("💡 Run 'python run_backtest.py' first to generate results")