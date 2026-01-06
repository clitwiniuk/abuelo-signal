#!/usr/bin/env python3
"""
Comprehensive FOMO Exit System Tests
Tests the FOMO exhaustion detection system with various scenarios
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
import pandas as pd

# Add project root to path
sys.path.append('.')

from core.interfaces import MarketData, Position, SignalType
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FOOMTestScenarios:
    """Test scenarios for FOMO exit detection"""
    
    @staticmethod
    def create_market_data(symbol: str, price: float, volume: int, timestamp: datetime) -> MarketData:
        """Create market data for testing"""
        return MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=price * 0.995,
            high=price * 1.005,
            low=price * 0.99,
            close=price,
            volume=volume,
            vwap=price
        )
    
    @staticmethod
    def create_position(symbol: str, entry_price: float, quantity: int = 100) -> Position:
        """Create position for testing"""
        return Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=entry_price,
            market_value=entry_price * quantity,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
    
    @staticmethod
    def scenario_volume_spike_price_stall() -> Dict[str, Any]:
        """
        Scenario 1: Volume spike with price stall (should trigger FOMO exit)
        """
        symbol = "TEST1"
        entry_price = 10.00
        current_price = 11.00  # 10% profit
        
        # Create history with normal volume, then spike
        base_time = datetime.now() - timedelta(minutes=15)
        bars = []
        
        # Normal volume bars (average ~100K)
        for i in range(9):
            price = entry_price + (i * 0.05)  # Gradual increase
            volume = 80000 + (i * 5000)  # Normal volume pattern
            bars.append(FOOMTestScenarios.create_market_data(
                symbol, price, volume, base_time + timedelta(minutes=i)
            ))
        
        # Current bar: Volume spike (250K = 2.5x average) + price stall
        current_bar = FOOMTestScenarios.create_market_data(
            symbol, current_price, 250000, base_time + timedelta(minutes=10)
        )
        
        position = FOOMTestScenarios.create_position(symbol, entry_price)
        
        return {
            'name': 'Volume Spike + Price Stall',
            'symbol': symbol,
            'bars': bars,
            'current_bar': current_bar,
            'position': position,
            'expected_exit': True,
            'expected_reason': 'fomo_exhaustion'
        }
    
    @staticmethod
    def scenario_insufficient_profit() -> Dict[str, Any]:
        """
        Scenario 2: FOMO conditions met but insufficient profit (should NOT trigger)
        """
        symbol = "TEST2"
        entry_price = 10.00
        current_price = 10.20  # Only 2% profit (< 3% minimum)
        
        base_time = datetime.now() - timedelta(minutes=15)
        bars = []
        
        # Normal volume bars
        for i in range(9):
            price = entry_price + (i * 0.02)
            volume = 100000
            bars.append(FOOMTestScenarios.create_market_data(
                symbol, price, volume, base_time + timedelta(minutes=i)
            ))
        
        # Volume spike but insufficient profit
        current_bar = FOOMTestScenarios.create_market_data(
            symbol, current_price, 300000, base_time + timedelta(minutes=10)
        )
        
        position = FOOMTestScenarios.create_position(symbol, entry_price)
        
        return {
            'name': 'Insufficient Profit (2%)',
            'symbol': symbol,
            'bars': bars,
            'current_bar': current_bar,
            'position': position,
            'expected_exit': False,
            'expected_reason': None
        }
    
    @staticmethod
    def scenario_velocity_decay() -> Dict[str, Any]:
        """
        Scenario 3: Price velocity decay (should trigger FOMO exit)
        """
        symbol = "TEST3"
        entry_price = 10.00
        
        base_time = datetime.now() - timedelta(minutes=15)
        bars = []
        
        # Strong momentum initially, then decay
        prices = [10.0, 10.3, 10.7, 11.2, 11.8, 12.2, 12.4, 12.5, 12.5, 12.5]  # Decelerating
        
        for i, price in enumerate(prices):
            volume = 120000  # Consistent volume
            bars.append(FOOMTestScenarios.create_market_data(
                symbol, price, volume, base_time + timedelta(minutes=i)
            ))
        
        current_price = 12.6  # 26% profit, slight move up
        current_bar = FOOMTestScenarios.create_market_data(
            symbol, current_price, 150000, base_time + timedelta(minutes=10)
        )
        
        position = FOOMTestScenarios.create_position(symbol, entry_price)
        
        return {
            'name': 'Velocity Decay',
            'symbol': symbol,
            'bars': bars,
            'current_bar': current_bar,
            'position': position,
            'expected_exit': True,
            'expected_reason': 'velocity_decay'
        }
    
    @staticmethod
    def scenario_normal_conditions() -> Dict[str, Any]:
        """
        Scenario 4: Normal healthy conditions (should NOT trigger exit)
        """
        symbol = "TEST4"
        entry_price = 10.00
        current_price = 11.50  # 15% profit
        
        base_time = datetime.now() - timedelta(minutes=15)
        bars = []
        
        # Healthy gradual increase
        for i in range(9):
            price = entry_price + (i * 0.15)  # Steady growth
            volume = 100000 + (i * 2000)  # Gradual volume increase
            bars.append(FOOMTestScenarios.create_market_data(
                symbol, price, volume, base_time + timedelta(minutes=i)
            ))
        
        # Current: continued healthy growth
        current_bar = FOOMTestScenarios.create_market_data(
            symbol, current_price, 120000, base_time + timedelta(minutes=10)
        )
        
        position = FOOMTestScenarios.create_position(symbol, entry_price)
        
        return {
            'name': 'Normal Healthy Conditions',
            'symbol': symbol,
            'bars': bars,
            'current_bar': current_bar,
            'position': position,
            'expected_exit': False,
            'expected_reason': None
        }
    
    @staticmethod
    def scenario_parabolic_exhaustion() -> Dict[str, Any]:
        """
        Scenario 5: Parabolic move with exhaustion signals
        """
        symbol = "TEST5"
        entry_price = 10.00
        
        base_time = datetime.now() - timedelta(minutes=15)
        bars = []
        
        # Parabolic acceleration then exhaustion
        prices = [10.0, 10.5, 11.2, 12.1, 13.5, 15.2, 17.1, 18.5, 19.2, 19.3]  # Parabolic then stall
        volumes = [100000, 120000, 150000, 200000, 300000, 450000, 600000, 400000, 200000, 150000]  # Volume climax then decline
        
        for i, (price, volume) in enumerate(zip(prices, volumes)):
            bars.append(FOOMTestScenarios.create_market_data(
                symbol, price, volume, base_time + timedelta(minutes=i)
            ))
        
        current_price = 19.4  # 94% profit, tiny move up
        current_bar = FOOMTestScenarios.create_market_data(
            symbol, current_price, 180000, base_time + timedelta(minutes=10)
        )
        
        position = FOOMTestScenarios.create_position(symbol, entry_price)
        
        return {
            'name': 'Parabolic Exhaustion',
            'symbol': symbol,
            'bars': bars,
            'current_bar': current_bar,
            'position': position,
            'expected_exit': True,
            'expected_reason': 'parabolic_exhaustion'
        }

class FOOMExitTester:
    """Main testing class for FOMO exit system"""
    
    def __init__(self):
        self.strategy = None
        self.test_results = []
        
    async def setup_strategy(self):
        """Initialize the ML strategy engine"""
        try:
            # Create minimal config for testing
            config = {
                'general': {
                    'default_symbols': 'TEST1,TEST2,TEST3,TEST4,TEST5',
                    'log_level': 'DEBUG'
                },
                'ml_multi_strategy': {
                    'confidence_threshold': 0.1,
                    'log_level': 'DEBUG'
                }
            }
            
            self.strategy = MLMultiStrategyEngine(config)
            await self.strategy.initialize()
            logger.info("✅ Strategy initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize strategy: {e}")
            raise
    
    async def run_scenario_test(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test scenario"""
        logger.info(f"\n🧪 Testing scenario: {scenario['name']}")
        logger.info(f"Symbol: {scenario['symbol']}")
        logger.info(f"Expected exit: {scenario['expected_exit']}")
        
        try:
            # Setup bars history
            symbol = scenario['symbol']
            self.strategy.bars_history[symbol] = scenario['bars']
            
            # Calculate profit percentage
            position = scenario['position']
            current_price = scenario['current_bar'].close
            profit_pct = (current_price - position.avg_price) / position.avg_price
            
            logger.info(f"Entry: ${position.avg_price:.2f}, Current: ${current_price:.2f}, Profit: {profit_pct:.1%}")
            
            # Test FOMO exhaustion detection
            result = await self.strategy._check_fomo_exhaustion(
                symbol, 
                scenario['current_bar'], 
                position, 
                profit_pct
            )
            
            # Analyze result
            got_exit = result is not None
            exit_reason = result.metadata.get('reason') if result else None
            
            success = got_exit == scenario['expected_exit']
            
            test_result = {
                'scenario': scenario['name'],
                'symbol': symbol,
                'expected_exit': scenario['expected_exit'],
                'got_exit': got_exit,
                'exit_reason': exit_reason,
                'expected_reason': scenario['expected_reason'],
                'profit_pct': profit_pct,
                'success': success,
                'details': result.metadata if result else None
            }
            
            # Log result
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"{status} - Expected: {scenario['expected_exit']}, Got: {got_exit}")
            if result:
                logger.info(f"Exit reason: {exit_reason}")
                logger.info(f"Signal details: {result.metadata}")
            
            return test_result
            
        except Exception as e:
            logger.error(f"❌ Error in scenario {scenario['name']}: {e}")
            return {
                'scenario': scenario['name'],
                'symbol': scenario['symbol'],
                'error': str(e),
                'success': False
            }
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        logger.info("🚀 Starting comprehensive FOMO exit tests\n")
        
        # Get all scenarios
        scenarios = [
            FOOMTestScenarios.scenario_volume_spike_price_stall(),
            FOOMTestScenarios.scenario_insufficient_profit(),
            FOOMTestScenarios.scenario_velocity_decay(),
            FOOMTestScenarios.scenario_normal_conditions(),
            FOOMTestScenarios.scenario_parabolic_exhaustion()
        ]
        
        # Initialize strategy
        await self.setup_strategy()
        
        # Run each scenario
        for scenario in scenarios:
            result = await self.run_scenario_test(scenario)
            self.test_results.append(result)
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("\n" + "="*80)
        logger.info("📊 FOMO EXIT SYSTEM TEST REPORT")
        logger.info("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.get('success', False))
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests} ✅")
        logger.info(f"Failed: {failed_tests} ❌")
        logger.info(f"Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        logger.info("\n📋 DETAILED RESULTS:")
        for i, result in enumerate(self.test_results, 1):
            status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
            logger.info(f"\n{i}. {result['scenario']} - {status}")
            logger.info(f"   Symbol: {result['symbol']}")
            
            if 'error' in result:
                logger.error(f"   Error: {result['error']}")
            else:
                logger.info(f"   Expected Exit: {result['expected_exit']}")
                logger.info(f"   Got Exit: {result['got_exit']}")
                logger.info(f"   Profit: {result['profit_pct']:.1%}")
                if result['got_exit']:
                    logger.info(f"   Exit Reason: {result['exit_reason']}")
        
        # Analysis and recommendations
        logger.info(f"\n🔍 ANALYSIS:")
        
        # Check for specific failure patterns
        false_negatives = [r for r in self.test_results if r.get('expected_exit') and not r.get('got_exit')]
        false_positives = [r for r in self.test_results if not r.get('expected_exit') and r.get('got_exit')]
        
        if false_negatives:
            logger.warning(f"⚠️  False Negatives (should exit but didn't): {len(false_negatives)}")
            for fn in false_negatives:
                logger.warning(f"   - {fn['scenario']}: Expected {fn['expected_reason']} exit")
        
        if false_positives:
            logger.warning(f"⚠️  False Positives (shouldn't exit but did): {len(false_positives)}")
            for fp in false_positives:
                logger.warning(f"   - {fp['scenario']}: Unexpected {fp['exit_reason']} exit")
        
        # Recommendations
        logger.info(f"\n💡 RECOMMENDATIONS:")
        if failed_tests == 0:
            logger.info("🎉 All tests passed! FOMO exit system is working correctly.")
        else:
            if false_negatives:
                logger.info("🔧 Consider relaxing FOMO detection thresholds:")
                logger.info("   - Lower volume spike threshold (currently 2.5x)")
                logger.info("   - Lower minimum profit requirement (currently 3%)")
                logger.info("   - Adjust velocity decay sensitivity")
            
            if false_positives:
                logger.info("🔧 Consider tightening FOMO detection thresholds:")
                logger.info("   - Higher volume spike threshold")
                logger.info("   - Higher minimum profit requirement")
                logger.info("   - Stricter price stall detection")
        
        logger.info("\n" + "="*80)

async def main():
    """Main test function"""
    tester = FOOMExitTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())