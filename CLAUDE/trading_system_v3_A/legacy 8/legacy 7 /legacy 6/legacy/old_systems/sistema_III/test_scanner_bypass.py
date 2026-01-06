#!/usr/bin/env python3
"""
Test Scanner Bypass
Creates a scanner that bypasses IBKR problematic scanners
and sends test opportunities directly to test Redis communication
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.service_locator import get_config
from shared.message_bus import MessageBus

class BypassScanner:
    """Scanner that bypasses IBKR and generates test opportunities"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("BypassScanner")
        self.config = get_config()

        # Use MessageBus like real scanner
        self.bridge = MessageBus()

        # Control
        self.is_running = False
        self.shutdown_requested = False
        self.cycle_count = 0

    async def initialize(self):
        """Initialize bypass scanner"""
        try:
            # Connect to Redis
            bridge_connected = await self.bridge.connect()
            if not bridge_connected:
                self.logger.error("❌ Redis connection failed")
                return False

            self.logger.info("✅ Bypass scanner connected to Redis")
            return True

        except Exception as e:
            self.logger.error(f"❌ Bypass scanner initialization failed: {e}")
            return False

    async def start(self):
        """Start bypass scanner loop"""
        if not await self.initialize():
            return False

        self.logger.info("🚀 Starting bypass scanner (no IBKR hangs)...")
        self.is_running = True

        # Main scanner loop - EXACTLY like real scanner
        while self.is_running and not self.shutdown_requested:
            try:
                self.logger.info("🔍 Starting scan cycle...")

                # Generate test opportunities (bypass IBKR completely)
                opportunities = await self._generate_test_opportunities()

                if opportunities:
                    # Publish to Redis with timeout
                    try:
                        await asyncio.wait_for(
                            self.bridge.publish_opportunities(opportunities),
                            timeout=10.0
                        )
                        self.logger.info(f"📡 Published {len(opportunities)} opportunities to coordinator")
                    except asyncio.TimeoutError:
                        self.logger.error("❌ Redis publish timeout")
                else:
                    self.logger.info("📭 No opportunities found in this cycle")

                # Wait before next scan (same as real scanner)
                scan_interval = 30
                self.logger.info(f"⏱️ Waiting {scan_interval}s until next scan...")
                await asyncio.sleep(scan_interval)

                self.cycle_count += 1

                # Stop after 10 cycles to test if it can run continuously
                if self.cycle_count >= 10:
                    self.logger.info("🏁 Completed 10 cycles - scanner working continuously!")
                    break

            except Exception as e:
                self.logger.error(f"❌ Error in scanner cycle: {e}")
                await asyncio.sleep(30)

        await self.stop()
        self.logger.info("🛑 Bypass scanner stopped")
        return True

    async def _generate_test_opportunities(self) -> List[Dict]:
        """Generate realistic test opportunities without IBKR"""
        try:
            # Simulate realistic opportunities
            test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX']
            opportunity_types = ['GAP_GO', 'DAILY_PLAYS', 'MACDV', 'BULL_FLAG']

            opportunities = []

            # Generate 2-5 opportunities per cycle
            import random
            num_opportunities = random.randint(2, 5)

            for i in range(num_opportunities):
                symbol = random.choice(test_symbols)
                opp_type = random.choice(opportunity_types)

                opportunity = {
                    'symbol': f"{symbol}_CYCLE_{self.cycle_count}",
                    'opportunity_type': opp_type,
                    'quality_score': random.uniform(70.0, 95.0),
                    'strategy_targets': {
                        'entry': random.uniform(100.0, 200.0),
                        'stop': random.uniform(90.0, 110.0),
                        'target': random.uniform(150.0, 250.0)
                    },
                    'catalyst_type': random.choice(['TECHNICAL', 'NEWS', 'EARNINGS']),
                    'catalyst_strength': random.uniform(0.5, 1.0),
                    'current_price': random.uniform(100.0, 200.0),
                    'gap_percentage': random.uniform(1.0, 8.0),
                    'volume_ratio': random.uniform(1.5, 5.0),
                    'trading_recommendation': random.choice(['BUY', 'HOLD', 'WATCH']),
                    'scan_timestamp': datetime.now().isoformat(),
                    'ibkr_rank': i + 1,
                    'news_count': random.randint(0, 5),
                    'sentiment_score': random.uniform(0.0, 1.0),
                    'test_cycle': self.cycle_count,
                    'test_source': 'bypass_scanner'
                }
                opportunities.append(opportunity)

            self.logger.info(f"🎯 Generated {len(opportunities)} test opportunities")
            return opportunities

        except Exception as e:
            self.logger.error(f"❌ Error generating opportunities: {e}")
            return []

    async def stop(self):
        """Stop bypass scanner"""
        try:
            self.is_running = False
            self.shutdown_requested = True

            # Disconnect from Redis
            await self.bridge.disconnect()
            self.logger.info("✅ Bypass scanner disconnected")

        except Exception as e:
            self.logger.error(f"❌ Error stopping bypass scanner: {e}")

