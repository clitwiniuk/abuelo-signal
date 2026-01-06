"""
Gap-Go Worker Logic
Worker específico para estrategia Gap & Go
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


class GapGoWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Gap & Go

    Criterios de entrada:
    - Gap >= 8%
    - Volume ratio >= 2.0x
    - Precio en rango smallcap (< $15)

    Criterios de salida:
    - Take profit: 15%
    - Stop loss: 3%
    - Time-based: Fin del día
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="gap_go",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Gap-Go - RELAXED
        self.min_gap = 3.0          # Gap mínimo requerido (%) - RELAXED: Reduced from 8% to 3%
        # Read min_volume_ratio from config (centralized)
        from core.service_locator import get_service_locator
        config = get_service_locator().get_config()
        self.min_volume_ratio = getattr(config, 'min_volume_ratio', 0.7)
        self.min_price = 0.5         # Precio mínimo - RELAXED: From 1.0 to 0.5
        self.max_price = 25.0        # Precio máximo (smallcap focus) - RELAXED: From 15 to 25

        # Entry confirmation tracking (ajustado para estrategia rápida)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 0    # Gap-Go necesita entrada INMEDIATA (0 = sin espera)
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'GAP_GO_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,
                take_profit_pct=15.0,
                quick_target_pct=6.0,
                trailing_activation=3.0,
                trailing_distance=2.0,
                max_position_hours=6.0
            ))

        self.logger.info(
            f"🎯 Gap-Go Worker configured: "
            f"gap>={self.min_gap}%, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Gap-Go (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Gap-Go Pattern Stages:
        1. [25%] Gap detected (>= min_gap)
        2. [50%] Price range & quality validated
        3. [75%] Price ABOVE VWAP (strength confirmed)
        4. [85%] CONSOLIDATION near VWAP (EARLY ENTRY - ready for breakout)
        5. [100%] BREAKOUT momentum (gap expanding, LATE - already moving)

        Early Entry Target: 85% = Consolidation detected, price holding strength

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            # Stage 1: Gap detected (25%)
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            if gap_pct >= self.min_gap:
                completion += 25.0
                self.logger.debug(f"📊 {symbol}: Gap stage (25%) - {gap_pct:.1f}%")
            else:
                return 0.0  # No gap, no pattern

            # Stage 2: Price range & quality (50%)
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)
            catalyst_type = opportunity.get('catalyst_type', '')
            catalyst_strength = opportunity.get('catalyst_strength', 0)

            # Check catalyst (avoid strong catalysts - defer to Daily Plays)
            strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT']
            if catalyst_type in strong_catalysts and catalyst_strength >= 6:
                self.logger.debug(f"📊 {symbol}: Strong catalyst - not Gap-Go pattern")
                return 0.0

            if self.min_price <= current_price <= self.max_price and quality_score >= 50.0:
                completion += 25.0
                self.logger.debug(f"📊 {symbol}: Quality stage (50%)")
            else:
                return completion

            # Stage 3: VWAP Strength Confirmation (75%)
            vwap_price = await self._get_vwap(symbol, current_price, opportunity)

            if vwap_price and current_price >= vwap_price:
                # Price above VWAP = strength confirmed
                completion += 25.0
                self.logger.debug(
                    f"📊 {symbol}: VWAP strength (75%) - ${current_price:.2f} >= ${vwap_price:.2f}"
                )
            else:
                # Price below VWAP = weakness, not ready
                self.logger.debug(
                    f"📊 {symbol}: Price below VWAP (${current_price:.2f} < ${vwap_price:.2f if vwap_price else 0:.2f}) - pattern not ready"
                )
                return completion

            # Stage 4: CONSOLIDATION vs BREAKOUT (85-100%)
            # Detect if consolidating (early entry) or breaking out (late)

            # Check gap momentum:
            # - Gap 8-12% = consolidating, ready for move (EARLY ENTRY)
            # - Gap > 15% = already moving parabolic (LATE, too extended)

            if gap_pct <= 15.0:
                # Consolidation range - early entry window
                completion += 10.0
                self.logger.debug(
                    f"📊 {symbol}: CONSOLIDATION (85%) - gap {gap_pct:.1f}% not extended"
                )
            else:
                # Parabolic move - pattern complete, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: PARABOLIC BREAKOUT - gap {gap_pct:.1f}% extended (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Gap-Go pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f}, "
                f"VWAP=${vwap_price:.2f if vwap_price else 0:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Gap-Go

        ENTRY STRATEGY (PMH BREAKOUT):
        - Calculate PMH (Premarket High 4:00-9:30 AM ET)
        - Wait for consolidation below PMH (15+ minutes)
        - Enter on breakout above PMH with volume confirmation

        FALLBACK: Pattern completion 80-95% if no PMH data

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

            # Get bars for pattern analysis
            bars = self.get_bars_from_opportunity(opportunity)
            current_price = opportunity.get('current_price', 0)

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

            # ============================================================
            # PMH BREAKOUT LOGIC (Primary Entry Logic)
            # ============================================================
            if bars and len(bars) > 0:
                # Calculate PMH from premarket bars
                pmh_price, pmh_time = self._calculate_pmh(bars)

                if pmh_price is not None:
                    self.logger.debug(f"📊 {symbol}: PMH calculated = ${pmh_price:.2f}")

                    # Check if consolidating below PMH
                    is_consolidating = self._detect_pmh_consolidation(bars, pmh_price)

                    if is_consolidating:
                        self.logger.info(
                            f"📊 {symbol}: CONSOLIDATION detected below PMH ${pmh_price:.2f}"
                        )

                        # Check for breakout above PMH
                        is_breakout, volume_ratio = self._detect_pmh_breakout(
                            bars, pmh_price, current_price
                        )

                        if is_breakout:
                            self.logger.info(
                                f"✅ {symbol}: PMH BREAKOUT confirmed! "
                                f"PMH: ${pmh_price:.2f}, Price: ${current_price:.2f}, "
                                f"Volume: {volume_ratio:.1f}x"
                            )
                            return True
                        else:
                            self.logger.info(
                                f"⚪ {symbol}: GAP-GO REJECTED - Consolidating but no breakout yet "
                                f"(volume ratio: {volume_ratio:.1f}x < 1.5x required)"
                            )
                            return False
                    else:
                        self.logger.info(
                            f"⚪ {symbol}: GAP-GO REJECTED - Not consolidating below PMH"
                        )
                        return False
                else:
                    self.logger.info(
                        f"⚪ {symbol}: GAP-GO REJECTED - No PMH data available"
                    )

            # ============================================================
            # FALLBACK: Pattern completion logic (if no PMH data)
            # ============================================================
            completion = await self.calculate_pattern_completion(opportunity)

            # EARLY ENTRY LOGIC:
            # - 0-79%: Pattern not ready, reject
            # - 80-95%: OPTIMAL entry window (consolidation ready for breakout)
            # - 96-100%: Too late, breakout already happening

            if completion < 80.0:
                self.logger.info(
                    f"⚪ {symbol}: GAP-GO REJECTED - Pattern not ready {completion:.0f}% < 80%"
                )
                return False

            if completion > 95.0:
                self.logger.info(
                    f"⚪ {symbol}: GAP-GO REJECTED - Pattern too complete {completion:.0f}% > 95%"
                )
                return False

            # Enter with fallback logic
            self.logger.info(
                f"✅ {symbol}: GAP-GO FALLBACK ENTRY APPROVED - Pattern {completion:.0f}% complete"
            )

            # Clean up any pending entries tracking
            if symbol in self.pending_entries:
                del self.pending_entries[symbol]

            return True

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
        Evalúa si debe salir de posición según criterios Gap-Go

        Exit Priority Order:
        0. STUFFED MOVE (failed PMH breakout - IMMEDIATE EXIT)
        1. FOMO Exhaustion
        2. Trailing Stop
        3. Take Profit
        4. Stop Loss
        5. Time Limit
        6. EOD Exit

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

            # Get market data for exit analysis
            market_data = None
            bars = None
            try:
                # Get recent bars for FOMO and PMH analysis
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='1 D',  # Full day for PMH calculation
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=False  # Include premarket for PMH
                )
                if bars:
                    market_data = {
                        'bars': bars,
                        'symbol': symbol,
                        'current_price': current_price
                    }
            except Exception as e:
                self.logger.debug(f"Could not get market data for exit analysis: {e}")

            # ============================================================
            # PRIORITY 0: STUFFED MOVE (failed breakout - IMMEDIATE EXIT)
            # ============================================================
            if bars and len(bars) > 0:
                # Calculate PMH
                pmh_price, pmh_time = self._calculate_pmh(bars)

                if pmh_price is not None:
                    # Check for stuffed move (failed breakout)
                    is_stuffed = self._detect_stuffed_move(bars, pmh_price, current_price)

                    if is_stuffed:
                        # Calculate PnL for logging
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        self.logger.warning(
                            f"🚨 {symbol}: STUFFED MOVE detected - IMMEDIATE EXIT! "
                            f"PMH: ${pmh_price:.2f}, Current: ${current_price:.2f}, "
                            f"PnL: {pnl_pct:+.2f}%"
                        )
                        return True, f"STUFFED_MOVE (PnL: {pnl_pct:+.2f}%)"

            # ============================================================
            # PRIORITY 1-6: Standard exit conditions via stop manager
            # ============================================================
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
                        'strategy': 'gap_go',
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

    async def _get_vwap(self, symbol: str, fallback_price: float, opportunity: Dict[str, Any] = None) -> float:
        """
        Obtiene el VWAP del día para el símbolo
        DEPRECATED: Use calculate_vwap_from_bars() from base class instead

        Args:
            symbol: Símbolo a consultar
            fallback_price: Precio a usar si falla el cálculo
            opportunity: Opportunity dict que puede contener bars_history

        Returns:
            VWAP price o None si no se puede calcular
        """
        # Use base class helper function
        bars = self.get_bars_from_opportunity(opportunity) if opportunity else []

        if bars and len(bars) > 0:
            return self.calculate_vwap_from_bars(bars)

        # Fallback: fetch from IBKR if no bars in opportunity
        try:
            from ib_insync import Stock
            from datetime import datetime
            import pytz

            eastern = pytz.timezone('US/Eastern')
            now = datetime.now(eastern)
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

            if now < market_open:
                return None

            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            return self.calculate_vwap_from_bars(bars) if bars else None

        except Exception as e:
            self.logger.debug(f"Could not fetch bars for VWAP: {e}")
            return None

    # ========================================================================
    # PMH (PREMARKET HIGH) BREAKOUT DETECTION
    # Migrated from gap_go_strategy.py according to MIGRATION_PLAN_READY.md
    # ========================================================================

    def _calculate_pmh(self, bars: list) -> Tuple[float, Any]:
        """
        Calculate Premarket High (4:00 - 9:30 AM ET)

        PMH Strategy:
        - Identify highest price during premarket session
        - Wait for consolidation below PMH
        - Enter on breakout above PMH with volume

        Args:
            bars: List of 1-minute bars (should include premarket data)

        Returns:
            Tuple (pmh_price, pmh_time) or (None, None) if no premarket data
        """
        try:
            if not bars or len(bars) == 0:
                return None, None

            from datetime import datetime
            import pytz

            eastern = pytz.timezone('US/Eastern')
            market_open_hour = 9
            market_open_minute = 30
            premarket_start_hour = 4

            # Filter bars for premarket period (4:00 - 9:30 AM ET)
            premarket_bars = []

            for bar in bars:
                # Convert bar timestamp to ET
                if hasattr(bar, 'timestamp'):
                    bar_time = bar.timestamp
                    if isinstance(bar_time, str):
                        from dateutil import parser
                        bar_time = parser.parse(bar_time)

                    # Make timezone aware if needed
                    if bar_time.tzinfo is None:
                        bar_time = eastern.localize(bar_time)
                    else:
                        bar_time = bar_time.astimezone(eastern)

                    hour = bar_time.hour
                    minute = bar_time.minute

                    # Check if in premarket window
                    if (hour >= premarket_start_hour and
                        (hour < market_open_hour or (hour == market_open_hour and minute < market_open_minute))):
                        premarket_bars.append(bar)

            if not premarket_bars:
                return None, None

            # Find highest price in premarket
            pmh_bar = max(premarket_bars, key=lambda b: b.high)
            pmh_price = pmh_bar.high
            pmh_time = pmh_bar.timestamp

            return pmh_price, pmh_time

        except Exception as e:
            self.logger.error(f"❌ Error calculating PMH: {e}")
            return None, None

    def _detect_pmh_consolidation(self, bars: list, pmh_price: float,
                                  min_consolidation_minutes: int = 15) -> bool:
        """
        Detect consolidation below PMH

        Consolidation criteria:
        - Price trading below PMH for min_consolidation_minutes
        - Price staying within tight range (< 3%)
        - Volume declining (not pumping yet)

        Args:
            bars: List of bars after market open
            pmh_price: Premarket high price
            min_consolidation_minutes: Minimum minutes of consolidation required

        Returns:
            True if consolidating below PMH, False otherwise
        """
        try:
            if not bars or pmh_price is None:
                return False

            from datetime import datetime
            import pytz

            eastern = pytz.timezone('US/Eastern')
            market_open_hour = 9
            market_open_minute = 30

            # Filter bars after market open
            market_bars = []

            for bar in bars:
                if hasattr(bar, 'timestamp'):
                    bar_time = bar.timestamp
                    if isinstance(bar_time, str):
                        from dateutil import parser
                        bar_time = parser.parse(bar_time)

                    if bar_time.tzinfo is None:
                        bar_time = eastern.localize(bar_time)
                    else:
                        bar_time = bar_time.astimezone(eastern)

                    hour = bar_time.hour
                    minute = bar_time.minute

                    # Only bars after 9:30 AM
                    if hour > market_open_hour or (hour == market_open_hour and minute >= market_open_minute):
                        market_bars.append(bar)

            if len(market_bars) < min_consolidation_minutes:
                return False

            # Take last N bars for consolidation check
            recent_bars = market_bars[-min_consolidation_minutes:]

            # Check all bars are below PMH (allowing 1% tolerance)
            pmh_threshold = pmh_price * 1.01
            all_below_pmh = all(bar.high < pmh_threshold for bar in recent_bars)

            if not all_below_pmh:
                return False

            # Check tight consolidation range (< 3%)
            highs = [bar.high for bar in recent_bars]
            lows = [bar.low for bar in recent_bars]

            high_range = max(highs)
            low_range = min(lows)

            if low_range == 0:
                return False

            range_pct = ((high_range - low_range) / low_range) * 100

            if range_pct >= 3.0:
                return False

            # All consolidation criteria met
            return True

        except Exception as e:
            self.logger.error(f"❌ Error detecting PMH consolidation: {e}")
            return False

    def _detect_pmh_breakout(self, bars: list, pmh_price: float,
                            current_price: float) -> Tuple[bool, float]:
        """
        Detect breakout above PMH

        Breakout criteria:
        - Price breaks above PMH by 0.5%+
        - Volume spike (>= 1.5x avg consolidation volume)
        - Close above PMH (confirmation)

        Args:
            bars: List of recent bars
            pmh_price: Premarket high price
            current_price: Current price

        Returns:
            Tuple (is_breakout, volume_ratio)
        """
        try:
            if not bars or pmh_price is None:
                return False, 0.0

            # Breakout threshold (0.5% above PMH)
            breakout_threshold = pmh_price * 1.005

            # Check if current price is breaking out
            if current_price < breakout_threshold:
                return False, 0.0

            # Get recent consolidation bars (last 15 bars before current)
            if len(bars) < 16:
                return False, 0.0

            consolidation_bars = bars[-16:-1]  # Exclude current bar
            current_bar = bars[-1]

            # Calculate average consolidation volume
            consol_volumes = [bar.volume for bar in consolidation_bars if bar.volume > 0]

            if not consol_volumes:
                return False, 0.0

            avg_consol_volume = sum(consol_volumes) / len(consol_volumes)

            # Check current bar volume spike
            if current_bar.volume == 0 or avg_consol_volume == 0:
                return False, 0.0

            volume_ratio = current_bar.volume / avg_consol_volume

            # Volume must be >= 1.5x consolidation average
            if volume_ratio < 1.5:
                return False, volume_ratio

            # Confirm close above PMH
            if current_bar.close <= pmh_price:
                return False, volume_ratio

            # BREAKOUT CONFIRMED
            return True, volume_ratio

        except Exception as e:
            self.logger.error(f"❌ Error detecting PMH breakout: {e}")
            return False, 0.0

    def _detect_stuffed_move(self, bars: list, pmh_price: float,
                            current_price: float) -> bool:
        """
        Detect stuffed move (failed breakout) - CRITICAL EXIT SIGNAL

        Stuffed move criteria:
        - Price spiked above PMH but rejected back below
        - High volume on rejection (> 2x recent average)
        - Close back below PMH

        This is an IMMEDIATE EXIT signal - the breakout failed

        Args:
            bars: List of recent bars
            pmh_price: Premarket high price
            current_price: Current price

        Returns:
            True if stuffed move detected (EXIT NOW), False otherwise
        """
        try:
            if not bars or pmh_price is None or len(bars) < 5:
                return False

            current_bar = bars[-1]
            recent_bars = bars[-5:]

            # Check if we had a spike above PMH (at least 2% above)
            spike_threshold = pmh_price * 1.02

            # Did price spike above PMH in recent bars?
            had_spike = any(bar.high > spike_threshold for bar in recent_bars)

            if not had_spike:
                return False

            # Is current price now below PMH? (rejection)
            if current_price >= pmh_price:
                return False

            # Check for volume explosion on rejection
            recent_volumes = [bar.volume for bar in recent_bars[:-1] if bar.volume > 0]

            if not recent_volumes:
                return False

            avg_recent_volume = sum(recent_volumes) / len(recent_volumes)

            if current_bar.volume == 0 or avg_recent_volume == 0:
                return False

            volume_ratio = current_bar.volume / avg_recent_volume

            # Volume explosion (> 2x) confirms stuffed move
            if volume_ratio > 2.0:
                self.logger.warning(
                    f"🚨 STUFFED MOVE detected! "
                    f"High: ${current_bar.high:.2f}, Close: ${current_price:.2f}, "
                    f"PMH: ${pmh_price:.2f}, Volume: {volume_ratio:.1f}x"
                )
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error detecting stuffed move: {e}")
            return False