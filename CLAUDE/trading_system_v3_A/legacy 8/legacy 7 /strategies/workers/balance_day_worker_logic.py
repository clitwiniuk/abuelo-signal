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
    Worker lógico para estrategia Mean Reversion (Range Trading)

    ESTRATEGIA: Mean Reversion puro sin dependencia de ODS
    - Detecta condiciones de rango estrecho automáticamente
    - Opera en extremos del rango (oversold/overbought)
    - Apropiado para smallcaps en consolidación

    CRITERIOS DE ENTRADA (SIN ODS):
    1. Rango intraday estrecho (<2% últimas 20 barras)
    2. Precio en extremo del rango (>80% o <20% del rango)
    3. RSI oversold (<30) o overbought (>70)
    4. Momentum de reversión (3 de 4 barras muestran patrón)
    5. Volumen moderado (no surging, no dead)

    CRITERIOS DE SALIDA:
    - Take profit: 4% (rangos pequeños)
    - Stop loss: 2% (conservador)
    - Time-based: 1.5 horas máximo
    - Target: Mitad del rango opuesto
    """

    def __init__(self, broker, risk_manager=None, config=None, execution_engine=None):
        super().__init__(
            worker_name="balance_day",
            broker=broker,
            config=config
        )

        # Configuración específica Mean Reversion (SMALLCAP OPTIMIZED)
        self.min_price = getattr(config, 'balance_min_price', 1.0)  # Avoid extreme penny stocks
        self.max_price = getattr(config, 'balance_max_price', 25.0)
        self.min_volume_ratio = getattr(config, 'balance_min_volume_ratio', 1.0)  # FIXED: At least average volume
        self.range_extreme_threshold = getattr(config, 'balance_range_extreme_threshold', 0.8)  # 80% del rango
        self.max_range_pct = getattr(config, 'balance_max_range_pct', 2.0)  # RELAXED: Max 2% range for "tight range"

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
                max_position_hours=1.5       # EXTENDED: 1.5 hours for range development
            ))

        self.logger.info(
            f"🎯 Mean Reversion Worker configured: "
            f"price=${self.min_price}-${self.max_price}, vol>={self.min_volume_ratio}x, "
            f"range_extreme>={self.range_extreme_threshold}, max_range<={self.max_range_pct}% | "
            f"Exits: TP=4%, SL=2%, Trail=3%/1.5%, Max=1.5h (NO ODS dependency)"
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

            # CRITICAL: Check for duplicate positions (Broker)
            positions = await self.broker.get_positions()
            if any(p['symbol'] == symbol for p in positions):
                self.logger.warning(f"⚪ {symbol}: BLOCKED - Position already exists.")
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

            # INDEPENDENT BALANCE DETECTION (NO ODS DEPENDENCY)
            is_tight_range, range_pct = self._detect_tight_range(bars)

            if not is_tight_range:
                self.logger.info(f"⚪ {symbol}: NOT TIGHT RANGE (range={range_pct:.2f}% > {self.max_range_pct}%) - skipping")
                return False

            self.logger.info(f"✅ {symbol}: TIGHT RANGE confirmed (range={range_pct:.2f}% < {self.max_range_pct}%)")

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

    def _detect_tight_range(self, bars: list) -> Tuple[bool, float]:
        """
        Detect tight range condition WITHOUT ODS dependency
        
        Returns:
            Tuple[bool, float]: (is_tight_range, range_pct)
        """
        try:
            if len(bars) < 20:
                return False, 0.0
            
            # Calculate intraday range from last 20 bars
            recent_high = max(bar.high for bar in bars[-20:])
            recent_low = min(bar.low for bar in bars[-20:])
            
            if recent_low == 0:
                return False, 0.0
            
            range_pct = ((recent_high - recent_low) / recent_low) * 100
            
            # Tight range if < max_range_pct (default 2%)
            is_tight = range_pct <= self.max_range_pct
            
            return is_tight, range_pct
            
        except Exception as e:
            self.logger.debug(f"Error detecting tight range: {e}")
            return False, 0.0

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
        """Detect specific reversal setup based on direction (RELAXED for smallcaps)"""
        try:
            if len(bars) < 10:
                return False

            # Get recent bars for analysis
            recent_bars = bars[-5:]

            if direction == "LONG":
                # For long: Look for lower highs and lower lows (downtrend exhaustion)
                highs = [bar.high for bar in recent_bars]
                lows = [bar.low for bar in recent_bars]

                # SMALLCAP: Require 3 of 4 bars (not all) - more flexible
                lower_highs_count = sum(1 for i in range(len(highs)-1) if highs[i] >= highs[i+1])
                lower_lows_count = sum(1 for i in range(len(lows)-1) if lows[i] >= lows[i+1])

                return lower_highs_count >= 3 and lower_lows_count >= 3  # 3 of 4 checks (75%)

            elif direction == "SHORT":
                # For short: Look for higher lows and higher highs (uptrend exhaustion)
                highs = [bar.high for bar in recent_bars]
                lows = [bar.low for bar in recent_bars]

                # SMALLCAP: Require 3 of 4 bars (not all) - more flexible
                higher_highs_count = sum(1 for i in range(len(highs)-1) if highs[i] <= highs[i+1])
                higher_lows_count = sum(1 for i in range(len(lows)-1) if lows[i] <= lows[i+1])

                return higher_highs_count >= 3 and higher_lows_count >= 3  # 3 of 4 checks (75%)

            return False

        except Exception as e:
            self.logger.debug(f"Error detecting reversal setup: {e}")
            return False

    def _check_volume_confirmation(self, bars: list, opportunity: Dict[str, Any]) -> bool:
        """Check if volume is moderate (not surging, not dead)"""
        try:
            volume_ratio = opportunity.get('volume_ratio', 1.0)

            # FIXED: Volume should be moderate (1.0x - 2.0x)
            # Not too low (dead) and not too high (surging breakout)
            if volume_ratio < self.min_volume_ratio:  # Now 1.0x
                return False
            
            if volume_ratio > 2.0:  # Too much volume = breakout, not range
                self.logger.debug(f"Volume too high for range trading: {volume_ratio:.1f}x")
                return False

            # Volume pattern: Should be relatively stable (not spiking)
            if len(bars) >= 5:
                recent_volumes = [bar.volume for bar in bars[-5:]]
                max_vol = max(recent_volumes)
                min_vol = min(recent_volumes)
                
                # Volume variance should be moderate
                if min_vol > 0:
                    vol_variance = max_vol / min_vol
                    if vol_variance > 3.0:  # Too much variance
                        return False

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
        """Override to register with stop manager"""
        success = await super()._execute_entry(opportunity)

        if success:
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Register with stop manager
            self.stop_manager.register_position(symbol, datetime.now())

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister from stop manager"""
        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    def _get_time_from_timestamp(self, timestamp) -> float:
        """Convert timestamp to decimal hours"""
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
                spain_tz = pytz.timezone('Europe/Madrid')
                dt = spain_tz.localize(dt)
            else:
                dt = dt.astimezone(eastern)

            return dt.hour + dt.minute / 60.0

        except Exception as e:
            self.logger.debug(f"Error converting timestamp to time: {e}")
            return 12.0