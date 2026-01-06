"""
Livermore Intraday Worker Logic
Worker 'Event-Driven' basado en los principios de Jesse Livermore.

PHILOSOPHY:
"The big money is made by the sitting, not the trading."
"Buy the breakout of the consolidation (Pivot Point), not the initial move."

PIPELINE:
1. OBSERVATION (Evento): Detecta movimiento inusual (Rango/Volumen).
2. PAUSE (Pivote): Espera consolidación saludable (Volumen bajando, precio aguantando).
3. ENTRY (Continuación): Compra el breakout de la pausa con volumen.

RISK MANAGEMENT (Livermore Style):
- Stop Loss: STRICT TECHNICAL. Mínimo de la pausa (Pivot point low).
- Take Profit: Open-ended. Trailing stop técnico para "dejar correr".
- Break Even: Rápido tras confirmación del breakout.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np

from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager

class LivermorePhase(Enum):
    OBSERVATION = "OBSERVATION"  # Detected initial move
    PAUSE = "PAUSE"              # Consolidating/Flagging
    READY = "READY"              # Ready for breakout entry
    ACTIVE = "ACTIVE"            # Position open

@dataclass
class LivermoreCandidate:
    symbol: str
    phase: LivermorePhase
    detection_time: datetime
    initial_high: float        # High of the initial impulse
    initial_low: float         # Low of the initial impulse
    pause_high: float = 0.0    # High of the consolidation
    pause_low: float = 0.0     # Low of the consolidation (Stop Loss level)
    vol_at_detection: float = 0.0
    last_update: datetime = None

class LivermoreIntradayWorkerLogic(BaseWorkerLogic):
    """
    Worker que implementa la estrategia de Jesse Livermore Intraday.
    Mantiene estado interno de candidatos observados.
    """
    

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="livermore_intraday",
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config # Pass config to parent
        )
        
        # --- LIVERMORE SPECIFIC CONFIG ---
        # Note: We look for section [LIVERMORE_INTRADAY_STRATEGY] in config.ini
        # but defaults are hardcoded here for safety.
        
        # 1. Observation Criteria
        # TEMP: Lowered for visualization testing (normally 3.0% and 1.5x)
        self.min_impulse_range = 1.0   # Min 1% move to start observing
        self.min_impulse_vol = 0.5     # Min 0.5x relative volume
        
        # 2. Pause Criteria
        self.min_pause_candles = 3     # Min 3 candles consolidation
        self.max_pause_drawdown = 0.40 # Max 40% retrace of impulse (Livermore wanted strength)
        
        # 3. Entry Criteria
        # TEMP: Lowered for visualization testing (normally 1.2x)
        self.breakout_vol_ratio = 0.5  # Volume surge on breakout
        
        # State Management (Persistent Cache)
        # OLD: self.watched_candidates: Dict[str, LivermoreCandidate] = {}
        # NEW: Use persistent cache that survives scanner cycles
        from core.worker_state_cache import get_worker_cache
        self._cache = get_worker_cache()
        self._cache_ttl = 6.0  # 6 hours TTL for intraday candidates
        
        # Stop Manager (Strict technical stops)
        # We manually configure this to ensure it matches Livermore's style
        from .worker_stop_manager import WorkerStopConfig, WorkerStopManager
        stop_config = WorkerStopConfig(
            stop_loss_pct=5.0,        # Hard stop fallback (Technical is primary)
            take_profit_pct=100.0,    # "Open ended" - let the trailing handle it
            trailing_activation=3.0,  # Activate trail after 3% gain
            trailing_distance=2.0,    # 2% trailing (tight but fair)
            max_position_hours=6.0    # Intraday max
        )
        # If config provided, try to load specific section, else use default
        if config:
             self.stop_manager = create_worker_stop_manager(config, 'LIVERMORE_INTRADAY_STRATEGY')
        else:
             self.stop_manager = WorkerStopManager(stop_config)

        self.logger.info("🎩 Livermore Intraday Worker initialized - 'The Event calls, the Continuity pays'")

    # ========== PERSISTENT CACHE HELPERS ==========

    @property
    def watched_candidates(self) -> Dict[str, LivermoreCandidate]:
        """Get all watched candidates from persistent cache"""
        return self._cache.get_all('livermore_intraday')

    def _get_candidate(self, symbol: str) -> Optional[LivermoreCandidate]:
        """Get a specific candidate from cache"""
        return self._cache.get('livermore_intraday', symbol)

    def _set_candidate(self, symbol: str, candidate: LivermoreCandidate):
        """Store candidate in persistent cache"""
        self._cache.set('livermore_intraday', symbol, candidate, ttl_hours=self._cache_ttl)

    def _remove_candidate(self, symbol: str):
        """Remove candidate from cache"""
        self._cache.delete('livermore_intraday', symbol)

    # ========== ENTRY LOGIC ==========

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        State Machine for Entry.
        Evaluating: Observation -> Pause -> Entry
        """
        symbol = opportunity.get('symbol')
        current_price = opportunity.get('current_price')

        # Check basic entry blocking rules (Hours, Blocked Symbol, etc)
        # We assume base filters are handled, but we double check Blocked
        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()
        if unified_manager and unified_manager.is_symbol_blocked(symbol):
            return False

        # Get history (bars)
        bars = self.get_bars_from_opportunity(opportunity)
        if not bars or len(bars) < 10:
            return False

        # --- STATE MACHINE ---

        # Case 0: New Candidate
        candidate = self._get_candidate(symbol)
        if candidate is None:
            self._evaluate_new_candidate(symbol, bars, current_price, opportunity)
            # Re-fetch candidate in case it was just created
            candidate = self._get_candidate(symbol)
            # Expose indicators (will be None if no impulse detected, or populated if impulse detected)
            self._expose_indicators(opportunity, candidate)
            return False # Never enter on first sight

        # Case 1: Existing Candidate
        candidate.last_update = datetime.now()
        self._set_candidate(symbol, candidate)  # Update timestamp in cache

        # Expose indicators for visualization BEFORE processing
        self._expose_indicators(opportunity, candidate)

        if candidate.phase == LivermorePhase.OBSERVATION:
            self._update_observation_phase(candidate, bars, current_price)
            self._set_candidate(symbol, candidate)  # Save phase transition to cache
            # Update exposed indicators after phase transition
            self._expose_indicators(opportunity, candidate)
            # If it just switched to READY inside update, we can check for entry immediately?
            # Livermore prefers confirming the pause first. Let's wait for next tick or logic flow.
            return False

        if candidate.phase == LivermorePhase.PAUSE:
            # Check for Breakout (Entry Trigger)
            entered = self._check_breakout_entry(candidate, bars, current_price, opportunity)
            if entered:
                # IMPORTANT: Set technical stop in opportunity for execution
                opportunity['stop_loss_price'] = candidate.pause_low
                opportunity['take_profit_price'] = current_price * 1.15  # Default 15% TP
                opportunity['strategy_note'] = "Livermore Breakout"
                self.logger.info(f"🎩 {symbol}: LIVERMORE ENTRY TRIGGERED! Breakout of {candidate.pause_high:.2f}")
                # Remove from watchlist after entry (to prevent re-entry)
                self._remove_candidate(symbol)
                return True
            else:
                # Check if pause failed (price dropped too much)
                self._validate_pause_integrity(candidate, current_price)
                self._set_candidate(symbol, candidate)  # Save validation result
                return False

        return False

    def _evaluate_new_candidate(self, symbol, bars, current_price, opportunity):
        """Step 1: Reaction Detection (Observation)"""
        # Look for impulse (last 5-10 bars)
        recent_bars = bars[-10:]
        low = min(b.low for b in recent_bars)
        high = max(b.high for b in recent_bars)

        impulse_pct = ((high - low) / low) * 100
        vol_ratio = opportunity.get('volume_ratio', 1.0)

        # Debug: Log impulse detection criteria
        self.logger.debug(
            f"🔎 {symbol}: Impulse Check - Range: {impulse_pct:.1f}% (need {self.min_impulse_range:.1f}%), "
            f"Vol: {vol_ratio:.1f}x (need {self.min_impulse_vol:.1f}x)"
        )

        if impulse_pct >= self.min_impulse_range and vol_ratio >= self.min_impulse_vol:
            # Valid Impulse Detected
            candidate = LivermoreCandidate(
                symbol=symbol,
                phase=LivermorePhase.OBSERVATION,
                detection_time=datetime.now(),
                initial_high=high,
                initial_low=low,
                vol_at_detection=vol_ratio
            )
            self._set_candidate(symbol, candidate)  # Save to persistent cache
            self.logger.info(f"👀 {symbol}: Added to Livermore Watchlist (Impulse: {impulse_pct:.1f}%)")

    def _update_observation_phase(self, candidate, bars, current_price):
        """Step 2: Check for Pause Formation"""
        # We need to see if price has stopped making new highs and is consolidating
        # Ideally, we want N candles inside the range of the impulse high
        
        # Simple logic: If current price is below impulse high but above 60% retrace level
        retrace_limit = candidate.initial_high - (candidate.initial_high - candidate.initial_low) * self.max_pause_drawdown
        
        if current_price < retrace_limit:
            # Failed structure - dropped too much
            self.logger.debug(f"❌ {candidate.symbol}: Dropped below retrace limit. Removing.")
            self._remove_candidate(candidate.symbol)
            return

        if current_price >= candidate.initial_high:
            # Impulse expanding - update high to track the true top of the move
            candidate.initial_high = max(candidate.initial_high, current_price)
            self.logger.debug(f"📈 {candidate.symbol}: Impulse expanding. New High: {candidate.initial_high:.2f}")
            return

        if current_price < candidate.initial_high:
            # It's trading below the high... potential pause.
            # Promote to PAUSE phase to start tracking consolidation geometry
            candidate.phase = LivermorePhase.PAUSE
            candidate.pause_high = candidate.initial_high # The level to break
            candidate.pause_low = min(b.low for b in bars[-3:]) # Provisional low
            self.logger.info(f"⏸️ {candidate.symbol}: Entering PAUSE phase. Watch for break of {candidate.pause_high}")
        else:
            self.logger.debug(f"ℹ️ {candidate.symbol}: Still in OBSERVATION. Price {current_price} >= High {candidate.initial_high}")

    def _validate_pause_integrity(self, candidate, current_price):
        """Step 4: Validate Pause (Continuity)"""
        # Update pause low (Technical Pivot Support)
        # If price drops below strict pivot -> Discard
        retrace_limit = candidate.initial_high - (candidate.initial_high - candidate.initial_low) * self.max_pause_drawdown
        
        if current_price < retrace_limit:
             self.logger.info(f"🗑️ {candidate.symbol}: Failed pause (Retraced > {self.max_pause_drawdown*100}%). Discarding.")
             self._remove_candidate(candidate.symbol)  # Remove from persistent cache

    def _check_breakout_entry(self, candidate, bars, current_price, opportunity):
        """Step 5: Entry Trigger"""
        # 1. Price breaks pause_high
        if current_price > candidate.pause_high:
            # 2. Volume confirmation?
            # Simple check: Current bar volume or opportunity volume ratio
            # For responsiveness, we trust the price break if scanner volume is high
            vol_ratio = opportunity.get('volume_ratio', 1.0)
            
            if vol_ratio >= self.breakout_vol_ratio:
                # 3. Update candidate status (so we don't buy twice)
                # Note: Will be removed in should_enter() after this returns True
                return True
        
        return False

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """Override exit logic to strictly enforce Livermore rules"""
        # 1. Technical Stop (Low of Pause) - Setup at entry
        # Typically passed via position metadata, if available.
        
        # Prepare position metadata (Critical for EOD_safe support)
        position_metadata = {
            'EOD_safe': position.get('EOD_safe', False),
            'trading_horizon': position.get('trading_horizon', 'unknown'),
            'expected_hold_hours': position.get('expected_hold_hours', 0),
            'opportunity_data': position.get('opportunity_data', {}),
            'strategy': self.worker_name,
            'side': position.get('side', 'LONG')
        }

        # Fallback to standard stop manager which has the trailing logic.
        return self.stop_manager.check_exit(
            symbol, 
            current_price, 
            position.get('entry_price'), 
            market_data=None, 
            position_metadata=position_metadata
        )

    def _expose_indicators(self, opportunity: Dict[str, Any], candidate: Optional[LivermoreCandidate]):
        """
        Expose Livermore indicators for WorkerLab visualization

        Indicators exposed:
        - livermore_phase: Current phase (OBSERVATION, PAUSE, READY, ACTIVE, or None)
        - livermore_pause_high: Breakout level (resistance to break)
        - livermore_pause_low: Technical stop loss level (pivot support)
        - livermore_initial_high: Top of the initial impulse
        - livermore_initial_low: Bottom of the initial impulse
        """
        if candidate is None:
            # No candidate yet - expose empty values
            opportunity['livermore_phase'] = None
            opportunity['livermore_pause_high'] = None
            opportunity['livermore_pause_low'] = None
            opportunity['livermore_initial_high'] = None
            opportunity['livermore_initial_low'] = None
        else:
            # Expose candidate levels
            opportunity['livermore_phase'] = candidate.phase.value
            opportunity['livermore_pause_high'] = candidate.pause_high if candidate.pause_high > 0 else None
            opportunity['livermore_pause_low'] = candidate.pause_low if candidate.pause_low > 0 else None
            opportunity['livermore_initial_high'] = candidate.initial_high
            opportunity['livermore_initial_low'] = candidate.initial_low

