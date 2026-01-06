
import unittest
from unittest.mock import MagicMock, patch
import logging
from scanner.smallcap.catalyst_analyzer import CatalystAnalyzer, CatalystInfo

# Mock FinBERT result class
class MockFinBERTResult:
    def __init__(self, sentiment, confidence, catalyst_type='FDA', catalyst_strength=8, keywords=None):
        self.sentiment = sentiment
        self.confidence = confidence
        self.catalyst_type = catalyst_type
        self.catalyst_strength = catalyst_strength
        self.keywords_found = keywords or []

class TestCatalystAnalyzer(unittest.TestCase):
    def setUp(self):
        # Default config for testing
        self.test_intraday_config = {
            'catalyst_max_age': {'FDA': 48, 'EARNINGS': 72},
            'news_age_multipliers': {'fresh': 1.0, 'recent': 0.9, 'stale': 0.5, 'expired': 0.0},
            'fresh_news_threshold': 6,
            'recent_news_threshold': 24,
            'stale_news_threshold': 72,
            'max_news_age_hours': 72,
            'max_news_age_premarket': 96
        }
        self.test_config = {
            'event_driven_config': {
                'enable_finbert_filter': True,
                'finbert_negative_threshold': -0.5,
                'accept_neutral_sentiment': True
            }
        }

    def test_initialization_robustness(self):
        """Test that initialization works with and without config"""
        # Case 1: With full config
        analyzer = CatalystAnalyzer(intraday_config=self.test_intraday_config, config=self.test_config)
        self.assertEqual(analyzer.config, self.test_config)
        
        # Case 2: Without config (should default to empty dict)
        analyzer_no_config = CatalystAnalyzer(intraday_config=self.test_intraday_config)
        self.assertEqual(analyzer_no_config.config, {})
        
        # Case 3: Without intraday config (should use default)
        analyzer_defaults = CatalystAnalyzer()
        self.assertIsNotNone(analyzer_defaults.intraday_config)

    def test_validate_sentiment_logic(self):
        """Test sentiment validation logic"""
        analyzer = CatalystAnalyzer(intraday_config=self.test_intraday_config, config=self.test_config)
        
        # Scenario 1: Positive Sentiment -> ACCEPT
        res_pos = MockFinBERTResult('positive', 0.9)
        self.assertTrue(analyzer._validate_sentiment(res_pos, gap_pct=5.0, volume_ratio=2.0, headline="Good news"))
        
        # Scenario 2: Neutral Sentiment -> ACCEPT (if allowed)
        res_neu = MockFinBERTResult('neutral', 0.8)
        self.assertTrue(analyzer._validate_sentiment(res_neu, gap_pct=5.0, volume_ratio=2.0, headline="Neutral news"))
        
        # Scenario 3: Negative Sentiment -> REJECT (if weak price action)
        res_neg = MockFinBERTResult('negative', 0.9)
        self.assertFalse(analyzer._validate_sentiment(res_neg, gap_pct=5.0, volume_ratio=2.0, headline="Bad news"))
        
        # Scenario 4: Negative Sentiment -> ACCEPT (Short Squeeze Override: Gap > 15%, Vol > 3x)
        self.assertTrue(analyzer._validate_sentiment(res_neg, gap_pct=20.0, volume_ratio=5.0, headline="Bad news but squeeze"))

    def test_validate_sentiment_no_config_crash(self):
        """Test that _validate_sentiment does NOT crash if config is missing"""
        # This simulates the state BEFORE our fix, but now with the fix applied
        # initializing without config defaults self.config to {}
        analyzer = CatalystAnalyzer(intraday_config=self.test_intraday_config)
        
        res = MockFinBERTResult('positive', 0.9)
        
        try:
            # Should NOT raise AttributeError
            result = analyzer._validate_sentiment(res, gap_pct=5.0, volume_ratio=2.0, headline="News")
            # If config is empty, enable_finbert_filter defaults to False (from .get({}, {}) safe access in code?)
            # Let's check the code: 
            # event_driven_config = self.config.get('event_driven_config', {})
            # if not event_driven_config.get('enable_finbert_filter', False): return True
            self.assertTrue(result) 
        except AttributeError as e:
            self.fail(f"Crashed with AttributeError: {e}")

    @patch('scanner.smallcap.catalyst_analyzer.FinBERTAnalyzer')
    def test_analyze_headline_integration(self, MockFinBERT):
        """Test integration of analyze_headline with mocked FinBERT"""
        # Setup mock
        mock_instance = MockFinBERT.return_value
        mock_instance.analyze_headline.return_value = MockFinBERTResult('positive', 0.95, 'FDA', 9)
        
        analyzer = CatalystAnalyzer(intraday_config=self.test_intraday_config, config=self.test_config)
        analyzer.finbert_analyzer = mock_instance # Force set mock
        
        # analyze_headline calling FinBERT
        info = analyzer.analyze_headline("FDA approves drug", news_age_hours=2.0, gap_pct=10.0, volume_ratio=2.0)
        
        self.assertEqual(info.catalyst_type, 'FDA')
        self.assertEqual(info.strength, 9)
        self.assertEqual(info.confidence, 0.95)

if __name__ == '__main__':
    unittest.main()
