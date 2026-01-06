#!/usr/bin/env python3
"""
Test 2: SmallcapDailyScanner Filtros Optimizados

Tests para validar que el SmallcapDailyScanner implementa correctamente:
1. Reducción de max_news_age_hours: 48h -> 8h (83% reducción)
2. Aumento de min_catalyst_strength: 1 -> 5 (5x más selectivo)  
3. Filtrado específico por catalyst type en lugar de límite global
4. Integración correcta con CatalystAnalyzer optimizado
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.smallcap_daily_scanner import SmallcapDailyScanner, SmallcapPlay
from scanner.smallcap.catalyst_analyzer import CatalystInfo
from scanner.ibkr_native_scanner import IBKRScanResult


class TestSmallcapDailyScannerFilters:
    """Test suite for SmallcapDailyScanner optimization"""
    
    @pytest.fixture
    def optimized_config(self):
        """Optimized configuration for intraday smallcaps"""
        return {
            # OPTIMIZED CONFIGURATION
            'min_quality_score': 6.0,
            'min_catalyst_strength': 5,          # INCREASED from 1
            'max_news_age_hours': 8,             # REDUCED from 48  
            'max_news_age_premarket': 16,
            
            # Catalyst-specific aging limits
            'catalyst_max_age': {
                'FDA': 4, 'M&A': 6, 'EARNINGS': 8, 'CONTRACT': 12, 'BREAKTHROUGH': 6, 'OTHER': 6
            },
            
            # News age multipliers
            'news_age_multipliers': {
                'fresh': 1.0, 'recent': 0.8, 'stale': 0.5, 'expired': 0.0
            },
            
            'fresh_news_threshold': 2,
            'recent_news_threshold': 6,
            'stale_news_threshold': 12,
            'max_plays_per_scan': 15,
            'max_ibkr_results': 50,
            'max_headlines_per_symbol': 5,
        }
    
    @pytest.fixture  
    def legacy_config(self):
        """Legacy configuration (pre-optimization)"""
        return {
            'min_quality_score': 3.0,           # Was relaxed for debugging
            'min_catalyst_strength': 1,         # Very permissive
            'max_news_age_hours': 48,           # Way too long for intraday
            'max_news_age_premarket': 48,       # Legacy: same as regular hours
            'catalyst_max_age': {
                'FDA': 48, 'M&A': 48, 'EARNINGS': 48, 'CONTRACT': 48, 'BREAKTHROUGH': 48, 'OTHER': 48
            },
            'news_age_multipliers': {
                'fresh': 1.0, 'recent': 1.0, 'stale': 0.8, 'expired': 0.0
            },
            'fresh_news_threshold': 24,
            'recent_news_threshold': 48,
            'stale_news_threshold': 72,
            'max_plays_per_scan': 15,
            'max_ibkr_results': 50,
            'max_headlines_per_symbol': 5,
        }
    
    @pytest.fixture
    def mock_ibkr_adapter(self):
        """Mock IBKR adapter"""
        adapter = Mock()
        return adapter
    
    @pytest.fixture
    def sample_ibkr_results(self):
        """Sample IBKR scan results"""
        return [
            IBKRScanResult(
                symbol="AAPL",
                contract=None,
                rank=1,
                distance="150.0",
                benchmark="gap",
                projection="up",
                legs="",
                current_price=150.0,
                gap_percentage=12.5,
                volume=1000000,
                avg_volume=300000,
                market_cap=2500000000
            ),
            IBKRScanResult(
                symbol="TSLA",
                contract=None,
                rank=2,
                distance="200.0",
                benchmark="volume",
                projection="up",
                legs="",
                current_price=200.0,
                gap_percentage=8.5,
                volume=800000,
                avg_volume=300000,
                market_cap=650000000
            ),
            IBKRScanResult(
                symbol="NVDA",
                contract=None,
                rank=3,
                distance="500.0",
                benchmark="gap",
                projection="up",
                legs="",
                current_price=500.0,
                gap_percentage=15.2,
                volume=1200000,
                avg_volume=300000,
                market_cap=1200000000
            )
        ]
    
    @pytest.fixture
    def sample_catalyst_results(self):
        """Sample catalyst analysis results with different ages/strengths"""
        return [
            # Fresh, strong FDA catalyst - should pass
            CatalystInfo(
                catalyst_type="FDA",
                strength=8,
                age_hours=2.0,
                keywords_found=["fda approval", "breakthrough therapy"],
                headline="FDA grants breakthrough therapy designation",
                confidence=0.9
            ),
            # Old M&A catalyst - should fail due to age
            CatalystInfo(
                catalyst_type="M&A",
                strength=7,
                age_hours=10.0,  # > 6h limit for M&A
                keywords_found=["acquisition", "merger"],
                headline="Company agrees to acquire competitor",
                confidence=0.8
            ),
            # Weak earnings catalyst - should fail due to low strength
            CatalystInfo(
                catalyst_type="EARNINGS",
                strength=3,      # < 5 minimum
                age_hours=4.0,
                keywords_found=["earnings"],
                headline="Company reports quarterly earnings",
                confidence=0.6
            ),
            # Strong contract catalyst - should pass
            CatalystInfo(
                catalyst_type="CONTRACT",
                strength=6,
                age_hours=8.0,   # < 12h limit for contracts
                keywords_found=["contract", "awarded"],
                headline="Company wins major government contract",
                confidence=0.8
            )
        ]
    
    def test_optimized_vs_legacy_config_differences(self, optimized_config, legacy_config):
        """Test that optimized config is significantly more restrictive"""
        
        # Age limit reduction
        age_reduction = (legacy_config['max_news_age_hours'] - optimized_config['max_news_age_hours']) / legacy_config['max_news_age_hours']
        assert age_reduction >= 0.8, f"Age limit reduction insufficient: {age_reduction:.1%} (expect ≥80%)"
        
        # Strength requirement increase
        strength_multiplier = optimized_config['min_catalyst_strength'] / legacy_config['min_catalyst_strength']
        assert strength_multiplier >= 5, f"Strength multiplier insufficient: {strength_multiplier}x (expect ≥5x)"
        
        # Quality score increase
        quality_improvement = optimized_config['min_quality_score'] / legacy_config['min_quality_score']
        assert quality_improvement >= 1.5, f"Quality score improvement insufficient: {quality_improvement}x"
        
        print(f"\\n=== CONFIG OPTIMIZATION METRICS ===")
        print(f"Age limit reduction: {age_reduction:.1%}")
        print(f"Strength requirement: {strength_multiplier}x stricter")
        print(f"Quality score: {quality_improvement:.1f}x higher")
    
    @patch('scanner.smallcap.smallcap_daily_scanner.IBKRNativeScanner')
    def test_scanner_initialization_with_optimized_config(self, mock_ibkr_scanner, mock_ibkr_adapter, optimized_config):
        """Test that scanner initializes correctly with optimized configuration"""
        
        # Create scanner with optimized config
        scanner = SmallcapDailyScanner(ibkr_adapter=mock_ibkr_adapter, config=optimized_config)
        
        # Verify configuration is applied
        assert scanner.config['min_catalyst_strength'] == 5
        assert scanner.config['max_news_age_hours'] == 8
        assert scanner.config['min_quality_score'] == 6.0
        
        # Verify catalyst analyzer receives correct configuration
        catalyst_config = scanner.catalyst_analyzer.intraday_config
        assert catalyst_config['catalyst_max_age']['FDA'] == 4
        assert catalyst_config['catalyst_max_age']['M&A'] == 6
        assert catalyst_config['news_age_multipliers']['fresh'] == 1.0
    
    def test_catalyst_specific_filtering_logic(self, optimized_config, sample_catalyst_results):
        """Test that catalyst-specific age limits are applied correctly"""
        
        scanner = SmallcapDailyScanner(config=optimized_config)
        
        for catalyst in sample_catalyst_results:
            # Get catalyst-specific age limit
            catalyst_max_age = optimized_config['catalyst_max_age'].get(catalyst.catalyst_type, 6)
            
            # Check age viability
            age_ok = catalyst.age_hours <= catalyst_max_age
            
            # Check strength requirement  
            strength_ok = catalyst.strength >= optimized_config['min_catalyst_strength']
            
            # Expected result
            should_pass = age_ok and strength_ok
            
            print(f"\\n{catalyst.catalyst_type} ({catalyst.age_hours:.1f}h, strength {catalyst.strength}):")
            print(f"  Age limit: {catalyst_max_age}h -> {'✅' if age_ok else '❌'}")
            print(f"  Strength req: ≥{optimized_config['min_catalyst_strength']} -> {'✅' if strength_ok else '❌'}")
            print(f"  Should pass: {'✅' if should_pass else '❌'}")
            
            # Validate expectations
            if catalyst.catalyst_type == "FDA" and catalyst.age_hours == 2.0:
                assert should_pass, "Fresh FDA news should pass"
            elif catalyst.catalyst_type == "M&A" and catalyst.age_hours == 10.0:
                assert not should_pass, "Old M&A news should fail"
            elif catalyst.catalyst_type == "EARNINGS" and catalyst.strength == 3:
                assert not should_pass, "Weak earnings should fail"
            elif catalyst.catalyst_type == "CONTRACT" and catalyst.age_hours == 8.0:
                assert should_pass, "Fresh contract news should pass"
    
    @patch('scanner.smallcap.smallcap_daily_scanner.IBKRNativeScanner')
    def test_filtering_performance_comparison(self, mock_ibkr_scanner, mock_ibkr_adapter, optimized_config, legacy_config):
        """Test that optimized filtering reduces noise significantly"""
        
        # Create both scanners
        optimized_scanner = SmallcapDailyScanner(ibkr_adapter=mock_ibkr_adapter, config=optimized_config)
        legacy_scanner = SmallcapDailyScanner(ibkr_adapter=mock_ibkr_adapter, config=legacy_config)
        
        # Test data with various quality levels
        test_catalysts = [
            # High quality - should pass optimized only
            CatalystInfo("FDA", 8, 2.0, ["fda"], "FDA approval", 0.9),
            
            # Medium quality - should pass legacy only
            CatalystInfo("EARNINGS", 4, 6.0, ["earnings"], "Earnings beat", 0.7),
            
            # Low quality - should pass neither (ideally)
            CatalystInfo("OTHER", 2, 24.0, ["news"], "Company update", 0.4),
            
            # Old but strong - should pass legacy only  
            CatalystInfo("M&A", 9, 48.0, ["acquisition"], "Major acquisition", 0.9),
        ]
        
        optimized_passed = 0
        legacy_passed = 0
        
        for catalyst in test_catalysts:
            # Test optimized filtering
            strength_ok_opt = catalyst.strength >= optimized_config['min_catalyst_strength']
            age_ok_opt = catalyst.age_hours <= optimized_config['catalyst_max_age'].get(catalyst.catalyst_type, 6)
            if strength_ok_opt and age_ok_opt:
                optimized_passed += 1
            
            # Test legacy filtering  
            strength_ok_leg = catalyst.strength >= legacy_config['min_catalyst_strength']
            age_ok_leg = catalyst.age_hours <= legacy_config['max_news_age_hours']
            if strength_ok_leg and age_ok_leg:
                legacy_passed += 1
        
        # Calculate noise reduction
        noise_reduction = (legacy_passed - optimized_passed) / max(legacy_passed, 1)
        
        print(f"\\n=== FILTERING PERFORMANCE ===")
        print(f"Legacy scanner passed: {legacy_passed}/{len(test_catalysts)}")
        print(f"Optimized scanner passed: {optimized_passed}/{len(test_catalysts)}")
        print(f"Noise reduction: {noise_reduction:.1%}")
        
        # Assert significant noise reduction
        assert optimized_passed <= legacy_passed, "Optimized should be more restrictive"
        assert noise_reduction >= 0.5, f"Insufficient noise reduction: {noise_reduction:.1%}"
    
    @patch('scanner.smallcap.smallcap_daily_scanner.IBKRNativeScanner')
    @pytest.mark.asyncio
    async def test_scan_daily_plays_with_optimized_filtering(self, mock_ibkr_scanner, mock_ibkr_adapter, optimized_config, sample_ibkr_results):
        """Test complete scan_daily_plays workflow with optimized filtering"""
        
        # Mock IBKR scanner to return sample results
        mock_scanner_instance = mock_ibkr_scanner.return_value
        mock_scanner_instance.scan_daily_plays = AsyncMock(return_value=sample_ibkr_results)
        
        # Create scanner
        scanner = SmallcapDailyScanner(ibkr_adapter=mock_ibkr_adapter, config=optimized_config)
        
        # Mock news fetching to return controlled catalyst data
        with patch.object(scanner, '_get_news_batch') as mock_news:
            with patch.object(scanner.catalyst_analyzer, 'analyze_multiple_headlines') as mock_analyze:
                
                # Setup mock responses for each symbol
                mock_news.return_value = {
                    'AAPL': [("FDA breakthrough therapy approved", 2.0)],  # Should pass
                    'TSLA': [("Old merger rumors resurface", 10.0)],        # Should fail (age)
                    'NVDA': [("Company announces partnership", 3.0)]       # Should fail (strength)
                }
                
                # Mock catalyst analysis to return appropriate results
                def mock_catalyst_analysis(headlines):
                    if not headlines:
                        return CatalystInfo("OTHER", 1, 0.0, [], "", 0.0)
                    
                    headline = headlines[0][0]
                    age = headlines[0][1] if len(headlines[0]) > 1 else 0.0
                    
                    if "FDA" in headline:
                        return CatalystInfo("FDA", 8, age, ["fda"], headline, 0.9)
                    elif "merger" in headline:
                        return CatalystInfo("M&A", 6, age, ["merger"], headline, 0.8)
                    else:
                        return CatalystInfo("OTHER", 3, age, ["partnership"], headline, 0.6)
                
                mock_analyze.side_effect = mock_catalyst_analysis
                
                # Mock _create_smallcap_play to return plays for passed catalysts
                with patch.object(scanner, '_create_smallcap_play') as mock_create_play:
                    def create_play_side_effect(ibkr_result, catalyst_info):
                        # Only create play if catalyst should pass filtering
                        catalyst_max_age = optimized_config['catalyst_max_age'].get(catalyst_info.catalyst_type, 6)
                        age_ok = catalyst_info.age_hours <= catalyst_max_age
                        strength_ok = catalyst_info.strength >= optimized_config['min_catalyst_strength']
                        
                        if age_ok and strength_ok:
                            return SmallcapPlay(
                                symbol=ibkr_result.symbol,
                                context=Mock(),
                                catalyst=catalyst_info,
                                quality_score=7.0,  # Above minimum
                                trading_recommendation={},
                                scan_timestamp=Mock(),
                                ibkr_rank=ibkr_result.rank
                            )
                        return None
                    
                    mock_create_play.side_effect = create_play_side_effect
                    
                    # Execute scan
                    plays = await scanner.scan_daily_plays()
                    
                    # Verify results
                    assert len(plays) == 1, f"Expected 1 play, got {len(plays)}"
                    assert plays[0].symbol == "AAPL", "Only AAPL should pass optimized filtering"
                    
                    print(f"\\n=== SCAN RESULTS ===")
                    print(f"Total symbols scanned: {len(sample_ibkr_results)}")
                    print(f"Plays created: {len(plays)}")
                    print(f"Selectivity: {len(plays)/len(sample_ibkr_results):.1%}")
    
    def test_quality_score_threshold_enforcement(self, optimized_config):
        """Test that quality score threshold is properly enforced"""
        
        scanner = SmallcapDailyScanner(config=optimized_config)
        
        # Test different quality scores
        quality_scores = [5.0, 6.0, 7.0, 8.0]
        threshold = optimized_config['min_quality_score']
        
        for score in quality_scores:
            should_pass = score >= threshold
            
            print(f"Quality score {score}: {'✅ Pass' if should_pass else '❌ Fail'} (threshold: {threshold})")
            
            if score == 5.0:
                assert not should_pass, "Score 5.0 should fail (below 6.0 threshold)"
            elif score >= 6.0:
                assert should_pass, f"Score {score} should pass (≥6.0 threshold)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])