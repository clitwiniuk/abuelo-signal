import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

from database.db_manager import get_trades_by_user, get_trading_stats, get_consecutive_stats
from utils.calculations import calculate_max_drawdown

def render_estadisticas_page():
    """Renderizar página de estadísticas"""
    st.markdown("<h1>📈 Estadísticas de Trading</h1>", unsafe_allow_html=True)
    
    user = st.session_state.user
    
    # Selector de período
    col_period, col_empty = st.columns([1, 3])
    with col_period:
        periodo = st.selectbox(
            "Período",
            ["Últimos 7 días", "Últimos 30 días", "Últimos 90 días", "Todo el tiempo"],
            index=1
        )
    
    # Mapear período a días
    dias_map = {
        "Últimos 7 días": 7,
        "Últimos 30 días": 30,
        "Últimos 90 días": 90,
        "Todo el tiempo": 3650
    }
    dias = dias_map[periodo]
    
    # Obtener estadísticas
    stats = get_trading_stats(user['id'], dias=dias)
    trades = get_trades_by_user(user['id'], fecha_desde=(date.today() - timedelta(days=dias)).isoformat())
    
    if not trades:
        st.info("No tienes trades registrados en este período. ¡Empieza a operar para ver tus estadísticas!")
        return
    
    # Métricas principales (estilo Steven Dux)
    st.markdown("### 📊 Métricas Principales")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        win_rate = stats.get('win_rate', 0)
        color = "#00C805" if win_rate >= 50 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 11px;">WIN RATE</div>
            <div style="color: {color}; font-size: 32px; font-weight: bold;">
                {win_rate:.1f}%
            </div>
            <div style="color: #666; font-size: 10px;">
                {stats.get('trades_ganados', 0)}W / {stats.get('trades_perdidos', 0)}L
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        pf = stats.get('profit_factor', 0)
        color = "#00C805" if pf >= 1.2 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 11px;">PROFIT FACTOR</div>
            <div style="color: {color}; font-size: 32px; font-weight: bold;">
                {pf:.2f}
            </div>
            <div style="color: #666; font-size: 10px;">
                GP: ${stats.get('gross_profit', 0):.0f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        ev = stats.get('expected_value', 0)
        color = "#00C805" if ev > 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 11px;">EXPECTED VALUE</div>
            <div style="color: {color}; font-size: 32px; font-weight: bold;">
                ${ev:.2f}
            </div>
            <div style="color: #666; font-size: 10px;">
                por trade
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        r_mult = stats.get('avg_r_multiple', 0) or 0
        color = "#00C805" if r_mult > 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 11px;">AVG R-MULTIPLE</div>
            <div style="color: {color}; font-size: 32px; font-weight: bold;">
                {r_mult:.2f}R
            </div>
            <div style="color: #666; font-size: 10px;">
                Objetivo: 2R+
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        total_pnl = stats.get('total_pnl', 0)
        color = "#00C805" if total_pnl > 0 else "#FF5000"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #B0B0B0; font-size: 11px;">P&L TOTAL</div>
            <div style="color: {color}; font-size: 32px; font-weight: bold;">
                ${total_pnl:,.2f}
            </div>
            <div style="color: #666; font-size: 10px;">
                {stats.get('total_trades', 0)} trades
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Métricas secundarias
    st.markdown("### 📈 Métricas Detalladas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_winner = stats.get('avg_winner', 0) or 0
        avg_loser = stats.get('avg_loser', 0) or 0
        st.markdown(f"""
        <div class="trading-card" style="text-align: center;">
            <div style="color: #B0B0B0; font-size: 12px; margin-bottom: 10px;">PROMEDIOS</div>
            <div style="color: #00C805; font-size: 20px; font-weight: bold;">
                +${avg_winner:.2f}
            </div>
            <div style="color: #666; font-size: 10px;">Avg Winner</div>
            <div style="color: #FF5000; font-size: 20px; font-weight: bold; margin-top: 10px;">
                ${avg_loser:.2f}
            </div>
            <div style="color: #666; font-size: 10px;">Avg Loser</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        consecutive = get_consecutive_stats(user['id'])
        st.markdown(f"""
        <div class="trading-card" style="text-align: center;">
            <div style="color: #B0B0B0; font-size: 12px; margin-bottom: 10px;">RACHAS</div>
            <div style="color: #00C805; font-size: 24px; font-weight: bold;">
                {consecutive['max_consecutive_wins']}
            </div>
            <div style="color: #666; font-size: 10px;">Max Wins</div>
            <div style="color: #FF5000; font-size: 24px; font-weight: bold; margin-top: 10px;">
                {consecutive['max_consecutive_losses']}
            </div>
            <div style="color: #666; font-size: 10px;">Max Losses</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        trades_plan = stats.get('trades_plan_cumplido', 0)
        total_trades = stats.get('total_trades', 0)
        plan_pct = (trades_plan / total_trades * 100) if total_trades > 0 else 0
        st.markdown(f"""
        <div class="trading-card" style="text-align: center;">
            <div style="color: #B0B0B0; font-size: 12px; margin-bottom: 10px;">DISCIPLINA</div>
            <div style="color: #00D4FF; font-size: 28px; font-weight: bold;">
                {plan_pct:.1f}%
            </div>
            <div style="color: #666; font-size: 10px;">Trades según plan</div>
            <div style="color: #666; font-size: 12px; margin-top: 10px;">
                {trades_plan}/{total_trades}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Calcular max drawdown
        if trades:
            df_trades = pd.DataFrame(trades)
            df_trades = df_trades.sort_values('fecha_entrada')
            df_trades['equity'] = user['capital_inicial_nivel'] + df_trades['pnl'].cumsum()
            max_dd = calculate_max_drawdown(df_trades['equity'])
        else:
            max_dd = 0
        
        color = "#00C805" if max_dd < 10 else "#FF5000"
        st.markdown(f"""
        <div class="trading-card" style="text-align: center;">
            <div style="color: #B0B0B0; font-size: 12px; margin-bottom: 10px;">MAX DRAWDOWN</div>
            <div style="color: {color}; font-size: 28px; font-weight: bold;">
                {max_dd:.1f}%
            </div>
            <div style="color: #666; font-size: 10px;">Máximo retroceso</div>
            <div style="color: #666; font-size: 12px; margin-top: 10px;">
                Objetivo: &lt;10%
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gráficos
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 📊 Equity Curve")
        
        if trades:
            df_trades = pd.DataFrame(trades)
            df_trades['fecha_entrada'] = pd.to_datetime(df_trades['fecha_entrada'])
            df_trades = df_trades.sort_values('fecha_entrada')
            df_trades['equity'] = user['capital_inicial_nivel'] + df_trades['pnl'].cumsum()
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_trades['fecha_entrada'],
                y=df_trades['equity'],
                mode='lines',
                name='Equity',
                line=dict(color='#00C805', width=2),
                fill='tonexty',
                fillcolor='rgba(0, 200, 5, 0.1)'
            ))
            
            fig.add_hline(y=user['capital_inicial_nivel'], line_dash="dash", 
                         line_color="#666", annotation_text="Inicial")
            
            # Marcar drawdowns
            running_max = df_trades['equity'].cummax()
            drawdown = (df_trades['equity'] - running_max) / running_max
            max_dd_idx = drawdown.idxmin()
            
            fig.add_trace(go.Scatter(
                x=[df_trades.loc[max_dd_idx, 'fecha_entrada']],
                y=[df_trades.loc[max_dd_idx, 'equity']],
                mode='markers',
                name='Max Drawdown',
                marker=dict(color='#FF5000', size=12, symbol='x')
            ))
            
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
    
    with col_right:
        st.markdown("### 📈 Distribución de P&L")
        
        if trades:
            pnls = [t.get('pnl', 0) for t in trades if t.get('pnl') is not None]
            
            fig = go.Figure()
            
            fig.add_trace(go.Histogram(
                x=pnls,
                nbinsx=20,
                marker_color=['#00C805' if p > 0 else '#FF5000' for p in pnls],
                opacity=0.8
            ))
            
            fig.add_vline(x=0, line_dash="dash", line_color="white")
            
            fig.update_layout(
                plot_bgcolor='#141414',
                paper_bgcolor='#0A0A0A',
                font_color='white',
                xaxis_title='P&L ($)',
                yaxis_title='Frecuencia',
                height=400,
                showlegend=False,
                bargap=0.1
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Análisis por Setup
    st.markdown("### 🎯 Análisis por Setup")
    
    if trades:
        df_trades = pd.DataFrame(trades)
        
        if 'setup' in df_trades.columns:
            setup_stats = df_trades.groupby('setup').agg({
                'pnl': ['count', lambda x: (x > 0).sum(), 'mean', 'sum']
            }).reset_index()
            
            setup_stats.columns = ['Setup', 'Total', 'Ganados', 'Avg P&L', 'Total P&L']
            setup_stats['Win Rate'] = (setup_stats['Ganados'] / setup_stats['Total'] * 100).round(1)
            setup_stats = setup_stats.sort_values('Total P&L', ascending=False)
            
            # Mostrar como barras
            fig = go.Figure()
            
            colors = ['#00C805' if x > 0 else '#FF5000' for x in setup_stats['Total P&L']]
            
            fig.add_trace(go.Bar(
                x=setup_stats['Setup'],
                y=setup_stats['Total P&L'],
                marker_color=colors,
                text=setup_stats['Win Rate'].apply(lambda x: f'{x:.0f}% WR'),
                textposition='auto'
            ))
            
            fig.update_layout(
                plot_bgcolor='#141414',
                paper_bgcolor='#0A0A0A',
                font_color='white',
                xaxis_title='Setup',
                yaxis_title='P&L Total ($)',
                height=350,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabla detallada
            st.dataframe(
                setup_stats[['Setup', 'Total', 'Win Rate', 'Avg P&L', 'Total P&L']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'Win Rate': st.column_config.ProgressColumn(
                        'Win Rate',
                        help='Porcentaje de trades ganadores',
                        format='%.1f%%',
                        min_value=0,
                        max_value=100
                    ),
                    'Avg P&L': st.column_config.NumberColumn(
                        'Avg P&L',
                        help='P&L promedio por trade',
                        format='$%.2f'
                    ),
                    'Total P&L': st.column_config.NumberColumn(
                        'Total P&L',
                        help='P&L total del setup',
                        format='$%.2f'
                    )
                }
            )
    
    st.markdown("---")
    
    # Tabla de trades detallada
    st.markdown("### 📋 Historial de Trades")
    
    if trades:
        df_display = pd.DataFrame(trades)
        
        # Formatear columnas
        if 'fecha_entrada' in df_display.columns:
            df_display['fecha'] = pd.to_datetime(df_display['fecha_entrada']).dt.strftime('%Y-%m-%d')
        
        columnas_mostrar = ['fecha', 'simbolo', 'setup', 'entrada', 'salida', 'size', 'pnl', 'r_multiple', 'cumplio_plan']
        columnas_existentes = [c for c in columnas_mostrar if c in df_display.columns]
        
        df_final = df_display[columnas_existentes].copy()
        
        # Formatear P&L
        if 'pnl' in df_final.columns:
            df_final['pnl'] = df_final['pnl'].apply(lambda x: f"${x:.2f}" if x is not None else "ABIERTO")
        
        # Formatear R-Multiple
        if 'r_multiple' in df_final.columns:
            df_final['r_multiple'] = df_final['r_multiple'].apply(lambda x: f"{x:.2f}R" if x is not None else "-")
        
        # Formatear cumplio_plan
        if 'cumplio_plan' in df_final.columns:
            df_final['cumplio_plan'] = df_final['cumplio_plan'].apply(lambda x: '✅' if x else '❌')
        
        st.dataframe(df_final, use_container_width=True, hide_index=True)
    
    # Exportar reporte
    st.markdown("---")
    col_export, col_empty = st.columns([1, 3])
    with col_export:
        if st.button("📥 Exportar Reporte PDF", use_container_width=True):
            st.info("Función de exportación en desarrollo. Próximamente disponible.")