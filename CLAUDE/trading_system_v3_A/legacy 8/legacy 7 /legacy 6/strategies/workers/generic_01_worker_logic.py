"""
GENERIC_01 Worker Logic
Worker específico para estrategia GENERIC_01 (Low Volume Accumulation)

Sistema más rentable del análisis con 41.04% edge
Detecta acumulación institucional en bajo volumen
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager, WorkerStopManager, WorkerStopConfig
from core.trade_arbiter import TradingHorizon


class Generic01WorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia GENERIC_01

    Edge: 41.04% (Sistema más rentable del análisis)
    Enfoque: Acumulación institucional en bajo volumen

    Mecanismo Objetivo: volume_effects_low_volume
    - Precio subiendo (daily_return_pct > 0)
    - Volumen bajo (< 2.0x promedio)
    - Indica acumulación discreta sin retail FOMO

    Criterios de entrada:
    - daily_return_pct > 0 (precio cerrando por encima del open)
    - Volumen NO alto (rechazar volume_ratio > 2.0)
    - Precio en rango operativo ($2-$50)
    - Sin gaps extremos (evitar parabolic moves)

    Criterios de salida:
    - Take profit: 32.83% (basado en edge validado)
    - Stop loss: 16.42% (risk/reward 2:1)
    - Time-based: 6 horas máximo (holding time óptimo)
    """

    def __init__(self, worker_name, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name=worker_name,
            execution_engine=execution_engine,
            risk_manager=risk_manager,
            config=config  # Pass config to BaseWorkerLogic
        )

        # Configuración específica GENERIC_01
        self.max_volume_ratio = 2.0   # Rechazar alto volumen (queremos bajo volumen)
        self.min_price = 2.0          # Precio mínimo operativo
        self.max_price = 50.0         # Precio máximo operativo
        self.max_gap = 8.0            # Gap máximo (evitar parabolic)

        # Validación de momentum positivo
        self.min_daily_return = 0.0   # daily_return_pct debe ser > 0

        # Entry confirmation (evitar false signals)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 1    # Una confirmación suficiente (sistema muy específico)
        self.confirmation_window = 60 # 1 minuto para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'GENERIC_01_STRATEGY')
        else:
            # Fallback: create with default parameters based on validated edge
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=16.42,      # Validado por análisis
                take_profit_pct=32.83,    # Validado por análisis
                quick_target_pct=None,    # No quick target
                trailing_activation=25.0, # Activar trailing al 75% del TP
                trailing_distance=10.0,   # Trailing stop conservador
                max_position_hours=6.0    # Holding time óptimo validado
            ))

        # Initialize trend filters (anti-reversal)
        if config:
            from .trend_filters import create_trend_filters_from_config
            self.trend_filters = create_trend_filters_from_config(config, 'GENERIC_01_STRATEGY', logger=self.logger)
        else:
            from .trend_filters import TrendFilters
            self.trend_filters = TrendFilters(logger=self.logger)

        self.logger.info(
            f"🎯 GENERIC_01 Worker configured: "
            f"vol<{self.max_volume_ratio}x, gap<{self.max_gap}%, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Edge: 41.04% | TP: 32.83% | SL: 16.42%")
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón GENERIC_01 (0-100%)

        PATTERN: Low Volume Accumulation

        Pattern Stages:
        1. [25%] Price in range & positive momentum
        2. [50%] Low volume confirmed (NOT high volume)
        3. [75%] Trading hours & quality validated
        4. [100%] Pattern fully confirmed

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            current_price = opportunity.get('current_price', 0)
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            volume_ratio = opportunity.get('volume_ratio', 0)

            # CRITICAL FIX: Calculate daily_return_pct from INTRADAY bars (first bar of day = open)
            # The 'open' field in opportunity is unreliable - we need TODAY's open from bars
            daily_return_pct = 0

            bars = self.get_bars_from_opportunity(opportunity)
            if bars and len(bars) > 0:
                # First bar of the day contains today's opening price
                first_bar_open = bars[0].open
                if first_bar_open and first_bar_open > 0:
                    daily_return_pct = ((current_price - first_bar_open) / first_bar_open) * 100
                    self.logger.debug(
                        f"📊 {symbol}: Daily return calculated - Open: ${first_bar_open:.2f}, "
                        f"Current: ${current_price:.2f}, Return: {daily_return_pct:+.2f}%"
                    )
                else:
                    self.logger.debug(f"⚠️ {symbol}: First bar has invalid open price: {first_bar_open}")
            else:
                self.logger.debug(f"⚠️ {symbol}: No intraday bars available to calculate daily return")

            quality_score = opportunity.get('quality_score', 0)

            # Stage 1: Price range & positive momentum (25%)
            if self.min_price <= current_price <= self.max_price:
                completion += 12.5
                self.logger.debug(f"📊 {symbol}: Price range OK - ${current_price:.2f}")
            else:
                self.logger.debug(f"📊 {symbol}: Price out of range ${current_price:.2f}")
                return 0.0

            # CRITICAL: Positive daily return (momentum)
            if daily_return_pct > self.min_daily_return:
                completion += 12.5
                self.logger.info(f"📊 {symbol}: Positive momentum (+{daily_return_pct:.2f}%)")
            else:
                self.logger.info(f"⚪ {symbol}: Negative/flat momentum ({daily_return_pct:.2f}%)")
                return 0.0

            # Stage 2: LOW volume confirmed (50%)
            # CRITICAL: We want LOW volume, NOT high volume
            if volume_ratio <= self.max_volume_ratio:
                completion += 25.0
                self.logger.info(
                    f"📊 {symbol}: LOW VOLUME confirmed ({volume_ratio:.1f}x <= {self.max_volume_ratio}x)"
                )
            else:
                self.logger.info(
                    f"⚪ {symbol}: Volume too high ({volume_ratio:.1f}x > {self.max_volume_ratio}x)"
                )
                return 0.0

            # Stage 3: Trading hours & quality (75%)
            # Use centralized hour validation from BaseWorkerLogic
            is_valid_hours, current_hour = self.is_within_entry_hours(symbol)

            if is_valid_hours:
                completion += 12.5
                self.logger.debug(f"📊 {symbol}: Trading hours OK ({current_hour:.2f})")
            else:
                # STRICT rejection for out-of-hours (fixes afterhours bug)
                self.logger.debug(
                    f"📊 {symbol}: Outside trading hours ({current_hour:.2f})"
                )
                return 0.0  # Strict rejection - no afterhours entries

            if quality_score >= 40.0:  # Lower threshold for low-volume plays
                completion += 12.5
                self.logger.debug(f"📊 {symbol}: Quality validated")
            else:
                return completion

            # Stage 4: Final confirmation (100%)
            # Check gap is not parabolic
            if gap_pct <= self.max_gap:
                completion += 25.0
                self.logger.info(
                    f"✅ {symbol}: GENERIC_01 pattern COMPLETE (100%) - "
                    f"Low vol accumulation, gap={gap_pct:.1f}%, ret=+{daily_return_pct:.2f}%"
                )
            else:
                self.logger.debug(
                    f"📊 {symbol}: Gap too large ({gap_pct:.1f}% > {self.max_gap}%)"
                )
                return completion

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios GENERIC_01

        STRATEGY: Enter when pattern reaches 75-100% completion
        - 75%: Basic pattern confirmed
        - 100%: Full pattern validated

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            self.logger.info(f"🔍 {symbol}: Starting GENERIC_01 evaluation")

            # ============================================================
            # VALIDATION 0: Check for duplicate positions (UnifiedPositionManager)
            # ============================================================
            from core.service_locator import get_unified_position_manager
            unified_manager = await get_unified_position_manager()

            if unified_manager and unified_manager.is_symbol_blocked(symbol):
                position = unified_manager.get_position(symbol)
                strategy_type = position['strategy_type'] if position else 'unknown'
                existing_worker = position.get('strategy', 'unknown') if position else 'unknown'
                self.logger.warning(
                    f"⚪ {symbol}: BLOCKED - already held in {strategy_type.upper()} trading (strategy: {existing_worker})"
                )
                return False

            # Legacy check: also check own active_positions (belt and suspenders)
            if symbol in self.active_positions:
                self.logger.debug(f"⏭️ {symbol}: Already have position (legacy check)")
                return False

            # Check ExecutionEngine for global position
            if hasattr(self.execution_engine, 'worker_positions'):
                if symbol in self.execution_engine.worker_positions:
                    self.logger.debug(f"⏭️ {symbol}: Position exists in ExecutionEngine")
                    return False

            # Check failed entries
            if symbol in self.failed_entries:
                attempts = self.failed_entries[symbol].get('attempts', 0)
                if attempts >= self.max_entry_attempts:
                    self.logger.debug(
                        f"🚫 {symbol}: Blacklisted ({attempts} failed attempts)"
                    )
                    return False

            # ============================================================
            # VALIDATION 1: Calculate pattern completion
            # ============================================================
            completion = await self.calculate_pattern_completion(opportunity)

            if completion < 75.0:
                self.logger.info(
                    f"⚪ {symbol}: Pattern incomplete ({completion:.0f}% < 75%)"
                )
                return False

            # ============================================================
            # VALIDATION 2: Entry confirmation tracking
            # ============================================================
            now = datetime.now()

            if symbol not in self.pending_entries:
                # First time seeing this opportunity
                self.pending_entries[symbol] = {
                    'first_seen': now,
                    'count': 1,
                    'completion': completion
                }
                self.logger.info(
                    f"👁️ {symbol}: First confirmation ({completion:.0f}%) - "
                    f"need {self.min_confirmations}"
                )
                return False
            else:
                # Check if within confirmation window
                entry_data = self.pending_entries[symbol]
                elapsed = (now - entry_data['first_seen']).total_seconds()

                if elapsed > self.confirmation_window:
                    # Window expired, reset
                    self.pending_entries[symbol] = {
                        'first_seen': now,
                        'count': 1,
                        'completion': completion
                    }
                    self.logger.info(
                        f"⏰ {symbol}: Confirmation window expired, resetting"
                    )
                    return False

                # Increment confirmation count
                entry_data['count'] += 1
                entry_data['completion'] = completion

                if entry_data['count'] < self.min_confirmations:
                    self.logger.info(
                        f"👁️ {symbol}: Confirmation {entry_data['count']}/{self.min_confirmations} "
                        f"({completion:.0f}%)"
                    )
                    return False

            # ============================================================
            # VALIDATION 2.5: FILTROS ANTI-REVERSAL (Evitar entradas en picos)
            # ============================================================
            # CRITICAL: Rechazar si MACD/RSI están en zona de reversión
            # Ejemplo: SAGT @ $2.50 con RSI 74.8 -> pérdida -$11.12

            bars = self.get_bars_from_opportunity(opportunity)
            current_price = opportunity.get('current_price', 0)

            if bars and len(bars) >= 30:
                is_trend_valid, trend_reason = self.trend_filters.check_trend_filters(bars, current_price)
                if not is_trend_valid:
                    self.logger.info(f"⚪ {symbol}: REJECTED - {trend_reason}")
                    # Limpiar pending entries si rechazamos por tendencia
                    if symbol in self.pending_entries:
                        del self.pending_entries[symbol]
                    return False

            # ============================================================
            # VALIDATION 3: Final risk checks
            # ============================================================

            # Check risk manager limits
            if not await self._check_risk_limits(opportunity):
                self.logger.warning(f"🚫 {symbol}: Risk limits exceeded")
                return False

            # ============================================================
            # ✅ ALL VALIDATIONS PASSED
            # ============================================================

            self.logger.info(
                f"✅ {symbol}: GENERIC_01 ENTRY APPROVED - "
                f"Pattern: {completion:.0f}%, Confirmations: {self.pending_entries[symbol]['count']}"
            )

            # Clean up pending entry
            if symbol in self.pending_entries:
                del self.pending_entries[symbol]

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_enter: {e}")
            return False

    async def _check_risk_limits(self, opportunity: Dict[str, Any]) -> bool:
        """
        Verifica límites de riesgo antes de entrada

        Args:
            opportunity: Opportunity data

        Returns:
            True si pasa validaciones, False si no
        """
        try:
            # Check max positions
            if len(self.active_positions) >= 3:  # Max 3 positions per worker
                return False

            # Check daily trade limit
            if hasattr(self.risk_manager, 'get_daily_trade_count'):
                daily_trades = await self.risk_manager.get_daily_trade_count()
                if daily_trades >= 10:  # Max 10 trades per day
                    return False

            # Check buying power
            if hasattr(self.risk_manager, 'get_available_buying_power'):
                buying_power = await self.risk_manager.get_available_buying_power()
                if buying_power < 1000:  # Minimum $1000 needed
                    return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Error checking risk limits: {e}")
            return False

    async def should_exit(
        self,
        symbol: str,
        position_data: Dict[str, Any],
        current_bar: Any
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de una posición

        Args:
            symbol: Symbol
            position_data: Position data from active_positions
            current_bar: Current market bar

        Returns:
            (should_exit, exit_reason)
        """
        try:
            # Use centralized stop manager
            should_exit, reason = await self.stop_manager.check_exit(
                symbol=symbol,
                position_data=position_data,
                current_bar=current_bar
            )

            if should_exit:
                self.logger.info(f"🚪 {symbol}: Exit signal - {reason}")

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in should_exit: {e}")
            return False, ""

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de una posición - PARÁMETROS CORREGIDOS
        
        CRITICAL FIX: Usar signature compatible con sistema base
        Ahora usa current_price en lugar de current_bar
        
        Args:
            symbol: Symbol
            position: Position data from active_positions
            current_price: Current price (fixed parameter)

        Returns:
            (should_exit, exit_reason)
        """
        try:
            entry_price = position.get('entry_price', 0)
            if entry_price == 0:
                self.logger.warning(f"⚠️ {symbol}: Invalid entry price in position data")
                return False, "Invalid entry price"

            # Get market data for FOMO detection (similar a daily_plays)
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

            self.logger.debug(f"📊 {symbol}: stop_manager.check_exit() = {should_exit}, reason = '{reason}'")
            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """
        Sobrescribe el método base para registro DUAL: stop_manager + unified manager
        
        CRITICAL FIX: Registra posición en WorkerStopManager para monitoring de exits
        Y en UnifiedPositionManager para prevenir duplicates
        """
        symbol = opportunity.get('symbol', 'UNKNOWN')

        try:
            # USAR LÓGICA BASE para todo el proceso de entrada
            entry_success = await super()._execute_entry(opportunity)
            
            if not entry_success:
                return False

            # 🛡️ CRITICAL FIX #1: Registrar con WorkerStopManager para monitoring de exits
            try:
                self.stop_manager.register_position(symbol, datetime.now())
                self.logger.info(f"📝 {symbol}: Registered with WorkerStopManager for exit monitoring")
            except Exception as e:
                self.logger.error(f"❌ {symbol}: Failed to register with WorkerStopManager: {e}")
                # Continue anyway, don't fail the entry
            
            # 🛡️ CRITICAL FIX #2: Registrar con UnifiedPositionManager para prevenir duplicates
            try:
                from core.service_locator import get_unified_position_manager
                unified_manager = await get_unified_position_manager()
                
                if unified_manager:
                    # Obtener datos de la posición
                    entry_price = opportunity.get('entry_price', 0.0)
                    quantity = opportunity.get('position_size', 0)
                    
                    if entry_price > 0 and quantity > 0:
                        position_value = entry_price * quantity
                        strategy_type = 'day'  # generic_01 es day trading
                        
                        position_data = {
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'position_value': position_value,
                            'strategy': self.worker_name,
                            'strategy_type': strategy_type,
                            'edge': 41.04,  # Edge validated
                            'take_profit': 32.83,
                            'stop_loss': 16.42,
                            'opened_at': datetime.now().isoformat()
                        }
                        
                        success = unified_manager.register_position(
                            symbol=symbol,
                            strategy_type=strategy_type,
                            position_data=position_data
                        )
                        
                        if success:
                            self.logger.info(f"💼 {symbol}: Registered with UnifiedPositionManager")
                        else:
                            self.logger.warning(f"⚠️ {symbol}: Failed to register with UnifiedPositionManager")
                
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol}: Error with UnifiedPositionManager: {e}")
                # Don't fail the entry for this

            return True

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error in _execute_entry: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

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

    def get_trading_horizon(self) -> TradingHorizon:
        """Returns trading horizon for this worker"""
        return TradingHorizon.INTRADAY

    def __str__(self):
        return (
            f"Generic01Worker(edge=41.04%, tp=32.83%, sl=16.42%, "
            f"active={len(self.active_positions)})"
        )
