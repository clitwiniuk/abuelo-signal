
import unittest
from datetime import datetime, time
from unittest.mock import MagicMock
from strategies.workers.worker_stop_manager import WorkerStopManager, WorkerStopConfig

class MockMarketData:
    def __init__(self, high, low, close):
        self.high = high
        self.low = low
        self.close = close

class TestMeritOvernight(unittest.TestCase):
    def setUp(self):
        self.config = WorkerStopConfig(
            stop_loss_pct=5.0,
            take_profit_pct=20.0,
            trailing_activation=10.0,
            trailing_distance=5.0,
            max_position_hours=8,
            end_of_day_hour=15.9
        )
        self.manager = WorkerStopManager(self.config)

    def test_swing_stays_open(self):
        # Scenario: Swing trade, should stay open regardless of strength
        # Strength = 0.5 (Weak) - But Demotion is DISABLED, so it should HOLD
        
        # 15:55 PM
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            # Fix: Create a mock object that behaves like a datetime but allows property access if needed
            # OR just trust that the code uses .hour which standard datetime has
            fixed_time = datetime(2025, 1, 1, 15, 55)
            mock_dt.now.return_value = fixed_time
            
            # The strategy logic uses: current_hour = market_time.hour + market_time.minute / 60
            # fixed_time has .hour and .minute, so this works natively
            
            # Weak close: Low=100, High=110, Current=102 (Strength=0.2)
            market_data = MockMarketData(high=110, low=100, close=102)
            
            should_exit, reason = self.manager.check_exit(
                symbol="SWING_WEAK",
                current_price=102,
                entry_price=100,
                market_data=market_data,
                position_metadata={'EOD_safe': True, 'trading_horizon': 'swing'}
            )
            
            print(f"Swing (Weak) Test: Exit={should_exit}, Reason={reason}")
            self.assertFalse(should_exit, "Swing trade should stay open (Demotion disabled)")

    def test_intraday_promotion(self):
        # Scenario: Intraday trade, STRONG close + WINNING -> Promote to Swing
        
        # 15:55 PM
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            # Need to Mock hour property access or ensure the logic uses the object we returned
            # The logic does: current_hour = market_time.hour + market_time.minute / 60
            # So the mock object needs .hour and .minute attributes
            
            # Let's mock the internal hour logic slightly differently or trust the mock above works 
            # if we pass the right object type. 
            # The code uses: market_time = datetime.now(...)
            # So mock_dt.now.return_value must have .hour
            
            # Strong close: Low=100, High=110, Current=109 (Strength=0.9)
            market_data = MockMarketData(high=110, low=100, close=109)
            
            should_exit, reason = self.manager.check_exit(
                symbol="INTRA_STRONG",
                current_price=109,
                entry_price=100, # PnL +9%
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday'}
            )
            
            print(f"Intraday (Strong) Test: Exit={should_exit}, Reason={reason}")
            self.assertFalse(should_exit, "Strong Intraday should be PROMOTED")

    def test_intraday_weak_closes(self):
        # Scenario: Intraday trade, WEAK close -> CLOSE
        
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            
            # Weak close: Low=100, High=110, Current=102 (Strength=0.2)
            market_data = MockMarketData(high=110, low=100, close=102)
            
            should_exit, reason = self.manager.check_exit(
                symbol="INTRA_WEAK",
                current_price=102,
                entry_price=100,
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday'}
            )
            
            print(f"Intraday (Weak) Test: Exit={should_exit}, Reason={reason}")
            self.assertTrue(should_exit, "Weak Intraday should CLOSE")

    def test_intraday_strong_loser_closes(self):
        # Scenario: Intraday trade, STRONG close but LOSING -> CLOSE (No reward for losers)
        
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            
            # Strong close relative to day, but entry was terrible (bagholding)
            # Low=100, High=110, Current=109 (Strength=0.9)
            # Entry=115 (Loss -5.2% - would likely stop out, but let's simulate smaller loss)
            # Entry=111 (-1.8%)
            market_data = MockMarketData(high=110, low=100, close=109)
            
            should_exit, reason = self.manager.check_exit(
                symbol="INTRA_LOSER",
                current_price=109,
                entry_price=111, # PnL -1.8%
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday'}
            )
            
            print(f"Intraday (Loser) Test: Exit={should_exit}, Reason={reason}")
            self.assertTrue(should_exit, "Losing Intraday should CLOSE regardless of strength")

    def test_intraday_short_exclusion(self):
        # Scenario: Intraday SHORT that is LOSING (Price > Entry) and closing at High (High Strength)
        # Assuming naive PnL calc returns positive for simplistic math ((110-100)/100 = +10%)
        # This MUST be rejected/closed, not promoted.
        
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            fixed_time = datetime(2025, 1, 1, 15, 55)
            mock_dt.now.return_value = fixed_time
            
            # Close at High (Strength 1.0)
            market_data = MockMarketData(high=110, low=100, close=110)
            
            # Naive PnL would interpret this as +10% gain if it doesn't know side
            # Entry=100, Price=110
            
            should_exit, reason = self.manager.check_exit(
                symbol="INTRA_SHORT_LOSER",
                current_price=110,
                entry_price=100,
                market_data=market_data,
                position_metadata={
                    'EOD_safe': False, 
                    'trading_horizon': 'intraday',
                    'side': 'SHORT',
                    'strategy': 'short_squeeze'
                }
            )
            
            print(f"Intraday (Short Safety) Test: Exit={should_exit}, Reason={reason}")
            self.assertTrue(should_exit, "Losing Short closing at High MUST CLOSE (Safety check)")

    def test_vcp_strict_split_behavior(self):
        # Verify the new split behavior
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            fixed_time = datetime(2025, 1, 1, 15, 55)
            mock_dt.now.return_value = fixed_time
            market_data = MockMarketData(high=110, low=100, close=110) # 100% Strength

            # Test 1: VCP Long (Eligible)
            should_exit_long, reason_long = self.manager.check_exit(
                symbol="VCP_LONG",
                current_price=110,
                entry_price=100, # +10%
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday', 'side': 'LONG', 'strategy': 'vcp_strict_long'}
            )
            self.assertFalse(should_exit_long, "VCP Long winning should be PROMOTED")

            # Test 2: VCP Short (Ineligible)
            # Even if winning (Entry 120, Price 110 -> Profitable), Shorts are NOT promoted
            should_exit_short, reason_short = self.manager.check_exit(
                symbol="VCP_SHORT",
                current_price=110,
                entry_price=120, # Profitable short
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday', 'side': 'SHORT', 'strategy': 'vcp_strict_short'}
            )
            # Should exit because Shorts are never promoted, logic falls through to EOD exit
            self.assertTrue(should_exit_short, "VCP Short (even if winning) should NOT be promoted")

    def test_scalp_exclusion(self):
        # Scenario: Scalp trade (Strong + Winning) -> Should CLOSE
        # Scalps are too risky to hold overnight regardless of strength
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            market_data = MockMarketData(high=110, low=100, close=110) # 100% Strength

            should_exit, reason = self.manager.check_exit(
                symbol="SCALP_WINNER",
                current_price=110,
                entry_price=100,
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'scalp', 'side': 'LONG'}
            )
            self.assertTrue(should_exit, "Scalp trades must always close, never promote")

    def test_breakeven_exclusion(self):
        # Scenario: Winning is strict (>0). What about exact breakeven?
        # Entry=100, Price=100. PnL=0.
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            market_data = MockMarketData(high=110, low=100, close=110) # 100% Strength

            should_exit, reason = self.manager.check_exit(
                symbol="BREAKEVEN_TRADE",
                current_price=100,
                entry_price=100,
                market_data=market_data,
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday', 'side': 'LONG'}
            )
            self.assertTrue(should_exit, "Breakeven trades should NOT be promoted (Need PnL > 0)")

    def test_strategy_name_safety_net(self):
        # Scenario: Metadata missing 'side' (defaults to LONG), but Strategy Name implies Short
        # This tests the "Name-based Safety Net"
        with unittest.mock.patch('strategies.workers.worker_stop_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 15, 55)
            market_data = MockMarketData(high=110, low=100, close=110)

            should_exit, reason = self.manager.check_exit(
                symbol="AMBIGUOUS_SHORT",
                current_price=110,
                entry_price=100,
                market_data=market_data,
                # Side missing! Defaults to LONG in code usually.
                # But strategy name has 'short'.
                position_metadata={'EOD_safe': False, 'trading_horizon': 'intraday', 'strategy': 'super_short_strategy'}
            )
            self.assertTrue(should_exit, "Strategy with 'short' in name must be blocked even if side metadata is missing")

if __name__ == '__main__':
    unittest.main()
