# scanner/smallcap/smallcap_daily_scanner.py
"""
SmallcapDailyScanner - Enhanced scanner specifically for smallcap daily plays
Combines the existing scanner functionality with intelligent filtering and auto-integration
"""

import asyncio
import logging
import json
import time
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

import yfinance as yf
import pandas as pd
from yahooquery import Ticker

from .smallcap_context import SmallcapContext
from .catalyst_analyzer import CatalystAnalyzer, CatalystInfo

# Import existing scanner components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scanner.daily_plays_filter import DailyPlaysFilter
    from scanner.news_sources import NewsExtractor
    from scanner.sentiment_analyzer import SentimentAnalyzer
except ImportError as e:
    logging.warning(f"Could not import existing scanner components: {e}")

logger = logging.getLogger(__name__)

@dataclass
class SmallcapPlay:
    """Represents a smallcap daily play opportunity"""
    symbol: str
    context: SmallcapContext
    catalyst: CatalystInfo
    quality_score: float
    trading_recommendation: Dict[str, Any]
    scan_timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'symbol': self.symbol,
            'context': asdict(self.context),
            'catalyst': asdict(self.catalyst),
            'quality_score': self.quality_score,
            'trading_recommendation': self.trading_recommendation,
            'scan_timestamp': self.scan_timestamp.isoformat()
        }

