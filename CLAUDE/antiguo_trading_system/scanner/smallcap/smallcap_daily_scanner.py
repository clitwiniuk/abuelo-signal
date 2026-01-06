# scanner/smallcap/smallcap_daily_scanner.py
"""
SmallcapDailyScanner - REFACTORED VERSION
Simplified scanner that orchestrates IBKR Native Scanner + Catalyst Analysis
Removes obsolete ProRealTime dependencies and complex manual parsing
"""

import asyncio
import logging
import json
import os
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from .smallcap_context import SmallcapContext
from .catalyst_analyzer import CatalystAnalyzer, CatalystInfo
from .multi_source_news import MultiSourceNewsChecker, NewsSourceConfig

class OpportunityType(Enum):
    """Types of trading opportunities"""
    CATALYST_NEWS = "catalyst_news"
    GAP_BREAKOUT = "gap_breakout"
    # BULL_FLAG_PATTERN = "bull_flag_pattern"
    VOLUME_SURGE = "volume_surge"
    MACDV_SIGNAL = "macdv_signal"
    SHORT_SQUEEZE = "short_squeeze"  # NEW: Short squeeze opportunity
    # DISABLED - Only using 4 core strategies
    # ORB_BREAKOUT = "orb_breakout"
    # VWAP_RECLAIM = "vwap_reclaim"
    # EOD_MOMENTUM = "eod_momentum"

# Import the new IBKR Native Scanner
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.ibkr_native_scanner import IBKRNativeScanner, IBKRScanResult
from adapters.ibkr_adapter import IBKRAdapter

logger = logging.getLogger(__name__)

@dataclass
class SmallcapPlay:
    """Represents a smallcap daily play opportunity"""
    symbol: str
    context: SmallcapContext
    catalyst: Optional[CatalystInfo]  # Now optional - not all plays need catalysts
    quality_score: float
    trading_recommendation: Dict[str, Any]
    scan_timestamp: datetime
    ibkr_rank: int  # Original IBKR scanner rank
    opportunity_type: OpportunityType  # NEW: Type of opportunity
    strategy_targets: List[str]  # NEW: Which strategies can trade this
    bars_1min: list = None  # NEW: 1-minute bars for pattern detection
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'symbol': self.symbol,
            'context': asdict(self.context),
            'catalyst': asdict(self.catalyst) if self.catalyst else None,
            'quality_score': self.quality_score,
            'trading_recommendation': self.trading_recommendation,
            'scan_timestamp': self.scan_timestamp.isoformat(),
            'ibkr_rank': self.ibkr_rank,
            'opportunity_type': self.opportunity_type.value,
            'strategy_targets': self.strategy_targets
        }

