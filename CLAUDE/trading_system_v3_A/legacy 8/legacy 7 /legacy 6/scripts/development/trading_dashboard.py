#!/usr/bin/env python3
"""
Trading Analytics Dashboard
===========================

Comprehensive Streamlit dashboard for analyzing trading_data.db
Provides detailed insights into trading performance, strategies, and patterns.
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Trading Analytics Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database path
DB_PATH = Path(__file__).parent / "trading_data.db"

@st.cache_data
def load_data():
    """Load data from trading database"""
    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}")
        return None, None, None, None
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load trades
    trades_df = pd.read_sql_query("""
        SELECT * FROM trades 
        ORDER BY entry_time DESC
    """, conn)
    
    # Load daily stats
    daily_stats_df = pd.read_sql_query("""
        SELECT * FROM daily_stats 
        ORDER BY date DESC
    """, conn)
    
    # Load advanced results
    advanced_df = pd.read_sql_query("""
        SELECT * FROM advanced_trading_results 
        ORDER BY trade_date DESC
    """, conn)
    
    # Load position risk config
    risk_config_df = pd.read_sql_query("""
        SELECT * FROM position_risk_config 
        WHERE is_active = 1
    """, conn)
    
    conn.close()
    
    # Process dates
    if not trades_df.empty:
        trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        trades_df['trade_date'] = trades_df['entry_time'].dt.date
    
    if not daily_stats_df.empty:
        daily_stats_df['date'] = pd.to_datetime(daily_stats_df['date'])
    
    if not advanced_df.empty:
        advanced_df['trade_date'] = pd.to_datetime(advanced_df['trade_date'])
    
    return trades_df, daily_stats_df, advanced_df, risk_config_df

def calculate_metrics(trades_df):
    """Calculate key trading metrics"""
    if trades_df.empty:
        return {}
    
    closed_trades = trades_df[trades_df['status'] == 'CLOSED']
    
    if closed_trades.empty:
        return {}
    
    total_trades = len(closed_trades)
    winning_trades = len(closed_trades[closed_trades['pnl'] > 0])
    losing_trades = len(closed_trades[closed_trades['pnl'] < 0])
    
    total_pnl = closed_trades['pnl'].sum()
    total_commission = closed_trades['commission'].sum()
    net_pnl = total_pnl - total_commission
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = closed_trades[closed_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = closed_trades[closed_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
    
    max_win = closed_trades['pnl'].max() if not closed_trades.empty else 0
    max_loss = closed_trades['pnl'].min() if not closed_trades.empty else 0
    
    profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else float('inf')
    
    avg_duration = closed_trades['duration_minutes'].mean() if 'duration_minutes' in closed_trades.columns else 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'net_pnl': net_pnl,
        'total_commission': total_commission,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_win': max_win,
        'max_loss': max_loss,
        'profit_factor': profit_factor,
        'avg_duration': avg_duration
    }

def main():
    st.title("📈 Trading Analytics Dashboard")
    st.markdown("---")
    
    # Load data
    trades_df, daily_stats_df, advanced_df, risk_config_df = load_data()
    
    if trades_df is None:
        st.error("Failed to load trading data")
        return
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    
    # Date range filter
    if not trades_df.empty:
        min_date = trades_df['entry_time'].min().date()
        max_date = trades_df['entry_time'].max().date()
        
        date_range = st.sidebar.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        # Strategy filter
        strategies = ['All'] + list(trades_df['strategy'].unique())
        selected_strategy = st.sidebar.selectbox("Strategy", strategies)
        
        # Status filter
        statuses = ['All'] + list(trades_df['status'].unique())
        selected_status = st.sidebar.selectbox("Status", statuses)
        
        # Apply filters
        filtered_df = trades_df.copy()
        
        if len(date_range) == 2:
            filtered_df = filtered_df[
                (filtered_df['entry_time'].dt.date >= date_range[0]) &
                (filtered_df['entry_time'].dt.date <= date_range[1])
            ]
        
        if selected_strategy != 'All':
            filtered_df = filtered_df[filtered_df['strategy'] == selected_strategy]
        
        if selected_status != 'All':
            filtered_df = filtered_df[filtered_df['status'] == selected_status]
    else:
        filtered_df = trades_df
    
    # Main dashboard
    if filtered_df.empty:
        st.warning("No trades found with current filters")
        return
    
    # Key Metrics
    st.header("📊 Key Metrics")
    metrics = calculate_metrics(filtered_df)
    
    if metrics:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Trades", metrics['total_trades'])
            st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
        
        with col2:
            st.metric("Net P&L", f"${metrics['net_pnl']:.2f}")
            st.metric("Gross P&L", f"${metrics['total_pnl']:.2f}")
        
        with col3:
            st.metric("Avg Win", f"${metrics['avg_win']:.2f}")
            st.metric("Avg Loss", f"${metrics['avg_loss']:.2f}")
        
        with col4:
            st.metric("Max Win", f"${metrics['max_win']:.2f}")
            st.metric("Max Loss", f"${metrics['max_loss']:.2f}")
        
        with col5:
            st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
            st.metric("Avg Duration", f"{metrics['avg_duration']:.0f}m")
    
    st.markdown("---")
    
    # Charts Section
    st.header("📈 Performance Analysis")
    
    # P&L Chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Cumulative P&L")
        closed_trades = filtered_df[filtered_df['status'] == 'CLOSED'].copy()
        if not closed_trades.empty:
            closed_trades = closed_trades.sort_values('entry_time')
            closed_trades['cumulative_pnl'] = closed_trades['pnl'].cumsum()
            
            fig = px.line(
                closed_trades, 
                x='entry_time', 
                y='cumulative_pnl',
                title="Cumulative P&L Over Time",
                labels={'cumulative_pnl': 'Cumulative P&L ($)', 'entry_time': 'Date'}
            )
            fig.update_traces(line_color='#1f77b4', line_width=2)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("P&L Distribution")
        if not closed_trades.empty:
            fig = px.histogram(
                closed_trades, 
                x='pnl',
                nbins=20,
                title="P&L Distribution",
                labels={'pnl': 'P&L ($)', 'count': 'Number of Trades'}
            )
            fig.add_vline(x=0, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
    
    # Strategy Performance
    st.subheader("Strategy Performance")
    if not filtered_df.empty:
        strategy_stats = filtered_df[filtered_df['status'] == 'CLOSED'].groupby('strategy').agg({
            'pnl': ['count', 'sum', 'mean'],
            'commission': 'sum'
        }).round(2)
        
        strategy_stats.columns = ['Trades', 'Total P&L', 'Avg P&L', 'Total Commission']
        strategy_stats['Net P&L'] = strategy_stats['Total P&L'] - strategy_stats['Total Commission']
        strategy_stats['Win Rate'] = filtered_df[filtered_df['status'] == 'CLOSED'].groupby('strategy').apply(
            lambda x: (x['pnl'] > 0).sum() / len(x) * 100
        ).round(1)
        
        st.dataframe(strategy_stats, use_container_width=True)
    
    # Symbol Performance
    st.subheader("Symbol Performance")
    if not filtered_df.empty:
        symbol_stats = filtered_df[filtered_df['status'] == 'CLOSED'].groupby('symbol').agg({
            'pnl': ['count', 'sum', 'mean'],
            'entry_price': 'mean',
            'exit_price': 'mean'
        }).round(2)
        
        symbol_stats.columns = ['Trades', 'Total P&L', 'Avg P&L', 'Avg Entry', 'Avg Exit']
        symbol_stats = symbol_stats.sort_values('Total P&L', ascending=False)
        
        st.dataframe(symbol_stats, use_container_width=True)
    
    # Detailed Trades Table
    st.header("📋 Trade Details")
    
    # Display options
    col1, col2 = st.columns(2)
    with col1:
        show_all_columns = st.checkbox("Show all columns", value=False)
    with col2:
        max_rows = st.selectbox("Max rows to display", [10, 25, 50, 100], index=1)
    
    # Prepare display dataframe
    display_df = filtered_df.head(max_rows).copy()
    
    if not show_all_columns:
        # Show key columns only
        key_columns = [
            'trade_id', 'symbol', 'strategy', 'side', 'quantity', 
            'entry_price', 'exit_price', 'pnl', 'status', 'entry_time'
        ]
        display_df = display_df[[col for col in key_columns if col in display_df.columns]]
    
    # Format for display
    if 'entry_time' in display_df.columns:
        display_df['entry_time'] = display_df['entry_time'].dt.strftime('%Y-%m-%d %H:%M')
    if 'exit_time' in display_df.columns:
        display_df['exit_time'] = display_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
    
    st.dataframe(display_df, use_container_width=True)
    
    # Active Positions
    if not risk_config_df.empty:
        st.header("🎯 Active Positions")
        st.dataframe(risk_config_df, use_container_width=True)
    
    # Daily Stats
    if not daily_stats_df.empty:
        st.header("📅 Daily Statistics")
        st.dataframe(daily_stats_df.head(10), use_container_width=True)
    
    # Advanced Analysis
    if not advanced_df.empty:
        st.header("🔬 Advanced Analysis")
        
        # Show sample of advanced data
        st.subheader("Detailed Trade Analysis")
        advanced_display = advanced_df[['ticker', 'trade_date', 'pnl', 'strategy_used', 'execution_quality', 'key_takeaways']].head(10)
        st.dataframe(advanced_display, use_container_width=True)
    
    # Export functionality
    st.header("💾 Export Data")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Export Trades CSV"):
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="Download Trades CSV",
                data=csv,
                file_name=f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if not daily_stats_df.empty and st.button("Export Daily Stats CSV"):
            csv = daily_stats_df.to_csv(index=False)
            st.download_button(
                label="Download Daily Stats CSV",
                data=csv,
                file_name=f"daily_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col3:
        if not advanced_df.empty and st.button("Export Advanced Analysis CSV"):
            csv = advanced_df.to_csv(index=False)
            st.download_button(
                label="Download Advanced Analysis CSV",
                data=csv,
                file_name=f"advanced_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
