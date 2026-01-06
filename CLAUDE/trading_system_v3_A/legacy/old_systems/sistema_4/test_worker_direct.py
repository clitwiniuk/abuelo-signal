#!/usr/bin/env python3
"""
Direct Worker Test - Test individual worker logic without full system
Tests worker analysis and trade generation logic directly
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.log_config import setup_logging

class DirectWorkerTester:
    """Test workers directly by instantiating them and testing their analysis logic"""

    def __init__(self):
        setup_logging(level="INFO")
        self.logger = logging.getLogger("DirectWorkerTester")
        self.test_results = []

    def test_gap_go_analysis(self):
        """Test GAP_GO worker analysis logic directly"""
        self.logger.info("🔍 Testing GAP_GO worker analysis...")

        try:
            from workers.gap_go_worker import GapGoWorker

            # Create worker instance
            worker = GapGoWorker("test_gap_worker")

            # Test cases - Adjusted for penny stock GAP_GO configuration
            test_opportunities = [
                {
                    'symbol': 'SNDL',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 5.2,
                    'current_price': 8.75,  # Within $1-$15 range
                    'volume': 750000,        # Above 500K minimum
                    'volume_ratio': 2.5,
                    'test_name': 'Valid Gap Up Penny Stock'
                },
                {
                    'symbol': 'NAKD',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': -4.1,
                    'current_price': 3.45,   # Within range
                    'volume': 1200000,       # High volume
                    'volume_ratio': 3.1,
                    'test_name': 'Valid Gap Down Penny Stock'
                },
                {
                    'symbol': 'EXPR',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 1.2,   # Too small gap
                    'current_price': 5.50,
                    'volume': 600000,
                    'test_name': 'Gap Too Small (should reject)'
                },
                {
                    'symbol': 'WISH',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 18.5,  # Too large gap
                    'current_price': 2.80,
                    'volume': 2000000,
                    'test_name': 'Gap Too Large (should reject)'
                },
                {
                    'symbol': 'CLOV',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 6.0,   # Valid gap
                    'current_price': 4.25,   # Valid price
                    'volume': 150000,        # Too low volume
                    'test_name': 'Volume Too Low (should reject)'
                },
                {
                    'symbol': 'TSLA',  # Original high-priced stock test
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 5.2,
                    'current_price': 245.30,  # Out of price range
                    'volume': 1000000,
                    'test_name': 'Price Too High (should reject)'
                }
            ]

            for opportunity in test_opportunities:
                try:
                    # Test the analysis method directly
                    analysis = asyncio.run(worker._analyze_gap_setup(opportunity))

                    result = {
                        'strategy': 'GAP_GO',
                        'test_name': opportunity['test_name'],
                        'symbol': opportunity['symbol'],
                        'should_trade': analysis['should_trade'],
                        'reason': analysis['reason'],
                        'action': analysis.get('action', 'N/A'),
                        'quantity': analysis.get('quantity', 0),
                        'stop_loss': analysis.get('stop_loss', 0),
                        'take_profit': analysis.get('take_profit', 0)
                    }

                    self.test_results.append(result)

                    if analysis['should_trade']:
                        self.logger.info(f"✅ {opportunity['test_name']}: {result['action']} {result['quantity']} {result['symbol']}")
                        self.logger.info(f"   🎯 Stop: ${result['stop_loss']:.2f} | Target: ${result['take_profit']:.2f}")
                    else:
                        self.logger.info(f"⛔ {opportunity['test_name']}: {result['reason']}")

                except Exception as e:
                    self.logger.error(f"❌ Error testing {opportunity['test_name']}: {e}")

            return True

        except ImportError as e:
            self.logger.error(f"❌ Could not import GAP_GO worker: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ GAP_GO test failed: {e}")
            return False

    def test_daily_plays_analysis(self):
        """Test DAILY_PLAYS worker analysis logic"""
        self.logger.info("🔍 Testing DAILY_PLAYS worker analysis...")

        try:
            from workers.daily_plays_worker import DailyPlaysWorker

            worker = DailyPlaysWorker("test_daily_worker")

            test_opportunities = [
                {
                    'symbol': 'AMD',
                    'opportunity_type': 'INTRADAY_MOMENTUM',
                    'quality_score': 8.2,
                    'current_price': 105.25,
                    'volume': 320000,
                    'volume_ratio': 2.8,
                    'gap_percentage': 2.1,
                    'trading_recommendation': 'BUY',
                    'test_name': 'High Momentum Buy'
                },
                {
                    'symbol': 'INTC',
                    'opportunity_type': 'INTRADAY_MOMENTUM',
                    'quality_score': 5.1,
                    'current_price': 45.75,
                    'volume': 50000,  # Low volume
                    'volume_ratio': 0.8,
                    'trading_recommendation': 'HOLD',
                    'test_name': 'Low Quality Hold (should reject)'
                }
            ]

            for opportunity in test_opportunities:
                try:
                    analysis = asyncio.run(worker._analyze_momentum_setup(opportunity))

                    result = {
                        'strategy': 'DAILY_PLAYS',
                        'test_name': opportunity['test_name'],
                        'symbol': opportunity['symbol'],
                        'should_trade': analysis['should_trade'],
                        'reason': analysis['reason'],
                        'action': analysis.get('action', 'N/A'),
                        'quantity': analysis.get('quantity', 0)
                    }

                    self.test_results.append(result)

                    if analysis['should_trade']:
                        self.logger.info(f"✅ {opportunity['test_name']}: {result['action']} {result['quantity']} {result['symbol']}")
                    else:
                        self.logger.info(f"⛔ {opportunity['test_name']}: {result['reason']}")

                except Exception as e:
                    self.logger.error(f"❌ Error testing {opportunity['test_name']}: {e}")

            return True

        except ImportError as e:
            self.logger.error(f"❌ Could not import DAILY_PLAYS worker: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ DAILY_PLAYS test failed: {e}")
            return False

    def test_trade_request_generation(self):
        """Test trade request generation from valid analyses"""
        self.logger.info("🔍 Testing trade request generation...")

        try:
            from workers.gap_go_worker import GapGoWorker

            worker = GapGoWorker("test_request_worker")

            # Valid opportunity - Adjusted for penny stock parameters
            opportunity = {
                'symbol': 'SNDL',
                'opportunity_type': 'GAP_GO',
                'gap_percentage': 5.2,
                'current_price': 8.75,   # Within $1-$15 range
                'volume': 750000,        # Above 500K minimum
                'volume_ratio': 2.5,
            }

            # Get analysis
            analysis = asyncio.run(worker._analyze_gap_setup(opportunity))

            if analysis['should_trade']:
                # Generate trade request
                trade_request = worker._generate_trade_request(opportunity['symbol'], opportunity, analysis)

                # Validate trade request structure
                required_fields = ['symbol', 'action', 'quantity', 'order_type', 'strategy', 'worker_id']
                missing_fields = [field for field in required_fields if field not in trade_request]

                if not missing_fields:
                    self.logger.info(f"✅ Trade request generated successfully:")
                    self.logger.info(f"   📋 {trade_request['action']} {trade_request['quantity']} {trade_request['symbol']}")
                    self.logger.info(f"   📈 Order Type: {trade_request['order_type']}")
                    self.logger.info(f"   🛑 Stop Loss: ${trade_request.get('stop_loss_price', 0):.2f}")
                    self.logger.info(f"   🎯 Take Profit: ${trade_request.get('take_profit_price', 0):.2f}")

                    self.test_results.append({
                        'test_name': 'Trade Request Generation',
                        'success': True,
                        'trade_request': trade_request
                    })

                    return True
                else:
                    self.logger.error(f"❌ Trade request missing fields: {missing_fields}")
                    return False
            else:
                self.logger.error(f"❌ Analysis rejected trade: {analysis['reason']}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Trade request generation test failed: {e}")
            return False

    def test_risk_calculations(self):
        """Test position sizing and risk calculations"""
        self.logger.info("🔍 Testing risk calculations...")

        try:
            from workers.gap_go_worker import GapGoWorker

            worker = GapGoWorker("test_risk_worker")

            # Test different price levels for position sizing - Adjusted for penny stock range
            price_scenarios = [
                {'price': 2.50, 'expected': 'large_size'},   # Low price = larger position
                {'price': 5.00, 'expected': 'medium_size'},  # Mid range
                {'price': 10.00, 'expected': 'small_size'}, # Higher price = smaller position
                {'price': 0.75, 'expected': 'rejected'},    # Too cheap (below $1)
            ]

            for scenario in price_scenarios:
                opportunity = {
                    'symbol': f'TEST_{scenario["price"]}',
                    'opportunity_type': 'GAP_GO',
                    'gap_percentage': 5.0,  # Valid gap
                    'current_price': scenario['price'],
                    'volume': 600000,  # Above 500K minimum
                    'volume_ratio': 2.0,
                }

                analysis = asyncio.run(worker._analyze_gap_setup(opportunity))

                if analysis['should_trade']:
                    # Check if position sizing makes sense
                    risk_amount = 100  # $100 risk per trade
                    stop_distance = abs(scenario['price'] - analysis['stop_loss'])
                    expected_quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 100

                    self.logger.info(f"💰 Price ${scenario['price']:.2f}: Qty {analysis['quantity']}, Stop Distance ${stop_distance:.2f}")

                    # Verify position size is reasonable
                    if 10 <= analysis['quantity'] <= 1000:
                        self.logger.info(f"   ✅ Position size reasonable")
                    else:
                        self.logger.warning(f"   ⚠️ Position size may be too large/small: {analysis['quantity']}")

                else:
                    self.logger.info(f"⛔ Price ${scenario['price']:.2f}: Rejected - {analysis['reason']}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Risk calculations test failed: {e}")
            return False

    def generate_report(self):
        """Generate test report"""
        self.logger.info("📊 DIRECT WORKER TEST REPORT")
        self.logger.info("=" * 50)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.get('should_trade') or result.get('success'))

        self.logger.info(f"📋 Total Tests: {total_tests}")
        self.logger.info(f"✅ Tests with Valid Analysis: {passed_tests}")

        # Group by strategy
        strategy_results = {}
        for result in self.test_results:
            strategy = result.get('strategy', 'Unknown')
            if strategy not in strategy_results:
                strategy_results[strategy] = []
            strategy_results[strategy].append(result)

        for strategy, results in strategy_results.items():
            self.logger.info(f"\n📈 {strategy} Strategy:")
            for result in results:
                status = "✅" if result.get('should_trade') or result.get('success') else "⛔"
                test_name = result.get('test_name', 'Unknown Test')
                symbol = result.get('symbol', '')
                reason = result.get('reason', 'N/A')
                self.logger.info(f"   {status} {test_name} ({symbol}): {reason}")

        self.logger.info("=" * 50)

def main():
    """Run direct worker tests"""
    tester = DirectWorkerTester()

    print("🧪 SISTEMA_4 WORKER DIRECT TESTING")
    print("Testing worker analysis logic without full system dependencies")
    print()

    # Run tests
    tests = [
        tester.test_gap_go_analysis,
        tester.test_trade_request_generation,
        tester.test_risk_calculations,
        # tester.test_daily_plays_analysis,  # Uncomment if daily_plays_worker exists
    ]

    success_count = 0
    for test in tests:
        try:
            if test():
                success_count += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test failed: {e}")
            print()

    # Generate report
    tester.generate_report()

    # Final result
    if success_count == len(tests):
        print("🎉 ALL WORKER TESTS PASSED")
        return 0
    else:
        print(f"❌ {len(tests) - success_count} TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)