class SmallcapDailyScanner:
    """
    Enhanced scanner for smallcap daily plays
    
    Features:
    1. Integrates with existing ProRealTime scanner data
    2. Enhanced catalyst analysis using CatalystAnalyzer
    3. Auto-scoring and filtering
    4. Direct integration with trading system
    5. Market regime awareness (simplified for smallcaps)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.logger = logging.getLogger(f"{__name__}.SmallcapDailyScanner")
        
        # Initialize components
        self.catalyst_analyzer = CatalystAnalyzer()
        
        # Try to initialize existing components
        try:
            self.daily_plays_filter = DailyPlaysFilter()
            self.news_extractor = NewsExtractor()
            self.sentiment_analyzer = SentimentAnalyzer()
            self.legacy_components_available = True
        except Exception as e:
            self.logger.warning(f"Legacy components not available: {e}")
            self.legacy_components_available = False
        
        # Cache for API calls
        self.float_cache = {}
        self.news_cache = {}
        
        self.logger.info("SmallcapDailyScanner initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for scanner"""
        return {
            # Basic filters
            'min_gap_percent': 8.0,          # Minimum 8% gap
            'min_premarket_volume': 300_000,  # Minimum premarket volume
            'max_float': 100_000_000,         # Maximum float size
            'min_price': 0.50,                # Minimum price
            'max_price': 15.00,               # Maximum price for smallcaps
            
            # Quality filters
            'min_quality_score': 6.0,        # Minimum quality score (0-10)
            'min_catalyst_strength': 4,      # Minimum catalyst strength
            'max_news_age_hours': 24,        # Maximum news age
            
            # Market regime filters
            'vix_threshold': 35,              # Skip if VIX > 35 (high fear)
            'spy_trend_required': False,      # Don't require SPY trend for smallcaps
            
            # Output limits
            'max_plays_per_scan': 10,         # Maximum plays to return
            'min_premarket_volume_ratio': 0.1,  # 10% of average daily volume
            
            # API settings
            'rate_limit_delay': 0.5,          # Seconds between API calls
            'max_retries': 3,                 # Max retries for failed calls
        }
    
    async def scan_smallcap_plays(self, prorealtime_data: Optional[str] = None) -> List[SmallcapPlay]:
        """
        Main scanning function - enhanced version of existing scanner
        
        Args:
            prorealtime_data: Optional ProRealTime screener data (CSV format)
            
        Returns:
            List of SmallcapPlay objects sorted by quality score
        """
        self.logger.info("🔍 Starting SmallcapDailyScanner scan...")
        
        try:
            # Step 1: Get candidate symbols
            if prorealtime_data:
                candidates = self._parse_prorealtime_data(prorealtime_data)
            else:
                # Fallback to programmatic screening (less reliable)
                candidates = await self._programmatic_screen()
            
            self.logger.info(f"   📊 Found {len(candidates)} candidates from initial screening")
            
            # Step 2: Apply basic filters
            filtered_candidates = self._apply_basic_filters(candidates)
            self.logger.info(f"   ✅ {len(filtered_candidates)} candidates passed basic filters")
            
            # Step 3: Enhance with market data
            enhanced_candidates = await self._enhance_with_market_data(filtered_candidates)
            self.logger.info(f"   📈 Enhanced {len(enhanced_candidates)} candidates with market data")
            
            # Step 4: Analyze catalysts
            catalyst_analyzed = await self._analyze_catalysts(enhanced_candidates)
            self.logger.info(f"   📰 Analyzed catalysts for {len(catalyst_analyzed)} candidates")
            
            # Step 5: Create SmallcapPlay objects and score
            plays = []
            for candidate in catalyst_analyzed:
                try:
                    play = await self._create_smallcap_play(candidate)
                    if play and play.quality_score >= self.config['min_quality_score']:
                        plays.append(play)
                except Exception as e:
                    self.logger.error(f"Error creating play for {candidate.get('symbol', 'unknown')}: {e}")
            
            # Step 6: Sort by quality score and limit results
            plays.sort(key=lambda p: p.quality_score, reverse=True)
            final_plays = plays[:self.config['max_plays_per_scan']]
            
            self.logger.info(f"🎯 Final result: {len(final_plays)} high-quality smallcap plays")
            
            return final_plays
            
        except Exception as e:
            self.logger.error(f"Error in scan_smallcap_plays: {e}")
            return []
    
    def _parse_prorealtime_data(self, data: str) -> List[Dict[str, Any]]:
        """Parse ProRealTime screener data"""
        candidates = []
        
        lines = data.strip().split('\n')
        if len(lines) < 2:
            return candidates
        
        # Skip header line
        for line in lines[1:]:
            try:
                # Expected format: "TICKER" "NAME" "CRITERION" "%VAR" "VAR" "TIME" "LAST" "VOLUME"
                parts = [p.strip('"') for p in line.split('\t') if p.strip()]
                
                if len(parts) >= 8:
                    symbol = parts[0].upper()
                    var_percent = float(parts[3].replace('%', '').replace('+', '').replace(',', '.'))
                    price = float(parts[6].replace(',', '.'))
                    volume_str = parts[7]
                    
                    # Parse volume (could be "289M", "1.5K", etc.)
                    volume = self._parse_volume_string(volume_str)
                    
                    candidates.append({
                        'symbol': symbol,
                        'name': parts[1],
                        'gap_percent': var_percent,
                        'price': price,
                        'volume': volume,
                        'insertion_time': parts[5]
                    })
                    
            except Exception as e:
                self.logger.warning(f"Error parsing line '{line}': {e}")
                continue
        
        return candidates
    
    def _parse_volume_string(self, volume_str: str) -> int:
        """Parse volume string like '289M', '1.5K' to integer"""
        try:
            volume_str = volume_str.upper().replace(',', '.')
            
            if 'M' in volume_str:
                return int(float(volume_str.replace('M', '')) * 1_000_000)
            elif 'K' in volume_str:
                return int(float(volume_str.replace('K', '')) * 1_000)
            else:
                return int(float(volume_str))
        except:
            return 0
    
    async def _programmatic_screen(self) -> List[Dict[str, Any]]:
        """
        Fallback programmatic screening if no ProRealTime data
        (Less reliable but better than nothing)
        """
        self.logger.warning("Using programmatic screening - less reliable than ProRealTime data")
        # This would implement a basic screener using yfinance or other APIs
        # For now, return empty list
        return []
    
    def _apply_basic_filters(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply basic filters to candidates"""
        filtered = []
        
        for candidate in candidates:
            # Gap filter
            if candidate.get('gap_percent', 0) < self.config['min_gap_percent']:
                continue
            
            # Price filter
            price = candidate.get('price', 0)
            if price < self.config['min_price'] or price > self.config['max_price']:
                continue
            
            # Volume filter
            if candidate.get('volume', 0) < self.config['min_premarket_volume']:
                continue
            
            filtered.append(candidate)
        
        return filtered
    
    async def _enhance_with_market_data(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance candidates with additional market data"""
        enhanced = []
        
        for candidate in candidates:
            try:
                symbol = candidate['symbol']
                
                # Get float data
                float_data = await self._get_float_data(symbol)
                candidate.update(float_data)
                
                # Skip if float too large
                if candidate.get('float', 0) > self.config['max_float']:
                    continue
                
                # Get volume data
                volume_data = await self._get_volume_data(symbol)
                candidate.update(volume_data)
                
                # Apply volume ratio filter
                if candidate.get('premarket_volume_ratio', 0) < self.config['min_premarket_volume_ratio']:
                    continue
                
                enhanced.append(candidate)
                
                # Rate limiting
                await asyncio.sleep(self.config['rate_limit_delay'])
                
            except Exception as e:
                self.logger.warning(f"Error enhancing {candidate.get('symbol', 'unknown')}: {e}")
                continue
        
        return enhanced
    
    async def _get_float_data(self, symbol: str) -> Dict[str, Any]:
        """Get float and market cap data for symbol"""
        if symbol in self.float_cache:
            return self.float_cache[symbol]
        
        try:
            ticker = Ticker(symbol)
            info = ticker.summary_detail[symbol] if symbol in ticker.summary_detail else {}
            stats = ticker.key_stats[symbol] if symbol in ticker.key_stats else {}
            
            float_shares = stats.get('floatShares', 50_000_000)  # Default estimate
            market_cap = info.get('marketCap', float_shares * 2)  # Rough estimate
            
            result = {
                'float': float_shares,
                'market_cap': market_cap
            }
            
            self.float_cache[symbol] = result
            return result
            
        except Exception as e:
            self.logger.warning(f"Error getting float data for {symbol}: {e}")
            return {
                'float': 50_000_000,  # Conservative default
                'market_cap': 100_000_000
            }
    
    async def _get_volume_data(self, symbol: str) -> Dict[str, Any]:
        """Get volume comparison data"""
        try:
            # Get recent volume data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1d")
            
            if len(hist) > 0:
                avg_volume = hist['Volume'].mean()
                current_volume = hist['Volume'].iloc[-1] if len(hist) > 0 else 1_000_000
                
                premarket_volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.5
                
                return {
                    'avg_daily_volume': int(avg_volume),
                    'premarket_volume_ratio': premarket_volume_ratio
                }
            
        except Exception as e:
            self.logger.warning(f"Error getting volume data for {symbol}: {e}")
        
        return {
            'avg_daily_volume': 2_000_000,  # Default estimate
            'premarket_volume_ratio': 0.3
        }
    
    async def _analyze_catalysts(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze news catalysts for candidates"""
        enhanced_candidates = []
        
        # Get news for all symbols in batch
        symbols = [c['symbol'] for c in candidates]
        news_data = await self._get_news_batch(symbols)
        
        for candidate in candidates:
            symbol = candidate['symbol']
            headlines = news_data.get(symbol, [])
            
            # Analyze catalyst
            catalyst = self.catalyst_analyzer.analyze_multiple_headlines(headlines)
            
            # Skip if catalyst too weak
            if catalyst.strength < self.config['min_catalyst_strength']:
                continue
            
            # Skip if news too old
            if catalyst.age_hours > self.config['max_news_age_hours']:
                continue
            
            candidate['catalyst'] = catalyst
            enhanced_candidates.append(candidate)
        
        return enhanced_candidates
    
    async def _get_news_batch(self, symbols: List[str]) -> Dict[str, List[Tuple[str, float]]]:
        """Get news headlines for multiple symbols"""
        news_results = {}
        
        for symbol in symbols:
            try:
                if symbol in self.news_cache:
                    news_results[symbol] = self.news_cache[symbol]
                    continue
                
                # Get news from Yahoo Finance
                headlines = await self._get_symbol_news(symbol)
                news_results[symbol] = headlines
                self.news_cache[symbol] = headlines
                
                # Rate limiting
                await asyncio.sleep(self.config['rate_limit_delay'])
                
            except Exception as e:
                self.logger.warning(f"Error getting news for {symbol}: {e}")
                news_results[symbol] = []
        
        return news_results
    
    async def _get_symbol_news(self, symbol: str) -> List[Tuple[str, float]]:
        """Get news headlines for a single symbol"""
        try:
            ticker = Ticker(symbol)
            news = ticker.news
            
            headlines = []
            current_time = datetime.now()
            
            for article in news[:5]:  # Limit to 5 most recent
                headline = article.get('title', '')
                pub_time = datetime.fromtimestamp(article.get('providerPublishTime', 0))
                age_hours = (current_time - pub_time).total_seconds() / 3600
                
                headlines.append((headline, age_hours))
            
            return headlines
            
        except Exception as e:
            self.logger.warning(f"Error getting news for {symbol}: {e}")
            return []
    
    async def _create_smallcap_play(self, candidate: Dict[str, Any]) -> Optional[SmallcapPlay]:
        """Create SmallcapPlay object from candidate data"""
        try:
            # Create SmallcapContext
            context = SmallcapContext(
                symbol=candidate['symbol'],
                timestamp=datetime.now(),
                current_price=candidate['price'],
                gap_percentage=candidate['gap_percent'] / 100.0,
                premarket_high=candidate['price'],  # Simplified
                premarket_low=candidate['price'] * 0.95,  # Simplified
                premarket_volume=candidate['volume'],
                avg_daily_volume=candidate['avg_daily_volume'],
                premarket_volume_ratio=candidate['premarket_volume_ratio'],
                news_catalyst_type=candidate['catalyst'].catalyst_type,
                news_age_hours=candidate['catalyst'].age_hours,
                catalyst_strength=candidate['catalyst'].strength,
                float_size=candidate['float'],
                market_cap=candidate['market_cap'],
                price_vs_premarket_high=1.0,  # Simplified
                volume_spike_confirmed=candidate['premarket_volume_ratio'] > 0.3,
                market_fear_level=self._get_market_fear_level()
            )
            
            # Check if tradeable
            if not context.is_tradeable():
                return None
            
            # Calculate quality score
            quality_score = context.get_play_quality_score()
            
            # Get trading recommendation
            trading_rec = self.catalyst_analyzer.get_catalyst_trading_recommendation(candidate['catalyst'])
            
            return SmallcapPlay(
                symbol=candidate['symbol'],
                context=context,
                catalyst=candidate['catalyst'],
                quality_score=quality_score,
                trading_recommendation=trading_rec,
                scan_timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error creating SmallcapPlay for {candidate.get('symbol', 'unknown')}: {e}")
            return None
    
    def _get_market_fear_level(self) -> str:
        """Simple market fear assessment based on VIX (if available)"""
        try:
            # This would get real VIX data
            # For now, return default
            return 'LOW'
        except:
            return 'MEDIUM'
    
    def get_formatted_output(self, plays: List[SmallcapPlay]) -> str:
        """Get formatted output for trading system integration"""
        if not plays:
            return "No high-quality smallcap plays found."
        
        # Format for direct copy-paste into trading system
        symbols = [play.symbol for play in plays]
        symbol_string = ", ".join(symbols)
        
        output = f"🎯 SMALLCAP DAILY PLAYS ({len(plays)} found):\n"
        output += f"📋 Symbols: {symbol_string}\n\n"
        
        output += "📊 PLAY DETAILS:\n"
        for i, play in enumerate(plays, 1):
            ctx = play.context
            cat = play.catalyst
            
            output += f"{i}. {play.symbol} (Score: {play.quality_score:.1f}/10)\n"
            output += f"   Gap: {ctx.gap_percentage*100:.1f}% | Price: ${ctx.current_price:.2f}\n"
            output += f"   Catalyst: {cat.catalyst_type} (Strength: {cat.strength}/10)\n"
            output += f"   Volume: {ctx.premarket_volume_ratio:.1f}x avg | Float: {ctx.float_size/1e6:.1f}M\n"
            output += f"   Rec: {play.trading_recommendation.get('strategy_preference', 'standard')}\n\n"
        
        return output
    
    def save_scan_results(self, plays: List[SmallcapPlay], filename: Optional[str] = None) -> str:
        """Save scan results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"smallcap_scan_{timestamp}.json"
        
        filepath = os.path.join("scanner", "smallcap", "results", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'scan_timestamp': datetime.now().isoformat(),
            'plays_count': len(plays),
            'plays': [play.to_dict() for play in plays]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Scan results saved to {filepath}")
        return filepath