"""
Momentum Breakout Worker Logic
Worker especializado para breakouts de momentum intraday
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradingHorizon


class MomentumBreakoutWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Momentum Breakout

    Enfoque: Breakouts de momentum puro sin requerir patrones técnicos complejos
    Ideal para capturar movimientos oportunistas que otros workers ignoran

    Criterios de entrada:
    - Precio rompe máximo/mínimo de últimas N barras
    - Volumen confirma el breakout (ratio mínimo)
    - Momentum confirmado (últimas X barras cerrando en misma dirección)
    - Filtros básicos de precio y liquidez

    Criterios de salida (CALIBRADOS para small caps):
     - Take profit: 10% (balance entre agresivo y realista)
     - Stop loss: 4% (amplio para volatilidad)
     - Trailing stop: 3% activation, 2.0% distance
     - Time-based exit: máximo 4 horas
     - Quick target: DISABLED (dejar que el momentum se desarrolle)
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="momentum_breakout",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración Momentum Breakout específica - LEE DESDE CONFIG.INI
        self.lookback_bars = getattr(config, 'lookback_bars', 5)  # Barras para detectar breakout
        self.min_volume_ratio = getattr(config, 'min_volume_ratio', 1.2)  # Ratio volumen mínimo
        self.min_price = getattr(config, 'min_price', 1.0)  # Precio mínimo
        self.max_price = getattr(config, 'max_price', 25.0)  # Precio máximo
        self.momentum_bars = getattr(config, 'momentum_bars', 3)  # Barras consecutivas en misma dirección

        # Initialize config attribute for _is_extended_hours_allowed method
        self.config = config

        # Initialize stop manager with momentum-specific parameters
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'MOMENTUM_BREAKOUT_STRATEGY')
        else:
            # Fallback: create with SMALLCAP-appropriate parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=4.0,           # 4% stop loss (más amplio para small caps volátiles)
                take_profit_pct=10.0,        # 10% profit target (balance entre agresivo y realista)
                quick_target_pct=0.0,        # DISABLED - No quick target, let momentum develop
                trailing_activation=3.0,     # Activate trailing at 3% (más conservador)
                trailing_distance=2.0,       # 2% trailing distance (más amplio)
                max_position_hours=4.0       # Max 4 hours (tiempo razonable para momentum)
            ))

        self.logger.info(
            f"🎯 Momentum Breakout Worker configured: "
            f"lookback={self.lookback_bars} bars, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}, momentum={self.momentum_bars} bars | "
            f"Exits: TP=10%, SL=4%, Trail=3%/2.0%, Max=4h, Quick=DISABLED (calibrado para small caps)"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Momentum Breakout (0-100%)

        PATTERN COMPLETION CRITERIA:
        - 40%: Datos básicos disponibles
        - 60%: Breakout detectado
        - 80%: Momentum confirmado + volumen
        - 100%: Setup completo listo para entrada

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            # Get bars for analysis
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < self.lookback_bars + 5:
                return 0.0

            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Stage 1: Basic data validation (40%)
            if current_price > 0 and volume_ratio > 0:
                completion += 40.0
                self.logger.debug(f"📊 {symbol}: Basic data validated")

            # Stage 2: Breakout detection (60%)
            breakout_detected, breakout_direction = self._detect_breakout(bars, current_price)
            if breakout_detected:
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: Breakout detected ({breakout_direction})")

            # Stage 3: Momentum confirmation + Volume (80-100%)
            if breakout_detected:
                momentum_confirmed = self._confirm_momentum(bars, breakout_direction)
                if momentum_confirmed:
                    completion += 20.0
                    self.logger.debug(f"📊 {symbol}: Momentum confirmed")

                    # Volume confirmation for full completion
                    if volume_ratio >= self.min_volume_ratio:
                        completion = 100.0
                        self.logger.info(f"✅ {symbol}: Momentum breakout setup complete (100%)")
                    else:
                        completion += 10.0  # Partial credit for momentum without volume

            self.logger.info(f"📊 {symbol}: Momentum pattern completion = {completion:.0f}%")
            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating momentum pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Momentum Breakout PROFESIONALES

        PROFESSIONAL MOMENTUM BREAKOUT STRATEGY (Mark Minervini / IBD style):
        1. Must be in UPTREND (price > VWAP, higher lows structure)
        2. Breakout from consolidation (NOT from downtrend)
        3. Volume confirmation (surge on breakout)
        4. Price position: NOT extended (< 10% from consolidation low)
        5. Quality filters: proper structure, no bull traps

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            self.logger.info(f"🔍 {symbol}: Starting PROFESSIONAL Momentum Breakout evaluation")

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

            # Get bars for detailed analysis (need more bars for proper structure analysis)
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 30:  # Need at least 30 bars for structure
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0}/30)")
                return False

            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Basic filters
            if not (self.min_price <= current_price <= self.max_price):
                self.logger.info(f"⚪ {symbol}: Price ${current_price:.2f} outside range")
                return False

            if volume_ratio < self.min_volume_ratio:
                self.logger.info(f"⚪ {symbol}: Volume {volume_ratio:.1f}x < min {self.min_volume_ratio:.1f}x")
                return False

            # ============================================================
            # ODS FILTER: Check Opening Drive Structure
            # ============================================================
            from core.ods_classifier import ODSDayType

            ods = await self.get_ods_for_symbol(symbol, bars)

            # Store ODS data for adaptive risk sizing
            opportunity['ods_data'] = ods

            # FILTER 1: Late entries on FAILED DRIVE (avoid false breakouts)
            from datetime import datetime
            # ODS CONTEXTUAL ADJUSTMENT (SMALLCAP-AWARE)
            confidence_boost = 1.0

            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.3  # +30% confidence
                self.logger.info(
                    f"✅ {symbol}: ODS BOOST - Bullish trend drive "
                    f"(strength={ods.strength:.1f}) - Momentum breakouts more reliable"
                )
            elif ods.day_type == ODSDayType.STRONG_BULLISH_OPEN:
                confidence_boost = 1.4  # +40% for strong opens
                self.logger.info(
                    f"🔥 {symbol}: ODS STRONG BOOST - Strong bullish open "
                    f"(strength={ods.strength:.1f}) - High conviction momentum setup"
                )
            elif ods.day_type == ODSDayType.MODERATE_BULLISH_OPEN:
                confidence_boost = 1.2  # +20% for moderate opens
                self.logger.info(
                    f"✅ {symbol}: ODS MODERATE BOOST - Moderate bullish open "
                    f"(strength={ods.strength:.1f}) - Good momentum setup"
                )
            elif ods.day_type == ODSDayType.FAILED_DRIVE:
                confidence_boost = 0.7  # -30% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Failed drive day "
                    f"(momentum reversed) - Reduced confidence but allowing momentum entry"
                )
            elif ods.day_type == ODSDayType.BALANCE_DAY:
                confidence_boost = 0.8  # -20% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Balance day "
                    f"(narrow range={ods.range_pct:.2f}%) - Reduced confidence but allowing momentum"
                )

            # Apply confidence boost to opportunity for adaptive risk sizing
            if 'confidence' in opportunity:
                original_confidence = opportunity['confidence']
                opportunity['confidence'] *= confidence_boost
                self.logger.debug(
                    f"📊 {symbol}: Confidence adjusted: {original_confidence:.1f} → {opportunity['confidence']:.1f} "
                    f"(boost: {confidence_boost:.2f}x)"
                )

            # ============================================================
            # INTRADAY STRUCTURE FILTERS: Critical for momentum breakouts
            # ============================================================
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Store Intraday Structure data for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # MIDDAY PHASE: Filter balance (no breakouts in chop)
            if structure.current_phase == IntradayPhase.MIDDAY:
                if structure.midday_structure == "BALANCE":
                    self.logger.info(
                        f"⚪ {symbol}: MIDDAY FILTER - Balance/chop zone - "
                        f"Momentum breakouts fail in tight range"
                    )
                    return False

                # BOOST on IMBALANCE breakout
                if structure.midday_structure == "IMBALANCE_BULLISH":
                    self.logger.info(
                        f"✅ {symbol}: MIDDAY BOOST - Imbalance breakout - "
                        f"Compression breakout favorable for momentum"
                    )

            # LIQUIDITY SWEEP: Strong boost on reclaim
            if structure.liquidity_sweep_detected:
                if structure.sweep_direction == "BULLISH_RECLAIM":
                    self.logger.info(
                        f"✅ {symbol}: LIQUIDITY SWEEP - Stops absorbed - "
                        f"Momentum breakout after sweep highly reliable"
                    )

            # TRAP DETECTION: Critical filter for momentum
            if structure.trap_detected:
                self.logger.info(
                    f"⚪ {symbol}: TRAP FILTER - {structure.trap_type} detected - "
                    f"Fake breakout, skip momentum entry"
                )
                return False

            # AFTERNOON: Extra caution on late breakouts
            if structure.current_phase == IntradayPhase.AFTERNOON:
                # Only trade afternoon if continuation from earlier move
                if structure.continuation_type not in ["PULLBACK_BULLISH", "VWAP_ROTATION"]:
                    self.logger.info(
                        f"⚪ {symbol}: AFTERNOON FILTER - Late breakout without continuation - "
                        f"High reversal risk"
                    )
                    return False

            # ============================================================
            # RULE 1: MUST BE ABOVE VWAP (in uptrend, not downtrend)
            # ============================================================
            vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price, opportunity=opportunity)

            if not vwap_valid:
                self.logger.info(f"⚪ {symbol}: REJECTED - {vwap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")

            # ============================================================
            # RULE 2: VERIFY PRICE STRUCTURE (uptrend, not extended)
            # ============================================================
            structure_valid, structure_reason = self._verify_price_structure(bars, current_price)

            if not structure_valid:
                self.logger.info(f"⚪ {symbol}: REJECTED - {structure_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Structure valid - {structure_reason}")

            # ============================================================
            # RULE 3: DETECT POST-MOMENTUM CONSOLIDATION BREAKOUT
            # ============================================================
            # NEW LOGIC: Don't chase the momentum spike, wait for consolidation then enter
            # This prevents buying at the top of the initial surge

            consolidation_breakout, breakout_details, support_level = self._detect_consolidation_after_momentum(
                bars, current_price, volume_ratio, symbol
            )

            if not consolidation_breakout:
                self.logger.info(f"⚪ {symbol}: {breakout_details}")
                return False

            # Store support level for dynamic stop loss
            opportunity['support_level'] = support_level

            self.logger.info(f"✅ {symbol}: CONSOLIDATION BREAKOUT - {breakout_details}")

            # ============================================================
            # RULE 4: VOLUME SURGE CONFIRMATION (breakout must have volume)
            # ============================================================
            volume_confirmed = self._confirm_volume_surge(bars, volume_ratio)

            if not volume_confirmed:
                self.logger.info(f"⚪ {symbol}: No volume surge on breakout")
                return False

            self.logger.info(f"✅ {symbol}: Volume surge confirmed")

            # ============================================================
            # RULE 5: NOT TOO EXTENDED (avoid buying tops)
            # ============================================================
            extended_check, extension_pct = self._check_if_extended(bars, current_price)

            if extended_check:
                self.logger.info(f"⚪ {symbol}: Too extended from base ({extension_pct:.1f}% > 10%)")
                return False

            self.logger.info(f"✅ {symbol}: Not extended ({extension_pct:.1f}% from base)")

            # Time validation - Use centralized hour validation from BaseWorkerLogic
            is_valid_hours, current_time = self.is_within_entry_hours(symbol)
            if not is_valid_hours:
                self.logger.info(f"⚪ {symbol}: Outside trading hours ({current_time:.2f})")
                return False

            # ============================================================
            # ALL RULES PASSED - HIGH QUALITY MOMENTUM BREAKOUT
            # ============================================================
            self.logger.info(
                f"✅ {symbol}: PROFESSIONAL MOMENTUM BREAKOUT APPROVED - "
                f"Quality: {breakout_quality:.0f}%, Extension: {extension_pct:.1f}%, Volume: {volume_ratio:.1f}x"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating momentum breakout for {symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _detect_breakout(self, bars: list, current_price: float) -> Tuple[bool, str]:
        """
        Detecta si hay un breakout basado en máximos/mínimos recientes

        Args:
            bars: Lista de barras recientes
            current_price: Precio actual

        Returns:
            Tuple[bool, str]: (breakout_detectado, dirección)
        """
        try:
            if len(bars) < self.lookback_bars:
                return False, 'none'

            # Get recent bars for analysis
            recent_bars = bars[-self.lookback_bars:]

            # Calculate highest high and lowest low of lookback period
            highest_high = max(bar.high for bar in recent_bars)
            lowest_low = min(bar.low for bar in recent_bars)

            # Check for breakout
            if current_price > highest_high:
                return True, 'long'
            elif current_price < lowest_low:
                return True, 'short'

            return False, 'none'

        except Exception as e:
            self.logger.debug(f"Error detecting breakout: {e}")
            return False, 'none'

    def _confirm_momentum(self, bars: list, direction: str) -> bool:
        """
        Confirma que hay momentum consistente en la dirección del breakout

        Args:
            bars: Lista de barras
            direction: 'long' o 'short'

        Returns:
            True si momentum está confirmado
        """
        try:
            if len(bars) < self.momentum_bars + 1:
                return False

            # Check last N bars for consistent direction
            recent_bars = bars[-self.momentum_bars:]

            if direction == 'long':
                # For longs: each bar should close higher than previous
                for i in range(1, len(recent_bars)):
                    if recent_bars[i].close <= recent_bars[i-1].close:
                        return False
                return True

            elif direction == 'short':
                # For shorts: each bar should close lower than previous
                for i in range(1, len(recent_bars)):
                    if recent_bars[i].close >= recent_bars[i-1].close:
                        return False
                return True

            return False

        except Exception as e:
            self.logger.debug(f"Error confirming momentum: {e}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para Momentum Breakout

        Momentum Breakout horizons:
        - INTRADAY (same day): Most common - intraday momentum play
        - SWING_SHORT (1-3 days): Very strong breakout + high volume
        - SCALP: Weak breakout (should be rejected or quick exit)

        Momentum Breakout es principalmente INTRADAY porque:
        - Depende de momentum puro (no catalysts)
        - Breakouts intraday tienden a revertir
        - Sin fundamentales que sostengan el movimiento

        Solo SWING_SHORT si breakout muy fuerte + alto volumen + buena R:R

        Factors:
        - Breakout strength (via confidence/quality score)
        - Volume surge confirmation
        - Risk/reward ratio
        - Market structure quality
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        daily_potential = signal_data.get('daily_potential', {})

        can_swing_short = daily_potential.get('can_swing_short', False)

        # SWING_SHORT: Exceptional breakout + DAILY ALLOWS (rare for this worker)
        if confidence > 75 and risk_reward > 3.0 and volume_zscore > 3.5 and can_swing_short:
            # Very strong breakout from consolidation + massive volume + daily context OK
            # May sustain over 1-2 days
            return TradingHorizon.SWING_SHORT, 24.0

        # INTRADAY: Standard momentum breakout (most common)
        elif confidence > 50 and risk_reward > 1.8:
            # Good breakout - play intraday momentum
            return TradingHorizon.INTRADAY, 4.0  # 4 hours typical

        # SCALP: Weaker breakout - quick in/out
        elif confidence > 40:
            return TradingHorizon.SCALP, 1.0  # 1 hour max

        # Very weak - should be rejected
        else:
            return TradingHorizon.SCALP, 0.5

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de la posición

        Args:
            symbol: Símbolo
            position: Datos de la posición
            current_price: Precio actual

        Returns:
            Tuple[bool, str]: (debe_salir, razón)
        """
        try:
            # Get entry price from position data
            entry_price = position.get('entry_price', 0)

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # Use stop manager for exit decisions (correct method: check_exit)
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None,  # Optional: can pass market data for FOMO detection
                position_metadata=position_metadata
            )

            if should_exit:
                self.logger.info(f"🔴 {symbol}: Momentum worker exit signal - {reason}")
            else:
                self.logger.debug(f"🟢 {symbol}: Momentum worker holding position")

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating momentum exit for {symbol}: {e}")
            # In case of error, exit for safety
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
            self.logger.debug(f"📝 Registered {symbol} with Momentum stop manager")

            # Register with unified position manager (prevent duplicates)
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 150.0)  # Default momentum position

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='momentum_breakout',
                    position_data={
                        'strategy': 'momentum_breakout',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (Momentum trading)")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager AND unified position manager"""
        # Calculate PnL before unregistering
        pnl_pct = None

        # Get position data from unified position manager
        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()

        if unified_manager:
            position_data = unified_manager.get_position(symbol)
            if position_data:
                entry_price = position_data.get('entry_price', 0)
                if entry_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    self.logger.debug(f"📊 {symbol} Momentum exit PnL: {pnl_pct:.2f}%")

        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Unregister from unified position manager
        if unified_manager:
            unified_manager.unregister_position(symbol, 'momentum_breakout', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (Momentum trading)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    def _get_time_from_timestamp(self, timestamp) -> float:
        """
        Convierte timestamp a hora decimal (ej: 14.5 para 14:30)

        Args:
            timestamp: Timestamp del bar

        Returns:
            Hora decimal (0.0-23.99)
        """
        try:
            import pytz
            from datetime import datetime

            # Convertir a datetime si es necesario
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif hasattr(timestamp, 'hour'):
                dt = timestamp
            else:
                # Fallback
                return 12.0

            # FIX: Always convert to Eastern time properly
            # datetime.now() returns local time (Spain), so we need to localize it first
            eastern = pytz.timezone('US/Eastern')
            if dt.tzinfo is None:
                # Assume input is in Spain timezone (Europe/Madrid) and convert to ET
                spain_tz = pytz.timezone('Europe/Madrid')
                dt = spain_tz.localize(dt)
            else:
                # If already has timezone, ensure it's converted to Eastern
                dt = dt.astimezone(eastern)

            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.debug(f"Error converting timestamp to time: {e}")
            return 12.0

    # ========================================================================
    # PROFESSIONAL MOMENTUM BREAKOUT ANALYSIS METHODS
    # ========================================================================

    def _verify_price_structure(self, bars: list, current_price: float) -> Tuple[bool, str]:
        """
        Verify price structure is healthy for momentum breakout

        Requirements:
        1. Higher lows structure (uptrend)
        2. NOT in extended downtrend
        3. Consolidation or base formation

        Returns:
            Tuple[bool, str]: (is_valid, reason)
        """
        try:
            if len(bars) < 20:
                return False, "Insufficient bars for structure analysis"

            # Get recent lows (last 20 bars)
            recent_bars = bars[-20:]
            lows = [bar.low for bar in recent_bars]
            closes = [bar.close for bar in recent_bars]

            # Check for higher lows structure (divide into 4 segments)
            segment_size = len(lows) // 4
            segment_lows = []
            for i in range(4):
                start = i * segment_size
                end = start + segment_size if i < 3 else len(lows)
                segment_low = min(lows[start:end]) if start < len(lows) else lows[-1]
                segment_lows.append(segment_low)

            # Count how many segments show higher lows
            higher_lows_count = sum(1 for i in range(1, len(segment_lows))
                                   if segment_lows[i] >= segment_lows[i-1] * 0.98)  # Allow 2% tolerance

            if higher_lows_count < 2:  # At least 2 of 3 segments must be higher
                return False, f"Downtrend structure (only {higher_lows_count}/3 segments with higher lows)"

            # Check current price is not way below recent average (indicates downtrend)
            avg_close_10 = sum(closes[-10:]) / 10
            if current_price < avg_close_10 * 0.95:  # More than 5% below 10-bar average
                return False, f"Price {((current_price/avg_close_10 - 1) * 100):.1f}% below 10-bar average (downtrend)"

            return True, f"Healthy uptrend structure ({higher_lows_count}/3 segments with higher lows)"

        except Exception as e:
            self.logger.error(f"Error verifying price structure: {e}")
            return False, f"Error: {str(e)}"

    def _detect_consolidation_after_momentum(
        self,
        bars: list,
        current_price: float,
        volume_ratio: float,
        symbol: str
    ) -> Tuple[bool, str]:
        """
        Detecta breakout de consolidación DESPUÉS de momentum spike inicial

        Strategy: "Don't Chase, Let it Come Back"
        - NO persigue el momentum spike inicial
        - Espera consolidación (3-5 barras rango estrecho)
        - Entra en breakout de consolidación con volumen

        Ventajas:
        1. Evita comprar en el top del spike inicial
        2. Mejor precio (pullback a consolidación)
        3. Confirma que el momentum no fue un pump & dump
        4. Volumen seco en consolidación + volume surge en breakout = alta probabilidad

        Criterios:
        1. Detecta momentum spike previo (5-15 barras atrás)
        2. Consolidación de 3-5 barras con rango <4%
        3. Volumen declining en consolidación
        4. Breakout de consolidación con volume surge

        Args:
            bars: Historical bars
            current_price: Current price
            volume_ratio: Current volume ratio
            symbol: Symbol for logging

        Returns:
            Tuple (consolidation_breakout: bool, details: str, support_level: float)
            support_level is consol_low for dynamic stop loss
        """
        try:
            if len(bars) < 20:
                return False, "Insufficient bars for consolidation detection", 0.0

            # 1. Buscar momentum spike en las últimas 5-15 barras
            lookback_start = min(15, len(bars) - 5)
            lookback_bars = bars[-lookback_start:-3]  # Excluye últimas 3 barras

            if not lookback_bars:
                return False, "Not enough historical data", 0.0

            # Encontrar el máximo del momentum spike
            spike_high = max(bar.high for bar in lookback_bars)
            spike_idx = next(i for i, bar in enumerate(lookback_bars) if bar.high == spike_high)

            # 2. Verificar que hubo un spike significativo (momentum inicial)
            pre_spike_bars = bars[-(lookback_start + 5):-lookback_start] if len(bars) > lookback_start + 5 else []
            if pre_spike_bars:
                pre_spike_high = max(bar.high for bar in pre_spike_bars)
                spike_magnitude = ((spike_high - pre_spike_high) / pre_spike_high) * 100

                if spike_magnitude < 2.0:
                    return False, f"No significant momentum spike detected ({spike_magnitude:.1f}% < 2%)", 0.0
            else:
                spike_magnitude = 0

            # 3. Verificar consolidación DESPUÉS del spike (últimas 3-6 barras)
            consolidation_bars = bars[-6:-1]  # Últimas 5 barras excl. current
            if len(consolidation_bars) < 3:
                return False, "Insufficient consolidation period", 0.0

            consol_high = max(bar.high for bar in consolidation_bars)
            consol_low = min(bar.low for bar in consolidation_bars)
            consol_range_pct = ((consol_high - consol_low) / consol_low) * 100

            # Consolidación debe ser TIGHT (<6% range) - RELAXED from 4% to capture more setups
            if consol_range_pct > 6.0:
                return False, f"Consolidation too wide ({consol_range_pct:.1f}% > 6%)", 0.0

            # 4. Verificar volumen declining en consolidación (señal de pausa saludable)
            if len(consolidation_bars) >= 3:
                early_consol_vol = sum(bar.volume for bar in consolidation_bars[:2]) / 2
                late_consol_vol = sum(bar.volume for bar in consolidation_bars[-2:]) / 2

                if early_consol_vol > 0:
                    volume_decline_ratio = late_consol_vol / early_consol_vol
                    volume_drying = volume_decline_ratio < 0.8
                else:
                    volume_drying = False
            else:
                volume_drying = False

            # 5. Verificar breakout de consolidación
            breakout_pct = ((current_price - consol_high) / consol_high) * 100

            if breakout_pct < 0.3:
                return False, f"No breakout from consolidation ({breakout_pct:.2f}% < 0.3%)", 0.0

            # 6. Verificar volume surge en breakout (crítico)
            if volume_ratio < 1.2:
                return False, f"Insufficient volume on breakout ({volume_ratio:.1f}x < 1.2x)", 0.0

            # Construcción de detalles
            details = (f"Momentum spike {spike_magnitude:.1f}% → "
                      f"Consolidation {consol_range_pct:.1f}% range → "
                      f"Breakout +{breakout_pct:.1f}% with {volume_ratio:.1f}x volume")

            if volume_drying:
                details += " (✅ dry volume in consolidation)"

            self.logger.info(f"🎯 {symbol}: POST-MOMENTUM CONSOLIDATION BREAKOUT - {details} (support: ${consol_low:.2f})")
            return True, details, consol_low

        except Exception as e:
            self.logger.error(f"Error detecting consolidation breakout for {symbol}: {e}")
            return False, f"Error: {str(e)}", 0.0

    def _detect_quality_breakout(self, bars: list, current_price: float) -> Tuple[bool, float, str]:
        """
        Detect QUALITY breakout (not just any breakout)

        Quality factors:
        1. Breaking consolidation high (not random spike)
        2. Multiple attempts at resistance (shows real buying pressure)
        3. Tight consolidation before breakout (< 5% range)
        4. Clean breakout (not choppy)

        Returns:
            Tuple[bool, float, str]: (is_breakout, quality_score, direction)
        """
        try:
            if len(bars) < 15:
                return False, 0.0, 'none'

            # Get consolidation period (last 10-15 bars before current)
            consolidation_bars = bars[-15:-1]  # Exclude current bar
            current_bar = bars[-1]

            # Calculate consolidation range
            consol_high = max(bar.high for bar in consolidation_bars)
            consol_low = min(bar.low for bar in consolidation_bars)
            consol_range_pct = ((consol_high - consol_low) / consol_low) * 100

            # Quality Score Components
            quality_score = 0.0

            # Factor 1: Tight consolidation (40 points max)
            if consol_range_pct < 3.0:  # Very tight (< 3%)
                quality_score += 40.0
            elif consol_range_pct < 5.0:  # Tight (< 5%)
                quality_score += 30.0
            elif consol_range_pct < 8.0:  # Acceptable (< 8%)
                quality_score += 20.0
            else:  # Too wide
                quality_score += 5.0

            # Factor 2: Multiple tests of resistance (30 points max)
            tests_of_high = sum(1 for bar in consolidation_bars if bar.high >= consol_high * 0.98)
            if tests_of_high >= 3:
                quality_score += 30.0
            elif tests_of_high >= 2:
                quality_score += 20.0
            else:
                quality_score += 10.0

            # Factor 3: Clean breakout above consolidation (30 points max)
            breakout_pct = ((current_price - consol_high) / consol_high) * 100

            if breakout_pct > 0.5:  # Clear breakout (> 0.5% above high)
                quality_score += 30.0
                is_breakout = True
                direction = 'long'
            elif breakout_pct > 0.2:  # Marginal breakout
                quality_score += 20.0
                is_breakout = True
                direction = 'long'
            else:
                is_breakout = False
                direction = 'none'

            self.logger.debug(
                f"Breakout analysis: Range={consol_range_pct:.1f}%, Tests={tests_of_high}, "
                f"Breakout={breakout_pct:.1f}%, Quality={quality_score:.0f}%"
            )

            return is_breakout, quality_score, direction

        except Exception as e:
            self.logger.error(f"Error detecting quality breakout: {e}")
            return False, 0.0, 'none'

    def _confirm_volume_surge(self, bars: list, current_volume_ratio: float) -> bool:
        """
        Confirm volume surge on breakout

        Requirements:
        1. Current volume > average (already checked by scanner)
        2. Volume trend increasing (last 3 bars)
        3. Breakout bar has highest volume in recent period

        Returns:
            bool: True if volume surge confirmed
        """
        try:
            if len(bars) < 10:
                return False

            recent_bars = bars[-10:]
            volumes = [bar.volume for bar in recent_bars]

            # Current bar should have higher than average volume
            avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
            current_volume = volumes[-1]

            if current_volume < avg_volume * 1.2:  # At least 20% above average
                return False

            # Volume trend: last 3 bars should show increasing volume
            last_3_volumes = volumes[-3:]
            volume_increasing = sum(1 for i in range(1, len(last_3_volumes))
                                   if last_3_volumes[i] > last_3_volumes[i-1])

            if volume_increasing >= 2:  # At least 2 of 2 increases
                return True

            # Alternatively, current bar is highest volume in period
            if current_volume == max(volumes):
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error confirming volume surge: {e}")
            return False

    def _check_if_extended(self, bars: list, current_price: float) -> Tuple[bool, float]:
        """
        Check if price is too extended from base (avoid buying tops)

        Extended if:
        - More than 10% from consolidation low
        - More than 15% from 20-bar low

        Returns:
            Tuple[bool, float]: (is_extended, extension_percentage)
        """
        try:
            if len(bars) < 20:
                return False, 0.0

            # Get base/consolidation low (last 10-15 bars)
            consolidation_bars = bars[-15:-1]
            base_low = min(bar.low for bar in consolidation_bars)

            # Extension from base
            extension_from_base = ((current_price - base_low) / base_low) * 100

            # Get 20-bar low for additional check
            recent_20_low = min(bar.low for bar in bars[-20:])
            extension_from_20bar = ((current_price - recent_20_low) / recent_20_low) * 100

            # Extended if more than 10% from base OR 15% from 20-bar low
            if extension_from_base > 10.0:
                return True, extension_from_base

            if extension_from_20bar > 15.0:
                return True, extension_from_20bar

            return False, extension_from_base

        except Exception as e:
            self.logger.error(f"Error checking extension: {e}")
            return False, 0.0