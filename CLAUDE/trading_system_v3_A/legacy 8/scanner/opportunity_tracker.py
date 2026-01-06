"""
Opportunity Tracker - Intelligent Deduplication for Scanner
Tracks sent opportunities and determines when re-scanning is warranted.
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TrackedOpportunity:
    """Stores metadata about a sent opportunity"""
    symbol: str
    opportunity_type: str
    scan_time: datetime
    quality_score: float
    volume_ratio: float
    gap_percentage: float
    current_price: float
    finbert_sentiment: float = 0.0
    catalyst_type: str = ""
    catalyst_strength: int = 0


class OpportunityTracker:
    """
    Tracks sent opportunities and determines when re-scanning is warranted.
    
    Re-send triggers:
    - CATALYST_CHANGE: FinBERT sentiment changed significantly (>0.3 delta)
    - VOLUME_SURGE: Volume increased >50%
    - BREAKOUT: Price moved >5% from last scan
    - QUALITY_UPGRADE: Quality score improved >15 points
    - NEW_OPPORTUNITY_TYPE: Different pattern detected
    - PERIODIC_REFRESH: 30+ minutes since last scan
    """
    
    def __init__(self, 
                 catalyst_threshold: float = 0.3,
                 volume_threshold: float = 0.5,
                 price_threshold: float = 0.05,
                 quality_threshold: float = 15.0,
                 refresh_interval_minutes: int = 30):
        """
        Initialize tracker with configurable thresholds.
        
        Args:
            catalyst_threshold: Min sentiment change to trigger update (0.3 = 30%)
            volume_threshold: Min volume ratio increase to trigger update (0.5 = 50%)
            price_threshold: Min price change to trigger update (0.05 = 5%)
            quality_threshold: Min quality score increase to trigger update (15 points)
            refresh_interval_minutes: Minutes before periodic refresh (30)
        """
        self.tracked: Dict[str, TrackedOpportunity] = {}
        
        # Thresholds
        self.catalyst_threshold = catalyst_threshold
        self.volume_threshold = volume_threshold
        self.price_threshold = price_threshold
        self.quality_threshold = quality_threshold
        self.refresh_interval_minutes = refresh_interval_minutes
        
        logger.info(f"📊 OpportunityTracker initialized with thresholds: "
                   f"catalyst={catalyst_threshold}, volume={volume_threshold}, "
                   f"price={price_threshold}, quality={quality_threshold}")
    
    def should_rescan(self, symbol: str, new_opportunity: Dict) -> Tuple[bool, str]:
        """
        Determine if opportunity should be re-sent.
        
        Returns:
            (should_send: bool, update_reason: str)
        """
        # First time seeing this symbol today
        if symbol not in self.tracked:
            return True, "FIRST_SCAN"
        
        tracked = self.tracked[symbol]
        now = datetime.now()
        
        # Check for material changes
        changes = self._detect_changes(tracked, new_opportunity, now)
        
        if changes:
            reason = changes[0]  # Primary reason
            logger.info(f"🔄 {symbol}: Re-scan triggered - {reason}")
            return True, reason
        
        # No material changes
        return False, "NO_CHANGE"
    
    def _detect_changes(self, 
                       tracked: TrackedOpportunity, 
                       new_opp: Dict,
                       now: datetime) -> list:
        """
        Detect material changes between tracked and new opportunity.
        
        Returns list of change reasons (empty if no changes).
        """
        changes = []
        
        # 1. Different opportunity type
        new_type = new_opp.get('opportunity_type', '')
        if new_type != tracked.opportunity_type:
            changes.append('NEW_OPPORTUNITY_TYPE')
        
        # 2. Catalyst change (FinBERT sentiment)
        new_sentiment = new_opp.get('finbert_sentiment', 0.0)
        sentiment_delta = abs(new_sentiment - tracked.finbert_sentiment)
        if sentiment_delta >= self.catalyst_threshold:
            changes.append('CATALYST_CHANGE')
        
        # 3. Volume surge
        new_volume_ratio = new_opp.get('volume_ratio', 0.0)
        volume_increase = (new_volume_ratio - tracked.volume_ratio) / max(tracked.volume_ratio, 0.1)
        if volume_increase >= self.volume_threshold:
            changes.append('VOLUME_SURGE')
        
        # 4. Price breakout
        new_price = new_opp.get('current_price', 0.0)
        price_change = abs(new_price - tracked.current_price) / max(tracked.current_price, 0.01)
        if price_change >= self.price_threshold:
            changes.append('BREAKOUT')
        
        # 5. Quality upgrade
        new_quality = new_opp.get('quality_score', 0.0)
        quality_delta = new_quality - tracked.quality_score
        if quality_delta >= self.quality_threshold:
            changes.append('QUALITY_UPGRADE')
        
        # 6. Periodic refresh (30+ minutes)
        minutes_since_scan = (now - tracked.scan_time).total_seconds() / 60
        if minutes_since_scan >= self.refresh_interval_minutes:
            changes.append('PERIODIC_REFRESH')
        
        return changes
    
    def get_changes(self, symbol: str, new_opportunity: Dict) -> Dict:
        """
        Calculate detailed change metrics between tracked and new opportunity.
        
        Returns dict with old/new values for changed fields.
        """
        if symbol not in self.tracked:
            return {}
        
        tracked = self.tracked[symbol]
        changes_detail = {}
        
        # Catalyst changes
        new_sentiment = new_opportunity.get('finbert_sentiment', 0.0)
        if abs(new_sentiment - tracked.finbert_sentiment) >= self.catalyst_threshold:
            changes_detail['catalyst'] = {
                'old_sentiment': tracked.finbert_sentiment,
                'new_sentiment': new_sentiment,
                'old_type': tracked.catalyst_type,
                'new_type': new_opportunity.get('catalyst_type', ''),
                'sentiment_delta': new_sentiment - tracked.finbert_sentiment
            }
        
        # Volume changes
        new_volume = new_opportunity.get('volume_ratio', 0.0)
        volume_increase = (new_volume - tracked.volume_ratio) / max(tracked.volume_ratio, 0.1)
        if volume_increase >= self.volume_threshold:
            changes_detail['volume_ratio'] = {
                'old': tracked.volume_ratio,
                'new': new_volume,
                'increase_pct': volume_increase * 100
            }
        
        # Price changes
        new_price = new_opportunity.get('current_price', 0.0)
        price_change = (new_price - tracked.current_price) / max(tracked.current_price, 0.01)
        if abs(price_change) >= self.price_threshold:
            changes_detail['price'] = {
                'old': tracked.current_price,
                'new': new_price,
                'change_pct': price_change * 100
            }
        
        # Quality changes
        new_quality = new_opportunity.get('quality_score', 0.0)
        if (new_quality - tracked.quality_score) >= self.quality_threshold:
            changes_detail['quality_score'] = {
                'old': tracked.quality_score,
                'new': new_quality,
                'improvement': new_quality - tracked.quality_score
            }
        
        return changes_detail
    
    def track_opportunity(self, symbol: str, opportunity: Dict):
        """Store opportunity in tracker after sending."""
        self.tracked[symbol] = TrackedOpportunity(
            symbol=symbol,
            opportunity_type=opportunity.get('opportunity_type', ''),
            scan_time=datetime.now(),
            quality_score=opportunity.get('quality_score', 0.0),
            volume_ratio=opportunity.get('volume_ratio', 0.0),
            gap_percentage=opportunity.get('gap_percentage', 0.0),
            current_price=opportunity.get('current_price', 0.0),
            finbert_sentiment=opportunity.get('finbert_sentiment', 0.0),
            catalyst_type=opportunity.get('catalyst_type', ''),
            catalyst_strength=opportunity.get('catalyst_strength', 0)
        )
        
        logger.debug(f"📝 Tracked {symbol}: type={opportunity.get('opportunity_type')}, "
                    f"quality={opportunity.get('quality_score'):.1f}")
    
    def reset_daily(self):
        """Clear tracker at market open (new trading day)."""
        count = len(self.tracked)
        self.tracked.clear()
        logger.info(f"🔄 OpportunityTracker reset - cleared {count} tracked symbols")
    
    def get_tracked_count(self) -> int:
        """Get number of currently tracked symbols."""
        return len(self.tracked)
    
    def is_tracked(self, symbol: str) -> bool:
        """Check if symbol is currently tracked."""
        return symbol in self.tracked
