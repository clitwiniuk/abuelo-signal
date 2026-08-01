import streamlit as st
from database.db_manager import get_user_achievements
from utils.achievements import ALL_ACHIEVEMENTS, get_achievement_progress

def render_logros_page():
    """Renderizar página de logros"""
    st.markdown("<h1>🏆 Logros y Badges</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    logros_desbloqueados = get_user_achievements(user['id'])
    
    # Contadores
    total_logros = len(ALL_ACHIEVEMENTS)
    logros_obtenidos = len(logros_desbloqueados)
    porcentaje = (logros_obtenidos / total_logros) * 100
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">LOGROS OBTENIDOS</div>
            <div style="color: #00D4FF; font-size: 36px; font-weight: bold;">
                {logros_obtenidos}/{total_logros}
            </div>
            <div style="color: #666; font-size: 11px;">
                {porcentaje:.1f}% completado
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # XP total
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">XP TOTAL</div>
            <div style="color: #00C805; font-size: 36px; font-weight: bold;">
                {user['xp_total']:,}
            </div>
            <div style="color: #666; font-size: 11px;">
                Nivel {user['nivel_actual']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Racha actual
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 12px;">RACHA ACTUAL</div>
            <div style="color: #FFD700; font-size: 36px; font-weight: bold;">
                {user.get('racha_dias', 0)} 🔥
            </div>
            <div style="color: #666; font-size: 11px;">
                días seguidos
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Logros desbloqueados
    st.markdown("### 🎉 Logros Desbloqueados")
    
    if logros_desbloqueados:
        cols = st.columns(4)
        for i, logro in enumerate(logros_desbloqueados):
            with cols[i % 4]:
                badge_icon = logro.get('badge_icon', '🏆')
                badge_name = logro.get('badge_name', 'Unknown')
                fecha = logro.get('fecha_desbloqueo', '')[:10]
                
                # Determinar clase CSS según tipo de logro
                if 'Elite' in badge_name or 'Diamond' in badge_name:
                    badge_class = 'achievement-diamond'
                elif 'Gold' in badge_name or 'Master' in badge_name:
                    badge_class = 'achievement-gold'
                elif 'Silver' in badge_name or 'Pro' in badge_name:
                    badge_class = 'achievement-silver'
                else:
                    badge_class = 'achievement-bronze'
                
                st.markdown(f"""
                <div class="achievement-badge {badge_class}" style="width: 100%; text-align: center; margin: 5px 0;">
                    <div style="font-size: 24px; margin-bottom: 5px;">{badge_icon}</div>
                    <div style="font-size: 11px; font-weight: bold;">{badge_name}</div>
                    <div style="font-size: 9px; opacity: 0.8;">{fecha}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Aún no has desbloqueado ningún logro. ¡Empieza a operar para ganar badges!")
    
    st.markdown("---")
    
    # Logros pendientes
    st.markdown("### 🎯 Logros Pendientes")
    
    logros_obtenidos_nombres = [l['badge_name'] for l in logros_desbloqueados]
    logros_pendientes = {k: v for k, v in ALL_ACHIEVEMENTS.items() if k not in logros_obtenidos_nombres}
    
    # Categorías
    categorias = {}
    for nombre, info in logros_pendientes.items():
        cat = info.get('category', 'General')
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append((nombre, info))
    
    for categoria, logros in categorias.items():
        with st.expander(f"📂 {categoria} ({len(logros)} logros)", expanded=False):
            for nombre, info in logros:
                progress = get_achievement_progress(user['id'], nombre)
                progreso_pct = min(100, (progress['current'] / progress['required']) * 100)
                
                col_info, col_progress = st.columns([2, 1])
                
                with col_info:
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px; margin: 10px 0;">
                        <span style="font-size: 24px;">{info.get('icon', '🏆')}</span>
                        <div>
                            <div style="font-weight: bold;">{nombre}</div>
                            <div style="font-size: 12px; color: #666;">{info.get('description', '')}</div>
                            <div style="font-size: 11px; color: #FFD700;">
                                Dificultad: {info.get('difficulty', 'Media')}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_progress:
                    st.markdown(f"""
                    <div style="text-align: center;">
                        <div style="font-size: 11px; color: #666; margin-bottom: 5px;">
                            {progress['current']}/{progress['required']} {progress['unit']}
                        </div>
                        <div class="xp-progress-container" style="height: 8px; width: 100%;">
                            <div class="xp-progress-bar" style="width: {progreso_pct}%"></div>
                        </div>
                        <div style="font-size: 10px; color: #00D4FF; margin-top: 3px;">
                            {progreso_pct:.0f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
    
    # Tabla de XP por acción
    st.markdown("---")
    st.markdown("### 💎 Sistema de XP")
    
    xp_table = {
        'Acción': [
            'Trade ejecutado según plan',
            'Trade winner',
            'Trade con R:R > 1:3',
            'Completar Daily Report Card',
            'Racha 7 días de Daily Reports',
            'Backtest 20 setups históricos',
            'Encontrar edge >60% en backtest',
            'Semana sin violar reglas de riesgo',
            'Racha 4 semanas sin violar reglas',
            'Identificar setup correctamente',
            'Ejecutar setup perfectamente',
            'Evitar overtrading',
            'Trade fuera de plan',
            'Trade con pérdida >2R'
        ],
        'XP Base': [
            '+10', '+5', '+10', '+15', '+50', '+30', '+100', '+50', '+200', '+5', '+15', '+20', '-20', '-40'
        ],
        'Descripción': [
            'Base por seguir tu plan',
            'Bonus por trade ganador',
            'Bonus por buen R:R',
            'Base por completar report',
            'Bonus por consistencia',
            'Base por backtesting',
            'Bonus por encontrar edge',
            'Base por disciplina',
            'Bonus por consistencia extrema',
            'Base por análisis correcto',
            'Bonus por ejecución perfecta',
            'Base por respetar límites',
            'Penalización por desviación',
            'Doble penalización por riesgo excesivo'
        ]
    }
    
    import pandas as pd
    df_xp = pd.DataFrame(xp_table)
    
    st.dataframe(df_xp, use_container_width=True, hide_index=True)
    
    # Consejos para ganar XP
    st.markdown("""
    <div style="background-color: #141414; padding: 20px; border-radius: 12px; margin-top: 20px;">
        <div style="color: #FFD700; font-weight: bold; font-size: 16px; margin-bottom: 15px;">
            💡 Estrategia para Subir de Nivel Rápidamente
        </div>
        <div style="color: #B0B0B0; font-size: 14px;">
            <ol style="padding-left: 20px; line-height: 1.8;">
                <li><strong>Completa tu Daily Report todos los días</strong> - 15 XP + bonus de racha</li>
                <li><strong>Sigue tu plan al 100%</strong> - 10 XP base + 5 XP bonus</li>
                <li><strong>Busca trades con R:R de al menos 2:1</strong> - Bonus de 10 XP</li>
                <li><strong>Practica backtesting regularmente</strong> - 30-100 XP por sesión</li>
                <li><strong>Mantén disciplina de riesgo</strong> - 50-200 XP semanal</li>
                <li><strong>Evita overtrading</strong> - 20 XP por día de control</li>
            </ol>
        </div>
        <div style="color: #00D4FF; font-size: 13px; margin-top: 15px; font-style: italic;">
            "La consistencia es más importante que la perfección. Pequeñas acciones diarias 
            llevan a grandes resultados."
        </div>
    </div>
    """, unsafe_allow_html=True)