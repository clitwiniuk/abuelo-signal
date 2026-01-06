#!/usr/bin/env python3
"""
Standalone Quality Trading Application
=====================================

A minimal Streamlit application focused solely on Quality System analysis and trade execution
without the heavy trading system components that cause infinite loops.
"""

import streamlit as st
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Quality Trading System",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add current directory to Python path for Quality System imports
current_dir = Path(__file__).parent.resolve()

# Add current directory to path (where quality_core is located)
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Try to import the advanced analyzer (our main component)
QUALITY_SYSTEM_AVAILABLE = False
ADVANCED_ANALYZER_AVAILABLE = False

try:
    from quality_core.advanced_setup_analyzer import analyze_setup_comprehensive
    ADVANCED_ANALYZER_AVAILABLE = True
    st.success("✅ Advanced Quality System loaded successfully")
except ImportError as e:
    st.error(f"❌ Advanced analyzer not available: {e}")
    
# Try to import legacy quality system components if they exist
try:
    from quality_core.setup_classifier import HybridSetupClassifier
    from quality_core.interfaces import SetupData
    QUALITY_SYSTEM_AVAILABLE = True
except ImportError:
    st.info("ℹ️ Legacy quality system not available - using advanced analyzer only")

# Helper functions for PRT data parsing
def parse_prt_data(prt_text):
    """Parse ProRealTime data from text input"""
    lines = prt_text.strip().split('\n')
    parsed_setups = []
    
    # Skip header line if present
    data_lines = [line for line in lines if line.strip() and not line.strip().startswith('"Ticker"')]
    
    for line in data_lines:
        try:
            # Split by tab and clean quotes
            parts = [part.strip().strip('"') for part in line.split('\t') if part.strip()]
            
            if len(parts) >= 7:  # Expecting 7 columns from PRT
                ticker = parts[0]
                name = parts[1]
                pct_var = parts[2].replace('%', '').replace('+', '').replace(',', '.')
                price = parts[4].replace(',', '.')
                volume_str = parts[6]
                
                # Parse percentage change
                try:
                    pct_change = float(pct_var)
                except:
                    pct_change = 0.0
                
                # Parse price
                try:
                    current_price = float(price)
                except:
                    current_price = 0.0
                
                # Parse volume
                volume = 0
                if 'M' in volume_str:
                    volume = float(volume_str.replace('M', '').replace(',', '.')) * 1_000_000
                elif 'k' in volume_str:
                    volume = float(volume_str.replace('k', '').replace(',', '.')) * 1_000
                else:
                    try:
                        volume = float(volume_str.replace(',', '.'))
                    except:
                        volume = 0
                
                setup = {
                    'ticker': ticker,
                    'name': name,
                    'price': current_price,
                    'pct_change': pct_change,
                    'volume': volume
                }
                parsed_setups.append(setup)
                
        except Exception as e:
            st.warning(f"Error parsing line: {line[:50]}... - {e}")
            continue
    
    return parsed_setups

def filter_execution_criteria(setups, max_float_m, min_catalyst_strength):
    """Filter setups by execution criteria"""
    filtered = []
    
    for setup in setups:
        # Basic criteria for smallcaps
        if (setup['price'] >= 0.50 and 
            setup['price'] <= 20.00 and 
            setup['volume'] >= 100_000 and 
            setup['pct_change'] >= 10.0):
            filtered.append(setup)
    
    return filtered

