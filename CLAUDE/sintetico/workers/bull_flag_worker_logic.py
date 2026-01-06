"""
Bull Flag Worker Logic
Worker específico para estrategia Bull Flag (Pattern-based continuation)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


class BullFlagWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia Bull Flag

    Enfoque: Pattern-based trading (continuation patterns)
    Ideal para movimientos con consolidación ordenada después de impulso

    Criterios de entrada:
    - Gap moderado (3-8%) - No muy grande, no muy pequeño
    - Volume ratio >= 2.0x (momentum confirmado)
    - Precio en rango smallcap ($1-$15)
    - Pattern quality indicators (consolidation)
    - No gaps extremos (queremos patrones limpios)

    Criterios de salida:
    - Take profit: 15% (projection of flagpole)
    - Stop loss: 5% (below flag low)
    - Trailing stop: 10% activation, 4% distance
    - Time-based: 6 horas máximo
    - Pattern invalidation detection
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="bull_flag",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica Bull Flag
        self.min_gap = 3.0            # Gap mínimo para flagpole
        self.max_gap = 8.0            # Gap máximo (no quieren extremos)
        self.min_volume_ratio = 2.0   # Volume ratio mínimo
        self.min_price = 1.0          # Precio mínimo
        self.max_price = 15.0         # Precio máximo (smallcaps)

        # Time-based
        self.min_hour = 9.5               # No entrar antes de 9:30
        self.max_hour = 14.5              # No entrar después de 14:30

        # Entry confirmation tracking (cooldown entre entradas)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 2    # Número de scans consecutivos antes de entrar
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'BULL_FLAG_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=5.0,
                take_profit_pct=15.0,
                quick_target_pct=None,
                trailing_activation=10.0,
                trailing_distance=4.0,
                max_position_hours=6.0
            ))

        self.logger.info(
            f"🎯 Bull Flag Worker configured: "
            f"gap={self.min_gap}-{self.max_gap}%, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Bull Flag (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Bull Flag Pattern Stages:
        1. [33%] Pole detected (gap in range 3-8%)
        2. [66%] Flag range + quality + hours validated
        3. [85%] FLAG CONSOLIDATION (EARLY ENTRY - gap in sweet spot, not extended)
        4. [100%] PARABOLIC EXTENSION (LATE - gap too large, already moved)

        Early Entry Target: 85% = Flag consolidating in sweet spot

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            gap_pct = abs(opportunity.get('gap_percentage', 0))
            current_price = opportunity.get('current_price', 0)
            catalyst_type = opportunity.get('catalyst_type', '')
            quality_score = opportunity.get('quality_score', 0)

            # Stage 1: Pole detected (33%)
            # Pole = initial strong move (gap in range)
            if self.min_gap <= gap_pct <= self.max_gap:
                completion += 33.0
                self.logger.debug(
                    f"📊 {symbol}: Pole stage (33%) - gap {gap_pct:.1f}%"
                )
            else:
                return 0.0

            # Check catalyst (avoid extreme ones)
            extreme_catalysts = ['FDA', 'M&A', 'EARNINGS']
            if catalyst_type in extreme_catalysts:
                self.logger.debug(f"📊 {symbol}: Extreme catalyst - not Bull Flag")
                return 0.0

            # Stage 2: Flag range + quality + hours (66%)
            import pytz
            from datetime import datetime
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)
            current_hour = now_et.hour + now_et.minute / 60

            if self.min_price <= current_price <= self.max_price:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Price range (44%)")
            else:
                return completion

            if quality_score >= 50.0:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Quality validated (55%)")
            else:
                return completion

            if self.min_hour <= current_hour <= self.max_hour:
                completion += 11.0
                self.logger.debug(f"📊 {symbol}: Trading hours (66%)")
            else:
                return completion

            # Stage 3: FLAG CONSOLIDATION vs BREAKOUT (85-100%)
            # Detect if consolidating in sweet spot (early) or extended (late)

            # Check gap sweet spot:
            # - Gap 4-7% = clean flag consolidation (EARLY ENTRY)
            # - Gap > 7.5% = extended, likely breaking out (LATE)

            if gap_pct <= 7.5:
                # Consolidation sweet spot - early entry window
                completion += 19.0
                self.logger.debug(
                    f"📊 {symbol}: FLAG CONSOLIDATION (85%) - gap {gap_pct:.1f}% in sweet spot"
                )
            else:
                # Extended move - breakout happening or done, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: FLAG EXTENSION - gap {gap_pct:.1f}% too large (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Bull Flag pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Bull Flag

        EARLY ENTRY STRATEGY:
        - Enter at 75-95% pattern completion (flag consolidating)
        - Avoid waiting for 100% completion (breakout already happened)

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
            # - 0-74%: Pattern not ready, reject
            # - 75-95%: OPTIMAL entry window (flag consolidating, ready for breakout)
            # - 96-100%: Too late, breakout already happening

            if completion < 75.0:
                self.logger.debug(
                    f"⏳ {symbol}: Pattern not ready - {completion:.0f}% < 75% (waiting for flag consolidation)"
                )
                return False

            if completion > 95.0:
                self.logger.warning(
                    f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, breakout happening)"
                )
                return False

            # OPTIMAL ENTRY WINDOW: 75-95%
            self.logger.info(
                f"✅ {symbol}: EARLY ENTRY APPROVED - Pattern {completion:.0f}% complete "
                f"(entering BEFORE breakout)"
            )

            # Clean up any pending entries tracking
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
        Evalúa si debe salir de posición según criterios Bull Flag

        Criterios de salida:
        1. Take profit: PnL >= 15% (flagpole projection)
        2. Stop loss: PnL <= -5% (below flag low)
        3. Trailing stop: Si PnL >= 10%, activar trailing a 4%
        4. Time-based: Más de 6 horas en posición
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