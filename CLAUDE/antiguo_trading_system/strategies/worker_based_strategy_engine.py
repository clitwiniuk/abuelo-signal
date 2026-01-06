"""
Worker-Based Strategy Engine
Orquestador de workers lógicos para procesamiento paralelo de estrategias
Reemplaza SimpleStrategyEngine con arquitectura de workers asíncronos

ENHANCED WITH TRADE ARBITER & CONTEXT ENGINE:
- Analyzes market context before worker routing
- Coordinates multiple workers competing for same ticker
- Selects best signal based on context + quality scoring
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import workers
from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
from strategies.workers.orb_worker_logic import ORBWorkerLogic
from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic
from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
from strategies.workers.generic_01_worker_logic import Generic01WorkerLogic
from strategies.workers.smallcaps_long_worker_logic import SmallCapsLongWorkerLogic
from strategies.workers.outlier_penny_extreme_worker_logic import OutlierPennyExtremeWorkerLogic
from strategies.workers.ods_universal_worker_logic import ODSUniversalWorkerLogic
from strategies.workers.ods_swing_universal_worker_logic import ODSSwingUniversalWorkerLogic
from strategies.workers.balance_day_worker_logic import BalanceDayWorkerLogic

# Trade Arbiter System (Context-Aware Worker Coordination)
from core.context_engine import get_context_engine, ContextAnalysis
from core.trade_arbiter import get_trade_arbiter
from core.worker_capabilities_config import register_all_workers


class WorkerBasedStrategyEngine:
    """
    Engine que orquesta múltiples workers lógicos

    Responsabilidades:
    - Iniciar workers como async tasks
    - Recibir oportunidades del scanner
    - Rutear oportunidades a workers relevantes
    - Coordinar evaluación paralela
    - Monitorear estado de workers

    Workers NO son procesos separados, son async tasks que:
    - Comparten ExecutionEngine
    - Comparten RiskManager
    - Gestionan sus propias posiciones
    - Evalúan en paralelo
    """

    def __init__(
        self,
        execution_engine: Any,
        risk_manager: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Inicializa worker-based engine

        Args:
            execution_engine: ExecutionEngine compartido
            risk_manager: RiskManager compartido
            config: Configuración opcional
        """
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager

        # Get config from execution_engine if available, otherwise use provided config
        if hasattr(execution_engine, 'config') and execution_engine.config:
            self.config = execution_engine.config
        else:
            self.config = config or {}

        self.logger = logging.getLogger("WorkerBasedEngine")

        # Workers disponibles
        self.workers: Dict[str, Any] = {}

        # Tasks de workers
        self.worker_tasks: List[asyncio.Task] = []

        # Estado
        self.is_running = False

        # Trade Arbiter System (Context-Aware Coordination)
        self.context_engine = get_context_engine()
        self.trade_arbiter = get_trade_arbiter()
        self.arbiter_enabled = True  # Can be disabled for legacy mode

        # Performance metrics
        self.metrics = {
            'opportunities_processed': 0,
            'opportunities_matched': 0,
            'opportunities_rejected': 0,
            'context_analyzed': 0,
            'arbiter_selected': 0,
            'arbiter_rejected': 0,
            'total_processing_time': 0.0,
            'avg_processing_time': 0.0,
            'worker_matches': {},  # {worker_name: count}
            'worker_entries': {},  # {worker_name: count}
            'context_distribution': {},  # {context_type: count}
        }

        self.logger.info("🏗️ Worker-Based Strategy Engine initialized (with Trade Arbiter)")


    async def initialize(self):
        """
        Inicializa y crea workers

        Phase 1: Gap-Go (DISABLED - no ha operado últimamente)
        Phase 2: MACDV
        Phase 3: DailyPlays + BullFlag (BullFlag DISABLED - patrones raros)
        Phase 4: VWAP Breakout
        Phase 5: Momentum Breakout (NEW)
        """
        self.logger.info("🔧 Initializing workers...")

        try:
            # Worker 1: Gap-Go (PHASE 1) - DISABLED (no ha operado últimamente)
            # self.workers['gap_go'] = GapGoWorkerLogic(
            #     execution_engine=self.execution_engine,
            #     risk_manager=self.risk_manager,
            #     config=self.config
            # )
            # self.logger.info("✅ Gap-Go worker created")

            # Worker 2: MACDV (PHASE 2)
            # UnifiedConfig doesn't have getboolean, use direct attribute access
            macdv_enabled = getattr(self.config, 'macdv_strategy_enabled', True)
            if macdv_enabled:
                self.workers['macdv'] = MacdvWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ MACDV worker created")
            else:
                self.logger.info("⏸️  MACDV worker DISABLED in config")

            # Worker 3: Daily Plays (PHASE 3 - NEW)
            daily_plays_enabled = getattr(self.config, 'daily_plays_strategy_enabled', True)
            if daily_plays_enabled:
                self.workers['daily_plays'] = DailyPlaysWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Daily Plays worker created")
            else:
                self.logger.info("⏸️  Daily Plays worker DISABLED in config")

            # Worker 3.5: ORB (Opening Range Breakout) - CRITICAL WORKER
            orb_enabled = getattr(self.config, 'orb_strategy_enabled', True)
            if orb_enabled:
                self.workers['orb_breakout'] = ORBWorkerLogic(
                    worker_name='orb_breakout',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager
                )
                self.logger.info("✅ ORB Breakout worker created (65-70% win rate)")
            else:
                self.logger.info("⏸️  ORB Breakout worker DISABLED in config")

            # Worker 4: Bull Flag (PHASE 3 - NEW) - DISABLED (patrones raros, máquina de estados compleja)
            # self.workers['bull_flag'] = BullFlagWorkerLogic(
            #     execution_engine=self.execution_engine,
            #     risk_manager=self.risk_manager,
            #     config=self.config
            # )
            # self.logger.info("✅ Bull Flag worker created")

            # Worker 5: VWAP Breakout (PHASE 4 - NEW)
            vwap_enabled = getattr(self.config, 'vwap_breakout_strategy_enabled', True)
            if vwap_enabled:
                self.workers['vwap_breakout'] = VWAPWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VWAP Breakout worker created")
            else:
                self.logger.info("⏸️  VWAP Breakout worker DISABLED in config")

            # Worker 6: Momentum Breakout (PHASE 5 - NEW)
            momentum_enabled = getattr(self.config, 'momentum_breakout_strategy_enabled', True)
            if momentum_enabled:
                self.workers['momentum_breakout'] = MomentumBreakoutWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Momentum Breakout worker created")
            else:
                self.logger.info("⏸️  Momentum Breakout worker DISABLED in config")

            # Worker 7: VCP Smallcap (Volatility Contraction Pattern for smallcaps)
            vcp_enabled = getattr(self.config, 'vcp_strategy_enabled', True)
            if vcp_enabled:
                self.workers['vcp_smallcap'] = VCPSmallcapWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VCP Smallcap worker created")
            else:
                self.logger.info("⏸️  VCP Smallcap worker DISABLED in config")

            # Worker 8: Volume Absorption Breakout (Scanner-Assisted)
            volume_absorption_enabled = getattr(self.config, 'volume_absorption_worker_enabled', True)
            if volume_absorption_enabled:
                self.workers['volume_absorption'] = VolumeAbsorptionWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Volume Absorption worker created")
            else:
                self.logger.info("⏸️  Volume Absorption worker DISABLED in config")

            # Worker 9: GENERIC_01 - Low Volume Accumulation (41.04% Edge)
            generic01_enabled = getattr(self.config, 'generic_01_strategy_enabled', True)
            if generic01_enabled:
                self.workers['generic_01'] = Generic01WorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ GENERIC_01 worker created (41.04% edge)")
            else:
                self.logger.info("⏸️  GENERIC_01 worker DISABLED in config")

            # Worker 10: Small Caps Long - Rule-based smallcap strategy (17.64% edge)
            smallcaps_enabled = getattr(self.config, 'smallcaps_long_strategy_enabled', True)
            if smallcaps_enabled:
                self.workers['smallcaps_long'] = SmallCapsLongWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Small Caps Long worker created (17.64% edge)")
            else:
                self.logger.info("⏸️  Small Caps Long worker DISABLED in config")

            # Worker 11: Outlier Penny Extreme - Penny stock outlier hunter (11.69% edge, EXTREME RISK)
            outlier_enabled = getattr(self.config, 'outlier_penny_extreme_strategy_enabled', True)
            if outlier_enabled:
                self.workers['outlier_penny_extreme'] = OutlierPennyExtremeWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Outlier Penny Extreme worker created (11.69% edge, 1% MAX position size)")
            else:
                self.logger.info("⏸️  Outlier Penny Extreme worker DISABLED in config")

            # Worker 12: ODS Universal - Pattern-driven worker (ARCHITECTURAL DECOUPLING)
            ods_universal_enabled = getattr(self.config, 'ods_universal_strategy_enabled', True)
            if ods_universal_enabled:
                self.workers['ods_universal'] = ODSUniversalWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ ODS Universal worker created (Pattern-Driven Architecture)")
            else:
                self.logger.info("⏸️  ODS Universal worker DISABLED in config")

            # Worker 13: ODS Swing Universal - Pattern-driven multiday swing worker
            ods_swing_enabled = getattr(self.config, 'ods_swing_universal_strategy_enabled', True)
            if ods_swing_enabled:
                self.workers['ods_swing_universal'] = ODSSwingUniversalWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ ODS Swing Universal worker created (Multiday Pattern-Driven, 1-7 days hold)")
            else:
                self.logger.info("⏸️  ODS Swing Universal worker DISABLED in config")

            # Worker 14: Balance Day - Range trading for balance days
            balance_day_enabled = getattr(self.config, 'balance_day_strategy_enabled', True)
            if balance_day_enabled:
                self.workers['balance_day'] = BalanceDayWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Balance Day worker created (Range Trading for Balance Days)")
            else:
                self.logger.info("⏸️  Balance Day worker DISABLED in config")

            self.logger.info(f"✅ {len(self.workers)} workers initialized")

            # Register workers with Trade Arbiter
            if self.arbiter_enabled:
                self.logger.info("📝 Registering workers with Trade Arbiter...")
                register_all_workers(self.trade_arbiter)
                self.logger.info("✅ All workers registered with Trade Arbiter")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error initializing workers: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def start(self):
        """
        Inicia todos los workers como async tasks

        Cada worker corre su loop de monitoreo en background
        """
        self.logger.info("🚀 Starting worker-based strategy engine...")

        try:
            # Inicializar workers si no se ha hecho
            if not self.workers:
                await self.initialize()

            # Iniciar cada worker como async task
            for name, worker in self.workers.items():
                task = asyncio.create_task(
                    worker.run(),
                    name=f"worker_{name}"
                )
                self.worker_tasks.append(task)
                self.logger.info(f"✅ Worker {name} task started")

            self.is_running = True
            self.logger.info(
                f"🎯 Worker-Based Engine running with {len(self.workers)} workers"
            )

        except Exception as e:
            self.logger.error(f"❌ Error starting workers: {e}")
            raise

    async def process_opportunity(self, opportunity: Dict[str, Any]):
        """
        Procesa oportunidad del scanner

        Flujo:
        1. Verifica si estamos en extended hours y si está habilitado
        2. Determina qué workers son relevantes
        3. Envía oportunidad a workers relevantes en paralelo
        4. Workers evalúan y ejecutan si cumplen criterios

        Args:
            opportunity: Dict con datos de oportunidad del scanner
        """
        start_time = datetime.now()

        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')

            # Métricas
            self.metrics['opportunities_processed'] += 1

            # EXTENDED HOURS CHECK: Verificar si podemos operar en extended hours
            if not self._is_extended_hours_allowed(symbol):
                self.metrics['opportunities_rejected'] += 1
                return

            # ================================================================
            # STEP 1: ANALYZE MARKET CONTEXT (Context Engine)
            # ================================================================
            context = None
            if self.arbiter_enabled:
                # Prepare ticker data for context analysis
                ticker_data = {
                    'symbol': symbol,
                    'bars': opportunity.get('bars_history', []),
                    'catalyst_type': opportunity.get('catalyst_type'),
                    'current_price': opportunity.get('current_price', 0),
                    'quality_score': opportunity.get('quality_score', 0),
                }

                # Analyze context
                context = self.context_engine.detect_context(ticker_data)
                self.metrics['context_analyzed'] += 1
                self.metrics['context_distribution'][context.context.value] = \
                    self.metrics['context_distribution'].get(context.context.value, 0) + 1

                self.logger.info(f"🧠 {symbol}: {context}")

                # Check if ticker is locked
                if self.trade_arbiter.is_ticker_locked(symbol):
                    self.logger.warning(f"🔒 {symbol}: Ticker locked, skipping")
                    self.metrics['opportunities_rejected'] += 1
                    return

            # Determinar workers relevantes (context-aware if enabled)
            if self.arbiter_enabled and context:
                # Filter workers by context compatibility
                from core.worker_capabilities_config import WORKER_CAPABILITIES
                relevant_workers = [
                    name for name, caps in WORKER_CAPABILITIES.items()
                    if caps.is_compatible(context.context) and name in self.workers
                ]

                if not relevant_workers:
                    self.logger.info(
                        f"⚪ {symbol}: No workers compatible with context {context.context.value}"
                    )
                    self.metrics['opportunities_rejected'] += 1
                    return

                self.logger.info(
                    f"🎯 {symbol}: {len(relevant_workers)} context-compatible workers: {relevant_workers}"
                )
            else:
                # Legacy mode: use pattern matching
                relevant_workers = self._match_workers(opportunity)

            if not relevant_workers:
                self.logger.debug(f"⚪ {symbol}: No relevant workers matched")
                self.metrics['opportunities_rejected'] += 1
                return

            # Actualizar métricas de matching
            self.metrics['opportunities_matched'] += 1
            for worker_name in relevant_workers:
                self.metrics['worker_matches'][worker_name] = \
                    self.metrics['worker_matches'].get(worker_name, 0) + 1

            self.logger.info(
                f"🎯 {symbol}: Routing to workers: {relevant_workers}"
            )

            # Procesar en paralelo con workers relevantes
            tasks = [
                self.workers[worker_name].process_opportunity(opportunity)
                for worker_name in relevant_workers
                if worker_name in self.workers
            ]

            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log resultados y métricas con más detalle
            for worker_name, result in zip(relevant_workers, results):
                if isinstance(result, Exception):
                    self.logger.error(
                        f"❌ {symbol}: Worker {worker_name} failed: {result}"
                    )
                elif result:
                    self.logger.info(
                        f"✅ {symbol}: Worker {worker_name} ENTERED POSITION - Opportunity executed!"
                    )
                    # Actualizar métrica de entries
                    self.metrics['worker_entries'][worker_name] = \
                        self.metrics['worker_entries'].get(worker_name, 0) + 1

                    # Lock ticker in Trade Arbiter (prevent duplicate entries)
                    if self.arbiter_enabled:
                        self.trade_arbiter.lock_ticker(symbol)
                else:
                    # Enhanced rejection logging - collect reasons from all workers
                    rejection_reasons = self._collect_worker_rejection_reasons(symbol, worker_name)
                    reason_str = f" | {rejection_reasons}" if rejection_reasons else ""
                    self.logger.info(
                        f"⚪ {symbol}: Worker {worker_name} evaluated but did NOT enter - Opportunity rejected{reason_str}"
                    )

        except Exception as e:
            self.logger.error(f"❌ Error processing opportunity: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            # Actualizar métricas de tiempo
            elapsed = (datetime.now() - start_time).total_seconds()
            self.metrics['total_processing_time'] += elapsed
            self.metrics['avg_processing_time'] = \
                self.metrics['total_processing_time'] / max(1, self.metrics['opportunities_processed'])

    def _match_workers(self, opportunity: Dict[str, Any]) -> List[str]:
        """
        UNIVERSAL ROUTING: Envía todas las oportunidades a todos los workers

        Filosofía:
        - No podemos decidir si usar Gap-Go vs Bull Flag solo por gap % o volumen
        - Cada worker debe analizar el patrón completo y decidir si aplica
        - Los workers son responsables de detectar su patrón específico

        Ventajas:
        - Workers analizan patrones completos, no métricas simples
        - No perdemos oportunidades por pre-filtros incorrectos
        - Cada worker decide basado en su expertise

        Early Entry Strategy:
        - Workers deben detectar patrones al 80% de completitud
        - Entrar ANTES de que el patrón se complete al 100%
        - Evitar llegar tarde al movimiento

        Args:
            opportunity: Datos de oportunidad

        Returns:
            Lista de todos los workers (universal routing)
        """
        try:
            symbol = opportunity.get('symbol', 'UNKNOWN')
            gap = abs(opportunity.get('gap_percentage', 0))
            volume_ratio = opportunity.get('volume_ratio', 0)
            catalyst_type = opportunity.get('catalyst_type', '')
            quality_score = opportunity.get('quality_score', 0)
            current_price = opportunity.get('current_price', 0)

            # Log opportunity metrics
            self.logger.debug(
                f"📊 {symbol} routing to ALL workers: "
                f"gap={gap:.1f}%, vol={volume_ratio:.1f}x, "
                f"catalyst={catalyst_type}, Q={quality_score:.1f}, "
                f"price=${current_price:.2f}"
            )

            # UNIVERSAL ROUTING: Todos los workers reciben todas las oportunidades
            # Cada worker decide si el patrón aplica basado en análisis completo
            workers = ['macdv', 'daily_plays', 'vwap_breakout', 'momentum_breakout', 'vcp_smallcap', 'balance_day', 'smallcaps_long', 'outlier_penny_extreme']

            self.logger.debug(
                f"🎯 {symbol}: Universal routing → {len(workers)} workers will analyze"
            )

            return workers

        except Exception as e:
            self.logger.error(f"❌ Error in universal routing: {e}")
            # Fallback: Still route to all workers (including new ones)
            return ['macdv', 'daily_plays', 'vwap_breakout', 'momentum_breakout', 'vcp_smallcap', 'balance_day', 'volume_absorption', 'generic_01', 'smallcaps_long', 'outlier_penny_extreme']

    def get_worker_status(self) -> Dict[str, Any]:
        """
        Obtiene estado de todos los workers

        Returns:
            Dict con estado de cada worker
        """
        status = {}

        for name, worker in self.workers.items():
            status[name] = {
                'active_positions': worker.get_active_positions_count(),
                'symbols': worker.get_active_symbols(),
                'is_running': worker.is_running
            }

        return status

    def log_status(self):
        """Log periódico del estado del engine"""
        try:
            status = self.get_worker_status()

            total_positions = sum(
                s['active_positions'] for s in status.values()
            )

            self.logger.info(
                f"📊 Engine Status: {len(self.workers)} workers, "
                f"{total_positions} total positions"
            )

            for name, worker_status in status.items():
                if worker_status['active_positions'] > 0:
                    self.logger.info(
                        f"   🔸 {name}: {worker_status['active_positions']} positions "
                        f"({', '.join(worker_status['symbols'])})"
                    )

            # Log performance metrics
            self.logger.info(
                f"📈 Performance Metrics: "
                f"Processed={self.metrics['opportunities_processed']}, "
                f"Matched={self.metrics['opportunities_matched']}, "
                f"Rejected={self.metrics['opportunities_rejected']}, "
                f"Avg Time={self.metrics['avg_processing_time']*1000:.2f}ms"
            )

            # Log worker-specific metrics
            if self.metrics['worker_matches']:
                self.logger.info("   Worker Matches: " +
                    ", ".join(f"{name}={count}"
                              for name, count in self.metrics['worker_matches'].items()))

            if self.metrics['worker_entries']:
                self.logger.info("   Worker Entries: " +
                    ", ".join(f"{name}={count}"
                              for name, count in self.metrics['worker_entries'].items()))

        except Exception as e:
            self.logger.error(f"❌ Error logging status: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de performance del engine

        Returns:
            Dict con métricas actuales
        """
        return self.metrics.copy()

    async def stop(self):
        """
        Detiene todos los workers y limpia recursos
        """
        self.logger.info("🛑 Stopping worker-based engine...")

        try:
            self.is_running = False

            # Detener workers
            stop_tasks = []
            for name, worker in self.workers.items():
                self.logger.info(f"🛑 Stopping worker {name}...")
                stop_tasks.append(worker.stop())

            # Esperar a que todos los workers se detengan
            await asyncio.gather(*stop_tasks, return_exceptions=True)

            # Cancelar tasks
            for task in self.worker_tasks:
                if not task.done():
                    task.cancel()

            # Esperar cancelación
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

            self.logger.info("✅ All workers stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping workers: {e}")

    async def analyze(self, symbol: str, data: Any) -> List[Any]:
        """
        Compatibilidad con interfaz antigua (SimpleStrategyEngine)

        DEPRECATED: Usar process_opportunity() en su lugar
        Este método existe solo para compatibilidad durante migración
        """
        self.logger.warning(
            "⚠️ analyze() is deprecated, use process_opportunity() instead"
        )

        # Convertir a formato opportunity
        opportunity = {
            'symbol': symbol,
            'current_price': getattr(data, 'close', 0),
            'gap_percentage': 0,  # TODO: Calcular del data
            'volume_ratio': 1.0,   # TODO: Calcular del data
            'catalyst_type': '',
            'quality_score': 50.0,
            'scan_timestamp': datetime.now().isoformat()
        }

        await self.process_opportunity(opportunity)
        return []  # No retorna signals, ejecuta directamente

    def _collect_worker_rejection_reasons(self, symbol: str, worker_name: str) -> str:
        """
        Collects rejection reasons from recent logs for a specific symbol and worker

        This is a simple implementation that looks for recent rejection patterns
        in the logs. A more sophisticated approach would be to have workers
        return structured rejection reasons.

        Args:
            symbol: The symbol that was rejected
            worker_name: The worker that rejected it

        Returns:
            String with rejection reasons or empty string if none found
        """
        try:
            # This is a placeholder - in a real implementation, workers would
            # return structured rejection data. For now, we'll return a generic message
            # indicating that detailed reasons are logged separately
            return "See detailed logs above for specific rejection criteria"
        except Exception:
            return ""

    def _is_extended_hours_allowed(self, symbol: str) -> bool:
        """
        Verifica si está permitido operar en extended hours para este símbolo

        Returns:
            True si está permitido, False si no
        """
        try:
            # Support both dict and object config formats
            if isinstance(self.config, dict):
                extended_hours_enabled = self.config.get('enable_extended_hours_trading', False)
                allow_premarket = self.config.get('allow_premarket_entries', False)
                allow_afterhours = self.config.get('allow_afterhours_entries', False)
            else:
                # Object with attributes (UnifiedConfig)
                extended_hours_enabled = getattr(self.config, 'enable_extended_hours_trading', False)
                allow_premarket = getattr(self.config, 'allow_premarket_entries', False)
                allow_afterhours = getattr(self.config, 'allow_afterhours_entries', False)

            # Si extended hours está habilitado globalmente, permitir todo
            if extended_hours_enabled:
                return True

            # Si extended hours no está habilitado globalmente, verificar sesiones específicas
            from core.extended_hours_manager import ExtendedHoursManager
            extended_manager = ExtendedHoursManager()
            current_session = extended_manager.get_market_session()

            if current_session.name in ['PREMARKET', 'AFTERHOURS']:
                # Permitir premarket si está habilitado específicamente
                if current_session.name == 'PREMARKET' and allow_premarket:
                    self.logger.info(
                        f"✅ {symbol}: Premarket trading ALLOWED - "
                        f"Current session: {current_session.name}"
                    )
                    return True
                # Permitir afterhours si está habilitado específicamente
                elif current_session.name == 'AFTERHOURS' and allow_afterhours:
                    self.logger.info(
                        f"✅ {symbol}: Afterhours trading ALLOWED - "
                        f"Current session: {current_session.name}"
                    )
                    return True
                else:
                    self.logger.info(
                        f"🚫 {symbol}: Extended hours trading DISABLED - "
                        f"Current session: {current_session.name}"
                    )
                    return False

            # Estamos en regular hours, permitir
            return True

        except Exception as e:
            self.logger.error(f"❌ Error checking extended hours for {symbol}: {e}")
            return False