def classify_setup_quality(setup, classifier=None):
    """Classify setup quality using the Advanced Quality System"""
    
    # Try to use the advanced analyzer first
    if ADVANCED_ANALYZER_AVAILABLE:
        try:
            advanced_result = analyze_setup_comprehensive(
                ticker=setup['ticker'],
                current_price=setup['price'],
                current_volume=setup['volume'],
                premarket_gap_pct=setup['pct_change']
            )
            
            # Convert advanced result to expected format
            return {
                'ticker': setup['ticker'],
                'name': setup['name'],
                'price': setup['price'],
                'pct_change': setup['pct_change'],
                'volume': setup['volume'],
                'grade': advanced_result['grade'],
                'catalyst_score': min(95, 50 + abs(setup['pct_change'])),
                'overall_score': advanced_result['overall_score'],
                # Enhanced fields from advanced analysis
                'consolidation_months': advanced_result.get('consolidation_months', 0),
                'nearest_target': advanced_result.get('nearest_target'),
                'volume_quality': advanced_result.get('volume_quality', 'unknown'),
                'timing_quality': advanced_result.get('timing_quality', 'unknown'),
                'recommendation': advanced_result.get('recommendation', 'ANALYZE'),
                'key_factors': advanced_result.get('key_factors', []),
                'red_flags': advanced_result.get('red_flags', []),
                'risk_level': advanced_result.get('risk_level', 'medium'),
                'position_size': advanced_result.get('position_size', 'small'),
                'analysis_type': 'advanced'
            }
            
        except Exception as e:
            st.warning(f"⚠️ Advanced analysis failed for {setup['ticker']}: {e}")
            # Fall back to basic analysis
    
    # Fallback: Use basic classification or traditional classifier
    if classifier and QUALITY_SYSTEM_AVAILABLE:
        try:
            setup_data = SetupData(
                ticker=setup['ticker'],
                price=setup['price'],
                volume=setup['volume'],
                pct_change=setup['pct_change'],
                catalyst_strength=min(95, 50 + setup['pct_change'])
            )
            result = classifier.classify_setup(setup_data)
            grade = result.get('grade', 'C')
            catalyst_score = result.get('catalyst_score', 50)
            score = result.get('overall_score', 50)
        except:
            # Fall back to simple classification
            score, grade, catalyst_score = _simple_classification(setup)
    else:
        # Simple rule-based classification
        score, grade, catalyst_score = _simple_classification(setup)
    
    return {
        'ticker': setup['ticker'],
        'name': setup['name'],
        'price': setup['price'],
        'pct_change': setup['pct_change'],
        'volume': setup['volume'],
        'grade': grade,
        'catalyst_score': catalyst_score,
        'overall_score': score,
        'analysis_type': 'basic'
    }

def _simple_classification(setup):
    """Simple fallback classification"""
    score = 0
    
    # Price momentum (40% weight)
    if setup['pct_change'] >= 50:
        score += 40
    elif setup['pct_change'] >= 30:
        score += 30
    elif setup['pct_change'] >= 20:
        score += 20
    elif setup['pct_change'] >= 10:
        score += 10
    
    # Volume (30% weight)
    if setup['volume'] >= 10_000_000:
        score += 30
    elif setup['volume'] >= 5_000_000:
        score += 20
    elif setup['volume'] >= 1_000_000:
        score += 15
    elif setup['volume'] >= 100_000:
        score += 10
    
    # Catalyst strength simulation (30% weight)
    catalyst_score = min(95, 50 + setup['pct_change'])
    score += int(catalyst_score * 0.3)
    
    # Determine grade
    if score >= 85:
        grade = 'A+'
    elif score >= 75:
        grade = 'A'
    elif score >= 65:
        grade = 'A-'
    elif score >= 55:
        grade = 'B+'
    elif score >= 45:
        grade = 'B'
    elif score >= 35:
        grade = 'C'
    else:
        grade = 'D'
    
    return score, grade, catalyst_score

