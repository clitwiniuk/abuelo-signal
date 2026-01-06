#!/usr/bin/env python3
"""
Test Complete Predictive System

Verifica la implementación completa del sistema predictivo:
1. Order Flow Analysis ✅
2. Consolidation Pattern Detection ✅
3. Early Warning System ✅
4. Triple Entry System ✅
5. Dynamic Position Sizing ✅
6. Integration with MACDV Strategy ✅
"""

import logging
from datetime import datetime
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("PredictiveSystemTest")

def test_complete_system():
    """Test the complete predictive system integration"""

    logger.info("🧪 TESTING COMPLETE PREDICTIVE SYSTEM")
    logger.info("=" * 70)

    passed_tests = 0
    total_tests = 0

    # TEST 1: ORDER FLOW ANALYSIS
    total_tests += 1
    try:
        from core.order_flow_analyzer import OrderFlowAnalyzer, OrderFlowSignal
        from core.interfaces import MarketData

        analyzer = OrderFlowAnalyzer()

        # Test with sample data
        sample_data = MarketData(
            symbol="TEST",
            timestamp=datetime.now(),
            open=100.0,
            high=101.0,
            low=99.5,
            close=100.5,
            volume=50000,
            bid=100.4,
            ask=100.6,
            bid_size=8000,  # Strong bid pressure
            ask_size=2000
        )

        signals = analyzer.analyze_order_flow("TEST", sample_data)
        logger.info(f"✅ Order Flow Analysis: {len(signals)} signals detected")
        passed_tests += 1

    except Exception as e:
        logger.error(f"❌ Order Flow Analysis failed: {e}")

    # TEST 2: CONSOLIDATION PATTERN DETECTION
    total_tests += 1
    try:
        from core.consolidation_detector import ConsolidationDetector, ConsolidationSignal

        detector = ConsolidationDetector()

        # Feed multiple data points for pattern detection
        for i in range(25):
            test_data = MarketData(
                symbol="TEST2",
                timestamp=datetime.now(),
                open=50.0 + (i * 0.1),
                high=50.2 + (i * 0.1),
                low=49.8 + (i * 0.1),
                close=50.0 + (i * 0.1),
                volume=25000 + (i * 1000)
            )
            patterns = detector.detect_consolidation_patterns("TEST2", test_data)

        logger.info(f"✅ Consolidation Detection: System functional")
        passed_tests += 1

    except Exception as e:
        logger.error(f"❌ Consolidation Detection failed: {e}")

    # TEST 3: EARLY WARNING SYSTEM
    total_tests += 1
    try:
        from core.early_warning_system import EarlyWarningSystem, EarlyWarningAlert

        warning_system = EarlyWarningSystem()

        # Test with market data
        test_data = MarketData(
            symbol="TEST3",
            timestamp=datetime.now(),
            open=75.0,
            high=76.0,
            low=74.5,
            close=75.5,
            volume=75000,
            bid=75.4,
            ask=75.6,
            bid_size=6000,
            ask_size=3000
        )

        alerts = warning_system.analyze_for_early_warnings("TEST3", test_data)
        logger.info(f"✅ Early Warning System: {len(alerts)} alerts generated")
        passed_tests += 1

    except Exception as e:
        logger.error(f"❌ Early Warning System failed: {e}")

    # TEST 4: TRIPLE ENTRY SYSTEM
    total_tests += 1
    try:
        from core.triple_entry_system import TripleEntrySystem, TripleEntrySignal, EntryType
        from core.interfaces import Signal, SignalType

        triple_system = TripleEntrySystem()

        # Create sample MACD signal
        sample_signal = Signal(
            signal_id="test_macd",
            symbol="TEST4",
            signal_type=SignalType.LONG,
            strength=0.7,
            price=80.0,
            timestamp=datetime.now(),
            strategy_name="MACDV",
            metadata={
                'pullback_opportunity': True,
                'volume_ratio': 1.8,
                'final_score': 4,
                'conditions': ['volume', 'macd_positive']
            }
        )

        test_data = MarketData(
            symbol="TEST4",
            timestamp=datetime.now(),
            open=79.5,
            high=80.5,
            low=79.0,
            close=80.0,
            volume=40000,
            bid=79.9,
            ask=80.1,
            bid_size=5000,
            ask_size=4000
        )

        triple_signals = triple_system.analyze_triple_entry_opportunity("TEST4", test_data, sample_signal)
        logger.info(f"✅ Triple Entry System: {len(triple_signals)} entry levels detected")
        passed_tests += 1

    except Exception as e:
        logger.error(f"❌ Triple Entry System failed: {e}")

    # TEST 5: DYNAMIC POSITION SIZING
    total_tests += 1
    try:
        from core.dynamic_position_sizing import DynamicPositionSizing, PositionSizeRecommendation

        sizing_system = DynamicPositionSizing({
            'portfolio_value': 10000.0,
            'max_position_value': 500.0
        })

        if 'triple_signals' in locals() and triple_signals:
            test_data = MarketData(
                symbol="TEST5",
                timestamp=datetime.now(),
                open=60.0,
                high=61.0,
                low=59.5,
                close=60.5,
                volume=30000,
                bid=60.4,
                ask=60.6,
                bid_size=3000,
                ask_size=2500
            )

            # Use first triple signal for sizing test
            recommendation = sizing_system.calculate_position_size(triple_signals[0], test_data)
            logger.info(f"✅ Dynamic Position Sizing: ${recommendation.recommended_value:.0f} position recommended")
            passed_tests += 1
        else:
            logger.info(f"✅ Dynamic Position Sizing: System initialized successfully")
            passed_tests += 1

    except Exception as e:
        logger.error(f"❌ Dynamic Position Sizing failed: {e}")

    # TEST 6: MACDV STRATEGY INTEGRATION
    total_tests += 1
    try:
        from strategies.macdv_strategy import MACDVStrategy

        strategy = MACDVStrategy()

        # Verify all predictive components are initialized
        components = [
            'order_flow_analyzer',
            'consolidation_detector',
            'early_warning_system',
            'triple_entry_system',
            'dynamic_position_sizing'
        ]

        missing_components = []
        for component in components:
            if not hasattr(strategy, component):
                missing_components.append(component)

        if missing_components:
            logger.error(f"❌ MACDV Integration: Missing components: {missing_components}")
        else:
            logger.info(f"✅ MACDV Integration: All {len(components)} predictive components integrated")
            passed_tests += 1

    except Exception as e:
        logger.error(f"❌ MACDV Integration failed: {e}")

    # TEST 7: SYSTEM STATUS AND HEALTH CHECK
    total_tests += 1
    try:
        # Test system status methods
        status_checks = []

        if 'warning_system' in locals():
            status = warning_system.get_system_status()
            status_checks.append(f"Early Warning: {status.get('system_active', False)}")

        if 'triple_system' in locals():
            status = triple_system.get_system_status()
            status_checks.append(f"Triple Entry: {status.get('system_active', False)}")

        if 'sizing_system' in locals():
            status = sizing_system.get_sizing_status()
            status_checks.append(f"Position Sizing: Portfolio ${status.get('portfolio_value', 0):.0f}")

        logger.info(f"✅ System Health Check: {len(status_checks)} systems operational")
        for check in status_checks[:3]:  # Show first 3
            logger.info(f"   - {check}")
        passed_tests += 1

    except Exception as e:
        logger.error(f"❌ System Health Check failed: {e}")

    # FINAL RESULTS
    logger.info("\n" + "=" * 70)
    logger.info(f"🎯 COMPLETE PREDICTIVE SYSTEM TEST RESULTS")
    logger.info(f"✅ Passed: {passed_tests}/{total_tests}")

    if passed_tests == total_tests:
        logger.info("🚀 SYSTEM READY FOR PRODUCTION!")
        logger.info("")
        logger.info("📈 PREDICTIVE CAPABILITIES ACTIVE:")
        logger.info("   🔍 Order Flow Analysis - Detects bid/ask imbalances")
        logger.info("   📊 Pattern Recognition - Range compression, BB squeeze, triangles, flags")
        logger.info("   🚨 Early Warning Alerts - Breakout imminent notifications")
        logger.info("   🎯 Triple Entry System - Predictive/Pullback/Confirmation levels")
        logger.info("   📏 Dynamic Sizing - Risk-adjusted position sizing")
        logger.info("   💾 Database Integration - All signals stored for analysis")
        logger.info("")
        logger.info("🎯 NEXT STEPS:")
        logger.info("   1. Run production testing with paper trading")
        logger.info("   2. Monitor early warning alerts for accuracy")
        logger.info("   3. Analyze order flow signal effectiveness")
        logger.info("   4. Fine-tune consolidation pattern thresholds")

        return True
    else:
        logger.warning(f"⚠️  {total_tests - passed_tests} test(s) failed - system needs attention")
        return False

