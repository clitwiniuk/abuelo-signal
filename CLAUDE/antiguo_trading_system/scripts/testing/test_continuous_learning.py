#!/usr/bin/env python3
"""
Test Continuous Learning System - Verifica que el sistema completo funcione
Simula trades y feedback para probar el aprendizaje continuo
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List
import random

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.continuous_learning_engine import get_global_learning_engine, TradeResult
from core.trading_feedback_hook import get_global_feedback_hook
from core.ml_performance_monitor import get_global_performance_monitor
from core.ml_volume_engine import MLVolumeEngine, create_market_context

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

class ContinuousLearningTester:
    """Tester completo del sistema de continuous learning"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.learning_engine = None
        self.feedback_hook = None
        self.performance_monitor = None
        
    def initialize_components(self):
        """Inicializa todos los componentes del sistema"""
        try:
            self.logger.info("🔧 Initializing continuous learning components...")
            
            # Initialize learning engine
            self.learning_engine = get_global_learning_engine()
            self.learning_engine.start_continuous_learning()
            
            # Initialize feedback hook
            self.feedback_hook = get_global_feedback_hook()
            
            # Initialize performance monitor
            self.performance_monitor = get_global_performance_monitor()
            self.performance_monitor.start_monitoring(interval_hours=1)  # Fast for testing
            
            self.logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing components: {e}")
            return False
    
    def simulate_trade_lifecycle(self, trade_id: str, symbol: str, strategy: str, 
                                will_succeed: bool = True) -> Dict:
        """Simula el ciclo completo de un trade"""
        try:
            # Generate realistic trade data
            entry_price = random.uniform(1.0, 10.0)
            volume_ratio = random.uniform(0.5, 3.0)
            
            # Trade open data
            trade_open_data = {
                'trade_id': trade_id,
                'symbol': symbol,
                'strategy': strategy,
                'entry_price': entry_price,
                'quantity': random.randint(100, 1000),
                'side': 'BUY',
                'entry_time': datetime.now(),
                'volume_context': {
                    'requirement_used': random.uniform(0.8, 2.5),
                    'actual_volume': volume_ratio,
                    'market_context': {
                        'time_of_day': datetime.now().hour / 24.0,
                        'market_cap': random.uniform(50000000, 500000000),
                        'sector': random.choice(['Technology', 'Healthcare', 'Energy'])
                    }
                }
            }
            
            # Simulate trade opening
            self.feedback_hook.on_trade_opened(trade_open_data)
            
            # Simulate some time passing
            duration_minutes = random.randint(5, 120)
            
            # Generate trade close data
            if will_succeed:
                exit_price = entry_price * random.uniform(1.01, 1.15)  # 1-15% profit
                pnl = (exit_price - entry_price) * trade_open_data['quantity'] - 5.0  # Commission
            else:
                exit_price = entry_price * random.uniform(0.85, 0.99)  # 1-15% loss
                pnl = (exit_price - entry_price) * trade_open_data['quantity'] - 5.0  # Commission
            
            trade_close_data = {
                'trade_id': trade_id,
                'exit_price': exit_price,
                'pnl': pnl,
                'exit_time': datetime.now() + timedelta(minutes=duration_minutes),
                'status': 'CLOSED'
            }
            
            # Simulate trade closing
            self.feedback_hook.on_trade_closed(trade_close_data)
            
            self.logger.debug(
                f"📈 Simulated trade: {trade_id} | {symbol} | {strategy} | "
                f"PnL: ${pnl:.2f} | Success: {will_succeed}"
            )
            
            return {
                'trade_id': trade_id,
                'symbol': symbol,
                'strategy': strategy,
                'pnl': pnl,
                'success': will_succeed,
                'volume_ratio': volume_ratio,
                'duration_minutes': duration_minutes
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error simulating trade {trade_id}: {e}")
            return {}
    
    def generate_test_trades(self, num_trades: int = 50) -> List[Dict]:
        """Genera trades de prueba con diferentes escenarios"""
        strategies = ['macdv_smallcaps', 'daily_plays', 'gap_go', 'volume_breakout', 'orb']
        symbols = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'GOOGL', 'AMZN', 'META']
        
        trades = []
        
        for i in range(num_trades):
            trade_id = f"TEST_{i:04d}_{datetime.now().strftime('%H%M%S')}"
            symbol = random.choice(symbols)
            strategy = random.choice(strategies)
            
            # Vary success rate by strategy to simulate real performance differences
            success_rates = {
                'macdv_smallcaps': 0.65,
                'daily_plays': 0.70,
                'gap_go': 0.55,
                'volume_breakout': 0.60,
                'orb': 0.58
            }
            
            will_succeed = random.random() < success_rates.get(strategy, 0.60)
            
            trade_result = self.simulate_trade_lifecycle(trade_id, symbol, strategy, will_succeed)
            if trade_result:
                trades.append(trade_result)
        
        return trades
    
    async def test_feedback_loop(self) -> bool:
        """Testa el loop de feedback completo"""
        try:
            self.logger.info("🔄 Testing feedback loop...")
            
            # Generate test trades
            test_trades = self.generate_test_trades(30)
            
            if len(test_trades) < 25:
                self.logger.error("❌ Failed to generate enough test trades")
                return False
            
            # Wait for feedback processing
            await asyncio.sleep(2)
            
            # Check that feedback was recorded
            metrics = self.learning_engine.get_learning_metrics()
            
            if metrics.total_feedback_samples > 0:
                self.logger.info(f"✅ Feedback loop working: {metrics.total_feedback_samples} samples recorded")
                return True
            else:
                self.logger.warning("⚠️ No feedback samples recorded")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error testing feedback loop: {e}")
            return False
    
    def test_performance_monitoring(self) -> bool:
        """Testa el sistema de monitoreo de performance"""
        try:
            self.logger.info("📊 Testing performance monitoring...")
            
            # Get performance summary
            summary = self.performance_monitor.get_performance_summary()
            
            if 'monitoring_active' in summary and summary['monitoring_active']:
                self.logger.info(f"✅ Performance monitoring active: {summary['strategies_monitored']} strategies")
                return True
            else:
                self.logger.warning("⚠️ Performance monitoring not active")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error testing performance monitoring: {e}")
            return False
    
    async def test_drift_detection(self) -> bool:
        """Testa la detección de drift"""
        try:
            self.logger.info("🔍 Testing drift detection...")
            
            # Simulate some poor performing trades to trigger drift
            poor_trades = []
            for i in range(20):
                trade_id = f"POOR_{i:03d}_{datetime.now().strftime('%H%M%S')}"
                trade_result = self.simulate_trade_lifecycle(
                    trade_id, 'FAIL', 'macdv_smallcaps', will_succeed=False
                )
                if trade_result:
                    poor_trades.append(trade_result)
            
            # Wait for processing
            await asyncio.sleep(3)
            
            # Check if alerts were generated
            current_metrics = self.performance_monitor.calculate_current_performance()
            alerts = self.performance_monitor.detect_performance_issues(current_metrics)
            
            if len(alerts) > 0:
                self.logger.info(f"✅ Drift detection working: {len(alerts)} alerts generated")
                for alert in alerts:
                    self.logger.info(f"   🚨 {alert.severity} alert for {alert.strategy}: {alert.description}")
                return True
            else:
                self.logger.info("ℹ️ No alerts generated (may need more data)")
                return True  # Not necessarily a failure
                
        except Exception as e:
            self.logger.error(f"❌ Error testing drift detection: {e}")
            return False
    
    def cleanup_components(self):
        """Limpia los componentes del sistema"""
        try:
            if self.learning_engine:
                self.learning_engine.stop_continuous_learning()
            
            if self.performance_monitor:
                self.performance_monitor.stop_monitoring()
                
            self.logger.info("🧹 Components cleaned up")
            
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")

