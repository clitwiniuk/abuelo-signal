import streamlit as st
import hashlib
import datetime
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de página debe ser lo primero
st.set_page_config(
    page_title="Small Cap Elite Academy",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importar módulos propios
import sys
sys.path.append('/mnt/okcomputer/output/small_cap_elite_academy')

from database.db_manager import (
    init_database, create_user, get_user_by_username, get_user_by_id,
    update_user_capital, add_xp_to_user, create_trade, close_trade,
    get_trades_by_user, get_trades_abiertos, get_trading_stats,
    get_consecutive_stats, create_or_update_daily_report, get_daily_report,
    unlock_achievement, get_user_achievements, check_achievement_exists,
    update_setup_mastery, get_setups_mastery, get_watchlist,
    add_to_watchlist, remove_from_watchlist, get_daily_reports_stats,
    create_replay_session, close_replay_session, get_replay_history
)

from utils.market_data import get_stock_data, get_small_cap_scanner, simulate_price_movement
from utils.calculations import calculate_r_multiple, calculate_position_size, calculate_slippage
from utils.achievements import check_all_achievements

# Inicializar base de datos
init_database()

# CSS Personalizado para estilo trading oscuro
st.markdown("""
<style>
    /* Paleta de colores principal */
    :root {
        --bg-primary: #0A0A0A;
        --bg-secondary: #141414;
        --bg-tertiary: #1E1E1E;
        --text-primary: #FFFFFF;
        --text-secondary: #B0B0B0;
        --green-bullish: #00C805;
        --red-bearish: #FF5000;
        --accent-gold: #FFD700;
        --accent-blue: #00D4FF;
        --border-color: #2A2A2A;
    }
    
    .main {
        background-color: var(--bg-primary);
        color: var(--text-primary);
    }
    
    .stApp {
        background-color: #0A0A0A;
    }
    
    /* Headers y títulos */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Cards y contenedores */
    .trading-card {
        background-color: #141414;
        border: 1px solid #2A2A2A;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #141414 0%, #1E1E1E 100%);
        border: 1px solid #2A2A2A;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
    }
    
    .metric-positive {
        color: #00C805 !important;
        font-size: 24px;
        font-weight: bold;
    }
    
    .metric-negative {
        color: #FF5000 !important;
        font-size: 24px;
        font-weight: bold;
    }
    
    /* Niveles y progreso */
    .level-badge-nivel-1 {
        background: linear-gradient(135deg, #CD7F32 0%, #8B4513 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .level-badge-nivel-2 {
        background: linear-gradient(135deg, #C0C0C0 0%, #808080 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .level-badge-nivel-3 {
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%);
        color: black;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .level-badge-nivel-4 {
        background: linear-gradient(135deg, #E5E4E2 0%, #A0A0A0 100%);
        color: black;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    .level-badge-nivel-5 {
        background: linear-gradient(135deg, #00D4FF 0%, #0099CC 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Barra de progreso XP */
    .xp-progress-container {
        background-color: #1E1E1E;
        border-radius: 10px;
        height: 20px;
        overflow: hidden;
        margin: 10px 0;
    }
    
    .xp-progress-bar {
        background: linear-gradient(90deg, #00C805 0%, #00D4FF 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.5s ease;
    }
    
    /* Botones de trading */
    .btn-buy {
        background-color: #00C805 !important;
        color: white !important;
        border: none !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        width: 100% !important;
    }
    
    .btn-sell {
        background-color: #FF5000 !important;
        color: white !important;
        border: none !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        width: 100% !important;
    }
    
    /* Alerts y notificaciones */
    .alert-warning {
        background-color: rgba(255, 215, 0, 0.1);
        border-left: 4px solid #FFD700;
        color: #FFD700;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
    
    .alert-danger {
        background-color: rgba(255, 80, 0, 0.1);
        border-left: 4px solid #FF5000;
        color: #FF5000;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
    
    .alert-success {
        background-color: rgba(0, 200, 5, 0.1);
        border-left: 4px solid #00C805;
        color: #00C805;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
    
    /* Tablas */
    .stDataFrame {
        background-color: #141414 !important;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #1E1E1E !important;
        color: white !important;
        border: 1px solid #2A2A2A !important;
    }
    
    /* Selectbox */
    .stSelectbox > div > div > select {
        background-color: #1E1E1E !important;
        color: white !important;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #141414 !important;
    }
    
    /* Badges de logros */
    .achievement-badge {
        display: inline-block;
        padding: 8px 12px;
        margin: 4px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
    }
    
    .achievement-bronze {
        background: linear-gradient(135deg, #CD7F32, #8B4513);
        color: white;
    }
    
    .achievement-silver {
        background: linear-gradient(135deg, #C0C0C0, #808080);
        color: white;
    }
    
    .achievement-gold {
        background: linear-gradient(135deg, #FFD700, #B8860B);
        color: black;
    }
    
    .achievement-diamond {
        background: linear-gradient(135deg, #00D4FF, #0099CC);
        color: white;
    }
    
    /* Streak counter */
    .streak-counter {
        background: linear-gradient(135deg, #FF6B35, #F7931E);
        color: white;
        padding: 10px 20px;
        border-radius: 25px;
        font-weight: bold;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Setup cards */
    .setup-card {
        background-color: #141414;
        border: 2px solid #2A2A2A;
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .setup-card:hover {
        border-color: #00D4FF;
        transform: translateY(-2px);
    }
    
    .setup-locked {
        opacity: 0.5;
        pointer-events: none;
    }
    
    /* Animación level up */
    @keyframes levelUp {
        0% { transform: scale(1); }
        50% { transform: scale(1.2); }
        100% { transform: scale(1); }
    }
    
    .level-up-animation {
        animation: levelUp 0.5s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# Funciones de utilidad
def hash_password(password):
    """Hashear contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_authentication():
    """Verificar si el usuario está autenticado"""
    if 'user' not in st.session_state:
        st.session_state.user = None
    return st.session_state.user is not None

def login_user(username, password):
    """Autenticar usuario"""
    user = get_user_by_username(username)
    if user and user['password_hash'] == hash_password(password):
        st.session_state.user = user
        return True
    return False

def logout_user():
    """Cerrar sesión"""
    st.session_state.user = None
    for key in list(st.session_state.keys()):
        if key != 'user':
            del st.session_state[key]

def get_nivel_info(nivel):
    """Obtener información del nivel"""
    niveles = {
        1: {"nombre": "CADETE", "color": "#CD7F32", "capital": 25000, 
            "horario": "9:30-11:30 AM", "max_trades": 3, "riesgo_max": 100},
        2: {"nombre": "ANALISTA TÉCNICO", "color": "#C0C0C0", "capital": 50000,
            "horario": "9:30 AM - 4:00 PM", "max_trades": 5, "riesgo_max": 200},
        3: {"nombre": "ESTRATEGA CUANTITATIVO", "color": "#FFD700", "capital": 100000,
            "horario": "9:30 AM - 4:00 PM", "max_trades": float('inf'), "riesgo_max": 500},
        4: {"nombre": "PSYCHOLOGY MASTER", "color": "#E5E4E2", "capital": 250000,
            "horario": "9:30 AM - 4:00 PM", "max_trades": float('inf'), "riesgo_max": 1000},
        5: {"nombre": "ELITE TRADER", "color": "#00D4FF", "capital": 1000000,
            "horario": "9:30 AM - 4:00 PM", "max_trades": float('inf'), "riesgo_max": 2500}
    }
    return niveles.get(nivel, niveles[1])

def get_xp_para_siguiente_nivel(nivel_actual):
    """Obtener XP necesario para siguiente nivel"""
    xp_niveles = {1: 500, 2: 1500, 3: 3500, 4: 7000, 5: float('inf')}
    return xp_niveles.get(nivel_actual, float('inf'))

def render_login_page():
    """Renderizar página de login/registro"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 40px 0;">
            <h1 style="font-size: 48px; margin-bottom: 10px;">📈</h1>
            <h1 style="font-size: 36px; background: linear-gradient(90deg, #00C805, #00D4FF); 
                      -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                SMALL CAP ELITE ACADEMY
            </h1>
            <p style="color: #B0B0B0; font-size: 18px; margin-top: 20px;">
                Domina el arte del trading de small caps<br>
                Desde principiante hasta trader élite
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Usuario", placeholder="Tu username")
                password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña")
                submitted = st.form_submit_button("Iniciar Sesión", use_container_width=True)
                
                if submitted:
                    if login_user(username, password):
                        st.success("¡Bienvenido de vuelta!")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos")
        
        with tab2:
            with st.form("register_form"):
                new_username = st.text_input("Usuario", placeholder="Elige un username único")
                new_email = st.text_input("Email", placeholder="tu@email.com")
                new_password = st.text_input("Contraseña", type="password", placeholder="Mínimo 6 caracteres")
                confirm_password = st.text_input("Confirmar Contraseña", type="password")
                submitted = st.form_submit_button("Crear Cuenta", use_container_width=True)
                
                if submitted:
                    if new_password != confirm_password:
                        st.error("Las contraseñas no coinciden")
                    elif len(new_password) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres")
                    else:
                        user_id = create_user(new_username, new_email, hash_password(new_password))
                        if user_id:
                            st.success("¡Cuenta creada exitosamente! Ahora puedes iniciar sesión")
                        else:
                            st.error("El usuario o email ya existe")

def render_header():
    """Renderizar header con info del usuario"""
    user = st.session_state.user
    nivel_info = get_nivel_info(user['nivel_actual'])
    
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1.5, 1.5, 1])
    
    with col1:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 15px;">
            <span style="font-size: 28px;">👤</span>
            <div>
                <div style="font-size: 18px; font-weight: bold;">{user['username']}</div>
                <div class="level-badge-nivel-{user['nivel_actual']}" style="font-size: 12px;">
                    NIVEL {user['nivel_actual']}: {nivel_info['nombre']}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">CAPITAL</div>
            <div style="color: #00C805; font-size: 20px; font-weight: bold;">
                ${user['capital_virtual']:,.0f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        xp_actual = user['xp_total']
        xp_siguiente = get_xp_para_siguiente_nivel(user['nivel_actual'])
        xp_anterior = get_xp_para_siguiente_nivel(user['nivel_actual'] - 1) if user['nivel_actual'] > 1 else 0
        progreso = min(100, ((xp_actual - xp_anterior) / (xp_siguiente - xp_anterior)) * 100) if xp_siguiente != float('inf') else 100
        
        st.markdown(f"""
        <div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #B0B0B0;">
                <span>XP: {xp_actual:,}</span>
                <span>Siguiente: {xp_siguiente:,}</span>
            </div>
            <div class="xp-progress-container">
                <div class="xp-progress-bar" style="width: {progreso}%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        if user['racha_dias'] > 0:
            st.markdown(f"""
            <div class="streak-counter">
                <span>🔥</span>
                <span>Racha: {user['racha_dias']} días</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col5:
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            logout_user()
            st.rerun()
    
    st.markdown("---")

def render_sidebar():
    """Renderizar menú lateral"""
    user = st.session_state.user
    
    st.sidebar.markdown(f"""
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 40px;">📈</div>
        <div style="font-size: 16px; font-weight: bold; color: #00D4FF;">
            SMALL CAP ELITE
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    # Expose get_nivel_info via session_state for pages
    st.session_state.get_nivel_info = get_nivel_info

    menu_options = {
        "📊 Dashboard": "dashboard",
        "💰 Trading": "trading",
        "🎬 Market Replay": "market_replay",
        "📓 Daily Report": "daily_report",
        "📈 Estadísticas": "estadisticas",
        "🎯 Setups": "setups",
        "🏆 Logros": "logros",
        "📚 Entrenamiento": "entrenamiento",
        "⭐ Watchlist": "watchlist"
    }
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "dashboard"
    
    for label, page in menu_options.items():
        if st.sidebar.button(label, use_container_width=True, 
                          type="primary" if st.session_state.current_page == page else "secondary"):
            st.session_state.current_page = page
            st.rerun()
    
    st.sidebar.markdown("---")
    
    # Información del nivel actual
    nivel_info = get_nivel_info(user['nivel_actual'])
    st.sidebar.markdown(f"""
    <div class="trading-card" style="font-size: 12px;">
        <div style="color: #B0B0B0; margin-bottom: 10px;">TU NIVEL ACTUAL</div>
        <div style="font-size: 16px; font-weight: bold; color: {nivel_info['color']}; margin-bottom: 10px;">
            {nivel_info['nombre']}
        </div>
        <div style="color: #B0B0B0;">
            💵 Capital: ${nivel_info['capital']:,.0f}<br>
            ⏰ Horario: {nivel_info['horario']}<br>
            📊 Max trades/día: {nivel_info['max_trades'] if nivel_info['max_trades'] != float('inf') else '∞'}<br>
            ⚠️ Riesgo máx/trade: ${nivel_info['riesgo_max']}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_dashboard():
    """Renderizar dashboard principal"""
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    
    # Verificar si completó el Daily Report hoy
    hoy = date.today().isoformat()
    daily_report = get_daily_report(user['id'], hoy)
    
    if not daily_report or not daily_report.get('completado'):
        st.markdown("""
        <div class="alert-warning">
            ⚠️ <strong>Daily Report Card pendiente</strong><br>
            Debes completar tu check-in matutino antes de operar hoy.
            <a href="#" style="color: #FFD700;">Ir a Daily Report →</a>
        </div>
        """, unsafe_allow_html=True)
    
    # Métricas principales
    stats = get_trading_stats(user['id'], dias=30)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        win_rate = stats.get('win_rate', 0)
        color = "#00C805" if win_rate >= 50 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">WIN RATE (30d)</div>
            <div style="color: {color}; font-size: 28px; font-weight: bold;">
                {win_rate:.1f}%
            </div>
            <div style="color: #666; font-size: 11px;">
                {stats.get('trades_ganados', 0)}/{stats.get('total_trades', 0)} trades
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        profit_factor = stats.get('profit_factor', 0)
        color = "#00C805" if profit_factor >= 1.2 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">PROFIT FACTOR</div>
            <div style="color: {color}; font-size: 28px; font-weight: bold;">
                {profit_factor:.2f}
            </div>
            <div style="color: #666; font-size: 11px;">
                Objetivo: &gt;1.2
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        ev = stats.get('expected_value', 0)
        color = "#00C805" if ev > 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">EXPECTED VALUE</div>
            <div style="color: {color}; font-size: 28px; font-weight: bold;">
                ${ev:.2f}
            </div>
            <div style="color: #666; font-size: 11px;">
                por trade
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        r_mult = stats.get('avg_r_multiple', 0) or 0
        color = "#00C805" if r_mult > 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">R-MULTIPLE PROMEDIO</div>
            <div style="color: {color}; font-size: 28px; font-weight: bold;">
                {r_mult:.2f}R
            </div>
            <div style="color: #666; font-size: 11px;">
                Objetivo: &gt;2R
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gráfico de equity curve y trades recientes
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📈 Equity Curve (Últimos 30 días)")
        
        trades = get_trades_by_user(user['id'], fecha_desde=(date.today() - timedelta(days=30)).isoformat())
        
        if trades:
            df_trades = pd.DataFrame(trades)
            df_trades['fecha_entrada'] = pd.to_datetime(df_trades['fecha_entrada'])
            df_trades = df_trades.sort_values('fecha_entrada')
            df_trades['equity'] = user['capital_inicial_nivel'] + df_trades['pnl'].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_trades['fecha_entrada'],
                y=df_trades['equity'],
                mode='lines+markers',
                name='Equity',
                line=dict(color='#00C805', width=2),
                marker=dict(size=6)
            ))
            
            fig.add_hline(y=user['capital_inicial_nivel'], line_dash="dash", 
                         line_color="#666", annotation_text="Capital Inicial")
            
            fig.update_layout(
                plot_bgcolor='#141414',
                paper_bgcolor='#0A0A0A',
                font_color='white',
                xaxis_title='Fecha',
                yaxis_title='Capital ($)',
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aún no tienes trades registrados. ¡Empieza a operar para ver tu equity curve!")
    
    with col_right:
        st.markdown("### 📝 Trades Recientes")
        
        trades_recientes = get_trades_by_user(user['id'], limit=5)
        
        if trades_recientes:
            for trade in trades_recientes:
                pnl = trade.get('pnl')
                if pnl is not None:
                    color = "#00C805" if pnl > 0 else "#FF5000"
                    emoji = "🟢" if pnl > 0 else "🔴"
                    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
                else:
                    color = "#FFD700"
                    emoji = "⏳"
                    pnl_str = "ABIERTO"
                
                st.markdown(f"""
                <div style="background-color: #141414; padding: 12px; border-radius: 8px; margin: 8px 0;
                            border-left: 3px solid {color};">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: bold;">{trade['simbolo']}</span>
                        <span style="color: {color};">{emoji} {pnl_str}</span>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-top: 4px;">
                        {trade['setup']} | {trade['fecha_entrada'][:10]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay trades recientes")
    
    # Próximos desafíos
    st.markdown("---")
    st.markdown("### 🎯 Próximos Desafíos")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        trades_totales = stats.get('total_trades', 0)
        progreso_20 = min(100, (trades_totales / 20) * 100)
        st.markdown(f"""
        <div class="trading-card">
            <div style="font-size: 24px; margin-bottom: 10px;">🥉</div>
            <div style="font-weight: bold; margin-bottom: 5px;">First Blood</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 10px;">
                Completa tu primer trade
            </div>
            <div class="xp-progress-container" style="height: 8px;">
                <div class="xp-progress-bar" style="width: {100 if trades_totales > 0 else 0}%"></div>
            </div>
            <div style="font-size: 11px; color: #666; margin-top: 5px;">
                {'✅ Completado' if trades_totales > 0 else '⏳ Pendiente'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        progreso_10 = min(100, (trades_totales / 10) * 100)
        st.markdown(f"""
        <div class="trading-card">
            <div style="font-size: 24px; margin-bottom: 10px;">📊</div>
            <div style="font-weight: bold; margin-bottom: 5px;">Consistency King</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 10px;">
                10 trades siguiendo tu plan
            </div>
            <div class="xp-progress-container" style="height: 8px;">
                <div class="xp-progress-bar" style="width: {progreso_10}%"></div>
            </div>
            <div style="font-size: 11px; color: #666; margin-top: 5px;">
                {trades_totales}/10 trades
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        setups = get_setups_mastery(user['id'])
        setups_dominados = sum(1 for s in setups if s['dominado'])
        st.markdown(f"""
        <div class="trading-card">
            <div style="font-size: 24px; margin-bottom: 10px;">🎓</div>
            <div style="font-weight: bold; margin-bottom: 5px;">Setup Master</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 10px;">
                Domina todos los setups
            </div>
            <div class="xp-progress-container" style="height: 8px;">
                <div class="xp-progress-bar" style="width: {(setups_dominados/4)*100}%"></div>
            </div>
            <div style="font-size: 11px; color: #666; margin-top: 5px;">
                {setups_dominados}/4 setups dominados
            </div>
        </div>
        """, unsafe_allow_html=True)

# Importar y renderizar otras páginas
from pages.trading import render_trading_page
from pages.market_replay import render_market_replay_page
from pages.daily_report import render_daily_report_page
from pages.estadisticas import render_estadisticas_page
from pages.setups import render_setups_page
from pages.logros import render_logros_page
from pages.entrenamiento import render_entrenamiento_page
from pages.watchlist import render_watchlist_page

def main():
    """Función principal"""
    if not check_authentication():
        render_login_page()
    else:
        render_header()
        render_sidebar()
        
        page = st.session_state.current_page
        
        if page == "dashboard":
            render_dashboard()
        elif page == "trading":
            render_trading_page()
        elif page == "market_replay":
            render_market_replay_page()
        elif page == "daily_report":
            render_daily_report_page()
        elif page == "estadisticas":
            render_estadisticas_page()
        elif page == "setups":
            render_setups_page()
        elif page == "logros":
            render_logros_page()
        elif page == "entrenamiento":
            render_entrenamiento_page()
        elif page == "watchlist":
            render_watchlist_page()

if __name__ == "__main__":
    main()