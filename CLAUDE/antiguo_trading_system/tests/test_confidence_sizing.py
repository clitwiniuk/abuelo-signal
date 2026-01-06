#!/usr/bin/env python3
"""
Test script para confidence-based position sizing
Verifica que el sizing dinámico funciona correctamente con diferentes niveles de confidence
"""

import sys
import os
from datetime import datetime
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interfaces import Signal, SignalType
from core.trading_execution_stage import TradingExecutionStage

@dataclass
class MockConfig:
    """Mock config para testing"""
    max_position_value: float = 200.0
    min_quantity: int = 10

    # Confidence sizing config
    enable_confidence_sizing: bool = False
    confidence_sizing_min_multiplier: float = 0.5
    confidence_sizing_max_multiplier: float = 1.5
    confidence_sizing_threshold_low: float = 60.0
    confidence_sizing_threshold_high: float = 85.0

class MockSignal:
    """Mock signal para testing"""
    def __init__(self, symbol: str, price: float, confidence: float = None, strength: float = None):
        self.symbol = symbol
        self.price = price
        self.signal_type = SignalType.LONG
        self.confidence = confidence
        self.strength = strength
        self.strategy = 'TestStrategy'
        self.timestamp = datetime.now()

def test_confidence_sizing_disabled():
    """Test que verifica sizing normal cuando confidence sizing está deshabilitado"""
    print("🧪 Testing confidence sizing DISABLED...")

    config = MockConfig()
    config.enable_confidence_sizing = False

    execution_stage = TradingExecutionStage(
        broker=None,
        risk_manager=None,
        config=config,
        event_bus=None
    )

    # Test con diferentes niveles de confidence
    test_cases = [
        MockSignal("AAPL", 50.0, confidence=90.0),  # High confidence
        MockSignal("AAPL", 50.0, confidence=50.0),  # Low confidence
        MockSignal("AAPL", 50.0, confidence=75.0),  # Medium confidence
    ]

    expected_size = max(config.min_quantity, int(200.0 / 50.0))  # max(10, 4) = 10 shares

    for signal in test_cases:
        size = execution_stage._calculate_position_size(signal)
        assert size == expected_size, f"Expected {expected_size}, got {size} for confidence {signal.confidence}"
        print(f"✅ Confidence {signal.confidence}% → {size} shares (sizing disabled)")

    print("🎉 Confidence sizing disabled test PASSED!\n")

def test_confidence_sizing_enabled():
    """Test que verifica sizing dinámico cuando confidence sizing está habilitado"""
    print("🧪 Testing confidence sizing ENABLED...")

    config = MockConfig()
    config.enable_confidence_sizing = True

    execution_stage = TradingExecutionStage(
        broker=None,
        risk_manager=None,
        config=config,
        event_bus=None
    )

    base_price = 10.0  # Use lower price so we can see sizing effects better
    base_size = int(200.0 / base_price)  # 20 shares normal

    test_cases = [
        # Low confidence (≤60%) → 0.5x multiplier
        {"signal": MockSignal("TEST1", base_price, confidence=50.0), "expected_multiplier": 0.5},
        {"signal": MockSignal("TEST2", base_price, confidence=60.0), "expected_multiplier": 0.5},

        # High confidence (≥85%) → 1.5x multiplier
        {"signal": MockSignal("TEST3", base_price, confidence=85.0), "expected_multiplier": 1.5},
        {"signal": MockSignal("TEST4", base_price, confidence=95.0), "expected_multiplier": 1.5},

        # Medium confidence → interpolated multipliers
        {"signal": MockSignal("TEST5", base_price, confidence=70.0), "expected_multiplier": "interpolated"},
        {"signal": MockSignal("TEST6", base_price, confidence=80.0), "expected_multiplier": "interpolated"},
    ]

    for case in test_cases:
        signal = case["signal"]
        size = execution_stage._calculate_position_size(signal)

        if case["expected_multiplier"] == "interpolated":
            # Para casos interpolados, solo verificamos que está entre min y max
            min_expected = max(config.min_quantity, int(200.0 * 0.5 / base_price))
            max_expected = int(200.0 * 1.5 / base_price)
            assert min_expected <= size <= max_expected, f"Size {size} not in interpolated range [{min_expected}, {max_expected}] for confidence {signal.confidence}"
            print(f"✅ Confidence {signal.confidence}% → {size} shares (interpolated)")
        else:
            expected_size = max(config.min_quantity, int(200.0 * case["expected_multiplier"] / base_price))
            assert size == expected_size, f"Expected {expected_size}, got {size} for confidence {signal.confidence}"
            print(f"✅ Confidence {signal.confidence}% → {size} shares (multiplier: {case['expected_multiplier']}x)")

    print("🎉 Confidence sizing enabled test PASSED!\n")

