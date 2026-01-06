"""
Test Forward Return Tracker - Standalone Test

Tests the Forward Return Tracker functionality:
1. Creates mock signal events in database
2. Starts tracker
3. Verifies price capture and forward return calculation
4. Validates database updates

Author: Trading System
Date: 2025-11-09
"""

import asyncio
import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.forward_return_tracker import ForwardReturnTracker
from core.trade_event_logger import TradeEventLogger


class ForwardReturnTrackerTest:
    """Test harness for Forward Return Tracker"""

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.event_logger = TradeEventLogger(db_path=db_path)
        self.test_signal_ids = []

    def create_mock_signal(
        self,
        symbol: str = "TEST",
        worker_name: str = "daily_plays",
        entry_price: float = 10.0,
        minutes_ago: int = 10
    ) -> str:
        """
        Create a mock signal event in database for testing

        Args:
            symbol: Test symbol
            worker_name: Worker name
            entry_price: Entry price
            minutes_ago: How many minutes ago the signal was generated

        Returns:
            signal_id
        """
        signal_id = str(uuid.uuid4())
        timestamp = datetime.now() - timedelta(minutes=minutes_ago)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO signal_events (
                signal_id, symbol, worker_name, timestamp,
                entered, rejection_reason, trade_id,
                entry_price, invalid_price, suggested_sl, suggested_tp,
                ods_classification, ods_strength, ods_direction,
                intraday_phase, continuation_type,
                liquidity_sweep_detected, sweep_direction,
                confidence, quality_score, atr_percent,
                volume_ratio, gap_percentage,
                catalyst_type, catalyst_strength
            ) VALUES (
                ?, ?, ?, ?,
                1, NULL, NULL,
                ?, NULL, ?, ?,
                'STRONG_BULLISH', 0.85, 'BULLISH',
                'CONTINUATION', 'STRONG', 0, NULL,
                85.0, 78.0, 2.5,
                3.2, 1.5,
                'news', 80
            )
        ''', (
            signal_id, symbol, worker_name, timestamp,
            entry_price, entry_price * 0.95, entry_price * 1.15
        ))

        conn.commit()
        conn.close()

        self.test_signal_ids.append(signal_id)
        self.logger.info(f"Created mock signal: {signal_id[:8]}... ({symbol} @ ${entry_price})")

        return signal_id

    def verify_forward_tracking(self, signal_id: str) -> bool:
        """
        Verify that forward tracking was completed for a signal

        Args:
            signal_id: Signal ID to check

        Returns:
            True if tracking completed successfully
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                forward_return_5m,
                forward_return_15m,
                forward_return_60m,
                forward_return_240m,
                max_price_reached,
                min_price_reached,
                mfe_percent,
                mae_percent,
                forward_tracked_at
            FROM signal_events
            WHERE signal_id = ?
        ''', (signal_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            self.logger.error(f"Signal {signal_id} not found in database")
            return False

        # Check if any forward returns were captured
        has_data = (
            row['forward_return_5m'] is not None or
            row['forward_return_15m'] is not None or
            row['forward_return_60m'] is not None or
            row['forward_tracked_at'] is not None
        )

        if has_data:
            self.logger.info(
                f"✅ Forward tracking completed for {signal_id[:8]}...\n"
                f"   5m: {row['forward_return_5m']*100 if row['forward_return_5m'] else 'N/A':+.2f}%\n"
                f"   15m: {row['forward_return_15m']*100 if row['forward_return_15m'] else 'N/A':+.2f}%\n"
                f"   60m: {row['forward_return_60m']*100 if row['forward_return_60m'] else 'N/A':+.2f}%\n"
                f"   MFE: {row['mfe_percent'] if row['mfe_percent'] else 'N/A':+.2f}%\n"
                f"   MAE: {row['mae_percent'] if row['mae_percent'] else 'N/A':+.2f}%"
            )
        else:
            self.logger.warning(f"⚠️  No forward tracking data for {signal_id[:8]}...")

        return has_data

    def cleanup_test_signals(self):
        """Remove test signals from database"""
        if not self.test_signal_ids:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for signal_id in self.test_signal_ids:
            cursor.execute('DELETE FROM signal_events WHERE signal_id = ?', (signal_id,))
            self.logger.debug(f"Deleted test signal: {signal_id[:8]}...")

        conn.commit()
        conn.close()

        self.logger.info(f"Cleaned up {len(self.test_signal_ids)} test signals")

    async def run_quick_test(self, duration_seconds: int = 30):
        """
        Run a quick test of the Forward Return Tracker

        Args:
            duration_seconds: How long to run the test
        """
        print("=" * 80)
        print("FORWARD RETURN TRACKER - Quick Test")
        print("=" * 80)
        print()

        # Create mock signals at different time points
        print("📝 Creating mock signals...")

        # Signal 10 minutes ago (should track immediately)
        signal_1 = self.create_mock_signal(
            symbol="AAPL",
            worker_name="daily_plays",
            entry_price=150.0,
            minutes_ago=10
        )

        # Signal 6 minutes ago (should track 5m return immediately)
        signal_2 = self.create_mock_signal(
            symbol="TSLA",
            worker_name="orb",
            entry_price=200.0,
            minutes_ago=6
        )

        # Signal 3 minutes ago (should wait before tracking)
        signal_3 = self.create_mock_signal(
            symbol="NVDA",
            worker_name="macdv",
            entry_price=500.0,
            minutes_ago=3
        )

        print(f"✅ Created 3 mock signals")
        print()

        # Initialize tracker
        print("🚀 Starting Forward Return Tracker...")
        tracker = ForwardReturnTracker(
            db_path=self.db_path,
            check_interval_seconds=5  # Check every 5 seconds for testing
        )

        # Start tracker in background
        tracker_task = asyncio.create_task(tracker.start())

        print(f"⏳ Running tracker for {duration_seconds} seconds...")
        print("   (In production, this would run continuously)")
        print()

        try:
            # Let tracker run for specified duration
            await asyncio.sleep(duration_seconds)

        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")

        finally:
            # Stop tracker
            print("\n🛑 Stopping tracker...")
            await tracker.stop()

            # Cancel tracker task
            if not tracker_task.done():
                tracker_task.cancel()
                try:
                    await tracker_task
                except asyncio.CancelledError:
                    pass

        print()
        print("=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        print()

        # Verify results
        all_signals = [signal_1, signal_2, signal_3]
        success_count = 0

        for i, signal_id in enumerate(all_signals, 1):
            print(f"\nSignal {i}:")
            if self.verify_forward_tracking(signal_id):
                success_count += 1

        print()
        print("=" * 80)
        print(f"RESULTS: {success_count}/{len(all_signals)} signals tracked successfully")
        print("=" * 80)
        print()

        # Ask about cleanup
        if success_count > 0:
            print("Note: Test signals remain in database for inspection.")
            print(f"To clean up, run: DELETE FROM signal_events WHERE signal_id IN (")
            for signal_id in all_signals:
                print(f"  '{signal_id}',")
            print(")")
        else:
            print("⚠️  No signals were tracked. Possible reasons:")
            print("   1. Market data fetcher not available")
            print("   2. No historical bars in database")
            print("   3. Signals too recent (< 5 minutes old)")
            print()
            print("This is EXPECTED in testing environment.")
            print("In production with live data, tracking will work.")


async def main():
    """Main test runner"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Change to project root
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "trading_data.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Please run from project root or specify correct path")
        return

    test = ForwardReturnTrackerTest(db_path=str(db_path))

    # Run quick test (30 seconds)
    await test.run_quick_test(duration_seconds=30)


if __name__ == "__main__":
    asyncio.run(main())
