
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from core.execution_engine_adapter import ExecutionEngineAdapter
from core.interfaces import OrderType, OrderSide
from core.extended_hours_manager import MarketSession

# Mock Config Object
class MockConfig:
    def __init__(self, order_type='MARKET', offset=0.005):
        self.default_order_type = order_type
        self.limit_price_offset_pct = offset
        self.enable_extended_hours_trading = True 

@pytest.fixture
def mock_deps():
    broker = MagicMock()
    broker.get_positions = AsyncMock(return_value={})
    broker.place_order = AsyncMock(return_value="123")
    # Mock get_market_data to avoid "stale price" warnings/errors
    market_data = MagicMock()
    market_data.last = 100.0
    market_data.bid = 99.9
    market_data.ask = 100.1
    broker.get_market_data = AsyncMock(return_value=market_data)

    risk_manager = MagicMock()
    risk_manager.validate_order = AsyncMock(return_value=True)
    # Mock position size calculation
    risk_manager.calculate_smallcap_position_size = MagicMock(return_value={
        'recommended_shares': 10,
        'recommended_percent': 0.1
    })
    risk_manager.config = MagicMock()
    # Set explicit values for config attributes to avoid MagicMock comparisons
    risk_manager.config.max_position_value = 200.0
    risk_manager.config.portfolio_value = 2500.0
    
    return broker, risk_manager

@pytest.mark.asyncio
async def test_execution_market_order_default(mock_deps):
    """Verify that default configuration uses MARKET orders"""
    broker, risk_manager = mock_deps
    config = MockConfig(order_type='MARKET')
    
    with patch('core.execution_engine_adapter.DatabaseManager'), \
         patch('core.execution_engine_adapter.get_trade_ohlc_recorder'):
        
        adapter = ExecutionEngineAdapter(broker=broker, risk_manager=risk_manager, config=config)
        
        # Mock internal components
        adapter.extended_hours_manager = MagicMock()
        adapter.extended_hours_manager.get_market_session = MagicMock(return_value=MarketSession.REGULAR)
        adapter._wait_for_execution_confirmation = AsyncMock(return_value=True) # Confirm execution

        # Execute
        await adapter.enter_position('AAPL', 'test_strat', {'current_price': 100.0})
        
        # Verify
        assert broker.place_order.called
        call_args = broker.place_order.call_args[0][0]
        assert call_args.order_type == OrderType.MARKET
        # For MARKET orders, price passed might be current price or None depending on implementation
        # The adapter passes limit_price=current_price even for MARKET, which is fine
        assert call_args.price == 100.0

@pytest.mark.asyncio
async def test_execution_limit_order_configured(mock_deps):
    """Verify that LIMIT configuration uses LIMIT orders with offset"""
    broker, risk_manager = mock_deps
    # Configure LIMIT with 1% offset
    config = MockConfig(order_type='LIMIT', offset=0.01)
    
    with patch('core.execution_engine_adapter.DatabaseManager'), \
         patch('core.execution_engine_adapter.get_trade_ohlc_recorder'):
        
        adapter = ExecutionEngineAdapter(broker=broker, risk_manager=risk_manager, config=config)
        
        # Mock internal components
        adapter.extended_hours_manager = MagicMock()
        adapter.extended_hours_manager.get_market_session = MagicMock(return_value=MarketSession.REGULAR)
        adapter._wait_for_execution_confirmation = AsyncMock(return_value=True) # Confirm execution

        # Execute
    await adapter.enter_position('AAPL', 'test_strat', {'current_price': 100.0})
    
    # Verify
    assert broker.place_order.called
    call_args = broker.place_order.call_args[0][0]
    assert call_args.order_type == OrderType.LIMIT
    assert call_args.price == 101.0
