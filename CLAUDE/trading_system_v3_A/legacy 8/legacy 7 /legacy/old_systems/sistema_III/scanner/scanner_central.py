#!/usr/bin/env python3
"""
Independent Scanner Process
Finds opportunities and publishes them via Redis pub/sub to trader
"""

import asyncio
import logging
import signal
import sys
import os
from typing import List, Dict, Any
from datetime import datetime
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.service_locator import get_config
from core.scanner_trader_bridge import ScannerTraderBridge
from adapters.ibkr_adapter import IBKRAdapter
# Use local copy of working scanner (no path absoluto)
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from scanner.original_scanners.daily_bounce.daily_bounce_scanner import DailyBounceScanner
from scanner.original_scanners.red_to_green.red_to_green_scanner import RedToGreenScanner
from utils.log_config import setup_logging
# Removed complex classifier - using simple approach like original scanner

class IndependentScanner:
    """
    Independent scanner process - runs separately from trader
    """

    def __init__(self):
        setup_logging(level="INFO", log_file="logs/scanner.log")
        self.logger = logging.getLogger("Scanner")

        # Load config
        self.config = get_config()

        # Scanner components
        self.scanner_ibkr = None
        self.scanner = None
        self.daily_bounce_scanner = None
        self.red_to_green_scanner = None
        self.bridge = ScannerTraderBridge()

