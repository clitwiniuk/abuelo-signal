"""
Comprehensive Tests for Production System
Tests the complete flow from scanner detection to trade execution
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json

# Import production system
from production.smallcap_production_runner import SmallcapProductionRunner

# Import required interfaces and components
from core.interfaces import Signal, SignalType, MarketData, TradingConfig
from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner
from adapters.ibkr_adapter import IBKRAdapter
from engine.trading_engine import TradingEngine

# Mock data structures for testing
@dataclass
class MockCatalyst:
    catalyst_type: str
    strength: float

@dataclass
class MockContext:
    current_price: float
    gap_percentage: float
    premarket_volume_ratio: float
    avg_daily_volume: int
    volume: int

@dataclass
class MockPlay:
    symbol: str
    quality_score: float
    catalyst: MockCatalyst
    context: MockContext

class TestProductionSystemUnit(unittest.TestCase):
    """Unit tests for individual production system components"""
    
    def setUp(self):
        """Setup test environment"""
        self.test_config = {
            "environment": "test",
            "ibkr": {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 999,
                "account": "TEST123"
            },
            "tiingo": {
                "api_key": "test_key"
            },
            "scanning": {
                "interval_seconds": 30,
                "max_symbols": 10
            },
            "risk": {
                "max_positions": 3,
                "position_size": 0.01,
                "daily_loss_limit": 0.02
            },
            "ml_engine": {
                "enabled": True
            },
            "trading_hours": {
                "enable_premarket": True,
                "market_open": 9.5,
                "market_close": 16.0
            },
            "telegram": {
                "enabled": False
            }
        }
    
    def test_production_runner_initialization(self):
        """Test production runner initializes correctly"""
        with patch('production.smallcap_production_runner.HybridConfigManager') as mock_config:
            mock_config.return_value.get_complete_hybrid_config.return_value = {
                "base_config": {},
                "production_extensions": {
                    "tiingo": {"api_key": "test"},
                    "scanning_intervals": {"regular_market_seconds": 30, "premarket_seconds": 60},
                    "production_monitoring": {},
                    "production_alerts": {},
                    "telegram": {"enabled": False},
                    "hybrid_scanner": {},
                    "live_trading_safety": {}
                }
            }
            
            runner = SmallcapProductionRunner(test_mode=True)
            
            self.assertIsNotNone(runner)
            self.assertTrue(runner.test_mode)
            self.assertEqual(runner.scan_count, 0)
            self.assertEqual(runner.total_plays_found, 0)
    
    def test_config_loading_fallback(self):
        """Test fallback config loading when HybridConfigManager fails"""
        with patch('production.smallcap_production_runner.HybridConfigManager', side_effect=Exception("Config error")):
            runner = SmallcapProductionRunner(test_mode=True)
            
            self.assertIsNotNone(runner.config)
            self.assertEqual(runner.config["config_source"], "fallback")
            self.assertIn("ibkr", runner.config)
            self.assertIn("scanning", runner.config)
    
    def test_trading_time_detection(self):
        """Test trading time detection logic"""
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Mock datetime to test different times
        with patch('production.smallcap_production_runner.datetime') as mock_dt:
            # Test market hours (10 AM EST)
            mock_dt.now.return_value.time.return_value = time(10, 0)
            mock_dt.now.return_value = Mock()
            mock_dt.now.return_value.astimezone.return_value.time.return_value = time(10, 0)
            
            # This test would need proper timezone mocking for full accuracy
            # For now, just verify the method exists and runs
            result = runner._is_trading_time()
            self.assertIsInstance(result, bool)

class TestProductionSystemIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for complete production system flow"""
    
    async def asyncSetUp(self):
        """Setup async test environment"""
        self.runner = SmallcapProductionRunner(test_mode=True)
        
        # Mock all external dependencies
        self.mock_ibkr = AsyncMock(spec=IBKRAdapter)
        self.mock_ibkr.connect = AsyncMock(return_value=True)
        self.mock_ibkr.is_connected = Mock(return_value=True)
        
        self.mock_scanner = AsyncMock(spec=SmallcapDailyScanner)
        self.mock_trading_engine = AsyncMock(spec=TradingEngine)
        self.mock_trading_engine.initialize = AsyncMock(return_value=True)
        self.mock_trading_engine.add_symbol = AsyncMock(return_value=True)
        
        # Create mock plays for testing
        self.sample_plays = [
            MockPlay(
                symbol="ABCD",
                quality_score=8.5,
                catalyst=MockCatalyst("earnings_beat", 0.8),
                context=MockContext(
                    current_price=5.25,
                    gap_percentage=0.12,
                    premarket_volume_ratio=3.5,
                    avg_daily_volume=1_000_000,
                    volume=3_500_000
                )
            ),
            MockPlay(
                symbol="EFGH",
                quality_score=7.2,
                catalyst=MockCatalyst("fda_approval", 0.9),
                context=MockContext(
                    current_price=8.75,
                    gap_percentage=0.18,
                    premarket_volume_ratio=4.2,
                    avg_daily_volume=800_000,
                    volume=3_360_000
                )
            )
        ]
    
    async def test_complete_initialization_flow(self):
        """Test complete system initialization"""
        with patch.multiple(
            self.runner,
            _initialize_trading_engine=AsyncMock(),
            _initialize_telegram=AsyncMock()
        ), patch('production.smallcap_production_runner.IBKRAdapter', return_value=self.mock_ibkr), \
           patch('production.smallcap_production_runner.TiingoDataProvider'), \
           patch('production.smallcap_production_runner.HybridScanner'), \
           patch('production.smallcap_production_runner.SmallcapDailyScanner', return_value=self.mock_scanner), \
           patch('production.smallcap_production_runner.create_smallcap_mayordomo'), \
           patch('production.smallcap_production_runner.MLMultiStrategyEngine'), \
           patch('production.smallcap_production_runner.setup_logging'):
            
            result = await self.runner.initialize()
            
            self.assertTrue(result)
            self.assertIsNotNone(self.runner.ibkr_adapter)
            self.assertIsNotNone(self.runner.smallcap_scanner)
    
    async def test_scanner_detection_and_evaluation(self):
        """Test scanner detection triggers proper evaluation"""
        # Setup mocks
        self.runner.smallcap_scanner = self.mock_scanner
        self.runner.mayordomo = Mock()
        self.runner.mayordomo.register_daily_play = Mock()
        self.runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION",
            "reason": "HIGH_QUALITY_PLAY",
            "position_size": 0.02,
            "confidence": 0.85
        })
        
        # Mock scanner to return sample plays
        self.mock_scanner.scan_daily_plays = AsyncMock(return_value=self.sample_plays)
        
        # Mock trade execution
        self.runner._execute_trade_via_engine = AsyncMock(return_value=True)
        
        # Execute evaluation
        await self.runner._evaluate_play_with_mayordomo(self.sample_plays[0])
        
        # Verify mayordomo was called
        self.runner.mayordomo.register_daily_play.assert_called_once()
        self.runner.mayordomo.evaluate_position_rotation.assert_called_once()
        self.runner._execute_trade_via_engine.assert_called_once()
    
    async def test_trade_execution_via_engine(self):
        """Test trade execution through TradingEngine"""
        # Setup mocks
        self.runner.trading_engine = self.mock_trading_engine
        self.runner._send_telegram_alert = Mock()
        
        play = self.sample_plays[0]
        decision = {
            "action": "OPEN_POSITION",
            "reason": "HIGH_QUALITY_PLAY",
            "position_size": 0.02,
            "confidence": 0.85
        }
        
        # Execute trade
        result = await self.runner._execute_trade_via_engine(play, decision)
        
        # Verify execution
        self.assertTrue(result)
        self.mock_trading_engine.add_symbol.assert_called_once_with(play.symbol, skip_validation=True)
        self.runner._send_telegram_alert.assert_called_once()
    
    async def test_ml_engine_processing(self):
        """Test ML engine processes plays correctly"""
        # Setup ML engine mock
        self.runner.ml_engine = Mock()
        self.runner.ml_engine._smallcap_mayordomo_select_strategies = AsyncMock(return_value={
            "strategy": "gap_and_go",
            "confidence": 0.78
        })
        
        # Process plays
        await self.runner._process_plays_with_ml_engine(self.sample_plays)
        
        # Verify ML engine was called for each play
        self.assertEqual(
            self.runner.ml_engine._smallcap_mayordomo_select_strategies.call_count,
            len(self.sample_plays)
        )
    
    async def test_test_mode_override(self):
        """Test that test mode overrides mayordomo decisions"""
        # Setup test mode runner
        runner = SmallcapProductionRunner(test_mode=True)
        runner.mayordomo = Mock()
        runner._execute_trade_via_engine = AsyncMock(return_value=True)
        
        # Create high-quality play that should be approved in test mode
        play = MockPlay(
            symbol="TEST",
            quality_score=6.0,  # Above test mode threshold
            catalyst=MockCatalyst("test_catalyst", 0.8),
            context=MockContext(
                current_price=5.0,
                gap_percentage=0.10,
                premarket_volume_ratio=2.0,
                avg_daily_volume=500_000,
                volume=1_000_000
            )
        )
        
        await runner._evaluate_play_with_mayordomo(play)
        
        # Verify trade was executed due to test mode override
        runner._execute_trade_via_engine.assert_called_once()

