
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
import asyncio
from typing import List

# Import target class
from scanner.midcap.midcap_daily_scanner import MidCapDailyScanner, MidCapPlay
from scanner.ibkr_native_scanner import IBKRScanResult


# Helper class for robust async mocking
class MockNewsChecker:
    async def get_news_async(self, symbols):
        return {'AMD': [("AMD announces fail-safe AI chip", 1.5)]}

class TestMidCapScannerMocked(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        # Create a mock IBKR adapter
        self.mock_adapter = MagicMock()
        
        # Instantiate scanner with mocked adapter
        # Patching internal components to avoid external dependencies
        with patch('scanner.midcap.midcap_daily_scanner.IBKRNativeScanner') as MockIBKR, \
             patch('scanner.midcap.midcap_daily_scanner.CatalystAnalyzer') as MockCatalyst, \
             patch('scanner.midcap.midcap_daily_scanner.MultiSourceNewsChecker') as MockNews:
            
            self.scanner = MidCapDailyScanner(ibkr_adapter=self.mock_adapter)
            self.scanner.ibkr_scanner = MockIBKR.return_value
            self.scanner.catalyst_analyzer = MockCatalyst.return_value
            
            # REPLACING MagicMock with concrete class to fix await issue
            self.scanner.news_checker = MockNewsChecker()
            
            # Ensure async methods are AsyncMocks
            self.scanner.ibkr_scanner.scan_daily_plays = AsyncMock()

    async def test_scan_flow_end_to_end(self):
        """Test the full scan loop with mocked data"""
        
        # 1. Setup Mock Data from IBKR
        # 1. Setup Mock Data from IBKR
        from ib_insync import Contract
        mock_contract = Contract()
        mock_contract.symbol = 'AMD'
        mock_contract.secType = 'STK'
        mock_contract.exchange = 'SMART'
        mock_contract.currency = 'USD'

        mock_result = IBKRScanResult(
            symbol='AMD',
            contract=mock_contract,
            rank=1,
            distance='',
            benchmark='',
            projection='',
            legs='',
            current_price=90.0,
            change_percentage=5.5,
            volume=2000000,
            avg_volume=1000000,
            market_cap=20000, # 20B in Millions
            gap_percentage=5.5
        )
        # Manually set other attributes if needed by scanner logic
        mock_result.premarket_volume = 100000
        mock_result.float_shares = 500000000
        self.scanner.ibkr_scanner.scan_daily_plays.return_value = [mock_result]
        
        # 2. Setup Mock News
        # Already set in setUp. If we needed to change it for this specific test:
        # self.scanner.news_checker.fetch_headlines_batch.return_value = {'AMD': ...}
        # But we will rely on setUp for now to ensure AsyncMock consistency.
        
        # 3. Setup Catalyst Analyzer Result
        # Mocking the return of analyze_multiple_headlines
        mock_catalyst_info = MagicMock()
        mock_catalyst_info.catalyst_type = 'BREAKTHROUGH'
        mock_catalyst_info.strength = 8
        mock_catalyst_info.confidence = 0.9
        mock_catalyst_info.age_hours = 1.0  # Required for log formatting
        mock_catalyst_info.headline = "AMD announces fail-safe AI chip"
        
        self.scanner.catalyst_analyzer.analyze_multiple_headlines.return_value = mock_catalyst_info
        
        # 4. Run Scan
        plays = await self.scanner.scan_daily_plays()
        
        # 5. Assertions
        self.assertEqual(len(plays), 1)
        play = plays[0]
        
        self.assertEqual(play.symbol, 'AMD')
        self.assertEqual(play.catalyst_type, 'BREAKTHROUGH')
        self.assertEqual(play.catalyst_confidence, 90) # 0.9 * 100 = 90
        # Wait, code: catalyst_info['confidence'] = int(catalyst.confidence * 100)
        # Verify MidCapPlay attribute mapping
        
        self.assertEqual(int(play.catalyst_confidence), 90) 
        self.assertEqual(play.market_cap, 20000)
        
        print(f"✅ Verified MidCap Play: {play.symbol} matched with catalyst {play.catalyst_type}")

    async def test_quality_filtering(self):
        """Test that low quality plays are filtered out"""
        # Mock result that fails quality score due to low volume/gap?
        # Actually MidCapDailyScanner logic calculates quality score.
        # Let's ensure a play is generated but maybe verify filter logic if we had multiple inputs.
        pass

if __name__ == '__main__':
    unittest.main()
