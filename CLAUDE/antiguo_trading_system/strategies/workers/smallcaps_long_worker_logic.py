"""
Small Caps Long Worker Logic
Worker específico para estrategia Small Caps Long basada en reglas validadas por el sistema de extracción de reglas.

Regla validada aplicada:
- RULE_detailed_volume_analysis_very_high_volume_bullish
  * Edge esperado: +17.64%
  * Consistencia: 73.6%
  * Preservación Walk-Forward: 55.6%
  * Sample size: 163 eventos históricos

Criterios de la regla (permissive adjustment):
1. volume_ratio >= 2.0  (very high volume - inclusive to accept exactly 2.0x)
2. daily_return_pct > 0  (bullish price action from open to current)

Enfoque: Long positions en small caps con EXACTLY validated criteria
Última actualización: 2025-11-06 - Simplificado para coincidir con regla validada
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class SmallCapsLongWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Small Caps Long

    Basado en reglas validadas por el sistema de extracción de reglas:
    - RULE_detailed_volume_analysis_very_high_volume_bullish
    - Edge esperado: +17.64%
    - Consistencia: 73.6%
    - Preservación Walk-Forward: 55.6%

    Criterios de entrada (UPDATED 2025-11-06):
    1. Small cap ($0.50-$25)
    2. Volume ratio >= 2.0x (permissive: includes exactly 2.0x)
    3. Daily return > 0% (EXACT match to rule: open to current)
    4. Precio > VWAP (filtro técnico adicional)
    5. Sin posiciones duplicadas
    6. ANTI-REVERSAL filters (5-min timeframe for reliability):
       - MACD no descendiendo (evita picos con tendencia bajista)
       - Precio no bajo EMA20 descendente
       - RSI < 75 (evita sobrecompra extrema)

    Criterios de salida (via WorkerStopManager):
    - Take profit: 15% (conservador para small caps)
    - Stop loss: 5%
    - Trailing stop: 4% activation, 2% distance
    - Time-based: 6 horas máximo
    - END_OF_DAY: 15:56 ET
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="smallcaps_long",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Small Caps Long
        self.min_price = 0.50          # Precio mínimo (small caps)
        self.max_price = 25.0          # Precio máximo (small caps)
        self.min_volume_ratio = 2.0    # Ratio mínimo de volumen (>=2.0x permissive: includes exactly 2.0x)
        self.min_market_cap = 50000000 # Capitalización mínima $50M

        # Requisitos técnicos
        self.require_vwap_above = True  # Precio debe estar > VWAP
        self.max_gap_pct = 15.0         # Máximo gap permitido (%)

        # Entry confirmation tracking
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 1    # 1 confirmación suficiente
        self.confirmation_window = 60 # Ventana de 1 minuto

        # FILTROS ANTI-REVERSAL: Usar módulo común
        from .trend_filters import create_trend_filters_from_config
        if config:
            self.trend_filters = create_trend_filters_from_config(config, 'SMALLCAPS_LONG_STRATEGY', logger=self.logger)
        else:
            from .trend_filters import TrendFilters
            self.trend_filters = TrendFilters(logger=self.logger)

        # Initialize centralized stop manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'SMALLCAPS_LONG_STRATEGY')

        self.logger.info(
            f"🎯 Small Caps Long Worker configured (EXACT RULE MATCH): "
            f"price=${self.min_price}-${self.max_price}, vol>={self.min_volume_ratio}x, "
            f"daily_return>0%, vwap_required={self.require_vwap_above}"
        )
        self.logger.info(f"   Expected Edge: +17.64% (validated on 163 events)")
        self.logger.info(f"   Anti-Reversal Filters: MACD={self.trend_filters.enable_macd}, "
                        f"EMA={self.trend_filters.enable_ema}, RSI={self.trend_filters.enable_rsi}")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    def _is_trading_hours(self, time_decimal: float) -> bool:
        """
        Check if current time is within allowed trading hours
        Small caps: 9:45 AM ET to 4:00 PM ET
        """
        return 9.75 <= time_decimal <= 16.0

    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hours in US/Eastern timezone"""
        try:
            import pytz
            from datetime import datetime

            eastern = pytz.timezone('US/Eastern')

            if isinstance(timestamp, str):
                from dateutil import parser
                dt = parser.parse(timestamp)
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
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

            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.error(f"Error converting timestamp to time: {e}")
            return 0.0

    def _validate_smallcap_criteria(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate basic small cap criteria

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (is_valid, reason)
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')
        current_price = opportunity.get('current_price', 0)
        volume_ratio = opportunity.get('volume_ratio', 0)
        market_cap = opportunity.get('market_cap', 0)

        # Price range validation
        if not (self.min_price <= current_price <= self.max_price):
            return False, f"Price ${current_price:.2f} outside range ${self.min_price}-${self.max_price}"

        # Volume validation
        if volume_ratio < self.min_volume_ratio:
            return False, f"Volume ratio {volume_ratio:.1f}x < {self.min_volume_ratio}x"

        # Market cap validation (if available)
        if market_cap > 0 and market_cap < self.min_market_cap:
            return False, f"Market cap ${market_cap:,.0f} < ${self.min_market_cap:,.0f}"

        return True, "Small cap criteria met"

    def _validate_technical_conditions(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate technical conditions for entry

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (is_valid, reason)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            current_price = opportunity.get('current_price', 0)
            gap_pct = abs(opportunity.get('gap_percentage', 0))

            # VWAP validation
            bars = self.get_bars_from_opportunity(opportunity)
            if bars and self.require_vwap_above:
                vwap_price = self.calculate_vwap_from_bars(bars)
                if vwap_price and current_price <= vwap_price:
                    return False, f"Price ${current_price:.2f} <= VWAP ${vwap_price:.2f}"

            # Gap validation (avoid extreme gaps)
            if gap_pct > self.max_gap_pct:
                return False, f"Gap {gap_pct:.1f}% > {self.max_gap_pct}%"

            # Basic trend validation (price should be moving up)
            if bars and len(bars) >= 3:
                recent_prices = [bar.close for bar in bars[-3:]]
                if recent_prices[-1] < recent_prices[0]:
                    return False, "Price trending down in recent bars"

            return True, "Technical conditions met"

        except Exception as e:
            self.logger.error(f"Error validating technical conditions: {e}")
            return False, f"Technical validation error: {str(e)}"

    def _calculate_daily_return(self, opportunity: Dict[str, Any]) -> float:
        """
        Calculate daily return (open to current price)

        This matches the exact calculation used in the validated rule:
        daily_return_pct = (current_price - open_price) / open_price * 100

        Args:
            opportunity: Opportunity data with bars

        Returns:
            Daily return percentage (can be negative)
        """
        try:
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 1:
                self.logger.warning("No bars available for daily_return calculation")
                return -999.0  # Sentinel value indicating failure

            # Get day's open price (first bar of the day)
            open_price = bars[0].open

            # Get current price
            current_price = opportunity.get('current_price', 0)

            if open_price <= 0:
                self.logger.warning(f"Invalid open_price: {open_price}")
                return -999.0

            # Calculate daily return
            daily_return_pct = ((current_price - open_price) / open_price) * 100

            return daily_return_pct

        except Exception as e:
            self.logger.error(f"Error calculating daily_return: {e}")
            return -999.0

    def _detect_bullish_volume_signal(self, opportunity: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Detect bullish volume signal - EXACT match to validated rule

        VALIDATED RULE: RULE_detailed_volume_analysis_very_high_volume_bullish

        Criteria (permissive adjustment):
        - volume_ratio >= 2.0  (very high volume - inclusive)
        - daily_return_pct > 0  (bullish price action)

        Edge: +17.64%
        Consistency: 73.6%
        Preservation: 55.6%
        Sample size: 163 events

        NO additional criteria to avoid overfitting and maintain validated edge.

        Args:
            opportunity: Opportunity data

        Returns:
            Tuple (signal_detected, details)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            volume_ratio = opportunity.get('volume_ratio', 0)

            self.logger.info(f"🔍 {symbol}: Checking VALIDATED rule - vol={volume_ratio:.1f}x")

            # CRITERION 1: Very high volume (>= 2.0x) - permissive to include exactly 2.0x
            if volume_ratio < 2.0:
                self.logger.info(f"❌ {symbol}: Volume {volume_ratio:.1f}x < 2.0x (rule requirement)")
                return False, f"Volume {volume_ratio:.1f}x < 2.0x"

            # CRITERION 2: Positive daily return (bullish)
            daily_return_pct = self._calculate_daily_return(opportunity)

            if daily_return_pct == -999.0:  # Calculation failed
                self.logger.warning(f"⚠️ {symbol}: Cannot calculate daily_return (missing bars)")
                return False, "Cannot calculate daily_return"

            if daily_return_pct <= 0:
                self.logger.info(f"❌ {symbol}: Daily return {daily_return_pct:.2f}% <= 0% (not bullish)")
                return False, f"Daily return {daily_return_pct:.2f}% <= 0%"

            # BOTH CRITERIA MET - EXACT RULE MATCH
            self.logger.info(
                f"✅ {symbol}: VALIDATED_RULE_MATCH - "
                f"vol={volume_ratio:.1f}x (>2.0), return={daily_return_pct:.2f}% (>0)"
            )

            return True, f"VALIDATED_RULE: vol={volume_ratio:.1f}x, daily_return={daily_return_pct:.2f}%"

        except Exception as e:
            self.logger.error(f"Error detecting bullish volume signal: {e}")
            return False, f"Signal detection error: {str(e)}"

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Small Caps Long

        CRITERIOS DE ENTRADA:
        1. Trading hours validation
        2. Small cap criteria (price, volume, market cap)
        3. Bullish volume signal detected (vol >= 2.0x, daily_return > 0%)
        4. Technical conditions met (VWAP, gap, price trend)
        5. Anti-reversal filters (MACD/EMA/RSI on 5-min bars - evita trampas)
        6. No duplicate positions

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

            self.logger.info(f"🔍 SMALLCAPS_LONG: Evaluating {symbol} at ${current_price:.2f}")

            # ====
            # CRITICAL VALIDATION 1: Check trading hours
            # ====
            from datetime import datetime
            import pytz
            # FIX: Use current time in Spain timezone, then convert to Eastern
            # Since we're in Spain (Europe/Madrid), datetime.now() gives Spain time
            spain_tz = pytz.timezone('Europe/Madrid')
            current_spain_time = datetime.now(spain_tz)
            current_time = self._get_time_from_timestamp(current_spain_time)

            if not self._is_trading_hours(current_time):
                self.logger.warning(
                    f"❌ {symbol}: REJECTED - Outside trading hours "
                    f"(current ET: {current_time:.2f}, allowed: 9.75-16.00 ET)"
                )
                return False

            # ====
            # VALIDATION 2: Small cap criteria
            # ====
            smallcap_valid, smallcap_reason = self._validate_smallcap_criteria(opportunity)
            if not smallcap_valid:
                self.logger.info(f"❌ {symbol}: REJECTED - {smallcap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Small cap criteria passed - {smallcap_reason}")

            # ====
            # VALIDATION 3: Bullish volume signal detection (MULTI-RULE)
            # ====
            signal_detected, signal_details = self._detect_bullish_volume_signal(opportunity)
            if not signal_detected:
                self.logger.info(f"❌ {symbol}: REJECTED - No bullish signal: {signal_details}")
                return False

            self.logger.info(f"✅ {symbol}: Bullish signal detected - {signal_details}")

            # Store signal details for horizon determination
            opportunity['_signal_details'] = signal_details

            # ====
            # VALIDATION 4: Technical conditions
            # ====
            technical_valid, technical_reason = self._validate_technical_conditions(opportunity)
            if not technical_valid:
                self.logger.info(f"❌ {symbol}: REJECTED - {technical_reason}")
                return False

            self.logger.info(f"✅ {symbol}: Technical conditions passed - {technical_reason}")

            # ====
            # VALIDATION 5: Anti-Reversal Filters (MACD/EMA/RSI) - Using 5-min bars
            # ====
            # Fetch 5-minute bars for more reliable trend analysis (less noise than 1-min)
            try:
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')

                bars_5min = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='1 D',        # 1 día de datos
                    barSizeSetting='5 mins',  # Barras de 5 minutos (menos ruido)
                    whatToShow='TRADES',
                    useRTH=False
                )

                if bars_5min and len(bars_5min) >= 30:
                    trend_valid, trend_reason = self.trend_filters.check_trend_filters(
                        bars=bars_5min,
                        current_price=current_price,
                        surveillance_mode=False  # Strict mode for smallcaps_long
                    )
                    if not trend_valid:
                        self.logger.info(f"⚪ {symbol}: REJECTED - Anti-reversal filter (5-min): {trend_reason}")
                        return False

                    self.logger.info(f"✅ {symbol}: Anti-reversal filters passed (5-min) - {trend_reason}")
                else:
                    self.logger.warning(f"⚠️ {symbol}: Insufficient 5-min bars for trend filters (using {len(bars_5min) if bars_5min else 0} bars)")
            except Exception as e:
                self.logger.error(f"⚠️ {symbol}: Error fetching 5-min bars for trend filters: {e}")
                # Continue without trend filter if bars cannot be fetched (fail-safe)

            # ====
            # ENTRY APPROVED
            # ====
            self.logger.info(
                f"✅ {symbol}: SMALLCAPS_LONG ENTRY APPROVED - "
                f"Price: ${current_price:.2f}, Signal: {signal_details}"
            )

            # Clean up any pending entries tracking
            if symbol in self.pending_entries:
                del self.pending_entries[symbol]

            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal ADAPTIVO basado en MULTIPLE RULES validadas

        ADAPTIVE HORIZON SYSTEM:
        - Analiza qué reglas se activaron para determinar el horizonte óptimo
        - Reglas de momentum → horizontes más largos (potencial swing)
        - Reglas de volumen puro → horizontes más cortos (intraday)
        - Reglas premarket → foco matutino
        - Múltiples señales → mayor confianza, horizontes más largos

        MARKET ADAPTATION:
        - Si el mercado muestra momentum fuerte → extiende horizonte
        - Si es breakout intraday puro → horizonte corto
        - Si hay confirmación premarket → foco mañana
        """
        volume_ratio = signal_data.get('volume_ratio', 1.0)
        confidence = signal_data.get('confidence', 50)

        # Extract signal details from opportunity data
        signal_details = signal_data.get('_signal_details', '')
        has_momentum_bounce = 'momentum_bounce' in signal_details
        has_strong_momentum = 'strong_momentum' in signal_details
        has_premarket = 'premarket_momentum' in signal_details
        has_composite = 'COMPOSITE' in signal_details
        has_weak_primary = 'WEAK PRIMARY' in signal_details

        # RULE-BASED HORIZON DETERMINATION:

        # SWING_SHORT: Momentum rules + strong volume + multiple confirmations
        if ((has_momentum_bounce or has_strong_momentum) and volume_ratio >= 2.0) or \
           (has_composite and volume_ratio >= 2.5) or \
           (volume_ratio >= 3.0 and confidence > 70):

            if has_momentum_bounce:
                horizon_hours = 72.0  # 3 days for bounce plays
                reason = "momentum bounce pattern"
            elif has_strong_momentum:
                horizon_hours = 48.0  # 2 days for continuation
                reason = "strong momentum continuation"
            else:
                horizon_hours = 24.0  # 1 day for volume breakout
                reason = "high volume breakout"

            self.logger.info(f"🎯 SWING_SHORT ({horizon_hours:.0f}h): {reason}")
            return TradingHorizon.SWING_SHORT, horizon_hours

        # INTRADAY: Standard volume breakout + decent confidence
        elif volume_ratio >= 2.0 and confidence > 60:

            if has_premarket:
                horizon_hours = 4.0  # Focus on morning
                reason = "premarket momentum + volume"
            elif has_weak_primary:
                horizon_hours = 3.0  # Quick scalp if weak primary
                reason = "weak primary signal"
            else:
                horizon_hours = 6.0  # Standard intraday
                reason = "standard volume breakout"

            self.logger.info(f"🎯 INTRADAY ({horizon_hours:.0f}h): {reason}")
            return TradingHorizon.INTRADAY, horizon_hours

        # REJECT: Insufficient signal strength
        else:
            self.logger.warning(f"❌ REJECTED: Insufficient signal (vol={volume_ratio:.1f}x, conf={confidence:.0f}%)")
            return TradingHorizon.SCALP, 0.5  # Will be rejected by entry logic

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios Small Caps Long

        Criterios de salida:
        1. Take profit: 15% (conservador para small caps volátiles)
        2. Stop loss: 5%
        3. Trailing stop: 4% activation, 2% distance
        4. Time-based: 6 horas máximo
        5. END_OF_DAY: 15:56 ET

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
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='300 S',  # 5 minutes
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
                self.logger.debug(f"Could not get market data for exit analysis: {e}")

            # Prepare position metadata
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 6.0)
            }

            # Use centralized stop manager
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
            # In case of error, exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager AND unified position manager"""
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager
            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} with stop manager")

            # Register with unified position manager
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 200.0)

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='long',
                    position_data={
                        'strategy': 'smallcaps_long',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat(),
                        'expected_edge': 17.64,  # From validated rule
                        'rule': 'detailed_volume_analysis_very_high_volume_bullish'
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (SMALLCAPS_LONG trading)")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from both managers"""
        # Calculate PnL before unregistering
        pnl_pct = None

        from core.service_locator import get_unified_position_manager
        unified_manager = await get_unified_position_manager()

        if unified_manager:
            position_data = unified_manager.get_position(symbol)
            if position_data:
                entry_price = position_data.get('entry_price', 0)
                if entry_price > 0:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    self.logger.debug(f"📊 {symbol} exit PnL: {pnl_pct:.2f}%")

        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Unregister from unified position manager
        if unified_manager:
            unified_manager.unregister_position(symbol, 'long', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (SMALLCAPS_LONG trading)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)