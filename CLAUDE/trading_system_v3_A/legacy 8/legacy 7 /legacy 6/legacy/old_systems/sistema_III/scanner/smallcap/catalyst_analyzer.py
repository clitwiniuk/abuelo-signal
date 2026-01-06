# scanner/smallcap/catalyst_analyzer.py
"""
CatalystAnalyzer - Analyzes news catalysts specifically for smallcap daily plays
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import FinBERT analyzer
try:
    from .finbert_analyzer import FinBERTAnalyzer
    FINBERT_AVAILABLE = True
except ImportError:
    try:
        from finbert_analyzer import FinBERTAnalyzer
        FINBERT_AVAILABLE = True
    except ImportError:
        FINBERT_AVAILABLE = False
        FinBERTAnalyzer = None

logger = logging.getLogger(__name__)

@dataclass
class CatalystInfo:
    """Information about a news catalyst"""
    catalyst_type: str          # FDA/EARNINGS/CONTRACT/M&A/OTHER
    strength: int               # 1-10 scale
    age_hours: float            # Hours since news
    keywords_found: List[str]   # Keywords that triggered this classification
    headline: str               # Original headline
    confidence: float           # 0-1 confidence in classification

class CatalystAnalyzer:
    """
    Analyzer specifically tuned for smallcap catalysts
    Much simpler than generic news analysis - focused on what moves smallcaps
    """
    
    # Catalyst patterns with weights
    CATALYST_PATTERNS = {
        'FDA': {
            'keywords': [
                'fda', 'fda approval', 'drug approval', 'clinical trial', 'phase i', 'phase ii', 'phase iii',
                'breakthrough therapy', 'orphan drug', 'fast track', 'priority review', 'biologics',
                'new drug application', 'nda', 'anda', 'investigational new drug', 'ind',
                'clinical data', 'trial results', 'regulatory approval', 'medical device'
            ],
            'strength_multiplier': 1.0,  # FDA news is massive for biotechs
            'base_strength': 8
        },
        
        'EARNINGS': {
            'keywords': [
                'earnings', 'quarterly results', 'q1 results', 'q2 results', 'q3 results', 'q4 results',
                'revenue beat', 'earnings beat', 'guidance raised', 'guidance increased', 'outlook',
                'profit', 'loss', 'eps', 'revenue', 'sales growth', 'record revenue'
            ],
            'strength_multiplier': 0.8,
            'base_strength': 6
        },
        
        'CONTRACT': {
            'keywords': [
                'contract', 'agreement', 'deal', 'order', 'awarded', 'selected', 'chosen',
                'partnership', 'collaboration', 'joint venture', 'license agreement',
                'supply agreement', 'distribution agreement', 'manufacturing agreement',
                'government contract', 'military contract', 'wins contract'
            ],
            'strength_multiplier': 0.9,
            'base_strength': 6
        },
        
        'M&A': {
            'keywords': [
                'acquisition', 'merger', 'buyout', 'takeover', 'acquired by', 'agrees to acquire',
                'purchase agreement', 'definitive agreement', 'cash offer', 'tender offer',
                'strategic buyer', 'private equity', 'going private'
            ],
            'strength_multiplier': 1.2,  # M&A can be huge for smallcaps
            'base_strength': 9
        },
        
        'BREAKTHROUGH': {
            'keywords': [
                'breakthrough', 'innovation', 'patent', 'patent approval', 'intellectual property',
                'technology advance', 'revolutionary', 'game changing', 'first of its kind',
                'proprietary', 'exclusive', 'patent granted'
            ],
            'strength_multiplier': 0.9,
            'base_strength': 7
        }
    }
    
    # Negative keywords that reduce strength
    NEGATIVE_KEYWORDS = [
        'delayed', 'postponed', 'failed', 'rejected', 'rejects', 'denied', 'declined',
        'investigation', 'lawsuit', 'fraud', 'sec investigation', 'fda warning',
        'recall', 'suspension', 'halt', 'regulatory action', 'safety concerns'
    ]
    
    def __init__(self, intraday_config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(f"{__name__}.CatalystAnalyzer")
        
        # Intraday-specific configuration for news aging
        self.intraday_config = intraday_config or self._get_default_intraday_config()
        
        # Initialize FinBERT analyzer if available
        self.finbert_analyzer = None
        if FINBERT_AVAILABLE:
            try:
                self.finbert_analyzer = FinBERTAnalyzer()
                self.logger.info("✅ FinBERT analyzer initialized - using advanced sentiment analysis")
            except Exception as e:
                self.logger.warning(f"Failed to initialize FinBERT: {e} - falling back to keyword analysis")
                self.finbert_analyzer = None
        else:
            self.logger.info("FinBERT not available - using keyword-based analysis")
        
        self.logger.info("CatalystAnalyzer initialized with intraday smallcap configuration")
        self.logger.info(f"Max news age limits: {self.intraday_config['catalyst_max_age']}")
    
    def _get_default_intraday_config(self) -> Dict[str, Any]:
        """Default configuration optimized for intraday smallcap trading"""
        return {
            # Catalyst-specific aging limits (hours)
            'catalyst_max_age': {
                'FDA': 4,                     # FDA momentum fades quickly
                'M&A': 6,                     # M&A has short momentum window
                'EARNINGS': 8,                # Earnings can sustain longer
                'CONTRACT': 12,               # Contracts more sustained
                'BREAKTHROUGH': 6,            # Breakthrough momentum medium
                'OTHER': 6                    # Default for unclassified
            },
            
            # News age strength multipliers
            'news_age_multipliers': {
                'fresh': 1.0,                 # 0-2 hours: full strength
                'recent': 0.9,                # 2-6 hours: 90% strength
                'stale': 0.6,                 # 6-12 hours: 60% strength
                'expired': 0.0                # 12+ hours: reject
            },
            
            # Timing thresholds (hours)
            'fresh_news_threshold': 2,        # Fresh news cutoff
            'recent_news_threshold': 8,       # Recent news cutoff (extended for CONTRACT)
            'stale_news_threshold': 14,       # Stale news cutoff
            
            # Global max age for any news (fallback)
            'max_news_age_hours': 8,          # Hard limit for intraday
            'max_news_age_premarket': 16,     # Allow overnight news in premarket
        }
    
    def analyze_headline(self, headline: str, news_age_hours: float = 0.0) -> CatalystInfo:
        """
        Analyze a single headline for catalyst information
        Uses FinBERT if available, otherwise falls back to keyword analysis
        
        Args:
            headline: News headline to analyze
            news_age_hours: Hours since news was published
            
        Returns:
            CatalystInfo with classification and strength
        """
        # Try FinBERT analysis first
        if self.finbert_analyzer:
            try:
                finbert_result = self.finbert_analyzer.analyze_headline(headline, news_age_hours)
                
                # Apply intraday time limits
                final_strength = finbert_result.catalyst_strength
                catalyst_max_age = self.intraday_config['catalyst_max_age'].get(finbert_result.catalyst_type, 6)
                
                if news_age_hours > catalyst_max_age:
                    self.logger.debug(f"FinBERT: News too old for {finbert_result.catalyst_type}: {news_age_hours:.1f}h > {catalyst_max_age}h")
                    # Less aggressive penalty for strong FinBERT results
                    if finbert_result.catalyst_strength >= 8:
                        final_strength = max(5, int(final_strength * 0.6))  # Keep strong catalysts viable
                    elif finbert_result.catalyst_strength >= 6:
                        final_strength = max(3, int(final_strength * 0.5))  # Medium reduction
                    else:
                        final_strength = max(1, int(final_strength * 0.3))  # Severe reduction for weak catalysts
                
                return CatalystInfo(
                    catalyst_type=finbert_result.catalyst_type,
                    strength=final_strength,
                    age_hours=news_age_hours,
                    keywords_found=finbert_result.keywords_found,
                    headline=headline,
                    confidence=finbert_result.confidence
                )
                
            except Exception as e:
                self.logger.warning(f"FinBERT analysis failed for '{headline[:50]}...': {e}")
                # Fall through to keyword analysis
        
        # Fallback to original keyword-based analysis
        return self._analyze_headline_keywords(headline, news_age_hours)
    
    def _analyze_headline_keywords(self, headline: str, news_age_hours: float = 0.0) -> CatalystInfo:
        """Original keyword-based analysis as fallback"""
        headline_lower = headline.lower()
        
        best_match = None
        best_strength = 0
        best_keywords = []
        best_type = 'OTHER'
        
        # Check each catalyst type
        for catalyst_type, pattern_info in self.CATALYST_PATTERNS.items():
            keywords_found = []
            
            # Find matching keywords
            for keyword in pattern_info['keywords']:
                if keyword in headline_lower:
                    keywords_found.append(keyword)
            
            if keywords_found:
                # Calculate strength based on keywords found and pattern strength
                base_strength = pattern_info['base_strength']
                keyword_bonus = min(len(keywords_found) * 0.5, 2.0)  # Max 2 bonus points
                multiplier = pattern_info['strength_multiplier']
                
                strength = (base_strength + keyword_bonus) * multiplier
                
                # Check for negative keywords that reduce strength
                negative_count = sum(1 for neg_word in self.NEGATIVE_KEYWORDS 
                                   if neg_word in headline_lower)
                strength -= negative_count * 3.0  # -3 points per negative keyword
                
                if strength > best_strength:
                    best_strength = strength
                    best_keywords = keywords_found
                    best_type = catalyst_type
                    best_match = pattern_info
        
        # Apply intraday time decay - much more aggressive for smallcaps
        if news_age_hours > 0:
            # First check if news exceeds basic catalyst type age limits (ignoring premarket)
            catalyst_max_age = self.intraday_config['catalyst_max_age'].get(best_type, 6)
            if news_age_hours > catalyst_max_age:
                # News too old for this catalyst type - return minimal strength
                best_strength = 1
                self.logger.debug(f"Keywords: News too old for {best_type}: {news_age_hours:.1f}h > {catalyst_max_age}h limit")
            else:
                # Apply intraday time decay multiplier
                time_multiplier = self._calculate_intraday_time_multiplier(news_age_hours)
                best_strength *= time_multiplier
                self.logger.debug(f"Keywords: Applied time multiplier {time_multiplier:.2f} for {news_age_hours:.1f}h old {best_type} news")
        
        # Ensure strength is in valid range
        best_strength = max(1, min(10, int(best_strength)))
        
        # Calculate confidence based on number of keywords and strength
        confidence = min(1.0, len(best_keywords) * 0.3 + (best_strength / 10.0) * 0.7)
        
        return CatalystInfo(
            catalyst_type=best_type,
            strength=best_strength,
            age_hours=news_age_hours,
            keywords_found=best_keywords,
            headline=headline,
            confidence=confidence
        )
    
    def _is_news_viable_for_intraday(self, catalyst_type: str, age_hours: float, force_market_hours: bool = False) -> bool:
        """
        Check if news is still viable for intraday trading based on catalyst type
        
        Args:
            catalyst_type: Type of catalyst (FDA, M&A, etc.)
            age_hours: Age of news in hours
            force_market_hours: If True, use market hours logic regardless of current time
            
        Returns:
            bool: True if news is still viable for intraday trading
        """
        max_age = self.intraday_config['catalyst_max_age'].get(catalyst_type, 6)
        
        # Special handling for premarket hours (allow overnight news)
        if not force_market_hours:
            from datetime import timezone, timedelta
            est_timezone = timezone(timedelta(hours=-5))
            current_hour = datetime.now(est_timezone).hour
            is_premarket = 4 <= current_hour <= 9  # 4:00 AM - 9:30 AM EST
            
            if is_premarket:
                max_age = self.intraday_config['max_news_age_premarket']
        
        return age_hours <= max_age
    
    def _calculate_intraday_time_multiplier(self, age_hours: float) -> float:
        """
        Calculate aggressive time decay multiplier optimized for intraday smallcap trading
        
        Args:
            age_hours: Age of news in hours
            
        Returns:
            float: Multiplier (0.0 to 1.0) to apply to catalyst strength
        """
        config = self.intraday_config
        
        if age_hours <= config['fresh_news_threshold']:
            # Fresh news (0-2h): Full strength
            return config['news_age_multipliers']['fresh']
        elif age_hours <= config['recent_news_threshold']:
            # Recent news (2-6h): 80% strength
            return config['news_age_multipliers']['recent']
        elif age_hours <= config['stale_news_threshold']:
            # Stale news (6-12h): 50% strength
            return config['news_age_multipliers']['stale']
        else:
            # Expired news (12h+): Reject
            return config['news_age_multipliers']['expired']
    
    def _calculate_time_decay(self, age_hours: float) -> float:
        """
        LEGACY METHOD - Use _calculate_intraday_time_multiplier instead
        Kept for backward compatibility
        """
        return self._calculate_intraday_time_multiplier(age_hours)
    
    def analyze_multiple_headlines(self, headlines: List[Tuple[str, float]]) -> CatalystInfo:
        """
        Analyze multiple headlines and return the strongest catalyst
        
        Args:
            headlines: List of (headline, age_hours) tuples
            
        Returns:
            CatalystInfo for the strongest catalyst found
        """
        if not headlines:
            return CatalystInfo(
                catalyst_type='OTHER',
                strength=1,
                age_hours=24.0,
                keywords_found=[],
                headline='No news found',
                confidence=0.0
            )
        
        best_catalyst = None
        
        for headline, age_hours in headlines:
            catalyst = self.analyze_headline(headline, age_hours)
            
            if best_catalyst is None or catalyst.strength > best_catalyst.strength:
                best_catalyst = catalyst
        
        return best_catalyst
    
    def get_catalyst_trading_recommendation(self, catalyst: CatalystInfo) -> Dict[str, Any]:
        """
        Get trading recommendations based on catalyst analysis
        """
        recommendations = {
            'should_trade': False,
            'urgency': 'LOW',
            'strategy_preference': 'conservative',
            'time_horizon': 'intraday',
            'risk_multiplier': 1.0
        }
        
        # FDA catalysts
        if catalyst.catalyst_type == 'FDA' and catalyst.strength >= 7:
            recommendations.update({
                'should_trade': True,
                'urgency': 'HIGH' if catalyst.age_hours < 4 else 'MEDIUM',
                'strategy_preference': 'aggressive_momentum',
                'risk_multiplier': 1.5
            })
        
        # M&A catalysts
        elif catalyst.catalyst_type == 'M&A' and catalyst.strength >= 8:
            recommendations.update({
                'should_trade': True,
                'urgency': 'HIGH',
                'strategy_preference': 'gap_go',
                'risk_multiplier': 2.0  # M&A can be massive moves
            })
        
        # Strong earnings
        elif catalyst.catalyst_type == 'EARNINGS' and catalyst.strength >= 6:
            recommendations.update({
                'should_trade': True,
                'urgency': 'MEDIUM',
                'strategy_preference': 'volume_momentum',
                'risk_multiplier': 1.2
            })
        
        # Contract news
        elif catalyst.catalyst_type == 'CONTRACT' and catalyst.strength >= 5:
            recommendations.update({
                'should_trade': True,
                'urgency': 'MEDIUM',
                'strategy_preference': 'daily_plays',
                'risk_multiplier': 1.1
            })
        
        # Adjust for news age
        if catalyst.age_hours > 12:
            recommendations['urgency'] = 'LOW'
            recommendations['risk_multiplier'] *= 0.8
        
        return recommendations
    
    def batch_analyze_symbols(self, symbol_headlines: Dict[str, List[Tuple[str, float]]]) -> Dict[str, CatalystInfo]:
        """
        Analyze catalysts for multiple symbols
        
        Args:
            symbol_headlines: Dict of {symbol: [(headline, age_hours), ...]}
            
        Returns:
            Dict of {symbol: CatalystInfo}
        """
        results = {}
        
        for symbol, headlines in symbol_headlines.items():
            try:
                catalyst_info = self.analyze_multiple_headlines(headlines)
                results[symbol] = catalyst_info
                
                self.logger.debug(f"Catalyst analysis for {symbol}: "
                                f"{catalyst_info.catalyst_type} "
                                f"(strength: {catalyst_info.strength})")
                
            except Exception as e:
                self.logger.error(f"Error analyzing catalyst for {symbol}: {e}")
                results[symbol] = CatalystInfo(
                    catalyst_type='OTHER',
                    strength=1,
                    age_hours=24.0,
                    keywords_found=[],
                    headline='Analysis error',
                    confidence=0.0
                )
        
        return results