def test_edge_cases():
    """Test casos límite y edge cases"""
    print("🧪 Testing edge cases...")

    config = MockConfig()
    config.enable_confidence_sizing = True
    config.min_quantity = 20  # Higher min quantity

    execution_stage = TradingExecutionStage(
        broker=None,
        risk_manager=None,
        config=config,
        event_bus=None
    )

    # Test con precio muy alto (debería respetar min_quantity)
    high_price_signal = MockSignal("EXPENSIVE", 1000.0, confidence=95.0)
    size = execution_stage._calculate_position_size(high_price_signal)
    assert size >= config.min_quantity, f"Size {size} below min_quantity {config.min_quantity}"
    print(f"✅ High price stock → {size} shares (respects min_quantity)")

    # Test con signal sin confidence (debería usar default)
    no_confidence_signal = MockSignal("NOCONF", 50.0)
    no_confidence_signal.confidence = None
    size = execution_stage._calculate_position_size(no_confidence_signal)
    assert size > 0, f"Got zero size for signal without confidence"
    print(f"✅ No confidence signal → {size} shares (uses default)")

    # Test con signal que tiene strength en lugar de confidence
    strength_signal = MockSignal("STRENGTH", 50.0, strength=0.85)
    strength_signal.confidence = None
    size = execution_stage._calculate_position_size(strength_signal)
    assert size > 0, f"Got zero size for signal with strength"
    print(f"✅ Strength-based signal → {size} shares (strength converted to confidence)")

    print("🎉 Edge cases test PASSED!\n")

def test_configuration_validation():
    """Test que verifica que la configuración es válida"""
    print("🧪 Testing configuration validation...")

    # Test con configuración custom
    config = MockConfig()
    config.enable_confidence_sizing = True
    config.confidence_sizing_min_multiplier = 0.3
    config.confidence_sizing_max_multiplier = 2.0
    config.confidence_sizing_threshold_low = 50.0
    config.confidence_sizing_threshold_high = 90.0

    execution_stage = TradingExecutionStage(
        broker=None,
        risk_manager=None,
        config=config,
        event_bus=None
    )

    # Test límites extremos
    test_cases = [
        MockSignal("LOW", 50.0, confidence=30.0),   # Muy baja → min multiplier
        MockSignal("HIGH", 50.0, confidence=95.0),  # Muy alta → max multiplier
    ]

    for signal in test_cases:
        size = execution_stage._calculate_position_size(signal)
        assert size >= config.min_quantity, f"Size {size} below min_quantity for confidence {signal.confidence}"
        print(f"✅ Custom config: Confidence {signal.confidence}% → {size} shares")

    print("🎉 Configuration validation test PASSED!\n")

def main():
    """Ejecutar todos los tests"""
    print("🚀 TESTING CONFIDENCE-BASED POSITION SIZING")
    print("=" * 60)

    try:
        # Test 1: Sizing disabled
        test_confidence_sizing_disabled()

        # Test 2: Sizing enabled
        test_confidence_sizing_enabled()

        # Test 3: Edge cases
        test_edge_cases()

        # Test 4: Configuration validation
        test_configuration_validation()

        print("=" * 60)
        print("🎉 ¡TODOS LOS TESTS PASARON!")
        print()
        print("✅ Confidence-based sizing está listo para usar:")
        print("   • Habilitar con: enable_confidence_sizing = true en config.ini")
        print("   • Configurar multiplicadores y umbrales según preferencias")
        print("   • Monitorear logs para ver ajustes de sizing en tiempo real")
        print()
        print("📊 Ejemplo de configuración en config.ini:")
        print("   enable_confidence_sizing = true")
        print("   confidence_sizing_min_multiplier = 0.5  # 50% size para baja confianza")
        print("   confidence_sizing_max_multiplier = 1.5  # 150% size para alta confianza")
        print("   confidence_sizing_threshold_low = 60.0   # Umbral confianza baja")
        print("   confidence_sizing_threshold_high = 85.0  # Umbral confianza alta")

        return True

    except Exception as e:
        print(f"❌ TESTS FALLARON: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)