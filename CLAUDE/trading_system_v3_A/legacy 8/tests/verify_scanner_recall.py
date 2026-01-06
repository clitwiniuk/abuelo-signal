
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner, SmallcapPlay
from scanner.ibkr_native_scanner import IBKRScanResult
from scanner.smallcap.catalyst_analyzer import CatalystInfo

class TestScannerRecall(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_adapter = MagicMock()
        
        # Initialize Scanner with test config
        self.config = {
            'min_quality_score': 50, # Strict for test
            'catalyst_max_age': {'EARNINGS': 24, 'NEWS': 24, 'OTHER': 24},
            'news_age_multipliers': {'fresh': 1.0, 'recent': 0.8, 'stale': 0.5},
            'fresh_news_threshold': 2,
            'recent_news_threshold': 6,
            'stale_news_threshold': 12,
            'max_news_age_hours': 24,
            'max_news_age_premarket': 24,
            'max_headlines_per_symbol': 5,
            'max_ibkr_results': 50,
            'max_plays_per_scan': 10
        }
        
        # Patch dependencies that require external connectivity
        with patch('scanner.smallcap.smallcap_daily_scanner.IBKRNativeScanner'), \
             patch('scanner.smallcap.smallcap_daily_scanner.CatalystAnalyzer'), \
             patch('scanner.smallcap.smallcap_daily_scanner.MultiSourceNewsChecker'):
             
             self.scanner = SmallcapDailyScanner(ibkr_adapter=self.mock_adapter, config=self.config)
             
             # Manually attach a mock catalyst analyzer for control
             self.scanner.catalyst_analyzer = MagicMock()

    def test_recall_known_winners(self):
        """
        Verify that known high-performing setups (from backtest) 
        pass the scanner's logic and receive high scores.
        """
        
        # 1. SCENARIO A: ASTS (Earnings Winner)
        # Simulation: Pre-market gap up on heavy volume
        asts_contract = MagicMock()
        asts_contract.symbol = 'ASTS'
        
        asts_result = IBKRScanResult(
            symbol='ASTS',
            contract=asts_contract,
            rank=1,
            distance="", benchmark="", projection="", legs="",
            current_price=12.50,
            gap_percentage=15.5, # Huge gap
            volume=5000000,      # Huge volume
            avg_volume=1000000,  # 5x relative
            market_cap=2000000000,
            estimated_float=100000000
        )
        
        # Mock Catalyst Analysis for ASTS
        asts_catalyst = CatalystInfo(
            catalyst_type='EARNINGS',
            strength=9,    # Very strong
            age_hours=0.5, # Fresh
            keywords_found=['earnings', 'beat'],
            headline="ASTS reports massive beat on revenue and partnerships",
            confidence=0.95
        )
        
        # 2. SCENARIO B: PLTR (Contract Winner)
        pltr_contract = MagicMock()
        pltr_contract.symbol = 'PLTR'
        
        pltr_result = IBKRScanResult(
            symbol='PLTR',
            contract=pltr_contract,
            rank=2,
            distance="", benchmark="", projection="", legs="",
            current_price=25.00,
            gap_percentage=12.5, # Realistic breakout gap
            volume=30000000,     # Strong Relative Volume (1.5x)
            avg_volume=20000000,
            market_cap=50000000000,
            estimated_float=1000000000
        )
        
        pltr_catalyst = CatalystInfo(
            catalyst_type='CONTRACT',
            strength=8,
            age_hours=1.0,
            keywords_found=['contract', 'army'],
            headline="PLTR wins huge army contract",
            confidence=0.9
        )
        
        # 3. SCENARIO C: NOISE (Low quality noise)
        noise_contract = MagicMock()
        noise_contract.symbol = 'NOISE'
        
        noise_result = IBKRScanResult(
            symbol='NOISE',
            contract=noise_contract,
            rank=50,
            distance="", benchmark="", projection="", legs="",
            current_price=5.00,
            gap_percentage=2.1,  # Weak gap
            volume=50000,        # Low volume
            avg_volume=100000,   # Low relative
            market_cap=100000000,
            estimated_float=10000000
        )
        
        noise_catalyst = CatalystInfo(
            catalyst_type='OTHER',
            strength=2, # Weak
            age_hours=5.0,
            keywords_found=[],
            headline="Some minor press release",
            confidence=0.2
        )

        # Setup the mock analyzer to return specific catalysts for specific calls
        # Note: logic calls analyze_multiple_headlines by default
        # We will bypass that and test _analyze_catalyst_opportunity directly for precision
        
        loop = asyncio.get_event_loop()
        
        print("\n🔎 TESTING SCANNER RECALL (Brain Check)...\n")
        
        # Test ASTS
        print(f"Testing ASTS (Earnings)...")
        asts_play = loop.run_until_complete(
            self.scanner._analyze_catalyst_opportunity(asts_result, asts_catalyst)
        )
        
        if asts_play:
            print(f"✅ ASTS DETECTED! Quality Score: {asts_play.quality_score:.1f}/10")
            print(f"   Recommendation: {asts_play.trading_recommendation}")
            self.assertTrue(asts_play.quality_score > 70, "ASTS should be High Quality (>70)")
        else:
            self.fail("❌ ASTS was REJECTED by Scanner Logic!")

        # Test PLTR
        print(f"\nTesting PLTR (Contract)...")
        pltr_play = loop.run_until_complete(
            self.scanner._analyze_catalyst_opportunity(pltr_result, pltr_catalyst)
        )
        
        if pltr_play:
            print(f"✅ PLTR DETECTED! Quality Score: {pltr_play.quality_score:.1f}/10")
            self.assertTrue(pltr_play.quality_score > 60, "PLTR should be Good Quality (>60)")
        else:
            self.fail("❌ PLTR was REJECTED by Scanner Logic!")
            
        # Test NOISE
        print(f"\nTesting NOISE (Weak)...")
        noise_play = loop.run_until_complete(
            self.scanner._analyze_catalyst_opportunity(noise_result, noise_catalyst)
        )
        
        if not noise_play or noise_play.quality_score < 50:
             print(f"✅ NOISE correctly filtered/scored low. (Score: {noise_play.quality_score if noise_play else 0})")
        else:
             print(f"⚠️ NOISE got a surprisingly high score: {noise_play.quality_score}")

        print("\n🎯 RECALL VERIFIED: The Scanner 'Brain' correctly identifies winners.")

if __name__ == '__main__':
    unittest.main()
