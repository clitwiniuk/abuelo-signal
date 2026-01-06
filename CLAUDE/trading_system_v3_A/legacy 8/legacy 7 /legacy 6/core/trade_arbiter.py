#!/usr/bin/env python3
"""
Trade Arbiter - Worker Coordination & Signal Selection

Coordinates multiple workers analyzing the same ticker and selects the best signal.

Key Features:
- Multi-worker parallel analysis
- Context-aware worker selection
- Signal quality scoring
- Ticker locking (one trade per ticker)
- Worker priority system
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from core.context_engine import MarketContext, ContextAnalysis, get_context_engine


class TradingHorizon(Enum):
    """Trading time horizon"""
    SCALP = "scalp"           # < 30 min
    INTRADAY = "intraday"     # Same day
    SWING_SHORT = "swing_short"  # 1-3 days
    SWING = "swing"           # 3-10 days


@dataclass
class WorkerCapabilities:
    """
    Define worker's capabilities and preferences
    """
    name: str
    priority: int             # 1-5, higher = higher priority when scores tie
    compatible_contexts: List[MarketContext]
    horizon: TradingHorizon
    historical_winrate: float  # 0.0-1.0
    avg_hold_time: float      # hours
    min_confidence: float     # Minimum confidence to act (0-100)

    def is_compatible(self, context: MarketContext) -> bool:
        """Check if worker is compatible with market context"""
        return context in self.compatible_contexts


@dataclass
class WorkerSignal:
    """
    Signal from a worker

    IMPORTANT: trading_horizon is SIGNAL-SPECIFIC, not worker-specific
    Example: MACDV can be SWING (strong signal) or SWING_SHORT (weaker signal)
    """
    worker_name: str
    symbol: str
    confidence: float         # Worker's own confidence (0-100)
    entry_price: float
    stop_loss: float
    take_profit: float
    quantity: int
    risk_reward: float        # TP distance / SL distance
    trading_horizon: TradingHorizon  # SIGNAL-SPECIFIC expected hold time
    expected_hold_hours: float  # Specific expected hold time (hours)
    timestamp: datetime
    metadata: Dict            # Additional signal data (includes EOD_safe flag)


@dataclass
class ScoredSignal:
    """Signal with arbiter score"""
    signal: WorkerSignal
    capabilities: WorkerCapabilities
    context_score: float      # How well signal matches context (0-100)
    total_score: float        # Final combined score (0-100)
    selected: bool = False
    rejection_reason: Optional[str] = None

    def __str__(self):
        status = "✅ SELECTED" if self.selected else f"❌ {self.rejection_reason}"
        return (f"{self.signal.worker_name}: Score={self.total_score:.1f} "
                f"(context={self.context_score:.1f}, conf={self.signal.confidence:.1f}) - {status}")


class TradeArbiter:
    """
    Trade Arbiter - Coordinates multiple workers and selects best signal

    Workflow:
    1. Receives ticker + context analysis
    2. Requests signals from all compatible workers
    3. Scores each signal based on multiple factors
    4. Selects best signal (or rejects all if quality too low)
    5. Executes trade and locks ticker
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TradeArbiter")

        # Ticker locking mechanism
        self.locked_tickers: Dict[str, datetime] = {}  # symbol -> lock_time
        self.lock_duration_minutes = 60  # Auto-unlock after 60 min if no trade

        # Cooldown mechanism (prevent re-entry after stop loss)
        # symbol -> {'unlock_time': datetime, 'reason': str}
        self.cooldown_tickers: Dict[str, Dict] = {}
        self.cooldown_minutes_stop_loss = 30  # 30 min cooldown after stop loss
        self.cooldown_minutes_trailing_stop = 15  # 15 min cooldown after trailing stop
        self.cooldown_minutes_take_profit = 5  # 5 min cooldown after take profit (short)

        # Worker registry
        self.workers: Dict[str, WorkerCapabilities] = {}

        # Minimum score to execute (0-100)
        self.MIN_SCORE_THRESHOLD = 50.0

        # Context engine
        self.context_engine = get_context_engine()

        self.logger.info("⚖️ TradeArbiter initialized - Multi-worker coordination active")

    def register_worker(self, capabilities: WorkerCapabilities):
        """Register a worker with its capabilities"""
        self.workers[capabilities.name] = capabilities
        contexts_str = ", ".join([c.value for c in capabilities.compatible_contexts])
        self.logger.info(
            f"📝 Registered worker: {capabilities.name} "
            f"(priority={capabilities.priority}, contexts=[{contexts_str}], "
            f"horizon={capabilities.horizon.value})"
        )

    def is_ticker_locked(self, symbol: str) -> bool:
        """Check if ticker is locked (has active trade or in cooldown)"""
        # Check cooldown first (from previous stop loss)
        if symbol in self.cooldown_tickers:
            cooldown_data = self.cooldown_tickers[symbol]
            unlock_time = cooldown_data['unlock_time']

            if datetime.now() < unlock_time:
                # Still in cooldown
                remaining_minutes = (unlock_time - datetime.now()).total_seconds() / 60
                self.logger.info(
                    f"🚫 {symbol}: In cooldown after {cooldown_data['reason']} "
                    f"({remaining_minutes:.1f}min remaining)"
                )
                return True
            else:
                # Cooldown expired
                del self.cooldown_tickers[symbol]
                self.logger.info(f"✅ {symbol}: Cooldown expired, ticker available")

        # Check active trade lock
        if symbol not in self.locked_tickers:
            return False

        # Check if lock expired
        lock_time = self.locked_tickers[symbol]
        if datetime.now() - lock_time > timedelta(minutes=self.lock_duration_minutes):
            # Lock expired, remove it
            del self.locked_tickers[symbol]
            self.logger.debug(f"🔓 {symbol}: Lock expired (no trade after {self.lock_duration_minutes}min)")
            return False

        return True

    def lock_ticker(self, symbol: str):
        """Lock ticker (prevent duplicate entries)"""
        self.locked_tickers[symbol] = datetime.now()
        self.logger.info(f"🔒 {symbol}: Ticker locked")

    def unlock_ticker(self, symbol: str, exit_reason: str = ""):
        """
        Unlock ticker (trade closed or cancelled)

        Args:
            symbol: Ticker symbol
            exit_reason: Reason for exit (e.g., "STOP_LOSS_5.0%", "TRAILING_STOP", "TAKE_PROFIT")
        """
        # Remove active trade lock
        if symbol in self.locked_tickers:
            del self.locked_tickers[symbol]

        # Apply cooldown based on exit reason
        cooldown_minutes = 0
        reason_lower = exit_reason.lower()

        if "stop_loss" in reason_lower or "stop loss" in reason_lower:
            # Stop loss = long cooldown (30 min)
            cooldown_minutes = self.cooldown_minutes_stop_loss
        elif "trailing_stop" in reason_lower or "trailing" in reason_lower:
            # Trailing stop = medium cooldown (15 min) - partial win
            cooldown_minutes = self.cooldown_minutes_trailing_stop
        elif "take_profit" in reason_lower or "tp_hit" in reason_lower:
            # Take profit = short cooldown (5 min) - successful trade
            cooldown_minutes = self.cooldown_minutes_take_profit
        elif "time" in reason_lower or "eod" in reason_lower or "close" in reason_lower:
            # Time-based exit = short cooldown (5 min)
            cooldown_minutes = self.cooldown_minutes_take_profit
        elif "error" in reason_lower:
            # Technical error = medium cooldown (15 min) to prevent error loops
            cooldown_minutes = self.cooldown_minutes_trailing_stop
        else:
            # Unknown reason = medium cooldown (15 min) - be cautious
            cooldown_minutes = self.cooldown_minutes_trailing_stop

        if cooldown_minutes > 0:
            unlock_time = datetime.now() + timedelta(minutes=cooldown_minutes)
            self.cooldown_tickers[symbol] = {
                'unlock_time': unlock_time,
                'reason': exit_reason or 'UNKNOWN'
            }
            self.logger.info(
                f"⏱️ {symbol}: Cooldown applied - {cooldown_minutes}min after {exit_reason or 'UNKNOWN'}"
            )
        else:
            self.logger.info(f"🔓 {symbol}: Ticker unlocked (no cooldown)")

    async def evaluate_and_select(self, symbol: str, context: ContextAnalysis,
                           worker_signals: List[WorkerSignal]) -> Optional[ScoredSignal]:
        """
        Evaluate all worker signals and select the best one

        ENHANCED with UnifiedPositionManager integration to prevent duplicates
        across ALL workers (intraday + swing + overnight).

        Args:
            symbol: Stock symbol
            context: Market context analysis
            worker_signals: List of signals from different workers

        Returns:
            ScoredSignal if a signal is selected, None if all rejected
        """
        try:
            self.logger.info(f"⚖️ {symbol}: Evaluating {len(worker_signals)} signals for context: {context.context.value}")

            # Check if ticker is locked (local cache)
            if self.is_ticker_locked(symbol):
                self.logger.warning(f"🔒 {symbol}: Ticker locked (local cache), rejecting all signals")
                return None

            # ENHANCEMENT: Check UnifiedPositionManager for global position blocking
            try:
                from core.service_locator import get_unified_position_manager
                unified_manager = await get_unified_position_manager()

                if unified_manager and unified_manager.is_symbol_blocked(symbol):
                    position = unified_manager.get_position(symbol)
                    strategy_type = position['strategy_type'] if position else 'unknown'
                    self.logger.warning(
                        f"🚫 {symbol}: GLOBAL BLOCK - Already held in {strategy_type.upper()} trading"
                    )
                    return None
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Could not check UnifiedPositionManager: {e}")
                # Continue anyway - local lock still protects us

            if not worker_signals:
                self.logger.debug(f"⚪ {symbol}: No signals to evaluate")
                return None

            # Score all signals
            scored_signals = []
            for signal in worker_signals:
                if signal.worker_name not in self.workers:
                    self.logger.warning(f"⚠️ {symbol}: Unknown worker {signal.worker_name}, skipping")
                    continue

                capabilities = self.workers[signal.worker_name]

                # Check context compatibility
                if not capabilities.is_compatible(context.context):
                    scored = ScoredSignal(
                        signal=signal,
                        capabilities=capabilities,
                        context_score=0.0,
                        total_score=0.0,
                        selected=False,
                        rejection_reason=f"incompatible_context_{context.context.value}"
                    )
                    scored_signals.append(scored)
                    continue

                # Score the signal
                context_score = self._score_context_match(signal, capabilities, context)
                total_score = self._calculate_total_score(signal, capabilities, context, context_score)

                scored = ScoredSignal(
                    signal=signal,
                    capabilities=capabilities,
                    context_score=context_score,
                    total_score=total_score,
                    selected=False
                )
                scored_signals.append(scored)

            # Sort by score (desc), then by priority (desc)
            scored_signals.sort(key=lambda x: (x.total_score, x.capabilities.priority), reverse=True)

            # Log all scores
            for scored in scored_signals:
                self.logger.info(f"  {scored}")

            # Select best signal if above threshold
            if scored_signals:
                best = scored_signals[0]

                if best.total_score >= self.MIN_SCORE_THRESHOLD:
                    best.selected = True
                    self.logger.info(
                        f"✅ {symbol}: Selected {best.signal.worker_name} "
                        f"(score={best.total_score:.1f}, priority={best.capabilities.priority})"
                    )
                    return best
                else:
                    best.rejection_reason = f"score_too_low_{best.total_score:.0f}<{self.MIN_SCORE_THRESHOLD:.0f}"
                    self.logger.info(
                        f"❌ {symbol}: Best score {best.total_score:.1f} below threshold "
                        f"{self.MIN_SCORE_THRESHOLD:.1f}, rejecting all"
                    )

            return None

        except Exception as e:
            self.logger.error(f"❌ Error evaluating signals for {symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _score_context_match(self, signal: WorkerSignal, capabilities: WorkerCapabilities,
                            context: ContextAnalysis) -> float:
        """
        Score how well signal matches market context (0-100)

        Factors:
        - Context compatibility (base score)
        - Context confidence
        - Worker specialty alignment
        """
        try:
            # Base score if compatible
            if not capabilities.is_compatible(context.context):
                return 0.0

            base_score = 50.0

            # Boost for high context confidence
            base_score += context.confidence * 0.3  # Up to +30 points

            # Boost for perfect matches
            perfect_matches = {
                'daily_plays': [MarketContext.CATALYST, MarketContext.TREND],
                'macdv': [MarketContext.TREND, MarketContext.NEUTRAL],
                'momentum_breakout': [MarketContext.MOMENTUM, MarketContext.TREND],
                'vwap': [MarketContext.RANGE, MarketContext.NEUTRAL]
            }

            worker_key = capabilities.name.lower()
            if worker_key in perfect_matches and context.context in perfect_matches[worker_key]:
                base_score += 20.0  # Perfect match bonus

            return min(base_score, 100.0)

        except Exception as e:
            self.logger.debug(f"Error scoring context match: {e}")
            return 0.0

    def _calculate_total_score(self, signal: WorkerSignal, capabilities: WorkerCapabilities,
                              context: ContextAnalysis, context_score: float) -> float:
        """
        Calculate total signal score (0-100)

        Scoring formula (ENHANCED with pattern alignment):
        - Historical winrate * 100: 0-100 points (base)
        - Context match: +10 if compatible
        - Volume quality: +5 if vol_zscore > 1.5
        - Risk/Reward: +5 if R:R > 2.0
        - Signal freshness: +3 if < 2 min old
        - Pattern alignment: +10 if ODS + Intraday aligned (NEW)
        - Quality score: +5 if quality > 80 (NEW)
        - Worker confidence: Scale by signal confidence
        """
        try:
            # Base score from historical performance
            base = capabilities.historical_winrate * 100

            # Context compatibility bonus
            if capabilities.is_compatible(context.context):
                base += 10.0

            # Volume quality bonus
            if context.vol_zscore > 1.5:
                base += 5.0

            # Risk/Reward bonus
            if signal.risk_reward > 2.0:
                base += 5.0

            # Freshness bonus
            age_seconds = (datetime.now() - signal.timestamp).total_seconds()
            if age_seconds < 120:  # < 2 minutes
                base += 3.0

            # ENHANCEMENT: Pattern Alignment Bonus
            metadata = signal.metadata or {}
            ods_data = metadata.get('ods_data')
            intraday_structure = metadata.get('intraday_structure')

            if ods_data and intraday_structure:
                # Count aligned patterns
                patterns_aligned = 0

                # Check ODS bullish
                if hasattr(ods_data, 'classification'):
                    if ods_data.classification in ['STRONG_BULLISH', 'MODERATE_BULLISH']:
                        patterns_aligned += 1
                elif hasattr(ods_data, 'day_type'):
                    from core.ods_classifier import ODSDayType
                    if ods_data.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                        patterns_aligned += 1

                # Check intraday structure alignment
                if hasattr(intraday_structure, 'continuation_type'):
                    if intraday_structure.continuation_type in ['PULLBACK_TO_VWAP', 'HIGHER_LOW']:
                        patterns_aligned += 1

                if hasattr(intraday_structure, 'liquidity_sweep_detected'):
                    if intraday_structure.liquidity_sweep_detected:
                        sweep_dir = getattr(intraday_structure, 'sweep_direction', 'NONE')
                        if sweep_dir == 'BULLISH_RECLAIM':
                            patterns_aligned += 1

                if hasattr(intraday_structure, 'midday_structure'):
                    if intraday_structure.midday_structure == 'IMBALANCE_BULLISH':
                        patterns_aligned += 1

                # Bonus for multiple patterns aligned
                if patterns_aligned >= 2:
                    base += 10.0  # Strong alignment bonus
                    self.logger.debug(
                        f"   📊 Pattern alignment bonus: {patterns_aligned} patterns aligned -> +10 points"
                    )
                elif patterns_aligned == 1:
                    base += 5.0  # Single pattern alignment

            # ENHANCEMENT: Quality Score Bonus
            quality_score = metadata.get('quality_score', 0)
            if quality_score > 80:
                base += 5.0  # High quality setup bonus
                self.logger.debug(f"   ⭐ Quality bonus: {quality_score}/100 -> +5 points")

            # Scale by worker's signal confidence
            confidence_factor = signal.confidence / 100.0
            base *= confidence_factor

            # Weight by context score
            total = (base * 0.7) + (context_score * 0.3)

            return min(total, 100.0)

        except Exception as e:
            self.logger.debug(f"Error calculating total score: {e}")
            return 0.0

    def prioritize_opportunities(self, scored_signals: List[ScoredSignal],
                                max_positions: int,
                                current_positions: int) -> List[ScoredSignal]:
        """
        Prioritize opportunities when portfolio is near capacity

        CAPITAL ALLOCATION OPTIMIZATION:
        When approaching max_positions limit, prioritize best signals
        and reject lower-quality ones to preserve capital for better setups.

        Args:
            scored_signals: All scored signals (sorted by score desc)
            max_positions: Maximum allowed positions
            current_positions: Current number of open positions

        Returns:
            List of signals approved for execution (may be filtered)
        """
        try:
            available_slots = max_positions - current_positions

            if available_slots <= 0:
                self.logger.warning(
                    f"⚠️ Portfolio FULL ({current_positions}/{max_positions}) - "
                    f"Rejecting all new signals"
                )
                return []

            # Filter to signals above threshold
            approved_signals = [s for s in scored_signals if s.total_score >= self.MIN_SCORE_THRESHOLD]

            if len(approved_signals) <= available_slots:
                # Room for all approved signals
                self.logger.info(
                    f"✅ Capital allocation: {len(approved_signals)} signals approved, "
                    f"{available_slots} slots available"
                )
                return approved_signals

            # OPTIMIZATION: Portfolio near capacity - prioritize best signals
            self.logger.info(
                f"⚠️ CAPITAL OPTIMIZATION: {len(approved_signals)} signals but only "
                f"{available_slots} slots -> Selecting top {available_slots}"
            )

            # Sort by total_score (desc), then priority (desc)
            approved_signals.sort(
                key=lambda x: (x.total_score, x.capabilities.priority),
                reverse=True
            )

            # Take only top N signals
            selected = approved_signals[:available_slots]
            rejected = approved_signals[available_slots:]

            # Log selections
            for sig in selected:
                self.logger.info(
                    f"  ✅ APPROVED: {sig.signal.worker_name} {sig.signal.symbol} "
                    f"(score={sig.total_score:.1f}, priority={sig.capabilities.priority})"
                )

            for sig in rejected:
                sig.selected = False
                sig.rejection_reason = f"portfolio_capacity_limit_{sig.total_score:.0f}"
                self.logger.info(
                    f"  ❌ REJECTED: {sig.signal.worker_name} {sig.signal.symbol} "
                    f"(score={sig.total_score:.1f}) - Portfolio capacity"
                )

            return selected

        except Exception as e:
            self.logger.error(f"❌ Error prioritizing opportunities: {e}")
            return scored_signals  # Return all on error


# Singleton instance
_trade_arbiter_instance = None

def get_trade_arbiter() -> TradeArbiter:
    """Get singleton TradeArbiter instance"""
    global _trade_arbiter_instance
    if _trade_arbiter_instance is None:
        _trade_arbiter_instance = TradeArbiter()
    return _trade_arbiter_instance
