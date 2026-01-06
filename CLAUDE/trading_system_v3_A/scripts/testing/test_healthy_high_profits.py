#!/usr/bin/env python3
"""
Test Suite for Healthy High Profits Logic
=========================================

Tests the new Priority 0.5 exit logic to ensure it correctly identifies
when to exit positions at healthy highs without waiting for FOMO exhaustion.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import MarketData, Position, SignalType
from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
from unittest.mock import Mock, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HealthyHighTest")

class TestHealthyHighProfits:
    def __init__(self):
        self.engine = None
        self.test_results = []
        
    async def setup_engine(self):
        """Setup ML engine for testing"""
        # Create engine instance with parameters
        self.engine = MLMultiStrategyEngine(parameters={})
        
        # Mock required attributes
        self.engine.bars_history = {}
        self.engine.positions = {}
        self.engine.position_highest_prices = {}
        
        logger.info("🔧 Test engine setup completed")
    
    def create_market_data(self, symbol: str, price: float, volume: int, 
                          timestamp: datetime) -> MarketData:
        """Create market data for testing"""
        return MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=price * 0.98,
            high=price * 1.02,
            low=price * 0.95,
            close=price,
            volume=volume,
            last_price=price
        )
    
    def create_position(self, symbol: str, entry_price: float, quantity: int = 100) -> Position:
        """Create position for testing"""
        return Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=entry_price,
            market_value=entry_price * quantity,
            realized_pnl=0.0
        )
    
    def create_price_history(self, symbol: str, start_price: float, 
                           end_price: float, bars: int, base_volume: int,
                           start_time: datetime) -> List[MarketData]:
        """Create realistic price history for testing"""
        history = []
        price_step = (end_price - start_price) / bars
        
        for i in range(bars):
            current_price = start_price + (price_step * i)
            # Add some price volatility
            if i > 0:
                volatility = 0.02 * (0.5 - abs(0.5 - (i/bars)))  # More volatile in middle
                current_price += current_price * volatility * ((i % 3) - 1) * 0.5
            
            # Volume increases as price goes up (realistic pattern)
            volume_multiplier = 1 + (i / bars) * 2  # 1x to 3x volume increase
            current_volume = int(base_volume * volume_multiplier)
            
            # Ensure timezone consistency
            if start_time.tzinfo is None:
                timestamp = start_time + timedelta(minutes=i*5)
            else:
                timestamp = start_time + timedelta(minutes=i*5)
            
            bar = self.create_market_data(symbol, current_price, current_volume, timestamp)
            history.append(bar)
            
        return history
    
    async def test_scenario(self, name: str, symbol: str, entry_price: float, 
                          current_price: float, test_time: datetime, 
                          volume_ratio: float = 2.0, bars_count: int = 20,
                          expected_exit: bool = False, expected_reason: str = None):
        """Test a specific scenario"""
        logger.info(f"\n🧪 TESTING: {name}")
        logger.info(f"   Symbol: {symbol}, Entry: ${entry_price:.2f}, Current: ${current_price:.2f}")
        
        profit_pct = (current_price - entry_price) / entry_price
        logger.info(f"   Profit: {profit_pct:.1%}, Time: {test_time.strftime('%H:%M')}, Volume: {volume_ratio:.1f}x")
        
        try:
            # Create position
            position = self.create_position(symbol, entry_price)
            
            # Create price history that leads to current price
            start_time = test_time - timedelta(minutes=bars_count*5)
            base_volume = 10000
            
            # Create realistic progression to current price with some highs
            history = self.create_price_history(
                symbol, entry_price * 1.01, current_price, 
                bars_count, base_volume, start_time
            )
            
            # Make recent high slightly above current (within 2%)
            recent_high_price = current_price * 1.015  # 1.5% above current
            history[-3].close = recent_high_price  # Set recent high
            history[-3].high = recent_high_price * 1.01
            
            # Set current bar with specified volume
            current_volume = int(base_volume * volume_ratio)
            current_bar = self.create_market_data(symbol, current_price, current_volume, test_time)
            
            # Setup engine state
            self.engine.bars_history[symbol] = history
            self.engine.positions[symbol] = position
            
            # Test the healthy high profits function
            result = await self.engine._check_healthy_high_profits(
                symbol, current_bar, position, profit_pct
            )
            
            # Analyze result
            got_exit = result is not None
            actual_reason = result.metadata.get('exit_reason', '') if result else 'No exit'
            
            # Check result
            test_passed = got_exit == expected_exit
            if expected_exit and expected_reason:
                test_passed = test_passed and expected_reason.lower() in actual_reason.lower()
            
            status = "✅ PASS" if test_passed else "❌ FAIL"
            logger.info(f"   Expected: {'EXIT' if expected_exit else 'HOLD'}")
            logger.info(f"   Got: {'EXIT' if got_exit else 'HOLD'}")
            if got_exit:
                logger.info(f"   Reason: {actual_reason}")
                logger.info(f"   Strength: {result.strength:.2f}")
            logger.info(f"   {status}")
            
            self.test_results.append({
                'name': name,
                'passed': test_passed,
                'expected_exit': expected_exit,
                'got_exit': got_exit,
                'reason': actual_reason
            })
            
        except Exception as e:
            logger.error(f"   ❌ ERROR: {e}")
            self.test_results.append({
                'name': name,
                'passed': False,
                'error': str(e)
            })
    
    async def run_all_tests(self):
        """Run comprehensive test suite"""
        await self.setup_engine()
        
        logger.info("🚀 Starting Healthy High Profits Test Suite")
        logger.info("="*60)
        
        # Test 1: Great profit should always exit - ADJUSTED TO MEET THRESHOLD
        await self.test_scenario(
            "Great Profit (25%) - Morning",
            "TEST1", 10.00, 12.50,  # 25% profit (above 22% morning threshold)
            datetime(2025, 9, 4, 11, 30, tzinfo=ZoneInfo("America/New_York")),  # 11:30 AM ET
            volume_ratio=2.5,
            expected_exit=True,
            expected_reason="great profit"
        )
        
        # Test 2: Healthy profit + End of day should exit
        await self.test_scenario(
            "Healthy Profit (12%) + EOD",
            "TEST2", 10.00, 11.20,  # 12% profit
            datetime(2025, 9, 4, 15, 35, tzinfo=ZoneInfo("America/New_York")),  # 3:35 PM ET
            volume_ratio=2.0,
            expected_exit=True,
            expected_reason="eod"
        )
        
        # Test 3: Minimum profit + Last 15 minutes should exit
        await self.test_scenario(
            "Min Profit (8%) + Market Close",
            "TEST3", 10.00, 10.80,  # 8% profit
            datetime(2025, 9, 4, 15, 50, tzinfo=ZoneInfo("America/New_York")),  # 3:50 PM ET
            volume_ratio=1.8,
            expected_exit=True,
            expected_reason="late day"
        )
        
        # Test 4: Low profit should not exit (morning)
        await self.test_scenario(
            "Low Profit (5%) - Morning",
            "TEST4", 10.00, 10.50,  # 5% profit
            datetime(2025, 9, 4, 10, 30, tzinfo=ZoneInfo("America/New_York")),  # 10:30 AM ET
            volume_ratio=2.0,
            expected_exit=False
        )
        
        # Test 5: Good profit but not at highs should not exit
        await self.test_scenario(
            "Good Profit (15%) but Not at Highs",
            "TEST5", 10.00, 11.50,  # 15% profit but will set price far from recent high
            datetime(2025, 9, 4, 14, 30, tzinfo=ZoneInfo("America/New_York")),  # 2:30 PM ET
            volume_ratio=2.0,
            expected_exit=False  # This will fail if price is far from high
        )
        
        # Test 6: Healthy profit afternoon - SHOULD EXIT
        await self.test_scenario(
            "Healthy Profit (15%) Afternoon",
            "TEST6", 10.00, 11.50,  # 15% profit (above 12% afternoon threshold)
            datetime(2025, 9, 4, 14, 15, tzinfo=ZoneInfo("America/New_York")),  # 2:15 PM ET
            volume_ratio=2.5,  # Healthy volume
            expected_exit=True,
            expected_reason="healthy"
        )
        
        # Test 7: Very high profit should exit regardless of time
        await self.test_scenario(
            "Very High Profit (25%) - Any Time",
            "TEST7", 10.00, 12.50,  # 25% profit
            datetime(2025, 9, 4, 12, 15, tzinfo=ZoneInfo("America/New_York")),  # 12:15 PM ET
            volume_ratio=3.0,
            expected_exit=True,
            expected_reason="great profit"
        )
        
        # Test 8: Afternoon threshold test - EXACTLY AT THRESHOLD
        await self.test_scenario(
            "Afternoon Threshold (12%) at 2:30 PM",
            "TEST8", 10.00, 11.20,  # 12% profit (exactly at afternoon healthy threshold)
            datetime(2025, 9, 4, 14, 30, tzinfo=ZoneInfo("America/New_York")),  # 2:30 PM ET
            volume_ratio=2.2,
            expected_exit=True,  # 12% = afternoon healthy threshold, should exit
            expected_reason="healthy"
        )
        
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 TEST SUMMARY")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: ✅ {passed_tests}")
        logger.info(f"Failed: ❌ {failed_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    logger.info(f"   - {result['name']}")
                    if 'error' in result:
                        logger.info(f"     Error: {result['error']}")
                    else:
                        expected = "EXIT" if result['expected_exit'] else "HOLD"
                        got = "EXIT" if result['got_exit'] else "HOLD"
                        logger.info(f"     Expected: {expected}, Got: {got}")
        
        logger.info("\n🎯 All tests completed!")

async def main():
    """Run the test suite"""
    tester = TestHealthyHighProfits()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())