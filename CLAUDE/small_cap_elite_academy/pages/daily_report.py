import streamlit as st
from datetime import date, datetime
from database.db_manager import create_or_update_daily_report, get_daily_report, add_xp_to_user

def render_daily_report_page():
    """Renderizar página de Daily Report Card"""
    st.markdown("<h1>📓 Daily Report Card</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    hoy = date.today().isoformat()
    
    # Verificar si ya completó el report de hoy
    report_existente = get_daily_report(user['id'], hoy)
    
    if report_existente and report_existente.get('completado'):
        st.success("✅ ¡Daily Report de hoy completado! Puedes continuar con tu trading.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Editar Report", use_container_width=True):
                report_existente['completado'] = False
        with col2:
            if st.button("💰 Ir a Trading", use_container_width=True, type="primary"):
                st.session_state.current_page = "trading"
                st.rerun()
    
    if not report_existente or not report_existente.get('completado'):
        st.markdown("""
        <div class="alert-warning">
            ⚠️ <strong>Check-in Matutino Obligatorio</strong><br>
            Completa este formulario antes de operar hoy. La autoconsciencia es clave para el éxito.
        </div>
        """, unsafe_allow_html=True)
        
        # Formulario Pre-Market
        st.markdown("### 🌅 Pre-Market Analysis")
        
        with st.form("daily_report_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                pre_market_score = st.slider(
                    "Calidad del análisis pre-market (1-10)",
                    min_value=1, max_value=10, value=5,
                    help="¿Qué tan bien preparado te sientes para hoy?"
                )
                
                estado_emocional = st.selectbox(
                    "Estado emocional actual",
                    ["Neutral", "Confiado", "Ansioso", "Miedo", "FOMO", 
                     "Frustrado", "Emocionado", "Cansado", "Enfocado"],
                    help="Sé honesto contigo mismo"
                )
                
                cumplio_sueno = st.radio(
                    "¿Dormiste al menos 7 horas?",
                    ["Sí", "No"],
                    horizontal=True
                )
            
            with col2:
                trades_planeados = st.number_input(
                    "Trades máximos planeados hoy",
                    min_value=0, max_value=20, value=3,
                    help="Sé realista con tu capacidad de atención"
                )
                
                riesgo_maximo = st.number_input(
                    "Riesgo máximo permitido hoy ($)",
                    min_value=0, max_value=10000, value=300,
                    step=50,
                    help="Máximo que estás dispuesto a perder hoy"
                )
                
                mercado_hoy = st.text_area(
                    "Análisis del mercado hoy",
                    placeholder="¿Qué ves en el mercado? ¿Algún catalyst importante?",
                    height=100
                )
            
            st.markdown("---")
            
            # Watchlist del día
            st.markdown("### ⭐ Watchlist de Hoy (Máximo 5 stocks)")
            
            watchlist_cols = st.columns(5)
            watchlist_items = []
            
            for i, col in enumerate(watchlist_cols):
                with col:
                    symbol = st.text_input(f"Stock {i+1}", key=f"watchlist_{i}", 
                                          placeholder="Ej: MARA")
                    setup = st.selectbox(f"Setup", 
                                        ["", "Morning Panic Dip", "VWAP Bounce", 
                                         "Opening Range Breakout", "First Red Day", "Otro"],
                                        key=f"setup_{i}")
                    if symbol:
                        watchlist_items.append({
                            'symbol': symbol.upper(),
                            'setup': setup
                        })
            
            st.markdown("---")
            
            # Reglas y compromisos
            st.markdown("### ✅ Reglas de Trading de Hoy")
            
            col_rules1, col_rules2 = st.columns(2)
            
            with col_rules1:
                regla_1 = st.checkbox("No operaré contra la tendencia principal", value=True)
                regla_2 = st.checkbox("Esperaré confirmación antes de entrar", value=True)
                regla_3 = st.checkbox("Usaré stop loss en TODOS mis trades", value=True)
            
            with col_rules2:
                regla_4 = st.checkbox("No haré revenge trading", value=True)
                regla_5 = st.checkbox("Respetaré mi límite de trades diarios", value=True)
                regla_6 = st.checkbox("Cerraré el día si pierdo más del riesgo máximo", value=True)
            
            st.markdown("---")
            
            # Botón de submit
            submitted = st.form_submit_button("✅ COMPLETAR CHECK-IN", use_container_width=True, type="primary")
            
            if submitted:
                # Guardar report
                create_or_update_daily_report(
                    user_id=user['id'],
                    fecha=hoy,
                    pre_market_score=pre_market_score,
                    estado_emocional=estado_emocional,
                    cumplio_sueno=(cumplio_sueno == "Sí"),
                    trades_planeados=trades_planeados,
                    riesgo_maximo_hoy=riesgo_maximo,
                    aprendizaje=mercado_hoy,
                    completado=True
                )
                
                # Añadir items a watchlist
                from database.db_manager import add_to_watchlist
                for item in watchlist_items:
                    add_to_watchlist(user['id'], item['symbol'], item['setup'])
                
                # Añadir XP
                add_xp_to_user(user['id'], 15)
                
                st.success("🎉 ¡Daily Report completado! +15 XP")
                st.balloons()
                
                # Mensaje motivacional según estado emocional
                mensajes = {
                    "Neutral": "Mantén la calma y sigue tu plan. La consistencia gana.",
                    "Confiado": "¡Buena energía! Asegúrate de no ser overconfident.",
                    "Ansioso": "Respira profundo. Solo opera setups A+. La paciencia es clave.",
                    "Miedo": "Si no te sientes bien, mejor no operes hoy. Protege tu capital.",
                    "FOMO": "Recuerda: siempre habrá otra oportunidad. No fuerces trades.",
                    "Frustrado": "Tómate un descanso. No operes con emociones negativas.",
                    "Emocionado": "Canaliza esa energía en disciplina, no en overtrading.",
                    "Cansado": "El descanso es parte del trading. Considera no operar hoy.",
                    "Enfocado": "¡Perfecto! Mantén esa concentración en cada trade."
                }
                
                st.info(f"💡 **Consejo del día:** {mensajes.get(estado_emocional, 'Sigue tu plan.')}")
                
                st.rerun()
    
    # Historial de Daily Reports
    st.markdown("---")
    st.markdown("### 📊 Historial de Daily Reports")
    
    from database.db_manager import get_daily_reports_stats
    reports = get_daily_reports_stats(user['id'], dias=30)
    
    if reports:
        import pandas as pd
        
        df_reports = pd.DataFrame(reports)
        df_reports['fecha'] = pd.to_datetime(df_reports['fecha'])
        df_reports = df_reports.sort_values('fecha', ascending=False)
        
        # Métricas de consistencia
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_reports = len(reports)
            st.metric("Total Reports", total_reports)
        
        with col2:
            avg_score = sum(r.get('pre_market_score', 0) for r in reports) / len(reports)
            st.metric("Score Promedio", f"{avg_score:.1f}/10")
        
        with col3:
            buen_sueno = sum(1 for r in reports if r.get('cumplio_sueno'))
            pct_sueno = (buen_sueno / len(reports)) * 100
            st.metric("Días con buen sueño", f"{pct_sueno:.0f}%")
        
        with col4:
            estados = [r.get('estado_emocional', 'Neutral') for r in reports]
            estado_comun = max(set(estados), key=estados.count)
            st.metric("Estado más común", estado_comun)
        
        # Tabla de reports recientes
        st.markdown("#### Últimos 7 días")
        
        recent = df_reports.head(7)[['fecha', 'pre_market_score', 'estado_emocional', 
                                      'cumplio_sueno', 'trades_planeados', 'completado']]
        
        # Formatear para mostrar
        recent_display = recent.copy()
        recent_display['fecha'] = recent_display['fecha'].dt.strftime('%Y-%m-%d')
        recent_display['cumplio_sueno'] = recent_display['cumplio_sueno'].apply(lambda x: '✅' if x else '❌')
        recent_display['completado'] = recent_display['completado'].apply(lambda x: '✅' if x else '❌')
        
        st.dataframe(recent_display, use_container_width=True, hide_index=True)
        
        # Gráfico de evolución emocional
        st.markdown("#### Evolución del Estado Emocional")
        
        # Mapear estados a valores numéricos
        estado_map = {
            'Miedo': 1, 'Frustrado': 2, 'Cansado': 3, 'Ansioso': 4,
            'FOMO': 5, 'Neutral': 6, 'Enfocado': 7, 'Confiado': 8, 'Emocionado': 9
        }
        
        df_reports['estado_num'] = df_reports['estado_emocional'].map(estado_map)
        
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_reports['fecha'],
            y=df_reports['estado_num'],
            mode='lines+markers',
            name='Estado Emocional',
            line=dict(color='#00D4FF', width=2),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=df_reports['fecha'],
            y=df_reports['pre_market_score'],
            mode='lines+markers',
            name='Pre-Market Score',
            line=dict(color='#00C805', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            plot_bgcolor='#141414',
            paper_bgcolor='#0A0A0A',
            font_color='white',
            xaxis_title='Fecha',
            yaxis_title='Nivel',
            height=400,
            yaxis=dict(
                tickmode='array',
                tickvals=list(estado_map.values()),
                ticktext=list(estado_map.keys())
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no tienes Daily Reports registrados. ¡Empieza hoy!")
    
    # Sección educativa
    with st.expander("📚 ¿Por qué es importante el Daily Report?"):
        st.markdown("""
        ### La importancia del registro diario
        
        Los traders profesionales como **Steven Dux**, **Kyle Williams** y **Alex Temiz** 
        atribuyen gran parte de su éxito al registro meticuloso de su estado mental y trades.
        
        **Beneficios del Daily Report Card:**
        
        1. **Autoconsciencia**: Reconocer tus patrones emocionales te permite anticipar errores
        2. **Disciplina**: El acto de registrar tus reglas aumenta el compromiso con ellas
        3. **Accountability**: Tener un registro objetivo evita el autoengaño
        4. **Mejora continua**: Revisar tu historial revela patrones de éxito y fracaso
        
        **Consejos:**
        - Sé 100% honesto contigo mismo
        - Completa el report ANTES de operar
        - Revisa tus reports semanalmente
        - Busca correlaciones entre tu estado y tus resultados
        
        > *"El trading es 80% psicología y 20% técnica"* - Mark Douglas
        """)