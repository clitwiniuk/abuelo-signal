"""
Bull Flag Worker Logic
Worker específico para estrategia Bull Flag (Pattern-based continuation)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


class BullFlagWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Bull Flag

    Enfoque: Pattern-based trading (continuation patterns)
    Ideal para movimientos con consolidación ordenada después de impulso

    Criterios de entrada:
    - Gap moderado (3-8%) - No muy grande, no muy pequeño
    - Volume ratio >= 2.0x (momentum confirmado)
    - Precio en rango smallcap ($1-$15)
    - Pattern quality indicators (consolidation)
    - No gaps extremos (queremos patrones limpios)

    Criterios de salida:
    - Take profit: 15% (projection of flagpole)
    - Stop loss: 5% (below flag low)
    - Trailing stop: 10% activation, 4% distance
    - Time-based: 6 horas máximo
    - Pattern invalidation detection
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="bull_flag",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Bull Flag - RELAXED
        self.min_gap = 1.0            # Gap mínimo para flagpole - RELAXED: From 3% to 1%
        self.max_gap = 15.0           # Gap máximo - RELAXED: From 8% to 15%
        # Read min_volume_ratio from config (centralized) - already imported above
        self.min_volume_ratio = getattr(config, 'min_volume_ratio', 0.7)
        self.min_price = 0.5          # Precio mínimo - RELAXED: From 1.0 to 0.5
        self.max_price = 25.0         # Precio máximo (smallcaps) - RELAXED: From 15 to 25

        # Time-based - REMOVED: Allow all trading hours including extended
        self.min_hour = 4.0   # Allow from premarket start
        self.max_hour = 20.0  # Allow until afterhours end

        # Entry confirmation tracking (cooldown entre entradas)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 2    # Número de scans consecutivos antes de entrar
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Bull Flag pattern detection state machine
        self.pattern_states = {}      # {symbol: 'SCANNING' | 'POLE' | 'FLAG' | 'BREAKOUT'}
        self.flagpole_data = {}       # {symbol: {start_price, high_price, start_time, ...}}
        self.flag_data = {}           # {symbol: {high_price, low_price, consolidation_bars, ...}}
        self.volume_profile = {}      # {symbol: {flagpole_vol: [], flag_vol: []}}

        # Bull Flag parameters
        self.min_flagpole_pct = 30.0      # Min pole gain %
        self.max_flagpole_pct = 60.0      # Max pole gain %
        self.min_flagpole_minutes = 5     # Min pole duration
        self.max_flagpole_minutes = 30    # Max pole duration
        self.min_flag_pullback_pct = 5.0  # Min flag retracement %
        self.max_flag_pullback_pct = 20.0 # Max flag retracement %
        self.min_flag_minutes = 5         # Min flag duration
        self.max_flag_minutes = 20        # Max flag duration
        self.max_formation_minutes = 60   # Max total pattern time
        self.breakout_threshold_pct = 1.0 # Breakout % above flag high
        self.breakout_volume_multiplier = 1.5  # Breakout volume multiplier

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'BULL_FLAG_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,
                take_profit_pct=15.0,
                quick_target_pct=None,
                trailing_activation=10.0,
                trailing_distance=4.0,
                max_position_hours=6.0
            ))

        self.logger.info(
            f"🎯 Bull Flag Worker configured: "
            f"gap={self.min_gap}-{self.max_gap}%, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Bull Flag (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Bull Flag Pattern Stages:
        1. [33%] Pole detected (gap in range 3-8%)
        2. [66%] Flag range + quality + hours validated
        3. [85%] FLAG CONSOLIDATION (EARLY ENTRY - gap in sweet spot, not extended)
        4. [100%] PARABOLIC EXTENSION (LATE - gap too large, already moved)

        Early Entry Target: 85% = Flag consolidating in sweet spot

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            gap_pct = abs(opportunity.get('gap_percentage', 0))
            current_price = opportunity.get('current_price', 0)
            catalyst_type = opportunity.get('catalyst_type', '')
            quality_score = opportunity.get('quality_score', 0)

            # Stage 1: Pole detected (33%)
            # Pole = initial strong move (gap in range)
            if self.min_gap <= gap_pct <= self.max_gap:
                completion += 33.0
                self.logger.debug(
                    f"📊 {symbol}: Pole stage (33%) - gap {gap_pct:.1f}%"
                )
            else:
                return 0.0

            # Check catalyst (avoid extreme ones)
            extreme_catalysts = ['FDA', 'M&A', 'EARNINGS']
            if catalyst_type in extreme_catalysts:
                self.logger.debug(f"📊 {symbol}: Extreme catalyst - not Bull Flag")
                return 0.0

            # Stage 2: Flag range + quality + hours (66%)
            import pytz
            from datetime import datetime
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)
            current_hour = now_et.hour + now_et.minute / 60

            if self.min_price <= current_price <= self.max_price:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Price range (44%)")
            else:
                return completion

            if quality_score >= 50.0:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Quality validated (55%)")
            else:
                return completion

            if self.min_hour <= current_hour <= self.max_hour:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Trading hours (66%)")
            else:
                # REMOVED: No time restrictions for testing - allow all trading hours
                # self.logger.warning(f"⚠️ {symbol}: OUTSIDE TRADING HOURS - current: {current_hour:.2f}, allowed: {self.min_hour:.2f}-{self.max_hour:.2f}")
                # return 0.0  # STRICT REJECTION - no entry outside hours
                pass  # Continue with pattern analysis

            # Stage 3: FLAG CONSOLIDATION vs BREAKOUT (85-100%)
            # Detect if consolidating in sweet spot (early) or extended (late)

            # Check gap sweet spot:
            # - Gap 4-7% = clean flag consolidation (EARLY ENTRY)
            # - Gap > 7.5% = extended, likely breaking out (LATE)

            if gap_pct <= 7.5:
                # Consolidation sweet spot - early entry window
                completion += 19.0
                self.logger.debug(
                    f"📊 {symbol}: FLAG CONSOLIDATION (85%) - gap {gap_pct:.1f}% in sweet spot"
                )
            else:
                # Extended move - breakout happening or done, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: FLAG EXTENSION - gap {gap_pct:.1f}% too large (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Bull Flag pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Bull Flag

        PATTERN DETECTION STRATEGY (State Machine):
        - SCANNING -> Look for flagpole start
        - POLE -> Wait for flagpole complete
        - FLAG -> Wait for breakout
        - BREAKOUT -> ENTER!

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # ============================================================
            # CRITICAL VALIDATION 0: Check for duplicate positions
            # ============================================================
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading"
                )
                return False

            current_price = opportunity.get('current_price', 0)
            bars = self.get_bars_from_opportunity(opportunity)

            self.logger.info(f"🔍 DEBUG {symbol}: Starting evaluation - bars={len(bars) if bars else 0}, price=${current_price:.2f}")

            # ============================================================
            # CRITICAL VALIDATION 1: VWAP strength check (universal filter)
            # ============================================================
            if bars and current_price > 0:
                vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price, opportunity=opportunity)

                if not vwap_valid:
                    self.logger.warning(
                        f"❌ {symbol}: REJECTED by VWAP filter - {vwap_reason}"
                    )
                    return False

                self.logger.info(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")
            else:
                self.logger.warning(f"⚠️ {symbol}: No bars or price=0, skipping VWAP validation")

            # ============================================================
            # BULL FLAG PATTERN STATE MACHINE
            # ============================================================
            if not bars or len(bars) < 10:
                self.logger.info(f"⚪ {symbol}: BULL_FLAG REJECTED - Not enough bars ({len(bars) if bars else 0} < 10)")
                return False

            # Get current pattern state
            current_state = self.pattern_states.get(symbol, 'SCANNING')
            self.logger.info(f"📊 DEBUG {symbol}: Current pattern state = {current_state}")

            if current_state == 'SCANNING':
                # Look for flagpole start
                if self._detect_flagpole_start(symbol, bars):
                    self.pattern_states[symbol] = 'POLE'
                    self.logger.info(f"🚩 {symbol}: State -> POLE (flagpole detected)")
                    return False  # Not entry yet, just detected start
                else:
                    self.logger.info(f"⚪ {symbol}: BULL_FLAG REJECTED - SCANNING state, no flagpole detected")
                    return False

            elif current_state == 'POLE':
                # Check if flagpole complete
                if self._is_flagpole_complete(symbol, bars):
                    self.pattern_states[symbol] = 'FLAG'
                    self.logger.info(f"🏁 {symbol}: State -> FLAG (flagpole complete, watching for flag)")
                    return False  # Wait for flag consolidation

                elif self._is_flagpole_failed(symbol, bars):
                    # Flagpole failed, reset
                    self.logger.warning(f"⚠️ {symbol}: Flagpole failed, resetting pattern")
                    self._reset_pattern_state(symbol)
                    return False
                else:
                    self.logger.info(f"⚪ {symbol}: BULL_FLAG REJECTED - POLE state, flagpole in progress")
                    return False

            elif current_state == 'FLAG':
                # Check for breakout
                if self._detect_flag_breakout(symbol, bars):
                    # ENTRY SIGNAL - Pattern complete!
                    flagpole = self.flagpole_data.get(symbol, {})
                    flag = self.flag_data.get(symbol, {})

                    pole_gain = ((flagpole.get('high_price', 0) - flagpole.get('start_price', 1)) /
                                flagpole.get('start_price', 1)) * 100
                    flag_pullback = ((flag.get('high_price', 0) - flag.get('low_price', 0)) /
                                    flag.get('high_price', 1)) * 100

                    self.logger.info(
                        f"✅ {symbol}: BULL FLAG BREAKOUT ENTRY! "
                        f"Pole: {pole_gain:.1f}%, Flag: {flag_pullback:.1f}%"
                    )

                    # Clean up pattern state
                    self._reset_pattern_state(symbol)

                    # Clean up any pending entries tracking
                    if symbol in self.pending_entries:
                        del self.pending_entries[symbol]

                    return True

                elif self._is_flag_failed(symbol, bars):
                    # Flag failed, reset
                    self.logger.warning(f"⚠️ {symbol}: Flag failed, resetting pattern")
                    self._reset_pattern_state(symbol)
                    return False
                else:
                    self.logger.info(f"⚪ {symbol}: BULL_FLAG REJECTED - FLAG state, no breakout yet")
                    return False

            # No entry conditions met
            self.logger.info(f"⚪ {symbol}: BULL_FLAG REJECTED - Unknown state or no conditions met")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            return False

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios Bull Flag

        Criterios de salida:
        1. Take profit: PnL >= 15% (flagpole projection)
        2. Stop loss: PnL <= -5% (below flag low)
        3. Trailing stop: Si PnL >= 10%, activar trailing a 4%
        4. Time-based: Más de 6 horas en posición
        5. EOD: Close cerca del cierre de mercado (15:45)

        Args:
            symbol: Símbolo de la posición
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            (should_exit, reason): Tupla con decisión y motivo
        """
        try:
            entry_price = position.get('entry_price', 0)

            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price")
                return False, ""

            # Get market data for FOMO detection
            market_data = None
            try:
                # Get recent bars for FOMO analysis
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='300 S',  # 5 minutes = 300 seconds
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True
                )
                if bars:
                    market_data = {
                        'bars': bars,
                        'symbol': symbol,
                        'current_price': current_price
                    }
            except Exception as e:
                self.logger.debug(f"Could not get market data for FOMO detection: {e}")

            # Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager AND unified position manager"""
        # Execute normal entry
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager for tracking
            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} with stop manager")

            # Register with unified position manager (prevent duplicates)
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 200.0)  # Default day trading position

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='day',
                    position_data={
                        'strategy': 'bull_flag',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (DAY trading)")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager AND unified position manager"""
        # Calculate PnL before unregistering (for post-exit cooldown)
        pnl_pct = None

        # Get position data from unified position manager to calculate PnL
        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()

        if unified_manager:
            position_data = unified_manager.get_position(symbol)
            if position_data:
                entry_price = position_data.get('entry_price', 0)
                if entry_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    self.logger.debug(f"📊 {symbol} exit PnL: {pnl_pct:.2f}% (entry: ${entry_price:.2f}, exit: ${current_price:.2f})")

        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Unregister from unified position manager with PnL data for cooldown
        if unified_manager:
            unified_manager.unregister_position(symbol, 'day', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (DAY trading)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    # ========================================================================
    # BULL FLAG PATTERN DETECTION
    # Migrated from bull_flag_strategy.py according to MIGRATION_PLAN_READY.md
    # ========================================================================

    def _reset_pattern_state(self, symbol: str) -> None:
        """Reset pattern state for a symbol"""
        self.pattern_states.pop(symbol, None)
        self.flagpole_data.pop(symbol, None)
        self.flag_data.pop(symbol, None)
        self.volume_profile.pop(symbol, None)
        self.logger.debug(f"🔄 {symbol}: Pattern state reset")

    def _detect_flagpole_start(self, symbol: str, bars: list) -> bool:
        """
        Detect start of potential flagpole (strong upward move beginning)

        Flagpole start criteria:
        - Price jump >= 1.5% from prev avg
        - Volume >= 1.3x prev avg
        - Green bar (close > open)

        Args:
            symbol: Symbol to check
            bars: List of recent bars (need at least 5 bars)

        Returns:
            True if flagpole start detected, False otherwise
        """
        try:
            if len(bars) < 5:
                return False

            recent_bars = bars[-10:] if len(bars) >= 10 else bars
            if len(recent_bars) < 5:
                return False

            current_bar = recent_bars[-1]
            prev_bars = recent_bars[-5:-1]  # Previous 4 bars

            # Check for price acceleration
            prev_avg_close = sum(b.close for b in prev_bars) / len(prev_bars)
            price_jump = (current_bar.close - prev_avg_close) / prev_avg_close

            # Check for volume spike
            prev_avg_volume = sum(b.volume for b in prev_bars) / len(prev_bars)
            volume_ratio = current_bar.volume / prev_avg_volume if prev_avg_volume > 0 else 1.0

            # Flagpole start criteria
            if (price_jump >= 0.015 and  # 1.5% jump minimum
                volume_ratio >= 1.3 and  # 1.3x volume increase
                current_bar.close > current_bar.open):  # Green bar

                # Initialize flagpole tracking
                self.flagpole_data[symbol] = {
                    'start_time': current_bar.timestamp,
                    'start_price': prev_avg_close,
                    'start_bar_idx': len(bars) - 1,
                    'high_price': current_bar.high,
                    'high_time': current_bar.timestamp
                }

                # Initialize volume tracking
                self.volume_profile[symbol] = {
                    'flagpole_vol': [current_bar.volume],
                    'flag_vol': []
                }

                self.logger.info(
                    f"🚩 {symbol}: FLAGPOLE START detected - "
                    f"Jump: {price_jump*100:.1f}%, Volume: {volume_ratio:.1f}x, "
                    f"Start: ${prev_avg_close:.2f}"
                )
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error detecting flagpole start for {symbol}: {e}")
            return False

    def _is_flagpole_complete(self, symbol: str, bars: list) -> bool:
        """
        Check if flagpole formation is complete

        Flagpole complete criteria:
        - Total gain: 30-60%
        - Time: 5-30 minutes
        - Pullback started (0.5% from high)

        Args:
            symbol: Symbol to check
            bars: List of bars

        Returns:
            True if flagpole complete, False if still forming
        """
        try:
            if symbol not in self.flagpole_data or len(bars) == 0:
                return False

            flagpole = self.flagpole_data[symbol]
            current_bar = bars[-1]

            # Update flagpole high if current bar is higher
            if current_bar.high > flagpole['high_price']:
                flagpole['high_price'] = current_bar.high
                flagpole['high_time'] = current_bar.timestamp
                self.volume_profile[symbol]['flagpole_vol'].append(current_bar.volume)
                return False  # Still extending

            # Check if we've started to pullback (flag formation)
            pullback_from_high = (flagpole['high_price'] - current_bar.close) / flagpole['high_price']

            # Flagpole complete if we see pullback and meet minimum requirements
            if pullback_from_high >= 0.005:  # 0.5% pullback from high
                # Validate flagpole meets requirements
                total_gain = (flagpole['high_price'] - flagpole['start_price']) / flagpole['start_price'] * 100

                # Calculate time elapsed
                from datetime import datetime
                start_time = flagpole['start_time']
                high_time = flagpole['high_time']

                if isinstance(start_time, str):
                    from dateutil import parser
                    start_time = parser.parse(start_time)
                if isinstance(high_time, str):
                    from dateutil import parser
                    high_time = parser.parse(high_time)

                time_elapsed = (high_time - start_time).total_seconds() / 60

                if (self.min_flagpole_pct <= total_gain <= self.max_flagpole_pct and
                    self.min_flagpole_minutes <= time_elapsed <= self.max_flagpole_minutes):

                    # Initialize flag tracking
                    self.flag_data[symbol] = {
                        'start_time': current_bar.timestamp,
                        'start_price': current_bar.close,
                        'high_price': flagpole['high_price'],  # Flag high = flagpole high
                        'low_price': current_bar.low,
                        'consolidation_bars': 1
                    }

                    self.logger.info(
                        f"✅ {symbol}: FLAGPOLE COMPLETE - "
                        f"Gain: {total_gain:.1f}%, Time: {time_elapsed:.1f}min, "
                        f"High: ${flagpole['high_price']:.2f}"
                    )
                    return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking flagpole complete for {symbol}: {e}")
            return False

    def _is_flagpole_failed(self, symbol: str, bars: list) -> bool:
        """
        Check if flagpole formation has failed

        Failure criteria:
        - Time > max_flagpole_minutes
        - Price < start price (lost all gains)

        Args:
            symbol: Symbol to check
            bars: List of bars

        Returns:
            True if flagpole failed, False otherwise
        """
        try:
            if symbol not in self.flagpole_data or len(bars) == 0:
                return True

            flagpole = self.flagpole_data[symbol]
            current_bar = bars[-1]

            from datetime import datetime
            start_time = flagpole['start_time']
            current_time = current_bar.timestamp

            if isinstance(start_time, str):
                from dateutil import parser
                start_time = parser.parse(start_time)
            if isinstance(current_time, str):
                from dateutil import parser
                current_time = parser.parse(current_time)

            time_elapsed = (current_time - start_time).total_seconds() / 60

            # Failed if too much time has passed
            if time_elapsed > self.max_flagpole_minutes:
                self.logger.warning(
                    f"⚠️ {symbol}: FLAGPOLE FAILED - Timeout ({time_elapsed:.1f}min > {self.max_flagpole_minutes}min)"
                )
                return True

            # Failed if price dropped too much from start
            current_gain = (current_bar.close - flagpole['start_price']) / flagpole['start_price']
            if current_gain < 0:  # Below starting point
                self.logger.warning(
                    f"⚠️ {symbol}: FLAGPOLE FAILED - Price below start (${current_bar.close:.2f} < ${flagpole['start_price']:.2f})"
                )
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking flagpole failed for {symbol}: {e}")
            return True

    def _detect_flag_breakout(self, symbol: str, bars: list) -> bool:
        """
        Detect breakout above flag consolidation

        Breakout criteria:
        - Price > flag_high * 1.01 (1% above)
        - Volume >= 1.5x avg flag volume
        - Close above breakout level (confirmation)

        Args:
            symbol: Symbol to check
            bars: List of bars

        Returns:
            True if breakout detected, False otherwise
        """
        try:
            if symbol not in self.flag_data or len(bars) == 0:
                return False

            flag = self.flag_data[symbol]
            current_bar = bars[-1]

            breakout_threshold = flag['high_price'] * (1 + self.breakout_threshold_pct / 100)

            # Check if we've broken above flag high
            if current_bar.high >= breakout_threshold:
                # Validate volume confirmation
                recent_flag_vol = self.volume_profile[symbol]['flag_vol']
                avg_flag_vol = sum(recent_flag_vol) / len(recent_flag_vol) if recent_flag_vol else current_bar.volume

                volume_ratio = current_bar.volume / avg_flag_vol if avg_flag_vol > 0 else 1.0

                if volume_ratio >= self.breakout_volume_multiplier:
                    self.logger.info(
                        f"🔥 {symbol}: FLAG BREAKOUT detected! "
                        f"Price: ${current_bar.high:.2f} > Threshold: ${breakout_threshold:.2f}, "
                        f"Volume: {volume_ratio:.1f}x"
                    )
                    return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error detecting flag breakout for {symbol}: {e}")
            return False

    def _is_flag_failed(self, symbol: str, bars: list) -> bool:
        """
        Check if flag formation has failed

        Failure criteria:
        - Pullback > 20% (too deep)
        - Time > max_flag_minutes
        - Close < flag start * 0.95 (breakdown)

        Args:
            symbol: Symbol to check
            bars: List of bars

        Returns:
            True if flag failed, False otherwise
        """
        try:
            if symbol not in self.flag_data or len(bars) == 0:
                return True

            flag = self.flag_data[symbol]
            flagpole = self.flagpole_data.get(symbol)
            if not flagpole:
                return True

            current_bar = bars[-1]

            # Update flag data
            flag['low_price'] = min(flag['low_price'], current_bar.low)
            flag['consolidation_bars'] += 1
            self.volume_profile[symbol]['flag_vol'].append(current_bar.volume)

            # Check time limits
            from datetime import datetime
            flag_start_time = flag['start_time']
            flagpole_start_time = flagpole['start_time']
            current_time = current_bar.timestamp

            if isinstance(flag_start_time, str):
                from dateutil import parser
                flag_start_time = parser.parse(flag_start_time)
            if isinstance(flagpole_start_time, str):
                from dateutil import parser
                flagpole_start_time = parser.parse(flagpole_start_time)
            if isinstance(current_time, str):
                from dateutil import parser
                current_time = parser.parse(current_time)

            flag_time = (current_time - flag_start_time).total_seconds() / 60
            total_time = (current_time - flagpole_start_time).total_seconds() / 60

            if flag_time > self.max_flag_minutes:
                self.logger.warning(
                    f"⚠️ {symbol}: FLAG FAILED - Timeout ({flag_time:.1f}min > {self.max_flag_minutes}min)"
                )
                return True

            if total_time > self.max_formation_minutes:
                self.logger.warning(
                    f"⚠️ {symbol}: FLAG FAILED - Total pattern timeout ({total_time:.1f}min > {self.max_formation_minutes}min)"
                )
                return True

            # Check if pullback is too deep
            pullback_pct = (flag['high_price'] - flag['low_price']) / flag['high_price'] * 100
            if pullback_pct > self.max_flag_pullback_pct:
                self.logger.warning(
                    f"⚠️ {symbol}: FLAG FAILED - Pullback too deep ({pullback_pct:.1f}% > {self.max_flag_pullback_pct}%)"
                )
                return True

            # Check if trend is breaking down
            if current_bar.close < flag['start_price'] * 0.95:  # 5% below flag start
                self.logger.warning(
                    f"⚠️ {symbol}: FLAG FAILED - Breakdown (${current_bar.close:.2f} < ${flag['start_price']*0.95:.2f})"
                )
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking flag failed for {symbol}: {e}")
            return True