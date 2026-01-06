"""
Test suite for position value validation in RiskManager.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from core.risk_manager import RiskManager
from core.interfaces import (
    Signal, SignalType, Order, OrderSide, OrderType,
    TradingConfig, Position, MarketData
)

# Test configuration
TEST_CONFIG = {
    'max_position_value': 200.0,
    'max_position_concentration': 0.5,  # 50%
    'max_order_value': 100.0,
    'max_daily_trades': 10,
    'max_daily_loss': -1000.0,
    'simulation_mode': True
}

@pytest.fixture
def risk_manager():
    """Create a RiskManager instance with test configuration."""
    config = TradingConfig(**TEST_CONFIG)
    rm = RiskManager(config)
    return rm

@pytest.fixture
def sample_position():
    """Create a sample position for testing."""
    return Position(
        symbol="TEST",
        quantity=10,
        avg_price=15.0,
        market_price=20.0,
        market_value=200.0,
        unrealized_pnl=50.0,
        entry_time=datetime.now() - timedelta(hours=1)
    )

@pytest.mark.asyncio
async def test_position_value_within_limits(risk_manager, sample_position):
    """Test position value within limits is accepted."""
    # Update positions in risk manager
    risk_manager.update_positions({"TEST": sample_position})
    
    # Create a buy order that won't exceed max position value
    order = Order(
        order_id="test-order-1",
        symbol="TEST",
        side=OrderSide.BUY,
        quantity=5,  # 5 * 20 = $100, total $300 which is > $200 limit
        order_type=OrderType.MARKET,
        price=20.0
    )
    
    # This should fail because it would exceed max_position_value
    result = await risk_manager.validate_order(order)
    assert result is False, "Should reject order that exceeds max_position_value"
    
    # Try a smaller order that stays within limits
    order.quantity = 2  # 2 * 20 = $40, total $240 which is > $200 limit
    result = await risk_manager.validate_order(order)
    assert result is False, "Should reject order that exceeds max_position_value"
    
    # Try a sell order which should be fine
    order.side = OrderSide.SELL
    order.quantity = 5  # Reducing position by 5 shares
    result = await risk_manager.validate_order(order)
    assert result is True, "Should accept sell order that reduces position"

@pytest.mark.asyncio
async def test_position_concentration(risk_manager, sample_position):
    """Test position concentration checks."""
    # Update positions with a position that's 50% of portfolio (limit)
    risk_manager.update_positions({"TEST": sample_position})
    
    # Mock portfolio value to be 2x position value (50% concentration)
    with patch.object(risk_manager, '_get_total_portfolio_value', return_value=400.0):
        # Try to increase position beyond concentration limit
        order = Order(
            order_id="test-order-2",
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=5,  # 5 * 20 = $100, new total $300 (75% of $400)
            order_type=OrderType.MARKET,
            price=20.0
        )
        
        result = await risk_manager.validate_order(order)
        assert result is False, "Should reject order that exceeds position concentration"
        
        # Check that the rejection reason is logged
        assert any("exceeds max_position_concentration" in str(call) 
                  for call in risk_manager.logger.warning.call_args_list)

@pytest.mark.asyncio
async def test_multiple_positions(risk_manager):
    """Test with multiple positions to ensure total portfolio checks work."""
    # Create two positions, each at 40% of portfolio
    positions = {
        "STOCK1": Position(
            symbol="STOCK1",
            quantity=10,
            avg_price=20.0,
            market_price=20.0,
            market_value=200.0,
            unrealized_pnl=0.0,
            entry_time=datetime.now() - timedelta(hours=2)
        ),
        "STOCK2": Position(
            symbol="STOCK2",
            quantity=15,
            avg_price=20.0,
            market_price=20.0,
            market_value=300.0,
            unrealized_pnl=0.0,
            entry_time=datetime.now() - timedelta(hours=1)
        )
    }
    
    # Mock total portfolio value to be $1000
    with patch.object(risk_manager, '_get_total_portfolio_value', return_value=1000.0):
        risk_manager.update_positions(positions)
        
        # Try to add a new position that would take us over max_position_value
        order = Order(
            order_id="test-order-3",
            symbol="STOCK3",
            side=OrderSide.BUY,
            quantity=15,  # 15 * 20 = $300, which is over max_position_value of $200
            order_type=OrderType.MARKET,
            price=20.0
        )
        
        result = await risk_manager.validate_order(order)
        assert result is False, "Should reject order that exceeds max_position_value"
        
        # Try a smaller order that's within limits
        order.quantity = 10  # 10 * 20 = $200, which is exactly the limit
        result = await risk_manager.validate_order(order)
        assert result is True, "Should accept order that's within max_position_value"

@pytest.mark.asyncio
async def test_position_value_edge_cases(risk_manager):
    """Test edge cases in position value validation."""
    # Test with zero price (should be handled gracefully)
    order = Order(
        order_id="test-order-4",
        symbol="TEST",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        price=0.0  # Zero price
    )
    
    # Should handle zero price gracefully (won't fail, but position value will be 0)
    result = await risk_manager.validate_order(order)
    assert result is True, "Should handle zero price gracefully"
    
    # Test with very large position value
    order.price = 10000.0  # 100 * 10000 = $1,000,000
    result = await risk_manager.validate_order(order)
    assert result is False, "Should reject extremely large position values"
