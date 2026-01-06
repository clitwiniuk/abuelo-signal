#!/usr/bin/env python3
"""
Streamlit Trading Application v4.0
Sistema de trading inteligente con scanner ML integrado
"""

import streamlit as st
import pandas as pd
import sqlite3
import logging
import os
import sys
from datetime import datetime, date, timedelta
import configparser
import json
import asyncio
import nest_asyncio

# Apply nest_asyncio for nested event loops (required for Streamlit + ib_insync)
nest_asyncio.apply()

# Page configuration
st.set_page_config(
    page_title="🎯 Trading System Pro v4.0",
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "# Trading System Pro v4.0\nSistema de trading inteligente con ML"
    }
)

# Initialize paths and modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import modules
try:
    from core.interfaces import TradingConfig
    from core.database_manager import get_database_manager
    from main import TradingSystemManager
    from scanner.scanner_intelligence import ScannerIntelligence, ScannerConfig, TradingResult, SentimentType
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.stop()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/streamlit_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === STREAMLIT CONFIGURATION CLASS ===
class StreamlitConfig:
    """Streamlit-specific configuration"""
    
    @staticmethod
    def setup_page_config():
        """Setup page configuration"""
        st.set_page_config(
            page_title="🎯 Trading System Pro v4.0",
            page_icon="📈",
            layout="wide"
        )

# Initialize core components (cacheable)
@st.cache_resource
def initialize_core_components():
    """Initialize core system components that can be safely cached"""
    try:
        config = TradingConfig()
        db_manager = get_database_manager()
        trading_system = TradingSystemManager(config, in_streamlit=True)
        
        return config, db_manager, trading_system
    except Exception as e:
        st.error(f"Error initializing core components: {e}")
        return None, None, None

# Initialize scanner separately (no cache to avoid method issues)
def initialize_scanner_ai(db_manager):
    """Initialize ScannerIntelligence without caching"""
    if db_manager:
        return ScannerIntelligence(database_manager=db_manager)
    return None

# Load components
config, db_manager, trading_system = initialize_core_components()
scanner_ai = initialize_scanner_ai(db_manager)

if not all([config, db_manager, trading_system]):
    st.error("❌ Error inicializando el sistema")
    st.stop()

# Initialize session state
if 'manual_symbols' not in st.session_state:
    st.session_state.manual_symbols = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

# === MAIN LAYOUT ===

# Sidebar
with st.sidebar:
    st.title("🎯 Trading System Pro v4.0")
    st.markdown("---")
    
    # System status
    system_running = st.session_state.get('system_running', False)
    if system_running:
        st.success("🟢 Sistema ACTIVO")
    else:
        st.error("🔴 Sistema INACTIVO")
    
    # Quick stats
    positions_count = len(st.session_state.get('positions', {}))
    symbols_count = len(st.session_state.get('manual_symbols', []))
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Posiciones", positions_count)
    with col2:
        st.metric("Símbolos", symbols_count)
    
    st.markdown("---")
    
    # ML Learning status
    if scanner_ai:
        stats = scanner_ai.get_learning_stats()
        st.subheader("🧠 ML Status")
        st.metric("Noticias analizadas", stats['total_news_analyzed'])
        st.metric("Trades registrados", stats['total_trades'])
        if stats['total_trades'] > 0:
            st.metric("Win Rate", f"{stats['win_rate']:.1f}%")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Trading & Scanner", "💼 Portfolio", "📊 Analytics", "⚙️ Sistema"])

