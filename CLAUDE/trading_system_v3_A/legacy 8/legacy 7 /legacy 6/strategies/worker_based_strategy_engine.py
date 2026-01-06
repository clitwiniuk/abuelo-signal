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

# Import workers (only existing files)
# from strategies.workers.macdv_worker_logic import MacdvWorkerLogic  # REMOVED - no longer used
from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
from strategies.workers.daily_plays_midcap_worker_logic import DailyPlaysMidCapWorkerLogic
from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
# from strategies.workers.momentum_breakout_worker_logic import MomentumBreakoutWorkerLogic  # REPLACED by Livermore
from strategies.workers.livermore_intraday_worker_logic import LivermoreIntradayWorkerLogic
from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
from strategies.workers.vcp_strict_long_worker_logic import VCPStrictLongWorkerLogic
from strategies.workers.vcp_strict_short_worker_logic import VCPStrictShortWorkerLogic
from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
from strategies.workers.buy_the_dip_worker_logic import BuyTheDipWorkerLogic
from strategies.workers.buy_and_hold_worker_logic import BuyAndHoldWorkerLogic
from strategies.workers.generic_01_worker_logic import Generic01WorkerLogic
from strategies.workers.parabolic_worker_logic import ParabolicWorkerLogic
from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic
from strategies.workers.gap_fade_worker_logic import GapFadeWorkerLogic
# from strategies.workers.smallcap_momentum_scalper_logic import SmallcapMomentumScalperLogic

