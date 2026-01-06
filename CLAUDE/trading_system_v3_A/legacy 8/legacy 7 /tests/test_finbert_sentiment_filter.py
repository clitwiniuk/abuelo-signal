"""
Tests for FinBERT Sentiment Filter (Phase 3)

Tests sentiment validation logic:
- Positive sentiment → always accepted
- Neutral sentiment → accepted (FDA, M&A often neutral)
- Negative sentiment + weak price → rejected (trap)
- Negative sentiment + massive price action → accepted (short squeeze)
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.smallcap.catalyst_analyzer import CatalystAnalyzer
from scanner.smallcap.finbert_analyzer import FinBERTResult


class TestFinBERTSentimentFilter(unittest.TestCase):
    """
    Test FinBERT sentiment validation (Phase 3)
    """

    def setUp(self):
        """Setup analyzer with event-driven config"""
        # Mock FinBERT analyzer to avoid loading the model
        with patch('scanner.smallcap.catalyst_analyzer.FinBERTAnalyzer'):
            # Use default config and store event_driven_config separately
            self.analyzer_enabled = CatalystAnalyzer()
            self.analyzer_disabled = CatalystAnalyzer()

            # Inject event_driven_config manually
            self.analyzer_enabled.config = {
                'event_driven_config': {
                    'enable_finbert_filter': True,
                    'finbert_negative_threshold': -0.5,
                    'accept_neutral_sentiment': True,
                }
            }

            self.analyzer_disabled.config = {
                'event_driven_config': {
                    'enable_finbert_filter': False,
                }
            }

    def test_positive_sentiment_accepted(self):
        """Test: Positive sentiment → always accepted"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'positive'
        finbert_result.confidence = 0.85

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=5.0,  # Weak gap
            volume_ratio=1.5,  # Weak volume
            headline="Test positive news"
        )

        self.assertTrue(is_valid, "Positive sentiment should always be accepted")

    def test_neutral_sentiment_accepted(self):
        """Test: Neutral sentiment → accepted (FDA, M&A often neutral)"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'neutral'
        finbert_result.confidence = 0.70

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=10.0,
            volume_ratio=3.0,
            headline="FDA approval announcement"
        )

        self.assertTrue(is_valid, "Neutral sentiment should be accepted by default")

    def test_negative_weak_price_rejected(self):
        """Test: Negative sentiment + weak gap + weak volume → REJECTED (trap)"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'negative'
        finbert_result.confidence = 0.90

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=8.0,  # < 15% (weak)
            volume_ratio=2.5,  # < 3x (weak)
            headline="Company faces regulatory issues"
        )

        self.assertFalse(is_valid, "Negative sentiment with weak price should be rejected")

    def test_negative_short_squeeze_accepted(self):
        """Test: Negative sentiment + massive gap + strong volume → ACCEPTED (short squeeze)"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'negative'
        finbert_result.confidence = 0.80

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=25.0,  # >= 15% (massive)
            volume_ratio=5.0,  # >= 3x (strong)
            headline="SEC investigation announced"
        )

        self.assertTrue(is_valid, "Negative sentiment with massive price action should be accepted (short squeeze)")

    def test_negative_edge_case_15pct_gap(self):
        """Test: Negative sentiment + exactly 15% gap + 3x volume → ACCEPTED"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'negative'
        finbert_result.confidence = 0.75

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=15.0,  # Exactly 15%
            volume_ratio=3.0,  # Exactly 3x
            headline="Negative guidance lowered"
        )

        self.assertTrue(is_valid, "Edge case: exactly 15% gap + 3x volume should be accepted")

    def test_negative_edge_case_14_9pct_gap(self):
        """Test: Negative sentiment + 14.9% gap + 3x volume → REJECTED"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'negative'
        finbert_result.confidence = 0.75

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=14.9,  # < 15%
            volume_ratio=3.0,  # Exactly 3x
            headline="Negative outlook"
        )

        self.assertFalse(is_valid, "Edge case: 14.9% gap should be rejected (< 15%)")

    def test_feature_flag_disabled(self):
        """Test: Feature flag disabled → all sentiment accepted"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'negative'
        finbert_result.confidence = 0.95

        is_valid = self.analyzer_disabled._validate_sentiment(
            finbert_result,
            gap_pct=3.0,  # Very weak
            volume_ratio=1.0,  # Very weak
            headline="Terrible news"
        )

        self.assertTrue(is_valid, "Feature flag disabled → all sentiment should be accepted (backward compatible)")

    def test_neutral_rejected_if_configured(self):
        """Test: Neutral sentiment rejected if accept_neutral_sentiment=False"""
        with patch('scanner.smallcap.catalyst_analyzer.FinBERTAnalyzer'):
            analyzer = CatalystAnalyzer()
            # Inject config with reject neutral
            analyzer.config = {
                'event_driven_config': {
                    'enable_finbert_filter': True,
                    'accept_neutral_sentiment': False,  # Reject neutral
                }
            }

        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'neutral'
        finbert_result.confidence = 0.70

        is_valid = analyzer._validate_sentiment(
            finbert_result,
            gap_pct=10.0,
            volume_ratio=3.0,
            headline="Neutral news"
        )

        self.assertFalse(is_valid, "Neutral sentiment should be rejected if accept_neutral_sentiment=False")

    def test_unknown_sentiment_fail_safe(self):
        """Test: Unknown sentiment → accepted (fail-safe)"""
        finbert_result = MagicMock(spec=FinBERTResult)
        finbert_result.sentiment = 'unknown'  # Not in [positive, neutral, negative]
        finbert_result.confidence = 0.50

        is_valid = self.analyzer_enabled._validate_sentiment(
            finbert_result,
            gap_pct=0.0,
            volume_ratio=0.0,
            headline="Unknown sentiment"
        )

        self.assertTrue(is_valid, "Unknown sentiment should be accepted as fail-safe")


if __name__ == '__main__':
    # Run tests
    print("🧪 Running FinBERT Sentiment Filter tests (Phase 3)...\n")
    unittest.main(verbosity=2)
