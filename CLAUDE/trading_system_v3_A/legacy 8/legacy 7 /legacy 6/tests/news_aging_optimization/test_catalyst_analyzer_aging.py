#!/usr/bin/env python3
"""
Test 1: CatalystAnalyzer Aging Diferenciado por Tipo

Tests para validar que el CatalystAnalyzer implementa correctamente:
1. Límites específicos por tipo de catalyst (FDA: 4h, M&A: 6h, etc.)
2. Multipliers de time decay agresivos
3. Detección automática de session (premarket vs market)
4. Filtrado inteligente basado en viabilidad intraday
"""

import pytest
import json
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.catalyst_analyzer import CatalystAnalyzer, CatalystInfo


class TestCatalystAnalyzerAging:
    """Test suite for CatalystAnalyzer aging optimization"""
    
    @pytest.fixture
    def intraday_config(self):
        """Configuration optimized for intraday smallcaps"""
        return {
            'catalyst_max_age': {
                'FDA': 4,                     # FDA momentum fades quickly
                'M&A': 6,                     # M&A has short momentum window
                'EARNINGS': 8,                # Earnings can sustain longer
                'CONTRACT': 12,               # Contracts more sustained
                'BREAKTHROUGH': 6,            # Breakthrough momentum medium
                'OTHER': 6                    # Default for unclassified
            },
            'news_age_multipliers': {
                'fresh': 1.0,                 # 0-2 hours: full strength
                'recent': 0.9,                # 2-6 hours: 90% strength
                'stale': 0.6,                 # 6-12 hours: 60% strength
                'expired': 0.0                # 12+ hours: reject
            },
            'fresh_news_threshold': 2,        # Fresh news cutoff
            'recent_news_threshold': 8,       # Recent news cutoff (extended for CONTRACT)
            'stale_news_threshold': 14,       # Stale news cutoff
            'max_news_age_hours': 8,          # Hard limit for intraday
            'max_news_age_premarket': 16,     # Allow overnight news in premarket
        }
    
    @pytest.fixture
    def analyzer(self, intraday_config):
        """CatalystAnalyzer with intraday optimization"""
        return CatalystAnalyzer(intraday_config=intraday_config)
    
    @pytest.fixture
    def test_data(self):
        """Load test data from JSON file"""
        test_data_path = os.path.join(os.path.dirname(__file__), 'test_data', 'catalyst_examples.json')
        with open(test_data_path, 'r') as f:
            return json.load(f)
    
    def test_catalyst_type_specific_aging_limits(self, analyzer, test_data):
        """Test that different catalyst types have different age limits (market hours only)"""
        
        # Test FDA - should reject after 4 hours (force market hours behavior)
        fda_old = test_data['fda_news'][1]  # 6 hours old
        assert not analyzer._is_news_viable_for_intraday('FDA', fda_old['age_hours'], force_market_hours=True)
        
        # Test M&A - should reject after 6 hours  
        ma_old = test_data['ma_news'][1]  # 8 hours old
        assert not analyzer._is_news_viable_for_intraday('M&A', ma_old['age_hours'], force_market_hours=True)
        
        # Test EARNINGS - should accept up to 8 hours
        earnings_ok = test_data['earnings_news'][0]  # 4 hours old
        assert analyzer._is_news_viable_for_intraday('EARNINGS', earnings_ok['age_hours'], force_market_hours=True)
        
        # Test CONTRACT - should accept up to 12 hours
        contract_ok = test_data['contract_news'][0]  # 8 hours old
        assert analyzer._is_news_viable_for_intraday('CONTRACT', contract_ok['age_hours'], force_market_hours=True)
    
    def test_time_decay_multipliers(self, analyzer):
        """Test aggressive time decay multipliers"""
        
        # Fresh news (0-2h) should get full strength
        assert analyzer._calculate_intraday_time_multiplier(1.0) == 1.0
        assert analyzer._calculate_intraday_time_multiplier(2.0) == 1.0
        
        # Recent news (2-8h) should get 90% strength
        assert analyzer._calculate_intraday_time_multiplier(3.0) == 0.9
        assert analyzer._calculate_intraday_time_multiplier(8.0) == 0.9
        
        # Stale news (8-14h) should get 60% strength
        assert analyzer._calculate_intraday_time_multiplier(10.0) == 0.6
        assert analyzer._calculate_intraday_time_multiplier(14.0) == 0.6
        
        # Expired news (14h+) should be rejected (0% strength)
        assert analyzer._calculate_intraday_time_multiplier(15.0) == 0.0
        assert analyzer._calculate_intraday_time_multiplier(24.0) == 0.0
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_premarket_session_detection(self, mock_datetime, analyzer):
        """Test that premarket hours allow longer news age"""
        
        # Mock premarket time (7:00 AM)
        mock_datetime.now.return_value = datetime(2025, 1, 21, 7, 0, 0)
        
        # During premarket, should allow 16-hour old news
        assert analyzer._is_news_viable_for_intraday('FDA', 15.0)  # Would normally be rejected
        assert analyzer._is_news_viable_for_intraday('M&A', 12.0)   # Would normally be rejected
        
        # But should still reject extremely old news
        assert not analyzer._is_news_viable_for_intraday('FDA', 20.0)
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_market_hours_strict_limits(self, mock_datetime, analyzer):
        """Test that market hours enforce strict catalyst-specific limits"""
        
        # Mock market hours (10:00 AM)
        mock_datetime.now.return_value = datetime(2025, 1, 21, 10, 0, 0)
        
        # During market hours, should enforce strict limits
        assert not analyzer._is_news_viable_for_intraday('FDA', 5.0)    # FDA limit is 4h
        assert not analyzer._is_news_viable_for_intraday('M&A', 7.0)    # M&A limit is 6h
        assert analyzer._is_news_viable_for_intraday('EARNINGS', 7.0)   # EARNINGS limit is 8h
        assert analyzer._is_news_viable_for_intraday('CONTRACT', 10.0)  # CONTRACT limit is 12h
    
    def test_catalyst_strength_with_aging(self, analyzer, test_data):
        """Test that catalyst strength is properly reduced with aging"""
        
        # Test fresh FDA news - should maintain high strength
        fda_fresh = test_data['fda_news'][0]
        result_fresh = analyzer.analyze_headline(fda_fresh['headline'], fda_fresh['age_hours'])
        
        # Test same headline but aged - should have reduced strength
        result_aged = analyzer.analyze_headline(fda_fresh['headline'], 10.0)  # 10 hours old
        
        assert result_fresh.strength >= 5  # Should pass minimum strength
        assert result_aged.strength < result_fresh.strength  # Should be reduced
        assert result_aged.strength == 1  # Should be minimal due to age limit exceeded
    
    def test_negative_keywords_impact(self, analyzer, test_data):
        """Test that negative keywords properly reduce strength"""
        
        negative_fda = test_data['negative_news'][0]
        result = analyzer.analyze_headline(negative_fda['headline'], negative_fda['age_hours'])
        
        # Should be classified as FDA but with very low strength due to negative keywords
        assert result.catalyst_type == 'FDA'
        assert result.strength <= 3  # Should be significantly reduced
    
    def test_end_to_end_catalyst_filtering(self, analyzer, test_data):
        """Test complete filtering pipeline for various catalyst types"""
        
        results = {}
        
        # Test all catalyst types with their examples
        for catalyst_type, examples in test_data.items():
            if catalyst_type != 'negative_news':  # Skip negative examples for this test
                results[catalyst_type] = []
                
                for example in examples:
                    result = analyzer.analyze_headline(example['headline'], example['age_hours'])
                    
                    # Check if should pass based on intraday viability
                    viable = analyzer._is_news_viable_for_intraday(result.catalyst_type, example['age_hours'])
                    passes_strength = result.strength >= 5
                    should_pass = viable and passes_strength
                    
                    results[catalyst_type].append({
                        'headline': example['headline'],
                        'age_hours': example['age_hours'],
                        'catalyst_type': result.catalyst_type,
                        'strength': result.strength,
                        'viable': viable,
                        'passes_strength': passes_strength,
                        'should_pass': should_pass,
                        'expected': example['should_pass_intraday']
                    })
                    
                    # Assert that result matches expectation
                    assert should_pass == example['should_pass_intraday'], \
                        f"Failed for {example['headline']}: expected {example['should_pass_intraday']}, got {should_pass}"
        
        # Print summary for debugging
        print("\\n=== CATALYST FILTERING RESULTS ===")
        for catalyst_type, test_results in results.items():
            passed = sum(1 for r in test_results if r['should_pass'])
            total = len(test_results)
            print(f"{catalyst_type.upper()}: {passed}/{total} passed intraday filtering")
    
    def test_performance_metrics(self, analyzer, test_data):
        """Test that optimization meets performance targets"""
        
        all_examples = []
        for examples in test_data.values():
            all_examples.extend(examples)
        
        passed_count = 0
        high_quality_count = 0
        
        for example in all_examples:
            result = analyzer.analyze_headline(example['headline'], example['age_hours'])
            viable = analyzer._is_news_viable_for_intraday(result.catalyst_type, example['age_hours'])
            passes_strength = result.strength >= 5
            
            if viable and passes_strength:
                passed_count += 1
                if result.strength >= 7:
                    high_quality_count += 1
        
        total_examples = len(all_examples)
        
        # Performance metrics
        pass_rate = passed_count / total_examples
        quality_rate = high_quality_count / max(passed_count, 1)  # Avoid division by zero
        
        print(f"\\n=== PERFORMANCE METRICS ===")
        print(f"Total examples: {total_examples}")
        print(f"Passed filtering: {passed_count} ({pass_rate:.1%})")
        print(f"High quality (≥7 strength): {high_quality_count} ({quality_rate:.1%})")
        
        # Assertions for performance targets
        assert pass_rate <= 0.6, f"Pass rate too high: {pass_rate:.1%} (expect ≤60% for selectivity)"
        assert quality_rate >= 0.3, f"Quality rate too low: {quality_rate:.1%} (expect ≥30% high quality)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])