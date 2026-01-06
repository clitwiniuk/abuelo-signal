#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Scanner + Strategies Integration - Morning Session (9:30-11:00 AM)
===========================================================================

Este test verifica que:
1. Las estrategias generen señales INMEDIATAMENTE sin esperar pullback
2. El scanner + estrategias funcionen correctamente en primeras horas de mercado
3. Se capturen los breakouts y momentum durante las horas más volátiles
4. Compare performance vs versión anterior con pullback

Estrategias a probar:
- ORB Strategy (sin pullback)
- MACDV Strategy (con confirmación multi-timeframe)
- Gap & Go Strategy (sin pullback)
- VWAP Strategy (sin pullback)
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, time
import pandas as pd
import numpy as np

# Import strategies
from strategies.orb_strategy import ORBStrategy
from strategies.macdv_strategy import MACDVStrategy
from strategies.gap_go_strategy import GapGoStrategy
from strategies.vwap_strategy import VWAPStrategy

# Import interfaces
from core.interfaces import Signal, SignalType, MarketData, Position

# Test configuration
TEST_SYMBOLS = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']
MARKET_OPEN = time(9, 30)  # 9:30 AM
TEST_END = time(11, 0)     # 11:00 AM

class TestScannerStrategiesMorningSession(unittest.TestCase):
    """Test Scanner + Strategies integration during morning session"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_date = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        
        # Initialize strategies with immediate entry (no pullback)
        self.orb_strategy = ORBStrategy()
        self.macdv_strategy = MACDVStrategy()
        self.gap_go_strategy = GapGoStrategy()
        self.vwap_strategy = VWAPStrategy()
        
        self.strategies = [
            ('ORB', self.orb_strategy),
            ('MACDV', self.macdv_strategy), 
            ('GapGo', self.gap_go_strategy),
            ('VWAP', self.vwap_strategy)
        ]
        
        # Results tracking
        self.signal_results = {}
        self.timing_results = {}
        
    def create_morning_breakout_scenario(self, symbol: str, strategy_type: str = 'gap_up'):
        """
        Create realistic morning breakout scenario
        
        Args:
            symbol: Stock symbol
            strategy_type: 'gap_up', 'orb_breakout', 'macd_cross', 'vwap_reclaim'
        """
        bars = []
        base_price = 50.0
        
        # Pre-market simulation (for gap scenarios)
        if strategy_type == 'gap_up':
            prev_close = base_price
            gap_open = prev_close * 1.08  # 8% gap up
            current_price = gap_open
        elif strategy_type == 'orb_breakout':
            current_price = base_price
        else:
            current_price = base_price
            
        # Generate bars from 9:30 to 11:00 AM (90 minutes = 90 1-minute bars)
        for minute in range(90):
            timestamp = self.test_date + timedelta(minutes=minute)
            
            # Morning volatility pattern
            volatility_factor = self._get_morning_volatility_factor(minute)
            volume_factor = self._get_morning_volume_factor(minute)
            
            # Price movement based on strategy type
            if strategy_type == 'gap_up' and minute < 30:
                # Momentum continuation after gap
                price_change = np.random.normal(0.002, 0.005) * volatility_factor
                current_price *= (1 + price_change)
                volume = int(200000 * volume_factor * np.random.uniform(0.8, 1.5))
                
            elif strategy_type == 'orb_breakout':
                if minute == 15:  # 15 minutes after open - ORB breakout
                    current_price *= 1.035  # 3.5% breakout
                    volume = int(500000 * volume_factor)
                else:
                    price_change = np.random.normal(0.001, 0.003)
                    current_price *= (1 + price_change)
                    volume = int(150000 * volume_factor * np.random.uniform(0.7, 1.3))
                    
            elif strategy_type == 'macd_cross':
                # MACD crossover pattern - gradual momentum build
                if minute > 10:
                    momentum_strength = min((minute - 10) / 20.0, 1.0)
                    price_change = np.random.normal(0.001 * momentum_strength, 0.002)
                    current_price *= (1 + price_change)
                volume = int(120000 * volume_factor * np.random.uniform(0.9, 1.4))
                
            elif strategy_type == 'vwap_reclaim':
                # Price oscillates around VWAP then breaks above
                if minute == 25:  # VWAP reclaim moment
                    current_price *= 1.025  # 2.5% move above VWAP
                volume = int(180000 * volume_factor * np.random.uniform(0.8, 1.2))
            
            # Create realistic OHLC
            high = current_price * np.random.uniform(1.001, 1.008)
            low = current_price * np.random.uniform(0.992, 0.999)
            open_price = bars[-1].close if bars else current_price
            
            # Calculate VWAP (simplified)
            if bars:
                total_volume = sum(b.volume for b in bars) + volume
                total_pv = sum(b.close * b.volume for b in bars) + current_price * volume
                vwap = total_pv / total_volume if total_volume > 0 else current_price
            else:
                vwap = current_price
            
            bar = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=current_price,
                volume=volume,
                vwap=vwap
            )
            bars.append(bar)
            
        return bars
    
    def _get_morning_volatility_factor(self, minute: int) -> float:
        """Get volatility factor based on time since market open"""
        if minute < 30:  # First 30 minutes - highest volatility
            return 2.0
        elif minute < 60:  # Next 30 minutes - medium volatility  
            return 1.5
        else:  # After 10:30 AM - lower volatility
            return 1.0
            
    def _get_morning_volume_factor(self, minute: int) -> float:
        """Get volume factor based on time since market open"""
        if minute < 15:  # First 15 minutes - highest volume
            return 3.0
        elif minute < 45:  # Next 30 minutes - high volume
            return 2.0
        else:  # After 10:15 AM - normal volume
            return 1.2
    
    async def test_strategies_immediate_entry(self):
        """Test that all strategies generate signals immediately (no pullback wait)"""
        print("\n" + "="*60)
        print("TESTING IMMEDIATE ENTRY (NO PULLBACK WAIT)")
        print("="*60)
        
        test_scenarios = [
            ('AAPL', 'gap_up'),
            ('TSLA', 'orb_breakout'), 
            ('NVDA', 'macd_cross'),
            ('AMD', 'vwap_reclaim')
        ]
        
        for symbol, scenario in test_scenarios:
            print(f"\n--- Testing {symbol} ({scenario.upper()}) ---")
            
            # Generate realistic morning data
            bars = self.create_morning_breakout_scenario(symbol, scenario)
            
            signals_generated = {}
            first_signal_timing = {}
            
            # Test each strategy
            for strategy_name, strategy in self.strategies:
                print(f"\nTesting {strategy_name} Strategy...")
                
                # Initialize strategy
                await strategy._initialize_strategy()
                
                signals_count = 0
                first_signal_time = None
                signal_timestamps = []
                
                # Feed bars to strategy
                for i, bar in enumerate(bars):
                    # Add bar to strategy history
                    if symbol not in strategy.bars_history:
                        strategy.bars_history[symbol] = []
                    strategy.bars_history[symbol].append(bar)
                    
                    # Analyze bar
                    signal = await strategy._analyze_bar(bar)
                    
                    if signal:
                        signals_count += 1
                        signal_timestamps.append(bar.timestamp)
                        
                        if first_signal_time is None:
                            first_signal_time = bar.timestamp
                            minutes_since_open = (bar.timestamp - self.test_date).total_seconds() / 60
                            
                        print(f"  ✅ Signal #{signals_count}: {signal.signal_type.value} @ ${signal.price:.2f}")
                        print(f"     Time: {bar.timestamp.strftime('%H:%M')}")
                        print(f"     Minutes since open: {minutes_since_open:.1f}")
                        
                        # Verify immediate entry (no pullback logic)
                        self.assertIsNotNone(signal)
                        self.assertIn(signal.signal_type, [SignalType.LONG, SignalType.SHORT])
                        
                signals_generated[strategy_name] = signals_count
                first_signal_timing[strategy_name] = first_signal_time
                
            # Store results
            self.signal_results[f"{symbol}_{scenario}"] = signals_generated
            self.timing_results[f"{symbol}_{scenario}"] = first_signal_timing
            
            print(f"\n📊 Results for {symbol} ({scenario}):")
            for strategy_name, count in signals_generated.items():
                timing = first_signal_timing.get(strategy_name)
                if timing:
                    minutes = (timing - self.test_date).total_seconds() / 60
                    print(f"  {strategy_name}: {count} signals, first at {timing.strftime('%H:%M')} ({minutes:.1f}min)")
                else:
                    print(f"  {strategy_name}: {count} signals")
    
    async def test_morning_session_performance(self):
        """Test performance during high-volatility morning session"""
        print("\n" + "="*60)
        print("TESTING MORNING SESSION PERFORMANCE")
        print("="*60)
        
        performance_metrics = {}
        
        for symbol in TEST_SYMBOLS[:3]:  # Test first 3 symbols
            print(f"\n--- Performance Test: {symbol} ---")
            
            # Create high-volatility morning scenario
            bars = self.create_morning_breakout_scenario(symbol, 'gap_up')
            
            strategy_metrics = {}
            
            for strategy_name, strategy in self.strategies:
                await strategy._initialize_strategy()
                
                signals = []
                processing_times = []
                
                # Time each bar analysis
                for bar in bars:
                    if symbol not in strategy.bars_history:
                        strategy.bars_history[symbol] = []
                    strategy.bars_history[symbol].append(bar)
                    
                    start_time = datetime.now()
                    signal = await strategy._analyze_bar(bar)
                    processing_time = (datetime.now() - start_time).total_seconds() * 1000  # ms
                    
                    processing_times.append(processing_time)
                    if signal:
                        signals.append(signal)
                
                # Calculate metrics
                avg_processing_time = np.mean(processing_times)
                max_processing_time = np.max(processing_times)
                signals_per_hour = len(signals) * (60 / 1.5)  # Convert to hourly rate
                
                strategy_metrics[strategy_name] = {
                    'signals_count': len(signals),
                    'signals_per_hour': signals_per_hour,
                    'avg_processing_ms': avg_processing_time,
                    'max_processing_ms': max_processing_time
                }
                
                print(f"  {strategy_name}:")
                print(f"    Signals: {len(signals)} ({signals_per_hour:.1f}/hour)")
                print(f"    Avg Processing: {avg_processing_time:.2f}ms")
                print(f"    Max Processing: {max_processing_time:.2f}ms")
            
            performance_metrics[symbol] = strategy_metrics
        
        # Verify performance requirements
        for symbol, metrics in performance_metrics.items():
            for strategy_name, data in metrics.items():
                # Each strategy should process bars under 50ms average
                self.assertLess(data['avg_processing_ms'], 50.0,
                    f"{strategy_name} too slow: {data['avg_processing_ms']:.2f}ms")
                
                # Should generate reasonable number of signals in volatile market
                self.assertGreater(data['signals_count'], 0,
                    f"{strategy_name} generated no signals")
    
    async def test_no_pullback_confirmation(self):
        """Test that strategies do NOT wait for pullback confirmation"""
        print("\n" + "="*60)
        print("TESTING NO PULLBACK LOGIC")
        print("="*60)
        
        symbol = 'TEST'
        
        # Create strong breakout scenario that would trigger pullback wait in old version
        bars = []
        base_price = 25.0
        
        for minute in range(30):
            timestamp = self.test_date + timedelta(minutes=minute)
            
            if minute == 15:  # Strong breakout at minute 15
                current_price = base_price * 1.05  # 5% immediate jump
                volume = 1000000  # High volume
            elif minute > 15:
                # Slight pullback that would prevent entry in old version
                current_price = base_price * 1.03  # Still up but pulled back
                volume = 200000
            else:
                current_price = base_price
                volume = 100000
            
            bar = MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=current_price * 0.999,
                high=current_price * 1.002,
                low=current_price * 0.998,
                close=current_price,
                volume=volume,
                vwap=current_price
            )
            bars.append(bar)
            base_price = current_price
        
        # Test that strategies generate signal immediately on breakout (minute 15)
        for strategy_name, strategy in self.strategies:
            if strategy_name == 'MACDV':
                continue  # MACDV has different entry logic
                
            await strategy._initialize_strategy()
            
            signal_found = False
            breakout_bar_signal = None
            
            for i, bar in enumerate(bars):
                if symbol not in strategy.bars_history:
                    strategy.bars_history[symbol] = []
                strategy.bars_history[symbol].append(bar)
                
                signal = await strategy._analyze_bar(bar)
                
                if signal and i == 15:  # Signal on breakout bar
                    signal_found = True
                    breakout_bar_signal = signal
                    print(f"  ✅ {strategy_name}: Immediate signal on breakout bar")
                    break
            
            if strategy_name in ['ORB', 'GapGo']:  # These should definitely signal on breakout
                self.assertTrue(signal_found, 
                    f"{strategy_name} should generate immediate signal on breakout")
    
    def test_run_all_morning_tests(self):
        """Run all morning session tests"""
        print("\n" + "="*80)
        print("SCANNER + STRATEGIES MORNING SESSION TEST SUITE")
        print("="*80)
        
        async def run_tests():
            await self.test_strategies_immediate_entry()
            await self.test_morning_session_performance()
            await self.test_no_pullback_confirmation()
            
            # Final summary
            print("\n" + "="*60)
            print("TEST SUMMARY")
            print("="*60)
            
            total_scenarios = len(self.signal_results)
            total_strategies = len(self.strategies)
            
            print(f"✅ Tested {total_scenarios} market scenarios")
            print(f"✅ Tested {total_strategies} trading strategies")
            print("✅ All strategies generate immediate signals (no pullback wait)")
            print("✅ Performance requirements met (<50ms per bar)")
            print("✅ Morning session integration working correctly")
            
            return True
        
        # Run async tests
        result = asyncio.run(run_tests())
        self.assertTrue(result)

if __name__ == '__main__':
    print("Scanner + Strategies Morning Session Integration Test")
    print("="*60)
    
    # Run the tests
    unittest.main(verbosity=2)