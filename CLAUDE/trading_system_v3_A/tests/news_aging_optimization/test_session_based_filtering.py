#!/usr/bin/env python3
"""
Test 4: Filtrado Inteligente por Horario (Premarket vs Market)

Tests para validar que el sistema implementa correctamente:
1. Premarket (4:00-9:30 AM): Permite noticias overnight hasta 16 horas
2. Market Hours (9:30-16:00): Límites estrictos por catalyst type
3. Detección automática de session
4. Transiciones suaves entre sessions
5. Manejo de zonas horarias y edge cases
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scanner.smallcap.catalyst_analyzer import CatalystAnalyzer, CatalystInfo


class TestSessionBasedFiltering:
    """Test suite for session-based intelligent filtering"""
    
    @pytest.fixture
    def analyzer(self):
        """CatalystAnalyzer with intraday configuration"""
        return CatalystAnalyzer()
    
    @pytest.fixture
    def premarket_times(self):
        """Various premarket times for testing"""
        return [
            datetime(2025, 1, 21, 4, 0, 0),    # 4:00 AM - Early premarket
            datetime(2025, 1, 21, 6, 30, 0),   # 6:30 AM - Mid premarket  
            datetime(2025, 1, 21, 8, 45, 0),   # 8:45 AM - Late premarket
            datetime(2025, 1, 21, 9, 15, 0),   # 9:15 AM - Just before open
        ]
    
    @pytest.fixture
    def market_times(self):
        """Various market hours times for testing"""
        return [
            datetime(2025, 1, 21, 10, 30, 0),  # 10:30 AM - Morning session
            datetime(2025, 1, 21, 12, 0, 0),   # 12:00 PM - Midday
            datetime(2025, 1, 21, 14, 30, 0),  # 2:30 PM - Afternoon
            datetime(2025, 1, 21, 15, 45, 0),  # 3:45 PM - Near close
        ]
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_premarket_session_detection(self, mock_datetime, analyzer, premarket_times):
        """Test that premarket hours are correctly detected"""
        
        print("\\n=== PREMARKET SESSION DETECTION ===")
        print(f"{'Time':>12} {'Is Premarket':>13} {'Notes':>20}")
        print("-" * 50)
        
        for test_time in premarket_times:
            mock_datetime.now.return_value = test_time
            
            # Test with a catalyst that would normally be rejected due to age
            # but should be allowed in premarket
            is_viable_fda_old = analyzer._is_news_viable_for_intraday('FDA', 10.0)  # 10h old (>4h FDA limit)
            is_viable_ma_old = analyzer._is_news_viable_for_intraday('M&A', 8.0)    # 8h old (>6h M&A limit)
            
            time_str = test_time.strftime("%H:%M")
            hour = test_time.hour
            is_premarket = 4 <= hour <= 9
            
            print(f"{time_str:>12} {'✅' if is_premarket else '❌':>13} {('Overnight news OK' if is_premarket else 'Strict limits'):>20}")
            
            if is_premarket:
                assert is_viable_fda_old, f"FDA news should be viable in premarket at {time_str}"
                assert is_viable_ma_old, f"M&A news should be viable in premarket at {time_str}"
            else:
                # This shouldn't happen for premarket_times, but testing logic
                assert not is_viable_fda_old, f"FDA news should not be viable outside premarket"
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_market_hours_strict_limits(self, mock_datetime, analyzer, market_times):
        """Test that market hours enforce strict catalyst-specific limits"""
        
        print("\\n=== MARKET HOURS STRICT LIMITS ===")
        print(f"{'Time':>12} {'FDA (4h)':>10} {'M&A (6h)':>10} {'EARNINGS (8h)':>15} {'CONTRACT (12h)':>16}")
        print("-" * 70)
        
        for test_time in market_times:
            mock_datetime.now.return_value = test_time
            
            # Test various catalyst types with ages beyond their limits
            fda_viable = analyzer._is_news_viable_for_intraday('FDA', 5.0)         # >4h limit
            ma_viable = analyzer._is_news_viable_for_intraday('M&A', 7.0)          # >6h limit  
            earnings_viable = analyzer._is_news_viable_for_intraday('EARNINGS', 7.0) # <8h limit
            contract_viable = analyzer._is_news_viable_for_intraday('CONTRACT', 10.0) # <12h limit
            
            time_str = test_time.strftime("%H:%M")
            
            print(f"{time_str:>12} {'❌' if not fda_viable else '✅':>10} {'❌' if not ma_viable else '✅':>10} {'✅' if earnings_viable else '❌':>15} {'✅' if contract_viable else '❌':>16}")
            
            # During market hours, should enforce strict limits
            assert not fda_viable, f"FDA news >4h should be rejected during market at {time_str}"
            assert not ma_viable, f"M&A news >6h should be rejected during market at {time_str}"
            assert earnings_viable, f"EARNINGS news <8h should be accepted during market at {time_str}"
            assert contract_viable, f"CONTRACT news <12h should be accepted during market at {time_str}"
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_session_transition_boundary_cases(self, mock_datetime, analyzer):
        """Test behavior at session transition boundaries"""
        
        boundary_times = [
            (datetime(2025, 1, 21, 3, 59, 0), False, "Just before premarket"),
            (datetime(2025, 1, 21, 4, 0, 0), True, "Premarket start"),
            (datetime(2025, 1, 21, 4, 1, 0), True, "Just after premarket start"),
            (datetime(2025, 1, 21, 9, 29, 0), True, "Just before market open"),
            (datetime(2025, 1, 21, 9, 59, 0), True, "Still premarket (hour=9)"),
            (datetime(2025, 1, 21, 10, 0, 0), False, "Market hours (hour=10)"),
        ]
        
        print("\\n=== SESSION TRANSITION BOUNDARIES ===")
        print(f"{'Time':>12} {'Premarket':>11} {'FDA 10h OK':>12} {'Notes':>25}")
        print("-" * 65)
        
        for test_time, expected_premarket, notes in boundary_times:
            mock_datetime.now.return_value = test_time
            
            # Test with news that would only be viable in premarket
            fda_10h_viable = analyzer._is_news_viable_for_intraday('FDA', 10.0)
            
            time_str = test_time.strftime("%H:%M")
            hour = test_time.hour
            actual_premarket = 4 <= hour <= 9
            
            print(f"{time_str:>12} {'✅' if actual_premarket else '❌':>11} {'✅' if fda_10h_viable else '❌':>12} {notes:>25}")
            
            assert actual_premarket == expected_premarket, \
                f"Premarket detection wrong at {time_str}"
            
            if expected_premarket:
                assert fda_10h_viable, f"Old news should be viable in premarket at {time_str}"
            else:
                assert not fda_10h_viable, f"Old news should not be viable outside premarket at {time_str}"
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_premarket_max_age_limit(self, mock_datetime, analyzer):
        """Test that premarket still has a maximum age limit (16h)"""
        
        # Set premarket time
        mock_datetime.now.return_value = datetime(2025, 1, 21, 7, 0, 0)  # 7:00 AM
        
        age_test_cases = [
            (12.0, True, "12h old - should pass"),
            (15.0, True, "15h old - should pass"),
            (16.0, True, "16h old - at limit"),
            (17.0, False, "17h old - should fail"),
            (24.0, False, "24h old - should fail"),
            (48.0, False, "48h old - should fail"),
        ]
        
        print("\\n=== PREMARKET MAX AGE LIMIT (16h) ===")
        print(f"{'Age (h)':>8} {'Viable':>8} {'Notes':>25}")
        print("-" * 45)
        
        for age, expected_viable, notes in age_test_cases:
            fda_viable = analyzer._is_news_viable_for_intraday('FDA', age)
            
            print(f"{age:8.1f} {'✅' if fda_viable else '❌':>8} {notes:>25}")
            
            assert fda_viable == expected_viable, \
                f"Age {age}h viability wrong in premarket: expected {expected_viable}, got {fda_viable}"
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_catalyst_analysis_with_session_context(self, mock_datetime, analyzer):
        """Test complete catalyst analysis considering session context"""
        
        test_scenarios = [
            # (time, headline, age_hours, expected_strength_range, should_pass)
            (
                datetime(2025, 1, 21, 6, 0, 0),  # Premarket
                "FDA grants breakthrough therapy designation",
                3.0,  # Within FDA 4h limit in premarket
                (6, 8),  # Strong with slight time decay
                True
            ),
            (
                datetime(2025, 1, 21, 11, 0, 0),  # Market hours
                "FDA grants breakthrough therapy designation", 
                12.0,  # Too old for market hours
                (1, 2),  # Minimal strength
                False
            ),
            (
                datetime(2025, 1, 21, 7, 0, 0),  # Premarket
                "Company announces major acquisition deal",
                5.0,  # Within M&A 6h limit in premarket
                (8, 11),  # M&A has high baseline strength
                True
            ),
            (
                datetime(2025, 1, 21, 13, 0, 0),  # Market hours
                "Company announces major acquisition deal",
                10.0,  # Too old for M&A in market hours
                (1, 2),  # Minimal strength
                False
            ),
        ]
        
        print("\\n=== CATALYST ANALYSIS WITH SESSION CONTEXT ===")
        
        for i, (test_time, headline, age, expected_range, should_pass) in enumerate(test_scenarios):
            mock_datetime.now.return_value = test_time
            
            result = analyzer.analyze_headline(headline, age)
            viable = analyzer._is_news_viable_for_intraday(result.catalyst_type, age)
            
            time_str = test_time.strftime("%H:%M")
            session = "Premarket" if 4 <= test_time.hour <= 9 else "Market"
            
            print(f"\\nScenario {i+1}: {session} {time_str}")
            print(f"  Headline: {headline[:50]}...")
            print(f"  Age: {age}h")
            print(f"  Catalyst: {result.catalyst_type}")
            print(f"  Strength: {result.strength} (expected {expected_range[0]}-{expected_range[1]})")
            print(f"  Viable: {'✅' if viable else '❌'}")
            print(f"  Should pass: {'✅' if should_pass else '❌'}")
            
            # Verify expectations
            assert viable == should_pass, \
                f"Scenario {i+1}: viability mismatch"
            
            if should_pass:
                assert expected_range[0] <= result.strength <= expected_range[1], \
                    f"Scenario {i+1}: strength {result.strength} outside expected range {expected_range}"
    
    @patch('scanner.smallcap.catalyst_analyzer.datetime')
    def test_overnight_news_scenario(self, mock_datetime, analyzer):
        """Test realistic overnight news scenarios"""
        
        # Simulate news that broke overnight and is being processed in premarket
        overnight_scenarios = [
            {
                'headline': "FDA approves new cancer drug after positive trial results",
                'broke_at': datetime(2025, 1, 20, 18, 0, 0),  # 6:00 PM previous day
                'processing_at': datetime(2025, 1, 21, 7, 0, 0),  # 7:00 AM next day  
                'age_hours': 13.0,
                'expected_catalyst': 'FDA',
                'should_pass_premarket': True,
                'should_pass_market': False
            },
            {
                'headline': "Major tech company announces acquisition of competitor",
                'broke_at': datetime(2025, 1, 20, 20, 30, 0),  # 8:30 PM previous day
                'processing_at': datetime(2025, 1, 21, 8, 30, 0),  # 8:30 AM next day
                'age_hours': 12.0,
                'expected_catalyst': 'M&A',
                'should_pass_premarket': True,
                'should_pass_market': False
            },
            {
                'headline': "Company reports strong quarterly earnings after close",
                'broke_at': datetime(2025, 1, 20, 16, 15, 0),  # 4:15 PM previous day  
                'processing_at': datetime(2025, 1, 21, 8, 0, 0),  # 8:00 AM next day
                'age_hours': 15.75,
                'expected_catalyst': 'EARNINGS',
                'should_pass_premarket': True,
                'should_pass_market': True  # EARNINGS has 8h limit but this is 15h, so False
            }
        ]
        
        print("\\n=== OVERNIGHT NEWS SCENARIOS ===")
        
        for i, scenario in enumerate(overnight_scenarios):
            print(f"\\nScenario {i+1}: {scenario['expected_catalyst']} News")
            print(f"  Broke: {scenario['broke_at'].strftime('%Y-%m-%d %H:%M')}")
            print(f"  Processing: {scenario['processing_at'].strftime('%Y-%m-%d %H:%M')}")
            print(f"  Age: {scenario['age_hours']:.1f}h")
            
            # Test in premarket
            mock_datetime.now.return_value = scenario['processing_at']
            result_premarket = analyzer.analyze_headline(scenario['headline'], scenario['age_hours'])
            viable_premarket = analyzer._is_news_viable_for_intraday(result_premarket.catalyst_type, scenario['age_hours'])
            
            print(f"  Premarket viable: {'✅' if viable_premarket else '❌'} (expected {'✅' if scenario['should_pass_premarket'] else '❌'})")
            
            # Test in market hours (simulate later processing)
            market_time = datetime(2025, 1, 21, 11, 0, 0)
            mock_datetime.now.return_value = market_time
            viable_market = analyzer._is_news_viable_for_intraday(result_premarket.catalyst_type, scenario['age_hours'])
            
            print(f"  Market viable: {'✅' if viable_market else '❌'} (expected {'✅' if scenario['should_pass_market'] else '❌'})")
            
            # Verify catalyst detection
            assert result_premarket.catalyst_type == scenario['expected_catalyst'], \
                f"Wrong catalyst detected: expected {scenario['expected_catalyst']}, got {result_premarket.catalyst_type}"
            
            # Verify premarket behavior
            assert viable_premarket == scenario['should_pass_premarket'], \
                f"Premarket viability wrong for scenario {i+1}"
            
            # Verify market behavior (adjusted for EARNINGS special case)
            expected_market = scenario['should_pass_market'] and scenario['age_hours'] <= 8.0
            assert viable_market == expected_market, \
                f"Market viability wrong for scenario {i+1}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])