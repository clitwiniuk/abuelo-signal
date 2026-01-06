#!/usr/bin/env python3
"""
Test Exact Sistema III Flow
Simulates the EXACT same flow as scanner_central.py + main.py
to identify why opportunities aren't being received
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

class ExactFlowTest:
    """Test the exact same flow as Sistema III scanner + coordinator"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("ExactFlowTest")
        self.config = get_config()

        # Components matching Sistema III exactly
        self.scanner_bus = MessageBus()  # Scanner publishes
        self.coordinator_bus = MessageBus()  # Coordinator listens

        # Test tracking
        self.opportunities_published = []
        self.opportunities_received = []
        self.test_start_time = None

    async def test_scanner_simulation(self):
        """Test 1: Simulate EXACT scanner_central.py flow"""
        self.logger.info("🧪 TEST: Simulating scanner_central.py exact flow")

        try:
            # 1. Connect scanner MessageBus (like scanner_central.py line 69)
            scanner_connected = await self.scanner_bus.connect()
            if not scanner_connected:
                self.logger.error("❌ Scanner MessageBus connection failed")
                return False

            self.logger.info("✅ Scanner MessageBus connected")

            # 2. Create opportunity exactly like scanner_central.py line 198-214
            opportunity = {
                'symbol': 'EXACT_TEST',
                'opportunity_type': 'GAP_GO',  # Using exact types from scanner
                'quality_score': 85.0,
                'strategy_targets': {'entry': 10.0, 'stop': 9.5, 'target': 11.0},
                'catalyst_type': 'TECHNICAL',
                'catalyst_strength': 0.8,
                'current_price': 10.0,
                'gap_percentage': 3.5,
                'volume_ratio': 2.5,
                'trading_recommendation': 'BUY',
                'scan_timestamp': datetime.now().isoformat(),
                'ibkr_rank': 1,
                'news_count': 2,
                'sentiment_score': 0.7
            }

            self.opportunities_published.append(opportunity)

            # 3. Publish using EXACT same call as scanner_central.py line 142
            self.logger.info("📡 Publishing opportunity using EXACT scanner flow...")
            success = await self.scanner_bus.publish_opportunities([opportunity])

            if success:
                self.logger.info("✅ Scanner published opportunity successfully")
                return True
            else:
                self.logger.error("❌ Scanner failed to publish opportunity")
                return False

        except Exception as e:
            self.logger.error(f"❌ Scanner simulation error: {e}")
            return False

    async def test_coordinator_simulation(self):
        """Test 2: Simulate EXACT main.py coordinator flow"""
        self.logger.info("🧪 TEST: Simulating main.py coordinator exact flow")

        try:
            # 1. Connect coordinator MessageBus (like main.py line 75)
            coord_connected = await self.coordinator_bus.connect()
            if not coord_connected:
                self.logger.error("❌ Coordinator MessageBus connection failed")
                return False

            self.logger.info("✅ Coordinator MessageBus connected")

            # 2. Subscribe using EXACT same call as main.py line 112
            await self.coordinator_bus.subscribe_to_opportunities(self._handle_opportunity_exact)
            self.logger.info("✅ Coordinator subscribed to opportunities")

            # 3. Wait for messages like coordinator does
            self.logger.info("⏱️ Waiting for opportunities...")
            await asyncio.sleep(10)  # Wait 10 seconds for messages

            if self.opportunities_received:
                self.logger.info(f"✅ Coordinator received {len(self.opportunities_received)} opportunities")
                return True
            else:
                self.logger.error("❌ Coordinator received NO opportunities")
                return False

        except Exception as e:
            self.logger.error(f"❌ Coordinator simulation error: {e}")
            return False

    async def _handle_opportunity_exact(self, opportunity: Dict):
        """Handle opportunity EXACTLY like main.py line 199-240"""
        try:
            self.opportunities_received.append(opportunity)
            symbol = opportunity.get('symbol', 'UNKNOWN')
            strategy = opportunity.get('opportunity_type', 'UNKNOWN')

            self.logger.info(f"🎯 Coordinator received opportunity: {symbol} ({strategy})")

            # Log like main.py does
            self.logger.info(f"✅ Processing: {symbol} - {strategy}")

        except Exception as e:
            self.logger.error(f"❌ Error handling opportunity: {e}")

    async def test_combined_flow(self):
        """Test 3: Run scanner + coordinator together like real system"""
        self.logger.info("🧪 TEST: Combined scanner + coordinator flow")

        try:
            # Start both components
            scanner_task = asyncio.create_task(self._scanner_worker())
            coord_task = asyncio.create_task(self._coordinator_worker())

            # Run for 2 minutes
            self.test_start_time = datetime.now()
            await asyncio.sleep(120)  # 2 minutes

            # Cancel tasks
            scanner_task.cancel()
            coord_task.cancel()

            try:
                await scanner_task
            except asyncio.CancelledError:
                pass

            try:
                await coord_task
            except asyncio.CancelledError:
                pass

            # Report results
            published = len(self.opportunities_published)
            received = len(self.opportunities_received)

            self.logger.info(f"📊 Results: Published {published}, Received {received}")

            if published > 0 and received > 0:
                self.logger.info("✅ Combined flow working")
                return True
            elif published > 0 and received == 0:
                self.logger.error("❌ Scanner publishes but coordinator doesn't receive")
                return False
            else:
                self.logger.error("❌ Scanner not publishing")
                return False

        except Exception as e:
            self.logger.error(f"❌ Combined flow error: {e}")
            return False

    async def _scanner_worker(self):
        """Scanner worker that publishes every 30 seconds"""
        try:
            await self.scanner_bus.connect()
            cycle = 0

            while True:
                opportunity = {
                    'symbol': f'SCANNER_TEST_{cycle}',
                    'opportunity_type': 'DAILY_PLAYS',
                    'quality_score': 75.0 + cycle,
                    'strategy_targets': {'entry': 10.0, 'stop': 9.5, 'target': 11.0},
                    'catalyst_type': 'TECHNICAL',
                    'catalyst_strength': 0.7,
                    'current_price': 10.0 + cycle * 0.1,
                    'gap_percentage': 2.0 + cycle * 0.5,
                    'volume_ratio': 2.0,
                    'trading_recommendation': 'BUY',
                    'scan_timestamp': datetime.now().isoformat(),
                    'ibkr_rank': cycle + 1,
                    'news_count': 1,
                    'sentiment_score': 0.6,
                    'cycle': cycle
                }

                await self.scanner_bus.publish_opportunities([opportunity])
                self.opportunities_published.append(opportunity)

                elapsed = (datetime.now() - self.test_start_time).total_seconds()
                self.logger.info(f"📡 Scanner published cycle {cycle} at {elapsed:.1f}s")

                cycle += 1
                await asyncio.sleep(30)  # 30 second interval like real scanner

        except asyncio.CancelledError:
            self.logger.info("🛑 Scanner worker cancelled")
        except Exception as e:
            self.logger.error(f"❌ Scanner worker error: {e}")

    async def _coordinator_worker(self):
        """Coordinator worker that listens for opportunities"""
        try:
            await self.coordinator_bus.connect()
            await self.coordinator_bus.subscribe_to_opportunities(self._handle_opportunity_exact)
            self.logger.info("✅ Coordinator worker listening...")

            # Keep listening
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("🛑 Coordinator worker cancelled")
        except Exception as e:
            self.logger.error(f"❌ Coordinator worker error: {e}")

    async def test_redis_channels_debug(self):
        """Test 4: Debug Redis channels and subscriptions"""
        self.logger.info("🧪 TEST: Redis channels debug")

        try:
            # Connect both buses
            await self.scanner_bus.connect()
            await self.coordinator_bus.connect()

            # Get channel info from both
            scanner_info = await self.scanner_bus.get_channel_info()
            coord_info = await self.coordinator_bus.get_channel_info()

            self.logger.info("📊 Scanner MessageBus info:")
            for key, value in scanner_info.items():
                self.logger.info(f"   {key}: {value}")

            self.logger.info("📊 Coordinator MessageBus info:")
            for key, value in coord_info.items():
                self.logger.info(f"   {key}: {value}")

            # Check if they use same channels
            scanner_channel = scanner_info.get('scanner_channel', 'unknown')
            coord_channel = coord_info.get('scanner_channel', 'unknown')

            if scanner_channel == coord_channel:
                self.logger.info(f"✅ Both use same channel: {scanner_channel}")
                return True
            else:
                self.logger.error(f"❌ Different channels: scanner={scanner_channel}, coord={coord_channel}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Channel debug error: {e}")
            return False

    async def run_all_tests(self):
        """Run all exact flow tests"""
        self.logger.info("🚀 Starting Exact Flow Tests")

        results = {}

        # Test 1: Scanner simulation
        self.opportunities_published = []
        self.opportunities_received = []
        results['scanner_simulation'] = await self.test_scanner_simulation()
        await self.scanner_bus.disconnect()

        await asyncio.sleep(1)

        # Test 2: Coordinator simulation
        self.opportunities_published = []
        self.opportunities_received = []
        results['coordinator_simulation'] = await self.test_coordinator_simulation()
        await self.coordinator_bus.disconnect()

        await asyncio.sleep(1)

        # Test 3: Channel debug
        results['channels_debug'] = await self.test_redis_channels_debug()
        await self.scanner_bus.disconnect()
        await self.coordinator_bus.disconnect()

        await asyncio.sleep(1)

        # Test 4: Combined flow
        self.opportunities_published = []
        self.opportunities_received = []
        self.scanner_bus = MessageBus()  # Fresh instances
        self.coordinator_bus = MessageBus()
        results['combined_flow'] = await self.test_combined_flow()
        await self.scanner_bus.disconnect()
        await self.coordinator_bus.disconnect()

        # Report results
        self.logger.info("📊 EXACT FLOW TEST RESULTS:")
        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            self.logger.info(f"   {test_name}: {status}")

        return results

async def main():
    """Run the exact flow test"""
    test = ExactFlowTest()

    print("🧪 EXACT SISTEMA III FLOW TEST")
    print("   Testing exact scanner_central.py + main.py flow")
    print("   Identifying why opportunities aren't received")
    print()

    try:
        results = await test.run_all_tests()

        # Determine if tests passed
        passed_tests = sum(1 for passed in results.values() if passed)
        total_tests = len(results)

        print(f"\n📈 SUMMARY: {passed_tests}/{total_tests} tests passed")

        if results.get('combined_flow', False):
            print("✅ Sistema III communication WORKING")
            return 0
        else:
            print("❌ Sistema III communication BROKEN")
            return 1

    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)