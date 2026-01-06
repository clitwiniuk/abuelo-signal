# scanner/streamlit_scanner_integration.py
"""
Streamlit integration for SmallcapDailyScanner
Provides clean interface for running IBKR Native Scanner
"""

import asyncio
import streamlit as st
import logging
from typing import List, Optional
from datetime import datetime

from scanner.smallcap import SmallcapDailyScanner, SmallcapPlay
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

class StreamlitScannerIntegration:
    """
    Integration class for running SmallcapDailyScanner in Streamlit
    Handles async operations and UI updates
    """
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None):
        self.ibkr_adapter = ibkr_adapter
        self.scanner = None
        self.last_scan_results = []
        self.last_scan_time = None
    
    async def run_scanner(self, show_progress: bool = True) -> List[SmallcapPlay]:
        """
        Run the scanner with Streamlit progress updates
        """
        if show_progress:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        try:
            # Initialize scanner
            if show_progress:
                status_text.text("🔧 Initializing IBKR Native Scanner...")
                progress_bar.progress(10)
            
            self.scanner = SmallcapDailyScanner(self.ibkr_adapter)
            
            # Run scan
            if show_progress:
                status_text.text("🔍 Scanning IBKR market data...")
                progress_bar.progress(30)
            
            plays = await self.scanner.scan_daily_plays()
            
            if show_progress:
                status_text.text("📰 Analyzing catalysts...")
                progress_bar.progress(70)
            
            # Processing complete
            if show_progress:
                status_text.text(f"✅ Found {len(plays)} high-quality plays")
                progress_bar.progress(100)
            
            # Store results
            self.last_scan_results = plays
            self.last_scan_time = datetime.now()
            
            # Clear progress
            if show_progress:
                progress_bar.empty()
                status_text.empty()
            
            return plays
            
        except Exception as e:
            logger.error(f"Error in scanner: {e}")
            if show_progress:
                st.error(f"Scanner error: {e}")
                progress_bar.empty()
                status_text.empty()
            return []
    
    def display_scan_results(self, plays: List[SmallcapPlay]):
        """
        Display scan results in Streamlit with nice formatting
        """
        if not plays:
            st.info("ℹ️ No high-quality smallcap plays found")
            return
        
        # Summary header
        st.success(f"🎯 Found {len(plays)} high-quality smallcap daily plays!")
        
        # Quick copy symbols
        symbols = [play.symbol for play in plays]
        symbols_text = ", ".join(symbols)
        
        st.text_area(
            "📋 Symbols (ready to copy):",
            value=symbols_text,
            height=60,
            help="Select all and copy these symbols to add to your trading system"
        )
        
        # Detailed results
        st.subheader("📊 Detailed Analysis")
        
        for i, play in enumerate(plays, 1):
            with st.expander(f"{i}. {play.symbol} - Score: {play.quality_score:.1f}/10"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "Gap",
                        f"{play.context.gap_percentage*100:+.1f}%",
                        help="Gap from previous close"
                    )
                    st.metric(
                        "Price",
                        f"${play.context.current_price:.2f}",
                        help="Current price"
                    )
                
                with col2:
                    volume_ratio = play.context.premarket_volume_ratio
                    st.metric(
                        "Volume",
                        f"{volume_ratio:.1f}x",
                        help="Volume vs average"
                    )
                    st.metric(
                        "IBKR Rank",
                        f"#{play.ibkr_rank}",
                        help="Original IBKR scanner ranking"
                    )
                
                with col3:
                    st.metric(
                        "Catalyst",
                        f"{play.catalyst.catalyst_type}",
                        help=f"Strength: {play.catalyst.strength}/10"
                    )
                    st.metric(
                        "Strategy",
                        play.trading_recommendation.get('strategy_preference', 'standard'),
                        help="Recommended trading strategy"
                    )
                
                # Additional details
                if play.catalyst.headline != 'No news found':
                    st.write(f"**News:** {play.catalyst.headline}")
                
                if play.catalyst.keywords_found:
                    st.write(f"**Keywords:** {', '.join(play.catalyst.keywords_found[:3])}")
    
    def get_symbols_for_trading_system(self) -> List[str]:
        """
        Get symbols from last scan for adding to trading system
        """
        if not self.last_scan_results:
            return []
        
        return [play.symbol for play in self.last_scan_results]
    
    def create_scanner_interface(self):
        """
        Create the complete scanner interface in Streamlit
        """
        st.header("🔍 IBKR Native Daily Plays Scanner")
        
        # Scanner controls
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("🚀 Run Daily Scanner", type="primary", use_container_width=True):
                with st.spinner("Running IBKR Native Scanner..."):
                    # Run async scanner
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        plays = loop.run_until_complete(self.run_scanner(show_progress=False))
                        self.display_scan_results(plays)
                        
                        # Store in session state for other components
                        st.session_state['scanner_results'] = plays
                        st.session_state['scanner_symbols'] = [p.symbol for p in plays]
                        
                    except Exception as e:
                        st.error(f"Scanner error: {e}")
                    finally:
                        loop.close()
        
        with col2:
            if st.button("📊 Show Last Results", use_container_width=True):
                if self.last_scan_results:
                    self.display_scan_results(self.last_scan_results)
                else:
                    st.info("No previous scan results")
        
        with col3:
            if st.button("➕ Add All to System", use_container_width=True):
                symbols = self.get_symbols_for_trading_system()
                if symbols:
                    # Add to session state for trading system pickup
                    if 'manual_symbols' not in st.session_state:
                        st.session_state.manual_symbols = []
                    
                    # Add unique symbols
                    added_count = 0
                    for symbol in symbols:
                        if symbol not in st.session_state.manual_symbols:
                            st.session_state.manual_symbols.append(symbol)
                            added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Added {added_count} symbols to trading system")
                        # Trigger trading system to pick up new symbols
                        st.rerun()
                    else:
                        st.info("All symbols already in trading system")
                else:
                    st.warning("No symbols to add - run scanner first")
        
        # Scanner status
        if self.last_scan_time:
            st.caption(f"Last scan: {self.last_scan_time.strftime('%H:%M:%S')} - "
                      f"{len(self.last_scan_results)} plays found")
        
        # Scanner info
        with st.expander("ℹ️ Scanner Information"):
            st.write("""
            **IBKR Native Scanner Features:**
            - ✅ Real-time IBKR market scanner data
            - ✅ Gap detection (>8% moves)
            - ✅ Volume surge identification
            - ✅ News catalyst analysis
            - ✅ Automatic quality scoring
            - ✅ Direct integration with trading system
            
            **No more copy/paste from ProRealTime!**
            """)
    
    async def cleanup(self):
        """Cleanup scanner resources"""
        if self.scanner:
            await self.scanner.disconnect()

# Convenience function for direct use in Streamlit
def create_scanner_interface(ibkr_adapter: Optional[IBKRAdapter] = None):
    """
    Create scanner interface directly - convenience function
    """
    if 'scanner_integration' not in st.session_state:
        st.session_state.scanner_integration = StreamlitScannerIntegration(ibkr_adapter)
    
    st.session_state.scanner_integration.create_scanner_interface()