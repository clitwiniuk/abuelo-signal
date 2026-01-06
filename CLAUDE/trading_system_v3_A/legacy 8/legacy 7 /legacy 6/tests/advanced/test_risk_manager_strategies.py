import pytest
from datetime import datetime, timedelta

from core.risk_manager import RiskManager
from core.interfaces import (
    Signal, SignalType, TradingConfig
)

# ---------------------------------------------------------------------------
# Helper factories (re-used but kept local to avoid inter-test dependencies)
# ---------------------------------------------------------------------------

def make_config(simulation: bool = True) -> TradingConfig:
    """Return a customised TradingConfig for RiskManager unit tests."""
    cfg = TradingConfig(
        max_positions=3,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=5,
        enable_filters=False,
        strategy_name="test",
    )
    cfg.simulation_mode = simulation
    cfg.max_trades_per_symbol = 5
    return cfg


def make_signal(strategy: str, strength: float = 0.6, ts: datetime | None = None) -> Signal:
    if ts is None:
        ts = datetime.now()
    return Signal(
        signal_id=f"{strategy}-sig",
        symbol="TEST",
        signal_type=SignalType.LONG,
        strength=strength,
        price=10.0,
        timestamp=ts,
        metadata={"strategy": strategy},
    )

# ---------------------------------------------------------------------------
# Parameterised tests for different strategies (GapGo, ORB)
# ---------------------------------------------------------------------------

STRATEGIES = ["GapGo", "ORB"]

@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_name", STRATEGIES)
async def test_validate_signal_accept(strategy_name):
    """RiskManager should accept valid signals from all strategies in simulation."""
    rm = RiskManager(make_config(simulation=True))
    sig = make_signal(strategy_name, strength=0.8)
    assert await rm.validate_signal(sig) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_name", STRATEGIES)
async def test_validate_signal_reject_on_strength(strategy_name):
    """Signal below minimum strength should be rejected."""
    rm = RiskManager(make_config(simulation=True))
    weak_sig = make_signal(strategy_name, strength=0.1)
    assert await rm.validate_signal(weak_sig) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_name", STRATEGIES)
async def test_per_symbol_trade_limit(strategy_name):
    """RiskManager should reject new signals once per-symbol daily limit reached."""
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)
    # Manually exhaust the limit
    rm.symbol_daily_trades["TEST"] = cfg.max_trades_per_symbol
    sig = make_signal(strategy_name, strength=0.8)
    assert await rm.validate_signal(sig) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_name", STRATEGIES)
async def test_daily_trade_limit(strategy_name):
    """RiskManager should reject signals when overall daily trade limit exceeded."""
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)
    rm.daily_trades = cfg.max_daily_trades  # hit global limit
    sig = make_signal(strategy_name, strength=0.8)
    assert await rm.validate_signal(sig) is False
