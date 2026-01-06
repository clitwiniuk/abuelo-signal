#!/usr/bin/env python3
"""
Sistema_4 Independent Scanner Process
Clean version without external system dependencies
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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared.config_reader import Sistema4Config
from shared.message_bus import MessageBus
from adapters.ibkr_adapter_clean import IBKRAdapterClean
from utils.log_config import setup_logging
from notifications import telegram_client

class Sistema4Scanner:
    """
    Clean Sistema_4 scanner - independent of other systems
    """

    def __init__(self):
        setup_logging(level="INFO", log_file="logs/scanner.log")
        self.logger = logging.getLogger("Sistema4Scanner")

        # Load config
        self.config = Sistema4Config()

        # Scanner components
        self.ibkr_adapter = None
        self.native_scanner = None
        self.message_bus = MessageBus()

        # Control
        self.is_running = False
        self.shutdown_requested = False

        self.logger.info("🔍 Sistema_4 Scanner initialized")

    async def initialize(self):
        """Initialize scanner components"""
        try:
            # Connect to message bus
            if not await self.message_bus.connect():
                self.logger.error("❌ Redis connection failed")
                return False

            # Create IBKR connection
            ibkr_config = self.config.get_ibkr_config()
            self.ibkr_adapter = IBKRAdapterClean(
                host=ibkr_config['host'],
                port=ibkr_config['port'],
                client_id=ibkr_config['client_id_scanner']
            )

            if not await self.ibkr_adapter.connect():
                self.logger.error("❌ IBKR connection failed")
                return False

            self.logger.info(f"✅ Scanner initialized with IBKR (client_id: {ibkr_config['client_id_scanner']})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Scanner initialization failed: {e}")
            return False

    async def start(self):
        """Start scanner process"""
        if not await self.initialize():
            return False

        self.logger.info("🚀 Starting Sistema_4 scanner...")
        self.is_running = True

        # Setup signal handlers
        def signal_handler(signum, frame):
            self.logger.info(f"📡 Signal {signum} received - shutting down scanner")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main scanner loop
        while self.is_running and not self.shutdown_requested:
            try:
                # Find opportunities
                opportunities = await self._scan_for_opportunities()

                if opportunities:
                    # Publish to Redis for workers
                    await self.message_bus.publish_opportunities(opportunities)
                    self.logger.info(f"📡 Published {len(opportunities)} opportunities")

                    # Send Telegram notifications for high-quality opportunities
                    try:
                        for opportunity in opportunities:
                            if opportunity.get('quality_score', 0) >= 7.0:
                                telegram_client.notify_opportunity_detected(
                                    symbol=opportunity['symbol'],
                                    opportunity_type=opportunity['opportunity_type'],
                                    details=opportunity
                                )
                    except Exception as e:
                        self.logger.debug(f"Telegram notification error: {e}")
                else:
                    self.logger.debug("📭 No opportunities found")

                # Wait before next scan
                scan_interval = getattr(self.config, 'scan_interval_seconds', 30)
                await asyncio.sleep(scan_interval)

            except Exception as e:
                self.logger.error(f"❌ Error in scanner cycle: {e}")
                await asyncio.sleep(30)  # Emergency wait

        await self.stop()
        self.logger.info("🛑 Scanner stopped")
        return True

    async def _scan_for_opportunities(self) -> List[Dict[str, Any]]:
        """Scan for trading opportunities using simplified approach"""
        try:
            opportunities = []

            # Get volume surge movers from IBKR
            volume_movers = await self._get_volume_surge_movers()

            if volume_movers:
                self.logger.info(f"📊 Found {len(volume_movers)} volume surge movers")

                for mover in volume_movers:
                    # Create opportunity from volume surge data
                    opportunity = {
                        'symbol': mover['symbol'],
                        'opportunity_type': 'VOLUME_SURGE',
                        'quality_score': self._calculate_quality_score(mover),
                        'current_price': mover.get('price', 0.0),
                        'volume_ratio': mover.get('volume_ratio', 1.0),
                        'percent_change': mover.get('percent_change', 0.0),
                        'trading_recommendation': self._get_trading_recommendation(mover),
                        'scan_timestamp': datetime.now().isoformat(),
                        'volume': mover.get('volume', 0)
                    }

                    # Only include opportunities with minimum quality
                    if opportunity['quality_score'] >= 5.0:
                        opportunities.append(opportunity)

            self.logger.info(f"🎯 Generated {len(opportunities)} opportunities")
            return opportunities

        except Exception as e:
            self.logger.error(f"❌ Error scanning for opportunities: {e}")
            return []

    async def _get_volume_surge_movers(self) -> List[Dict[str, Any]]:
        """Get volume surge movers from IBKR with improved error handling"""
        try:
            if not self.ibkr_adapter or not self.ibkr_adapter.is_connected:
                self.logger.debug("❌ IBKR adapter not connected")
                return []

            # Try to get data from IBKR scanner, handling Error 162 gracefully
            scan_results = await self.ibkr_adapter.run_scanner({
                'instrument': 'STK',
                'location_code': 'STK.US.MAJOR',
                'scan_code': 'TOP_VOLUME_RATE',
                'number_of_rows': 20,
                'above_price': 0.5,
                'above_volume': 100000,
                'market_cap_below': 2000000000,
                'stock_type': 'ALL'
            })

            if scan_results:
                self.logger.info(f"📊 IBKR scanner found {len(scan_results)} results")

                movers = []
                for result in scan_results:
                    # Get additional market data for each symbol
                    price = await self.ibkr_adapter.get_current_price(result.get('symbol', ''))

                    mover = {
                        'symbol': result.get('symbol', ''),
                        'price': price if price > 0 else result.get('price', 0.0),
                        'volume_ratio': result.get('volume_ratio', 1.0),
                        'percent_change': result.get('percent_change', 0.0),
                        'volume': result.get('volume', 0)
                    }

                    if mover['symbol'] and mover['price'] > 1.0:  # Basic filters
                        movers.append(mover)

                return movers
            else:
                self.logger.debug("📭 IBKR scanner returned no results (Error 162 is normal)")
                return []

        except Exception as e:
            self.logger.debug(f"IBKR scanner error (normal): {e}")
            return []

    def _calculate_quality_score(self, mover: Dict[str, Any]) -> float:
        """Calculate quality score for opportunity"""
        try:
            score = 5.0  # Base score

            # Volume factor
            volume_ratio = mover.get('volume_ratio', 1.0)
            if volume_ratio > 3.0:
                score += 2.0
            elif volume_ratio > 2.0:
                score += 1.0

            # Price change factor
            percent_change = abs(mover.get('percent_change', 0.0))
            if percent_change > 10.0:
                score += 2.0
            elif percent_change > 5.0:
                score += 1.0

            # Price range filter
            price = mover.get('price', 0.0)
            if 2.0 <= price <= 50.0:
                score += 1.0

            return min(score, 10.0)  # Cap at 10

        except Exception as e:
            self.logger.error(f"Error calculating quality score: {e}")
            return 5.0

    def _get_trading_recommendation(self, mover: Dict[str, Any]) -> str:
        """Get basic trading recommendation"""
        try:
            percent_change = mover.get('percent_change', 0.0)
            volume_ratio = mover.get('volume_ratio', 1.0)

            if percent_change > 5.0 and volume_ratio > 2.0:
                return "STRONG_BUY"
            elif percent_change > 2.0 and volume_ratio > 1.5:
                return "BUY"
            elif percent_change < -5.0 and volume_ratio > 2.0:
                return "SHORT"
            else:
                return "WATCH"

        except Exception as e:
            self.logger.error(f"Error getting recommendation: {e}")
            return "WATCH"

    async def stop(self):
        """Stop scanner"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            if self.ibkr_adapter:
                await self.ibkr_adapter.disconnect()
                self.logger.info("✅ IBKR disconnected")

            if self.message_bus:
                await self.message_bus.disconnect()
                self.logger.info("✅ Message bus disconnected")

        except Exception as e:
            self.logger.error(f"❌ Error stopping scanner: {e}")

async def main():
    """Main function for scanner"""
    scanner = Sistema4Scanner()

    print("🔍 SISTEMA_4 CLEAN SCANNER")
    print("   ✅ Independent of other systems")
    print("   ✅ Redis pub/sub communication")
    print("   ✅ Clean IBKR integration")
    print()

    try:
        success = await scanner.start()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n🛑 Scanner interrupted by user")
        await scanner.stop()
        return 0
    except Exception as e:
        print(f"❌ Scanner failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)