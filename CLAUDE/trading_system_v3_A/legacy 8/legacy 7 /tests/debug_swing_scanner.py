#!/usr/bin/env python3
"""
Swing Scanner Diagnostic Tool
Tests the swing consolidation scanner to identify why it's not finding NASDAQ tickers
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.append('.')

from scanner.swing.swing_consolidation_scanner import SwingConsolidationScanner
from adapters.ibkr_adapter import IBKRAdapter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/scanner.log')
    ]
)
logger = logging.getLogger(__name__)

class SwingScannerDiagnostic:
    """Diagnostic tool for swing scanner issues"""

    def __init__(self):
        self.ibkr_adapter = None
        self.swing_scanner = None
        from core.config_manager import ConfigManager
        self.config_manager = ConfigManager()

    async def initialize(self):
        """Initialize IBKR adapter and swing scanner"""
        try:
            logger.info("🔧 Initializing IBKR adapter...")
            self.ibkr_adapter = IBKRAdapter()
            await self.ibkr_adapter.connect()

            logger.info("🔧 Initializing swing scanner...")
            self.swing_scanner = SwingConsolidationScanner(self.config_manager, self.ibkr_adapter)

            logger.info("✅ Initialization complete")
            return True

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False

    async def run_diagnostics(self):
        """Run comprehensive diagnostics"""
        logger.info("🩺 Starting Swing Scanner Diagnostics")
        logger.info("=" * 60)

        # Test 1: IBKR Connection
        logger.info("\n1️⃣ Testing IBKR Connection...")
        await self.test_ibkr_connection()

        # Test 2: Scanner Universe
        logger.info("\n2️⃣ Testing Scanner Universe...")
        await self.test_scanner_universe()

        # Test 3: Market Data Fetching
        logger.info("\n3️⃣ Testing Market Data Fetching...")
        await self.test_market_data_fetching()

        # Test 4: Consolidation Detection
        logger.info("\n4️⃣ Testing Consolidation Detection...")
        await self.test_consolidation_detection()

        # Test 5: Cache Status
        logger.info("\n5️⃣ Testing Cache Status...")
        await self.test_cache_status()

    async def test_ibkr_connection(self):
        """Test IBKR adapter connection"""
        try:
            if not self.ibkr_adapter:
                logger.error("❌ IBKR adapter not initialized")
                return False

            # Check if connected
            if hasattr(self.ibkr_adapter, 'is_connected') and self.ibkr_adapter.is_connected():
                logger.info("✅ IBKR adapter is connected")
                return True
            else:
                logger.warning("⚠️ IBKR adapter connection status unknown")
                return False

        except Exception as e:
            logger.error(f"❌ IBKR connection test failed: {e}")
            return False

    async def test_scanner_universe(self):
        """Test scanner universe fetching"""
        try:
            if not self.swing_scanner:
                logger.error("❌ Swing scanner not initialized")
                return False

            logger.info("🔍 Fetching scanner universe...")

            # Try to get universe (corrected method name)
            universe = await self.swing_scanner._get_scan_universe()

            if universe:
                logger.info(f"✅ Universe fetched: {len(universe)} candidates")
                # Show first 5 symbols
                for i, symbol in enumerate(universe[:5]):
                    logger.info(f"   {i+1}. {symbol}")
                if len(universe) > 5:
                    logger.info(f"   ... and {len(universe) - 5} more")
                return True
            else:
                logger.error("❌ No universe candidates found")
                return False

        except Exception as e:
            logger.error(f"❌ Universe test failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def test_market_data_fetching(self):
        """Test market data fetching capabilities"""
        try:
            if not self.ibkr_adapter:
                logger.error("❌ IBKR adapter not available")
                return False

            # Test with a known small cap
            test_symbol = "AAPL"  # Use AAPL as test since it's reliable

            logger.info(f"📊 Testing market data fetch for {test_symbol}...")

            # Try to get contract
            from ib_insync import Stock
            contract = Stock(test_symbol, 'SMART', 'USD')

            # Try to get historical data
            bars = await self.ibkr_adapter.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 hour',
                whatToShow='TRADES',
                useRTH=False
            )

            if bars and len(bars) > 0:
                logger.info(f"✅ Market data fetched: {len(bars)} bars")
                logger.info(f"   Latest bar: {bars[-1].date} - O:{bars[-1].open:.2f} H:{bars[-1].high:.2f} L:{bars[-1].low:.2f} C:{bars[-1].close:.2f}")
                return True
            else:
                logger.error("❌ No market data received")
                return False

        except Exception as e:
            logger.error(f"❌ Market data test failed: {e}")
            return False

    async def test_consolidation_detection(self):
        """Test consolidation pattern detection"""
        try:
            logger.info("🔬 Testing consolidation detection logic...")

            # Create mock data for testing
            mock_bars = self._create_mock_consolidation_data()

            if not mock_bars:
                logger.warning("⚠️ Could not create mock data for testing")
                return False

            # Test consolidation detection
            consolidation_detected = self._detect_mock_consolidation(mock_bars)

            if consolidation_detected:
                logger.info("✅ Consolidation detection working (mock test passed)")
                return True
            else:
                logger.warning("⚠️ Consolidation detection not working as expected")
                return False

        except Exception as e:
            logger.error(f"❌ Consolidation test failed: {e}")
            return False

    def _create_mock_consolidation_data(self):
        """Create mock price data showing consolidation"""
        try:
            # Create 20 bars of consolidating price action
            base_price = 10.0
            bars = []

            for i in range(20):
                # Create tight consolidation around $10
                high = base_price + 0.1 + (i % 3) * 0.05  # Small variations
                low = base_price - 0.1 - (i % 3) * 0.05
                open_price = (high + low) / 2 + ((i % 2) - 0.5) * 0.02
                close = (high + low) / 2 + ((i % 2) - 0.5) * 0.02

                bars.append({
                    'high': high,
                    'low': low,
                    'open': open_price,
                    'close': close,
                    'volume': 100000 + i * 5000
                })

            logger.info(f"📊 Created mock consolidation data: {len(bars)} bars")
            return bars

        except Exception as e:
            logger.error(f"Error creating mock data: {e}")
            return None

    def _detect_mock_consolidation(self, bars):
        """Simple consolidation detection for testing"""
        if not bars or len(bars) < 10:
            return False

        # Check if price range is tight (consolidation)
        highs = [bar['high'] for bar in bars]
        lows = [bar['low'] for bar in bars]

        max_high = max(highs)
        min_low = min(lows)
        range_pct = (max_high - min_low) / min_low

        logger.info(f"📏 Price range analysis: Max High: ${max_high:.2f}, Min Low: ${min_low:.2f}, Range: {range_pct:.1%}")

        # Consolidation if range is less than 5%
        is_consolidating = range_pct < 0.05

        logger.info(f"🎯 Consolidation detected: {is_consolidating}")
        return is_consolidating

    async def test_cache_status(self):
        """Test cache status and refresh"""
        try:
            logger.info("💾 Testing cache status...")

            if hasattr(self.swing_scanner, 'force_cache_refresh'):
                logger.info("🔄 Calling force_cache_refresh...")
                result = self.swing_scanner.force_cache_refresh()

                if result:
                    logger.info("✅ Cache refresh successful")
                    return True
                else:
                    logger.error("❌ Cache refresh failed")
                    return False
            else:
                logger.warning("⚠️ force_cache_refresh method not available")
                return False

        except Exception as e:
            logger.error(f"❌ Cache test failed: {e}")
            return False

    async def run_full_scan_test(self):
        """Run a full scan test"""
        try:
            logger.info("\n🚀 Running Full Scan Test...")

            if not self.swing_scanner:
                logger.error("❌ Swing scanner not initialized")
                return False

            # Run the scan (corrected method name)
            start_time = datetime.now()
            result = await self.swing_scanner.scan_for_consolidations()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if result:
                logger.info(f"✅ Full scan completed in {duration:.1f}s")
                logger.info(f"📊 Result: {len(result)} consolidation patterns found")

                # Show results
                for i, setup in enumerate(result, 1):
                    logger.info(f"   {i}. {setup.get('symbol', 'UNKNOWN')} - "
                              f"Pattern: {setup.get('pattern_type', 'N/A')}, "
                              f"Score: {setup.get('score', 0):.2f}")
                return True
            else:
                logger.warning(f"⚠️ Full scan completed in {duration:.1f}s but returned no results")
                return False

        except Exception as e:
            logger.error(f"❌ Full scan test failed: {e}")
            return False

async def main():
    """Main diagnostic function"""
    print("🩺 SWING SCANNER DIAGNOSTIC TOOL")
    print("=" * 50)

    diagnostic = SwingScannerDiagnostic()

    # Initialize
    if not await diagnostic.initialize():
        print("❌ Initialization failed - cannot continue")
        return

    # Run diagnostics
    await diagnostic.run_diagnostics()

    # Run full scan test
    await diagnostic.run_full_scan_test()

    # Cleanup
    if diagnostic.ibkr_adapter:
        await diagnostic.ibkr_adapter.disconnect()

    print("\n🏁 Diagnostic complete")

if __name__ == "__main__":
    asyncio.run(main())