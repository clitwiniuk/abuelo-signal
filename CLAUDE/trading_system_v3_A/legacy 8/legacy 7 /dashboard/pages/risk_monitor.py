import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard.dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header
import plotly.graph_objects as go
import pandas as pd

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("⚠️ Risk Monitor", "Real-time risk exposure and portfolio health")

# Update timestamp
st.session_state['last_update'] = datetime.now()

# --- REAL-TIME RISK METRICS ---
render_section_header("🎯 Real-Time Risk Metrics")

risk_data = utils.get_comprehensive_risk_metrics()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    current_exposure = risk_data.get('current_exposure', 0)
    max_exposure = risk_data.get('max_exposure', 10000)
    exposure_pct = (current_exposure / max_exposure * 100) if max_exposure > 0 else 0

    st.metric(
        "Total Exposure",
        f"${current_exposure:,.2f}",
        delta=f"{exposure_pct:.1f}% of limit",
        help=f"Maximum allowed: ${max_exposure:,.2f}"
    )

with col2:
    daily_pnl = risk_data.get('daily_pnl', 0)
    pnl_color = "normal" if daily_pnl >= 0 else "inverse"

    st.metric(
        "Daily P&L",
        f"${daily_pnl:,.2f}",
        delta=f"{daily_pnl:+.2f}",
        delta_color=pnl_color,
        help="Profit/Loss for current trading day"
    )

with col3:
    max_loss_limit = risk_data.get('max_loss_limit', -500)
    distance_to_limit = abs(daily_pnl - max_loss_limit) if daily_pnl < 0 else abs(max_loss_limit)

    st.metric(
        "Loss Limit Distance",
        f"${distance_to_limit:.2f}",
        delta=f"Limit: ${max_loss_limit:.2f}",
        help="Distance to max daily loss limit"
    )

with col4:
    active_positions = risk_data.get('active_positions', 0)
    max_positions = risk_data.get('max_positions', 5)

    st.metric(
        "Active Positions",
        f"{active_positions}/{max_positions}",
        delta=f"{max_positions - active_positions} slots available",
        help="Current positions vs maximum allowed"
    )

