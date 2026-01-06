#!/usr/bin/env python3
"""
Test Workers Scanner Data Usage - TARGETED TEST

Specifically tests that Daily Plays and ORB workers USE scanner-provided data
instead of recalculating.

This test mocks time and conditions to ensure workers execute their logic.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, List
from unittest.mock import patch, Mock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def create_enriched_opportunity_for_daily_plays() -> Dict[str, Any]:
    """Create opportunity that will pass Daily Plays filters"""
    from datetime import datetime

    # Create bars that represent a trend
    bars = []
    base_time = datetime.now().replace(hour=10, minute=0, second=0)  # 10 AM ET
    for i in range(60):
        bars.append(Mock(
            timestamp=base_time + timedelta(minutes=i),
            open=5.0 + i * 0.02,
            high=5.1 + i * 0.02,
            low=4.95 + i * 0.02,
            close=5.05 + i * 0.02,
            volume=100000
        ))

    return {
        'symbol': 'TEST',
        'opportunity_type': 'INTRADAY_MOMENTUM',
        'quality_score': 85.0,  # High quality to pass filters
        'strategy_type': 'daily_plays',
        'strategy_targets': ['DAILY_PLAYS'],
        'catalyst_type': 'FDA',  # Strong catalyst
        'catalyst_strength': 9.0,
        'current_price': 6.20,
        'gap_percentage': 12.5,  # Good gap
        'volume_ratio': 4.5,  # Strong volume
        'trading_recommendation': 'BUY',
        'scan_timestamp': datetime.now().isoformat(),
        'bars_history': bars,

        # Scanner enrichments
        'atr_percent': 4.5,
        'ods_data': {
            'day_type': 'TREND_DRIVE_BULLISH',
            'classification': 'STRONG_BULLISH',
            'strength': 9.0,
            'direction': 'BULLISH',
            'upside_move_pct': 8.0,
            'downside_move_pct': -0.5,
            'range_pct': 8.5,
            'volume_ratio': 4.5
        },
        'intraday_structure': {
            'current_phase': 'CONTINUATION',
            'continuation_type': 'PULLBACK_TO_VWAP',
            'liquidity_sweep_detected': True,
            'sweep_direction': 'BULLISH_RECLAIM',
            'midday_structure': None
        },
    }


def create_enriched_opportunity_for_orb() -> Dict[str, Any]:
    """Create opportunity that will pass ORB filters"""
    from datetime import datetime

    # Create ORB bars (9:30-10:00) + breakout bars
    bars = []
    base_time = datetime.now().replace(hour=9, minute=30, second=0)

    # ORB period: 9:30-10:00
    for i in range(30):
        bars.append(Mock(
            timestamp=base_time + timedelta(minutes=i),
            open=5.0,
            high=5.20,
            low=4.90,
            close=5.10,
            volume=150000
        ))

    # Breakout bars: 10:00-10:05
    for i in range(5):
        bars.append(Mock(
            timestamp=base_time + timedelta(minutes=30 + i),
            open=5.25,
            high=5.35,
            low=5.20,
            close=5.32,
            volume=200000  # Strong volume
        ))

    return {
        'symbol': 'TEST',
        'opportunity_type': 'INTRADAY_MOMENTUM',
        'quality_score': 80.0,
        'strategy_type': 'orb',
        'strategy_targets': ['ORB'],
        'catalyst_type': 'TECHNICAL',
        'catalyst_strength': 7.0,
        'current_price': 5.32,  # Above ORB high
        'gap_percentage': 5.0,
        'volume_ratio': 2.5,
        'trading_recommendation': 'BUY',
        'scan_timestamp': datetime.now().isoformat(),
        'bars_history': bars,

        # Scanner enrichments
        'atr_percent': 3.8,
        'ods_data': {
            'day_type': 'TREND_DRIVE_BULLISH',
            'classification': 'MODERATE_BULLISH',
            'strength': 7.0,
            'direction': 'BULLISH',
            'upside_move_pct': 5.0,
            'downside_move_pct': -1.0,
            'range_pct': 6.0,
            'volume_ratio': 2.5
        },
        'intraday_structure': {
            'current_phase': 'OPENING_DRIVE',
            'continuation_type': 'PENDING',
            'liquidity_sweep_detected': False,
            'sweep_direction': 'NONE',
            'midday_structure': None
        },
        'orb_data': {
            'orb_high': 5.20,
            'orb_low': 4.90,
            'orb_range_pct': 6.1,
            'orb_bar_count': 30,
            'current_vs_orb': 'ABOVE_HIGH',
            'orb_avg_volume': 150000
        }
    }


async def test_daily_plays_uses_scanner_data():
    """Test that Daily Plays Worker uses scanner-provided ODS and Structure data"""
    print("=" * 80)
    print("TEST: Daily Plays Worker - Scanner Data Usage")
    print("=" * 80)
    print()

    # Setup logging capture
    import logging
    from io import StringIO

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger("Worker.daily_plays")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Import worker
    from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic

    # Mock dependencies
    mock_execution_engine = Mock()
    mock_risk_manager = Mock()
    mock_risk_manager.can_take_new_position = Mock(return_value=True)

    # Create worker
    worker = DailyPlaysWorkerLogic(
        execution_engine=mock_execution_engine,
        risk_manager=mock_risk_manager
    )

    # Create opportunity
    opportunity = create_enriched_opportunity_for_daily_plays()

    # Mock current time to be during trading hours
    mock_time = datetime.now().replace(hour=10, minute=30)  # 10:30 AM ET

    print("Testing should_enter() with scanner-enriched opportunity...")
    print(f"  Symbol: {opportunity['symbol']}")
    print(f"  Quality: {opportunity['quality_score']}")
    print(f"  Has ODS data: {opportunity.get('ods_data') is not None}")
    print(f"  Has Structure data: {opportunity.get('intraday_structure') is not None}")
    print()

    # Patch datetime to simulate trading hours
    with patch('strategies.workers.daily_plays_worker_logic.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        try:
            result = await worker.should_enter(opportunity)
            print(f"  should_enter() result: {result}")
        except Exception as e:
            print(f"  ❌ should_enter() failed: {e}")
            import traceback
            traceback.print_exc()

    # Check logs for scanner data usage
    log_output = log_stream.getvalue()

    print()
    print("Checking logs for scanner data usage indicators...")
    print()

    uses_ods_from_scanner = "Using ODS data from scanner (efficient)" in log_output
    calculates_ods_locally = "Calculating ODS locally" in log_output

    uses_structure_from_scanner = "Using Intraday Structure data from scanner (efficient)" in log_output
    calculates_structure_locally = "Calculating Intraday Structure locally" in log_output

    # Results
    print("Results:")
    print("-" * 80)

    if uses_ods_from_scanner:
        print("  ✅ PASS: Worker uses ODS data from scanner (efficient)")
    elif calculates_ods_locally:
        print("  ❌ FAIL: Worker calculates ODS locally (scanner data not used)")
    else:
        print("  ⚠️  UNKNOWN: No ODS calculation detected in logs")

    if uses_structure_from_scanner:
        print("  ✅ PASS: Worker uses Intraday Structure from scanner (efficient)")
    elif calculates_structure_locally:
        print("  ❌ FAIL: Worker calculates Structure locally (scanner data not used)")
    else:
        print("  ⚠️  UNKNOWN: No Structure calculation detected in logs")

    print()
    print("=" * 80)

    return uses_ods_from_scanner and uses_structure_from_scanner


async def test_orb_uses_scanner_data():
    """Test that ORB Worker uses scanner-provided ORB data"""
    print("=" * 80)
    print("TEST: ORB Worker - Scanner Data Usage")
    print("=" * 80)
    print()

    # Setup logging capture
    import logging
    from io import StringIO

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger("Worker.orb_breakout")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Import worker
    from strategies.workers.orb_worker_logic import ORBWorkerLogic

    # Mock dependencies
    mock_execution_engine = Mock()
    mock_risk_manager = Mock()
    mock_risk_manager.can_take_new_position = Mock(return_value=True)

    # Create worker
    worker = ORBWorkerLogic(
        execution_engine=mock_execution_engine,
        risk_manager=mock_risk_manager
    )

    # Create opportunity
    opportunity = create_enriched_opportunity_for_orb()

    # Mock current time to be during ORB entry window (10:05 AM)
    mock_time = datetime.now().replace(hour=10, minute=5)

    print("Testing should_enter() with scanner-enriched opportunity...")
    print(f"  Symbol: {opportunity['symbol']}")
    print(f"  Quality: {opportunity['quality_score']}")
    print(f"  Has ORB data: {opportunity.get('orb_data') is not None}")
    print()

    # Patch datetime to simulate ORB entry window
    with patch('strategies.workers.orb_worker_logic.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        try:
            result = await worker.should_enter(opportunity)
            print(f"  should_enter() result: {result}")
        except Exception as e:
            print(f"  ❌ should_enter() failed: {e}")
            import traceback
            traceback.print_exc()

    # Check logs for scanner data usage
    log_output = log_stream.getvalue()

    print()
    print("Checking logs for scanner data usage indicators...")
    print()

    uses_orb_from_scanner = "Using ORB data from scanner (efficient)" in log_output
    calculates_orb_locally = "Calculating ORB locally" in log_output

    # Results
    print("Results:")
    print("-" * 80)

    if uses_orb_from_scanner:
        print("  ✅ PASS: Worker uses ORB data from scanner (efficient)")
    elif calculates_orb_locally:
        print("  ❌ FAIL: Worker calculates ORB locally (scanner data not used)")
    else:
        print("  ⚠️  UNKNOWN: No ORB calculation detected in logs")

    print()
    print("=" * 80)

    return uses_orb_from_scanner


async def main():
    """Main test runner"""
    print("\n" + "=" * 80)
    print("WORKERS SCANNER DATA USAGE - TARGETED TEST")
    print("=" * 80)
    print()

    # Test Daily Plays
    daily_plays_pass = await test_daily_plays_uses_scanner_data()

    print("\n")

    # Test ORB
    orb_pass = await test_orb_uses_scanner_data()

    # Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()

    if daily_plays_pass:
        print("✅ Daily Plays Worker: Uses scanner data correctly")
    else:
        print("❌ Daily Plays Worker: Does NOT use scanner data")

    if orb_pass:
        print("✅ ORB Worker: Uses scanner data correctly")
    else:
        print("❌ ORB Worker: Does NOT use scanner data")

    print()

    if daily_plays_pass and orb_pass:
        print("🎉 ALL TESTS PASSED - Workers use scanner data efficiently!")
        print("=" * 80)
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Review workers implementation")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
