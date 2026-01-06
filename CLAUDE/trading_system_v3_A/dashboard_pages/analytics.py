import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("📈 Analytics", "Performance analytics and deep dive metrics")

# --- ADVANCED METRICS CARDS ---
render_section_header("🎯 Key Performance Indicators")

adv_metrics = utils.get_additional_metrics()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Sharpe Ratio",
        f"{adv_metrics['sharpe_ratio']:.2f}",
        help="Risk-adjusted return metric (higher is better)"
    )

with col2:
    st.metric(
        "Max Drawdown",
        f"${adv_metrics['max_drawdown']:.2f}",
        delta=f"{adv_metrics['max_drawdown_pct']:.1f}%",
        delta_color="inverse",
        help="Largest peak-to-trough decline"
    )

with col3:
    hours = adv_metrics['avg_duration_minutes'] / 60
    st.metric(
        "Avg Hold Time",
        f"{hours:.1f}h" if hours >= 1 else f"{adv_metrics['avg_duration_minutes']:.0f}m",
        help="Average trade duration"
    )

with col4:
    st.metric(
        "Best Day",
        f"${adv_metrics['best_day_pnl']:.2f}",
        delta="Best",
        delta_color="normal",
        help="Highest single-day P&L"
    )

with col5:
    st.metric(
        "Worst Day",
        f"${adv_metrics['worst_day_pnl']:.2f}",
        delta="Worst",
        delta_color="inverse",
        help="Lowest single-day P&L"
    )

# Second row of advanced metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Max Win Streak",
        f"{adv_metrics['max_consecutive_wins']}",
        help="Most consecutive winning trades"
    )

with col2:
    st.metric(
        "Max Loss Streak",
        f"{adv_metrics['max_consecutive_losses']}",
        help="Most consecutive losing trades"
    )

with col3:
    streak_color = "normal" if adv_metrics['current_streak_type'] == 'Wins' else "inverse"
    st.metric(
        "Current Streak",
        f"{adv_metrics['current_streak']} {adv_metrics['current_streak_type']}",
        delta=adv_metrics['current_streak_type'],
        delta_color=streak_color,
        help="Current consecutive wins or losses"
    )

st.markdown("<br>", unsafe_allow_html=True)

render_section_header("📈 Performance Analytics")

# Equity Curve
df_equity = utils.get_equity_curve()

