
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pandas_ta to prevent import error
sys.modules['pandas_ta'] = MagicMock()

from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic

class TestTieredSizing(unittest.TestCase):
    def setUp(self):
        # Mock Config
        self.mock_config = MagicMock()
        # Setup getboolean for enable_tiered_sizing
        def getboolean_side_effect(section, key, fallback=False):
            if key == 'enable_tiered_sizing': return True
            return fallback
        self.mock_config.getboolean.side_effect = getboolean_side_effect
        
        def get_side_effect(section, key, fallback=None):
            if key == 'earnings_risk_multiplier': return 1.5
            if key == 'standard_risk_multiplier': return 0.5
            return fallback
        self.mock_config.get.side_effect = get_side_effect

        def getfloat_side_effect(section, key, fallback=0.0):
            if key == 'min_price': return 5.0
            if key == 'max_price': return 200.0
            if key == 'min_quality_score': return 65.0
            if key == 'min_volume_ratio': return 2.0
            return fallback
        self.mock_config.getfloat.side_effect = getfloat_side_effect

        def getint_side_effect(section, key, fallback=0):
            if key == 'min_avg_volume': return 100000
            return fallback
        self.mock_config.getint.side_effect = getint_side_effect
        
        # Use defaults for base risk attributes
        self.mock_config.base_risk_percent = 1.0  # 1% base
        self.mock_config.min_risk_percent = 0.5
        self.mock_config.max_risk_percent = 2.0
        self.mock_config.quality_boost_threshold = 100 # Disable boost for clear test
        self.mock_config.pattern_alignment_threshold = 100 # Disable boost
        self.mock_config.high_volatility_threshold = 100 # Disable reduction

        # Instantiate Worker
        self.worker = DailyPlaysWorkerLogic(
            execution_engine=MagicMock(),
            risk_manager=MagicMock(),
            config=self.mock_config
        )
        # Mock Service Locator config access
        self.worker.service_locator = MagicMock()
        self.worker.service_locator.get_config.return_value = self.mock_config

    def test_tiered_risk_application(self):
        # Base Opportunity
        base_opp = {
            'symbol': 'TEST',
            'quality_score': 70, # Neutral
            'atr_percent': 2.0,
            'catalyst_type': 'NONE'
        }

        # 1. Test EARNINGS (Tier A)
        opp_earnings = base_opp.copy()
        opp_earnings['catalyst_type'] = 'EARNINGS'
        
        risk_earnings = self.worker.calculate_adaptive_risk(opp_earnings)
        print(f"\n[TEST] Earnings Risk: {risk_earnings*100:.2f}% (Expected ~1.5%)")

        # 2. Test NEWS (Tier B)
        opp_news = base_opp.copy()
        opp_news['catalyst_type'] = 'NEWS'
        
        risk_news = self.worker.calculate_adaptive_risk(opp_news)
        print(f"[TEST] News Risk:     {risk_news*100:.2f}% (Expected ~0.5%)")

        # ASSERTIONS
        # Base risk is 1.0% (0.01)
        # Earnings should be 1.5x -> 1.5%
        # News should be 0.5x -> 0.5%
        
        self.assertAlmostEqual(risk_earnings, 0.015, places=4, msg="Earnings risk should be 1.5x base")
        self.assertAlmostEqual(risk_news, 0.005, places=4, msg="News risk should be 0.5x base")
        
        print("\n✅ Tiered Sizing Logic VERIFIED: Earnings gets 3x the size of News.")

if __name__ == '__main__':
    unittest.main()
