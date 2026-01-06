#!/usr/bin/env python3
"""
Test Redis Communication between Scanner and Coordinator
Simulates the exact flow to identify the 10-minute timeout issue
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
from core.scanner_trader_bridge import ScannerTraderBridge

class RedisCommTest:
    """Test Redis communication between scanner and coordinator components"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("RedisTest")
        self.config = get_config()

        # Test components
        self.message_bus = MessageBus()  # Sistema III style
        self.scanner_bridge = ScannerTraderBridge()  # Original style

        # Test data
        self.opportunities_received = []
        self.test_start_time = None

    async def test_message_bus_only(self):
        """Test 1: Sistema III MessageBus pub/sub"""
        self.logger.info("🧪 TEST 1: Sistema III MessageBus communication")

        try:
            # Connect message bus
            connected = await self.message_bus.connect()
            if not connected:
                self.logger.error("❌ MessageBus connection failed")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._handle_opportunity)
            self.logger.info("✅ Subscribed to opportunities")

            # Wait a bit for subscription to be ready
            await asyncio.sleep(2)

            # Publish test opportunity
            test_opportunity = {
                'symbol': 'TEST',
                'opportunity_type': 'GAP_GO',
                'quality_score': 85.0,
                'scan_timestamp': datetime.now().isoformat(),
                'test_id': 'message_bus_test'
            }

            self.logger.info("📡 Publishing test opportunity...")
            success = await self.message_bus.publish_opportunities([test_opportunity])

            if success:
                self.logger.info("✅ Test opportunity published")
                # Wait for message to be received
                await asyncio.sleep(5)

                if self.opportunities_received:
                    self.logger.info(f"✅ TEST 1 PASSED: Received {len(self.opportunities_received)} opportunities")
                    return True
                else:
                    self.logger.error("❌ TEST 1 FAILED: No opportunities received")
                    return False
            else:
                self.logger.error("❌ TEST 1 FAILED: Could not publish opportunity")
                return False

        except Exception as e:
            self.logger.error(f"❌ TEST 1 ERROR: {e}")
            return False
        finally:
            await self.message_bus.disconnect()

    async def test_scanner_bridge_only(self):
        """Test 2: Original ScannerTraderBridge"""
        self.logger.info("🧪 TEST 2: Original ScannerTraderBridge communication")

        try:
            # Connect scanner bridge
            connected = await self.scanner_bridge.connect()
            if not connected:
                self.logger.error("❌ ScannerBridge connection failed")
                return False

            # Publish test opportunity using original bridge
            test_opportunity = {
                'symbol': 'TEST2',
                'opportunity_type': 'DAILY_PLAYS',
                'quality_score': 90.0,
                'scan_timestamp': datetime.now().isoformat(),
                'test_id': 'scanner_bridge_test'
            }

            self.logger.info("📡 Publishing via ScannerBridge...")
            await self.scanner_bridge.publish_opportunities([test_opportunity])
            self.logger.info("✅ ScannerBridge publish completed")

            return True

        except Exception as e:
            self.logger.error(f"❌ TEST 2 ERROR: {e}")
            return False
        finally:
            await self.scanner_bridge.disconnect()

    async def test_timeout_simulation(self):
        """Test 3: Simulate the 10-minute timeout scenario"""
        self.logger.info("🧪 TEST 3: 10-minute timeout simulation")

        try:
            # Connect both systems
            bus_connected = await self.message_bus.connect()
            bridge_connected = await self.scanner_bridge.connect()

            if not bus_connected or not bridge_connected:
                self.logger.error("❌ Connection failed in timeout test")
                return False

            # Subscribe to opportunities
            await self.message_bus.subscribe_to_opportunities(self._handle_timeout_opportunity)
            self.logger.info("✅ Timeout test subscribed")

            self.test_start_time = datetime.now()

            # Simulate scanner publishing opportunities every 30 seconds
            for i in range(20):  # Run for 10 minutes (20 * 30 seconds)
                opportunity = {
                    'symbol': f'TIMEOUT_TEST_{i}',
                    'opportunity_type': 'MACDV',
                    'quality_score': 75.0 + i,
                    'scan_timestamp': datetime.now().isoformat(),
                    'test_id': f'timeout_test_{i}',
                    'cycle': i
                }

                # Publish via ScannerBridge (like real scanner)
                await self.scanner_bridge.publish_opportunities([opportunity])

                elapsed = (datetime.now() - self.test_start_time).total_seconds()
                self.logger.info(f"⏱️ Cycle {i}: {elapsed:.1f}s elapsed, published {opportunity['symbol']}")

                # Check if we've hit the 10-minute mark
                if elapsed > 600:  # 10 minutes
                    self.logger.warning("🚨 Reached 10-minute mark!")
                    break

                await asyncio.sleep(30)  # Wait 30 seconds like real scanner

            # Final check
            total_elapsed = (datetime.now() - self.test_start_time).total_seconds()
            self.logger.info(f"🏁 Timeout test completed: {total_elapsed:.1f}s, received {len(self.opportunities_received)} opportunities")

            return len(self.opportunities_received) > 0

        except Exception as e:
            self.logger.error(f"❌ TEST 3 ERROR: {e}")
            return False
        finally:
            await self.message_bus.disconnect()
            await self.scanner_bridge.disconnect()

    async def _handle_opportunity(self, opportunity: Dict):
        """Handle opportunity for TEST 1"""
        self.opportunities_received.append(opportunity)
        self.logger.info(f"📨 MessageBus received: {opportunity.get('symbol')} ({opportunity.get('test_id')})")

    async def _handle_timeout_opportunity(self, opportunity: Dict):
        """Handle opportunity for TEST 3"""
        self.opportunities_received.append(opportunity)
        elapsed = (datetime.now() - self.test_start_time).total_seconds()
        self.logger.info(f"📨 Timeout test received: {opportunity.get('symbol')} at {elapsed:.1f}s")

    async def run_all_tests(self):
        """Run all communication tests"""
        self.logger.info("🚀 Starting Redis Communication Tests")

        results = {}

        # Reset for each test
        self.opportunities_received = []
        results['test1_message_bus'] = await self.test_message_bus_only()

        await asyncio.sleep(2)  # Brief pause between tests

        self.opportunities_received = []
        results['test2_scanner_bridge'] = await self.test_scanner_bridge_only()

        await asyncio.sleep(2)

        self.opportunities_received = []
        results['test3_timeout'] = await self.test_timeout_simulation()

        # Report results
        self.logger.info("📊 TEST RESULTS:")
        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            self.logger.info(f"   {test_name}: {status}")

        return results

async def main():
    """Run the Redis communication test"""
    test = RedisCommTest()

    print("🧪 REDIS COMMUNICATION TEST")
    print("   Testing Sistema III vs Original communication")
    print("   Looking for 10-minute timeout patterns")
    print()

    try:
        results = await test.run_all_tests()

        # Determine if tests passed
        passed_tests = sum(1 for passed in results.values() if passed)
        total_tests = len(results)

        print(f"\n📈 SUMMARY: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print("✅ All tests passed - Redis communication working")
            return 0
        else:
            print("❌ Some tests failed - Redis communication issues detected")
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