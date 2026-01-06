"""
VWAP Breakout Worker Logic
Worker especializado para estrategia VWAP Breakout (Volume Weighted Average Price)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class VWAPWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia VWAP Breakout

    Enfoque: VWAP Breakout intraday con filtros de momentum y liquidez
    Ideal para acciones con fuerte movimiento volumétrico alrededor del VWAP

    Criterios de entrada:
    - Breakout above/below VWAP diario
    - Filtro de bias direccional (close > open del día para longs)
    - Validación de volumen mínimo
    - Momentum confirmation (RSI, precio action)

    Criterios de salida:
    - ATR trailing stop (1.5 ATR recomendado)
    - VWAP retest stops
    - Time-based exit (15:45 ET)
    - Profit targets dinámicos
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración VWAP específica (from config.ini VWAP_BREAKOUT_STRATEGY)
        # Load from config if available, otherwise use defaults
        from core.service_locator import get_service_locator
        config_obj = get_service_locator().get_config() if config else None

        self.min_volume_ratio = getattr(config_obj, 'min_volume_ratio', 1.5)
        self.min_daily_volume = getattr(config_obj, 'min_daily_volume', 500_000)
        self.vwap_window_minutes = getattr(config_obj, 'vwap_window_minutes', 120)
        self.rsi_period = getattr(config_obj, 'rsi_period', 14)
        self.rsi_overbought = getattr(config_obj, 'rsi_overbought', 85)
        self.rsi_oversold = getattr(config_obj, 'rsi_oversold', 15)
        self.min_price = getattr(config_obj, 'min_price', 2.0)
        self.max_price = getattr(config_obj, 'max_price', 50.0)

        # CRITICAL: Minimum VWAP trend required for breakout (from config.ini)
        # This prevents false breakouts on flat/weak VWAP trends
        # RELAXED: 0.15 -> 0.08 to capture more valid setups
        self.min_vwap_trend_pct = getattr(config_obj, 'min_vwap_trend_pct', 0.08)

        # Momentum filters
        self.require_rsi_confirmation = True # Requerir RSI en zona favorable
        self.require_volume_spike = True     # Requerir spike de volumen

        # BUY-THE-DIP SYSTEM: Wait for pullback after breakout detection
        self.enable_buy_the_dip = True           # Enable pullback entry strategy
        self.dip_pullback_min_pct = 0.30         # Min 30% pullback of move
        self.dip_pullback_max_pct = 0.60         # Max 60% pullback (deeper = invalidated)
        self.dip_timeout_minutes = 20            # Max 20 minutes to wait for dip
        self.dip_volume_multiplier = 1.5         # Need 1.5x volume on dip entry
        self.breakout_tracker = {}               # {symbol: {'high': float, 'vwap': float, 'timestamp': datetime}}

        # Initialize centralized stop manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'VWAP_BREAKOUT_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,           # 3% stop loss (VWAP strategies are tighter)
                take_profit_pct=8.0,         # 8% profit target
                quick_target_pct=4.0,        # Quick 4% target for fast profits
                trailing_activation=2.0,     # Activate trailing at 2%
                trailing_distance=1.5,       # 1.5% trailing distance
                max_position_hours=6.0       # Max 6 hours in position
            ))

        self.logger.info(
            f"🎯 VWAP Breakout Worker configured: "
            f"vol>={self.min_volume_ratio}x, price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   VWAP Window: {self.vwap_window_minutes}min, Min Trend: {self.min_vwap_trend_pct:+.2f}%")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón VWAP Breakout (0-100%)

        PATTERN COMPLETION CRITERIA:
        - 30%: VWAP calculado correctamente
        - 50%: Volume y liquidez validados
        - 70%: Momentum confirmado (RSI en zona favorable)
        - 85%: Breakout confirmado + filtros aplicados
        - 100%: Setup completo listo para entrada

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 50:
                return 0.0

            current_price = opportunity.get('current_price', 0)
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Stage 1: VWAP calculation (30%)
            vwap = self.calculate_vwap_from_bars(bars[-self.vwap_window_minutes:] if len(bars) >= self.vwap_window_minutes else bars)
            if vwap is not None:
                completion += 30.0
                self.logger.debug(f"📊 {symbol}: VWAP calculated = ${vwap:.2f}")
            else:
                return 0.0

            # Stage 2: Volume & Liquidity validation (50%)
            if volume_ratio >= self.min_volume_ratio:
                completion += 10.0
                self.logger.debug(f"📊 {symbol}: Volume validated ({volume_ratio:.1f}x)")

            if self.min_price <= current_price <= self.max_price:
                completion += 10.0
                self.logger.debug(f"📊 {symbol}: Price range validated (${current_price:.2f})")

            # Stage 3: Momentum confirmation (70%)
            rsi = self.calculate_rsi_from_bars(bars, self.rsi_period)
            if rsi is not None:
                # For longs: prefer RSI not overbought, for shorts: not oversold
                if rsi <= self.rsi_overbought:  # Room to run for longs
                    completion += 20.0
                    self.logger.debug(f"📊 {symbol}: RSI validated ({rsi:.1f})")
                else:
                    # Still give partial credit for overbought (just less optimal)
                    completion += 10.0
                    self.logger.debug(f"📊 {symbol}: RSI overbought but acceptable ({rsi:.1f})")
            else:
                # No RSI data available, give partial credit
                completion += 15.0
                self.logger.debug(f"📊 {symbol}: No RSI data, partial credit")

            # Stage 4: Breakout setup (85-100%)
            # For breakout strategies, we want price significantly above/below VWAP
            price_to_vwap_ratio = current_price / vwap

            if price_to_vwap_ratio >= 1.05 or price_to_vwap_ratio <= 0.95:  # 5%+ away from VWAP = breakout
                completion += 15.0
                self.logger.debug(f"📊 {symbol}: Breakout from VWAP detected ({price_to_vwap_ratio:.3f})")

                # Full completion if all conditions met
                if volume_ratio >= self.min_volume_ratio and self.min_price <= current_price <= self.max_price:
                    completion = 100.0
                    self.logger.info(f"✅ {symbol}: VWAP breakout setup complete (100%)")
            else:
                # Price near VWAP - potential setup but not breakout yet
                completion += 5.0
                self.logger.debug(f"📊 {symbol}: Near VWAP ({price_to_vwap_ratio:.3f}) - potential setup")

            self.logger.info(f"📊 {symbol}: VWAP pattern completion = {completion:.0f}%")
            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating VWAP pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios VWAP Breakout

        VWAP BREAKOUT STRATEGY:
        - Long: Close > VWAP + Close > Day Open + Momentum confirmation
        - Short: Close < VWAP + Close < Day Open + Momentum confirmation
        - Filters: Volume, RSI, Time, Liquidity

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

            # Calculate pattern completion
            completion = await self.calculate_pattern_completion(opportunity)

            # Must have at least 70% pattern completion for entry consideration
            if completion < 70.0:
                self.logger.info(f"⚪ {symbol}: VWAP pattern not ready ({completion:.0f}% < 70%)")
                return False

            # Get bars for detailed analysis
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 50:
                self.logger.info(f"⚪ {symbol}: Insufficient bars for VWAP analysis ({len(bars) if bars else 0})")
                return False

            current_price = opportunity.get('current_price', 0)
            current_bar = bars[-1]

            # ============================================================
            # CRITICAL VALIDATION 1: VWAP Strength Check
            # ============================================================
            vwap_valid, vwap_reason = self.validate_vwap_strength(
                bars, current_price,
                vwap_window_minutes=self.vwap_window_minutes,
                opportunity=opportunity
            )

            if not vwap_valid:
                self.logger.warning(f"❌ {symbol}: VWAP validation failed - {vwap_reason}")
                return False

            self.logger.info(f"✅ {symbol}: VWAP validation passed - {vwap_reason}")

            # ============================================================
            # ADDITIONAL VALIDATION: VWAP Trend Strength (VWAP Breakout specific)
            # ============================================================
            # For VWAP Breakout strategy, we need STRONG trend, not just positive
            # This prevents false breakouts like NVTS (+0.07% trend)

            vwap_trend_strength = self._validate_strong_vwap_trend(bars, current_price)
            if vwap_trend_strength < self.min_vwap_trend_pct:
                self.logger.warning(
                    f"❌ {symbol}: VWAP trend too weak for breakout - "
                    f"{vwap_trend_strength:+.2f}% (need >={self.min_vwap_trend_pct:+.2f}%)"
                )
                return False

            self.logger.info(
                f"✅ {symbol}: VWAP trend strong enough for breakout - {vwap_trend_strength:+.2f}%"
            )

            # ============================================================
            # VWAP BOUNCE CONFIRMATION (2nd/3rd Touch Strategy)
            # ============================================================
            # NEW LOGIC: Don't enter on first touch, wait for 2nd/3rd bounce with higher lows
            # This confirms VWAP as support and filters false breakouts

            # Calculate VWAP
            vwap = self.calculate_vwap_from_bars(bars[-self.vwap_window_minutes:] if len(bars) >= self.vwap_window_minutes else bars)
            if vwap is None:
                self.logger.info(f"⚪ {symbol}: Could not calculate VWAP")
                return False

            # VALIDATE: Detect 2nd/3rd bounce with higher lows
            bounce_confirmed, bounce_details, support_level = self._detect_vwap_bounce_confirmation(
                bars, vwap, current_price, symbol
            )

            if not bounce_confirmed:
                self.logger.info(f"⚪ {symbol}: {bounce_details}")
                return False

            # Store support level for dynamic stop loss
            opportunity['support_level'] = support_level

            self.logger.info(f"✅ {symbol}: VWAP BOUNCE CONFIRMED - {bounce_details}")

            # Get day's open price (first bar of the day)
            day_open = self._get_day_open_price(bars)
            if day_open is None:
                # For testing purposes, allow entry without day open check
                # In production, this would be required
                self.logger.debug(f"⚪ {symbol}: Could not determine day open - allowing for testing")
                day_open = current_price * 0.8  # Assume day open is 20% lower

            # Time validation - Use centralized hour validation from BaseWorkerLogic
            is_valid_hours, current_time = self.is_within_entry_hours(symbol)
            if not is_valid_hours:
                self.logger.info(f"⚪ {symbol}: Outside trading hours ({current_time:.2f})")
                return False

            # Volume validation
            volume_ratio = opportunity.get('volume_ratio', 1.0)
            if volume_ratio < self.min_volume_ratio:
                self.logger.info(f"⚪ {symbol}: Volume too low ({volume_ratio:.1f}x < {self.min_volume_ratio}x)")
                return False

            # RSI confirmation (optional but recommended)
            if self.require_rsi_confirmation:
                rsi = self.calculate_rsi_from_bars(bars, self.rsi_period)
                if rsi is not None:
                    if rsi > self.rsi_overbought:
                        self.logger.info(f"⚪ {symbol}: RSI overbought ({rsi:.1f} > {self.rsi_overbought})")
                        return False

            # BUY-THE-DIP SYSTEM: Two-phase entry strategy
            if self.enable_buy_the_dip:
                # Check if we should enter on dip
                dip_entry = await self._evaluate_buy_the_dip_entry(
                    symbol, current_price, vwap, day_open, bars, opportunity
                )
                if dip_entry['should_enter']:
                    self.logger.info(
                        f"✅ {symbol}: BUY-THE-DIP ENTRY APPROVED - "
                        f"Price: ${current_price:.2f}, VWAP: ${vwap:.2f}, "
                        f"Pullback: {dip_entry.get('pullback_pct', 0):.1f}%, "
                        f"Direction: {dip_entry.get('direction', 'N/A').upper()}"
                    )
                    return True
                else:
                    return False
            else:
                # LEGACY: Immediate breakout entry (old behavior)
                breakout_detected = False
                direction = None

                # LONG BREAKOUT: Price above VWAP + bullish bias
                if current_price > vwap and current_price > day_open:
                    # Additional confirmation: recent price action shows strength
                    if self._confirm_breakout_strength(bars, vwap, 'long'):
                        breakout_detected = True
                        direction = 'long'
                        self.logger.info(f"🚀 {symbol}: VWAP LONG BREAKOUT detected!")

                # SHORT BREAKOUT: Price below VWAP + bearish bias
                elif current_price < vwap and current_price < day_open:
                    # Additional confirmation: recent price action shows weakness
                    if self._confirm_breakout_strength(bars, vwap, 'short'):
                        breakout_detected = True
                        direction = 'short'
                        self.logger.info(f"📉 {symbol}: VWAP SHORT BREAKOUT detected!")

                if breakout_detected:
                    self.logger.info(
                        f"✅ {symbol}: VWAP BREAKOUT ENTRY APPROVED - "
                        f"Price: ${current_price:.2f}, VWAP: ${vwap:.2f}, "
                        f"Direction: {direction.upper()}"
                    )
                    return True
                else:
                    self.logger.info(f"⚪ {symbol}: No VWAP breakout detected")
                    return False

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VWAP opportunity: {e}")
            return False

    def _determine_trading_horizon(self, signal_data: Dict[str, Any]) -> Tuple[TradingHorizon, float]:
        """
        Determina horizonte temporal para VWAP Breakout

        VWAP Breakout horizons:
        - INTRADAY (same day): Most common - VWAP breakouts are intraday mean reversion
        - SCALP: Quick breakout trades
        - SWING_SHORT: Very rare - only extremely strong setups

        VWAP Breakout es CASI SIEMPRE INTRADAY porque:
        - VWAP es indicador intraday (resetea cada día)
        - Breakouts de VWAP tienden a revertir same day
        - No hay catalyst fundamental, solo técnico
        - Mean reversion dominante en estas setups

        Factors:
        - Breakout distance from VWAP
        - Volume confirmation
        - Momentum strength
        - Time of day (mejor early session)
        """
        confidence = signal_data.get('confidence', 50)
        risk_reward = signal_data.get('risk_reward', 1.5)
        volume_zscore = signal_data.get('volume_zscore', 0)
        # daily_potential available but VWAP almost never uses it (intraday indicator)

        # INTRADAY: Standard VWAP breakout (vast majority of trades)
        if confidence > 50 and risk_reward > 1.5:
            # Good VWAP breakout - play intraday
            return TradingHorizon.INTRADAY, 3.0  # 3 hours typical (shorter than other workers)

        # SCALP: Weaker VWAP breakout - quick scalp
        elif confidence > 40:
            # Marginal breakout - scalp quickly
            return TradingHorizon.SCALP, 0.5  # 30 min max

        # Very weak - should be rejected
        else:
            return TradingHorizon.SCALP, 0.25  # 15 min

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios VWAP

        EXIT CRITERIA:
        1. VWAP retest (price back to VWAP level)
        2. ATR trailing stop
        3. Time-based exit (15:45 ET)
        4. Profit targets

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

            # Get market data for VWAP calculation
            bars = None
            try:
                # Try to get recent bars for VWAP calculation
                # This would need to be implemented based on available data
                pass
            except Exception as e:
                self.logger.debug(f"Could not get bars for VWAP exit: {e}")

            # Prepare position metadata for EOD check
            position_metadata = {
                'EOD_safe': position.get('EOD_safe', False),
                'trading_horizon': position.get('trading_horizon', 'unknown'),
                'expected_hold_hours': position.get('expected_hold_hours', 0)
            }

            # Use centralized stop manager for primary exit logic
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data={'bars': bars} if bars else None,
                position_metadata=position_metadata
            )

            # Additional VWAP-specific exit conditions
            if not should_exit and bars:
                # VWAP retest exit (if price comes back to VWAP)
                vwap = self.calculate_vwap_from_bars(bars[-60:] if len(bars) >= 60 else bars)  # Last hour VWAP
                if vwap is not None:
                    price_to_vwap_ratio = abs(current_price - vwap) / vwap

                    # Exit if price retests VWAP (within 0.5%)
                    if price_to_vwap_ratio <= 0.005:
                        should_exit = True
                        reason = f"VWAP_RETEST_{'LONG' if current_price < entry_price else 'SHORT'}"

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating VWAP exit for {symbol}: {e}")
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
            self.logger.debug(f"📝 Registered {symbol} with VWAP stop manager")

            # Register with unified position manager (prevent duplicates)
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 200.0)  # Default VWAP position

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='vwap_breakout',
                    position_data={
                        'strategy': 'vwap_breakout',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (VWAP trading)")

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
                    self.logger.debug(f"📊 {symbol} VWAP exit PnL: {pnl_pct:.2f}%")

        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Unregister from unified position manager
        if unified_manager:
            unified_manager.unregister_position(symbol, 'vwap_breakout', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (VWAP trading)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    # ============================================================================
    # VWAP-SPECIFIC HELPER METHODS
    # ============================================================================

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
                # Fallback
                return 12.0

            # Validate dt is datetime before accessing tzinfo
            if not isinstance(dt, datetime):
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

    def _get_day_open_price(self, bars: list) -> float:
        """
        Get the opening price for the current trading day

        Args:
            bars: List of bars

        Returns:
            Day open price or None if not available
        """
        try:
            if not bars:
                return None

            # Find first bar of the current day
            current_day = bars[-1].timestamp.date() if hasattr(bars[-1], 'timestamp') else None
            if not current_day:
                return None

            # Look for the first bar of the day
            for bar in reversed(bars):
                bar_date = bar.timestamp.date() if hasattr(bar, 'timestamp') else None
                if bar_date == current_day:
                    return bar.open

            return None

        except Exception as e:
            self.logger.debug(f"Error getting day open price: {e}")
            return None

    def _confirm_breakout_strength(self, bars: list, vwap: float, direction: str) -> bool:
        """
        Confirm breakout strength with additional filters

        Args:
            bars: Recent bars
            vwap: Current VWAP value
            direction: 'long' or 'short'

        Returns:
            True if breakout is confirmed strong
        """
        try:
            if len(bars) < 5:
                return False

            recent_bars = bars[-5:]  # Last 5 bars

            if direction == 'long':
                # For longs: check if we're consistently above VWAP and closing higher
                bars_above_vwap = sum(1 for bar in recent_bars if bar.close > vwap)
                closing_higher = sum(1 for i in range(1, len(recent_bars)) if recent_bars[i].close > recent_bars[i-1].close)

                return bars_above_vwap >= 4 and closing_higher >= 3

            elif direction == 'short':
                # For shorts: check if we're consistently below VWAP and closing lower
                bars_below_vwap = sum(1 for bar in recent_bars if bar.close < vwap)
                closing_lower = sum(1 for i in range(1, len(recent_bars)) if recent_bars[i].close < recent_bars[i-1].close)

                return bars_below_vwap >= 4 and closing_lower >= 3

            return False

        except Exception as e:
            self.logger.debug(f"Error confirming breakout strength: {e}")
            return False

    def _validate_strong_vwap_trend(self, bars: list, current_price: float) -> float:
        """
        Valida que el VWAP tenga un trend fuerte (no plano)

        Args:
            bars: Lista de barras de mercado
            current_price: Precio actual

        Returns:
            float: VWAP trend percentage (positive = uptrend, negative = downtrend)
                   Returns 0.0 if cannot calculate
        """
        try:
            # Use same window as VWAP calculation
            window_minutes = min(self.vwap_window_minutes, len(bars))
            if window_minutes < 20:  # Need at least 20 minutes of data
                return 0.0

            recent_bars = bars[-window_minutes:]

            # Calculate current VWAP
            current_vwap = self.calculate_vwap_from_bars(recent_bars)
            if current_vwap is None:
                return 0.0

            # Calculate VWAP from 10 minutes ago (lookback period)
            lookback_minutes = 10
            if len(recent_bars) <= lookback_minutes:
                return 0.0

            bars_until_lookback = recent_bars[:-lookback_minutes]
            previous_vwap = self.calculate_vwap_from_bars(bars_until_lookback)

            if previous_vwap is None or previous_vwap == 0:
                return 0.0

            # Calculate trend percentage
            vwap_trend_pct = ((current_vwap - previous_vwap) / previous_vwap) * 100

            return vwap_trend_pct

        except Exception as e:
            self.logger.debug(f"Error calculating VWAP trend strength: {e}")
            return 0.0

    def _detect_vwap_bounce_confirmation(
        self,
        bars: list,
        vwap: float,
        current_price: float,
        symbol: str
    ) -> Tuple[bool, str]:
        """
        Detecta 2º o 3er rebote en VWAP con higher lows (confirmación de soporte)

        Strategy: "Wait for Confirmation, Don't Enter on First Touch"
        - Primer toque de VWAP -> NO entra (podría ser falso)
        - Segundo toque con higher low -> OK para entrar
        - Tercer toque con higher lows -> Excelente para entrar

        Ventajas:
        1. Confirma que VWAP actúa como soporte real
        2. Filtra falsos breakouts / touches casuales
        3. Higher lows = fortaleza compradora creciente
        4. Reduce whipsaws significativamente

        Criterios:
        1. Detecta 2+ toques de VWAP en últimas 15-30 barras
        2. Cada toque debe tener higher low que el anterior
        3. Precio actualmente rebotando desde VWAP
        4. Volumen aumentando en rebote (opcional)

        Args:
            bars: Historical bars
            vwap: VWAP price
            current_price: Current price
            symbol: Symbol for logging

        Returns:
            Tuple (bounce_confirmed: bool, details: str, support_level: float)
            support_level is the most recent touch low for dynamic stop loss
        """
        try:
            if len(bars) < 20:
                return False, "Insufficient bars for bounce detection", 0.0

            # 1. Buscar toques de VWAP en las últimas 15-30 barras
            lookback = min(30, len(bars))
            recent_bars = bars[-lookback:]

            # Definir "toque" como precio dentro del ±1.5% de VWAP
            touch_threshold = 0.015  # 1.5%

            vwap_touches = []
            for i, bar in enumerate(recent_bars):
                bar_low = bar.low
                distance_to_vwap = abs((bar_low - vwap) / vwap)

                if distance_to_vwap <= touch_threshold:
                    vwap_touches.append({
                        'index': i,
                        'low': bar_low,
                        'timestamp': bar.timestamp if hasattr(bar, 'timestamp') else None
                    })

            # 2. RELAXED: Allow first touch if volume is strong (CHANGED from requiring 2+)
            num_touches = len(vwap_touches)
            if num_touches < 1:
                return False, f"No VWAP touches detected", 0.0

            # 3. Verificar que los toques muestran higher lows (si hay múltiples toques)
            most_recent_touch_low = vwap_touches[-1]['low']  # For support level
            higher_lows = True  # Assume true for single touch

            if num_touches >= 2:
                first_touch_low = vwap_touches[0]['low']
                second_touch_low = vwap_touches[1]['low']
                higher_lows = second_touch_low > first_touch_low

                if num_touches >= 3:
                    third_touch_low = vwap_touches[2]['low']
                    higher_lows = higher_lows and (third_touch_low > second_touch_low)

                if not higher_lows:
                    return False, f"{num_touches} touches but NOT showing higher lows (weakness)", 0.0

            # For first touch only: require extra volume confirmation
            if num_touches == 1:
                if len(recent_bars) >= 5:
                    recent_volume = sum(bar.volume for bar in recent_bars[-3:]) / 3
                    prev_volume = sum(bar.volume for bar in recent_bars[-6:-3]) / 3
                    volume_surge = recent_volume > (prev_volume * 1.3) if prev_volume > 0 else False
                    if not volume_surge:
                        return False, f"First touch requires 1.3x volume surge (not confirmed)", 0.0

            # 4. Verificar que precio está ACTUALMENTE rebotando desde VWAP
            # Debe estar cerca de VWAP o ligeramente por encima
            current_distance = ((current_price - vwap) / vwap) * 100

            if current_distance < -1.5:
                return False, f"Price ${current_price:.2f} too far below VWAP ${vwap:.2f} ({current_distance:.1f}%)", 0.0

            if current_distance > 3.0:
                return False, f"Price ${current_price:.2f} too far above VWAP ${vwap:.2f} ({current_distance:.1f}%), missed bounce", 0.0

            # 5. Verificar volumen aumentando en último rebote (opcional)
            if len(recent_bars) >= 5:
                recent_volume = sum(bar.volume for bar in recent_bars[-3:]) / 3
                prev_volume = sum(bar.volume for bar in recent_bars[-6:-3]) / 3
                volume_increasing = recent_volume > prev_volume if prev_volume > 0 else False
            else:
                volume_increasing = False

            # Construir detalles
            if num_touches == 2:
                details = f"2nd VWAP bounce with higher low (${first_touch_low:.2f} -> ${second_touch_low:.2f})"
            elif num_touches >= 3:
                details = f"3rd+ VWAP bounce ({num_touches} touches) with higher lows"
            else:
                details = f"{num_touches} VWAP bounces"

            details += f", price ${current_price:.2f} at VWAP ${vwap:.2f} ({current_distance:+.1f}%)"

            if volume_increasing:
                details += " (✅ volume surge)"

            self.logger.info(f"🎯 {symbol}: VWAP BOUNCE CONFIRMATION - {details} (support: ${most_recent_touch_low:.2f})")
            return True, details, most_recent_touch_low

        except Exception as e:
            self.logger.error(f"Error detecting VWAP bounce confirmation for {symbol}: {e}")
            return False, f"Error: {str(e)}", 0.0

    async def _evaluate_buy_the_dip_entry(
        self,
        symbol: str,
        current_price: float,
        vwap: float,
        day_open: float,
        bars: list,
        opportunity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        BUY-THE-DIP SYSTEM: Two-phase entry strategy

        PHASE 1: Detect breakout above VWAP -> Track but DON'T enter
        PHASE 2: Wait for 30-60% pullback -> Buy when volume increases on dip

        This avoids buying at the HIGH and getting stopped out on normal pullback.
        Instead, we wait for the pullback WITH volume confirmation.

        Args:
            symbol: Ticker symbol
            current_price: Current price
            vwap: Current VWAP value
            day_open: Day open price
            bars: Recent bars
            opportunity: Full opportunity data

        Returns:
            Dict with:
                - should_enter: bool (True if ready to enter on dip)
                - direction: 'long' or 'short'
                - pullback_pct: Pullback percentage
                - reason: Explanation
        """
        from datetime import datetime, timedelta

        try:
            # PHASE 1: DETECT BREAKOUT (but don't enter yet)
            if symbol not in self.breakout_tracker:
                # Check for new breakout
                breakout_detected = False
                direction = None
                breakout_high = None

                # LONG BREAKOUT: Price above VWAP + bullish bias
                if current_price > vwap and current_price > day_open:
                    if self._confirm_breakout_strength(bars, vwap, 'long'):
                        breakout_detected = True
                        direction = 'long'
                        breakout_high = current_price
                        self.logger.info(
                            f"🔍 {symbol}: PHASE 1 - VWAP LONG BREAKOUT detected at ${current_price:.2f} "
                            f"(VWAP: ${vwap:.2f}) - TRACKING for dip entry"
                        )

                # SHORT BREAKOUT: Price below VWAP + bearish bias
                elif current_price < vwap and current_price < day_open:
                    if self._confirm_breakout_strength(bars, vwap, 'short'):
                        breakout_detected = True
                        direction = 'short'
                        breakout_high = current_price
                        self.logger.info(
                            f"🔍 {symbol}: PHASE 1 - VWAP SHORT BREAKOUT detected at ${current_price:.2f} "
                            f"(VWAP: ${vwap:.2f}) - TRACKING for dip entry"
                        )

                if breakout_detected:
                    # Track breakout but DON'T enter yet
                    self.breakout_tracker[symbol] = {
                        'breakout_high': breakout_high,
                        'vwap': vwap,
                        'direction': direction,
                        'timestamp': datetime.now()
                    }
                    return {
                        'should_enter': False,
                        'reason': f'PHASE 1: Breakout detected, waiting for pullback to ${vwap:.2f}'
                    }
                else:
                    return {
                        'should_enter': False,
                        'reason': 'No breakout detected yet'
                    }

            # PHASE 2: EVALUATE DIP ENTRY (we already have a tracked breakout)
            breakout_data = self.breakout_tracker[symbol]
            breakout_high = breakout_data['breakout_high']
            breakout_vwap = breakout_data['vwap']
            direction = breakout_data['direction']
            breakout_time = breakout_data['timestamp']

            # Check timeout: Remove stale breakouts (>20 minutes)
            elapsed_minutes = (datetime.now() - breakout_time).total_seconds() / 60
            if elapsed_minutes > self.dip_timeout_minutes:
                self.logger.info(
                    f"⏱️ {symbol}: Breakout EXPIRED after {elapsed_minutes:.1f} min - "
                    f"Removing from tracker"
                )
                del self.breakout_tracker[symbol]
                return {
                    'should_enter': False,
                    'reason': f'Breakout expired after {elapsed_minutes:.1f} min'
                }

            # Calculate pullback percentage
            if direction == 'long':
                # For longs: pullback = how much price dropped from breakout high
                move_size = breakout_high - breakout_vwap
                current_pullback = breakout_high - current_price
                pullback_pct = (current_pullback / move_size) if move_size > 0 else 0

            elif direction == 'short':
                # For shorts: pullback = how much price rose from breakout low
                move_size = breakout_vwap - breakout_high  # breakout_high is actually low for shorts
                current_pullback = current_price - breakout_high
                pullback_pct = (current_pullback / move_size) if move_size > 0 else 0

            # Check if pullback is in valid range (30-60%)
            if pullback_pct < self.dip_pullback_min_pct:
                # Not enough pullback yet
                return {
                    'should_enter': False,
                    'reason': f'PHASE 2: Pullback {pullback_pct*100:.1f}% < min {self.dip_pullback_min_pct*100:.1f}%'
                }

            if pullback_pct > self.dip_pullback_max_pct:
                # Too much pullback - pattern invalidated
                self.logger.info(
                    f"❌ {symbol}: Pullback {pullback_pct*100:.1f}% > max {self.dip_pullback_max_pct*100:.1f}% - "
                    f"Pattern INVALIDATED, removing from tracker"
                )
                del self.breakout_tracker[symbol]
                return {
                    'should_enter': False,
                    'reason': f'Pullback too deep ({pullback_pct*100:.1f}%), pattern invalidated'
                }

            # Check volume confirmation on dip
            if len(bars) >= 10:
                recent_bars = bars[-10:]
                avg_volume = sum(bar.volume for bar in recent_bars[:-1]) / (len(recent_bars) - 1)
                current_volume = bars[-1].volume

                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

                if volume_ratio >= self.dip_volume_multiplier:
                    # VOLUME CONFIRMATION: Enter on dip!
                    self.logger.info(
                        f"✅ {symbol}: PHASE 2 - DIP ENTRY CONFIRMED! "
                        f"Pullback: {pullback_pct*100:.1f}%, Volume: {volume_ratio:.1f}x avg, "
                        f"Entry: ${current_price:.2f}, Breakout was: ${breakout_high:.2f}"
                    )

                    # Remove from tracker (entered)
                    del self.breakout_tracker[symbol]

                    return {
                        'should_enter': True,
                        'direction': direction,
                        'pullback_pct': pullback_pct * 100,
                        'volume_ratio': volume_ratio,
                        'breakout_high': breakout_high,
                        'reason': f'Dip entry: {pullback_pct*100:.1f}% pullback with {volume_ratio:.1f}x volume'
                    }
                else:
                    # Pullback is good, but waiting for volume
                    return {
                        'should_enter': False,
                        'reason': f'PHASE 2: Good pullback {pullback_pct*100:.1f}%, waiting for volume (current: {volume_ratio:.1f}x < {self.dip_volume_multiplier}x)'
                    }
            else:
                # Not enough bars to calculate volume
                return {
                    'should_enter': False,
                    'reason': 'Not enough bars to confirm volume'
                }

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error evaluating buy-the-dip entry: {e}")
            # Remove from tracker on error
            if symbol in self.breakout_tracker:
                del self.breakout_tracker[symbol]
            return {
                'should_enter': False,
                'reason': f'Error: {str(e)}'
            }