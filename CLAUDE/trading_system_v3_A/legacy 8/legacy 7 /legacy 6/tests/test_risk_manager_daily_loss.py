
import unittest
from unittest.mock import MagicMock
from core.risk_manager import RiskManager
from core.interfaces import TradingConfig

class TestRiskManagerDailyLoss(unittest.TestCase):
    def setUp(self):
        # Mock config
        self.config = MagicMock(spec=TradingConfig)
        self.config.portfolio_capital = 2000.0
        self.config.max_daily_loss_pct = 5.0
        self.config.max_daily_trades = 100
        self.config.simulation_mode = False
        self.config.debug_mode = False
        
        # Initialize RiskManager
        self.risk_manager = RiskManager(self.config)

    def test_daily_loss_limit_calculation(self):
        """Test that the limit is calculated correctly: 2000 * 5% = -100"""
        # We can't access the internal limit directly easily without modifying the code to expose it,
        # but we can test the behavior around the limit.
        
        # Limit should be -100.0
        
        # Case 1: PnL = -50 (Safe)
        self.risk_manager.daily_pnl = -50.0
        is_safe = self.risk_manager._check_daily_loss_limit()
        print(f"PnL: -50.0, Limit: -100.0 -> Safe? {is_safe}")
        self.assertTrue(is_safe, "Should be safe when PnL (-50) > Limit (-100)")

        # Case 2: PnL = -99 (Safe)
        self.risk_manager.daily_pnl = -99.0
        is_safe = self.risk_manager._check_daily_loss_limit()
        print(f"PnL: -99.0, Limit: -100.0 -> Safe? {is_safe}")
        self.assertTrue(is_safe, "Should be safe when PnL (-99) > Limit (-100)")

        # Case 3: PnL = -101 (Unsafe)
        self.risk_manager.daily_pnl = -101.0
        is_safe = self.risk_manager._check_daily_loss_limit()
        print(f"PnL: -101.0, Limit: -100.0 -> Safe? {is_safe}")
        self.assertFalse(is_safe, "Should be UNSAFE when PnL (-101) < Limit (-100)")

        # Case 4: PnL = -200 (Unsafe)
        self.risk_manager.daily_pnl = -200.0
        is_safe = self.risk_manager._check_daily_loss_limit()
        print(f"PnL: -200.0, Limit: -100.0 -> Safe? {is_safe}")
        self.assertFalse(is_safe, "Should be UNSAFE when PnL (-200) < Limit (-100)")

if __name__ == '__main__':
    unittest.main()