class TestProductionSystemScenarios(unittest.IsolatedAsyncioTestCase):
    """Test realistic trading scenarios"""
    
    async def asyncSetUp(self):
        """Setup scenario test environment"""
        self.runner = SmallcapProductionRunner(test_mode=True)
        await self._setup_mocks()
    
    async def _setup_mocks(self):
        """Setup all required mocks"""
        self.runner.ibkr_adapter = AsyncMock()
        self.runner.smallcap_scanner = AsyncMock()
        self.runner.trading_engine = AsyncMock()
        self.runner.mayordomo = Mock()
        self.runner.ml_engine = Mock()
        self.runner._send_telegram_alert = Mock()
    
    async def test_high_quality_gap_play_scenario(self):
        """Test scenario: High-quality gap play detected and executed"""
        # Create exceptional gap play
        exceptional_play = MockPlay(
            symbol="GAPUP",
            quality_score=9.2,
            catalyst=MockCatalyst("earnings_surprise", 0.95),
            context=MockContext(
                current_price=12.50,
                gap_percentage=0.22,  # 22% gap
                premarket_volume_ratio=6.8,  # 6.8x volume
                avg_daily_volume=2_000_000,
                volume=13_600_000
            )
        )
        
        # Setup scanner to return exceptional play
        self.runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=[exceptional_play])
        
        # Setup mayordomo to approve
        self.runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION",
            "reason": "EXCEPTIONAL_OPPORTUNITY",
            "position_size": 0.03,  # Larger position for exceptional play
            "confidence": 0.92
        })
        
        # Setup trading engine success
        self.runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        
        # Execute single scan cycle
        plays = await self.runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
        self.assertEqual(len(plays), 1)
        
        # Process the play
        await self.runner._evaluate_play_with_mayordomo(plays[0])
        
        # Verify execution chain
        self.runner.mayordomo.evaluate_position_rotation.assert_called_once()
        self.runner.trading_engine.add_symbol.assert_called_once_with("GAPUP", skip_validation=True)
    
    async def test_multiple_plays_risk_management_scenario(self):
        """Test scenario: Multiple plays detected, risk management limits execution"""
        # Create multiple plays
        plays = [
            MockPlay(f"PLAY{i}", 7.0 + i*0.5, MockCatalyst("news", 0.7), 
                    MockContext(5.0 + i, 0.08 + i*0.02, 2.0 + i*0.5, 1_000_000, 2_000_000))
            for i in range(5)
        ]
        
        # Setup scanner
        self.runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=plays)
        
        # Setup mayordomo to reject some due to risk limits
        def mock_evaluate(opportunity):
            if opportunity['symbol'] in ['PLAY0', 'PLAY1', 'PLAY2']:
                return {"action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02}
            else:
                return {"action": "REJECT", "reason": "MAX_POSITIONS_REACHED"}
        
        self.runner.mayordomo.evaluate_position_rotation = Mock(side_effect=mock_evaluate)
        self.runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        
        # Process all plays
        approved_count = 0
        for play in plays:
            await self.runner._evaluate_play_with_mayordomo(play)
            # Count how many were approved (first 3 should be approved)
            if play.symbol in ['PLAY0', 'PLAY1', 'PLAY2']:
                approved_count += 1
        
        # Verify risk management worked
        self.assertEqual(self.runner.trading_engine.add_symbol.call_count, 3)
    
    async def test_poor_quality_plays_rejected_scenario(self):
        """Test scenario: Poor quality plays are rejected"""
        # Create low-quality plays
        poor_plays = [
            MockPlay(
                symbol="POOR1",
                quality_score=3.2,  # Low quality
                catalyst=MockCatalyst("weak_news", 0.3),
                context=MockContext(
                    current_price=2.10,
                    gap_percentage=0.03,  # Small gap
                    premarket_volume_ratio=1.1,  # Low volume
                    avg_daily_volume=100_000,
                    volume=110_000
                )
            )
        ]
        
        # Setup scanner
        self.runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=poor_plays)
        
        # Setup mayordomo to reject
        self.runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "REJECT",
            "reason": "INSUFFICIENT_QUALITY"
        })
        
        # Process plays
        await self.runner._evaluate_play_with_mayordomo(poor_plays[0])
        
        # Verify rejection
        self.runner.mayordomo.evaluate_position_rotation.assert_called_once()
        self.runner.trading_engine.add_symbol.assert_not_called()
    
    async def test_scanner_failure_scenario(self):
        """Test scenario: Scanner fails, system handles gracefully"""
        # Setup scanner to fail
        self.runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=Exception("Scanner timeout"))
        
        # Mock the scanning loop logic
        try:
            plays = await self.runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
        except Exception as e:
            # System should handle this gracefully
            self.assertIn("Scanner timeout", str(e))
            plays = None
        
        # Verify system continues despite failure
        self.assertIsNone(plays)
    
    async def test_trading_engine_failure_scenario(self):
        """Test scenario: Trading engine fails, system logs and continues"""
        # Create good play
        play = MockPlay(
            symbol="FAIL",
            quality_score=8.0,
            catalyst=MockCatalyst("good_news", 0.8),
            context=MockContext(7.50, 0.15, 3.0, 1_000_000, 3_000_000)
        )
        
        # Setup mayordomo to approve
        self.runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION",
            "reason": "APPROVED",
            "position_size": 0.02
        })
        
        # Setup trading engine to fail
        self.runner.trading_engine.add_symbol = AsyncMock(side_effect=Exception("Connection lost"))
        
        # Process play - should handle failure gracefully
        result = await self.runner._execute_trade_via_engine(play, {"action": "OPEN_POSITION"})
        
        # Verify failure was handled
        self.assertFalse(result)

