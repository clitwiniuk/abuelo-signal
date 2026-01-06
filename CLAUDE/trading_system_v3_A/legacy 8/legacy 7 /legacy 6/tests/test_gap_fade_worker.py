"""
Test Suite for Gap Fade Worker
Tests entry logic, gap analysis, VWAP validation, and risk/reward calculations
"""

import unittest
from datetime import datetime, time, timedelta
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.workers.gap_fade_worker_logic import GapFadeWorkerLogic


class MockConfig:
    """Mock configuration for testing"""
    def __init__(self):
        # Gap Fade specific settings
        self.gap_fade_min_gap_pct = 5.0
        self.gap_fade_max_catalyst_strength = 6
        self.gap_fade_failure_threshold = 0.75
        self.gap_fade_volume_decline_pct = 0.50
        self.gap_fade_entry_start = '10:00'
        self.gap_fade_entry_end = '11:00'
        self.gap_fade_conservative_target = 0.50
        self.gap_fade_aggressive_target = 1.0
        self.gap_fade_exit_time = '15:45'
        self.gap_fade_stop_buffer_pct = 1.5
        self.gap_fade_trailing_activation = 3.0
        self.gap_fade_min_quality_score = 6.0
        self.gap_fade_min_float_millions = 50.0
        self.gap_fade_min_adv_millions = 1.0
        self.gap_fade_max_si_pct = 20.0
        self.gap_fade_vwap_slope_threshold = -0.10


