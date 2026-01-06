
import asyncio
import logging
import json
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock pandas_ta before other imports
sys.modules['pandas_ta'] = MagicMock()

from scanner.smallcap.proactive_scanner import ProactiveScanner
from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.database_manager import DatabaseManager
from scanner.ibkr_native_scanner import IBKRScanResult

class ModularBacktest:
    """
    Simulates the end-to-end flow of the Proactive Squeeze System:
    Day 0: Proactive Scanner detects a 'Green Day 1' setup and saves to DB.
    Day 1: Trader process loads the candidate, worker logic evaluates intraday open
           and triggers a 'BREAKOUT_OPEN' trade with stylized sizing.
    """
    
    def __init__(self):
        self.setup_logging()
        self.db_manager = DatabaseManager()
        self.symbol = "SIM_RUNNER"
        
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("ModularBacktest")

    async def run(self):
        self.logger.info("🎬 Starting Modular Backtest Simulation...")
        
        # 1. Clean up simulation state
        self._cleanup()
        
        # 2. Simulate DAY 0: Proactive Detection
        await self.simulate_day_0_detection()
        
        # 3. Simulate DAY 1: Worker Execution
        await self.simulate_day_1_execution()
        
        self.logger.info("🏁 Modular Backtest Completed Successfully!")

    def _cleanup(self):
        """Reset DB for simulation"""
        with sqlite3.connect(self.db_manager.db_path) as conn:
            conn.execute("DELETE FROM proactive_candidates WHERE symbol = ?", (self.symbol,))
            conn.commit()
        self.logger.info(f"🧹 Cleaned up state for {self.symbol}")

    async def simulate_day_0_detection(self):
        self.logger.info(f"--- 📅 DAY 0: Detecting {self.symbol} ---")
        
        # Mocking IBKR Adapter and News
        mock_ibkr = MagicMock()
        
        # Mock Daily Bars for Green Day 1
        # Previous 14 days: Low volume (100k), Price 8.5
        day_0_bars = []
        for i in range(14, 0, -1):
            day_0_bars.append(MagicMock(
                date=(datetime.now() - timedelta(days=i+1)), 
                open=8.5, high=8.7, low=8.4, close=8.5, volume=100000
            ))
            
        # Today (Day 0): 23.5% gain, 80% retention, 3x volume (300k)
        # PrevClose 8.5, Open 8.5, High 11.0, Close 10.5
        day_0_bars.append(MagicMock(
            date=(datetime.now() - timedelta(days=1)), 
            open=8.5, high=11.0, low=8.5, close=10.5, volume=350000 # 3.5x vol
        ))
        
        mock_ibkr.get_bars = AsyncMock(return_value=day_0_bars)
        
        # Mock Borrows
        mock_ibkr.get_short_data = AsyncMock(return_value={
            'short_status': 'HTB', # IDEAL
            'shortable_shares': 500
        })

        scanner = ProactiveScanner(ibkr_adapter=mock_ibkr)
        
        # Mock News Catalyst
        scanner._check_news_catalyst = AsyncMock(return_value=True)
        
        # Create a mock result instead of strict IBKRScanResult class
        mock_result = MagicMock()
        mock_result.symbol = self.symbol
        mock_result.rank = 1
        mock_result.gap_percentage = 25.0
        mock_result.current_price = 10.5
        mock_result.volume = 300000
        
        # Execute scan
        pattern = await scanner._analyze_daily_structure(mock_result)
        if pattern:
            scanner._save_candidates([pattern])
            self.logger.info(f"✅ DAY 0 SUCCESS: {self.symbol} saved to DB as {pattern['pattern_type']}")
            self.logger.info(f"   Metrics: rel_vol={pattern['metrics']['rel_vol']:.1f}, quality={pattern['metrics']['squeeze_quality']}")
            self.logger.info(f"   Levels: Day1High=${pattern['key_levels']['day1_high']:.2f}")
        else:
            self.logger.error("❌ DAY 0 FAILURE: Pattern not detected")
            sys.exit(1)

    async def simulate_day_1_execution(self):
        self.logger.info(f"--- 📅 DAY 1 (Opening): Executing {self.symbol} ---")
        
        # Mock Worker dependencies
        mock_ee = MagicMock()
        mock_broker = MagicMock()
        mock_ee.broker = mock_broker
        
        # Day 1 Open: Market gaps to 10.05 (0.5% above Day 1 High 10.0)
        # We need to simulate the worker receiving this through Redis
        
        # 1. Setup Worker
        from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
        worker = ShortSqueezeWorkerLogic(execution_engine=mock_ee, risk_manager=MagicMock(), config=MagicMock())
        
        # We need to mock the opportunity arriving with standard metadata
        # In real life, SmallcapDailyScanner._load_proactive_watchlist fills this
        opportunity = {
            'symbol': self.symbol,
            'current_price': 10.05, # Breakout!
            'trading_recommendation': {
                'day1_high': 10.0,
                'squeeze_quality': 'IDEAL' # 1.0x sizing
            }
        }
        
        # 2. Check Detection
        should_enter = await worker.should_enter(opportunity)
        self.logger.info(f"🔍 Worker Evaluation: should_enter={should_enter}, setup_type={opportunity.get('setup_type')}")
        
        if should_enter and opportunity.get('setup_type') == 'BREAKOUT_OPEN':
            self.logger.info("✅ DAY 1 DETECTION SUCCESS: Breakout Open triggered!")
            
            # 3. Check Sizing
            # Mock base risk manager to return 1.5% base risk
            with patch('strategies.workers.base_worker_logic.BaseWorkerLogic.calculate_adaptive_risk', return_value=0.015):
                final_risk = worker.calculate_adaptive_risk(opportunity)
                stop_loss = opportunity.get('stop_loss')
                
                self.logger.info(f"📐 Sizing Check: Final Risk={final_risk*100:.2f}% (Expected 1.50%)")
                self.logger.info(f"🛡️ Protection Check: Stop Loss=${stop_loss:.2f} (Expected $9.90)")
                
                if final_risk == 0.015 and abs(stop_loss - 9.90) < 0.01:
                    self.logger.info("✅ DAY 1 SIZING SUCCESS: Correct risk and stop loss applied")
                else:
                    self.logger.error(f"❌ DAY 1 SIZING FAILURE: Risk={final_risk}, Stop={stop_loss}")
                    sys.exit(1)
        else:
            self.logger.error(f"❌ DAY 1 DETECTION FAILURE: Setup not triggered correctly")
            sys.exit(1)

if __name__ == "__main__":
    backtester = ModularBacktest()
    asyncio.run(backtester.run())
