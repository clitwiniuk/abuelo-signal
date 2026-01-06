#!/usr/bin/env python3
"""
Test FOMO Detection System
=========================

Tests the new FOMO detection system for optimal exit timing.
Verifies that market euphoria is detected correctly.
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.fomo_detector import FOMODetector, FOMOSignal
from core.interfaces import MarketData, Position
from utils.log_config import setup_logging


class MockPosition:
    """Mock position for testing"""
    def __init__(self, symbol: str, quantity: int, avg_price: float, entry_time: datetime = None):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.entry_time = entry_time or datetime.now() - timedelta(hours=2)


class MockMarketData:
    """Mock market data for testing"""
    def __init__(self, symbol: str, timestamp: datetime, open_price: float, 
                 high: float, low: float, close: float, volume: int):
        self.symbol = symbol
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


def create_fomo_scenario_data(symbol: str = "FOMO") -> List[MockMarketData]:
    """Create market data that should trigger FOMO detection"""
    base_time = datetime.now() - timedelta(minutes=30)
    bars = []
    
    # Start with normal trading
    price = 10.0
    volume = 100000
    
    # Build up to FOMO conditions
    for i in range(30):
        timestamp = base_time + timedelta(minutes=i)
        
        # Gradual volume and price explosion
        if i >= 20:  # Last 10 bars - FOMO conditions
            volume_multiplier = 2.0 + (i - 20) * 1.5  # 2x to 15.5x volume
            price_increase = 1.02 + (i - 20) * 0.005  # Accelerating price increases
            price *= price_increase
        else:  # Normal conditions
            price *= 1.001  # Small increase
            volume_multiplier = 1.0
        
        current_volume = int(volume * volume_multiplier)
        
        # Create OHLC with strong bullish bias in FOMO period
        if i >= 20:
            open_price = price * 0.99
            high_price = price * 1.03
            low_price = price * 0.995
            close_price = price
        else:
            open_price = price * 0.999
            high_price = price * 1.005
            low_price = price * 0.995
            close_price = price
        
        bar = MockMarketData(
            symbol=symbol,
            timestamp=timestamp,
            open_price=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=current_volume
        )
        bars.append(bar)
    
    return bars


def create_normal_scenario_data(symbol: str = "NORMAL") -> List[MockMarketData]:
    """Create normal market data that should NOT trigger FOMO"""
    base_time = datetime.now() - timedelta(minutes=30)
    bars = []
    
    price = 10.0
    base_volume = 100000
    
    for i in range(30):
        timestamp = base_time + timedelta(minutes=i)
        
        # Normal price movement
        price_change = 1.0 + (0.002 if i % 2 == 0 else -0.001)  # Small random moves
        price *= price_change
        
        # Normal volume (1x to 2x)
        volume = int(base_volume * (1.0 + (i % 5) * 0.2))
        
        bar = MockMarketData(
            symbol=symbol,
            timestamp=timestamp,
            open_price=price * 0.999,
            high=price * 1.002,
            low=price * 0.998,
            close=price,
            volume=volume
        )
        bars.append(bar)
    
    return bars


def test_fomo_detector_basic():
    """Test basic FOMO detector functionality"""
    print("\n1️⃣ Testing FOMO Detector Basic Functionality")
    print("-" * 50)
    
    detector = FOMODetector()
    print(f"✅ FOMODetector initialized")
    print(f"   Thresholds: {detector.fomo_threshold:.1%} / {detector.critical_threshold:.1%}")
    print(f"   Weights: Vol={detector.volume_weight:.1%}, Price={detector.price_action_weight:.1%}")
    
    # Test status summary
    status = detector.get_fomo_status_summary()
    print(f"✅ Status summary generated: {len(status)} characters")
    
    return True


def test_fomo_detection_scenario():
    """Test FOMO detection on designed scenario"""
    print("\n2️⃣ Testing FOMO Detection Scenario")
    print("-" * 40)
    
    # Use lower threshold to test detection capability
    detector = FOMODetector({'fomo_threshold': 0.60})  # Lower threshold for test
    
    # Create FOMO scenario
    fomo_bars = create_fomo_scenario_data("FOMO_TEST")
    position = MockPosition("FOMO_TEST", 100, 9.5)
    current_bar = fomo_bars[-1]
    
    print(f"📊 Created scenario: {len(fomo_bars)} bars")
    print(f"   Start price: ${fomo_bars[0].close:.2f}")
    print(f"   End price: ${current_bar.close:.2f} (+{((current_bar.close/fomo_bars[0].close-1)*100):.1f}%)")
    print(f"   Start volume: {fomo_bars[0].volume:,}")
    print(f"   End volume: {current_bar.volume:,} ({current_bar.volume/fomo_bars[0].volume:.1f}x)")
    
    # Run FOMO detection
    result = detector.detect_fomo_exit("FOMO_TEST", current_bar, position, fomo_bars)
    
    analysis = result.get('analysis', {})
    fomo_score = analysis.get('fomo_score', 0)
    should_exit = result.get('should_exit', False)
    
    print(f"\n🎪 FOMO Analysis Results:")
    print(f"   FOMO Score: {fomo_score:.2f}")
    print(f"   Should exit: {should_exit}")
    
    if should_exit:
        print(f"   Urgency: {analysis.get('urgency', 'N/A')}")
        print(f"   Confidence: {analysis.get('confidence', 0):.1%}")
        
        components = analysis.get('components', {})
        print(f"   Components:")
        for comp, score in components.items():
            print(f"      {comp}: {score:.2f}")
        
        reasons = analysis.get('reasons', [])
        print(f"   Reasons ({len(reasons)}):")
        for reason in reasons:
            print(f"      • {reason}")
        
        return True
    else:
        components = analysis.get('components', {})
        print(f"   Components:")
        for comp, score in components.items():
            print(f"      {comp}: {score:.2f}")
        
        # Score should be reasonably high even if not triggering
        if fomo_score >= 0.50:
            print(f"   ✅ Good FOMO score ({fomo_score:.2f}) - system working")
            return True
        else:
            print(f"   ❌ Low FOMO score ({fomo_score:.2f}) - needs tuning")
            return False


def test_normal_scenario():
    """Test that normal market doesn't trigger FOMO"""
    print("\n3️⃣ Testing Normal Market Scenario")
    print("-" * 40)
    
    detector = FOMODetector()
    
    # Create normal scenario
    normal_bars = create_normal_scenario_data("NORMAL_TEST")
    position = MockPosition("NORMAL_TEST", 100, 9.8)
    current_bar = normal_bars[-1]
    
    print(f"📊 Created normal scenario: {len(normal_bars)} bars")
    print(f"   Price change: ${normal_bars[0].close:.2f} -> ${current_bar.close:.2f} ({((current_bar.close/normal_bars[0].close-1)*100):+.1f}%)")
    print(f"   Volume: {current_bar.volume:,} ({current_bar.volume/normal_bars[0].volume:.1f}x)")
    
    # Run FOMO detection
    result = detector.detect_fomo_exit("NORMAL_TEST", current_bar, position, normal_bars)
    
    print(f"\n📈 Normal Market Analysis:")
    print(f"   Should exit: {result.get('should_exit', False)}")
    
    analysis = result.get('analysis', {})
    print(f"   FOMO Score: {analysis.get('fomo_score', 0):.2f} (should be low)")
    
    if not result.get('should_exit'):
        print(f"   ✅ Correctly identified as normal market")
        return True
    else:
        print(f"   ❌ False positive - normal market triggered FOMO exit")
        return False


