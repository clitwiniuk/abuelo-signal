import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.risk_manager import RiskManager
from core.interfaces import (
    Signal, SignalType, Order, OrderSide, OrderType,
    TradingConfig, Position
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_config(simulation: bool = True) -> TradingConfig:
    """Return a TradingConfig with smaller limits for testing."""
    cfg = TradingConfig(
        max_positions=3,
        max_risk_per_trade=0.02,
        max_daily_loss=-500.0,
        max_daily_trades=5,
        enable_filters=False,
        strategy_name="test",
    )
    # Inject custom attributes for RiskManager
    cfg.simulation_mode = simulation
    cfg.max_trades_per_symbol = 5
    cfg.max_position_value = 200.0  # $200 max position value
    cfg.max_position_concentration = 0.5  # 50% max concentration
    cfg.max_order_value = 100.0  # $100 max order value
    return cfg


def make_signal(strength: float = 0.5, ts: datetime | None = None) -> Signal:
    if ts is None:
        ts = datetime.now()
    return Signal(
        signal_id="test-signal",
        symbol="TEST",
        signal_type=SignalType.LONG,
        strength=strength,
        price=100.0,
        timestamp=ts,
    )


def make_order(qty: int = 10, price: float | None = None) -> Order:
    return Order(
        order_id="test-order",
        symbol="TEST",
        side=OrderSide.BUY,
        quantity=qty,
        order_type=OrderType.MARKET if price is None else OrderType.LIMIT,
        price=price,
    )


def make_positions(values: list[float]) -> dict[str, Position]:
    """Create dummy positions with given market values.
    
    Args:
        values: List of position market values
        
    Returns:
        Dictionary of Position objects keyed by symbol
    """
    pos = {}
    now = datetime.now()
    for i, val in enumerate(values):
        symbol = f"SYM{i}"
        price = abs(val) / 100 if val != 0 else 10.0  # Avoid division by zero
        quantity = int(val / price) if val != 0 else 0
        pos[symbol] = Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=price,
            market_price=price,
            market_value=val,
            unrealized_pnl=0.0,
            entry_time=now - timedelta(hours=1),
        )
    return pos

# ---------------------------------------------------------------------------
# Tests for validate_signal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_signal_pass_simulation():
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)

    signal = make_signal()
    result = await rm.validate_signal(signal)
    assert result is True


@pytest.mark.asyncio
async def test_validate_signal_fail_strength():
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)

    weak_signal = make_signal(strength=0.1)
    result = await rm.validate_signal(weak_signal)
    assert result is False


@pytest.mark.asyncio
async def test_validate_signal_fail_daily_trade_limit():
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)

    # exceed daily trades
    rm.daily_trades = cfg.max_daily_trades
    signal = make_signal()
    result = await rm.validate_signal(signal)
    assert result is False


@pytest.mark.asyncio
async def test_validate_signal_market_hours_check():
    """Outside market hours & not simulation should fail."""
    # 3 AM ET (outside regular session)
    ny_tz = ZoneInfo("US/Eastern")
    timestamp = datetime.now(ny_tz).replace(hour=3, minute=0, second=0, microsecond=0)

    cfg = make_config(simulation=False)
    rm = RiskManager(cfg)

    signal = make_signal(ts=timestamp)
    result = await rm.validate_signal(signal)
    assert result is False

# ---------------------------------------------------------------------------
# Tests for validate_order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_order_pass():
    cfg = make_config()
    rm = RiskManager(cfg)
    
    # Mock position data
    rm.update_positions({"TEST": Position(
        symbol="TEST",
        quantity=0,
        avg_price=0,
        market_price=10.0,
        market_value=0,
        unrealized_pnl=0.0,
        entry_time=datetime.now() - timedelta(hours=1)
    )})
    
    order = make_order(qty=5, price=10.0)  # 5 * 10 = $50 order
    result = await rm.validate_order(order)
    assert result is True


