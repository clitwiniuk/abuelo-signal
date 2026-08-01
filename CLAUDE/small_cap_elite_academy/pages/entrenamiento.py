import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import random
from datetime import datetime, date, timedelta

from utils.market_data import get_stock_data, serie_sintetica
from database.db_manager import add_xp_to_user

def render_entrenamiento_page():
    """Renderizar página de entrenamiento"""
    st.markdown("<h1>📚 Centro de Entrenamiento</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    
    # Tabs para diferentes modos
    tab1, tab2, tab3 = st.tabs(["🎯 Pattern Recognition", "⏪ Replay Histórico", "🔥 Drill Intensivo"])
    
    # Tab 1: Pattern Recognition
    with tab1:
        st.markdown("### 🎯 Pattern Recognition")
        st.markdown("""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            Practica identificando setups en charts históricos reales. 
            El reconocimiento de patrones es una habilidad que se desarrolla con la repetición.
        </div>
        """, unsafe_allow_html=True)
        
        # Configuración
        col1, col2, col3 = st.columns(3)
        
        with col1:
            setup_practica = st.selectbox(
                "Setup a practicar",
                ["Todos", "Morning Panic Dip", "VWAP Bounce", "Opening Range Breakout", "First Red Day"]
            )
        
        with col2:
            dificultad = st.select_slider(
                "Dificultad",
                options=["Fácil", "Medio", "Difícil"],
                value="Medio"
            )
        
        with col3:
            num_ejercicios = st.number_input("Ejercicios", min_value=5, max_value=50, value=10)
        
        # Iniciar sesión de entrenamiento
        if 'pattern_session' not in st.session_state:
            st.session_state.pattern_session = {
                'active': False,
                'current': 0,
                'correct': 0,
                'ejercicios': []
            }
        
        if not st.session_state.pattern_session['active']:
            if st.button("🚀 Iniciar Sesión de Entrenamiento", type="primary", use_container_width=True):
                st.session_state.pattern_session['active'] = True
                st.session_state.pattern_session['current'] = 0
                st.session_state.pattern_session['correct'] = 0
                # Generar ejercicios (simulados)
                setups = ["Morning Panic Dip", "VWAP Bounce", "Opening Range Breakout", "First Red Day"]
                st.session_state.pattern_session['ejercicios'] = [
                    {'setup': random.choice(setups), 'symbol': random.choice(['MARA', 'RIOT', 'AMC', 'GME'])}
                    for _ in range(num_ejercicios)
                ]
                st.rerun()
        
        else:
            session = st.session_state.pattern_session
            
            # Mostrar progreso
            progreso = (session['current'] / len(session['ejercicios'])) * 100
            st.markdown(f"""
            <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span>Progreso: {session['current']}/{len(session['ejercicios'])}</span>
                    <span>Aciertos: {session['correct']}</span>
                </div>
                <div class="xp-progress-container">
                    <div class="xp-progress-bar" style="width: {progreso}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if session['current'] < len(session['ejercicios']):
                ejercicio = session['ejercicios'][session['current']]
                
                # Simular chart
                st.markdown(f"#### 📊 Chart {session['current'] + 1}: {ejercicio['symbol']}")
                
                # Generar chart de ejemplo con datos sintéticos realistas
                fig = go.Figure()
                
                # Obtener datos históricos reales y generar serie sintética
                try:
                    # Obtener datos históricos de un stock real
                    real_data = get_stock_data(ejercicio['symbol'], period="2mo", interval="1d")
                    
                    if real_data is not None and not real_data.empty:
                        # Generar serie sintética con aleatoriedad controlada
                        synthetic_data = serie_sintetica(real_data, n_candlesticks=5, n_bloques=6)
                        
                        if synthetic_data is not None:
                            # Usar los datos sintéticos
                            chart_data = synthetic_data.tail(30)  # Últimas 30 velas
                        else:
                            # Fallback a datos reales si falla sintética
                            chart_data = real_data.tail(30)
                    else:
                        # Fallback a datos simulados si no hay datos reales
                        raise ValueError("No hay datos reales disponibles")
                        
                except:
                    # Fallback a simulación mejorada si todo falla
                    n = 30
                    base_price = 100
                    
                    # Generar retornos aleatorios con volatilidad realista
                    returns = np.random.normal(0, 0.02, n)  # 2% volatilidad diaria
                    prices = [base_price]
                    
                    for i in range(1, n):
                        new_price = prices[-1] * (1 + returns[i])
                        prices.append(new_price)
                    
                    # Crear DataFrame OHLC realista
                    chart_data = pd.DataFrame({
                        'open': prices,
                        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
                        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
                        'close': prices[1:] + [prices[-1]],
                        'volume': np.random.randint(1000000, 5000000, n)
                    })
                
                # Añadir velas al gráfico
                fig.add_trace(go.Candlestick(
                    x=list(range(len(chart_data))),
                    open=chart_data['open'],
                    high=chart_data['high'],
                    low=chart_data['low'],
                    close=chart_data['close'],
                    name='Price',
                    increasing_line_color='#00C805',
                    decreasing_line_color='#FF5000'
                ))
                
                fig.update_layout(
                    plot_bgcolor='#141414',
                    paper_bgcolor='#0A0A0A',
                    font_color='white',
                    height=400,
                    showlegend=False,
                    xaxis=dict(showgrid=True, gridcolor='#2A2A2A', rangeslider_visible=False),
                    yaxis=dict(showgrid=True, gridcolor='#2A2A2A')
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Pregunta
                st.markdown("#### 🤔 ¿Qué setup identificas en este chart?")
                
                opciones = ["Morning Panic Dip", "VWAP Bounce", "Opening Range Breakout", "First Red Day", "Ninguno"]
                respuesta = st.radio("Selecciona tu respuesta:", opciones, key=f"resp_{session['current']}")
                
                col_check, col_skip = st.columns(2)
                
                with col_check:
                    if st.button("✅ Verificar", type="primary", use_container_width=True):
                        correcta = respuesta == ejercicio['setup']
                        
                        if correcta:
                            st.session_state.pattern_session['correct'] += 1
                            st.success(f"✅ ¡Correcto! Este es un {ejercicio['setup']}")
                            add_xp_to_user(user['id'], 5)
                        else:
                            st.error(f"❌ Incorrecto. Este es un {ejercicio['setup']}")
                        
                        # Mostrar explicación
                        explicaciones = {
                            "Morning Panic Dip": "El precio cayó >20% en los primeros minutos y luego rebotó en soporte.",
                            "VWAP Bounce": "El precio tocó la línea VWAP y rebotó con confirmación de volumen.",
                            "Opening Range Breakout": "El precio rompió el rango de apertura con volumen creciente.",
                            "First Red Day": "Después de varios días alcistas, aparece el primer día con caída."
                        }
                        
                        st.info(f"💡 **Explicación:** {explicaciones.get(ejercicio['setup'], '')}")
                        
                        st.session_state.pattern_session['current'] += 1
                        
                        if st.button("Siguiente →"):
                            st.rerun()
                
                with col_skip:
                    if st.button("⏭️ Saltar", use_container_width=True):
                        st.session_state.pattern_session['current'] += 1
                        st.rerun()
            
            else:
                # Sesión completada
                precision = (session['correct'] / len(session['ejercicios'])) * 100
                
                st.balloons()
                st.success(f"🎉 ¡Sesión completada! Precisión: {precision:.1f}%")
                
                # XP ganado
                xp_ganado = session['correct'] * 5
                if precision >= 80:
                    xp_ganado += 50
                    st.success("🏆 Bonus de +50 XP por excelente precisión!")
                
                st.info(f"Total XP ganado: +{xp_ganado}")
                
                if st.button("🔄 Nueva Sesión", use_container_width=True):
                    st.session_state.pattern_session['active'] = False
                    st.rerun()
    
    # Tab 2: Replay Histórico
    with tab2:
        st.markdown("### ⏪ Replay Histórico")
        st.markdown("""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            Opera días históricos reales con datos de mercado. Practica en condiciones 
            realistas sin arriesgar capital. Incluye épocas de alta volatilidad como Enero 2021.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fecha_replay = st.date_input(
                "Fecha a replay",
                value=datetime(2021, 1, 27),
                min_value=datetime(2020, 1, 1),
                max_value=datetime.now() - timedelta(days=1)
            )
        
        with col2:
            symbol_replay = st.selectbox(
                "Símbolo",
                ["GME", "AMC", "MARA", "RIOT", "PLTR", "NIO", "TSLA"]
            )
        
        with col3:
            velocidad = st.select_slider(
                "Velocidad",
                options=["1x", "2x", "5x", "10x"],
                value="2x"
            )
        
        if st.button("▶️ Iniciar Replay", type="primary", use_container_width=True):
            st.info(f"🎬 Cargando replay de {symbol_replay} para {fecha_replay}...")
            
            # Simular carga de datos
            with st.spinner("Cargando datos históricos..."):
                # En producción, esto cargaría datos reales de esa fecha
                st.success("✅ Datos cargados. Modo replay activo.")
                
                # Mostrar chart con datos sintéticos realistas
                fig = go.Figure()
                
                # Obtener datos históricos y generar serie sintética
                try:
                    # Obtener datos históricos reales del symbol
                    real_data = get_stock_data(symbol_replay, period="3mo", interval="1d")
                    
                    if real_data is not None and not real_data.empty:
                        # Generar serie sintética para mayor aleatoriedad
                        synthetic_data = serie_sintetica(real_data, n_candlesticks=5, n_bloques=8)
                        
                        if synthetic_data is not None:
                            # Usar datos sintéticos para replay
                            chart_data = synthetic_data.tail(40)  # 40 velas para replay
                        else:
                            # Fallback a datos reales
                            chart_data = real_data.tail(40)
                    else:
                        # Fallback a simulación mejorada
                        raise ValueError("No hay datos reales")
                        
                except:
                    # Simulación mejorada con volatilidad realista
                    n = 40
                    
                    # Simular diferentes comportamientos según symbol y fecha
                    if symbol_replay == "GME" and fecha_replay.year == 2021:
                        # Simular la manía de GME con alta volatilidad
                        base = 40
                        trend = np.linspace(0, 300, n)  # Trend alcista fuerte
                        volatility = 0.15  # 15% volatilidad
                    elif symbol_replay in ["AMC", "MARA", "RIOT"]:
                        # Simular meme stocks con volatilidad media-alta
                        base = 20
                        trend = np.random.normal(0, 2, n)
                        volatility = 0.08
                    else:
                        # Stocks normales con volatilidad estándar
                        base = 50
                        trend = np.random.normal(0, 1, n)
                        volatility = 0.03
                    
                    # Generar precios con tendencia y volatilidad
                    returns = np.random.normal(0, volatility, n) + (trend / base / n)
                    prices = [base]
                    
                    for i in range(1, n):
                        new_price = prices[-1] * (1 + returns[i])
                        prices.append(max(new_price, 1))  # Evitar precios negativos
                    
                    # Crear DataFrame OHLC realista
                    chart_data = pd.DataFrame({
                        'open': prices,
                        'high': [p * (1 + abs(np.random.normal(0, volatility/2))) for p in prices],
                        'low': [p * (1 - abs(np.random.normal(0, volatility/2))) for p in prices],
                        'close': prices[1:] + [prices[-1]],
                        'volume': np.random.randint(500000, 10000000, n)
                    })
                
                # Añadir velas al gráfico
                fig.add_trace(go.Candlestick(
                    x=list(range(len(chart_data))),
                    open=chart_data['open'],
                    high=chart_data['high'],
                    low=chart_data['low'],
                    close=chart_data['close'],
                    name='Price',
                    increasing_line_color='#00C805',
                    decreasing_line_color='#FF5000'
                ))
                
                fig.update_layout(
                    title=f"{symbol_replay} - {fecha_replay} (Replay)",
                    plot_bgcolor='#141414',
                    paper_bgcolor='#0A0A0A',
                    font_color='white',
                    height=500,
                    xaxis_rangeslider_visible=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Controles de replay
                col_play, col_pause, col_stop = st.columns(3)
                
                with col_play:
                    st.button("▶️ Play", use_container_width=True)
                with col_pause:
                    st.button("⏸️ Pausa", use_container_width=True)
                with col_stop:
                    st.button("⏹️ Detener", use_container_width=True)
                
                # Panel de orden
                st.markdown("---")
                st.markdown("#### 📝 Order Entry (Replay Mode)")
                
                col_buy, col_sell = st.columns(2)
                with col_buy:
                    st.button("🟢 COMPRAR", use_container_width=True, type="primary")
                with col_sell:
                    st.button("🔴 VENDER", use_container_width=True)
        
        # Épocas famosas
        st.markdown("---")
        st.markdown("### 📅 Épocas Famosas para Practicar")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="setup-card">
                <div style="font-weight: bold; color: #FFD700;">Enero 2021</div>
                <div style="font-size: 12px; color: #666; margin: 10px 0;">
                    La época de las meme stocks. GME, AMC y otras acciones 
                    tuvieron movimientos extremos.
                </div>
                <div style="font-size: 11px; color: #00C805;">
                    Volatilidad: EXTREMA
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="setup-card">
                <div style="font-weight: bold; color: #00D4FF;">Marzo 2020</div>
                <div style="font-size: 12px; color: #666; margin: 10px 0;">
                    Crash del COVID-19. Oportunidades de short y luego 
                    recuperación masiva.
                </div>
                <div style="font-size: 11px; color: #FF5000;">
                    Volatilidad: ALTA
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="setup-card">
                <div style="font-weight: bold; color: #00C805;">Noviembre 2024</div>
                <div style="font-size: 12px; color: #666; margin: 10px 0;">
                    Rally post-elecciones. Mercado alcista con 
                    oportunidades en small caps.
                </div>
                <div style="font-size: 11px; color: #00C805;">
                    Volatilidad: MEDIA
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Tab 3: Drill Intensivo
    with tab3:
        st.markdown("### 🔥 Drill Intensivo")
        st.markdown("""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            Repetición deliberada de un setup específico. Practica la misma entrada 
            10-20 veces para desarrollar memoria muscular y consistencia.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            setup_drill = st.selectbox(
                "Setup para practicar",
                ["Morning Panic Dip", "VWAP Bounce", "Opening Range Breakout"]
            )
            
            num_repeticiones = st.slider("Repeticiones", 5, 30, 10)
        
        with col2:
            duracion = st.select_slider(
                "Duración de la sesión",
                options=["15 min", "30 min", "1 hora", "2 horas"],
                value="30 min"
            )
            
            focus_area = st.multiselect(
                "Áreas de enfoque",
                ["Timing de entrada", "Colocación de stop", "Gestión de posición", "Salida parcial"],
                default=["Timing de entrada"]
            )
        
        if st.button("🔥 Iniciar Drill", type="primary", use_container_width=True):
            st.success(f"🔥 Drill iniciado: {setup_drill}")
            
            # Simular drill
            progreso = st.progress(0)
            
            for i in range(num_repeticiones):
                progreso.progress((i + 1) / num_repeticiones)
                
                # Mostrar ejercicio
                st.markdown(f"#### Repetición {i + 1}/{num_repeticiones}")
                
                # Simular escenario con datos sintéticos realistas
                fig = go.Figure()
                
                # Obtener datos históricos para generar sintéticos
                try:
                    # Usar un stock real como base según el setup
                    symbol_map = {
                        "Morning Panic Dip": "MARA",
                        "VWAP Bounce": "PLTR", 
                        "Opening Range Breakout": "TSLA"
                    }
                    base_symbol = symbol_map.get(setup_drill, "SPY")
                    
                    # Obtener datos reales
                    real_data = get_stock_data(base_symbol, period="1mo", interval="1h")
                    
                    if real_data is not None and not real_data.empty:
                        # Generar serie sintética
                        synthetic_data = serie_sintetica(real_data, n_candlesticks=3, n_bloques=7)
                        
                        if synthetic_data is not None:
                            chart_data = synthetic_data.tail(20)
                        else:
                            chart_data = real_data.tail(20)
                    else:
                        raise ValueError("No hay datos reales")
                        
                except:
                    # Simulación mejorada según el setup
                    n = 20
                    base_price = 100
                    
                    if setup_drill == "Morning Panic Dip":
                        # Simular pánico matutino con caída y rebote
                        returns = np.concatenate([
                            np.random.normal(-0.03, 0.02, 4),  # Caída fuerte
                            np.random.normal(0.02, 0.015, 8),  # Rebote
                            np.random.normal(0.005, 0.01, 7)   # Estabilización
                        ])
                    elif setup_drill == "VWAP Bounce":
                        # Simular rebote en VWAP con volatilidad controlada
                        returns = np.concatenate([
                            np.random.normal(-0.01, 0.015, 6),  # Ligera caída
                            np.random.normal(0.015, 0.01, 7),  # Rebote
                            np.random.normal(0.005, 0.008, 6)  # Continuación
                        ])
                    else:  # Opening Range Breakout
                        # Simular breakout con expansión de volatilidad
                        returns = np.concatenate([
                            np.random.normal(0, 0.005, 8),     # Consolidación
                            np.random.normal(0.02, 0.015, 6),   # Breakout
                            np.random.normal(0.01, 0.01, 5)     # Trend continuado
                        ])
                    
                    # Generar precios
                    prices = [base_price]
                    for ret in returns:
                        new_price = prices[-1] * (1 + ret)
                        prices.append(max(new_price, 1))
                    
                    # Crear DataFrame OHLC realista
                    chart_data = pd.DataFrame({
                        'open': prices,
                        'high': [p * (1 + abs(np.random.normal(0, 0.008))) for p in prices],
                        'low': [p * (1 - abs(np.random.normal(0, 0.008))) for p in prices],
                        'close': prices[1:] + [prices[-1]],
                        'volume': np.random.randint(100000, 2000000, n)
                    })
                
                # Añadir velas al gráfico
                fig.add_trace(go.Candlestick(
                    x=list(range(len(chart_data))),
                    open=chart_data['open'],
                    high=chart_data['high'],
                    low=chart_data['low'],
                    close=chart_data['close'],
                    name='Price',
                    increasing_line_color='#00C805',
                    decreasing_line_color='#FF5000'
                ))
                
                fig.update_layout(
                    plot_bgcolor='#141414',
                    paper_bgcolor='#0A0A0A',
                    font_color='white',
                    height=300,
                    xaxis_rangeslider_visible=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Preguntas de evaluación
                st.markdown("**Evalúa tu ejecución:**")
                
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    timing = st.select_slider(
                        f"Timing {i+1}",
                        options=["Muy temprano", "Temprano", "Perfecto", "Tarde", "Muy tarde"],
                        key=f"timing_{i}"
                    )
                
                with col_b:
                    stop = st.select_slider(
                        f"Stop {i+1}",
                        options=["Muy ajustado", "Ajustado", "Correcto", "Lejano", "Muy lejano"],
                        key=f"stop_{i}"
                    )
                
                with col_c:
                    confianza = st.slider(
                        f"Confianza {i+1}",
                        1, 10, 5,
                        key=f"conf_{i}"
                    )
                
                st.markdown("---")
            
            # Resumen del drill
            st.balloons()
            st.success("🎉 ¡Drill completado!")
            
            xp_ganado = num_repeticiones * 3
            add_xp_to_user(user['id'], xp_ganado)
            
            st.info(f"XP ganado: +{xp_ganado}")
            
            st.markdown("""
            <div style="background-color: #141414; padding: 20px; border-radius: 12px; margin-top: 20px;">
                <div style="color: #FFD700; font-weight: bold; margin-bottom: 10px;">
                    💡 Reflexión Post-Drill
                </div>
                <div style="color: #B0B0B0;">
                    La repetición deliberada es clave para la maestría. Al practicar el mismo 
                    setup múltiples veces, estás construyendo memoria muscular y patrones 
                    neuronales que te permitirán ejecutar con precisión bajo presión.
                </div>
            </div>
            """, unsafe_allow_html=True)