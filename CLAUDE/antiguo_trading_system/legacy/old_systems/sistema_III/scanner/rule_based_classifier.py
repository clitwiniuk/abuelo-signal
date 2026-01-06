#!/usr/bin/env python3
"""
Rule-Based Scanner Classifier for Sistema_III
Integrates with existing scanner_main.py to classify opportunities by strategy
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

@dataclass
class MarketContext:
    """Market context for classification - built from your existing scanner data"""
    symbol: str
    current_price: float
    gap_percent: float
    volume_ratio: float
    spread_percent: float = 1.0  # Default if not available
    market_cap_millions: Optional[float] = None
    news_sentiment: Optional[float] = None
    news_count: int = 0
    earnings_days_away: Optional[int] = None

@dataclass
class ClassificationResult:
    """Result of ticker classification"""
    symbol: str
    primary_strategy: str  # gap_go, daily_plays, macdv, bull_flag
    confidence_score: float  # 0.0 to 1.0
    reasoning: List[str]  # Why this classification
    metadata: Dict[str, Any] = None

class RuleBasedClassifier:
    """
    Intelligent ticker classifier - integrates with your scanner_main.py
    Routes tickers to specialized workers based on market characteristics
    """

    def __init__(self):
        self.logger = logging.getLogger("Classifier")

    def classify_ticker(self, context: MarketContext) -> ClassificationResult:
        """
        Main classification logic - route ticker to optimal strategy worker
        """
        try:
            reasoning = []
            primary_strategy = None
            confidence_score = 0.0

            # Rule 1: HIGH VOLUME + NEWS → DAILY_PLAYS (News-driven momentum)
            if self._is_daily_plays_candidate(context):
                primary_strategy = "daily_plays"
                confidence_score, rule_reasoning = self._score_daily_plays(context)
                reasoning.extend(rule_reasoning)

            # Rule 2: MEAN REVERSION CONDITIONS → GAP_GO (Gap fill plays)
            elif self._is_gap_go_candidate(context):
                primary_strategy = "gap_go"
                confidence_score, rule_reasoning = self._score_gap_go(context)
                reasoning.extend(rule_reasoning)

            # Rule 3: MOMENTUM CONTINUATION → BULL_FLAG (Pattern breakouts)
            elif self._is_bull_flag_candidate(context):
                primary_strategy = "bull_flag"
                confidence_score, rule_reasoning = self._score_bull_flag(context)
                reasoning.extend(rule_reasoning)

            # Rule 4: BASELINE/DEFAULT → MACDV (Technical baseline)
            else:
                primary_strategy = "macdv"
                confidence_score, rule_reasoning = self._score_macdv(context)
                reasoning.extend(rule_reasoning)

            self.logger.info(f"📊 {context.symbol} → {primary_strategy.upper()} (confidence: {confidence_score:.2f})")

            return ClassificationResult(
                symbol=context.symbol,
                primary_strategy=primary_strategy,
                confidence_score=confidence_score,
                reasoning=reasoning,
                metadata=self._build_metadata(context)
            )

        except Exception as e:
            self.logger.error(f"❌ Classification failed for {context.symbol}: {e}")
            # Emergency fallback to MACDV
            return ClassificationResult(
                symbol=context.symbol,
                primary_strategy="macdv",
                confidence_score=0.3,
                reasoning=[f"Classification error, fallback to MACDV"],
                metadata={}
            )

    def _is_daily_plays_candidate(self, context: MarketContext) -> bool:
        """High volume + news/catalyst = daily momentum play"""
        high_volume = context.volume_ratio >= 4.0
        has_news = context.news_count >= 2 or (context.news_sentiment and context.news_sentiment > 0.6)
        significant_gap = abs(context.gap_percent) >= 3.0

        return high_volume and (has_news or significant_gap)

    def _score_daily_plays(self, context: MarketContext) -> Tuple[float, List[str]]:
        """Score daily plays setup"""
        score = 0.0
        reasoning = []

        # Volume component (40% of score)
        if context.volume_ratio >= 8.0:
            score += 0.4
            reasoning.append(f"Extreme volume: {context.volume_ratio:.1f}x")
        elif context.volume_ratio >= 5.0:
            score += 0.3
            reasoning.append(f"High volume: {context.volume_ratio:.1f}x")
        elif context.volume_ratio >= 4.0:
            score += 0.2
            reasoning.append(f"Elevated volume: {context.volume_ratio:.1f}x")

        # News/Catalyst component (30% of score)
        if context.news_count >= 3:
            score += 0.25
            reasoning.append(f"Multiple news: {context.news_count}")
        elif context.news_count >= 1:
            score += 0.15
            reasoning.append(f"News catalyst: {context.news_count}")

        if context.news_sentiment and context.news_sentiment > 0.7:
            score += 0.15
            reasoning.append(f"Positive sentiment: {context.news_sentiment:.2f}")
        elif context.news_sentiment and context.news_sentiment > 0.5:
            score += 0.1
            reasoning.append(f"Good sentiment: {context.news_sentiment:.2f}")

        # Gap component (20% of score)
        gap_abs = abs(context.gap_percent)
        if gap_abs >= 8.0:
            score += 0.2
            reasoning.append(f"Large gap: {context.gap_percent:.1f}%")
        elif gap_abs >= 5.0:
            score += 0.15
            reasoning.append(f"Medium gap: {context.gap_percent:.1f}%")

        # Price suitability (10% of score)
        if 2.0 <= context.current_price <= 12.0:
            score += 0.1
            reasoning.append(f"Good price: ${context.current_price:.2f}")

        return min(score, 1.0), reasoning

    def _is_gap_go_candidate(self, context: MarketContext) -> bool:
        """Low-med volume + manageable gap = mean reversion"""
        moderate_volume = 1.5 <= context.volume_ratio <= 4.0
        manageable_gap = 1.5 <= abs(context.gap_percent) <= 6.0
        not_too_newsy = context.news_count <= 2

        return moderate_volume and manageable_gap and not_too_newsy

    def _score_gap_go(self, context: MarketContext) -> Tuple[float, List[str]]:
        """Score gap-go mean reversion setup"""
        score = 0.0
        reasoning = []

        # Gap size component (40% of score) - sweet spot for mean reversion
        gap_abs = abs(context.gap_percent)
        if 2.0 <= gap_abs <= 4.0:
            score += 0.4
            reasoning.append(f"Ideal gap for reversion: {context.gap_percent:.1f}%")
        elif 1.5 <= gap_abs <= 6.0:
            score += 0.3
            reasoning.append(f"Workable gap: {context.gap_percent:.1f}%")

        # Volume component (30% of score) - not too hot
        if 1.8 <= context.volume_ratio <= 3.0:
            score += 0.3
            reasoning.append(f"Perfect volume: {context.volume_ratio:.1f}x")
        elif 1.5 <= context.volume_ratio <= 4.0:
            score += 0.2
            reasoning.append(f"Good volume: {context.volume_ratio:.1f}x")

        # Price range component (20% of score)
        if 3.0 <= context.current_price <= 10.0:
            score += 0.2
            reasoning.append(f"Sweet spot price: ${context.current_price:.2f}")

        # Low news = better for mean reversion (10% of score)
        if context.news_count <= 1:
            score += 0.1
            reasoning.append("Low news noise")

        return min(score, 1.0), reasoning

    def _is_bull_flag_candidate(self, context: MarketContext) -> bool:
        """Medium gap + medium volume + decent price = continuation pattern"""
        momentum_volume = 2.0 <= context.volume_ratio <= 8.0
        momentum_gap = 1.0 <= abs(context.gap_percent) <= 5.0
        good_price = 2.0 <= context.current_price <= 15.0

        return momentum_volume and momentum_gap and good_price

    def _score_bull_flag(self, context: MarketContext) -> Tuple[float, List[str]]:
        """Score bull flag continuation setup"""
        score = 0.0
        reasoning = []

        # Positive gap momentum (35% of score)
        if context.gap_percent > 0:  # Positive gaps preferred for bull flags
            if 1.5 <= context.gap_percent <= 3.0:
                score += 0.35
                reasoning.append(f"Bullish gap momentum: +{context.gap_percent:.1f}%")
            elif 1.0 <= context.gap_percent <= 4.0:
                score += 0.25
                reasoning.append(f"Positive gap: +{context.gap_percent:.1f}%")
        else:
            # Negative gaps get lower score but still possible
            gap_abs = abs(context.gap_percent)
            if gap_abs <= 2.0:
                score += 0.15
                reasoning.append(f"Small negative gap: {context.gap_percent:.1f}%")

        # Volume pattern (30% of score)
        if 2.5 <= context.volume_ratio <= 5.0:
            score += 0.3
            reasoning.append(f"Flag volume: {context.volume_ratio:.1f}x")
        elif 2.0 <= context.volume_ratio <= 7.0:
            score += 0.2
            reasoning.append(f"Decent volume: {context.volume_ratio:.1f}x")

        # Price suitability (25% of score)
        if 3.0 <= context.current_price <= 8.0:
            score += 0.25
            reasoning.append(f"Flag-friendly price: ${context.current_price:.2f}")
        elif 2.0 <= context.current_price <= 12.0:
            score += 0.15
            reasoning.append(f"Workable price: ${context.current_price:.2f}")

        # Some news is okay for bull flags (10% of score)
        if context.news_count == 1:
            score += 0.1
            reasoning.append("Moderate catalyst")

        return min(score, 1.0), reasoning

    def _score_macdv(self, context: MarketContext) -> Tuple[float, List[str]]:
        """Score MACDV technical baseline (fallback strategy)"""
        score = 0.4  # Base score for technical analysis
        reasoning = ["Technical baseline strategy"]

        # Volume consideration
        if context.volume_ratio >= 1.5:
            score += 0.15
            reasoning.append(f"Above average volume: {context.volume_ratio:.1f}x")

        # Price range consideration
        if 1.0 <= context.current_price <= 20.0:
            score += 0.15
            reasoning.append(f"Tradeable price: ${context.current_price:.2f}")

        # Gap consideration
        gap_abs = abs(context.gap_percent)
        if gap_abs <= 3.0:
            score += 0.1
            reasoning.append(f"Manageable gap: {context.gap_percent:.1f}%")

        return min(score, 1.0), reasoning

    def _build_metadata(self, context: MarketContext) -> Dict[str, Any]:
        """Build classification metadata"""
        return {
            'gap_category': self._categorize_gap(context.gap_percent),
            'volume_category': self._categorize_volume(context.volume_ratio),
            'price_tier': self._categorize_price(context.current_price),
            'news_level': self._categorize_news(context.news_count),
            'classification_timestamp': datetime.now().isoformat()
        }

    def _categorize_gap(self, gap_percent: float) -> str:
        """Categorize gap size"""
        gap_abs = abs(gap_percent)
        if gap_abs < 1.0:
            return "minimal"
        elif gap_abs < 3.0:
            return "small"
        elif gap_abs < 8.0:
            return "medium"
        else:
            return "large"

    def _categorize_volume(self, volume_ratio: float) -> str:
        """Categorize volume ratio"""
        if volume_ratio < 1.5:
            return "low"
        elif volume_ratio < 3.0:
            return "normal"
        elif volume_ratio < 6.0:
            return "elevated"
        else:
            return "high"

    def _categorize_price(self, price: float) -> str:
        """Categorize price tier"""
        if price < 2.0:
            return "penny"
        elif price < 5.0:
            return "low"
        elif price < 10.0:
            return "mid"
        else:
            return "high"

    def _categorize_news(self, news_count: int) -> str:
        """Categorize news level"""
        if news_count == 0:
            return "none"
        elif news_count == 1:
            return "light"
        elif news_count <= 3:
            return "moderate"
        else:
            return "heavy"