@pytest.mark.asyncio
async def test_validate_order_fail_size():
    cfg = make_config()
    rm = RiskManager(cfg)
    # Too large quantity
    large_order = make_order(qty=100000)
    result = await rm.validate_order(large_order)
    assert result is False


# ---------------------------------------------------------------------------
# Tests for portfolio risk checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_portfolio_concentration_fail():
    cfg = make_config()
    rm = RiskManager(cfg)

    positions = make_positions([100000, 500])  # one position dominates (~99%)
    ok = await rm.check_portfolio_risk(positions)
    assert ok is False


@pytest.mark.asyncio
async def test_check_portfolio_risk_pass():
    cfg = make_config()
    rm = RiskManager(cfg)

    positions = make_positions([10000, 8000, 7000])
    ok = await rm.check_portfolio_risk(positions)
    assert ok is True


@pytest.mark.asyncio
async def test_check_portfolio_concentration_fail():
    cfg = make_config()
    rm = RiskManager(cfg)
    
    # Mock total portfolio value
    rm._get_total_portfolio_value = lambda: 1000.0
    
    # Create positions that exceed concentration (80% in one position)
    positions = make_positions([800.0, 100.0, 100.0])
    
    # Update positions in risk manager
    rm.update_positions(positions)
    
    # Create an order that would increase the concentrated position
    order = Order(
        order_id="test-order-conc",
        symbol="SYM0",  # The concentrated position
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        price=10.0
    )
    
    # Should fail concentration check
    result = await rm.validate_order(order)
    assert result is False


@pytest.mark.asyncio
async def test_check_portfolio_risk_pass():
    cfg = make_config()
    rm = RiskManager(cfg)
    
    # Mock total portfolio value
    rm._get_total_portfolio_value = lambda: 1000.0
    
    # Create positions that are within limits
    positions = make_positions([200.0, 150.0, 150.0])  # All <= max_position_value of 200
    rm.update_positions(positions)
    
    # Create a valid order
    order = Order(
        order_id="test-order-valid",
        symbol="SYM3",  # New position
        side=OrderSide.BUY,
        quantity=5,
        order_type=OrderType.MARKET,
        price=10.0  # 5 * 10 = $50 order
    )
    
    # Should pass all checks
    result = await rm.validate_order(order)
    assert result is True

# ---------------------------------------------------------------------------
# Additional tests: simulation flag, daily loss limit, exposure, per-symbol limit
# ---------------------------------------------------------------------------

def test_symbol_daily_trades_limit_exceeded():
    cfg = make_config()
    rm = RiskManager(cfg)
    rm.symbol_daily_trades['TEST'] = cfg.max_trades_per_symbol
    assert rm._check_symbol_trade_limit('TEST') is False

def test_symbol_daily_trades_limit_reset():
    cfg = make_config()
    rm = RiskManager(cfg)
    rm.symbol_daily_trades['TEST'] = cfg.max_trades_per_symbol
    rm.symbol_daily_trades.clear()
    assert rm.symbol_daily_trades == {}

@pytest.mark.asyncio
async def test_simulation_flag_propagation():
    cfg = make_config(simulation=False)
    rm = RiskManager(cfg)
    assert rm.simulation_mode is False
    cfg2 = make_config(simulation=True)
    rm2 = RiskManager(cfg2)
    assert rm2.simulation_mode is True


@pytest.mark.asyncio
async def test_daily_loss_limit_exceeded():
    cfg = make_config(simulation=True)
    rm = RiskManager(cfg)
    # daily_pnl below the negative limit triggers failure
    rm.daily_pnl = cfg.max_daily_loss - 100  # e.g., -600 vs limit -500
    valid = await rm.validate_signal(make_signal())
    assert valid is False


@pytest.mark.asyncio
async def test_portfolio_exposure_limit_fail():
    cfg = make_config()
    # Lower exposure threshold for test
    cfg.max_portfolio_exposure = 50_000
    rm = RiskManager(cfg)
    positions = make_positions([60_000, -10_000])  # absolute long exposure 60k > 50k
    ok = await rm.check_portfolio_risk(positions)
    assert ok is False
