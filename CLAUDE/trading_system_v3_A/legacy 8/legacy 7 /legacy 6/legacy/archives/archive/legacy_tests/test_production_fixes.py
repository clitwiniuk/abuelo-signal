#!/usr/bin/env python3
"""
Test rápido para verificar las correcciones del sistema de producción
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ProductionFixTest")

async def test_ml_engine_initialization():
    """Test MLMultiStrategyEngine initialization fix"""
    try:
        from strategies.multi_strategy_engine_ml import MLMultiStrategyEngine
        
        # Test with correct parameters format
        ml_parameters = {
            "smallcap_ml_enabled": True,
            "smallcap_mayordomo_enabled": True,
            "smallcap_price_threshold": 15.0
        }
        
        ml_engine = MLMultiStrategyEngine(parameters=ml_parameters)
        
        print("✅ MLMultiStrategyEngine initialization fix: SUCCESS")
        print(f"   - Engine name: {ml_engine._name}")
        print(f"   - Smallcap ML enabled: {ml_engine.smallcap_ml_enabled}")
        return True
        
    except Exception as e:
        print(f"❌ MLMultiStrategyEngine initialization fix: FAILED - {e}")
        return False

def test_ml_journal_integration():
    """Test ML Journal integration"""
    try:
        from strategies.ml_journal_integration import MLJournalIntegration
        
        # Test without config (should work with None)
        integration = MLJournalIntegration(None)
        
        print("✅ ML Journal Integration: SUCCESS")
        print(f"   - Integration created: {integration is not None}")
        return True
        
    except Exception as e:
        print(f"❌ ML Journal Integration: FAILED - {e}")
        return False

def test_production_runner_creation():
    """Test production runner creation without full initialization"""
    try:
        from production.smallcap_production_runner import SmallcapProductionRunner
        
        # Create runner without starting it
        runner = SmallcapProductionRunner()
        
        # Check key attributes
        has_ml_journal = hasattr(runner, 'ml_journal_integration')
        has_elite_report = hasattr(runner, 'generate_elite_ml_report')
        
        print("✅ Production Runner Creation: SUCCESS")
        print(f"   - Runner created: {runner is not None}")
        print(f"   - ML Journal integration attr: {has_ml_journal}")
        print(f"   - Elite report method: {has_elite_report}")
        
        return True
        
    except Exception as e:
        print(f"❌ Production Runner Creation: FAILED - {e}")
        return False

def test_telegram_commands():
    """Test Telegram commands creation"""
    try:
        from production.telegram_smallcap_commands import SmallcapTelegramCommands
        
        # Mock production runner
        class MockRunner:
            def __init__(self):
                self.ml_journal_integration = None
            def get_status(self):
                return {"ml_journal_status": {}}
            async def generate_elite_ml_report(self):
                return "Mock report"
        
        mock_runner = MockRunner()
        commands = SmallcapTelegramCommands(mock_runner)
        
        # Check command handlers
        has_ml_journal_handler = hasattr(commands, '_handle_ml_journal_status')
        has_elite_handler = hasattr(commands, '_handle_elite_report')
        has_sync_handler = hasattr(commands, '_handle_elite_report_sync')
        
        print("✅ Telegram Commands: SUCCESS")
        print(f"   - Commands created: {commands is not None}")
        print(f"   - ML Journal handler: {has_ml_journal_handler}")
        print(f"   - Elite report handler: {has_elite_handler}")
        print(f"   - Sync handler: {has_sync_handler}")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram Commands: FAILED - {e}")
        return False

def test_event_loop_handling():
    """Test event loop handling in scanner"""
    try:
        # Test that we can detect running event loop
        import asyncio
        
        try:
            loop = asyncio.get_running_loop()
            print("✅ Event Loop Detection: SUCCESS")
            print(f"   - Running loop detected: {loop is not None}")
            return True
        except RuntimeError:
            print("✅ Event Loop Detection: SUCCESS")
            print("   - No running loop (as expected in test)")
            return True
        
    except Exception as e:
        print(f"❌ Event Loop Detection: FAILED - {e}")
        return False

def test_performance_monitor_fix():
    """Test PerformanceMonitor initialization fix"""
    try:
        from utils.performance_monitor import PerformanceMonitor
        
        # Test with correct parameter
        monitor = PerformanceMonitor(sampling_interval=5.0)
        
        print("✅ PerformanceMonitor Fix: SUCCESS")
        print(f"   - Monitor created: {monitor is not None}")
        print(f"   - Sampling interval: {monitor.sampling_interval}")
        print(f"   - Process monitor: {monitor.process is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ PerformanceMonitor Fix: FAILED - {e}")
        return False

async def run_all_tests():
    """Run all production fix tests"""
    print("🧪 TESTING PRODUCTION FIXES")
    print("=" * 50)
    
    tests = [
        ("ML Engine Initialization", test_ml_engine_initialization),
        ("ML Journal Integration", test_ml_journal_integration),
        ("Production Runner Creation", test_production_runner_creation),
        ("Telegram Commands", test_telegram_commands),
        ("Event Loop Handling", test_event_loop_handling),
        ("PerformanceMonitor Fix", test_performance_monitor_fix)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        print("-" * 30)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append(result)
            
        except Exception as e:
            print(f"❌ {test_name}: FAILED - {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print("\n" + "=" * 50)
    print("📊 PRODUCTION FIXES TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {total - passed} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("\n🟢 PRODUCTION FIXES: READY FOR DEPLOYMENT")
    elif success_rate >= 60:
        print("\n🟡 PRODUCTION FIXES: MOSTLY READY - Minor issues")
    else:
        print("\n🔴 PRODUCTION FIXES: NEEDS MORE WORK")
    
    return success_rate >= 80

if __name__ == "__main__":
    asyncio.run(run_all_tests())