#!/usr/bin/env python3
"""
Test Workers Real Execution - Hybrid Integration Test

Tests REAL workers with mock opportunities to verify:
1. Workers execute correctly with scanner-enriched data
2. Workers USE scanner data instead of recalculating (check logs)
3. Adaptive risk sizing works correctly
4. All workers are compatible with enhanced opportunity format

This is a CRITICAL test before paper trading.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, List
from io import StringIO

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class LogCapture(logging.Handler):
    """Custom logging handler to capture log messages for testing"""
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(self.format(record))

    def has_message(self, substring: str) -> bool:
        """Check if any log message contains the substring"""
        return any(substring in msg for msg in self.messages)

    def clear(self):
        """Clear captured messages"""
        self.messages = []


class MockBar:
    """Mock bar for testing"""
    def __init__(self, timestamp, open_price, high, low, close, volume):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


def create_mock_bars(symbol: str = "TEST", num_bars: int = 60) -> List[MockBar]:
    """Create realistic mock bars for testing"""
    bars = []
    base_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
    base_price = 5.00

    for i in range(num_bars):
        bar_time = base_time + timedelta(minutes=i)

        # Simulate uptrend with volatility
        trend = i * 0.03  # Slow uptrend
        volatility = 0.15

        open_price = base_price + trend
        high = open_price + volatility
        low = open_price - (volatility * 0.5)
        close = open_price + (volatility * 0.3)
        volume = 100000 + (i * 2000)

        bars.append(MockBar(bar_time, open_price, high, low, close, volume))

    return bars


def create_enriched_opportunity(
    symbol: str = "TEST",
    strategy_type: str = "daily_plays",
    with_scanner_data: bool = True
) -> Dict[str, Any]:
    """
    Create a realistic enriched opportunity for testing

    Args:
        symbol: Stock symbol
        strategy_type: Strategy type (daily_plays, orb, macdv, vcp, etc.)
        with_scanner_data: Include scanner enrichments (ODS, Structure, ATR, ORB)

    Returns:
        Mock opportunity dict
    """
    bars = create_mock_bars(symbol, num_bars=60)
    current_price = 5.25

    opportunity = {
        # Core data
        'symbol': symbol,
        'opportunity_type': 'INTRADAY_MOMENTUM',
        'quality_score': 75.0,
        'strategy_type': strategy_type,
        'strategy_targets': ['DAILY_PLAYS'] if strategy_type == 'daily_plays' else ['ORB'],
        'catalyst_type': 'TECHNICAL',
        'catalyst_strength': 7.5,
        'current_price': current_price,
        'gap_percentage': 8.5,
        'volume_ratio': 3.2,
        'trading_recommendation': 'BUY',
        'scan_timestamp': datetime.now().isoformat(),
        'ibkr_rank': 15,
        'news_count': 2,
        'sentiment_score': 0.7,

        # Bars history
        'bars_history': bars,

        # Market data
        'market_cap': 50000000,  # $50M
        'float_size': 10000000,  # 10M shares
        'avg_volume': 500000,

        # Risk management
        'suggested_stop_loss': 4.95,
        'suggested_take_profit': 5.75,
        'suggested_position_size': 400,
        'risk_reward_ratio': 1.67,
    }

    # Add scanner enrichments if requested
    if with_scanner_data:
        opportunity.update({
            # ATR for adaptive risk sizing
            'atr_percent': 4.5,

            # ODS data
            'ods_data': {
                'day_type': 'TREND_DRIVE_BULLISH',
                'classification': 'STRONG_BULLISH',
                'strength': 8.5,
                'direction': 'BULLISH',
                'upside_move_pct': 6.0,
                'downside_move_pct': -1.0,
                'range_pct': 7.0,
                'volume_ratio': 2.5
            },

            # Intraday structure
            'intraday_structure': {
                'current_phase': 'CONTINUATION',
                'continuation_type': 'PULLBACK_TO_VWAP',
                'liquidity_sweep_detected': True,
                'sweep_direction': 'BULLISH_RECLAIM',
                'midday_structure': None
            },

            # ORB data
            'orb_data': {
                'orb_high': 5.30,
                'orb_low': 4.95,
                'orb_range_pct': 3.2,
                'orb_bar_count': 30,
                'current_vs_orb': 'ABOVE_HIGH',
                'orb_avg_volume': 150000
            }
        })

    return opportunity


class WorkerTestHarness:
    """Test harness for testing real workers"""

    def __init__(self):
        self.log_capture = LogCapture()
        self.test_results = {}

        # Setup logging to capture worker logs
        self.setup_logging()

    def setup_logging(self):
        """Setup logging to capture worker messages"""
        # Add our custom handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_capture)
        root_logger.setLevel(logging.DEBUG)

    async def test_worker(
        self,
        worker_name: str,
        worker_class,
        opportunity: Dict[str, Any],
        expect_scanner_data_usage: bool = True
    ) -> Dict[str, Any]:
        """
        Test a single worker with real execution

        Args:
            worker_name: Name of the worker
            worker_class: Worker class to instantiate
            opportunity: Opportunity dict to test with
            expect_scanner_data_usage: Whether to expect scanner data usage

        Returns:
            Test result dict
        """
        print(f"\n{'='*80}")
        print(f"Testing Worker: {worker_name}")
        print(f"{'='*80}")

        result = {
            'worker_name': worker_name,
            'initialization': False,
            'should_enter_executed': False,
            'should_enter_result': None,
            'uses_scanner_data': False,
            'adaptive_risk_calculated': False,
            'adaptive_risk_value': None,
            'errors': []
        }

        try:
            # Clear log capture
            self.log_capture.clear()

            # Mock ExecutionEngine and RiskManager
            from unittest.mock import Mock, AsyncMock

            mock_execution_engine = Mock()
            mock_risk_manager = Mock()
            mock_risk_manager.can_take_new_position = Mock(return_value=True)
            mock_risk_manager.validate_position_size = Mock(return_value=True)

            # Initialize worker
            print(f"   Initializing {worker_name}...")
            worker = worker_class(
                execution_engine=mock_execution_engine,
                risk_manager=mock_risk_manager
            )
            result['initialization'] = True
            print(f"   ✅ Worker initialized")

            # Execute should_enter
            print(f"   Executing should_enter()...")
            try:
                should_enter_result = await worker.should_enter(opportunity)
                result['should_enter_executed'] = True
                result['should_enter_result'] = should_enter_result

                if should_enter_result:
                    print(f"   ✅ should_enter() returned True (signal detected)")
                else:
                    print(f"   ⚪ should_enter() returned False (no signal)")
            except Exception as e:
                print(f"   ❌ should_enter() failed: {e}")
                result['errors'].append(f"should_enter failed: {e}")

            # Check if worker used scanner data
            if expect_scanner_data_usage:
                print(f"   Checking scanner data usage...")

                # Check logs for scanner data usage indicators
                uses_ods_from_scanner = self.log_capture.has_message("Using ODS data from scanner")
                uses_structure_from_scanner = self.log_capture.has_message("Using Intraday Structure data from scanner")
                uses_orb_from_scanner = self.log_capture.has_message("Using ORB data from scanner")

                if uses_ods_from_scanner or uses_structure_from_scanner or uses_orb_from_scanner:
                    result['uses_scanner_data'] = True
                    print(f"   ✅ Worker uses scanner data:")
                    if uses_ods_from_scanner:
                        print(f"      ✓ ODS data from scanner")
                    if uses_structure_from_scanner:
                        print(f"      ✓ Intraday Structure from scanner")
                    if uses_orb_from_scanner:
                        print(f"      ✓ ORB data from scanner")
                else:
                    # Some workers might not use pattern data (e.g., MACDV, VCP)
                    print(f"   ℹ️  Worker doesn't use scanner pattern data (may be expected)")

            # Test adaptive risk sizing
            print(f"   Testing adaptive risk sizing...")
            try:
                # Calculate adaptive risk - pass None for ods_data and intraday_structure
                # The method will extract from opportunity dict if available
                adaptive_risk = worker.calculate_adaptive_risk(
                    opportunity=opportunity,
                    ods_data=None,
                    intraday_structure=None
                )

                result['adaptive_risk_calculated'] = True
                result['adaptive_risk_value'] = adaptive_risk

                risk_pct = adaptive_risk * 100
                base_risk_pct = 1.2
                improvement = ((adaptive_risk / 0.012) - 1) * 100

                print(f"   ✅ Adaptive risk: {risk_pct:.2f}% (base: {base_risk_pct:.2f}%, {improvement:+.1f}%)")

            except Exception as e:
                print(f"   ⚠️  Adaptive risk calculation failed: {e}")
                result['errors'].append(f"Adaptive risk failed: {e}")

        except Exception as e:
            print(f"   ❌ Worker test failed: {e}")
            result['errors'].append(f"Worker test failed: {e}")
            import traceback
            traceback.print_exc()

        return result

    async def run_all_worker_tests(self):
        """Run tests for all workers"""
        print("=" * 80)
        print("WORKERS REAL EXECUTION TEST - HYBRID INTEGRATION")
        print("=" * 80)
        print()

        # Define workers to test (ALL workers with enabled=true in config.ini)
        workers_to_test = [
            {
                'name': 'Daily Plays',
                'module': 'strategies.workers.daily_plays_worker_logic',
                'class': 'DailyPlaysWorkerLogic',
                'strategy_type': 'daily_plays',
                'expect_scanner_data': True
            },
            {
                'name': 'ORB',
                'module': 'strategies.workers.orb_worker_logic',
                'class': 'ORBWorkerLogic',
                'strategy_type': 'orb',
                'expect_scanner_data': True
            },
            {
                'name': 'MACDV',
                'module': 'strategies.workers.macdv_worker_logic',
                'class': 'MacdvWorkerLogic',
                'strategy_type': 'macdv',
                'expect_scanner_data': False  # MACDV uses technical indicators, not ODS/Structure
            },
            {
                'name': 'Momentum Breakout',
                'module': 'strategies.workers.momentum_breakout_worker_logic',
                'class': 'MomentumBreakoutWorkerLogic',
                'strategy_type': 'momentum_breakout',
                'expect_scanner_data': False  # Technical pattern, not ODS/Structure
            },
            {
                'name': 'VCP Smallcap',
                'module': 'strategies.workers.vcp_smallcap_worker_logic',
                'class': 'VCPSmallcapWorkerLogic',
                'strategy_type': 'vcp',
                'expect_scanner_data': False  # VCP is chart pattern, not ODS/Structure
            },
        ]

        results = []

        for worker_config in workers_to_test:
            try:
                # Import worker class
                module = __import__(worker_config['module'], fromlist=[worker_config['class']])
                worker_class = getattr(module, worker_config['class'])

                # Create opportunity for this worker
                opportunity = create_enriched_opportunity(
                    symbol=f"{worker_config['name'].upper()}_TEST",
                    strategy_type=worker_config['strategy_type'],
                    with_scanner_data=True
                )

                # Test worker
                result = await self.test_worker(
                    worker_name=worker_config['name'],
                    worker_class=worker_class,
                    opportunity=opportunity,
                    expect_scanner_data_usage=worker_config['expect_scanner_data']
                )

                results.append(result)
                self.test_results[worker_config['name']] = result

            except Exception as e:
                print(f"\n❌ Failed to test {worker_config['name']}: {e}")
                results.append({
                    'worker_name': worker_config['name'],
                    'initialization': False,
                    'should_enter_executed': False,
                    'should_enter_result': None,
                    'uses_scanner_data': False,
                    'adaptive_risk_calculated': False,
                    'adaptive_risk_value': None,
                    'errors': [f"Import/setup failed: {e}"]
                })

        # Print summary
        self.print_summary(results)

        return results

    def print_summary(self, results: List[Dict[str, Any]]):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print()

        total = len(results)
        initialized = sum(1 for r in results if r.get('initialization', False))
        should_enter_ok = sum(1 for r in results if r.get('should_enter_executed', False))
        uses_scanner = sum(1 for r in results if r.get('uses_scanner_data', False))
        adaptive_risk_ok = sum(1 for r in results if r.get('adaptive_risk_calculated', False))
        has_errors = sum(1 for r in results if r.get('errors', []))

        print(f"Workers Tested: {total}")
        print(f"✅ Initialized: {initialized}/{total}")
        print(f"✅ should_enter() executed: {should_enter_ok}/{total}")
        print(f"✅ Uses scanner data: {uses_scanner}/{total} (where expected)")
        print(f"✅ Adaptive risk calculated: {adaptive_risk_ok}/{total}")
        print(f"❌ Workers with errors: {has_errors}/{total}")
        print()

        # Detail by worker
        print("Worker Details:")
        print("-" * 80)
        for result in results:
            status = "✅" if not result['errors'] else "❌"
            print(f"{status} {result['worker_name']}")

            if result['should_enter_executed']:
                signal = "SIGNAL" if result['should_enter_result'] else "NO SIGNAL"
                print(f"   should_enter: {signal}")

            if result['uses_scanner_data']:
                print(f"   ✓ Uses scanner data")

            if result['adaptive_risk_calculated']:
                risk_pct = result['adaptive_risk_value'] * 100
                print(f"   ✓ Adaptive risk: {risk_pct:.2f}%")

            if result['errors']:
                for error in result['errors']:
                    print(f"   ❌ {error}")

        print()
        print("=" * 80)

        if has_errors == 0:
            print("🎉 ALL WORKERS TESTED SUCCESSFULLY!")
        else:
            print(f"⚠️  {has_errors} workers had errors - review above")

        print("=" * 80)


async def main():
    """Main test runner"""
    harness = WorkerTestHarness()
    results = await harness.run_all_worker_tests()

    # Exit with error code if any worker failed
    if any(r['errors'] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
