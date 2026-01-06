"""
MACDV Worker Logic
Worker específico para estrategia MACD-V (Technical momentum)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


class MacdvWorkerLogic(BaseWorkerLogic):
    """
    Worker lógico para estrategia MACD-V

    Enfoque: Trading técnico basado en momentum sin gaps grandes
    Ideal para movimientos intraday normales con confirmación de volumen

    Criterios de entrada:
    - Gap pequeño (< 5%)
    - Volume ratio >= 1.5x
    - Precio en rango smallcap ($1-$25)
    - Sin noticias mayores (momentum técnico puro)
    - Horario de mercado normal (9:30-15:30)

    Criterios de salida:
    - Take profit: 10%
    - Stop loss: 4%
    - Trailing stop: 8% activation, 4% distance
    - Time-based: 4 horas máximo
    """

    def __init__(self, execution_engine, risk_manager, config=None):
        super().__init__(
            worker_name="macdv",
            execution_engine=execution_engine,
            risk_manager=risk_manager
        )

        # Configuración específica MACDV
        self.max_gap = 5.0           # Gap máximo (queremos movimientos normales)
        self.min_volume_ratio = 1.5  # Volume ratio mínimo
        self.min_price = 1.0         # Precio mínimo
        self.max_price = 25.0        # Precio máximo (smallcaps)

        # Time-based
        self.min_hour = 9.5               # No entrar antes de 9:30
        self.max_hour = 15.5              # No entrar después de 15:30

        # Entry confirmation tracking (cooldown entre entradas)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 2    # Número de scans consecutivos antes de entrar
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'MACDV_STRATEGY')
        else:
            # Fallback: create with default parameters
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            self.stop_manager = WorkerStopManager(WorkerStopConfig(
                stop_loss_pct=4.0,
                take_profit_pct=10.0,
                quick_target_pct=None,
                trailing_activation=8.0,
                trailing_distance=4.0,
                max_position_hours=4.0
            ))

        self.logger.info(
            f"🎯 MACDV Worker configured: "
            f"gap<{self.max_gap}%, vol>={self.min_volume_ratio}x, "
            f"price=${self.min_price}-${self.max_price}"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón MACDV (0-100%)

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        MACDV Pattern Stages:
        1. [33%] Price in range & technical catalyst
        2. [66%] Trading hours & quality validated
        3. [85%] NORMAL TECHNICAL MOVE (EARLY ENTRY - momentum building)
        4. [100%] PARABOLIC MOVE (LATE - already extended)

        Early Entry Target: 85% = Technical move detected, not yet parabolic

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

            # Stage 1: Price range & technical catalyst (33%)
            major_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH']
            if catalyst_type not in major_catalysts:
                completion += 17.0
                self.logger.debug(f"📊 {symbol}: Technical catalyst (17%)")
            else:
                self.logger.debug(f"📊 {symbol}: Major catalyst - not MACDV pattern")
                return 0.0

            if self.min_price <= current_price <= self.max_price:
                completion += 16.0
                self.logger.debug(f"📊 {symbol}: Price range (33%) - ${current_price:.2f}")
            else:
                return completion

            # Stage 2: Trading hours & quality (66%)
            from datetime import datetime
            import pytz
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(eastern)
            current_hour = now_et.hour + now_et.minute / 60

            if self.min_hour <= current_hour <= self.max_hour:
                completion += 17.0
                self.logger.debug(f"📊 {symbol}: Trading hours (50%)")
            else:
                return completion

            if quality_score >= 50.0:
                completion += 16.0
                self.logger.debug(f"📊 {symbol}: Quality validated (66%)")
            else:
                return completion

            # Stage 3: NORMAL vs PARABOLIC MOVE (85-100%)
            # Detect if normal technical move (early entry) or parabolic (late)

            # Check gap magnitude:
            # - Gap 0-5% = normal technical move (EARLY ENTRY)
            # - Gap > 8% = parabolic extension (LATE, too extended)

            if gap_pct <= self.max_gap:
                # Normal technical move - early entry window
                completion += 19.0
                self.logger.debug(
                    f"📊 {symbol}: NORMAL MOVE (85%) - gap {gap_pct:.1f}% not parabolic"
                )
            else:
                # Parabolic move - pattern complete, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: PARABOLIC EXTENSION - gap {gap_pct:.1f}% too large (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: MACDV pattern = {completion:.0f}% "
                f"(gap={gap_pct:.1f}%, price=${current_price:.2f})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios MACDV

        EARLY ENTRY STRATEGY:
        - Enter at 70-95% pattern completion (divergence forming)
        - Avoid waiting for 100% completion (crossover already happened)

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
            # - 0-69%: Pattern not ready, reject
            # - 70-95%: OPTIMAL entry window (divergence forming, momentum building)
            # - 96-100%: Too late, crossover already happening

            if completion < 70.0:
                self.logger.debug(
                    f"⏳ {symbol}: Pattern not ready - {completion:.0f}% < 70% (waiting for divergence)"
                )
                return False

            if completion > 95.0:
                self.logger.warning(
                    f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, crossover happening)"
                )
                return False

            # OPTIMAL ENTRY WINDOW: 70-95%
            self.logger.info(
                f"✅ {symbol}: EARLY ENTRY APPROVED - Pattern {completion:.0f}% complete "
                f"(entering BEFORE crossover)"
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
        Evalúa si debe salir de posición según criterios MACDV

        Criterios de salida:
        1. Take profit: PnL >= 10%
        2. Stop loss: PnL <= -4%
        3. Trailing stop: Si PnL >= 8%, activar trailing a 4%
        4. Time-based: Más de 4 horas en posición
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