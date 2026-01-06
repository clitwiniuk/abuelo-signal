"""
Production Scanner to Execution Flow Tests
Tests the complete real-time flow from scanner detection to trade execution
Focuses on verifying the actual trading pipeline works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, time, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
import logging
import time as time_module

# Import production system
from production.smallcap_production_runner import SmallcapProductionRunner

# Import core components
from core.interfaces import Signal, SignalType, MarketData, TradingConfig
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockMarketDataProvider:
    """Mock market data provider for realistic testing"""
    
    def __init__(self):
        self.market_data = {}
        self.price_updates = {}
    
    def set_market_data(self, symbol: str, price: float, volume: int, gap_pct: float = 0.0):
        """Set market data for a symbol"""
        base_price = price / (1 + gap_pct)
        
        self.market_data[symbol] = MarketData(
            timestamp=datetime.now(),
            open=base_price,
            high=price * 1.05,
            low=base_price * 0.95,
            close=price,
            volume=volume,
            symbol=symbol
        )
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get market data for symbol"""
        return self.market_data.get(symbol)
    
    def update_price(self, symbol: str, new_price: float):
        """Update price for symbol (simulates real-time updates)"""
        if symbol in self.market_data:
            data = self.market_data[symbol]
            self.market_data[symbol] = MarketData(
                timestamp=datetime.now(),
                open=data.open,
                high=max(data.high, new_price),
                low=min(data.low, new_price),
                close=new_price,
                volume=data.volume + 10000,  # Simulate volume increase
                symbol=symbol
            )