# ORB Worker (Opening Range Breakout)
from strategies.workers.orb_worker_logic import ORBWorkerLogic
# from strategies.workers.smallcaps_long_worker_logic import SmallCapsLongWorkerLogic
# from strategies.workers.outlier_penny_extreme_worker_logic import OutlierPennyExtremeWorkerLogic
# from strategies.workers.ods_universal_worker_logic import ODSUniversalWorkerLogic
from strategies.workers.ods_swing_universal_worker_logic import ODSSwingUniversalWorkerLogic
from strategies.workers.holy_grail_worker_logic import HolyGrailWorkerLogic
from strategies.workers.short_squeeze_worker_logic import ShortSqueezeWorkerLogic
from strategies.workers.catalyst_dna_worker_logic import CatalystDNAWorkerLogic
# from strategies.workers.balance_day_worker_logic import BalanceDayWorkerLogic

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

        # Load config.ini as ConfigParser for workers that need it (v2.0 refactored workers)
        import configparser
        import os
        self.config_parser = configparser.ConfigParser()
        config_ini_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
        if os.path.exists(config_ini_path):
            self.config_parser.read(config_ini_path)
            self.logger.info(f"✅ Loaded config.ini for refactored workers from {config_ini_path}")
        else:
            self.logger.warning(f"⚠️ config.ini not found at {config_ini_path} - workers will use fallbacks")

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

            # Worker 2: MACDV (PHASE 2) - LEGACY/DISABLED
            # PERMANENTLY DISABLED - Legacy worker, no longer in use
            # macdv_enabled = getattr(self.config, 'macdv_strategy_enabled', True)
            # if macdv_enabled:
            #     self.workers['macdv'] = MacdvWorkerLogic(
            #         execution_engine=self.execution_engine,
            #         risk_manager=self.risk_manager,
            #         config=self.config
            #     )
            #     self.logger.info("✅ MACDV worker created")
            # else:
            #     self.logger.info("⏸️  MACDV worker DISABLED in config")
            self.logger.info("⏸️  MACDV worker PERMANENTLY DISABLED (legacy)")

            # Worker 3: Daily Plays (PHASE 3 - NEW) - REFACTORED v2.0
            daily_plays_enabled = getattr(self.config, 'daily_plays_strategy_enabled', True)
            if daily_plays_enabled:
                self.workers['daily_plays'] = DailyPlaysWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config_parser  # NOW PASSING ConfigParser (v2.0 refactored)
                )
                self.logger.info("✅ Daily Plays worker created (v2.0 - REFACTORED with config)")
            else:
                self.logger.info("⏸️  Daily Plays worker DISABLED in config")

            # Worker 3.1: Daily Plays Mid-Cap (v2.0 - REFACTORED)
            daily_plays_midcap_enabled = getattr(self.config, 'daily_plays_midcap_strategy_enabled', True)
            if daily_plays_midcap_enabled:
                self.workers['daily_plays_midcap'] = DailyPlaysMidCapWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config_parser
                )
                self.logger.info("✅ Daily Plays Mid-Cap worker created (v2.0 - REFACTORED)")
            else:
                self.logger.info("⏸️  Daily Plays Mid-Cap worker DISABLED in config")

            # Worker 3.5: ORB (Opening Range Breakout) - REFACTORED v2.0
            orb_enabled = getattr(self.config, 'orb_strategy_enabled', True)
            if orb_enabled:
                self.workers['orb_breakout'] = ORBWorkerLogic(
                    worker_name='orb_breakout',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config_parser  # NOW PASSING CONFIG
                )
                self.logger.info("✅ ORB Breakout worker created (v2.0 - REFACTORED with config)")
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
                    worker_name='vwap_breakout',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VWAP Breakout worker created")
            else:
                self.logger.info("⏸️  VWAP Breakout worker DISABLED in config")

            # Worker 6: MOMENTUM BREAKOUT -> REPLACED BY LIVERMORE INTRADAY
            # momentum_enabled = getattr(self.config, 'momentum_breakout_strategy_enabled', True)
            livermore_enabled = getattr(self.config, 'livermore_intraday_strategy_enabled', True)
            
            if livermore_enabled:
                 self.workers['livermore_intraday'] = LivermoreIntradayWorkerLogic(
                     execution_engine=self.execution_engine,
                     risk_manager=self.risk_manager,
                     config=self.config  # Passing config for LIVERMORE_INTRADAY_STRATEGY
                 )
                 self.logger.info("✅ Livermore Intraday worker created (Stateful Event-Driven Strategy)")
            else:
                 self.logger.info("⏸️  Livermore Intraday worker DISABLED in config")

            # if momentum_enabled:
            #     self.workers['momentum_breakout'] = MomentumBreakoutWorkerLogic(
            #         worker_name='momentum_breakout',
            #         execution_engine=self.execution_engine,
            #         risk_manager=self.risk_manager,
            #         config=self.config
            #     )
            #     self.logger.info("✅ Momentum Breakout worker created")
            # else:
            #     self.logger.info("⏸️  Momentum Breakout worker DISABLED in config")

            # Worker 7: VCP Smallcap (Volatility Contraction Pattern for smallcaps)
            vcp_enabled = getattr(self.config, 'vcp_strategy_enabled', True)
            if vcp_enabled:
                self.workers['vcp_smallcap'] = VCPSmallcapWorkerLogic(
                    worker_name='vcp_smallcap',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VCP Smallcap worker created")
            else:
                self.logger.info("⏸️  VCP Smallcap worker DISABLED in config")

            # Worker 7B-1: VCP Strict LONG (Accumulation - Overnight Eligible)
            vcp_strict_long_enabled = getattr(self.config, 'vcp_strict_long_strategy_enabled', True)
            if vcp_strict_long_enabled:
                self.workers['vcp_strict_long'] = VCPStrictLongWorkerLogic(
                    worker_name='vcp_strict_long',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VCP STRICT LONG worker created (Accumulation)")
            else:
                self.logger.info("⏸️  VCP STRICT LONG worker DISABLED in config")

            # Worker 7B-2: VCP Strict SHORT (Distribution - Intraday Only)
            vcp_strict_short_enabled = getattr(self.config, 'vcp_strict_short_strategy_enabled', True)
            if vcp_strict_short_enabled:
                self.workers['vcp_strict_short'] = VCPStrictShortWorkerLogic(
                    worker_name='vcp_strict_short',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ VCP STRICT SHORT worker created (Distribution)")
            else:
                self.logger.info("⏸️  VCP STRICT SHORT worker DISABLED in config")

            # Worker 8: Volume Absorption Breakout (Scanner-Assisted)
            volume_absorption_enabled = getattr(self.config, 'volume_absorption_worker_enabled', True)
            if volume_absorption_enabled:
                self.workers['volume_absorption'] = VolumeAbsorptionWorkerLogic(
                    worker_name='volume_absorption',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Volume Absorption worker created")
            else:
                self.logger.info("⏸️  Volume Absorption worker DISABLED in config")

            # Worker 8.5: Buy The Dip - Dip buying in uptrends (Scanner-Assisted)
            buy_the_dip_enabled = getattr(self.config, 'buy_the_dip_worker_enabled', True)
            if buy_the_dip_enabled:
                self.workers['buy_the_dip'] = BuyTheDipWorkerLogic(
                    worker_name='buy_the_dip',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config_parser  # Passing ConfigParser (v2.0 refactored)
                )
                self.logger.info("✅ Buy The Dip worker created (v2.0 - REFACTORED with config)")
            else:
                self.logger.info("⏸️  Buy The Dip worker DISABLED in config")

            # Worker 8.6: Buy and Hold - Immediate entry on scanner opportunities (Morning Session)
            buy_and_hold_enabled = getattr(self.config, 'buy_and_hold_worker_enabled', True)
            if buy_and_hold_enabled:
                self.workers['buy_and_hold'] = BuyAndHoldWorkerLogic(
                    worker_name='buy_and_hold',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config_parser  # Passing ConfigParser (v2.0 refactored)
                )
                self.logger.info("✅ Buy and Hold worker created (immediate entry on morning opportunities)")
            else:
                self.logger.info("⏸️  Buy and Hold worker DISABLED in config")

            # Worker 8.7: Parabolic Extension - EARLY-stage parabolic acceleration trading
            parabolic_enabled = getattr(self.config, 'parabolic_strategy_enabled', True)
            if parabolic_enabled:
                self.workers['parabolic'] = ParabolicWorkerLogic(
                    worker_name='parabolic',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config  # Passing config for detector + worker parameters
                )
                self.logger.info("✅ Parabolic Extension worker created (EARLY-stage acceleration trading)")
            else:
                self.logger.info("⏸️  Parabolic Extension worker DISABLED in config")

            # Worker 8.8: Short Parabolic - SHORT positions on parabolic exhaustion
            short_parabolic_enabled = getattr(self.config, 'short_parabolic_strategy_enabled', True)
            if short_parabolic_enabled:
                self.workers['short_parabolic'] = ShortParabolicWorkerLogic(
                    worker_name='short_parabolic',
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager,
                    config=self.config
                )
                self.logger.info("✅ Short Parabolic worker created (SHORT parabolic exhaustion)")
            else:
                self.logger.info("⏸️  Short Parabolic worker DISABLED in config")

            # Worker 8.9: Gap Fade - SHORT positions on failed gaps (62-68% win rate)
            gap_fade_enabled = getattr(self.config, 'gap_fade_strategy_enabled', True)
            if gap_fade_enabled:
                self.workers['gap_fade'] = GapFadeWorkerLogic(
                    config=self.config
                )
                self.logger.info("✅ Gap Fade worker created (SHORT gaps without catalyst, 62-68% WR)")
            else:
                self.logger.info("⏸️  Gap Fade worker DISABLED in config")

            # Worker 9: GENERIC_01 - Low Volume Accumulation (41.04% Edge)
            # DISABLED: Poor performance - many breakeven exits and stop losses
            generic01_enabled = False  # getattr(self.config, 'generic_01_strategy_enabled', True)
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
            # Worker 10: Small Caps Long - DISABLED (file missing)
            # smallcaps_enabled = getattr(self.config, 'smallcaps_long_strategy_enabled', True)
            # if smallcaps_enabled:
            #     self.workers['smallcaps_long'] = SmallCapsLongWorkerLogic(...)
            self.logger.info("⏸️  Small Caps Long worker DISABLED (file missing)")

            # Worker 11: Outlier Penny Extreme - DISABLED (file missing)
            # outlier_enabled = getattr(self.config, 'outlier_penny_extreme_strategy_enabled', True)
            # if outlier_enabled:
            #     self.workers['outlier_penny_extreme'] = OutlierPennyExtremeWorkerLogic(...)
            self.logger.info("⏸️  Outlier Penny Extreme worker DISABLED (file missing)")

            # Worker 12: ODS Universal - DISABLED (file missing)
            # ods_universal_enabled = getattr(self.config, 'ods_universal_strategy_enabled', True)
            # if ods_universal_enabled:
            #     self.workers['ods_universal'] = ODSUniversalWorkerLogic(...)
            self.logger.info("⏸️  ODS Universal worker DISABLED (file missing)")

            # Worker 13: ODS Swing Universal
            ods_swing_enabled = getattr(self.config, 'ods_swing_universal_strategy_enabled', True)
            if ods_swing_enabled:
                self.workers['ods_swing_universal'] = ODSSwingUniversalWorkerLogic(
                    execution_engine=self.execution_engine,
                    risk_manager=self.risk_manager
                )
                self.logger.info("✅ ODS Swing Universal worker initialized")
            else:
                self.logger.info("⏸️  ODS Swing Universal worker DISABLED (config)")

            # Worker 14: The Holy Grail (New)
            holy_grail_enabled = getattr(self.config, 'holy_grail_strategy_enabled', True)
            if holy_grail_enabled:
                 self.workers['holy_grail'] = HolyGrailWorkerLogic(
                     execution_engine=self.execution_engine,
                     risk_manager=self.risk_manager,
                     config=self.config
                 )
                 self.logger.info("✅ Holy Grail worker initialized")
            else:
                 self.logger.info("⏸️  Holy Grail worker DISABLED (config)")

            # Worker 16: Short Squeeze - Proactive Scanner Execution
            short_squeeze_enabled = getattr(self.config, 'short_squeeze_strategy_enabled', True)
            if short_squeeze_enabled:
                 self.workers['short_squeeze'] = ShortSqueezeWorkerLogic(
                     execution_engine=self.execution_engine,
                     risk_manager=self.risk_manager,
                     config=self.config_parser
                 )
                 self.logger.info("✅ Short Squeeze worker initialized (Proactive Execution)")
            else:
                 self.logger.info("⏸️  Short Squeeze worker DISABLED (config)")

            # Worker 17: Catalyst DNA - Market DNA adapted for smallcaps (LONG only)
            catalyst_dna_enabled = getattr(self.config, 'catalyst_dna_strategy_enabled', True)
            if catalyst_dna_enabled:
                 self.workers['catalyst_dna'] = CatalystDNAWorkerLogic(
                     worker_name='catalyst_dna',
                     execution_engine=self.execution_engine,
                     risk_manager=self.risk_manager,
                     config=self.config_parser
                 )
                 self.logger.info("✅ Catalyst DNA worker initialized (Market DNA for Smallcaps - LONG)")
            else:
                 self.logger.info("⏸️  Catalyst DNA worker DISABLED (config)")

            # Worker 15: Balance Day - DISABLED (file missing)
            # balance_day_enabled = getattr(self.config, 'balance_day_strategy_enabled', True)
            # if balance_day_enabled:
            #     self.workers['balance_day'] = BalanceDayWorkerLogic(...)
            self.logger.info("⏸️  Balance Day worker DISABLED (file missing)")

            # Worker 15: Smallcap Momentum Scalper - DISABLED (file missing)
            # scalper_enabled = getattr(self.config, 'smallcap_momentum_scalper_enabled', True)
            # if scalper_enabled:
            #     self.workers['smallcap_momentum_scalper'] = SmallcapMomentumScalperLogic(
            #         config=self.config,
            #         logger=self.logger
            #     )
            #     self.logger.info("✅ Smallcap Momentum Scalper worker initialized")
            # else:
            #     self.logger.info("⏸️  Smallcap Momentum Scalper worker DISABLED (config)")
            self.logger.info("⏸️  Smallcap Momentum Scalper worker DISABLED (file missing)")

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
                # Try both 'bars_history' and 'bars' fields (scanner may use different names)
                bars = opportunity.get('bars_history', opportunity.get('bars', []))

                # 🔧 FIX: If bars are missing, fetch them from broker
                if not bars or len(bars) == 0:
                    self.logger.info(f"📊 {symbol}: No bars in opportunity, fetching from broker...")
                    bars = await self._fetch_bars_for_symbol(symbol)
                    # Add fetched bars to opportunity for workers to use
                    opportunity['bars'] = bars
                    if bars:
                        self.logger.info(f"✅ {symbol}: Fetched {len(bars)} bars from broker")
                    else:
                        self.logger.warning(f"⚠️ {symbol}: Could not fetch bars from broker")

                ticker_data = {
                    'symbol': symbol,
                    'bars': bars,
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

            # SMART ROUTING: If opportunity has a specific 'strategy' target, prioritize it
            target_strategy = opportunity.get('strategy')
            if target_strategy and target_strategy in self.workers:
                self.logger.debug(f"🎯 {symbol}: Precised routing to '{target_strategy}'")
                return [target_strategy]

            # UNIVERSAL ROUTING (Fallback): Todos los workers reciben todas las oportunidades
            # Cada worker decide si el patrón aplica basado en análisis completo
            workers = ['daily_plays', 'daily_plays_midcap', 'orb_breakout', 'vwap_breakout', 'livermore_intraday', 'vcp_smallcap', 'vcp_strict', 'balance_day', 'smallcaps_long', 'outlier_penny_extreme', 'volume_absorption', 'holy_grail', 'parabolic', 'short_parabolic']

            self.logger.debug(
                f"🎯 {symbol}: Universal routing -> {len(workers)} workers will analyze"
            )

            return workers

        except Exception as e:
            self.logger.error(f"❌ Error in universal routing: {e}")
            # Fallback: Still route to all workers (including new ones)
            # Fallback: Still route to all workers (including new ones)
            return ['daily_plays', 'orb_breakout', 'vwap_breakout', 'livermore_intraday', 'vcp_smallcap', 'vcp_strict', 'balance_day', 'volume_absorption', 'generic_01', 'smallcaps_long', 'outlier_penny_extreme', 'holy_grail', 'parabolic', 'short_parabolic']

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

    async def _fetch_bars_for_symbol(self, symbol: str, timeframe: str = '5 mins', count: int = 50) -> list:
        """
        Fetch historical bars for a symbol from the broker

        This method is called when the scanner doesn't provide bars in the opportunity.
        It fetches intraday bars (5 mins by default) to enable context analysis.

        Args:
            symbol: Stock symbol to fetch bars for
            timeframe: Bar timeframe (default: '5 mins' - IBKR format: 'N unit')
            count: Number of bars to fetch (default: 50)

        Returns:
            List of bar objects (IBKR BarData objects) or empty list if fetch fails
        """
        try:
            # Access broker through execution_engine
            if not hasattr(self.execution_engine, 'broker'):
                self.logger.error(f"❌ {symbol}: ExecutionEngine has no broker attribute")
                return []

            broker = self.execution_engine.broker

            # Check if broker has get_bars method
            if not hasattr(broker, 'get_bars'):
                self.logger.error(f"❌ {symbol}: Broker has no get_bars method")
                return []

            # Fetch bars from broker
            self.logger.debug(f"📊 {symbol}: Fetching {count}x {timeframe} bars from broker...")
            bars = await broker.get_bars(symbol, timeframe, count)

            if bars and len(bars) > 0:
                self.logger.debug(f"✅ {symbol}: Fetched {len(bars)} bars successfully")
                return bars
            else:
                self.logger.warning(f"⚠️ {symbol}: Broker returned no bars")
                return []

        except Exception as e:
            self.logger.error(f"❌ {symbol}: Error fetching bars: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []