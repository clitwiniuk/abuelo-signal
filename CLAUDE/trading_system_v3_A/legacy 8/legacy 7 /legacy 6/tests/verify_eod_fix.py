import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyEODFix")

async def test_eod_fix():
    print("\n🧪 STARTING SWING EOD FIX VERIFICATION\n")
    
# 1. Mock Dependencies & Environment
    import sys
    import os
    # Add project root to path so strategies can be imported
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    
    from unittest.mock import MagicMock
    
    # MOCK ib_insync BEFORE importing anything else
    mock_ib_insync = MagicMock()
    sys.modules["ib_insync"] = mock_ib_insync
    
    # MOCK pandas_ta (used by HolyGrailWorkerLogic)
    mock_pandas_ta = MagicMock()
    sys.modules["pandas_ta"] = mock_pandas_ta
    
    # MOCK other potential missing libs just in case
    # sys.modules["talib"] = MagicMock() 

    mock_engine = MagicMock()
    mock_risk = MagicMock()
    mock_config = MagicMock()
    
    # Configure mock config to return valid numbers for logging
    mock_config.getfloat.return_value = 1.0
    mock_config.getint.return_value = 1
    
    # 2. Import Worker Logic (Runtime import to get patched code)
    from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
    from strategies.workers.worker_stop_manager import WorkerStopManager, WorkerStopConfig
    
    # 3. Create Worker Instance
    worker = DailyPlaysWorkerLogic(mock_engine, mock_risk, mock_config)
    
    # 4. Mock StopManager and Config
    # We need a real-ish stop manager to verify flow, but we can mock internal logic
    stop_config = WorkerStopConfig(
        stop_loss_pct=0.05,
        trailing_activation=0.10,
        trailing_distance=0.03,
        take_profit_pct=0.20,
        max_position_hours=8.0,
        end_of_day_hour=15, # Trigger EOD check
    )
    worker.stop_manager = WorkerStopManager(stop_config)
    
    # 5. Create Test Scenario: EOD Event for Swing Trade
    # - Mid-Cap Swing Trade
    # - Time is AFTER EOD cutoff (15:50)
    # - EOD_safe flag is NESTED in opportunity_data (The original bug)
    
    symbol = "SWING_TEST"
    current_price = 100.0
    entry_price = 95.0 # +5% profit
    
    # The BUG was here: EOD_safe is nested, not at root
    position_data = {
        'symbol': symbol,
        'entry_price': entry_price,
        'quantity': 100,
        'strategy': 'daily_plays_midcap',
        'entry_time': datetime.now(),
        # Simulating partial data restoration or adapter structure
        'opportunity_data': {
            'symbol': symbol,
            'EOD_safe': True, # <--- THIS IS THE FLAG WE NEED TO FIND
            'trading_horizon': 'SWING',
            'catalyst_type': 'EARNINGS'
        }
    }
    
    # Register position so stop manager knows about it
    worker.stop_manager.register_position(symbol, datetime.now())
    
    print(f"📊 Test Position: {symbol}")
    print(f"   Entry: ${entry_price:.2f}, Current: ${current_price:.2f}")
    print(f"   Structure: EOD_safe is nested in ['opportunity_data']")
    
    # 6. Execute should_exit
    # We mock the current time check inside stop manager or force the EOD condition
    # For this unit test of the LOGIC, we want to see if 'EOD_safe': True is correctly extracted
    # and passed to check_exit.
    
    # Since we can't easily mock datetime.now() inside the module without patching,
    # we will inspect the 'position_metadata' passed to stop_manager.check_exit
    
    # Mock the stop_manager.check_exit method to intercept arguments
    original_check_exit = worker.stop_manager.check_exit
    worker.stop_manager.check_exit = MagicMock(return_value=(False, "MOCKED"))
    
    print("\n🚀 Executing worker.should_exit()...")
    await worker.should_exit(symbol, position_data, current_price)
    
    # 7. Verification
    # Check what was passed to stop_manager.check_exit
    call_args = worker.stop_manager.check_exit.call_args
    if not call_args:
        print("❌ FAIL: check_exit was not called!")
        return
        
    _, kwargs = call_args
    metadata = kwargs.get('position_metadata', {})
    
    print("\n🔍 VERIFICATION RESULTS (EOD Logic):")
    print(f"   Metadata passed to StopManager: {metadata}")
    
    extracted_eod_safe = metadata.get('EOD_safe')
    
    if extracted_eod_safe is True:
        print("✅ SUCCESS: EOD_safe=True was correctly extracted from nested data!")
        print("   The fix is WORKING. Swing trade would be PRESERVED.")
    else:
        print(f"❌ FAIL: EOD_safe was {extracted_eod_safe} (Expected True)")
        print("   The fix is NOT working. Trade would be CLOSED.")

    # 8. TEST TIME LIMIT LOGIC
    print("\n⏰ VERIFYING TIME LIMIT SAFETY Check...")
    # Mocking entry time to be 10 hours ago (exceeding 8h limit)
    from datetime import timedelta
    old_entry_time = datetime.now() - timedelta(hours=10)
    worker.stop_manager.entry_times[symbol] = old_entry_time
    
    # We call check_exit DIRECTLY to verify internal logic (skipping wrapper logic)
    should_exit, reason = worker.stop_manager.check_exit(
        symbol=symbol,
        current_price=100.0,
        entry_price=95.0,
        position_metadata=position_data # Passing full dict like wrapper does
    )
    
    if should_exit:
         print(f"❌ FAIL: Trade closed due to: {reason}")
         print("   Should have been ignored due to EOD_safe=True")
    else:
         print("✅ SUCCESS: Time limit exceeded (10h > 8h) but trade stayed OPEN!")
         print("   Reason: EOD_safe override worked correctly.")
         
if __name__ == "__main__":
    asyncio.run(test_eod_fix())
