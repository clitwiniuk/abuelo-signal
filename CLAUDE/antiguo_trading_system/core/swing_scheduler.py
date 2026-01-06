"""
Swing Trading Scheduler
Manages EOD scanning and market open execution for swing trading

Schedule:
- EOD Scan: 15:40 ET daily (21:40 España) - Detect consolidation patterns
- Market Open: 9:30 ET daily - Execute BREAKOUT mode entries
- Intraday Monitor: Every 5 minutes during regular hours - Execute PULLBACK mode entries
- Position Check: Every 30 minutes - Monitor exit conditions
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional
import pytz


class SwingScheduler:
    """
    Scheduler for swing trading operations

    Daily workflow:
    1. 15:40 ET - Run EOD scanner for consolidation patterns
    2. Save top 2 picks to database
    3. 9:30 ET next day - Check for BREAKOUT mode entries
    4. 9:30-16:00 ET - Monitor for PULLBACK mode entries (every 5 min)
    5. All day - Monitor positions for exits (every 30 min)
    """

    def __init__(self, scanner, worker, logger: Optional[logging.Logger] = None):
        """
        Initialize swing scheduler

        Args:
            scanner: SwingConsolidationScanner instance
            worker: ConsolidationBreakoutWorker instance
            logger: Optional logger
        """
        self.scanner = scanner
        self.worker = worker
        self.logger = logger or logging.getLogger("SwingScheduler")

        # Timezone
        self.eastern = pytz.timezone('US/Eastern')

        # Schedule times
        self.eod_scan_time = time(15, 40)       # EOD scan at 15:40 ET (21:40 España)
        self.market_open = time(9, 30)          # Market open 9:30 ET
        self.market_close = time(16, 0)         # Market close 16:00 ET

        # Tracking
        self.last_eod_scan_date = None
        self.last_market_open_check = None
        self.swing_picks = []                   # Current swing picks from EOD scan
        self.active_positions = {}              # {symbol: position_data}

        # Running state
        self.running = False
        self.tasks = []

        # Database path for restoration
        self.db_path = "trading_data.db"

        self.logger.info("📅 Swing Scheduler initialized")

        # Restore active swing positions from database
        self._restore_active_positions()

    def _restore_active_positions(self):
        """
        Restore active swing positions from database after restart

        Critical for:
        - Continuing to monitor positions
        - Re-registering with UnifiedPositionManager
        - Preventing duplicate entries
        """
        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all ACTIVE swing trades
            cursor.execute("""
                SELECT
                    symbol,
                    entry_price,
                    quantity,
                    entry_date,
                    support_level,
                    resistance_level,
                    pattern_type,
                    breakout_score,
                    created_at
                FROM swing_trades
                WHERE status = 'ACTIVE'
                ORDER BY entry_date DESC
            """)

            rows = cursor.fetchall()
            conn.close()

            if not rows or len(rows) == 0:
                self.logger.debug("No active swing positions to restore")
                return

            self.logger.info(f"🔄 Restoring {len(rows)} swing position(s)...")

            for row in rows:
                symbol = row['symbol']

                # Restore to active_positions tracking
                self.active_positions[symbol] = {
                    'symbol': symbol,
                    'entry_price': row['entry_price'],
                    'quantity': row['quantity'],
                    'entry_date': row['entry_date'],
                    'entry_time': row['created_at'],  # Use created_at as entry_time
                    'support': row['support_level'],
                    'resistance': row['resistance_level'],
                    'pattern_type': row['pattern_type'],
                    'breakout_score': row['breakout_score'],
                    'strategy_type': 'swing'  # Mark as swing for UnifiedPositionManager
                }

                self.logger.info(
                    f"   ✓ {symbol}: ${row['entry_price']:.2f} x {row['quantity']} "
                    f"({row['pattern_type']}, entry: {row['entry_date']})"
                )

            # Re-register with UnifiedPositionManager (async operation)
            self._reregister_with_unified_manager()

            self.logger.info(
                f"✅ Restored {len(self.active_positions)} swing position(s) - "
                f"monitoring resumed"
            )

        except Exception as e:
            self.logger.error(f"❌ Error restoring swing positions: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def _reregister_with_unified_manager(self):
        """
        Re-register swing positions with UnifiedPositionManager

        This is critical to prevent:
        - Day trading workers from entering same symbol
        - Duplicate position detection
        - Capital allocation tracking
        """
        try:
            # Import here to avoid circular imports
            from core.service_locator import get_service_locator
            import asyncio

            # Get UnifiedPositionManager synchronously
            service_locator = get_service_locator()

            # Create async function to get manager
            async def get_manager():
                return await service_locator.get_or_create_unified_position_manager()

            # Run in event loop if available, otherwise create new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, schedule as task
                    asyncio.create_task(self._async_reregister())
                else:
                    # If no loop running, run directly
                    unified_manager = loop.run_until_complete(get_manager())
                    self._do_reregister(unified_manager)
            except RuntimeError:
                # No event loop exists, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                unified_manager = loop.run_until_complete(get_manager())
                self._do_reregister(unified_manager)

        except Exception as e:
            self.logger.warning(
                f"⚠️ Could not re-register with UnifiedPositionManager: {e}"
            )
            self.logger.warning(
                "   Positions restored but duplicate prevention may not work until "
                "UnifiedPositionManager is initialized"
            )

    async def _async_reregister(self):
        """Async version of reregistration for when event loop is running"""
        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()
        self._do_reregister(unified_manager)

    def _do_reregister(self, unified_manager):
        """Perform the actual reregistration"""
        if not unified_manager:
            self.logger.warning("⚠️ UnifiedPositionManager not available")
            return

        reregistered = 0
        for symbol, pos in self.active_positions.items():
            # Check if already registered (in case of double-initialization)
            if unified_manager.is_symbol_blocked(symbol):
                self.logger.debug(f"   {symbol}: Already registered, skipping")
                continue

            # Calculate position value
            position_value = pos['entry_price'] * pos['quantity']

            # Register with unified manager
            success = unified_manager.register_position(
                symbol=symbol,
                strategy_type='swing',
                position_data=pos
            )

            if success:
                reregistered += 1
                self.logger.info(
                    f"   💼 Re-registered {symbol} with UnifiedPositionManager "
                    f"(${position_value:.2f})"
                )

        if reregistered > 0:
            self.logger.info(
                f"✅ Re-registered {reregistered} position(s) with UnifiedPositionManager"
            )

    async def start(self):
        """Start all scheduled tasks"""
        if self.running:
            self.logger.warning("⚠️ Scheduler already running")
            return

        self.running = True
        self.logger.info("▶️ Starting swing scheduler...")

        # Start all scheduled tasks
        self.tasks = [
            asyncio.create_task(self._eod_scan_loop()),
            asyncio.create_task(self._market_open_loop()),
            asyncio.create_task(self._intraday_monitor_loop()),
            asyncio.create_task(self._position_monitor_loop())
        ]

        self.logger.info("✅ Swing scheduler started - all tasks running")

    async def stop(self):
        """Stop all scheduled tasks"""
        if not self.running:
            return

        self.logger.info("⏹️ Stopping swing scheduler...")
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)

        self.tasks = []
        self.logger.info("✅ Swing scheduler stopped")

    async def _eod_scan_loop(self):
        """
        EOD scanner loop - Runs daily at 15:40 ET

        Scans for consolidation patterns and saves top 2 picks
        """
        while self.running:
            try:
                now_et = datetime.now(self.eastern)
                current_date = now_et.date()
                current_time = now_et.time()

                # DEBUG: Log current time check
                self.logger.debug(f"🔍 SwingScheduler EOD check - Current ET: {now_et}, Time: {current_time}, Scan time: {self.eod_scan_time}")
                self.logger.debug(f"   Last scan date: {self.last_eod_scan_date}, Current date: {current_date}")

                # Check if we should run EOD scan
                time_condition = current_time >= self.eod_scan_time
                date_condition = (self.last_eod_scan_date is None or self.last_eod_scan_date < current_date)
                should_run = time_condition and date_condition

                self.logger.debug(f"   Time condition (>= {self.eod_scan_time}): {time_condition}")
                self.logger.debug(f"   Date condition (not scanned today): {date_condition}")
                self.logger.debug(f"   Should run scan: {should_run}")

                if should_run:
                    self.logger.info(f"🔍 Starting EOD consolidation scan at {now_et}")

                    # Run scanner
                    swing_picks = await self.scanner.scan_for_consolidations()

                    if swing_picks and len(swing_picks) > 0:
                        self.swing_picks = swing_picks
                        self.logger.info(
                            f"✅ EOD scan complete - {len(swing_picks)} picks identified: "
                            f"{', '.join(p['symbol'] for p in swing_picks)}"
                        )

                        # Log details
                        for pick in swing_picks:
                            self.logger.info(
                                f"   📊 {pick['symbol']}: "
                                f"{pick['pattern_type']}, "
                                f"score {pick['breakout_score']:.0f}, "
                                f"mode: {pick['entry_mode']}"
                            )
                    else:
                        self.logger.info("📭 EOD scan complete - no picks found")

                    self.last_eod_scan_date = current_date

                # Sleep for 1 minute before checking again
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in EOD scan loop: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(60)

    async def _market_open_loop(self):
        """
        Market open loop - Runs daily at 9:30 ET

        Executes BREAKOUT mode entries for swing picks
        """
        while self.running:
            try:
                now_et = datetime.now(self.eastern)
                current_date = now_et.date()
                current_time = now_et.time()

                # Check if we should check for entries (9:30-9:45 ET)
                entry_window_end = time(9, 45)
                should_check = (
                    self.market_open <= current_time <= entry_window_end and
                    (self.last_market_open_check is None or self.last_market_open_check < current_date)
                )

                if should_check and len(self.swing_picks) > 0:
                    self.logger.info(f"🔔 Market open - checking BREAKOUT entries at {now_et}")

                    # Check each swing pick for BREAKOUT mode entry
                    for pick in self.swing_picks:
                        symbol = pick.get('symbol', 'UNKNOWN')
                        entry_mode = pick.get('entry_mode', 'BREAKOUT')

                        # Only process BREAKOUT mode at market open
                        if entry_mode != 'BREAKOUT':
                            self.logger.debug(f"⏭️ {symbol}: Skipping (mode: {entry_mode})")
                            continue

                        # Check if already in position
                        if symbol in self.active_positions:
                            self.logger.debug(f"⏭️ {symbol}: Already in position")
                            continue

                        # Try to enter
                        self.logger.info(f"🎯 {symbol}: Attempting BREAKOUT entry...")
                        success = await self.worker.process_swing_pick(pick)

                        if success:
                            self.active_positions[symbol] = pick
                            self.logger.info(f"✅ {symbol}: BREAKOUT entry executed")
                        else:
                            self.logger.debug(f"⏳ {symbol}: Entry criteria not met")

                    self.last_market_open_check = current_date

                # Sleep for 1 minute before checking again
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in market open loop: {e}")
                await asyncio.sleep(60)

    async def _intraday_monitor_loop(self):
        """
        Intraday monitor loop - Runs every 5 minutes during market hours

        Executes PULLBACK mode entries for swing picks
        """
        while self.running:
            try:
                now_et = datetime.now(self.eastern)
                current_time = now_et.time()

                # Check if during market hours (9:30-16:00 ET)
                is_market_hours = self.market_open <= current_time <= self.market_close

                if is_market_hours and len(self.swing_picks) > 0:
                    self.logger.debug(f"🔍 Intraday monitor - checking PULLBACK entries")

                    # Check each swing pick for PULLBACK mode entry
                    for pick in self.swing_picks:
                        symbol = pick.get('symbol', 'UNKNOWN')
                        entry_mode = pick.get('entry_mode', 'BREAKOUT')

                        # Only process PULLBACK mode during intraday
                        if entry_mode != 'PULLBACK':
                            continue

                        # Check if already in position
                        if symbol in self.active_positions:
                            continue

                        # Try to enter
                        self.logger.debug(f"🎯 {symbol}: Checking PULLBACK entry...")
                        success = await self.worker.process_swing_pick(pick)

                        if success:
                            self.active_positions[symbol] = pick
                            self.logger.info(f"✅ {symbol}: PULLBACK entry executed")

                # Sleep for 5 minutes before checking again
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in intraday monitor loop: {e}")
                await asyncio.sleep(300)

    async def _position_monitor_loop(self):
        """
        Position monitor loop - Runs every 30 minutes

        Monitors swing positions for exit conditions
        """
        while self.running:
            try:
                now_et = datetime.now(self.eastern)
                current_time = now_et.time()

                # Check if during market hours
                is_market_hours = self.market_open <= current_time <= self.market_close

                if is_market_hours and len(self.active_positions) > 0:
                    self.logger.debug(f"🔍 Position monitor - checking {len(self.active_positions)} positions")

                    # Check each active position
                    symbols_to_remove = []

                    for symbol, position in self.active_positions.items():
                        # Check exit conditions
                        exited = await self.worker.check_position_exit(symbol, position)

                        if exited:
                            self.logger.info(f"🔚 {symbol}: Position exited")
                            symbols_to_remove.append(symbol)

                    # Remove exited positions
                    for symbol in symbols_to_remove:
                        del self.active_positions[symbol]

                # Sleep for 30 minutes before checking again
                await asyncio.sleep(1800)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Error in position monitor loop: {e}")
                await asyncio.sleep(1800)

    def get_status(self) -> dict:
        """
        Get scheduler status

        Returns:
            Status dictionary
        """
        now_et = datetime.now(self.eastern)

        return {
            'running': self.running,
            'current_time_et': now_et.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'last_eod_scan': self.last_eod_scan_date.isoformat() if self.last_eod_scan_date else None,
            'last_market_open_check': self.last_market_open_check.isoformat() if self.last_market_open_check else None,
            'swing_picks_count': len(self.swing_picks),
            'swing_picks': [
                {
                    'symbol': p['symbol'],
                    'pattern_type': p.get('pattern_type', 'unknown'),
                    'entry_mode': p.get('entry_mode', 'unknown'),
                    'breakout_score': p.get('breakout_score', 0)
                }
                for p in self.swing_picks
            ],
            'active_positions_count': len(self.active_positions),
            'active_positions': list(self.active_positions.keys())
        }
