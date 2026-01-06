# scanner/web_interface.py
"""
Interfaz web simple para el Daily Plays Filter usando Streamlit
"""

import streamlit as st
import asyncio
import pandas as pd
from daily_plays_filter import DailyPlaysFilter, FilterCriteria
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="Daily Plays Filter",
    page_icon="📊", 
    layout="wide"
)

def main():
    st.title("📊 Daily Plays Filter")
    st.markdown("Filtro avanzado para plays del día con datos de ProRealTime")
    
    # Sidebar for configuration
    st.sidebar.header("⚙️ Configuración")
    
    max_float = st.sidebar.number_input(
        "Float máximo (millones)",
        min_value=1,
        max_value=1000,
        value=100,
        step=10
    ) * 1_000_000
    
    # Sentiment filter selector
    st.sidebar.subheader("🎯 Filtro de Catalizadores")
    sentiment_filter = st.sidebar.radio(
        "Tipo de catalizadores a incluir:",
        options=["Solo POSITIVOS", "POSITIVOS + NEUTRALES"],
        index=0,  # Default to strict
        help="Solo POSITIVOS = Más conservador, menos señales pero mayor calidad\nPOSITIVOS + NEUTRALES = Más permisivo, más señales pero menor calidad"
    )
    
    # Main interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📋 Datos de ProRealTime")
        st.markdown("Pega aquí los datos del ProScreener:")
        
        # Large text area for PRT data
        prt_data = st.text_area(
            "Datos ProScreener",
            height=300,
            placeholder='"Ticker"    "Nombre"    "%Var"    "Var"    "Último"    "Inserción"    "Volumen"\n"ATNF"    "180 LIFE SCIENCES"    "+206,59%"    "+6,90"    "10,24(c)"    "07:00:33"    "225M"\n"AAL"    "AMERICAN AIRLINES GROUP INC."    "+12,09%"    "+1,40"    "12,98(c)"    "07:00:33"    "115M"',
            help="Copia y pega directamente desde ProRealTime ProScreener - Soporta ambos formatos automáticamente"
        )
        
        # Filter button
        if st.button("🔍 Filtrar Tickers", type="primary", use_container_width=True):
            if prt_data.strip():
                # Create progress tracking containers
                progress_container = st.container()
                status_container = st.container()
                
                with progress_container:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                
                try:
                    # Run async filter with progress tracking
                    include_neutral = sentiment_filter == "POSITIVOS + NEUTRALES"
                    result = asyncio.run(filter_tickers_async_with_progress(
                        prt_data, max_float, include_neutral, progress_bar, status_text
                    ))
                    
                    # Clear progress indicators
                    progress_bar.empty()
                    status_text.empty()
                    
                    if result:
                        tickers, detailed_results = result
                        st.session_state['filtered_tickers'] = tickers
                        st.session_state['detailed_results'] = detailed_results
                        st.success(f"✅ Procesamiento completado! {len(tickers)} tickers encontrados.")
                    else:
                        st.session_state['filtered_tickers'] = []
                        st.session_state['detailed_results'] = {}
                        st.warning("⚠️ No se encontraron tickers que cumplan todos los criterios.")
                        
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    st.error(f"❌ Error durante el procesamiento: {e}")
                    st.session_state['filtered_tickers'] = []
            else:
                st.error("Por favor, pega los datos de ProRealTime")
    
    with col2:
        st.header("⚙️ Criterios de Filtrado")
        
        # Show current criteria
        # Show sentiment filter mode
        sentiment_mode = "Solo POSITIVOS" if sentiment_filter == "Solo POSITIVOS" else "POSITIVOS + NEUTRALES"
        criteria_info = f"""
        **Criterios actuales:**
        - 📊 Float máximo: {max_float:,.0f} acciones
        - 📈 Gap mínimo: 10% (filtrado en PRT)
        - 📊 Volumen premarket: >500K (filtrado en PRT)
        - 📰 Catalizadores: {sentiment_mode}
        """
        st.markdown(criteria_info)
        
        # Keywords expandable section
        with st.expander("📰 Palabras clave de catalizadores"):
            keywords = [
                "FDA", "earnings", "acquisition", "merger", "clinical", 
                "breakthrough", "partnership", "contract", "innovation",
                "bitcoin", "crypto", "oil", "gas", "drilling"
            ]
            st.markdown("**Algunos ejemplos:**")
            for i in range(0, len(keywords), 3):
                cols = st.columns(3)
                for j, keyword in enumerate(keywords[i:i+3]):
                    if j < len(cols):
                        cols[j].write(f"• {keyword}")
    
    # Results section
    st.header("🎯 Resultados")
    
    if 'filtered_tickers' in st.session_state:
        tickers = st.session_state['filtered_tickers']
        
        if tickers:
            # Display results in different formats
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📋 Lista para copiar")
                ticker_string = ', '.join(tickers)
                st.text_area(
                    "Tickers filtrados:",
                    value=ticker_string,
                    height=100,
                    help="Copia esta lista para usar en tu trading system"
                )
            
            with col2:
                st.subheader("📊 Lista detallada")
                df = pd.DataFrame(tickers, columns=['Ticker'])
                df['Index'] = range(1, len(df) + 1)
                df = df[['Index', 'Ticker']]
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Enhanced results section
            if 'detailed_results' in st.session_state:
                with st.expander("📰 Análisis Detallado de Noticias", expanded=False):
                    detailed_results = st.session_state['detailed_results']
                    
                    for ticker in tickers:
                        if ticker in detailed_results:
                            result = detailed_results[ticker]
                            sentiment_analysis = result.get('sentiment_analysis')
                            
                            col_ticker, col_sentiment, col_confidence = st.columns([1, 2, 1])
                            
                            with col_ticker:
                                st.markdown(f"**{ticker}**")
                            
                            with col_sentiment:
                                if sentiment_analysis:
                                    sentiment = sentiment_analysis.sentiment.value
                                    summary = sentiment_analysis.summary
                                    if sentiment == 'positive':
                                        st.success(f"✅ {summary}")
                                    elif sentiment == 'negative':
                                        st.error(f"❌ {summary}")
                                    else:
                                        st.info(f"ℹ️ {summary}")
                                else:
                                    st.info("Análisis básico - Catalizador detectado")
                            
                            with col_confidence:
                                if sentiment_analysis:
                                    confidence = sentiment_analysis.confidence
                                    st.metric("Confianza", f"{confidence:.2f}")
                                
                            # Show sources
                            sources_info = []
                            for source, data in result.get('sources', {}).items():
                                if data.get('has_catalyst'):
                                    articles = data.get('articles_found', 0)
                                    sources_info.append(f"✅ {source} ({articles} articles)")
                                else:
                                    sources_info.append(f"❌ {source}")
                            
                            if sources_info:
                                st.caption("Fuentes: " + " | ".join(sources_info))
                            
                            st.divider()
            
            # Download button
            st.download_button(
                label="💾 Descargar lista como CSV",
                data=pd.DataFrame(tickers, columns=['Ticker']).to_csv(index=False),
                file_name=f"daily_plays_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
            
        else:
            # Show specific reason why no tickers were found
            if 'detailed_results' in st.session_state:
                detailed_results = st.session_state['detailed_results']
                
                # Analyze what actually happened
                # Use detailed_results to get the actual parsed count, not the final filtered tickers
                parsed_count = len(detailed_results) if detailed_results else 0
                news_filtered_count = 0
                positive_catalyst_count = 0
                neutral_catalyst_count = 0
                
                # Analyze detailed results
                for ticker in detailed_results:
                    result = detailed_results[ticker]
                    if result.get('has_catalyst'):
                        news_filtered_count += 1
                        if result.get('has_positive_catalyst'):
                            positive_catalyst_count += 1
                        else:
                            # Has catalyst but not positive = neutral/negative
                            neutral_catalyst_count += 1
                
                # Debug info for troubleshooting
                debug_info = f"Debug: {parsed_count} parseados, {news_filtered_count} con noticias, {positive_catalyst_count} positivos, {neutral_catalyst_count} neutrales"
                
                # Show the actual reason with available information
                if parsed_count == 0:
                    reason = f"❌ Error en el formato de datos de ProRealTime"
                elif news_filtered_count > 0 and positive_catalyst_count == 0:
                    if sentiment_filter == "Solo POSITIVOS":
                        reason = f"❌ {news_filtered_count} tickers con catalizadores NEUTRALES/NEGATIVOS (cambia a 'POSITIVOS + NEUTRALES' para incluirlos)"
                    else:
                        reason = f"❌ {news_filtered_count} tickers con catalizadores pero no pasaron otros filtros"
                elif news_filtered_count == 0:
                    reason = f"❌ Se procesaron {parsed_count} tickers pero ninguno tuvo catalizadores en noticias"
                elif positive_catalyst_count > 0:
                    reason = f"❌ {positive_catalyst_count} tickers con catalizadores POSITIVOS pero no pasaron filtro de float"
                else:
                    reason = f"❌ Error en procesamiento ({debug_info})"
                
                st.warning(f"⚠️ No se encontraron tickers que cumplan todos los criterios\n\n**Razón específica:**\n{reason}")
            else:
                st.warning("⚠️ No se encontraron tickers que cumplan todos los criterios")
    
    # Instructions
    with st.expander("📖 Instrucciones de uso"):
        st.markdown("""
        ### Cómo usar este filtro:
        
        1. **En ProRealTime ProScreener:**
           - Configura filtros para volumen premarket >500K
           - Configura gap positivo >10%
           - Exporta o copia los resultados
        
        2. **En esta interfaz:**
           - Pega los datos en el área de texto
           - Ajusta el float máximo si es necesario
           - Haz clic en "Filtrar Tickers"
        
        3. **Resultado:**
           - Lista de tickers que cumplen TODOS los criterios
           - Float <100M shares
           - Noticias recientes con catalizadores
        
        ### Formatos soportados de ProRealTime:
        
        **Formato nuevo (recomendado):**
        ```
        "Ticker"    "Nombre"    "%Var"    "Var"    "Último"    "Inserción"    "Volumen"
        "ATNF"    "180 LIFE SCIENCES"    "+206,59%"    "+6,90"    "10,24(c)"    "07:00:33"    "225M"
        ```
        
        **Formato anterior (también compatible):**
        ```
        "Ticker"    "Nombre"    "Criterio"    "%Var"    "Var"    "Inserción"    "Último"    "Volumen"
        "TLRY"    "TILRAY BRANDS INC."    "6"    "+0,34%"    "+0,0031"    "20:03:57"    "0,9231"    "289M"
        ```
        """)

async def filter_tickers_async(prt_data: str, max_float: float) -> list:
    """Run the async filter function (legacy)"""
    try:
        criteria = FilterCriteria(max_float_shares=max_float)
        
        async with DailyPlaysFilter(criteria) as filter_tool:
            result_tickers = await filter_tool.filter_tickers(prt_data)
            return result_tickers
            
    except Exception as e:
        st.error(f"Error procesando datos: {e}")
        return []

async def filter_tickers_async_with_progress(prt_data: str, max_float: float, 
                                           include_neutral: bool, progress_bar, status_text) -> list:
    """Run the async filter function with progress tracking"""
    try:
        # Step 1: Initialize (5%)
        progress_bar.progress(0.05)
        status_text.text("🔧 Inicializando scanner...")
        
        criteria = FilterCriteria(max_float_shares=max_float)
        
        # Step 2: Parse data (10%)
        progress_bar.progress(0.10)
        status_text.text("📋 Analizando datos de ProRealTime...")
        
        async with DailyPlaysFilter(criteria) as filter_tool:
            # Parse ProRealTime data
            ticker_data = filter_tool.parse_prt_data(prt_data)
            if not ticker_data:
                status_text.text("❌ No se encontraron tickers válidos")
                return []
            
            tickers = [t.ticker for t in ticker_data]
            total_tickers = len(tickers)
            
            # Step 3: Float data collection (15% -> 50%)
            progress_bar.progress(0.15)
            status_text.text(f"💰 Obteniendo datos de float para {total_tickers} tickers...")
            
            # Custom float data collection with progress
            float_data = await get_float_data_with_progress(
                filter_tool, tickers, progress_bar, status_text, 0.15, 0.50
            )
            
            # Filter by float
            float_filtered = []
            for ticker in tickers:
                float_shares = float_data.get(ticker)
                if float_shares is not None and float_shares <= criteria.max_float_shares:
                    float_filtered.append(ticker)
            
            progress_bar.progress(0.55)
            status_text.text(f"📊 Después del filtro de float: {len(float_filtered)} tickers")
            
            if not float_filtered:
                status_text.text("⚠️ Ningún ticker pasó el filtro de float")
                return []
            
            # Step 4: News analysis (55% -> 95%)
            progress_bar.progress(0.60)
            status_text.text(f"📰 Analizando noticias y catalizadores para {len(float_filtered)} tickers...")
            
            # Custom news analysis with progress
            news_data, detailed_news_results = await get_news_data_with_progress(
                filter_tool, float_filtered, include_neutral, progress_bar, status_text, 0.60, 0.95
            )
            
            # Final filtering based on sentiment preference
            final_filtered = []
            for ticker in float_filtered:
                if include_neutral:
                    # Accept both positive and neutral catalysts
                    has_any_catalyst = ticker in detailed_news_results and detailed_news_results[ticker].get('has_catalyst', False)
                    if has_any_catalyst:
                        final_filtered.append(ticker)
                else:
                    # Only accept positive catalysts (strict mode)
                    has_positive_catalyst = news_data.get(ticker, False)
                    if has_positive_catalyst:
                        final_filtered.append(ticker)
            
            # Step 5: Complete (100%)
            progress_bar.progress(1.0)
            status_text.text(f"✅ Análisis completado: {len(final_filtered)} tickers finales")
            
            return (final_filtered, detailed_news_results)
            
    except Exception as e:
        status_text.text(f"❌ Error: {e}")
        raise e

async def get_float_data_with_progress(filter_tool, tickers, progress_bar, status_text, 
                                     start_progress, end_progress):
    """Get float data with progress updates"""
    float_data = {}
    total_tickers = len(tickers)
    progress_range = end_progress - start_progress
    
    # Process in batches
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_progress = start_progress + (i / total_tickers) * progress_range
        
        progress_bar.progress(batch_progress)
        status_text.text(f"💰 Procesando float batch {i//batch_size + 1}/{(total_tickers-1)//batch_size + 1}...")
        
        # Call the original method
        from yahooquery import Ticker
        
        try:
            ticker_obj = Ticker(batch)
            key_stats_data = ticker_obj.key_stats
            
            for ticker in batch:
                try:
                    if ticker in key_stats_data and isinstance(key_stats_data[ticker], dict):
                        ticker_info = key_stats_data[ticker]
                        
                        float_shares = None
                        for field in ['floatShares', 'sharesOutstanding', 'impliedSharesOutstanding']:
                            if field in ticker_info and ticker_info[field]:
                                float_shares = ticker_info[field]
                                break
                        
                        float_data[ticker] = float_shares
                    else:
                        float_data[ticker] = None
                        
                except Exception:
                    float_data[ticker] = None
                    
            # Small delay between batches
            await asyncio.sleep(0.3)
            
        except Exception:
            for ticker in batch:
                float_data[ticker] = None
    
    return float_data

async def get_news_data_with_progress(filter_tool, tickers, include_neutral, progress_bar, status_text,
                                    start_progress, end_progress):
    """Get news data with progress updates"""
    total_tickers = len(tickers)
    progress_range = end_progress - start_progress
    
    # Process individually for better progress tracking
    news_results = {}
    detailed_results_all = {}
    
    for i, ticker in enumerate(tickers):
        progress = start_progress + (i / total_tickers) * progress_range
        progress_bar.progress(progress)
        status_text.text(f"📰 Analizando noticias: {ticker} ({i+1}/{total_tickers})")
        
        try:
            # Call the multi-source news checker for this ticker
            detailed_results = await filter_tool.news_checker.check_all_sources([ticker])
            
            if ticker in detailed_results:
                result = detailed_results[ticker]
                detailed_results_all[ticker] = result  # Store detailed results
                
                has_positive_catalyst = result.get('has_positive_catalyst', False)
                news_results[ticker] = has_positive_catalyst
                
                # Show brief result based on filtering mode
                sentiment_analysis = result.get('sentiment_analysis')
                has_any_catalyst = result.get('has_catalyst', False)
                
                if include_neutral:
                    # Permissive mode: accept positive + neutral
                    if has_any_catalyst:
                        if sentiment_analysis:
                            sentiment = sentiment_analysis.sentiment.value
                            confidence = sentiment_analysis.confidence
                            status_text.text(f"📰 {ticker}: ✅ {sentiment.upper()} catalyst (conf: {confidence:.2f})")
                        else:
                            status_text.text(f"📰 {ticker}: ✅ Catalyst found")
                        news_results[ticker] = True
                    else:
                        status_text.text(f"📰 {ticker}: ❌ No catalysts")
                        news_results[ticker] = False
                else:
                    # Strict mode: only positive
                    if has_positive_catalyst:
                        if sentiment_analysis:
                            sentiment = sentiment_analysis.sentiment.value
                            confidence = sentiment_analysis.confidence
                            status_text.text(f"📰 {ticker}: ✅ {sentiment.upper()} catalyst (conf: {confidence:.2f})")
                        else:
                            status_text.text(f"📰 {ticker}: ✅ Positive catalyst found")
                        news_results[ticker] = True
                    else:
                        if has_any_catalyst and sentiment_analysis:
                            sentiment = sentiment_analysis.sentiment.value
                            status_text.text(f"📰 {ticker}: ❌ {sentiment.upper()} catalyst (filtered in strict mode)")
                        else:
                            status_text.text(f"📰 {ticker}: ❌ No positive catalysts")
                        news_results[ticker] = False
            else:
                news_results[ticker] = False
                detailed_results_all[ticker] = {'has_catalyst': False, 'sources': {}}
                
        except Exception as e:
            news_results[ticker] = False
            detailed_results_all[ticker] = {'has_catalyst': False, 'error': str(e)}
            status_text.text(f"📰 {ticker}: ⚠️ Error checking news")
        
        # Small delay between tickers
        await asyncio.sleep(0.1)
    
    return news_results, detailed_results_all

if __name__ == "__main__":
    main()