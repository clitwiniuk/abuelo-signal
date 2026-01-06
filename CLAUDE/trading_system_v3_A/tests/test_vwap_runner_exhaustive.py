
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from strategies.workers.smallcap_vwap_runner_worker_logic import SmallcapVwapRunnerWorker

# Mock Config
class MockConfig:
    def getfloat(self, section, key, fallback=0.0):
        defaults = {
            'min_quality': 60.0,
            'stop_loss_pct': 0.02,
            'vwap_buffer_pct': 0.01,
            'trailing_stop_pct': 0.03,
            'risk_per_trade': 0.01
        }
        return defaults.get(key, fallback)

# Mock Execution Engine
class MockExecutionEngine:
    def __init__(self):
        self.entered_positions = []
        self.exited_positions = []
        
    async def enter_position(self, symbol, strategy, opportunity_data):
        print(f"💰 ENGINE: Entering {symbol} ({strategy})")
        self.entered_positions.append({
            'symbol': symbol,
            'opportunity': opportunity_data
        })
        # Return a mock position
        return {
            'symbol': symbol,
            'entry_price': opportunity_data.get('current_price'),
            'quantity': 100,
            'status': 'OPEN'
        }

    async def exit_position(self, symbol, reason):
        print(f"🚪 ENGINE: Exiting {symbol} ({reason})")
        self.exited_positions.append({
            'symbol': symbol, 
            'reason': reason
        })
        return True

    def get_account_balance(self):
        return 100000.0

# Mock Risk Manager
class MockRiskManager:
    def __init__(self):
        self.config = MagicMock()
        self.broker_positions = {}

