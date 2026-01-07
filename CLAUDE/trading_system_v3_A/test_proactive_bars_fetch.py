#!/usr/bin/env python3
"""
Test script to validate proactive monitor bars fetching fix
Tests that _fetch_intraday_bars() works correctly for active candidates
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from core.execution_engine_adapter import ExecutionEngine
from core.risk_manager import RiskManager
from adapters.ibkr_adapter import IBKRAdapter
import configparser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProactiveBarsTest")

async def test_bars_fetch():
    """Test that we can fetch bars for proactive candidates"""

    # Load config
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Initialize components
    logger.info("Initializing IBKR connection...")
    ibkr = IBKRAdapter(config)
    await ibkr.initialize()

    risk_manager = RiskManager(config)
    execution_engine = ExecutionEngine(ibkr, risk_manager, config)

    # Create worker
    logger.info("Creating short_squeeze worker...")
    worker = ShortSqueezeWorkerLogic(execution_engine, risk_manager, config)

    # Test symbols from active proactive candidates
    test_symbols = ['AZI', 'ZNTL', 'LVRO', 'PRZO']

    logger.info(f"\n{'='*60}")
    logger.info("Testing bars fetch for proactive candidates")
    logger.info(f"{'='*60}\n")

    for symbol in test_symbols:
        logger.info(f"\n--- Testing {symbol} ---")

        try:
            # Test _fetch_intraday_bars method
            bars = await worker._fetch_intraday_bars(symbol)

            if bars:
                logger.info(f"✅ {symbol}: Successfully fetched {len(bars)} bars")
                if len(bars) > 0:
                    first_bar = bars[0]
                    last_bar = bars[-1]
                    logger.info(f"   First bar: {first_bar.get('timestamp')} - Close: ${first_bar.get('close', 0):.2f}")
                    logger.info(f"   Last bar:  {last_bar.get('timestamp')} - Close: ${last_bar.get('close', 0):.2f}")
            else:
                logger.warning(f"⚠️ {symbol}: No bars returned (IBKR may not have data)")

        except Exception as e:
            logger.error(f"❌ {symbol}: Error fetching bars: {e}")

    logger.info(f"\n{'='*60}")
    logger.info("Test completed")
    logger.info(f"{'='*60}\n")

    # Cleanup
    await ibkr.cleanup()

if __name__ == "__main__":
    logger.info("🧪 Starting Proactive Bars Fetch Test\n")
    asyncio.run(test_bars_fetch())