with col5:
    concentration = risk_data.get('max_position_concentration', 0)
    conc_color = "normal" if concentration < 30 else "inverse"

    st.metric(
        "Max Concentration",
        f"{concentration:.1f}%",
        delta="Healthy" if concentration < 30 else "High",
        delta_color=conc_color,
        help="Largest position as % of total exposure"
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- EXPOSURE BREAKDOWN ---
render_section_header("📊 Exposure Breakdown")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 💰 Capital Allocation")

    # Gauge chart for capital usage
    exposure_pct = (current_exposure / max_exposure * 100) if max_exposure > 0 else 0

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=exposure_pct,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Capital Utilization", 'font': {'size': 16}},
        delta={'reference': 80, 'suffix': '%'},
        gauge={
            'axis': {'range': [None, 100], 'ticksuffix': '%'},
            'bar': {'color': "#00CC96"},
            'steps': [
                {'range': [0, 50], 'color': "rgba(0, 204, 150, 0.1)"},
                {'range': [50, 80], 'color': "rgba(255, 165, 0, 0.1)"},
                {'range': [80, 100], 'color': "rgba(239, 85, 59, 0.1)"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))

    fig_gauge.update_layout(
        height=300,
        font={'family': 'Inter, sans-serif'},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    st.plotly_chart(fig_gauge, use_container_width=True)

with col_right:
    st.markdown("#### 📈 Position Distribution")

    position_breakdown = utils.get_position_breakdown()

    if not position_breakdown.empty:
        fig_pie = go.Figure(data=[go.Pie(
            labels=position_breakdown['symbol'],
            values=position_breakdown['exposure'],
            hole=0.4,
            marker=dict(
                colors=['#00CC96', '#AB63FA', '#FFA500', '#00D4FF', '#EF553B'],
                line=dict(color='white', width=2)
            ),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Exposure: $%{value:,.2f}<br>%{percent}<extra></extra>'
        )])

        fig_pie.update_layout(
            height=300,
            font=dict(family='Inter, sans-serif'),
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("📊 No active positions")

st.markdown("<br>", unsafe_allow_html=True)

# --- RISK LIMITS & ALERTS ---
render_section_header("🚨 Risk Limits & Status")

limits = utils.get_risk_limits()

# Create risk limit cards
col1, col2, col3 = st.columns(3)

with col1:
    daily_loss = abs(daily_pnl) if daily_pnl < 0 else 0
    daily_loss_limit = abs(limits.get('max_daily_loss', 500))
    daily_loss_pct = (daily_loss / daily_loss_limit * 100) if daily_loss_limit > 0 else 0

    status_color = '#00CC96' if daily_loss_pct < 50 else '#FFA500' if daily_loss_pct < 80 else '#EF553B'
    status_icon = '🟢' if daily_loss_pct < 50 else '🟡' if daily_loss_pct < 80 else '🔴'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Daily Loss Limit</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 1.5rem; font-weight: 700; color: {status_color};">
                {status_icon} ${daily_loss:.2f} / ${daily_loss_limit:.2f}
            </div>
            <div style="margin-top: 0.5rem;">
                <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: {status_color}; height: 100%; width: {min(daily_loss_pct, 100):.0f}%;
                                transition: width 0.3s ease;"></div>
                </div>
                <div style="margin-top: 0.25rem; font-size: 0.875rem; color: var(--text-secondary);">
                    {daily_loss_pct:.1f}% used
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    position_limit = limits.get('max_positions', 5)
    positions_pct = (active_positions / position_limit * 100) if position_limit > 0 else 0

    status_color = '#00CC96' if positions_pct < 80 else '#FFA500' if positions_pct < 100 else '#EF553B'
    status_icon = '🟢' if positions_pct < 80 else '🟡' if positions_pct < 100 else '🔴'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Position Limit</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 1.5rem; font-weight: 700; color: {status_color};">
                {status_icon} {active_positions} / {position_limit}
            </div>
            <div style="margin-top: 0.5rem;">
                <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: {status_color}; height: 100%; width: {min(positions_pct, 100):.0f}%;
                                transition: width 0.3s ease;"></div>
                </div>
                <div style="margin-top: 0.25rem; font-size: 0.875rem; color: var(--text-secondary);">
                    {positions_pct:.1f}% used
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    exposure_limit = limits.get('max_exposure', 10000)
    exposure_used_pct = (current_exposure / exposure_limit * 100) if exposure_limit > 0 else 0

    status_color = '#00CC96' if exposure_used_pct < 80 else '#FFA500' if exposure_used_pct < 100 else '#EF553B'
    status_icon = '🟢' if exposure_used_pct < 80 else '🟡' if exposure_used_pct < 100 else '🔴'

    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Exposure Limit</div>
        <div style="margin-top: 1rem;">
            <div style="font-size: 1.5rem; font-weight: 700; color: {status_color};">
                {status_icon} ${current_exposure:.0f} / ${exposure_limit:.0f}
            </div>
            <div style="margin-top: 0.5rem;">
                <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background: {status_color}; height: 100%; width: {min(exposure_used_pct, 100):.0f}%;
                                transition: width 0.3s ease;"></div>
                </div>
                <div style="margin-top: 0.25rem; font-size: 0.875rem; color: var(--text-secondary);">
                    {exposure_used_pct:.1f}% used
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- POSITION RISK DETAILS ---
render_section_header("📋 Position Risk Details")

position_risks = utils.get_position_risk_details()

if not position_risks.empty:
    # Style the dataframe
    styled_df = position_risks.style.format({
        'exposure': '${:,.2f}',
        'unrealized_pnl': '${:,.2f}',
        'risk_score': '{:.0f}',
        'stop_loss': '${:.2f}',
        'distance_to_stop': '{:.2f}%'
    }).background_gradient(
        subset=['risk_score'],
        cmap='RdYlGn_r',
        vmin=0,
        vmax=100
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=300)

    # Summary stats
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    col_s1.metric("Positions Shown", len(position_risks))
    col_s2.metric("Total Exposure", f"${position_risks['exposure'].sum():,.2f}")
    col_s3.metric("Total P&L", f"${position_risks['unrealized_pnl'].sum():,.2f}")
    col_s4.metric("Avg Risk Score", f"{position_risks['risk_score'].mean():.0f}/100")
else:
    st.info("📊 No active positions to analyze")

st.markdown("<br>", unsafe_allow_html=True)

# --- DRAWDOWN ANALYSIS ---
render_section_header("📉 Drawdown Analysis")

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### 💧 Current Drawdown")

    drawdown_data = utils.get_drawdown_series()

    if not drawdown_data.empty:
        fig_dd = go.Figure()

        fig_dd.add_trace(go.Scatter(
            x=drawdown_data['date'],
            y=drawdown_data['drawdown'],
            mode='lines',
            fill='tozeroy',
            name='Drawdown',
            line=dict(color='#EF553B', width=2),
            fillcolor='rgba(239, 85, 59, 0.1)',
            hovertemplate='<b>%{x}</b><br>Drawdown: %{y:.2f}%<extra></extra>'
        ))

        fig_dd.update_layout(
            xaxis_title='Date',
            yaxis_title='Drawdown (%)',
            hovermode='x unified',
            template='plotly_white',
            height=300,
            font=dict(family='Inter, sans-serif'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )

        st.plotly_chart(fig_dd, use_container_width=True)
    else:
        st.info("No drawdown data available")

with col_chart2:
    st.markdown("#### 📊 Risk Distribution")

    risk_distribution = utils.get_risk_distribution()

    if risk_distribution:
        categories = list(risk_distribution.keys())
        values = list(risk_distribution.values())
        colors = ['#00CC96', '#FFA500', '#EF553B']

        fig_risk = go.Figure(data=[go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=values,
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
        )])

        fig_risk.update_layout(
            xaxis_title='Risk Level',
            yaxis_title='Number of Positions',
            template='plotly_white',
            height=300,
            font=dict(family='Inter, sans-serif'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )

        st.plotly_chart(fig_risk, use_container_width=True)
    else:
        st.info("No risk distribution data")

# --- RISK ALERTS ---
st.markdown("<br>", unsafe_allow_html=True)
render_section_header("⚠️ Active Risk Alerts")

alerts = utils.get_active_risk_alerts()

if alerts:
    for alert in alerts:
        severity = alert.get('severity', 'info')
        icon = '🔴' if severity == 'critical' else '🟡' if severity == 'warning' else '🔵'
        color = '#EF553B' if severity == 'critical' else '#FFA500' if severity == 'warning' else '#00D4FF'

        st.markdown(f"""
        <div style="padding: 1rem; margin-bottom: 0.75rem; background: var(--bg-card);
                    border-radius: 8px; border-left: 4px solid {color};">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span style="font-size: 1.5rem;">{icon}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 1rem; color: var(--text-primary);">
                        {alert.get('title', 'Alert')}
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        {alert.get('message', '')}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">
                        {alert.get('timestamp', '')}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("✅ No active risk alerts. All systems within normal parameters.")
