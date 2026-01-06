"""
Production System Test Runner
Executes comprehensive tests to validate the complete production trading system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import unittest
import json
import time
from datetime import datetime
from typing import Dict, List, Any
import logging

# Import test modules
from test_production_system import TestProductionSystemUnit
from test_production_execution_flow import ProductionExecutionFlowTester
from test_production_scanner_execution import ProductionScannerExecutionTester

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionTestRunner:
    """Comprehensive test runner for production system"""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "unit_tests": {},
            "integration_tests": {},
            "execution_flow_tests": {},
            "scanner_execution_tests": {},
            "performance_tests": {},
            "summary": {}
        }
    
    def run_unit_tests(self) -> Dict[str, Any]:
        """Run unit tests for production system components"""
        print("🧪 RUNNING UNIT TESTS")
        print("=" * 50)
        
        # Create test suite
        suite = unittest.TestSuite()
        suite.addTest(unittest.makeSuite(TestProductionSystemUnit))
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        result = runner.run(suite)
        
        # Collect results
        unit_results = {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success_rate": (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun if result.testsRun > 0 else 0,
            "failure_details": [str(failure) for failure in result.failures],
            "error_details": [str(error) for error in result.errors]
        }
        
        self.test_results["unit_tests"] = unit_results
        
        print(f"\n✅ Unit Tests: {unit_results['tests_run']} run, {unit_results['success_rate']:.1%} success rate")
        return unit_results
    
    async def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests for complete system flow"""
        print("\n🔗 RUNNING INTEGRATION TESTS")
        print("=" * 50)
        
        tester = ProductionExecutionFlowTester()
        
        # Test scenarios
        scenarios = [
            ("high_quality_gaps", 2),
            ("mixed_quality", 2), 
            ("risk_management", 3),
            ("edge_cases", 1)
        ]
        
        integration_results = {
            "scenarios_tested": len(scenarios),
            "scenarios_passed": 0,
            "scenarios_failed": 0,
            "scenario_details": []
        }
        
        for scenario_name, expected_executions in scenarios:
            print(f"\n🧪 Testing integration scenario: {scenario_name}")
            
            try:
                result = await tester.test_scenario(scenario_name, expected_executions)
                
                if result.get("success", False):
                    integration_results["scenarios_passed"] += 1
                    status = "✅ PASSED"
                else:
                    integration_results["scenarios_failed"] += 1
                    status = "❌ FAILED"
                
                print(f"{status}: {result.get('trades_executed', 0)} trades from {result.get('plays_detected', 0)} plays")
                
                integration_results["scenario_details"].append({
                    "scenario": scenario_name,
                    "success": result.get("success", False),
                    "trades_executed": result.get("trades_executed", 0),
                    "plays_detected": result.get("plays_detected", 0),
                    "processing_time": result.get("processing_time_seconds", 0),
                    "expectation_met": result.get("expectation_met", False)
                })
                
            except Exception as e:
                integration_results["scenarios_failed"] += 1
                print(f"❌ FAILED: {e}")
                integration_results["scenario_details"].append({
                    "scenario": scenario_name,
                    "success": False,
                    "error": str(e)
                })
        
        integration_results["success_rate"] = integration_results["scenarios_passed"] / integration_results["scenarios_tested"]
        self.test_results["integration_tests"] = integration_results
        
        print(f"\n✅ Integration Tests: {integration_results['scenarios_passed']}/{integration_results['scenarios_tested']} passed")
        return integration_results
    
    async def run_scanner_execution_tests(self) -> Dict[str, Any]:
        """Run scanner-to-execution flow tests"""
        print("\n🔍➡️⚡ RUNNING SCANNER-EXECUTION TESTS")
        print("=" * 50)
        
        tester = ProductionScannerExecutionTester()
        
        # Test scenarios
        scenarios = ["morning_gaps", "news_driven", "mixed_signals"]
        
        scanner_results = {
            "scenarios_tested": len(scenarios),
            "scenarios_passed": 0,
            "scenarios_failed": 0,
            "scenario_details": [],
            "performance_metrics": {}
        }
        
        for scenario in scenarios:
            print(f"\n🧪 Testing scanner-execution: {scenario}")
            
            try:
                result = await tester.test_complete_execution_flow(scenario)
                
                if result.get("success", False):
                    scanner_results["scenarios_passed"] += 1
                    status = "✅ PASSED"
                    
                    print(f"{status}: {result['orders_filled']} orders filled from {result['plays_detected']} plays")
                    print(f"   📊 Execution rate: {result['execution_rate']:.1%}")
                    print(f"   ⏱️  Processing time: {result['processing_time_seconds']:.3f}s")
                else:
                    scanner_results["scenarios_failed"] += 1
                    status = "❌ FAILED"
                    print(f"{status}: {result.get('error', 'Unknown error')}")
                
                scanner_results["scenario_details"].append({
                    "scenario": scenario,
                    "success": result.get("success", False),
                    "plays_detected": result.get("plays_detected", 0),
                    "orders_filled": result.get("orders_filled", 0),
                    "execution_rate": result.get("execution_rate", 0),
                    "processing_time": result.get("processing_time_seconds", 0)
                })
                
            except Exception as e:
                scanner_results["scenarios_failed"] += 1
                print(f"❌ FAILED: {e}")
                scanner_results["scenario_details"].append({
                    "scenario": scenario,
                    "success": False,
                    "error": str(e)
                })
        
        scanner_results["success_rate"] = scanner_results["scenarios_passed"] / scanner_results["scenarios_tested"]
        self.test_results["scanner_execution_tests"] = scanner_results
        
        print(f"\n✅ Scanner-Execution Tests: {scanner_results['scenarios_passed']}/{scanner_results['scenarios_tested']} passed")
        return scanner_results
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance and stress tests"""
        print("\n🚀 RUNNING PERFORMANCE TESTS")
        print("=" * 50)
        
        tester = ProductionScannerExecutionTester()
        
        performance_results = {
            "load_test": {},
            "stress_metrics": {},
            "benchmarks": {}
        }
        
        try:
            # Load test
            print("🧪 Running load test...")
            load_result = await tester.test_performance_under_load()
            
            if load_result.get("success", False):
                print(f"✅ Load test passed:")
                print(f"   📊 Processed: {load_result['total_plays']} plays")
                print(f"   🚀 Throughput: {load_result['plays_per_second']:.1f} plays/sec")
                print(f"   ⏱️  Avg time per play: {load_result['avg_time_per_play']:.3f}s")
                
                performance_results["load_test"] = {
                    "success": True,
                    "total_plays": load_result["total_plays"],
                    "throughput_plays_per_sec": load_result["plays_per_second"],
                    "avg_time_per_play": load_result["avg_time_per_play"],
                    "orders_placed": load_result["orders_placed"]
                }
                
                # Set benchmarks
                performance_results["benchmarks"] = {
                    "min_throughput_plays_per_sec": 10.0,  # Minimum acceptable throughput
                    "max_avg_time_per_play": 0.5,          # Maximum time per play
                    "throughput_meets_benchmark": load_result["plays_per_second"] >= 10.0,
                    "timing_meets_benchmark": load_result["avg_time_per_play"] <= 0.5
                }
                
            else:
                print("❌ Load test failed")
                performance_results["load_test"] = {"success": False, "error": "Load test failed"}
                
        except Exception as e:
            print(f"❌ Performance tests failed: {e}")
            performance_results["load_test"] = {"success": False, "error": str(e)}
        
        self.test_results["performance_tests"] = performance_results
        
        print(f"\n✅ Performance Tests completed")
        return performance_results
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        print("\n📊 GENERATING TEST SUMMARY")
        print("=" * 50)
        
        # Calculate overall metrics
        total_tests = 0
        total_passed = 0
        
        # Unit tests
        unit = self.test_results.get("unit_tests", {})
        if unit:
            unit_tests = unit.get("tests_run", 0)
            unit_passed = unit_tests - unit.get("failures", 0) - unit.get("errors", 0)
            total_tests += unit_tests
            total_passed += unit_passed
        
        # Integration tests
        integration = self.test_results.get("integration_tests", {})
        if integration:
            int_tests = integration.get("scenarios_tested", 0)
            int_passed = integration.get("scenarios_passed", 0)
            total_tests += int_tests
            total_passed += int_passed
        
        # Scanner-execution tests
        scanner = self.test_results.get("scanner_execution_tests", {})
        if scanner:
            scan_tests = scanner.get("scenarios_tested", 0)
            scan_passed = scanner.get("scenarios_passed", 0)
            total_tests += scan_tests
            total_passed += scan_passed
        
        # Performance tests
        performance = self.test_results.get("performance_tests", {})
        perf_passed = 1 if performance.get("load_test", {}).get("success", False) else 0
        total_tests += 1
        total_passed += perf_passed
        
        # Overall success rate
        overall_success_rate = total_passed / total_tests if total_tests > 0 else 0
        
        summary = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_tests - total_passed,
            "overall_success_rate": overall_success_rate,
            "test_categories": {
                "unit_tests": {
                    "tests": unit.get("tests_run", 0),
                    "passed": unit_tests - unit.get("failures", 0) - unit.get("errors", 0) if unit else 0,
                    "success_rate": unit.get("success_rate", 0)
                },
                "integration_tests": {
                    "tests": integration.get("scenarios_tested", 0),
                    "passed": integration.get("scenarios_passed", 0),
                    "success_rate": integration.get("success_rate", 0)
                },
                "scanner_execution_tests": {
                    "tests": scanner.get("scenarios_tested", 0),
                    "passed": scanner.get("scenarios_passed", 0),
                    "success_rate": scanner.get("success_rate", 0)
                },
                "performance_tests": {
                    "tests": 1,
                    "passed": perf_passed,
                    "success_rate": perf_passed
                }
            },
            "recommendations": self._generate_recommendations()
        }
        
        self.test_results["summary"] = summary
        
        # Print summary
        print(f"📈 OVERALL RESULTS:")
        print(f"   Total tests: {total_tests}")
        print(f"   Passed: {total_passed}")
        print(f"   Failed: {total_tests - total_passed}")
        print(f"   Success rate: {overall_success_rate:.1%}")
        
        print(f"\n📋 BY CATEGORY:")
        for category, metrics in summary["test_categories"].items():
            print(f"   {category}: {metrics['passed']}/{metrics['tests']} ({metrics['success_rate']:.1%})")
        
        return summary
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check unit test results
        unit = self.test_results.get("unit_tests", {})
        if unit.get("success_rate", 0) < 1.0:
            recommendations.append("Fix unit test failures before production deployment")
        
        # Check integration test results
        integration = self.test_results.get("integration_tests", {})
        if integration.get("success_rate", 0) < 0.8:
            recommendations.append("Address integration test failures - core functionality may be compromised")
        
        # Check performance
        performance = self.test_results.get("performance_tests", {})
        load_test = performance.get("load_test", {})
        if not load_test.get("success", False):
            recommendations.append("Performance tests failed - system may not handle production load")
        
        benchmarks = performance.get("benchmarks", {})
        if not benchmarks.get("throughput_meets_benchmark", True):
            recommendations.append("System throughput below benchmark - consider optimization")
        
        if not benchmarks.get("timing_meets_benchmark", True):
            recommendations.append("Processing time per play too slow - optimize execution pipeline")
        
        # Scanner-execution tests
        scanner = self.test_results.get("scanner_execution_tests", {})
        if scanner.get("success_rate", 0) < 0.8:
            recommendations.append("Scanner-to-execution flow has issues - verify trading pipeline")
        
        if not recommendations:
            recommendations.append("All tests passed - system ready for production deployment")
        
        return recommendations
    
    def save_results(self, filename: str = None):
        """Save test results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/Users/carlos/proyectos/TRADING/1_PROYECTOS_ACTIVOS/CLAUDE/trading_system_v3/tests/production_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            print(f"\n💾 Test results saved to: {filename}")
        except Exception as e:
            print(f"\n⚠️  Could not save results: {e}")
    
    async def run_all_tests(self):
        """Run all production system tests"""
        print("🚀 COMPREHENSIVE PRODUCTION SYSTEM TESTS")
        print("=" * 70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        start_time = time.time()
        
        try:
            # Run all test categories
            self.run_unit_tests()
            await self.run_integration_tests()
            await self.run_scanner_execution_tests()
            await self.run_performance_tests()
            
            # Generate summary
            summary = self.generate_summary()
            
            end_time = time.time()
            total_time = end_time - start_time
            
            print(f"\n⏱️  Total test time: {total_time:.2f} seconds")
            
            # Print recommendations
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(summary["recommendations"], 1):
                print(f"   {i}. {rec}")
            
            # Save results
            self.save_results()
            
            # Final status
            success_rate = summary["overall_success_rate"]
            if success_rate >= 0.9:
                print(f"\n🎉 EXCELLENT: {success_rate:.1%} success rate - Production ready!")
            elif success_rate >= 0.8:
                print(f"\n✅ GOOD: {success_rate:.1%} success rate - Minor issues to address")
            elif success_rate >= 0.6:
                print(f"\n⚠️  FAIR: {success_rate:.1%} success rate - Significant issues need attention")
            else:
                print(f"\n❌ POOR: {success_rate:.1%} success rate - Major problems, not production ready")
            
            return self.test_results
            
        except Exception as e:
            print(f"\n❌ Test execution failed: {e}")
            import traceback
            traceback.print_exc()
            return None

async def main():
    """Main test execution function"""
    runner = ProductionTestRunner()
    results = await runner.run_all_tests()
    
    if results:
        print(f"\n✅ Test execution completed successfully")
        return 0
    else:
        print(f"\n❌ Test execution failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