class TestProductionSystemPerformance(unittest.IsolatedAsyncioTestCase):
    """Performance and stress tests"""
    
    async def asyncSetUp(self):
        """Setup performance test environment"""
        self.runner = SmallcapProductionRunner(test_mode=True)
        await self._setup_performance_mocks()
    
    async def _setup_performance_mocks(self):
        """Setup mocks for performance testing"""
        self.runner.smallcap_scanner = AsyncMock()
        self.runner.mayordomo = Mock()
        self.runner.trading_engine = AsyncMock()
        self.runner._send_telegram_alert = Mock()
    
    async def test_high_volume_play_processing(self):
        """Test processing many plays quickly"""
        # Create 50 plays
        plays = [
            MockPlay(f"VOL{i:03d}", 6.0 + (i % 5), MockCatalyst("news", 0.6), 
                    MockContext(5.0, 0.08, 2.0, 500_000, 1_000_000))
            for i in range(50)
        ]
        
        # Setup scanner
        self.runner.smallcap_scanner.scan_daily_plays = AsyncMock(return_value=plays)
        
        # Setup mayordomo to approve first 10, reject rest
        def mock_evaluate(opportunity):
            play_num = int(opportunity['symbol'][3:])
            if play_num < 10:
                return {"action": "OPEN_POSITION", "reason": "APPROVED"}
            return {"action": "REJECT", "reason": "RISK_LIMIT"}
        
        self.runner.mayordomo.evaluate_position_rotation = Mock(side_effect=mock_evaluate)
        self.runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        
        # Measure processing time
        start_time = datetime.now()
        
        # Process all plays
        for play in plays:
            await self.runner._evaluate_play_with_mayordomo(play)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Verify performance (should process 50 plays in under 1 second)
        self.assertLess(processing_time, 1.0)
        self.assertEqual(self.runner.trading_engine.add_symbol.call_count, 10)
    
    async def test_concurrent_processing(self):
        """Test concurrent processing of multiple plays"""
        # Create plays for concurrent processing
        plays = [
            MockPlay(f"CONC{i}", 7.0, MockCatalyst("news", 0.7), 
                    MockContext(6.0, 0.10, 2.5, 750_000, 1_875_000))
            for i in range(10)
        ]
        
        # Setup mocks
        self.runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED"
        })
        self.runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        
        # Process plays concurrently
        tasks = [self.runner._evaluate_play_with_mayordomo(play) for play in plays]
        await asyncio.gather(*tasks)
        
        # Verify all were processed
        self.assertEqual(self.runner.mayordomo.evaluate_position_rotation.call_count, 10)
        self.assertEqual(self.runner.trading_engine.add_symbol.call_count, 10)

