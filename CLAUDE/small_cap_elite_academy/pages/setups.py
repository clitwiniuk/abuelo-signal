import streamlit as st
from database.db_manager import get_setups_mastery

def render_setups_page():
    """Renderizar página de setups"""
    st.markdown("<h1>🎯 Biblioteca de Setups</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    setups = get_setups_mastery(user['id'])
    
    st.markdown("""
    <div style="background-color: #141414; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
        <div style="color: #B0B0B0; font-size: 14px;">
            Domina estos setups probados por traders profesionales. Cada setup tiene su propio 
            edge estadístico. Practica hasta que la ejecución sea automática.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Información de cada setup
    setups_info = {
        "Morning Panic Dip": {
            "trader": "Kyle Williams",
            "icon": "🌅",
            "descripcion": "Aprovecha el pánico matutino en small caps para comprar en soporte.",
            "trigger": "Caída >20% en primeros 15 minutos de apertura",
            "confirmacion": [
                "Volumen >2x el promedio",
                "Precio en nivel de soporte psicológico ($1, $2, $5, $10)",
                "Rechazo con velas de reversión (hammer, engulfing)"
            ],
            "entrada": "Break del high de la vela de rechazo",
            "stop_loss": "Bajo del mínimo del día o nivel de soporte",
            "target": "Mínimo 1:3 R:R, ideal 1:5",
            "riesgo": "Alto - Small caps volátiles",
            "nivel_requerido": 1,
            "tips": [
                "Mejor en stocks con catalyst reciente (earnings, news)",
                "Evitar si el mercado general está en caída fuerte",
                "Esperar confirmación de volumen, no anticipar"
            ]
        },
        "VWAP Bounce": {
            "trader": "Alex Temiz",
            "icon": "📊",
            "descripcion": "Opera el rebote del precio en la línea VWAP con confirmación de volumen.",
            "trigger": "Precio cruza VWAP hacia abajo y muestra señales de rechazo",
            "confirmacion": [
                "3 velas de 1min confirmando rechazo en VWAP",
                "Volumen creciente en el rebote",
                "Vela verde que cierra por encima de VWAP"
            ],
            "entrada": "Break del high de la vela de confirmación",
            "stop_loss": "Bajo del rango de consolidación o VWAP",
            "target": "1:2 a 1:4 R:R",
            "riesgo": "Medio - Depende de la tendencia intradía",
            "nivel_requerido": 1,
            "tips": [
                "Funciona mejor en tendencia alcista intradía",
                "Múltiples toques a VWAP aumentan probabilidad",
                "Evitar si VWAP está muy lejos del precio"
            ]
        },
        "First Red Day": {
            "trader": "Short Selling",
            "icon": "🔻",
            "descripcion": "Opera en corto después de una racha alcista cuando aparece el primer día rojo.",
            "trigger": "Después de 3+ días verdes consecutivos, primer día rojo",
            "confirmacion": [
                "Gap down en la apertura O reversión intradía",
                "Volumen alto en la caída",
                "Break de soporte del día anterior"
            ],
            "entrada": "Break del low del día anterior o consolidación",
            "stop_loss": "Alto del día anterior (resistencia clave)",
            "target": "1:3 a 1:5 R:R",
            "riesgo": "Alto - Short squeezes posibles",
            "nivel_requerido": 3,
            "tips": [
                "SOLO para traders con experiencia (Nivel 3+)",
                "Verificar borrow availability antes de operar",
                "Tener un plan claro de salida, los shorts pueden explotar"
            ]
        },
        "Opening Range Breakout": {
            "trader": "Lance Breitstein",
            "icon": "🚀",
            "descripcion": "Opera el breakout del rango establecido en los primeros minutos del día.",
            "trigger": "Break de rango de primeros 5-30 minutos",
            "confirmacion": [
                "Volumen creciente en el breakout",
                "Alineación con tendencia mayor (diaria)",
                "Consolidación antes del break (construcción de base)"
            ],
            "entrada": "Pullback al nivel de breakout o break directo",
            "stop_loss": "Bajo del rango de apertura o 50% del pullback",
            "target": "1:2 a 1:4 R:R",
            "riesgo": "Medio - Falsos breaks comunes",
            "nivel_requerido": 1,
            "tips": [
                "Definir el rango claramente antes de operar",
                "Esperar cierre de vela por encima/del rango",
                "Tamaño de posición menor debido a volatilidad"
            ]
        }
    }
    
    # Mostrar cada setup
    for setup_data in setups:
        setup_name = setup_data['setup_type']
        info = setups_info.get(setup_name, {})
        
        if not info:
            continue
        
        # Verificar si está bloqueado por nivel
        bloqueado = user['nivel_actual'] < info.get('nivel_requerido', 1)
        
        # Card del setup
        opacity = "0.5" if bloqueado else "1"
        cursor = "not-allowed" if bloqueado else "pointer"
        
        with st.expander(f"{info.get('icon', '📈')} {setup_name} - by {info.get('trader', 'Unknown')}", 
                        expanded=False):
            
            if bloqueado:
                st.error(f"🔒 Bloqueado - Requiere Nivel {info.get('nivel_requerido')}")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**{info.get('descripcion', '')}**")
                
                st.markdown("#### 🎯 Trigger")
                st.markdown(f"{info.get('trigger', '')}")
                
                st.markdown("#### ✅ Confirmación")
                for conf in info.get('confirmacion', []):
                    st.markdown(f"- {conf}")
                
                st.markdown("#### 📝 Plan de Trade")
                st.markdown(f"""
                <div style="background-color: #1E1E1E; padding: 15px; border-radius: 8px;">
                    <div style="margin-bottom: 8px;">
                        <span style="color: #00C805;">▶ ENTRADA:</span> {info.get('entrada', '')}
                    </div>
                    <div style="margin-bottom: 8px;">
                        <span style="color: #FF5000;">⛔ STOP:</span> {info.get('stop_loss', '')}
                    </div>
                    <div>
                        <span style="color: #00D4FF;">🎯 TARGET:</span> {info.get('target', '')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### 💡 Tips del Pro")
                for tip in info.get('tips', []):
                    st.markdown(f"- {tip}")
            
            with col2:
                # Progreso del usuario en este setup
                st.markdown("#### 📊 Tu Progreso")
                
                trades_practicados = setup_data.get('trades_practicados', 0)
                trades_ganados = setup_data.get('trades_ganados', 0)
                win_rate = setup_data.get('win_rate', 0)
                dominado = setup_data.get('dominado', False)
                
                st.markdown(f"""
                <div class="metric-card">
                    <div style="color: #B0B0B0; font-size: 12px;">TRADES</div>
                    <div style="color: white; font-size: 28px; font-weight: bold;">
                        {trades_practicados}
                    </div>
                    <div style="color: #666; font-size: 11px;">
                        {trades_ganados} ganados
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                color_wr = "#00C805" if win_rate >= 50 else "#FF5000"
                st.markdown(f"""
                <div class="metric-card" style="margin-top: 10px;">
                    <div style="color: #B0B0B0; font-size: 12px;">WIN RATE</div>
                    <div style="color: {color_wr}; font-size: 28px; font-weight: bold;">
                        {win_rate:.1f}%
                    </div>
                    <div style="color: #666; font-size: 11px;">
                        Objetivo: 60%
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Barra de progreso hacia dominio
                progreso = min(100, (trades_practicados / 20) * 100)
                st.markdown(f"""
                <div style="margin-top: 15px;">
                    <div style="font-size: 11px; color: #666; margin-bottom: 5px;">
                        Progreso hacia dominio: {trades_practicados}/20 trades
                    </div>
                    <div class="xp-progress-container" style="height: 10px;">
                        <div class="xp-progress-bar" style="width: {progreso}%"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if dominado:
                    st.success("✅ SETUP DOMINADO")
                elif trades_practicados >= 20 and win_rate >= 60:
                    st.info("🎯 ¡Cerca! Mantén consistencia")
                elif trades_practicados < 20:
                    st.warning(f"📚 Practica más: {20 - trades_practicados} trades restantes")
                else:
                    st.warning("📈 Mejora tu win rate")
                
                # Nivel de riesgo
                riesgo_color = {"Alto": "#FF5000", "Medio": "#FFD700", "Bajo": "#00C805"}
                riesgo = info.get('riesgo', 'Medio')
                st.markdown(f"""
                <div style="margin-top: 15px; text-align: center;">
                    <span style="background-color: {riesgo_color.get(riesgo, '#FFD700')}; 
                                color: black; padding: 4px 12px; border-radius: 12px; 
                                font-size: 11px; font-weight: bold;">
                        RIESGO: {riesgo.upper()}
                    </span>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Sección de práctica
    st.markdown("### 🎓 Modo Práctica")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="setup-card">
            <div style="font-size: 24px; margin-bottom: 10px;">🎯</div>
            <div style="font-weight: bold; margin-bottom: 5px;">Pattern Recognition</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 15px;">
                Practica identificando setups en charts históricos
            </div>
            <button style="width: 100%; background-color: #00D4FF; color: black; 
                          border: none; padding: 8px; border-radius: 6px; font-weight: bold;">
                Iniciar
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Iniciar Pattern Recognition", key="btn_pattern"):
            st.session_state.current_page = "entrenamiento"
            st.session_state.training_mode = "pattern"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="setup-card">
            <div style="font-size: 24px; margin-bottom: 10px;">⏪</div>
            <div style="font-weight: bold; margin-bottom: 5px;">Replay Histórico</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 15px;">
                Opera días históricos con datos reales
            </div>
            <button style="width: 100%; background-color: #00D4FF; color: black; 
                          border: none; padding: 8px; border-radius: 6px; font-weight: bold;">
                Iniciar
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Iniciar Replay", key="btn_replay"):
            st.session_state.current_page = "entrenamiento"
            st.session_state.training_mode = "replay"
            st.rerun()
    
    with col3:
        st.markdown("""
        <div class="setup-card">
            <div style="font-size: 24px; margin-bottom: 10px;">🔥</div>
            <div style="font-weight: bold; margin-bottom: 5px;">Drill Intensivo</div>
            <div style="font-size: 12px; color: #666; margin-bottom: 15px;">
                Repetición deliberada de un setup específico
            </div>
            <button style="width: 100%; background-color: #00D4FF; color: black; 
                          border: none; padding: 8px; border-radius: 6px; font-weight: bold;">
                Iniciar
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Iniciar Drill", key="btn_drill"):
            st.session_state.current_page = "entrenamiento"
            st.session_state.training_mode = "drill"
            st.rerun()
    
    # Comparativa con traders top
    st.markdown("---")
    st.markdown("### 🏆 Benchmark: Traders Profesionales")
    
    benchmark_data = {
        'Métrica': ['Win Rate', 'Profit Factor', 'Avg R-Multiple', 'Max Drawdown', 'Trades/Mes'],
        'Steven Dux': ['55-60%', '2.5+', '2.5R', '<15%', '200+'],
        'Kyle Williams': ['50-55%', '2.0+', '2.0R', '<20%', '100+'],
        'Alex Temiz': ['60-65%', '2.2+', '2.2R', '<12%', '150+'],
        'Tú (Objetivo)': ['>55%', '>1.5', '>2.0R', '<10%', '50+']
    }
    
    df_benchmark = pd.DataFrame(benchmark_data)
    st.dataframe(df_benchmark, use_container_width=True, hide_index=True)
    
    st.markdown("""
    <div style="background-color: #141414; padding: 15px; border-radius: 8px; margin-top: 20px;">
        <div style="color: #FFD700; font-weight: bold; margin-bottom: 10px;">💡 Recuerda</div>
        <div style="color: #B0B0B0; font-size: 13px;">
            Los traders profesionales no ganan todos sus trades. Su edge viene de:
            <ul style="margin-top: 8px; padding-left: 20px;">
                <li>Win rate moderado (50-60%) con buen R:R</li>
                <li>Disciplina estricta en la gestión de riesgo</li>
                <li>Consistencia en la ejecución de setups</li>
                <li>Control emocional y autoconsciencia</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)