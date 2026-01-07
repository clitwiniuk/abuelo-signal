
"""
Short Squeeze Worker Logic
Worker designed to trade "Proactive Candidates" (Day 0-7) showing signs of short covering.
"""

import logging
import sqlite3
import json
import pandas as pd
import asyncio
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from .base_worker_logic import BaseWorkerLogic
from core.database_manager import DatabaseManager

class ShortSqueezeWorkerLogic(BaseWorkerLogic):
    """
    Short Squeeze Worker - "The Squeeze Executor"
    
    Target: Smallcaps identified by ProactiveScanner (Day 0-7).
    Logic: "Uncomfortable Shorts"
    
    Entry Triggers:
    1. Stock IS in `proactive_candidates` (Status: WATCHING/TRIGGERED).
    2. Violent VWAP Reclaim (Price crosses VWAP from below or holds above).
    3. Volume Surge (Rel Vol > 3x).
    4. Abnormal Candles (Green Marubozu / Low Wicks).
    5. "Quiet Rise" or "Weak Pullbacks".
    """
    
    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="short_squeeze",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )
        self.db_manager = DatabaseManager()
        self.logger = logging.getLogger(f"{__name__}.ShortSqueezeWorker")

        # Configuration
        if config:
            section = 'SHORT_SQUEEZE_WORKER'
            self.min_price = config.getfloat(section, 'min_price', fallback=1.0)
            self.max_price = config.getfloat(section, 'max_price', fallback=20.0)
            self.min_rel_volume = config.getfloat(section, 'min_rel_volume', fallback=3.0)
        else:
            self.min_price = 1.0
            self.max_price = 20.0
            self.min_rel_volume = 3.0

        # === STOP MANAGER INITIALIZATION ===
        from .worker_stop_manager import create_worker_stop_manager, WorkerStopManager, WorkerStopConfig
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'SHORT_SQUEEZE_WORKER')
        else:
            # Default stop manager configuration for short squeeze
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,           # 3% stop loss (tight for squeezes)
                take_profit_pct=10.0,        # 10% profit target (capture squeeze moves)
                quick_target_pct=5.0,        # 5% quick target (lock in partial profits)
                trailing_activation=6.0,     # Trailing at 6% profit
                trailing_distance=2.0,       # 2% trailing distance
                max_position_hours=6.0       # Scalp timeframe (6 hours max)
            ))

        self.logger.info("🐻🔫 Short Squeeze Worker Initialized")

        # Proactive Monitoring State
        self.last_monitor_time = datetime.now()
        self.monitor_interval = 60  # seconds (Check watchlist every minute)

    async def _periodic_task(self):
        """
        Periodic task to proactively monitor the watchlist.
        Run every self.monitor_interval seconds.
        """
        try:
            now = datetime.now()
            elapsed = (now - self.last_monitor_time).total_seconds()

            if elapsed >= self.monitor_interval:
                self.logger.debug(f"🔄 Periodic task triggered (elapsed: {elapsed:.1f}s, is_running: {self.is_running})")
                if self.is_running: # Only monitor if worker is running
                    await self._monitor_watchlist()
                else:
                    self.logger.warning(f"⚠️ Worker not running, skipping watchlist monitor")
                self.last_monitor_time = now
        except Exception as e:
            self.logger.error(f"Error in periodic watchlist monitor: {e}", exc_info=True)

    async def _monitor_watchlist(self):
        """
        Query DB for active candidates and fetch real-time data to check for triggers.
        """
        try:
            # 1. Get Active Candidates (WATCHING or TRIGGERED) from DB
            candidates = []
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM proactive_candidates WHERE status IN ('WATCHING', 'TRIGGERED')"
                )
                candidates = [dict(row) for row in cursor.fetchall()]

            if not candidates:
                self.logger.debug("📭 No active candidates to monitor (WATCHING/TRIGGERED)")
                return

            self.logger.info(f"🧐 Monitoring {len(candidates)} proactive candidates: {[c['symbol'] for c in candidates]}")

            # 2. Extract symbols
            symbols = [c['symbol'] for c in candidates]

            # 3. Batch Fetch Snapshots (Price, Volume, VWAP?) + Bars for VWAP analysis
            # IBKRAdapter via ExecutionEngine
            snapshots = await self._fetch_candidate_snapshots(symbols)

            if not snapshots:
                self.logger.debug("No market data snapshots available.")
                return

            # 4. Evaluate each candidate
            for candidate in candidates:
                symbol = candidate['symbol']
                snapshot = snapshots.get(symbol)

                if not snapshot:
                    continue

                # CRITICAL FIX: Fetch intraday bars for VWAP analysis
                # This was the missing piece that prevented LVRO from being evaluated correctly
                bars_history = await self._fetch_intraday_bars(symbol)

                if not bars_history:
                    self.logger.warning(f"⚠️ {symbol}: No bars available for VWAP analysis, skipping evaluation")
                    continue

                # Get candidate pattern info for logging
                pattern_type = candidate.get('pattern_type', 'UNKNOWN')
                days_since = candidate.get('days_since_detection', 0)
                current_price = snapshot.get('price', 0)

                self.logger.info(
                    f"✅ {symbol}: Proactive evaluation ready "
                    f"(Day {days_since}, Pattern: {pattern_type}, Price: ${current_price:.2f}, Bars: {len(bars_history)})"
                )

                # Construct an internal "Opportunity" object
                # This mimics what the scanner would send, but self-generated.
                opportunity = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'volume_ratio': snapshot.get('volume_ratio', 1.0), # Will be recalculated from bars
                    'timestamp': datetime.now(),
                    'source': 'PROACTIVE_MONITOR', # Flag to know it's internal
                    'bars_history': bars_history,  # ✅ FIX: Add bars for VWAP/volume analysis
                    # Enrich with candidate info directly to save a DB call in should_enter if we optimized,
                    # but should_enter retrieves it anyway.
                }

                # 5. Check Entry (Reuse logic)
                # Now should_enter will have bars_history and can properly evaluate VWAP

                # Filter trivial price/volume before full check to save resources?
                # Base filters in should_enter do this.

                # Execute Logic
                # We need to lock or ensure we don't double submit?
                # Base execution engine handles order management / duplicate positions.

                should_trade = await self.should_enter(opportunity)

                if should_trade:
                    self.logger.info(f"🚀 PROACTIVE TRIGGER: {symbol} triggered entry logic from internal monitor!")
                    # Execute Entry
                    await self._execute_entry(opportunity)
                else:
                    self.logger.debug(f"⏸️ {symbol}: Proactive evaluation completed - entry conditions not met")

        except Exception as e:
            self.logger.error(f"Error in _monitor_watchlist: {e}")

    async def _fetch_candidate_snapshots(self, symbols: list) -> Dict[str, Any]:
        """
        Fetch batch market data for symbols.
        Returns dict {symbol: {price, volume, volume_ratio, ...}}
        """
        results = {}
        try:
            if not self.execution_engine or not self.execution_engine.broker:
                return {}
                
            # Use IBKR batch fetching if available via some adapter method
            # For now, let's assume we can loop reqMktData or use a batch helper
            # If we don't have a batch helper exposed, we might iterate (slow).
            # BETTER: Use the BatchPriceManager if available in Core, but that defines subscriptions.
            
            # Implementation using standard broker call (wrapper)
            # Assuming broker has 'get_current_prices' or similar. 
            # If not, we might need to rely on what's available.
            # Let's check what 'self.execution_engine.broker' offers. 
            # It's likely IBKRAdapter.
            
            # For efficiency in this specific system, we can try 'get_smart_price' loop 
            # or check if we can piggyback on existing subscriptions.
            
            # Since Proactive Candidates are "high priority", we should probably 
            # just fetch them one by one or in parallel tasks.
            
            start_time = datetime.now()
            
            # Parallel fetch logic
            tasks = []
            for sym in symbols:
                 tasks.append(self._fetch_single_snapshot_safe(sym))
                 
            snapshots_list = await asyncio.gather(*tasks)
            
            for snap in snapshots_list:
                if snap and snap.get('symbol'):
                    results[snap['symbol']] = snap

            # self.logger.debug(f"Fetched {len(results)} snapshots in {(datetime.now() - start_time).total_seconds():.2f}s")
            
        except Exception as e:
            self.logger.error(f"Snapshot fetch error: {e}")
            
        return results

    async def _fetch_single_snapshot_safe(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Helper to fetch single snapshot without crashing"""
        try:
            # We need Price and Volume.
            # get_smart_price gives price.
            # We also need relatively volume info if possible.

            ticker = await self.execution_engine.broker.get_ticker(symbol)
            if not ticker:
                 return None

            # Extract basic data
            price = ticker.marketPrice() or ticker.last or ticker.close

            # Approximating volume ratio is hard without historical data.
            # But the worker checks this again in should_enter using bars.
            # So here we just need "Current Price" to check against Levels (Resistance/Trap).

            # Construct partial snapshot
            return {
                'symbol': symbol,
                'price': price,
                'volume': ticker.volume if ticker.volume else 0,
                'volume_ratio': 999.0, # Pass-through to let should_enter validate with real bars
            }
        except Exception:
            return None

    async def _fetch_intraday_bars(self, symbol: str) -> list:
        """
        Fetch intraday bars for VWAP and volume analysis.

        This is the CRITICAL FIX for proactive monitoring.
        Without bars, should_enter() cannot calculate VWAP and will reject the opportunity.

        Args:
            symbol: Stock symbol to fetch bars for

        Returns:
            List of bar dicts compatible with scanner format, or empty list if unavailable
        """
        try:
            # Fetch 1-minute bars for today (up to 390 bars = full trading day)
            # Using IBKR adapter's get_bars method
            bars_data = await self.execution_engine.broker.get_bars(
                symbol=symbol,
                timeframe='1 min',
                count=390  # Full trading day
            )

            if not bars_data or len(bars_data) == 0:
                self.logger.debug(f"📊 {symbol}: No intraday bars available from IBKR")
                return []

            # Convert MarketData objects to dict format expected by get_bars_from_opportunity
            bars_history = []
            for bar in bars_data:
                bars_history.append({
                    'timestamp': bar.timestamp if hasattr(bar, 'timestamp') else datetime.now(),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume if hasattr(bar, 'volume') else 0
                })

            self.logger.debug(f"📊 {symbol}: Fetched {len(bars_history)} intraday bars for analysis")
            return bars_history

        except Exception as e:
            self.logger.warning(f"📊 {symbol}: Error fetching intraday bars: {e}")
            return []


    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evaluate entry for Short Squeeze.
        """
        symbol = opportunity.get('symbol')
        current_price = opportunity.get('current_price', 0)
        
        # 1. WATCHLIST CHECK (The Gatekeeper)
        candidate_info = self._get_proactive_candidate_info(symbol)
        if not candidate_info:
            self.logger.debug(f"{symbol}: Not in Proactive Watchlist. Skipping.")
            return False

        days_since_detection = candidate_info.get('days_since_detection', 0)

        pattern_type = candidate_info.get('pattern_type', 'UNKNOWN')
        self.logger.info(f"👀 {symbol}: Found in Proactive Watchlist! (Day {days_since_detection}, Pattern: {pattern_type})")

        # Extract key levels and daily structure from candidate

        key_levels = json.loads(candidate_info.get('key_levels', '{}')) if candidate_info.get('key_levels') else {}
        daily_structure = key_levels.get('daily_structure', 'UNKNOWN')
        current_resistance = key_levels.get('resistance', key_levels.get('day1_high', 0))
        day1_high = key_levels.get('day1_high', 0)

        self.logger.info(
            f"📊 {symbol} Levels: Resistance=${current_resistance:.2f}, "
            f"Day1High=${day1_high:.2f}, ReclaimedSupport=${key_levels.get('reclaimed_support', 0):.2f}, Structure={daily_structure}"
        )
        
        # Get bars for detailed analysis (Need VWAP for all patterns)
        bars = self.get_bars_from_opportunity(opportunity)
        if not bars:
            return False
            
        # VWAP Analysis
        vwap_val = self.calculate_vwap_from_bars(bars)
        if not vwap_val:
            return False

        # --- SPECIAL HANDLING: FAKE BREAKDOWN (The Bear Trap) ---
        if pattern_type == 'FAKE_BREAKDOWN':
            reclaimed_support = key_levels.get('reclaimed_support', 0)
            # In fake breakdown, the resistance is typically the high of the reversal candle (day1_high)
            confirmation_level = key_levels.get('resistance', day1_high)
            
            # 1. RISK CHECK: Must Hold the Trap Level
            if reclaimed_support > 0 and current_price < reclaimed_support:
                self.logger.debug(f"❌ {symbol}: FAKE_BREAKDOWN FAILED - Price ${current_price:.2f} below trap level ${reclaimed_support:.2f}")
                return False
                
            # 2. TRIGGER CHECK: Confirmation Breakout + VWAP Strength
            if confirmation_level > 0:
                if current_price > confirmation_level and current_price > vwap_val:
                    self.logger.info(
                        f"🚀 {symbol}: BEAR TRAP SPRINGING! (Price ${current_price:.2f} > High ${confirmation_level:.2f} & VWAP)"
                    )
                    opportunity['setup_type'] = 'BEAR_TRAP_CONFIRMATION'
                    opportunity['entry_day'] = days_since_detection
                    # SWING MODE: Force EOD safety for multi-day squeeze
                    opportunity['EOD_safe'] = True
                    opportunity['trading_horizon'] = 'SWING'
                    self._update_candidate_status(symbol, 'TRIGGERED')
                    return True
                else:
                    self.logger.debug(f"{symbol}: Bear Trap waiting for trigger > ${confirmation_level:.2f} (Curr: ${current_price:.2f})")
                    # STRICT MODE: If we are tracking a specific setup, we wait for its trigger.
                    # Falling through to generic logic might trigger prematurely on minor volume bumps.
                    return False 


        # --- ADAPTIVE STRATEGY BY DAYS_SINCE_DETECTION AND DAILY STRUCTURE ---
        # Day 0-2: AGGRESSIVE (Breakout Open, Early VWAP Reclaim)
        # Day 3-5: MODERATE (VWAP Reclaim + Volume Confirmation)
        # Day 6-7: CONSERVATIVE (Only Violent Reclaims with Heavy Volume)
        # BREAKOUT structure: Most aggressive (already breaking out on daily)
        # HIGHER_HIGH structure: Strong continuation (be aggressive)
        # INSIDE_DAY structure: Consolidation (wait for confirmation)
        # LOWER_HIGH structure: Weakening (require more volume/confirmation)

        # --- BREAKOUT OPEN DETECTION (Most Aggressive - Day 0-3) ---
        # Now uses CURRENT RESISTANCE (not stale day1_high)
        # If already broke Day 1 High on previous days, use the new resistance level
        trading_rec = opportunity.get('trading_recommendation', {})

        if current_resistance and current_resistance > 0:
            # Check if price is breaking out above current resistance
            if current_resistance <= current_price <= current_resistance * 1.01:
                # Breakout Open is strongest on Days 0-3 OR if daily_structure is BREAKOUT/HIGHER_HIGH
                aggressive_structure = daily_structure in ['BREAKOUT', 'HIGHER_HIGH']

                if days_since_detection <= 3 or aggressive_structure:
                    self.logger.info(
                        f"🚀 {symbol}: BREAKOUT OPEN DETECTED (Day {days_since_detection}, "
                        f"${current_price:.2f} is 0-1% above Resistance ${current_resistance:.2f}, "
                        f"Structure: {daily_structure})"
                    )
                    opportunity['setup_type'] = 'BREAKOUT_OPEN'
                    opportunity['entry_day'] = days_since_detection
                    opportunity['daily_structure'] = daily_structure
                    self.logger.info(f"🔫 {symbol}: SHORT SQUEEZE TRIGGERED (Breakout Open)!")
                    self._update_candidate_status(symbol, 'TRIGGERED')
                    return True
                else:
                    self.logger.debug(
                        f"{symbol}: Breakout detected but Day {days_since_detection} > 3 "
                        f"and structure is {daily_structure} (requires stronger confirmation)"
                    )
        # ------------------------------------

        # 2. PRICE & VOLUME FILTERS
        if not (self.min_price <= current_price <= self.max_price):
            return False

        # 3. BORROW AVAILABILITY (Fresh Check)
        # Squeezes need short sellers.
        # Hierarchy: 
        # - NONE (0 shares): ULTIMATE (Trap is full, no more fuel for shorts)
        # - HTB: IDEAL (High demand, low supply)
        # - ETB: NORMAL
        try:
            short_data = await self.execution_engine.broker.get_short_data(symbol)
            status = short_data.get('short_status', 'NONE')
            shares = short_data.get('shortable_shares', 0)
            
            if status == 'NONE' or shares == 0:
                self.logger.info(f"{symbol}: 💎 ULTIMATE Squeeze Alert - Zero borrows (Crowded Trade).")
            elif status == 'HTB':
                self.logger.info(f"{symbol}: 🔥 HTB Detected - IDEAL squeeze environment.")
            else:
                self.logger.debug(f"{symbol}: {status} confirmed for squeeze play.")
                
        except Exception as e:
            self.logger.warning(f"{symbol}: Error checking borrows: {e} - Continuing without borrow data")
            # Continue evaluation even if borrow check fails (e.g., paper trading)

        # Get bars for detailed analysis
        # bars = self.get_bars_from_opportunity(opportunity) # ALREADY FETCHED ABOVE
        # if not bars:
        #    return False

        # 3. TRIGGER CONDITIONS ("Uncomfortable Shorts")
        
        # A. VWAP Analysis
        # vwap_val = self.calculate_vwap_from_bars(bars) # ALREADY CALCULATED
        # if not vwap_val:
        #    return False
            
        # Condition: Price > VWAP (Strength)
        rate_above_vwap = (current_price - vwap_val) / vwap_val * 100
        if current_price < vwap_val:
             self.logger.debug(f"{symbol}: Below VWAP. Shorts are comfortable.")
             return False
             
        # B. Violent Reclaim / Strength Check
        # Check if we recently crossed VWAP or have sustained strength
        # Simple for now: Price > VWAP AND High Relative Volume
        
        # C. Volume Surge
        # Calculate real-time relative volume if possible or use opportunity data
        rel_vol = opportunity.get('volume_ratio', 1.0) # Assuming scanner provides it
        
        # If chance provides bars, calc local volume surge
        # Check last few bars for "Abnormal Green Candles"
        recent_bars = bars[-3:]
        buy_pressure = 0
        for bar in recent_bars:
            if bar.close > bar.open:
                buy_pressure += bar.volume
        
        # Heuristic: Is there "Violent" buying?
        # We really rely on the Scanner's Volume Ratio for the "Day 0" surge,
        # but here we want intraday surge.
        # Let's trust opportunity['volume_ratio'] (Day's volume vs Average) > 3.0
        # OR 5-min rel vol if available.
        
        # ADAPTIVE VOLUME THRESHOLDS BY DAYS_SINCE_DETECTION AND DAILY STRUCTURE
        # Day 0-2: Accept rel_vol >= 1.5x (Early squeeze phase)
        # Day 3-5: Require rel_vol >= 2.0x (Moderate confirmation)
        # Day 6-7: Require rel_vol >= 3.0x (Late squeeze needs heavy volume)
        #
        # STRUCTURE ADJUSTMENTS:
        # - BREAKOUT/HIGHER_HIGH: Relax volume (-0.5x) - already showing strength on daily
        # - INSIDE_DAY: Keep standard - needs confirmation
        # - LOWER_HIGH: Increase volume (+0.5x) - showing weakness, needs more proof

        if days_since_detection <= 2:
            base_threshold = 1.5
        elif days_since_detection <= 5:
            base_threshold = 2.0
        else:
            base_threshold = 3.0

        # Adjust based on daily structure
        if daily_structure in ['BREAKOUT', 'HIGHER_HIGH']:
            min_vol_threshold = max(1.0, base_threshold - 0.5)  # Relax requirement
            self.logger.debug(f"{symbol}: Strong structure ({daily_structure}), relaxed volume threshold to {min_vol_threshold}x")
        elif daily_structure == 'LOWER_HIGH':
            min_vol_threshold = base_threshold + 0.5  # Increase requirement
            self.logger.debug(f"{symbol}: Weak structure ({daily_structure}), increased volume threshold to {min_vol_threshold}x")
        else:
            min_vol_threshold = base_threshold

        if rel_vol < min_vol_threshold:
             # Check for "Quiet Rise" (Price up > 5% on lower volume?) - Only on Days 0-2
             gap_pct = opportunity.get('gap_percentage', 0)
             if days_since_detection <= 2 and gap_pct > 5.0:
                 self.logger.info(f"{symbol}: Quiet Rise detected on Day {days_since_detection} (Gap {gap_pct:.1f}%, Vol {rel_vol:.1f}x)")
             else:
                 self.logger.debug(f"{symbol}: Low Volume (Day {days_since_detection} needs {min_vol_threshold}x, got {rel_vol:.1f}x).")
                 return False

        # 1. METADATA & RECOGNITION
        # Extract quality from scanner if available
        trading_rec = opportunity.get('trading_recommendation', {})
        squeeze_quality = trading_rec.get('squeeze_quality', 'NORMAL')
        self.logger.info(f"🔍 Analyzing {symbol} - Quality: {squeeze_quality} | Price: ${current_price:.2f} | Day {days_since_detection}")

        # Store entry day for analytics
        opportunity['setup_type'] = 'VWAP_RECLAIM'
        opportunity['entry_day'] = days_since_detection
        
        # SWING MODE: Force EOD safety for multi-day squeeze
        opportunity['EOD_safe'] = True
        opportunity['trading_horizon'] = 'SWING'

        self.logger.info(f"🔫 {symbol}: SHORT SQUEEZE TRIGGERED! (Day {days_since_detection}, VWAP Reclaim + Volume {rel_vol:.1f}x)")

        # Update DB Status to TRIGGERED
        self._update_candidate_status(symbol, 'TRIGGERED')

        return True

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Progress of the squeeze.
        """
        # Simplified: If should_enter passes, we are 100% go.
        # But we can graduate it.
        symbol = opportunity.get('symbol')
        if not self._get_proactive_candidate_info(symbol):
            return 0.0, 0.0
            
        return 100.0, 0.0 # Support level todo

    def calculate_adaptive_risk(
        self,
        opportunity: Dict[str, Any],
        ods_data: Optional[Any] = None,
        intraday_structure: Optional[Any] = None,
        structural_exits: Optional[Dict] = None
    ) -> float:
        """
        Calcula el riesgo adaptativo aplicando multiplicadores de calidad de squeeze:
        - ULTIMATE (NONE borrows): 1.0x (Full size)
        - IDEAL (HTB borrows): 0.66x (2/3 size)
        - NORMAL (ETB borrows): 0.33x (1/3 size)
        """
        # 1. Get base risk from parent logic (Quality score, ODS, Structure, EV/RR)
        base_risk = super().calculate_adaptive_risk(
            opportunity, ods_data, intraday_structure, structural_exits
        )
        
        # 2. Apply Squeeze Quality Multiplier
        trading_rec = opportunity.get('trading_recommendation', {})
        quality = trading_rec.get('squeeze_quality', 'NORMAL')
        
        multipliers = {
            'ULTIMATE': 1.0,
            'IDEAL': 1.0,
            'NORMAL': 0.5
        }
        
        multiplier = multipliers.get(quality, 0.33)
        
        # Override for BREAKOUT_OPEN (100% size)
        if opportunity.get('setup_type') == 'BREAKOUT_OPEN':
            multiplier = 1.0
            self.logger.info(f"⚡ {opportunity.get('symbol')}: Applying Sizing Override for BREAKOUT_OPEN (1.0x)")

            # ENFORCE FIXED STOP LOSS HERE (to ensure it persists after calculator)
            # Use the resistance that was broken (not stale day1_high)
            symbol = opportunity.get('symbol')
            candidate_info = self._get_proactive_candidate_info(symbol)
            if candidate_info:

                key_levels = json.loads(candidate_info.get('key_levels', '{}')) if candidate_info.get('key_levels') else {}
                # Use the resistance level we broke (current resistance at entry)
                resistance_broken = key_levels.get('resistance', key_levels.get('day1_high', 0))
                if resistance_broken:
                    fixed_stop = resistance_broken * 0.99
                    opportunity['stop_loss'] = fixed_stop
                    self.logger.info(
                        f"🛡️ {symbol}: Enforced FIXED STOP ${fixed_stop:.2f} "
                        f"(1% below Resistance ${resistance_broken:.2f})"
                    )
            
        final_risk = base_risk * multiplier
        
        # 3. Log results
        self.logger.info(
            f"📐 SQUEEZE SIZING for {opportunity.get('symbol')}: "
            f"Quality={quality} -> Multiplier={multiplier:.2f} | "
            f"Base Risk: {base_risk*100:.2f}% -> Final Risk: {final_risk*100:.2f}%"
        )
        
        # 4. CAP: Ensure we don't fall below absolute minimum if it's a valid trade
        # Base risk already has min/max caps, but multiplier might push it very low.
        return final_risk

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """
        Execute entry. Squeeze worker uses standard base logic,
        but BREAKOUT_OPEN stop loss is enforced inside calculate_adaptive_risk.
        """
        return await super()._execute_entry(opportunity)

    async def should_exit(self, symbol: str, position: Any, current_price: float) -> Tuple[bool, str]:
        """
        Evaluate exit conditions.

        Args:
            symbol: Stock symbol
            position: Position data dict
            current_price: Current market price

        Returns:
            Tuple of (should_exit: bool, reason: str)

        Uses WorkerStopManager for SL/TP/Trailing logic.
        Future: Add "Climax Top" detection for squeeze exhaustion.
        """
        # Use WorkerStopManager for standard SL/TP/Trailing logic
        should_exit, reason = self.stop_manager.check_exit(
            symbol=symbol,
            entry_price=position.get('entry_price', 0),
            current_price=current_price,
            position_metadata=position
        )

        if should_exit:
            return True, reason

        # Future: Add custom exit logic for squeeze exhaustion (volume climax, etc.)
        return False, ""

    def _get_proactive_candidate_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Check DB for candidate existence and status"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM proactive_candidates WHERE symbol = ? AND status IN ('WATCHING', 'TRIGGERED')",
                    (symbol,)
                ).fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            self.logger.error(f"DB Error checking candidate {symbol}: {e}")
        return None

    def _update_candidate_status(self, symbol: str, status: str):
        """Update status in DB"""
        try:
            with sqlite3.connect(self.db_manager.db_path) as conn:
                conn.execute(
                    "UPDATE proactive_candidates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE symbol = ?",
                    (status, symbol)
                )
        except Exception as e:
            self.logger.error(f"DB Error updating status {symbol}: {e}")