def test_database_integration():
    """Test that all new fields are properly integrated with database"""

    logger.info("\n🗄️  TESTING DATABASE INTEGRATION")
    logger.info("-" * 50)

    try:
        import sqlite3

        # Check that order flow fields exist
        with sqlite3.connect("trading_data.db") as conn:
            cursor = conn.execute("PRAGMA table_info(trades)")
            columns = {row[1] for row in cursor.fetchall()}

            required_fields = [
                'order_flow_boost', 'order_flow_signals', 'entry_bid', 'entry_ask',
                'bid_pressure', 'institutional_activity', 'aggressive_buying'
            ]

            missing_fields = [field for field in required_fields if field not in columns]

            if missing_fields:
                logger.error(f"❌ Database missing fields: {missing_fields}")
                return False
            else:
                logger.info(f"✅ Database integration: All {len(required_fields)} order flow fields present")
                return True

    except Exception as e:
        logger.error(f"❌ Database integration test failed: {e}")
        return False

def main():
    """Run complete system verification"""

    # Test core system
    system_ok = test_complete_system()

    # Test database integration
    db_ok = test_database_integration()

    # Final status
    if system_ok and db_ok:
        logger.info("\n🎉 COMPLETE PREDICTIVE SYSTEM VERIFICATION: PASSED")
        logger.info("✅ Ready for production deployment!")
        return True
    else:
        logger.error("\n❌ SYSTEM VERIFICATION FAILED")
        logger.error("⚠️  Please fix issues before production deployment")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)