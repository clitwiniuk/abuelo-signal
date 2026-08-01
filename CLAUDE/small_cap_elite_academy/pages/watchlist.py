import streamlit as st
import pandas as pd
from database.db_manager import get_watchlist, add_to_watchlist, remove_from_watchlist
from utils.market_data import get_stock_data, get_small_cap_scanner

def render_watchlist_page():
    """Renderizar página de watchlist"""
    st.markdown("<h1>⭐ Watchlist</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    watchlist = get_watchlist(user['id'])
    
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📋 Mi Watchlist")
        
        if watchlist:
            # Actualizar con datos de mercado
            watchlist_data = []
            
            for item in watchlist:
                symbol = item['simbolo']
                
                # Obtener datos actuales (simulado)
                try:
                    df = get_stock_data(symbol, period="1d", interval="5m")
                    if df is not None and not df.empty:
                        current_price = df['close'].iloc[-1]
                        prev_close = df['close'].iloc[0]
                        change_pct = ((current_price - prev_close) / prev_close) * 100
                        volume = df['volume'].sum()
                    else:
                        current_price = 0
                        change_pct = 0
                        volume = 0
                except:
                    current_price = 0
                    change_pct = 0
                    volume = 0
                
                watchlist_data.append({
                    'symbol': symbol,
                    'setup': item.get('setup_detectado', 'Sin setup'),
                    'notas': item.get('notas', ''),
                    'price': current_price,
                    'change_pct': change_pct,
                    'volume': volume,
                    'id': item['id']
                })
            
            # Mostrar como tabla interactiva
            for item in watchlist_data:
                change_color = "#00C805" if item['change_pct'] > 0 else "#FF5000"
                change_icon = "▲" if item['change_pct'] > 0 else "▼"
                
                with st.container():
                    col_sym, col_price, col_change, col_setup, col_action = st.columns([1.5, 1, 1, 1.5, 0.5])
                    
                    with col_sym:
                        st.markdown(f"**{item['symbol']}**")
                    
                    with col_price:
                        st.markdown(f"${item['price']:.2f}")
                    
                    with col_change:
                        st.markdown(f"<span style='color: {change_color};'>{change_icon} {abs(item['change_pct']):.2f}%</span>", 
                                  unsafe_allow_html=True)
                    
                    with col_setup:
                        st.markdown(f"<span style='font-size: 11px; color: #666;'>{item['setup']}</span>", 
                                  unsafe_allow_html=True)
                    
                    with col_action:
                        if st.button("🗑️", key=f"del_{item['id']}", help="Eliminar"):
                            remove_from_watchlist(user['id'], item['symbol'])
                            st.rerun()
                    
                    st.markdown("---")
        else:
            st.info("Tu watchlist está vacía. Agrega stocks para monitorear.")
    
    with col_right:
        st.markdown("### ➕ Agregar a Watchlist")
        
        with st.form("add_watchlist"):
            new_symbol = st.text_input("Símbolo", placeholder="Ej: MARA").upper()
            new_setup = st.selectbox(
                "Setup detectado",
                ["", "Morning Panic Dip", "VWAP Bounce", "Opening Range Breakout", 
                 "First Red Day", "Otro"]
            )
            new_notas = st.text_area("Notas", placeholder="¿Por qué está en tu radar?")
            
            submitted = st.form_submit_button("Agregar", use_container_width=True, type="primary")
            
            if submitted:
                if new_symbol:
                    if add_to_watchlist(user['id'], new_symbol, new_setup, new_notas):
                        st.success(f"✅ {new_symbol} agregado a tu watchlist")
                        st.rerun()
                    else:
                        st.error("No se pudo agregar. ¿Ya existe en tu lista?")
                else:
                    st.error("Ingresa un símbolo válido")
        
        st.markdown("---")
        
        # Scanner rápido
        st.markdown("### 🔍 Scanner Rápido")
        
        if st.button("🔄 Escanear Small Caps", use_container_width=True):
            with st.spinner("Escaneando..."):
                scanner = get_small_cap_scanner()
                
                if not scanner.empty:
                    st.success(f"{len(scanner)} stocks encontrados")
                    
                    for _, stock in scanner.head(5).iterrows():
                        change_color = "#00C805" if stock['change_pct'] > 0 else "#FF5000"
                        
                        st.markdown(f"""
                        <div style="background-color: #141414; padding: 10px; border-radius: 6px; margin: 5px 0;">
                            <div style="display: flex; justify-content: space-between;">
                                <span style="font-weight: bold;">{stock['symbol']}</span>
                                <span style="color: {change_color};">{stock['change_pct']:.1f}%</span>
                            </div>
                            <div style="font-size: 11px; color: #666;">
                                ${stock['price']:.2f} | Cap: ${stock['market_cap']:.0f}M
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"➕ {stock['symbol']}", key=f"add_scan_{stock['symbol']}"):
                            add_to_watchlist(user['id'], stock['symbol'])
                            st.rerun()
    
    # Pre-market gapper
    st.markdown("---")
    st.markdown("### 🌅 Pre-Market Gappers")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    gappers = [
        {'symbol': 'MARA', 'gap': 15.3, 'volume': '2.5M'},
        {'symbol': 'RIOT', 'gap': -8.7, 'volume': '1.8M'},
        {'symbol': 'AMC', 'gap': 22.1, 'volume': '5.2M'},
        {'symbol': 'GME', 'gap': -5.4, 'volume': '3.1M'},
        {'symbol': 'SOFI', 'gap': 12.8, 'volume': '890K'}
    ]
    
    cols = [col1, col2, col3, col4, col5]
    
    for i, gapper in enumerate(gappers):
        with cols[i]:
            gap_color = "#00C805" if gapper['gap'] > 0 else "#FF5000"
            gap_icon = "▲" if gapper['gap'] > 0 else "▼"
            
            st.markdown(f"""
            <div class="trading-card" style="text-align: center;">
                <div style="font-weight: bold; font-size: 16px;">{gapper['symbol']}</div>
                <div style="color: {gap_color}; font-size: 20px; font-weight: bold;">
                    {gap_icon} {abs(gapper['gap']):.1f}%
                </div>
                <div style="font-size: 11px; color: #666;">
                    Vol: {gapper['volume']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"Ver {gapper['symbol']}", key=f"gap_{gapper['symbol']}", use_container_width=True):
                st.session_state.selected_symbol = gapper['symbol']
                st.session_state.current_page = "trading"
                st.rerun()
    
    # Checklist pre-market
    st.markdown("---")
    st.markdown("### ✅ Checklist Pre-Market")
    
    checklist_items = [
        "Revisar overnight news y earnings",
        "Identificar gappers con volumen",
        "Marcar niveles clave de soporte/resistencia",
        "Definir máximo de trades para hoy",
        "Preparar watchlist con setups potenciales",
        "Verificar estado emocional (Daily Report)"
    ]
    
    cols = st.columns(2)
    for i, item in enumerate(checklist_items):
        with cols[i % 2]:
            st.checkbox(item, key=f"checklist_{i}")
    
    # Consejos
    st.markdown("---")
    st.markdown("""
    <div style="background-color: #141414; padding: 20px; border-radius: 12px;">
        <div style="color: #FFD700; font-weight: bold; margin-bottom: 10px;">
            💡 Consejos para tu Watchlist
        </div>
        <div style="color: #B0B0B0; font-size: 13px;">
            <ul style="padding-left: 20px; line-height: 1.8;">
                <li><strong>Máximo 5 stocks:</strong> Menos es más. Enfócate en calidad, no cantidad.</li>
                <li><strong>Asigna un setup a cada stock:</strong> Saber qué buscas aumenta tu probabilidad.</li>
                <li><strong>Actualiza diariamente:</strong> Elimina stocks que ya no cumplan criterios.</li>
                <li><strong>Prioriza por volumen:</strong> El volumen es el combustible de los movimientos.</li>
                <li><strong>Ten paciencia:</strong> No todos los días hay oportunidades A+.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)