# Removed complex classifier - using simple approach like original scanner

        # Scheduling control for daily vs intraday scanning
        self.last_daily_scan = None
        self.daily_scan_hour = 6  # 6 AM daily scan time

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info("🔍 Independent Scanner Process initialized")

    async def initialize(self):
        """Initialize scanner with separate IBKR connection"""
        try:
            # Connect to Redis bridge
            bridge_connected = await self.bridge.connect()
            if not bridge_connected:
                self.logger.error("❌ Redis connection failed - scanner cannot publish opportunities")
                return False

            # Create separate IBKR connection for scanner
            scanner_client_id = self.config.getint('IBKR', 'client_id_scanner', fallback=101)
            self.scanner_ibkr = IBKRAdapter(
                host=self.config.get('IBKR', 'host', fallback='127.0.0.1'),
                port=self.config.getint('IBKR', 'port', fallback=7497),
                client_id=scanner_client_id
            )

            await self.scanner_ibkr.connect()
            self.logger.info(f"✅ Scanner IBKR connected (client_id: {scanner_client_id})")

            # Initialize local SmallcapDailyScanner (copy of working one)
            self.scanner = SmallcapDailyScanner(ibkr_adapter=self.scanner_ibkr)
            self.logger.info("✅ SmallcapDailyScanner (local copy) initialized")

            # Initialize daily bounce scanner (shares same IBKR connection)
            self.daily_bounce_scanner = DailyBounceScanner(ibkr_adapter=self.scanner_ibkr, logger=self.logger)
            self.logger.info("✅ DailyBounceScanner initialized")

            # Initialize red to green scanner (shares same IBKR connection)
            self.red_to_green_scanner = RedToGreenScanner(ibkr_adapter=self.scanner_ibkr, logger=self.logger)
            self.logger.info("✅ RedToGreenScanner initialized")

            return True

        except Exception as e:
            self.logger.error(f"❌ Scanner initialization failed: {e}")
            return False

    async def start(self):
        """Start independent scanner loop"""
        if not await self.initialize():
            return False

        self.logger.info("🚀 Starting independent scanner process...")
        self.is_running = True

        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.error(f"📡 Signal {signum} received - shutting down scanner")
            self.logger.error(f"🔍 DEBUG: Signal source: {frame.f_code.co_filename}:{frame.f_lineno}")
            import traceback
            traceback.print_stack(frame)
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main scanner loop
        while self.is_running and not self.shutdown_requested:
            try:
                self.logger.info("🔍 Starting scan cycle...")
                self.logger.error(f"🔍 DEBUG: Loop conditions - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

                # Find opportunities with TIMEOUT to prevent hanging
                try:
                    opportunities = await asyncio.wait_for(
                        self._scan_for_opportunities(),
                        timeout=300.0  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    self.logger.error("❌ Scanner timeout after 5 minutes - continuing to next cycle")
                    opportunities = []

                if opportunities:
                    # Publish to Redis with timeout
                    try:
                        await asyncio.wait_for(
                            self.bridge.publish_opportunities(opportunities),
                            timeout=10.0  # 10 second timeout
                        )
                        self.logger.info(f"📡 Published {len(opportunities)} opportunities to trader")
                    except asyncio.TimeoutError:
                        self.logger.error("❌ Redis publish timeout - continuing")
                else:
                    self.logger.info("📭 No opportunities found in this cycle")

                # Wait before next scan
                scan_interval = getattr(self.config, 'scan_interval_seconds', 30)
                self.logger.info(f"⏱️ Waiting {scan_interval}s until next scan...")
                self.logger.debug(f"🔍 DEBUG: About to sleep for {scan_interval}s - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")
                await asyncio.sleep(scan_interval)
                self.logger.debug(f"🔍 DEBUG: Woke up from sleep - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

            except Exception as e:
                self.logger.error(f"❌ Error in scanner cycle: {e}")
                import traceback
                self.logger.error(f"🔍 Exception traceback: {traceback.format_exc()}")
                await asyncio.sleep(30)  # Emergency wait

        # DEBUG: Why did we exit the loop?
        self.logger.error(f"🔍 DEBUG: Exited scanner loop - is_running: {self.is_running}, shutdown_requested: {self.shutdown_requested}")

        await self.stop()
        self.logger.info("🛑 Scanner process stopped")
        return True

    async def _scan_for_opportunities(self) -> List[Dict[str, Any]]:
        """Scan for opportunities using UNIFIED scanner (intraday + daily)"""
        try:
            all_opportunities = []

            # 1. INTRADAY SCANNING (every cycle)
            self.logger.info("🔍 Starting intraday IBKR scanning...")
            intraday_plays = await self.scanner.scan_daily_plays()

            if intraday_plays:
                self.logger.info(f"📊 Intraday scanner found {len(intraday_plays)} plays")

                # Convert to opportunities with CORRECT types that workers expect
                for play in intraday_plays:
                    # Classify opportunity type based on context
                    gap_pct = getattr(play.context, 'gap_percentage', 0.0)
                    volume_ratio = getattr(play.context, 'premarket_volume_ratio', 0.0)
                    quality_score = play.quality_score

                    # Simple classification logic for worker types
                    if gap_pct >= 2.0:
                        opportunity_type = 'GAP_GO'
                    elif quality_score >= 75.0:
                        opportunity_type = 'DAILY_PLAYS'
                    elif volume_ratio >= 3.0:
                        opportunity_type = 'BULL_FLAG'
                    else:
                        opportunity_type = 'MACDV'

                    opportunity = {
                        'symbol': play.symbol,
                        'opportunity_type': opportunity_type,  # Use worker-compatible types
                        'quality_score': quality_score,
                        'strategy_targets': play.strategy_targets,
                        'catalyst_type': play.catalyst.catalyst_type if play.catalyst and hasattr(play.catalyst, 'catalyst_type') else 'TECHNICAL',
                        'catalyst_strength': play.catalyst.strength if play.catalyst and hasattr(play.catalyst, 'strength') else 0.0,
                        'current_price': getattr(play.context, 'current_price', 0.0),
                        'gap_percentage': gap_pct,
                        'volume_ratio': volume_ratio,
                        'trading_recommendation': play.trading_recommendation,
                        'scan_timestamp': datetime.now().isoformat(),
                        'ibkr_rank': play.ibkr_rank,
                        'news_count': len(play.catalyst.news_headlines) if play.catalyst and hasattr(play.catalyst, 'news_headlines') else 0,
                        'sentiment_score': getattr(play.catalyst, 'sentiment_score', 0.0) if play.catalyst else 0.0
                    }
                    all_opportunities.append(opportunity)
                    self.logger.info(f"📊 {play.symbol}: Classified as {opportunity_type} (gap: {gap_pct:.1f}%, quality: {quality_score:.1f})")

            # 2. SIMPLIFIED: Skip complex scanner analysis - let workers handle strategy-specific logic
            self.logger.info("📭 Skipping complex bounce/R2G scanning - workers will handle strategy analysis")

            # 3. SUMMARY AND RETURN
            if not all_opportunities:
                self.logger.info("📭 No opportunities found in unified scan")
                return []

            # Log summary by opportunity type (simple approach like original)
            type_counts = {}
            for opp in all_opportunities:
                opp_type = opp['opportunity_type']
                type_counts[opp_type] = type_counts.get(opp_type, 0) + 1

            type_summary = ', '.join([f"{t}: {c}" for t, c in type_counts.items()])
            self.logger.info(f"🎯 Unified scan: {len(all_opportunities)} opportunities - {type_summary}")

            return all_opportunities

        except Exception as e:
            self.logger.error(f"❌ Error in unified scanning: {e}")
            # Emergency fallback
            return [
                {
                    'symbol': 'EMERGENCY',
                    'opportunity_type': 'INTRADAY_MOMENTUM',
                    'quality_score': 50.0,
                    'catalyst_type': 'ERROR_FALLBACK',
                    'catalyst_strength': 0.5,
                    'current_price': 10.0,
                    'gap_percentage': 5.0,
                    'volume_ratio': 1.5,
                    'trading_recommendation': 'HOLD',
                    'scan_timestamp': datetime.now().isoformat(),
                    'ibkr_rank': 1,
                    'news_count': 0,
                    'sentiment_score': 0.0
                }
            ]

    def _should_run_daily_scan(self) -> bool:
        """Determine if daily bounce scan should run"""
        try:
            now = datetime.now()

            # Run daily scan at 6 AM or if never run before
            if self.last_daily_scan is None:
                return True

            # Check if it's past daily scan time and we haven't run today
            last_scan_date = self.last_daily_scan.date()
            current_date = now.date()

            if current_date > last_scan_date and now.hour >= self.daily_scan_hour:
                return True

            # For testing: run every 2 hours during market hours
            time_since_last = now - self.last_daily_scan
            if time_since_last.total_seconds() > 7200:  # 2 hours
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking daily scan schedule: {e}")
            return False

    async def stop(self):
        """Stop scanner process"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            # Disconnect IBKR
            if self.scanner_ibkr:
                await self.scanner_ibkr.disconnect()
                self.logger.info("✅ Scanner IBKR disconnected")

            # Disconnect bridge
            await self.bridge.disconnect()
            self.logger.info("✅ Redis bridge disconnected")

        except Exception as e:
            self.logger.error(f"❌ Error stopping scanner: {e}")

async def main():
    """Main function for independent scanner"""
    scanner = IndependentScanner()

    print("🔍 INDEPENDENT SCANNER PROCESS")
    print("   ✅ Separate IBKR connection")
    print("   ✅ Redis pub/sub communication")
    print("   ✅ Independent of trader")
    print()

    try:
        success = await scanner.start()
        scanner.logger.error(f"🔍 DEBUG: scanner.start() returned {success}")
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n🛑 Scanner interrupted by user")
        scanner.logger.error("🔍 DEBUG: KeyboardInterrupt in main()")
        await scanner.stop()
        return 0
    except Exception as e:
        print(f"❌ Scanner failed: {e}")
        scanner.logger.error(f"🔍 DEBUG: Exception in main(): {e}")
        import traceback
        scanner.logger.error(f"🔍 DEBUG: Main exception traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)