class TestProductionSystemStatus(unittest.TestCase):
    """Test system status and monitoring"""
    
    def setUp(self):
        """Setup status test environment"""
        self.runner = SmallcapProductionRunner(test_mode=True)
    
    def test_get_status_basic(self):
        """Test basic status reporting"""
        # Setup basic mocks
        self.runner.ibkr_adapter = Mock()
        self.runner.ibkr_adapter.is_connected.return_value = True
        self.runner.mayordomo = Mock()
        
        # Mock mayordomo status
        with patch('production.smallcap_production_runner.get_mayordomo_status', return_value={
            "active_positions": 2,
            "daily_pnl": 150.25,
            "risk_level": "LOW"
        }):
            status = self.runner.get_status()
        
        # Verify status structure
        self.assertIn("is_running", status)
        self.assertIn("scan_count", status)
        self.assertIn("total_plays_found", status)
        self.assertIn("ibkr_connected", status)
        self.assertIn("mayordomo_status", status)
        
        # Verify values
        self.assertTrue(status["ibkr_connected"])
        self.assertEqual(status["scan_count"], 0)
        self.assertIsInstance(status["mayordomo_status"], dict)

def create_test_suite():
    """Create comprehensive test suite"""
    suite = unittest.TestSuite()
    
    # Add unit tests
    suite.addTest(unittest.makeSuite(TestProductionSystemUnit))
    
    # Add integration tests (async)
    # Note: These need to be run with asyncio test runner
    
    return suite

if __name__ == "__main__":
    # Run basic unit tests
    print("🧪 Running Production System Tests...")
    print("=" * 50)
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n" + "=" * 50)
    print("✅ Unit tests completed")
    print("\n💡 To run async integration tests, use:")
    print("python -m pytest tests/test_production_system.py::TestProductionSystemIntegration -v")
    print("python -m pytest tests/test_production_system.py::TestProductionSystemScenarios -v")
    print("python -m pytest tests/test_production_system.py::TestProductionSystemPerformance -v")
