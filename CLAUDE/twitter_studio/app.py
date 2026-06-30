"""Twitter Studio — entry point."""

import sys
from pathlib import Path

# Make project root importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

import nest_asyncio
nest_asyncio.apply()

import streamlit as st

from auth.auth_service import auth_service
from config.settings import settings, COOKIES_FILE
from database.schema import init_db
from utils.logger import logger

# ---------------------------------------------------------------------------
# Page config (MUST be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Twitter Studio",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — dark theme inspired by Linear / Vercel
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Root palette */
    :root {
        --bg: #0d1117;
        --card: #161b22;
        --border: #30363d;
        --accent: #58a6ff;
        --accent2: #3fb950;
        --warn: #d29922;
        --danger: #f85149;
        --text: #c9d1d9;
        --muted: #8b949e;
    }
    .stApp { background-color: var(--bg); color: var(--text); }
    section[data-testid="stSidebar"] { background-color: var(--card); border-right: 1px solid var(--border); }
    .stButton > button {
        background: var(--accent); color: #fff; border: none;
        border-radius: 6px; font-weight: 600;
    }
    .stButton > button:hover { opacity: 0.85; }
    .stTextInput > div > input, .stSelectbox > div, .stNumberInput input {
        background: var(--card); color: var(--text); border-color: var(--border);
    }
    .metric-card {
        background: var(--card); border: 1px solid var(--border);
        border-radius: 10px; padding: 16px 20px; margin-bottom: 8px;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: var(--accent); }
    .metric-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
    a { color: var(--accent); }
    hr { display: none !important; }

    /* st.metric nativo */
    [data-testid="stMetric"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] { color: #8b949e; font-size: 0.75rem; }
    [data-testid="stMetricValue"] { color: #c9d1d9; font-size: 1.4rem; font-weight: 700; }

    /* Radio como chips */
    div[data-testid="stHorizontalBlock"] .stRadio > div { flex-direction: row; gap: 8px; }
    .stRadio label {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 20px; padding: 4px 14px;
        font-size: 0.85rem; cursor: pointer;
    }
    .stRadio label:has(input:checked) {
        background: #1f3a5f; border-color: #58a6ff; color: #58a6ff;
    }

    /* Search input más grande */
    .search-hero input { font-size: 1.1rem !important; padding: 12px 16px !important; }

    /* Tabs más limpios */
    .stTabs [data-baseweb="tab"] { font-size: 0.85rem; padding: 8px 16px; }
    .stTabs [aria-selected="true"] { color: #58a6ff; border-bottom-color: #58a6ff; }

    /* Sidebar nav buttons — look like menu items, not buttons */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--text) !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 400 !important;
        text-align: left !important;
        padding: 8px 12px !important;
        margin: 1px 0 !important;
        transition: background 0.15s;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(88,166,255,0.08) !important;
        color: var(--accent) !important;
        opacity: 1 !important;
    }
    /* Active page button */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: rgba(88,166,255,0.15) !important;
        color: var(--accent) !important;
        font-weight: 600 !important;
        border-left: 3px solid var(--accent) !important;
        border-radius: 0 6px 6px 0 !important;
    }
    /* Logout button stays red-ish */
    section[data-testid="stSidebar"] .stButton:last-child > button {
        color: var(--danger) !important;
    }
    section[data-testid="stSidebar"] .stButton:last-child > button:hover {
        background: rgba(248,81,73,0.1) !important;
        color: var(--danger) !important;
    }
    /* Sidebar user info block */
    .sidebar-user {
        padding: 12px 4px 8px 4px;
        margin-bottom: 4px;
    }
    .sidebar-user .name { font-weight: 700; font-size: 1rem; color: var(--text); }
    .sidebar-user .handle { font-size: 0.85rem; color: var(--muted); }
    .sidebar-user .stats { font-size: 0.78rem; color: var(--muted); margin-top: 4px; }
    .nav-section-label {
        font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em;
        color: var(--muted); text-transform: uppercase;
        padding: 12px 12px 4px 12px; margin: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Bootstrap DB
# ---------------------------------------------------------------------------
init_db()

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "page" not in st.session_state:
    st.session_state.page = "search"

# ---------------------------------------------------------------------------
# Auto-login: cookies first, then .env credentials
# ---------------------------------------------------------------------------
if not st.session_state.authenticated:
    if COOKIES_FILE.exists():
        with st.spinner("Restaurando sesión..."):
            if auth_service.try_cookie_login():
                st.session_state.authenticated = True
                st.session_state.current_user = auth_service.get_current_user()
                logger.info("Auto-login via cookies OK")

    if not st.session_state.authenticated and settings.x_username and settings.x_password:
        with st.spinner("Iniciando sesión con credenciales .env..."):
            ok = auth_service.login(
                username=settings.x_username,
                email=settings.x_email,
                password=settings.x_password,
                language=settings.app_language,
            )
            if ok:
                st.session_state.authenticated = True
                st.session_state.current_user = auth_service.get_current_user()
                logger.info("Auto-login via .env credentials OK")

# ---------------------------------------------------------------------------
# LOGIN SCREEN
# ---------------------------------------------------------------------------
def render_login() -> None:
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h1 style='text-align:center; color:#58a6ff;'>Twitter Studio</h1>"
            "<p style='text-align:center; color:#8b949e;'>Plataforma de inteligencia para X</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="@username")
            email = st.text_input("Email", placeholder="tu@email.com")
            password = st.text_input("Contraseña", type="password")
            language = st.selectbox("Idioma", ["en-US", "es", "fr", "de", "it", "pt"])
            submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)

        if submitted:
            if not username or not email or not password:
                st.error("Completa todos los campos")
                return
            with st.spinner("Iniciando sesión..."):
                ok = auth_service.login(
                    username=username.lstrip("@"),
                    email=email,
                    password=password,
                    language=language,
                )
            if ok:
                st.session_state.authenticated = True
                st.session_state.current_user = auth_service.get_current_user()
                st.success("Sesión iniciada correctamente")
                st.rerun()
            else:
                st.error("Error al iniciar sesión. Verifica tus credenciales.")


