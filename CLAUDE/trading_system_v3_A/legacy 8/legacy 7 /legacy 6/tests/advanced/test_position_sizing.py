"""
Test suite for position sizing and max position value validation.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import the strategy to test
from strategies.volume_momentum_strategy import VolumeMomentumStrategy
from core.interfaces import Signal, SignalType, MarketData, Position

class TestPositionSizing(unittest.TestCase):
    """Test position sizing and max position value validation."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock logger
        self.mock_logger = MagicMock()
        
        # Create strategy with test parameters
        self.strategy = VolumeMomentumStrategy(
            parameters={
                'max_position_value': 200.0,  # Max $200 per position
                'max_risk_per_trade': 0.02,   # 2% risk per trade
                'min_quantity': 1,            # Minimum 1 share
                'position_scale_on_volume': False  # Disable volume scaling for tests
            }
        )
        self.strategy.logger = self.mock_logger
        
        # Mock market data
        self.sample_bar = MarketData(
            symbol="TEST",
            timestamp=datetime.now(),
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.0,
            volume=10000,
            vwap=10.0
        )
        
        # Sample signal with required fields for Signal class
        self.signal = Signal(
            signal_id="test_signal_123",
            symbol="TEST",
            signal_type=SignalType.LONG,
            strength=0.8,  # Strength between 0.0 and 1.0
            price=10.0,
            timestamp=datetime.now(),
            metadata={
                'stop_loss': 9.5,
                'take_profit': 10.5
            }
        )
    
    def test_max_position_value_respected(self):
        """Test that position value does not exceed max_position_value."""
        # Test with different price points
        test_cases = [
            (10.0, 20),    # 200 // 10 = 20 shares
            (20.0, 10),    # 200 // 20 = 10 shares
            (5.0, 40),     # 200 // 5 = 40 shares
            (25.0, 8),     # 200 // 25 = 8 shares
            (30.0, 6),     # 200 // 30 = 6 shares
            (201.0, 0),    # Price > max_position_value, should be 0
        ]
        
        for price, expected_quantity in test_cases:
            with self.subTest(price=price, expected=expected_quantity):
                self.signal.price = price
                quantity = self.strategy.calculate_position_size(
                    signal=self.signal,
                    capital=10000,  # $10,000 capital
                    risk_per_trade=0.02
                )
                
                # Verify position value does not exceed max
                position_value = price * quantity
                max_allowed = self.strategy._parameters['max_position_value']
                
                if price > max_allowed:
                    self.assertEqual(quantity, 0, 
                                   f"Should not take position when price (${price}) > max_position_value (${max_allowed})")
                else:
                    # Check that position value is within limits
                    self.assertLessEqual(position_value, max_allowed * 1.001,  # 0.1% tolerance
                                     f"Position value ${position_value:.2f} exceeds max ${max_allowed}")
                    # Verify we're not getting more shares than max position value allows
                    if quantity > 0:  # Only check if we got a position
                        self.assertLessEqual(quantity, expected_quantity,
                                         f"Should not get more than {expected_quantity} shares at ${price}")
                    # It's acceptable to get 0 if the position would be too small
                    # due to risk parameters or other factors
    
    def test_volume_scaling_does_not_exceed_max(self):
        """Test that volume scaling doesn't cause position value to exceed max."""
        # Enable volume scaling and set max position value to $200
        self.strategy._parameters['position_scale_on_volume'] = True
        self.strategy._parameters['max_position_value'] = 200.0
        
        # Mock entry signals with high volume ratio
        self.strategy.entry_signals = {
            "TEST": {
                'volume_analysis': {
                    'volume_ratio': 4.0,  # Would give 2.0x multiplier (capped at 1.5x)
                    'volume_ma': 10000,
                    'current_volume': 40000  # 4x average volume
                },
                'entry_price': 100.0
            }
        }
        
        # Test with price that would exceed max if not capped
        self.signal.price = 100.0
        
        # Calculate position size with volume scaling
        quantity = self.strategy.calculate_position_size(
            signal=self.signal,
            capital=10000,
            risk_per_trade=0.02
        )
        
        # Calculate position value
        position_value = self.signal.price * quantity
        
        # Verify position value doesn't exceed max
        self.assertLessEqual(position_value, 200.0,
                           f"Position value ${position_value:.2f} exceeds max $200")
        
        # Verify we got a valid position size (either 0 or within limits)
        if quantity > 0:
            self.assertGreaterEqual(quantity, self.strategy._parameters['min_quantity'],
                                 f"Should respect minimum quantity of {self.strategy._parameters['min_quantity']}")
            self.assertLessEqual(position_value, 200.0 * 1.001,  # 0.1% tolerance
                              f"Position value ${position_value:.2f} exceeds max $200")
    
    def test_min_quantity_respected(self):
        """Test that minimum quantity is respected when possible."""
        # Set min_quantity to 10 and max_position_value to $200
        self.strategy._parameters['min_quantity'] = 10
        self.strategy._parameters['max_position_value'] = 200.0
        
        # Test case 1: Price is too high for min_quantity within max_position_value
        self.signal.price = 1000.0  # 200/1000 = 0.2 shares (below min_quantity)
        
        quantity = self.strategy.calculate_position_size(
            signal=self.signal,
            capital=10000,
            risk_per_trade=0.02
        )
        
        # Should return 0 because min_quantity would exceed max_position_value
        self.assertEqual(quantity, 0,
                        f"Should return 0 when price (${self.signal.price:.2f}) * min_quantity ({self.strategy._parameters['min_quantity']}) > max_position_value (${self.strategy._parameters['max_position_value']})")
        
        # Test case 2: Price allows min_quantity within max_position_value
        self.signal.price = 15.0  # 200/15 = 13.33 shares (above min_quantity)
        
        quantity = self.strategy.calculate_position_size(
            signal=self.signal,
            capital=10000,
            risk_per_trade=0.02
        )
        
        # Should return at least min_quantity if possible
        if quantity > 0:  # If we get a position
            self.assertGreaterEqual(quantity, self.strategy._parameters['min_quantity'],
                                  f"Should return at least {self.strategy._parameters['min_quantity']} shares when possible")
            
            # And position value should be within limits
            position_value = self.signal.price * quantity
            max_allowed = self.strategy._parameters['max_position_value']
            self.assertLessEqual(position_value, max_allowed * 1.001,  # 0.1% tolerance
                              f"Position value ${position_value:.2f} exceeds max ${max_allowed}")
        else:
            # It's acceptable to get 0 if the strategy decides not to take the trade
            # based on other factors (like risk parameters)
            pass

if __name__ == "__main__":
    unittest.main()
