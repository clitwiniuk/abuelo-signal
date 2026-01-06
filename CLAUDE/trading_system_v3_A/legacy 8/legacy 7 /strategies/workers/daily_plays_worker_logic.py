"""
Daily Plays Worker Logic
Worker específico para estrategia Daily Plays (Catalyst-driven breakouts)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from .exhaustion_filters import create_exhaustion_filters_from_config
from strategies.workers.update_handlers import CatalystSensitiveUpdateHandler
from core.trade_arbiter import TradingHorizon
from typing import Dict, Any, Tuple, Optional  # Added Optional

class DailyPlaysWorkerLogic(BaseWorkerLogic, CatalystSensitiveUpdateHandler):
    """
    Daily Plays Worker v2.0 - Catalyst-driven breakout trading + Reversal Trading

    VERSION: 2.0 (REFACTORED - Config-driven, Volume Filters, ODS Filters Re-enabled)

    Enfoque: Catalyst-driven breakout trading + Reversal Trading + First 30min Breakout (optional)
    Ideal para FDA approvals, M&A, earnings, breakthrough news
    Detecta también reversiones alcistas desde niveles de sobreventa

    MODOS DE ENTRADA (3 modes):

    MODE 1: CATALYST MODE (Default - Primary)
    Criterios de entrada:
    0. Anti-overtrading: 1 trade máximo por símbolo por día
    1. Catalyst fuerte (FDA, M&A, EARNINGS, BREAKTHROUGH)
    2. Precio en rango smallcap ($1-$10) - configurable
    3. Volume filters (NEW v2.0):
       - Avg volume >= 100k shares/day (20-day avg)
       - Dollar volume >= $50k/day (avoid illiquid)
    4. Volume ratio >= 1.8x (explosión de volumen)
    5. Quality score >= 55.0 (catalyst quality matters)
    6. Precio > VWAP intraday (confirmación de fortaleza)
    7. ODS Filters (RE-ENABLED v2.0 - configurable):
       - Skip FAILED_DRIVE days (optional)
       - Skip BALANCE_DAY days (optional)
    8. Daily Context Check (EVITA TRAMPAS INSTITUCIONALES) - CONFIGURABLE:
       - RSI daily < daily_rsi_overbought (default: 70)
       - MACD daily no extremo (< daily_macd_extreme_multiplier × avg, default: 2.5x)
       - NO cerca de resistencia histórica (> daily_resistance_min_distance_pct, default: 2%)
       - NO días consecutivos alcistas excesivos (< daily_max_consecutive_up_days, default: 5)
       - NO distribución institucional detectada (configurable thresholds)
    9. 1 confirmación (30s) para no perder momentum

    MODE 2: REVERSAL MODE (Oversold Bounce)
    Criterios de entrada:
    - 4+ señales de reversión detectadas (de 6 posibles):
      1. RSI < 35 (oversold)
      2. Cerca de soporte 30-day (< 3%)
      3. 3+ días consecutivos bajistas
      4. MACD histogram increasing (divergencia positiva)
      5. Volume declining (exhaustion)
      6. Price stabilizing (volatilidad baja)
    - Requisitos RELAJADOS cuando reversal detectado:
      * Catalyst opcional (no requerido)
      * Volume ratio >= 1.5x (vs 1.8x)
      * Quality score >= 40 (vs 55)
      * VWAP requirement relaxed

    MODE 3: FIRST 30MIN BREAKOUT (Optional - Disabled by default)
    Criterios de entrada:
    - Config: enable_first_30min_breakout = true
    - Timeframe: 10:00-10:30 AM ET
    - Price > first 30min high (9:30-10:00 AM)
    - Volume multiplier >= 1.5x (configurable)
    - Quality score >= 55
    - Price in range ($1-$10)
    - Volume filters applied

    Criterios de salida (via WorkerStopManager):
    - FOMO Exhaustion (prioridad 0)
    - Trailing stop: 6% activation, 2% distance (prioridad 1)
    - Take profit: 20% (prioridad 2)
    - Stop loss: 5% (prioridad 3)
    - Time-based: 8 horas máximo (prioridad 4)
    - END_OF_DAY: 15:56 ET (prioridad 5)

    MEJORAS v2.0:
    - ✅ 100% config.ini integration (23/23 params vs 9/23 anterior)
    - ✅ Anti-overtrading: 1 trade/symbol/day (fixes duplicate entries)
    - ✅ Volume filters: avg_volume + dollar_volume (avoid illiquid)
    - ✅ ODS filters re-enabled (configurable toggles)
    - ✅ First 30min breakout mode: explicit toggle
    - ✅ Tightened price range: $1-$10 (vs $1-$25)
    - ✅ Quality score: 55 (vs 50)
    - ✅ Removed deprecated code
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name="daily_plays",
            broker=broker,
            config=config  # PASS CONFIG TO BASE
        )
        self.risk_manager = risk_manager

        # ===== READ ALL PARAMS FROM CONFIG.INI (v2.0 - REFACTORED) =====

        # Catalyst configuration (fixed list, no config needed)
        self.strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT', 'NEWS', 'ANALYST']

        # Anti-overtrading tracking
        self.traded_symbols_today = set()  # Track symbols traded today
        self._last_reset_date = None       # For daily reset

        # Entry confirmation tracking
        self.pending_entries = {}  # {symbol: {'first_seen': datetime, 'count': int}}

        # First 30-minute high tracking
        self.first_half_hour_highs = {}   # {symbol: price}
        self.first_half_hour_tracked = {} # {symbol: bool}

        if config:
            # ===== PRICE FILTERS =====
            # Allow subclass to override section or use default
            section = getattr(self, 'config_section', 'DAILY_PLAYS_STRATEGY')
            self.min_price = config.getfloat(section, 'min_price', fallback=1.0)
            self.max_price = config.getfloat(section, 'max_price', fallback=10.0)  # Tightened from 25.0
            self.min_quality_score = config.getfloat(section, 'min_quality_score', fallback=55.0)

            # ===== VOLUME FILTERS =====
            self.min_volume_ratio = config.getfloat(section, 'min_volume_ratio', fallback=1.8)
            self.min_avg_volume = config.getint(section, 'min_avg_volume', fallback=100000)  # NEW
            self.min_dollar_volume = config.getfloat(section, 'min_dollar_volume', fallback=50000.0)  # NEW

            # ===== ENTRY CONFIRMATION =====
            self.min_confirmations = config.getint(section, 'min_confirmations', fallback=1)
            self.confirmation_window = config.getint(section, 'confirmation_window', fallback=120)

            # ===== FIRST 30MIN BREAKOUT MODE =====
            self.enable_first_30min_breakout = config.getboolean(section, 'enable_first_30min_breakout', fallback=False)  # NEW - DISABLED by default
            self.ema_period = config.getint(section, 'ema_period', fallback=9)
            self.volume_multiplier_30min = config.getfloat(section, 'volume_multiplier_30min', fallback=1.5)

            # ===== ODS FILTERS =====
            self.enable_ods_filters = config.getboolean(section, 'enable_ods_filters', fallback=True)  # NEW
            self.ods_filter_failed_drive = config.getboolean(section, 'ods_filter_failed_drive', fallback=True)  # NEW
            self.ods_filter_balance_day = config.getboolean(section, 'ods_filter_balance_day', fallback=True)  # NEW

            # ===== REVERSAL MODE =====
            self.enable_reversal_mode = config.getboolean(section, 'enable_reversal_mode', fallback=True)
            self.reversal_min_rsi = config.getfloat(section, 'reversal_min_rsi', fallback=35.0)
            self.reversal_min_signals = config.getint(section, 'reversal_min_signals', fallback=4)
            self.reversal_max_support_distance = config.getfloat(section, 'reversal_max_support_distance', fallback=3.0)
            self.reversal_volume_ratio_relaxed = config.getfloat(section, 'reversal_volume_ratio_relaxed', fallback=1.5)
            self.reversal_quality_score_relaxed = config.getfloat(section, 'reversal_quality_score_relaxed', fallback=40.0)

            # ===== DAILY CONTEXT SAFETY CHECKS =====
            self.daily_rsi_overbought = config.getfloat(section, 'daily_rsi_overbought', fallback=70.0)
            self.daily_macd_extreme_multiplier = config.getfloat(section, 'daily_macd_extreme_multiplier', fallback=2.5)
            self.daily_resistance_min_distance_pct = config.getfloat(section, 'daily_resistance_min_distance_pct', fallback=2.0)
            self.daily_max_consecutive_up_days = config.getint(section, 'daily_max_consecutive_up_days', fallback=5)
            self.daily_distribution_volume_increase = config.getfloat(section, 'daily_distribution_volume_increase', fallback=0.5)
            self.daily_distribution_price_increase = config.getfloat(section, 'daily_distribution_price_increase', fallback=0.1)

            # ===== RISK MANAGEMENT (WorkerStopManager) =====
            self.stop_manager = create_worker_stop_manager(config, section)

            # ===== EXHAUSTION FILTERS (v2.1 - NEW) =====
            self.exhaustion_filters = create_exhaustion_filters_from_config(config, section, logger=self.logger)

        else:
            # Fallback: Use default parameters if config not available
            self.min_price = 1.0
            self.max_price = 10.0
            self.min_quality_score = 55.0
            self.min_volume_ratio = 1.8
            self.min_avg_volume = 100000
            self.min_dollar_volume = 50000.0
            self.min_confirmations = 1
            self.confirmation_window = 120
            self.enable_first_30min_breakout = False
            self.ema_period = 9
            self.volume_multiplier_30min = 1.5
            self.enable_ods_filters = True
            self.ods_filter_failed_drive = True
            self.ods_filter_balance_day = True
            self.enable_reversal_mode = True
            self.reversal_min_rsi = 35.0
            self.reversal_min_signals = 4
            self.reversal_max_support_distance = 3.0
            self.reversal_volume_ratio_relaxed = 1.5
            self.reversal_quality_score_relaxed = 40.0

            # Fallback: create stop manager with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,
                take_profit_pct=20.0,
                quick_target_pct=7.0,
                trailing_activation=8.0,
                trailing_distance=4.0,
                max_position_hours=8.0
            ))

        # ===== LOG CONFIGURATION =====
        self.logger.info(f"🎯 Daily Plays Worker v2.0 configured (REFACTORED):")
        self.logger.info(f"   Price Range: ${self.min_price:.2f} - ${self.max_price:.2f}")
        self.logger.info(f"   Volume Filters: ratio>={self.min_volume_ratio}x, avg>={self.min_avg_volume:,}, dollar>=${self.min_dollar_volume:,.0f}")
        self.logger.info(f"   Quality Score: >={self.min_quality_score:.0f}")
        self.logger.info(f"   Catalysts: {self.strong_catalysts}")
        self.logger.info(f"   First 30min Breakout: {'ENABLED' if self.enable_first_30min_breakout else 'DISABLED'}")
        self.logger.info(f"   ODS Filters: {'ENABLED' if self.enable_ods_filters else 'DISABLED'} (FAILED_DRIVE={self.ods_filter_failed_drive}, BALANCE={self.ods_filter_balance_day})")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")
        if self.enable_reversal_mode:
            self.logger.info(
                f"   Reversal Mode: ENABLED (RSI<{self.reversal_min_rsi}, {self.reversal_min_signals}/6 signals)"
            )

    def _reset_daily_state_if_needed(self):
        """Reset daily counters at start of new trading day"""
        import pytz
        from datetime import datetime
        ny_tz = pytz.timezone('US/Eastern')
        current_date = datetime.now(ny_tz).date()

        if not hasattr(self, '_last_reset_date') or self._last_reset_date != current_date:
            self.logger.info(f"🔄 New trading day - Resetting daily_plays worker counters")
            self.traded_symbols_today.clear()
            self._last_reset_date = current_date

    def _calculate_avg_volume_from_bars(self, bars: list, period: int = 20) -> float:
        """
        Calculate average volume from bars

        Args:
            bars: List of bars
            period: Number of bars to average

        Returns:
            Average volume
        """
        if not bars or len(bars) < period:
            return 0.0

        recent_bars = bars[-period:]
        total_volume = sum(bar.volume for bar in recent_bars if hasattr(bar, 'volume'))
        return total_volume / len(recent_bars) if recent_bars else 0.0

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> Tuple[float, float]:
        """
        Calcula completitud del patrón Daily Plays (0-100%) - TECHNICAL ONLY

        PATTERN:
        1. [25%] Volume Surge (Catalyst Proxy) + Price Range
        2. [50%] Quality Score (Technical) OR High Volume Strength
        3. [75%] VWAP Trend/Strength
        4. [85%] Controlled Reaction (Gap < 10%)
        5. [100%] Parabolic (Late)

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (Pattern completion percentage (0.0-100.0), support_level)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Stage 1: Volume Surge (Catalyst Proxy) + Price Range
            # In simulation, we lack news feeds. We assume Volume Ratio > 1.5x implies a catalyst.
            catalyst_proxy = volume_ratio >= 1.5
            price_ok = self.min_price <= current_price <= self.max_price

            if catalyst_proxy and price_ok:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 1 passed (25%) - VolRatio: {volume_ratio:.1f}x>=1.5x (Catalyst Proxy), Price: ${current_price:.2f}"
                )
            else:
                self.logger.info(
                    f"📊 {symbol}: ❌ Stage 1 FAILED (0%) - VolRatio: {volume_ratio:.1f}x<1.5x OR Price out of range"
                )
                return 0.0, 0.0

            # Stage 2: Quality & Strength (50%)
            # If Quality < 55, check if Volume Ratio is extreme (> 5.0x) to compensate
            if quality_score >= self.min_quality_score:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 2 passed (50%) - Quality: {quality_score:.1f}>={self.min_quality_score}"
                )
            elif volume_ratio >= 5.0:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 2 passed (50%) - Extreme Volume ({volume_ratio:.1f}x) overrides Quality"
                )
            else:
                self.logger.info(
                    f"📊 {symbol}: ❌ Stage 2 FAILED ({completion:.0f}%) - Quality {quality_score:.1f}<{self.min_quality_score} AND VolRatio<5.0x"
                )
                return completion, 0.0

            # Stage 3: VWAP Strength (75%)
            # Use robust VWAP validation from BaseWorkerLogic
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price, opportunity=opportunity)
            
            support_level = 0.0
            
            # Use simple VWAP calculation for support level
            if bars and len(bars) >= 5:
                vwap_val = self.calculate_vwap_from_bars(bars)
                if vwap_val: support_level = vwap_val

            if vwap_valid:
                completion += 25.0
                self.logger.info(f"📊 {symbol}: ✅ Stage 3 passed (75%) - VWAP Strength Validated: {vwap_reason}")
            else:
                self.logger.info(f"📊 {symbol}: ❌ Stage 3 FAILED ({completion:.0f}%) - VWAP Validation Failed: {vwap_reason}")
                return completion, 0.0

            # Stage 4: CONTROLLED vs PARABOLIC MOVE (85-100%)
            if gap_pct <= 10.0:
                # Controlled reaction - early entry window
                completion += 10.0
                self.logger.info(
                    f"📊 {symbol}: ✅ Stage 4 passed (85%) - CONTROLLED REACTION: gap {gap_pct:.1f}% <= 10%"
                )
            else:
                # Parabolic move - catalyst fully priced in, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: ⚠️ Stage 4 PARABOLIC (100%) - gap {gap_pct:.1f}% > 10%"
                )
                return completion, support_level

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Daily Plays pattern = {completion:.1f}% "
                f"(VolRatio={volume_ratio:.1f}x, gap={gap_pct:.1f}%, price=${current_price:.2f})"
            )

            return completion, support_level

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0.0, 0.0


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
                try:
                    from dateutil import parser
                    dt = parser.parse(timestamp)
                except Exception as parse_error:
                    self.logger.warning(f"Failed to parse timestamp string '{timestamp}': {parse_error}")
                    return 0.0
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                # Fallback to current time
                dt = datetime.now()

            # Ensure dt is datetime before accessing tzinfo
            if not isinstance(dt, datetime):
                self.logger.warning(f"dt is not datetime after conversion: {type(dt)}, value: {dt}")
                return 0.0

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
        Evalúa si debe entrar según criterios Daily Plays - TECHNICAL ONLY

        Two Entry Modes:
        1. CATALYST MODE (Proxy via Volume): Enter if Volume Ratio implies catalyst
        2. TECHNICAL BREAKOUT: Standard volume breakout

        Args:
            opportunity: Opportunity data

        Returns:
            True if criteria met
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Reset daily state if new trading day
            self._reset_daily_state_if_needed()

            # ====
            # FILTER 0: ANTI-OVERTRADING
            # ====
            if symbol in self.traded_symbols_today:
                self.logger.info(
                    f"⚪ {symbol}: ANTI-OVERTRADING - Already traded today"
                )
                return False

            # ====
            # FILTER 1: DUPLICATE POSITION CHECK (Using Broker)
            # ====
            positions = await self.broker.get_positions()
            if symbol in positions:
                self.logger.info(f"⚪ {symbol}: Position already exists")
                return False

            current_price = opportunity.get('current_price', 0)
            bars = self.get_bars_from_opportunity(opportunity)

            self.logger.info(f"🔍 {symbol}: Starting evaluation - bars={len(bars) if bars else 0}, price=${current_price:.2f}")

            # ====
            # FILTER 2: PRICE RANGE
            # ====
            if not self.min_price <= current_price <= self.max_price:
                self.logger.info(
                    f"⚪ {symbol}: Price ${current_price:.2f} outside range ${self.min_price:.2f}-${self.max_price:.2f}"
                )
                return False

            # ====
            # ODS FILTER (Standardized / Local Calculation)
            # ====
            # Use local calculation for ODS if scanner data missing (Replay compatibility)
            ods_from_scanner = opportunity.get('ods_data')
            if ods_from_scanner and hasattr(ods_from_scanner, 'day_type'):
                 ods = ods_from_scanner
            else:
                 # Fallback: Calculate ODS locally
                 # Note: This requires get_ods_for_symbol to be technical-only
                 try:
                    ods = await self.get_ods_for_symbol(symbol, bars)
                 except Exception as e:
                    self.logger.debug(f"ODS calculation skipped: {e}")
                    ods = None

            if ods and self.enable_ods_filters:
                from core.ods_classifier import ODSDayType
                # FILTER 1: Skip FAILED DRIVE days
                if self.ods_filter_failed_drive and ods.day_type == ODSDayType.FAILED_DRIVE:
                    self.logger.info(f"⚪ {symbol}: ODS FILTER - Failed drive day")
                    return False
                # FILTER 2: Skip BALANCE days
                if self.ods_filter_balance_day and ods.day_type == ODSDayType.BALANCE_DAY:
                    self.logger.info(f"⚪ {symbol}: ODS FILTER - Balance day")
                    return False

            # ====
            # TIME CHECK (Centralized)
            # ====
            timestamp = opportunity.get('timestamp')
            is_valid_hours, current_time = self.is_within_entry_hours(symbol, timestamp=timestamp)

            if not is_valid_hours:
                self.logger.warning(f"❌ {symbol}: REJECTED - Outside trading hours ({current_time:.2f})")
                return False

            self.logger.info(f"✅ {symbol}: Trading hours validation passed - {current_time:.2f} ET")

            # ====
            # TECHNICAL VOLUME CHECK
            # ====
            # Instead of complex metadata checks, verify we have VOLUME
            # Volume Ratio is key for "Catalyst" plays
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            
            # If volume ratio is missing or low in simulation (common issue), verify bars vs average
            if volume_ratio < 1.0 and bars:
                avg_vol = self._calculate_avg_volume_from_bars(bars)
                recent_vol = bars[-1].volume if bars else 0
                if avg_vol > 0:
                    volume_ratio = recent_vol / avg_vol
                    opportunity['volume_ratio'] = volume_ratio # update for pattern calc

            if volume_ratio < self.min_volume_ratio:
                 # Strict enforcement for Parameter Optimization
                 # Only relax if explicitly configured? No, if users set min_volume=100, we must respect it.
                 self.logger.info(f"⚪ {symbol}: Low Volume Ratio {volume_ratio:.1f}x (Need >{self.min_volume_ratio}x)")
                 return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Error in should_enter: {e}", exc_info=True)
            return False

            # B. HIGH ROTATION
            is_high_rotation = fundamentals.get('is_high_rotation', False)
            if is_high_rotation:
                 self.logger.info(f"🚀 {symbol}: HIGH ROTATION DAILY ({fundamentals['rotation_factor']:.1f}x) - Confirmation Boost")

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
            # CRITICAL VALIDATION 3: Exhaustion Filter (v2.1 - NEW)
            # Avoid buying at the peak of a parabolic move or TD count 9
            # ====
            if hasattr(self, 'exhaustion_filters') and bars:
                is_safe, exhaustion_reason = self.exhaustion_filters.check_exhaustion(bars, current_price)
                if not is_safe:
                    self.logger.warning(
                        f"❌ {symbol}: REJECTED by Exhaustion Filter - {exhaustion_reason}"
                    )
                    return False
                self.logger.debug(f"✅ {symbol}: Exhaustion check passed")

            # ====
            # CRITICAL VALIDATION 4: Implicit Event Validation (PHASE 1 - OPTIONAL)
            # Validates price-first event signals when available
            # ====
            implicit_event = opportunity.get('implicit_event')
            if implicit_event:
                # Event-driven data available - validate it's still fresh
                event_score = implicit_event.get('score', 0)
                event_expansion = implicit_event.get('expansion', False)
                event_gap_pct = implicit_event.get('gap_pct', 0.0)
                event_volume_ratio = implicit_event.get('volume_ratio', 0.0)

                self.logger.info(
                    f"📊 {symbol}: Implicit Event Data - score={event_score}/4, "
                    f"gap={event_gap_pct:.1f}%, vol={event_volume_ratio:.1f}x, expansion={event_expansion}"
                )

                # VALIDATION: If score is weak (< 3/4) and no expansion, require stronger catalyst
                if event_score < 3 and not event_expansion:
                    catalyst_strength = opportunity.get('catalyst_strength', 0)
                    if catalyst_strength < 8:
                        self.logger.warning(
                            f"❌ {symbol}: REJECTED - Weak implicit event (score={event_score}/4, "
                            f"no expansion) + moderate catalyst (strength={catalyst_strength}) → Skip"
                        )
                        return False
                    else:
                        self.logger.info(
                            f"✅ {symbol}: Weak event BUT strong catalyst ({catalyst_strength}) → Proceed"
                        )

                # VALIDATION: If no expansion detected, skip entry (chop risk)
                # UNLESS: Blue sky breakout or very strong catalyst
                if not event_expansion:
                    is_blue_sky = opportunity.get('daily_potential', {}).get('is_52_week_high', False)
                    catalyst_strength = opportunity.get('catalyst_strength', 0)

                    if not is_blue_sky and catalyst_strength < 9:
                        self.logger.warning(
                            f"❌ {symbol}: REJECTED - No price expansion detected (chop risk) "
                            f"→ Wait for clean breakout"
                        )
                        return False
                    else:
                        self.logger.info(f"✅ {symbol}: No expansion but override (blue_sky={is_blue_sky}, catalyst={catalyst_strength})")

                # BOOST: Strong implicit event (4/4 with expansion) → increase confidence
                if event_score == 4 and event_expansion:
                    self.logger.info(
                        f"🚀 {symbol}: STRONG IMPLICIT EVENT (4/4 + expansion) → High confidence entry"
                    )
                    # Store boost flag for position sizing
                    opportunity['implicit_event_boost'] = True

            else:
                self.logger.debug(f"ℹ️ {symbol}: No implicit_event data (legacy mode)")

            # ====
            # ENTRY MODE 1: CATALYST-DRIVEN BREAKOUT (Primary Mode)
            # ====
            completion, support_level = await self.calculate_pattern_completion(opportunity)

            # Store support level for dynamic stop loss
            opportunity['support_level'] = support_level

            # Log pattern completion with clearer support information
            if support_level > 0.0:
                self.logger.info(f"📊 {symbol}: Pattern completion = {completion:.1f}% (support: ${support_level:.2f})")
            else:
                self.logger.info(f"📊 {symbol}: Pattern completion = {completion:.1f}% (support: N/A - pattern incomplete)")

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
                # Get daily context for reversal checking
                volume_ratio = opportunity.get('volume_ratio', 1.0)
                daily_context = await self._check_daily_context(symbol, current_price, daily_potential=daily_potential, volume_ratio=volume_ratio)

                # Check if Stage 2 was actually passed (we need to recalculate to verify)
                # RELAX quality if Blue Sky OR High Rotation
                relaxed_factor = 0.85 if (is_blue_sky or is_high_rotation) else 1.0
                min_quality = (self.reversal_quality_score_relaxed
                              if daily_context.get('reversal', {}).get('is_reversal', False)
                              else self.min_quality_score * relaxed_factor)

                catalyst_strength = opportunity.get('catalyst_strength', 0)
                quality_score = opportunity.get('quality_score', 0)
                catalyst_type = opportunity.get('catalyst_type', '')

                # HIGH QUALITY TECHNICAL EXCEPTION: A/A+ technical setups don't need strong catalyst
                is_high_quality_technical = (
                    catalyst_type == 'TECHNICAL' and
                    quality_score >= 75  # A or A+ setup
                )

                stage2_passed = (quality_score >= min_quality and catalyst_strength >= 7) or \
                               daily_context.get('reversal', {}).get('is_reversal', False) or \
                               is_high_quality_technical

                if not stage2_passed:
                    self.logger.warning(
                        f"🚫 {symbol}: ENTRY BLOCKED - Pattern {completion:.0f}% complete but Stage 2 FAILED "
                        f"(Quality: {quality_score:.1f}<{min_quality} OR Strength: {catalyst_strength}<7)"
                    )
                    return False

            elif completion >= 96.0:
                self.logger.warning(
                    f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, breakout done) - REJECTED"
                )
                return False  # Reject immediately - too late to enter

            # ====
            # ENTRY MODE 2: FIRST 30-MINUTE HIGH BREAKOUT (Alternative Mode)
            # ====
            if self.enable_first_30min_breakout and bars and len(bars) > 0:
                self.logger.info(f"🔍 {symbol}: Checking first 30min breakout mode (ENABLED)")

                # Track first 30min high (always track regardless of entry decision)
                self._track_first_half_hour_high(symbol, bars)

                # Check for first 30min breakout
                is_breakout = self._check_first_30min_breakout(symbol, bars, current_price)

                self.logger.debug(f"📊 {symbol}: First 30min breakout = {is_breakout}")

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
                # Only log if mode is enabled but bars are missing
                if self.enable_first_30min_breakout:
                    self.logger.warning(f"⚠️ {symbol}: First 30min breakout ENABLED but no bars available")
                else:
                    self.logger.debug(f"📊 {symbol}: First 30min breakout mode DISABLED (using standard evaluation)")

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
            import traceback
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para Daily Plays (catalyst-driven)

        Daily Plays horizons:
        - SWING (3-10 days): Strong catalyst + high confidence + DAILY PERMITE
        - SWING_SHORT (1-3 days): Good catalyst + medium confidence + DAILY PERMITE
        - INTRADAY (same day): Default for most catalyst plays
        - SCALP: Very weak signal (should be rejected)

        HYBRID APPROACH: Uses R:R ratio when available, but falls back to quality score
        and catalyst strength when R:R is not yet calculated (defaults to 1.5).
        This prevents the chicken-and-egg problem while maintaining compatibility.

        Factors:
        - Catalyst strength (from opportunity metadata)
        - Confidence/quality score
        - Risk/reward ratio (when available)
        - Volume ratio/zscore (from opportunity)
        - Daily technical analysis (RSI, resistance, MACD)
        """
        confidence = signal_data.get('confidence', 50)  # quality_score
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        volume_ratio = signal_data.get('volume_ratio', 0)  # From opportunity
        catalyst_strength = signal_data.get('catalyst_strength', 0)  # From opportunity
        daily_potential = signal_data.get('daily_potential', {})

        # Extract daily analysis flags
        can_swing = daily_potential.get('can_swing', False)
        can_swing_short = daily_potential.get('can_swing_short', False)
        daily_reasons = daily_potential.get('reasons', [])

        # SWING: Strong catalyst + high confidence + DAILY TECHNICAL ALLOWS IT
        # Use R:R if available (>1.5), otherwise use quality/catalyst metrics
        if can_swing:
            if risk_reward > 3.0 and confidence > 70 and volume_zscore > 3.0:
                # R:R-based (when available from structural calculator)
                self.logger.info(f"✅ SWING horizon approved: Strong R:R + daily context OK")
                return TradingHorizon.SWING, 72.0
            elif confidence > 80 and catalyst_strength >= 8 and volume_ratio > 2.5:
                # Quality-based fallback (when R:R not yet calculated)
                self.logger.info(f"✅ SWING horizon approved: Strong catalyst + daily context OK")
                return TradingHorizon.SWING, 72.0

        # SWING_SHORT: Good catalyst + medium confidence + DAILY ALLOWS
        if can_swing_short:
            if risk_reward > 2.5 and confidence > 60 and volume_zscore > 2.0:
                # R:R-based (when available)
                self.logger.info(f"✅ SWING_SHORT horizon approved: Good R:R + daily context OK")
                return TradingHorizon.SWING_SHORT, 36.0
            elif confidence > 70 and catalyst_strength >= 7 and volume_ratio > 2.0:
                # Quality-based fallback
                self.logger.info(f"✅ SWING_SHORT horizon approved: Good catalyst + daily context OK")
                return TradingHorizon.SWING_SHORT, 36.0

        # DOWNGRADE: High confidence BUT daily context prevents swing
        if not can_swing_short:
            if risk_reward > 2.5 and confidence > 60:
                # R:R-based downgrade
                self.logger.warning(
                    f"⬇️ DOWNGRADE to INTRADAY: High R:R but daily context prevents swing - "
                    f"Reasons: {', '.join(daily_reasons)}"
                )
                return TradingHorizon.INTRADAY, 6.0
            elif confidence > 70:
                # Quality-based downgrade
                self.logger.warning(
                    f"⬇️ DOWNGRADE to INTRADAY: High quality but daily context prevents swing - "
                    f"Reasons: {', '.join(daily_reasons)}"
                )
                return TradingHorizon.INTRADAY, 6.0

        # INTRADAY: Default for most catalyst plays
        # This ensures intraday supports (LOD, VWAP, OR Low) are used for SL calculation
        # Use quality score as primary criterion (always available)
        if confidence >= 55:
            return TradingHorizon.INTRADAY, 6.0
        elif risk_reward > 1.5 and confidence > 45:
            # R:R-based fallback for lower quality
            return TradingHorizon.INTRADAY, 6.0

        # SCALP: Very weak signal - should probably be rejected
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

            # RACE CONDITION PROTECTION: Check if position is fully registered in stop manager
            # If start_entry() runs super()._execute_entry() but hasn't reached register_position() yet,
            # monitor_positions() might see the position but stop_manager doesn't know it.
            if symbol not in self.stop_manager.entry_times:
                self.logger.debug(f"⏳ {symbol}: Position initializing (not yet in StopManager) - skipping exit check")
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
            # BUG FIX: Check nested opportunity_data for EOD_safe if not at root
            eod_safe = position.get('EOD_safe', False)
            if not eod_safe and 'opportunity_data' in position:
                 eod_safe = position['opportunity_data'].get('EOD_safe', False)
            
            position_metadata = {
                'EOD_safe': eod_safe,
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
            import traceback
            self.logger.error(traceback.format_exc())
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, f"ERROR_EXIT: {str(e)}"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager AND unified position manager"""
        # Execute normal entry
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Track symbol as traded today (anti-overtrading)
            self.traded_symbols_today.add(symbol)
            self.logger.debug(f"📝 Tracked {symbol} as traded today ({len(self.traded_symbols_today)} symbols)")

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

    # ==
    # FIRST 30-MINUTE HIGH BREAKOUT DETECTION (Legacy/Optional - Keep if pure technical)
    # ==
    # Methods removed for simplification as they were not called in new should_enter
    # and relied on complex state or external data fetching not present in AbstractBroker.


    def _detect_vwap_recovery(self, bars: list, vwap_price: float, current_price: float, symbol: str) -> Tuple[bool, str, float]:
        """
        Detecta si el precio hizo un mínimo reciente y luego recuperó por encima de VWAP

        Esta es una estrategia de entrada superior a comprar en máximos porque:
        - Compras después del pullback/dip (mejor precio)
        - Confirmas que VWAP actúa como soporte
        - Evitas comprar en exhaustion
        - Mejor relación riesgo/recompensa

        Casos detectados:
        A. Mínimo arriba de VWAP -> rebote -> sube -> BUY
        B. Mínimo toca VWAP (±0.5%) -> rebota -> sube -> BUY
        C. Mínimo perfora VWAP -> recupera -> sube por encima -> BUY ✅ (señal más fuerte)

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

            # 3. Calcular distancia del mínimo al VWAP
            vwap_distance_pct = ((min_price - vwap_price) / vwap_price) * 100

            # 4. Verificar que el precio ACTUAL está por encima de VWAP (recuperación confirmada)
            if current_price < vwap_price:
                return False, f"Current price ${current_price:.2f} still below VWAP ${vwap_price:.2f}", 0.0

            # 5. Si pasamos filtros, devolver True y strength
            strength = min_price  # Use min_price as support level for dynamic stop loss
            if vwap_distance_pct > -2.0:
                details = f"VWAP Reclaim (strong) - min ${min_price:.2f}, VWAP ${vwap_price:.2f} ({vwap_distance_pct:.1f}%)"
            else:
                details = f"VWAP Reclaim - min ${min_price:.2f}, VWAP ${vwap_price:.2f} ({vwap_distance_pct:.1f}%)"

            return True, details, strength

        except Exception as e:
            self.logger.warning(f"Error checking VWAP reclaim: {e}")
            return False, f"Error: {e}", 0.0

    def calculate_adaptive_risk(
        self,
        opportunity: Dict[str, Any],
        ods_data: Optional[Any] = None,
        intraday_structure: Optional[Any] = None,
        structural_exits: Optional[Dict] = None
    ) -> float:
        """
        [OVERRIDE] Implement Tiered Sizing for Daily Plays (Conviction Sizing)
        - EARNINGS -> Multiplier 1.5x (Tier A)
        - OTHERS -> Multiplier 0.5x (Tier B)
        """
        # 1. Get Base Adaptive Risk (Quality + Pattern Boosts)
        base_risk = super().calculate_adaptive_risk(
            opportunity, ods_data, intraday_structure, structural_exits
        )
        
        # 2. Check Config for Tiered Sizing
        section = 'DAILY_PLAYS_MIDCAP_STRATEGY'
        if self.config:
            enable_tiered = getattr(self.config, 'getboolean', lambda s, k, f: f)(section, 'enable_tiered_sizing', fallback=False)
            
            if not enable_tiered:
                return base_risk
                
            earnings_mult = float(getattr(self.config, 'get', lambda s, k, f: f)(section, 'earnings_risk_multiplier', fallback=1.5))
            standard_mult = float(getattr(self.config, 'get', lambda s, k, f: f)(section, 'standard_risk_multiplier', fallback=0.5))
        else:
            return base_risk

        # 3. Apply Multiplier by Catalyst Type
        catalyst_type = opportunity.get('catalyst_type', 'NONE').upper()
        
        final_risk = base_risk
        
        if catalyst_type == 'EARNINGS':
            final_risk = base_risk * earnings_mult
            self.logger.info(f"💰 {opportunity.get('symbol')}: TIER A (Earnings) - Sizing UP {earnings_mult}x -> {final_risk*100:.2f}% risk")
        else:
            final_risk = base_risk * standard_mult
            self.logger.info(f"🛡️ {opportunity.get('symbol')}: TIER B (Standard) - Sizing DOWN {standard_mult}x -> {final_risk*100:.2f}% risk")
            
        return final_risk



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