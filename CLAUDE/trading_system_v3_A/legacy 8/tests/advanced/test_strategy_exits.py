"""Unit tests for exit logic of strategies.
We directly test the _check_exit_conditions helpers because full engine context is heavy.
"""
import datetime as dt
import pytest

from strategies.macdv_strategy import MACDVStrategy
from strategies.gap_go_strategy import GapGoStrategy
from strategies.orb_strategy import ORBStrategy
from core.interfaces import MarketData, SignalType


@pytest.mark.parametrize("strategy_cls, setup_entry", [
    (
        MACDVStrategy,
        lambda strat: strat.entry_signals.update({
            'TEST': {
                'type': 'bullish',
                'price': 100.0,
                'atr': 1.0,
                'bars_in_trade': 0,
            }
        }),
    ),
    (
        GapGoStrategy,
        lambda strat: strat.entry_signals.update({
            'TEST': {
                'gap_data': {'direction': 'up'},
                'entry_price': 100.0,
                'bars_in_trade': 0,
            }
        }),
    ),
    (
        ORBStrategy,
        lambda strat: strat.breakout_signals.update({
            'TEST': {
                'direction': 'bullish',
                'timestamp': dt.datetime(2025, 7, 2, 9, 35),
                'entry_price': 100.0,
                'target_price': 110.0,
                'stop_price': 95.0,
                'bars_in_trade': 0,
            }
        }),
    ),
])
def test_stop_loss_exit(strategy_cls, setup_entry):
    strat = strategy_cls()
    setup_entry(strat)
    bar = MarketData(
        symbol='TEST',
        timestamp=dt.datetime(2025, 7, 2, 10, 0),
        open=95.0, high=96.0, low=94.0, close=94.5, volume=10000
    )
    exit_sig = strat._check_exit_conditions('TEST', bar)
    assert exit_sig is not None
    assert exit_sig.signal_type in {SignalType.EXIT_LONG, SignalType.EXIT_SHORT}
    assert exit_sig.metadata.get('reason') == 'stop_loss'


def _make_bar(price: float, hour: int = 15, minute: int = 40):
    return MarketData(
        symbol='TEST',
        timestamp=dt.datetime(2025, 7, 2, hour, minute),
        open=price, high=price, low=price, close=price, volume=10000
    )

@pytest.mark.parametrize("strategy_cls, setup_entry, exit_hour", [
    (MACDVStrategy,
     lambda s: s.entry_signals.update({'TEST': {'type': 'bullish', 'price': 100.0, 'atr': 1.0}}),
     15),
    (GapGoStrategy,
     lambda s: s.entry_signals.update({'TEST': {'gap_data': {'direction': 'up'}, 'entry_price': 100.0}}),
     15),
    (ORBStrategy,
     lambda s: s.breakout_signals.update({'TEST': {'direction': 'bullish', 'timestamp': dt.datetime(2025, 7, 2, 9, 35), 'entry_price': 100.0, 'target_price': 110.0, 'stop_price': 95.0}}),
     15),
])
def test_eod_exit(strategy_cls, setup_entry, exit_hour):
    strat = strategy_cls()
    setup_entry(strat)
    bar = _make_bar(100.0, hour=exit_hour, minute=31)  # after 15:30 or hour>=15 for checks
    sig = strat._check_exit_conditions('TEST', bar)
    assert sig is not None
    assert sig.metadata.get('reason') in {'eod', 'time_exit', 'eod'}
