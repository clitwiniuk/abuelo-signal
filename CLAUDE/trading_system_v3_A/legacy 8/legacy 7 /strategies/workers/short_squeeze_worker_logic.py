
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
    
    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name="short_squeeze",
            broker=broker,
            config=config
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
        
        # Anti-overtrading tracking
        self.traded_symbols_today = set()  # Track symbols traded today
        self._last_reset_date = None       # For daily reset

    async def _periodic_task(self):
        """
        Periodic task to proactively monitor the watchlist.
        Run every self.monitor_interval seconds.
        """
        try:
            now = datetime.now()
            if (now - self.last_monitor_time).total_seconds() >= self.monitor_interval:
                if self.is_running: # Only monitor if worker is running
                    await self._monitor_watchlist()
                self.last_monitor_time = now
        except Exception as e:
            self.logger.error(f"Error in periodic watchlist monitor: {e}")

    async def _monitor_watchlist(self):
        """
        Query DB for active candidates and fetch real-time data to check for triggers.
        """
        try:
            # 1. Get Active Candidates (WATCHING or TRIGGERED) from DB
            candidates = []
            try:
                with sqlite3.connect(self.db_manager.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(
                        "SELECT * FROM proactive_candidates WHERE status IN ('WATCHING', 'TRIGGERED')"
                    )
                    candidates = [dict(row) for row in cursor.fetchall()]
            except Exception as db_err:
                 # DB might be locked or missing in test env
                 self.logger.debug(f"DB access error in monitor: {db_err}")
                 return

            if not candidates:
                return

            self.logger.info(f"🧐 Monitoring {len(candidates)} proactive candidates...")
            
            # 2. Extract symbols
            symbols = [c['symbol'] for c in candidates]
            
            # 3. Batch Fetch Snapshots
            snapshots = await self._fetch_candidate_snapshots(symbols)
            
            if not snapshots:
                return

            # 4. Evaluate each candidate
            for candidate in candidates:
                symbol = candidate['symbol']
                snapshot = snapshots.get(symbol)
                
                if not snapshot:
                    continue
                    
                # Construct an internal "Opportunity" object
                opportunity = {
                    'symbol': symbol,
                    'current_price': snapshot.get('price', 0),
                    'volume_ratio': snapshot.get('volume_ratio', 1.0),
                    'gap_percentage': snapshot.get('gap_percentage', 0.0),
                    'timestamp': datetime.now(),
                    'source': 'PROACTIVE_MONITOR',
                    # Inject candidate info directly to avoid DB re-fetch in should_enter
                    'candidate_info': candidate
                }

                # 5. Check Entry (Reuse logic)
                should_trade = await self.should_enter(opportunity)
                
                if should_trade:
                    self.logger.info(f"🚀 PROACTIVE TRIGGER: {symbol} triggered entry logic from internal monitor!")
                    # Execute Entry
                    await self._execute_entry(opportunity)

        except Exception as e:
            self.logger.error(f"Error in _monitor_watchlist: {e}")

    def _reset_daily_state_if_needed(self):
        """Reset daily counters at start of new trading day"""
        import pytz
        from datetime import datetime
        ny_tz = pytz.timezone('US/Eastern')
        current_date = datetime.now(ny_tz).date()

        if not hasattr(self, '_last_reset_date') or self._last_reset_date != current_date:
            self.logger.info(f"🔄 New trading day - Resetting Short Squeeze worker counters")
            self.traded_symbols_today.clear()
            self._last_reset_date = current_date

    async def _fetch_candidate_snapshots(self, symbols: list) -> Dict[str, Any]:
        """
        Fetch batch market data for symbols.
        Returns dict {symbol: {price, volume, volume_ratio, ...}}
        """
        results = {}
        try:
            # Use broker if available
            if not self.broker:
                return {}
            
            # If broker has batch fetching (e.g. LiveIBKRBroker custom method) - todo
            # For now, parallel single fetch
            tasks = []
            for sym in symbols:
                 tasks.append(self._fetch_single_snapshot_safe(sym))
                 
            snapshots_list = await asyncio.gather(*tasks)
            
            for snap in snapshots_list:
                if snap and snap.get('symbol'):
                    results[snap['symbol']] = snap
            
        except Exception as e:
            self.logger.error(f"Snapshot fetch error: {e}")
            
        return results

    async def _fetch_single_snapshot_safe(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Helper to fetch single snapshot without crashing"""
        try:
            # Prefer broker.get_current_price if available
            if hasattr(self.broker, 'get_current_price'):
                price = await self.broker.get_current_price(symbol)
                # Volume?
                return {
                    'symbol': symbol,
                    'price': price,
                    'volume': 0, # Placeholder if not available
                    'volume_ratio': 999.0, 
                }
            
            # Fallback to legacy execution engine if present
            if hasattr(self, 'execution_engine') and self.execution_engine:
                 ticker = await self.execution_engine.broker.get_ticker(symbol)
                 if ticker:
                    return {
                        'symbol': symbol,
                        'price': ticker.marketPrice() or ticker.last or ticker.close,
                        'volume': ticker.volume if ticker.volume else 0,
                        'volume_ratio': 999.0,
                    }
            
            return None
        except Exception:
            return None


    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evaluate entry for Short Squeeze using "Smart" Scoring System.
        """
        try:
            symbol = opportunity.get('symbol')
            current_price = opportunity.get('current_price', 0)
            
            # Reset daily state if new trading day
            self._reset_daily_state_if_needed()

            # 1. ANTI-OVERTRADING CHECK
            if symbol in self.traded_symbols_today:
                self.logger.info(f"⚪ {symbol}: ANTI-OVERTRADING - Already traded today")
                return False

            # 2. WATCHLIST CHECK
            candidate_info = opportunity.get('candidate_info')
            if not candidate_info:
                candidate_info = self._get_proactive_candidate_info(symbol)
                
            if not candidate_info:
                self.logger.debug(f"{symbol}: Not in Proactive Watchlist. Skipping.")
                return False

            # 3. CALCULATE SCORE (The "Smart" Filter)
            # This calls internal logic to validate Fuel, Trigger, Momentum, and Extension
            completion, support_level = await self.calculate_pattern_completion(opportunity)
            
            # Store support level for risk management if needed
            opportunity['support_level'] = support_level

            # 4. EVALUATE ENTRY "SWEET SPOT" (75-100%)
            if 75.0 <= completion <= 100.0:
                 self.logger.info(
                    f"✅ {symbol}: SQUEEZE TRIGGERED! Score {completion:.0f}% (Sweet Spot). "
                    f"Price ${current_price:.2f}"
                 )
                 # Mark as traded
                 self.traded_symbols_today.add(symbol)
                 return True
            
            elif completion > 100.0:
                 self.logger.info(f"⚪ {symbol}: REJECTED - Too late / Parabolic (Score {completion:.0f}% > 100%)")
                 return False
            else:
                 self.logger.debug(f"⚪ {symbol}: REJECTED - Setup not ready (Score {completion:.0f}% < 75%)")
                 return False
                 
        except Exception as e:
            self.logger.error(f"Error in should_enter: {e}", exc_info=True)
            return False

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calculate Squeeze Pattern Score (0-100%).
        
        STAGES:
        1. Fuel (Volume/Borrows): 25%
        2. Trigger (VWAP): 25%
        3. Momentum (Recent Action): 25%
        4. Extension (Sweet Spot): 25%
        """
        try:
            symbol = opportunity.get('symbol')
            current_price = opportunity.get('current_price', 0)
            score = 0.0
            
            # --- STAGE 1: FUEL (25 pts) ---
            # Either High Volume OR Scarce Borrows
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            short_status = 'ETB'
            if hasattr(self.broker, 'get_short_data'):
                sd = await self.broker.get_short_data(symbol)
                short_status = sd.get('short_status', 'ETB')
                
            has_fuel = False
            if short_status in ['NONE', 'HTB']:
                has_fuel = True
                self.logger.debug(f"Stage 1 PASS: Short Fuel ({short_status})")
            elif volume_ratio >= 3.0:
                has_fuel = True
                self.logger.debug(f"Stage 1 PASS: Volume Fuel ({volume_ratio:.1f}x)")
                
            if has_fuel: score += 25.0
            
            # --- STAGE 2: TRIGGER / VWAP (25 pts) ---
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_val = 0.0
            if bars:
                vwap_val = self.calculate_vwap_from_bars(bars)
                if vwap_val and current_price > vwap_val:
                    score += 25.0
                    self.logger.debug(f"Stage 2 PASS: Price > VWAP")
                    
            # --- STAGE 3: MOMENTUM (25 pts) ---
            # Require recent green candle or sustain
            if bars and len(bars) >= 3:
                recent_bullish = bars[-1].close > bars[-1].open or bars[-2].close > bars[-2].open
                if recent_bullish:
                    score += 25.0
                    self.logger.debug(f"Stage 3 PASS: Bullish Momentum")
                    
            # --- STAGE 4: EXTENSION / SWEET SPOT (25 pts) ---
            # Gap < 15% (avoid buying top)
            gap_pct = opportunity.get('gap_percentage', 0.0)
            if gap_pct <= 15.0:
                score += 25.0
                self.logger.debug(f"Stage 4 PASS: Controlled Reaction (Gap {gap_pct:.1f}%)")
            else:
                # If parabolic, we award 0 here, keeping score at max 75 (which is border)
                # Or we can return 100 to indicate "Too Late" if we treat 100 as BAD.
                # DailyPlays treats 100 as "Parabolic/Too Late".
                # Let's align: If Gap > 20%, force score to 100 (Too Late)
                if gap_pct > 20.0:
                    score = 101.0
                    self.logger.debug("Stage 4 FAIL: Parabolic (Gap > 20%) -> Force 101 (Too Late)")
                    
            return score, vwap_val
            
        except Exception as e:
            self.logger.error(f"Error in squeeze scoring: {e}")
            return 0.0, 0.0

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

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calculate Squeeze Pattern Score (0-100%).
        
        STAGES:
        1. Fuel (Volume/Borrows): 25%
        2. Trigger (VWAP): 25%
        3. Momentum (Recent Action): 25%
        4. Extension (Sweet Spot): 25%
        """
        try:
            symbol = opportunity.get('symbol')
            current_price = opportunity.get('current_price', 0)
            score = 0.0
            
            # --- STAGE 1: FUEL (25 pts) ---
            # Either High Volume OR Scarce Borrows
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            short_status = 'ETB'
            if hasattr(self.broker, 'get_short_data'):
                sd = await self.broker.get_short_data(symbol)
                short_status = sd.get('short_status', 'ETB')
                
            has_fuel = False
            if short_status in ['NONE', 'HTB']:
                has_fuel = True
                self.logger.debug(f"Stage 1 PASS: Short Fuel ({short_status})")
            elif volume_ratio >= 3.0:
                has_fuel = True
                self.logger.debug(f"Stage 1 PASS: Volume Fuel ({volume_ratio:.1f}x)")
                
            if has_fuel: score += 25.0
            
            # --- STAGE 2: TRIGGER / VWAP (25 pts) ---
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_val = 0.0
            if bars:
                vwap_val = self.calculate_vwap_from_bars(bars)
                if vwap_val and current_price > vwap_val:
                    score += 25.0
                    self.logger.debug(f"Stage 2 PASS: Price > VWAP")
                    
            # --- STAGE 3: MOMENTUM (25 pts) ---
            # Require recent green candle or sustain
            if bars and len(bars) >= 3:
                recent_bullish = bars[-1].close > bars[-1].open or bars[-2].close > bars[-2].open
                if recent_bullish:
                    score += 25.0
                    self.logger.debug(f"Stage 3 PASS: Bullish Momentum")
                    
            # --- STAGE 4: EXTENSION / SWEET SPOT (25 pts) ---
            # Gap < 15% (avoid buying top)
            gap_pct = opportunity.get('gap_percentage', 0.0)
            if gap_pct <= 15.0:
                score += 25.0
                self.logger.debug(f"Stage 4 PASS: Controlled Reaction (Gap {gap_pct:.1f}%)")
            else:
                # If parabolic, we award 0 here, keeping score at max 75 (which is border)
                # Or we can return 100 to indicate "Too Late" if we treat 100 as BAD.
                # DailyPlays treats 100 as "Parabolic/Too Late".
                # Let's align: If Gap > 20%, force score to 100 (Too Late)
                if gap_pct > 20.0:
                    score = 100.0
                    self.logger.debug("Stage 4 FAIL: Parabolic (Gap > 20%) -> Force 100 (Too Late)")
                    
            return score, vwap_val
            
        except Exception as e:
            self.logger.error(f"Error in squeeze scoring: {e}")
            return 0.0, 0.0
            
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
