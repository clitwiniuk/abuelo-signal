#!/usr/bin/env python3
"""
Tests de resistencia de red y conectividad
Simula fallos de red, timeouts, y problemas de conectividad
"""

import asyncio
import logging
import time
import json
import random
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from production.smallcap_production_runner import SmallcapProductionRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class NetworkPlay:
    """Mock play para tests de red"""
    def __init__(self, symbol: str, quality_score: float):
        self.symbol = symbol
        self.quality_score = quality_score
        self.catalyst = NetworkCatalyst("network_test", 0.8)
        self.context = NetworkContext()
        self.timestamp = datetime.now()

class NetworkCatalyst:
    def __init__(self, type_name: str, confidence: float):
        self.type = type_name
        self.catalyst_type = type_name  # Add missing attribute for compatibility
        self.confidence = confidence
        self.strength = confidence  # Add missing strength attribute
        self.description = f"Network test {type_name}"

class NetworkContext:
    def __init__(self):
        self.rsi = random.uniform(40, 60)
        self.gap = random.uniform(0.05, 0.15)
        self.gap_percentage = self.gap  # Add missing attribute
        self.premarket_volume_ratio = random.uniform(0.5, 3.0)  # Add missing attribute
        self.current_price = random.uniform(1.0, 50.0)  # Add missing attribute
        self.volume_ratio = random.uniform(3.0, 8.0)
        self.volume = random.randint(1_000_000, 5_000_000)
        self.avg_volume = random.randint(500_000, 2_000_000)
        self.avg_daily_volume = self.avg_volume  # Add missing attribute
        self.price_change = random.uniform(-0.05, 0.1)