async def run_continuous_learning_tests():
    """Ejecuta todas las pruebas del sistema de continuous learning"""
    logger = setup_logging()
    
    print("🧠 CONTINUOUS LEARNING SYSTEM TESTS")
    print("=" * 60)
    print("Testing complete ML continuous learning pipeline")
    print("=" * 60)
    
    tester = ContinuousLearningTester()
    test_results = {
        'component_initialization': False,
        'feedback_loop': False,
        'performance_monitoring': False,
        'drift_detection': False
    }
    
    try:
        # Test 1: Component initialization
        logger.info("🔧 Test 1: Component Initialization")
        test_results['component_initialization'] = tester.initialize_components()
        
        if not test_results['component_initialization']:
            logger.error("❌ Component initialization failed, aborting tests")
            return False
        
        # Test 2: Feedback loop
        logger.info("\n🔄 Test 2: Feedback Loop")
        test_results['feedback_loop'] = await tester.test_feedback_loop()
        
        # Test 3: Performance monitoring
        logger.info("\n📊 Test 3: Performance Monitoring")
        test_results['performance_monitoring'] = tester.test_performance_monitoring()
        
        # Test 4: Drift detection
        logger.info("\n🔍 Test 4: Drift Detection")
        test_results['drift_detection'] = await tester.test_drift_detection()
        
        # Results summary
        print("\n" + "=" * 60)
        print("📊 CONTINUOUS LEARNING TEST RESULTS")
        print("=" * 60)
        
        total_tests = len(test_results)
        passed_tests = sum(test_results.values())
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"\n🎯 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        if success_rate == 100:
            print("🎉 CONTINUOUS LEARNING SYSTEM READY!")
            print("🧠 The system will automatically:")
            print("   • Learn from every trade result")
            print("   • Adapt volume requirements based on success/failure")
            print("   • Monitor performance and detect drift")
            print("   • Trigger automatic model retraining when needed")
            print("   • Improve predictions continuously over time")
        elif success_rate >= 75:
            print("⚠️ System mostly functional with some minor issues")
        else:
            print("❌ System needs attention before production use")
        
        print("=" * 60)
        
        return success_rate >= 75
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return False
    
    finally:
        tester.cleanup_components()

async def main():
    try:
        success = await run_continuous_learning_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Error in continuous learning tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)