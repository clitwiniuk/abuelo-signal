#!/usr/bin/env python3
"""
Backtest Results Analysis
Analyzes the CSV results from backtesting to identify patterns and optimization opportunities
"""

import pandas as pd
import sys
from pathlib import Path

def analyze_backtest_results(csv_file):
    """Analyze backtest results from CSV file"""
    
    # Load the CSV data
    try:
        df = pd.read_csv(csv_file)
        print(f"📊 BACKTEST RESULTS ANALYSIS")
        print("=" * 50)
        print(f"📁 File: {csv_file}")
        print(f"📈 Total trades: {len(df)}")
        
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file}")
        return
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return
    
    # Overall Performance Metrics
    print(f"\n💰 OVERALL PERFORMANCE:")
    total_pnl = df['pnl'].sum()
    total_pnl_pct = df['pnl_pct'].sum()
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = len(df[df['pnl'] < 0])
    win_rate = (winning_trades / len(df)) * 100 if len(df) > 0 else 0
    
    print(f"   💵 Total P&L: ${total_pnl:.2f}")
    print(f"   📊 Total P&L %: {total_pnl_pct:.2f}%")
    print(f"   ✅ Winning trades: {winning_trades}")
    print(f"   ❌ Losing trades: {losing_trades}")
    print(f"   📈 Win rate: {win_rate:.1f}%")
    
    if winning_trades > 0:
        avg_win = df[df['pnl'] > 0]['pnl'].mean()
        print(f"   💚 Average win: ${avg_win:.2f}")
    
    if losing_trades > 0:
        avg_loss = df[df['pnl'] < 0]['pnl'].mean()
        print(f"   💔 Average loss: ${avg_loss:.2f}")
    
    # Symbol Analysis
    print(f"\n🎯 SYMBOL PERFORMANCE:")
    symbol_stats = df.groupby('symbol').agg({
        'pnl': ['count', 'sum', 'mean'],
        'pnl_pct': 'mean'
    }).round(2)
    
    symbol_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'Avg_PnL_Pct']
    symbol_stats = symbol_stats.sort_values('Total_PnL', ascending=False)
    
    print("   Symbol | Trades | Total P&L | Avg P&L | Avg P&L %")
    print("   " + "-" * 50)
    for symbol, row in symbol_stats.iterrows():
        print(f"   {symbol:6} | {row['Trades']:6.0f} | ${row['Total_PnL']:8.2f} | ${row['Avg_PnL']:6.2f} | {row['Avg_PnL_Pct']:6.2f}%")
    
    # Exit Reason Analysis
    print(f"\n🚪 EXIT REASON ANALYSIS:")
    exit_stats = df.groupby('exit_reason').agg({
        'pnl': ['count', 'sum', 'mean']
    }).round(2)
    
    exit_stats.columns = ['Count', 'Total_PnL', 'Avg_PnL']
    exit_stats = exit_stats.sort_values('Total_PnL', ascending=False)
    
    print("   Exit Reason    | Count | Total P&L | Avg P&L")
    print("   " + "-" * 45)
    for reason, row in exit_stats.iterrows():
        print(f"   {reason:14} | {row['Count']:5.0f} | ${row['Total_PnL']:8.2f} | ${row['Avg_PnL']:6.2f}")
    
    # Time Analysis
    print(f"\n⏰ TIME PATTERN ANALYSIS:")
    df['entry_hour'] = pd.to_datetime(df['entry_time']).dt.hour
    time_stats = df.groupby('entry_hour').agg({
        'pnl': ['count', 'sum', 'mean']
    }).round(2)
    
    time_stats.columns = ['Count', 'Total_PnL', 'Avg_PnL']
    time_stats = time_stats.sort_values('Total_PnL', ascending=False)
    
    print("   Hour | Count | Total P&L | Avg P&L")
    print("   " + "-" * 35)
    for hour, row in time_stats.iterrows():
        print(f"   {hour:4.0f} | {row['Count']:5.0f} | ${row['Total_PnL']:8.2f} | ${row['Avg_PnL']:6.2f}")
    
    # Duration Analysis
    print(f"\n⏱️  DURATION ANALYSIS:")
    duration_bins = [0, 5, 15, 30, 60, 120, float('inf')]
    duration_labels = ['0-5min', '5-15min', '15-30min', '30-60min', '60-120min', '120min+']
    df['duration_bin'] = pd.cut(df['duration_minutes'], bins=duration_bins, labels=duration_labels, right=False)
    
    duration_stats = df.groupby('duration_bin').agg({
        'pnl': ['count', 'sum', 'mean']
    }).round(2)
    
    duration_stats.columns = ['Count', 'Total_PnL', 'Avg_PnL']
    
    print("   Duration   | Count | Total P&L | Avg P&L")
    print("   " + "-" * 40)
    for duration, row in duration_stats.iterrows():
        print(f"   {str(duration):10} | {row['Count']:5.0f} | ${row['Total_PnL']:8.2f} | ${row['Avg_PnL']:6.2f}")
    
    # Risk Metrics
    print(f"\n⚠️  RISK METRICS:")
    max_drawdown = df['max_drawdown'].min()  # Most negative value
    max_profit = df['max_profit_reached'].max()
    
    print(f"   📉 Worst drawdown: ${max_drawdown:.2f}")
    print(f"   📈 Best profit reached: ${max_profit:.2f}")
    
    # Recommendations
    print(f"\n💡 OPTIMIZATION OPPORTUNITIES:")
    
    # Best performing symbols
    best_symbols = symbol_stats[symbol_stats['Total_PnL'] > 0].head(3)
    if len(best_symbols) > 0:
        print(f"   🎯 Focus on profitable symbols: {', '.join(best_symbols.index.tolist())}")
    
    # Worst performing symbols
    worst_symbols = symbol_stats[symbol_stats['Total_PnL'] < -5].head(3)
    if len(worst_symbols) > 0:
        print(f"   ❌ Consider avoiding: {', '.join(worst_symbols.index.tolist())}")
    
    # Best times
    best_hours = time_stats[time_stats['Total_PnL'] > 0].head(3)
    if len(best_hours) > 0:
        print(f"   ⏰ Most profitable hours: {', '.join([f'{int(h):02d}:00' for h in best_hours.index.tolist()])}")
    
    # Worst times
    worst_hours = time_stats[time_stats['Total_PnL'] < -10].head(3)
    if len(worst_hours) > 0:
        print(f"   🚫 Avoid trading at: {', '.join([f'{int(h):02d}:00' for h in worst_hours.index.tolist()])}")
    
    # Exit reason insights
    if 'TRAILING_STOP' in exit_stats.index and 'END_OF_DAY' in exit_stats.index:
        ts_pnl = exit_stats.loc['TRAILING_STOP', 'Total_PnL']
        eod_pnl = exit_stats.loc['END_OF_DAY', 'Total_PnL']
        if eod_pnl > ts_pnl:
            print(f"   ⚙️  Consider adjusting trailing stop - END_OF_DAY exits perform better")
    
    print(f"\n" + "=" * 50)

if __name__ == "__main__":
    # Find the most recent backtest results file
    current_dir = Path(__file__).parent
    project_root = current_dir.parent
    
    # Look for CSV files in both backtesting directory and project root
    csv_files = list(current_dir.glob("backtest_results_*.csv")) + list(project_root.glob("backtest_results_*.csv"))
    
    if not csv_files:
        print("❌ No backtest results CSV files found")
        print("💡 Run 'python run_backtest.py' first to generate results")
        sys.exit(1)
    
    # Use the most recent file
    latest_csv = max(csv_files, key=lambda x: x.stat().st_mtime)
    analyze_backtest_results(latest_csv)