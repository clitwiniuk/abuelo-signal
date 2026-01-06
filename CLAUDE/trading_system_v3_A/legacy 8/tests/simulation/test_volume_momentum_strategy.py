#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unit tests for the optimised VolumeMomentumStrategy.

These tests focus on the key improvements requested:
1. Position sizing respecting max_position_value / min_quantity and price caps.
2. Commission impact warning (>1% of position value).
3. Exit logic: stop-loss, trailing-stop, profit-target.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from strategies.volume_momentum_strategy import VolumeMomentumStrategy
from core.interfaces import Signal, SignalType, MarketData, Position

# --- Helpers -----------------------------------------------------------------

def _make_bar(symbol: str, price: float, ts: datetime | None = None) -> MarketData:
    """Create a single bar with minimal required fields."""
    return MarketData(
        symbol=symbol,
        timestamp=ts or datetime.utcnow(),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=100_000,
        vwap=price,
    )


def _make_position(symbol: str, qty: int, entry_price: float) -> Position:
    """Helper to create a dummy Position object."""
    return Position(
        symbol=symbol,
        quantity=qty,
        avg_price=entry_price,
        market_price=entry_price,
        market_value=qty * entry_price,
        unrealized_pnl=0.0,
        entry_time=datetime.utcnow(),
    )


# --- Test Case ----------------------------------------------------------------

class TestVolumeMomentumStrategy(unittest.TestCase):
    def setUp(self):
        # Use small account defaults already embedded in strategy
        self.strategy = VolumeMomentumStrategy()
        self.strategy.logger = MagicMock()

        # Basic signal template
        self.signal = Signal(
            signal_id="sig123",
            symbol="TEST",
            signal_type=SignalType.LONG,
            strength=0.9,
            price=10.0,
            timestamp=datetime.utcnow(),
        )

    # 1. Position sizing: price greater than max_position_value should return 0
    def test_position_size_blocked_by_high_price(self):
        self.signal.price = 5000.0  # greater than max_position_value ($2,000)
        qty = self.strategy.calculate_position_size(self.signal, capital=10_000, risk_per_trade=0.01)
        self.assertEqual(qty, 0, "Position size should be 0 when price > max_position_value")

    # 2. Commission warning when commission >1% of position value
    def test_commission_warning_triggered(self):
        with patch.object(self.strategy.logger, "warning") as mock_warn:
            # Force small position where commissions dominate (price very low)
            self.signal.price = 1.0
            self.strategy.calculate_position_size(self.signal, capital=500, risk_per_trade=0.01)
            mock_warn.assert_called(), "Expected commission warning to be logged when commission% > 1%"

    # 3. Stop-loss exit triggered correctly
    def test_stop_loss_exit(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=100, entry_price=entry_price)

        # Register entry for strategy
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "long",
                "atr_at_entry": 1.0,  # ATR so stop_loss_pct = 1.7*1/10=17%
            }
        }

        # Price drops −20% => should hit stop-loss (17% threshold)
        bar = _make_bar("TEST", price=8.0)
        reason = self.strategy._check_strategy_exit(position, bar)
        self.assertEqual(reason, "stop_loss")

    # 4. Profit-target exit triggered at +20%
    def test_profit_target_exit(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "long",
                "atr_at_entry": 1.0,
            }
        }
        # Price rises +25% => should hit profit_target
        bar = _make_bar("TEST", price=12.5)
        reason = self.strategy._check_strategy_exit(position, bar)
        self.assertEqual(reason, "profit_target")

    # 5. Trailing-stop activation after threshold met
    def test_trailing_stop_exit(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "long",
                "atr_at_entry": 1.0,
            }
        }
        # First bar pushes P&L above activation (+12%)
        bar1 = _make_bar("TEST", price=11.2)
        self.strategy._check_strategy_exit(position, bar1)  # update highest_price

        # Second bar pulls back 7% from high -> below trailing distance 5%
        bar2 = _make_bar("TEST", price=10.4)
        reason = self.strategy._check_strategy_exit(position, bar2)
        self.assertEqual(reason, "trailing_stop")

    # 6. VWAP reversal exit for long position
    def test_vwap_reversal_exit_long(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "long",
                "atr_at_entry": 1.0,
            }
        }
        # No exit when price within 0.5% below VWAP
        with patch.object(self.strategy, "_calculate_vwap", return_value=10.0), \
             patch.object(self.strategy, "_analyze_momentum_indicators", return_value={"momentum_confirmed": True}):
            bar_ok = _make_bar("TEST", price=9.95)
            self.assertIsNone(self.strategy._check_strategy_exit(position, bar_ok))
        # Exit when price 2% below VWAP (threshold 1%)
        with patch.object(self.strategy, "_calculate_vwap", return_value=10.0), \
             patch.object(self.strategy, "_analyze_momentum_indicators", return_value={"momentum_confirmed": True}):
            bar_exit = _make_bar("TEST", price=9.8)
            self.assertEqual(self.strategy._check_strategy_exit(position, bar_exit), "vwap_reversal")

    # 7. VWAP reversal exit for short position
    def test_vwap_reversal_exit_short(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=-100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "short",
                "atr_at_entry": 1.0,
            }
        }
        # No exit when price within 0.5% above VWAP
        with patch.object(self.strategy, "_calculate_vwap", return_value=10.0), \
             patch.object(self.strategy, "_analyze_momentum_indicators", return_value={"momentum_confirmed": True}):
            bar_ok = _make_bar("TEST", price=10.05)
            self.assertIsNone(self.strategy._check_strategy_exit(position, bar_ok))
        # Exit when price 3% above VWAP
        with patch.object(self.strategy, "_calculate_vwap", return_value=10.0), \
             patch.object(self.strategy, "_analyze_momentum_indicators", return_value={"momentum_confirmed": True}):
            bar_exit = _make_bar("TEST", price=10.3)
            self.assertEqual(self.strategy._check_strategy_exit(position, bar_exit), "vwap_reversal")

    # 8. Momentum loss exit
    def test_momentum_loss_exit(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "long",
                "atr_at_entry": 1.0,
            }
        }
        with patch.object(self.strategy, "_analyze_momentum_indicators", return_value={"momentum_confirmed": False}):
            bar = _make_bar("TEST", price=10.0)
            self.assertEqual(self.strategy._check_strategy_exit(position, bar), "momentum_loss")

    # 9. Trailing stop for short position
    def test_trailing_stop_exit_short(self):
        entry_price = 10.0
        position = _make_position("TEST", qty=-100, entry_price=entry_price)
        self.strategy.entry_signals = {
            "TEST": {
                "entry_price": entry_price,
                "signal_direction": "short",
                "atr_at_entry": 1.0,
            }
        }
        bar1 = _make_bar("TEST", price=8.5)
        self.strategy._check_strategy_exit(position, bar1)
        bar2 = _make_bar("TEST", price=9.5)
        self.assertEqual(self.strategy._check_strategy_exit(position, bar2), "trailing_stop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