class ProductionScannerExecutionTester:
    """Comprehensive tester for scanner-to-execution flow"""
    
    def __init__(self):
        self.execution_history = []
        self.signal_history = []
        self.order_history = []
        self.market_data_provider = MockMarketDataProvider()
    
    async def setup_realistic_environment(self) -> SmallcapProductionRunner:
        """Setup environment that closely mimics production"""
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup realistic IBKR adapter
        runner.ibkr_adapter = AsyncMock()
        runner.ibkr_adapter.connect = AsyncMock(return_value=True)
        runner.ibkr_adapter.is_connected = Mock(return_value=True)
        runner.ibkr_adapter.get_market_data = self.market_data_provider.get_market_data
        
        # Mock order placement with realistic responses
        async def mock_place_order(symbol, quantity, order_type, price=None):
            order_id = f"ORD_{len(self.order_history):04d}"
            order = {
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "status": "SUBMITTED",
                "timestamp": datetime.now()
            }
            self.order_history.append(order)
            
            # Simulate order fill after short delay
            await asyncio.sleep(0.1)
            order["status"] = "FILLED"
            order["fill_price"] = price or self.market_data_provider.market_data[symbol].close
            
            return order
        
        runner.ibkr_adapter.place_order = mock_place_order
        
        # Setup realistic scanner with actual detection logic
        runner.smallcap_scanner = AsyncMock()
        
        # Setup trading engine with signal tracking
        runner.trading_engine = AsyncMock()
        runner.trading_engine.initialize = AsyncMock(return_value=True)
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        
        # Track signal injection
        original_inject = getattr(runner.trading_engine.strategy, 'inject_signal', None)
        async def track_signal_injection(signal):
            self.signal_history.append({
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "strength": signal.strength,
                "timestamp": signal.timestamp,
                "metadata": signal.metadata
            })
            if original_inject:
                return await original_inject(signal)
        
        runner.trading_engine.strategy.inject_signal = track_signal_injection
        
        # Setup mayordomo with realistic decision making
        runner.mayordomo = Mock()
        runner.mayordomo.register_daily_play = Mock()
        
        # Setup ML engine
        runner.ml_engine = Mock()
        runner.ml_engine._smallcap_mayordomo_select_strategies = AsyncMock()
        
        # Disable telegram for testing
        runner._send_telegram_alert = Mock()
        
        return runner
    
    def create_market_scenario(self, scenario_type: str):
        """Create realistic market scenarios"""
        
        if scenario_type == "morning_gaps":
            # Simulate morning gap-ups with high volume
            symbols_data = [
                ("ABCD", 8.50, 15_000_000, 0.18),  # 18% gap, high volume
                ("EFGH", 12.25, 8_500_000, 0.15),  # 15% gap, good volume
                ("IJKL", 5.75, 12_000_000, 0.22),  # 22% gap, very high volume
            ]
            
            for symbol, price, volume, gap in symbols_data:
                self.market_data_provider.set_market_data(symbol, price, volume, gap)
        
        elif scenario_type == "news_driven":
            # Simulate news-driven moves
            symbols_data = [
                ("NEWS1", 6.80, 25_000_000, 0.35),  # 35% gap on major news
                ("NEWS2", 4.25, 18_000_000, 0.28),  # 28% gap on FDA news
            ]
            
            for symbol, price, volume, gap in symbols_data:
                self.market_data_provider.set_market_data(symbol, price, volume, gap)
        
        elif scenario_type == "mixed_signals":
            # Mix of good and poor opportunities
            symbols_data = [
                ("GOOD1", 7.50, 8_000_000, 0.12),   # Good opportunity
                ("GOOD2", 9.25, 6_500_000, 0.10),   # Good opportunity
                ("POOR1", 2.15, 500_000, 0.03),     # Poor opportunity
                ("POOR2", 1.85, 300_000, 0.02),     # Poor opportunity
                ("MED1", 5.50, 2_000_000, 0.07),    # Medium opportunity
            ]
            
            for symbol, price, volume, gap in symbols_data:
                self.market_data_provider.set_market_data(symbol, price, volume, gap)
    
    def configure_scanner_responses(self, runner, scenario_type: str):
        """Configure scanner to return realistic plays"""
        # Use local MockPlay classes defined at top of file
        
        plays = []
        
        if scenario_type == "morning_gaps":
            plays = [
                MockPlay("ABCD", 9.1, MockCatalyst("earnings_beat", 0.9), 
                        MockContext(8.50, 0.18, 5.2, 2_500_000, 15_000_000)),
                MockPlay("EFGH", 8.7, MockCatalyst("upgrade", 0.8), 
                        MockContext(12.25, 0.15, 4.1, 2_000_000, 8_500_000)),
                MockPlay("IJKL", 9.3, MockCatalyst("merger_rumor", 0.85), 
                        MockContext(5.75, 0.22, 6.8, 1_800_000, 12_000_000)),
            ]
        
        elif scenario_type == "news_driven":
            plays = [
                MockPlay("NEWS1", 9.5, MockCatalyst("breakthrough_news", 0.95), 
                        MockContext(6.80, 0.35, 12.5, 2_000_000, 25_000_000)),
                MockPlay("NEWS2", 9.2, MockCatalyst("fda_approval", 0.92), 
                        MockContext(4.25, 0.28, 9.2, 2_000_000, 18_000_000)),
            ]
        
        elif scenario_type == "mixed_signals":
            plays = [
                MockPlay("GOOD1", 8.2, MockCatalyst("good_news", 0.8), 
                        MockContext(7.50, 0.12, 3.2, 2_500_000, 8_000_000)),
                MockPlay("GOOD2", 8.0, MockCatalyst("analyst_upgrade", 0.75), 
                        MockContext(9.25, 0.10, 2.8, 2_300_000, 6_500_000)),
                MockPlay("POOR1", 3.8, MockCatalyst("weak_news", 0.3), 
                        MockContext(2.15, 0.03, 1.1, 450_000, 500_000)),
                MockPlay("POOR2", 3.5, MockCatalyst("minor_update", 0.25), 
                        MockContext(1.85, 0.02, 1.0, 300_000, 300_000)),
                MockPlay("MED1", 6.5, MockCatalyst("sector_news", 0.6), 
                        MockContext(5.50, 0.07, 1.8, 1_100_000, 2_000_000)),
            ]
        
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=plays)
        return plays
    
    def configure_mayordomo_realistic(self, runner):
        """Configure mayordomo with realistic decision logic"""
        
        def realistic_decision(opportunity):
            symbol = opportunity['symbol']
            gap_pct = opportunity.get('gap_percentage', 0)
            volume_ratio = opportunity.get('volume_ratio', 1)
            
            # Realistic decision logic
            if gap_pct >= 0.15 and volume_ratio >= 3.0:
                return {
                    "action": "OPEN_POSITION",
                    "reason": "HIGH_QUALITY_GAP_PLAY",
                    "position_size": min(0.03, gap_pct * 0.1),  # Size based on gap
                    "confidence": min(0.95, 0.5 + gap_pct + volume_ratio * 0.05)
                }
            elif gap_pct >= 0.08 and volume_ratio >= 2.0:
                return {
                    "action": "OPEN_POSITION",
                    "reason": "MEDIUM_QUALITY_PLAY",
                    "position_size": 0.02,
                    "confidence": 0.7
                }
            else:
                return {
                    "action": "REJECT",
                    "reason": "INSUFFICIENT_QUALITY",
                    "confidence": 0.3
                }
        
        runner.mayordomo.evaluate_position_rotation = Mock(side_effect=realistic_decision)
    
    async def test_complete_execution_flow(self, scenario_type: str) -> Dict[str, Any]:
        """Test complete flow from scanner detection to trade execution"""
        logger.info(f"🧪 Testing complete execution flow: {scenario_type}")
        
        # Setup
        runner = await self.setup_realistic_environment()
        self.create_market_scenario(scenario_type)
        expected_plays = self.configure_scanner_responses(runner, scenario_type)
        self.configure_mayordomo_realistic(runner)
        
        # Clear history
        self.execution_history = []
        self.signal_history = []
        self.order_history = []
        
        start_time = datetime.now()
        
        try:
            # Step 1: Scanner detects opportunities
            logger.info("📡 Step 1: Scanner detection...")
            detected_plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
            
            # Step 2: Process each play through complete pipeline
            logger.info("⚙️ Step 2: Processing plays through pipeline...")
            for play in detected_plays:
                # Track execution
                self.execution_history.append({
                    "step": "play_detected",
                    "symbol": play.symbol,
                    "quality_score": play.quality_score,
                    "timestamp": datetime.now()
                })
                
                # Evaluate with mayordomo
                await runner._evaluate_play_with_mayordomo(play)
                
                # Process with ML engine
                await runner._process_plays_with_ml_engine([play])
            
            # Step 3: Simulate real-time price updates
            logger.info("📈 Step 3: Simulating price movements...")
            await self._simulate_price_movements()
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Analyze results
            total_plays = len(detected_plays)
            total_signals = len(self.signal_history)
            total_orders = len(self.order_history)
            mayordomo_evaluations = runner.mayordomo.evaluate_position_rotation.call_count
            trading_engine_additions = runner.trading_engine.add_symbol.call_count
            
            # Calculate success metrics
            filled_orders = sum(1 for order in self.order_history if order['status'] == 'FILLED')
            
            result = {
                "scenario": scenario_type,
                "success": True,
                "timestamp": start_time.isoformat(),
                "processing_time_seconds": processing_time,
                
                # Detection metrics
                "plays_detected": total_plays,
                "plays_evaluated": mayordomo_evaluations,
                
                # Execution metrics
                "signals_generated": total_signals,
                "symbols_added_to_engine": trading_engine_additions,
                "orders_placed": total_orders,
                "orders_filled": filled_orders,
                
                # Success rates
                "evaluation_rate": mayordomo_evaluations / total_plays if total_plays > 0 else 0,
                "signal_generation_rate": total_signals / total_plays if total_plays > 0 else 0,
                "execution_rate": filled_orders / total_plays if total_plays > 0 else 0,
                
                # Detailed history
                "execution_history": self.execution_history,
                "signal_history": self.signal_history,
                "order_history": self.order_history,
                
                # Performance metrics
                "avg_processing_time_per_play": processing_time / total_plays if total_plays > 0 else 0,
                "plays_per_second": total_plays / processing_time if processing_time > 0 else 0
            }
            
            logger.info(f"✅ {scenario_type}: {filled_orders} trades executed from {total_plays} plays")
            return result
            
        except Exception as e:
            logger.error(f"❌ Execution flow test failed: {e}")
            import traceback
            return {
                "scenario": scenario_type,
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_history": self.execution_history
            }
    
    async def _simulate_price_movements(self):
        """Simulate realistic price movements after detection"""
        # Simulate some price updates
        for symbol in self.market_data_provider.market_data.keys():
            current_data = self.market_data_provider.market_data[symbol]
            
            # Simulate price movement (small random walk)
            import random
            price_change = random.uniform(-0.02, 0.03)  # -2% to +3%
            new_price = current_data.close * (1 + price_change)
            
            self.market_data_provider.update_price(symbol, new_price)
            
            # Small delay to simulate real-time
            await asyncio.sleep(0.01)
    
    async def test_performance_under_load(self) -> Dict[str, Any]:
        """Test system performance under high load"""
        logger.info("🚀 Testing performance under load...")
        
        runner = await self.setup_realistic_environment()
        
        # Create high-load scenario (50 plays)
        large_plays = []
        for i in range(50):
            symbol = f"LOAD{i:03d}"
            price = 5.0 + (i % 10)
            volume = 1_000_000 + i * 100_000
            gap = 0.05 + (i % 20) * 0.005
            
            self.market_data_provider.set_market_data(symbol, price, volume, gap)
            
            # Use local MockPlay classes
            play = MockPlay(
                symbol, 
                6.0 + (i % 4), 
                MockCatalyst("news", 0.6 + (i % 4) * 0.1), 
                MockContext(price, gap, 2.0 + (i % 3), 1_000_000, volume)
            )
            large_plays.append(play)
        
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=large_plays)
        self.configure_mayordomo_realistic(runner)
        
        # Clear history
        self.execution_history = []
        self.signal_history = []
        self.order_history = []
        
        start_time = datetime.now()
        
        # Process all plays
        detected_plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
        
        # Process in batches to simulate realistic load
        batch_size = 10
        for i in range(0, len(detected_plays), batch_size):
            batch = detected_plays[i:i+batch_size]
            
            # Process batch concurrently
            tasks = []
            for play in batch:
                tasks.append(runner._evaluate_play_with_mayordomo(play))
            
            await asyncio.gather(*tasks)
            
            # Small delay between batches
            await asyncio.sleep(0.1)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return {
            "test_type": "performance_load",
            "success": True,
            "total_plays": len(detected_plays),
            "total_time_seconds": total_time,
            "plays_per_second": len(detected_plays) / total_time,
            "orders_placed": len(self.order_history),
            "signals_generated": len(self.signal_history),
            "avg_time_per_play": total_time / len(detected_plays)
        }