class SmallcapDailyScanner:
    """
    REFACTORED SmallcapDailyScanner
    
    Now a lightweight orchestrator that:
    1. Uses IBKRNativeScanner for finding candidates (replaces ProRealTime)
    2. Enhances with CatalystAnalyzer for news intelligence
    3. Creates SmallcapContext for ML integration
    4. Returns ranked SmallcapPlay objects
    
    REMOVED:
    - ProRealTime parsing logic
    - Manual Yahoo Finance API calls
    - Complex volume/float fetching (now handled by IBKR)
    - Fallback programmatic screening
    """
    
    def __init__(self, ibkr_adapter: Optional[IBKRAdapter] = None, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.SmallcapDailyScanner")
        # TEMPORARY: Set info level for detailed analysis logging
        self.logger.setLevel(logging.INFO)

        # Core components - simplified
        self.ibkr_adapter = ibkr_adapter  # Store adapter reference for bar fetching
        self.ibkr_scanner = IBKRNativeScanner(ibkr_adapter)
        # Pass intraday config to CatalystAnalyzer
        catalyst_config = {
            'catalyst_max_age': self.config['catalyst_max_age'],
            'news_age_multipliers': self.config['news_age_multipliers'],
            'fresh_news_threshold': self.config['fresh_news_threshold'],
            'recent_news_threshold': self.config['recent_news_threshold'],
            'stale_news_threshold': self.config['stale_news_threshold'],
            'max_news_age_hours': self.config['max_news_age_hours'],
            'max_news_age_premarket': self.config['max_news_age_premarket']
        }
        self.catalyst_analyzer = CatalystAnalyzer(intraday_config=catalyst_config)
        
        # Initialize multi-source news system with enhanced fallback sources
        news_config = NewsSourceConfig(
            newsapi_key=self.config.get('newsapi_key'),  # Optional NewsAPI key
            finnhub_key=self.config.get('finnhub_key'),  # Free Finnhub key
            polygon_key=self.config.get('polygon_key'),  # Free Polygon key
            max_headlines_per_source=self.config['max_headlines_per_symbol'],
            days_back=7
        )
        self.news_checker = MultiSourceNewsChecker(news_config)
        # Link news checker to scanner for reliability metrics
        self.news_checker._parent_scanner = self
        
        # Cache for news with adaptive refresh system - LEGACY (replaced by TTL cache)
        self.news_cache = {}  # DEPRECATED - using _news_cache with TTL
        self._last_news_cache_refresh = datetime.now()

        # News scanning optimization
        self.news_scan_cooldown = {}  # {symbol: last_scan_time}
        self.news_priority_queue = []  # Symbols without news get priority
        self.min_scan_interval_no_news = 30  # 30 seconds for symbols without news
        self.min_scan_interval_with_news = 300  # 5 minutes for symbols with news
        
        # Import adaptive cache manager
        try:
            from core.adaptive_cache_manager import adaptive_cache_manager
            self._adaptive_cache_manager = adaptive_cache_manager
            self._use_adaptive_cache = True
            self.logger.info("🧠 Adaptive news cache system enabled")
        except ImportError as e:
            # Fallback to fixed interval
            self._news_cache_refresh_interval = 15 * 60  # 15 minutes fallback
            self._use_adaptive_cache = False
            self.logger.warning(f"⚠️ Adaptive cache not available ({e}), using fixed 15min intervals")
        
        # Session tracking with temporal re-analysis capability
        self.processed_tickers_session = {}    # {symbol: last_processed_time} for temporal tracking
        self.active_plays_session = []          # Current active plays for the session
        self.short_squeeze_sent_tickers = set()  # Track tickers that have been sent for short squeeze trading
        self.session_start_time = datetime.now()

        # Memory management - TTL caches with automatic cleanup and adaptive behavior
        from cachetools import TTLCache
        self._news_cache = TTLCache(maxsize=500, ttl=600)  # 10 min TTL, max 500 entries
        self._context_cache = TTLCache(maxsize=200, ttl=300)  # 5 min TTL, max 200 entries
        self._fintel_cache = TTLCache(maxsize=100, ttl=1800)  # 30 min TTL, max 100 entries

        # Adaptive cache system - extend TTL when primary sources fail
        self._source_reliability = {
            'finviz': {'success_rate': 1.0, 'last_check': datetime.now()},
            'finnhub': {'success_rate': 1.0, 'last_check': datetime.now()},
            'yahoo': {'success_rate': 1.0, 'last_check': datetime.now()},
            'polygon': {'success_rate': 1.0, 'last_check': datetime.now()},
            'newsapi': {'success_rate': 1.0, 'last_check': datetime.now()},
        }
        self._adaptive_cache_enabled = True
        
        # OPTIMIZATION 4: Re-analysis configuration - ULTRA-AGGRESSIVE to prevent blocking
        # CRITICAL FIX: Previous values were causing permanent cooldown
        # FURTHER OPTIMIZED: Even more aggressive for real-time performance
        self.reanalysis_cooldown_minutes = 0.5    # Re-analyze after 30s (was 1min, was 3min)
        self.fresh_news_reanalysis_minutes = 0.25  # Re-analyze fresh news after 15s (was 30s, was 2min)
        self.active_plays_cooldown_minutes = 1  # Cooldown for active plays: 1 min (was 2min, was 5min)
        self.max_active_plays_age_minutes = 15  # Auto-remove plays older than 15min (was 30min)
        
        self.logger.info("SmallcapDailyScanner REFACTORED initialized")
        self.logger.info("✅ IBKR Native Scanner integration enabled")
        self.logger.info("✅ Multi-source news system enabled")
        self.logger.info(f"   Available sources: {self.news_checker._get_available_sources()}")
        
        if self._use_adaptive_cache:
            self.logger.info("🔄 Adaptive news cache system enabled - intervals adjust by market period")
        else:
            self.logger.info(f"🔄 Fixed news cache refresh enabled: every {self._news_cache_refresh_interval // 60} minutes")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Optimized configuration for smallcaps intraday trading"""
        return {
            # Quality filters - RELAXED FOR TESTING
            'min_quality_score': 3.0,        # Minimum quality score (0-10) - REDUCED for more opportunities
            'min_catalyst_strength': 2,      # TESTING: Reduced to 2 (was 5) for more catalyst testing
            'max_news_age_hours': 8,         # Maximum news age - REDUCED to 8 hours for intraday
            'max_news_age_premarket': 16,    # Allow overnight news in premarket
            
            # Catalyst-specific aging limits (hours) - TEMPORARILY RELAXED FOR TESTING
            'catalyst_max_age': {
                'FDA': 24,                    # TESTING: Extended to 24h (was 4)
                'M&A': 24,                    # TESTING: Extended to 24h (was 6)
                'EARNINGS': 24,               # TESTING: Extended to 24h (was 8)
                'CONTRACT': 24,               # TESTING: Extended to 24h (was 12)
                'BREAKTHROUGH': 24,           # TESTING: Extended to 24h (was 6)
                'OTHER': 24                   # TESTING: Extended to 24h (was 6)
            },
            
            # News age strength multipliers
            'news_age_multipliers': {
                'fresh': 1.0,                 # 0-2 hours: full strength
                'recent': 0.8,                # 2-6 hours: 80% strength
                'stale': 0.5,                 # 6-12 hours: 50% strength
                'expired': 0.0                # 12+ hours: reject
            },
            
            # Timing thresholds (hours)
            'fresh_news_threshold': 2,        # Fresh news cutoff
            'recent_news_threshold': 6,       # Recent news cutoff
            'stale_news_threshold': 12,       # Stale news cutoff
            
            # Output limits
            'max_plays_per_scan': 15,         # Maximum plays to return
            
            # IBKR scanner limits
            'max_ibkr_results': 50,           # Max from IBKR scanner
            
            # News analysis
            'max_headlines_per_symbol': 5,    # Limit news analysis
            
            # Multi-source news configuration (optional)
            'newsapi_key': None,              # Optional NewsAPI key for premium news access
        }
    
    def _check_and_refresh_news_cache(self) -> bool:
        """
        Check if news cache should be refreshed using adaptive intervals
        Returns True if cache was refreshed
        """
        current_time = datetime.now()
        
        if self._use_adaptive_cache:
            # Use adaptive cache manager
            should_refresh, refresh_info = self._adaptive_cache_manager.should_refresh_cache(
                self._last_news_cache_refresh, current_time
            )
            
            if should_refresh:
                period_name = refresh_info['period_name']
                priority = refresh_info['priority']
                interval = refresh_info['required_interval_minutes']
                cache_size = len(self.news_cache)
                
                self.logger.info(f"🔄 Adaptive news cache refresh triggered ({period_name}, {priority})")
                self.logger.info(f"   ⏱️ Interval: {interval:.1f}min, Time elapsed: {refresh_info['time_since_refresh_minutes']:.1f}min")
                
                self.news_cache.clear()
                self._last_news_cache_refresh = current_time
                
                self.logger.info(f"✅ Adaptive news cache refreshed: cleared {cache_size} entries")
                return True
        else:
            # Fallback to fixed interval
            time_since_refresh = (current_time - self._last_news_cache_refresh).total_seconds()
            
            if time_since_refresh >= self._news_cache_refresh_interval:
                cache_size = len(self.news_cache)
                self.logger.info(f"🔄 Fixed news cache refresh triggered after {time_since_refresh // 60:.1f} minutes")
                
                self.news_cache.clear()
                self._last_news_cache_refresh = current_time
                
                self.logger.info(f"✅ Fixed news cache refreshed: cleared {cache_size} entries")
                return True
        
        return False
    
    def check_and_refresh_cache(self) -> Dict[str, bool]:
        """
        Check and refresh both news cache and IBKR cache if needed
        Returns dict with refresh status for both caches
        """
        results = {
            'news_cache_refreshed': False,
            'ibkr_cache_refreshed': False
        }
        
        # Refresh news cache
        results['news_cache_refreshed'] = self._check_and_refresh_news_cache()
        
        # Refresh IBKR cache if scanner is available
        if hasattr(self, 'ibkr_scanner') and hasattr(self.ibkr_scanner, '_check_and_refresh_cache'):
            results['ibkr_cache_refreshed'] = self.ibkr_scanner._check_and_refresh_cache()
        
        if results['news_cache_refreshed'] or results['ibkr_cache_refreshed']:
            self.logger.info(f"🔄 Cache refresh completed: news={results['news_cache_refreshed']}, ibkr={results['ibkr_cache_refreshed']}")
        
        return results
    
    async def scan_daily_plays(self, force_refresh: bool = False) -> List[SmallcapPlay]:
        """
        MAIN SCANNING FUNCTION - Completely refactored

        Args:
            force_refresh: Force refresh of cached data

        Returns:
            List of SmallcapPlay objects sorted by quality score
        """
        self.logger.info("🔍 Starting REFACTORED SmallcapDailyScanner...")

        # CRITICAL FIX: Clean up old active plays to prevent permanent cooldown
        current_time = datetime.now()
        initial_play_count = len(self.active_plays_session)

        # Remove plays older than max_active_plays_age_minutes
        # Note: SmallcapPlay uses 'scan_timestamp', not 'timestamp'
        self.active_plays_session = [
            play for play in self.active_plays_session
            if (current_time - play.scan_timestamp).total_seconds() / 60 < self.max_active_plays_age_minutes
        ]

        removed_plays = initial_play_count - len(self.active_plays_session)
        if removed_plays > 0:
            self.logger.info(f"🗑️ Removed {removed_plays} stale plays (older than {self.max_active_plays_age_minutes}min)")

        # Check and refresh news cache if needed (15-minute intervals)
        news_cache_refreshed = self._check_and_refresh_news_cache()
        if news_cache_refreshed:
            self.logger.info("🔄 Fresh news data will be fetched due to cache refresh")

        # Clear cache if force refresh requested
        if force_refresh:
            self._news_cache.clear()
            self._context_cache.clear()
            self._fintel_cache.clear()
            self.logger.info("🔄 All TTL caches cleared due to force_refresh=True")

        try:
            # Step 1: Get candidates from IBKR Native Scanner
            self.logger.info("   📊 Fetching candidates from IBKR Native Scanner...")
            ibkr_results = await self.ibkr_scanner.scan_daily_plays(
                max_results=self.config['max_ibkr_results']
            )
            
            if not ibkr_results:
                self.logger.warning("   ⚠️  No results from IBKR scanner")
                return []
            
            self.logger.info(f"   ✅ IBKR found {len(ibkr_results)} candidates")
            
            # Filter tickers based on temporal re-analysis logic
            current_time = datetime.now()
            new_tickers = []
            already_processed = []
            reanalyzed_tickers = []
            
            for result in ibkr_results:
                symbol = result.symbol
                
                # Check if ticker was processed before
                if symbol not in self.processed_tickers_session:
                    # Never processed - definitely analyze
                    new_tickers.append(result)
                else:
                    # Previously processed - check if enough time has passed
                    # Handle backward compatibility with old format (set) vs new format (dict)
                    ticker_data = self.processed_tickers_session[symbol]
                    
                    if isinstance(ticker_data, dict) and 'time' in ticker_data:
                        # New format with timestamp
                        last_processed = ticker_data['time']
                        time_since_processed = (current_time - last_processed).total_seconds() / 60  # minutes
                    else:
                        # Old format (set) or corrupted data - force re-analysis
                        self.logger.warning(f"   🔄 {symbol}: Old format detected, forcing re-analysis")
                        new_tickers.append(result)
                        reanalyzed_tickers.append(symbol)
                        continue
                    
                    # Determine cooldown based on ticker status
                    has_active_play = any(play.symbol == symbol for play in self.active_plays_session)
                    
                    if has_active_play:
                        # Longer cooldown for tickers with active plays
                        required_cooldown = self.active_plays_cooldown_minutes
                    else:
                        # Check if ticker had fresh news for shorter cooldown
                        had_fresh_news = ticker_data.get('had_fresh_news', False)
                        required_cooldown = self.fresh_news_reanalysis_minutes if had_fresh_news else self.reanalysis_cooldown_minutes
                    
                    if time_since_processed >= required_cooldown:
                        # Time for re-analysis
                        new_tickers.append(result)
                        reanalyzed_tickers.append(symbol)
                    else:
                        # Still in cooldown
                        already_processed.append(symbol)
            
            if already_processed:
                self.logger.info(f"   🔄 Skipping {len(already_processed)} tickers in cooldown: {', '.join(already_processed[:5])}{'...' if len(already_processed) > 5 else ''}")
            
            if reanalyzed_tickers:
                self.logger.info(f"   🔄 Re-analyzing {len(reanalyzed_tickers)} tickers after cooldown: {', '.join(reanalyzed_tickers[:5])}{'...' if len(reanalyzed_tickers) > 5 else ''}")
            
            if not new_tickers:
                self.logger.info(f"   ⏸️  All {len(ibkr_results)} tickers in cooldown. Current active plays: {len(self.active_plays_session)}")
                return self.active_plays_session.copy()  # Return existing plays
            
            never_processed = len(new_tickers) - len(reanalyzed_tickers)
            self.logger.info(f"   🆕 Processing {len(new_tickers)} tickers ({never_processed} new, {len(reanalyzed_tickers)} re-analyzed)")
            
            # Step 2: Create MULTI-TRACK opportunities 
            self.logger.info("   🎯 Creating multi-track opportunities...")
            plays = await self._create_multi_track_opportunities(new_tickers)
            
            # Step 3: Sort and limit results
            plays.sort(key=lambda p: p.quality_score, reverse=True)
            final_plays = plays[:self.config['max_plays_per_scan']]
            
            # Update session tracking with timestamps and metadata
            current_time = datetime.now()
            for result in new_tickers:
                # Check if this ticker had fresh news for future re-analysis logic
                had_fresh_news = False
                # Check if any of the plays generated from this ticker had fresh catalyst news
                for play in plays:
                    if (play.symbol == result.symbol and 
                        play.catalyst and 
                        play.catalyst.age_hours <= 1.0):
                        had_fresh_news = True
                        break
                
                self.processed_tickers_session[result.symbol] = {
                    'time': current_time,
                    'had_fresh_news': had_fresh_news
                }
            
            # Update active plays (add new ones, keep existing ones)
            for play in final_plays:
                # Only add if not already in active plays
                if not any(existing.symbol == play.symbol for existing in self.active_plays_session):
                    self.active_plays_session.append(play)
            
            # Session statistics
            session_duration = datetime.now() - self.session_start_time
            self.logger.info(f"🎯 REFACTORED scanner result: {len(final_plays)} new high-quality plays")
            self.logger.info(f"📊 Session stats: {len(self.processed_tickers_session)} total tickers processed, {len(self.active_plays_session)} active plays, running {session_duration}")
            
            # Return combination of new plays and existing active plays
            all_active_plays = self.active_plays_session.copy()
            all_active_plays.sort(key=lambda p: p.quality_score, reverse=True)
            
            return all_active_plays[:self.config['max_plays_per_scan']]
            
        except Exception as e:
            self.logger.error(f"Error in scan_daily_plays: {e}")
            return []
    
    async def _create_multi_track_opportunities(self, ibkr_results: List[IBKRScanResult]) -> List[SmallcapPlay]:
        """
        OPTIMIZED: Create multiple opportunity types for each ticker with PARALLEL fetching
        Each ticker can trigger multiple strategies, not just catalyst-driven

        OPTIMIZATION: Parallelize news + bars fetching to reduce from 3min to 30sec cycles
        """
        all_plays = []

        # OPTIMIZATION 1: Get news data for all tickers in PARALLEL (not sequential)
        symbols = [result.symbol for result in ibkr_results]
        self.logger.info(f"🔄 OPTIMIZATION: Parallel news fetching for {len(symbols)} symbols")
        news_data, cache_hits = await self._get_news_batch(symbols)

        # OPTIMIZATION 2: Parallel bars fetching for all symbols that pass initial analysis
        # CACHE INCREMENTAL: Check bars cache first
        bars_tasks = {}
        bars_results = {}
        bars_cache_hits = 0
        bars_cache_misses = 0

        # Initialize bars_results for all symbols to avoid KeyError
        for result in ibkr_results:
            bars_results[result.symbol] = []

        for result in ibkr_results:
            symbol = result.symbol
            self.logger.info(f"   🎯 Analyzing {symbol} for multi-track opportunities...")
            self.logger.info(f"   📊 IBKR Data: price=${result.current_price:.2f}, gap={result.gap_percentage:.1f}%, volume={result.volume:,}, avg_vol={result.avg_volume:,}, mcap=${result.market_cap/1e6:.0f}M")

            # Analyze for each opportunity type
            opportunities = []

            # 1. CATALYST NEWS opportunity
            catalyst_play = await self._analyze_catalyst_opportunity(result, news_data.get(symbol, []))
            if catalyst_play:
                opportunities.append(catalyst_play)
                self.logger.info(f"   📰 {symbol}: CATALYST opportunity detected")
            else:
                self.logger.info(f"   ❌ {symbol}: CATALYST opportunity NOT detected")

            # 2. GAP BREAKOUT opportunity
            gap_play = await self._analyze_gap_opportunity(result)
            if gap_play:
                opportunities.append(gap_play)
                self.logger.info(f"   📈 {symbol}: GAP BREAKOUT opportunity detected")
            else:
                self.logger.info(f"   ❌ {symbol}: GAP BREAKOUT opportunity NOT detected")

            # DISABLED - 3. BULL FLAG opportunity (momentum continuation patterns)
            # bull_flag_play = await self._analyze_bull_flag_opportunity(result)
            # if bull_flag_play:
            #     opportunities.append(bull_flag_play)
            #     self.logger.info(f"   🏴 {symbol}: BULL FLAG opportunity detected")
            # else:
            #     self.logger.info(f"   ❌ {symbol}: BULL FLAG opportunity NOT detected")

            # 4. VOLUME SURGE opportunity
            volume_play = await self._analyze_volume_opportunity(result)
            if volume_play:
                opportunities.append(volume_play)
                self.logger.info(f"   💥 {symbol}: VOLUME SURGE opportunity detected")
            else:
                self.logger.info(f"   ❌ {symbol}: VOLUME SURGE opportunity NOT detected")

            # 5. MACDV SIGNAL opportunity
            macdv_play = await self._analyze_macdv_opportunity(result)
            if macdv_play:
                opportunities.append(macdv_play)
                self.logger.info(f"   📉 {symbol}: MACDV SIGNAL opportunity detected")
            else:
                self.logger.info(f"   ❌ {symbol}: MACDV SIGNAL opportunity NOT detected")

            # 6. SHORT SQUEEZE opportunity (NEW)
            short_squeeze_play = await self._analyze_short_squeeze_opportunity(result)
            if short_squeeze_play:
                opportunities.append(short_squeeze_play)
                self.logger.info(f"   🐻 {symbol}: SHORT SQUEEZE opportunity detected")
            else:
                self.logger.info(f"   ❌ {symbol}: SHORT SQUEEZE opportunity NOT detected")

            # OPTIMIZATION 3: Queue bars fetching for symbols with opportunities (parallel + cache)
            if opportunities and self.ibkr_adapter:
                # CACHE INCREMENTAL: Check bars cache first
                bars_cache_key = f"bars_{symbol}"
                if bars_cache_key in self._context_cache:
                    bars_results[symbol] = self._context_cache[bars_cache_key]
                    bars_cache_hits += 1
                    self.logger.debug(f"💾 {symbol}: Bars cache hit - using cached bars")
                else:
                    try:
                        from ib_insync import Stock
                        contract = Stock(symbol, 'SMART', 'USD')
                        # Create task for parallel execution
                        task = self.ibkr_adapter.ib.reqHistoricalDataAsync(
                            contract,
                            endDateTime='',
                            durationStr='1 D',
                            barSizeSetting='1 min',
                            whatToShow='TRADES',
                            useRTH=False
                        )
                        bars_tasks[symbol] = task
                        bars_cache_misses += 1
                    except Exception as e:
                        self.logger.warning(f"   ⚠️ {symbol}: Could not queue bars fetch - {e}")
                        bars_results[symbol] = []

            # Add all valid opportunities for this ticker
            all_plays.extend(opportunities)

            if opportunities:
                types = [opp.opportunity_type.value for opp in opportunities]
                self.logger.info(f"   ✅ {symbol}: {len(opportunities)} opportunities created ({', '.join(types)})")
            else:
                # SHORT SQUEEZE INTEGRATION: Check for short squeeze opportunity when no other opportunities detected
                # Only send once per ticker per session to avoid duplicate trading
                if symbol not in self.short_squeeze_sent_tickers:
                    self.logger.info(f"   ❌ {symbol}: No opportunities detected - checking for SHORT SQUEEZE potential")
                    short_squeeze_play = await self._analyze_short_squeeze_opportunity(result)
                    if short_squeeze_play:
                        opportunities.append(short_squeeze_play)
                        self.logger.info(f"   🐻 {symbol}: SHORT SQUEEZE opportunity detected (fallback)")
                        # Send signal to Redis for trader_main (only once per ticker)
                        await self._send_short_squeeze_signal(symbol, short_squeeze_play)
                        # Mark as sent to prevent duplicate signals
                        self.short_squeeze_sent_tickers.add(symbol)
                        self.logger.info(f"   📤 {symbol}: Short squeeze signal sent (first time for this ticker)")
                    else:
                        self.logger.info(f"   ❌ {symbol}: No opportunities detected (including short squeeze)")
                else:
                    self.logger.info(f"   ⏭️ {symbol}: Skipping short squeeze check (already sent signal this session)")

        # OPTIMIZATION 4: Execute all bars fetching in parallel + CACHE INCREMENTAL
        if bars_tasks:
            self.logger.info(f"🔄 OPTIMIZATION: Parallel bars fetching for {len(bars_tasks)} symbols")
            self.logger.info(f"💾 CACHE INCREMENTAL: {bars_cache_hits} bars cache hits, {bars_cache_misses} bars cache misses")
            try:
                # Execute all bars tasks in parallel
                bars_results_list = await asyncio.gather(*bars_tasks.values(), return_exceptions=True)

                # Process results and update cache
                for i, (symbol, task) in enumerate(bars_tasks.items()):
                    result = bars_results_list[i]
                    if isinstance(result, Exception):
                        self.logger.warning(f"   ⚠️ {symbol}: Bars fetch failed - {result}")
                        bars_results[symbol] = []
                    else:
                        bars = result
                        if bars:
                            # Convert BarData objects to dicts for JSON serialization
                            bars_1min = [{
                                'timestamp': bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                                'open': float(bar.open),
                                'high': float(bar.high),
                                'low': float(bar.low),
                                'close': float(bar.close),
                                'volume': int(bar.volume)
                            } for bar in bars]
                            bars_results[symbol] = bars_1min
                            # CACHE INCREMENTAL: Store in TTL cache
                            bars_cache_key = f"bars_{symbol}"
                            self._context_cache[bars_cache_key] = bars_1min
                            self.logger.debug(f"   📊 {symbol}: Fetched {len(bars_1min)} 1-min bars (cached)")
                        else:
                            bars_results[symbol] = []
            except Exception as e:
                self.logger.error(f"Error in parallel bars fetching: {e}")
                # Fallback: empty bars for all
                bars_results = {symbol: [] for symbol in bars_tasks.keys()}

        # Assign bars to all opportunities for each symbol
        for play in all_plays:
            symbol = play.symbol
            play.bars_1min = bars_results.get(symbol, [])

        # Log final optimization statistics
        total_symbols = len(ibkr_results)
        news_cache_hit_rate = cache_hits / total_symbols if total_symbols > 0 else 0
        bars_cache_hit_rate = bars_cache_hits / max(1, bars_cache_hits + bars_cache_misses)

        self.logger.info(f"🚀 OPTIMIZATION SUMMARY:")
        self.logger.info(f"   📊 Total symbols processed: {total_symbols}")
        self.logger.info(f"   💾 News cache hit rate: {news_cache_hit_rate:.1%} ({cache_hits}/{total_symbols})")
        self.logger.info(f"   📈 Bars cache hit rate: {bars_cache_hit_rate:.1%} ({bars_cache_hits}/{bars_cache_hits + bars_cache_misses})")
        self.logger.info(f"   ⚡ Parallel operations: news + bars fetching")
        self.logger.info(f"   🎯 Expected performance: 3min → 30sec cycle time")

        self.logger.info(f"🎯 OPTIMIZED multi-track analysis complete: {len(all_plays)} total opportunities")
        return all_plays
    
    async def _analyze_catalyst_opportunity(self, result: IBKRScanResult, headlines: List) -> Optional[SmallcapPlay]:
        """Analyze for CATALYST NEWS opportunity"""
        try:
            self.logger.info(f"   📰 {result.symbol}: CATALYST analysis - {len(headlines)} headlines")
            if not headlines:
                self.logger.info(f"   ❌ {result.symbol}: CATALYST - No headlines found")
                return None
                
            # Use existing catalyst analyzer
            catalyst = self.catalyst_analyzer.analyze_multiple_headlines(headlines)
            self.logger.info(f"   📊 {result.symbol}: CATALYST - type={catalyst.catalyst_type}, strength={catalyst.strength}, age={catalyst.age_hours:.1f}h")

            # Apply catalyst filters (RELAXED FOR TESTING)
            strength_ok = catalyst.strength >= 1  # REDUCED from min_catalyst_strength
            catalyst_max_age = self.config['catalyst_max_age'].get(catalyst.catalyst_type, 48)  # INCREASED to 48h
            age_ok = catalyst.age_hours <= catalyst_max_age

            self.logger.info(f"   🔍 {result.symbol}: CATALYST filters - strength_ok={strength_ok} ({catalyst.strength}>=1), age_ok={age_ok} ({catalyst.age_hours:.1f}<={catalyst_max_age})")

            if not (strength_ok and age_ok):
                self.logger.debug(f"   ❌ {result.symbol}: CATALYST - Failed filters (strength={catalyst.strength}, age={catalyst.age_hours:.1f}h)")
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # Calculate quality score (catalyst-focused)
            quality_score = self._calculate_catalyst_quality_score(result, catalyst, context)
            
            if quality_score >= self.config['min_quality_score']:
                trading_rec = self.catalyst_analyzer.get_catalyst_trading_recommendation(catalyst)
                
                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=catalyst,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.CATALYST_NEWS,
                    strategy_targets=['catalyst_momentum']
                )
                
        except Exception as e:
            self.logger.error(f"Error analyzing catalyst opportunity for {result.symbol}: {e}")
        
        return None
    
    async def _analyze_gap_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for GAP BREAKOUT opportunity"""
        try:
            self.logger.debug(f"   📈 {result.symbol}: GAP analysis - gap={result.gap_percentage:.1f}%, price=${result.current_price:.2f}")

            # Check if significant gap (RELAXED)
            if result.gap_percentage < 3.0:  # Minimum 3% gap (REDUCED from 8%)
                self.logger.debug(f"   ❌ {result.symbol}: GAP - Gap too small ({result.gap_percentage:.1f}% < 3.0%)")
                return None

            # Create context
            context = await self._create_context(result)
            if not context:
                self.logger.debug(f"   ❌ {result.symbol}: GAP - Could not create context")
                return None

            # Gap-specific quality checks (RELAXED)
            price_ok = 2.0 <= context.current_price <= 15.0
            volume_ok = context.premarket_volume_ratio >= 1.5  # REDUCED from 2.0
            self.logger.debug(f"   🔍 {result.symbol}: GAP checks - price_ok={price_ok} (${context.current_price:.2f} in 2-15), volume_ok={volume_ok} (ratio={context.premarket_volume_ratio:.1f} >= 1.5)")
            if (context.current_price < 2.0 or context.current_price > 15.0 or
                context.premarket_volume_ratio < 1.5):
                self.logger.debug(f"   ❌ {result.symbol}: GAP - Failed quality checks")
                return None

            # Calculate quality score (gap-focused)
            quality_score = self._calculate_gap_quality_score(result, context)
            self.logger.debug(f"   📊 {result.symbol}: GAP quality_score={quality_score:.1f} (need >= {self.config['min_quality_score']})")

            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'gap_breakout',
                    'risk_level': 'HIGH' if result.gap_percentage > 15 else 'MEDIUM',
                    'time_horizon': 'intraday'
                }

                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,  # No catalyst needed for technical gap
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.GAP_BREAKOUT,
                    strategy_targets=['gap_go']
                )
            else:
                self.logger.debug(f"   ❌ {result.symbol}: GAP - Quality score too low")

        except Exception as e:
            self.logger.error(f"Error analyzing gap opportunity for {result.symbol}: {e}")

        return None

    async def _analyze_bull_flag_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for BULL FLAG opportunity (momentum continuation patterns)"""
        try:
            self.logger.debug(f"   🏴 {result.symbol}: BULL FLAG analysis - gap={result.gap_percentage:.1f}%, price=${result.current_price:.2f}")
            # Bull Flag criteria: Small-medium gap (1.5-3%) with good volume and bullish trend
            gap_pct = abs(result.gap_percentage)
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 0

            gap_ok = 1.5 <= gap_pct <= 3.0
            volume_ok = 1.8 <= volume_ratio <= 5.0
            price_ok = 2.0 <= result.current_price <= 15.0
            bullish_ok = result.gap_percentage > 0

            self.logger.debug(f"   🔍 {result.symbol}: BULL FLAG checks - gap_ok={gap_ok} ({gap_pct:.1f}% in 1.5-3), volume_ok={volume_ok} ({volume_ratio:.1f}x in 1.8-5), price_ok={price_ok} (${result.current_price:.2f} in 2-15), bullish_ok={bullish_ok} (gap > 0)")

            if (1.5 <= gap_pct <= 3.0 and                    # Small to medium gap
                1.8 <= volume_ratio <= 5.0 and              # Good volume but not explosive
                2.0 <= result.current_price <= 15.0 and     # Suitable price range for smallcaps
                result.gap_percentage > 0):                  # Must be positive gap (bullish)

                # Create context
                context = await self._create_context_for_result(result)
                if not context:
                    return None

                # Calculate quality score for bull flag
                quality_score = 50.0  # Base score

                # Add points for gap size (sweet spot is 2-2.5%)
                if 2.0 <= gap_pct <= 2.5:
                    quality_score += 25.0
                elif 1.8 <= gap_pct < 2.0 or 2.5 < gap_pct <= 2.8:
                    quality_score += 15.0

                # Add points for volume (sweet spot is 2-3x)
                if 2.0 <= volume_ratio <= 3.0:
                    quality_score += 20.0
                elif 1.8 <= volume_ratio < 2.0 or 3.0 < volume_ratio <= 4.0:
                    quality_score += 10.0

                # Add points for price range (optimal 5-10)
                if 5.0 <= result.current_price <= 10.0:
                    quality_score += 15.0
                elif 3.0 <= result.current_price < 5.0 or 10.0 < result.current_price <= 12.0:
                    quality_score += 8.0

                if quality_score >= self.config['min_quality_score']:
                    return SmallcapPlay(
                        symbol=result.symbol,
                        context=context,
                        catalyst=None,
                        quality_score=quality_score,
                        trading_recommendation=f"Bull Flag pattern: {gap_pct:.1f}% gap with {volume_ratio:.1f}x volume",
                        scan_timestamp=datetime.now(),
                        ibkr_rank=result.rank,
                        opportunity_type=OpportunityType.BULL_FLAG_PATTERN,
                        strategy_targets=['bull_flag']
                    )

        except Exception as e:
            self.logger.error(f"Error analyzing bull flag opportunity for {result.symbol}: {e}")

        return None

    async def _analyze_orb_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for ORB BREAKOUT opportunity"""
        try:
            # ORB requires specific volume and price conditions
            if (result.current_price < 2.0 or result.current_price > 12.0 or
                result.volume == 0 or result.avg_volume == 0):
                return None
                
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 0
            if volume_ratio < 2.0:  # Minimum 2x volume
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # Calculate quality score (ORB-focused)
            quality_score = self._calculate_orb_quality_score(result, context)
            
            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'orb_breakout',
                    'risk_level': 'MEDIUM',
                    'time_horizon': 'intraday',
                    'volume_confirmation': True
                }
                
                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.ORB_BREAKOUT,
                    strategy_targets=['orb']
                )
                
        except Exception as e:
            self.logger.error(f"Error analyzing ORB opportunity for {result.symbol}: {e}")
            
        return None
    
    async def _analyze_volume_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for VOLUME SURGE opportunity"""
        try:
            self.logger.debug(f"   💥 {result.symbol}: VOLUME analysis - volume={result.volume:,}, avg={result.avg_volume:,}")
            if result.volume == 0 or result.avg_volume == 0:
                self.logger.debug(f"   ❌ {result.symbol}: VOLUME - Zero volume data")
                return None

            volume_ratio = result.volume / result.avg_volume
            self.logger.debug(f"   📊 {result.symbol}: VOLUME ratio = {volume_ratio:.1f}x")
            if volume_ratio < 3.0:  # Explosive volume needs 3x+ (REDUCED from 5.0)
                self.logger.debug(f"   ❌ {result.symbol}: VOLUME - Ratio too low ({volume_ratio:.1f}x < 3.0x)")
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # Calculate quality score (volume-focused)
            quality_score = self._calculate_volume_quality_score(result, context)
            
            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'volume_explosion',
                    'risk_level': 'HIGH',  # Volume explosions are volatile
                    'time_horizon': 'short_term'
                }
                
                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.VOLUME_SURGE,
                    strategy_targets=['explosive_volume']
                )
                
        except Exception as e:
            self.logger.error(f"Error analyzing volume opportunity for {result.symbol}: {e}")
            
        return None
    
    async def _analyze_vwap_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for VWAP RECLAIM opportunity"""
        try:
            # Basic filters for VWAP strategy
            if (result.current_price < 2.0 or result.current_price > 15.0):
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # VWAP-specific checks (simplified)
            if context.premarket_volume_ratio < 1.5:
                return None
                
            # Calculate quality score (VWAP-focused)
            quality_score = self._calculate_vwap_quality_score(result, context)
            
            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'vwap_reclaim',
                    'risk_level': 'MEDIUM',
                    'time_horizon': 'intraday'
                }
                
                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.VWAP_RECLAIM,
                    strategy_targets=['vwap_smallcaps']
                )
                
        except Exception as e:
            self.logger.error(f"Error analyzing VWAP opportunity for {result.symbol}: {e}")
            
        return None
    
    async def _analyze_macdv_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for MACDV SIGNAL opportunity"""
        try:
            self.logger.debug(f"   📉 {result.symbol}: MACDV analysis - price=${result.current_price:.2f}, gap={result.gap_percentage:.1f}%, vol={result.volume:,}")
            # Basic filters for MACDV strategy
            price_ok = 2.0 <= result.current_price <= 15.0
            self.logger.debug(f"   🔍 {result.symbol}: MACDV checks - price_ok={price_ok} (${result.current_price:.2f} in 2-15)")
            if (result.current_price < 2.0 or result.current_price > 15.0):
                self.logger.debug(f"   ❌ {result.symbol}: MACDV - Price out of range (${result.current_price:.2f} not in 2-15)")
                return None

            # Create context
            context = await self._create_context(result)
            if not context:
                self.logger.debug(f"   ❌ {result.symbol}: MACDV - Could not create context")
                return None

            # MACDV requires moderate volume
            volume_ok = context.premarket_volume_ratio >= 1.5
            self.logger.debug(f"   🔍 {result.symbol}: MACDV volume check - volume_ok={volume_ok} (ratio={context.premarket_volume_ratio:.1f} >= 1.5)")
            if context.premarket_volume_ratio < 1.5:
                self.logger.debug(f"   ❌ {result.symbol}: MACDV - Volume too low ({context.premarket_volume_ratio:.1f} < 1.5)")
                return None

            # Calculate quality score (MACDV-focused)
            quality_score = self._calculate_macdv_quality_score(result, context)
            self.logger.debug(f"   📊 {result.symbol}: MACDV quality_score={quality_score:.1f} (need >= {self.config['min_quality_score']})")

            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'macdv_signal',
                    'risk_level': 'MEDIUM',
                    'time_horizon': 'intraday'
                }

                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.MACDV_SIGNAL,
                    strategy_targets=['macdv_smallcaps']
                )
            else:
                self.logger.debug(f"   ❌ {result.symbol}: MACDV - Quality score too low")

        except Exception as e:
            self.logger.error(f"Error analyzing MACDV opportunity for {result.symbol}: {e}")

        return None

    async def _analyze_short_squeeze_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for SHORT SQUEEZE opportunity"""
        try:
            self.logger.debug(f"   🐻 {result.symbol}: SHORT SQUEEZE analysis - price=${result.current_price:.2f}, gap={result.gap_percentage:.1f}%, vol={result.volume:,}")

            # Check if ticker appears in recent Fintel CSV files
            fintel_found = await self._check_fintel_short_squeeze(result.symbol)
            if not fintel_found:
                self.logger.debug(f"   ❌ {result.symbol}: SHORT SQUEEZE - Not found in recent Fintel data")
                return None

            # Basic filters for short squeeze strategy
            price_ok = 2.0 <= result.current_price <= 20.0  # Slightly higher range for short squeezes
            self.logger.debug(f"   🔍 {result.symbol}: SHORT SQUEEZE checks - price_ok={price_ok} (${result.current_price:.2f} in 2-20), fintel_found={fintel_found}")

            if not price_ok:
                self.logger.debug(f"   ❌ {result.symbol}: SHORT SQUEEZE - Price out of range (${result.current_price:.2f} not in 2-20)")
                return None

            # Create context
            context = await self._create_context(result)
            if not context:
                self.logger.debug(f"   ❌ {result.symbol}: SHORT SQUEEZE - Could not create context")
                return None

            # Short squeezes often have moderate volume
            volume_ok = context.premarket_volume_ratio >= 1.2
            self.logger.debug(f"   🔍 {result.symbol}: SHORT SQUEEZE volume check - volume_ok={volume_ok} (ratio={context.premarket_volume_ratio:.1f} >= 1.2)")
            if not volume_ok:
                self.logger.debug(f"   ❌ {result.symbol}: SHORT SQUEEZE - Volume too low ({context.premarket_volume_ratio:.1f} < 1.2)")
                return None

            # Calculate quality score (short squeeze-focused)
            quality_score = self._calculate_short_squeeze_quality_score(result, context)
            self.logger.debug(f"   📊 {result.symbol}: SHORT SQUEEZE quality_score={quality_score:.1f} (need >= {self.config['min_quality_score']})")

            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'short_squeeze',
                    'risk_level': 'HIGH',  # Short squeezes are volatile
                    'time_horizon': 'swing',
                    'fintel_confirmed': True
                }

                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.SHORT_SQUEEZE,
                    strategy_targets=['swing_short_squeeze']
                )
            else:
                self.logger.debug(f"   ❌ {result.symbol}: SHORT SQUEEZE - Quality score too low")

        except Exception as e:
            self.logger.error(f"Error analyzing short squeeze opportunity for {result.symbol}: {e}")

        return None
    
    async def _analyze_eod_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for EOD MOMENTUM opportunity"""
        try:
            # EOD strategy is time-sensitive - only activate late in session
            current_time = datetime.now().time()
            eod_start = datetime.strptime("15:30:00", "%H:%M:%S").time()
            
            if current_time < eod_start:
                return None  # Not EOD time yet
                
            # Basic filters
            if (result.current_price < 1.0 or result.current_price > 20.0):
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # Calculate quality score (EOD-focused)
            quality_score = self._calculate_eod_quality_score(result, context)
            
            if quality_score >= self.config['min_quality_score']:
                trading_rec = {
                    'action': 'LONG',
                    'entry_type': 'eod_momentum',
                    'risk_level': 'HIGH',  # EOD plays are riskier
                    'time_horizon': 'short_term'
                }
                
                return SmallcapPlay(
                    symbol=result.symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation=trading_rec,
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.EOD_MOMENTUM,
                    strategy_targets=['eod_momentum']
                )
                
        except Exception as e:
            self.logger.error(f"Error analyzing EOD opportunity for {result.symbol}: {e}")
            
        return None
    
    def reset_session_cache(self):
        """Reset session tracking - call at start of new trading day or when needed"""
        self.processed_tickers_session.clear()
        self.active_plays_session.clear()
        self.short_squeeze_sent_tickers.clear()  # Reset short squeeze tracking for new session
        self.session_start_time = datetime.now()

        # Also refresh news cache and scanning optimization when resetting session
        self._news_cache.clear()
        self._context_cache.clear()
        self._fintel_cache.clear()
        self.news_scan_cooldown.clear()
        self.news_priority_queue.clear()
        self._last_news_cache_refresh = datetime.now()

        self.logger.info("🔄 OPTIMIZED: Session cache reset - ready for new tickers")
        self.logger.info("🔄 OPTIMIZED: News cache and scanning optimization reset for new session")
        self.logger.info("🔄 OPTIMIZED: Short squeeze sent tickers reset for new session")
        self.logger.info(f"   ⚡ ULTRA-FAST Re-analysis: {self.reanalysis_cooldown_minutes}min standard, {self.fresh_news_reanalysis_minutes}min fresh news, {self.active_plays_cooldown_minutes}min active plays")
        self.logger.info(f"   News scanning: {self.min_scan_interval_no_news}s for symbols without news, {self.min_scan_interval_with_news}s for symbols with news")
    
    def force_cache_refresh(self):
        """Manually trigger cache refresh - useful for testing"""
        # Force refresh news cache and scanning optimization
        news_cache_size = len(self._news_cache)
        context_cache_size = len(self._context_cache)
        fintel_cache_size = len(self._fintel_cache)
        cooldown_count = len(self.news_scan_cooldown)
        priority_count = len(self.news_priority_queue)

        self._news_cache.clear()
        self._context_cache.clear()
        self._fintel_cache.clear()
        self.news_scan_cooldown.clear()
        self.news_priority_queue.clear()
        self._last_news_cache_refresh = datetime.now()

        # Force refresh IBKR scanner cache if available
        if hasattr(self.ibkr_scanner, '_price_cache'):
            ibkr_cache_sizes = {
                'price': len(self.ibkr_scanner._price_cache),
                'volume': len(self.ibkr_scanner._volume_cache),
                'fundamental': len(self.ibkr_scanner._fundamental_cache)
            }
            self.ibkr_scanner._price_cache.clear()
            self.ibkr_scanner._volume_cache.clear()
            self.ibkr_scanner._fundamental_cache.clear()
            self.ibkr_scanner._last_cache_refresh = datetime.now()

            total_ibkr_cleared = sum(ibkr_cache_sizes.values())
            self.logger.info(f"🔄 Manual cache refresh: cleared {news_cache_size} news, {context_cache_size} context, {fintel_cache_size} fintel entries, {cooldown_count} cooldowns, {priority_count} priority items + {total_ibkr_cleared} IBKR entries")
        else:
            self.logger.info(f"🔄 Manual cache refresh: cleared {news_cache_size} news, {context_cache_size} context, {fintel_cache_size} fintel entries, {cooldown_count} cooldowns, {priority_count} priority items")

        return True
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics including memory usage and source reliability"""
        session_duration = datetime.now() - self.session_start_time
        return {
            'processed_tickers_count': len(self.processed_tickers_session),
            'active_plays_count': len(self.active_plays_session),
            'session_duration': str(session_duration),
            'processed_tickers': list(self.processed_tickers_session.keys()),
            'active_plays_symbols': [play.symbol for play in self.active_plays_session],
            'memory_stats': {
                'news_cache_size': len(self._news_cache),
                'context_cache_size': len(self._context_cache),
                'fintel_cache_size': len(self._fintel_cache),
                'short_squeeze_sent_count': len(self.short_squeeze_sent_tickers)
            },
            'source_reliability': self._source_reliability
        }

    def update_source_reliability(self, source_name: str, success: bool):
        """Update reliability metrics for news sources"""
        if source_name not in self._source_reliability:
            return

        current = self._source_reliability[source_name]
        # Simple exponential moving average for success rate
        alpha = 0.1  # Weight for new measurement
        current['success_rate'] = (1 - alpha) * current['success_rate'] + alpha * (1.0 if success else 0.0)
        current['last_check'] = datetime.now()

        # Adaptive cache behavior: extend TTL when primary sources fail
        if self._adaptive_cache_enabled and source_name == 'finviz' and not success:
            # Extend news cache TTL when Finviz fails
            if hasattr(self, '_news_cache') and hasattr(self._news_cache, '_ttl'):
                # Temporarily extend cache TTL to 20 minutes when primary source fails
                self._news_cache._ttl = 1200  # 20 minutes
                self.logger.info("🔄 Adaptive cache: Extended news cache TTL to 20min due to Finviz failure")
    
    async def _analyze_catalysts_batch(self, ibkr_results: List[IBKRScanResult]) -> List[tuple]:
        """
        Batch analyze catalysts for IBKR results
        Much more efficient than individual calls
        """
        catalyst_results = []
        
        # Get symbols list
        symbols = [result.symbol for result in ibkr_results]
        
        # Batch get news for all symbols
        news_data, _ = await self._get_news_batch(symbols)
        
        # Analyze catalysts
        for result in ibkr_results:
            headlines = news_data.get(result.symbol, [])
            catalyst = self.catalyst_analyzer.analyze_multiple_headlines(headlines)
            
            # TEMP DEBUG: Log catalyst analysis for each symbol (using INFO)
            self.logger.info(f"   🔍 {result.symbol}: strength={catalyst.strength}, age={catalyst.age_hours:.1f}h, type={catalyst.catalyst_type}")
            
            # Apply intraday catalyst filters with type-specific aging
            strength_ok = catalyst.strength >= self.config['min_catalyst_strength']
            
            # Use catalyst-specific age limit instead of global
            catalyst_max_age = self.config['catalyst_max_age'].get(catalyst.catalyst_type, 6)
            age_ok = catalyst.age_hours <= catalyst_max_age
            
            if strength_ok and age_ok:
                catalyst_results.append((result, catalyst))
                self.logger.info(f"   ✅ {result.symbol}: PASSED catalyst filters ({catalyst.catalyst_type}, {catalyst.strength}str, {catalyst.age_hours:.1f}h)")
            else:
                self.logger.info(f"   ❌ {result.symbol}: FAILED catalyst filters - {catalyst.catalyst_type}: strength={catalyst.strength} (need ≥{self.config['min_catalyst_strength']}), age={catalyst.age_hours:.1f}h (need ≤{catalyst_max_age}h)")
                
        self.logger.info(f"   📰 {len(catalyst_results)}/{len(ibkr_results)} passed catalyst filters (DEBUG MODE)")
        
        # TEMP DEBUG: If no results, show first few failed ones
        if len(catalyst_results) == 0 and ibkr_results:
            self.logger.warning("   🚨 NO CATALYST RESULTS - showing first 3 failed examples:")
            for i, result in enumerate(ibkr_results[:3]):
                headlines = news_data.get(result.symbol, [])
                catalyst = self.catalyst_analyzer.analyze_multiple_headlines(headlines)
                catalyst_max_age = self.config['catalyst_max_age'].get(catalyst.catalyst_type, 6)
                self.logger.warning(f"     {i+1}. {result.symbol}: {catalyst.catalyst_type} strength={catalyst.strength} (need ≥{self.config['min_catalyst_strength']}), age={catalyst.age_hours:.1f}h (need ≤{catalyst_max_age}h)")
                if headlines:
                    self.logger.warning(f"        Headlines: {headlines[0][0][:100]}...")
                else:
                    self.logger.warning(f"        No headlines found")
        
        self.logger.info(f"   📰 {len(catalyst_results)}/{len(ibkr_results)} passed catalyst filters")
        
        return catalyst_results
    
    async def _get_news_batch(self, symbols: List[str]) -> tuple[Dict[str, List[tuple]], int]:
        """
        OPTIMIZED Multi-source news fetching with intelligent scanning and CACHE INCREMENTAL

        Optimization strategy:
        1. Prioritize symbols without news or with stale news
        2. Apply cooldown periods based on news availability
        3. Reduce API calls for symbols with recent fresh news
        4. Focus scanning resources on high-potential opportunities
        5. CACHE INCREMENTAL: Only refetch changed data, not everything

        Sources (priority order):
        1. Finviz (primary) - Best quality financial news
        2. YahooQuery (secondary) - Reliable fallback
        3. NewsAPI (optional) - Professional aggregation
        4. SEC EDGAR (specialized) - Official filings

        Returns: Dict[symbol, List[(headline, age_hours)]]
        """
        current_time = datetime.now()
        symbols_to_scan = []
        symbols_skipped = []

        # CACHE INCREMENTAL OPTIMIZATION: Check TTL cache first
        complete_results = {}
        cache_hits = 0
        cache_misses = 0

        for symbol in symbols:
            # Check TTL cache first
            cache_key = f"news_{symbol}"
            if cache_key in self._news_cache:
                cached_data = self._news_cache[cache_key]
                complete_results[symbol] = cached_data
                cache_hits += 1
                self.logger.debug(f"💾 {symbol}: News cache hit - using cached data")
            else:
                complete_results[symbol] = []  # Will be populated if scanned
                cache_misses += 1

        self.logger.info(f"💾 CACHE INCREMENTAL: {cache_hits} cache hits, {cache_misses} cache misses")

        # Only scan symbols not in cache or cache expired
        symbols_to_scan = [symbol for symbol in symbols if not complete_results[symbol]]

        if not symbols_to_scan:
            self.logger.info("⚡ All symbols served from cache - no API calls needed")
            return complete_results, cache_hits

        # OPTIMIZATION: Filter remaining symbols based on scanning cooldown
        symbols_to_scan_filtered = []
        symbols_skipped_cooldown = []

        for symbol in symbols_to_scan:
            last_scan = self.news_scan_cooldown.get(symbol)
            has_cached_news = symbol in self.news_cache and self.news_cache[symbol]

            if last_scan is None:
                # Never scanned - high priority
                symbols_to_scan_filtered.append(symbol)
                self.logger.debug(f"🆕 {symbol}: First scan (high priority)")
            else:
                time_since_scan = (current_time - last_scan).total_seconds()

                # Determine scan interval based on news availability
                if has_cached_news:
                    # Has news - use longer interval
                    required_interval = self.min_scan_interval_with_news
                    priority_reason = "has news"
                else:
                    # No news - use shorter interval for faster discovery
                    required_interval = self.min_scan_interval_no_news
                    priority_reason = "no news"

                if time_since_scan >= required_interval:
                    symbols_to_scan_filtered.append(symbol)
                    self.logger.debug(f"🔄 {symbol}: Scan due ({priority_reason}, {time_since_scan:.0f}s since last)")
                else:
                    symbols_skipped_cooldown.append(symbol)
                    self.logger.debug(f"⏸️ {symbol}: Skipping scan ({priority_reason}, {required_interval - time_since_scan:.0f}s remaining)")

        # Log optimization results
        if symbols_skipped_cooldown:
            self.logger.info(f"⚡ News scan optimization: {len(symbols_to_scan_filtered)}/{len(symbols_to_scan)} symbols need scanning")
            self.logger.info(f"   ⏸️ Skipped {len(symbols_skipped_cooldown)} symbols in cooldown")

        if not symbols_to_scan_filtered:
            self.logger.info("⚡ All remaining symbols in cooldown - using cached news data")
            return complete_results

        self.logger.info(f"🗞️ Fetching news from multi-source system for {len(symbols_to_scan_filtered)} symbols")

        try:
            # Use multi-source news checker only for symbols that need scanning
            news_results = await self.news_checker.get_news_for_symbols(symbols_to_scan_filtered)

            # Update TTL cache and cooldowns for scanned symbols
            for symbol in symbols_to_scan_filtered:
                headlines = news_results.get(symbol, [])
                cache_key = f"news_{symbol}"
                self._news_cache[cache_key] = headlines  # TTL cache
                self.news_cache[symbol] = headlines  # Legacy cache for compatibility
                self.news_scan_cooldown[symbol] = current_time

                # Update priority queue
                if not headlines:
                    # No news found - keep in priority queue for faster re-scanning
                    if symbol not in self.news_priority_queue:
                        self.news_priority_queue.append(symbol)
                else:
                    # Has news - remove from priority queue
                    if symbol in self.news_priority_queue:
                        self.news_priority_queue.remove(symbol)

                # Update complete results
                complete_results[symbol] = headlines

            # Log results summary
            total_headlines = sum(len(headlines) for headlines in news_results.values())
            symbols_with_news = sum(1 for headlines in news_results.values() if headlines)

            self.logger.info(f"📰 Multi-source news results:")
            self.logger.info(f"   • {symbols_with_news}/{len(symbols_to_scan_filtered)} scanned symbols have news")
            self.logger.info(f"   • {total_headlines} total headlines collected")
            self.logger.info(f"   • Available sources: {self.news_checker._get_available_sources()}")

            # Ensure all requested symbols have entries
            for symbol in symbols:
                if symbol not in complete_results:
                    complete_results[symbol] = []

            return complete_results, cache_hits

        except Exception as e:
            self.logger.error(f"Error in optimized multi-source news fetching: {e}")

            # Fallback to basic YahooQuery if multi-source fails
            self.logger.info("📰 Falling back to basic YahooQuery news...")
            fallback_result, fallback_cache_hits = await self._get_news_batch_fallback(symbols)
            return fallback_result, fallback_cache_hits
    
    async def _get_news_batch_fallback(self, symbols: List[str]) -> tuple[Dict[str, List[tuple]], int]:
        """
        Fallback news fetching using basic YahooQuery (original method)
        Used if multi-source system fails
        """
        from yahooquery import Ticker
        
        news_results = {}
        
        # Process in smaller batches for better reliability
        batch_size = 5  # Reduced batch size for fallback
        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]
            
            try:
                ticker = Ticker(batch_symbols)
                raw_news_data = ticker.news() if hasattr(ticker, 'news') else {}
                
                # Handle different data formats
                if isinstance(raw_news_data, dict):
                    news_data = raw_news_data
                elif isinstance(raw_news_data, list):
                    news_data = {}
                    for symbol in batch_symbols:
                        news_data[symbol] = raw_news_data
                else:
                    news_data = {}
                
                current_time = datetime.now()
                
                for symbol in batch_symbols:
                    headlines = []
                    if symbol in news_data and news_data[symbol]:
                        for article in news_data[symbol][:self.config['max_headlines_per_symbol']]:
                            try:
                                if isinstance(article, dict):
                                    headline = article.get('title', '')
                                    pub_time = datetime.fromtimestamp(article.get('providerPublishTime', 0))
                                elif isinstance(article, str):
                                    headline = article
                                    pub_time = current_time
                                else:
                                    continue
                                
                                age_hours = (current_time - pub_time).total_seconds() / 3600
                                headlines.append((headline, age_hours))
                            except Exception as e:
                                self.logger.debug(f"Error processing fallback article for {symbol}: {e}")
                                continue
                    
                    news_results[symbol] = headlines
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Error in fallback news for batch {batch_symbols}: {e}")
                for symbol in batch_symbols:
                    news_results[symbol] = []
        
        return news_results, 0  # Return 0 cache hits for fallback method
    
    async def _create_smallcap_play(self, ibkr_result: IBKRScanResult, catalyst: CatalystInfo) -> Optional[SmallcapPlay]:
        """
        Create SmallcapPlay from IBKR result + catalyst analysis
        Much simpler now that IBKR provides most data
        """
        try:
            self.logger.info(f"      📊 Creating context for {ibkr_result.symbol}")
            # Create SmallcapContext using IBKR data
            context = SmallcapContext(
                symbol=ibkr_result.symbol,
                timestamp=datetime.now(),
                current_price=ibkr_result.current_price,
                gap_percentage=ibkr_result.gap_percentage,
                premarket_high=ibkr_result.current_price,  # Simplified - IBKR could provide this
                premarket_low=ibkr_result.current_price * 0.95,  # Simplified
                premarket_volume=ibkr_result.volume,
                avg_daily_volume=ibkr_result.avg_volume,
                premarket_volume_ratio=ibkr_result.volume / ibkr_result.avg_volume if ibkr_result.avg_volume > 0 else 0.5,
                news_catalyst_type=catalyst.catalyst_type,
                news_age_hours=catalyst.age_hours,
                catalyst_strength=catalyst.strength,
                float_size=50_000_000,  # IBKR could provide this, using default for now
                market_cap=ibkr_result.market_cap,
                price_vs_premarket_high=1.0,  # Simplified
                volume_spike_confirmed=ibkr_result.volume > ibkr_result.avg_volume * 2,
                market_fear_level=self._get_simple_market_fear()
            )
            
            # Check if tradeable
            self.logger.info(f"      🔍 Checking if {ibkr_result.symbol} is tradeable...")
            if not context.is_tradeable():
                self.logger.info(f"      ❌ {ibkr_result.symbol}: NOT tradeable (context.is_tradeable() returned False)")
                return None
            
            self.logger.info(f"      ✅ {ibkr_result.symbol}: Is tradeable")
            
            # Calculate enhanced quality score
            self.logger.info(f"      🎯 Calculating quality score for {ibkr_result.symbol}")
            quality_score = self._calculate_enhanced_quality_score(context, ibkr_result)
            self.logger.info(f"      📊 {ibkr_result.symbol}: quality_score={quality_score:.2f}")
            
            # Get trading recommendation
            trading_rec = self.catalyst_analyzer.get_catalyst_trading_recommendation(catalyst)
            
            play = SmallcapPlay(
                symbol=ibkr_result.symbol,
                context=context,
                catalyst=catalyst,
                quality_score=quality_score,
                trading_recommendation=trading_rec,
                scan_timestamp=datetime.now(),
                ibkr_rank=ibkr_result.rank
            )
            
            self.logger.info(f"      ✅ {ibkr_result.symbol}: SmallcapPlay created successfully")
            return play
            
        except Exception as e:
            self.logger.error(f"Error creating SmallcapPlay for {ibkr_result.symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _calculate_enhanced_quality_score(self, context: SmallcapContext, ibkr_result: IBKRScanResult) -> float:
        """
        Enhanced quality scoring that combines SmallcapContext + IBKR ranking
        """
        # Base score from context
        base_score = context.get_play_quality_score()
        
        # IBKR ranking bonus (higher is better)
        ibkr_bonus = max(0, (50 - ibkr_result.rank) / 10.0)  # 0-5 bonus points
        
        # IBKR quality score bonus
        ibkr_quality_bonus = getattr(ibkr_result, 'quality_score', 0) / 20.0  # 0-5 bonus
        
        total_score = base_score + ibkr_bonus + ibkr_quality_bonus
        
        return min(total_score, 10.0)  # Cap at 10
    
    def _get_simple_market_fear(self) -> str:
        """Simplified market fear - could enhance with real VIX data"""
        # This could be enhanced to get real VIX from IBKR
        return 'LOW'  # Default for now
    
    def get_formatted_output(self, plays: List[SmallcapPlay]) -> str:
        """Get formatted output combining IBKR + catalyst data"""
        if not plays:
            return "No high-quality smallcap plays found."
        
        symbols = [play.symbol for play in plays]
        symbol_string = ", ".join(symbols)
        
        output = f"🎯 REFACTORED SMALLCAP SCANNER ({len(plays)} plays):\n"
        output += f"📋 Symbols: {symbol_string}\n\n"
        
        output += "📊 ENHANCED PLAY DETAILS:\n"
        for i, play in enumerate(plays, 1):
            ctx = play.context
            cat = play.catalyst
            
            output += f"{i}. {play.symbol} (Score: {play.quality_score:.1f}/10, IBKR Rank: #{play.ibkr_rank})\n"
            output += f"   Gap: {ctx.gap_percentage*100:+.1f}% | Price: ${ctx.current_price:.2f}\n"
            output += f"   Catalyst: {cat.catalyst_type} (Strength: {cat.strength}/10, Age: {cat.age_hours:.1f}h)\n"
            output += f"   Volume: {ctx.premarket_volume:,} ({ctx.premarket_volume_ratio:.1f}x avg)\n"
            output += f"   Strategy: {play.trading_recommendation.get('strategy_preference', 'standard')}\n\n"
        
        return output
    
    # Quality score calculation methods for multi-track opportunities
    def _calculate_catalyst_quality_score(self, result: IBKRScanResult, catalyst: CatalystInfo, context: SmallcapContext) -> float:
        """
        Calculate quality score for catalyst opportunities

        Note: For catalyst plays, we're more lenient with gap direction
        because catalysts can work on red-to-green moves. But we still
        favor positive price action.
        """
        try:
            # Base score from catalyst strength
            catalyst_score = catalyst.strength / 10.0

            # Volume factor
            volume_score = min(1.0, context.premarket_volume_ratio / 5.0)

            # Price movement factor - favor bullish gaps but allow small bearish ones
            if result.gap_percentage is None:
                price_score = 0.5  # Neutral if no gap data
            elif result.gap_percentage >= 0:
                # Positive gap = full credit
                price_score = min(1.0, result.gap_percentage / 20.0)
            else:
                # Negative gap = partial credit (catalyst can overcome small gaps)
                # Max penalty for gaps < -5%
                price_score = max(0.2, 0.5 + (result.gap_percentage / 10.0))

            # Freshness factor (newer = better)
            freshness_score = max(0.1, 1.0 - (catalyst.age_hours / 24.0))

            # Weighted composite
            composite = (catalyst_score * 0.4 + volume_score * 0.25 +
                        price_score * 0.25 + freshness_score * 0.1)

            return min(100.0, composite * 100.0)

        except Exception:
            return 50.0  # Default moderate score
    
    def _calculate_gap_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """
        Calculate quality score for gap opportunities

        IMPORTANT: This is for LONG gap opportunities. Negative gaps receive ZERO score.
        """
        try:
            # CRITICAL: For LONG opportunities, negative gaps should receive ZERO score
            # Don't use abs() - direction matters!
            if result.gap_percentage is None:
                gap_score = 0.0
            elif result.gap_percentage < 0:
                # Negative gap = bearish = bad for LONG
                gap_score = 0.0
                self.logger.debug(f"   ⚠️ {result.symbol}: Negative gap {result.gap_percentage:.1f}% - penalizing quality score for LONG")
            else:
                # Positive gap = bullish (8-25% optimal for gap plays)
                gap_score = min(1.0, result.gap_percentage / 20.0)

            # Volume confirmation
            volume_score = min(1.0, context.premarket_volume_ratio / 3.0)

            # Price range score (prefer $2-12 range)
            if 2.0 <= result.current_price <= 12.0:
                price_score = 1.0
            else:
                price_score = 0.6

            # Market cap factor (prefer smallcaps)
            if result.market_cap > 0:
                mcap_score = max(0.3, 1.0 - (result.market_cap / 2000))  # Penalty above $2B
            else:
                mcap_score = 0.7

            composite = (gap_score * 0.4 + volume_score * 0.3 +
                        price_score * 0.2 + mcap_score * 0.1)

            return min(100.0, composite * 100.0)

        except Exception:
            return 50.0
    
    def _calculate_orb_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for ORB opportunities"""
        try:
            # Volume factor (ORB needs good volume)
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 0
            volume_score = min(1.0, volume_ratio / 3.0)
            
            # Price range optimization
            if 3.0 <= result.current_price <= 10.0:
                price_score = 1.0
            else:
                price_score = 0.7
                
            # Gap factor (moderate gaps good for ORB)
            if result.gap_percentage:
                if 2.0 <= abs(result.gap_percentage) <= 8.0:
                    gap_score = 1.0
                else:
                    gap_score = 0.6
            else:
                gap_score = 0.8  # No gap is fine for ORB
                
            # Market time factor (ORB is morning-focused)
            current_time = datetime.now().time()
            morning_optimal = datetime.strptime("10:30:00", "%H:%M:%S").time()
            
            if current_time <= morning_optimal:
                time_score = 1.0
            else:
                time_score = 0.6
                
            composite = (volume_score * 0.35 + price_score * 0.25 + 
                        gap_score * 0.25 + time_score * 0.15)
            
            return min(100.0, composite * 100.0)
            
        except Exception:
            return 50.0
    
    def _calculate_volume_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for volume surge opportunities"""
        try:
            # Volume explosion magnitude
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 0
            volume_score = min(1.0, volume_ratio / 10.0)  # Cap at 10x
            
            # Price movement confirmation
            price_score = min(1.0, abs(result.gap_percentage) / 15.0) if result.gap_percentage else 0.3
            
            # Liquidity factor
            dollar_volume = result.volume * result.current_price
            liquidity_score = min(1.0, dollar_volume / 1000000)  # $1M+ preferred
            
            # Market cap factor
            if result.market_cap > 0:
                mcap_score = max(0.2, 1.0 - (result.market_cap / 1000))  # Prefer <$1B
            else:
                mcap_score = 0.7
                
            composite = (volume_score * 0.5 + price_score * 0.2 + 
                        liquidity_score * 0.2 + mcap_score * 0.1)
            
            return min(100.0, composite * 100.0)
            
        except Exception:
            return 50.0
    
    def _calculate_vwap_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for VWAP opportunities"""
        try:
            # Basic technical scoring
            volume_score = min(1.0, context.premarket_volume_ratio / 2.0)
            price_score = 0.8 if 2.0 <= result.current_price <= 15.0 else 0.5
            
            # Liquidity and market cap
            dollar_volume = result.volume * result.current_price
            liquidity_score = min(1.0, dollar_volume / 500000)
            
            composite = (volume_score * 0.4 + price_score * 0.3 + liquidity_score * 0.3)
            return min(100.0, composite * 100.0)
            
        except Exception:
            return 50.0
    
    def _calculate_macdv_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for MACDV opportunities"""
        try:
            # Similar to VWAP but with different weighting
            volume_score = min(1.0, context.premarket_volume_ratio / 2.5)
            price_score = 0.9 if 2.0 <= result.current_price <= 12.0 else 0.6

            # Moderate gap preference
            if result.gap_percentage:
                gap_score = 1.0 if abs(result.gap_percentage) <= 10.0 else 0.7
            else:
                gap_score = 0.8

            composite = (volume_score * 0.4 + price_score * 0.35 + gap_score * 0.25)
            return min(100.0, composite * 100.0)

        except Exception:
            return 50.0

    def _calculate_short_squeeze_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for short squeeze opportunities"""
        try:
            # Fintel confirmation is the primary factor
            fintel_score = 1.0  # If we reach here, Fintel confirmed

            # Volume factor (moderate volume preferred for short squeezes)
            volume_score = min(1.0, context.premarket_volume_ratio / 3.0)

            # Price range score (short squeezes work well in various ranges)
            if 2.0 <= result.current_price <= 15.0:
                price_score = 1.0
            elif 15.0 < result.current_price <= 20.0:
                price_score = 0.8
            else:
                price_score = 0.5

            # Gap factor (small gaps often better for short squeezes)
            if result.gap_percentage:
                if abs(result.gap_percentage) <= 5.0:
                    gap_score = 1.0
                elif abs(result.gap_percentage) <= 10.0:
                    gap_score = 0.8
                else:
                    gap_score = 0.6
            else:
                gap_score = 0.9  # No gap is fine

            # Market cap factor (smaller caps more susceptible to squeezes)
            if result.market_cap > 0:
                if result.market_cap <= 500:  # Under $500M
                    mcap_score = 1.0
                elif result.market_cap <= 1000:  # Under $1B
                    mcap_score = 0.8
                else:
                    mcap_score = 0.6
            else:
                mcap_score = 0.7

            composite = (fintel_score * 0.4 + volume_score * 0.25 +
                        price_score * 0.15 + gap_score * 0.1 + mcap_score * 0.1)
            return min(100.0, composite * 100.0)

        except Exception:
            return 50.0
    
    def _calculate_eod_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for EOD opportunities"""
        try:
            # EOD focuses on daily momentum and volume
            volume_score = min(1.0, context.premarket_volume_ratio / 2.0)
            
            # Price momentum (any meaningful move)
            price_score = min(1.0, abs(result.gap_percentage) / 10.0) if result.gap_percentage else 0.4
            
            # Time factor (later = better for EOD)
            current_time = datetime.now().time()
            eod_optimal = datetime.strptime("15:45:00", "%H:%M:%S").time()
            
            if current_time >= eod_optimal:
                time_score = 1.0
            else:
                time_score = 0.7
                
            composite = (volume_score * 0.4 + price_score * 0.35 + time_score * 0.25)
            return min(100.0, composite * 100.0)
            
        except Exception:
            return 50.0
    
    async def _create_context(self, result: IBKRScanResult) -> Optional[SmallcapContext]:
        """Create SmallcapContext from IBKR result"""
        try:
            # Calculate volume ratio
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 1.0
            
            # Create context with correct SmallcapContext parameters
            context = SmallcapContext(
                symbol=result.symbol,
                timestamp=datetime.now(),
                current_price=result.current_price,
                gap_percentage=result.gap_percentage,
                premarket_high=result.current_price * 1.02,  # Estimate
                premarket_low=result.current_price * 0.98,   # Estimate
                premarket_volume=result.volume,
                avg_daily_volume=result.avg_volume,
                premarket_volume_ratio=volume_ratio,
                news_catalyst_type="UNKNOWN",  # Will be set by catalyst analysis
                news_age_hours=0.0,
                catalyst_strength=0,
                float_size=result.estimated_float,
                market_cap=result.market_cap,
                price_vs_premarket_high=0.98,  # Estimate
                volume_spike_confirmed=volume_ratio >= 3.0,
                market_fear_level="LOW"  # Default
            )
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error creating context for {result.symbol}: {e}")
            return None
    
    def save_scan_results(self, plays: List[SmallcapPlay], filename: Optional[str] = None) -> str:
        """Save refactored scan results"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"smallcap_scan_refactored_{timestamp}.json"
        
        filepath = os.path.join("scanner", "smallcap", "results", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'scan_timestamp': datetime.now().isoformat(),
            'scanner_version': 'REFACTORED_IBKR_NATIVE',
            'plays_count': len(plays),
            'plays': [play.to_dict() for play in plays]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Refactored scan results saved to {filepath}")
        return filepath
    
    async def _check_fintel_short_squeeze(self, symbol: str) -> bool:
        """
        Check if ticker appears in recent Fintel CSV files for short squeeze potential
        Returns True if found in any of the 20 most recent files
        Uses TTL cache to avoid repeated file I/O
        """
        # Check cache first
        cache_key = f"fintel_{symbol}"
        if cache_key in self._fintel_cache:
            cached_result = self._fintel_cache[cache_key]
            self.logger.debug(f"🐻 {symbol}: Using cached Fintel result: {cached_result}")
            return cached_result

        try:
            fintel_csv_dir = "fintel/csv"
            if not os.path.exists(fintel_csv_dir):
                self.logger.warning(f"Fintel CSV directory not found: {fintel_csv_dir}")
                self._fintel_cache[cache_key] = False
                return False

            # Get all CSV files
            csv_files = [f for f in os.listdir(fintel_csv_dir) if f.endswith('.csv')]
            if not csv_files:
                self.logger.warning("No CSV files found in fintel/csv directory")
                self._fintel_cache[cache_key] = False
                return False

            # Sort files by date (descending - most recent first)
            def extract_date(filename):
                try:
                    # Format: DD-MM-YY-Tabla 1.csv (e.g., 31-7-25-Tabla 1.csv)
                    parts = filename.split('-')
                    if len(parts) >= 3:
                        day, month, year = parts[0], parts[1], parts[2]
                        # Convert 2-digit year to 4-digit
                        year = f"20{year}" if len(year) == 2 else year
                        return datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
                except (ValueError, IndexError):
                    pass
                return datetime.min  # If parsing fails, put at end

            csv_files.sort(key=extract_date, reverse=True)

            # Take only the 20 most recent files
            recent_files = csv_files[:20]
            self.logger.debug(f"Checking {len(recent_files)} most recent Fintel files for {symbol}")

            # Check each file for the ticker
            for filename in recent_files:
                filepath = os.path.join(fintel_csv_dir, filename)
                try:
                    # Read CSV with proper encoding and separator detection
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8', low_memory=False)

                    # Check if 'Security' column exists
                    if 'Security' not in df.columns:
                        self.logger.debug(f"'Security' column not found in {filename}, trying alternative names")
                        # Try alternative column names
                        alt_names = ['security', 'SECURITY', 'Ticker', 'ticker', 'TICKER', 'Symbol', 'symbol', 'SYMBOL']
                        security_col = None
                        for alt in alt_names:
                            if alt in df.columns:
                                security_col = alt
                                break
                        if not security_col:
                            self.logger.debug(f"No security column found in {filename}, columns: {list(df.columns)}")
                            continue
                    else:
                        security_col = 'Security'

                    # Check if ticker is in the Security column (handle format: "TICKER / Company Name")
                    found = False
                    for security_value in df[security_col].values:
                        # Extract ticker from format "TICKER / Company Name"
                        if ' / ' in str(security_value):
                            ticker_in_file = str(security_value).split(' / ')[0].strip()
                        else:
                            ticker_in_file = str(security_value).strip()

                        if ticker_in_file == symbol:
                            found = True
                            break

                    if found:
                        self.logger.info(f"🐻 {symbol}: Found in recent Fintel file {filename}")
                        self._fintel_cache[cache_key] = True
                        return True

                except Exception as e:
                    self.logger.warning(f"Error reading {filename}: {e}")
                    continue

            self.logger.debug(f"🐻 {symbol}: Not found in any of the 20 most recent Fintel files")
            self._fintel_cache[cache_key] = False
            return False

        except Exception as e:
            self.logger.error(f"Error checking Fintel data for {symbol}: {e}")
            self._fintel_cache[cache_key] = False
            return False

    async def _send_short_squeeze_signal(self, symbol: str, play: SmallcapPlay) -> None:
        """
        Send short squeeze signal to Redis for trader_main processing
        """
        try:
            import redis
            import json

            # Connect to Redis (assuming default localhost:6379)
            redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

            # Prepare signal data
            signal_data = {
                'symbol': symbol,
                'signal_type': 'short_squeeze',
                'opportunity_type': play.opportunity_type.value,
                'quality_score': play.quality_score,
                'trading_recommendation': play.trading_recommendation,
                'scan_timestamp': play.scan_timestamp.isoformat(),
                'fintel_confirmed': True,
                'strategy_targets': play.strategy_targets,
                'source': 'smallcap_scanner_short_squeeze'
            }

            # Send to Redis queue for swing worker
            queue_key = 'swing_signals'  # Key for swing trading signals
            redis_client.lpush(queue_key, json.dumps(signal_data))

            self.logger.info(f"📤 SHORT SQUEEZE signal sent to Redis for {symbol}: quality_score={play.quality_score:.1f}")

        except Exception as e:
            self.logger.error(f"Error sending short squeeze signal to Redis for {symbol}: {e}")

    async def disconnect(self):
        """Cleanup connections"""
        if self.ibkr_scanner:
            await self.ibkr_scanner.disconnect()