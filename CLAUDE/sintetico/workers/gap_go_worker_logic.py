"""
Gap-Go Worker Logic
Worker específico para estrategia Gap & Go
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


class GapGoWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Gap & Go

    Criterios de entrada:
    - Gap >= 8%
    - Volume ratio >= 2.0x
    - Precio en rango smallcap (< $15)

    Criterios de salida:
    - Take profit: 15%
    - Stop loss: 3%
    - Time-based: Fin del día
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="gap_go",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Gap-Go
        self.min_gap = 8.0          # Gap mínimo requerido (%)
        self.min_volume_ratio = 2.0  # Volume ratio mínimo
        self.max_price = 15.0        # Precio máximo (smallcap focus)

        # Entry confirmation tracking (ajustado para estrategia rápida)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 0    # Gap-Go necesita entrada INMEDIATA (0 = sin espera)
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'GAP_GO_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=3.0,
                take_profit_pct=15.0,
                quick_target_pct=6.0,
                trailing_activation=3.0,
                trailing_distance=2.0,
                max_position_hours=6.0
            ))

        self.logger.info(
            f"🎯 Gap-Go Worker configured: "
            f"gap>={self.min_gap}%, vol>={self.min_volume_ratio}x"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Gap-Go (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Gap-Go Pattern Stages:
        1. [25%] Gap detected (>= min_gap)
        2. [50%] Price range & quality validated
        3. [75%] Price ABOVE VWAP (strength confirmed)
        4. [85%] CONSOLIDATION near VWAP (EARLY ENTRY - ready for breakout)
        5. [100%] BREAKOUT momentum (gap expanding, LATE - already moving)

        Early Entry Target: 85% = Consolidation detected, price holding strength

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            # Stage 1: Gap detected (25%)
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            if gap_pct >= self.min_gap:
                completion += 25.0
                self.logger.debug(f"📊 {symbol}: Gap stage (25%) - {gap_pct:.1f}%")
            else:
                return 0.0  # No gap, no pattern

            # Stage 2: Price range & quality (50%)
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)
            catalyst_type = opportunity.get('catalyst_type', '')
            catalyst_strength = opportunity.get('catalyst_strength', 0)

            # Check catalyst (avoid strong catalysts - defer to Daily Plays)
            strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT']
            if catalyst_type in strong_catalysts and catalyst_strength >= 6:
                self.logger.debug(f"📊 {symbol}: Strong catalyst - not Gap-Go pattern")
                return 0.0

            if current_price <= self.max_price and quality_score >= 50.0:
                completion += 25.0
                self.logger.debug(f"📊 {symbol}: Quality stage (50%)")
            else:
                return completion

            # Stage 3: VWAP Strength Confirmation (75%)
            vwap_price = await self._get_vwap(symbol, current_price, opportunity)

            if vwap_price and current_price >= vwap_price:
                # Price above VWAP = strength confirmed
                completion += 25.0
                self.logger.debug(
                    f"📊 {symbol}: VWAP strength (75%) - ${current_price:.2f} >= ${vwap_price:.2f}"
                )
            else:
                # Price below VWAP = weakness, not ready
                self.logger.debug(
                    f"📊 {symbol}: Price below VWAP (${current_price:.2f} < ${vwap_price:.2f if vwap_price else 0:.2f}) - pattern not ready"
                )
                return completion

            # Stage 4: CONSOLIDATION vs BREAKOUT (85-100%)
            # Detect if consolidating (early entry) or breaking out (late)

            # Check gap momentum:
            # - Gap 8-12% = consolidating, ready for move (EARLY ENTRY)
            # - Gap > 15% = already moving parabolic (LATE, too extended)

            if gap_pct <= 15.0:
                # Consolidation range - early entry window
                completion += 10.0
                self.logger.debug(
                    f"📊 {symbol}: CONSOLIDATION (85%) - gap {gap_pct:.1f}% not extended"
                )
            else:
                # Parabolic move - pattern complete, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: PARABOLIC BREAKOUT - gap {gap_pct:.1f}% extended (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Gap-Go pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f}, "
                f"VWAP=${vwap_price:.2f if vwap_price else 0:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Gap-Go

        EARLY ENTRY STRATEGY:
        - Enter at 80% pattern completion (consolidation detected)
        - Avoid waiting for 100% completion (breakout already happened)

        Criterios:
        1. Pattern completion >= 80% (early entry target)
        2. Pattern completion <= 95% (avoid entering too late)

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Calculate pattern completion percentage
            completion = await self.calculate_pattern_completion(opportunity)

            # EARLY ENTRY LOGIC:
            # - 0-79%: Pattern not ready, reject
            # - 80-95%: OPTIMAL entry window (consolidation ready for breakout)
            # - 96-100%: Too late, breakout already happening

            if completion < 80.0:
                self.logger.debug(
                    f"⏳ {symbol}: Pattern not ready - {completion:.0f}% < 80% (waiting for consolidation)"
                )
                return False

            if completion > 95.0:
                self.logger.warning(
                    f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, already moving)"
                )
                return False

            # OPTIMAL ENTRY WINDOW: 80-95%
            # Enter immediately - no confirmation waiting needed
            # The pattern completion calculation already validates the setup
            self.logger.info(
                f"✅ {symbol}: EARLY ENTRY APPROVED - Pattern {completion:.0f}% complete "
                f"(entering BEFORE full breakout)"
            )

            # Clean up any pending entries tracking (no longer needed with early entry)
            if symbol in self.pending_entries:
                del self.pending_entries[symbol]

            return True

        except Exception as e:
            self.logger.error(f"❌ Error evaluating opportunity: {e}")
            return False

    async def should_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si debe salir de posición según criterios Gap-Go

        Criterios de salida:
        1. Take profit: PnL >= 15%
        2. Stop loss: PnL <= -3%
        3. Time-based: Más de 6 horas en posición
        4. EOD: Close cerca del cierre de mercado

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
                    durationStr='5 min',
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

            # Use centralized stop manager to check exit conditions
            should_exit, reason = self.stop_manager.check_exit(
                symbol=symbol,
                current_price=current_price,
                entry_price=entry_price,
                market_data=market_data
            )

            return should_exit, reason

        except Exception as e:
            self.logger.error(f"❌ Error evaluating exit for {symbol}: {e}")
            # In case of error, unregister and exit for safety
            self.stop_manager.unregister_position(symbol)
            return True, "ERROR_EXIT"

    async def _execute_entry(self, opportunity: Dict[str, Any]) -> bool:
        """Override to register position with stop manager"""
        # Execute normal entry
        success = await super()._execute_entry(opportunity)

        if success:
            # Register position with stop manager for tracking
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')
            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} with stop manager")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager"""
        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    async def _get_vwap(self, symbol: str, fallback_price: float, opportunity: Dict[str, Any] = None) -> float:
        """
        Obtiene el VWAP del día para el símbolo
        DEPRECATED: Use calculate_vwap_from_bars() from base class instead

        Args:
            symbol: Símbolo a consultar
            fallback_price: Precio a usar si falla el cálculo
            opportunity: Opportunity dict que puede contener bars_history

        Returns:
            VWAP price o None si no se puede calcular
        """
        # Use base class helper function
        bars = self.get_bars_from_opportunity(opportunity) if opportunity else []

        if bars and len(bars) > 0:
            return self.calculate_vwap_from_bars(bars)

        # Fallback: fetch from IBKR if no bars in opportunity
        try:
            from ib_insync import Stock
            from datetime import datetime
            import pytz

            eastern = pytz.timezone('US/Eastern')
            now = datetime.now(eastern)
            market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

            if now < market_open:
                return None

            contract = Stock(symbol, 'SMART', 'USD')
            bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True
            )

            return self.calculate_vwap_from_bars(bars) if bars else None

        except Exception as e:
            self.logger.debug(f"Could not fetch bars for VWAP: {e}")
            return None