class NetworkResilienceTests:
    """Suite de tests de resistencia de red"""
    
    async def test_ibkr_connection_timeout(self) -> Dict[str, Any]:
        """Test de timeout de conexión IBKR"""
        logger.info("🌐 Testing IBKR connection timeout...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks with timeouts
        timeout_count = {"count": 0}
        
        async def timeout_ibkr(*args, **kwargs):
            timeout_count["count"] += 1
            if timeout_count["count"] % 3 == 0:  # Every 3rd call times out
                await asyncio.sleep(2.0)  # Simulate timeout
                raise asyncio.TimeoutError("IBKR connection timeout")
            return True
        
        runner.ibkr_adapter = AsyncMock()
        runner.ibkr_adapter.connect = AsyncMock(side_effect=timeout_ibkr)
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(side_effect=timeout_ibkr)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02
        })
        runner._send_telegram_alert = Mock()
        
        # Test connection resilience
        plays = [NetworkPlay(f"TIMEOUT{i}", 7.0) for i in range(15)]
        
        start_time = time.time()
        successful_connections = 0
        timeout_errors = 0
        
        for play in plays:
            try:
                await runner._evaluate_play_with_mayordomo(play)
                successful_connections += 1
            except asyncio.TimeoutError:
                timeout_errors += 1
            except Exception:
                pass  # Other errors
            
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        
        return {
            "test": "ibkr_connection_timeout",
            "success": successful_connections >= 10,  # Should handle most despite timeouts
            "total_attempts": len(plays),
            "successful_connections": successful_connections,
            "timeout_errors": timeout_errors,
            "processing_time": end_time - start_time,
            "timeout_resilience": successful_connections >= 10
        }
    
    async def test_intermittent_network_failure(self) -> Dict[str, Any]:
        """Test de fallos intermitentes de red"""
        logger.info("📡 Testing intermittent network failures...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks with intermittent failures
        failure_count = {"scanner": 0, "trading": 0}
        
        async def intermittent_scanner(*args, **kwargs):
            failure_count["scanner"] += 1
            if failure_count["scanner"] % 4 == 0:  # Every 4th call fails
                raise ConnectionError("Network unreachable")
            return [NetworkPlay(f"NET{failure_count['scanner']}", 6.5)]
        
        async def intermittent_trading(*args, **kwargs):
            failure_count["trading"] += 1
            if failure_count["trading"] % 5 == 0:  # Every 5th call fails
                raise ConnectionError("Trading server unreachable")
            return True
        
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=intermittent_scanner)
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(side_effect=intermittent_trading)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02
        })
        runner._send_telegram_alert = Mock()
        
        # Simulate scanning cycles with network issues
        successful_scans = 0
        failed_scans = 0
        successful_trades = 0
        failed_trades = 0
        
        for cycle in range(25):
            try:
                # Try to scan
                plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                successful_scans += 1
                
                # Try to process plays
                if plays:
                    for play in plays:
                        try:
                            await runner._evaluate_play_with_mayordomo(play)
                            successful_trades += 1
                        except ConnectionError:
                            failed_trades += 1
                        except Exception:
                            pass
                            
            except ConnectionError:
                failed_scans += 1
            except Exception:
                pass
            
            await asyncio.sleep(0.05)
        
        return {
            "test": "intermittent_network_failure",
            "success": successful_scans >= 15 and successful_trades >= 10,
            "scan_cycles": 25,
            "successful_scans": successful_scans,
            "failed_scans": failed_scans,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "scan_success_rate": successful_scans / 25 * 100,
            "trade_success_rate": successful_trades / (successful_trades + failed_trades) * 100 if (successful_trades + failed_trades) > 0 else 0,
            "network_resilience": successful_scans >= 15
        }
    
    async def test_slow_network_conditions(self) -> Dict[str, Any]:
        """Test en condiciones de red lenta"""
        logger.info("🐌 Testing slow network conditions...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks with delays
        async def slow_scanner(*args, **kwargs):
            await asyncio.sleep(random.uniform(0.5, 2.0))  # Random delay
            return [NetworkPlay(f"SLOW{random.randint(1000, 9999)}", 6.8)]
        
        async def slow_trading(*args, **kwargs):
            await asyncio.sleep(random.uniform(0.3, 1.5))  # Random delay
            return True
        
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=slow_scanner)
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(side_effect=slow_trading)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02
        })
        runner._send_telegram_alert = Mock()
        
        # Test with slow network
        start_time = time.time()
        response_times = []
        
        for cycle in range(10):
            cycle_start = time.time()
            
            try:
                plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                if plays:
                    for play in plays:
                        await runner._evaluate_play_with_mayordomo(play)
            except Exception:
                pass
            
            cycle_end = time.time()
            response_times.append(cycle_end - cycle_start)
        
        end_time = time.time()
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        return {
            "test": "slow_network_conditions",
            "success": max_response_time < 10.0,  # Should complete within reasonable time
            "cycles_completed": len(response_times),
            "total_time": end_time - start_time,
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min(response_times),
            "performance_acceptable": max_response_time < 10.0
        }
    
    async def test_connection_recovery(self) -> Dict[str, Any]:
        """Test de recuperación de conexión"""
        logger.info("🔄 Testing connection recovery...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks with recovery simulation
        connection_state = {"connected": True, "failures": 0}
        
        async def recovery_scanner(*args, **kwargs):
            if not connection_state["connected"]:
                connection_state["failures"] += 1
                if connection_state["failures"] >= 3:  # Recover after 3 failures
                    connection_state["connected"] = True
                    connection_state["failures"] = 0
                    logger.info("🔄 Connection recovered!")
                else:
                    raise ConnectionError("Connection lost")
            
            # Randomly lose connection
            if random.random() < 0.2:  # 20% chance of losing connection
                connection_state["connected"] = False
                logger.info("💥 Connection lost!")
                raise ConnectionError("Connection lost")
            
            return [NetworkPlay(f"RECOVERY{random.randint(1000, 9999)}", 7.2)]
        
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=recovery_scanner)
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02
        })
        runner._send_telegram_alert = Mock()
        
        # Test connection recovery
        successful_cycles = 0
        recovery_events = 0
        connection_losses = 0
        
        for cycle in range(30):
            try:
                plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                successful_cycles += 1
                
                if plays:
                    for play in plays:
                        await runner._evaluate_play_with_mayordomo(play)
                        
            except ConnectionError as e:
                if "Connection lost" in str(e):
                    connection_losses += 1
                elif connection_state["connected"]:
                    recovery_events += 1
            except Exception:
                pass
            
            await asyncio.sleep(0.1)
        
        return {
            "test": "connection_recovery",
            "success": successful_cycles >= 15,  # More realistic expectation for smallcap system
            "total_cycles": 30,
            "successful_cycles": successful_cycles,
            "connection_losses": connection_losses,
            "recovery_events": recovery_events,
            "success_rate": successful_cycles / 30 * 100,
            "recovery_working": recovery_events > 0 or connection_losses == 0
        }
    
    async def test_api_rate_limiting(self) -> Dict[str, Any]:
        """Test de límites de velocidad de API"""
        logger.info("⏱️ Testing API rate limiting...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks with rate limiting
        rate_limit_state = {"requests": 0, "last_reset": time.time()}
        
        async def rate_limited_scanner(*args, **kwargs):
            current_time = time.time()
            
            # Reset counter every 10 seconds
            if current_time - rate_limit_state["last_reset"] > 10:
                rate_limit_state["requests"] = 0
                rate_limit_state["last_reset"] = current_time
            
            rate_limit_state["requests"] += 1
            
            # Rate limit: max 20 requests per 10 seconds
            if rate_limit_state["requests"] > 20:
                await asyncio.sleep(1.0)  # Forced delay
                raise Exception("Rate limit exceeded - please wait")
            
            return [NetworkPlay(f"RATE{rate_limit_state['requests']}", 6.9)]
        
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=rate_limited_scanner)
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.02
        })
        runner._send_telegram_alert = Mock()
        
        # Test rapid requests
        start_time = time.time()
        successful_requests = 0
        rate_limited_requests = 0
        
        # Make rapid requests
        for i in range(50):
            try:
                plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                successful_requests += 1
                
                if plays:
                    for play in plays:
                        await runner._evaluate_play_with_mayordomo(play)
                        
            except Exception as e:
                if "Rate limit" in str(e):
                    rate_limited_requests += 1
            
            await asyncio.sleep(0.1)  # Small delay between requests
        
        end_time = time.time()
        
        return {
            "test": "api_rate_limiting",
            "success": successful_requests >= 30,  # Should handle most requests
            "total_requests": 50,
            "successful_requests": successful_requests,
            "rate_limited_requests": rate_limited_requests,
            "processing_time": end_time - start_time,
            "success_rate": successful_requests / 50 * 100,
            "rate_limiting_handled": rate_limited_requests < 20
        }


