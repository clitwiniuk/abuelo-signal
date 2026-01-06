import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard.dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("🌐 Market Context", "Real-time market conditions and trading environment")

# Update timestamp
st.session_state['last_update'] = datetime.now()

# --- MARKET INDICES ---
render_section_header("📊 Major Indices & Market Indicators")

market_data = utils.get_market_indices()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    spy_change = market_data.get('SPY_change', 0.0)
    st.metric(
        "SPY (S&P 500)",
        f"${market_data.get('SPY_price', 0):.2f}",
        delta=f"{spy_change:+.2f}%",
        delta_color="normal" if spy_change >= 0 else "inverse",
        help="S&P 500 ETF - Overall market direction"
    )

with col2:
    qqq_change = market_data.get('QQQ_change', 0.0)
    st.metric(
        "QQQ (Nasdaq)",
        f"${market_data.get('QQQ_price', 0):.2f}",
        delta=f"{qqq_change:+.2f}%",
        delta_color="normal" if qqq_change >= 0 else "inverse",
        help="Nasdaq 100 ETF - Tech sector"
    )

with col3:
    iwm_change = market_data.get('IWM_change', 0.0)
    st.metric(
        "IWM (Russell 2000)",
        f"${market_data.get('IWM_price', 0):.2f}",
        delta=f"{iwm_change:+.2f}%",
        delta_color="normal" if iwm_change >= 0 else "inverse",
        help="Small cap index - Direct smallcap correlation"
    )

with col4:
    vix_val = market_data.get('VIX', 0.0)
    vix_status = "🟢 Low" if vix_val < 15 else "🟡 Medium" if vix_val < 25 else "🔴 High"
    st.metric(
        "VIX (Volatility)",
        f"{vix_val:.2f}",
        delta=vix_status,
        help="Market volatility index - Fear gauge"
    )