# ---------------------------------------------------------------------------
# SIDEBAR navigation
# ---------------------------------------------------------------------------
def render_sidebar() -> str:
    user = st.session_state.current_user

    with st.sidebar:
        # User info block
        if user:
            cols = st.columns([1, 3])
            with cols[0]:
                if user.avatar_url:
                    st.image(user.avatar_url, width=48)
            with cols[1]:
                followers = getattr(user, "followers_count", 0)
                tweets = getattr(user, "tweet_count", 0)
                st.markdown(
                    f"<div class='sidebar-user'>"
                    f"<div class='name'>{user.name}</div>"
                    f"<div class='handle'>@{user.username}</div>"
                    f"<div class='stats'>{followers:,} seguidores · {tweets:,} tweets</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='nav-section-label'>Explorar</div>", unsafe_allow_html=True)

        explorar_pages = {
            "dashboard": "🏠  Mi cuenta",
            "search":    "🔍  Buscar",
            "profile":   "👤  Analizar perfil",
        }
        for key, label in explorar_pages.items():
            active = st.session_state.page == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.markdown("<div class='nav-section-label'>Seguimiento</div>", unsafe_allow_html=True)

        seguimiento_pages = {
            "monitor":  "📡  Monitor",
            "research": "🔬  Research",
        }
        for key, label in seguimiento_pages.items():
            active = st.session_state.page == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.write("")
        st.markdown("<hr style='border-color:#30363d; display:block !important;'>", unsafe_allow_html=True)

        active_sys = st.session_state.page == "system"
        if st.button("⚙️  Sistema", key="nav_system", use_container_width=True,
                     type="primary" if active_sys else "secondary"):
            st.session_state.page = "system"
            st.rerun()

        if st.button("🚪  Cerrar sesión", use_container_width=True):
            auth_service.logout()
            st.session_state.authenticated = False
            st.session_state.current_user = None
            st.rerun()

    return st.session_state.page


# ---------------------------------------------------------------------------
# Page router
# ---------------------------------------------------------------------------
def route(page: str) -> None:
    if page == "dashboard":
        from pages.dashboard import render
    elif page == "search":
        from pages.search import render
    elif page == "profile":
        from pages.profile import render
    elif page == "monitor":
        from pages.monitor import render
    elif page == "research":
        from pages.research import render
    elif page == "system":
        from pages.system import render
    else:
        from pages.search import render
    render()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not st.session_state.authenticated:
        render_login()
        return

    page = render_sidebar()
    route(page)


if __name__ == "__main__":
    main()
else:
    main()
