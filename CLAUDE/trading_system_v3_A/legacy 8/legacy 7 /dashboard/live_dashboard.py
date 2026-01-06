"""
PRO TRADING STATION - Main Dashboard Application
Multi-page Streamlit app for algorithmic trading monitoring
"""

import streamlit as st
import time
from datetime import datetime
from dashboard_shared import init_session_state

# --- Page Config (Must be first) ---
st.set_page_config(
    page_title="TRADING STATION",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
init_session_state()

# Custom CSS for sidebar title
st.markdown("""
<style>
    /* Sidebar title styling */
    [data-testid="stSidebarNav"] {
        padding-top: 0 !important;
    }

    [data-testid="stSidebarNav"]::before {
        content: "⚡ TRADING STATION";
        margin-left: 20px;
        margin-top: 20px;
        margin-bottom: 10px;
        font-size: 20px;
        font-weight: 700;
        color: #00CC96;
        display: block;
        font-family: 'Inter', sans-serif;
        position: relative;
        top: 0px;
    }

    [data-testid="stSidebarNav"]::after {
        content: "Real-time trading dashboard";
        display: block;
        margin-left: 20px;
        margin-bottom: 20px;
        font-size: 12px;
        color: #888;
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Controls ---
with st.sidebar:
    # Auto-Refresh Control
    st.session_state['auto_refresh'] = st.checkbox(
        "📡 Live Auto-Refresh",
        value=st.session_state['auto_refresh'],
        help="Auto-refresh the current page"
    )

    if st.session_state['auto_refresh']:
        st.session_state['refresh_interval'] = st.slider(
            "Refresh Interval (s)",
            3, 30,
            st.session_state['refresh_interval']
        )

    st.markdown("---")

    # Mock Data Toggle
    st.session_state['mock_mode'] = st.toggle(
        "🛠️ Demo Mode",
        st.session_state['mock_mode'],
        help="Display mock data for demonstration"
    )

    st.markdown("---")

    # Last Update Info
    st.caption(f"Last update: {st.session_state['last_update'].strftime('%H:%M:%S')}")

    st.markdown("---")
    st.caption("© 2024 TRADING STATION")

# Define pages
overview_page = st.Page(
    "dashboard_pages/overview.py",
    title="Overview",
    icon="📊",
    default=True
)

analytics_page = st.Page(
    "dashboard_pages/analytics.py",
    title="Analytics",
    icon="📈"
)

market_page = st.Page(
    "dashboard_pages/market_context.py",
    title="Market Context",
    icon="🌐"
)

risk_page = st.Page(
    "dashboard_pages/risk_monitor.py",
    title="Risk Monitor",
    icon="⚠️"
)

alerts_page = st.Page(
    "dashboard_pages/alerts.py",
    title="Alerts",
    icon="🔔"
)

config_page = st.Page(
    "dashboard_pages/configuration.py",
    title="Configuration",
    icon="⚙️"
)

system_page = st.Page(
    "dashboard_pages/system_health.py",
    title="System Health",
    icon="🛡️"
)

notes_page = st.Page(
    "dashboard_pages/notes.py",
    title="Notes",
    icon="📝"
)

# Navigation structure
pg = st.navigation(
    {
        "Dashboard": [overview_page, analytics_page],
        "Market & Risk": [market_page, risk_page, alerts_page],
        "System": [config_page, system_page],
        "Tools": [notes_page],
    }
)

# Run the selected page
pg.run()

# Auto-refresh logic (at the end)
if st.session_state['auto_refresh']:
    time.sleep(st.session_state['refresh_interval'])
    st.rerun()
