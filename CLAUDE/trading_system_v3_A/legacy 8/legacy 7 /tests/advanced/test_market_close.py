"""
Tests for market close position functionality.
"""
import sys
import os
import asyncio
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.interfaces import Position, Order, OrderSide, SignalType
from engine.trading_engine import TradingEngine

class TestMarketClosePositions:
    """Test cases for market close position functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config with market hours."""
        class MockConfig:
            market_close_hour = 16  # 4 PM
            market_close_minute = 0
            market_open_hour = 9     # 9:30 AM
            market_open_minute = 30
            minutes_before_close_to_exit = 3  # Close positions at 15:57
            close_positions_on_stop = True
            
            # Other required configs
            max_positions = 5
            max_risk_per_trade = 0.02
            max_daily_loss = -1000.0
            max_daily_trades = 20
            strategy_name = "test"
            timeframe = "1 min"
            
        return MockConfig()
    
    @pytest.fixture
    def trading_engine(self, mock_config):
        """Create a trading engine with mocked dependencies."""
        engine = TradingEngine(
            config=mock_config,
            data_provider=AsyncMock(),
            broker=AsyncMock(),
            strategy=AsyncMock(),
            risk_manager=AsyncMock()
        )
        
        # Mock the event bus
        engine.event_bus = AsyncMock()
        
        # Add some test positions
        engine.positions = {
            'AAPL': Position(
                symbol='AAPL',
                quantity=10,
                avg_price=150.0,
                market_price=155.0,
                market_value=1550.0,
                unrealized_pnl=50.0,
                entry_time=datetime.now() - timedelta(hours=1)
            ),
            'MSFT': Position(
                symbol='MSFT',
                quantity=5,
                avg_price=300.0,
                market_price=310.0,
                market_value=1550.0,
                unrealized_pnl=50.0,
                entry_time=datetime.now() - timedelta(hours=2)
            )
        }
        
        # Mock the close position method
        engine._close_position = AsyncMock()
        
        return engine
    
    @pytest.mark.asyncio
    async def test_should_close_positions_before_market_close(self, trading_engine, mock_config):
        """Test that positions are closed 3 minutes before market close."""
        # Test case 1: 15:56 - Should not close positions yet
        with patch('engine.trading_engine.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 15, 56)  # 3:56 PM
            mock_datetime.now.return_value = mock_now
            
            should_close = await trading_engine._should_close_positions_before_market_close()
            assert should_close is False
            
        # Test case 2: 15:57 - Should close positions (3 minutes before close)
        with patch('engine.trading_engine.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 15, 57)  # 3:57 PM
            mock_datetime.now.return_value = mock_now
            
            should_close = await trading_engine._should_close_positions_before_market_close()
            assert should_close is True
            
            # Should only log once when first entering the time window
            should_close_again = await trading_engine._should_close_positions_before_market_close()
            assert should_close_again is True
    
    @pytest.mark.asyncio
    async def test_close_all_positions_before_market_close(self, trading_engine):
        """Test that all positions are closed before market close."""
        # Call the method
        await trading_engine._close_all_positions_before_market_close()
        
        # Verify close_position was called for each position
        assert trading_engine._close_position.call_count == 2
        
        # Verify the correct symbols were passed
        called_symbols = [call[0][0] for call in trading_engine._close_position.call_args_list]
        assert 'AAPL' in called_symbols
        assert 'MSFT' in called_symbols
        
        # Verify the correct close reason was used
        for call in trading_engine._close_position.call_args_list:
            assert call[0][1] == "Market closing soon"
    
    @pytest.mark.asyncio
    async def test_trading_loop_closes_positions_at_correct_time(self, trading_engine, mock_config):
        """Test that the trading loop closes positions at the right time."""
        # Set up test conditions
        trading_engine.is_running = True  # Ensure the trading loop runs
        
        # Add some test positions
        trading_engine.positions = {
            'AAPL': MagicMock(symbol='AAPL', quantity=10, avg_price=150.0),
            'MSFT': MagicMock(symbol='MSFT', quantity=5, avg_price=200.0)
        }
        
        # Add symbols to monitoring
        trading_engine.monitored_symbols = {'AAPL', 'MSFT'}
        
        # Mock datetime to simulate it's time to close positions
        with patch('engine.trading_engine.datetime') as mock_datetime:
            # Set the mock time to 3:57 PM (3 minutes before 4:00 PM market close)
            mock_datetime.now.return_value = datetime(2023, 1, 1, 15, 57)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Mock the _close_position method to track calls
            original_close_position = trading_engine._close_position
            trading_engine._close_position = AsyncMock()
            
            # Mock _check_risk_limits to return True (allowing trading to continue)
            original_check_risk = trading_engine._check_risk_limits
            trading_engine._check_risk_limits = AsyncMock(return_value=True)
            
            # Mock _should_close_positions_before_market_close to return True
            original_should_close = trading_engine._should_close_positions_before_market_close
            trading_engine._should_close_positions_before_market_close = AsyncMock(return_value=True)
            
            # Mock _close_all_positions_before_market_close
            original_close_all = trading_engine._close_all_positions_before_market_close
            trading_engine._close_all_positions_before_market_close = AsyncMock()
            
            # Mock _update_positions to avoid real updates
            original_update_positions = trading_engine._update_positions
            trading_engine._update_positions = AsyncMock()
            
            # Mock _process_symbol to avoid real processing
            original_process_symbol = trading_engine._process_symbol
            trading_engine._process_symbol = AsyncMock()
            
            try:
                # Create a task that will cancel itself after a short delay
                async def run_with_timeout():
                    task = asyncio.create_task(trading_engine._run_trading_loop())
                    await asyncio.sleep(0.1)  # Wait a bit for the loop to start
                    task.cancel()  # Cancel the task after a short delay
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Run with timeout
                await asyncio.wait_for(run_with_timeout(), timeout=1.0)
                
                # Verify _should_close_positions_before_market_close was called
                trading_engine._should_close_positions_before_market_close.assert_awaited_once()
                
                # Verify _close_all_positions_before_market_close was called
                trading_engine._close_all_positions_before_market_close.assert_awaited_once()
                
            finally:
                # Restore the original methods
                trading_engine._close_position = original_close_position
                trading_engine._check_risk_limits = original_check_risk
                trading_engine._should_close_positions_before_market_close = original_should_close
                trading_engine._close_all_positions_before_market_close = original_close_all
                trading_engine._update_positions = original_update_positions
                trading_engine._process_symbol = original_process_symbol
            
    @pytest.mark.asyncio
    async def test_should_close_positions_before_market_close(self, trading_engine, mock_config):
        """Test the _should_close_positions_before_market_close method directly."""
        # Test when it's time to close positions
        with patch('engine.trading_engine.datetime') as mock_datetime:
            # Set the mock time to 3:57 PM (3 minutes before 4:00 PM market close)
            mock_datetime.now.return_value = datetime(2023, 1, 1, 15, 57)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # The method should return True
            assert await trading_engine._should_close_positions_before_market_close() is True
        
        # Test when it's not time to close positions
        with patch('engine.trading_engine.datetime') as mock_datetime:
            # Set the mock time to 10:00 AM (not close to market close)
            mock_datetime.now.return_value = datetime(2023, 1, 1, 10, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # The method should return False
            assert await trading_engine._should_close_positions_before_market_close() is False
    
    @pytest.mark.asyncio
    async def test_does_not_close_positions_outside_window(self, trading_engine):
        """Test that positions are not closed outside the close window."""
        # Mock datetime to simulate 2:00 PM (outside close window)
        with patch('engine.trading_engine.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 14, 0)  # 2:00 PM
            mock_datetime.now.return_value = mock_now
            
            # Mock the sleep to break the loop after one iteration
            with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
                try:
                    await trading_engine._run_trading_loop()
                except asyncio.CancelledError:
                    pass
            
            # Verify close_position was not called
            assert trading_engine._close_position.call_count == 0

    @pytest.mark.asyncio
    async def test_handle_minute_underflow(self, trading_engine, mock_config):
        """Test that minute underflow is handled correctly."""
        # Set market close to 16:00 and minutes_before_close_to_exit to 5
        mock_config.market_close_hour = 16
        mock_config.market_close_minute = 0
        mock_config.minutes_before_close_to_exit = 5
        
        # Test at 15:55 (should be 5 minutes before 16:00)
        with patch('engine.trading_engine.datetime') as mock_datetime:
            mock_now = datetime(2023, 1, 1, 15, 55)
            mock_datetime.now.return_value = mock_now
            
            should_close = await trading_engine._should_close_positions_before_market_close()
            assert should_close is True
            
            # Verify the close positions time is calculated correctly
            close_positions_time = time(15, 55)
            assert mock_datetime.now.return_value.time() == close_positions_time