with col5:
    market_breadth = market_data.get('market_breadth', 0)
    breadth_color = "normal" if market_breadth > 0 else "inverse"
    st.metric(
        "Market Breadth",
        f"{market_breadth:+d}",
        delta=f"{'Bullish' if market_breadth > 0 else 'Bearish'}",
        delta_color=breadth_color,
        help="Advances minus Declines"
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- TRADING HOURS & SESSION INFO ---
render_section_header("⏰ Trading Session Info")

session_info = utils.get_trading_session_info()

col_left, col_right = st.columns(2)

with col_left:
    market_status = session_info.get('market_status', 'UNKNOWN')
    is_open = market_status == 'OPEN'

    status_color = '#00CC96' if is_open else '#EF553B'
    status_icon = '🟢' if is_open else '🔴'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Market Status</div>
        <h2 style="color: {status_color}; margin: 0.5rem 0;">
            {status_icon} {market_status}
        </h2>
        <div style="color: var(--text-secondary); font-size: 0.875rem;">
            Current Time: {session_info.get('current_time', 'N/A')} ET
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Session Schedule</div>
        <div style="margin-top: 0.5rem;">
            <div style="margin-bottom: 0.5rem;">
                <strong>Pre-Market:</strong> {session_info.get('premarket_time', '4:00 AM - 9:30 AM')} ET
            </div>
            <div style="margin-bottom: 0.5rem;">
                <strong>Regular:</strong> {session_info.get('regular_time', '9:30 AM - 4:00 PM')} ET
            </div>
            <div>
                <strong>After-Hours:</strong> {session_info.get('afterhours_time', '4:00 PM - 8:00 PM')} ET
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- SECTOR PERFORMANCE ---
render_section_header("📈 Sector Performance (Today)")

sector_data = utils.get_sector_performance()

if sector_data:
    # Create horizontal bar chart for sectors
    fig_sectors = go.Figure()

    sectors = list(sector_data.keys())
    performances = list(sector_data.values())
    colors = ['#00CC96' if x >= 0 else '#EF553B' for x in performances]

    fig_sectors.add_trace(go.Bar(
        y=sectors,
        x=performances,
        orientation='h',
        marker_color=colors,
        text=[f'{x:+.2f}%' for x in performances],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Change: %{x:+.2f}%<extra></extra>'
    ))

    fig_sectors.update_layout(
        xaxis_title='Performance (%)',
        yaxis_title='',
        height=400,
        template='plotly_white',
        font=dict(family='Inter, sans-serif'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        margin=dict(l=150, r=50, t=30, b=50)
    )

    st.plotly_chart(fig_sectors, use_container_width=True)
else:
    st.info("📊 Sector data unavailable")

st.markdown("<br>", unsafe_allow_html=True)

# --- MARKET SENTIMENT INDICATORS ---
render_section_header("🎯 Market Sentiment & Quality Indicators")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📊 Volume & Liquidity")

    volume_metrics = utils.get_volume_metrics()

    m1, m2 = st.columns(2)
    m1.metric(
        "NYSE Volume",
        f"{volume_metrics.get('nyse_volume', 0):,.0f}M",
        delta=f"{volume_metrics.get('nyse_vs_avg', 0):+.0f}% vs Avg",
        help="NYSE total volume compared to 20-day average"
    )

    m2.metric(
        "NASDAQ Volume",
        f"{volume_metrics.get('nasdaq_volume', 0):,.0f}M",
        delta=f"{volume_metrics.get('nasdaq_vs_avg', 0):+.0f}% vs Avg",
        help="NASDAQ total volume compared to 20-day average"
    )

    m3, m4 = st.columns(2)
    m3.metric(
        "New Highs",
        f"{volume_metrics.get('new_highs', 0)}",
        help="Stocks making 52-week highs today"
    )

    m4.metric(
        "New Lows",
        f"{volume_metrics.get('new_lows', 0)}",
        help="Stocks making 52-week lows today"
    )

with col2:
    st.markdown("#### 🔥 Smallcap Movers")

    top_movers = utils.get_smallcap_movers(limit=5)

    if not top_movers.empty:
        for idx, row in top_movers.iterrows():
            change_pct = row.get('change_pct', 0)
            color = '#00CC96' if change_pct >= 0 else '#EF553B'

            st.markdown(f"""
            <div style="padding: 0.75rem; margin-bottom: 0.5rem; background: var(--bg-card);
                        border-radius: 8px; border-left: 3px solid {color};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="font-size: 1rem;">{row['symbol']}</strong>
                        <span style="color: var(--text-secondary); margin-left: 0.5rem; font-size: 0.875rem;">
                            ${row.get('price', 0):.2f}
                        </span>
                    </div>
                    <div style="font-weight: 600; color: {color}; font-size: 1rem;">
                        {change_pct:+.2f}%
                    </div>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">
                    Vol: {row.get('volume', 0):,.0f} | Float: {row.get('float', 0):.1f}M
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("📊 No significant movers detected")

st.markdown("<br>", unsafe_allow_html=True)

# --- TRADING CONDITIONS SUMMARY ---
render_section_header("🎯 Trading Conditions Summary")

conditions = utils.get_trading_conditions()

col1, col2, col3 = st.columns(3)

with col1:
    trend_score = conditions.get('trend_score', 50)
    trend_color = '#00CC96' if trend_score >= 60 else '#FFA500' if trend_score >= 40 else '#EF553B'
    trend_label = 'Bullish' if trend_score >= 60 else 'Neutral' if trend_score >= 40 else 'Bearish'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Market Trend</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 2rem; font-weight: 700; color: {trend_color};">
                {trend_score}/100
            </div>
            <div style="font-size: 1rem; margin-top: 0.5rem; color: {trend_color};">
                {trend_label}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    volatility_score = conditions.get('volatility_score', 50)
    vol_color = '#00CC96' if volatility_score <= 40 else '#FFA500' if volatility_score <= 70 else '#EF553B'
    vol_label = 'Low' if volatility_score <= 40 else 'Medium' if volatility_score <= 70 else 'High'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Volatility Level</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 2rem; font-weight: 700; color: {vol_color};">
                {volatility_score}/100
            </div>
            <div style="font-size: 1rem; margin-top: 0.5rem; color: {vol_color};">
                {vol_label}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    opportunity_score = conditions.get('opportunity_score', 50)
    opp_color = '#00CC96' if opportunity_score >= 60 else '#FFA500' if opportunity_score >= 40 else '#EF553B'
    opp_label = 'High' if opportunity_score >= 60 else 'Medium' if opportunity_score >= 40 else 'Low'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Setup Quality</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 2rem; font-weight: 700; color: {opp_color};">
                {opportunity_score}/100
            </div>
            <div style="font-size: 1rem; margin-top: 0.5rem; color: {opp_color};">
                {opp_label}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Trading Recommendation
st.markdown("<br>", unsafe_allow_html=True)

recommendation = conditions.get('recommendation', 'Monitor market conditions')
recommendation_color = '#00CC96' if 'favorable' in recommendation.lower() else '#FFA500' if 'caution' in recommendation.lower() else '#EF553B'

st.markdown(f"""
<div style="padding: 1.5rem; background: var(--bg-card); border-radius: 12px;
            border-left: 4px solid {recommendation_color};">
    <div style="font-weight: 600; font-size: 0.875rem; color: var(--text-secondary);
                text-transform: uppercase; margin-bottom: 0.5rem;">
        Trading Recommendation
    </div>
    <div style="font-size: 1.125rem; color: var(--text-primary); font-weight: 500;">
        {recommendation}
    </div>
</div>
""", unsafe_allow_html=True)
