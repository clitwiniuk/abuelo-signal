"""
Mock Simple Strategy for Testing
Simple strategy with no dependencies to test pipeline functionality
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from core.interfaces import Signal, MarketData, SignalType, Position
from strategies.base import BaseStrategy


class MockSimpleStrategy(BaseStrategy):
    """Simple mock strategy for pipeline testing"""

    def __init__(self, parameters: Dict[str, Any] = None):
        super().__init__(name="MockSimpleStrategy", parameters=parameters)

        # Simple parameters
        self.min_gap_threshold = parameters.get('min_gap_threshold', 3.0) if parameters else 3.0
        self.min_volume_ratio = parameters.get('min_volume_ratio', 1.5) if parameters else 1.5
        self.confidence_base = 0.7

    async def initialize(self, event_bus=None):
        """Simple initialization"""
        self.logger.info(f"✅ {self.name} initialized with simple parameters")
        return True

    async def _analyze_bar(self, symbol: str, bar: MarketData) -> List[Signal]:
        """Simple analysis that generates signals based on basic criteria"""
        signals = []

        try:
            # Calculate basic metrics
            prev_close = getattr(bar, 'prev_close', bar.close)
            avg_volume = getattr(bar, 'avg_volume', 100_000)

            if prev_close > 0:
                gap_percent = (bar.open - prev_close) / prev_close * 100
            else:
                gap_percent = 0

            volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 1.0

            # Simple signal generation rules
            signal_generated = False
            confidence = 0.0

            # Rule 1: Gap Up with Volume
            if gap_percent >= self.min_gap_threshold and volume_ratio >= self.min_volume_ratio:
                confidence = min(0.95, self.confidence_base + (gap_percent / 100) + (volume_ratio / 10))
                signal_generated = True
                self.logger.info(f"📈 Gap Up signal: {gap_percent:.1f}% gap, {volume_ratio:.1f}x volume")

            # Rule 2: High Volume Breakout
            elif volume_ratio >= 3.0 and bar.close > bar.open * 1.02:
                confidence = min(0.90, self.confidence_base + (volume_ratio / 20))
                signal_generated = True
                self.logger.info(f"🚀 Volume breakout: {volume_ratio:.1f}x volume, +{((bar.close/bar.open-1)*100):.1f}%")

            # Rule 3: Steady Momentum
            elif volume_ratio >= 1.2 and bar.close > bar.open * 1.01:
                confidence = min(0.80, self.confidence_base + (volume_ratio / 30))
                signal_generated = True
                self.logger.info(f"📊 Momentum: {volume_ratio:.1f}x volume, +{((bar.close/bar.open-1)*100):.1f}%")

            if signal_generated:
                signal = Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    timestamp=bar.timestamp,
                    entry_price=bar.close,
                    confidence=confidence,
                    stop_loss=bar.close * 0.95,  # 5% stop
                    take_profit=bar.close * 1.15,  # 15% target
                    quantity=100
                )
                signal.strategy_name = self.name
                signals.append(signal)

        except Exception as e:
            self.logger.error(f"❌ Error in mock strategy analysis: {e}")

        return signals

    def should_exit(self, symbol: str, position: Position, current_price: float) -> bool:
        """Simple exit logic"""
        if position.quantity > 0:  # Long position
            # Exit at +10% profit or -5% loss
            pnl_pct = (current_price - position.entry_price) / position.entry_price
            return pnl_pct >= 0.10 or pnl_pct <= -0.05
        return False

    def on_position_update(self, symbol: str, position: Position):
        """Handle position updates"""
        self.logger.debug(f"📊 Mock strategy position update: {symbol} - {position.quantity} shares")

    def get_name(self) -> str:
        return "MockSimpleStrategy"

    def get_description(self) -> str:
        return "Simple mock strategy for pipeline testing"