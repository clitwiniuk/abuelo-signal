"""
MACDV Worker Logic
Worker específico para estrategia MACD-V (Technical momentum)
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class MacdvWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia MACD-V

    Enfoque: Trading técnico basado en momentum sin gaps grandes
    Ideal para movimientos intraday normales con confirmación de volumen

    Criterios de entrada (HIGH-LOW STRATEGY - Momentum Starting):
    - Gap mínimo 0% (permite no gaps - típico de High-Low setups)
    - Volume ratio >= 1.0x (relajado para detectar momentum temprano)
    - Divergencia MACD >= 50/100 (más sensible para momentum incipiente)
    - Momentum building detection (precio subiendo gradualmente desde low)
    - Precio en rango smallcap ($1-$15)
    - Sin noticias mayores (momentum técnico puro)
    - RECHAZA: High-High setups (momentum demasiado fuerte/extendido)

    Criterios de salida:
    - Take profit: 10%
    - Stop loss: 4%
    - Trailing stop: 8% activation, 4% distance
    - Time-based: 4 horas máximo
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="macdv",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica MACDV - SMALLCAP OPTIMIZED
        self.max_gap = 5.0           # Gap máximo (queremos movimientos normales)
        # Read min_volume_ratio from config (centralized) - already imported above
        self.min_volume_ratio = getattr(config, 'min_volume_ratio', 1.0)  # SMALLCAP: Relaxed from 0.7 to 1.0
        self.min_price = 0.5         # SMALLCAP: Relaxed from 1.0 to 0.5
        self.max_price = 25.0        # SMALLCAP: Relaxed from 15.0 to 25.0

        # Entry confirmation tracking (cooldown entre entradas)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 2    # Número de scans consecutivos antes de entrar
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'MACDV_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=4.0,
                take_profit_pct=10.0,
                quick_target_pct=None,
                trailing_activation=8.0,
                trailing_distance=4.0,
                max_position_hours=4.0
            ))

        self.logger.info(
            f"🎯 MACDV Worker configured: "
            f"gap<{self.max_gap}%, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón MACDV (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        MACDV Pattern Stages:
        1. [33%] Price in range & technical catalyst
        2. [66%] Trading hours & quality validated
        3. [85%] NORMAL TECHNICAL MOVE (EARLY ENTRY - momentum building)
        4. [100%] PARABOLIC MOVE (LATE - already extended)

        Early Entry Target: 85% = Technical move detected, not yet parabolic

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

            # Stage 1: Price range & technical catalyst (33%)
            major_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH']
            if catalyst_type not in major_catalysts:
                completion += 17.0
                self.logger.debug(f"📊 {symbol}: Technical catalyst (17%)")
            else:
                self.logger.debug(f"📊 {symbol}: Major catalyst - not MACDV pattern")
                return 0.0

            if self.min_price <= current_price <= self.max_price:
                completion += 16.0
                self.logger.debug(f"📊 {symbol}: Price range (33%) - ${current_price:.2f}")
            else:
                return completion

            # Stage 2: Trading hours & quality (66%) - STRICT TIME ENFORCEMENT
            from datetime import datetime
            import pytz
            # Use centralized hour validation from BaseWorkerLogic
            is_valid_hours, current_hour = self.is_within_entry_hours(symbol)

            if is_valid_hours:
                completion += 17.0
                self.logger.debug(f"📊 {symbol}: Trading hours (50%) - {current_hour:.2f}")
            else:
                # STRICT REJECTION - no entry outside centralized hours
                return 0.0

            if quality_score >= 50.0:
                completion += 16.0
                self.logger.debug(f"📊 {symbol}: Quality validated (66%)")
            else:
                return completion

            # Stage 3: NORMAL vs PARABOLIC MOVE (85-100%)
            # Detect if normal technical move (early entry) or parabolic (late)

            # Check gap magnitude:
            # - Gap 0-5% = normal technical move (EARLY ENTRY)
            # - Gap > 8% = parabolic extension (LATE, too extended)

            if gap_pct <= self.max_gap:
                # Normal technical move - early entry window
                completion += 19.0
                self.logger.debug(
                    f"📊 {symbol}: NORMAL MOVE (85%) - gap {gap_pct:.1f}% not parabolic"
                )
            else:
                # Parabolic move - pattern complete, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: PARABOLIC EXTENSION - gap {gap_pct:.1f}% too large (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: MACDV pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios MACDV

        EARLY ENTRY STRATEGY:
        - Enter at 70-95% pattern completion (divergence forming)
        - Avoid waiting for 100% completion (crossover already happened)

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            self.logger.info(f"🔍 {symbol}: Starting MACDV evaluation")

            # ============================================================
            # CRITICAL VALIDATION 0: Check for duplicate positions
            # ============================================================
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position.get('strategy_type', 'UNKNOWN') if position else 'UNKNOWN'
                strategy_name = position.get('strategy', 'UNKNOWN') if position else 'UNKNOWN'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading (strategy: {strategy_name})"
                )
                # DEBUG: Log position details for diagnosis
                if position:
                    self.logger.debug(f"🔍 DEBUG {symbol}: Position details - {position}")
                else:
                    self.logger.debug(f"🔍 DEBUG {symbol}: No position found but is_symbol_blocked=True - checking cooldowns")
                    active_cooldowns = unified_manager.get_active_cooldowns()
                    if symbol in active_cooldowns:
                        cooldown_data = active_cooldowns[symbol]
                        remaining_minutes = (cooldown_data['until'] - datetime.now()).total_seconds() / 60
                        self.logger.debug(f"🔍 DEBUG {symbol}: In cooldown - {remaining_minutes:.1f}min remaining, reason: {cooldown_data['reason']}")
                return False

            self.logger.info(f"✅ {symbol}: Position check passed")

            # Calculate pattern completion percentage
            completion = await self.calculate_pattern_completion(opportunity)
            self.logger.info(f"📊 {symbol}: Pattern completion = {completion:.0f}%")

            # EARLY ENTRY LOGIC (VERY RELAXED FOR HIGH-LOW):
            # - 0-25%: Pattern not ready, reject
            # - 25-95%: OPTIMAL entry window (divergence forming, momentum building)
            # - 96-100%: Too late, crossover already happening

            if completion < 25.0:  # Very relaxed for High-Low setups
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED - Pattern not ready {completion:.0f}% < 25%"
                )
                return False

            if completion > 95.0:
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED - Pattern too complete {completion:.0f}% > 95%"
                )
                return False

            self.logger.info(f"✅ {symbol}: Pattern completion check passed ({completion:.0f}%)")

            # ====
            # ODS FILTER: Check Opening Drive Structure
            # ====
            from core.ods_classifier import ODSDayType

            bars = self.get_bars_from_opportunity(opportunity)
            ods = await self.get_ods_for_symbol(symbol, bars)

            # Store ODS data for adaptive risk sizing
            opportunity['ods_data'] = ods

            # ODS CONTEXTUAL ADJUSTMENT (SMALLCAP-AWARE)
            confidence_boost = 1.0

            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.3  # +30% confidence
                self.logger.info(
                    f"✅ {symbol}: ODS BOOST - Bullish trend drive "
                    f"(strength={ods.strength:.1f}) - MACD divergence more reliable"
                )
            elif ods.day_type == ODSDayType.STRONG_BULLISH_OPEN:
                confidence_boost = 1.4  # +40% for strong opens
                self.logger.info(
                    f"🔥 {symbol}: ODS STRONG BOOST - Strong bullish open "
                    f"(strength={ods.strength:.1f}) - High conviction setup"
                )
            elif ods.day_type == ODSDayType.MODERATE_BULLISH_OPEN:
                confidence_boost = 1.2  # +20% for moderate opens
                self.logger.info(
                    f"✅ {symbol}: ODS MODERATE BOOST - Moderate bullish open "
                    f"(strength={ods.strength:.1f}) - Good setup"
                )
            elif ods.day_type == ODSDayType.FAILED_DRIVE:
                confidence_boost = 0.7  # -30% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Failed drive day "
                    f"(momentum reversed) - Reduced confidence but allowing entry"
                )
            elif ods.day_type == ODSDayType.BALANCE_DAY:
                confidence_boost = 0.8  # -20% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Balance day "
                    f"(narrow range={ods.range_pct:.2f}%) - Reduced confidence but allowing entry"
                )

            # Apply confidence boost to opportunity for adaptive risk sizing
            if 'confidence' in opportunity:
                original_confidence = opportunity['confidence']
                opportunity['confidence'] *= confidence_boost
                self.logger.debug(
                    f"📊 {symbol}: Confidence adjusted: {original_confidence:.1f} → {opportunity['confidence']:.1f} "
                    f"(boost: {confidence_boost:.2f}x)"
                )

            # ====
            # INTRADAY STRUCTURE FILTERS: Patterns relevant to MACD divergence
            # ====
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Store Intraday Structure data for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # MIDDAY PHASE: Filter balance (divergence needs trend)
            if structure.current_phase == IntradayPhase.MIDDAY:
                if structure.midday_structure == "BALANCE":
                    self.logger.info(
                        f"⚪ {symbol}: MIDDAY FILTER - Balance zone - "
                        f"MACD divergence unreliable in tight range"
                    )
                    return False

            # LIQUIDITY SWEEP: Boost on reclaim (divergence + sweep = strong signal)
            if structure.liquidity_sweep_detected:
                if structure.sweep_direction == "BULLISH_RECLAIM":
                    self.logger.info(
                        f"✅ {symbol}: LIQUIDITY SWEEP BOOST - Divergence + sweep reclaim - "
                        f"High probability reversal setup"
                    )

            # TRAP DETECTION: Filter out fake moves
            if structure.trap_detected:
                self.logger.info(
                    f"⚪ {symbol}: TRAP FILTER - {structure.trap_type} detected - "
                    f"MACD divergence may be false signal"
                )
                return False

            # OPTIMAL ENTRY WINDOW: 50-95%
            # Get bars for VWAP and MACD analysis
            current_price = opportunity.get('current_price', 0)

            if not bars or len(bars) < 35:
                self.logger.info(f"⚪ {symbol}: MACDV REJECTED - Insufficient bars ({len(bars) if bars else 0}/35)")
                return False

            self.logger.info(f"✅ {symbol}: Bars check passed ({len(bars)} bars)")

            # CRITICAL VALIDATION 1: VWAP strength check (universal filter + catalyst override)
            vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price, opportunity=opportunity)

            if not vwap_valid:
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED by VWAP filter - {vwap_reason}"
                )
                return False

            self.logger.debug(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")

            # CRITICAL VALIDATION 2: ADAPTIVE MULTI-TIMEFRAME MACD SYSTEM
            # Analyzes ALL timeframes (1m, 5m, 15m, 30m) and detects dominant one
            # Only enters when there's CONSENSUS across timeframes

            self.logger.info(f"🔍 {symbol}: Starting Adaptive Multi-Timeframe MACD Analysis...")

            # 2A. Get all timeframe bars
            bars_1min = bars  # Already have 1min
            bars_5min = await self._get_bars_multi_timeframe(symbol, '5 mins', '1 D')  # 1 day for 5min bars
            bars_15min = await self._get_bars_multi_timeframe(symbol, '15 mins', '2 D')  # 2 days for 15min bars
            bars_30min = await self._get_bars_multi_timeframe(symbol, '30 mins', '5 D')  # 5 days for 30min bars

            # 2B. Calculate MACD for all available timeframes
            timeframe_analysis = {}

            if bars_1min and len(bars_1min) >= 35:
                macd_1m = self.calculate_macd(bars_1min, fast_period=12, slow_period=26, signal_period=9)
                if macd_1m:
                    timeframe_analysis['1min'] = {
                        'macd_data': macd_1m,
                        'bars': bars_1min,
                        'weight': 1.0  # Lowest weight
                    }

            if bars_5min and len(bars_5min) >= 35:
                macd_5m = self.calculate_macd(bars_5min, fast_period=12, slow_period=26, signal_period=9)
                if macd_5m:
                    timeframe_analysis['5min'] = {
                        'macd_data': macd_5m,
                        'bars': bars_5min,
                        'weight': 2.0  # Medium weight
                    }

            if bars_15min and len(bars_15min) >= 35:
                macd_15m = self.calculate_macd(bars_15min, fast_period=12, slow_period=26, signal_period=9)
                if macd_15m:
                    timeframe_analysis['15min'] = {
                        'macd_data': macd_15m,
                        'bars': bars_15min,
                        'weight': 3.0  # Higher weight
                    }

            if bars_30min and len(bars_30min) >= 35:
                macd_30m = self.calculate_macd(bars_30min, fast_period=12, slow_period=26, signal_period=9)
                if macd_30m:
                    timeframe_analysis['30min'] = {
                        'macd_data': macd_30m,
                        'bars': bars_30min,
                        'weight': 4.0  # Highest weight (most reliable)
                    }

            if len(timeframe_analysis) < 2:
                self.logger.info(f"⚪ {symbol}: MACDV REJECTED - Insufficient timeframes ({len(timeframe_analysis)}/2+ needed)")
                return False

            self.logger.info(f"📊 {symbol}: Analyzing {len(timeframe_analysis)} timeframes: {list(timeframe_analysis.keys())}")

            # 2C. Analyze each timeframe and score
            timeframe_scores = self._analyze_all_timeframes(symbol, timeframe_analysis)

            # 2D. Detect dominant timeframe (where trend is clearest)
            dominant_tf, confidence = self._detect_dominant_timeframe(symbol, timeframe_scores)

            if not dominant_tf:
                self.logger.info(f"⚪ {symbol}: MACDV REJECTED - No dominant timeframe detected")
                return False

            self.logger.info(f"🎯 {symbol}: Dominant timeframe: {dominant_tf} (confidence: {confidence:.0f}%)")

            # 2E. Verify CONSENSUS across timeframes (all must agree or be neutral)
            consensus, consensus_reason = self._verify_timeframe_consensus(symbol, timeframe_scores, dominant_tf)

            if not consensus:
                self.logger.info(f"⚪ {symbol}: MACDV REJECTED - {consensus_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Timeframe consensus achieved - {consensus_reason}")

            # 2F. Use dominant timeframe for divergence detection
            dominant_macd = timeframe_analysis[dominant_tf]['macd_data']
            dominant_bars = timeframe_analysis[dominant_tf]['bars']

            # Detect MACD divergence on dominant timeframe
            divergence_type, divergence_strength = self._detect_divergence(dominant_bars, dominant_macd)

            # HIGH-LOW STRATEGY: Accept setups with momentum building (relaxed criteria)
            momentum_building = self._detect_momentum_building(bars, current_price)

            if divergence_type == 'REGULAR_BULLISH' and divergence_strength >= 30.0:  # Much more relaxed
                # BULLISH DIVERGENCE DETECTED - Now wait for pullback entry
                pullback_entry, pullback_details, support_level = self._detect_macd_pullback_entry(
                    bars, current_price, dominant_macd, symbol
                )

                if not pullback_entry:
                    self.logger.info(
                        f"⚪ {symbol}: Divergence detected but waiting for pullback - {pullback_details}"
                    )
                    return False

                # Store support level for dynamic stop loss
                opportunity['support_level'] = support_level

                self.logger.info(
                    f"✅ {symbol}: MACDV PULLBACK ENTRY APPROVED - {pullback_details} "
                    f"(Divergence strength: {divergence_strength:.0f}/100)"
                )
            elif momentum_building:
                # MOMENTUM BUILDING - Accept even without strong divergence
                self.logger.info(
                    f"✅ {symbol}: MACDV HIGH-LOW ENTRY APPROVED - Momentum building detected "
                    f"(price action favorable for early entry)"
                )
            else:
                # NO DIVERGENCE and NO MOMENTUM BUILDING - Reject entry
                if divergence_type:
                    self.logger.info(
                        f"⚪ {symbol}: MACDV REJECTED - {divergence_type} divergence too weak ({divergence_strength:.0f}/100 < 30)"
                    )
                else:
                    self.logger.info(f"⚪ {symbol}: MACDV REJECTED - No bullish divergence or momentum building detected")
                return False

            # =================================================================
            # HIGH-LOW FILTERS: Very relaxed - accept most setups
            # =================================================================

            # ONLY reject absolutely extreme setups that are clearly overbought
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            if gap_pct > 25.0:  # Extremely large gap = clearly overbought
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED - Extremely overbought (gap {gap_pct:.1f}% > 25%)"
                )
                return False

            # Check if price is insanely far above VWAP
            vwap_distance = (current_price - bars[-1].vwap) / bars[-1].vwap if hasattr(bars[-1], 'vwap') and bars[-1].vwap > 0 else 0
            if vwap_distance > 0.50:  # More than 50% above VWAP = insane
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED - Insanely overbought (price {vwap_distance:.1f}% > VWAP)"
                )
                return False

            # Only reject ridiculous volume spikes
            avg_volume = sum(bar.volume for bar in bars[-20:]) / 20 if len(bars) >= 20 else bars[-1].volume
            volume_ratio = bars[-1].volume / avg_volume if avg_volume > 0 else 1.0
            if volume_ratio > 20.0:  # Ridiculous volume = clearly manipulated
                self.logger.info(
                    f"⚪ {symbol}: MACDV REJECTED - Ridiculous volume (volume {volume_ratio:.1f}x = manipulated)"
                )
                return False

            # Clean up any pending entries tracking
            if symbol in self.pending_entries:
                del self.pending_entries[symbol]

            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para MACDV (technical momentum)

        MACDV horizons:
        - SWING_SHORT (1-3 days): Strong MACD divergence + high confidence
        - INTRADAY (same day): Medium divergence + decent confidence
        - SCALP: Weak divergence (should be rejected)

        MACDV típicamente NO genera SWING largo porque es momentum técnico,
        no catalyst-driven. Máximo SWING_SHORT para divergencias muy fuertes.

        Factors:
        - MACD divergence strength (via confidence)
        - Multi-timeframe consensus
        - Risk/reward ratio
        - Volume confirmation
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        daily_potential = signal_data.get('daily_potential', {})

        can_swing_short = daily_potential.get('can_swing_short', False)

        # SWING_SHORT: Very strong MACD divergence + multi-timeframe + DAILY ALLOWS
        if confidence > 75 and risk_reward > 2.5 and volume_zscore > 2.0 and can_swing_short:
            # Strong technical setup + daily context OK - may play out over 1-2 days
            return TradingHorizon.SWING_SHORT, 30.0  # ~1.25 days

        # INTRADAY: Good MACD divergence (most common for MACDV)
        elif confidence > 55 and risk_reward > 2.0:
            # Standard MACDV setup - intraday momentum play
            return TradingHorizon.INTRADAY, 4.0  # 4 hours typical

        # SCALP: Weak divergence - close quickly or reject
        elif confidence > 45:
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
        Evalúa si debe salir de posición según criterios MACDV

        Criterios de salida:
        1. Take profit: PnL >= 10%
        2. Stop loss: PnL <= -4%
        3. Trailing stop: Si PnL >= 8%, activar trailing a 4%
        4. Time-based: Más de 4 horas en posición
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

            # Debug: Check if position is in UnifiedPositionManager
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()
            if unified_manager:
                is_blocked = unified_manager.is_symbol_blocked(symbol)
                position_in_manager = unified_manager.get_position(symbol)
                self.logger.debug(f"🔍 DEBUG {symbol}: is_blocked={is_blocked}, position_in_manager={position_in_manager is not None}")
                if not is_blocked:
                    self.logger.warning(f"⚠️ {symbol}: Position not found in UnifiedPositionManager - may exit with ERROR_EXIT")
            else:
                self.logger.warning(f"⚠️ {symbol}: UnifiedPositionManager not available")

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

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data,
                position_metadata=position_metadata
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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
                # CRITICAL FIX: Get REAL execution price from ExecutionEngine instead of opportunity price
                # The opportunity price (~$2.14) may differ from actual execution price (~$1.95) due to slippage
                real_entry_price = await self._get_actual_entry_price(symbol)
                if real_entry_price <= 0:
                    # Fallback to opportunity price if we can't get real execution price
                    real_entry_price = opportunity.get('current_price', 0)
                    self.logger.warning(f"⚠️ {symbol}: Could not get real execution price, using opportunity price ${real_entry_price:.2f}")

                position_value = opportunity.get('position_value', 200.0)  # Default day trading position

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='day',
                    position_data={
                        'strategy': 'macdv',
                        'entry_price': real_entry_price,  # Use REAL execution price, not opportunity price
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (DAY trading) - Entry: ${real_entry_price:.2f}")

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
    # MACD CALCULATION & DIVERGENCE DETECTION
    # Migrated from macdv_strategy.py according to MIGRATION_PLAN_READY.md
    # ========================================================================

    def _calculate_ema(self, prices: list, period: int) -> list:
        """
        Calculate Exponential Moving Average

        Args:
            prices: List of closing prices
            period: EMA period

        Returns:
            List of EMA values
        """
        if len(prices) < period:
            return []

        multiplier = 2.0 / (period + 1)
        ema = [sum(prices[:period]) / period]  # SMA for first value

        for i in range(period, len(prices)):
            ema_value = (prices[i] * multiplier) + (ema[-1] * (1 - multiplier))
            ema.append(ema_value)

        return ema

    def calculate_macd(self, bars: list, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, Any]:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        MACD Line = 12-period EMA - 26-period EMA
        Signal Line = 9-period EMA of MACD Line
        Histogram = MACD Line - Signal Line

        Args:
            bars: List of bars (from bars_history or opportunity)
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)

        Returns:
            Dict with 'macd', 'signal', 'histogram', 'macd_line', 'signal_line' arrays
            or None if insufficient data
        """
        try:
            if not bars or len(bars) < slow_period + signal_period:
                return None

            # Extract closing prices
            closes = [bar.close for bar in bars]

            # Calculate EMAs
            ema_fast = self._calculate_ema(closes, fast_period)
            ema_slow = self._calculate_ema(closes, slow_period)

            if not ema_fast or not ema_slow:
                return None

            # Align arrays (slow EMA starts later)
            start_idx = slow_period - fast_period
            if start_idx > 0:
                ema_fast = ema_fast[start_idx:]

            # Calculate MACD line
            macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]

            # Calculate signal line (EMA of MACD line)
            signal_line = self._calculate_ema(macd_line, signal_period)

            if not signal_line:
                return None

            # Calculate histogram (align arrays)
            histogram = [macd_line[i + len(macd_line) - len(signal_line)] - signal_line[i]
                        for i in range(len(signal_line))]

            return {
                'macd': macd_line[-1],           # Current MACD value
                'signal': signal_line[-1],       # Current signal value
                'histogram': histogram[-1],      # Current histogram
                'macd_line': macd_line,          # Full MACD line array
                'signal_line': signal_line,      # Full signal line array
                'histogram_line': histogram      # Full histogram array
            }

        except Exception as e:
            self.logger.error(f"❌ Error calculating MACD: {e}")
            return None

    async def _get_actual_entry_price(self, symbol: str) -> float:
        """
        Get the actual execution price from IBKR after order fill

        This is critical for accurate PnL calculation since opportunity price
        may differ from execution price due to slippage.

        Returns:
            Real execution price, 0 if not available
        """
        try:
            # Get position data from ExecutionEngine which should have the real execution price
            if hasattr(self.execution_engine, 'worker_positions') and symbol in self.execution_engine.worker_positions:
                position_data = self.execution_engine.worker_positions[symbol]
                entry_price = position_data.get('entry_price', 0)
                if entry_price > 0:
                    self.logger.debug(f"✅ {symbol}: Got real execution price ${entry_price:.2f} from ExecutionEngine")
                    return entry_price

            # Fallback: Try to get from broker positions
            if hasattr(self.execution_engine, 'broker') and hasattr(self.execution_engine.broker, 'ib'):
                try:
                    # Get positions from IBKR
                    positions = self.execution_engine.broker.ib.positions()
                    for pos in positions:
                        if hasattr(pos, 'contract') and hasattr(pos.contract, 'symbol'):
                            if pos.contract.symbol == symbol:
                                # For long positions, avgCost is the entry price
                                if hasattr(pos, 'position') and pos.position > 0:
                                    entry_price = getattr(pos, 'avgCost', 0)
                                    if entry_price > 0:
                                        self.logger.debug(f"✅ {symbol}: Got real execution price ${entry_price:.2f} from IBKR positions")
                                        return entry_price
                except Exception as e:
                    self.logger.debug(f"Could not get execution price from IBKR positions: {e}")

            self.logger.warning(f"⚠️ {symbol}: Could not get real execution price, will use opportunity price")
            return 0.0

        except Exception as e:
            self.logger.error(f"❌ Error getting actual entry price for {symbol}: {e}")
            return 0.0

    def _find_price_swings(self, bars: list, lookback: int = 5) -> Dict[str, list]:
        """
        Find price swing highs and lows (local extrema)

        A swing high is a bar where price.high is higher than N bars before and after
        A swing low is a bar where price.low is lower than N bars before and after

        Args:
            bars: List of price bars
            lookback: Number of bars to look before/after for comparison

        Returns:
            Dict with 'highs': [(index, price), ...], 'lows': [(index, price), ...]
        """
        try:
            highs = []
            lows = []

            if len(bars) < lookback * 2 + 1:
                return {'highs': highs, 'lows': lows}

            for i in range(lookback, len(bars) - lookback):
                # Check for swing high
                is_high = True
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and bars[j].high >= bars[i].high:
                        is_high = False
                        break

                if is_high:
                    highs.append((i, bars[i].high))

                # Check for swing low
                is_low = True
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and bars[j].low <= bars[i].low:
                        is_low = False
                        break

                if is_low:
                    lows.append((i, bars[i].low))

            return {'highs': highs, 'lows': lows}

        except Exception as e:
            self.logger.error(f"❌ Error finding price swings: {e}")
            return {'highs': [], 'lows': []}

    def _find_macd_swings(self, macd_line: list, lookback: int = 5) -> Dict[str, list]:
        """
        Find MACD swing highs and lows (local extrema in MACD line)

        Args:
            macd_line: Array of MACD values
            lookback: Number of values to look before/after

        Returns:
            Dict with 'highs': [(index, value), ...], 'lows': [(index, value), ...]
        """
        try:
            highs = []
            lows = []

            if len(macd_line) < lookback * 2 + 1:
                return {'highs': highs, 'lows': lows}

            for i in range(lookback, len(macd_line) - lookback):
                # Check for swing high
                is_high = True
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and macd_line[j] >= macd_line[i]:
                        is_high = False
                        break

                if is_high:
                    highs.append((i, macd_line[i]))

                # Check for swing low
                is_low = True
                for j in range(i - lookback, i + lookback + 1):
                    if j != i and macd_line[j] <= macd_line[i]:
                        is_low = False
                        break

                if is_low:
                    lows.append((i, macd_line[i]))

            return {'highs': highs, 'lows': lows}

        except Exception as e:
            self.logger.error(f"❌ Error finding MACD swings: {e}")
            return {'highs': [], 'lows': []}

    def _detect_divergence(self, bars: list, macd_data: Dict[str, Any]) -> Tuple[str, float]:
        """
        Detect MACD divergence (bullish or bearish)

        Divergence Types:
        1. REGULAR_BULLISH: Price lower low + MACD higher low → Bullish signal
        2. REGULAR_BEARISH: Price higher high + MACD lower high → Bearish signal
        3. HIDDEN_BULLISH: Price higher low + MACD lower low → Continuation
        4. HIDDEN_BEARISH: Price lower high + MACD higher high → Continuation

        Args:
            bars: List of price bars
            macd_data: MACD calculation result (with 'macd_line')

        Returns:
            Tuple (divergence_type, strength) where:
                divergence_type: 'REGULAR_BULLISH', 'REGULAR_BEARISH', 'HIDDEN_BULLISH', 'HIDDEN_BEARISH', or None
                strength: 0-100 confidence score
        """
        try:
            if not macd_data or 'macd_line' not in macd_data:
                return None, 0.0

            macd_line = macd_data['macd_line']

            # Find price and MACD swings
            price_swings = self._find_price_swings(bars, lookback=5)
            macd_swings = self._find_macd_swings(macd_line, lookback=5)

            price_highs = price_swings['highs']
            price_lows = price_swings['lows']
            macd_highs = macd_swings['highs']
            macd_lows = macd_swings['lows']

            # Need at least 2 swings to detect divergence
            if len(price_lows) < 2 or len(macd_lows) < 2:
                if len(price_highs) < 2 or len(macd_highs) < 2:
                    return None, 0.0

            # REGULAR BULLISH DIVERGENCE: Price lower low + MACD higher low
            if len(price_lows) >= 2 and len(macd_lows) >= 2:
                # Get last two price lows
                price_low_1 = price_lows[-2][1]  # Previous low
                price_low_2 = price_lows[-1][1]  # Current low

                # Get last two MACD lows (aligned with price)
                macd_low_1_idx = price_lows[-2][0]  # Index of previous price low
                macd_low_2_idx = price_lows[-1][0]  # Index of current price low

                # Find closest MACD lows to these price lows
                def find_closest_macd_low(target_idx, macd_lows_list):
                    closest = min(macd_lows_list, key=lambda x: abs(x[0] - target_idx))
                    return closest[1]

                macd_low_1 = find_closest_macd_low(macd_low_1_idx, macd_lows)
                macd_low_2 = find_closest_macd_low(macd_low_2_idx, macd_lows)

                # Check for bullish divergence
                if price_low_2 < price_low_1 and macd_low_2 > macd_low_1:
                    strength = self._calculate_divergence_strength(
                        price_low_1, price_low_2, macd_low_1, macd_low_2
                    )
                    return 'REGULAR_BULLISH', strength

            # REGULAR BEARISH DIVERGENCE: Price higher high + MACD lower high
            if len(price_highs) >= 2 and len(macd_highs) >= 2:
                price_high_1 = price_highs[-2][1]
                price_high_2 = price_highs[-1][1]

                macd_high_1_idx = price_highs[-2][0]
                macd_high_2_idx = price_highs[-1][0]

                def find_closest_macd_high(target_idx, macd_highs_list):
                    closest = min(macd_highs_list, key=lambda x: abs(x[0] - target_idx))
                    return closest[1]

                macd_high_1 = find_closest_macd_high(macd_high_1_idx, macd_highs)
                macd_high_2 = find_closest_macd_high(macd_high_2_idx, macd_highs)

                if price_high_2 > price_high_1 and macd_high_2 < macd_high_1:
                    strength = self._calculate_divergence_strength(
                        price_high_1, price_high_2, macd_high_1, macd_high_2
                    )
                    return 'REGULAR_BEARISH', strength

            return None, 0.0

        except Exception as e:
            self.logger.error(f"❌ Error detecting divergence: {e}")
            return None, 0.0

    def _detect_momentum_building(self, bars: list, current_price: float) -> bool:
        """
        Detect momentum building from a low (High-Low setup characteristic)

        Simplified version: Just check if price is trending up with increasing volume
        """
        try:
            if len(bars) < 5:
                return False

            # Get recent bars (last 5 for simplicity)
            recent_bars = bars[-5:]

            # Simple momentum check: more bars closing higher than lower
            closes = [bar.close for bar in recent_bars]
            higher_closes = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])

            # Volume trend: more bars with higher volume
            volumes = [bar.volume for bar in recent_bars]
            higher_volumes = sum(1 for i in range(1, len(volumes)) if volumes[i] > volumes[i-1])

            # Very simple criteria for High-Low setups
            price_trending_up = higher_closes >= 3  # At least 3 of 4 bars closing higher
            volume_increasing = higher_volumes >= 2  # At least 2 of 4 bars with higher volume

            momentum_building = price_trending_up and volume_increasing

            if momentum_building:
                self.logger.debug(
                    f"📈 Momentum building detected - Higher closes: {higher_closes}/4, "
                    f"Higher volumes: {higher_volumes}/4"
                )

            return momentum_building

        except Exception as e:
            self.logger.error(f"❌ Error detecting momentum building: {e}")
            return False

    def _detect_macd_pullback_entry(
        self,
        bars: list,
        current_price: float,
        macd_data: Dict[str, Any],
        symbol: str
    ) -> Tuple[bool, str]:
        """
        Detecta entrada en pullback después de divergencia MACD detectada

        Strategy: "Wait for the Pullback, Don't Chase"
        - Divergencia detectada → NO entra inmediatamente
        - Espera pullback a EMA21 o VWAP
        - Confirma volumen bajo en pullback (exhaustion vendedora)
        - Entra cuando precio recupera + MACD girando al alza

        Ventajas:
        1. Mejor precio (pullback vs perseguir)
        2. Confirma que divergencia es válida (no falsa señal)
        3. Volumen bajo en pullback = institucionales no venden
        4. MACD girando = timing perfecto

        Criterios:
        1. Precio cerca de soporte (EMA21 o VWAP ±2%)
        2. Precio recuperando desde mínimo reciente
        3. MACD histogram positivo o girando al alza
        4. Volumen declining (opcional pero ideal)

        Args:
            bars: Historical bars
            current_price: Current price
            macd_data: MACD data from dominant timeframe
            symbol: Symbol for logging

        Returns:
            Tuple (pullback_entry: bool, details: str, support_level: float)
            support_level is recent_low for dynamic stop loss
        """
        try:
            if len(bars) < 21:
                return False, "Insufficient bars for pullback detection", 0.0

            # 1. Calcular EMA21 (soporte clave)
            ema21 = self._calculate_ema(bars, period=21)
            if ema21 is None or ema21 == 0:
                return False, "EMA21 calculation failed", 0.0

            # 2. Calcular VWAP como soporte alternativo
            vwap = self.calculate_vwap_from_bars(bars) if hasattr(self, 'calculate_vwap_from_bars') else None

            # 3. Verificar si está cerca de soporte (EMA21 o VWAP)
            distance_to_ema21 = abs((current_price - ema21) / ema21) * 100
            near_ema21 = distance_to_ema21 <= 2.0  # Dentro del 2% de EMA21

            near_vwap = False
            if vwap and vwap > 0:
                distance_to_vwap = abs((current_price - vwap) / vwap) * 100
                near_vwap = distance_to_vwap <= 2.0  # Dentro del 2% de VWAP

            near_support = near_ema21 or near_vwap

            if not near_support:
                support_msg = f"EMA21 ${ema21:.2f} ({distance_to_ema21:.1f}% away)"
                if vwap:
                    support_msg += f", VWAP ${vwap:.2f}"
                return False, f"Not near support - {support_msg}", 0.0

            # 4. Verificar recuperación desde mínimo reciente (últimas 5-10 barras)
            lookback = min(10, len(bars))
            recent_bars = bars[-lookback:]
            recent_low = min(bar.low for bar in recent_bars)
            recovery_from_low = ((current_price - recent_low) / recent_low) * 100

            if recovery_from_low < 0.3:
                return False, f"No recovery from recent low (${recent_low:.2f}, +{recovery_from_low:.2f}%)", 0.0

            # 5. Verificar MACD histogram (debe ser positivo o girando al alza)
            macd_hist = macd_data.get('histogram', [])
            if len(macd_hist) < 2:
                return False, "Insufficient MACD data", 0.0

            current_hist = macd_hist[-1]
            prev_hist = macd_hist[-2]
            hist_turning_up = current_hist > prev_hist  # Girando al alza

            if current_hist < 0 and not hist_turning_up:
                return False, f"MACD histogram negative and declining ({current_hist:.4f})", 0.0

            # 6. Verificar volumen declining (opcional)
            if len(bars) >= 10:
                recent_volume = sum(bar.volume for bar in bars[-5:]) / 5
                prev_volume = sum(bar.volume for bar in bars[-10:-5]) / 5
                volume_declining = recent_volume < prev_volume if prev_volume > 0 else False
            else:
                volume_declining = False

            # Construir detalles
            support_level = f"EMA21 ${ema21:.2f}" if near_ema21 else f"VWAP ${vwap:.2f}"
            details = f"Pullback to {support_level}, recovered +{recovery_from_low:.1f}% from low ${recent_low:.2f}"

            if hist_turning_up:
                details += ", MACD turning up"
            else:
                details += f", MACD positive ({current_hist:.4f})"

            if volume_declining:
                details += " (✅ dry volume)"

            self.logger.info(f"🎯 {symbol}: MACD PULLBACK ENTRY - {details} (support: ${recent_low:.2f})")
            return True, details, recent_low

        except Exception as e:
            self.logger.error(f"Error detecting MACD pullback entry for {symbol}: {e}")
            return False, f"Error: {str(e)}", 0.0

    def _calculate_divergence_strength(self, price_1: float, price_2: float,
                                       macd_1: float, macd_2: float) -> float:
        """
        Calculate divergence strength (0-100)

        Factors:
        - Magnitude of price divergence
        - Magnitude of MACD divergence
        - Agreement between the two

        Args:
            price_1: Previous price swing
            price_2: Current price swing
            macd_1: Previous MACD swing
            macd_2: Current MACD swing

        Returns:
            Strength score 0-100
        """
        try:
            # Calculate price change percentage
            price_change_pct = abs((price_2 - price_1) / price_1) * 100

            # Calculate MACD change percentage (relative to average)
            macd_avg = (abs(macd_1) + abs(macd_2)) / 2
            if macd_avg == 0:
                macd_change_pct = 0
            else:
                macd_change_pct = abs((macd_2 - macd_1) / macd_avg) * 100

            # Base strength from price divergence (0-50 points)
            price_score = min(price_change_pct * 10, 50)

            # MACD divergence strength (0-50 points)
            macd_score = min(macd_change_pct * 5, 50)

            # Total strength
            total_strength = price_score + macd_score

            return min(total_strength, 100.0)

        except Exception as e:
            self.logger.error(f"❌ Error calculating divergence strength: {e}")
            return 0.0

    async def _get_bars_multi_timeframe(self, symbol: str, bar_size: str, duration: str) -> list:
        """
        Get bars for any timeframe (generalized version)

        Args:
            symbol: Stock symbol
            bar_size: Bar size (e.g., '5 mins', '15 mins', '30 mins')
            duration: Duration to fetch (e.g., '3 hours', '1 day', '2 days')

        Returns:
            List of bars, or None if failed
        """
        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')

            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=False  # Include extended hours
            )

            if bars:
                self.logger.debug(f"✅ {symbol}: Retrieved {len(bars)} {bar_size} bars")
                return list(bars)
            else:
                self.logger.debug(f"⚠️ {symbol}: No {bar_size} bars returned")
                return None

        except Exception as e:
            self.logger.debug(f"Could not get {bar_size} bars for {symbol}: {e}")
            return None

    def _verify_macd_alignment(self, macd_1min: Dict, macd_5min: Dict, symbol: str) -> Tuple[bool, str]:
        """
        Verify that MACD signals are aligned across 1min and 5min timeframes

        Alignment Rules:
        1. Both must be in bullish territory (MACD > Signal) OR both bearish
        2. 5min must show bullish structure (MACD trending up or near crossover)
        3. Histogram must be positive on both OR 5min histogram turning positive

        Args:
            macd_1min: MACD data from 1-minute timeframe
            macd_5min: MACD data from 5-minute timeframe
            symbol: Stock symbol (for logging)

        Returns:
            Tuple (is_aligned, reason)
        """
        try:
            # Extract current values
            macd_1m = macd_1min['macd']
            signal_1m = macd_1min['signal']
            hist_1m = macd_1min['histogram']

            macd_5m = macd_5min['macd']
            signal_5m = macd_5min['signal']
            hist_5m = macd_5min['histogram']

            # Get recent histogram trend on 5min
            hist_5m_line = macd_5min.get('histogram_line', [])
            hist_5m_trend = None
            if len(hist_5m_line) >= 3:
                recent_hist = hist_5m_line[-3:]
                if recent_hist[-1] > recent_hist[-2] > recent_hist[-3]:
                    hist_5m_trend = "IMPROVING"
                elif recent_hist[-1] > 0:
                    hist_5m_trend = "POSITIVE"
                else:
                    hist_5m_trend = "NEGATIVE"

            self.logger.debug(
                f"📊 {symbol}: 1m MACD={macd_1m:.3f} Signal={signal_1m:.3f} Hist={hist_1m:.3f}"
            )
            self.logger.debug(
                f"📊 {symbol}: 5m MACD={macd_5m:.3f} Signal={signal_5m:.3f} Hist={hist_5m:.3f} Trend={hist_5m_trend}"
            )

            # RULE 1: 1min MUST be bullish (MACD > Signal or very close)
            macd_1m_bullish = macd_1m >= signal_1m - 0.01  # Allow tiny tolerance

            if not macd_1m_bullish:
                return False, f"1min bearish (MACD {macd_1m:.3f} < Signal {signal_1m:.3f})"

            # RULE 2: 5min must NOT be strongly bearish (contradicting 1min signal)
            # Allow if 5min is:
            # - Already bullish (MACD > Signal)
            # - Histogram improving (moving toward bullish)
            # - Histogram positive even if MACD < Signal (crossover imminent)

            macd_5m_bullish = macd_5m > signal_5m

            if macd_5m_bullish:
                return True, "Both timeframes bullish"

            # 5min not yet crossed, but check if it's moving in right direction
            if hist_5m_trend == "IMPROVING":
                # Histogram getting better = trend changing toward bullish
                return True, "5min improving (crossover forming)"

            if hist_5m > -0.02:  # Very close to crossover (within 0.02 of zero)
                return True, "5min near crossover (hist close to 0)"

            # 5min is bearish and not improving = contradicts 1min signal
            return False, f"5min contradicts 1min (MACD {macd_5m:.3f} < Signal {signal_5m:.3f}, trend={hist_5m_trend})"

        except Exception as e:
            self.logger.error(f"❌ Error verifying MACD alignment: {e}")
            return False, f"Error: {str(e)}"

    # ========================================================================
    # ADAPTIVE MULTI-TIMEFRAME SYSTEM
    # ========================================================================

    def _analyze_all_timeframes(self, symbol: str, timeframe_analysis: Dict) -> Dict:
        """
        Analyze all available timeframes and score each one

        Scoring factors:
        1. MACD position (bullish vs bearish)
        2. Histogram trend (improving, stable, deteriorating)
        3. Distance from crossover
        4. Strength of signal

        Returns:
            Dict with scores for each timeframe
        """
        scores = {}

        for tf_name, tf_data in timeframe_analysis.items():
            macd_data = tf_data['macd_data']
            weight = tf_data['weight']

            # Extract MACD values
            macd = macd_data['macd']
            signal = macd_data['signal']
            histogram = macd_data['histogram']
            hist_line = macd_data.get('histogram_line', [])

            # Score components
            score = 0.0
            signal_type = 'NEUTRAL'

            # 1. MACD Position Score (0-40 points)
            if macd > signal:
                position_score = 40.0
                signal_type = 'BULLISH'
            elif macd > signal - 0.02:  # Very close to crossover
                position_score = 30.0
                signal_type = 'NEAR_BULLISH'
            elif macd < signal - 0.05:  # Clearly bearish
                position_score = 0.0
                signal_type = 'BEARISH'
            else:
                position_score = 15.0
                signal_type = 'NEUTRAL'

            score += position_score

            # 2. Histogram Trend Score (0-30 points)
            if len(hist_line) >= 3:
                recent_hist = hist_line[-3:]
                if recent_hist[-1] > recent_hist[-2] > recent_hist[-3]:
                    trend_score = 30.0  # Improving
                    trend_type = 'IMPROVING'
                elif recent_hist[-1] > recent_hist[-2]:
                    trend_score = 20.0  # Partially improving
                    trend_type = 'IMPROVING'
                elif histogram > 0:
                    trend_score = 15.0  # Positive but not improving
                    trend_type = 'POSITIVE'
                else:
                    trend_score = 0.0  # Negative or deteriorating
                    trend_type = 'NEGATIVE'
            else:
                trend_score = 10.0
                trend_type = 'UNKNOWN'

            score += trend_score

            # 3. Distance from Crossover Score (0-30 points)
            distance = abs(histogram)
            if distance < 0.01:  # Very close to crossover
                distance_score = 30.0
            elif distance < 0.03:
                distance_score = 20.0
            elif distance < 0.05:
                distance_score = 10.0
            else:
                distance_score = 0.0

            score += distance_score

            # Apply timeframe weight (higher timeframes get bonus)
            weighted_score = score * weight

            scores[tf_name] = {
                'raw_score': score,
                'weighted_score': weighted_score,
                'signal_type': signal_type,
                'trend_type': trend_type,
                'histogram': histogram,
                'weight': weight,
                'macd': macd,
                'signal': signal
            }

            self.logger.debug(
                f"📊 {symbol} {tf_name}: Score={score:.0f} (weighted={weighted_score:.0f}), "
                f"Signal={signal_type}, Trend={trend_type}, Hist={histogram:.3f}"
            )

        return scores

    def _detect_dominant_timeframe(self, symbol: str, timeframe_scores: Dict) -> Tuple[str, float]:
        """
        Detect which timeframe has the clearest/strongest signal

        The dominant timeframe is the one with:
        1. Highest weighted score
        2. Clear bullish signal (not neutral/bearish)
        3. Minimum score threshold (60+)

        Returns:
            Tuple[str, float]: (dominant_timeframe, confidence)
        """
        try:
            # Find timeframe with highest weighted score
            best_tf = None
            best_score = 0.0
            best_raw_score = 0.0

            for tf_name, tf_score in timeframe_scores.items():
                weighted = tf_score['weighted_score']
                raw = tf_score['raw_score']
                signal_type = tf_score['signal_type']

                # Must be at least NEAR_BULLISH to be dominant
                if signal_type in ['BULLISH', 'NEAR_BULLISH']:
                    if weighted > best_score:
                        best_score = weighted
                        best_tf = tf_name
                        best_raw_score = raw

            # Require minimum score threshold
            if best_raw_score < 50.0:  # Need at least 50/100 raw score
                self.logger.debug(f"📊 {symbol}: Best score {best_raw_score:.0f} below threshold (50)")
                return None, 0.0

            # Calculate confidence based on raw score
            confidence = min(best_raw_score, 100.0)

            self.logger.info(
                f"🎯 {symbol}: Dominant TF={best_tf}, Score={best_raw_score:.0f}/100, "
                f"Confidence={confidence:.0f}%"
            )

            return best_tf, confidence

        except Exception as e:
            self.logger.error(f"❌ Error detecting dominant timeframe: {e}")
            return None, 0.0

    def _verify_timeframe_consensus(self, symbol: str, timeframe_scores: Dict,
                                   dominant_tf: str) -> Tuple[bool, str]:
        """
        Verify timeframe consensus with HIERARCHICAL logic

        SMART CONSENSUS RULES (hierarchical):
        1. Dominant timeframe MUST be BULLISH/NEAR_BULLISH
        2. Lower timeframes (faster than dominant): Can be anything (ignored)
        3. Higher timeframes (slower than dominant): Must NOT contradict strongly
        4. Equal or higher timeframes: At least 50% must agree

        Example:
        - If dominant=5min: Ignore 1min, check 15min/30min don't contradict
        - If dominant=30min: Ignore 1min/5min/15min (they'll follow)

        Returns:
            Tuple[bool, str]: (has_consensus, reason)
        """
        try:
            # Timeframe hierarchy (order matters)
            tf_hierarchy = ['1min', '5min', '15min', '30min']

            # Find dominant position in hierarchy
            try:
                dominant_idx = tf_hierarchy.index(dominant_tf)
            except ValueError:
                return False, f"Unknown dominant timeframe: {dominant_tf}"

            dominant_signal = timeframe_scores[dominant_tf]['signal_type']

            # Rule 1: Dominant must be bullish
            if dominant_signal not in ['BULLISH', 'NEAR_BULLISH']:
                return False, f"Dominant TF ({dominant_tf}) not bullish ({dominant_signal})"

            # Rule 2: Check ONLY equal or higher timeframes (slower)
            higher_tfs = [tf for i, tf in enumerate(tf_hierarchy)
                         if i >= dominant_idx and tf in timeframe_scores]

            if len(higher_tfs) == 0:
                return False, "No higher timeframes available"

            # Analyze higher/equal timeframes only
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0

            for tf_name in higher_tfs:
                if tf_name not in timeframe_scores:
                    continue

                signal = timeframe_scores[tf_name]['signal_type']

                if signal in ['BULLISH', 'NEAR_BULLISH']:
                    bullish_count += 1
                elif signal == 'BEARISH':
                    bearish_count += 1
                else:
                    neutral_count += 1

            total_higher = len(higher_tfs)

            # Rule 3: NO higher timeframe can be strongly BEARISH
            # Exception: If dominant is 1min, allow 1 bearish in higher TFs
            max_bearish_allowed = 1 if dominant_tf == '1min' else 0

            if bearish_count > max_bearish_allowed:
                bearish_tfs = [tf for tf in higher_tfs
                              if timeframe_scores[tf]['signal_type'] == 'BEARISH']
                return False, (f"{bearish_count} higher TFs bearish {bearish_tfs} "
                             f"(contradicts {dominant_tf})")

            # Rule 4: At least 50% of equal/higher TFs must be bullish
            bullish_pct = (bullish_count / total_higher) * 100
            if bullish_pct < 50.0:
                return False, (f"Only {bullish_pct:.0f}% of higher TFs bullish "
                             f"({bullish_count}/{total_higher})")

            # Success - build reason string
            lower_tfs = [tf for i, tf in enumerate(tf_hierarchy)
                        if i < dominant_idx and tf in timeframe_scores]

            reason = (f"Dominant={dominant_tf} (bullish), "
                     f"Higher TFs: {bullish_count}/{total_higher} bullish")

            if lower_tfs:
                reason += f", Lower TFs ignored: {lower_tfs}"

            return True, reason

        except Exception as e:
            self.logger.error(f"❌ Error verifying consensus: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"Error: {str(e)}"