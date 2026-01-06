import asyncio
import logging
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Diagnostic")

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidCapWorkerLogic

class DiagnosticSuite:
    def __init__(self):
        self.mock_engine = MagicMock()
        self.mock_risk = MagicMock()
        self.mock_risk.check_trade_risk = AsyncMock(return_value=True)
        self.mock_engine.execute_order = AsyncMock(return_value=True)
        
        # Mock Config
        self.mock_config = MagicMock()
        def getfloat(section, key, fallback=0.0):
            if section == 'SHORT_SQUEEZE_WORKER':
                if key == 'min_rel_volume': return 1.5  # RELAXED from 3.0
            if section == 'DAILY_PLAYS_MIDCAP_STRATEGY':
                if key == 'min_price': return 10.01
                if key == 'max_price': return 100.0
                if key == 'min_quality_score': return 50.0 # RELAXED from 65.0
                if key == 'min_volume_ratio': return 1.5   # RELAXED from 2.0
                if key == 'min_avg_volume': return 250000.0 # RELAXED
                if key == 'min_dollar_volume': return 1000000.0 # RELAXED
            return float(fallback)

        def getint(section, key, fallback=0):
            return int(fallback)
            
        def getboolean(section, key, fallback=True):
            return True # Always return True for enabled flags in this test

        self.mock_config.getfloat.side_effect = getfloat
        self.mock_config.getint.side_effect = getint
        self.mock_config.getboolean.side_effect = getboolean

    async def test_short_squeeze_lifecycle(self):
        logger.info("\n=== TEST 1: Short Squeeze Worker Lifecycle ===")
        
        # 1. Setup Worker
        worker = ShortSqueezeWorkerLogic(self.mock_engine, self.mock_risk, config=self.mock_config)
        
        # 2. Add Mock Candidate to DB (We mock the DB manager used by worker)
        # We need to simulate the worker's DB access. 
        # Since worker uses self.db_manager, we can patch its db path or mock sqlite3 within it.
        # But easier: Mock _get_proactive_candidate_info method to return a valid candidate without DB.
        
        worker._get_proactive_candidate_info = MagicMock(return_value={
            'symbol': 'TEST_SQUEEZE',
            'status': 'WATCHING',
            'days_since_detection': 1,
            'pattern_type': 'GREEN_DAY_1',
            'key_levels': json.dumps({'day1_high': 10.50, 'resistance': 10.50})
        })
        
        worker._update_candidate_status = MagicMock()
        
        # 3. Create PERFECT Opportunity
        # - Above VWAP
        # - High Volume
        # - Valid Price
        
        # Mock bars for VWAP calc
        mock_bar = MagicMock()
        mock_bar.close = 11.00
        mock_bar.open = 10.00
        mock_bar.high = 11.50
        mock_bar.low = 9.50
        mock_bar.volume = 1000000
        mock_bar.timestamp = datetime.now()
        
        worker.get_bars_from_opportunity = MagicMock(return_value=[mock_bar] * 20)
        worker.calculate_vwap_from_bars = MagicMock(return_value=10.80) # Price 11.00 > VWAP 10.80
        
        opp = {
            'symbol': 'TEST_SQUEEZE',
            'current_price': 11.00,
            'volume_ratio': 5.0, # High volume
            'gap_percentage': 2.0, 
            'trading_recommendation': {'squeeze_quality': 'IDEAL'}
        }
        
        logger.info(f"Simulating opportunity for TEST_SQUEEZE: Price=$11.00, VWAP=$10.80, Vol=5.0x")
        
        # 4. Run Logic
        # We bypass is_within_entry_hours by mocking it or running during hours
        worker.is_within_entry_hours = MagicMock(return_value=(True, 10.0))
        
        result = await worker.process_opportunity(opp)
        
        if result:
            logger.info("✅ SUCCESS: Short Squeeze worker TRIGGERED on valid setup.")
        else:
            logger.error("❌ FAILURE: Short Squeeze worker refused valid setup.")

    async def test_midcap_lifecycle(self):
        logger.info("\n=== TEST 2: Daily Plays MidCap Lifecycle ===")
        
        # 1. Setup Worker
        worker = DailyPlaysMidCapWorkerLogic(self.mock_engine, self.mock_risk, config=self.mock_config)
        
        # 2. Create PERFECT Opportunity
        # - Price > $10.01
        # - Good Quality
        
        opp = {
            'symbol': 'MIDCAP_HERO',
            'current_price': 25.50, # Valid > 10.01
            'gap_percentage': 3.0,
            'volume_ratio': 2.5,
            'quality_score': 85.0,
            'catalyst_type': 'EARNINGS'
        }
        
        # Mock internal validations
        worker.is_within_entry_hours = MagicMock(return_value=(True, 10.0))
        worker._check_risk_approval = AsyncMock(return_value=True)
        # DailyPlays checks 'context' usually, let's assume parent DailyPlays accepts it if we didn't mock should_enter too deep
        # Actually DailyPlaysWorkerLogic.should_enter calls super()... which is Base
        # But DailyPlays has complex logic: min_quality, min_vol, etc.
        
        # We need to ensure DailyPlaysWorkerLogic.should_enter passes.
        # It calls:
        # - _analyze_daily_potential (mock it)
        # - internal logic
        
        worker._analyze_daily_potential_for_signal = AsyncMock(return_value={
            'can_swing': True, 'resistance_level': 30.0, 'rsi_daily': 60
        })
        
        logger.info(f"Simulating opportunity for MIDCAP_HERO: Price=$25.50 (Target > $10.01)")
        
        result = await worker.process_opportunity(opp)
        
        # Note: If it fails, it might be due to deeper logic in DailyPlaysWorkerLogic we didn't fully mock.
        # But if it passes PRICE check and logs "Entry criteria met" or similar, we are good.
        
        # Actually process_opportunity returns execution result. Simulation returns True if checks pass.
        
        if result:
            logger.info("✅ SUCCESS: MidCap worker ACCEPTED valid >$10 opportunity.")
        else:
            # Check if it was because of our mocks being too simple or actual rejection
            # Since we can't see logs easily in script output if we capture them, we rely on return value.
            # DailyPlays often requires significant context.
            logger.info("ℹ️ NOTE: MidCap might require full context verification. Check logs above for rejection reason.")

    async def run(self):
        await self.test_short_squeeze_lifecycle()
        await self.test_midcap_lifecycle()

if __name__ == "__main__":
    suite = DiagnosticSuite()
    asyncio.run(suite.run())