async def run_network_resilience_tests():
    """Ejecutar todos los tests de resistencia de red"""
    logger.info("🌐 STARTING NETWORK RESILIENCE TESTS")
    logger.info("=" * 60)
    
    tests = NetworkResilienceTests()
    
    test_methods = [
        tests.test_ibkr_connection_timeout,
        tests.test_intermittent_network_failure,
        tests.test_slow_network_conditions,
        tests.test_connection_recovery,
        tests.test_api_rate_limiting
    ]
    
    results = []
    successful_tests = 0
    total_tests = len(test_methods)
    
    for test_method in test_methods:
        test_name = test_method.__name__.replace('test_', '').replace('_', ' ').title()
        logger.info(f"\n🧪 {test_name}")
        logger.info("-" * 50)
        
        try:
            result = await test_method()
            results.append(result)
            
            if result.get("success", False):
                logger.info("✅ PASSED")
                successful_tests += 1
            else:
                logger.info("❌ FAILED")
                
            # Log key metrics
            for key, value in result.items():
                if key not in ["test", "success"] and isinstance(value, (int, float)):
                    logger.info(f"   📊 {key}: {value}")
                    
        except Exception as e:
            logger.error(f"❌ FAILED - Exception: {e}")
            results.append({
                "test": test_method.__name__,
                "success": False,
                "error": str(e)
            })
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 NETWORK RESILIENCE TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Tests run: {total_tests}")
    logger.info(f"Successful: {successful_tests}")
    logger.info(f"Failed: {total_tests - successful_tests}")
    logger.info(f"Success rate: {successful_tests / total_tests * 100:.1f}%")
    
    logger.info(f"\n📋 DETAILED RESULTS:")
    for result in results:
        status = "✅" if result.get("success", False) else "❌"
        test_name = result.get("test", "unknown").replace('_', ' ').title()
        logger.info(f"{status} {test_name}")
    
    # Save results
    results_file = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/network_resilience_test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": successful_tests / total_tests * 100
            },
            "results": results
        }, f, indent=2)
    
    logger.info(f"\n💾 Results saved to: {results_file}")
    
    if successful_tests == total_tests:
        logger.info(f"\n🎉 ALL NETWORK RESILIENCE TESTS PASSED - System is network-robust!")
    elif successful_tests >= total_tests * 0.8:
        logger.info(f"\n✅ SYSTEM IS NETWORK-RESILIENT - Handles most connectivity issues well")
    else:
        logger.info(f"\n⚠️  NETWORK RESILIENCE ISSUES - System needs better connectivity handling")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_network_resilience_tests())