class CoordinatorTester:
    """Test if coordinator receives opportunities from bypass scanner"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("CoordinatorTester")
        self.config = get_config()

        # Use MessageBus like real coordinator
        self.message_bus = MessageBus()

        # Track received opportunities
        self.opportunities_received = []
        self.is_running = False

    async def start_listening(self):
        """Start listening for opportunities like real coordinator"""
        try:
            # Connect to Redis
            connected = await self.message_bus.connect()
            if not connected:
                self.logger.error("❌ Coordinator tester connection failed")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._handle_opportunity)
            self.logger.info("✅ Coordinator tester listening for opportunities...")

            self.is_running = True

            # Listen for 6 minutes (enough for 10+ scanner cycles)
            await asyncio.sleep(360)

            self.logger.info(f"📊 Test completed: Received {len(self.opportunities_received)} opportunities")

            return len(self.opportunities_received) > 0

        except Exception as e:
            self.logger.error(f"❌ Coordinator tester error: {e}")
            return False
        finally:
            await self.message_bus.disconnect()

    async def _handle_opportunity(self, opportunity: Dict):
        """Handle received opportunity"""
        try:
            self.opportunities_received.append(opportunity)
            symbol = opportunity.get('symbol', 'UNKNOWN')
            strategy = opportunity.get('opportunity_type', 'UNKNOWN')
            cycle = opportunity.get('test_cycle', 'N/A')

            self.logger.info(f"🎯 Coordinator received: {symbol} ({strategy}) - Cycle {cycle}")

        except Exception as e:
            self.logger.error(f"❌ Error handling opportunity: {e}")

async def run_bypass_test():
    """Run the complete bypass test"""
    print("🧪 SCANNER BYPASS TEST")
    print("   🔄 Bypasses problematic IBKR scanners")
    print("   📡 Tests pure Redis communication")
    print("   ⏱️ Runs for 6 minutes to test continuity")
    print()

    # Create scanner and coordinator tester
    scanner = BypassScanner()
    coordinator = CoordinatorTester()

    try:
        # Start both concurrently
        scanner_task = asyncio.create_task(scanner.start())
        coordinator_task = asyncio.create_task(coordinator.start_listening())

        # Wait for both to complete
        scanner_result, coordinator_result = await asyncio.gather(
            scanner_task, coordinator_task, return_exceptions=True
        )

        print(f"\n📊 BYPASS TEST RESULTS:")
        print(f"   Scanner result: {'✅ SUCCESS' if scanner_result else '❌ FAILED'}")
        print(f"   Coordinator result: {'✅ SUCCESS' if coordinator_result else '❌ FAILED'}")
        print(f"   Opportunities received: {len(coordinator.opportunities_received)}")

        if scanner_result and coordinator_result and len(coordinator.opportunities_received) > 0:
            print("✅ BYPASS TEST PASSED - Redis communication works without IBKR hangs")
            return 0
        else:
            print("❌ BYPASS TEST FAILED - Issue not related to IBKR scanners")
            return 1

    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        await scanner.stop()
        return 0
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_bypass_test())
    sys.exit(exit_code)