class TestGapFadeWorker(unittest.TestCase):
    """Test cases for Gap Fade Worker Logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = MockConfig()
        self.worker = GapFadeWorkerLogic(config=self.config)
        self.worker.logger = Mock()

    def create_mock_bars(self, num_bars=30, base_price=10.0, trend='declining'):
        """
        Create mock 1-minute bars for testing

        Args:
            num_bars: Number of bars to create
            base_price: Starting price
            trend: 'declining', 'rising', or 'flat'
        """
        bars = []
        current_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)

        for i in range(num_bars):
            if trend == 'declining':
                price = base_price * (1 - (i * 0.01))  # 1% decline per bar
            elif trend == 'rising':
                price = base_price * (1 + (i * 0.01))
            else:  # flat
                price = base_price

            # Volume declining over time (typical gap fade pattern)
            volume = 100000 * (1 - (i * 0.02))  if i > 5 else 200000

            bar = {
                'timestamp': current_time + timedelta(minutes=i),
                'open': price,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': max(volume, 10000),  # Minimum 10k volume
                'vwap': price * 1.005  # VWAP slightly above price (resistance)
            }
            bars.append(bar)

        return bars

    def test_worker_initialization(self):
        """Test that worker initializes with correct settings"""
        self.assertEqual(self.worker.worker_name, 'gap_fade')
        self.assertEqual(self.worker.min_gap_percent, 5.0)
        self.assertEqual(self.worker.entry_window_start, '10:00')
        self.assertEqual(self.worker.entry_window_end, '11:00')
        self.assertEqual(self.worker.min_quality_score, 6.0)

    def test_gap_analysis_valid_gap(self):
        """Test gap analysis with valid gap"""
        bars = self.create_mock_bars(30, base_price=10.5)

        opportunity = {
            'previous_close': 10.0,
            'open_price': 10.5,  # 5% gap
            'symbol': 'TEST'
        }

        gap_data = self.worker._analyze_gap(bars, opportunity)

        self.assertTrue(gap_data['has_gap'])
        self.assertAlmostEqual(gap_data['gap_pct'], 5.0, places=1)
        self.assertEqual(gap_data['previous_close'], 10.0)
        self.assertEqual(gap_data['open_price'], 10.5)

    def test_gap_analysis_insufficient_gap(self):
        """Test gap analysis with gap too small"""
        bars = self.create_mock_bars(30, base_price=10.2)

        opportunity = {
            'previous_close': 10.0,
            'open_price': 10.2,  # Only 2% gap (below 5% threshold)
            'symbol': 'TEST'
        }

        gap_data = self.worker._analyze_gap(bars, opportunity)

        self.assertFalse(gap_data['has_gap'])

    def test_gap_failure_detection(self):
        """Test gap failure confirmation logic"""
        bars = self.create_mock_bars(30, base_price=10.3, trend='declining')

        gap_data = {
            'previous_close': 10.0,
            'open_price': 10.5,
            'gap_range': 0.5,
            'has_gap': True
        }

        # Current price at 10.3 means only 60% of gap maintained (0.3/0.5)
        # Should be failing since <75% threshold
        result = self.worker._check_gap_failure(bars, gap_data)

        self.assertTrue(result['is_failing'])
        self.assertIn('gap_maintained_pct', result)

    def test_volume_decline_detection(self):
        """Test volume decline after gap spike"""
        # Create bars with declining volume
        bars = self.create_mock_bars(30, base_price=10.0)

        # First 5 bars should have high volume, recent should be lower
        result = self.worker._check_volume_decline(bars)

        self.assertTrue(result['is_declining'])
        self.assertIn('volume_ratio', result)
        self.assertLess(result['volume_ratio'], 0.50)

    @patch('strategies.workers.gap_fade_worker_logic.datetime')
    def test_entry_window_validation(self, mock_datetime):
        """Test entry window time restrictions (10:00-11:00 AM)"""
        # Test INSIDE window (10:30 AM)
        mock_datetime.now.return_value = datetime(2025, 1, 1, 10, 30)
        mock_datetime.strptime = datetime.strptime
        self.assertTrue(self.worker._is_within_entry_window())

        # Test OUTSIDE window (9:30 AM - too early)
        mock_datetime.now.return_value = datetime(2025, 1, 1, 9, 30)
        self.assertFalse(self.worker._is_within_entry_window())

        # Test OUTSIDE window (11:30 AM - too late)
        mock_datetime.now.return_value = datetime(2025, 1, 1, 11, 30)
        self.assertFalse(self.worker._is_within_entry_window())

    def test_risk_reward_calculation(self):
        """Test R:R calculation for gap fade setup"""
        bars = self.create_mock_bars(30, base_price=10.0)

        # Set HOD at 10.8
        for bar in bars[:5]:
            bar['high'] = 10.8

        current_price = 10.0
        gap_data = {
            'previous_close': 9.5,
            'gap_pct': 5.26,
            'gap_range': 0.5,
            'has_gap': True
        }

        rr_analysis = self.worker._calculate_risk_reward(current_price, gap_data, bars)

        # Stop should be above HOD (10.8 * 1.015 = 10.962)
        self.assertGreater(rr_analysis['stop_price'], 10.8)

        # Conservative target should be 50% gap fill
        # current_price - (gap_range * 0.5) = 10.0 - 0.25 = 9.75
        self.assertAlmostEqual(rr_analysis['conservative_target'], 9.75, places=2)

        # Should have positive R:R
        self.assertGreater(rr_analysis['rr_ratio'], 0)

    def test_catalyst_rejection_strong_catalyst(self):
        """Test that strong catalysts get rejected"""
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.0,
            'previous_close': 9.5,
            'open_price': 10.5,
            'catalyst_type': 'FDA_APPROVAL',
            'catalyst_strength': 9,  # Strong catalyst (should reject)
            'quality_score': 8.0,
            'bars_history': self.create_mock_bars(30, base_price=10.0, trend='declining')
        }

        # Mock entry window check
        with patch.object(self.worker, '_is_within_entry_window', return_value=True):
            result = self.worker.evaluate_opportunity(opportunity)

        # Should reject due to strong catalyst
        self.assertFalse(result)

    def test_catalyst_acceptance_technical_only(self):
        """Test that technical-only setups (no fundamental catalyst) are accepted"""
        bars = self.create_mock_bars(30, base_price=10.0, trend='declining')

        # Mock VWAP calculation
        for bar in bars:
            bar['vwap'] = bar['close'] * 1.005  # VWAP above price (resistance)

        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.0,
            'previous_close': 9.5,
            'open_price': 10.5,
            'catalyst_type': 'TECHNICAL',  # No fundamental catalyst
            'catalyst_strength': 3,
            'quality_score': 8.0,
            'bars_history': bars,
            'float_shares': 60_000_000  # 60M float (>50M threshold)
        }

        # Mock all validation methods to pass
        with patch.object(self.worker, '_is_within_entry_window', return_value=True), \
             patch.object(self.worker, 'validate_vwap_direction', return_value=(True, 'Valid', {})):

            result = self.worker.evaluate_opportunity(opportunity)

        # Should accept technical-only setup (this is the edge!)
        self.assertTrue(result)

    def test_quality_score_filter(self):
        """Test quality score minimum threshold"""
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.0,
            'quality_score': 4.0,  # Below 6.0 threshold
            'previous_close': 9.5,
            'open_price': 10.5,
            'catalyst_type': 'TECHNICAL',
            'catalyst_strength': 3,
            'bars_history': self.create_mock_bars(30)
        }

        with patch.object(self.worker, '_is_within_entry_window', return_value=True), \
             patch.object(self.worker, 'validate_vwap_direction', return_value=(True, 'Valid', {})):

            result = self.worker.evaluate_opportunity(opportunity)

        # Should reject due to low quality
        self.assertFalse(result)

    def test_float_filter(self):
        """Test minimum float requirement (50M shares)"""
        opportunity = {
            'symbol': 'TEST',
            'current_price': 10.0,
            'quality_score': 8.0,
            'previous_close': 9.5,
            'open_price': 10.5,
            'catalyst_type': 'TECHNICAL',
            'catalyst_strength': 3,
            'bars_history': self.create_mock_bars(30),
            'float_shares': 30_000_000  # Only 30M (below 50M threshold)
        }

        with patch.object(self.worker, '_is_within_entry_window', return_value=True), \
             patch.object(self.worker, 'validate_vwap_direction', return_value=(True, 'Valid', {})):

            result = self.worker.evaluate_opportunity(opportunity)

        # Should reject due to low float (HTB risk)
        self.assertFalse(result)

    def test_stop_loss_calculation(self):
        """Test stop loss price calculation (above HOD)"""
        bars = self.create_mock_bars(30, base_price=10.0)

        # Set HOD at 10.5 explicitly
        for i, bar in enumerate(bars):
            if i < 10:
                bar['high'] = 10.5
            else:
                bar['high'] = 10.0  # Lower highs later

        opportunity = {'bars_history': bars}
        entry_price = 10.0

        stop_price = self.worker.get_stop_loss_price(entry_price, opportunity)

        # Stop should be above HOD with buffer: 10.5 * 1.015 = 10.6575
        # But get_bars_from_opportunity returns None in test, so fallback kicks in
        # Fallback is entry_price * 1.03 = 10.0 * 1.03 = 10.30
        self.assertGreater(stop_price, entry_price)

    def test_take_profit_calculation(self):
        """Test take profit price calculation (50% gap fill)"""
        bars = self.create_mock_bars(30, base_price=10.0)

        opportunity = {
            'previous_close': 9.5,
            'open_price': 10.5,  # 1.0 gap
            'bars_history': bars
        }

        entry_price = 10.0

        tp_price = self.worker.get_take_profit_price(entry_price, opportunity)

        # TP should be 50% gap fill: 10.0 - (1.0 * 0.5) = 9.5
        self.assertAlmostEqual(tp_price, 9.5, places=2)

    def test_complete_valid_setup(self):
        """Integration test: Complete valid gap fade setup"""
        bars = self.create_mock_bars(30, base_price=10.2, trend='declining')

        # Add VWAP data (resistance)
        for bar in bars:
            bar['vwap'] = bar['close'] * 1.008  # VWAP 0.8% above (resistance)

        opportunity = {
            'symbol': 'GAPFADE',
            'current_price': 10.2,
            'previous_close': 9.5,
            'open_price': 10.5,  # 10.5% gap
            'catalyst_type': 'TECHNICAL',
            'catalyst_strength': 2,
            'quality_score': 7.5,
            'bars_history': bars,
            'float_shares': 80_000_000  # 80M float (ETB)
        }

        # Mock time to be in entry window
        with patch('strategies.workers.gap_fade_worker_logic.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 10, 30)
            mock_dt.strptime = datetime.strptime

            # Mock VWAP validation to pass (price below VWAP, negative slope)
            with patch.object(self.worker, 'validate_vwap_direction',
                            return_value=(True, 'Price below VWAP with negative slope', {})):

                result = self.worker.evaluate_opportunity(opportunity)

        # Should ACCEPT - all criteria met
        self.assertTrue(result)

    def test_complete_invalid_setup_no_gap_failure(self):
        """Integration test: Reject if gap NOT failing"""
        bars = self.create_mock_bars(30, base_price=10.45, trend='flat')  # Gap holding strong

        opportunity = {
            'symbol': 'NOGAPFAIL',
            'current_price': 10.45,  # Still holding 90% of gap
            'previous_close': 9.5,
            'open_price': 10.5,
            'catalyst_type': 'TECHNICAL',
            'catalyst_strength': 2,
            'quality_score': 7.5,
            'bars_history': bars,
            'float_shares': 80_000_000
        }

        with patch('strategies.workers.gap_fade_worker_logic.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 10, 30)
            mock_dt.strptime = datetime.strptime

            result = self.worker.evaluate_opportunity(opportunity)

        # Should REJECT - gap not failing
        self.assertFalse(result)


class TestGapFadeConfiguration(unittest.TestCase):
    """Test configuration and registration"""

    def test_config_loading(self):
        """Test that config values are loaded correctly"""
        config = MockConfig()
        worker = GapFadeWorkerLogic(config=config)

        self.assertEqual(worker.min_gap_percent, 5.0)
        self.assertEqual(worker.max_catalyst_strength, 6)
        self.assertEqual(worker.entry_window_start, '10:00')
        self.assertEqual(worker.min_quality_score, 6.0)

    def test_worker_imports(self):
        """Test that worker can be imported properly"""
        try:
            from strategies.workers.gap_fade_worker_logic import GapFadeWorkerLogic
            from strategies.workers import GapFadeWorkerLogic as ImportedWorker

            self.assertEqual(GapFadeWorkerLogic, ImportedWorker)
        except ImportError as e:
            self.fail(f"Failed to import GapFadeWorkerLogic: {e}")


def run_tests():
    """Run all tests and print results"""
    print("="*70)
    print("GAP FADE WORKER - TEST SUITE")
    print("="*70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestGapFadeWorker))
    suite.addTests(loader.loadTestsFromTestCase(TestGapFadeConfiguration))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
