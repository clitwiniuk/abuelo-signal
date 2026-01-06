
import asyncio
import logging
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner, OpportunityType
from scanner.ibkr_native_scanner import IBKRScanResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_intraday_mover_logic():
    """Test if the new INTRADAY_MOVER logic catches a FLYE-like scenario"""
    
    print("\n--- Testing INTRADAY_MOVER Logic ---")
    
    # Mock scanner
    scanner = SmallcapDailyScanner()
    scanner.config['min_quality_score'] = 1.0 # Low threshold for test
    scanner._create_context = AsyncMock(return_value=MagicMock()) # Mock context creation
    
    # Simulate FLYE: 
    # - Price: $8.40
    # - Gap: 0.9% (Small)
    # - Change: +25% (Large intraday move)
    # - Volume: 150k (Moderate/Low)
    
    flye_result = IBKRScanResult(
        symbol="FLYE",
        rank=1,
        contract=MagicMock(), # Add required contract arg
        distance="",
        benchmark="",
        projection="",
        legs="",
        current_price=8.40,
        change_percentage=25.0, # 25% move
        gap_percentage=0.9,
        volume=150000,
        avg_volume=100000,
        market_cap=50000000
    )
    
    print(f"Simulating FLYE: Price=${flye_result.current_price}, Change={flye_result.change_percentage}%, Vol={flye_result.volume}")
    
    # Test the method directly
    play = await scanner._analyze_intraday_mover_opportunity(flye_result)
    
    if play:
        print(f"✅ SUCCESS: Detected INTRADAY_MOVER opportunity!")
        print(f"   Type: {play.opportunity_type}")
        print(f"   Quality: {play.quality_score}")
        print(f"   Rec: {play.trading_recommendation}")
    else:
        print(f"❌ FAILURE: Did not detect opportunity")

    # Test a non-mover (should fail)
    boring_result = IBKRScanResult(
        symbol="BORE",
        rank=2,
        contract=MagicMock(),
        distance="",
        benchmark="",
        projection="",
        legs="",
        current_price=10.0,
        change_percentage=2.0, # Only 2% move
        gap_percentage=0.0,
        volume=200000,
        avg_volume=200000,
        market_cap=50000000
    )
    
    print(f"\nSimulating BORE: Price=${boring_result.current_price}, Change={boring_result.change_percentage}%, Vol={boring_result.volume}")
    play_boring = await scanner._analyze_intraday_mover_opportunity(boring_result)
    
    if not play_boring:
        print(f"✅ SUCCESS: Correctly rejected non-mover")
    else:
        print(f"❌ FAILURE: Incorrectly detected non-mover")

if __name__ == "__main__":
    asyncio.run(test_intraday_mover_logic())
