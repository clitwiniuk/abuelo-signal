# scanner/streamlit_hybrid_scanner.py
"""
Streamlit interface for Hybrid Scanner (IBKR + Tiingo)
Complete integration for smallcap daily plays with real-time edge
"""

import asyncio
import streamlit as st
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .hybrid_scanner import HybridScanner, HybridScanResult, DataSource
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

class StreamlitHybridScanner:
    """
    Streamlit interface for the Hybrid Scanner
    Combines IBKR + Tiingo for maximum smallcap coverage
    """
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.ibkr_adapter = ibkr_adapter
        self.hybrid_scanner = None
        self.last_scan_results = []
        self.last_scan_time = None
        self.scan_stats = {}
    
    def create_interface(self):
        """Create the complete hybrid scanner interface"""
        st.header("🔍 Hybrid Scanner (IBKR + Tiingo)")
        
        # Configuration section
        with st.expander("⚙️ Scanner Configuration", expanded=False):
            self._create_config_interface()
        
        # Scanner controls
        self._create_scanner_controls()
        
        # Results display
        if self.last_scan_results:
            self._display_results()
        
        # Scanner information
        self._create_info_section()
    
    def _create_config_interface(self):
        """Create configuration interface"""
        st.subheader("Data Source Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**IBKR Configuration**")
            ibkr_available = self.ibkr_adapter is not None
            st.write(f"Status: {'✅ Connected' if ibkr_available else '❌ Not connected'}")
            
            if not ibkr_available:
                st.warning("IBKR not available. Using Tiingo only mode.")
        
        with col2:
            st.write("**Tiingo Configuration**")
            tiingo_key = st.text_input(
                "Tiingo API Key",
                type="password",
                help="Enter your Tiingo API key for real-time data",
                key="tiingo_api_key"
            )
            
            if tiingo_key:
                st.success("✅ Tiingo API key configured")
                st.session_state['tiingo_configured'] = True
            else:
                st.info("💡 Get your free API key at tiingo.com")
                st.session_state['tiingo_configured'] = False
        
        # Scanning parameters
        st.subheader("Scanning Parameters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_gap = st.slider("Min Gap %", 0.05, 0.50, 0.08, 0.01, format="%.2f")
            st.session_state['min_gap_percent'] = min_gap
        
        with col2:
            min_volume_ratio = st.slider("Min Volume Ratio", 1.0, 10.0, 2.0, 0.5)
            st.session_state['min_volume_ratio'] = min_volume_ratio
        
        with col3:
            max_results = st.slider("Max Results", 5, 50, 20, 5)
            st.session_state['max_results'] = max_results
        
        # Price range
        col1, col2 = st.columns(2)
        with col1:
            min_price = st.number_input("Min Price $", 0.50, 5.00, 0.50, 0.25)
            st.session_state['min_price'] = min_price
        
        with col2:
            max_price = st.number_input("Max Price $", 5.00, 50.00, 15.00, 1.00)
            st.session_state['max_price'] = max_price
    
    def _create_scanner_controls(self):
        """Create scanner control buttons"""
        st.subheader("Scanner Controls")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🚀 Run Hybrid Scan", type="primary", use_container_width=True):
                self._run_hybrid_scan()
        
        with col2:
            if st.button("📊 IBKR Only", use_container_width=True):
                self._run_ibkr_only()
        
        with col3:
            if st.button("📡 Tiingo Only", use_container_width=True):
                self._run_tiingo_only()
        
        with col4:
            if st.button("📈 Show Last Results", use_container_width=True):
                if self.last_scan_results:
                    self._display_results()
                else:
                    st.info("No previous scan results")
        
        # Scanner status
        if self.last_scan_time:
            st.caption(f"Last scan: {self.last_scan_time.strftime('%H:%M:%S')} - "
                      f"{len(self.last_scan_results)} plays found")
    
    def _run_hybrid_scan(self):
        """Run the full hybrid scan"""
        if not self._validate_configuration():
            return
        
        with st.spinner("🔍 Running Hybrid Scanner (IBKR + Tiingo)..."):
            try:
                # Get configuration
                config = self._get_scan_config()
                
                # Initialize hybrid scanner
                tiingo_key = st.session_state.get('tiingo_api_key')
                self.hybrid_scanner = HybridScanner(
                    ibkr_adapter=self.ibkr_adapter,
                    tiingo_api_key=tiingo_key
                )
                
                # Run async scan
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    results = loop.run_until_complete(
                        self.hybrid_scanner.scan_daily_plays(**config)
                    )
                    
                    self.last_scan_results = results
                    self.last_scan_time = datetime.now()
                    self.scan_stats = self.hybrid_scanner.get_scan_statistics()
                    
                    if results:
                        st.success(f"✅ Found {len(results)} hybrid plays!")
                        self._display_results()
                        
                        # Store in session state
                        st.session_state['hybrid_scan_results'] = results
                        st.session_state['hybrid_scan_symbols'] = [r.symbol for r in results]
                    else:
                        st.warning("No plays found meeting criteria")
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                st.error(f"Hybrid scan error: {e}")
                logger.error(f"Hybrid scan error: {e}")
    
    def _run_ibkr_only(self):
        """Run IBKR scanner only"""
        if not self.ibkr_adapter:
            st.error("IBKR not available")
            return
        
        with st.spinner("📊 Running IBKR Scanner..."):
            try:
                from .ibkr_native_scanner import IBKRNativeScanner
                
                scanner = IBKRNativeScanner(self.ibkr_adapter)
                config = self._get_scan_config()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    results = loop.run_until_complete(
                        scanner.scan_daily_plays(max_results=config['max_results'])
                    )
                    
                    if results:
                        st.success(f"📊 IBKR found {len(results)} candidates")
                        self._display_ibkr_results(results)
                    else:
                        st.warning("No IBKR results found")
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                st.error(f"IBKR scan error: {e}")
    
    def _run_tiingo_only(self):
        """Run Tiingo scanner only"""
        if not st.session_state.get('tiingo_configured', False):
            st.error("Tiingo API key not configured")
            return
        
        with st.spinner("📡 Running Tiingo Scanner..."):
            try:
                from .tiingo_data_provider import TiingoDataProvider
                
                tiingo_key = st.session_state.get('tiingo_api_key')
                config = self._get_scan_config()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Define async function for Streamlit compatibility
                    async def scan_with_tiingo():
                        async with TiingoDataProvider(tiingo_key) as tiingo:
                            return await tiingo.scan_gap_movers(
                                min_gap_percent=config['min_gap_percent'],
                                min_price=config['min_price'],
                                max_price=config['max_price'],
                                max_results=config['max_results']
                            )
                    
                    # Run async function in event loop
                    results = loop.run_until_complete(scan_with_tiingo())
                    
                    if results:
                        st.success(f"📡 Tiingo found {len(results)} gap movers")
                        self._display_tiingo_results(results)
                    else:
                        st.warning("No Tiingo results found")
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                st.error(f"Tiingo scan error: {e}")
    
    def _validate_configuration(self) -> bool:
        """Validate scanner configuration"""
        ibkr_available = self.ibkr_adapter is not None
        tiingo_available = st.session_state.get('tiingo_configured', False)
        
        if not ibkr_available and not tiingo_available:
            st.error("❌ No data sources available. Configure IBKR or Tiingo.")
            return False
        
        if not ibkr_available:
            st.warning("⚠️ IBKR not available - using Tiingo only")
        
        if not tiingo_available:
            st.warning("⚠️ Tiingo not configured - using IBKR only")
        
        return True
    
    def _get_scan_config(self) -> Dict[str, Any]:
        """Get scan configuration from session state"""
        return {
            'min_gap_percent': st.session_state.get('min_gap_percent', 0.08),
            'min_volume_ratio': st.session_state.get('min_volume_ratio', 2.0),
            'min_price': st.session_state.get('min_price', 0.50),
            'max_price': st.session_state.get('max_price', 15.00),
            'max_results': st.session_state.get('max_results', 20)
        }
    
    def _display_results(self):
        """Display hybrid scan results"""
        if not self.last_scan_results:
            return
        
        results = self.last_scan_results
        
        st.subheader(f"🎯 Hybrid Scanner Results ({len(results)} plays)")
        
        # Source summary
        source_counts = {}
        for result in results:
            source = result.primary_source.value
            source_counts[source] = source_counts.get(source, 0) + 1
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Plays", len(results))
        with col2:
            st.metric("IBKR", source_counts.get('IBKR', 0))
        with col3:
            st.metric("Tiingo", source_counts.get('TIINGO', 0))
        with col4:
            st.metric("Hybrid", source_counts.get('HYBRID', 0))
        
        # Quick copy symbols
        symbols = [r.symbol for r in results]
        symbols_text = ", ".join(symbols)
        
        st.text_area(
            "📋 Symbols (ready to copy):",
            value=symbols_text,
            height=60,
            help="Copy these symbols to your trading system"
        )
        
        # Detailed results
        st.subheader("📊 Detailed Results")
        
        for i, result in enumerate(results, 1):
            with st.expander(f"{i}. {result.symbol} - Score: {result.overall_score:.0f} ({result.primary_source.value})"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    gap_direction = "📈" if result.gap_percentage > 0 else "📉"
                    st.metric(
                        "Gap",
                        f"{result.gap_percentage*100:+.1f}%",
                        delta=gap_direction,
                        help="Gap from previous close"
                    )
                    st.metric(
                        "Price",
                        f"${result.current_price:.2f}",
                        help="Current price"
                    )
                
                with col2:
                    st.metric(
                        "Volume",
                        f"{result.volume_ratio:.1f}x",
                        help="Volume vs average"
                    )
                    st.metric(
                        "Data Quality",
                        result.data_quality,
                        help="Data source quality rating"
                    )
                
                with col3:
                    st.metric(
                        "Gap Rank",
                        f"#{result.gap_rank}",
                        help="Gap ranking"
                    )
                    st.metric(
                        "Volume Rank", 
                        f"#{result.volume_rank}",
                        help="Volume ranking"
                    )
                
                # Source details
                source_icon = {"IBKR": "🏦", "TIINGO": "📡", "HYBRID": "🔄"}[result.primary_source.value]
                st.write(f"**Source:** {source_icon} {result.primary_source.value}")
                st.write(f"**Session:** {result.market_session}")
                st.write(f"**Timestamp:** {result.timestamp.strftime('%H:%M:%S')}")
        
        # Add to trading system button
        if st.button("➕ Add All to Trading System", type="secondary", use_container_width=True):
            self._add_symbols_to_trading_system(symbols)
    
    def _display_ibkr_results(self, results):
        """Display IBKR-only results"""
        st.write("**IBKR Scanner Results:**")
        for i, result in enumerate(results[:10], 1):
            st.write(f"{i}. {result.symbol} - Gap: {result.gap_percentage*100:+.1f}% - ${result.current_price:.2f}")
    
    def _display_tiingo_results(self, results):
        """Display Tiingo-only results"""
        st.write("**Tiingo Scanner Results:**")
        for i, result in enumerate(results[:10], 1):
            quote = result.quote
            st.write(f"{i}. {quote.symbol} - Gap: {quote.gap_percentage*100:+.1f}% - ${quote.last_price:.2f}")
    
    def _add_symbols_to_trading_system(self, symbols: List[str]):
        """Add symbols to trading system session state"""
        if 'manual_symbols' not in st.session_state:
            st.session_state.manual_symbols = []
        
        added_count = 0
        for symbol in symbols:
            if symbol not in st.session_state.manual_symbols:
                st.session_state.manual_symbols.append(symbol)
                added_count += 1
        
        if added_count > 0:
            st.success(f"✅ Added {added_count} symbols to trading system")
            st.rerun()
        else:
            st.info("All symbols already in trading system")
    
    def _create_info_section(self):
        """Create information section"""
        with st.expander("ℹ️ Hybrid Scanner Information"):
            st.write("""
            **Hybrid Scanner Features:**
            
            🔄 **Intelligent Data Fusion:**
            - Combines IBKR Market Scanner + Tiingo real-time data
            - Automatic failover between sources
            - Cross-validation of data quality
            - Best available data for each symbol
            
            🎯 **Smallcap Optimization:**
            - Real-time pre-market gap detection
            - Volume surge identification
            - Price range filtering ($0.50-$15)
            - Smallcap-specific data sources
            
            📊 **Data Sources:**
            - **IBKR:** Fast execution integration, comprehensive scanner
            - **Tiingo:** Real-time smallcap data, pre-market coverage
            - **Hybrid:** Cross-validated, highest quality results
            
            ⚡ **Real-time Edge:**
            - No more manual ProRealTime copy/paste
            - Real-time data maintains trading edge
            - Automated catalyst detection
            - Direct integration with trading system
            """)
        
        # Scanner statistics
        if self.scan_stats:
            with st.expander("📈 Scanner Statistics"):
                stats = self.scan_stats
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Scans", stats.get('total_scans', 0))
                with col2:
                    st.metric("Success Rate", f"{stats.get('success_rate', 0):.1f}%")
                with col3:
                    sources = stats.get('data_sources', {})
                    ibkr_status = "✅" if sources.get('ibkr_available', False) else "❌"
                    tiingo_status = "✅" if sources.get('tiingo_available', False) else "❌"
                    st.write(f"**Sources:** IBKR {ibkr_status} | Tiingo {tiingo_status}")

# Convenience function for main Streamlit app
def create_hybrid_scanner_interface(ibkr_adapter: Optional[IBKRAdapter] = None):
    """Create hybrid scanner interface - convenience function"""
    if 'hybrid_scanner_interface' not in st.session_state:
        st.session_state.hybrid_scanner_interface = StreamlitHybridScanner(ibkr_adapter)
    
    st.session_state.hybrid_scanner_interface.create_interface()