import streamlit as st
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard.dashboard_utils as utils
from dashboard_shared import apply_custom_css, init_session_state, render_header, render_section_header

# Apply custom styles
apply_custom_css()
init_session_state()

# Header
render_header("🔔 Alerts & Notifications", "Configure alerts and monitor trading events")

# Update timestamp
st.session_state['last_update'] = datetime.now()

# --- ACTIVE ALERTS ---
render_section_header("🚨 Active Alerts")

active_alerts = utils.get_recent_alerts(limit=20)

if active_alerts:
    # Filter controls
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        severity_filter = st.multiselect(
            "Filter by Severity",
            options=['Critical', 'Warning', 'Info'],
            default=['Critical', 'Warning', 'Info']
        )

    with col_f2:
        category_filter = st.multiselect(
            "Filter by Category",
            options=['Risk', 'Position', 'Market', 'System'],
            default=['Risk', 'Position', 'Market', 'System']
        )

    with col_f3:
        time_filter = st.selectbox(
            "Time Range",
            options=['Last Hour', 'Last 4 Hours', 'Today', 'Last 24h', 'All'],
            index=3
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Display alerts
    for alert in active_alerts:
        severity = alert.get('severity', 'info').lower()
        category = alert.get('category', 'System')

        # Apply filters
        if severity.capitalize() not in severity_filter:
            continue
        if category not in category_filter:
            continue

        # Icon and color based on severity
        if severity == 'critical':
            icon = '🔴'
            color = '#EF553B'
            bg_color = 'rgba(239, 85, 59, 0.05)'
        elif severity == 'warning':
            icon = '🟡'
            color = '#FFA500'
            bg_color = 'rgba(255, 165, 0, 0.05)'
        else:
            icon = '🔵'
            color = '#00D4FF'
            bg_color = 'rgba(0, 212, 255, 0.05)'

        # Category icon
        cat_icons = {
            'Risk': '⚠️',
            'Position': '📊',
            'Market': '🌐',
            'System': '🛡️'
        }
        cat_icon = cat_icons.get(category, '📌')

        timestamp = alert.get('timestamp', '')
        title = alert.get('title', 'Alert')
        message = alert.get('message', '')
        details = alert.get('details', '')

        st.markdown(f"""
        <div style="padding: 1.25rem; margin-bottom: 1rem; background: {bg_color};
                    border-radius: 12px; border-left: 4px solid {color};
                    transition: all 0.3s ease;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="display: flex; align-items: start; gap: 1rem; flex: 1;">
                    <div style="font-size: 1.75rem;">{icon}</div>
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span style="font-size: 0.875rem;">{cat_icon}</span>
                            <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-secondary);
                                        text-transform: uppercase; letter-spacing: 0.5px;">
                                {category}
                            </span>
                        </div>
                        <div style="font-weight: 600; font-size: 1.125rem; color: var(--text-primary);
                                    margin-bottom: 0.5rem;">
                            {title}
                        </div>
                        <div style="font-size: 0.9375rem; color: var(--text-primary); line-height: 1.5;
                                    margin-bottom: 0.5rem;">
                            {message}
                        </div>
                        {f'<div style="font-size: 0.875rem; color: var(--text-secondary); font-family: monospace; margin-top: 0.5rem; padding: 0.5rem; background: rgba(0,0,0,0.05); border-radius: 4px;">{details}</div>' if details else ''}
                    </div>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap;
                            margin-left: 1rem;">
                    {timestamp}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("🎉 No alerts at this time. All systems operating normally.")

st.markdown("<br>", unsafe_allow_html=True)

# --- ALERT CONFIGURATION ---
render_section_header("⚙️ Alert Configuration")

st.markdown("Configure thresholds for automatic alerts")

col_config1, col_config2 = st.columns(2)

with col_config1:
    st.markdown("#### 💰 P&L Alerts")

    with st.form("pnl_alerts"):
        enable_pnl_alerts = st.toggle("Enable P&L Alerts", value=True)

        col_p1, col_p2 = st.columns(2)

        with col_p1:
            daily_loss_alert = st.number_input(
                "Daily Loss Alert ($)",
                min_value=0.0,
                value=300.0,
                step=50.0,
                help="Alert when daily loss exceeds this amount"
            )

            daily_profit_alert = st.number_input(
                "Daily Profit Target ($)",
                min_value=0.0,
                value=500.0,
                step=50.0,
                help="Alert when daily profit reaches this amount"
            )

        with col_p2:
            position_loss_alert = st.number_input(
                "Position Loss Alert ($)",
                min_value=0.0,
                value=100.0,
                step=10.0,
                help="Alert when single position loss exceeds this amount"
            )

            position_profit_alert = st.number_input(
                "Position Profit Alert ($)",
                min_value=0.0,
                value=150.0,
                step=10.0,
                help="Alert when single position profit reaches this amount"
            )

        submitted_pnl = st.form_submit_button("💾 Save P&L Alerts", use_container_width=True)

        if submitted_pnl:
            # Save configuration
            utils.save_alert_config('pnl_alerts', {
                'enabled': enable_pnl_alerts,
                'daily_loss': daily_loss_alert,
                'daily_profit': daily_profit_alert,
                'position_loss': position_loss_alert,
                'position_profit': position_profit_alert
            })
            st.success("✅ P&L alerts configuration saved!")

with col_config2:
    st.markdown("#### ⚠️ Risk Alerts")

    with st.form("risk_alerts"):
        enable_risk_alerts = st.toggle("Enable Risk Alerts", value=True)

        col_r1, col_r2 = st.columns(2)

        with col_r1:
            exposure_alert = st.number_input(
                "Exposure Alert (%)",
                min_value=0,
                max_value=100,
                value=85,
                step=5,
                help="Alert when capital utilization exceeds this %"
            )

            drawdown_alert = st.number_input(
                "Drawdown Alert (%)",
                min_value=0,
                max_value=100,
                value=15,
                step=5,
                help="Alert when drawdown exceeds this %"
            )

        with col_r2:
            position_limit_alert = st.number_input(
                "Position Limit Alert",
                min_value=0,
                max_value=10,
                value=5,
                step=1,
                help="Alert when approaching max positions"
            )

            concentration_alert = st.number_input(
                "Concentration Alert (%)",
                min_value=0,
                max_value=100,
                value=40,
                step=5,
                help="Alert when single position exceeds this % of portfolio"
            )

        submitted_risk = st.form_submit_button("💾 Save Risk Alerts", use_container_width=True)

        if submitted_risk:
            # Save configuration
            utils.save_alert_config('risk_alerts', {
                'enabled': enable_risk_alerts,
                'exposure': exposure_alert,
                'drawdown': drawdown_alert,
                'position_limit': position_limit_alert,
                'concentration': concentration_alert
            })
            st.success("✅ Risk alerts configuration saved!")

st.markdown("<br>", unsafe_allow_html=True)

col_config3, col_config4 = st.columns(2)

with col_config3:
    st.markdown("#### 🌐 Market Alerts")

    with st.form("market_alerts"):
        enable_market_alerts = st.toggle("Enable Market Alerts", value=True)

        vix_alert = st.number_input(
            "VIX Alert Level",
            min_value=0.0,
            value=30.0,
            step=5.0,
            help="Alert when VIX exceeds this level"
        )

        market_drop_alert = st.number_input(
            "Market Drop Alert (%)",
            min_value=0.0,
            value=2.0,
            step=0.5,
            help="Alert when SPY drops more than this % intraday"
        )

        volume_alert = st.number_input(
            "Unusual Volume Alert (x avg)",
            min_value=1.0,
            value=3.0,
            step=0.5,
            help="Alert when volume is X times the average"
        )

        submitted_market = st.form_submit_button("💾 Save Market Alerts", use_container_width=True)

        if submitted_market:
            utils.save_alert_config('market_alerts', {
                'enabled': enable_market_alerts,
                'vix_level': vix_alert,
                'market_drop': market_drop_alert,
                'volume_multiplier': volume_alert
            })
            st.success("✅ Market alerts configuration saved!")

with col_config4:
    st.markdown("#### 🛡️ System Alerts")

    with st.form("system_alerts"):
        enable_system_alerts = st.toggle("Enable System Alerts", value=True)

        connection_alert = st.toggle(
            "Alert on Connection Loss",
            value=True,
            help="Alert when connection to broker is lost"
        )

        execution_alert = st.toggle(
            "Alert on Failed Orders",
            value=True,
            help="Alert when order execution fails"
        )

        worker_alert = st.toggle(
            "Alert on Worker Errors",
            value=True,
            help="Alert when strategy workers encounter errors"
        )

        submitted_system = st.form_submit_button("💾 Save System Alerts", use_container_width=True)

        if submitted_system:
            utils.save_alert_config('system_alerts', {
                'enabled': enable_system_alerts,
                'connection_loss': connection_alert,
                'failed_orders': execution_alert,
                'worker_errors': worker_alert
            })
            st.success("✅ System alerts configuration saved!")

st.markdown("<br>", unsafe_allow_html=True)

# --- ALERT STATISTICS ---
render_section_header("📊 Alert Statistics")

col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)

alert_stats = utils.get_alert_statistics()

col_stat1.metric(
    "Total Alerts (24h)",
    alert_stats.get('total_24h', 0),
    help="Total alerts in last 24 hours"
)

col_stat2.metric(
    "Critical",
    alert_stats.get('critical', 0),
    delta="High Priority",
    delta_color="inverse",
    help="Critical alerts requiring immediate attention"
)

col_stat3.metric(
    "Warnings",
    alert_stats.get('warnings', 0),
    delta="Medium Priority",
    help="Warning alerts"
)

col_stat4.metric(
    "Info",
    alert_stats.get('info', 0),
    delta="Low Priority",
    delta_color="off",
    help="Informational alerts"
)

col_stat5.metric(
    "Most Frequent",
    alert_stats.get('most_frequent_type', 'N/A'),
    help="Most common alert type"
)

st.markdown("<br>", unsafe_allow_html=True)

# --- NOTIFICATION PREFERENCES ---
render_section_header("🔔 Notification Preferences")

st.info("💡 **Coming Soon**: Email and Telegram notifications. Currently alerts are displayed in dashboard only.")

col_notif1, col_notif2 = st.columns(2)

with col_notif1:
    st.markdown("#### 📧 Email Notifications (Coming Soon)")
    email_enabled = st.toggle("Enable Email Notifications", value=False, disabled=True)
    email_address = st.text_input("Email Address", placeholder="your@email.com", disabled=True)
    email_frequency = st.selectbox(
        "Email Frequency",
        options=['Immediate', 'Hourly Digest', 'Daily Summary'],
        disabled=True
    )

with col_notif2:
    st.markdown("#### 📱 Telegram Notifications (Coming Soon)")
    telegram_enabled = st.toggle("Enable Telegram Notifications", value=False, disabled=True)
    telegram_chat = st.text_input("Telegram Chat ID", placeholder="@your_chat_id", disabled=True)
    telegram_filter = st.multiselect(
        "Alert Levels to Send",
        options=['Critical', 'Warning', 'Info'],
        default=['Critical'],
        disabled=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# Clear all alerts button
if st.button("🗑️ Clear All Alerts History", type="secondary"):
    if utils.clear_alerts_history():
        st.success("✅ Alerts history cleared successfully!")
        st.rerun()
    else:
        st.error("❌ Failed to clear alerts history")