class TestSmallcapVwapRunnerWorker(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        self.mock_engine = MockExecutionEngine()
        self.mock_config = MockConfig()
        self.mock_risk_manager = MockRiskManager()
        
        # Patch heavy dependencies in BaseWorkerLogic.__init__
        self.patcher1 = patch('utils.log_config.setup_worker_logging', return_value=MagicMock())
        self.patcher2 = patch('core.service_locator.get_service_locator', return_value=MagicMock())
        self.patcher3 = patch('core.trade_event_logger.TradeEventLogger', return_value=MagicMock())
        self.patcher4 = patch('core.swing_transition_analyzer.SwingTransitionAnalyzer', return_value=MagicMock())
        
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()
        self.patcher4.start()
        
        # Pass config so BaseWorkerLogic sets self.config
        self.worker = SmallcapVwapRunnerWorker(
            self.mock_engine, 
            risk_manager=self.mock_risk_manager,
            config=self.mock_config
        )

    async def asyncTearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()


    async def test_1_scanner_communication_entry_criteria(self):
        """Verify worker accepts/rejects opportunities correctly (Scanner Interface)"""
        print("\n=== TEST 1: Scanner Communication & Entry Logic ===")
        
        # Case A: Perfect Setup
        opportunity_valid = {
            'symbol': 'VALID1',
            'quality_score': 80.0,  # > 60
            'current_price': 10.50,
            'vwap': 10.40,          # Price > VWAP
            'open': 10.45,
            'close': 10.50,         # Green Bar
        }
        
        should_enter, _, reason = await self.worker.should_enter(opportunity_valid)
        print(f"Case A (Valid): {should_enter} | Reason: {reason}")
        self.assertTrue(should_enter, "Should enter on valid criteria")

        # Case B: Low Quality
        opportunity_low_q = opportunity_valid.copy()
        opportunity_low_q['quality_score'] = 50.0
        should_enter, _, reason = await self.worker.should_enter(opportunity_low_q)
        print(f"Case B (Low Quality): {should_enter} | Reason: {reason}")
        self.assertFalse(should_enter, "Should reject low quality")

        # Case C: Below VWAP
        opportunity_below_vwap = opportunity_valid.copy()
        opportunity_below_vwap['current_price'] = 10.30
        should_enter, _, reason = await self.worker.should_enter(opportunity_below_vwap)
        print(f"Case C (Below VWAP): {should_enter} | Reason: {reason}")
        self.assertFalse(should_enter, "Should reject below VWAP")

        # Case D: Red Candle
        opportunity_red = opportunity_valid.copy()
        opportunity_red['open'] = 10.55
        opportunity_red['close'] = 10.50
        should_enter, _, reason = await self.worker.should_enter(opportunity_red)
        print(f"Case D (Red Candle): {should_enter} | Reason: {reason}")
        self.assertFalse(should_enter, "Should reject red candle")

    async def test_2_order_processing_and_sizing(self):
        """Verify position sizing and entry execution"""
        print("\n=== TEST 2: Order Processing & Sizing ===")
        
        symbol = 'ENTRY_TEST'
        price = 100.0
        vwap = 99.0
        
        opportunity = {
            'symbol': symbol,
            'current_price': price,
            'vwap': vwap,
            'quality_score': 75.0
        }
        
        # Calculate Risk
        # Stop 1: 2% -> 98.0
        # Stop 2: VWAP buffer 1% -> 99 * 0.99 = 98.01
        # Max(Stop) = 98.01
        # Risk Per Share = 100 - 98.01 = 1.99
        # Account Risk = 100k * 1% = 1000
        # Shares = 1000 / 1.99 = ~502
        
        shares = await self.worker.calculate_position_size(symbol, price, opportunity)
        print(f"Calculated Shares: {shares} (Expected ~502)")
        self.assertTrue(490 <= shares <= 510, f"Share count {shares} out of expected range")
        
    async def test_3_exit_logic_vwap_break(self):
        """Verify VWAP break triggers exit"""
        print("\n=== TEST 3: Exit Logic (VWAP Break) ===")
        symbol = 'EXIT_VWAP'
        
        # Setup position
        self.worker.active_positions[symbol] = {
            'entry_price': 100.0,
            'dynamic_stop_price': 98.0,
            'high_water_mark': 100.0
        }
        
        # Bar Data: Price drops below VWAP
        current_bar = {
            'close': 99.50,
            'vwap': 99.60, # Price < VWAP
            'timestamp': datetime.now()
        }
        
        should_exit, reason = await self.worker.should_exit(symbol, {}, current_bar)
        print(f"VWAP Break Check: {should_exit} | Reason: {reason}")
        self.assertTrue(should_exit, "Should exit on VWAP break")
        self.assertIn("VWAP break", reason)

    async def test_4_trailing_stop_logic(self):
        """Verify trailing stop updates and triggers"""
        print("\n=== TEST 4: Trailing Stop Logic ===")
        symbol = 'TRAIL_TEST'
        
        # Initial State
        self.worker.active_positions[symbol] = {
            'entry_price': 100.0,
            'dynamic_stop_price': 98.0,
            'high_water_mark': 100.0
        }
        
        # Step 1: Price Rises to 110 (Trail should move up)
        # Trail 3% -> 110 * 0.97 = 106.7
        bar_rise = {'close': 110.0, 'timestamp': datetime.now()}
        await self.worker.update_position(symbol, {}, bar_rise)
        
        new_stop = self.worker.active_positions[symbol]['dynamic_stop_price']
        print(f"Price rises to 110. New Stop: {new_stop:.2f} (Expected ~106.70)")
        self.assertAlmostEqual(new_stop, 106.7, delta=0.1)
        
        # Step 2: Price drops to 106 (Below trail 106.7)
        bar_drop = {'close': 106.0, 'vwap': 100.0, 'timestamp': datetime.now()}
        should_exit, reason = await self.worker.should_exit(symbol, {}, bar_drop)
        
        print(f"Price drops to 106. Exit? {should_exit} | Reason: {reason}")
        self.assertTrue(should_exit, "Should exit on trailing stop hit")
        self.assertIn("Stop hit", reason)

if __name__ == '__main__':
    unittest.main()