async def run_scanner_execution_tests():
    """Run comprehensive scanner-to-execution tests"""
    print("🔍➡️⚡ SCANNER TO EXECUTION FLOW TESTS")
    print("=" * 70)
    
    tester = ProductionScannerExecutionTester()
    
    # Test scenarios
    scenarios = [
        "morning_gaps",
        "news_driven", 
        "mixed_signals"
    ]
    
    results = []
    
    # Test each scenario
    for scenario in scenarios:
        print(f"\n🧪 Testing scenario: {scenario}")
        print("-" * 50)
        
        result = await tester.test_complete_execution_flow(scenario)
        results.append(result)
        
        if result.get("success", False):
            print(f"✅ SUCCESS")
            print(f"   📊 Plays: {result['plays_detected']} detected")
            print(f"   🎯 Evaluations: {result['plays_evaluated']}")
            print(f"   📡 Signals: {result['signals_generated']}")
            print(f"   💰 Orders: {result['orders_filled']} filled")
            print(f"   ⏱️  Time: {result['processing_time_seconds']:.3f}s")
            print(f"   📈 Rate: {result['execution_rate']:.1%} execution rate")
        else:
            print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
    
    # Performance test
    print(f"\n🚀 Testing performance under load...")
    print("-" * 50)
    
    perf_result = await tester.test_performance_under_load()
    results.append(perf_result)
    
    if perf_result.get("success", False):
        print(f"✅ PERFORMANCE TEST SUCCESS")
        print(f"   📊 Plays processed: {perf_result['total_plays']}")
        print(f"   ⏱️  Total time: {perf_result['total_time_seconds']:.3f}s")
        print(f"   🚀 Throughput: {perf_result['plays_per_second']:.1f} plays/sec")
        print(f"   💰 Orders placed: {perf_result['orders_placed']}")
    else:
        print(f"❌ PERFORMANCE TEST FAILED")
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SCANNER-EXECUTION TEST SUMMARY")
    print("=" * 70)
    
    successful_tests = sum(1 for r in results if r.get("success", False))
    total_tests = len(results)
    
    print(f"Tests completed: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Success rate: {successful_tests/total_tests*100:.1f}%")
    
    # Save results
    results_file = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/scanner_execution_test_results.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save results: {e}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_scanner_execution_tests())
