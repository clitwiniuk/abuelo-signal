"""
Daily Plays Worker Logic
Worker específico para estrategia Daily Plays (Catalyst-driven breakouts)
"""

import logging
from typing import Dict, Any, Tuple
from .base_worker_logic import BaseWorkerLogic
from .worker_stop_manager import create_worker_stop_manager


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
    5. Precio > VWAP intraday (confirmación de fortaleza - tolerancia configurable)
    6. Daily Context Check (EVITA TRAMPAS INSTITUCIONALES):

    Criterios de entrada MOMENTUM RUNNER (Nuevo):
    1. Gap > 10% + Volume > 3x + Precio < $20 (smallcap runner)
    2. VWAP check con tolerancia 10% (configurable)
    3. Quality score >= 30.0 (relajado)
    4. Entrada inmediata (0 confirmaciones)
    5. Skip daily context checks (para velocidad)
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

    Criterios de salida (via WorkerStopManager - DUAL CONFIG):

    MOMENTUM RUNNERS (Intraday):
    - Quick Target: 25% (si rápido, prioridad 0)
    - FOMO Exhaustion (prioridad 1)
    - Trailing stop: 10% activation, 5% distance (prioridad 2)
    - Take profit: 50% (prioridad 3)
    - Stop loss: 5% (prioridad 4)
    - Time-based: 6.5 horas máximo (prioridad 5)
    - END_OF_DAY: 15:56 ET (prioridad 6)

    CATALYST PLAYS:
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

        # Configuración específica Daily Plays
        self.strong_catalysts = ['FDA', 'M&A', 'EARNINGS', 'BREAKTHROUGH', 'CONTRACT']
        self.min_volume_ratio = 0.5   # Volume ratio mínimo (bajado para testing en pre-market)
        self.min_price = 1.0          # Precio mínimo
        self.max_price = 50.0         # Precio máximo (más alto que otros)
        self.min_quality_score = 50.0 # Quality score mínimo (aumentado para mayor calidad)

        # Entry confirmation tracking (ajustado para estrategia de catalyst)
        self.pending_entries = {}     # {symbol: {'first_seen': datetime, 'count': int}}
        self.min_confirmations = 1    # Catalyst plays: 1 confirmación (30s) para no perder momentum
        self.confirmation_window = 120 # Ventana de 2 minutos para confirmar

        # Track position types for dynamic exit logic
        self.position_types = {}      # {symbol: 'runner' | 'catalyst'}

        # ===== NUEVO: Configuración para Momentum Runners =====
        self.runner_config = {
            'min_gap_pct': 10.0,           # Gap mínimo para runners
            'min_volume_ratio': 3.0,       # Volume mínimo para runners
            'max_price': 20.0,             # Precio máximo para smallcap runners
            'vwap_tolerance': 0.9,         # Tolerancia VWAP (10% menos)
            'min_quality_score': 30.0,     # Quality score relajado
            'min_confirmations': 0,        # Entrada inmediata
            'confirmation_window': 30,     # 30 segundos
            'skip_daily_checks': True,     # Skip checks diarios
            'catalyst_optional': True      # Catalizador opcional
        }

        self.catalyst_config = {
            'min_gap_pct': 0.0,            # No gap mínimo
            'min_volume_ratio': 0.5,       # Volume normal
            'max_price': 50.0,             # Precio máximo normal
            'vwap_tolerance': 1.0,         # VWAP estricto
            'min_quality_score': 50.0,     # Quality score normal
            'min_confirmations': 1,        # 1 confirmación
            'confirmation_window': 120,    # 2 minutos
            'skip_daily_checks': False,    # Checks diarios activos
            'catalyst_optional': False     # Catalizador requerido
        }

        # ===== NUEVO: Configuración Dual de Stops =====
        self.runner_stop_config = {
            'stop_loss_pct': 5.0,          # SL igual
            'take_profit_pct': 50.0,       # TP más alto para runners
            'quick_target_pct': 25.0,      # Target parcial rápido
            'trailing_activation': 10.0,   # Activación más alta
            'trailing_distance': 5.0,      # Distancia más amplia
            'max_position_hours': 6.5      # INTRADAY only (cierra antes EOD)
        }

        self.catalyst_stop_config = {
            'stop_loss_pct': 5.0,          # SL estándar
            'take_profit_pct': 20.0,       # TP conservador
            'quick_target_pct': None,      # Sin quick target
            'trailing_activation': 6.0,    # Activación media
            'trailing_distance': 3.0,      # Distancia media
            'max_position_hours': 8.0      # Hasta 8 horas
        }

        # Initialize centralized stop manager from config.ini
        if config:
            self.stop_manager = create_worker_stop_manager(config, 'DAILY_PLAYS_STRATEGY')

            # Load Reversal Mode configuration
            self.enable_reversal_mode = config.getboolean('DAILY_PLAYS_STRATEGY', 'enable_reversal_mode', fallback=True)
            self.reversal_min_rsi = config.getfloat('DAILY_PLAYS_STRATEGY', 'reversal_min_rsi', fallback=35.0)
            self.reversal_min_signals = config.getint('DAILY_PLAYS_STRATEGY', 'reversal_min_signals', fallback=4)
            self.reversal_max_support_distance = config.getfloat('DAILY_PLAYS_STRATEGY', 'reversal_max_support_distance', fallback=3.0)
            self.reversal_volume_ratio_relaxed = config.getfloat('DAILY_PLAYS_STRATEGY', 'reversal_volume_ratio_relaxed', fallback=1.5)
            self.reversal_quality_score_relaxed = config.getfloat('DAILY_PLAYS_STRATEGY', 'reversal_quality_score_relaxed', fallback=40.0)
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

            # Reversal mode defaults
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
        self.logger.info(f"   🚀 Momentum Runner Mode: gap>={self.runner_config['min_gap_pct']}%, "
            f"vol>={self.runner_config['min_volume_ratio']}x, price<${self.runner_config['max_price']}"
        )
        self.logger.info(f"   🎯 Runner Stops: TP={self.runner_stop_config['take_profit_pct']}%, "
            f"QT={self.runner_stop_config['quick_target_pct']}%, Trail={self.runner_stop_config['trailing_activation']}%/{self.runner_stop_config['trailing_distance']}%, "
            f"Time={self.runner_stop_config['max_position_hours']}h (INTRADAY)"
        )
        self.logger.info(f"   📊 Catalyst Stops: TP={self.catalyst_stop_config['take_profit_pct']}%, "
            f"Trail={self.catalyst_stop_config['trailing_activation']}%/{self.catalyst_stop_config['trailing_distance']}%, "
            f"Time={self.catalyst_stop_config['max_position_hours']}h"
        )
        self.logger.info(f"   Stop Manager: {self.stop_manager.config}")
        if self.enable_reversal_mode:
            self.logger.info(
                f"   Reversal Mode ENABLED: RSI<{self.reversal_min_rsi}, "
                f"{self.reversal_min_signals}/6 signals required"
            )

    def _detect_momentum_runner(self, opportunity: Dict[str, Any]) -> bool:
        """
        Detecta movimientos explosivos tipo CYPH (+65%)

        Criterios para Momentum Runners:
        - Gap > 10% (movimiento explosivo)
        - Volume > 3x (interés masivo)
        - Precio < $20 (smallcap runner típico)

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            True si cumple criterios de momentum runner
        """
        try:
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            volume_ratio = opportunity.get('volume_ratio', 0)
            current_price = opportunity.get('current_price', 0)

            is_runner = (gap_pct >= self.runner_config['min_gap_pct'] and
                        volume_ratio >= self.runner_config['min_volume_ratio'] and
                        current_price <= self.runner_config['max_price'])

            if is_runner:
                symbol = opportunity.get('symbol', 'UNKNOWN')
                self.logger.info(
                    f"🚀 {symbol}: MOMENTUM RUNNER DETECTED - "
                    f"Gap {gap_pct:.1f}%, Vol {volume_ratio:.1f}x, Price ${current_price:.2f}"
                )

            return is_runner

        except Exception as e:
            self.logger.debug(f"Error detecting momentum runner: {e}")
            return False

    def _get_config_for_opportunity(self, opportunity: Dict[str, Any]) -> Dict:
        """
        Retorna configuración apropiada según tipo de oportunidad

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            Dict con configuración (runner_config o catalyst_config)
        """
        if self._detect_momentum_runner(opportunity):
            return self.runner_config
        return self.catalyst_config

    def _get_stop_config_for_opportunity(self, opportunity: Dict[str, Any]) -> Dict:
        """
        Retorna configuración de stops apropiada según tipo de oportunidad

        Args:
            opportunity: Datos de la oportunidad

        Returns:
            Dict con configuración de stops (runner_stop_config o catalyst_stop_config)
        """
        if self._detect_momentum_runner(opportunity):
            return self.runner_stop_config
        return self.catalyst_stop_config

    def _is_fast_move(self, symbol: str, pnl_pct: float) -> bool:
        """
        Determina si el movimiento de ganancia fue rápido (dentro de 2 horas)

        Args:
            symbol: Símbolo de la posición
            pnl_pct: Porcentaje de ganancia actual

        Returns:
            True si fue un movimiento rápido
        """
        try:
            if symbol not in self.stop_manager.entry_times:
                return False

            entry_time = self.stop_manager.entry_times[symbol]
            from datetime import datetime

            # Handle string timestamps (from restoration)
            if isinstance(entry_time, str):
                try:
                    from dateutil import parser
                    entry_time = parser.parse(entry_time)
                except Exception:
                    return False

            hours_in_position = (datetime.now() - entry_time).total_seconds() / 3600

            # Consider fast move if reached target within 2 hours
            is_fast = hours_in_position <= 2.0

            if is_fast:
                self.logger.debug(f"⚡ {symbol}: Fast move detected - {pnl_pct:.1f}% in {hours_in_position:.1f}h")

            return is_fast

        except Exception as e:
            self.logger.debug(f"Error checking fast move for {symbol}: {e}")
            return False

    async def calculate_pattern_completion(self, opportunity: Dict[str, Any]) -> float:
        """
        Calcula completitud del patrón Daily Plays (0-100%)

        MODO DUAL:
        - Momentum Runners: Lógica simplificada con VWAP tolerance
        - Catalyst Plays: Lógica completa tradicional

        Args:
            opportunity: Opportunity data

        Returns:
            Pattern completion percentage (0.0-100.0)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # ===== DETECTAR TIPO DE OPORTUNIDAD =====
            config = self._get_config_for_opportunity(opportunity)
            is_runner = self._detect_momentum_runner(opportunity)

            if is_runner:
                return await self._calculate_runner_pattern_completion(opportunity, config)

            # ===== LÓGICA TRADICIONAL PARA CATALYST PLAYS =====
            return await self._calculate_catalyst_pattern_completion(opportunity, config)

        except Exception as e:
            self.logger.error(f"❌ Error calculating pattern completion: {e}")
            return 0.0

    async def _calculate_runner_pattern_completion(self, opportunity: Dict[str, Any], config: Dict) -> float:
        """
        Pattern completion para Momentum Runners con VWAP tolerance

        Runners Pattern:
        - Gap 10-20% = 80% (ready to run)
        - Gap >20% = 90% (running)
        - VWAP check con tolerancia configurable
        - Siempre early entry para capturar momentum
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            gap_pct = abs(opportunity.get('gap_percentage', 0))
            volume_ratio = opportunity.get('volume_ratio', 0)
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)

            # Base completion para runners explosivos
            if gap_pct >= 20.0:
                completion = 90.0  # Running hard
                reason = "PARABOLIC RUNNER"
            elif gap_pct >= 15.0:
                completion = 85.0  # Strong momentum
                reason = "STRONG MOMENTUM"
            elif gap_pct >= 10.0:
                completion = 80.0  # Ready to run
                reason = "READY TO RUN"
            else:
                return 0.0  # Not a runner

            # Bonus por volumen extremo
            if volume_ratio >= 5.0:
                completion += 5.0  # Cap at 95%
                reason += " + EXTREME VOLUME"

            # ===== VWAP CHECK CON TOLERANCIA =====
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_price = self.calculate_vwap_from_bars(bars) if bars else None

            if vwap_price:
                vwap_threshold = vwap_price * config['vwap_tolerance']  # Aplicar tolerancia
                if current_price >= vwap_threshold:
                    self.logger.debug(
                        f"🚀 {symbol}: VWAP check PASSED - "
                        f"${current_price:.2f} >= ${vwap_threshold:.2f} (tolerance: {config['vwap_tolerance']})"
                    )
                else:
                    # VWAP check fallido - reducir completion
                    completion -= 10.0
                    reason += " - VWAP BELOW THRESHOLD"
                    self.logger.debug(
                        f"🚀 {symbol}: VWAP check FAILED - "
                        f"${current_price:.2f} < ${vwap_threshold:.2f} (tolerance: {config['vwap_tolerance']})"
                    )

            completion = min(completion, 95.0)  # Never 100% for runners

            self.logger.info(
                f"🚀 {symbol}: RUNNER PATTERN = {completion:.0f}% ({reason}) - "
                f"Gap {gap_pct:.1f}%, Vol {volume_ratio:.1f}x, Price ${current_price:.2f}, "
                f"VWAP ${vwap_price:.2f if vwap_price else 'N/A'}"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating runner pattern completion: {e}")
            return 0.0

    async def _calculate_catalyst_pattern_completion(self, opportunity: Dict[str, Any], config: Dict) -> float:
        """
        Pattern completion original para Catalyst Plays con config dinámica

        PATTERN-ONLY ANALYSIS (volumen ya validado por scanner):

        Daily Plays Pattern Stages:
        1. [25%] Catalyst detected + price range
        2. [50%] Quality & catalyst strength validated
        3. [75%] Daily context safe + VWAP strength
        4. [85%] CATALYST REACTING (EARLY ENTRY - price moving but controlled)
        5. [100%] PARABOLIC MOVE (LATE - catalyst fully priced in)

        Early Entry Target: 85% = Catalyst reacting, not yet parabolic
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            completion = 0.0

            catalyst_type = opportunity.get('catalyst_type', '')
            catalyst_strength = opportunity.get('catalyst_strength', 0)
            current_price = opportunity.get('current_price', 0)
            quality_score = opportunity.get('quality_score', 0)
            gap_pct = abs(opportunity.get('gap_percentage', 0))

            # Check daily context (skip si config lo indica)
            skip_daily = config.get('skip_daily_checks', False)
            daily_context = await self._check_daily_context(symbol, current_price, skip_checks=skip_daily)

            # Stage 1: Catalyst + price range (25%)
            catalyst_required = config.get('catalyst_optional', False)
            if catalyst_required or (catalyst_type in self.strong_catalysts and
                config['min_price'] <= current_price <= config['max_price']):
                completion += 25.0
                self.logger.debug(
                    f"📊 {symbol}: Catalyst stage (25%) - {catalyst_type}"
                )
            elif self.enable_reversal_mode and daily_context.get('reversal', {}).get('is_reversal', False):
                # Reversal setup detected - catalyst not required
                completion += 25.0
                self.logger.debug(
                    f"📊 {symbol}: Reversal setup (25%) - catalyst optional"
                )
            else:
                return 0.0

            # Stage 2: Quality & catalyst strength (50%)
            min_quality = config['min_quality_score']
            if quality_score >= min_quality and catalyst_strength >= 6:
                completion += 25.0
                self.logger.debug(
                    f"📊 {symbol}: Quality/strength (50%) - "
                    f"Q={quality_score:.1f}, strength={catalyst_strength}"
                )
            elif daily_context.get('reversal', {}).get('is_reversal', False):
                # Reversal mode - relaxed requirements
                completion += 25.0
                self.logger.debug(f"📊 {symbol}: Reversal relaxed (50%)")
            else:
                return completion

            # Stage 3: Daily context + VWAP (75%)
            if not skip_daily and not daily_context['is_safe']:
                self.logger.debug(
                    f"📊 {symbol}: Daily context unsafe - {daily_context['reason']}"
                )
                return completion

            # Get VWAP from bars_history if available
            bars = self.get_bars_from_opportunity(opportunity)
            vwap_price = self.calculate_vwap_from_bars(bars) if bars else None

            if vwap_price:
                vwap_threshold = vwap_price * config['vwap_tolerance']  # Aplicar tolerancia
                if current_price >= vwap_threshold:
                    # Price holding above VWAP = catalyst showing strength
                    completion += 25.0
                    self.logger.debug(
                        f"📊 {symbol}: Safe context + VWAP (75%) - "
                        f"${current_price:.2f} >= ${vwap_threshold:.2f} (tolerance: {config['vwap_tolerance']})"
                    )
                else:
                    # VWAP check fallido - reducir completion
                    completion += 15.0
                    self.logger.debug(
                        f"📊 {symbol}: Safe context (65%) - below VWAP threshold "
                        f"${current_price:.2f} < ${vwap_threshold:.2f}"
                    )
                    return completion
            else:
                # No VWAP data - still add partial completion
                completion += 20.0
                self.logger.debug(f"📊 {symbol}: Safe context (70%) - no VWAP data")

            # Stage 4: CONTROLLED vs PARABOLIC MOVE (85-100%)
            # Detect if catalyst reacting normally (early) or parabolic (late)

            # Check gap magnitude:
            # - Gap 0-10% = controlled reaction (EARLY ENTRY)
            # - Gap > 15% = parabolic move (LATE, too extended)

            if gap_pct <= 10.0:
                # Controlled reaction - early entry window
                completion += 10.0
                self.logger.debug(
                    f"📊 {symbol}: CONTROLLED REACTION (85%) - gap {gap_pct:.1f}% not parabolic"
                )
            else:
                # Parabolic move - catalyst fully priced in, too late
                completion = 100.0
                self.logger.info(
                    f"🔥 {symbol}: PARABOLIC CATALYST MOVE - gap {gap_pct:.1f}% extended (100%)"
                )
                return completion

            # Final pattern state logging
            self.logger.info(
                f"📊 {symbol}: Daily Plays pattern = {completion:.0f}% "
                f"(catalyst={catalyst_type}, gap={gap_pct:.1f}%, "
                f"price=${current_price:.2f}, VWAP=${vwap_price:.2f if vwap_price else 'N/A'})"
            )

            return completion

        except Exception as e:
            self.logger.error(f"❌ Error calculating catalyst pattern completion: {e}")
            return 0.0

    async def should_enter(self, opportunity: Dict[str, Any]) -> bool:
        """
        Evalúa si debe entrar según criterios Daily Plays

        MODO DUAL:
        - Momentum Runners: Entrada inmediata con criterios simplificados
        - Catalyst Plays: Early entry strategy tradicional

        Args:
            opportunity: Datos de la oportunidad del scanner

        Returns:
            True si cumple criterios, False si no
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Get appropriate config for this opportunity
            config = self._get_config_for_opportunity(opportunity)
            is_runner = self._detect_momentum_runner(opportunity)

            # Calculate pattern completion percentage
            completion = await self.calculate_pattern_completion(opportunity)

            # Different logic for runners vs catalyst plays
            if is_runner:
                # MOMENTUM RUNNERS: More aggressive entry
                min_completion = 75.0  # Standard for runners
                max_completion = 100.0  # Allow higher completion for runners

                if completion < min_completion:
                    self.logger.debug(
                        f"⏳ {symbol}: Runner pattern not ready - {completion:.0f}% < {min_completion:.0f}%"
                    )
                    return False

                self.logger.info(
                    f"🚀 {symbol}: MOMENTUM RUNNER ENTRY - Pattern {completion:.0f}% complete"
                )
                return True

            else:
                # CATALYST PLAYS: Traditional early entry
                # EARLY ENTRY LOGIC:
                # - 0-74%: Pattern not ready, reject
                # - 75-95%: OPTIMAL entry window (catalyst aligning, volume building)
                # - 96-100%: Too late, breakout complete

                if completion < 75.0:
                    self.logger.debug(
                        f"⏳ {symbol}: Pattern not ready - {completion:.0f}% < 75% (waiting for catalyst alignment)"
                    )
                    return False

                if completion > 95.0:
                    self.logger.warning(
                        f"⚠️ {symbol}: Pattern too complete - {completion:.0f}% > 95% (too late, breakout done)"
                    )
                    return False

                # OPTIMAL ENTRY WINDOW: 75-95%
                self.logger.info(
                    f"✅ {symbol}: EARLY ENTRY APPROVED - Pattern {completion:.0f}% complete "
                    f"(entering BEFORE full breakout)"
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
        Evalúa si debe salir de posición según criterios Daily Plays

        MODO DUAL: Usa configuración diferente para momentum runners vs catalyst plays

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

            # Get position type and appropriate stop config
            position_type = self.position_types.get(symbol, 'catalyst')
            stop_config = (self.runner_stop_config if position_type == 'runner'
                          else self.catalyst_stop_config)

            # Create dynamic stop manager for this position
            from .worker_stop_manager import WorkerStopManager, WorkerStopConfig
            dynamic_stop_manager = WorkerStopManager(WorkerStopConfig(**stop_config))

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

            # Check quick target for momentum runners (custom logic)
            if position_type == 'runner' and stop_config.get('quick_target_pct'):
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                if pnl_pct >= stop_config['quick_target_pct']:
                    # Check if it's a fast move (within 2 hours)
                    if self._is_fast_move(symbol, pnl_pct):
                        self.logger.info(f"🚀 {symbol}: QUICK TARGET {stop_config['quick_target_pct']}% hit - Fast runner exit")
                        return True, f"QUICK_TARGET_{stop_config['quick_target_pct']}% (Fast momentum capture)"

            # Use dynamic stop manager to check exit conditions
            should_exit, reason = dynamic_stop_manager.check_exit(
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
        """Override to register position with stop manager and track position type"""
        # Execute normal entry
        success = await super()._execute_entry(opportunity)

        if success:
            # Register position with stop manager for tracking
            from datetime import datetime
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Track position type for dynamic exit logic
            is_runner = self._detect_momentum_runner(opportunity)
            self.position_types[symbol] = 'runner' if is_runner else 'catalyst'

            self.stop_manager.register_position(symbol, datetime.now())
            self.logger.debug(f"📝 Registered {symbol} ({'runner' if is_runner else 'catalyst'}) with stop manager")

        return success

    async def _execute_exit(self, symbol: str, reason: str, current_price: float):
        """Override to unregister position from stop manager and clean up tracking"""
        # Unregister from stop manager
        self.stop_manager.unregister_position(symbol)

        # Clean up position type tracking
        self.position_types.pop(symbol, None)

        # Execute normal exit
        await super()._execute_exit(symbol, reason, current_price)

    async def _check_daily_context(self, symbol: str, current_price: float, skip_checks: bool = False) -> Dict[str, Any]:
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
            skip_checks: Si True, skip daily context checks (para momentum runners)

        Returns:
            Dict con resultado del análisis
        """
        # MOMENTUM RUNNERS: Skip daily context checks
        if skip_checks:
            return {
                'is_safe': True,
                'reason': 'Momentum runner - daily checks skipped',
                'daily_rsi': 50.0,
                'consecutive_up_days': 0,
                'distance_to_resistance_pct': 10.0  # Safe distance
            }
        try:
            # Obtener barras diarias (últimos 30 días)
            from ib_insync import Stock
            contract = Stock(symbol, 'SMART', 'USD')

            daily_bars = await self.execution_engine.broker.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='30 D',
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

            # ===================================================================
            # CHECK 1: RSI Daily - Detectar sobrecompra extrema
            # ===================================================================
            rsi_daily = self._calculate_rsi(closes, period=14)
            if rsi_daily > 70:
                return {
                    'is_safe': False,
                    'reason': f'Daily RSI overbought: {rsi_daily:.1f} > 70 (exhaustion risk)',
                    'daily_rsi': rsi_daily
                }

            # ===================================================================
            # CHECK 2: MACD Daily - Detectar sobrecompra extrema
            # ===================================================================
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

            # ===================================================================
            # CHECK 3: Resistencia histórica cercana
            # ===================================================================
            resistance_30d = max(highs)
            distance_to_resistance = ((resistance_30d - current_price) / current_price) * 100

            if distance_to_resistance < 2.0:  # Menos de 2% de distancia a máximo
                return {
                    'is_safe': False,
                    'reason': f'Too close to 30-day resistance: ${resistance_30d:.2f} (distance: {distance_to_resistance:.1f}%)',
                    'resistance': resistance_30d,
                    'distance_to_resistance_pct': distance_to_resistance
                }

            # ===================================================================
            # CHECK 4: Días consecutivos alcistas (agotamiento)
            # ===================================================================
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

            # ===================================================================
            # CHECK 5: Distribución institucional
            # ===================================================================
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

            # ===================================================================
            # REVERSAL MODE: Detectar setups de reversión alcista
            # ===================================================================
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

            # ===================================================================
            # ✅ TODOS LOS CHECKS PASADOS
            # ===================================================================
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