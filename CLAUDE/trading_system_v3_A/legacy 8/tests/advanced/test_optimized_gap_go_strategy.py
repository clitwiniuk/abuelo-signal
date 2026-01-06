"""
Test suite for the optimized Gap & Go strategy.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.optimized_gap_go_strategy import OptimizedGapGoStrategy
from core.interfaces import Signal, SignalType, MarketData, Position


class TestOptimizedGapGoStrategy(unittest.TestCase):
    """Test the optimized Gap & Go strategy."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock logger
        self.mock_logger = MagicMock()
        
        # Create strategy with test parameters
        self.strategy = OptimizedGapGoStrategy(
            parameters={
                'max_position_value': 200.0,
                'min_position_value': 100.0,
                'max_risk_per_trade': 0.02,
                'min_quantity': 10,
                'stop_loss_pct': 0.05,
                'profit_target': 0.10,
                'trailing_activation': 0.05,
                'trailing_distance': 0.02,
                'scanner_gap_timeout': 15,
                'breakout_buffer': 0.001,
                'gap_fill_buffer': 0.03,
                'market_open_hour': 9.5,
                'no_entry_after': 11.0,
                'max_hold_time': 60
            }
        )
        self.strategy.logger = self.mock_logger
        
        # Sample market data
        self.sample_bar = MarketData(
            symbol="TEST",
            timestamp=datetime.now().replace(hour=10, minute=0),  # 10:00 AM
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.2,
            volume=50000,
            vwap=10.1
        )
        
        # Sample gap data from scanner
        self.gap_data = {
            'gap_percentage': 5.0,  # 5% gap up
            'current_price': 10.0,
            'volume_ratio': 2.5,
            'timestamp': datetime.now().replace(hour=9, minute=30),  # 9:30 AM
            'score': 0.8
        }
    
    async def test_add_scanner_gap(self):
        """Test adding a gap from external scanner."""
        await self.strategy.add_scanner_gap("TEST", self.gap_data)
        
        # Verify gap was added
        self.assertIn("TEST", self.strategy.scanner_gaps)
        self.assertEqual(self.strategy.scanner_gaps["TEST"]["gap_percent"], 5.0)
        self.assertEqual(self.strategy.scanner_gaps["TEST"]["direction"], "up")
    
    async def test_entry_signal_generation(self):
        """Test entry signal generation with valid conditions."""
        # Add gap data
        await self.strategy.add_scanner_gap("TEST", self.gap_data)
        
        # Mock bars history
        self.strategy.bars_history = {
            "TEST": [
                MarketData(
                    symbol="TEST",
                    timestamp=datetime.now().replace(hour=10, minute=0) - timedelta(days=1),
                    open=9.5,
                    high=9.7,
                    low=9.3,
                    close=9.5,
                    volume=20000,
                    vwap=9.5
                )
            ] * 10  # 10 days of history
        }
        
        # Create bar with good conditions
        good_bar = MarketData(
            symbol="TEST",
            timestamp=datetime.now().replace(hour=10, minute=0),
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.3,  # Up from open (breakout)
            volume=50000,  # Good volume
            vwap=10.1
        )
        
        # Mock the entry condition methods
        with patch.object(self.strategy, '_check_simple_breakout', return_value=True), \
             patch.object(self.strategy, '_check_gap_fill_risk', return_value=True), \
             patch.object(self.strategy, '_check_volume_sustained', return_value=True):
            
            # Should generate entry signal
            signal = await self.strategy._analyze_bar(good_bar)
            
            # Verify signal
            self.assertIsNotNone(signal)
            self.assertEqual(signal.symbol, "TEST")
            self.assertEqual(signal.signal_type, SignalType.LONG)
            self.assertEqual(signal.price, 10.3)
            self.assertGreaterEqual(signal.strength, 0.66)  # At least 2/3 conditions
    
    async def test_no_entry_with_failed_conditions(self):
        """Test that no entry signal is generated when conditions fail."""
        # Add gap data
        await self.strategy.add_scanner_gap("TEST", self.gap_data)
        
        # Mock bars history
        self.strategy.bars_history = {
            "TEST": [
                MarketData(
                    symbol="TEST",
                    timestamp=datetime.now().replace(hour=10, minute=0) - timedelta(days=1),
                    open=9.5,
                    high=9.7,
                    low=9.3,
                    close=9.5,
                    volume=20000,
                    vwap=9.5
                )
            ] * 10
        }
        
        # Create bar with poor conditions
        poor_bar = MarketData(
            symbol="TEST",
            timestamp=datetime.now().replace(hour=10, minute=0),
            open=10.0,
            high=10.1,
            low=9.7,
            close=9.8,  # Down from open (no breakout)
            volume=10000,  # Low volume
            vwap=9.9
        )
        
        # Mock the entry condition methods
        with patch.object(self.strategy, '_check_simple_breakout', return_value=False), \
             patch.object(self.strategy, '_check_gap_fill_risk', return_value=False), \
             patch.object(self.strategy, '_check_volume_sustained', return_value=False):
            
            # Should not generate entry signal
            signal = await self.strategy._analyze_bar(poor_bar)
            
            # Verify no signal
            self.assertIsNone(signal)
    
    async def test_exit_conditions(self):
        """Test exit conditions."""
        # Add gap data
        await self.strategy.add_scanner_gap("TEST", self.gap_data)
        
        # Setup entry signal
        entry_time = datetime.now().replace(hour=10, minute=0)
        self.strategy.entry_signals["TEST"] = {
            'gap_data': {
                'direction': 'up',
                'gap_percent': 5.0
            },
            'entry_price': 10.0,
            'entry_time': entry_time,
            'highest_price': 10.5,
            'lowest_price': 9.8
        }
        
        # Test cases for different exit conditions
        test_cases = [
            # Stop loss
            {
                'bar': MarketData(
                    symbol="TEST",
                    timestamp=entry_time + timedelta(minutes=15),
                    open=10.0,
                    high=10.0,
                    low=9.0,
                    close=9.4,  # Down 6% from entry (stop loss triggered)
                    volume=30000,
                    vwap=9.5
                ),
                'expected_reason': 'stop_loss'
            },
            # Profit target
            {
                'bar': MarketData(
                    symbol="TEST",
                    timestamp=entry_time + timedelta(minutes=15),
                    open=10.0,
                    high=11.5,
                    low=10.0,
                    close=11.1,  # Up 11% from entry (profit target)
                    volume=40000,
                    vwap=10.8
                ),
                'expected_reason': 'profit_target'
            },
            # Trailing stop
            {
                'bar': MarketData(
                    symbol="TEST",
                    timestamp=entry_time + timedelta(minutes=15),
                    open=10.0,
                    high=10.8,
                    low=10.2,
                    close=10.3,  # Up 3% from entry, but down from highest
                    volume=35000,
                    vwap=10.4
                ),
                'expected_reason': None  # Not triggered yet
            },
            # Time limit
            {
                'bar': MarketData(
                    symbol="TEST",
                    timestamp=entry_time + timedelta(minutes=65),  # Over 60 min limit
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.1,
                    volume=25000,
                    vwap=10.1
                ),
                'expected_reason': 'time_limit'
            }
        ]
        
        for i, case in enumerate(test_cases):
            # Reset entry signals for each test
            if i > 0:
                self.strategy.entry_signals["TEST"] = {
                    'gap_data': {
                        'direction': 'up',
                        'gap_percent': 5.0
                    },
                    'entry_price': 10.0,
                    'entry_time': entry_time,
                    'highest_price': 10.5,
                    'lowest_price': 9.8
                }
            
            # For trailing stop test, mock the gap fill check
            if i == 2:  # Trailing stop case
                with patch.object(self.strategy, '_check_gap_fill_risk', return_value=True):
                    signal = await self.strategy._check_exit_conditions("TEST", case['bar'])
            else:
                with patch.object(self.strategy, '_check_gap_fill_risk', return_value=True):
                    signal = await self.strategy._check_exit_conditions("TEST", case['bar'])
            
            if case['expected_reason']:
                self.assertIsNotNone(signal, f"Case {i}: Should generate exit signal")
                self.assertEqual(signal.metadata['reason'], case['expected_reason'], 
                               f"Case {i}: Wrong exit reason")
            else:
                self.assertIsNone(signal, f"Case {i}: Should not generate exit signal")
    
    def test_position_sizing(self):
        """Test position sizing respects max position value."""
        # Create signal
        signal = Signal(
            signal_id="test_signal",
            symbol="TEST",
            signal_type=SignalType.LONG,
            strength=0.8,
            price=10.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # Test with different prices
        test_cases = [
            (10.0, 20),    # 200 // 10 = 20 shares (max position value)
            (5.0, 20),     # Risk-based would be 40, but max is 20 due to max_position_value
            (20.0, 10),    # 200 // 20 = 10 shares
            (2.0, 50),     # Min quantity is 10, but risk allows 50
            (50.0, 10),    # Min quantity is 10 (even though max_position_value would allow only 4)
        ]
        
        for price, expected_quantity in test_cases:
            signal.price = price
            quantity = self.strategy.calculate_position_size(
                signal=signal,
                capital=10000,  # $10,000 capital
                risk_per_trade=0.02
            )
            
            self.assertEqual(quantity, expected_quantity, 
                           f"Price ${price}: Expected {expected_quantity} shares, got {quantity}")
    
    def test_time_validation(self):
        """Test time validation functions."""
        # Valid times
        self.assertTrue(self.strategy._is_valid_entry_time(9.5))  # 9:30 AM
        self.assertTrue(self.strategy._is_valid_entry_time(10.0))  # 10:00 AM
        self.assertTrue(self.strategy._is_valid_entry_time(11.0))  # 11:00 AM
        
        # Invalid times
        self.assertFalse(self.strategy._is_valid_entry_time(9.4))  # 9:24 AM (too early)
        self.assertFalse(self.strategy._is_valid_entry_time(11.1))  # 11:06 AM (too late)
    
    def test_gap_expiration(self):
        """Test gap expiration check."""
        current_time = datetime.now()
        
        # Fresh gap (5 minutes old)
        fresh_gap = {
            'timestamp': current_time - timedelta(minutes=5)
        }
        self.assertFalse(self.strategy._is_gap_expired(fresh_gap, current_time))
        
        # Expired gap (20 minutes old)
        expired_gap = {
            'timestamp': current_time - timedelta(minutes=20)
        }
        self.assertTrue(self.strategy._is_gap_expired(expired_gap, current_time))


if __name__ == "__main__":
    unittest.main()
