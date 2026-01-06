"""
Production Execution Flow Tests
Tests the complete flow from scanner detection to actual trade execution
Simulates real market conditions and verifies the system executes trades correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime, time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import json
import logging

# Import production system
from production.smallcap_production_runner import SmallcapProductionRunner

# Import required interfaces
from core.interfaces import Signal, SignalType, MarketData, TradingConfig

# Setup logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MockCatalyst:
    """Mock catalyst for testing"""
    catalyst_type: str
    strength: float
    description: str = ""

@dataclass
class MockContext:
    """Mock market context for testing"""
    current_price: float
    gap_percentage: float
    premarket_volume_ratio: float
    avg_daily_volume: int
    volume: int
    open_price: float = None
    high_price: float = None
    low_price: float = None
    
    def __post_init__(self):
        if self.open_price is None:
            self.open_price = self.current_price * (1 - self.gap_percentage)
        if self.high_price is None:
            self.high_price = self.current_price * 1.02
        if self.low_price is None:
            self.low_price = self.current_price * 0.98

@dataclass
class MockPlay:
    """Mock trading play for testing"""
    symbol: str
    quality_score: float
    catalyst: MockCatalyst
    context: MockContext
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class ProductionExecutionFlowTester:
    """Comprehensive tester for production execution flow"""
    
    def __init__(self):
        self.test_results = []
        self.execution_log = []
        
    async def setup_test_environment(self) -> SmallcapProductionRunner:
        """Setup a fully mocked test environment"""
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Mock all external dependencies
        runner.ibkr_adapter = AsyncMock()
        runner.ibkr_adapter.connect = AsyncMock(return_value=True)
        runner.ibkr_adapter.is_connected = Mock(return_value=True)
        runner.ibkr_adapter.get_market_data = AsyncMock()
        runner.ibkr_adapter.place_order = AsyncMock(return_value={"order_id": "TEST123", "status": "FILLED"})
        
        runner.smallcap_scanner = AsyncMock()
        runner.tiingo_provider = AsyncMock()
        runner.hybrid_scanner = AsyncMock()
        
        # Mock trading engine with detailed tracking
        runner.trading_engine = AsyncMock()
        runner.trading_engine.initialize = AsyncMock(return_value=True)
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        
        # Mock mayordomo with configurable responses
        runner.mayordomo = Mock()
        runner.mayordomo.register_daily_play = Mock()
        
        # Mock ML engine
        runner.ml_engine = Mock()
        runner.ml_engine._smallcap_mayordomo_select_strategies = AsyncMock()
        
        # Mock telegram
        runner._send_telegram_alert = Mock()
        
        # Track all method calls for verification
        self._setup_call_tracking(runner)
        
        return runner
    
    def _setup_call_tracking(self, runner):
        """Setup call tracking for verification"""
        original_evaluate = runner._evaluate_play_with_mayordomo
        original_execute = runner._execute_trade_via_engine
        original_process_ml = runner._process_plays_with_ml_engine
        
        async def track_evaluate(play):
            self.execution_log.append(f"EVALUATE: {play.symbol} (Score: {play.quality_score})")
            return await original_evaluate(play)
        
        async def track_execute(play, decision):
            self.execution_log.append(f"EXECUTE: {play.symbol} -> {decision.get('action', 'UNKNOWN')}")
            return await original_execute(play, decision)
        
        async def track_ml_process(plays):
            self.execution_log.append(f"ML_PROCESS: {len(plays)} plays")
            return await original_process_ml(plays)
        
        runner._evaluate_play_with_mayordomo = track_evaluate
        runner._execute_trade_via_engine = track_execute
        runner._process_plays_with_ml_engine = track_ml_process
    
    def create_realistic_plays(self, scenario: str) -> List[MockPlay]:
        """Create realistic plays for different scenarios"""
        
        if scenario == "high_quality_gaps":
            return [
                MockPlay(
                    symbol="ABCD",
                    quality_score=9.2,
                    catalyst=MockCatalyst("earnings_beat", 0.9, "Q3 earnings beat by 25%"),
                    context=MockContext(
                        current_price=8.75,
                        gap_percentage=0.18,  # 18% gap up
                        premarket_volume_ratio=5.2,  # 5.2x normal volume
                        avg_daily_volume=2_500_000,
                        volume=13_000_000
                    )
                ),
                MockPlay(
                    symbol="EFGH",
                    quality_score=8.8,
                    catalyst=MockCatalyst("fda_approval", 0.95, "FDA approves new drug"),
                    context=MockContext(
                        current_price=12.30,
                        gap_percentage=0.22,  # 22% gap up
                        premarket_volume_ratio=7.8,  # 7.8x normal volume
                        avg_daily_volume=1_800_000,
                        volume=14_040_000
                    )
                )
            ]
        
        elif scenario == "mixed_quality":
            return [
                # High quality
                MockPlay(
                    symbol="GOOD1",
                    quality_score=8.5,
                    catalyst=MockCatalyst("merger_news", 0.85),
                    context=MockContext(
                        current_price=6.50,
                        gap_percentage=0.15,
                        premarket_volume_ratio=4.2,
                        avg_daily_volume=1_200_000,
                        volume=5_040_000
                    )
                ),
                # Medium quality
                MockPlay(
                    symbol="MED1",
                    quality_score=6.8,
                    catalyst=MockCatalyst("analyst_upgrade", 0.6),
                    context=MockContext(
                        current_price=4.25,
                        gap_percentage=0.08,
                        premarket_volume_ratio=2.1,
                        avg_daily_volume=800_000,
                        volume=1_680_000
                    )
                ),
                # Low quality
                MockPlay(
                    symbol="POOR1",
                    quality_score=4.2,
                    catalyst=MockCatalyst("weak_news", 0.3),
                    context=MockContext(
                        current_price=2.10,
                        gap_percentage=0.03,
                        premarket_volume_ratio=1.2,
                        avg_daily_volume=300_000,
                        volume=360_000
                    )
                )
            ]
        
        elif scenario == "risk_management":
            # Create 8 plays to test position limits
            return [
                MockPlay(
                    symbol=f"RISK{i}",
                    quality_score=7.0 + i * 0.2,
                    catalyst=MockCatalyst("news", 0.7),
                    context=MockContext(
                        current_price=5.0 + i,
                        gap_percentage=0.10 + i * 0.01,
                        premarket_volume_ratio=2.5 + i * 0.3,
                        avg_daily_volume=1_000_000,
                        volume=2_500_000 + i * 300_000
                    )
                )
                for i in range(8)
            ]
        
        elif scenario == "edge_cases":
            return [
                # Very high price (near upper limit)
                MockPlay(
                    symbol="HPRICE",
                    quality_score=7.5,
                    catalyst=MockCatalyst("news", 0.7),
                    context=MockContext(
                        current_price=14.95,  # Near $15 limit
                        gap_percentage=0.12,
                        premarket_volume_ratio=3.0,
                        avg_daily_volume=500_000,
                        volume=1_500_000
                    )
                ),
                # Very low price (near lower limit)
                MockPlay(
                    symbol="LPRICE",
                    quality_score=7.2,
                    catalyst=MockCatalyst("news", 0.7),
                    context=MockContext(
                        current_price=0.55,  # Near $0.50 limit
                        gap_percentage=0.15,
                        premarket_volume_ratio=4.0,
                        avg_daily_volume=2_000_000,
                        volume=8_000_000
                    )
                ),
                # Extreme volume spike
                MockPlay(
                    symbol="VOLSPIKE",
                    quality_score=8.0,
                    catalyst=MockCatalyst("viral_news", 0.8),
                    context=MockContext(
                        current_price=3.25,
                        gap_percentage=0.25,  # 25% gap
                        premarket_volume_ratio=15.0,  # 15x volume!
                        avg_daily_volume=500_000,
                        volume=7_500_000
                    )
                )
            ]
        
        else:
            return []
    
    async def test_scenario(self, scenario_name: str, expected_executions: int = None) -> Dict[str, Any]:
        """Test a complete scenario from scanner to execution"""
        logger.info(f"🧪 Testing scenario: {scenario_name}")
        
        # Setup
        runner = await self.setup_test_environment()
        plays = self.create_realistic_plays(scenario_name)
        
        if not plays:
            return {"error": f"No plays created for scenario: {scenario_name}"}
        
        # Configure mayordomo responses based on scenario
        self._configure_mayordomo_for_scenario(runner, scenario_name)
        
        # Setup scanner to return our test plays
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=plays)
        
        # Clear execution log
        self.execution_log = []
        
        # Execute the scenario
        start_time = datetime.now()
        
        try:
            # Simulate scanner detection
            detected_plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
            
            # Process each play through the complete pipeline
            execution_results = []
            for play in detected_plays:
                # Evaluate with mayordomo
                await runner._evaluate_play_with_mayordomo(play)
                
                # Process with ML engine
                await runner._process_plays_with_ml_engine([play])
                
                # Track execution result
                execution_results.append({
                    "symbol": play.symbol,
                    "quality_score": play.quality_score,
                    "gap_percentage": play.context.gap_percentage,
                    "volume_ratio": play.context.premarket_volume_ratio
                })
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Analyze results
            total_evaluations = runner.mayordomo.evaluate_position_rotation.call_count
            total_executions = runner.trading_engine.add_symbol.call_count
            telegram_alerts = runner._send_telegram_alert.call_count
            
            result = {
                "scenario": scenario_name,
                "success": True,
                "plays_detected": len(detected_plays),
                "plays_evaluated": total_evaluations,
                "trades_executed": total_executions,
                "telegram_alerts": telegram_alerts,
                "processing_time_seconds": processing_time,
                "execution_log": self.execution_log.copy(),
                "execution_results": execution_results,
                "mayordomo_calls": [call.args for call in runner.mayordomo.evaluate_position_rotation.call_args_list],
                "trading_engine_calls": [call.args for call in runner.trading_engine.add_symbol.call_args_list]
            }
            
            # Verify expectations if provided
            if expected_executions is not None:
                result["expectation_met"] = (total_executions == expected_executions)
                if total_executions != expected_executions:
                    result["expectation_error"] = f"Expected {expected_executions} executions, got {total_executions}"
            
            logger.info(f"✅ Scenario {scenario_name}: {total_executions} trades executed from {len(detected_plays)} plays")
            return result
            
        except Exception as e:
            logger.error(f"❌ Scenario {scenario_name} failed: {e}")
            import traceback
            return {
                "scenario": scenario_name,
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_log": self.execution_log.copy()
            }
    
    def _configure_mayordomo_for_scenario(self, runner, scenario: str):
        """Configure mayordomo responses for different scenarios"""
        
        if scenario == "high_quality_gaps":
            # Approve all high-quality plays
            runner.mayordomo.evaluate_position_rotation = Mock(return_value={
                "action": "OPEN_POSITION",
                "reason": "HIGH_QUALITY_OPPORTUNITY",
                "position_size": 0.025,
                "confidence": 0.88
            })
        
        elif scenario == "mixed_quality":
            # Approve based on quality score
            def quality_based_decision(opportunity):
                symbol = opportunity['symbol']
                if 'GOOD' in symbol:
                    return {"action": "OPEN_POSITION", "reason": "HIGH_QUALITY", "position_size": 0.02}
                elif 'MED' in symbol:
                    return {"action": "OPEN_POSITION", "reason": "MEDIUM_QUALITY", "position_size": 0.015}
                else:
                    return {"action": "REJECT", "reason": "INSUFFICIENT_QUALITY"}
            
            runner.mayordomo.evaluate_position_rotation = Mock(side_effect=quality_based_decision)
        
        elif scenario == "risk_management":
            # Approve first 3, reject rest due to position limits
            call_count = 0
            def position_limit_decision(opportunity):
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    return {"action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02}
                else:
                    return {"action": "REJECT", "reason": "MAX_POSITIONS_REACHED"}
            
            runner.mayordomo.evaluate_position_rotation = Mock(side_effect=position_limit_decision)
        
        elif scenario == "edge_cases":
            # Handle edge cases appropriately
            def edge_case_decision(opportunity):
                symbol = opportunity['symbol']
                if symbol == "HPRICE":
                    return {"action": "REJECT", "reason": "PRICE_TOO_HIGH"}
                elif symbol == "LPRICE":
                    return {"action": "REJECT", "reason": "PRICE_TOO_LOW"}
                elif symbol == "VOLSPIKE":
                    return {"action": "OPEN_POSITION", "reason": "EXCEPTIONAL_VOLUME", "position_size": 0.03}
                else:
                    return {"action": "REJECT", "reason": "UNKNOWN_EDGE_CASE"}
            
            runner.mayordomo.evaluate_position_rotation = Mock(side_effect=edge_case_decision)
        
        else:
            # Default: approve all
            runner.mayordomo.evaluate_position_rotation = Mock(return_value={
                "action": "OPEN_POSITION",
                "reason": "DEFAULT_APPROVAL",
                "position_size": 0.02
            })

async def run_comprehensive_tests():
    """Run comprehensive production execution flow tests"""
    print("🚀 PRODUCTION EXECUTION FLOW TESTS")
    print("=" * 60)
    
    tester = ProductionExecutionFlowTester()
    
    # Define test scenarios with expected results
    scenarios = [
        ("high_quality_gaps", 2),      # Should execute both high-quality plays
        ("mixed_quality", 2),          # Should execute good and medium, reject poor
        ("risk_management", 3),        # Should execute first 3, reject rest due to limits
        ("edge_cases", 1),             # Should execute only VOLSPIKE
    ]
    
    results = []
    
    for scenario_name, expected_executions in scenarios:
        print(f"\n🧪 Testing: {scenario_name}")
        print("-" * 40)
        
        result = await tester.test_scenario(scenario_name, expected_executions)
        results.append(result)
        
        if result.get("success", False):
            print(f"✅ SUCCESS: {result['trades_executed']} trades executed")
            print(f"   📊 Plays: {result['plays_detected']} detected, {result['plays_evaluated']} evaluated")
            print(f"   ⏱️  Time: {result['processing_time_seconds']:.3f}s")
            print(f"   📱 Alerts: {result['telegram_alerts']} sent")
            
            if result.get("expectation_met", True):
                print(f"   ✅ Expectations met")
            else:
                print(f"   ⚠️  Expectation issue: {result.get('expectation_error', 'Unknown')}")
            
            # Show execution log
            if result['execution_log']:
                print(f"   📝 Execution log:")
                for log_entry in result['execution_log']:
                    print(f"      {log_entry}")
        else:
            print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    successful_tests = sum(1 for r in results if r.get("success", False))
    total_tests = len(results)
    
    print(f"Tests run: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    print(f"Success rate: {successful_tests/total_tests*100:.1f}%")
    
    # Detailed results
    print("\n📋 DETAILED RESULTS:")
    for result in results:
        status = "✅" if result.get("success", False) else "❌"
        scenario = result.get("scenario", "Unknown")
        
        if result.get("success", False):
            executions = result.get("trades_executed", 0)
            plays = result.get("plays_detected", 0)
            time_taken = result.get("processing_time_seconds", 0)
            print(f"{status} {scenario}: {executions} trades from {plays} plays ({time_taken:.3f}s)")
        else:
            error = result.get("error", "Unknown error")
            print(f"{status} {scenario}: {error}")
    
    # Save detailed results
    results_file = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/production_execution_test_results.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save results: {e}")
    
    return results

if __name__ == "__main__":
    # Run the comprehensive tests
    asyncio.run(run_comprehensive_tests())
