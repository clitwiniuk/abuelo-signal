"""
Daily Plays Worker Logic
Worker específico para estrategia Daily Plays (Catalyst-driven breakouts)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class DailyPlaysWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Daily Plays

    Enfoque: Catalyst-driven breakout trading + Reversal Trading
    Ideal para FDA approvals, M&A, earnings, breakthrough news
    Detecta también reversiones alcistas desde niveles de sobreventa

    Criterios de entrada NORMAL (Catalyst Mode):
    1. Catalyst fuerte (FDA, M&A, EARNINGS, BREAKTHROUGH)
    2. Volume ratio >= 0.5x (explosión de volumen)
    3. Precio en rango smallcap ($1-$50)
    4. Quality score >= 50.0 (catalyst quality matters)
    5. Precio > VWAP intraday (confirmación de fortaleza)
    6. Daily Context Check (EVITA TRAMPAS INSTITUCIONALES):
       - RSI daily < 70 (no overbought)
       - MACD daily no extremo
       - NO cerca de resistencia histórica (> 2% distancia)
       - NO 5+ días consecutivos alcistas
       - NO distribución institucional detectada
    7. 1 confirmación (30s) para no perder momentum

    Criterios de entrada REVERSAL MODE (Oversold Bounce):
    - 4+ señales de reversión detectadas (de 6 posibles):
      1. RSI < 35 (oversold)
      2. Cerca de soporte 30-day (< 3%)
      3. 3+ días consecutivos bajistas
      4. MACD histogram increasing (divergencia positiva)
      5. Volume declining (exhaustion)
      6. Price stabilizing (volatilidad baja)
    - Requisitos RELAJADOS cuando reversal detectado:
      * Catalyst opcional (no requerido)
      * Volume ratio >= 1.5x (vs 2.0x)
      * Quality score >= 40 (vs 50)
      * VWAP requirement relaxed

    Criterios de salida (via WorkerStopManager):
    - FOMO Exhaustion (prioridad 0)
    - Trailing stop: 6% activation, 3% distance (prioridad 1)
    - Take profit: 20% (prioridad 2)
    - Stop loss: 5% (prioridad 3)
    - Time-based: 8 horas máximo (prioridad 4)
    - END_OF_DAY: 15:56 ET (prioridad 5)
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="daily_plays",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Daily Plays - SMALLCAP OPTIMIZED
        self.strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT', 'NEWS', 'ANALYST']  # RELAXED: Added NEWS, ANALYST
        # Read min_volume_ratio from config (centralized)
        from core.service_locator import get_service_locator
        config = get_service_locator().get_config()
        self.min_volume_ratio = getattr(config, 'min_volume_ratio', 1.2)  # SMALLCAP: Relaxed from 2.0 to 1.2
        self.min_price = 0.5          # Precio mínimo - RELAXED: From 1.0 to 0.5
        self.max_price = 25.0         # Precio máximo (smallcaps) - RELAXED: From 15 to 25
        self.min_quality_score = 35.0 # SMALLCAP: Relaxed from 75.0 to 35.0 (realistic for smallcaps)

        # Entry confirmation tracking (ajustado para estrategia de catalyst)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 1    # Catalyst plays: 1 confirmación (30s) para no perder momentum
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # First 30-minute high tracking (9:30-10:00 AM breakout strategy)
        self.first_half_hour_highs = {}  # {symbol: price}
        self.first_half_hour_tracked = {}  # {symbol: bool}
        self.ema_period = 9  # EMA9 for first 30min breakout
        self.volume_multiplier_30min = 1.5  # Volume spike for breakout confirmation

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'DAILY_PLAYS_STRATEGY')



            # Load Reversal Mode configuration
            self.enable_reversal_mode = getattr(config, 'enable_reversal_mode', True)
            self.reversal_min_rsi = getattr(config, 'reversal_min_rsi', 35.0)
            self.reversal_min_signals = int(getattr(config, 'reversal_min_signals', 4))
            self.reversal_max_support_distance = getattr(config, 'reversal_max_support_distance', 3.0)
            self.reversal_volume_ratio_relaxed = getattr(config, 'reversal_volume_ratio_relaxed', 1.5)
            self.reversal_quality_score_relaxed = getattr(config, 'reversal_quality_score_relaxed', 40.0)

        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,
                take_profit_pct=20.0,
                quick_target_pct=7.0,
                trailing_activation=3.0,
                trailing_distance=2.0,
                max_position_hours=8.0
            ))

        # Reversal mode configuration (hardcoded defaults - config is UnifiedConfig dataclass)
        self.enable_reversal_mode = True
        self.reversal_min_rsi = 35.0
        self.reversal_min_signals = 4
        self.reversal_max_support_distance = 3.0
        self.reversal_volume_ratio_relaxed = 1.5
        self.reversal_quality_score_relaxed = 40.0

        self.logger.info(
            f"🎯 Daily Plays Worker configured: "
            f"catalysts={self.strong_catalysts}, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}, Q>={self.min_quality_score}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")
        if self.enable_reversal_mode:
            self.logger.info(
                f"   Reversal Mode ENABLED: RSI<{self.reversal_min_rsi}, "
                f"{self.reversal_min_signals}/6 signals required"
            )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calcula completitud del patrón Daily Plays (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Daily Plays Pattern Stages:
        1. [25%] Catalyst detected + price range
        2. [50%] Quality & catalyst strength validated
        3. [75%] Daily context safe + VWAP strength
        4. [85%] CATALYST REACTING (EARLY ENTRY - price moving but controlled)
        5. [100%] PARABOLIC MOVE (LATE - catalyst fully priced in)

        Early Entry Target: 85% = Catalyst reacting, not yet parabolic

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (Pattern completion percentage (0.0-100.0), support_level for dynamic stop)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0  # Initialize completion to ensure it's never None

            catalyst_type = opportunity.get('catalyst_type', '')
            catalyst_strength = opportunity.get('catalyst_strength', 0)
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)
            gap_pct = abs(opportunity.get('gap_percentage', 0))

            # Check daily context first (needed for reversal/safety checks)
            daily_context = await self._check_daily_context(symbol, current_price)

            # Stage 1: Catalyst + price range (25%)
            # Allow TECHNICAL catalyst for technical setups (gap breakouts, volume surges, etc.)
            catalyst_ok = (catalyst_type in self.strong_catalysts or catalyst_type in ['TECHNICAL', 'OTHER'])
            price_ok = self.min_price <= current_price <= self.max_price

            if catalyst_ok and price_ok:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 1 passed (25%) - Catalyst: {catalyst_type}, Price: ${current_price:.2f}"
                )
            elif self.enable_reversal_mode and daily_context.get('reversal', {}).get('is_reversal', False):
                # Reversal setup detected - catalyst not required
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 1 passed (25%) - Reversal setup (catalyst optional)"
                )
            else:
                # More specific error message
                reason_parts = []
                if not catalyst_ok:
                    reason_parts.append(f"Catalyst '{catalyst_type}' not in strong_catalysts {self.strong_catalysts} and not TECHNICAL")
                if not price_ok:
                    reason_parts.append(f"Price ${current_price:.2f} out of range ${self.min_price}-${self.max_price}")

                self.logger.info(
                    f"📊 {symbol}: ❌ Stage 1 FAILED (0%) - {' AND '.join(reason_parts)}"
                )
                return 0.0

            # Stage 2: Quality & catalyst strength (50%)
            min_quality = (self.reversal_quality_score_relaxed
                          if daily_context.get('reversal', {}).get('is_reversal', False)
                          else self.min_quality_score)

            # HIGH QUALITY TECHNICAL EXCEPTION: A/A+ technical setups don't need strong catalyst
            is_high_quality_technical = (
                catalyst_type == 'TECHNICAL' and
                quality_score >= 75  # A or A+ setup
            )

            # FIX: Only strong catalysts (FDA, M&A, Earnings beats) - was >= 5
            if quality_score >= min_quality and catalyst_strength >= 7:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 2 passed (50%) - Quality: {quality_score:.1f}>={min_quality}, Strength: {catalyst_strength}>=5"
                )
            elif is_high_quality_technical:
                # High-quality technical setups (A/A+) pass without strong catalyst
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 2 passed (50%) - High-quality TECHNICAL setup (Q={quality_score:.1f}>=75)"
                )
            elif daily_context.get('reversal', {}).get('is_reversal', False):
                # Reversal mode - relaxed requirements
                completion += 25.0
                self.logger.info(f"📊 {symbol}: ✅ Stage 2 passed (50%) - Reversal relaxed")
            else:
                self.logger.info(
                    f"📊 {symbol}: ❌ Stage 2 FAILED ({completion:.0f}%) - Quality: {quality_score:.1f}<{min_quality} OR Strength: {catalyst_strength}<5"
                )
                return completion, 0.0

            # Stage 3: Daily context + VWAP (75%)
            if not daily_context['is_safe']:
                self.logger.info(
                    f"📊 {symbol}: ❌ Stage 3 FAILED ({completion:.0f}%) - Daily context unsafe: {daily_context['reason']}"
                )
                return completion, 0.0

            # Get VWAP from bars_history if available
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_price = self.calculate_vwap_from_bars(bars) if bars else None
            vwap_str = f"${vwap_price:.2f}" if vwap_price else "N/A"

            # NEW LOGIC: Detect recovery from recent low back above VWAP
            # This catches pullbacks and bounces - much better entry than buying at highs
            support_level = 0.0  # For dynamic stop loss
            if vwap_price and bars and len(bars) >= 5:
                recent_low_detected, recovery_details, support_level = self._detect_vwap_recovery(bars, vwap_price, current_price, symbol)

                if recent_low_detected:
                    # Perfect entry: Price made a low, then recovered above VWAP
                    completion += 25.0
                    self.logger.info(
                        f"📊 {symbol}: ✅ Stage 3 passed (75%) - VWAP RECOVERY detected: {recovery_details} (support: ${support_level:.2f})"
                    )
                elif current_price >= vwap_price:
                    # Acceptable: Price above VWAP but no clear recovery signal
                    completion += 25.0
                    self.logger.info(
                        f"📊 {symbol}: ✅ Stage 3 passed (75%) - Price ${current_price:.2f} >= VWAP {vwap_str}"
                    )
                else:
                    # Price below VWAP - wait for recovery
                    completion += 15.0
                    self.logger.info(
                        f"📊 {symbol}: ⚠️ Stage 3 partial (65%) - Price ${current_price:.2f} < VWAP {vwap_str}, waiting for recovery"
                    )
                    return completion, 0.0
            elif vwap_price and current_price >= vwap_price:
                # Fallback: Not enough bars for recovery detection, just check price > VWAP
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 3 passed (75%) - Price ${current_price:.2f} >= VWAP {vwap_str}"
                )
            else:
                # Price below VWAP or no VWAP available
                completion += 15.0
                self.logger.info(
                    f"📊 {symbol}: ⚠️ Stage 3 partial (65%) - Price ${current_price:.2f} below VWAP {vwap_str}"
                )
                return completion, 0.0

            # Stage 4: CONTROLLED vs PARABOLIC MOVE (85-100%)
            # Detect if catalyst reacting normally (early) or parabolic (late)

            # Check gap magnitude:
            # - Gap 0-10% = controlled reaction (EARLY ENTRY)
            # - Gap > 15% = parabolic move (LATE, too extended)

            if gap_pct <= 10.0:
                # Controlled reaction - early entry window
                completion += 10.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 4 passed (85%) - CONTROLLED REACTION: gap {gap_pct:.1f}% <= 10% (not parabolic)"
                )
            else:
                # Parabolic move - catalyst fully priced in, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: ⚠️ Stage 4 PARABOLIC (100%) - gap {gap_pct:.1f}% > 10% (too extended, too late)"
                )
                return completion, support_level

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Daily Plays pattern = {completion:.1f}% "
                f"(catalyst={catalyst_type}, gap={gap_pct:.1f}%, "
                f"price=${current_price:.2f}, VWAP={vwap_str}, support=${support_level:.2f})"
            )

            return completion, support_level

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0.0, 0.0

    def _is_trading_hours(self, time_decimal: float) -> bool:
        """
        DEPRECATED: Use centralized is_within_entry_hours() from BaseWorkerLogic

        This method is kept for backward compatibility but delegates to centralized validation.

        Args:
            time_decimal: Time as decimal hours (e.g., 9.5 = 9:30 AM)

        Returns:
            True if within allowed trading hours, False otherwise
        """
        # Delegate to centralized validation from BaseWorkerLogic
        is_valid, _ = self.is_within_entry_hours()
        return is_valid

    def _get_time_from_timestamp(self, timestamp) -> float:
        """
        Convert timestamp to decimal hours in US/Eastern timezone

        Args:
            timestamp: Timestamp (datetime, str, or numeric)

        Returns:
            Time as decimal hours (e.g., 9.5 = 9:30 AM ET)
        """
        try:
            import pytz
            from datetime import datetime

            eastern = pytz.timezone('US/Eastern')

            # Convert timestamp to datetime if needed
            if isinstance(timestamp, str):
                from dateutil import parser
                dt = parser.parse(timestamp)
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                # Fallback to current time
                dt = datetime.now()

            # FIX: Always convert to Eastern time properly
            # datetime.now() returns local time (Spain), so we need to localize it first
            if dt.tzinfo is None:
                # Assume input is in Spain timezone (Europe/Madrid) and convert to ET
                spain_tz = pytz.timezone('Europe/Madrid')
                dt = spain_tz.localize(dt)
            else:
                # If already has timezone, ensure it's converted to Eastern
                dt = dt.astimezone(eastern)

            # Convert to decimal hours
            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.error(f"Error converting timestamp to time: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Daily Plays

        TWO ENTRY MODES:
        1. CATALYST MODE: Enter at 75-95% pattern completion (catalyst aligning)
        2. FIRST 30MIN BREAKOUT MODE: Enter on breakout above 9:30-10:00 AM high

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # ====
            # CRITICAL VALIDATION 0: Check for duplicate positions
            # ====
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

            # ====
            # ODS FILTER: Check Opening Drive Structure
            # ENHANCEMENT: Use scanner-provided ODS data if available (more efficient)
            # ====
            from core.ods_classifier import ODSDayType

            # Try to use ODS data from scanner first (already calculated)
            ods_from_scanner = opportunity.get('ods_data')
            if ods_from_scanner and isinstance(ods_from_scanner, dict):
                # Scanner provided ODS data - reconstruct ODSData object
                from core.ods_classifier import ODSData
                ods = ODSData(
                    day_type=ODSDayType[ods_from_scanner.get('day_type', 'INSUFFICIENT_DATA')],
                    direction=ods_from_scanner.get('direction', 'NONE'),
                    strength=ods_from_scanner.get('strength', 0.0),
                    open_price=ods_from_scanner.get('open_price', 0.0) if 'open_price' in ods_from_scanner else 0.0,
                    high_12min=ods_from_scanner.get('high_12min', 0.0) if 'high_12min' in ods_from_scanner else 0.0,
                    low_12min=ods_from_scanner.get('low_12min', 0.0) if 'low_12min' in ods_from_scanner else 0.0,
                    close_12min=ods_from_scanner.get('close_12min', 0.0) if 'close_12min' in ods_from_scanner else 0.0,
                    range_pct=ods_from_scanner.get('range_pct', 0.0),
                    distance_from_open_pct=ods_from_scanner.get('distance_from_open_pct', 0.0) if 'distance_from_open_pct' in ods_from_scanner else 0.0,
                    volume_ratio=ods_from_scanner.get('volume_ratio', 0.0),
                    upside_move_pct=ods_from_scanner.get('upside_move_pct', 0.0),
                    downside_move_pct=ods_from_scanner.get('downside_move_pct', 0.0)
                )
                ods.classification = ods_from_scanner.get('classification', '')
                self.logger.debug(f"✅ {symbol}: Using ODS data from scanner (efficient)")
            else:
                # Fallback: Calculate ODS ourselves (legacy behavior)
                ods = await self.get_ods_for_symbol(symbol, bars)
                self.logger.debug(f"ℹ️ {symbol}: Calculating ODS locally (scanner didn't provide)")

            # Store ODS data for adaptive risk sizing
            opportunity['ods_data'] = ods

            # ODS FILTERS DISABLED - ARCHITECTURAL DECOUPLING
            # Pattern-specific filtering moved to dedicated ODS-driven worker
            # This worker now operates independently based on its own rules

            # FILTER 1: Skip FAILED DRIVE days (catalyst momentum reversed) - DISABLED
            # if ods.day_type == ODSDayType.FAILED_DRIVE:
            #     self.logger.info(
            #         f"⚪ {symbol}: ODS FILTER - Failed drive day "
            #         f"(momentum reversed @ {ods.distance_from_open_pct:.2f}% from open) - "
            #         f"Catalyst plays don't work on reversals"
            #     )
            #     return False

            # FILTER 2: Skip BALANCE days (no clear trend) - DISABLED
            # if ods.day_type == ODSDayType.BALANCE_DAY:
            #     self.logger.info(
            #         f"⚪ {symbol}: ODS FILTER - Balance day "
            #         f"(range={ods.range_pct:.2f}%, vol={ods.volume_ratio:.1f}x) - "
            #         f"No trend, avoid catalyst breakouts"
            #     )
            #     return False

            # Log ODS for informational purposes only (used for adaptive risk sizing)
            self.logger.debug(
                f"ℹ️ {symbol}: ODS={ods.day_type.value} (direction={ods.direction}, "
                f"strength={ods.strength:.1f}) - NOT used for filtering"
            )

            # ODS CONTEXTUAL ADJUSTMENT (SMALLCAP-AWARE)
            confidence_boost = 1.0

            if ods.day_type == ODSDayType.TREND_DRIVE_BULLISH:
                confidence_boost = 1.3  # +30% confidence
                self.logger.info(
                    f"✅ {symbol}: ODS BOOST - Bullish trend drive "
                    f"(strength={ods.strength:.1f}, +{ods.distance_from_open_pct:.2f}%) - "
                    f"Catalyst alignment favorable"
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
                confidence_boost = 0.9  # REDUCED from -20% to -10% for smallcaps
                self.logger.info(
                    f"⚠️ {symbol}: ODS LIGHT REDUCTION - Balance day "
                    f"(narrow range={ods.range_pct:.2f}%) - Smallcap catalyst may still work"
                )

            # Log ODS status
            if ods.day_type == ODSDayType.PENDING:
                self.logger.debug(f"🕐 {symbol}: ODS pending (before 9:42 AM)")
            elif ods.day_type != ODSDayType.INSUFFICIENT_DATA:
                self.logger.info(
                    f"🕐 {symbol}: ODS={ods.day_type.value}, direction={ods.direction}, "
                    f"strength={ods.strength:.1f}"
                )

            # ====
            # INTRADAY STRUCTURE FILTERS: Check contextual patterns (6 patterns)
            # ENHANCEMENT: Use scanner-provided structure data if available (more efficient)
            # ====
            from core.intraday_structure_classifier import IntradayPhase, IntradayStructureData

            # Try to use Intraday Structure data from scanner first (already calculated)
            structure_from_scanner = opportunity.get('intraday_structure')
            if structure_from_scanner and isinstance(structure_from_scanner, dict):
                # Scanner provided structure data - reconstruct IntradayStructureData object
                # Scanner only sends: current_phase, continuation_type, liquidity_sweep_detected,
                # sweep_direction, midday_structure
                structure = IntradayStructureData(
                    symbol=symbol,
                    current_phase=IntradayPhase[structure_from_scanner.get('current_phase', 'OPENING_DRIVE')]
                )
                # Update fields that scanner provides
                structure.continuation_type = structure_from_scanner.get('continuation_type', 'PENDING')
                structure.liquidity_sweep_detected = structure_from_scanner.get('liquidity_sweep_detected', False)
                structure.sweep_direction = structure_from_scanner.get('sweep_direction', 'NONE')
                structure.midday_structure = structure_from_scanner.get('midday_structure', 'PENDING')

                self.logger.debug(f"✅ {symbol}: Using Intraday Structure data from scanner (efficient)")
            else:
                # Fallback: Calculate Structure ourselves (legacy behavior)
                structure = await self.get_intraday_structure_for_symbol(symbol, bars)
                self.logger.debug(f"ℹ️ {symbol}: Calculating Intraday Structure locally (scanner didn't provide)")

            # Store Intraday Structure data for adaptive risk sizing
            opportunity['intraday_structure'] = structure

            # CONTINUATION PHASE (12-30 min): Pullback confirmation
            if structure.current_phase == IntradayPhase.CONTINUATION:
                if structure.continuation_type == "PULLBACK_BULLISH":
                    confidence_boost *= 1.2  # Additional +20% on pullback
                    self.logger.info(
                        f"✅ {symbol}: CONTINUATION BOOST - Pullback to VWAP confirmed "
                        f"(quality={structure.continuation_quality:.1f})"
                    )

            # MID_MORNING PHASE (30-120 min): Liquidity sweep detection
            if structure.current_phase == IntradayPhase.MID_MORNING:
                if structure.liquidity_sweep_detected:
                    if structure.sweep_direction == "BULLISH_RECLAIM":
                        confidence_boost *= 1.3  # +30% on institutional absorption
                        self.logger.info(
                            f"✅ {symbol}: LIQUIDITY SWEEP - Bullish reclaim detected "
                            f"(strength={structure.sweep_strength:.1f}) - Institutional buying"
                        )

            # MIDDAY PHASE (120-210 min): Balance/Imbalance filtering
            if structure.current_phase == IntradayPhase.MIDDAY:
                # FILTER: Skip BALANCE (chop zone)
                if structure.midday_structure == "BALANCE":
                    self.logger.info(
                        f"⚪ {symbol}: MIDDAY FILTER - Balance/chop zone detected "
                        f"(range={structure.balance_range_pct:.2f}%) - Catalyst plays fail in tight range"
                    )
                    return False

                # BOOST: IMBALANCE breakout confirmed
                if structure.midday_structure == "IMBALANCE_BULLISH":
                    confidence_boost *= 1.4  # +40% on midday breakout
                    self.logger.info(
                        f"✅ {symbol}: MIDDAY BOOST - Imbalance breakout confirmed "
                        f"(compression={structure.compression_ratio:.3f}) - Late breakout play"
                    )

            # AFTERNOON PHASE (210-330 min): Trap detection
            if structure.current_phase == IntradayPhase.AFTERNOON:
                # FILTER: Skip BULL TRAPS (low volume fake breakouts)
                if structure.trap_detected and structure.trap_type == "BULL_TRAP":
                    self.logger.info(
                        f"⚪ {symbol}: AFTERNOON FILTER - Bull trap detected - "
                        f"Fake breakout without volume, high reversal risk"
                    )
                    return False

            # FINAL_DRIVE PHASE (330-390 min): Closing bias
            if structure.current_phase == IntradayPhase.FINAL_DRIVE:
                # FILTER: Skip FADE_SETUP (parabolic move without volume)
                if structure.final_drive_type == "FADE_SETUP":
                    self.logger.info(
                        f"⚪ {symbol}: FINAL DRIVE FILTER - Fade setup detected "
                        f"(low volume parabolic) - High reversal risk at close"
                    )
                    return False

                # BOOST: CLOSING_RAMP (institutional positioning)
                if structure.final_drive_type == "CLOSING_RAMP":
                    confidence_boost *= 1.15  # +15% on closing ramp
                    self.logger.info(
                        f"✅ {symbol}: FINAL DRIVE BOOST - Closing ramp detected "
                        f"(quality={structure.final_drive_quality:.1f}) - Institutional positioning"
                    )

            # Log current phase
            self.logger.debug(
                f"📊 {symbol}: Intraday Phase={structure.current_phase.value} "
                f"(min={structure.minutes_since_open})"
            )

            # ====
            # CRITICAL VALIDATION 1: Check trading hours - Use centralized validation
            # ====
            is_valid_hours, current_time = self.is_within_entry_hours(symbol)

            if bars and len(bars) > 0:
                last_bar_timestamp = bars[-1].timestamp
                # DEBUG: Log timestamp details
                self.logger.debug(
                    f"🕐 {symbol}: Last bar timestamp: {last_bar_timestamp}, "
                    f"current system time (ET): {current_time:.2f}"
                )

            if not is_valid_hours:
                self.logger.warning(
                    f"❌ {symbol}: REJECTED - Outside centralized trading hours "
                    f"(current ET: {current_time:.2f})"
                )
                return False

            self.logger.info(f"✅ {symbol}: Trading hours validation passed - {current_time:.2f} ET")

            # ====
            # EARLY ANALYSIS: Daily potential (needed for horizon determination)
            # ====
            daily_potential = await self._analyze_daily_potential_for_signal(opportunity)

            # ====
            # CRITICAL VALIDATION 2: VWAP strength check (universal filter)
            # ====
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

            # ====
            # ENTRY MODE 1: CATALYST-DRIVEN BREAKOUT (Primary Mode)
            # ====
            completion, support_level = await self.calculate_pattern_completion(opportunity)

            # Store support level for dynamic stop loss
            opportunity['support_level'] = support_level

            self.logger.info(f"📊 DEBUG {symbol}: Pattern completion = {completion:.1f}% (support: ${support_level:.2f})")

            # CATALYST ENTRY LOGIC:
            # - 0-74%: Pattern not ready, reject
            # - 75-95%: OPTIMAL entry window (catalyst aligning, volume building)
            # - 96-100%: Too late, breakout complete

            if 75.0 <= completion <= 95.0:
                self.logger.info(
                    f"✅ {symbol}: CATALYST MODE ENTRY APPROVED - Pattern {completion:.0f}% complete "
                    f"(entering BEFORE full breakout)"
                )

                # Clean up any pending entries tracking
                if symbol in self.pending_entries:
                    del self.pending_entries[symbol]

                return True

            # 🛡️ PROTECTION: If Stage 2 failed, reject entry even if pattern completion is in range
            # This prevents entering on setups that fail critical quality/strength criteria
            if completion >= 75.0:
                # Check if Stage 2 was actually passed (we need to recalculate to verify)
                min_quality = (self.reversal_quality_score_relaxed
                              if daily_context.get('reversal', {}).get('is_reversal', False)
                              else self.min_quality_score)

                catalyst_strength = opportunity.get('catalyst_strength', 0)
                quality_score = opportunity.get('quality_score', 0)

                stage2_passed = (quality_score >= min_quality and catalyst_strength >= 6) or \
                               daily_context.get('reversal', {}).get('is_reversal', False)

                if not stage2_passed:
                    self.logger.warning(
                        f"🚫 {symbol}: ENTRY BLOCKED - Pattern {completion:.0f}% complete but Stage 2 FAILED "
                        f"(Quality: {quality_score:.1f}<{min_quality} OR Strength: {catalyst_strength}<6)"
                    )
                    return False

            elif completion >= 96.0:
                self.logger.warning(
                    f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, breakout done)"
                )
                # Don't return False yet - check first 30min breakout mode

            # ====
            # ENTRY MODE 2: FIRST 30-MINUTE HIGH BREAKOUT (Alternative Mode)
            # ====
            if bars and len(bars) > 0:
                self.logger.info(f"🔍 DEBUG {symbol}: Checking first 30min breakout mode")

                # Track first 30min high (always track regardless of entry decision)
                self._track_first_half_hour_high(symbol, bars)

                # Check for first 30min breakout
                is_breakout = self._check_first_30min_breakout(symbol, bars, current_price)

                self.logger.info(f"📊 DEBUG {symbol}: First 30min breakout = {is_breakout}")

                if is_breakout:
                    # Validate EMA9 condition
                    ema_valid, ema9_value = self._check_ema_condition(bars)
                    self.logger.info(f"📊 DEBUG {symbol}: EMA9 valid = {ema_valid}, EMA9 = ${ema9_value:.2f}")

                    if not ema_valid:
                        self.logger.info(
                            f"⏳ {symbol}: REJECTED - First 30min breakout detected but EMA9 condition not met"
                        )
                        return False

                    # Validate volume spike
                    volume_valid, volume_ratio = self._check_volume_spike(bars)
                    self.logger.info(f"📊 DEBUG {symbol}: Volume spike valid = {volume_valid}, ratio = {volume_ratio:.1f}x")

                    if not volume_valid:
                        self.logger.info(
                            f"⏳ {symbol}: REJECTED - First 30min breakout detected but volume spike not confirmed"
                        )
                        return False

                    # ALL CONDITIONS MET - ENTER
                    self.logger.info(
                        f"✅ {symbol}: FIRST 30MIN BREAKOUT MODE ENTRY APPROVED! "
                        f"Price ${current_price:.2f} > 30min high ${self.first_half_hour_highs[symbol]:.2f}, "
                        f"EMA9 ${ema9_value:.2f}, Volume {volume_ratio:.1f}x"
                    )

                    # Clean up any pending entries tracking
                    if symbol in self.pending_entries:
                        del self.pending_entries[symbol]

                    return True
            else:
                self.logger.info(f"⚠️ DEBUG {symbol}: No bars available for first 30min breakout check")

            # ====
            # NO ENTRY CONDITIONS MET
            # ====
            if completion < 75.0:
                self.logger.info(
                    f"⚪ {symbol}: DAILY_PLAYS REJECTED - Pattern not ready ({completion:.1f}% < 75%)"
                )
            elif completion > 95.0:
                self.logger.info(
                    f"⚪ {symbol}: DAILY_PLAYS REJECTED - Pattern too complete ({completion:.1f}% > 95%)"
                )
            else:
                self.logger.info(
                    f"⚪ {symbol}: DAILY_PLAYS REJECTED - Unknown reason (completion={completion:.1f}%)"
                )

            return False

        except Exception as e:
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para Daily Plays (catalyst-driven)

        Daily Plays horizons:
        - SWING (3-10 days): Strong catalyst + high confidence + DAILY PERMITE
        - SWING_SHORT (1-3 days): Good catalyst + medium confidence + DAILY PERMITE
        - INTRADAY (same day): Weaker catalyst or daily context prevents swing
        - SCALP: Very weak signal (should be rejected)

        Factors:
        - Catalyst strength (from opportunity metadata)
        - Confidence/quality score
        - Risk/reward ratio
        - Volume surge (catalyst confirmation)
        - Daily technical analysis (RSI, resistance, MACD)
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        daily_potential = signal_data.get('daily_potential', {})

        # Extract daily analysis flags
        can_swing = daily_potential.get('can_swing', False)
        can_swing_short = daily_potential.get('can_swing_short', False)
        daily_reasons = daily_potential.get('reasons', [])

        # SWING: Strong catalyst + high confidence + DAILY TECHNICAL ALLOWS IT
        if confidence > 70 and risk_reward > 3.0 and volume_zscore > 3.0 and can_swing:
            # FDA approvals, M&A, strong breakthrough news + technical space
            self.logger.info(f"✅ SWING horizon approved: Strong catalyst + daily context OK")
            return TradingHorizon.SWING, 72.0  # 3 days expected

        # SWING_SHORT: Good catalyst + medium confidence + DAILY ALLOWS (or downgrade from SWING)
        elif confidence > 60 and risk_reward > 2.5 and volume_zscore > 2.0 and can_swing_short:
            # Earnings, contract wins, analyst upgrades + technical space
            self.logger.info(f"✅ SWING_SHORT horizon approved: Good catalyst + daily context OK")
            return TradingHorizon.SWING_SHORT, 36.0  # 1.5 days expected

        # DOWNGRADE: High confidence BUT daily context prevents swing
        elif confidence > 60 and risk_reward > 2.5 and not can_swing_short:
            self.logger.warning(
                f"⬇️ DOWNGRADE to INTRADAY: High signal quality but daily context prevents swing - "
                f"Reasons: {', '.join(daily_reasons)}"
            )
            return TradingHorizon.INTRADAY, 6.0

        # INTRADAY: Decent catalyst but lower confidence or R:R
        elif confidence > 45 and risk_reward > 1.5:
            # News, general catalysts - close same day
            return TradingHorizon.INTRADAY, 6.0

        # SCALP: Weak signal - should probably be rejected
        else:
            return TradingHorizon.SCALP, 0.5

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios Daily Plays

        Criterios de salida:
        1. Take profit: PnL >= 20% (catalysts pueden ir lejos)
        2. Stop loss: PnL <= -5%
        3. Trailing stop: Si PnL >= 12%, activar trailing a 5%
        4. Time-based: Más de 8 horas en posición
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

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0),
                'opportunity_data': position.get('opportunity_data', {})  # Pass dynamic TP/SL data
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
                        'strategy': 'daily_plays',
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

    async def _check_daily_context(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """
        Analiza gráfico diario para evitar entrar en trampas institucionales

        RED FLAGS (rechazar entrada):
        1. RSI daily > 70 (overbought extremo)
        2. MACD daily en zona de sobrecompra extrema
        3. Precio cerca de resistencia histórica (< 2% de distancia)
        4. 5+ días consecutivos alcistas (posible reversión)
        5. Volumen creciente pero precio decreciente (distribución)

        Args:
            symbol: Símbolo a analizar
            current_price: Precio actual

        Returns:
            Dict con resultado del análisis:
            {
                'is_safe': bool,
                'reason': str,
                'daily_rsi': float,
                'consecutive_up_days': int,
                'distance_to_resistance_pct': float
            }
        """
        try:
            # Obtener barras diarias (últimos 30 días)
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')

            daily_bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 M',  # 1 month (approximately 30 days)
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )

            if not daily_bars or len(daily_bars) < 20:
                # Sin suficiente historia, permitir pero con warning
                self.logger.debug(f"{symbol}: Insufficient daily history ({len(daily_bars) if daily_bars else 0} bars)")
                return {'is_safe': True, 'reason': 'Insufficient daily history'}

            # Extraer datos
            closes = [bar.close for bar in daily_bars]
            highs = [bar.high for bar in daily_bars]
            lows = [bar.low for bar in daily_bars]
            volumes = [bar.volume for bar in daily_bars]

            # ====
            # CHECK 1: RSI Daily - Detectar sobrecompra extrema
            # ====
            rsi_daily = self._calculate_rsi(closes, period=14)
            if rsi_daily > 70:
                return {
                    'is_safe': False,
                    'reason': f'Daily RSI overbought: {rsi_daily:.1f} > 70 (exhaustion risk)',
                    'daily_rsi': rsi_daily
                }

            # ====
            # CHECK 2: MACD Daily - Detectar sobrecompra extrema
            # ====
            macd_line, signal_line, histogram = self._calculate_macd(closes)

            # Verificar si MACD está en zona de sobrecompra extrema
            # Comparar histograma actual con promedio histórico
            avg_histogram = sum(abs(h) for h in histogram[-20:]) / 20
            current_histogram = histogram[-1]

            if current_histogram > avg_histogram * 2.5:
                return {
                    'is_safe': False,
                    'reason': f'Daily MACD extreme overbought (histogram {current_histogram:.3f} >> avg {avg_histogram:.3f})',
                    'daily_macd_histogram': current_histogram
                }

            # ====
            # CHECK 3: Resistencia histórica cercana
            # ====
            resistance_30d = max(highs)
            distance_to_resistance = ((resistance_30d - current_price) / current_price) * 100

            if distance_to_resistance < 2.0:  # Menos de 2% de distancia a máximo
                return {
                    'is_safe': False,
                    'reason': f'Too close to 30-day resistance: ${resistance_30d:.2f} (distance: {distance_to_resistance:.1f}%)',
                    'resistance': resistance_30d,
                    'distance_to_resistance_pct': distance_to_resistance
                }

            # ====
            # CHECK 4: Días consecutivos alcistas (agotamiento)
            # ====
            consecutive_up_days = 0
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] > closes[i-1]:
                    consecutive_up_days += 1
                else:
                    break

            if consecutive_up_days >= 5:  # 5+ días seguidos subiendo
                return {
                    'is_safe': False,
                    'reason': f'Exhaustion risk: {consecutive_up_days} consecutive up days',
                    'consecutive_up_days': consecutive_up_days
                }

            # ====
            # CHECK 5: Distribución institucional
            # ====
            # Últimos 3 días: volumen aumenta pero precio no sube proporcionalmente
            if len(volumes) >= 3 and len(closes) >= 3:
                recent_vol_trend = (volumes[-1] - volumes[-3]) / volumes[-3] if volumes[-3] > 0 else 0
                recent_price_trend = (closes[-1] - closes[-3]) / closes[-3] if closes[-3] > 0 else 0

                # Volumen aumenta mucho (+50%) pero precio sube poco (+10% o menos)
                if recent_vol_trend > 0.5 and recent_price_trend < 0.1:
                    return {
                        'is_safe': False,
                        'reason': f'Distribution pattern: vol +{recent_vol_trend*100:.0f}%, price +{recent_price_trend*100:.0f}%'
                    }

            # ====
            # REVERSAL MODE: Detectar setups de reversión alcista
            # ====
            reversal_data = None
            if self.enable_reversal_mode:
                reversal_data = self._detect_reversal_setup(
                    closes=closes,
                    highs=highs,
                    lows=lows,
                    volumes=volumes,
                    current_price=current_price,
                    rsi_daily=rsi_daily,
                    macd_histogram=histogram
                )

            # ====
            # ✅ TODOS LOS CHECKS PASADOS
            # ====
            result = {
                'is_safe': True,
                'reason': 'Daily context healthy',
                'daily_rsi': rsi_daily,
                'daily_macd_histogram': current_histogram,
                'consecutive_up_days': consecutive_up_days,
                'distance_to_resistance_pct': distance_to_resistance
            }

            # Add reversal data if detected
            if reversal_data:
                result['reversal'] = reversal_data

            return result

        except Exception as e:
            self.logger.error(f"❌ Error checking daily context for {symbol}: {e}")
            # En caso de error de conexión, SER CONSERVADOR y rechazar
            # No podemos verificar trampas institucionales sin datos diarios
            return {'is_safe': False, 'reason': f'Cannot verify daily context - connection error: {str(e)[:100]}'}

    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """
        Calcula el RSI (Relative Strength Index)

        Args:
            prices: Lista de precios de cierre
            period: Período del RSI (default 14)

        Returns:
            Valor del RSI (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral si no hay suficientes datos

        # Calcular cambios de precio
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # Separar ganancias y pérdidas
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Promedio de ganancias y pérdidas
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0  # Todo ganancias = overbought extremo

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: list, fast=12, slow=26, signal=9) -> Tuple[float, float, list]:
        """
        Calcula el MACD (Moving Average Convergence Divergence)

        Args:
            prices: Lista de precios de cierre
            fast: Período EMA rápida (default 12)
            slow: Período EMA lenta (default 26)
            signal: Período señal (default 9)

        Returns:
            Tupla (macd_line, signal_line, histogram)
        """
        if len(prices) < slow:
            return 0.0, 0.0, [0.0]

        # Función auxiliar para calcular EMA
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]  # Primer valor = SMA
            for price in data[period:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values

        # Calcular EMAs
        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)

        # MACD line = EMA_fast - EMA_slow
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]

        # Signal line = EMA del MACD line
        signal_line = ema(macd_line, signal)

        # Histogram = MACD - Signal
        histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]

        return macd_line[-1], signal_line[-1], histogram

    def _detect_reversal_setup(
        self,
        closes: list,
        highs: list,
        lows: list,
        volumes: list,
        current_price: float,
        rsi_daily: float,
        macd_histogram: list
    ) -> Dict[str, Any]:
        """
        Detecta setups de reversión alcista desde niveles de sobreventa

        REVERSAL SIGNALS (6 total):
        1. RSI < 35 (oversold)
        2. Near support level (within 3% of 30-day low)
        3. 3+ consecutive down days
        4. MACD histogram increasing (divergencia positiva)
        5. Volume declining (selling exhaustion)
        6. Price stabilizing (low volatility last 3 days)

        Args:
            closes: Lista de precios de cierre
            highs: Lista de máximos
            lows: Lista de mínimos
            volumes: Lista de volúmenes
            current_price: Precio actual
            rsi_daily: RSI daily pre-calculado
            macd_histogram: Histograma MACD

        Returns:
            Dict con señales de reversión:
            {
                'is_reversal': bool,
                'signal_count': int,
                'signals': list[str],
                'reversal_score': int
            }
        """
        signals = []
        signal_count = 0

        try:
            # SIGNAL 1: RSI oversold
            if rsi_daily < self.reversal_min_rsi:
                signals.append(f"RSI oversold ({rsi_daily:.1f})")
                signal_count += 1

            # SIGNAL 2: Near support (30-day low)
            support_30d = min(lows)
            distance_to_support = ((current_price - support_30d) / support_30d) * 100
            if distance_to_support < self.reversal_max_support_distance:
                signals.append(f"Near support ({distance_to_support:.1f}% away)")
                signal_count += 1

            # SIGNAL 3: Consecutive down days
            consecutive_down_days = 0
            for i in range(len(closes) - 1, 0, -1):
                if closes[i] < closes[i-1]:
                    consecutive_down_days += 1
                else:
                    break

            if consecutive_down_days >= 3:
                signals.append(f"{consecutive_down_days} consecutive down days")
                signal_count += 1

            # SIGNAL 4: MACD histogram increasing (bullish divergence)
            if len(macd_histogram) >= 3:
                recent_hist_trend = macd_histogram[-1] - macd_histogram[-3]
                if recent_hist_trend > 0:  # Histogram increasing
                    signals.append("MACD histogram increasing")
                    signal_count += 1

            # SIGNAL 5: Volume declining (selling exhaustion)
            if len(volumes) >= 5:
                avg_vol_earlier = sum(volumes[-5:-2]) / 3
                avg_vol_recent = sum(volumes[-2:]) / 2
                if avg_vol_recent < avg_vol_earlier * 0.8:  # 20% decline in volume
                    signals.append("Volume declining (exhaustion)")
                    signal_count += 1

            # SIGNAL 6: Price stabilizing (low volatility)
            if len(highs) >= 3 and len(lows) >= 3:
                recent_ranges = [(highs[i] - lows[i]) / lows[i] for i in range(-3, 0)]
                avg_range = sum(recent_ranges) / len(recent_ranges)
                if avg_range < 0.05:  # Less than 5% daily range = stabilizing
                    signals.append("Price stabilizing (low volatility)")
                    signal_count += 1

            # Determine if reversal setup is valid
            is_reversal = signal_count >= self.reversal_min_signals

            return {
                'is_reversal': is_reversal,
                'signal_count': signal_count,
                'signals': signals,
                'reversal_score': signal_count,
                'distance_to_support_pct': distance_to_support
            }

        except Exception as e:
            self.logger.debug(f"Error detecting reversal setup: {e}")
            return {
                'is_reversal': False,
                'signal_count': 0,
                'signals': [],
                'reversal_score': 0
            }

    # ==
    # FIRST 30-MINUTE HIGH BREAKOUT DETECTION
    # Migrated from daily_plays_strategy.py according to legacy system
    # ==

    def _track_first_half_hour_high(self, symbol: str, bars: list) -> None:
        """
        Track the high of the first 30 minutes after market open (9:30-10:00 AM ET)

        Strategy:
        - Calculate highest price during 9:30-10:00 AM
        - Wait for this window to complete
        - Watch for breakout above this high with volume

        Args:
            symbol: Symbol to track
            bars: List of 1-minute bars (should include market open data)
        """
        try:
            if not bars or len(bars) == 0:
                return

            from datetime import datetime, time
            import pytz

            eastern = pytz.timezone('US/Eastern')
            market_open_time = time(9, 30)  # 9:30 AM
            first_half_hour_end_time = time(10, 0)  # 10:00 AM

            # Filter bars during first 30 minutes (9:30-10:00 AM)
            first_half_hour_bars = []

            for bar in bars:
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

                    bar_time_only = bar_time.time()

                    # Check if in first 30-minute window
                    if market_open_time <= bar_time_only < first_half_hour_end_time:
                        first_half_hour_bars.append(bar)

            if not first_half_hour_bars:
                return

            # Calculate highest price in first 30 minutes
            high_price = max(bar.high for bar in first_half_hour_bars)

            # Store or update the high
            if symbol not in self.first_half_hour_highs:
                self.first_half_hour_highs[symbol] = high_price
                self.logger.debug(
                    f"📊 {symbol}: First 30min high tracked = ${high_price:.2f}"
                )
            else:
                old_high = self.first_half_hour_highs[symbol]
                self.first_half_hour_highs[symbol] = max(old_high, high_price)

            # Check if we're past 10:00 AM - mark as tracked
            current_bar = bars[-1]
            current_time = current_bar.timestamp
            if isinstance(current_time, str):
                from dateutil import parser
                current_time = parser.parse(current_time)

            if current_time.tzinfo is None:
                current_time = eastern.localize(current_time)
            else:
                current_time = current_time.astimezone(eastern)

            current_time_only = current_time.time()

            if current_time_only >= first_half_hour_end_time:
                if symbol not in self.first_half_hour_tracked:
                    self.first_half_hour_tracked[symbol] = True
                    self.logger.info(
                        f"✅ {symbol}: First 30min complete - High: ${self.first_half_hour_highs[symbol]:.2f}"
                    )

        except Exception as e:
            self.logger.error(f"❌ Error tracking first half hour high for {symbol}: {e}")

    def _check_first_30min_breakout(self, symbol: str, bars: list, current_price: float) -> bool:
        """
        Check if current price breaks the first 30-minute high

        Breakout criteria:
        - First 30min tracking complete (past 10:00 AM)
        - Current price > first 30min high

        Args:
            symbol: Symbol to check
            bars: List of bars
            current_price: Current price

        Returns:
            True if breakout detected, False otherwise
        """
        try:
            # Must have tracked first 30min high
            if symbol not in self.first_half_hour_highs:
                return False

            # Must be past first 30min window
            if not self.first_half_hour_tracked.get(symbol, False):
                return False

            first_half_hour_high = self.first_half_hour_highs[symbol]

            # Check for breakout
            is_breakout = current_price > first_half_hour_high

            if is_breakout:
                self.logger.info(
                    f"🔥 {symbol}: FIRST 30MIN BREAKOUT! "
                    f"Price ${current_price:.2f} > High ${first_half_hour_high:.2f}"
                )

            return is_breakout

        except Exception as e:
            self.logger.error(f"❌ Error checking first 30min breakout for {symbol}: {e}")
            return False

    def _detect_vwap_recovery(self, bars: list, vwap_price: float, current_price: float, symbol: str) -> Tuple[bool, str]:
        """
        Detecta si el precio hizo un mínimo reciente y luego recuperó por encima de VWAP

        Esta es una estrategia de entrada superior a comprar en máximos porque:
        - Compras después del pullback/dip (mejor precio)
        - Confirmas que VWAP actúa como soporte
        - Evitas comprar en exhaustion
        - Mejor relación riesgo/recompensa

        Casos detectados:
        A. Mínimo arriba de VWAP → rebote → sube → BUY
        B. Mínimo toca VWAP (±0.5%) → rebota → sube → BUY
        C. Mínimo perfora VWAP → recupera → sube por encima → BUY ✅ (señal más fuerte)

        Args:
            bars: Lista de barras (mínimo 5 barras)
            vwap_price: Precio VWAP actual
            current_price: Precio actual
            symbol: Símbolo (para logging)

        Returns:
            Tuple (recovery_detected: bool, details: str, support_level: float)
            support_level is the price to use for dynamic stop loss
        """
        try:
            if len(bars) < 5:
                return False, "Insufficient bars", 0.0

            # Analizar últimas 5-10 barras para detectar patrón
            lookback = min(10, len(bars))
            recent_bars = bars[-lookback:]

            # 1. Encontrar el mínimo reciente (últimas 5-10 barras)
            min_price = min(bar.low for bar in recent_bars)
            min_bar_idx = next(i for i, bar in enumerate(recent_bars) if bar.low == min_price)

            # 2. El mínimo debe estar en las últimas 3-8 barras (no la más reciente, necesitamos ver recuperación)
            if min_bar_idx >= len(recent_bars) - 2:
                # Mínimo demasiado reciente, no hay confirmación de recuperación
                return False, f"Recent low too fresh (bar {min_bar_idx})", 0.0

            # 3. Calcular distancia del mínimo al VWAP
            vwap_distance_pct = ((min_price - vwap_price) / vwap_price) * 100

            # 4. Verificar que el precio ACTUAL está por encima de VWAP (recuperación confirmada)
            if current_price < vwap_price:
                return False, f"Current price ${current_price:.2f} still below VWAP ${vwap_price:.2f}", 0.0

            # 5. Verificar que hubo recuperación desde el mínimo
            recovery_pct = ((current_price - min_price) / min_price) * 100

            if recovery_pct < 0.3:
                # Recuperación insuficiente (menos de 0.3%)
                return False, f"Insufficient recovery: {recovery_pct:.2f}%", 0.0

            # 6. Clasificar tipo de recuperación
            if vwap_distance_pct < -1.0:
                # Caso C: Perforó VWAP y recuperó (señal más fuerte)
                recovery_type = "STRONG RECOVERY"
                details = f"Low ${min_price:.2f} pierced VWAP by {abs(vwap_distance_pct):.1f}%, recovered to ${current_price:.2f} (+{recovery_pct:.1f}%)"
            elif abs(vwap_distance_pct) <= 0.5:
                # Caso B: Tocó VWAP y rebotó
                recovery_type = "VWAP BOUNCE"
                details = f"Low ${min_price:.2f} touched VWAP ${vwap_price:.2f}, bounced to ${current_price:.2f} (+{recovery_pct:.1f}%)"
            else:
                # Caso A: Mínimo arriba de VWAP, rebote sin tocar
                recovery_type = "PULLBACK RECOVERY"
                details = f"Low ${min_price:.2f} above VWAP (${vwap_price:.2f}), recovered to ${current_price:.2f} (+{recovery_pct:.1f}%)"

            self.logger.info(f"🎯 {symbol}: {recovery_type} - {details}")
            return True, details, min_price

        except Exception as e:
            self.logger.error(f"❌ Error detecting VWAP recovery for {symbol}: {e}")
            return False, f"Error: {str(e)}", 0.0

    def _check_ema_condition(self, bars: list) -> Tuple[bool, float]:
        """
        Check if EMA9 is below current price

        EMA9 criterion:
        - Calculate EMA9 from last 9 bars
        - Current price must be >= EMA9 * 0.99 (1% tolerance for slight pullbacks)

        Args:
            bars: List of bars (at least 9 bars required)

        Returns:
            Tuple (meets_condition, ema9_value)
        """
        try:
            if len(bars) < self.ema_period:
                return False, 0.0

            # Extract close prices for EMA calculation
            closes = [bar.close for bar in bars[-self.ema_period:]]

            # Calculate EMA9 using exponential weighted average
            import pandas as pd
            price_series = pd.Series(closes)
            ema9 = price_series.ewm(span=self.ema_period, adjust=False).mean().iloc[-1]

            current_price = bars[-1].close
            # Allow 1% tolerance below EMA9 (price >= ema9 * 0.99)
            ema9_threshold = ema9 * 0.99
            meets_condition = current_price >= ema9_threshold

            if meets_condition:
                self.logger.debug(
                    f"✅ EMA9 condition met - Price ${current_price:.2f} >= EMA9 ${ema9:.2f} * 0.99 (${ema9_threshold:.2f})"
                )
            else:
                self.logger.debug(
                    f"❌ EMA9 condition NOT met - Price ${current_price:.2f} < EMA9 ${ema9:.2f} * 0.99 (${ema9_threshold:.2f})"
                )

            return meets_condition, float(ema9)

        except Exception as e:
            self.logger.error(f"❌ Error checking EMA condition: {e}")
            return False, 0.0

    def _check_volume_spike(self, bars: list, lookback: int = 8) -> Tuple[bool, float]:
        """
        Check if current volume is at least 1.5x the average of last N bars

        Volume spike criterion:
        - Current bar volume >= 1.5x average of previous N bars
        - Confirms breakout with volume expansion

        Args:
            bars: List of bars (at least lookback+1 bars required)
            lookback: Number of bars to calculate average (default 8)

        Returns:
            Tuple (meets_condition, volume_ratio)
        """
        try:
            if len(bars) < lookback + 1:
                return False, 0.0

            # Get current bar volume
            current_volume = bars[-1].volume

            # Calculate average volume of previous N bars (exclude current)
            previous_volumes = [bar.volume for bar in bars[-(lookback+1):-1]]
            avg_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else 0

            if avg_volume == 0:
                return False, 0.0

            # Calculate volume ratio
            volume_ratio = current_volume / avg_volume

            # Check if meets 1.5x criterion
            meets_condition = volume_ratio >= self.volume_multiplier_30min

            if meets_condition:
                self.logger.debug(
                    f"✅ Volume spike confirmed - "
                    f"{current_volume:,.0f} vs avg {avg_volume:,.0f} ({volume_ratio:.1f}x)"
                )
            else:
                self.logger.debug(
                    f"❌ Volume spike NOT confirmed - "
                    f"{current_volume:,.0f} vs avg {avg_volume:,.0f} ({volume_ratio:.1f}x, need {self.volume_multiplier_30min}x)"
                )

            return meets_condition, volume_ratio

        except Exception as e:
            self.logger.error(f"❌ Error checking volume spike: {e}")
            return False, 0.0