if not df_equity.empty:
    # Main Equity Curve
    fig_equity = go.Figure()

    fig_equity.add_trace(go.Scatter(
        x=df_equity['time'],
        y=df_equity['cumulative_pnl'],
        mode='lines',
        name='Equity',
        line=dict(color='#00CC96', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 204, 150, 0.1)',
        hovertemplate='<b>Time:</b> %{x}<br><b>Equity:</b> $%{y:,.2f}<extra></extra>'
    ))

    fig_equity.update_layout(
        title='<b>Cumulative Equity Curve</b>',
        xaxis_title='Time',
        yaxis_title='Cumulative P&L ($)',
        hovermode='x unified',
        template='plotly_white',
        height=400,
        font=dict(family='Inter, sans-serif', size=12),
        title_font=dict(size=18, family='Inter, sans-serif'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    st.plotly_chart(fig_equity, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Secondary Charts
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### 📊 Today's Performance")
        df_intraday = utils.get_intraday_equity()

        if not df_intraday.empty:
            fig_intraday = go.Figure()
            fig_intraday.add_trace(go.Scatter(
                x=df_intraday['time'],
                y=df_intraday['cumulative_pnl'],
                mode='lines+markers',
                name='Intraday P&L',
                line=dict(color='#AB63FA', width=2),
                marker=dict(size=6),
                hovertemplate='<b>%{x}</b><br>P&L: $%{y:,.2f}<extra></extra>'
            ))

            fig_intraday.update_layout(
                xaxis_title='Time',
                yaxis_title='P&L ($)',
                hovermode='x unified',
                template='plotly_white',
                height=300,
                font=dict(family='Inter, sans-serif'),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )

            st.plotly_chart(fig_intraday, use_container_width=True)
        else:
            st.info("No intraday trades yet")

    with col_chart2:
        st.markdown("#### 💰 P&L Distribution")
        df_pnl = utils.get_pnl_distribution()

        if not df_pnl.empty:
            fig_hist = go.Figure()

            # Separate wins and losses
            wins = df_pnl[df_pnl['pnl'] > 0]['pnl']
            losses = df_pnl[df_pnl['pnl'] <= 0]['pnl']

            fig_hist.add_trace(go.Histogram(
                x=wins,
                name='Wins',
                marker_color='#00CC96',
                opacity=0.7,
                nbinsx=20
            ))

            fig_hist.add_trace(go.Histogram(
                x=losses,
                name='Losses',
                marker_color='#EF553B',
                opacity=0.7,
                nbinsx=20
            ))

            fig_hist.update_layout(
                xaxis_title='P&L ($)',
                yaxis_title='Frequency',
                hovermode='x unified',
                template='plotly_white',
                height=300,
                barmode='overlay',
                font=dict(family='Inter, sans-serif'),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )

            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No trade data available")

    st.markdown("<br>", unsafe_allow_html=True)

    # Advanced Analytics
    render_section_header("🧠 Advanced Analytics")

    df_analytics = utils.get_analytics_data()

    if not df_analytics.empty:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### 📊 Strategy Performance")
            strat_stats = df_analytics.groupby('strategy')['pnl'].sum().sort_values(ascending=False).reset_index()

            fig_strat = go.Figure()

            colors = ['#00CC96' if x >= 0 else '#EF553B' for x in strat_stats['pnl']]

            fig_strat.add_trace(go.Bar(
                x=strat_stats['strategy'],
                y=strat_stats['pnl'],
                marker_color=colors,
                text=strat_stats['pnl'].apply(lambda x: f'${x:,.0f}'),
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Total P&L: $%{y:,.2f}<extra></extra>'
            ))

            fig_strat.update_layout(
                xaxis_title='Strategy',
                yaxis_title='Total P&L ($)',
                template='plotly_white',
                height=350,
                font=dict(family='Inter, sans-serif'),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )

            st.plotly_chart(fig_strat, use_container_width=True)

        with col_b:
            st.markdown("#### 🕐 Hourly Performance")
            df_analytics['hour'] = df_analytics['entry_time'].dt.hour
            hourly_stats = df_analytics.groupby('hour')['pnl'].sum().reset_index()

            fig_hour = go.Figure()

            colors = ['#00CC96' if x >= 0 else '#EF553B' for x in hourly_stats['pnl']]

            fig_hour.add_trace(go.Bar(
                x=hourly_stats['hour'],
                y=hourly_stats['pnl'],
                marker_color=colors,
                hovertemplate='<b>Hour %{x}:00</b><br>P&L: $%{y:,.2f}<extra></extra>'
            ))

            fig_hour.update_layout(
                xaxis_title='Hour of Day',
                yaxis_title='P&L ($)',
                template='plotly_white',
                height=350,
                xaxis=dict(tickmode='linear', dtick=1),
                font=dict(family='Inter, sans-serif'),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False
            )

            st.plotly_chart(fig_hour, use_container_width=True)

        # Strategy Metrics Table
        st.markdown("#### 🎯 Strategy Efficiency Metrics")

        strategy_metrics = []
        for strat in df_analytics['strategy'].unique():
            s_df = df_analytics[df_analytics['strategy'] == strat]
            total = len(s_df)
            wins = len(s_df[s_df['pnl'] > 0])
            win_rate = (wins / total * 100) if total > 0 else 0
            avg_win = s_df[s_df['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
            avg_loss = s_df[s_df['pnl'] <= 0]['pnl'].mean() if (total - wins) > 0 else 0
            total_pnl = s_df['pnl'].sum()

            # Profit factor
            gross_profit = s_df[s_df['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(s_df[s_df['pnl'] < 0]['pnl'].sum())
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

            strategy_metrics.append({
                "Strategy": strat,
                "Trades": total,
                "Win Rate": f"{win_rate:.1f}%",
                "Total P&L": f"${total_pnl:,.2f}",
                "Profit Factor": f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞",
                "Avg Win": f"${avg_win:.2f}",
                "Avg Loss": f"${avg_loss:.2f}",
                "R:R Ratio": f"{abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "∞"
            })

        df_metrics = pd.DataFrame(strategy_metrics)

        # Style the dataframe
        def highlight_winrate(val):
            try:
                num = float(val.strip('%'))
                if num >= 60:
                    return 'background-color: rgba(0, 204, 150, 0.2)'
                elif num < 45:
                    return 'background-color: rgba(239, 85, 59, 0.2)'
            except:
                pass
            return ''

        styled_metrics = df_metrics.style.applymap(highlight_winrate, subset=['Win Rate'])

        st.dataframe(styled_metrics, use_container_width=True, hide_index=True)
    else:
        st.info("📊 Insufficient data for analytics. Start trading to see insights!")

else:
    st.warning("📈 No equity data available yet. Execute some trades to see analytics.")

# Trade Ledger
st.markdown("<br>", unsafe_allow_html=True)
render_section_header("📋 Trade History")

df_trades = utils.get_closed_trades(100)
if not df_trades.empty:
    # Add filters
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        filter_strategy = st.multiselect(
            "Filter by Strategy",
            options=df_trades['strategy'].unique() if 'strategy' in df_trades.columns else [],
            default=[]
        )

    with col_f2:
        filter_side = st.multiselect(
            "Filter by Side",
            options=df_trades['side'].unique() if 'side' in df_trades.columns else [],
            default=[]
        )

    # Apply filters
    filtered_df = df_trades.copy()
    if filter_strategy:
        filtered_df = filtered_df[filtered_df['strategy'].isin(filter_strategy)]
    if filter_side:
        filtered_df = filtered_df[filtered_df['side'].isin(filter_side)]

    # Display
    if not filtered_df.empty:
        styled_trades = filtered_df.style.format({
            'pnl': '${:.2f}',
            'entry_price': '${:.2f}',
            'exit_price': '${:.2f}',
            'commission': '${:.2f}'
        }).background_gradient(subset=['pnl'], cmap='RdYlGn')

        st.dataframe(styled_trades, use_container_width=True, height=400)

        # Summary stats
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Trades Shown", len(filtered_df))
        col_s2.metric("Total P&L", f"${filtered_df['pnl'].sum():,.2f}")
        col_s3.metric("Avg P&L", f"${filtered_df['pnl'].mean():.2f}")
        col_s4.metric("Best Trade", f"${filtered_df['pnl'].max():.2f}")
    else:
        st.info("No trades match the selected filters")
else:
    st.info("📋 No closed trades in history yet")

# --- ADDITIONAL ANALYSIS CHARTS ---
st.markdown("<br>", unsafe_allow_html=True)
render_section_header("📊 Additional Analysis")

col_chart3, col_chart4 = st.columns(2)

with col_chart3:
    st.markdown("#### 📅 Daily P&L Performance")
    daily_pnl_df = utils.get_daily_pnl_series()

    if not daily_pnl_df.empty:
        fig_daily = go.Figure()

        colors = ['#00CC96' if x >= 0 else '#EF553B' for x in daily_pnl_df['daily_pnl']]

        fig_daily.add_trace(go.Bar(
            x=daily_pnl_df['date'],
            y=daily_pnl_df['daily_pnl'],
            marker_color=colors,
            hovertemplate='<b>%{x}</b><br>Daily P&L: $%{y:,.2f}<extra></extra>'
        ))

        fig_daily.update_layout(
            xaxis_title='Date',
            yaxis_title='Daily P&L ($)',
            hovermode='x unified',
            template='plotly_white',
            height=350,
            font=dict(family='Inter, sans-serif'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )

        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.info("No daily P&L data available")

with col_chart4:
    st.markdown("#### ⏱️ Duration vs P&L Analysis")
    duration_df = utils.get_trade_duration_analysis()

    if not duration_df.empty:
        fig_duration = go.Figure()

        colors = ['#00CC96' if x >= 0 else '#EF553B' for x in duration_df['pnl']]

        fig_duration.add_trace(go.Scatter(
            x=duration_df['duration_minutes'],
            y=duration_df['pnl'],
            mode='markers',
            marker=dict(
                size=8,
                color=colors,
                opacity=0.7,
                line=dict(width=1, color='white')
            ),
            text=duration_df['strategy'],
            hovertemplate='<b>%{text}</b><br>Duration: %{x:.0f} min<br>P&L: $%{y:.2f}<extra></extra>'
        ))

        fig_duration.update_layout(
            xaxis_title='Trade Duration (minutes)',
            yaxis_title='P&L ($)',
            hovermode='closest',
            template='plotly_white',
            height=350,
            font=dict(family='Inter, sans-serif'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )

        st.plotly_chart(fig_duration, use_container_width=True)
    else:
        st.info("No duration data available")

# Win Rate Over Time
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("#### 📈 Win Rate Evolution (Rolling 20-trade window)")

if not df_trades.empty and len(df_trades) >= 20:
    # Calculate rolling win rate
    df_winrate = df_trades.copy()
    df_winrate['is_win'] = (df_winrate['pnl'] > 0).astype(int)
    df_winrate['rolling_winrate'] = df_winrate['is_win'].rolling(window=20, min_periods=1).mean() * 100

    fig_winrate = go.Figure()

    fig_winrate.add_trace(go.Scatter(
        x=df_winrate.index,
        y=df_winrate['rolling_winrate'],
        mode='lines',
        name='Rolling Win Rate',
        line=dict(color='#AB63FA', width=2),
        fill='tozeroy',
        fillcolor='rgba(171, 99, 250, 0.1)',
        hovertemplate='<b>Trade #%{x}</b><br>Win Rate: %{y:.1f}%<extra></extra>'
    ))

    # Add 50% reference line
    fig_winrate.add_hline(
        y=50,
        line_dash="dash",
        line_color="gray",
        annotation_text="50% Break-even",
        annotation_position="right"
    )

    fig_winrate.update_layout(
        xaxis_title='Trade Number',
        yaxis_title='Win Rate (%)',
        hovermode='x unified',
        template='plotly_white',
        height=300,
        font=dict(family='Inter, sans-serif'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        yaxis=dict(range=[0, 100])
    )

    st.plotly_chart(fig_winrate, use_container_width=True)
elif len(df_trades) > 0:
    st.info(f"Need at least 20 trades for rolling win rate (currently {len(df_trades)} trades)")
else:
    st.info("No trade data available for win rate analysis")
