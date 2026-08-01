import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, date, timedelta

from database.db_manager import (
    create_trade, close_trade, get_trades_abiertos, get_trades_by_user,
    update_user_capital, add_xp_to_user, update_setup_mastery
)
from utils.market_data import get_stock_data, get_small_cap_scanner, is_market_open
from utils.calculations import (
    calculate_r_multiple, calculate_position_size, calculate_slippage,
    validate_trade_plan
)
from utils.achievements import check_all_achievements
from utils.lightweight_charts import render_lightweight_chart

def render_trading_page():
    """Renderizar página de trading"""
    st.markdown("<h1>💰 Simulador de Trading</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    nivel_info = st.session_state.get_nivel_info(user['nivel_actual'])
    
    # Verificar si mercado está abierto (simulado)
    market_open = True  # Para demo, siempre abierto
    
    # Verificar si completó daily report
    hoy = date.today().isoformat()
    from database.db_manager import get_daily_report
    daily_report = get_daily_report(user['id'], hoy)
    
    if not daily_report or not daily_report.get('completado'):
        st.markdown("""
        <div class="alert-danger">
            ⚠️ <strong>Daily Report Card pendiente</strong><br>
            Debes completar tu check-in matutino antes de operar.
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ir a Daily Report →", type="primary"):
            st.session_state.current_page = "daily_report"
            st.rerun()
        return
    
    # Layout de 3 columnas
    col_left, col_center, col_right = st.columns([1.2, 3, 1.2])
    
    # Panel izquierdo: Scanner y Watchlist
    with col_left:
        st.markdown("### 🔍 Scanner Small Caps")
        
        # Scanner de small caps
        with st.spinner("Cargando scanner..."):
            scanner_df = get_small_cap_scanner()
        
        if not scanner_df.empty:
            # Filtros
            min_gap = st.slider("Gap mínimo %", -20, 50, 5)
            scanner_filtered = scanner_df[scanner_df['change_pct'].abs() >= min_gap]
            
            st.markdown(f"**{len(scanner_filtered)} stocks encontrados**")
            
            for _, stock in scanner_filtered.head(10).iterrows():
                change_color = "#00C805" if stock['change_pct'] > 0 else "#FF5000"
                change_icon = "▲" if stock['change_pct'] > 0 else "▼"
                
                st.markdown(f"""
                <div style="background-color: #141414; padding: 10px; border-radius: 8px; 
                            margin: 5px 0; cursor: pointer; border-left: 3px solid {change_color};"
                     onclick="st.session_state.selected_symbol = '{stock['symbol']}'">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: bold;">{stock['symbol']}</span>
                        <span style="color: {change_color};">{change_icon} {stock['change_pct']:.1f}%</span>
                    </div>
                    <div style="font-size: 11px; color: #666;">
                        ${stock['price']:.2f} | Vol: {stock['volume']:,.0f}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Ver {stock['symbol']}", key=f"btn_{stock['symbol']}"):
                    st.session_state.selected_symbol = stock['symbol']
                    st.rerun()
        
        st.markdown("---")
        
        # Watchlist rápida
        st.markdown("### ⭐ Watchlist")
        from database.db_manager import get_watchlist
        watchlist = get_watchlist(user['id'])
        
        if watchlist:
            for item in watchlist[:5]:
                st.markdown(f"""
                <div style="background-color: #141414; padding: 8px; border-radius: 6px; margin: 3px 0;">
                    <div style="font-weight: bold;">{item['simbolo']}</div>
                    <div style="font-size: 11px; color: #666;">{item.get('setup_detectado', 'Sin setup')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Tu watchlist está vacía")
    
    # Panel central: Chart y controles
    with col_center:
        # Selector de símbolo
        selected_symbol = st.session_state.get('selected_symbol', 'MARA')
        
        col_sym, col_tf, col_chart, col_source, col_refresh = st.columns([2, 1, 1, 1, 1])
        with col_sym:
            symbol = st.text_input("Símbolo", value=selected_symbol, key="symbol_input").upper()
        with col_tf:
            timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=1)
        with col_chart:
            chart_type = st.selectbox("Gráfico", ["Profesional", "Estándar"], index=0)
        with col_source:
            data_source = st.selectbox(
                "Datos", 
                ["Demo", "IBKR", "Yahoo"], 
                index=0, 
                help="Demo: datos sintéticos realistas\nIBKR: conexión directa (requiere TWS)\nYahoo: datos públicos (rate limiting)"
            )
        with col_refresh:
            if st.button("🔄 Actualizar", use_container_width=True):
                st.rerun()
        
        # Obtener datos
        use_ibkr = data_source == "IBKR"
        use_demo = data_source == "Demo"
        with st.spinner(f"Cargando {symbol} via {data_source}..."):
            df = get_stock_data(symbol, period="5d", interval=timeframe, use_ibkr=use_ibkr, use_demo=use_demo)
        
        if df is not None and not df.empty:
            # Chart principal - elegir tipo
            if chart_type == "Profesional":
                # Usar Lightweight Charts de TradingView
                st.markdown(f"### 📊 {symbol} - ${df['close'].iloc[-1]:.2f}")
                render_lightweight_chart(
                    data=df, 
                    symbol=symbol, 
                    height=600, 
                    show_volume=True
                )
            else:
                # Usar gráfico estándar de Plotly
                # Chart principal
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=(f'{symbol} - ${df["close"].iloc[-1]:.2f}', 'Volumen', 'VWAP')
                )
                
                # Velas
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='OHLC',
                    increasing_line_color='#00C805',
                    decreasing_line_color='#FF5000'
                ), row=1, col=1)
                
                # VWAP
                if 'vwap' in df.columns:
                    fig.add_trace(go.Scatter(
                        x=df.index,
                        y=df['vwap'],
                        mode='lines',
                        name='VWAP',
                        line=dict(color='#00D4FF', width=1.5)
                    ), row=1, col=1)
                
                # Volumen
                colors = ['#00C805' if df['close'].iloc[i] >= df['open'].iloc[i] else '#FF5000' 
                         for i in range(len(df))]
                fig.add_trace(go.Bar(
                    x=df.index,
                    y=df['volume'],
                    name='Volumen',
                    marker_color=colors
                ), row=2, col=1)
                
                # VWAP en panel separado
                if 'vwap' in df.columns:
                    fig.add_trace(go.Scatter(
                        x=df.index,
                        y=df['vwap'],
                        mode='lines',
                        name='VWAP',
                        line=dict(color='#FFD700', width=1)
                    ), row=3, col=1)
                
                fig.update_layout(
                    plot_bgcolor='#141414',
                    paper_bgcolor='#0A0A0A',
                    font_color='white',
                    xaxis_rangeslider_visible=False,
                    height=600,
                    showlegend=False,
                    margin=dict(l=50, r=50, t=50, b=50)
                )
                
                # Configurar horario de mercado para todos los subplots
                fig.update_xaxes(
                    rangebreaks=[
                        dict(bounds=["16:00", "09:30"]),  # Excluir horas fuera de mercado
                        dict(bounds=["sat", "mon"]),        # Excluir fines de semana
                    ],
                    gridcolor='#2A2A2A', 
                    showgrid=True
                )
                fig.update_yaxes(gridcolor='#2A2A2A', showgrid=True)
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Información del stock
            current_price = df['close'].iloc[-1]
            day_high = df['high'].max()
            day_low = df['low'].min()
            volume = df['volume'].sum()
            
            col_info1, col_info2, col_info3, col_info4 = st.columns(4)
            with col_info1:
                st.metric("Precio", f"${current_price:.2f}")
            with col_info2:
                st.metric("High del día", f"${day_high:.2f}")
            with col_info3:
                st.metric("Low del día", f"${day_low:.2f}")
            with col_info4:
                st.metric("Volumen", f"{volume:,.0f}")
        else:
            st.error(f"No se pudieron cargar datos para {symbol}")
    
    # Panel derecho: Order Entry
    with col_right:
        st.markdown("### 📝 Order Entry")
        
        # Verificar trades abiertos
        trades_abiertos = get_trades_abiertos(user['id'])
        
        if trades_abiertos:
            st.markdown("#### 📊 Posiciones Abiertas")
            for trade in trades_abiertos:
                current_pnl = (current_price - trade['entrada']) * trade['size'] if df is not None else 0
                pnl_color = "#00C805" if current_pnl > 0 else "#FF5000"
                
                st.markdown(f"""
                <div style="background-color: #141414; padding: 12px; border-radius: 8px; 
                            margin: 8px 0; border: 2px solid {pnl_color};">
                    <div style="font-weight: bold;">{trade['simbolo']} - {trade['setup']}</div>
                    <div style="font-size: 12px; color: #666;">
                        Entrada: ${trade['entrada']:.2f}<br>
                        Size: {trade['size']} shares<br>
                        P&L: <span style="color: {pnl_color}">${current_pnl:.2f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col_close, col_partial = st.columns(2)
                with col_close:
                    if st.button("Cerrar", key=f"close_{trade['id']}", use_container_width=True):
                        st.session_state.trade_to_close = trade
                        st.session_state.current_price = current_price
                        st.rerun()
        
        # Formulario de nueva orden
        st.markdown("#### ➕ Nueva Orden")
        
        with st.form("order_form"):
            # Tipo de operación
            operation_type = st.radio("Tipo", ["LONG", "SHORT"], horizontal=True)
            
            # Setup
            setups_disponibles = ['Morning Panic Dip', 'VWAP Bounce', 'Opening Range Breakout']
            if user['nivel_actual'] >= 3:
                setups_disponibles.append('First Red Day')
            
            setup = st.selectbox("Setup", setups_disponibles)
            
            # Precios
            entry_price = st.number_input("Precio Entrada", 
                                         value=current_price if df is not None else 10.0,
                                         min_value=0.01, step=0.01, format="%.2f")
            
            stop_loss = st.number_input("Stop Loss", 
                                       value=entry_price * 0.98,
                                       min_value=0.01, step=0.01, format="%.2f")
            
            take_profit = st.number_input("Take Profit", 
                                         value=entry_price * 1.06,
                                         min_value=0.01, step=0.01, format="%.2f")
            
            # Calcular posición
            risk_amount = nivel_info['riesgo_max']
            if stop_loss < entry_price:
                risk_per_share = entry_price - stop_loss
                shares = int(risk_amount / risk_per_share)
            else:
                shares = 100
            
            size = st.number_input("Size (shares)", value=shares, min_value=1, step=10)
            
            # Mostrar cálculos
            total_cost = size * entry_price
            max_risk = size * (entry_price - stop_loss) if stop_loss < entry_price else 0
            potential_reward = size * (take_profit - entry_price) if take_profit > entry_price else 0
            rr_ratio = potential_reward / max_risk if max_risk > 0 else 0
            
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 10px; border-radius: 6px; margin: 10px 0;">
                <div style="font-size: 12px; color: #666;">Resumen:</div>
                <div style="font-size: 13px;">
                    Costo total: <strong>${total_cost:,.2f}</strong><br>
                    Riesgo máx: <span style="color: #FF5000;">${max_risk:,.2f}</span><br>
                    Beneficio pot: <span style="color: #00C805;">${potential_reward:,.2f}</span><br>
                    R:R Ratio: <strong>{rr_ratio:.2f}:1</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Validaciones
            warnings = []
            if rr_ratio < 2:
                warnings.append(f"⚠️ R:R bajo ({rr_ratio:.1f}:1). Mínimo recomendado: 2:1")
            if max_risk > nivel_info['riesgo_max']:
                warnings.append(f"⚠️ Riesgo excede ${nivel_info['riesgo_max']}")
            
            for w in warnings:
                st.warning(w)
            
            # Botón de ejecutar
            submitted = st.form_submit_button("🚀 EJECUTAR TRADE", use_container_width=True, 
                                             type="primary" if len(warnings) == 0 else "secondary")
            
            if submitted:
                # Validar trade
                validation = validate_trade_plan(
                    entry_price, stop_loss, take_profit, setup, nivel_info['riesgo_max']
                )
                
                if not validation['valid']:
                    for error in validation['errors']:
                        st.error(error)
                else:
                    # Crear trade
                    trade_id = create_trade(
                        user_id=user['id'],
                        simbolo=symbol,
                        setup=setup,
                        entrada=entry_price,
                        size=size,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        tipo_operacion=operation_type,
                        emocion_entrada=daily_report.get('estado_emocional', 'Neutral')
                    )
                    
                    # Añadir XP
                    add_xp_to_user(user['id'], 10)
                    
                    st.success(f"✅ Trade ejecutado! ID: {trade_id}")
                    st.rerun()
        
        # Hotkeys info
        st.markdown("""
        <div style="background-color: #141414; padding: 10px; border-radius: 6px; margin-top: 15px;">
            <div style="font-size: 12px; color: #666; margin-bottom: 5px;">HOTKEYS</div>
            <div style="font-size: 11px;">
                <kbd style="background: #2A2A2A; padding: 2px 6px; border-radius: 3px;">F1</kbd> Compra rápida<br>
                <kbd style="background: #2A2A2A; padding: 2px 6px; border-radius: 3px;">F2</kbd> Venta rápida<br>
                <kbd style="background: #2A2A2A; padding: 2px 6px; border-radius: 3px;">ESC</kbd> Cancelar
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Modal para cerrar trade
    if 'trade_to_close' in st.session_state:
        trade = st.session_state.trade_to_close
        current_price = st.session_state.get('current_price', trade['entrada'])
        
        st.markdown("---")
        st.markdown("### 🔒 Cerrar Posición")
        
        col1, col2 = st.columns(2)
        with col1:
            exit_price = st.number_input("Precio de salida", 
                                        value=current_price,
                                        min_value=0.01, step=0.01)
        with col2:
            emocion_salida = st.selectbox("Emoción al cerrar", 
                                         ["Neutral", "Feliz", "Aliviado", "Arrepentido", 
                                          "Ansioso", "Confiado", "Frustrado"])
        
        cumplio_plan = st.radio("¿Seguiste tu plan?", ["Sí", "No", "Parcial"], horizontal=True)
        notas = st.text_area("Notas del trade", placeholder="¿Qué aprendiste?")
        
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("✅ Confirmar Cierre", type="primary", use_container_width=True):
                # Calcular P&L
                if trade['tipo_operacion'] == 'LONG':
                    pnl = (exit_price - trade['entrada']) * trade['size']
                else:
                    pnl = (trade['entrada'] - exit_price) * trade['size']
                
                pnl_pct = (pnl / (trade['entrada'] * trade['size'])) * 100
                
                # Calcular R-Multiple
                r_mult = calculate_r_multiple(
                    trade['entrada'], exit_price, trade['stop_loss'], trade['tipo_operacion']
                )
                
                # Cerrar trade
                close_trade(
                    trade_id=trade['id'],
                    salida=exit_price,
                    pnl=pnl,
                    pnl_porcentaje=pnl_pct,
                    r_multiple=r_mult,
                    cumplio_plan=(cumplio_plan == "Sí"),
                    emocion_salida=emocion_salida,
                    notas=notas
                )
                
                # Actualizar capital
                nuevo_capital = user['capital_virtual'] + pnl
                update_user_capital(user['id'], nuevo_capital)
                
                # Actualizar mastery del setup
                update_setup_mastery(user['id'], trade['setup'], ganado=(pnl > 0))
                
                # Añadir XP
                xp_ganado = 10
                if pnl > 0:
                    xp_ganado += 5
                if r_mult >= 3:
                    xp_ganado += 10
                if cumplio_plan == "Sí":
                    xp_ganado += 5
                
                add_xp_to_user(user['id'], xp_ganado)
                
                # Verificar logros
                nuevos_logros = check_all_achievements(user['id'])
                if nuevos_logros:
                    for logro in nuevos_logros:
                        st.balloons()
                        st.success(f"🏆 ¡Logro desbloqueado: {logro}!")
                
                # Limpiar session state
                del st.session_state.trade_to_close
                del st.session_state.current_price
                
                st.success(f"Trade cerrado! P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")
                st.rerun()
        
        with col_cancel:
            if st.button("❌ Cancelar", use_container_width=True):
                del st.session_state.trade_to_close
                if 'current_price' in st.session_state:
                    del st.session_state.current_price
                st.rerun()