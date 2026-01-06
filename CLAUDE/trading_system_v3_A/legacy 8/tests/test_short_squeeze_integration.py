import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.swing.short_squeeze_scanner import ShortSqueezeScanner
from strategies.swing_workers.short_squeeze_worker import ShortSqueezeWorker

# Mock objects
class MockExecutionEngine:
    def __init__(self):
        self.broker = MagicMock()

class MockRiskManager:
    pass

# Subclass to mock data fetching
class MockShortSqueezeScanner(ShortSqueezeScanner):
    async def _fetch_yahoo_stats(self, symbols):
        print(f"   [MOCK] Fetching stats for {symbols}")
        return {
            'GME': {'float_shares': 45_000_000, 'short_percent': 0.25, 'short_ratio': 5.0}, # Valid Squeeze
            'AAPL': {'float_shares': 15_000_000_000, 'short_percent': 0.01, 'short_ratio': 1.0} # Invalid
        }

async def test_integration():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("TestShortSqueeze")
    
    print("\n--- Testing Short Squeeze Scanner (with Mocks) ---")
    scanner = MockShortSqueezeScanner(logger=logger)
    
    # Mock candidates
    candidates = [
        {'symbol': 'GME', 'current_price': 25.0, 'gap_percentage': 5.0, 'volume_ratio': 2.0, 'quality_score': 80},
        {'symbol': 'AAPL', 'current_price': 150.0, 'gap_percentage': 1.0, 'volume_ratio': 1.0, 'quality_score': 60}
    ]
    
    opportunities = await scanner.scan_squeeze_candidates(candidates)
    print(f"Found {len(opportunities)} squeeze opportunities")
    
    for opp in opportunities:
        print(f"  ✅ Opportunity: {opp['symbol']}")
        print(f"     Float: {opp['squeeze_data']['float_shares']/1_000_000}M (<50M)")
        print(f"     Short: {opp['squeeze_data']['short_percent']:.1%} (>10%)")
        print(f"     Quality Score: {opp['quality_score']} (Boosted)")

    assert len(opportunities) == 1
    assert opportunities[0]['symbol'] == 'GME'
        
    print("\n--- Testing Short Squeeze Worker ---")
    worker = ShortSqueezeWorker(MockExecutionEngine(), MockRiskManager())
    
    for opp in opportunities:
        should_enter, reason = await worker.should_enter(opp)
        print(f"  - {opp['symbol']} Entry Decision: {should_enter}")
        print(f"    Reason: {reason}")
        
        assert should_enter is True
        assert "SQUEEZE_BREAKOUT" in reason

if __name__ == "__main__":
    asyncio.run(test_integration())
