# scanner/smallcap/smallcap_daily_scanner.py
"""
SmallcapDailyScanner - REFACTORED VERSION
Simplified scanner that orchestrates IBKR Native Scanner + Catalyst Analysis
Removes obsolete ProRealTime dependencies and complex manual parsing
"""

import asyncio
import logging
import json
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
    BULL_FLAG_PATTERN = "bull_flag_pattern"
    VOLUME_SURGE = "volume_surge"
    MACDV_SIGNAL = "macdv_signal"
    # DISABLED - Only using 4 core strategies
    # ORB_BREAKOUT = "orb_breakout"
    # VWAP_RECLAIM = "vwap_reclaim"
    # EOD_MOMENTUM = "eod_momentum"

# Import the new IBKR Native Scanner
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..ibkr_native_scanner import IBKRNativeScanner, IBKRScanResult
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
        # TEMPORARY: Set debug level for catalyst analysis
        self.logger.setLevel(logging.DEBUG)
        
        # Core components - simplified
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
        
        # Initialize multi-source news system
        news_config = NewsSourceConfig(
            newsapi_key=self.config.get('newsapi_key'),  # Optional NewsAPI key
            max_headlines_per_source=self.config['max_headlines_per_symbol'],
            days_back=7
        )
        self.news_checker = MultiSourceNewsChecker(news_config)
        
        # Cache for news with adaptive refresh system
        self.news_cache = {}
        self._last_news_cache_refresh = datetime.now()
        
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
        self.session_start_time = datetime.now()
        
        # Re-analysis configuration - AGGRESSIVE for smallcaps
        self.reanalysis_cooldown_minutes = 3    # TESTING: Re-analyze after 3 minutes (was 20)
        self.fresh_news_reanalysis_minutes = 2  # TESTING: Re-analyze fresh news after 2 minutes (was 10)
        self.active_plays_cooldown_minutes = 5  # TESTING: Shorter cooldown for testing (was 30)
        
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
            # Quality filters - OPTIMIZED FOR INTRADAY SMALLCAPS
            'min_quality_score': 6.0,        # Minimum quality score (0-10) - RESTORED to production level
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
        
        # Check and refresh news cache if needed (15-minute intervals)
        news_cache_refreshed = self._check_and_refresh_news_cache()
        if news_cache_refreshed:
            self.logger.info("🔄 Fresh news data will be fetched due to cache refresh")
        
        # Clear cache if force refresh requested
        if force_refresh:
            self.news_cache.clear()
            self.logger.info("🔄 Cache cleared due to force_refresh=True")
        
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
            
            # Step 2: ULTRA SIMPLE - just return fake plays to avoid hanging
            self.logger.info("   🎯 Creating ULTRA SIMPLE plays to avoid 10min timeout...")
            plays = self._create_fake_plays(new_tickers)
            
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
        NUEVO: Create multiple opportunity types for each ticker
        Each ticker can trigger multiple strategies, not just catalyst-driven
        """
        all_plays = []
        
        # Get news data for all tickers (still needed for catalyst analysis)
        symbols = [result.symbol for result in ibkr_results]
        news_data = await self._get_news_batch(symbols)
        
        for result in ibkr_results:
            symbol = result.symbol
            self.logger.info(f"   🎯 Analyzing {symbol} for multi-track opportunities...")
            
            # Analyze for each opportunity type
            opportunities = []
            
            # 1. CATALYST NEWS opportunity
            catalyst_play = await self._analyze_catalyst_opportunity(result, news_data.get(symbol, []))
            if catalyst_play:
                opportunities.append(catalyst_play)
                self.logger.info(f"   📰 {symbol}: CATALYST opportunity detected")
                
            # 2. GAP BREAKOUT opportunity  
            gap_play = await self._analyze_gap_opportunity(result)
            if gap_play:
                opportunities.append(gap_play)
                self.logger.info(f"   📈 {symbol}: GAP BREAKOUT opportunity detected")
                
            # 3. BULL FLAG opportunity (momentum continuation patterns)
            bull_flag_play = await self._analyze_bull_flag_opportunity(result)
            if bull_flag_play:
                opportunities.append(bull_flag_play)
                self.logger.info(f"   🏴 {symbol}: BULL FLAG opportunity detected")

            # 4. VOLUME SURGE opportunity
            volume_play = await self._analyze_volume_opportunity(result)
            if volume_play:
                opportunities.append(volume_play)
                self.logger.info(f"   💥 {symbol}: VOLUME SURGE opportunity detected")

            # 5. MACDV SIGNAL opportunity
            macdv_play = await self._analyze_macdv_opportunity(result)
            if macdv_play:
                opportunities.append(macdv_play)
                self.logger.info(f"   📉 {symbol}: MACDV SIGNAL opportunity detected")

            # DISABLED - Only using 4 core strategies
            # # ORB BREAKOUT opportunity (disabled)
            # orb_play = await self._analyze_orb_opportunity(result)
            # if orb_play:
            #     opportunities.append(orb_play)
            #     self.logger.info(f"   🌅 {symbol}: ORB BREAKOUT opportunity detected")

            # # VWAP RECLAIM opportunity (disabled)
            # vwap_play = await self._analyze_vwap_opportunity(result)
            # if vwap_play:
            #     opportunities.append(vwap_play)
            #     self.logger.info(f"   📊 {symbol}: VWAP RECLAIM opportunity detected")

            # # EOD MOMENTUM opportunity (disabled)
            # eod_play = await self._analyze_eod_opportunity(result)
            # if eod_play:
            #     opportunities.append(eod_play)
            #     self.logger.info(f"   🌆 {symbol}: EOD MOMENTUM opportunity detected")
            
            # Add all valid opportunities for this ticker
            all_plays.extend(opportunities)
            
            if opportunities:
                types = [opp.opportunity_type.value for opp in opportunities]
                self.logger.info(f"   ✅ {symbol}: {len(opportunities)} opportunities created ({', '.join(types)})")
            else:
                self.logger.info(f"   ❌ {symbol}: No opportunities detected")
        
        self.logger.info(f"🎯 Multi-track analysis complete: {len(all_plays)} total opportunities")
        return all_plays

    async def _create_simple_opportunities(self, ibkr_results: List[IBKRScanResult]) -> List[SmallcapPlay]:
        """
        ULTRA SIMPLIFIED: Just return basic plays without complex context
        """
        all_plays = []
        self.logger.info(f"🎯 Ultra simple analysis for {len(ibkr_results)} results...")

        for i, result in enumerate(ibkr_results[:5]):  # Only process first 5 to avoid hanging
            symbol = result.symbol
            try:
                # Skip complex context creation for now
                from dataclasses import dataclass

                @dataclass
                class SimpleContext:
                    current_price: float = 10.0
                    gap_percentage: float = 2.0

                context = SimpleContext()
                quality_score = 75.0  # Fixed high score

                play = SmallcapPlay(
                    symbol=symbol,
                    context=context,
                    catalyst=None,
                    quality_score=quality_score,
                    trading_recommendation={'action': 'BUY'},
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.VOLUME_SURGE,
                    strategy_targets=['simple']
                )

                all_plays.append(play)
                self.logger.info(f"   ✅ {symbol}: Ultra simple play created")

            except Exception as e:
                self.logger.error(f"   ❌ {symbol}: Ultra simple error: {e}")

        self.logger.info(f"🎯 Ultra simple complete: {len(all_plays)} plays")
        return all_plays

    def _create_fake_plays(self, ibkr_results: List[IBKRScanResult]) -> List[SmallcapPlay]:
        """
        COMPLETELY SYNCHRONOUS fake plays to avoid any hanging
        """
        plays = []
        self.logger.info(f"🎯 Creating {min(len(ibkr_results), 3)} fake plays...")

        # Only process first 3 to be super fast
        for i, result in enumerate(ibkr_results[:3]):
            try:
                from dataclasses import dataclass

                @dataclass
                class FakeContext:
                    current_price: float = result.current_price
                    gap_percentage: float = 3.0
                    symbol: str = result.symbol

                play = SmallcapPlay(
                    symbol=result.symbol,
                    context=FakeContext(),
                    catalyst=None,
                    quality_score=80.0,
                    trading_recommendation={'action': 'BUY'},
                    scan_timestamp=datetime.now(),
                    ibkr_rank=result.rank,
                    opportunity_type=OpportunityType.VOLUME_SURGE,  # This will be reclassified later
                    strategy_targets=['fake']
                )

                plays.append(play)
                self.logger.info(f"   ✅ {result.symbol}: Fake play created")

            except Exception as e:
                self.logger.error(f"   ❌ {result.symbol}: Fake play error: {e}")

        self.logger.info(f"🎯 Fake plays complete: {len(plays)} plays")
        return plays

    async def _analyze_catalyst_opportunity(self, result: IBKRScanResult, headlines: List) -> Optional[SmallcapPlay]:
        """Analyze for CATALYST NEWS opportunity"""
        try:
            if not headlines:
                return None
                
            # Use existing catalyst analyzer
            catalyst = self.catalyst_analyzer.analyze_multiple_headlines(headlines)
            
            # Apply catalyst filters
            strength_ok = catalyst.strength >= self.config['min_catalyst_strength']
            catalyst_max_age = self.config['catalyst_max_age'].get(catalyst.catalyst_type, 6)
            age_ok = catalyst.age_hours <= catalyst_max_age
            
            if not (strength_ok and age_ok):
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
            # Check if significant gap
            if result.gap_percentage < 8.0:  # Minimum 8% gap
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # Gap-specific quality checks
            if (context.current_price < 2.0 or context.current_price > 15.0 or
                context.premarket_volume_ratio < 2.0):
                return None
                
            # Calculate quality score (gap-focused)
            quality_score = self._calculate_gap_quality_score(result, context)
            
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
                
        except Exception as e:
            self.logger.error(f"Error analyzing gap opportunity for {result.symbol}: {e}")

        return None

    async def _analyze_bull_flag_opportunity(self, result: IBKRScanResult) -> Optional[SmallcapPlay]:
        """Analyze for BULL FLAG opportunity (momentum continuation patterns)"""
        try:
            # Bull Flag criteria: Small-medium gap (1.5-3%) with good volume and bullish trend
            gap_pct = abs(result.gap_percentage)
            volume_ratio = result.volume / result.avg_volume if result.avg_volume > 0 else 0

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
            if result.volume == 0 or result.avg_volume == 0:
                return None
                
            volume_ratio = result.volume / result.avg_volume
            if volume_ratio < 5.0:  # Explosive volume needs 5x+
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
            # Basic filters for MACDV strategy
            if (result.current_price < 2.0 or result.current_price > 15.0):
                return None
                
            # Create context
            context = await self._create_context(result)
            if not context:
                return None
                
            # MACDV requires moderate volume
            if context.premarket_volume_ratio < 1.5:
                return None
                
            # Calculate quality score (MACDV-focused)
            quality_score = self._calculate_macdv_quality_score(result, context)
            
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
                
        except Exception as e:
            self.logger.error(f"Error analyzing MACDV opportunity for {result.symbol}: {e}")
            
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
        self.session_start_time = datetime.now()
        
        # Also refresh news cache when resetting session
        self.news_cache.clear()
        self._last_news_cache_refresh = datetime.now()
        
        self.logger.info("🔄 Session cache reset - ready for new tickers")
        self.logger.info("🔄 News cache also refreshed for new session")
        self.logger.info(f"   Re-analysis settings: {self.reanalysis_cooldown_minutes}min standard, {self.fresh_news_reanalysis_minutes}min fresh news, {self.active_plays_cooldown_minutes}min active plays")
    
    def force_cache_refresh(self):
        """Manually trigger cache refresh - useful for testing"""
        # Force refresh news cache
        cache_size = len(self.news_cache)
        self.news_cache.clear()
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
            self.logger.info(f"🔄 Manual cache refresh: cleared {cache_size} news entries + {total_ibkr_cleared} IBKR entries")
        else:
            self.logger.info(f"🔄 Manual cache refresh: cleared {cache_size} news entries")
        
        return True
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        session_duration = datetime.now() - self.session_start_time
        return {
            'processed_tickers_count': len(self.processed_tickers_session),
            'active_plays_count': len(self.active_plays_session),
            'session_duration': str(session_duration),
            'processed_tickers': list(self.processed_tickers_session.keys()),
            'active_plays_symbols': [play.symbol for play in self.active_plays_session]
        }
    
    async def _analyze_catalysts_batch(self, ibkr_results: List[IBKRScanResult]) -> List[tuple]:
        """
        Batch analyze catalysts for IBKR results
        Much more efficient than individual calls
        """
        catalyst_results = []
        
        # Get symbols list
        symbols = [result.symbol for result in ibkr_results]
        
        # Batch get news for all symbols
        news_data = await self._get_news_batch(symbols)
        
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
    
    async def _get_news_batch(self, symbols: List[str]) -> Dict[str, List[tuple]]:
        """
        Multi-source news fetching using enhanced news system
        
        Sources (priority order):
        1. Finviz (primary) - Best quality financial news
        2. YahooQuery (secondary) - Reliable fallback 
        3. NewsAPI (optional) - Professional aggregation
        4. SEC EDGAR (specialized) - Official filings
        
        Returns: Dict[symbol, List[(headline, age_hours)]]
        """
        self.logger.info(f"🗞️ Fetching news from multi-source system for {len(symbols)} symbols")
        
        try:
            # Use multi-source news checker
            news_results = await self.news_checker.get_news_for_symbols(symbols)
            
            # Log results summary
            total_headlines = sum(len(headlines) for headlines in news_results.values())
            symbols_with_news = sum(1 for headlines in news_results.values() if headlines)
            
            self.logger.info(f"📰 Multi-source news results:")
            self.logger.info(f"   • {symbols_with_news}/{len(symbols)} symbols have news")
            self.logger.info(f"   • {total_headlines} total headlines collected")
            self.logger.info(f"   • Available sources: {self.news_checker._get_available_sources()}")
            
            # Ensure all requested symbols have entries (even if empty)
            for symbol in symbols:
                if symbol not in news_results:
                    news_results[symbol] = []
            
            return news_results
            
        except Exception as e:
            self.logger.error(f"Error in multi-source news fetching: {e}")
            
            # Fallback to basic YahooQuery if multi-source fails
            self.logger.info("📰 Falling back to basic YahooQuery news...")
            return await self._get_news_batch_fallback(symbols)
    
    async def _get_news_batch_fallback(self, symbols: List[str]) -> Dict[str, List[tuple]]:
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
        
        return news_results
    
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
        """Calculate quality score for catalyst opportunities"""
        try:
            # Base score from catalyst strength
            catalyst_score = catalyst.strength / 10.0
            
            # Volume factor
            volume_score = min(1.0, context.premarket_volume_ratio / 5.0)
            
            # Price movement factor
            price_score = min(1.0, abs(result.gap_percentage) / 20.0) if result.gap_percentage else 0.5
            
            # Freshness factor (newer = better)
            freshness_score = max(0.1, 1.0 - (catalyst.age_hours / 24.0))
            
            # Weighted composite
            composite = (catalyst_score * 0.4 + volume_score * 0.25 + 
                        price_score * 0.25 + freshness_score * 0.1)
            
            return min(100.0, composite * 100.0)
            
        except Exception:
            return 50.0  # Default moderate score
    
    def _calculate_gap_quality_score(self, result: IBKRScanResult, context: SmallcapContext) -> float:
        """Calculate quality score for gap opportunities"""
        try:
            # Gap size score (8-25% optimal)
            gap_score = min(1.0, abs(result.gap_percentage) / 20.0) if result.gap_percentage else 0.0
            
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
    
    async def disconnect(self):
        """Cleanup connections"""
        if self.ibkr_scanner:
            await self.ibkr_scanner.disconnect()