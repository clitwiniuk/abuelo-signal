#!/usr/bin/env python3
"""
Forward Return Tracker - Production Runner

Runs the Forward Return Tracker as a standalone service that monitors
signal_events and captures forward returns.

This should run ALONGSIDE the main trading system during paper trading.

Usage:
    # Run in production mode
    python run_forward_tracker.py

    # Run with custom check interval
    python run_forward_tracker.py --interval 30

    # Run with different database
    python run_forward_tracker.py --db /path/to/trading_data.db

Author: Trading System
Date: 2025-11-09
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

from core.forward_return_tracker import ForwardReturnTracker


class GracefulShutdown:
    """Handle graceful shutdown on SIGINT/SIGTERM"""

    def __init__(self):
        self.shutdown_requested = False

    def request_shutdown(self, signum, frame):
        """Signal handler"""
        print("\n\n⚠️  Shutdown requested...")
        self.shutdown_requested = True


async def main():
    """Main runner"""
    parser = argparse.ArgumentParser(
        description='Run Forward Return Tracker for TP/SL optimization'
    )
    parser.add_argument(
        '--db',
        default='trading_data.db',
        help='Path to trading database (default: trading_data.db)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('forward_tracker.log')
        ]
    )

    logger = logging.getLogger(__name__)

    # Verify database exists
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Please ensure trading_data.db exists or specify correct path")
        return 1

    # Print startup banner
    print()
    print("=" * 80)
    print("FORWARD RETURN TRACKER - Production Mode")
    print("=" * 80)
    print()
    print(f"Database: {db_path.absolute()}")
    print(f"Check Interval: {args.interval} seconds")
    print(f"Log Level: {args.log_level}")
    print()
    print("This tracker will:")
    print("  1. Monitor signal_events for pending forward tracking")
    print("  2. Capture prices at 5m, 15m, 60m, 240m intervals")
    print("  3. Calculate MFE/MAE for each signal")
    print("  4. Update signal_events with forward returns")
    print()
    print("Press Ctrl+C to stop gracefully")
    print("=" * 80)
    print()

    # Setup graceful shutdown
    shutdown_handler = GracefulShutdown()
    signal.signal(signal.SIGINT, shutdown_handler.request_shutdown)
    signal.signal(signal.SIGTERM, shutdown_handler.request_shutdown)

    # Initialize tracker
    tracker = ForwardReturnTracker(
        db_path=str(db_path),
        check_interval_seconds=args.interval
    )

    # Start tracker
    logger.info("Starting Forward Return Tracker...")
    tracker_task = asyncio.create_task(tracker.start())

    try:
        # Run until shutdown requested
        while not shutdown_handler.shutdown_requested:
            await asyncio.sleep(1)

            # Check if tracker task failed
            if tracker_task.done():
                exception = tracker_task.exception()
                if exception:
                    logger.error(f"Tracker task failed: {exception}")
                    break
                else:
                    logger.warning("Tracker task completed unexpectedly")
                    break

    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        import traceback
        logger.error(traceback.format_exc())

    finally:
        # Graceful shutdown
        print("\n\n🛑 Shutting down Forward Return Tracker...")
        logger.info("Stopping tracker...")

        # Stop tracker
        await tracker.stop()

        # Cancel task if still running
        if not tracker_task.done():
            tracker_task.cancel()
            try:
                await tracker_task
            except asyncio.CancelledError:
                pass

        logger.info("Tracker stopped successfully")
        print("✅ Shutdown complete")
        print()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
