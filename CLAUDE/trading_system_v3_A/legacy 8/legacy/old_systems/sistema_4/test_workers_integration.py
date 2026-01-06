#!/usr/bin/env python3
"""
Test Workers Integration - Comprehensive testing of worker signal processing
Tests that workers correctly process scanner opportunities and generate valid trade orders
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shared.database import Sistema4Database
from shared.message_bus import MessageBus
from execution.execution_engine import ExecutionEngine
from utils.log_config import setup_logging

class WorkerIntegrationTester:
    """
    Tests the complete worker workflow:
    1. Scanner publishes opportunities
    2. Workers process and analyze opportunities
    3. Workers generate trade requests
    4. Execution Engine receives and validates requests
    """

    def __init__(self):
        setup_logging(level="INFO", log_file="logs/worker_integration_test.log")
        self.logger = logging.getLogger("WorkerIntegrationTester")

        # Components
        self.database = Sistema4Database()
        self.message_bus = MessageBus()
        self.execution_engine = ExecutionEngine()

        # Test results
        self.test_results = []
        self.opportunities_sent = 0
        self.trade_requests_received = 0
        self.valid_orders = 0
        self.invalid_orders = 0

        self.logger.info("🧪 Worker Integration Tester initialized")

    async def setup(self):
        """Setup test environment"""
        try:
            # Connect message bus
            if not await self.message_bus.connect():
                raise Exception("Failed to connect to Redis")

            # Start execution engine
            if not await self.execution_engine.start():
                raise Exception("Failed to start execution engine")

            # Subscribe to trade requests to monitor them
            await self.message_bus._subscribe_to_channel("trade_requests", self._monitor_trade_request)

            self.logger.info("✅ Test environment setup complete")
            return True

        except Exception as e:
            self.logger.error(f"❌ Setup failed: {e}")
            return False

    async def run_comprehensive_test(self):
        """Run comprehensive worker test suite"""
        self.logger.info("🚀 Starting comprehensive worker integration test...")

        if not await self.setup():
            return False

        # Test cases for different strategies
        test_cases = [
            self._test_gap_go_opportunities(),
            self._test_daily_plays_opportunities(),
            self._test_bull_flag_opportunities(),
            self._test_macdv_opportunities(),
            self._test_edge_cases(),
            self._test_risk_management(),
        ]

        # Run all test cases
        for test_case in test_cases:
            try:
                await test_case
                await asyncio.sleep(2)  # Wait between tests
            except Exception as e:
                self.logger.error(f"❌ Test case failed: {e}")

        # Generate final report
        await self._generate_test_report()

        return True

    async def _test_gap_go_opportunities(self):
        """Test GAP_GO worker with various gap scenarios"""
        self.logger.info("🔍 Testing GAP_GO opportunities...")

        # Valid gap up opportunity
        gap_up_opportunity = {
            'symbol': 'AAPL',
            'opportunity_type': 'GAP_GO',
            'quality_score': 8.5,
            'gap_percentage': 5.2,  # 5.2% gap up
            'current_price': 150.75,
            'volume': 250000,
            'volume_ratio': 2.5,
            'catalyst_type': 'EARNINGS',
            'catalyst_strength': 0.8,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Valid gap down opportunity
        gap_down_opportunity = {
            'symbol': 'TSLA',
            'opportunity_type': 'GAP_GO',
            'quality_score': 7.8,
            'gap_percentage': -4.1,  # 4.1% gap down
            'current_price': 245.30,
            'volume': 180000,
            'volume_ratio': 3.1,
            'catalyst_type': 'NEWS',
            'catalyst_strength': 0.7,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Invalid gap (too small)
        small_gap_opportunity = {
            'symbol': 'MSFT',
            'opportunity_type': 'GAP_GO',
            'quality_score': 6.0,
            'gap_percentage': 1.2,  # Too small gap
            'current_price': 330.50,
            'volume': 100000,
            'volume_ratio': 1.5,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Invalid gap (too large)
        large_gap_opportunity = {
            'symbol': 'NVDA',
            'opportunity_type': 'GAP_GO',
            'quality_score': 9.2,
            'gap_percentage': 25.5,  # Too large gap
            'current_price': 425.80,
            'volume': 500000,
            'volume_ratio': 4.0,
            'scan_timestamp': datetime.now().isoformat()
        }

        opportunities = [gap_up_opportunity, gap_down_opportunity, small_gap_opportunity, large_gap_opportunity]

        for opportunity in opportunities:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(1)

        self.logger.info(f"✅ Published {len(opportunities)} GAP_GO opportunities")

    async def _test_daily_plays_opportunities(self):
        """Test DAILY_PLAYS worker with intraday momentum opportunities"""
        self.logger.info("🔍 Testing DAILY_PLAYS opportunities...")

        # High momentum opportunity
        momentum_opportunity = {
            'symbol': 'AMD',
            'opportunity_type': 'INTRADAY_MOMENTUM',
            'quality_score': 8.2,
            'current_price': 105.25,
            'volume': 320000,
            'volume_ratio': 2.8,
            'gap_percentage': 2.1,
            'catalyst_type': 'TECHNICAL',
            'catalyst_strength': 0.75,
            'trading_recommendation': 'BUY',
            'strategy_targets': {
                'entry': 105.25,
                'stop_loss': 102.50,
                'target_1': 108.00,
                'target_2': 110.50
            },
            'scan_timestamp': datetime.now().isoformat()
        }

        # Low momentum opportunity (should be filtered)
        low_momentum_opportunity = {
            'symbol': 'INTC',
            'opportunity_type': 'INTRADAY_MOMENTUM',
            'quality_score': 5.1,
            'current_price': 45.75,
            'volume': 50000,  # Low volume
            'volume_ratio': 0.8,
            'gap_percentage': 0.3,
            'trading_recommendation': 'HOLD',  # Not actionable
            'scan_timestamp': datetime.now().isoformat()
        }

        opportunities = [momentum_opportunity, low_momentum_opportunity]

        for opportunity in opportunities:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(1)

        self.logger.info(f"✅ Published {len(opportunities)} DAILY_PLAYS opportunities")

    async def _test_bull_flag_opportunities(self):
        """Test BULL_FLAG worker with continuation patterns"""
        self.logger.info("🔍 Testing BULL_FLAG opportunities...")

        # Valid bull flag setup
        bull_flag_opportunity = {
            'symbol': 'GOOGL',
            'opportunity_type': 'BULL_FLAG',
            'quality_score': 7.9,
            'current_price': 2650.30,
            'volume': 180000,
            'pattern_type': 'BULL_FLAG',
            'consolidation_days': 3,
            'breakout_level': 2665.00,
            'flag_pole_height': 120.50,
            'target_price': 2785.50,
            'stop_loss_level': 2610.00,
            'pattern_strength': 0.82,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Weak pattern (should be filtered)
        weak_pattern_opportunity = {
            'symbol': 'META',
            'opportunity_type': 'BULL_FLAG',
            'quality_score': 4.5,
            'current_price': 315.40,
            'volume': 45000,  # Low volume
            'pattern_strength': 0.35,  # Weak pattern
            'consolidation_days': 8,  # Too long consolidation
            'scan_timestamp': datetime.now().isoformat()
        }

        opportunities = [bull_flag_opportunity, weak_pattern_opportunity]

        for opportunity in opportunities:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(1)

        self.logger.info(f"✅ Published {len(opportunities)} BULL_FLAG opportunities")

    async def _test_macdv_opportunities(self):
        """Test MACDV worker with MACD divergence setups"""
        self.logger.info("🔍 Testing MACDV opportunities...")

        # Valid MACD divergence
        macdv_opportunity = {
            'symbol': 'CRM',
            'opportunity_type': 'MACDV',
            'quality_score': 8.7,
            'current_price': 220.15,
            'volume': 150000,
            'macd_signal': 'BULLISH_DIVERGENCE',
            'macd_histogram': 0.45,
            'rsi_level': 35.2,  # Oversold
            'divergence_strength': 0.78,
            'time_frame': '1D',
            'confirmation_signals': ['RSI_OVERSOLD', 'VOLUME_SPIKE'],
            'scan_timestamp': datetime.now().isoformat()
        }

        # False signal (should be filtered)
        false_signal_opportunity = {
            'symbol': 'ORCL',
            'opportunity_type': 'MACDV',
            'quality_score': 3.2,
            'current_price': 115.80,
            'volume': 30000,  # Low volume
            'macd_signal': 'WEAK_SIGNAL',
            'divergence_strength': 0.25,  # Too weak
            'rsi_level': 55.0,  # Neutral
            'scan_timestamp': datetime.now().isoformat()
        }

        opportunities = [macdv_opportunity, false_signal_opportunity]

        for opportunity in opportunities:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(1)

        self.logger.info(f"✅ Published {len(opportunities)} MACDV opportunities")

    async def _test_edge_cases(self):
        """Test edge cases and error handling"""
        self.logger.info("🔍 Testing edge cases...")

        # Missing required fields
        incomplete_opportunity = {
            'symbol': 'EDGE1',
            'opportunity_type': 'GAP_GO',
            # Missing gap_percentage, current_price, etc.
            'scan_timestamp': datetime.now().isoformat()
        }

        # Invalid symbol
        invalid_symbol_opportunity = {
            'symbol': '',  # Empty symbol
            'opportunity_type': 'GAP_GO',
            'quality_score': 7.0,
            'gap_percentage': 3.5,
            'current_price': 50.0,
            'scan_timestamp': datetime.now().isoformat()
        }

        # Unknown opportunity type
        unknown_type_opportunity = {
            'symbol': 'EDGE3',
            'opportunity_type': 'UNKNOWN_STRATEGY',
            'quality_score': 8.0,
            'current_price': 100.0,
            'scan_timestamp': datetime.now().isoformat()
        }

        edge_cases = [incomplete_opportunity, invalid_symbol_opportunity, unknown_type_opportunity]

        for opportunity in edge_cases:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(0.5)

        self.logger.info(f"✅ Published {len(edge_cases)} edge case opportunities")

    async def _test_risk_management(self):
        """Test risk management and position limits"""
        self.logger.info("🔍 Testing risk management...")

        # High-priced stock (should calculate smaller position size)
        expensive_stock_opportunity = {
            'symbol': 'BRK-A',
            'opportunity_type': 'GAP_GO',
            'quality_score': 8.0,
            'gap_percentage': 2.5,
            'current_price': 525000.00,  # Very expensive
            'volume': 5,  # Low volume for expensive stock
            'scan_timestamp': datetime.now().isoformat()
        }

        # Penny stock (should be filtered out)
        penny_stock_opportunity = {
            'symbol': 'PENNY',
            'opportunity_type': 'GAP_GO',
            'quality_score': 9.0,  # High quality score but...
            'gap_percentage': 15.0,
            'current_price': 0.50,  # Too cheap
            'volume': 1000000,
            'scan_timestamp': datetime.now().isoformat()
        }

        risk_test_cases = [expensive_stock_opportunity, penny_stock_opportunity]

        for opportunity in risk_test_cases:
            await self._publish_opportunity(opportunity)
            await asyncio.sleep(1)

        self.logger.info(f"✅ Published {len(risk_test_cases)} risk management test cases")

    async def _publish_opportunity(self, opportunity: Dict[str, Any]):
        """Publish opportunity to Redis for workers to process"""
        try:
            opportunities = [opportunity]
            await self.message_bus._publish_to_channel("opportunities", json.dumps(opportunities))
            self.opportunities_sent += 1

            self.logger.debug(f"📡 Published opportunity: {opportunity['symbol']} ({opportunity['opportunity_type']})")

        except Exception as e:
            self.logger.error(f"❌ Error publishing opportunity: {e}")

    async def _monitor_trade_request(self, trade_request_json: str):
        """Monitor trade requests generated by workers"""
        try:
            trade_request = json.loads(trade_request_json)
            self.trade_requests_received += 1

            symbol = trade_request.get('symbol', 'UNKNOWN')
            action = trade_request.get('action', 'UNKNOWN')
            quantity = trade_request.get('quantity', 0)
            strategy = trade_request.get('strategy', 'UNKNOWN')

            # Validate trade request
            is_valid = self._validate_trade_request(trade_request)

            if is_valid:
                self.valid_orders += 1
                self.logger.info(f"✅ Valid trade request: {strategy} - {action} {quantity} {symbol}")
            else:
                self.invalid_orders += 1
                self.logger.warning(f"⚠️ Invalid trade request: {strategy} - {symbol}")

            # Store result for reporting
            self.test_results.append({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'strategy': strategy,
                'action': action,
                'quantity': quantity,
                'valid': is_valid,
                'trade_request': trade_request
            })

        except Exception as e:
            self.logger.error(f"❌ Error monitoring trade request: {e}")

    def _validate_trade_request(self, trade_request: Dict[str, Any]) -> bool:
        """Validate that trade request has all required fields and logical values"""
        required_fields = ['symbol', 'action', 'quantity', 'strategy', 'worker_id']

        # Check required fields
        for field in required_fields:
            if field not in trade_request or not trade_request[field]:
                self.logger.debug(f"Missing or empty field: {field}")
                return False

        # Validate action
        if trade_request['action'] not in ['BUY', 'SELL']:
            self.logger.debug(f"Invalid action: {trade_request['action']}")
            return False

        # Validate quantity
        quantity = trade_request['quantity']
        if not isinstance(quantity, int) or quantity <= 0 or quantity > 10000:
            self.logger.debug(f"Invalid quantity: {quantity}")
            return False

        # Validate symbol format
        symbol = trade_request['symbol']
        if not isinstance(symbol, str) or len(symbol) < 1 or len(symbol) > 10:
            self.logger.debug(f"Invalid symbol: {symbol}")
            return False

        # Validate stop loss and take profit if present
        if 'stop_loss_price' in trade_request:
            stop_loss = trade_request['stop_loss_price']
            if stop_loss <= 0:
                self.logger.debug(f"Invalid stop loss: {stop_loss}")
                return False

        if 'take_profit_price' in trade_request:
            take_profit = trade_request['take_profit_price']
            if take_profit <= 0:
                self.logger.debug(f"Invalid take profit: {take_profit}")
                return False

        return True

    async def _generate_test_report(self):
        """Generate comprehensive test report"""
        await asyncio.sleep(3)  # Wait for any remaining messages

        self.logger.info("📊 WORKER INTEGRATION TEST REPORT")
        self.logger.info("=" * 50)
        self.logger.info(f"📡 Opportunities Published: {self.opportunities_sent}")
        self.logger.info(f"📥 Trade Requests Received: {self.trade_requests_received}")
        self.logger.info(f"✅ Valid Orders Generated: {self.valid_orders}")
        self.logger.info(f"❌ Invalid Orders: {self.invalid_orders}")

        if self.trade_requests_received > 0:
            success_rate = (self.valid_orders / self.trade_requests_received) * 100
            self.logger.info(f"📈 Success Rate: {success_rate:.1f}%")

        # Detailed results by strategy
        strategy_stats = {}
        for result in self.test_results:
            strategy = result['strategy']
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {'total': 0, 'valid': 0}
            strategy_stats[strategy]['total'] += 1
            if result['valid']:
                strategy_stats[strategy]['valid'] += 1

        self.logger.info("\n📋 Results by Strategy:")
        for strategy, stats in strategy_stats.items():
            success_rate = (stats['valid'] / stats['total']) * 100 if stats['total'] > 0 else 0
            self.logger.info(f"  {strategy}: {stats['valid']}/{stats['total']} valid ({success_rate:.1f}%)")

        # Database stats
        db_stats = self.database.get_stats()
        self.logger.info(f"\n💾 Database Stats: {db_stats}")

        self.logger.info("=" * 50)

        # Determine overall test result
        overall_success = self.valid_orders > 0 and (self.invalid_orders / max(self.trade_requests_received, 1)) < 0.3

        if overall_success:
            self.logger.info("🎉 WORKER INTEGRATION TEST PASSED")
        else:
            self.logger.error("❌ WORKER INTEGRATION TEST FAILED")

        return overall_success

    async def cleanup(self):
        """Clean up test environment"""
        try:
            await self.execution_engine.stop()
            await self.message_bus.disconnect()
            self.logger.info("✅ Test cleanup complete")
        except Exception as e:
            self.logger.error(f"❌ Cleanup error: {e}")

async def main():
    """Run worker integration test"""
    tester = WorkerIntegrationTester()

    try:
        success = await tester.run_comprehensive_test()
        await tester.cleanup()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        await tester.cleanup()
        return 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        await tester.cleanup()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)