"""
Tests for ImplicitEventDetector (Smallcaps)

Tests casos reales de smallcaps:
- FDA approvals con gaps masivos
- Earnings beats
- Pumps sin fundamento (rechazar)
- Chop intraday (rechazar)
"""

import unittest
import asyncio
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.smallcap.implicit_event_detector import ImplicitEventDetector


class TestImplicitEventDetector(unittest.TestCase):
    """
    Test detector de eventos implícitos para smallcaps
    """

    def setUp(self):
        """Setup detector con config para smallcaps"""
        self.detector = ImplicitEventDetector({
            'min_gap_pct': 10.0,      # Smallcaps: 10%+
            'min_volume_ratio': 3.0,  # Smallcaps: 3x+
            'min_range_percentile': 85,
            'min_event_score': 2      # 2/4 flexible
        })

    def test_fda_approval_strong_event(self):
        """Test: FDA approval con gap +50%, volume 8x → SÍ evento (score 3/4 sin bars)"""
        loop = asyncio.get_event_loop()

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='BIOTECH',
                current_price=7.50,
                previous_close=5.00,      # +50% gap
                current_volume=8000000,
                avg_volume=1000000,        # 8x volume
                current_range=3.0,
                historical_ranges=[0.3] * 60  # Rango histórico bajo
            )
        )

        # Debe detectar evento
        self.assertIsNotNone(result)
        self.assertEqual(result['symbol'], 'BIOTECH')
        self.assertEqual(result['score'], 3)  # Gap + Vol + Range (sin bars = no expansion)
        self.assertGreaterEqual(result['gap_pct'], 50.0)
        self.assertGreaterEqual(result['volume_ratio'], 8.0)

    def test_earnings_beat_moderate_event(self):
        """Test: Earnings beat con gap +20%, volume 4x → SÍ evento (score 3/4)"""
        loop = asyncio.get_event_loop()

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='EARNER',
                current_price=4.80,
                previous_close=4.00,      # +20% gap
                current_volume=4000000,
                avg_volume=1000000,        # 4x volume
                current_range=1.2,
                historical_ranges=[0.4] * 60
            )
        )

        # Debe detectar evento
        self.assertIsNotNone(result)
        self.assertEqual(result['score'], 3)  # Gap + Vol + Range
        self.assertIn('Gap +20', ' '.join(result['reasons']))

    def test_pump_no_fundamento_rejected(self):
        """Test: Pump sin fundamento (gap +5%, vol 1.5x) → NO evento (score 0/4)"""
        loop = asyncio.get_event_loop()

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='PUMP',
                current_price=1.05,
                previous_close=1.00,      # +5% gap (bajo threshold 10%)
                current_volume=150000,
                avg_volume=100000,         # 1.5x volume (bajo threshold 3x)
                current_range=0.10,
                historical_ranges=[0.08] * 60
            )
        )

        # NO debe detectar evento
        self.assertIsNone(result)

    def test_weak_gap_high_volume(self):
        """Test: Gap bajo pero volumen alto → SÍ evento si score >= 2"""
        loop = asyncio.get_event_loop()

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='WEIRD',
                current_price=3.30,
                previous_close=3.00,      # +10% gap (justo en threshold)
                current_volume=5000000,
                avg_volume=1000000,        # 5x volume (fuerte)
                current_range=0.80,
                historical_ranges=[0.20] * 60  # Rango muy alto
            )
        )

        # Debe detectar evento (gap + vol + range = 3/4)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result['score'], 2)

    def test_expansion_detection(self):
        """Test: Detección de expansión con bars alcistas"""
        loop = asyncio.get_event_loop()

        # Bars alcistas consecutivas (expansión limpia)
        bullish_bars = [
            {'open': 5.0, 'close': 5.2, 'high': 5.3, 'low': 5.0},  # Alcista
            {'open': 5.2, 'close': 5.5, 'high': 5.6, 'low': 5.1},  # Alcista
            {'open': 5.5, 'close': 5.8, 'high': 5.9, 'low': 5.4},  # Alcista
        ]

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='EXPAND',
                current_price=5.80,
                previous_close=5.00,      # +16% gap
                current_volume=3500000,
                avg_volume=1000000,        # 3.5x volume
                current_range=0.50,
                historical_ranges=[0.20] * 60,
                bars=bullish_bars
            )
        )

        # Debe detectar evento + expansión
        self.assertIsNotNone(result)
        self.assertTrue(result['expansion'])
        self.assertEqual(result['score'], 4)  # Gap + Vol + Range + Expansion

    def test_chop_no_expansion(self):
        """Test: Chop intraday (bars erráticas) → NO expansión"""
        loop = asyncio.get_event_loop()

        # Bars erráticas (chop)
        choppy_bars = [
            {'open': 5.0, 'close': 4.9, 'high': 5.1, 'low': 4.8},  # Roja
            {'open': 4.9, 'close': 5.1, 'high': 5.2, 'low': 4.8},  # Verde
            {'open': 5.1, 'close': 5.0, 'high': 5.2, 'low': 4.9},  # Roja
        ]

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='CHOP',
                current_price=5.00,
                previous_close=4.50,      # +11% gap
                current_volume=3200000,
                avg_volume=1000000,        # 3.2x volume
                current_range=0.40,
                historical_ranges=[0.20] * 60,
                bars=choppy_bars
            )
        )

        # Debe detectar evento pero SIN expansión
        self.assertIsNotNone(result)
        self.assertFalse(result['expansion'])
        self.assertEqual(result['score'], 3)  # Gap + Vol + Range (no expansion)

    def test_invalid_previous_close(self):
        """Test: previous_close inválido → retorna None"""
        loop = asyncio.get_event_loop()

        result = loop.run_until_complete(
            self.detector.detect_anomaly(
                symbol='INVALID',
                current_price=5.00,
                previous_close=0.0,       # ← INVÁLIDO
                current_volume=1000000,
                avg_volume=500000,
                current_range=0.50,
                historical_ranges=[0.20] * 60
            )
        )

        # Debe retornar None (error de validación)
        self.assertIsNone(result)

    def test_config_summary(self):
        """Test: get_config_summary retorna config correcta"""
        summary = self.detector.get_config_summary()

        self.assertEqual(summary['asset_class'], 'SMALLCAPS')
        self.assertEqual(summary['min_gap_pct'], 10.0)
        self.assertEqual(summary['min_volume_ratio'], 3.0)
        self.assertEqual(summary['min_range_percentile'], 85)
        self.assertEqual(summary['min_event_score'], 2)

    def test_percentile_calculation(self):
        """Test: Cálculo de percentile correcto"""
        # Rango actual = 1.0
        # Histórico: [0.1, 0.2, 0.3, ..., 0.9]  (todos menores que 1.0)
        historical = [0.1 * i for i in range(1, 10)]  # [0.1, 0.2, ..., 0.9]

        percentile = self.detector._calculate_percentile(1.0, historical)

        # 9 valores menores de 9 total = 100%
        self.assertEqual(percentile, 100.0)

    def test_percentile_with_no_historical(self):
        """Test: Percentile con histórico vacío → retorna 50 (neutral)"""
        percentile = self.detector._calculate_percentile(1.0, [])

        self.assertEqual(percentile, 50.0)


if __name__ == '__main__':
    # Run tests
    print("🧪 Running ImplicitEventDetector tests (Smallcaps)...\n")
    unittest.main(verbosity=2)
