"""
Unit Tests for ShortSqueezeWorkerLogic
Tests worker decision logic in isolation
"""
import unittest
import asyncio
import sqlite3
import json
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
import sys
import os

sys.modules['pandas_ta'] = MagicMock()
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager

class MockConfig:
    def getfloat(self, section, key, fallback=0.0):
        return fallback

class TestShortSqueezeWorkerLogic(unittest.TestCase):
    """Test worker entry logic"""
    
    def setUp(self):
        self.db = DatabaseManager()
        self.conn = sqlite3.connect(self.db.db_path)
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        
        # Mock broker
        self.mock_broker = MagicMock()
        # Default: Easy to Borrow is True
        self.mock_broker.get_short_data = AsyncMock(return_value={
            'shortable': True, 
            'shortable_shares': 100000,
            'is_etb': True,
            'short_status': 'ETB'
        })
        
        self.mock_ee = MagicMock()
        self.mock_ee.broker = self.mock_broker
        
        # Create worker
        self.worker = ShortSqueezeWorkerLogic(
            execution_engine=self.mock_ee,
            risk_manager=MagicMock(),
            config=MockConfig()
        )
        
    def tearDown(self):
        self.conn.execute("DELETE FROM proactive_candidates")
        self.conn.commit()
        self.conn.close()
        
    def _insert_candidate(self, symbol):
        """Helper to insert test candidate"""
        self.conn.execute("""
            INSERT INTO proactive_candidates 
            (symbol, detection_date, pattern_type, status)
            VALUES (?, date('now'), 'GREEN_DAY_1', 'WATCHING')
        """, (symbol,))
        self.conn.commit()
        
    def _create_bars(self, price_start, price_end, count=50):
        """Helper to create mock bars"""
        bars = []
        step = (price_end - price_start) / count
        for i in range(count):
            p = price_start + (i * step)
            bars.append(MagicMock(
                timestamp=datetime.now(),
                open=p, high=p+0.05, low=p-0.05, close=p+0.02, volume=100000
            ))
        return bars
        
    def test_entry_with_valid_candidate(self):
        """Test entry when candidate is in watchlist and ETB"""
        self._insert_candidate('TEST')
        
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.50,
            'volume_ratio': 3.0,
            'vwap': 10.00,
            'bars': self._create_bars(10.0, 10.5)
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertTrue(result, "Should enter when all conditions met and ETB")
        
    def test_accept_htb_on_day_of_operation(self):
        """Test acceptance if stock is HTB on the day of operation (Ideal for Squeeze)"""
        self._insert_candidate('TEST_HTB')
        
        # Mock HTB on this call
        self.mock_broker.get_short_data = AsyncMock(return_value={
            'shortable': True,
            'shortable_shares': 1000,
            'is_etb': False,
            'short_status': 'HTB'
        })
        
        opportunity = {
            'symbol': 'TEST_HTB',
            'current_price': 10.50,
            'volume_ratio': 3.0,
            'vwap': 10.00,
            'bars': self._create_bars(10.0, 10.5)
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertTrue(result, "Should accept HTB on the day of operation as it's ideal for a squeeze")

    def test_accept_ultimate_with_quality_metadata(self):
        """Test that ULTIMATE quality is correctly passed and handled"""
        self._insert_candidate('TEST_ULTIMATE')
        
        # Mock ZERO borrows
        self.mock_broker.get_short_data = AsyncMock(return_value={
            'shortable': True,
            'shortable_shares': 0,
            'is_etb': False,
            'short_status': 'NONE'
        })
        
        opportunity = {
            'symbol': 'TEST_ULTIMATE',
            'current_price': 10.50,
            'volume_ratio': 3.0,
            'vwap': 10.00,
            'trading_recommendation': {
                'squeeze_quality': 'ULTIMATE'
            },
            'bars': self._create_bars(10.0, 10.5)
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertTrue(result)
        # Verify ULTIMATE log was triggered
        # Note: We rely on manual log inspection or capturing logs if needed, 
        # but here we just ensure it doesn't crash and returns True.
        
    def test_reject_not_in_watchlist(self):
        """Test rejection when not in watchlist"""
        opportunity = {
            'symbol': 'UNKNOWN',
            'current_price': 10.50,
            'volume_ratio': 3.0,
            'vwap': 10.00
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertFalse(result, "Should reject if not in watchlist")
        
    def test_calculate_adaptive_risk_multipliers(self):
        """Test that different squeeze quality levels apply correct multipliers"""
        # Base risk should be handled by super(), we just check if multi is applied.
        # We need to mock service_locator.get_config to avoid loading actual config
        from unittest.mock import MagicMock
        mock_config = MagicMock()
        mock_config.enable_adaptive_risk_sizing = True
        mock_config.base_risk_percent = 1.0 # 1.0%
        mock_config.min_risk_percent = 0.5
        mock_config.max_risk_percent = 5.0
        mock_config.quality_boost_threshold = 100 # No boost
        mock_config.quality_boost_amount = 0.3
        mock_config.pattern_alignment_threshold = 10 # No boost
        mock_config.pattern_alignment_boost = 0.2
        mock_config.high_volatility_threshold = 8.0
        mock_config.high_volatility_reduction = 0.2
        
        self.worker.service_locator.get_config = MagicMock(return_value=mock_config)
        
        base_opportunity = {
            'symbol': 'TEST',
            'quality_score': 50,
            'trading_recommendation': {}
        }
        
        # 1. ULTIMATE -> 1.0x
        base_opportunity['trading_recommendation']['squeeze_quality'] = 'ULTIMATE'
        risk_ultimate = self.worker.calculate_adaptive_risk(base_opportunity)
        self.assertAlmostEqual(risk_ultimate, 0.01, places=4) # 1.0 * 1.0% = 1.0%
        
        # 2. IDEAL -> 1.0x (Updated to more aggressive)
        base_opportunity['trading_recommendation']['squeeze_quality'] = 'IDEAL'
        risk_ideal = self.worker.calculate_adaptive_risk(base_opportunity)
        self.assertAlmostEqual(risk_ideal, 0.01, places=4) # 1.0 * 1.0 = 1.0%
        
        # 3. NORMAL -> 0.5x (Updated to more aggressive)
        base_opportunity['trading_recommendation']['squeeze_quality'] = 'NORMAL'
        risk_normal = self.worker.calculate_adaptive_risk(base_opportunity)
        self.assertAlmostEqual(risk_normal, 0.005, places=4) # 1.0 * 0.5 = 0.5%

    def test_breakout_open_detection(self):
        """Test detection when price is 0-1% above Day 1 High"""
        self._insert_candidate('BREAKOUT')
        
        opportunity = {
            'symbol': 'BREAKOUT',
            'current_price': 10.05, # 0.5% above 10.0
            'trading_recommendation': {
                'day1_high': 10.0
            }
        }
        
        # Test exact range
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertTrue(result)
        self.assertEqual(opportunity.get('setup_type'), 'BREAKOUT_OPEN')

        # Test slightly outside (too high)
        opportunity['current_price'] = 10.15 # 1.5% above
        opportunity['setup_type'] = None
        # Should continue to normal logic (VWAP check) which might fail if no bars
        opportunity['bars'] = [] # Force failure of normal logic
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertFalse(result)

    def test_breakout_open_sizing_and_stop(self):
        """Test sizing override and stop loss enforcement for Breakout Open"""
        self.worker.calculate_adaptive_risk = MagicMock(return_value=0.012) # 1.2% base
        
        opportunity = {
            'symbol': 'BREAKOUT',
            'current_price': 10.05,
            'setup_type': 'BREAKOUT_OPEN',
            'trading_recommendation': {
                'day1_high': 10.0,
                'squeeze_quality': 'NORMAL' # Would normally be 0.5x
            }
        }
        
        # 1. Test Sizing Override (should be 1.0x even if NORMAL)
        # Re-mocking calculate_adaptive_risk with real method to test logic
        from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
        original_method = ShortSqueezeWorkerLogic.calculate_adaptive_risk
        
        # Sizing test (NORMAL quality + BREAKOUT_OPEN setup)
        # Mock base logic to return 1.2%
        with unittest.mock.patch('strategies.workers.base_worker_logic.BaseWorkerLogic.calculate_adaptive_risk', return_value=0.012):
            risk = original_method(self.worker, opportunity)
            self.assertEqual(risk, 0.012) # 1.0 multiplier applied
            # Verify stop loss was also set as a side effect
            self.assertAlmostEqual(opportunity['stop_loss'], 9.90) # 10.0 * 0.99

    def test_reject_price_below_vwap(self):
        """Test rejection when price < VWAP"""
        self._insert_candidate('TEST')
        
        # Bars from 9.0 to 10.0 -> VWAP around 9.5
        opportunity = {
            'symbol': 'TEST',
            'current_price': 9.20,  # Below VWAP (9.5)
            'volume_ratio': 3.0,
            'vwap': 10.00,
            'bars': self._create_bars(9.0, 10.0)
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertFalse(result, "Should reject when price < VWAP")
        
    def test_quiet_rise_scenario(self):
        """Test Quiet Rise (low volume but high gap)"""
        self._insert_candidate('TEST')
        
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.50,
            'volume_ratio': 1.5,  # Low volume
            'gap_percentage': 6.0,  # High gap
            'vwap': 10.00,
            'bars': self._create_bars(10.0, 10.5)
        }
        
        result = asyncio.run(self.worker.should_enter(opportunity))
        self.assertTrue(result, "Should enter on Quiet Rise")

if __name__ == '__main__':
    unittest.main()
