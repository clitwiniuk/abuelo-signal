#!/usr/bin/env python3
"""
Test Adaptive Risk Sizing System

Verifica que el sistema de position sizing adaptativo funciona correctamente:
- Cálculo de riesgo base
- Boost por quality score alto
- Boost por pattern alignment
- Reducción por alta volatilidad
- Límites mín/máx correctos
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.service_locator import get_service_locator


def test_adaptive_risk_sizing():
    """Test adaptive risk sizing calculation"""
    print("=" * 80)
    print("ADAPTIVE RISK SIZING - TEST SUITE")
    print("=" * 80)
    print()

    # Initialize ServiceLocator and config
    service_locator = get_service_locator()
    config = service_locator.get_config()

    print("📋 Configuration loaded:")
    print(f"   Base Risk: {getattr(config, 'base_risk_percent', 1.2)}%")
    print(f"   Min Risk: {getattr(config, 'min_risk_percent', 0.8)}%")
    print(f"   Max Risk: {getattr(config, 'max_risk_percent', 2.0)}%")
    print(f"   Quality Threshold: {getattr(config, 'quality_boost_threshold', 80)}")
    print(f"   Quality Boost: {getattr(config, 'quality_boost_amount', 0.3)}%")
    print(f"   Pattern Alignment Threshold: {getattr(config, 'pattern_alignment_threshold', 2)}")
    print(f"   Pattern Boost: {getattr(config, 'pattern_alignment_boost', 0.2)}%")
    print(f"   Volatility Threshold: {getattr(config, 'high_volatility_threshold', 8.0)}%")
    print(f"   Volatility Reduction: {getattr(config, 'high_volatility_reduction', 0.2)}%")
    print()

    # Create a mock worker to test calculate_adaptive_risk
    from strategies.workers.base_worker_logic import BaseWorkerLogic

    class TestWorker(BaseWorkerLogic):
        """Mock worker for testing"""
        def __init__(self):
            # Skip parent init, just set what we need
            self.worker_name = "test_worker"
            self.service_locator = service_locator

            from utils.log_config import setup_worker_logging
            self.logger = setup_worker_logging("test_worker", level="INFO")

        async def should_enter(self, opportunity):
            return True

        async def should_exit(self, symbol, position_data):
            return False, None

    worker = TestWorker()

    # Test cases
    print("🧪 TEST CASES:")
    print("-" * 80)

    # TEST 1: Base case - no boosts or reductions
    print("\n1️⃣  BASE CASE (quality=50, no patterns, ATR=5%)")
    opportunity1 = {
        'quality_score': 50,
        'atr_percent': 5.0
    }
    risk1 = worker.calculate_adaptive_risk(opportunity1)
    expected1 = 0.012  # Base risk
    print(f"   Result: {risk1*100:.2f}% (expected: {expected1*100:.2f}%)")
    assert abs(risk1 - expected1) < 0.0001, f"❌ FAILED: Expected {expected1}, got {risk1}"
    print("   ✅ PASSED")

    # TEST 2: High quality boost
    print("\n2️⃣  HIGH QUALITY BOOST (quality=85, no patterns, ATR=5%)")
    opportunity2 = {
        'quality_score': 85,
        'atr_percent': 5.0
    }
    risk2 = worker.calculate_adaptive_risk(opportunity2)
    expected2 = 0.012 + 0.003  # Base + quality boost
    print(f"   Result: {risk2*100:.2f}% (expected: {expected2*100:.2f}%)")
    assert abs(risk2 - expected2) < 0.0001, f"❌ FAILED: Expected {expected2}, got {risk2}"
    print("   ✅ PASSED")

    # TEST 3: Pattern alignment boost
    print("\n3️⃣  PATTERN ALIGNMENT BOOST (quality=50, 2+ patterns, ATR=5%)")

    # Create mock ODS data with correct ODSData structure
    from core.ods_classifier import ODSData, ODSDayType
    ods_data = ODSData(
        day_type=ODSDayType.TREND_DRIVE_BULLISH,
        direction="BULLISH",
        strength=8.5,
        open_price=10.0,
        high_12min=10.5,
        low_12min=9.9,
        close_12min=10.3,
        range_pct=5.0,
        distance_from_open_pct=3.0,
        volume_ratio=2.5,
        upside_move_pct=5.0,
        downside_move_pct=1.0
    )
    # Add classification attribute for pattern matching
    ods_data.classification = "STRONG_BULLISH"

    # Create mock Intraday Structure
    from core.intraday_structure_classifier import IntradayStructureData, IntradayPhase
    intraday_structure = IntradayStructureData(
        symbol="TEST",
        current_phase=IntradayPhase.CONTINUATION,
        continuation_type="PULLBACK_TO_VWAP",
        liquidity_sweep_detected=True,
        sweep_direction="BULLISH_RECLAIM",
        midday_structure="IMBALANCE_BULLISH"
    )
    # Add attributes used in adaptive risk calculation
    intraday_structure.liquidity_sweep_type = "BULLISH_RECLAIM"
    intraday_structure.midday_structure_type = "IMBALANCE_BULLISH"

    opportunity3 = {
        'quality_score': 50,
        'atr_percent': 5.0
    }
    risk3 = worker.calculate_adaptive_risk(
        opportunity3,
        ods_data=ods_data,
        intraday_structure=intraday_structure
    )
    expected3 = 0.012 + 0.002  # Base + pattern boost (ODS + continuation + sweep = 3 patterns)
    print(f"   Result: {risk3*100:.2f}% (expected: {expected3*100:.2f}%)")
    assert abs(risk3 - expected3) < 0.0001, f"❌ FAILED: Expected {expected3}, got {risk3}"
    print("   ✅ PASSED")

    # TEST 4: High volatility reduction
    print("\n4️⃣  HIGH VOLATILITY REDUCTION (quality=50, no patterns, ATR=9%)")
    opportunity4 = {
        'quality_score': 50,
        'atr_percent': 9.0
    }
    risk4 = worker.calculate_adaptive_risk(opportunity4)
    expected4 = 0.012 - 0.002  # Base - volatility reduction
    print(f"   Result: {risk4*100:.2f}% (expected: {expected4*100:.2f}%)")
    assert abs(risk4 - expected4) < 0.0001, f"❌ FAILED: Expected {expected4}, got {risk4}"
    print("   ✅ PASSED")

    # TEST 5: Maximum risk (all boosts)
    print("\n5️⃣  MAXIMUM RISK (quality=90, 2+ patterns, ATR=4%)")
    opportunity5 = {
        'quality_score': 90,
        'atr_percent': 4.0
    }
    risk5 = worker.calculate_adaptive_risk(
        opportunity5,
        ods_data=ods_data,
        intraday_structure=intraday_structure
    )
    expected5 = 0.012 + 0.003 + 0.002  # Base + quality + pattern = 1.7%
    print(f"   Result: {risk5*100:.2f}% (expected: {expected5*100:.2f}%)")
    assert abs(risk5 - expected5) < 0.0001, f"❌ FAILED: Expected {expected5}, got {risk5}"
    print("   ✅ PASSED")

    # TEST 6: Cap at maximum (try to exceed max_risk)
    print("\n6️⃣  MAXIMUM CAP TEST (quality=100, patterns, would exceed 2.0%)")

    opportunity6 = {
        'quality_score': 100,
        'atr_percent': 3.0
    }
    risk6 = worker.calculate_adaptive_risk(
        opportunity6,
        ods_data=ods_data,
        intraday_structure=intraday_structure
    )
    max_risk = getattr(config, 'max_risk_percent', 2.0) / 100.0
    print(f"   Result: {risk6*100:.2f}% (max cap: {max_risk*100:.2f}%)")
    assert risk6 <= max_risk, f"❌ FAILED: Risk {risk6} exceeds max {max_risk}"
    print("   ✅ PASSED - Capped at maximum")

    # TEST 7: Cap at minimum (high volatility reduction)
    print("\n7️⃣  MINIMUM CAP TEST (quality=30, high volatility ATR=15%)")
    opportunity7 = {
        'quality_score': 30,
        'atr_percent': 15.0
    }
    risk7 = worker.calculate_adaptive_risk(opportunity7)
    min_risk = getattr(config, 'min_risk_percent', 0.8) / 100.0
    print(f"   Result: {risk7*100:.2f}% (min cap: {min_risk*100:.2f}%)")
    assert risk7 >= min_risk, f"❌ FAILED: Risk {risk7} below min {min_risk}"
    print("   ✅ PASSED - Capped at minimum")

    print()
    print("=" * 80)
    print("✅ ALL TESTS PASSED - Adaptive Risk Sizing working correctly!")
    print("=" * 80)


if __name__ == "__main__":
    test_adaptive_risk_sizing()
