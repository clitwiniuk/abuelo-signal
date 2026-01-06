"""
VCP (Volatility Contraction Pattern) Worker Logic - Smallcap Intraday Edition
Worker especializado en detectar contracciones de volatilidad para entrada anticipada

Basado en Mark Minervini VCP pero adaptado para:
- Smallcaps (alta volatilidad, bajo float)
- Timeframe intradiario (1min, 5min, 15min)
- Análisis multitimeframe (1min, 5min, 15min)
- Entrada ANTICIPADA (antes del breakout completo)
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta
from .base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradingHorizon


class VCPSmallcapWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para VCP (Volatility Contraction Pattern) en smallcaps intradiario

    FILOSOFÍA VCP:
    El patrón VCP es una serie de contracciones sucesivas en el precio, donde cada
    contracción es más pequeña que la anterior. Esto indica acumulación institucional
    antes de un movimiento explosivo.

    ADAPTACIÓN PARA SMALLCAPS INTRADIARIO:
    1. Contracciones más rápidas (minutos en vez de días)
    2. Entrada ANTICIPADA al 80-85% del patrón (antes del breakout)
    3. Multitimeframe: validación en 1min, 5min, 15min
    4. Catalysts importantes (news, halts, runners)

    CRITERIOS DE ENTRADA (80-85% del patrón):
    - 3+ contracciones detectadas (cada una más pequeña)
    - Volumen declinando en cada contracción (acumulación)
    - Precio cerca del nivel de breakout (98-99% del high)
    - Estructura multitimeframe alineada
    - NO espera el breakout completo (entra antes)

    CRITERIOS DE SALIDA:
    - Take profit: 15% (smallcaps volátiles)
    - Stop loss: 5% (amplio para volatilidad)
    - Trailing stop: 8% activation, 4% distance
    - Time-based exit: máximo 6 horas (intradiario)
    - Breakout failure: si no rompe en 30 min, salir
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración VCP específica (TIGHTENED for quality)
        self.min_contractions = getattr(config, 'vcp_min_contractions', 2)  # RELAXED: 3 -> 2 contracciones
        self.max_contraction_minutes = getattr(config, 'vcp_max_contraction_minutes', 45)  # Max 45min por contracción
        self.entry_threshold_pct = getattr(config, 'vcp_entry_threshold', 98.0)  # Entrar al 98% del high
        self.min_price = getattr(config, 'vcp_min_price', 1.0)  # TIGHTENED: Avoid extreme penny stocks
        self.max_price = getattr(config, 'vcp_max_price', 25.0)  # Match other workers
        self.min_volume_ratio = getattr(config, 'vcp_min_volume_ratio', 1.0)  # TIGHTENED: VCP needs volume at pivot
        self.min_quality_score = getattr(config, 'vcp_min_quality_score', 55.0)  # TIGHTENED: Minimum acceptable quality

        # ODS Filters (Market Structure)
        self.enable_ods_filters = getattr(config, 'enable_ods_filters', True)  # NEW: Configurable

        # Multitimeframe settings
        self.use_multitimeframe = getattr(config, 'vcp_use_multitimeframe', False)  # DISABLED: Too strict for smallcaps
        self.mtf_timeframes = ['1min', '5min', '15min']  # Timeframes a analizar

        # Catalyst requirements (RELAXED for technical VCP pattern)
        self.require_catalyst = getattr(config, 'vcp_require_catalyst', False)  # RELAXED: VCP is technical pattern
        self.accepted_catalysts = ['NEWS', 'EARNINGS', 'HALT', 'RUNNER', 'FDA', 'CONTRACT', 'OTHER', 'TECHNICAL']  # Added OTHER/TECHNICAL

        self.config = config

        # Initialize stop manager with VCP-specific parameters
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'VCP_SMALLCAP_STRATEGY')
        else:
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,            # 5% stop (amplio para volatilidad)
                take_profit_pct=15.0,         # 15% profit target (smallcaps)
                quick_target_pct=0.0,         # No quick target (dejar desarrollar)
                trailing_activation=8.0,      # Activar trailing a 8%
                trailing_distance=4.0,        # 4% trailing distance
                max_position_hours=6.0        # Max 6 horas
            ))

        self.logger.info(
            f"🎯 VCP Smallcap Worker configured (QUALITY FOCUSED): "
            f"contractions>={self.min_contractions}, Q>={self.min_quality_score}, "
            f"price=${self.min_price}-${self.max_price}, vol>={self.min_volume_ratio}x, "
            f"MTF={self.use_multitimeframe}, catalyst_required={self.require_catalyst} | "
            f"Exits: TP=15%, SL=5%, Trail=8%/4%, Max=6h"
        )


    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Public interface for pattern completion (BaseWorkerLogic compatibility).
        Wraps _calculate_vcp_completion with correct context extraction.
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            current_price = opportunity.get('current_price', 0)
            bars = self.get_bars_from_opportunity(opportunity)
            
            if not bars:
                return 0.0, 0.0
            
            # Determine context for Supply Exhaustion logic
            quality_score = opportunity.get('quality_score', 0)
            is_blue_sky = opportunity.get('is_blue_sky', False)
            # Use same logic as should_enter
            is_supply_exhaustion = is_blue_sky or (quality_score >= 70.0)

            return await self._calculate_vcp_completion(
                bars, current_price, symbol,
                allow_flat_structure=is_supply_exhaustion
            )
        except Exception as e:
            self.logger.error(f"Error in public calculate_pattern_completion: {e}")
            return 0.0, 0.0

    async def _calculate_vcp_completion(
        self,
        bars: list,
        current_price: float,
        symbol: str,
        allow_flat_structure: bool = False
    ) -> Tuple[float, float]:
        """
        Calcula % de completitud del patrón VCP (0-100%)
        allow_flat_structure: If True, skips 'decreasing contractions' check (for Supply Exhaustion)

        PATTERN COMPLETION STAGES:
        - 0-20%: Datos básicos disponibles
        - 20-40%: Primera contracción detectada
        - 40-60%: Segunda contracción detectada
        - 60-80%: Tercera+ contracción detectada (patrón formándose)
        - 80-90%: Precio cerca del breakout (98%+ del high) - EARLY ENTRY ZONE
        - 90-100%: Volumen building + MTF confirmación - OPTIMAL ENTRY
        - 100%: Breakout completo (demasiado tarde)

        Returns:
            Tuple (Pattern completion percentage (0.0-100.0), support_level for dynamic stop)
        """
        try:
            completion = 0.0
            support_level = 0.0

            if not bars or len(bars) < 15:  # RELAXED: 20 -> 15 bars minimum
                return 0.0, 0.0

            # Stage 1: Basic data validation (20%)
            if current_price > 0: # volume_ratio is not passed here, so only check price
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: Basic data validated")

            # Stage 2-3: Detect contractions (20% each)
            contractions = self._detect_contractions(bars)
            num_contractions = len(contractions)

            # Relax contraction count if allow_flat_structure (strong momentum needs less consolidation)
            min_contractions_for_completion = max(1, self.min_contractions - 1) if allow_flat_structure else self.min_contractions

            if num_contractions >= 1:
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: 1st contraction detected")
                # Update support level to the low of the most recent contraction
                support_level = contractions[-1]['low']

            if num_contractions >= 2:
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: 2nd contraction detected")
                # Update support level to the low of the most recent contraction
                support_level = contractions[-1]['low']

            if num_contractions >= 3:
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: 3rd+ contraction detected ({num_contractions} total)")
                # Update support level to the low of the most recent contraction
                support_level = contractions[-1]['low']

            # Validate contractions are decreasing in size (VCP requirement)
            if not self._validate_contractions_decreasing(contractions, allow_constant_range=allow_flat_structure):
                self.logger.info(f"⚪ {symbol}: Contractions not decreasing in size (invalid VCP)")
                return 0.0, 0.0 # Invalidate completion if VCP structure is broken
            
            # Validate contraction trend (Reject Descending Triangles / Bearish VCP)
            if not self._validate_contraction_trend(contractions):
                self.logger.info(f"⚪ {symbol}: Invalid contraction trend (Bearish/Descending) - Rejecting")
                return 0.0, 0.0

            # Stage 4: Price near breakout level (10%)
            if num_contractions >= min_contractions_for_completion:
                breakout_level = max(bar.high for bar in bars[-20:])
                proximity_pct = (current_price / breakout_level) * 100

                if proximity_pct >= self.entry_threshold_pct:  # 98%+
                    completion += 10.0
                    self.logger.debug(f"📊 {symbol}: Price near breakout ({proximity_pct:.1f}%)")

            # Stage 5: Volume and MTF confirmation (10%)
            if completion >= 80.0:
                # Check volume building
                volume_building = self._check_volume_building(bars)

                # Check multitimeframe alignment (if enabled)
                mtf_aligned = True
                if self.use_multitimeframe:
                    # Use base class method for multi-timeframe trend analysis
                    mtf_aligned, mtf_reason, mtf_details = self.check_multi_timeframe_trend(bars, symbol)

                if volume_building and mtf_aligned:
                    completion = min(100.0, completion + 10.0)
                    self.logger.info(f"✅ {symbol}: VCP setup optimal - volume building + MTF aligned")

            self.logger.info(
                f"📊 {symbol}: VCP pattern completion = {completion:.0f}% "
                f"({num_contractions} contractions, support=${support_level:.2f})"
            )
            return completion, support_level

        except Exception as e:
            self.logger.error(f"❌ Error calculating VCP pattern completion for {symbol}: {e}")
            return 0.0, 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios VCP para smallcaps intradiario

        EARLY ENTRY STRATEGY:
        - NO espera breakout completo (100%)
        - Entra al 80-90% del patrón (antes del breakout)
        - Objetivo: capturar el movimiento desde el inicio

        Returns:
            True si cumple criterios VCP, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            
            # 1. DAILY CONTEXT ANALYSIS (New: Check for Blue Sky / 52-Week Highs)
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)
            is_blue_sky = daily_potential.get('is_52_week_high', False)
            
            if is_blue_sky:
                self.logger.info(f"🌤️ {symbol}: BLUE SKY VCP DETECTED - Enabling Aggressive Mode")

            # 1.5. FUNDAMENTAL ANALYSIS (Float & Halt)
            fundamentals = await self._analyze_smallcap_fundamentals(opportunity)
            is_high_rotation = fundamentals.get('is_high_rotation', False)
            
            # Safety: Halt Risk
            if fundamentals.get('is_halt_risk', False):
                self.logger.warning(f"🛑 {symbol}: ABORT VCP - Too close to LULD Halt Band")
                return False

            # Boost: High Rotation
            if is_high_rotation:
                self.logger.info(f"🚀 {symbol}: HIGH ROTATION VCP ({fundamentals['rotation_factor']:.1f}x) - Prime Setup")

            self.logger.info(f"🔍 {symbol}: Starting VCP Smallcap evaluation (BlueSky={is_blue_sky})")

            # ============================================================
            # VALIDATION 0: Check for duplicate positions
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

            # ============================================================
            # VALIDATION 1: Basic filters (price, volume)
            # ============================================================
            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            quality_score = opportunity.get('quality_score', 0)

            if not (self.min_price <= current_price <= self.max_price):
                self.logger.info(f"⚪ {symbol}: Price ${current_price:.2f} outside range")
                return False

            # Define Supply Exhaustion Context (High Quality / Blue Sky)
            # Used to override Volume and Breakout-Proximity checks
            is_supply_exhaustion = (is_blue_sky or quality_score >= 70.0)

            if volume_ratio < self.min_volume_ratio:
                 if is_supply_exhaustion:
                      self.logger.info(f"✅ {symbol}: Low Volume ({volume_ratio:.1f}x) accepted due to SUPPLY EXHAUSTION/QUALITY (QS={quality_score}, BlueSky={is_blue_sky})")
                 else:
                     self.logger.info(f"⚪ {symbol}: Volume {volume_ratio:.1f}x < min {self.min_volume_ratio:.1f}x and no exhaustion context")
                     return False
            
            # ============================================================
            # VALIDATION 1.5: Quality score filter (avoid low-quality setups)
            # ============================================================
            # quality_score extracted above
            if quality_score < self.min_quality_score:
                self.logger.info(f"⚪ {symbol}: Quality {quality_score:.1f} < min {self.min_quality_score:.1f}")
                return False

            # ============================================================
            # VALIDATION 2: Catalyst requirement (optional for VCP technical pattern)
            # ============================================================
            if self.require_catalyst:
                catalyst = opportunity.get('catalyst_type', 'NONE')
                if catalyst not in self.accepted_catalysts:
                    self.logger.info(f"⚪ {symbol}: No valid catalyst (got: {catalyst})")
                    return False

                self.logger.info(f"✅ {symbol}: Valid catalyst - {catalyst}")

            # ============================================================
            # VALIDATION 3: Get bars and validate minimum data
            # ============================================================
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 15:  # RELAXED: 30 -> 15 bars
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0}/15)")
                return False

            # ============================================================
            # ODS FILTER: Check Opening Drive Structure (Standardized)
            # ============================================================
            is_ods_allowed, confidence_boost = await self.check_ods_filters(symbol, bars, opportunity)
            
            if not is_ods_allowed:
                return False

            # Apply confidence boost
            if 'confidence' in opportunity:
                 opportunity['confidence'] *= confidence_boost



            # ============================================================
            # INTRADAY STRUCTURE FILTERS: VCP pivot timing
            # ============================================================
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Store Intraday Structure data for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # MIDDAY PHASE: Best time for VCP pivot breakouts
            if structure.current_phase == IntradayPhase.MIDDAY:
                # Filter balance (VCP needs breakout)
                # Filter balance (VCP needs breakout)
                if structure.midday_structure == "BALANCE":
                    self.logger.info(
                        f"✅ {symbol}: MIDDAY BALANCE CONFIRMED - Tight consolidation ({structure.balance_range_pct:.2f}%) - "
                        f"Perfect setup for VCP Pivot"
                    )
                    # No return False here! We WANT balance for VCP.

                # BOOST on imbalance (perfect VCP timing)
                if structure.midday_structure == "IMBALANCE_BULLISH":
                    self.logger.info(
                        f"✅ {symbol}: MIDDAY BOOST - Imbalance breakout - "
                        f"Ideal timing for VCP pivot entry"
                    )

            # CONTINUATION: VCP works well on pullbacks
            if structure.continuation_type == "PULLBACK_BULLISH":
                self.logger.info(
                    f"✅ {symbol}: CONTINUATION BOOST - Pullback setup - "
                    f"VCP pivot favorable after pullback"
                )

            # TRAP DETECTION: Filter fake pivots
            if structure.trap_detected:
                self.logger.info(
                    f"⚪ {symbol}: TRAP FILTER - {structure.trap_type} - "
                    f"VCP pivot may be false breakout"
                )
                return False

            # ============================================================
            # VALIDATION 4: VCP Pattern Calculation
            # ============================================================
            completion, support_level = await self._calculate_vcp_completion(
                bars, current_price, symbol, allow_flat_structure=is_supply_exhaustion
            )

            # Relax completion threshold for Supply Exhaustion (1 tight contraction = 40-50% is enough)
            min_completion = 40.0 if is_supply_exhaustion else 60.0

            if completion < min_completion: # Minimum completion for a valid VCP setup
                self.logger.info(f"⚪ {symbol}: VCP pattern completion too low ({completion:.0f}% < {min_completion:.0f}%)")
                return False

            # Extract contractions from the completion calculation (if needed for volume validation)
            contractions = self._detect_contractions(bars)
            num_contractions = len(contractions)

            # Relax contraction count if Blue Sky or Supply Exhaustion (strong momentum/exhaustion needs less consolidation)
            min_contractions = max(1, self.min_contractions - 1) if (is_blue_sky or is_supply_exhaustion) else self.min_contractions
            
            if num_contractions < min_contractions:
                self.logger.info(
                    f"⚪ {symbol}: Insufficient contractions ({num_contractions}/{min_contractions})"
                )
                return False

            # The decreasing contractions check is now part of _calculate_vcp_completion
            # If completion is > 0, it means contractions were valid.

            contraction_ranges = [f"{c['range_pct']:.1f}%" for c in contractions]
            self.logger.info(
                f"✅ {symbol}: VCP pattern detected - {num_contractions} contractions "
                f"(ranges: {contraction_ranges})"
            )

            # ============================================================
            # VALIDATION 5: Volume pattern (must decline during contractions)
            # ============================================================
            # ============================================================
            # VALIDATION 5: Volume pattern (must decline during contractions)
            # ============================================================
            volume_valid = self._validate_volume_pattern(
                contractions, 
                allow_flat_volume=is_supply_exhaustion
            )
            
            # Force accept volume pattern if Blue Sky OR High Rotation (massive interest override)
            if not volume_valid and (is_blue_sky or is_high_rotation):
                 self.logger.info(f"✅ {symbol}: Force accepting volume pattern due to CONTEXT (BlueSky={is_blue_sky}, Rot={is_high_rotation})")
                 volume_valid = True
            
            if not volume_valid:
                self.logger.info(f"⚪ {symbol}: Volume pattern invalid (not declining)")
                return False

            self.logger.info(f"✅ {symbol}: Volume pattern valid (declining during contractions)")

            # ============================================================
            # VALIDATION 7: PIVOT ENTRY (Buy the Reaction, Not the Action)
            # ============================================================
            # NEW LOGIC: Enter on pivot from last contraction, NOT at 98% breakout
            # This provides better entry price and confirms institutional accumulation

            # ============================================================
            # VALIDATION 7: PIVOT ENTRY
            # ============================================================
            pivot_detected, pivot_details, support_level = self._detect_vcp_pivot(
                bars, contractions, current_price, symbol, allow_breakout_buy=is_supply_exhaustion
            )

            if not pivot_detected:
                self.logger.info(f"⚪ {symbol}: No VCP pivot detected - {pivot_details}")
                return False

            # Store support level for dynamic stop loss
            opportunity['support_level'] = support_level

            self.logger.info(f"✅ {symbol}: VCP PIVOT ENTRY - {pivot_details}")

            # ============================================================
            # VALIDATION 8: VWAP strength (avoid weak stocks)
            # ============================================================
            vwap_valid, vwap_reason = self.validate_vwap_strength(
                bars, current_price, opportunity=opportunity
            )

            # Override logic REMOVED: User request to enforce VWAP check
            if is_supply_exhaustion and not vwap_valid:
                # We log it but do NOT force it to True anymore
                self.logger.info(f"⚪ {symbol}: High Quality/Blue Sky but FAILED VWAP ({vwap_reason}) - REJECTING despite supply exhaustion context")


            if not vwap_valid:
                self.logger.info(f"⚪ {symbol}: VWAP validation failed - {vwap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: VWAP validation passed (or overridden) - {vwap_reason}")

            # ============================================================
            # VALIDATION 9: Time restrictions - Use centralized validation
            # ============================================================
            should_check_time = True
            
            # Allow extended hours for ODS Balance / Supply Exhaustion if enabled?
            # No, keep strict hours for now, but use CORRECT time.
            
            is_valid_hours, current_time = self.is_within_entry_hours(
                symbol, 
                timestamp=opportunity.get('timestamp')
            )
            
            # Allow extended hours for Supply Exhaustion (late day accumulation/icebergs often break late)
            if not is_valid_hours and is_supply_exhaustion and current_time <= 15.95:
                 self.logger.info(f"✅ {symbol}: Extending entry window to 15.95 for Supply Exhaustion (current: {current_time:.2f})")
                 is_valid_hours = True

            if not is_valid_hours:
                self.logger.info(f"⚪ {symbol}: Outside trading hours ({current_time:.2f})")
                return False

            # ============================================================
            # ALL VALIDATIONS PASSED - VCP EARLY ENTRY APPROVED
            # ============================================================
            # Calculate proximity for logging
            breakout_level = max(bar.high for bar in bars[-20:]) if len(bars) >= 20 else current_price
            proximity_pct = (current_price / breakout_level) * 100 if breakout_level > 0 else 0

            self.logger.info(
                f"✅ {symbol}: VCP SMALLCAP EARLY ENTRY APPROVED - "
                f"{num_contractions} contractions, {proximity_pct:.1f}% to breakout, "
                f"vol={volume_ratio:.1f}x, catalyst={opportunity.get('catalyst_type', 'NONE')}"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VCP for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de la posición VCP

        EXIT LOGIC:
        1. Standard stops (TP/SL/Trailing) via stop_manager
        2. Breakout failure: si no rompe en 30 min, salir
        3. Loss of structure: si pierde soporte clave

        Returns:
            Tuple[bool, str]: (debe_salir, razón)
        """
        try:
            entry_price = position.get('entry_price', 0)
            entry_time = position.get('entry_time')

            # Prepare position metadata
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0),
                'opportunity_data': position.get('opportunity_data', {})  # Pass dynamic TP/SL data
            }

            # Check standard exits (TP/SL/Trailing/Time)
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None,
                position_metadata=position_metadata
            )

            if should_exit:
                self.logger.info(f"🔴 {symbol}: VCP exit signal - {reason}")
                return True, reason

            # Additional VCP-specific exit: Breakout failure check REMOVED
            # Reason: Patterns do not have a fixed duration. Leaving trade room to breathe.
            # We rely solely on Stop Loss and Trailing Stop.

            return False, "HOLDING"

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VCP exit for {symbol}: {e}")
            return True, "ERROR_EXIT"

    # ========================================================================
    # VCP PATTERN DETECTION METHODS
    # ========================================================================

    def _detect_contractions(self, bars: List) -> List[Dict[str, Any]]:
        """
        Detecta contracciones en el patrón VCP

        Una contracción es un período de consolidación donde:
        - El rango price (high-low) es menor que la contracción anterior
        - Duración típica: 5-45 minutos (intradiario)

        Returns:
            Lista de contracciones detectadas con metadatos:
            [
                {'start_idx': 0, 'end_idx': 10, 'range_pct': 2.5, 'avg_volume': 50000},
                {'start_idx': 11, 'end_idx': 18, 'range_pct': 1.8, 'avg_volume': 35000},
                ...
            ]
        """
        try:
            if len(bars) < 20:
                return []

            contractions = []
            window_size = 10  # Analyze 10-bar windows for contractions

            # Slide window through bars looking for tight ranges
            for i in range(0, len(bars) - window_size, 5):  # Step by 5 bars
                window_bars = bars[i:i + window_size]

                # Calculate range for this window
                window_high = max(bar.high for bar in window_bars)
                window_low = min(bar.low for bar in window_bars)
                window_range_pct = ((window_high - window_low) / window_low) * 100

                # Calculate average volume
                avg_volume = sum(bar.volume for bar in window_bars) / len(window_bars)

                # A contraction is a tight range (< 5% for smallcaps)
                # FIX: Added min limit (> 1.5%) to ignore micro-noise (like RZLV's 0.2% contractions)
                if 1.5 <= window_range_pct < 5.0:
                    contractions.append({
                        'start_idx': i,
                        'end_idx': i + window_size,
                        'range_pct': window_range_pct,
                        'avg_volume': avg_volume,
                        'high': window_high,
                        'low': window_low
                    })

            # Filter: remove overlapping contractions (keep tightest)
            # This prioritizes the smallest range, which is good for VCP, assuming it passed the 1.5% min filter
            contractions = self._filter_overlapping_contractions(contractions)

            # RULE: First contraction must be significant (> 2.5%) 
            # This ensures we are not just seeing a flat line from the start.
            # Real VCP starts with volatility and compresses.
            if contractions and contractions[0]['range_pct'] < 2.5:
                # If the very first contraction is tiny, it's likely just a low liquidity flat line
                # But to be safe, only reject if we have multiple tiny ones (chop)
                if len(contractions) > 3:
                     # Filter completely if pattern starts weak and stays weak
                     return []

            # RULE: Max contractions limit (Infinite Contraction Loop Fix)
            # If we see > 6 contractions, it's likely a channel or chop, not a VCP setup
            if len(contractions) > 6:
                self.logger.info(f"⚪ VCP Reject: Too many contractions ({len(contractions)} > 6) - likely chop/noise")
                return []
            
            return contractions

        except Exception as e:
            self.logger.error(f"Error detecting contractions: {e}")
            return []

    def _filter_overlapping_contractions(
        self,
        contractions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filtra contracciones que se solapan, manteniendo las más tight
        """
        if not contractions:
            return []

        filtered = []
        last_end_idx = -1

        for contraction in sorted(contractions, key=lambda x: x['start_idx']):
            # If doesn't overlap with previous, add it
            if contraction['start_idx'] > last_end_idx:
                filtered.append(contraction)
                last_end_idx = contraction['end_idx']
            # If overlaps but is tighter, replace previous
            elif contraction['range_pct'] < filtered[-1]['range_pct']:
                filtered[-1] = contraction
                last_end_idx = contraction['end_idx']

        return filtered

    def _validate_contractions_decreasing(
        self,
        contractions: List[Dict[str, Any]],
        allow_constant_range: bool = False
    ) -> bool:
        """
        Valida que las contracciones sean decrecientes en tamaño (VCP requirement)

        CRITICAL VCP RULE:
        Cada contracción debe ser más pequeña que la anterior
        Esto indica compresión de volatilidad (spring coiling)
        """
        if len(contractions) < 2:
            return True  # Can't validate with < 2 contractions

        if allow_constant_range:
            return True  # Skip check if flat structure is allowed (Supply Exhaustion)

        # Check each contraction is smaller than previous (allow 10% tolerance)
        for i in range(1, len(contractions)):
            curr_range = contractions[i]['range_pct']
            prev_range = contractions[i-1]['range_pct']

            # Current should be <= previous (with 10% tolerance)
            if curr_range > prev_range * 1.1:
                return False

        return True

    def _validate_volume_pattern(
        self,
        contractions: List[Dict[str, Any]],
        allow_flat_volume: bool = False
    ) -> bool:
        """
        Valida que el volumen decline durante las contracciones (acumulación)
        allow_flat_volume: If True, skips check for Supply Exhaustion/Icebergs

        VCP VOLUME PATTERN:
        - Volumen alto en primera contracción (initial selling)
        - Volumen declina en contracciones subsecuentes (absorption)
        - Indica smart money acumulando silenciosamente
        """
        if len(contractions) < 2:
            return True  # Can't validate with < 2 contractions

        if allow_flat_volume:
            return True  # Skip check for Supply Exhaustion/Icebergs

        # Check volume trend is declining
        volumes = [c['avg_volume'] for c in contractions]

        # At least 60% of contractions should have lower volume than previous
        declining_count = sum(
            1 for i in range(1, len(volumes))
            if volumes[i] <= volumes[i-1] * 1.1  # Allow 10% tolerance
        )

        declining_pct = (declining_count / (len(volumes) - 1)) * 100

        return declining_pct >= 60.0





    def _validate_contraction_trend(self, contractions: List[Dict[str, Any]]) -> bool:
        """
        Valida la dirección de las contracciones para evitar Triángulos Descendientes (Bearish).

        REGLAS:
        1. VCP Alcista Ideal: Lows crecientes (Ascending Triangle / Coil).
        2. Caja/Rectángulo: Lows planos Y Highs planos.
        3. RECHAZAR: Lows planos (Soporte) Y Highs decrecientes (Descending Triangle).
        4. RECHAZAR: Lows decrecientes (Tendencia bajista).
        
        Returns:
            True si el patrón es constructivo (Alcista/Neutro), False si es bajista.
        """
        if len(contractions) < 2:
            return True

        # Analizar tendencia de Lows y Highs
        lows = [c['low'] for c in contractions]
        highs = [c['high'] for c in contractions]

        # 1. Contar Lows decrecientes vs crecientes
        decreasing_lows = 0
        flat_lows = 0
        increasing_lows = 0
        
        for i in range(1, len(lows)):
            change = (lows[i] - lows[i-1]) / lows[i-1]
            if change < -0.001: # -0.1% tolerance
                decreasing_lows += 1
            elif change > 0.001: # +0.1% tolerance
                increasing_lows += 1
            else:
                flat_lows += 1
        
        # Si la mayoría son decrecientes -> BAJISTA
        if decreasing_lows > increasing_lows and decreasing_lows > flat_lows:
            self.logger.info("⚪ Trend Reject: Contractions making Lower Lows")
            return False
            
        # 2. Detectar Triángulo Descendente (Soporte Plano + Highs Decrecientes)
        # Si dominan los Lows Planos, verificar que los Highs no sean decrecientes
        if flat_lows >= increasing_lows:
            decreasing_highs = 0
            for i in range(1, len(highs)):
                if highs[i] < highs[i-1] * 0.995: # -0.5% tolerance (significant drop)
                    decreasing_highs += 1
            
            # Si tenemos lows planos y highs bajando consistentemente
            if decreasing_highs >= len(highs) // 2:
                 self.logger.info("⚪ Trend Reject: Descending Triangle detected (Flat Lows + Lower Highs)")
                 return False

        return True

    # NOTE: _check_multitimeframe_alignment removed - now using check_multi_timeframe_trend
    # from base_worker_logic.py which provides full EMA9/21 trend analysis across 5min, 15min, 60min

    def _check_volume_building(self, bars: List) -> bool:
        """
        Verifica si el volumen está incrementando en las últimas barras (Building),
        lo cual suele preceder o acompañar al breakout.
        """
        try:
            if len(bars) < 15:
                return False

            # Comparar volumen reciente (últimas 3 barras) vs contexto (anteriores 10)
            recent_vol = sum(b.volume for b in bars[-3:]) / 3
            context_vol = sum(b.volume for b in bars[-13:-3]) / 10
            
            if context_vol == 0:
                return True
                
            # Si el volumen está aumentando (o al menos se mantiene alto relativo a la contracción seca)
            # Pedimos un ligero incremento o que sea sustancial
            return recent_vol > context_vol * 1.0

        except Exception:
            return False

    def _detect_vcp_pivot(
        self,
        bars: list,
        contractions: list,
        current_price: float,
        symbol: str,
        allow_breakout_buy: bool = False
    ) -> Tuple[bool, str, float]:
        """
        Detecta entrada en PIVOT de última contracción VCP (85-95% del high)
        Args:
            allow_breakout_buy: If True, entry is allowed even at breakout point (up to 99.5%)
        """
        try:
            if len(bars) < 10 or not contractions:
                return False, "Insufficient data", 0.0

            # 1. Obtener última contracción
            last_contraction = contractions[-1]
            contraction_range_pct = last_contraction['range_pct']

            # 2. Encontrar el high de las últimas 20 barras (breakout level)
            breakout_level = max(bar.high for bar in bars[-20:])

            # 3. Encontrar el pivot (mínimo reciente en última contracción)
            # Buscar en últimas 5-10 barras
            lookback = min(10, len(bars))
            recent_bars = bars[-lookback:]
            pivot_low = min(bar.low for bar in recent_bars)

            # 4. Calcular posición actual respecto al breakout level
            proximity_pct = (current_price / breakout_level) * 100

            # 5. CRITERIO CLAVE: Precio debe estar en 80-95% del high
            # Override: If allow_breakout_buy (Supply Exhaustion), allow up to 101.0% (Breakout)
            upper_limit = 101.0 if allow_breakout_buy else 95.0

            if proximity_pct < 80.0:
                return False, f"Price too far from breakout ({proximity_pct:.1f}% < 80%)", 0.0

            if proximity_pct > upper_limit:
                return False, f"Price too close to breakout ({proximity_pct:.1f}% > {upper_limit}%), wait for pullback", 0.0

            # 6. Verificar que está pivoteando desde el mínimo
            recovery_from_pivot = ((current_price - pivot_low) / pivot_low) * 100
            
            # Relax recovery check if Supply Exhaustion (flat consolidation allowed)
            min_recovery = 0.0 if allow_breakout_buy else 0.3

            if recovery_from_pivot < min_recovery:
                return False, f"Insufficient recovery from pivot ({recovery_from_pivot:.2f}% < {min_recovery}%)", 0.0

            # 7. Verificar volumen seco en última contracción (opcional pero ideal)
            if len(bars) >= 20:
                recent_volume = sum(bar.volume for bar in bars[-10:]) / 10
                avg_volume = sum(bar.volume for bar in bars[-20:]) / 20
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

                if volume_ratio > 0.8:
                    # Volumen no está seco, pero no es bloqueante
                    details = (f"Pivot at {proximity_pct:.1f}% of high ${breakout_level:.2f}, "
                             f"recovered {recovery_from_pivot:.1f}% from low ${pivot_low:.2f} "
                             f"(⚠️ volume ratio {volume_ratio:.2f} not dry)")
                else:
                    details = (f"Pivot at {proximity_pct:.1f}% of high ${breakout_level:.2f}, "
                             f"recovered {recovery_from_pivot:.1f}% from low ${pivot_low:.2f} "
                             f"(✅ dry volume {volume_ratio:.2f})")
            else:
                details = (f"Pivot at {proximity_pct:.1f}% of high ${breakout_level:.2f}, "
                         f"recovered {recovery_from_pivot:.1f}% from low ${pivot_low:.2f}")

            self.logger.info(f"🎯 {symbol}: VCP PIVOT DETECTED - {details} (support: ${pivot_low:.2f})")
            return True, details, pivot_low

        except Exception as e:
            self.logger.error(f"Error detecting VCP pivot for {symbol}: {e}")
            return False, f"Error: {str(e)}", 0.0

    def _determine_trading_horizon(
        self,
        signal_data: Dict[str, Any]
    ) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para VCP

        VCP horizons:
        - INTRADAY (4-6h): Default for intraday VCP
        - SWING_SHORT (24h): Strong VCP with daily context support
        - SCALP (1h): Weak VCP or late entry
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        daily_potential = signal_data.get('daily_potential', {})

        can_swing_short = daily_potential.get('can_swing_short', False)

        # SWING_SHORT: Strong VCP + daily context allows
        if confidence > 80 and risk_reward > 3.0 and can_swing_short:
            return TradingHorizon.SWING_SHORT, 24.0

        # INTRADAY: Standard VCP play (most common)
        elif confidence > 60 and risk_reward > 2.0:
            return TradingHorizon.INTRADAY, 6.0

        # SCALP: Weaker VCP or late entry
        else:
            return TradingHorizon.SCALP, 1.0

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager"""
        success = await super()._execute_entry(opportunity)

        if success:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager
            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} with VCP stop manager")

            # Register with unified position manager
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 150.0)

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='vcp_smallcap',
                    position_data={
                        'strategy': 'vcp_smallcap',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (VCP trading)")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager"""
        # Calculate PnL
        pnl_pct = None

        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()

        if unified_manager:
            position_data = unified_manager.get_position(symbol)
            if position_data:
                entry_price = position_data.get('entry_price', 0)
                if entry_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Unregister from unified position manager
        if unified_manager:
            unified_manager.unregister_position(symbol, 'vcp_smallcap', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (VCP trading)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    def _get_time_from_timestamp(self, timestamp) -> float:
        """
        Convierte timestamp a hora decimal (ej: 14.5 para 14:30)
        """
        try:
            import pytz
            from datetime import datetime

            if isinstance(timestamp, str):
                try:
                    from dateutil import parser
                    dt = parser.parse(timestamp)
                except Exception:
                    return 12.0
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                return 12.0

            # Validate dt is datetime before accessing tzinfo
            if not isinstance(dt, datetime):
                return 12.0

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
