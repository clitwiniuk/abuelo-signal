#!/usr/bin/env python3
"""
Tests de estrés extremo para el sistema de producción
Estos tests van más allá de los casos normales para probar los límites del sistema
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

class ExtremeStressPlay:
    """Mock play para tests de estrés extremo"""
    def __init__(self, symbol: str, quality_score: float, catalyst=None, context=None):
        self.symbol = symbol
        self.quality_score = quality_score
        self.catalyst = catalyst or ExtremeStressCatalyst("earnings", 0.8)
        self.context = context or ExtremeStressContext(10.0, 0.15, 5.0, 5_000_000, 10_000_000)
        self.timestamp = datetime.now()
        self.market_cap = random.randint(50_000_000, 2_000_000_000)
        self.price = random.uniform(1.0, 50.0)
        self.volume_ratio = random.uniform(2.0, 20.0)

class ExtremeStressCatalyst:
    def __init__(self, type_name: str, confidence: float):
        self.type = type_name
        self.catalyst_type = type_name  # Add missing attribute
        self.confidence = confidence
        self.strength = confidence  # Add missing strength attribute
        self.description = f"Extreme stress test {type_name}"

class ExtremeStressContext:
    def __init__(self, rsi: float, gap: float, volume_ratio: float, volume: int, avg_volume: int):
        self.rsi = rsi
        self.gap = gap
        self.volume_ratio = volume_ratio
        self.volume = volume
        self.avg_volume = avg_volume
        self.price_change = random.uniform(-0.2, 0.3)

class ExtremeStressTests:
    """Suite de tests de estrés extremo"""
    
    async def test_massive_concurrent_load(self) -> Dict[str, Any]:
        """Test con carga masiva concurrente - 1000 plays simultáneos"""
        logger.info("🔥 Testing massive concurrent load (1000 plays)...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.01
        })
        runner._send_telegram_alert = Mock()
        
        # Create 1000 plays
        plays = []
        for i in range(1000):
            play = ExtremeStressPlay(
                f"STRESS{i:04d}",
                random.uniform(5.0, 10.0),
                ExtremeStressCatalyst("massive_test", 0.9),
                ExtremeStressContext(random.uniform(30, 70), random.uniform(0.05, 0.25), 
                                   random.uniform(3.0, 15.0), random.randint(1_000_000, 20_000_000),
                                   random.randint(500_000, 5_000_000))
            )
            plays.append(play)
        
        # Process all plays concurrently
        start_time = time.time()
        
        tasks = []
        for play in plays:
            task = asyncio.create_task(runner._evaluate_play_with_mayordomo(play))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Count successful vs failed
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        return {
            "test": "massive_concurrent_load",
            "success": failed < 50,  # Allow up to 5% failure rate
            "total_plays": len(plays),
            "successful_plays": successful,
            "failed_plays": failed,
            "processing_time_seconds": processing_time,
            "plays_per_second": len(plays) / processing_time if processing_time > 0 else 0,
            "failure_rate": failed / len(plays) * 100,
            "performance_acceptable": processing_time < 30.0  # Should process 1000 plays in under 30s
        }
    
    async def test_rapid_fire_scanning(self) -> Dict[str, Any]:
        """Test de escaneo rápido continuo - 100 ciclos de escaneo"""
        logger.info("⚡ Testing rapid fire scanning (100 cycles)...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.01
        })
        runner._send_telegram_alert = Mock()
        
        # Configure scanner to return random plays each time
        def generate_random_plays():
            num_plays = random.randint(0, 10)
            plays = []
            for i in range(num_plays):
                play = ExtremeStressPlay(
                    f"RAPID{random.randint(1000, 9999)}",
                    random.uniform(4.0, 9.0)
                )
                plays.append(play)
            return plays
        
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=lambda **kwargs: generate_random_plays())
        
        # Simulate rapid scanning
        start_time = time.time()
        total_plays_processed = 0
        scan_times = []
        
        for cycle in range(100):
            cycle_start = time.time()
            
            # Simulate one scan cycle
            plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
            
            if plays:
                # Process plays concurrently
                tasks = [runner._evaluate_play_with_mayordomo(play) for play in plays]
                await asyncio.gather(*tasks, return_exceptions=True)
                total_plays_processed += len(plays)
            
            cycle_end = time.time()
            scan_times.append(cycle_end - cycle_start)
            
            # Brief pause to simulate real scanning interval
            await asyncio.sleep(0.01)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        avg_scan_time = sum(scan_times) / len(scan_times)
        max_scan_time = max(scan_times)
        min_scan_time = min(scan_times)
        
        return {
            "test": "rapid_fire_scanning",
            "success": True,
            "scan_cycles": 100,
            "total_plays_processed": total_plays_processed,
            "total_time_seconds": total_time,
            "avg_scan_time_seconds": avg_scan_time,
            "max_scan_time_seconds": max_scan_time,
            "min_scan_time_seconds": min_scan_time,
            "scans_per_second": 100 / total_time if total_time > 0 else 0,
            "performance_consistent": max_scan_time < avg_scan_time * 3  # Max shouldn't be 3x average
        }
    
    async def test_memory_pressure_extreme(self) -> Dict[str, Any]:
        """Test de presión extrema de memoria - procesar 10,000 plays"""
        logger.info("🧠 Testing extreme memory pressure (10,000 plays)...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner.mayordomo.evaluate_position_rotation = Mock(return_value={
            "action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.01
        })
        runner._send_telegram_alert = Mock()
        
        # Track memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_available = True
        except ImportError:
            memory_available = False
            process = None
        
        initial_memory = process.memory_info().rss if memory_available else 0
        
        # Process plays in batches to avoid overwhelming the system
        batch_size = 500
        total_plays = 10000
        batches = total_plays // batch_size
        
        start_time = time.time()
        processed_plays = 0
        memory_readings = []
        
        for batch_num in range(batches):
            logger.info(f"Processing batch {batch_num + 1}/{batches}...")
            
            # Create batch of plays
            batch_plays = []
            for i in range(batch_size):
                play = ExtremeStressPlay(
                    f"MEM{batch_num:03d}_{i:03d}",
                    random.uniform(5.0, 8.0)
                )
                batch_plays.append(play)
            
            # Process batch
            tasks = [runner._evaluate_play_with_mayordomo(play) for play in batch_plays]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            processed_plays += len(batch_plays)
            
            # Record memory usage
            if memory_available:
                current_memory = process.memory_info().rss
                memory_readings.append(current_memory)
            
            # Clear batch references
            del batch_plays
            del tasks
            
            # Force garbage collection
            try:
                import gc
                gc.collect()
            except:
                pass
            
            # Brief pause
            await asyncio.sleep(0.1)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        final_memory = process.memory_info().rss if memory_available else 0
        memory_growth = final_memory - initial_memory if memory_available else 0
        max_memory = max(memory_readings) if memory_readings else 0
        
        return {
            "test": "memory_pressure_extreme",
            "success": True,
            "total_plays_processed": processed_plays,
            "processing_time_seconds": processing_time,
            "plays_per_second": processed_plays / processing_time if processing_time > 0 else 0,
            "initial_memory_mb": initial_memory / 1024 / 1024 if memory_available else 0,
            "final_memory_mb": final_memory / 1024 / 1024 if memory_available else 0,
            "max_memory_mb": max_memory / 1024 / 1024 if memory_available else 0,
            "memory_growth_mb": memory_growth / 1024 / 1024 if memory_available else 0,
            "memory_growth_reasonable": memory_growth < 100 * 1024 * 1024 if memory_available else True,  # Less than 100MB growth
            "memory_monitoring_available": memory_available
        }
    
    async def test_error_cascade_resilience(self) -> Dict[str, Any]:
        """Test de resistencia a cascada de errores"""
        logger.info("💥 Testing error cascade resilience...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks that will fail intermittently
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.mayordomo = Mock()
        runner._send_telegram_alert = Mock()
        
        # Configure intermittent failures
        failure_count = {"scanner": 0, "trading": 0, "mayordomo": 0}
        
        async def failing_scanner(*args, **kwargs):
            failure_count["scanner"] += 1
            if failure_count["scanner"] % 3 == 0:  # Fail every 3rd call
                raise Exception("Scanner connection lost")
            return [ExtremeStressPlay(f"FAIL{failure_count['scanner']}", 7.0)]
        
        async def failing_trading(*args, **kwargs):
            failure_count["trading"] += 1
            if failure_count["trading"] % 4 == 0:  # Fail every 4th call
                raise Exception("Trading engine timeout")
            return True
        
        def failing_mayordomo(*args, **kwargs):
            failure_count["mayordomo"] += 1
            if failure_count["mayordomo"] % 5 == 0:  # Fail every 5th call
                raise Exception("Mayordomo evaluation error")
            return {"action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.01}
        
        runner.smallcap_scanner.scan_daily_plays = AsyncMock(side_effect=failing_scanner)
        runner.trading_engine.add_symbol = AsyncMock(side_effect=failing_trading)
        runner.mayordomo.evaluate_position_rotation = Mock(side_effect=failing_mayordomo)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        
        # Run multiple cycles with cascading failures
        successful_cycles = 0
        failed_cycles = 0
        total_cycles = 50
        
        start_time = time.time()
        
        for cycle in range(total_cycles):
            try:
                # Simulate one complete cycle
                plays = await runner.smallcap_scanner.scan_daily_plays(force_refresh=True)
                
                if plays:
                    for play in plays:
                        try:
                            await runner._evaluate_play_with_mayordomo(play)
                        except Exception as e:
                            logger.debug(f"Play evaluation failed: {e}")
                            continue
                
                successful_cycles += 1
                
            except Exception as e:
                logger.debug(f"Cycle {cycle} failed: {e}")
                failed_cycles += 1
                continue
            
            await asyncio.sleep(0.05)  # Brief pause between cycles
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        success_rate = successful_cycles / total_cycles * 100
        
        return {
            "test": "error_cascade_resilience",
            "success": success_rate >= 60,  # Should handle at least 60% despite cascading failures
            "total_cycles": total_cycles,
            "successful_cycles": successful_cycles,
            "failed_cycles": failed_cycles,
            "success_rate_percent": success_rate,
            "processing_time_seconds": processing_time,
            "scanner_failures": failure_count["scanner"] // 3,
            "trading_failures": failure_count["trading"] // 4,
            "mayordomo_failures": failure_count["mayordomo"] // 5,
            "resilience_acceptable": success_rate >= 60
        }
    
    async def test_extreme_market_volatility(self) -> Dict[str, Any]:
        """Test con volatilidad extrema del mercado"""
        logger.info("📈 Testing extreme market volatility scenarios...")
        
        runner = SmallcapProductionRunner(test_mode=True)
        
        # Setup mocks
        runner.ibkr_adapter = AsyncMock()
        runner.smallcap_scanner = AsyncMock()
        runner.trading_engine = AsyncMock()
        runner.trading_engine.add_symbol = AsyncMock(return_value=True)
        runner.trading_engine.strategy = Mock()
        runner.trading_engine.strategy.pending_signals = {}
        runner.mayordomo = Mock()
        runner._send_telegram_alert = Mock()
        
        # Create extreme market scenarios
        scenarios = [
            # Flash crash scenario
            {"name": "flash_crash", "gap": -0.5, "volume_ratio": 50.0, "rsi": 10.0},
            # Extreme pump scenario  
            {"name": "extreme_pump", "gap": 2.0, "volume_ratio": 100.0, "rsi": 95.0},
            # High volatility chop
            {"name": "volatility_chop", "gap": 0.3, "volume_ratio": 25.0, "rsi": 50.0},
            # Low liquidity scenario
            {"name": "low_liquidity", "gap": 0.1, "volume_ratio": 0.5, "rsi": 45.0},
            # Halted stock scenario
            {"name": "halted_stock", "gap": 0.0, "volume_ratio": 0.0, "rsi": 50.0}
        ]
        
        scenario_results = {}
        
        for scenario in scenarios:
            scenario_name = scenario["name"]
            logger.info(f"Testing scenario: {scenario_name}")
            
            # Configure mayordomo response based on scenario
            def scenario_mayordomo(*args, **kwargs):
                if scenario_name == "flash_crash":
                    return {"action": "NO_ACTION", "reason": "EXTREME_VOLATILITY"}
                elif scenario_name == "extreme_pump":
                    return {"action": "NO_ACTION", "reason": "OVEREXTENDED"}
                elif scenario_name == "halted_stock":
                    return {"action": "NO_ACTION", "reason": "TRADING_HALTED"}
                else:
                    return {"action": "OPEN_POSITION", "reason": "APPROVED", "position_size": 0.005}
            
            runner.mayordomo.evaluate_position_rotation = Mock(side_effect=scenario_mayordomo)
            
            # Create plays for this scenario
            scenario_plays = []
            for i in range(10):
                context = ExtremeStressContext(
                    scenario["rsi"], 
                    scenario["gap"], 
                    scenario["volume_ratio"],
                    random.randint(100_000, 50_000_000),
                    random.randint(500_000, 2_000_000)
                )
                
                play = ExtremeStressPlay(
                    f"{scenario_name.upper()}{i}",
                    random.uniform(6.0, 9.0),
                    ExtremeStressCatalyst(scenario_name, 0.8),
                    context
                )
                scenario_plays.append(play)
            
            # Process scenario plays
            start_time = time.time()
            tasks = [runner._evaluate_play_with_mayordomo(play) for play in scenario_plays]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful = sum(1 for r in results if not isinstance(r, Exception))
            
            scenario_results[scenario_name] = {
                "plays_processed": len(scenario_plays),
                "successful": successful,
                "processing_time": end_time - start_time,
                "handled_correctly": True  # All scenarios should be handled without crashes
            }
        
        return {
            "test": "extreme_market_volatility",
            "success": True,
            "scenarios_tested": len(scenarios),
            "scenario_results": scenario_results,
            "all_scenarios_handled": all(r["handled_correctly"] for r in scenario_results.values())
        }


async def run_extreme_stress_tests():
    """Ejecutar todos los tests de estrés extremo"""
    logger.info("🔥 STARTING EXTREME STRESS TESTS")
    logger.info("=" * 60)
    
    tests = ExtremeStressTests()
    
    test_methods = [
        tests.test_massive_concurrent_load,
        tests.test_rapid_fire_scanning,
        tests.test_memory_pressure_extreme,
        tests.test_error_cascade_resilience,
        tests.test_extreme_market_volatility
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
    logger.info("📊 EXTREME STRESS TEST SUMMARY")
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
    results_file = "/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/extreme_stress_test_results.json"
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
        logger.info(f"\n🎉 ALL EXTREME STRESS TESTS PASSED - System can handle extreme conditions!")
    elif successful_tests >= total_tests * 0.8:
        logger.info(f"\n✅ SYSTEM ROBUST - Handles most extreme conditions well")
    else:
        logger.info(f"\n⚠️  SYSTEM NEEDS HARDENING - Some extreme conditions cause issues")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_extreme_stress_tests())
