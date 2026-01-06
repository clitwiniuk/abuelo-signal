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

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="vcp_smallcap",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración VCP específica
        self.min_contractions = getattr(config, 'vcp_min_contractions', 2)  # RELAXED: 3 → 2 contracciones
        self.max_contraction_minutes = getattr(config, 'vcp_max_contraction_minutes', 45)  # Max 45min por contracción
        self.entry_threshold_pct = getattr(config, 'vcp_entry_threshold', 98.0)  # Entrar al 98% del high
        self.min_price = getattr(config, 'vcp_min_price', 0.5)  # RELAXED: 1.0 → 0.5 for penny smallcaps
        self.max_price = getattr(config, 'vcp_max_price', 25.0)  # RELAXED: 20 → 25 to match other workers
        self.min_volume_ratio = getattr(config, 'vcp_min_volume_ratio', 0.7)  # RELAXED: 1.5 → 0.7 (VCP forma con bajo vol)
        self.min_quality_score = getattr(config, 'vcp_min_quality_score', 40.0)  # NEW: Filter low-quality setups

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
            f"🎯 VCP Smallcap Worker configured (RELAXED for smallcaps): "
            f"contractions>={self.min_contractions}, Q>={self.min_quality_score}, "
            f"price=${self.min_price}-${self.max_price}, vol>={self.min_volume_ratio}x, "
            f"MTF={self.use_multitimeframe}, catalyst_required={self.require_catalyst} | "
            f"Exits: TP=15%, SL=5%, Trail=8%/4%, Max=6h"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calcula completitud del patrón VCP (0-100%)

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
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0
            support_level = 0.0

            # Get bars for analysis
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 15:  # RELAXED: 20 → 15 bars minimum
                return 0.0, 0.0

            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Stage 1: Basic data validation (20%)
            if current_price > 0 and volume_ratio > 0:
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: Basic data validated")

            # Stage 2-3: Detect contractions (20% each)
            contractions = self._detect_contractions(bars)
            num_contractions = len(contractions)

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

            # Stage 4: Price near breakout level (10%)
            if num_contractions >= 3:
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
            self.logger.error(f"❌ Error calculating VCP pattern completion: {e}")
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
            self.logger.info(f"🔍 {symbol}: Starting VCP Smallcap evaluation")

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

            if not (self.min_price <= current_price <= self.max_price):
                self.logger.info(f"⚪ {symbol}: Price ${current_price:.2f} outside range")
                return False

            if volume_ratio < self.min_volume_ratio:
                self.logger.info(f"⚪ {symbol}: Volume {volume_ratio:.1f}x < min {self.min_volume_ratio:.1f}x")
                return False

            # ============================================================
            # VALIDATION 1.5: Quality score filter (avoid low-quality setups)
            # ============================================================
            quality_score = opportunity.get('quality_score', 0)
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
            if not bars or len(bars) < 15:  # RELAXED: 30 → 15 bars
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0}/15)")
                return False

            # ============================================================
            # ODS FILTER: Check Opening Drive Structure
            # ============================================================
            from core.ods_classifier import ODSDayType

            ods = await self.get_ods_for_symbol(symbol, bars)

            # Store ODS data for adaptive risk sizing
            opportunity['ods_data'] = ods

            # ODS CONTEXTUAL ADJUSTMENT (SMALLCAP-AWARE)
            confidence_boost = 1.0

            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.3  # +30% confidence
                self.logger.info(
                    f"✅ {symbol}: ODS BOOST - Bullish trend drive "
                    f"(strength={ods.strength:.1f}) - Favorable for VCP breakouts"
                )
            elif ods.day_type == ODSDayType.STRONG_BULLISH_OPEN:
                confidence_boost = 1.4  # +40% for strong opens
                self.logger.info(
                    f"🔥 {symbol}: ODS STRONG BOOST - Strong bullish open "
                    f"(strength={ods.strength:.1f}) - High conviction VCP setup"
                )
            elif ods.day_type == ODSDayType.MODERATE_BULLISH_OPEN:
                confidence_boost = 1.2  # +20% for moderate opens
                self.logger.info(
                    f"✅ {symbol}: ODS MODERATE BOOST - Moderate bullish open "
                    f"(strength={ods.strength:.1f}) - Good VCP setup"
                )
            elif ods.day_type == ODSDayType.FAILED_DRIVE:
                confidence_boost = 0.7  # -30% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Failed drive day "
                    f"(momentum reversed) - Reduced confidence but allowing VCP reversal pivot"
                )
            elif ods.day_type == ODSDayType.BALANCE_DAY:
                confidence_boost = 0.8  # -20% confidence (reduce, don't reject)
                self.logger.info(
                    f"⚠️ {symbol}: ODS REDUCTION - Balance day "
                    f"(narrow range={ods.range_pct:.2f}%) - Reduced confidence but allowing VCP"
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
            # INTRADAY STRUCTURE FILTERS: VCP pivot timing
            # ============================================================
            from core.intraday_structure_classifier import IntradayPhase

            structure = await self.get_intraday_structure_for_symbol(symbol, bars)

            # Store Intraday Structure data for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # MIDDAY PHASE: Best time for VCP pivot breakouts
            if structure.current_phase == IntradayPhase.MIDDAY:
                # Filter balance (VCP needs breakout)
                if structure.midday_structure == "BALANCE":
                    self.logger.info(
                        f"⚪ {symbol}: MIDDAY FILTER - Tight balance - "
                        f"Wait for imbalance before VCP pivot"
                    )
                    return False

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
            # VALIDATION 4: Detect VCP contractions (CORE PATTERN)
            # ============================================================
            contractions = self._detect_contractions(bars)
            num_contractions = len(contractions)

            if num_contractions < self.min_contractions:
                self.logger.info(
                    f"⚪ {symbol}: Insufficient contractions ({num_contractions}/{self.min_contractions})"
                )
                return False

            # Validate contractions are decreasing in size (VCP requirement)
            if not self._validate_contractions_decreasing(contractions):
                self.logger.info(f"⚪ {symbol}: Contractions not decreasing in size (invalid VCP)")
                return False

            contraction_ranges = [f"{c['range_pct']:.1f}%" for c in contractions]
            self.logger.info(
                f"✅ {symbol}: VCP pattern detected - {num_contractions} contractions "
                f"(ranges: {contraction_ranges})"
            )

            # ============================================================
            # VALIDATION 5: Volume pattern (must decline during contractions)
            # ============================================================
            volume_valid = self._validate_volume_pattern(contractions)
            if not volume_valid:
                self.logger.info(f"⚪ {symbol}: Volume pattern invalid (not declining)")
                return False

            self.logger.info(f"✅ {symbol}: Volume pattern valid (declining during contractions)")

            # ============================================================
            # VALIDATION 7: PIVOT ENTRY (Buy the Reaction, Not the Action)
            # ============================================================
            # NEW LOGIC: Enter on pivot from last contraction, NOT at 98% breakout
            # This provides better entry price and confirms institutional accumulation

            pivot_detected, pivot_details, support_level = self._detect_vcp_pivot(
                bars, contractions, current_price, symbol
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

            if not vwap_valid:
                self.logger.info(f"⚪ {symbol}: VWAP validation failed - {vwap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")

            # ============================================================
            # VALIDATION 9: Time restrictions - Use centralized validation
            # ============================================================
            is_valid_hours, current_time = self.is_within_entry_hours(symbol)
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

            # Additional VCP-specific exit: Breakout failure check
            if entry_time:
                time_in_position = (datetime.now() - entry_time).total_seconds() / 60  # minutes

                # If no breakout after 30 minutes, exit (pattern failed)
                if time_in_position > 30:
                    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                    # If not making progress (< 3% gain after 30 min), exit
                    if pnl_pct < 3.0:
                        self.logger.info(
                            f"🔴 {symbol}: VCP breakout failure - "
                            f"no progress after {time_in_position:.0f} min (PnL: {pnl_pct:+.1f}%)"
                        )
                        return True, "VCP_BREAKOUT_FAILURE"

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
                if window_range_pct < 5.0:
                    contractions.append({
                        'start_idx': i,
                        'end_idx': i + window_size,
                        'range_pct': window_range_pct,
                        'avg_volume': avg_volume,
                        'high': window_high,
                        'low': window_low
                    })

            # Filter: remove overlapping contractions (keep tightest)
            contractions = self._filter_overlapping_contractions(contractions)

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
        contractions: List[Dict[str, Any]]
    ) -> bool:
        """
        Valida que las contracciones sean decrecientes en tamaño (VCP requirement)

        CRITICAL VCP RULE:
        Cada contracción debe ser más pequeña que la anterior
        Esto indica compresión de volatilidad (spring coiling)
        """
        if len(contractions) < 2:
            return True  # Can't validate with < 2 contractions

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
        contractions: List[Dict[str, Any]]
    ) -> bool:
        """
        Valida que el volumen decline durante las contracciones (acumulación)

        VCP VOLUME PATTERN:
        - Volumen alto en primera contracción (initial selling)
        - Volumen declina en contracciones subsecuentes (absorption)
        - Indica smart money acumulando silenciosamente
        """
        if len(contractions) < 2:
            return True  # Can't validate with < 2 contractions

        # Check volume trend is declining
        volumes = [c['avg_volume'] for c in contractions]

        # At least 60% of contractions should have lower volume than previous
        declining_count = sum(
            1 for i in range(1, len(volumes))
            if volumes[i] <= volumes[i-1] * 1.1  # Allow 10% tolerance
        )

        declining_pct = (declining_count / (len(volumes) - 1)) * 100

        return declining_pct >= 60.0

    def _check_volume_building(self, bars: List) -> bool:
        """
        Verifica que el volumen esté building up (preparándose para breakout)

        Returns:
            True si volumen está building, False si no
        """
        try:
            if len(bars) < 10:
                return False

            # Compare last 3 bars vs previous 7 bars
            recent_volume = sum(bar.volume for bar in bars[-3:]) / 3
            previous_volume = sum(bar.volume for bar in bars[-10:-3]) / 7

            # Recent volume should be higher (building up)
            return recent_volume > previous_volume * 1.2  # 20% increase

        except Exception as e:
            self.logger.error(f"Error checking volume building: {e}")
            return False

    # NOTE: _check_multitimeframe_alignment removed - now using check_multi_timeframe_trend
    # from base_worker_logic.py which provides full EMA9/21 trend analysis across 5min, 15min, 60min

    def _detect_vcp_pivot(
        self,
        bars: list,
        contractions: list,
        current_price: float,
        symbol: str
    ) -> Tuple[bool, str]:
        """
        Detecta entrada en PIVOT de última contracción VCP (85-95% del high)

        Strategy: "Buy the Reaction, Not the Action"
        - NO espera al breakout (98%+) = comprar en máximos
        - Entra en el PIVOT de la última contracción = comprar en pullback

        Ventajas:
        1. Mejor precio de entrada (5-10% más barato que breakout)
        2. Stop loss más ajustado (debajo del pivot)
        3. Mayor R:R (más margen hasta resistencia)
        4. Confirma acumulación institucional (volumen seco en contracción)

        Criterios:
        1. Última contracción tiene volumen seco (< 60% average)
        2. Precio está pivoteando desde el mínimo de la contracción
        3. Precio está en 85-95% del high (NO 98%+)
        4. Precio muestra recuperación (+0.5% desde mínimo reciente)

        Args:
            bars: Historical bars
            contractions: Lista de contracciones detectadas
            current_price: Precio actual
            symbol: Symbol para logging

        Returns:
            Tuple (pivot_detected: bool, details: str, support_level: float)
            support_level is the pivot_low for dynamic stop loss
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

            # 5. CRITERIO CLAVE: Precio debe estar en 80-95% del high (RELAXED from 85-95%)
            #    NO al 98%+ (eso es comprar en máximos)
            if proximity_pct < 80.0:
                return False, f"Price too far from breakout ({proximity_pct:.1f}% < 80%)", 0.0

            if proximity_pct > 95.0:
                return False, f"Price too close to breakout ({proximity_pct:.1f}% > 95%), wait for pullback", 0.0

            # 6. Verificar que está pivoteando desde el mínimo
            recovery_from_pivot = ((current_price - pivot_low) / pivot_low) * 100

            if recovery_from_pivot < 0.3:
                return False, f"Insufficient recovery from pivot ({recovery_from_pivot:.2f}% < 0.3%)", 0.0

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

            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif hasattr(timestamp, 'hour'):
                dt = timestamp
            else:
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
