"""
Shared components and styles for the trading dashboard
"""
import streamlit as st
from datetime import datetime

# Common CSS styles for all pages
DASHBOARD_CSS = """
<style>
    /* ============= GLOBAL STYLES ============= */

    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Root Variables for Theme */
    :root {
        --primary-color: #00CC96;
        --danger-color: #EF553B;
        --warning-color: #FFA500;
        --info-color: #00D4FF;
        --success-color: #00CC96;
        --purple-color: #AB63FA;
        --bg-card: #f8f9fa;
        --bg-card-dark: #1e1e1e;
        --text-primary: #0e1117;
        --text-secondary: #6c757d;
        --border-color: #e0e0e0;
        --shadow-sm: 0 2px 4px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
        --border-radius: 12px;
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Dark mode overrides */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-card: #262730;
            --bg-card-dark: #1a1a1a;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
            --border-color: #404040;
            --shadow-sm: 0 2px 4px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
            --shadow-lg: 0 10px 15px rgba(0,0,0,0.5);
        }
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Custom Font */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Monospace for numbers */
    .metric-value, code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ============= HEADER STYLES ============= */

    .main-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, #00a078 100%);
        padding: 1.5rem 2rem;
        border-radius: var(--border-radius);
        margin-bottom: 2rem;
        box-shadow: var(--shadow-lg);
        color: white;
    }

    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 0.95rem;
    }

    /* ============= METRIC CARDS ============= */

    .metric-card {
        background: var(--bg-card);
        border-radius: var(--border-radius);
        padding: 1.25rem;
        box-shadow: var(--shadow-md);
        transition: var(--transition);
        border: 1px solid var(--border-color);
        height: 100%;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }

    .metric-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--text-secondary);
        margin-bottom: 0.5rem;
    }

    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
    }

    .metric-delta {
        font-size: 0.875rem;
        font-weight: 500;
    }

    .metric-delta.positive {
        color: var(--success-color);
    }

    .metric-delta.negative {
        color: var(--danger-color);
    }

    /* ============= TRADE CARDS ============= */

    .trade-card {
        background: var(--bg-card);
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-md);
        border-left: 4px solid;
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }

    .trade-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, var(--primary-color), transparent);
        opacity: 0;
        transition: var(--transition);
    }

    .trade-card:hover::before {
        opacity: 1;
    }

    .trade-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-lg);
    }

    .trade-card-long {
        border-left-color: var(--success-color);
    }

    .trade-card-short {
        border-left-color: var(--danger-color);
    }

    .trade-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .trade-symbol {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0;
    }

    .trade-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        background: rgba(0,0,0,0.05);
        margin-left: 0.75rem;
        letter-spacing: 0.5px;
    }

    @media (prefers-color-scheme: dark) {
        .trade-badge {
            background: rgba(255,255,255,0.1);
        }
    }

    .trade-pnl {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }

    .trade-pnl.positive {
        color: var(--success-color);
    }

    .trade-pnl.negative {
        color: var(--danger-color);
    }

    .trade-details {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.75rem;
        margin-top: 1rem;
    }

    .trade-detail-item {
        font-size: 0.875rem;
    }

    .trade-detail-label {
        color: var(--text-secondary);
        font-weight: 500;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }

    .trade-detail-value {
        color: var(--text-primary);
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ============= STATUS INDICATORS ============= */

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.875rem;
        font-weight: 600;
        transition: var(--transition);
    }

    .status-badge.online {
        background: rgba(0, 204, 150, 0.1);
        color: var(--success-color);
        border: 1px solid rgba(0, 204, 150, 0.3);
    }

    .status-badge.offline {
        background: rgba(239, 85, 59, 0.1);
        color: var(--danger-color);
        border: 1px solid rgba(239, 85, 59, 0.3);
    }

    .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }

    .status-indicator.online {
        background: var(--success-color);
    }

    .status-indicator.offline {
        background: var(--danger-color);
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* ============= CONSOLE/LOG STYLES ============= */

    .console-container {
        background: #1a1a1a;
        border-radius: var(--border-radius);
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.875rem;
        line-height: 1.6;
        box-shadow: var(--shadow-md);
    }

    .log-entry {
        margin-bottom: 0.5rem;
        padding: 0.5rem;
        border-left: 3px solid transparent;
        border-radius: 4px;
        transition: var(--transition);
    }

    .log-entry:hover {
        background: rgba(255,255,255,0.05);
    }

    .log-entry.error {
        border-left-color: var(--danger-color);
        background: rgba(239, 85, 59, 0.05);
    }

    .log-entry.warning {
        border-left-color: var(--warning-color);
        background: rgba(255, 165, 0, 0.05);
    }

    .log-entry.success {
        border-left-color: var(--success-color);
        background: rgba(0, 204, 150, 0.05);
    }

    .log-timestamp {
        color: #666;
        font-size: 0.75rem;
        margin-right: 0.75rem;
    }

    .log-icon {
        margin: 0 0.5rem;
    }

    .log-message {
        color: #e0e0e0;
        font-weight: 500;
    }

    /* ============= TABLE STYLES ============= */

    .dataframe {
        border-radius: var(--border-radius) !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-md) !important;
    }

    /* ============= SECTION HEADERS ============= */

    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid var(--border-color);
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    /* ============= RESPONSIVE ============= */

    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 1.5rem;
        }

        .metric-value {
            font-size: 1.5rem;
        }

        .trade-symbol {
            font-size: 1.25rem;
        }

        .trade-pnl {
            font-size: 1.25rem;
        }
    }

    /* ============= ANIMATIONS ============= */

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .fade-in {
        animation: fadeIn 0.5s ease-out;
    }

    /* ============= UTILITY CLASSES ============= */

    .text-success { color: var(--success-color) !important; }
    .text-danger { color: var(--danger-color) !important; }
    .text-warning { color: var(--warning-color) !important; }
    .text-info { color: var(--info-color) !important; }
    .text-muted { color: var(--text-secondary) !important; }

    .bg-success { background-color: rgba(0, 204, 150, 0.1) !important; }
    .bg-danger { background-color: rgba(239, 85, 59, 0.1) !important; }
    .bg-warning { background-color: rgba(255, 165, 0, 0.1) !important; }
    .bg-info { background-color: rgba(0, 212, 255, 0.1) !important; }
</style>
"""

def apply_custom_css():
    """Apply custom CSS styles to the page"""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

def init_session_state():
    """Initialize session state variables"""
    if 'mock_mode' not in st.session_state:
        st.session_state['mock_mode'] = False
    if 'last_update' not in st.session_state:
        st.session_state['last_update'] = datetime.now()
    if 'auto_refresh' not in st.session_state:
        st.session_state['auto_refresh'] = False
    if 'refresh_interval' not in st.session_state:
        st.session_state['refresh_interval'] = 5

def render_header(title, subtitle):
    """Render page header with title and subtitle"""
    st.markdown(f"""
    <div class="main-header fade-in">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

def render_section_header(text):
    """Render a section header"""
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)

def render_status_badge(is_online):
    """Render a status badge"""
    status_class = 'online' if is_online else 'offline'
    status_text = 'SYSTEM ONLINE' if is_online else 'SYSTEM OFFLINE'
    return f"""
    <div class="status-badge {status_class}">
        <span class="status-indicator {status_class}"></span>
        {status_text}
    </div>
    """
