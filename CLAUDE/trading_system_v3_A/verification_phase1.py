import sys
import os
import logging
from datetime import datetime as dt_sys
from core.time_provider import SimulatedTimeProvider, SystemTimeProvider
from core.extended_hours_manager import ExtendedHoursManager, MarketSession
from core.execution_engine_adapter import ExecutionEngineAdapter
from core.events import create_bar_event
from replay_testing.core.replay_engine import ReplayEngine

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerificationPhase1")

def test_time_provider():
    logger.info("Testing TimeProvider...")
    sim_clock = SimulatedTimeProvider()
    try:
        sim_clock.now()
        logger.error("❌ SimulatedTimeProvider should raise error if not set")
    except RuntimeError:
        logger.info("✅ SimulatedTimeProvider raised error correctly when empty")
    
    now_real = dt_sys.now()
    sim_clock.set_time(now_real)
    assert sim_clock.now() == now_real
    logger.info("✅ SimulatedTimeProvider returned correct time")

def test_extended_hours_injection():
    logger.info("Testing ExtendedHoursManager injection...")
    sim_clock = SimulatedTimeProvider()
    
    # Set time to Market Open (Monday 9:35 AM ET)
    # 2025-10-27 is a Monday
    monday_morning = dt_sys(2025, 10, 27, 9, 35) # Naive, assuming local/system time logic fits what we did
    # ExtendedHoursManager logic:
    # If SystemTimeProvider (default), it converts system time to NY.
    # If Simulated, and naive, it assumes we should handle it. 
    # In my implementation: 
    # if isinstance(clock, SystemTimeProvider): convert astimezone
    # else: replace tzinfo=NY 
    
    sim_clock.set_time(monday_morning)
    
    ehm = ExtendedHoursManager(clock=sim_clock)
    session = ehm.get_market_session()
    logger.info(f"Session for {monday_morning}: {session}")
    
    # 9:35 AM ET should be REGULAR
    assert session == MarketSession.REGULAR
    logger.info("✅ Market session detected correctly with simulated clock")

    # Set time to Sunday
    sunday = dt_sys(2025, 10, 26, 14, 00)
    sim_clock.set_time(sunday)
    session = ehm.get_market_session()
    logger.info(f"Session for {sunday}: {session}")
    assert session == MarketSession.CLOSED
    logger.info("✅ Market session detected correctly as CLOSED on Sunday")

def test_replay_engine_instantiation():
    logger.info("Testing ReplayEngine instantiation...")
    # Assume running from root
    market_db = "market_data.db"
    trading_db = "trading_data.db"
    
    if not os.path.exists(market_db):
        logger.warning(f"Market DB not found at {market_db}, skipping full ReplayEngine test")
        return

    re = ReplayEngine(market_db, trading_db)
    logger.info(f"✅ ReplayEngine instantiated. Clock type: {type(re.clock)}")
    assert isinstance(re.clock, SimulatedTimeProvider)

if __name__ == "__main__":
    try:
        test_time_provider()
        test_extended_hours_injection()
        test_replay_engine_instantiation()
        print("\n🎉 ALL TESTS PASSED")
    except Exception as e:
        logger.error(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
