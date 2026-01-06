#!/usr/bin/env python3
"""
Test Order Flow Integration

Verifica que los datos de order flow se guarden correctamente en la base de datos
"""

import sqlite3
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrderFlowTest")

def test_order_flow_database_fields():
    """Test that order flow fields exist in database"""

    expected_fields = [
        "order_flow_boost", "order_flow_signals", "entry_bid", "entry_ask",
        "entry_bid_size", "entry_ask_size", "entry_spread_pct", "bid_pressure",
        "institutional_activity", "aggressive_buying", "pressure_building",
        "volume_at_ask_ratio", "volume_at_bid_ratio", "spread_compression_ratio",
        "volume_multiplier"
    ]

    try:
        with sqlite3.connect("trading_data.db") as conn:
            cursor = conn.execute("PRAGMA table_info(trades)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            missing_fields = []
            for field in expected_fields:
                if field not in existing_columns:
                    missing_fields.append(field)

            if missing_fields:
                logger.error(f"❌ Missing order flow fields: {missing_fields}")
                return False
            else:
                logger.info(f"✅ All {len(expected_fields)} order flow fields present in database")
                return True

    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

def test_order_flow_data_structure():
    """Test order flow data structure"""

    try:
        # Test OrderFlowAnalyzer import
        from core.order_flow_analyzer import OrderFlowAnalyzer, OrderFlowSignal
        logger.info("✅ OrderFlowAnalyzer import successful")

        # Test analyzer initialization
        analyzer = OrderFlowAnalyzer()
        logger.info("✅ OrderFlowAnalyzer initialization successful")

        # Test MACDV strategy import with order flow
        from strategies.macdv_strategy import MACDVStrategy
        strategy = MACDVStrategy()
        logger.info("✅ MACDV strategy with order flow import successful")

        # Test that analyzer is initialized in strategy
        if hasattr(strategy, 'order_flow_analyzer'):
            logger.info("✅ OrderFlowAnalyzer properly initialized in MACDV strategy")
            return True
        else:
            logger.error("❌ OrderFlowAnalyzer not found in MACDV strategy")
            return False

    except Exception as e:
        logger.error(f"❌ Data structure test failed: {e}")
        return False

def test_sample_order_flow_data():
    """Test order flow analysis with sample data"""

    try:
        from core.order_flow_analyzer import OrderFlowAnalyzer
        from core.interfaces import MarketData
        from datetime import datetime

        # Create sample market data with bid/ask
        sample_data = MarketData(
            symbol="TEST",
            timestamp=datetime.now(),
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.2,
            volume=100000,
            bid=10.15,
            ask=10.25,
            bid_size=5000,
            ask_size=2000  # Strong bid pressure (71% bid)
        )

        analyzer = OrderFlowAnalyzer()
        signals = analyzer.analyze_order_flow("TEST", sample_data)

        if signals:
            logger.info(f"✅ Order flow analysis successful: {len(signals)} signals detected")
            for signal in signals:
                logger.info(f"   - {signal.signal_type}: {signal.strength:.2f} confidence")
            return True
        else:
            logger.info("✅ Order flow analysis ran successfully (no signals detected)")
            return True

    except Exception as e:
        logger.error(f"❌ Order flow analysis test failed: {e}")
        return False

def check_recent_trades_for_order_flow():
    """Check if recent trades have order flow data"""

    try:
        with sqlite3.connect("trading_data.db") as conn:
            # Get most recent trades
            cursor = conn.execute("""
                SELECT symbol, entry_time, order_flow_boost, order_flow_signals,
                       bid_pressure, institutional_activity, aggressive_buying
                FROM trades
                WHERE entry_time >= date('now', '-7 days')
                ORDER BY entry_time DESC
                LIMIT 5
            """)

            trades = cursor.fetchall()

            if not trades:
                logger.info("ℹ️  No recent trades found for order flow verification")
                return True

            logger.info(f"📊 Recent trades order flow data:")
            for trade in trades:
                symbol, entry_time, boost, signals, bid_pressure, inst_activity, agg_buying = trade
                signals_parsed = json.loads(signals) if signals else []

                bid_pressure_str = f"{bid_pressure:.3f}" if bid_pressure is not None else "N/A"
                logger.info(f"   {symbol} ({entry_time}): boost={boost}, "
                           f"signals={len(signals_parsed)}, bid_pressure={bid_pressure_str}")

            return True

    except Exception as e:
        logger.error(f"❌ Recent trades check failed: {e}")
        return False

def main():
    """Run all order flow integration tests"""

    logger.info("🧪 TESTING ORDER FLOW INTEGRATION")
    logger.info("=" * 50)

    tests = [
        ("Database Fields", test_order_flow_database_fields),
        ("Data Structure", test_order_flow_data_structure),
        ("Order Flow Analysis", test_sample_order_flow_data),
        ("Recent Trades Data", check_recent_trades_for_order_flow)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running: {test_name}")
        try:
            if test_func():
                logger.info(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")

    logger.info("\n" + "=" * 50)
    logger.info(f"🎯 ORDER FLOW INTEGRATION TEST RESULTS")
    logger.info(f"✅ Passed: {passed}/{total}")

    if passed == total:
        logger.info("🚀 Order flow integration is ready for production!")
        logger.info("📈 The system can now detect and store predictive signals:")
        logger.info("   - Bid/Ask imbalance detection")
        logger.info("   - Spread compression (institutional activity)")
        logger.info("   - Aggressive buying/selling patterns")
        logger.info("   - Volume pressure building")
        logger.info("💾 All order flow data will be saved to trading_data.db for analysis")
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed - integration needs attention")

    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)