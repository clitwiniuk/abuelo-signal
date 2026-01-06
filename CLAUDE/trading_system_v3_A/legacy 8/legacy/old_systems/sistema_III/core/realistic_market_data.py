"""
Realistic Market Data Enricher - Industry-proven approach
Simple, essential indicators that actually matter in live trading
Based on what successful funds actually use
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np

from core.interfaces import MarketData


@dataclass
class EssentialIndicators:
    """Essential indicators only - the 20% that gives 80% results"""
    # Core trend
    rsi_14: float = 50.0

    # Core volume
    volume_ratio: float = 1.0  # current_volume / avg_volume
    volume_trend: str = "neutral"  # increasing, decreasing, neutral

    # Core price action
    gap_percent: float = 0.0
    distance_to_resistance_pct: float = 10.0
    price_trend_5min: str = "neutral"

    # Core timing
    minutes_since_open: int = 0
    optimal_trading_time: bool = True


@dataclass
class SetupContext:
    """Simple setup context - quality over complexity"""
    # Basic quality
    clean_setup: bool = True
    volume_confirmation: bool = False
    time_quality: str = "good"  # good, fair, poor

    # Risk factors
    volatility_level: str = "normal"  # low, normal, high
    gap_risk: str = "low"  # low, medium, high


@dataclass
class RealisticMarketData(MarketData):
    """Realistic market data - essential enrichments only"""
    # Core enrichments
    essential_indicators: EssentialIndicators = field(default_factory=EssentialIndicators)
    setup_context: SetupContext = field(default_factory=SetupContext)

    # Scanner metadata
    enrichment_timestamp: datetime = field(default_factory=datetime.now)


class RealisticDataEnricher:
    """
    Realistic data enricher based on industry practices
    - Focus on essential indicators that matter
    - Avoid overfitting with complex calculations
    - Fast, reliable, battle-tested approach
    """

    def __init__(self):
        self.min_bars_required = 20  # Minimum for reliable calculations

    def enrich_market_data(self, symbol: str, current_data: MarketData,
                          historical_bars: List[MarketData]) -> RealisticMarketData:
        """Enrich with essential indicators only"""
        try:
            # Create realistic enhanced data
            enhanced = RealisticMarketData(
                symbol=current_data.symbol,
                timestamp=current_data.timestamp,
                open=current_data.open,
                high=current_data.high,
                low=current_data.low,
                close=current_data.close,
                volume=current_data.volume
            )

            # Copy any additional attributes
            for attr in ['prev_close', 'avg_volume']:
                if hasattr(current_data, attr):
                    setattr(enhanced, attr, getattr(current_data, attr))

            # Calculate essential indicators
            if len(historical_bars) >= self.min_bars_required:
                enhanced.essential_indicators = self._calculate_essentials(
                    current_data, historical_bars
                )
                enhanced.setup_context = self._assess_setup_context(
                    current_data, historical_bars, enhanced.essential_indicators
                )

            enhanced.enrichment_timestamp = datetime.now()
            return enhanced

        except Exception as e:
            # Fallback: return basic data in enhanced wrapper
            return RealisticMarketData(
                symbol=current_data.symbol,
                timestamp=current_data.timestamp,
                open=current_data.open,
                high=current_data.high,
                low=current_data.low,
                close=current_data.close,
                volume=current_data.volume
            )

    def _calculate_essentials(self, current: MarketData,
                             history: List[MarketData]) -> EssentialIndicators:
        """Calculate only essential indicators"""
        try:
            # RSI (simplified, reliable calculation)
            rsi = self._calculate_simple_rsi([bar.close for bar in history[-20:]], current.close)

            # Volume ratio (most important volume indicator)
            avg_volume = np.mean([bar.volume for bar in history[-20:]])
            volume_ratio = current.volume / avg_volume if avg_volume > 0 else 1.0

            # Volume trend (simple but effective)
            recent_volumes = [bar.volume for bar in history[-5:]]
            if len(recent_volumes) >= 3:
                if recent_volumes[-1] > recent_volumes[-3]:
                    volume_trend = "increasing"
                elif recent_volumes[-1] < recent_volumes[-3] * 0.8:
                    volume_trend = "decreasing"
                else:
                    volume_trend = "neutral"
            else:
                volume_trend = "neutral"

            # Gap calculation
            prev_close = getattr(current, 'prev_close', None)
            if not prev_close and len(history) >= 1:
                prev_close = history[-1].close

            gap_percent = 0.0
            if prev_close and prev_close > 0:
                gap_percent = (current.open - prev_close) / prev_close * 100

            # Distance to resistance (simple calculation)
            recent_highs = [bar.high for bar in history[-10:]]
            max_high = max(recent_highs) if recent_highs else current.high
            distance_to_resistance = ((max_high - current.close) / current.close * 100) if max_high > current.close else 0

            # Price trend (last 5 bars)
            if len(history) >= 5:
                first_close = history[-5].close
                trend = "bullish" if current.close > first_close * 1.01 else "bearish" if current.close < first_close * 0.99 else "neutral"
            else:
                trend = "neutral"

            # Time since open
            now = datetime.now()
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
            if now.date() == market_open.date():
                minutes_since_open = max(0, int((now - market_open).total_seconds() / 60))
            else:
                minutes_since_open = 0

            return EssentialIndicators(
                rsi_14=rsi,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
                gap_percent=gap_percent,
                distance_to_resistance_pct=distance_to_resistance,
                price_trend_5min=trend,
                minutes_since_open=minutes_since_open,
                optimal_trading_time=self._is_optimal_time(minutes_since_open)
            )

        except Exception:
            return EssentialIndicators()

    def _assess_setup_context(self, current: MarketData, history: List[MarketData],
                             indicators: EssentialIndicators) -> SetupContext:
        """Assess setup quality with simple, reliable metrics"""
        try:
            # Clean setup (not too choppy)
            if len(history) >= 10:
                price_changes = []
                for i in range(1, min(11, len(history))):
                    change = abs(history[-i].close - history[-i-1].close) / history[-i-1].close
                    price_changes.append(change)
                avg_change = np.mean(price_changes)
                clean_setup = avg_change < 0.025  # Less than 2.5% average change
            else:
                clean_setup = True

            # Volume confirmation
            volume_confirmation = indicators.volume_ratio > 1.2

            # Time quality
            if 30 <= indicators.minutes_since_open <= 360:  # 10:00 - 15:30
                time_quality = "good"
            elif 15 <= indicators.minutes_since_open <= 390:  # 9:45 - 16:00
                time_quality = "fair"
            else:
                time_quality = "poor"

            # Volatility assessment
            if abs(indicators.gap_percent) > 8:
                volatility = "high"
            elif abs(indicators.gap_percent) > 3:
                volatility = "normal"
            else:
                volatility = "low"

            # Gap risk
            if abs(indicators.gap_percent) > 10:
                gap_risk = "high"
            elif abs(indicators.gap_percent) > 5:
                gap_risk = "medium"
            else:
                gap_risk = "low"

            return SetupContext(
                clean_setup=clean_setup,
                volume_confirmation=volume_confirmation,
                time_quality=time_quality,
                volatility_level=volatility,
                gap_risk=gap_risk
            )

        except Exception:
            return SetupContext()

    def _calculate_simple_rsi(self, prices: List[float], current_price: float) -> float:
        """Simple, reliable RSI calculation"""
        try:
            if len(prices) < 14:
                return 50.0

            # Add current price
            all_prices = prices + [current_price]

            # Calculate changes
            changes = [all_prices[i] - all_prices[i-1] for i in range(1, len(all_prices))]

            # Separate gains and losses
            gains = [change if change > 0 else 0 for change in changes[-14:]]
            losses = [-change if change < 0 else 0 for change in changes[-14:]]

            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return max(0, min(100, rsi))

        except Exception:
            return 50.0

    def _is_optimal_time(self, minutes_since_open: int) -> bool:
        """Determine if current time is optimal for trading"""
        # Avoid first 30 minutes (too volatile) and last 30 minutes (unpredictable)
        return 30 <= minutes_since_open <= 360


# Global enricher instance
_realistic_enricher = None

def get_realistic_enricher() -> RealisticDataEnricher:
    """Get or create global realistic data enricher"""
    global _realistic_enricher
    if _realistic_enricher is None:
        _realistic_enricher = RealisticDataEnricher()
    return _realistic_enricher


if __name__ == "__main__":
    print("🧪 Realistic Market Data Enricher Test")
    print("=" * 50)

    enricher = RealisticDataEnricher()
    print("✅ Realistic enricher created")
    print("📊 Essential indicators: RSI, Volume Ratio, Gap%, Distance to Resistance")
    print("⏰ Time quality, Setup context, Risk assessment")
    print("🎯 Industry-proven, battle-tested approach")
    print("=" * 50)