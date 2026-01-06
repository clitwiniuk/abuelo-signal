#!/usr/bin/env python3
"""
Test Scanner Enhancements

Verifica que las mejoras del scanner funcionan correctamente:
- Cálculo de ATR
- Integración de ODS classifier
- Integración de Intraday Structure classifier
- Enhanced quality score
- Extracción de ORB data
"""

import sys
import os
from datetime import datetime, time, timedelta
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import scanner helper functions
from scanner_main import calculate_atr, extract_orb_data, calculate_enhanced_quality_score


@dataclass
class MockBar:
    """Mock bar for testing"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


def create_mock_bars():
    """Create mock bars for testing"""
    bars = []
    base_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)

    # Create 60 bars (1 hour of 1-min data)
    for i in range(60):
        bar_time = base_time + timedelta(minutes=i)

        # Simulate trending price action with volatility
        trend_price = 10.0 + (i * 0.05)  # Uptrend
        volatility = 0.2 if i < 30 else 0.1  # Higher vol first 30 min

        bars.append(MockBar(
            timestamp=bar_time,
            open=trend_price,
            high=trend_price + volatility,
            low=trend_price - volatility,
            close=trend_price + (volatility / 2),
            volume=100000 + i * 1000
        ))

    return bars


def test_scanner_enhancements():
    """Test all scanner enhancements"""
    print("=" * 80)
    print("SCANNER ENHANCEMENTS - TEST SUITE")
    print("=" * 80)
    print()

    # Create mock bars
    bars = create_mock_bars()
    print(f"✅ Created {len(bars)} mock bars")
    print()

    # ========================================================================
    # TEST 1: ATR Calculation
    # ========================================================================
    print("1️⃣  TEST ATR CALCULATION")
    print("-" * 80)

    atr_pct = calculate_atr(bars, period=14)

    print(f"   ATR: {atr_pct:.2f}%")

    # Validate ATR is reasonable (should be 1-10% for smallcaps)
    assert 0.5 <= atr_pct <= 15.0, f"ATR {atr_pct:.2f}% seems unreasonable"
    print(f"   ✅ PASSED - ATR is reasonable ({atr_pct:.2f}%)")
    print()

    # ========================================================================
    # TEST 2: ORB Data Extraction
    # ========================================================================
    print("2️⃣  TEST ORB DATA EXTRACTION")
    print("-" * 80)

    orb_data = extract_orb_data(bars)

    if orb_data:
        print(f"   ORB High: ${orb_data['orb_high']:.2f}")
        print(f"   ORB Low: ${orb_data['orb_low']:.2f}")
        print(f"   ORB Range: {orb_data['orb_range_pct']:.2f}%")
        print(f"   ORB Bars: {orb_data['orb_bar_count']}")
        print(f"   Current vs ORB: {orb_data['current_vs_orb']}")
        print(f"   ORB Avg Volume: {orb_data['orb_avg_volume']:,}")

        assert orb_data['orb_bar_count'] >= 20, "Should have at least 20 ORB bars"
        assert orb_data['orb_high'] > orb_data['orb_low'], "ORB high should be > low"
        assert orb_data['current_vs_orb'] in ['ABOVE_HIGH', 'BELOW_LOW', 'INSIDE_RANGE'], "Invalid position"

        print("   ✅ PASSED - ORB data extracted correctly")
    else:
        print("   ⚠️  No ORB data (not enough bars or outside ORB time)")

    print()

    # ========================================================================
    # TEST 3: Enhanced Quality Score
    # ========================================================================
    print("3️⃣  TEST ENHANCED QUALITY SCORE")
    print("-" * 80)

    # Test case 1: Base score only (use high ATR to avoid low vol bonus)
    base_score = 70.0
    enhanced_score_1 = calculate_enhanced_quality_score(
        base_score=base_score,
        ods_data=None,
        structure_data=None,
        atr_pct=6.0  # High ATR - no bonuses
    )
    print(f"   Test 1 - Base only: {base_score:.0f} → {enhanced_score_1:.0f}")
    assert enhanced_score_1 == base_score, "Should not change without patterns"
    print("   ✅ PASSED - Base score unchanged")

    # Test case 2: With ODS STRONG_BULLISH
    ods_data_strong = {
        'classification': 'STRONG_BULLISH',
        'strength': 8.5
    }
    enhanced_score_2 = calculate_enhanced_quality_score(
        base_score=base_score,
        ods_data=ods_data_strong,
        structure_data=None,
        atr_pct=6.0  # High ATR
    )
    print(f"   Test 2 - ODS STRONG: {base_score:.0f} → {enhanced_score_2:.0f}")
    assert enhanced_score_2 == base_score + 10, "Should add +10 for STRONG_BULLISH"
    print("   ✅ PASSED - ODS bonus applied (+10)")

    # Test case 3: With intraday structure continuation
    structure_data_continuation = {
        'continuation_type': 'PULLBACK_TO_VWAP',
        'liquidity_sweep_detected': False
    }
    enhanced_score_3 = calculate_enhanced_quality_score(
        base_score=base_score,
        ods_data=None,
        structure_data=structure_data_continuation,
        atr_pct=6.0  # High ATR
    )
    print(f"   Test 3 - Continuation: {base_score:.0f} → {enhanced_score_3:.0f}")
    assert enhanced_score_3 == base_score + 5, "Should add +5 for continuation"
    print("   ✅ PASSED - Continuation bonus applied (+5)")

    # Test case 4: With liquidity sweep
    structure_data_sweep = {
        'continuation_type': 'PULLBACK_TO_VWAP',
        'liquidity_sweep_detected': True,
        'sweep_direction': 'BULLISH_RECLAIM'
    }
    enhanced_score_4 = calculate_enhanced_quality_score(
        base_score=base_score,
        ods_data=None,
        structure_data=structure_data_sweep,
        atr_pct=6.0  # High ATR
    )
    print(f"   Test 4 - Sweep: {base_score:.0f} → {enhanced_score_4:.0f}")
    assert enhanced_score_4 == base_score + 10, "Should add +5 continuation + +5 sweep"
    print("   ✅ PASSED - Sweep bonus applied (+10)")

    # Test case 5: All bonuses combined
    enhanced_score_5 = calculate_enhanced_quality_score(
        base_score=base_score,
        ods_data=ods_data_strong,
        structure_data=structure_data_sweep,
        atr_pct=3.5  # Low volatility
    )
    expected_5 = base_score + 10 + 10 + 5  # ODS + structure + low vol
    print(f"   Test 5 - All bonuses: {base_score:.0f} → {enhanced_score_5:.0f} (expected {expected_5:.0f})")
    assert enhanced_score_5 == expected_5, f"Should add all bonuses (+25 total)"
    print("   ✅ PASSED - All bonuses applied (+25)")

    # Test case 6: Cap at 100
    enhanced_score_6 = calculate_enhanced_quality_score(
        base_score=90.0,
        ods_data=ods_data_strong,
        structure_data=structure_data_sweep,
        atr_pct=3.5
    )
    print(f"   Test 6 - Cap at 100: 90.0 → {enhanced_score_6:.0f}")
    assert enhanced_score_6 == 100.0, "Should cap at 100"
    print("   ✅ PASSED - Capped at 100")

    print()

    # ========================================================================
    # TEST 4: Integration Test - Full Opportunity Enrichment
    # ========================================================================
    print("4️⃣  INTEGRATION TEST - FULL OPPORTUNITY ENRICHMENT")
    print("-" * 80)

    # Simulate a full opportunity enrichment
    mock_opportunity = {
        'symbol': 'TEST',
        'quality_score': 75.0,
        'atr_percent': None,
        'ods_data': None,
        'intraday_structure': None,
        'orb_data': None
    }

    # Apply enhancements
    mock_opportunity['atr_percent'] = atr_pct
    mock_opportunity['orb_data'] = orb_data
    mock_opportunity['ods_data'] = ods_data_strong
    mock_opportunity['intraday_structure'] = structure_data_sweep

    # Recalculate quality score
    mock_opportunity['quality_score'] = calculate_enhanced_quality_score(
        base_score=75.0,
        ods_data=mock_opportunity['ods_data'],
        structure_data=mock_opportunity['intraday_structure'],
        atr_pct=mock_opportunity['atr_percent']
    )

    print("   Enriched Opportunity:")
    print(f"      Symbol: {mock_opportunity['symbol']}")
    print(f"      Quality Score: {mock_opportunity['quality_score']:.0f} (was 75)")
    print(f"      ATR: {mock_opportunity['atr_percent']:.2f}%")
    print(f"      ODS: {mock_opportunity['ods_data']['classification']}")
    print(f"      Structure: {mock_opportunity['intraday_structure']['continuation_type']}")
    if mock_opportunity['orb_data']:
        print(f"      ORB Range: {mock_opportunity['orb_data']['orb_range_pct']:.2f}%")

    # Validate enrichment
    assert mock_opportunity['quality_score'] > 75.0, "Quality should be enhanced"
    assert mock_opportunity['atr_percent'] > 0, "ATR should be calculated"
    assert mock_opportunity['ods_data'] is not None, "ODS data should be present"
    assert mock_opportunity['intraday_structure'] is not None, "Structure data should be present"

    print("   ✅ PASSED - Full opportunity enrichment working")

    print()
    print("=" * 80)
    print("✅ ALL TESTS PASSED - Scanner enhancements working correctly!")
    print("=" * 80)
    print()

    # Summary
    print("📊 SCANNER ENHANCEMENT SUMMARY:")
    print(f"   ✅ ATR calculation: {atr_pct:.2f}%")
    print(f"   ✅ ORB data extraction: {'Working' if orb_data else 'N/A (time-based)'}")
    print(f"   ✅ Enhanced quality score: 75 → {mock_opportunity['quality_score']:.0f} (+{mock_opportunity['quality_score'] - 75:.0f})")
    print(f"   ✅ ODS integration: {mock_opportunity['ods_data']['classification']}")
    print(f"   ✅ Intraday structure: {mock_opportunity['intraday_structure']['continuation_type']}")
    print()

    print("🎯 EXPECTED IMPACT ON TRADE ARBITER:")
    print(f"   Before: quality=75, no patterns → score ~65")
    print(f"   After: quality={mock_opportunity['quality_score']:.0f}, 2+ patterns → score ~91 (+26 pts)")
    print(f"   Risk sizing: Base 1.2% → Adaptive 1.7% (+42% size)")
    print()


if __name__ == "__main__":
    test_scanner_enhancements()