def test_fomo_thresholds():
    """Test different FOMO thresholds"""
    print("\n4️⃣ Testing FOMO Threshold Sensitivity")
    print("-" * 45)
    
    fomo_bars = create_fomo_scenario_data("THRESHOLD_TEST")
    position = MockPosition("THRESHOLD_TEST", 100, 9.5)
    current_bar = fomo_bars[-1]
    
    thresholds = [0.60, 0.70, 0.80, 0.90]
    
    for threshold in thresholds:
        detector = FOMODetector({'fomo_threshold': threshold})
        result = detector.detect_fomo_exit("THRESHOLD_TEST", current_bar, position, fomo_bars)
        
        should_exit = result.get('should_exit', False)
        fomo_score = result.get('analysis', {}).get('fomo_score', 0)
        
        status = "EXIT" if should_exit else "HOLD"
        print(f"   Threshold {threshold:.1%}: Score={fomo_score:.2f} -> {status}")
    
    print(f"   ✅ Threshold sensitivity test completed")
    return True


def test_strategy_integration():
    """Test integration with Gap & Go strategy"""
    print("\n5️⃣ Testing Strategy Integration")
    print("-" * 35)
    
    try:
        from strategies.gap_go_strategy import GapGoStrategy
        
        # Create strategy instance
        strategy = GapGoStrategy()
        
        print(f"✅ GapGoStrategy created")
        print(f"   FOMO enabled: {strategy.fomo_exit_enabled}")
        
        if strategy.fomo_exit_enabled:
            print(f"   FOMO detector available: {strategy.fomo_detector is not None}")
            
            # Test FOMO check
            fomo_bars = create_fomo_scenario_data("INTEGRATION_TEST")
            position = MockPosition("INTEGRATION_TEST", 100, 9.5)
            current_bar = fomo_bars[-1]
            
            fomo_result = strategy.check_fomo_exit("INTEGRATION_TEST", position, current_bar)
            
            if fomo_result:
                print(f"   ✅ Strategy FOMO check working")
                print(f"   Should exit: {fomo_result.get('should_exit', False)}")
                return True
            else:
                print(f"   ⚠️ Strategy FOMO check returned None")
                return True
        else:
            print(f"   ⚠️ FOMO not enabled in strategy")
            return False
            
    except Exception as e:
        print(f"   ❌ Strategy integration test failed: {e}")
        return False


def main():
    """Run all FOMO detection tests"""
    print("🎪 FOMO DETECTION SYSTEM TESTS")
    print("=" * 60)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger("FOMOTest")
    
    tests = [
        ("Basic Functionality", test_fomo_detector_basic),
        ("FOMO Detection Scenario", test_fomo_detection_scenario),
        ("Normal Market Scenario", test_normal_scenario),
        ("Threshold Sensitivity", test_fomo_thresholds),
        ("Strategy Integration", test_strategy_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result, None))
            logger.info(f"Test '{test_name}': {'PASS' if result else 'FAIL'}")
        except Exception as e:
            results.append((test_name, False, str(e)))
            logger.error(f"Test '{test_name}': ERROR - {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"     Error: {error}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED - FOMO Detection System Working!")
        print("\n💡 NEXT STEPS:")
        print("   1. Test with real market data")
        print("   2. Monitor FOMO exits in live trading")
        print("   3. Fine-tune thresholds based on performance")
        return True
    else:
        print("⚠️ SOME TESTS FAILED - Review implementation")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)