import streamlit as st
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header, render_status_badge
from datetime import datetime

# Apply custom styles
apply_custom_css()
init_session_state()

# Update timestamp
st.session_state['last_update'] = datetime.now()

# Header
render_header("📊 Overview", "Real-time trading dashboard • Live market monitoring")

# --- TOP KPI METRICS ---
stats = utils.get_pnl_stats()
if st.session_state['mock_mode']:
    stats = {'total_pnl': 1250.50, 'today_pnl': 345.20, 'win_rate': 65.4, 'total_trades': 12}

# System Status
is_running = utils.is_process_running()

# KPI Cards Row 1
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Net P&L (All Time)",
        f"${stats['total_pnl']:,.2f}",
        delta=None,
        help="Total cumulative profit/loss"
    )

with col2:
    delta_sign = "+" if stats['today_pnl'] >= 0 else ""
    st.metric(
        "Today's P&L",
        f"${stats['today_pnl']:,.2f}",
        delta=f"{delta_sign}${abs(stats['today_pnl']):,.2f}",
        delta_color="normal" if stats['today_pnl'] >= 0 else "inverse",
        help="Profit/loss for current trading day"
    )

with col3:
    st.metric(
        "Win Rate",
        f"{stats['win_rate']:.1f}%",
        delta=None,
        help="Percentage of profitable trades"
    )

with col4:
    st.metric(
        "Total Trades",
        f"{stats['total_trades']}",
        delta=None,
        help="Total number of executed trades"
    )

with col5:
    st.markdown(render_status_badge(is_running), unsafe_allow_html=True)
    st.caption("System Status")

st.markdown("<br>", unsafe_allow_html=True)

# --- TRADING & RISK METRICS ---
col_left, col_right = st.columns(2)

with col_left:
    render_section_header("💼 Trading Activity")

    trading_metrics = utils.get_trading_metrics()
    if st.session_state['mock_mode']:
        trading_metrics = {
            "active_positions": 3,
            "pending_orders": 0,
            "last_execution": "AAPL",
            "trades_today": 5
        }

    m1, m2 = st.columns(2)
    m1.metric("Active Positions", trading_metrics['active_positions'])
    m2.metric("Pending Orders", trading_metrics['pending_orders'])

    m3, m4 = st.columns(2)
    m3.metric("Last Execution", trading_metrics['last_execution'])
    m4.metric("Trades Today", trading_metrics['trades_today'])

