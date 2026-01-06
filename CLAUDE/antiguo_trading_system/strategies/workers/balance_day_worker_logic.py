"""
Balance Day Worker Logic
Worker específico para días BALANCE_DAY (sin trend claro)
Estrategia de range trading para smallcaps intraday
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager
from core.trade_arbiter import TradingHorizon


class BalanceDayWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Balance Day Trading

    FUNCIONA SOLO EN DÍAS BALANCE_DAY (según ODS):
    - Rango estrecho (<0.5%)
    - Sin impulso direccional claro
    - Volumen bajo/moderado

    ESTRATEGIAS DE RANGE TRADING:
    1. Mean Reversion: Compra lows, vende highs del rango
    2. Range Breakout: Espera breakout confirmado del rango
    3. Scalping: Entradas rápidas en extremos del rango

    CRITERIOS DE ENTRADA:
    - Solo en BALANCE_DAY confirmado por ODS
    - Precio en extremos del rango diario (80% o 120% del VWAP)
    - Volumen seco en el extremo (acumulación)
    - Momentum técnico en reversión

    CRITERIOS DE SALIDA:
    - Take profit: 3-5% (rangos pequeños)
    - Stop loss: 2% (amplio para volatilidad)
    - Time-based: 30-60 minutos máximo
    - Target alcanzado: Mitad del rango opuesto
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="balance_day",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Balance Day
        self.min_price = getattr(config, 'balance_min_price', 0.5)  # Smallcaps
        self.max_price = getattr(config, 'balance_max_price', 25.0)
        self.min_volume_ratio = getattr(config, 'balance_min_volume_ratio', 0.8)  # Más permisivo
        self.range_extreme_threshold = getattr(config, 'balance_range_extreme_threshold', 0.8)  # 80% del rango
        self.max_range_pct = getattr(config, 'balance_max_range_pct', 1.0)  # Máximo 1% rango para "balance"

        # Initialize stop manager con parámetros conservadores para range trading
        from .worker_stop_manager import create_worker_stop_manager
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'BALANCE_DAY_STRATEGY')
        else:
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=2.0,           # 2% stop (conservador para range)
                take_profit_pct=4.0,         # 4% profit (rangos pequeños)
                quick_target_pct=0.0,        # No quick target
                trailing_activation=3.0,     # Trailing a 3%
                trailing_distance=1.5,       # 1.5% trailing
                max_position_hours=1.0       # Max 1 hora (scalping)
            ))

        self.logger.info(
            f"🎯 Balance Day Worker configured: "
            f"price=${self.min_price}-${self.max_price}, vol>={self.min_volume_ratio}x, "
            f"range_extreme>={self.range_extreme_threshold}, max_range<={self.max_range_pct}% | "
            f"Exits: TP=4%, SL=2%, Trail=3%/1.5%, Max=1h"
        )

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Balance Day (0-100%)

        PATTERN STAGES:
        - 30%: Balance day confirmado por ODS
        - 60%: Precio en extremo del rango
        - 90%: Momentum de reversión detectado
        - 100%: Setup completo listo para entrada
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            # Get bars
            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 20:
                return 0.0

            current_price = opportunity.get('current_price', 0)

            # Stage 1: ODS Balance Day confirmation (30%)
            from core.ods_classifier import ODSDayType
            ods = await self.get_ods_for_symbol(symbol, bars)

            if ods.day_type == ODSDayType.BALANCE_DAY:
                completion += 30.0
                self.logger.debug(f"📊 {symbol}: Balance day confirmed by ODS")
            else:
                self.logger.debug(f"📊 {symbol}: Not a balance day (ODS={ods.day_type.value})")
                return 0.0  # Solo funciona en balance days

            # Stage 2: Price at range extreme (60%)
            range_position = self._calculate_range_position(bars, current_price)
            if range_position >= self.range_extreme_threshold:
                completion += 30.0
                self.logger.debug(f"📊 {symbol}: Price at range extreme ({range_position:.1f})")
            else:
                completion += 10.0  # Partial credit
                self.logger.debug(f"📊 {symbol}: Price not at extreme ({range_position:.1f})")

            # Stage 3: Reversal momentum (90%)
            if self._detect_reversal_momentum(bars):
                completion += 30.0
                self.logger.debug(f"📊 {symbol}: Reversal momentum detected")
            else:
                completion += 20.0  # Partial credit
                self.logger.debug(f"📊 {symbol}: No clear reversal momentum")

            # Stage 4: Volume confirmation (100%)
            volume_confirmed = self._check_volume_confirmation(bars, opportunity)
            if volume_confirmed:
                completion = 100.0
                self.logger.info(f"✅ {symbol}: Balance day setup complete (100%)")

            self.logger.info(f"📊 {symbol}: Balance pattern completion = {completion:.0f}%")
            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating balance pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Balance Day

        REQUIERE: ODS = BALANCE_DAY
        ESTRATEGIA: Mean reversion en extremos del rango
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            self.logger.info(f"🔍 {symbol}: Starting BALANCE DAY evaluation")

            # CRITICAL: Check for duplicate positions
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                self.logger.warning(f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()}")
                return False

            bars = self.get_bars_from_opportunity(opportunity)
            if not bars or len(bars) < 20:
                self.logger.info(f"⚪ {symbol}: Insufficient bars ({len(bars) if bars else 0}/20)")
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

            # CRITICAL: MUST BE BALANCE DAY
            from core.ods_classifier import ODSDayType
            ods = await self.get_ods_for_symbol(symbol, bars)

            if ods.day_type != ODSDayType.BALANCE_DAY:
                self.logger.info(f"⚪ {symbol}: NOT BALANCE DAY (ODS={ods.day_type.value}) - skipping")
                return False

            self.logger.info(f"✅ {symbol}: BALANCE DAY confirmed (range={ods.range_pct:.2f}%, vol={ods.volume_ratio:.1f}x)")

            # VWAP validation (required for range trading)
            vwap_valid, vwap_reason = self.validate_vwap_strength(bars, current_price, opportunity=opportunity)
            if not vwap_valid:
                self.logger.info(f"⚪ {symbol}: VWAP validation failed - {vwap_reason}")
                return False

            # Detect range extremes and direction
            range_position, direction = self._analyze_range_extreme(bars, current_price)

            if range_position < self.range_extreme_threshold:
                self.logger.info(f"⚪ {symbol}: Price not at range extreme ({range_position:.1f} < {self.range_extreme_threshold})")
                return False

            # Check for reversal setup
            reversal_setup = self._detect_reversal_setup(bars, direction)

            if not reversal_setup:
                self.logger.info(f"⚪ {symbol}: No reversal setup detected")
                return False

            # Volume confirmation
            volume_ok = self._check_volume_confirmation(bars, opportunity)
            if not volume_ok:
                self.logger.info(f"⚪ {symbol}: Volume confirmation failed")
                return False

            # Time validation - Use centralized hour validation from BaseWorkerLogic
            is_valid_hours, current_time = self.is_within_entry_hours(symbol)
            if not is_valid_hours:
                self.logger.info(f"⚪ {symbol}: Outside trading hours ({current_time:.2f})")
                return False

            # Calculate support/resistance for stop loss
            support_level = self._calculate_range_support(bars, direction)

            # Store for dynamic stop loss
            opportunity['support_level'] = support_level

            # ENTRY APPROVED
            self.logger.info(
                f"✅ {symbol}: BALANCE DAY ENTRY APPROVED - "
                f"{direction.upper()} at range extreme ({range_position:.1f}), "
                f"support=${support_level:.2f}, vol={volume_ratio:.1f}x"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating balance day for {symbol}: {e}")
            return False

    def _calculate_range_position(self, bars: list, current_price: float) -> float:
        """Calculate where current price is within the day's range (0-1)"""
        try:
            if len(bars) < 10:
                return 0.5

            # Calculate day's range from recent bars
            recent_high = max(bar.high for bar in bars[-20:])
            recent_low = min(bar.low for bar in bars[-20:])
            range_size = recent_high - recent_low

            if range_size == 0:
                return 0.5

            # Position within range (0 = at low, 1 = at high)
            position = (current_price - recent_low) / range_size
            return max(0.0, min(1.0, position))

        except Exception as e:
            self.logger.debug(f"Error calculating range position: {e}")
            return 0.5

    def _analyze_range_extreme(self, bars: list, current_price: float) -> Tuple[float, str]:
        """Analyze if price is at range extreme and determine direction"""
        range_position = self._calculate_range_position(bars, current_price)

        if range_position <= (1 - self.range_extreme_threshold):
            return range_position, "LONG"  # Near low = buy
        elif range_position >= self.range_extreme_threshold:
            return range_position, "SHORT"  # Near high = sell
        else:
            return range_position, "NEUTRAL"

    def _detect_reversal_momentum(self, bars: list) -> bool:
        """Detect if there's momentum suggesting reversal"""
        try:
            if len(bars) < 5:
                return False

            # Check last 3 bars for reversal pattern
            recent_bars = bars[-3:]

            # For potential reversal: bars should be getting smaller (exhaustion)
            ranges = [bar.high - bar.low for bar in recent_bars]
            volumes = [bar.volume for bar in recent_bars]

            # Check if ranges are decreasing (exhaustion)
            range_decreasing = ranges[0] > ranges[1] > ranges[2]

            # Check if volume is decreasing (distribution)
            volume_decreasing = volumes[0] > volumes[1] > volumes[2]

            return range_decreasing and volume_decreasing

        except Exception as e:
            self.logger.debug(f"Error detecting reversal momentum: {e}")
            return False

    def _detect_reversal_setup(self, bars: list, direction: str) -> bool:
        """Detect specific reversal setup based on direction"""
        try:
            if len(bars) < 10:
                return False

            # Get recent bars for analysis
            recent_bars = bars[-5:]

            if direction == "LONG":
                # For long: Look for lower highs and lower lows (downtrend exhaustion)
                highs = [bar.high for bar in recent_bars]
                lows = [bar.low for bar in recent_bars]

                # Check for lower highs and lower lows
                lower_highs = all(highs[i] >= highs[i+1] for i in range(len(highs)-1))
                lower_lows = all(lows[i] >= lows[i+1] for i in range(len(lows)-1))

                return lower_highs and lower_lows

            elif direction == "SHORT":
                # For short: Look for higher lows and higher highs (uptrend exhaustion)
                highs = [bar.high for bar in recent_bars]
                lows = [bar.low for bar in recent_bars]

                # Check for higher highs and higher lows
                higher_highs = all(highs[i] <= highs[i+1] for i in range(len(highs)-1))
                higher_lows = all(lows[i] <= lows[i+1] for i in range(len(lows)-1))

                return higher_highs and higher_lows

            return False

        except Exception as e:
            self.logger.debug(f"Error detecting reversal setup: {e}")
            return False

    def _check_volume_confirmation(self, bars: list, opportunity: Dict[str, Any]) -> bool:
        """Check if volume confirms the reversal setup"""
        try:
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # Basic volume check
            if volume_ratio < self.min_volume_ratio:
                return False

            # Check volume pattern in recent bars
            if len(bars) >= 5:
                recent_volumes = [bar.volume for bar in bars[-5:]]
                avg_recent_volume = sum(recent_volumes) / len(recent_volumes)

                # Compare with earlier volume
                if len(bars) >= 10:
                    earlier_volumes = [bar.volume for bar in bars[-10:-5]]
                    avg_earlier_volume = sum(earlier_volumes) / len(earlier_volumes)

                    # Volume should be drying up (lower than earlier)
                    return avg_recent_volume <= avg_earlier_volume * 1.2

            return True

        except Exception as e:
            self.logger.debug(f"Error checking volume confirmation: {e}")
            return False

    def _calculate_range_support(self, bars: list, direction: str) -> float:
        """Calculate support level for stop loss based on range"""
        try:
            if len(bars) < 10:
                return 0.0

            recent_high = max(bar.high for bar in bars[-20:])
            recent_low = min(bar.low for bar in bars[-20:])

            if direction == "LONG":
                # For long trades, support is recent low
                return recent_low
            elif direction == "SHORT":
                # For short trades, support is recent high
                return recent_high
            else:
                return (recent_high + recent_low) / 2

        except Exception as e:
            self.logger.debug(f"Error calculating range support: {e}")
            return 0.0

    async def should_exit(self, symbol: str, position: Dict[str, Any], current_price: float) -> Tuple[bool, str]:
        """Exit logic for balance day trading"""
        try:
            entry_price = position.get('entry_price', 0)

            # Use stop manager for standard exits
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=None,
                position_metadata={
                    'EOD_safe': position.get('EOD_safe', True),  # Balance trading is safer
                    'trading_horizon': position.get('trading_horizon', 'unknown'),
                    'expected_hold_hours': position.get('expected_hold_hours', 1.0)
                }
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating balance exit for {symbol}: {e}")
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register with unified position manager"""
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager
            self.stop_manager.register_position(symbol, datetime.now())

            # Register with unified position manager
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager:
                current_price = opportunity.get('current_price', 0)
                position_value = opportunity.get('position_value', 100.0)  # Smaller positions for scalping

                unified_manager.register_position(
                    symbol=symbol,
                    strategy_type='balance_day',
                    position_data={
                        'strategy': 'balance_day',
                        'entry_price': current_price,
                        'position_value': position_value,
                        'entry_time': datetime.now().isoformat()
                    }
                )
                self.logger.info(f"💼 Registered {symbol} with UnifiedPositionManager (BALANCE DAY)")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister from managers"""
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
            unified_manager.unregister_position(symbol, 'balance_day', pnl_pct, reason)
            self.logger.info(f"💼 Unregistered {symbol} from UnifiedPositionManager (BALANCE DAY)")

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hours"""
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
                spain_tz = pytz.timezone('Europe/Madrid')
                dt = spain_tz.localize(dt)
            else:
                dt = dt.astimezone(eastern)

            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.debug(f"Error converting timestamp to time: {e}")
            return 12.0