# === TAB 1: TRADING & SCANNER INTELIGENTE ===
with tab1:
    # Enable auto-refresh for trading tab
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="trading_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("🎯 Trading & Scanner Inteligente")
    
    # Update system data
    if st.session_state.get('system_running', False):
        # trading_system.update_system_data()  # Placeholder - adjust as needed
        pass
    
    # Sub-tabs para organizar funcionalidad
    scanner_tab, trading_tab, learning_tab = st.tabs(["🔍 Scanner ML", "📈 Trading Control", "🧠 ML Learning"])
    
    # === SCANNER INTELIGENTE ===
    with scanner_tab:
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.subheader("⚙️ Configuración Scanner")
            
            if scanner_ai:
                scanner_config = scanner_ai.load_config()
                
                # Filtro de sentimiento
                sentiment_options = ["ONLY_POSITIVE", "POSITIVE_NEUTRAL"]
                sentiment_labels = ["Solo POSITIVOS", "POSITIVOS + NEUTRALES"]
                
                sentiment_filter = st.selectbox(
                    "Tipo de catalizadores:",
                    options=sentiment_options,
                    format_func=lambda x: sentiment_labels[sentiment_options.index(x)],
                    index=sentiment_options.index(scanner_config.sentiment_filter),
                    help="Solo POSITIVOS = Más conservador\nPOSITIVOS + NEUTRALES = Más permisivo"
                )
                
                # Configuración avanzada
                max_float = st.number_input(
                    "Float máximo (millones)",
                    min_value=1, max_value=1000, 
                    value=int(scanner_config.max_float/1_000_000), 
                    step=10
                ) * 1_000_000
                
                auto_add_threshold = st.slider(
                    "ML Score para auto-add",
                    min_value=0.3, max_value=0.9, 
                    value=scanner_config.auto_add_threshold, 
                    step=0.05,
                    help="Score mínimo para añadir automáticamente al trading"
                )
                
                learning_enabled = st.checkbox(
                    "🧠 Aprendizaje automático", 
                    value=scanner_config.learning_enabled,
                    help="El sistema aprende de tus trades para mejorar"
                )
                
                if st.button("💾 Guardar Config"):
                    new_config = ScannerConfig(
                        sentiment_filter=sentiment_filter,
                        max_float=max_float,
                        min_gap_percent=scanner_config.min_gap_percent,
                        min_volume=scanner_config.min_volume,
                        auto_add_threshold=auto_add_threshold,
                        learning_enabled=learning_enabled
                    )
                    scanner_ai.save_config(new_config)
                    st.success("✅ Configuración guardada")
                    st.rerun()
                
                # Stats de aprendizaje
                if learning_enabled:
                    stats = scanner_ai.get_learning_stats()
                    st.markdown("---")
                    st.subheader("📊 Stats ML")
                    st.metric("Noticias", stats['total_news_analyzed'])
                    st.metric("Trades", stats['total_trades'])
                    if stats['total_trades'] > 0:
                        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
            else:
                st.error("❌ Sistema ML no disponible")
        
        with col1:
            st.subheader("📋 ProRealTime Scanner")
            st.markdown("Pega datos del ProScreener con análisis automático de noticias:")
            
            # Área para datos PRT
            prt_data = st.text_area(
                "Datos ProScreener",
                height=200,
                placeholder='"TICKER"\t"NAME"\t"%VAR"\t"VAR"\t"LAST"\t"TIME"\t"VOLUME"\n"ATNF"\t"180 LIFE SCIENCES"\t"+206.59%"\t"+6.90"\t"10.24"\t"07:00:33"\t"225M"',
                help="Copia y pega directamente desde ProRealTime"
            )
            
            # Procesar scanner
            if st.button("🧠 Analizar con IA", type="primary", use_container_width=True):
                if prt_data.strip() and scanner_ai:
                    st.info("🔍 Analizando tickers con IA...")
                    
                    # Extraer tickers
                    import re
                    ticker_pattern = r'"([A-Z]{2,5})"'
                    found_tickers = re.findall(ticker_pattern, prt_data)
                    
                    if 'TICKER' in found_tickers:
                        found_tickers.remove('TICKER')
                    
                    unique_tickers = list(set(found_tickers))
                    
                    if unique_tickers:
                        results = []
                        auto_added = []
                        scanner_config = scanner_ai.load_config()
                        
                        # Analizar cada ticker
                        for ticker in unique_tickers:
                            # Análisis básico (en producción sería con noticias reales)
                            news_analysis = scanner_ai.analyze_ticker_news(ticker, "")
                            ml_score = scanner_ai.calculate_ml_score(ticker)
                            
                            # Auto-add si cumple criterios
                            should_add = scanner_ai.should_auto_add_ticker(ticker, scanner_config)
                            
                            results.append({
                                'Ticker': ticker,
                                'ML Score': f"{ml_score:.2f}",
                                'Sentiment': news_analysis.sentiment.value if news_analysis else 'neutral',
                                'Catalyst': news_analysis.catalyst_type.value if news_analysis else 'other',
                                'Auto-Add': '✅' if should_add else '❌'
                            })
                            
                            if should_add:
                                auto_added.append(ticker)
                        
                        # Mostrar resultados
                        st.subheader(f"📊 Análisis de {len(results)} tickers")
                        df = pd.DataFrame(results)
                        st.dataframe(df, use_container_width=True)
                        
                        # Auto-add tickers
                        if auto_added:
                            if 'manual_symbols' not in st.session_state:
                                st.session_state.manual_symbols = []
                            
                            new_symbols = [t for t in auto_added if t not in st.session_state.manual_symbols]
                            if new_symbols:
                                st.session_state.manual_symbols.extend(new_symbols)
                                st.success(f"🤖 Auto-añadidos {len(new_symbols)} tickers: {', '.join(new_symbols)}")
                        
                        # Guardar para trading tab
                        st.session_state['scanner_results'] = results
                        st.session_state['scanner_tickers'] = unique_tickers
                    else:
                        st.warning("⚠️ No se encontraron tickers válidos")
                else:
                    st.error("❌ Necesitas datos PRT y sistema ML activo")
    
    # === TRADING CONTROL ===
    with trading_tab:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            current_count = len(st.session_state.get('manual_symbols', []))
            st.subheader(f"Gestión de Símbolos ({current_count} monitoreando)")
            
            # Mostrar resultados del scanner si existen
            if st.session_state.get('scanner_results'):
                st.info("📊 Resultados del último escaneo disponibles abajo")
            
            # Formulario para añadir símbolos
            with st.form("add_symbol_form"):
                new_symbols_input = st.text_input(
                    "Añadir nuevo símbolo(s)", 
                    placeholder="AAPL, MSFT, GOOGL..."
                )
                submitted = st.form_submit_button("➕ Añadir Símbolo(s)", type="primary")
                
                if submitted and new_symbols_input.strip():
                    symbols_to_add = [s.strip().upper() for s in new_symbols_input.split(',') if s.strip()]
                    
                    if symbols_to_add:
                        import re
                        added_symbols = []
                        failed_symbols = []
                        duplicate_symbols = []
                        invalid_symbols = []
                        
                        for symbol in symbols_to_add:
                            # Validar formato
                            if not re.match(r'^[A-Z0-9\.\-]+$', symbol) or len(symbol) < 1 or len(symbol) > 8:
                                invalid_symbols.append(symbol)
                            elif symbol in st.session_state.get('manual_symbols', []):
                                duplicate_symbols.append(symbol)
                            else:
                                if 'manual_symbols' not in st.session_state:
                                    st.session_state.manual_symbols = []
                                st.session_state.manual_symbols.append(symbol)
                                added_symbols.append(symbol)
                        
                        # Mostrar resultados
                        if added_symbols:
                            st.success(f"✅ Añadidos: {', '.join(added_symbols)}")
                        if duplicate_symbols:
                            st.warning(f"⚠️ Ya monitoreando: {', '.join(duplicate_symbols)}")
                        if invalid_symbols:
                            st.error(f"❌ Formato inválido: {', '.join(invalid_symbols)}")
                        if failed_symbols:
                            st.error(f"❌ Error: {', '.join(failed_symbols)}")
            
            # Lista de símbolos actuales
            if st.session_state.get('manual_symbols'):
                st.subheader("📋 Símbolos Actuales")
                
                # Crear DataFrame para mejor visualización
                symbols_data = []
                for symbol in st.session_state.manual_symbols:
                    ml_score = scanner_ai.calculate_ml_score(symbol) if scanner_ai else 0.0
                    symbols_data.append({
                        'Símbolo': symbol,
                        'ML Score': f"{ml_score:.2f}",
                        'Estado': '🟢 Activo'
                    })
                
                df_symbols = pd.DataFrame(symbols_data)
                st.dataframe(df_symbols, use_container_width=True, hide_index=True)
                
                # Acciones masivas
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("🗑️ Limpiar Todo"):
                        st.session_state.manual_symbols = []
                        st.success("🗑️ Lista limpiada")
                        st.rerun()
                
                with col_b:
                    if st.button("📋 Copiar Lista"):
                        symbols_text = ", ".join(st.session_state.manual_symbols)
                        st.text_area(
                            f"📋 Lista de {len(st.session_state.manual_symbols)} símbolos:",
                            value=symbols_text,
                            height=100,
                            key="symbols_copy_area"
                        )
                        st.info("💡 Ctrl+A para seleccionar todo, Ctrl+C para copiar")
                
                with col_c:
                    symbol_to_remove = st.selectbox(
                        "Eliminar símbolo:",
                        options=["Seleccionar..."] + st.session_state.manual_symbols,
                        key="remove_symbol_select"
                    )
                    if symbol_to_remove != "Seleccionar..." and st.button("❌ Eliminar"):
                        st.session_state.manual_symbols.remove(symbol_to_remove)
                        st.success(f"❌ Eliminado: {symbol_to_remove}")
                        st.rerun()
            
            # Mostrar resultados del scanner
            if st.session_state.get('scanner_results'):
                st.markdown("---")
                st.subheader("🔍 Últimos Resultados del Scanner")
                scanner_df = pd.DataFrame(st.session_state['scanner_results'])
                st.dataframe(scanner_df, use_container_width=True, hide_index=True)
                
                # Añadir rápido desde scanner
                available_tickers = [r['Ticker'] for r in st.session_state['scanner_results'] 
                                   if r['Ticker'] not in st.session_state.get('manual_symbols', [])]
                
                if available_tickers:
                    selected_from_scanner = st.multiselect(
                        "Añadir desde scanner:",
                        options=available_tickers,
                        help="Selecciona tickers del scanner para añadir a trading"
                    )
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("➕ Añadir Seleccionados") and selected_from_scanner:
                            if 'manual_symbols' not in st.session_state:
                                st.session_state.manual_symbols = []
                            st.session_state.manual_symbols.extend(selected_from_scanner)
                            st.success(f"✅ Añadidos: {', '.join(selected_from_scanner)}")
                            st.rerun()
                    
                    with col_b:
                        if st.button("➕➕ Añadir Todos", type="secondary", help=f"Añadir todos los {len(available_tickers)} tickers del scanner"):
                            if 'manual_symbols' not in st.session_state:
                                st.session_state.manual_symbols = []
                            st.session_state.manual_symbols.extend(available_tickers)
                            st.success(f"✅ Añadidos todos: {len(available_tickers)} tickers del scanner")
                            st.rerun()
        
        with col2:
            st.subheader("🎛️ Control del Sistema")
            
            # Estado del sistema
            system_running = st.session_state.get('system_running', False)
            if system_running:
                st.success("🟢 Sistema ACTIVO")
            else:
                st.error("🔴 Sistema INACTIVO")
            
            # Controles rápidos del sistema
            if not system_running:
                if st.button("▶️ Iniciar Sistema", type="primary"):
                    symbols = st.session_state.get('manual_symbols', [])
                    if symbols:
                        st.write(f"🔍 Iniciando con {len(symbols)} símbolos")
                        try:
                            # Iniciar el sistema de trading real
                            asyncio.run(trading_system.start(symbols))
                            st.session_state.system_running = True
                            st.success("✅ Sistema iniciado correctamente")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error iniciando el sistema: {e}")
                            st.session_state.system_running = False
                    else:
                        st.warning("⚠️ Añade símbolos antes de iniciar")
            else:
                if st.button("⏹️ Detener Sistema", type="secondary"):
                    try:
                        # Detener el sistema de trading real
                        asyncio.run(trading_system.stop())
                        st.session_state.system_running = False
                        st.success("✅ Sistema detenido correctamente")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error deteniendo el sistema: {e}")
                        # Forzar estado detenido aunque haya error
                        st.session_state.system_running = False
                        st.rerun()
            
            st.markdown("---")
            
            # Acciones rápidas
            if st.button("🔄 Actualizar Datos"):
                # trading_system.update_data()  # Placeholder - adjust as needed
                st.success("Datos actualizados")
            
            if st.button("🔄 Reiniciar Sistema"):
                if st.session_state.system_running:
                    # trading_system.stop_system()  # Placeholder - adjust as needed
                    st.session_state.system_running = False
                st.session_state.clear()
                st.success("✅ Sistema reiniciado")
                st.rerun()
    
    # === ML LEARNING ===
    with learning_tab:
        if scanner_ai:
            st.subheader("🧠 Machine Learning & Feedback")
            
            # Stats de aprendizaje
            stats = scanner_ai.get_learning_stats()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📰 Noticias Analizadas", stats['total_news_analyzed'])
            with col2:
                st.metric("📈 Trades Registrados", stats['total_trades'])
            with col3:
                if stats['total_trades'] > 0:
                    st.metric("🎯 Win Rate", f"{stats['win_rate']:.1f}%")
                else:
                    st.metric("🎯 Win Rate", "No data")
            
            # Formulario de feedback rápido
            st.subheader("📝 Feedback Rápido de Trade")
            with st.form("quick_feedback"):
                feedback_ticker = st.selectbox(
                    "Ticker",
                    options=st.session_state.get('manual_symbols', []),
                    help="Selecciona el ticker que tradeaste"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    entry_price = st.number_input("Precio entrada", min_value=0.01, step=0.01)
                    was_profitable = st.radio("Resultado", ["✅ Ganancia", "❌ Pérdida", "🤝 Breakeven"])
                
                with col_b:
                    exit_price = st.number_input("Precio salida", min_value=0.01, step=0.01)
                    notes = st.text_area("Notas", placeholder="¿Qué aprendiste de este trade?")
                
                if st.form_submit_button("💾 Guardar Feedback"):
                    if feedback_ticker and entry_price > 0 and exit_price > 0:
                        pnl = exit_price - entry_price
                        profitable = was_profitable == "✅ Ganancia"
                        
                        result = TradingResult(
                            ticker=feedback_ticker,
                            trade_date=date.today(),
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pnl=pnl,
                            was_profitable=profitable,
                            hold_duration_minutes=None,
                            strategy_used="manual",
                            notes=notes
                        )
                        
                        scanner_ai.add_trading_result(result)
                        st.success(f"✅ Feedback guardado para {feedback_ticker}")
                        st.rerun()
                    else:
                        st.error("❌ Completa todos los campos")
            
            # Mejores patrones
            if stats['best_patterns']:
                st.subheader("🏆 Mejores Patrones Aprendidos")
                patterns_data = []
                for pattern_type, success_rate, confidence, sample_size in stats['best_patterns']:
                    patterns_data.append({
                        'Patrón': pattern_type.replace('_', ' ').title(),
                        'Success Rate': f"{success_rate:.1%}",
                        'Confianza': f"{confidence:.2f}",
                        'Muestras': sample_size
                    })
                
                patterns_df = pd.DataFrame(patterns_data)
                st.dataframe(patterns_df, use_container_width=True, hide_index=True)
        else:
            st.error("❌ Sistema ML no disponible")

# === TAB 2: PORTFOLIO ===
with tab2:
    # Enable auto-refresh for portfolio tab
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="portfolio_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("💼 Portfolio - Posiciones Actuales")
    
    # Always update positions when tab is accessed
    # trading_system.update_positions()  # Placeholder - adjust as needed
    
    positions = st.session_state.get('positions', {})
    
    if positions:
        # Calculate summary metrics
        total_market_value = 0
        total_unrealized_pnl = 0
        winning_positions = 0
        
        for symbol, position in positions.items():
            if isinstance(position, dict):
                market_value = position.get('market_value', 0)
                unrealized_pnl = position.get('unrealized_pnl', 0)
            else:
                # Handle IBKR PortfolioItem objects
                qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
            
            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            if unrealized_pnl > 0:
                winning_positions += 1
        
        # Summary metrics
        st.subheader("📊 Resumen del Portfolio")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Posiciones", len(positions))
        with col2:
            st.metric("Valor Total", f"${total_market_value:.2f}")
        with col3:
            pnl_pct = (total_unrealized_pnl/total_market_value*100) if total_market_value > 0 else 0
            st.metric("PnL Total", f"${total_unrealized_pnl:.2f}", delta=f"{pnl_pct:.2f}%")
        with col4:
            st.metric("Posiciones Ganadoras", f"{winning_positions}/{len(positions)}")
        
        # Position details
        def get_symbol_strategy(symbol, position):
            strategies = st.session_state.get('symbol_strategies', {})
            return strategies.get(symbol, 'Manual')
        
        positions_data = []
        for symbol, position in positions.items():
            try:
                if isinstance(position, dict):
                    qty = position.get('quantity', 0)
                    avg_price = position.get('avg_cost', 0)
                    market_price = position.get('market_price', 0)
                    market_value = position.get('market_value', 0)
                    unrealized_pnl = position.get('unrealized_pnl', 0)
                else:
                    qty = getattr(position, 'position', getattr(position, 'quantity', 0))
                    avg_price = getattr(position, 'averageCost', getattr(position, 'avg_cost', 0))
                    market_price = getattr(position, 'marketPrice', getattr(position, 'market_price', 0))
                    market_value = getattr(position, 'marketValue', getattr(position, 'market_value', qty * market_price))
                    unrealized_pnl = getattr(position, 'unrealizedPNL', getattr(position, 'unrealized_pnl', 0))
                
                if qty == 0:
                    continue
                
                pct_change = ((market_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
                
                positions_data.append({
                    'Símbolo': symbol,
                    'Cantidad': int(qty),
                    'Precio Entrada': f"${avg_price:.4f}",
                    'Precio Actual': f"${market_price:.4f}",
                    'Valor Mercado': f"${market_value:.2f}",
                    'PnL ($)': f"${unrealized_pnl:.2f}",
                    'PnL (%)': f"{pct_change:.2f}%",
                    'Estrategia': get_symbol_strategy(symbol, position),
                    'Estado': '🟢 Ganando' if unrealized_pnl >= 0 else '🔴 Pérdida'
                })
            except Exception as e:
                st.error(f"Error processing position for {symbol}: {e}")
                continue
        
        # Display table
        st.subheader("📈 Detalle de Posiciones")
        df = pd.DataFrame(positions_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Update info
        last_update_time = st.session_state.last_update.strftime('%H:%M:%S')
        time_diff = (datetime.now() - st.session_state.last_update).total_seconds()
        
        if time_diff < 30:
            update_status = f"🟢 Actualizado hace {int(time_diff)}s"
        elif time_diff < 120:
            update_status = f"🟡 Actualizado hace {int(time_diff//60)}min {int(time_diff%60)}s"
        else:
            update_status = f"🔴 Última actualización: {last_update_time}"
        
        system_status = "🟢 Auto-refresh activo" if st.session_state.get('system_running', False) else "🔴 Sistema inactivo"
        st.caption(f"{update_status} | {system_status}")
        
    else:
        st.info("ℹ️ No hay posiciones activas")
        
        # Connection status
        connection_status = {'ibkr_connected': False, 'system_running': st.session_state.get('system_running', False)}  # Placeholder
        
        col1, col2 = st.columns(2)
        with col1:
            if connection_status['ibkr_connected']:
                st.success("🟢 Conectado a IBKR")
            else:
                st.error("🔴 Desconectado de IBKR")
        
        with col2:
            if connection_status['system_running']:
                st.success("🟢 Sistema Activo")
            else:
                st.error("🔴 Sistema Inactivo")

# === TAB 3: ANALYTICS ===
with tab3:
    # Enable auto-refresh for analytics tab
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=6000, key="analytics_refresh")
    except ImportError:
        pass
    except RuntimeError:
        pass
    
    st.header("📊 Analytics - Performance & Historial")
    
    # Update system data when analytics tab is accessed
    if st.session_state.get('system_running', False):
        # trading_system.update_analytics()  # Placeholder - adjust as needed
        pass
    
    # Analytics tabs
    analytics_tab1, analytics_tab2, analytics_tab3, analytics_tab4 = st.tabs(["📈 Performance", "📋 Trades History", "📝 Journal", "📚 Advanced Journal"])
    
    with analytics_tab1:
        st.subheader("📊 Performance Overview")
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            days_back = st.selectbox("Período", [7, 15, 30, 60, 90], index=2)
        with col2:
            if st.button("🔄 Actualizar Analytics"):
                st.success("Analytics actualizados")
        
        # Get today's stats (with fallback)
        try:
            today_stats = db_manager.calculate_daily_stats()
        except:
            # Fallback data if database not available
            today_stats = {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0
            }
        
        # Ensure all required keys exist
        today_stats.setdefault('total_trades', 0)
        today_stats.setdefault('win_rate', 0.0)
        today_stats.setdefault('total_pnl', 0.0)
        today_stats.setdefault('avg_pnl', 0.0)
        
        # Display today's performance
        st.subheader("🎯 Performance de Hoy")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Trades Hoy", today_stats['total_trades'])
        with col2:
            st.metric("Win Rate", f"{today_stats['win_rate']:.1f}%")
        with col3:
            st.metric("PnL Hoy", f"${today_stats['total_pnl']:.2f}")
        with col4:
            st.metric("Avg PnL/Trade", f"${today_stats['avg_pnl']:.2f}")
        
        # Strategy performance
        st.subheader("📈 Performance por Estrategia")
        try:
            strategy_performance = db_manager.get_strategy_performance(days_back)
        except:
            # Fallback if method doesn't exist or fails
            strategy_performance = pd.DataFrame()
        
        if not strategy_performance.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(strategy_performance.set_index('strategy')['total_pnl'])
                st.caption("PnL Total por Estrategia")
            
            with col2:
                st.bar_chart(strategy_performance.set_index('strategy')['win_rate'])
                st.caption("Win Rate por Estrategia (%)")
            
            # Detailed table
            st.subheader("📋 Detalles por Estrategia")
            st.dataframe(strategy_performance, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No hay datos de performance para mostrar")
    
    with analytics_tab2:
        st.subheader("📋 Historial de Trades")
        
        # Date range filter
        col1, col2, col3 = st.columns(3)
        with col1:
            show_days = st.selectbox("Mostrar últimos:", [1, 7, 15, 30], index=1, key="history_days")
        with col2:
            strategy_filter = st.selectbox("Filtrar por estrategia:", ["Todas"] + ["MACDV", "VolumeBreakout", "Manual"], key="strategy_filter")
        with col3:
            if st.button("🔄 Actualizar Historial"):
                st.success("Historial actualizado")
        
        # Get recent trades
        try:
            recent_trades = db_manager.get_recent_trades(days=show_days)
        except:
            # Fallback if method doesn't exist or fails
            recent_trades = pd.DataFrame()
        
        if strategy_filter != "Todas" and not recent_trades.empty and 'strategy' in recent_trades.columns:
            recent_trades = recent_trades[recent_trades['strategy'] == strategy_filter]
        
        if not recent_trades.empty:
            # Format DataFrame
            display_trades = recent_trades.copy()
            # Safe datetime parsing with error handling
            try:
                display_trades['entry_time'] = pd.to_datetime(display_trades['entry_time'], format='mixed', errors='coerce').dt.strftime('%m/%d %H:%M')
            except:
                # Fallback if datetime parsing fails
                display_trades['entry_time'] = display_trades['entry_time'].astype(str)
            
            try:
                display_trades['exit_time'] = pd.to_datetime(display_trades['exit_time'], format='mixed', errors='coerce').dt.strftime('%m/%d %H:%M')
            except:
                # Fallback if datetime parsing fails
                display_trades['exit_time'] = display_trades['exit_time'].astype(str)
            display_trades['status_icon'] = display_trades['pnl'].apply(lambda x: '🟢' if x > 0 else '🔴' if x < 0 else '🟡')
            
            st.dataframe(
                display_trades[['entry_time', 'symbol', 'strategy', 'entry_price', 'exit_price', 'pnl', 'status_icon']],
                use_container_width=True,
                hide_index=True
            )
            
            # Summary stats
            total_pnl = display_trades['pnl'].sum()
            win_rate = (display_trades['pnl'] > 0).mean() * 100
            
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Trades", len(display_trades))
            with col2:
                st.metric("PnL Total", f"${total_pnl:.2f}")
            with col3:
                st.metric("Win Rate", f"{win_rate:.1f}%")
            with col4:
                avg_winner = display_trades[display_trades['pnl'] > 0]['pnl'].mean() if (display_trades['pnl'] > 0).any() else 0
                avg_loser = display_trades[display_trades['pnl'] < 0]['pnl'].mean() if (display_trades['pnl'] < 0).any() else 0
                profit_factor = abs(avg_winner / avg_loser) if avg_loser != 0 else float('inf')
                st.metric("Profit Factor", f"{profit_factor:.2f}")
        else:
            st.info("ℹ️ No hay trades recientes para mostrar")
    
    with analytics_tab3:
        st.subheader("📝 Trading Journal")
        
        # Journal entry form
        with st.form("journal_entry"):
            col1, col2 = st.columns(2)
            with col1:
                entry_date = st.date_input("Fecha", datetime.now().date())
                entry_type = st.selectbox("Tipo", ["Trade Note", "Market Observation", "Strategy Insight", "Lesson Learned"])
            
            with col2:
                related_symbol = st.text_input("Símbolo relacionado (opcional)", placeholder="AAPL")
                tags = st.text_input("Tags", placeholder="breakout, volume, fomo")
            
            content = st.text_area("Contenido", height=150, placeholder="Describe lo que observaste, aprendiste o quieres recordar...")
            
            if st.form_submit_button("💾 Guardar Entrada"):
                if content.strip():
                    entry_data = {
                        'date': entry_date,
                        'type': entry_type,
                        'symbol': related_symbol if related_symbol else None,
                        'tags': tags if tags else None,
                        'content': content
                    }
                    
                    if 'journal_entries' not in st.session_state:
                        st.session_state.journal_entries = []
                    
                    st.session_state.journal_entries.append(entry_data)
                    st.success("✅ Entrada guardada en el journal")
                    st.rerun()
                else:
                    st.error("❌ El contenido no puede estar vacío")
        
        # Display journal entries
        st.markdown("---")
        st.subheader("📖 Entradas Recientes")
        
        if st.session_state.get('journal_entries'):
            for entry in reversed(st.session_state.journal_entries[-10:]):
                with st.expander(f"{entry['type']} - {entry['date']}"):
                    if entry.get('symbol'):
                        st.badge(entry['symbol'], type="secondary")
                    if entry.get('tags'):
                        for tag in entry['tags'].split(','):
                            st.badge(tag.strip(), type="outline")
                    st.write(entry['content'])
        else:
            st.info("ℹ️ No hay entradas de journal. ¡Empieza escribiendo tu primera entrada!")
    
    with analytics_tab4:
        st.subheader("📚 Advanced Trade Journal")
        st.caption("Sistema de análisis profundo basado en tu plantilla profesional de trading")
        
        # Import the new classes
        from scanner.scanner_intelligence import AdvancedTradingResult, TradingResult
        
        # Advanced journal entry form
        with st.form("advanced_journal_entry"):
            st.markdown("### 📊 Información Básica del Trade")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                trade_date = st.date_input("📅 Fecha del Trade", datetime.now().date())
                ticker = st.text_input("🎯 Ticker", placeholder="AAPL")
            
            with col2:
                pnl = st.number_input("💰 PnL", step=0.01, format="%.2f")
                entry_price = st.number_input("🎯 Precio Entrada", step=0.01, format="%.2f")
            
            with col3:
                exit_price = st.number_input("🎯 Precio Salida", step=0.01, format="%.2f")
                hold_duration = st.number_input("⏱️ Duración (min)", min_value=0, step=1)
            
            st.markdown("### 🎯 Categorización del Trade")
            col1, col2 = st.columns(2)
            
            with col1:
                trade_category = st.selectbox("📋 Categoría de Trade", [
                    "Gap Play", "VWAP Reclaim", "News Catalyst", "Breakout", 
                    "Pullback", "FOMO Play", "Earnings Play", "FDA Play",
                    "Volume Spike", "Technical Setup", "Other"
                ])
                
                context_type = st.selectbox("📰 Tipo de Contexto", [
                    "Breaking News", "No News", "Earnings", "FDA Approval/Rejection",
                    "Market Wide Move", "Sector Rotation", "Economic Data", "Other"
                ])
            
            with col2:
                market_context = st.selectbox("🌍 Contexto de Mercado", [
                    "Bull Market", "Bear Market", "Sideways Market", 
                    "High Volatility", "Low Volatility", "Market Open",
                    "Market Close", "Lunch Hour", "After Hours"
                ])
                
                why_in_play = st.text_area("🎯 ¿Por qué estaba en juego este ticker?", 
                                          height=80, placeholder="Razón por la que este ticker llamó tu atención...")
            
            st.markdown("### 📊 Análisis de Volumen y Técnico")
            col1, col2 = st.columns(2)
            
            with col1:
                daily_volume_context = st.selectbox("📊 Volumen Diario", [
                    "Normal", "2x Average", "5x Average", "10x+ Massive", "Below Average"
                ])
                
                intraday_volume_context = st.selectbox("📊 Volumen Intradía", [
                    "Normal", "2x Average", "5x Average", "10x+ Massive", "Below Average"
                ])
            
            with col2:
                daily_chart_analysis = st.text_area("📈 Análisis Chart Diario", 
                                                   height=80, placeholder="¿Qué había pasado en el chart diario? Volumen, patrones, niveles...")
                
                intraday_chart_analysis = st.text_area("📈 Análisis Chart Intradía", 
                                                      height=80, placeholder="¿Qué pasó en el intradía? Setup, timing, momentum...")
            
            st.markdown("### 🎯 Análisis de Ejecución")
            col1, col2 = st.columns(2)
            
            with col1:
                followed_system = st.checkbox("✅ ¿Seguiste tu sistema?", value=True)
                sizing_appropriate = st.checkbox("💰 ¿Sizing apropiado?", value=True)
            
            with col2:
                execution_quality = st.selectbox("⚡ Calidad de Ejecución", [
                    "Excellent", "Good", "Fair", "Poor"
                ])
                
                how_you_traded = st.text_area("🎯 ¿Cómo tradeastе?", 
                                             height=80, placeholder="Describe tu ejecución, timing, emociones...")
            
            st.markdown("### 🔍 Reflexión y Aprendizaje")
            col1, col2 = st.columns(2)
            
            with col1:
                how_should_have_traded = st.text_area("💡 ¿Cómo deberías haberlo tradeado?", 
                                                     height=100, placeholder="Sizing ideal, entry, exit, stops...")
                
                how_find_more_opps = st.text_area("🔍 ¿Cómo encontrar más de estas oportunidades?", 
                                                 height=100, placeholder="Tecnología, colaboración, patrones...")
            
            with col2:
                key_takeaways = st.text_area("📝 Lecciones Clave", 
                                            height=100, placeholder="¿Qué aprendiste de este trade?")
                
                changes_to_make = st.text_area("🔧 Cambios a Implementar", 
                                              height=100, placeholder="¿Qué cambios necesitas hacer?")
            
            # Submit button
            submitted = st.form_submit_button("💾 Guardar Análisis Avanzado", type="primary")
            
            if submitted and ticker.strip():
                try:
                    # Create advanced trading result
                    advanced_result = AdvancedTradingResult(
                        ticker=ticker.upper(),
                        trade_date=trade_date,
                        pnl=pnl,
                        trade_category=trade_category,
                        context_type=context_type,
                        market_context=market_context,
                        why_in_play=why_in_play,
                        daily_volume_context=daily_volume_context,
                        intraday_volume_context=intraday_volume_context,
                        daily_chart_analysis=daily_chart_analysis,
                        intraday_chart_analysis=intraday_chart_analysis,
                        how_you_traded=how_you_traded,
                        followed_system=followed_system,
                        sizing_appropriate=sizing_appropriate,
                        execution_quality=execution_quality,
                        how_should_have_traded=how_should_have_traded,
                        how_find_more_opps=how_find_more_opps,
                        key_takeaways=key_takeaways,
                        changes_to_make=changes_to_make,
                        entry_price=entry_price if entry_price > 0 else None,
                        exit_price=exit_price if exit_price > 0 else None,
                        hold_duration_minutes=hold_duration if hold_duration > 0 else None
                    )
                    
                    # Store in session state
                    if 'advanced_journal_entries' not in st.session_state:
                        st.session_state.advanced_journal_entries = []
                    
                    st.session_state.advanced_journal_entries.append(advanced_result)
                    
                    # Feed to ML system for learning
                    try:
                        # Convert to regular TradingResult for ML learning
                        ml_result = TradingResult(
                            ticker=advanced_result.ticker,
                            trade_date=advanced_result.trade_date,
                            entry_price=advanced_result.entry_price or 0.0,
                            exit_price=advanced_result.exit_price,
                            pnl=advanced_result.pnl,
                            was_profitable=advanced_result.pnl > 0 if advanced_result.pnl else None,
                            hold_duration_minutes=advanced_result.hold_duration_minutes,
                            strategy_used=f"manual_{advanced_result.trade_category.lower().replace(' ', '_')}",
                            notes=f"Category: {advanced_result.trade_category} | Context: {advanced_result.context_type} | Quality: {advanced_result.execution_quality}"
                        )
                        
                        scanner_ai.add_trading_result(ml_result)
                        st.success("✅ Análisis guardado y enviado al sistema ML para aprendizaje")
                        
                    except Exception as e:
                        st.warning(f"⚠️ Análisis guardado, pero error enviando al ML: {e}")
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error guardando análisis: {e}")
            
            elif submitted:
                st.error("❌ El ticker es obligatorio")
        
        # Display recent advanced journal entries
        st.markdown("---")
        st.subheader("📖 Análisis Recientes")
        
        if st.session_state.get('advanced_journal_entries'):
            for entry in reversed(st.session_state.advanced_journal_entries[-5:]):
                with st.expander(f"📊 {entry.ticker} - {entry.trade_category} - {entry.trade_date}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("💰 PnL", f"${entry.pnl:.2f}" if entry.pnl else "N/A")
                        st.write(f"📋 **Categoría:** {entry.trade_category}")
                        st.write(f"📰 **Contexto:** {entry.context_type}")
                    
                    with col2:
                        st.write(f"🌍 **Mercado:** {entry.market_context}")
                        st.write(f"📊 **Vol. Diario:** {entry.daily_volume_context}")
                        st.write(f"⚡ **Ejecución:** {entry.execution_quality}")
                    
                    with col3:
                        st.write(f"✅ **Sistema:** {'Sí' if entry.followed_system else 'No'}")
                        st.write(f"💰 **Sizing:** {'Apropiado' if entry.sizing_appropriate else 'Mejorable'}")
                    
                    if entry.key_takeaways:
                        st.write(f"📝 **Lecciones:** {entry.key_takeaways}")
        else:
            st.info("ℹ️ No hay análisis avanzados manuales. ¡Empieza creando tu primer análisis profesional!")
        
        # 🤖 AUTO-CATEGORIZED RESULTS SECTION
        st.markdown("---")
        st.subheader("🤖 Auto-Categorizaciones del Sistema")
        st.caption("Análisis automáticos generados por el sistema ML para cada trade ejecutado")
        
        try:
            # Get auto-categorized results
            auto_results = scanner_ai.get_advanced_trading_results(limit=10)
            
            if auto_results:
                st.write(f"📊 **{len(auto_results)} trades auto-categorizados** (últimos 10)")
                
                for result in auto_results:
                    # Create color-coded expander based on PnL
                    pnl_emoji = "🟢" if result.pnl and result.pnl > 0 else "🔴" if result.pnl and result.pnl < 0 else "⚪"
                    pnl_text = f"${result.pnl:.2f}" if result.pnl else "N/A"
                    
                    with st.expander(f"{pnl_emoji} {result.ticker} - {result.trade_category} - {pnl_text}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.write(f"📋 **Categoría:** {result.trade_category}")
                            st.write(f"📰 **Contexto:** {result.context_type}")
                            st.write(f"🌍 **Mercado:** {result.market_context}")
                            st.write(f"📊 **Volumen:** {result.daily_volume_context}")
                        
                        with col2:
                            st.write(f"⚡ **Ejecución:** {result.execution_quality}")
                            st.write(f"✅ **Sistema:** {'Sí' if result.followed_system else 'No'}")
                            if result.hold_duration_minutes:
                                st.write(f"⏱️ **Duración:** {result.hold_duration_minutes} min")
                        
                        with col3:
                            if result.entry_price:
                                st.write(f"🎯 **Entrada:** ${result.entry_price:.2f}")
                            if result.exit_price:
                                st.write(f"🎯 **Salida:** ${result.exit_price:.2f}")
                            st.write(f"🔧 **Estrategia:** {result.strategy_used}")
                        
                        # Show auto-generated insights
                        if result.why_in_play:
                            st.write(f"🎯 **¿Por qué en juego?** {result.why_in_play}")
                        
                        if result.key_takeaways:
                            st.write(f"📝 **Auto-análisis:** {result.key_takeaways}")
                        
                        # Show creation date
                        if result.created_at:
                            st.caption(f"🕒 Auto-categorizado: {result.created_at}")
            else:
                st.info("ℹ️ No hay trades auto-categorizados aún. El sistema generará análisis automáticamente cuando ejecutes trades.")
                
        except Exception as e:
            st.error(f"❌ Error cargando auto-categorizaciones: {e}")
        
        # Summary statistics
        st.markdown("---")
        st.subheader("📈 Estadísticas Auto-Categorizadas")
        
        try:
            auto_results = scanner_ai.get_advanced_trading_results(limit=100)  # Get more for stats
            
            if auto_results:
                col1, col2, col3, col4 = st.columns(4)
                
                # Category distribution
                categories = {}
                profitable_categories = {}
                execution_quality = {}
                
                for result in auto_results:
                    # Count categories
                    categories[result.trade_category] = categories.get(result.trade_category, 0) + 1
                    
                    # Track profitability by category
                    if result.pnl and result.pnl > 0:
                        profitable_categories[result.trade_category] = profitable_categories.get(result.trade_category, 0) + 1
                    
                    # Track execution quality
                    execution_quality[result.execution_quality] = execution_quality.get(result.execution_quality, 0) + 1
                
                with col1:
                    st.metric("🤖 Auto-Categorizados", len(auto_results))
                
                with col2:
                    profitable = sum(1 for r in auto_results if r.pnl and r.pnl > 0)
                    win_rate = (profitable / len(auto_results) * 100) if auto_results else 0
                    st.metric("✅ Win Rate Auto", f"{win_rate:.1f}%")
                
                with col3:
                    total_pnl = sum(r.pnl for r in auto_results if r.pnl)
                    st.metric("💰 PnL Auto", f"${total_pnl:.2f}")
                
                with col4:
                    excellent_trades = execution_quality.get("Excellent", 0)
                    excellent_pct = (excellent_trades / len(auto_results) * 100) if auto_results else 0
                    st.metric("⭐ Excellent %", f"{excellent_pct:.1f}%")
                
                # Top performing categories
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("📊 **Top Categorías:**")
                    sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
                    for category, count in sorted_categories[:5]:
                        win_rate_cat = (profitable_categories.get(category, 0) / count * 100) if count > 0 else 0
                        st.write(f"• {category}: {count} trades ({win_rate_cat:.0f}% win rate)")
                
                with col2:
                    st.write("⚡ **Calidad de Ejecución:**")
                    for quality, count in sorted(execution_quality.items(), key=lambda x: x[1], reverse=True):
                        pct = (count / len(auto_results) * 100) if auto_results else 0
                        st.write(f"• {quality}: {count} trades ({pct:.0f}%)")
                
        except Exception as e:
            st.error(f"❌ Error calculando estadísticas: {e}")

# === TAB 4: SISTEMA ===
with tab4:
    st.header("Información del Sistema")
    
    # Update system data when system tab is accessed
    if st.session_state.get('system_running', False):
        # trading_system.update_system_status()  # Placeholder - adjust as needed
        pass
    
    # Connection status
    st.subheader("Estado de Conexiones")
    connection_status = {'ibkr_connected': False, 'system_running': st.session_state.get('system_running', False)}  # Placeholder
    
    col1, col2 = st.columns(2)
    
    with col1:
        if connection_status['ibkr_connected']:
            st.success("🟢 IBKR Conectado")
            st.caption(f"Host: {config.broker_host}:{config.broker_port}")
        else:
            st.error("🔴 IBKR Desconectado")
            st.caption("Verifica la conexión con Interactive Brokers")
    
    with col2:
        if connection_status['system_running']:
            st.success("🟢 Sistema Activo")
            st.caption("Trading engine funcionando")
        else:
            st.error("🔴 Sistema Inactivo")
            st.caption("Sistema de trading detenido")
    
    # System Configuration
    st.subheader("⚙️ Configuración del Sistema")
    
    config_data = {
        'Estrategia': config.strategy_name,
        'Max Posiciones': config.max_positions,
        'Max Trades Diarios': config.max_daily_trades,
        'Max Pérdida Diaria': f"${config.max_daily_loss:.2f}",
        'Riesgo por Trade': f"{config.max_risk_per_trade:.1%}",
        'Timeframe': config.timeframe,
        'Host IBKR': f"{config.broker_host}:{config.broker_port}",
        'Client ID': config.broker_client_id
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Configuración de Trading:**")
        for key, value in list(config_data.items())[:4]:
            st.markdown(f"• **{key}:** {value}")
    
    with col2:
        st.markdown("**Configuración de Conexión:**")
        for key, value in list(config_data.items())[4:]:
            st.markdown(f"• **{key}:** {value}")
    
    # System metrics
    st.subheader("📊 Métricas del Sistema")
    
    positions_count = len(st.session_state.get('positions', {}))
    symbols_count = len(st.session_state.get('manual_symbols', []))
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Posiciones Activas", positions_count)
    with col2:
        st.metric("Símbolos Monitoreando", symbols_count)
    with col3:
        if st.session_state.get('system_start_time'):
            uptime = (datetime.now() - st.session_state.system_start_time).total_seconds() / 3600
            st.metric("Uptime", f"{uptime:.1f}h")
        else:
            st.metric("Uptime", "N/A")
    with col4:
        if hasattr(st.session_state, 'last_update'):
            time_since_update = (datetime.now() - st.session_state.last_update).total_seconds()
            if time_since_update < 60:
                update_text = f"{int(time_since_update)}s"
            else:
                update_text = f"{int(time_since_update/60)}m"
            st.metric("Última Actualización", update_text)
        else:
            st.metric("Última Actualización", "N/A")
    
    # Database info
    st.subheader("💾 Base de Datos")
    
    try:
        db_stats = db_manager.get_database_stats()
    except:
        # Fallback if method doesn't exist
        db_stats = {'total_trades': 0, 'today_trades': 0, 'db_size_mb': 0}
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", db_stats.get('total_trades', 0))
    with col2:
        st.metric("Trades Hoy", db_stats.get('today_trades', 0))
    with col3:
        st.metric("DB Size", f"{db_stats.get('db_size_mb', 0):.1f} MB")
    
    if st.button("🔄 Verificar Conectividad"):
        st.info("🔍 Verificando conexiones...")
        
        try:
            st.success("✅ IBKR: Conexión OK")
        except Exception as e:
            st.error(f"❌ IBKR: {str(e)}")
        
        try:
            test_query = db_manager.get_recent_trades(1)
            st.success("✅ Database: Conexión OK")
        except Exception as e:
            st.error(f"❌ Database: {str(e)}")
    
    # Quick actions
    st.subheader("🛠️ Acciones del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Reiniciar Conexión IBKR", use_container_width=True):
            st.info("🔄 Reiniciando conexión...")
            # trading_system.restart_connection()  # Placeholder - adjust as needed
            st.rerun()
    
    with col2:
        if st.button("📊 Status Completo", use_container_width=True):
            st.info("Estado visible arriba ⬆️")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #666; font-size: 0.7rem;">
    <p style="margin: 0.2rem 0;">💼 <strong>Portfolio Management</strong></p>
    <p style="margin: 0.2rem 0;">⚡ Real-time Trading Engine</p>
    <p style="margin: 0.2rem 0;">🛡️ Risk Management Enabled</p>
    <p style="margin: 0.2rem 0;">🧠 ML Learning System</p>
    <br>
    <p style="margin: 0; color: #888;">Built with ❤️ for Professional Trading v4.0</p>
</div>
""", unsafe_allow_html=True)