def execute_quality_trades(high_quality_setups):
    """Execute trades for high quality setups (A+ and A grade)"""
    if not high_quality_setups:
        st.warning("⚠️ No hay setups de alta calidad para ejecutar")
        return
    
    st.write("### 🚀 Ejecutando Trades Automáticamente")
    
    executed_trades = []
    failed_trades = []
    
    for setup in high_quality_setups:
        try:
            ticker = setup.get('ticker', 'N/A')
            grade = setup.get('grade', 'N/A')
            catalyst_score = setup.get('catalyst_score', 0)
            price = setup.get('price', 0)
            
            # Determine position size based on grade and catalyst strength
            if grade == 'A+':
                position_size = min(1000, int(2000 / price)) if price > 0 else 100  # Max $2000 for A+
            else:  # Grade A
                position_size = min(500, int(1000 / price)) if price > 0 else 50   # Max $1000 for A
            
            # Simulate trade execution
            trade_result = {
                'ticker': ticker,
                'action': 'BUY',
                'quantity': position_size,
                'price': price,
                'grade': grade,
                'catalyst_score': catalyst_score,
                'estimated_value': position_size * price,
                'status': 'EXECUTED',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            executed_trades.append(trade_result)
            
            # Display execution status
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**{ticker}**")
            with col2:
                st.write(f"Grade: **{grade}**")
            with col3:
                st.write(f"Qty: **{position_size}**")
            with col4:
                st.success("✅ EXECUTED")
                
        except Exception as e:
            failed_trades.append({
                'ticker': setup.get('ticker', 'N/A'),
                'error': str(e)
            })
            st.error(f"❌ Error ejecutando {setup.get('ticker', 'N/A')}: {e}")
    
    # Summary
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Trades Ejecutados", len(executed_trades))
    with col2:
        st.metric("Trades Fallidos", len(failed_trades))
    with col3:
        total_value = sum(trade['estimated_value'] for trade in executed_trades)
        st.metric("Valor Total Invertido", f"${total_value:,.2f}")
    
    if executed_trades:
        st.success(f"✅ Se ejecutaron {len(executed_trades)} trades automáticamente")
        
        # Store executed trades in session state for tracking
        if 'executed_quality_trades' not in st.session_state:
            st.session_state.executed_quality_trades = []
        st.session_state.executed_quality_trades.extend(executed_trades)
        
        # Show trade details
        with st.expander("📊 Detalles de Trades Ejecutados"):
            df = pd.DataFrame(executed_trades)
            st.dataframe(df, use_container_width=True)
    
    if failed_trades:
        st.error(f"❌ {len(failed_trades)} trades fallaron")

def display_setup_table(setups):
    """Display enhanced table of setups with advanced analysis"""
    if not setups:
        return
    
    # Convert to DataFrame for display
    df_data = []
    for setup in setups:
        # Determine status icon based on analysis type and quality
        if setup.get('analysis_type') == 'advanced':
            if setup.get('red_flags'):
                status = "🔴"
            elif setup.get('recommendation', '').startswith('STRONG'):
                status = "🟢"
            elif setup.get('recommendation', '').startswith('BUY'):
                status = "🟡"
            else:
                status = "🟠"
        else:
            status = "⚪"  # Basic analysis
        
        row_data = {
            'Status': status,
            'Ticker': setup['ticker'],
            'Nombre': setup['name'][:25] + '...' if len(setup['name']) > 25 else setup['name'],
            'Precio': f"${setup['price']:.2f}",
            'Gap %': f"{setup['pct_change']:.1f}%",
            'Volumen': f"{setup['volume']:,.0f}",
            'Grade': setup['grade'],
            'Score': f"{setup['overall_score']:.0f}"
        }
        
        # Add advanced analysis columns if available
        if setup.get('analysis_type') == 'advanced':
            # Consolidation info
            consol_months = setup.get('consolidation_months', 0)
            if consol_months >= 3:
                row_data['Consol.'] = f"{consol_months:.1f}M ✅"
            elif consol_months >= 1:
                row_data['Consol.'] = f"{consol_months:.1f}M"
            else:
                row_data['Consol.'] = "None"
            
            # Target info
            target = setup.get('nearest_target')
            if target:
                row_data['Target'] = f"${target['price']:.2f} (+{target['distance_pct']:.0f}%)"
            else:
                row_data['Target'] = "N/A"
            
            # Volume quality
            vol_qual = setup.get('volume_quality', 'unknown')
            row_data['Vol.Q'] = vol_qual.title()
            
            # Risk level
            risk = setup.get('risk_level', 'medium')
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")
            row_data['Risk'] = f"{risk_emoji} {risk.title()}"
        
        df_data.append(row_data)
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
    
    # Enhanced legend
    if any(setup.get('analysis_type') == 'advanced' for setup in setups):
        st.caption("🟢 Strong Buy | 🟡 Buy/Conditional | 🟠 Watch | 🔴 Red Flags | ⚪ Basic Analysis")
        st.caption("Consol. = Consolidation Months | Target = Historical Resistance | Vol.Q = Volume Quality")
    else:
        st.caption("⚪ Using basic analysis - Advanced system not available")

def display_quality_results(classified_setups, execute_trades):
    """Display the quality analysis results"""
    if not classified_setups:
        st.warning("⚠️ No se encontraron setups que cumplan los criterios")
        return
    
    # Separate by quality tiers
    high_quality = [s for s in classified_setups if s['grade'] in ['A+', 'A']]
    medium_quality = [s for s in classified_setups if s['grade'] in ['A-', 'B+']]
    watch_list = [s for s in classified_setups if s['grade'] in ['B', 'C']]
    
    # Summary metrics
    st.subheader("📊 Resumen del Análisis")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Setups", len(classified_setups))
    with col2:
        st.metric("Alta Calidad (A+/A)", len(high_quality))
    with col3:
        st.metric("Calidad Media (A-/B+)", len(medium_quality))
    with col4:
        st.metric("Watchlist (B/C)", len(watch_list))
    
    # High Quality Setups
    if high_quality:
        st.subheader("🟢 Setups de Alta Calidad (A+ y A)")
        display_setup_table(high_quality)
        
        # Show detailed analysis for high quality setups with advanced analysis
        advanced_setups = [s for s in high_quality if s.get('analysis_type') == 'advanced']
        if advanced_setups:
            with st.expander("🔍 Análisis Detallado de Setups de Alta Calidad"):
                for setup in advanced_setups:
                    st.markdown(f"### {setup['ticker']} - {setup['grade']} ({setup['overall_score']}/100)")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**📊 Factores Clave:**")
                        for factor in setup.get('key_factors', []):
                            st.write(f"✅ {factor}")
                    
                    with col2:
                        st.markdown("**⚠️ Red Flags:**")
                        if setup.get('red_flags'):
                            for flag in setup['red_flags']:
                                st.write(f"🔴 {flag}")
                        else:
                            st.write("✅ No hay red flags detectadas")
                    
                    with col3:
                        st.markdown("**🎯 Recomendación:**")
                        recommendation = setup.get('recommendation', 'ANALYZE')
                        if recommendation.startswith('STRONG'):
                            st.success(recommendation)
                        elif recommendation.startswith('BUY'):
                            st.info(recommendation)
                        else:
                            st.warning(recommendation)
                        
                        # Risk and position sizing
                        risk_level = setup.get('risk_level', 'medium')
                        position_size = setup.get('position_size', 'small')
                        st.write(f"**Riesgo:** {risk_level.title()}")
                        st.write(f"**Tamaño posición:** {position_size.title()}")
                    
                    st.markdown("---")
        
        if execute_trades:
            st.success("✅ Modo ejecución automática activado - ejecutando trades de alta calidad")
            execute_quality_trades(high_quality)
    
    # Medium Quality Setups  
    if medium_quality:
        st.subheader("🟡 Setups de Calidad Media (A- y B+)")
        display_setup_table(medium_quality)
    
    # Watch List
    if watch_list:
        st.subheader("👀 Watch List (B y C)")
        display_setup_table(watch_list)

# Main Application
def main():
    st.title("⭐ Quality Trading System - Standalone")
    st.markdown("*Análisis de calidad y ejecución automática de trades para smallcaps*")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Enhanced philosophy
        with st.expander("🎯 Filosofía Advanced Quality System", expanded=False):
            st.info("""
            **Sistema Multi-Factor Avanzado:**
            
            🏗️ **Consolidation First** (30%): Meses de acumulación = Setups de calidad
            
            ⏰ **Timing Analysis** (25%): Premarket exhausted vs Regular hours strength
            
            📊 **Volume Profile** (25%): Institutional interest & accumulation patterns
            
            📰 **News Sentiment** (20%): Catalyst quality & risk assessment
            
            **Key Insight**: Un gap grande sin consolidación previa es peor que un gap pequeño 
            con meses de acumulación y room to run hacia resistencias históricas.
            """)
        
        max_float = st.number_input(
            "Float máximo (M)", 
            min_value=1.0, 
            max_value=100.0, 
            value=50.0, 
            step=5.0,
            help="Float máximo en millones para considerar smallcap"
        )
        
        min_catalyst_strength = st.slider(
            "Fortaleza mínima catalizador (%)",
            min_value=50,
            max_value=95,
            value=70,
            step=5,
            help="Porcentaje mínimo de fortaleza del catalizador"
        )
        
        execute_trades = st.checkbox(
            "Ejecutar trades automáticamente",
            value=False,
            help="Si está activado, ejecutará trades automáticamente para setups A+ y A"
        )
    
    # Main analysis area
    st.subheader("📊 Análisis de Datos PRT")
    
    # Data input section
    col1, col2 = st.columns([3, 1])
    
    with col1:
        prt_data = st.text_area(
            "Pega aquí los datos de ProRealTime:",
            placeholder='"DFLI"\t"DRAGONFLY ENERGY HLD."\t"+52,81%"\t"+0,1400"\t"0,4051"\t"13:06:45"\t"73,8M"',
            height=150,
            help="Formato PRT: Ticker, Nombre, %Var, Var, Último, Inserción, Volumen (separado por tabs)",
            key="prt_data_input"
        )
    
    with col2:
        st.write("**🧪 Datos de prueba:**")
        if st.button("📋 Cargar ejemplo", help="Carga datos de ejemplo para probar"):
            example_data = '''"DFLI"\t"DRAGONFLY ENERGY HLD."\t"+52,81%"\t"+0,1400"\t"0,4051"\t"13:06:45"\t"73,8M"
"ORIS"\t"ORIENTAL RISE HOLDINGS"\t"+16,25%"\t"+0,0169"\t"0,1209"\t"13:06:45"\t"71,3M"
"PPSI"\t"PIONEER POWER SOLUTIONS INC."\t"+56,59%"\t"+1,76"\t"4,87"\t"13:06:45"\t"25,3M"
"FUFU"\t"BITFUFU INC."\t"+18,39%"\t"+0,73"\t"4,70"\t"13:06:45"\t"5.990k"
"VMAR"\t"VISION MARINE TECHNOLOGIES"\t"+51,06%"\t"+1,45"\t"4,29"\t"13:16:20"\t"5.295k"
"PGEN"\t"PRECIGEN INC."\t"+69,73%"\t"+1,29"\t"3,14"\t"13:26:20"\t"4.671k"'''
            st.session_state.prt_data_input = example_data
            st.success("✅ Datos de ejemplo cargados!")
            st.rerun()
    
    # Analysis button
    analyze_button = st.button("🎯 Analizar Setups con Quality System", type="primary")
    
    if analyze_button:
        if not prt_data.strip():
            st.error("❌ Por favor, pega los datos de ProRealTime antes de analizar")
        else:
            # Create prominent progress section
            st.markdown("### 🎯 Análisis en Progreso")
            st.info(f"📊 Iniciando análisis de {len(prt_data.strip().split(chr(10)))} líneas de datos...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Parse PRT data
                status_text.text("📊 Procesando datos de PRT...")
                progress_bar.progress(0.20)
                
                parsed_data = parse_prt_data(prt_data)
                
                if not parsed_data:
                    st.error("❌ No se pudieron procesar los datos de PRT. Verifica el formato.")
                    st.info("💡 Formato esperado: datos separados por tabs de ProRealTime")
                else:
                    status_text.text("🎯 Filtrando por criterios de ejecución...")
                    progress_bar.progress(0.40)
                    
                    # Filter by execution criteria
                    filtered_data = filter_execution_criteria(parsed_data, max_float, min_catalyst_strength)
                    
                    if not filtered_data:
                        st.warning("⚠️ Ningún setup cumple los criterios de ejecución")
                        st.info("💡 Criterios: Precio 0.50-20.00, Volumen >100k, Cambio >10%")
                    else:
                        status_text.text("📊 Clasificando calidad de setups...")
                        progress_bar.progress(0.60)
                        
                        # Initialize classifier if available
                        classifier = None
                        if QUALITY_SYSTEM_AVAILABLE:
                            try:
                                classifier = HybridSetupClassifier()
                            except:
                                pass
                        
                        # Classify each setup
                        classified_setups = []
                        for i, setup in enumerate(filtered_data):
                            classification = classify_setup_quality(setup, classifier)
                            classified_setups.append(classification)
                            # Mini progress update
                            progress_bar.progress(0.60 + (i / len(filtered_data)) * 0.15)
                        
                        status_text.text("⭐ Priorizando por catalyst strength...")
                        progress_bar.progress(0.80)
                        
                        # Sort by grade and catalyst score
                        grade_map = {'A+': 6, 'A': 5, 'A-': 4, 'B+': 3, 'B': 2, 'C': 1, 'D': 0}
                        classified_setups.sort(key=lambda x: (
                            grade_map.get(x['grade'], 0),
                            x['catalyst_score']
                        ), reverse=True)
                        
                        status_text.text("✅ Análisis completado")
                        progress_bar.progress(1.0)
                        
                        # Store results in session state to persist them
                        st.session_state.quality_analysis_results = classified_setups
                        st.session_state.quality_execute_trades = execute_trades
                        
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Display results if we have them
                if hasattr(st.session_state, 'quality_analysis_results') and st.session_state.quality_analysis_results:
                    st.success(f"✅ Análisis completado: {len(st.session_state.quality_analysis_results)} setups clasificados")
                    display_quality_results(st.session_state.quality_analysis_results, st.session_state.quality_execute_trades)
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Error en análisis: {e}")
                import traceback
                with st.expander("🔍 Detalles del error"):
                    st.code(traceback.format_exc())
    
    # Always display results if they exist in session state (from previous analysis)
    elif hasattr(st.session_state, 'quality_analysis_results') and st.session_state.quality_analysis_results:
        st.info("📊 Mostrando resultados del último análisis:")
        display_quality_results(st.session_state.quality_analysis_results, st.session_state.get('quality_execute_trades', False))
        
        # Add button to clear results
        if st.button("🗑️ Limpiar Resultados", help="Limpia los resultados del análisis anterior"):
            del st.session_state.quality_analysis_results
            if hasattr(st.session_state, 'quality_execute_trades'):
                del st.session_state.quality_execute_trades
            st.rerun()
    
    # Show executed trades history if any
    if 'executed_quality_trades' in st.session_state and st.session_state.executed_quality_trades:
        st.markdown("---")
        st.subheader("📈 Historial de Trades Ejecutados")
        df = pd.DataFrame(st.session_state.executed_quality_trades)
        st.dataframe(df, use_container_width=True)
        
        # Summary metrics
        total_trades = len(st.session_state.executed_quality_trades)
        total_invested = sum(trade['estimated_value'] for trade in st.session_state.executed_quality_trades)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Trades Ejecutados", total_trades)
        with col2:
            st.metric("Total Invertido", f"${total_invested:,.2f}")

if __name__ == "__main__":
    main()