with col_right:
    render_section_header("🛡️ Risk Management")

    risk_metrics = utils.get_risk_metrics()
    if st.session_state['mock_mode']:
        risk_metrics = {
            "daily_pnl": 345.20,
            "drawdown": -115.50,
            "max_loss": 500.0,
            "exposure": 2450.0
        }

    r1, r2 = st.columns(2)
    pnl_delta = "+" if risk_metrics['daily_pnl'] >= 0 else ""
    r1.metric(
        "Daily P&L",
        f"${risk_metrics['daily_pnl']:.2f}",
        delta=f"{pnl_delta}${abs(risk_metrics['daily_pnl']):.2f}",
        delta_color="normal" if risk_metrics['daily_pnl'] >= 0 else "inverse"
    )

    dd_pct = (risk_metrics['drawdown'] / 5000) * 100 if risk_metrics['drawdown'] != 0 else 0
    r2.metric(
        "Drawdown",
        f"${risk_metrics['drawdown']:.2f}",
        delta=f"{dd_pct:.1f}%",
        delta_color="inverse" if dd_pct < 0 else "normal"
    )

    r3, r4 = st.columns(2)
    r3.metric("Max Loss Allowed", f"${risk_metrics['max_loss']:.2f}")

    exposure_pct = (risk_metrics['exposure'] / 5000) * 100 if risk_metrics['exposure'] > 0 else 0
    r4.metric(
        "Current Exposure",
        f"${risk_metrics['exposure']:.2f}",
        delta=f"{exposure_pct:.1f}%"
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- ACTIVE POSITIONS & CONSOLE ---
render_section_header("📋 Active Operations")

tab_positions, tab_scanner, tab_console = st.tabs(["🎯 Active Positions", "📡 Scanner Feed", "📟 Live Console"])

with tab_positions:
    active_trades = utils.get_active_trades()
    if st.session_state['mock_mode']:
        active_trades = utils.generate_mock_data()

    if not active_trades.empty:
        # Display in 2-column grid
        for i in range(0, len(active_trades), 2):
            cols = st.columns(2)

            for j, col in enumerate(cols):
                if i + j < len(active_trades):
                    row = active_trades.iloc[i + j]
                    with col:
                        pnl_val = row['pnl']
                        pnl_color = "#00CC96" if pnl_val >= 0 else "#EF553B"
                        pnl_class = "positive" if pnl_val >= 0 else "negative"
                        side_badge = "LONG" if row['side'] == 'BUY' else "SHORT"
                        side_class = "long" if row['side'] == 'BUY' else "short"

                        # Calculate price change
                        entry_price = row.get('actual_entry_price', row['entry_price'])
                        current_price = row.get('current_price', entry_price)
                        price_change_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                        st.markdown(f"""
                        <div class="trade-card trade-card-{side_class} fade-in">
                            <div class="trade-header">
                                <div>
                                    <span class="trade-symbol">{row['symbol']}</span>
                                    <span class="trade-badge">{side_badge}</span>
                                </div>
                                <h3 class="trade-pnl {pnl_class}">${pnl_val:.2f}</h3>
                            </div>
                            <div class="trade-details">
                                <div class="trade-detail-item">
                                    <div class="trade-detail-label">Strategy</div>
                                    <div class="trade-detail-value">{row['strategy']}</div>
                                </div>
                                <div class="trade-detail-item">
                                    <div class="trade-detail-label">Quantity</div>
                                    <div class="trade-detail-value">{int(row['quantity'])}</div>
                                </div>
                                <div class="trade-detail-item">
                                    <div class="trade-detail-label">Entry Price</div>
                                    <div class="trade-detail-value">${entry_price:.2f}</div>
                                </div>
                                <div class="trade-detail-item">
                                    <div class="trade-detail-label">Current Price</div>
                                    <div class="trade-detail-value" style="color: {pnl_color}">
                                        ${current_price:.2f}
                                        <span style="font-size: 0.75rem">({price_change_pct:+.2f}%)</span>
                                    </div>
                                </div>
                            </div>
                            <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-secondary);">
                                🕒 Entry: {row.get('entry_time', 'N/A')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        st.info("💤 No active positions. Waiting for trading opportunities...")

with tab_scanner:
    st.markdown("### Latest Scanner Opportunities")

    scanner_df = utils.get_scanner_feed(limit=15)
    if not scanner_df.empty:
        display_df = scanner_df.copy()
        display_df['Time'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
        display_df = display_df[[
            'Time', 'symbol', 'current_price', 'gap_percentage',
            'volume_ratio', 'quality_score', 'catalyst_type'
        ]]
        display_df.columns = ['Time', 'Symbol', 'Price', 'Gap %', 'Vol Ratio', 'Quality', 'Catalyst']

        styled_df = display_df.style.format({
            'Price': '${:.2f}',
            'Gap %': '{:+.1f}%',
            'Vol Ratio': '{:.1f}x',
            'Quality': '{:.0f}'
        })

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=400)
    else:
        st.info("📊 Scanning for opportunities...")

with tab_console:
    st.markdown("### System Event Log")

    events = utils.parse_log_events(lines=100)

    if events:
        # Use a container with custom styling
        with st.container():
            # Apply console styling
            st.markdown("""
            <style>
                .console-log {
                    background: #1a1a1a;
                    border-radius: 12px;
                    padding: 1rem;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 0.875rem;
                    line-height: 1.6;
                    max-height: 600px;
                    overflow-y: auto;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.4);
                }
                .log-line {
                    margin-bottom: 0.5rem;
                    padding: 0.5rem;
                    border-left: 3px solid transparent;
                    border-radius: 4px;
                }
                .log-line.error {
                    border-left-color: #EF553B;
                    background: rgba(239, 85, 59, 0.05);
                }
                .log-line.warning {
                    border-left-color: #FFA500;
                    background: rgba(255, 165, 0, 0.05);
                }
                .log-line.success {
                    border-left-color: #00CC96;
                    background: rgba(0, 204, 150, 0.05);
                }
                .log-time {
                    color: #666;
                    font-size: 0.75rem;
                    margin-right: 0.75rem;
                }
                .log-msg {
                    color: #e0e0e0;
                    font-weight: 500;
                }
            </style>
            """, unsafe_allow_html=True)

            # Create log content
            log_content = '<div class="console-log">'

            for event in events[:50]:  # Limit to 50 most recent
                event_class = event['type'].lower()
                import html
                safe_message = html.escape(event['message'])

                log_content += f'<div class="log-line {event_class}">'
                log_content += f'<span class="log-time">{event["time"]}</span>'
                log_content += f'<span>{event["icon"]}</span> '
                log_content += f'<span class="log-msg">{safe_message}</span>'
                log_content += '</div>'

            log_content += '</div>'

            st.markdown(log_content, unsafe_allow_html=True)
    else:
        st.info("📋 Waiting for system events...")
