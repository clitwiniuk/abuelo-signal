#!/usr/bin/env python3
"""
Replay Engine - Motor de reproducción de condiciones reales

Reproduce día a día, barra a barra, las mismas condiciones que tuvo el sistema
en tiempo real, permitiendo verificar cada decisión del worker.
"""

import sys
import os
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field

# Add parent directory to path para importar módulos del sistema real
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strategies.workers.base_worker_logic import BaseWorkerLogic
from strategies.workers.base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradeArbiter, get_trade_arbiter
from core.time_provider import SimulatedTimeProvider
from core.extended_hours_manager import ExtendedHoursManager


class MockWorker(BaseWorkerLogic):
    """Mock worker para replay testing - ACTUALIZADO para generar trades"""
    
    def __init__(self, worker_name: str):
        super().__init__(worker_name, None, None)
        self.worker_name = worker_name
        self.entry_count = 0  # Track entries made
    
    async def should_enter(self, opportunity):
        """Mock implementation - ACEPTA entradas bajo condiciones REALISTAS para testing"""

        # Basic filters para encontrar oportunidades realistas
        symbol = opportunity.get('symbol', '')
        price = opportunity.get('current_price', 0)
        volume = opportunity.get('volume', 0)
        timestamp = opportunity.get('timestamp')

        # Conditions para aceptar entrada (RELAXED para testing):
        conditions = []

        # 1. Volume filter - RELAXED: acepta si volume > 1000 (antes 10000)
        if volume > 1000:
            conditions.append("volume_ok")

        # 2. Price filter - RELAXED: acepta precios entre $1-$100 (antes $2-50)
        if 1.0 <= price <= 100.0:
            conditions.append("price_ok")

        # 3. Time filter - RELAXED: evita solo primeros 30 minutos (antes 45 min)
        if timestamp:
            hour = timestamp.hour
            minute = timestamp.minute
            if not (hour == 9 and minute < 30):  # Después de 9:30 AM
                conditions.append("time_ok")

        # 4. Max 3 entries per symbol per day (antes 2)
        max_entries = 3
        if self.entry_count < max_entries:
            conditions.append("daily_limit_ok")

        # 5. Probability-based acceptance (INCREASED: 50% chance if basic conditions met)
        if len(conditions) >= 3:  # RELAXED: solo necesita 3 de 4 filtros
            import random
            if random.random() < 0.5:  # 50% chance (antes 30%)
                self.entry_count += 1
                return True

        return False
    
    async def should_exit(self, position, current_bar):
        """Mock implementation - sale en stop loss o take profit"""
        
        current_price = current_bar.close
        entry_price = position.get('entry_price', 0)
        
        # Exit conditions:
        # 1. Stop loss - sale si baja 3%
        if current_price <= entry_price * 0.97:
            return True
        
        # 2. Take profit - sale si sube 6%
        if current_price >= entry_price * 1.06:
            return True
        
        # 3. End of day - sale 5 minutos antes del cierre
        timestamp = current_bar.timestamp
        hour = timestamp.hour
        minute = timestamp.minute
        if hour == 15 and minute >= 55:
            return True
        
        return False
    
    async def calculate_pattern_completion(self, opportunity):
        """Mock implementation - calcula completion realista"""
        
        # Return pattern completion entre 75-95% (above 75% threshold)
        import random
        return random.uniform(75.0, 95.0)


@dataclass
class ReplayBar:
    """
    Barra de datos para replay (similar a ib_insync BarData)
    """
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    # Indicadores técnicos
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    vwap: Optional[float] = None

    # Metadata
    volume_ratio: float = 0.0
    gap_percentage: float = 0.0


@dataclass
class WorkerDecisions:
    """
    Decisiones de UN worker específico en un evento
    """
    worker_name: str
    decisions: List['ReplayDecision'] = field(default_factory=list)
    entries_attempted: int = 0
    entries_approved: int = 0
    entries_rejected: int = 0


@dataclass
class ReplayEvent:
    """
    Evento de replay - representa un ticker específico en un día específico

    Un evento = 1 ticker + 1 día
    MÚLTIPLES workers pueden evaluar el mismo evento (pero solo 1 en posición a la vez)

    Ejemplo:
        Evento: MSAI @ 2025-10-31
            09:30 - generic_01 evalúa: RECHAZADO
            10:15 - daily_plays evalúa: RECHAZADO
            11:00 - macdv evalúa: APROBADO ✅ (entra)
            11:30 - macdv sale: Stop loss
            12:00 - daily_plays evalúa: APROBADO ✅ (entra)
            14:00 - daily_plays sale: Take profit

        ✅ Mismo EVENTO
        ✅ Diferentes workers evaluaron
        ❌ Nunca 2 workers en posición simultánea
    """
    symbol: str
    date: str

    # Event metadata
    total_bars: int = 0
    first_bar_time: Optional[datetime] = None
    last_bar_time: Optional[datetime] = None

    # Decisions by worker - cada worker tiene sus propias decisiones
    # Key: worker_name -> WorkerDecisions
    worker_decisions: Dict[str, WorkerDecisions] = field(default_factory=dict)

    # Simulated trades for this event (from ANY worker)
    # Contiene trades de todos los workers que operaron
    simulated_trades: List[Dict] = field(default_factory=list)

    # Real trades for comparison (from ANY worker)
    real_trades: List[Dict] = field(default_factory=list)
    
    # Stats
    bars_processed: int = 0
    decisions_made: int = 0
    entries_approved: int = 0
    entries_rejected: int = 0
    exits_executed: int = 0
    exits_triggered: List[Dict] = field(default_factory=list)

    # Discrepancies specific to this event
    discrepancies: List[Dict] = field(default_factory=list)

    # Current active position (only ONE worker at a time)
    active_position: Optional[Dict] = None

    def get_event_id(self) -> str:
        """Unique identifier for this event"""
        return f"{self.symbol}_{self.date}"

    def add_decision(self, worker_name: str, decision: 'ReplayDecision'):
        """Add decision from a specific worker"""
        if worker_name not in self.worker_decisions:
            self.worker_decisions[worker_name] = WorkerDecisions(worker_name=worker_name)

        self.worker_decisions[worker_name].decisions.append(decision)

        if decision.decision_type == 'ENTRY':
            self.worker_decisions[worker_name].entries_attempted += 1
            if decision.should_enter:
                self.worker_decisions[worker_name].entries_approved += 1
            else:
                self.worker_decisions[worker_name].entries_rejected += 1

    def get_all_decisions(self) -> List['ReplayDecision']:
        """Get all decisions from all workers"""
        all_decisions = []
        for worker_dec in self.worker_decisions.values():
            all_decisions.extend(worker_dec.decisions)
        return sorted(all_decisions, key=lambda d: d.timestamp)

    def get_workers_that_evaluated(self) -> List[str]:
        """Get list of workers that evaluated this event"""
        return list(self.worker_decisions.keys())

    def get_workers_that_traded(self) -> List[str]:
        """Get list of workers that actually entered positions"""
        return list(set([trade.get('worker', 'UNKNOWN') for trade in self.simulated_trades]))

    def __str__(self):
        workers = ', '.join(self.get_workers_that_evaluated())
        return f"Event({self.symbol} @ {self.date}, workers: [{workers}], {len(self.simulated_trades)} trades)"


@dataclass
class ReplayDecision:
    """
    Decisión tomada durante replay
    """
    timestamp: datetime
    symbol: str
    worker_name: str
    decision_type: str  # 'ENTRY', 'EXIT', 'HOLD', 'REJECTED'

    # Entry-specific
    should_enter: bool = False
    entry_price: float = 0.0
    side: str = 'LONG'  # 'LONG' or 'SHORT'
    quantity: int = 0
    pattern_completion: float = 0.0

    # Exit-specific
    should_exit: bool = False
    exit_price: float = 0.0
    exit_reason: str = ""

    # Verification
    checks_passed: Dict[str, bool] = field(default_factory=dict)
    checks_failed: Dict[str, str] = field(default_factory=dict)

    # Metadata
    notes: str = ""


@dataclass
class ReplaySession:
    """
    Sesión completa de replay de un día

    Contiene múltiples ReplayEvents (uno por cada ticker del día)
    """
    date: str
    worker_name: str

    # Events: cada ticker es un evento independiente
    # Key: symbol -> ReplayEvent
    events: Dict[str, ReplayEvent] = field(default_factory=dict)

    # Global statistics (agregados de todos los eventos)
    total_bars_processed: int = 0
    total_decisions: int = 0
    total_events: int = 0
    entries_approved: int = 0
    entries_rejected: int = 0
    exits_executed: int = 0
    exits_triggered: List[Dict] = field(default_factory=list)  # List of all exits triggered in session

    # Global verification
    total_discrepancies: int = 0

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def symbols(self) -> List[str]:
        """List of symbols processed in this session"""
        return list(self.events.keys())
    
    @symbols.setter
    def symbols(self, value: List[str]):
        """Allow setting symbols (for compatibility)"""
        pass  # Just ignore the assignment, we compute it from events

    @property
    def simulated_trades(self) -> List[Dict]:
        """All simulated trades from all events"""
        trades = []
        for event in self.events.values():
            trades.extend(event.simulated_trades)
        return trades

    @property
    def discrepancies(self) -> List[Dict]:
        """All discrepancies from all events"""
        discs = []
        for event in self.events.values():
            discs.extend(event.discrepancies)
        return discs

    def get_event(self, symbol: str) -> Optional[ReplayEvent]:
        """Get event for specific symbol"""
        return self.events.get(symbol)

    def add_event(self, event: ReplayEvent):
        """Add event to session"""
        self.events[event.symbol] = event
        self.total_events += 1


class ReplayEngine:
    """
    Motor de Replay - Reproduce condiciones reales del sistema

    Features:
    - Carga datos de market_data.db
    - Ejecuta workers con condiciones reales
    - Verifica cada decisión
    - Compara con trades reales
    - NO ejecuta trades reales (solo simula)
    """

    def __init__(self,
                 market_data_db_path: str,
                 trading_data_db_path: str,
                 verbose: bool = False):
        """
        Initialize Replay Engine

        Args:
            market_data_db_path: Path to market_data.db (datos de mercado)
            trading_data_db_path: Path to trading_data.db (trades reales)
            verbose: Enable verbose logging
        """
        self.market_data_db = market_data_db_path
        self.trading_data_db = trading_data_db_path
        self.verbose = verbose

        # DEBUG: Log the actual paths being used
        print(f"DEBUG: ReplayEngine initialized with market_data_db_path: '{market_data_db_path}'")
        print(f"DEBUG: ReplayEngine initialized with trading_data_db_path: '{trading_data_db_path}'")
        print(f"DEBUG: Current working directory: '{os.getcwd()}'")
        print(f"DEBUG: Checking if market data file exists: {os.path.exists(market_data_db_path)}")
        print(f"DEBUG: Checking if trading data file exists: {os.path.exists(trading_data_db_path)}")

        # Setup logging
        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Simulated state (como el sistema real pero sin ejecutar nada)
        self.active_positions: Dict[str, Dict] = {}  # symbol -> position_data
        self.locked_symbols: Dict[str, datetime] = {}  # symbol -> lock_time
        self.cooldown_symbols: Dict[str, Dict] = {}  # symbol -> cooldown_data

        # Time Provider for simulation
        self.clock = SimulatedTimeProvider()

        # Arbiter simulado
        self.arbiter = None
        
        # Daily data store
        self.daily_data = {}
        
        # Signal Recorder (Persistence Phase 4)
        from core.scanner_signal_recorder import ScannerSignalRecorder
        self.signal_recorder = ScannerSignalRecorder()



        self.logger.info("🔄 ReplayEngine initialized")
        self.logger.info(f"   Market data: {market_data_db_path}")
        self.logger.info(f"   Trading data: {trading_data_db_path}")
        # print("DEBUG: ReplayEngine initialized (MODIFIED VERSION)")

    def replay_day(self,
                   date: str,
                   worker_names: Optional[List[str]] = None,
                   symbols: Optional[List[str]] = None,
                   mock_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
                   setup_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                   scanner_adapter=None) -> ReplaySession:
        
        # print(f"DEBUG: replay_day called with mock_metadata keys: {list(mock_metadata.keys()) if mock_metadata else 'None'}")
        """
        Reproduce un día completo con uno o múltiples workers

        Args:
            date: Fecha en formato 'YYYY-MM-DD'
            worker_names: Lista de workers a evaluar (None = todos los workers disponibles)
            symbols: Lista de símbolos a analizar (None = todos)
            mock_metadata: Dict[str, Dict] con metadatos simulados por símbolo (ej. {'FOXX': {'quality_score': 80}})
            setup_callback: Función opcional para configurar workers antes del loop (recibe self.workers)

        Returns:
            ReplaySession con todas las decisiones y resultados

        Note:
            - Cada símbolo + día = 1 EVENTO
            - Múltiples workers pueden evaluar el MISMO evento
            - Solo 1 worker puede tener posición activa a la vez por evento
        """
        # Default: usar todos los workers disponibles
        if not worker_names:
            worker_names = ['generic_01', 'daily_plays', 'macdv', 'vcp_smallcap', 'volume_absorption']

        workers_str = ', '.join(worker_names)
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"🔄 REPLAY SESSION: {date}")
        self.logger.info(f"   Workers: {workers_str}")
        self.logger.info(f"{'='*80}\n")

        session = ReplaySession(
            date=date,
            worker_name=workers_str,  # Para compatibilidad, guardar como string
            start_time=datetime.now()
        )

        # 1. Load market data for the day
        bars_by_symbol = self._load_market_data(date, symbols)

        if not bars_by_symbol:
            self.logger.error(f"❌ No market data found for {date}")
            return session

        session.symbols = list(bars_by_symbol.keys())
        self.logger.info(f"📊 Loaded data for {len(session.symbols)} symbols")

        # Scanner Adapter: Fetch signals for this day
        self.scanner_adapter_data = {}
        if scanner_adapter:
            try:
                import asyncio
                # Determine date range (just this day for replay_day)
                date_dt = datetime.strptime(date, '%Y-%m-%d')
                
                # We need to run the async scan method
                # Since replay_day is synchronous (though it calls async methods inside), we need to handle this carefully
                # In this codebase context, replay_day seems to be running in sync context but using asyncio.run inside helpers
                # Let's use asyncio.run here for simplicity if loop is not running, or await if it is
                
                # Check for running loop
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                         # This is tricky without changing replay_day to async
                         # For now, simplistic assumption: replay_day is called from async backtester usually
                         # But wait, replay_day signature is def replay_day(self,...), not async def
                         
                         # Since HistoricalScannerAdapter.scan_history is async, and we are in sync method...
                         # We'll use a wrapper or just run_until_complete if we own the loop
                         pass
                except RuntimeError:
                    # No running loop, safe to use asyncio.run
                    self.scanner_adapter_data = asyncio.run(scanner_adapter.scan_history(session.symbols, date_dt, date_dt))
                    self.logger.info(f"🔍 Scanner Adapter found signals for: {list(self.scanner_adapter_data.get(date, []))}")
            except Exception as e:
                self.logger.error(f"Error running scanner adapter: {e}")

        # 2. Load worker instances (REAL worker code)
        workers = {}
        for worker_name in worker_names:
            worker = self._load_worker(worker_name)
            if worker:
                workers[worker_name] = worker
                # Inject replay date for accurate daily tracking
                if hasattr(worker, 'set_replay_date'):
                    worker.set_replay_date(date)
                    self.logger.debug(f"✅ Injected replay date {date} into {worker_name}")
            else:
                self.logger.warning(f"⚠️ Failed to load worker {worker_name}, skipping")

        # CALLBACK: Allow external configuration of workers
        if setup_callback:
            setup_callback(workers)

        if not workers:
            self.logger.error(f"❌ No workers loaded successfully (and none injected via callback)")
            return session

        # 3. Initialize simulated arbiter
        self.arbiter = get_trade_arbiter()

        # 4. Replay bar by bar for each symbol (cada símbolo = un evento)
        # MÚLTIPLES workers evalúan el MISMO evento
        for symbol, bars in bars_by_symbol.items():
            self.logger.info(f"\n📈 Replaying EVENT: {symbol} @ {date} ({len(bars)} bars)")

            # Create independent event for this symbol + date
            event = ReplayEvent(
                symbol=symbol,
                date=date,
                total_bars=len(bars),
                first_bar_time=bars[0].timestamp if bars else None,
                last_bar_time=bars[-1].timestamp if bars else None
            )
            
            # Store bars in event for EOD closure
            event.bars = bars

            # NOTE: Do NOT reset active_positions here - positions should persist across symbols in same day
            # Only reset locked_symbols and cooldown_symbols per event
            # self.active_positions = {}  # REMOVED - keep positions open until EOD
            if not hasattr(self, '_day_state_initialized') or self._current_replay_date != date:
                # Reset state only when starting a new day
                self.active_positions = {}
                self.locked_symbols = {}
                self.cooldown_symbols = {}
                self._day_state_initialized = True
                self._current_replay_date = date
            # Per-event: only reset locks/cooldowns, not positions
            # (positions need to persist across symbols in the same day)
            self.locked_symbols = {}
            self.cooldown_symbols = {}
            
            # Initialize worker decisions for this event
            self.worker_decisions = {}
            for worker_name in workers:
                self.worker_decisions[worker_name] = WorkerDecisions(worker_name=worker_name)

            # Process each bar for this event
            for bar_idx, bar in enumerate(bars):
                session.total_bars_processed += 1

                # Update Simulated Clock
                self.clock.set_time(bar.timestamp)

                # Build bars history up to current bar (for pattern detection)
                bars_history = bars[:bar_idx + 1]

                # CADA WORKER evalúa este bar (como en el sistema real)
                # COLLECT DECISIONS PHASE
                # First collect all decisions from all workers for this bar
                bar_decisions = []
                
                for worker_name, worker in workers.items():
                    # Process this bar with this worker
                    decision = self._process_bar(worker, bar, event, mock_metadata, bars_history)

                    if decision:
                        bar_decisions.append(decision)
                        # Store decision in event history
                        self.worker_decisions[worker_name].decisions.append(decision)
                        event.decisions_made += 1
                
                # EXECUTE PHASE - Process collected decisions
                # 1. Separate entries and exits & others
                entries = [d for d in bar_decisions if d.decision_type == 'ENTRY']
                exits = [d for d in bar_decisions if d.decision_type == 'EXIT']
                others = [d for d in bar_decisions if d.decision_type not in ['ENTRY', 'EXIT']]
                
                # 2. Process Exits (Priority over entries)
                for decision in exits:
                    event.exits_executed += 1
                    event.exits_triggered.append({
                        'reason': decision.exit_reason,
                        'price': decision.exit_price,
                        'timestamp': decision.timestamp
                    })
                    self._simulate_exit(symbol, decision, event)
                
                # 3. Process Entries (Deterministic Competition)
                if entries:
                    # Filter only entries for symbol not already active (if multiple workers want entry on closed symbol)
                    # But wait, we might have closed it just now (in Exits step).
                    # So we check active_positions again.
                    if symbol not in self.active_positions:
                        # DETERMINISTIC WINNER SELECTION
                        # Sort by pattern_completion desc, then worker_name asc
                        # This matches EntryCompetition logic
                        winner = max(entries, key=lambda x: (x.pattern_completion, x.worker_name))
                        
                        # Process winner
                        event.entries_approved += 1
                        self._simulate_entry(symbol, winner, event, workers.get(winner.worker_name))
                        
                        # Mark others as 'LOSER' (conceptually, already rejected by not being winner)
                        for loser in entries:
                            if loser != winner:
                                # We can log them or count them as rejected?
                                # event.entries_rejected += 1 # Optional
                                self.logger.debug(f"   ⚠️ {loser.worker_name} lost competition to {winner.worker_name}")
                    else:
                        # Symbol active, ignore all entries
                        pass
                
                # 4. Handle other decisions (rejected, hold, etc)
                for decision in others:
                    if decision.decision_type == 'REJECTED':
                        event.entries_rejected += 1

            # 5. Load real trades for THIS event (symbol + date, ANY worker)
            event.real_trades = self._load_real_trades_for_event(date, None, symbol)

            # 6. Compare this event's replay vs real trades
            event.discrepancies = self._compare_event_with_real(event)
            session.total_discrepancies += len(event.discrepancies)

            # Add event to session
            session.add_event(event)

            # Log event summary
            workers_evaluated = event.get_workers_that_evaluated()
            workers_traded = event.get_workers_that_traded()
            self.logger.info(
                f"   Event complete: {len(event.get_all_decisions())} decisions, "
                f"{len(event.simulated_trades)} simulated trades, "
                f"{len(event.real_trades)} real trades, "
                f"{len(event.discrepancies)} discrepancies"
            )
            self.logger.info(f"   Workers evaluated: {', '.join(workers_evaluated)}")
            if workers_traded:
                self.logger.info(f"   Workers traded: {', '.join(workers_traded)}")

        # Close any remaining open positions at end of day
        self.logger.info(f"DEBUG: Active positions before EOD close: {len(self.active_positions)}")
        for symbol in self.active_positions:
            self.logger.info(f"  - {symbol}")
        self._close_open_positions_eod(session)

        session.end_time = datetime.now()
        elapsed = (session.end_time - session.start_time).total_seconds()

        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"✅ REPLAY COMPLETED in {elapsed:.1f}s")
        self.logger.info(f"{'='*80}")
        # Aggregate results
        session.total_bars_processed = sum(e.bars_processed for e in session.events.values())
        session.total_decisions = sum(e.decisions_made for e in session.events.values())
        session.entries_approved = sum(e.entries_approved for e in session.events.values())
        session.entries_rejected = sum(e.entries_rejected for e in session.events.values())
        session.exits_executed = sum(e.exits_executed for e in session.events.values())
        
        # Aggregate all exits triggered
        for event in session.events.values():
            session.exits_triggered.extend(event.exits_triggered)

        self.logger.info(f"   Bars processed: {session.total_bars_processed}")
        self.logger.info(f"   Decisions made: {session.total_decisions}")
        self.logger.info(f"   Entries approved: {session.entries_approved}")
        self.logger.info(f"   Entries rejected: {session.entries_rejected}")
        self.logger.info(f"   Exits executed: {session.exits_executed}")
        self.logger.info(f"   Simulated trades: {len(session.simulated_trades)}")
        self.logger.info(f"   Discrepancies: {len(session.discrepancies)}")

        return session

    def _load_market_data(self, date: str, symbols: Optional[List[str]]) -> Dict[str, List[ReplayBar]]:
        """
        Carga datos de market_data.db para el día especificado
        
        FALLBACK: Si no hay datos en intraday_bars, intenta cargar desde
        trade_intraday_bars en trading_data.db (datos de trades ejecutados)

        Returns:
            Dict[symbol -> List[ReplayBar]]
        """
        try:
            # PRIORITY 1: Force load from trade_ohlc_snapshots in trading_data.db (USER REQUEST)
            # This table contains the high-fidelity captured data from live trading
            self.logger.info(f"🔄 Loading data from trade_ohlc_snapshots (Priority Source)...")
            bars_by_symbol = self._load_trade_snapshots_data(date, symbols)
            
            if bars_by_symbol:
                self.logger.info(f"✅ Successfully loaded {len(bars_by_symbol)} symbols from snapshots")
                return bars_by_symbol
                
            self.logger.warning(f"No data in trade_ohlc_snapshots for {date}, trying legacy sources...")

            conn = sqlite3.connect(self.market_data_db)

            # Build query
            query = """
                SELECT
                    symbol, bar_timestamp, open_price, high_price, low_price, close_price, volume,
                    vwap
                FROM intraday_bars
                WHERE DATE(bar_timestamp) = ?
            """

            params = [date]

            if symbols:
                placeholders = ','.join('?' * len(symbols))
                query += f" AND symbol IN ({placeholders})"
                params.extend(symbols)

            query += " ORDER BY symbol, bar_timestamp"

            try:
                df = pd.read_sql_query(query, conn, params=params)
            except Exception as e:
                self.logger.warning(f"Primary market data query failed (table missing?): {e}")
                df = pd.DataFrame()
                
            conn.close()

            if df.empty:
                self.logger.warning(f"No data in intraday_bars for {date}, trying trade_intraday_bars...")
                # FALLBACK 1: Try loading from trade_intraday_bars in trading_data.db
                bars = self._load_trade_intraday_data(date, symbols)
                return bars

            # Convert to ReplayBar objects grouped by symbol
            bars_by_symbol = {}

            print(f"DEBUG: SQL DataFrame shape: {df.shape}")
            print(f"DEBUG: SQL DataFrame columns: {df.columns.tolist()}")
            print(f"DEBUG: SQL Unique symbols: {df['symbol'].unique().tolist()}")
            
            for symbol in df['symbol'].unique():
                symbol_df = df[df['symbol'] == symbol]

                bars = []
                for _, row in symbol_df.iterrows():
                    bar = ReplayBar(
                        symbol=row['symbol'],
                        timestamp=pd.to_datetime(row['bar_timestamp']),
                        open=float(row['open_price']),
                        high=float(row['high_price']),
                        low=float(row['low_price']),
                        close=float(row['close_price']),
                        volume=int(row['volume']),
                        rsi=None,  # No disponible en intraday_bars
                        macd=None,  # No disponible en intraday_bars
                        macd_signal=None,  # No disponible en intraday_bars
                        vwap=float(row['vwap']) if pd.notna(row['vwap']) else None
                    )
                    bars.append(bar)

                bars_by_symbol[symbol] = bars

                self.logger.info(f"   Loaded {len(bars)} bars for {symbol}")

            print(f"DEBUG: Final bars_by_symbol keys: {list(bars_by_symbol.keys())}")
            print(f"DEBUG: Final bars_by_symbol length: {len(bars_by_symbol)}")
            
            # Add detailed logging for debugging
            if not bars_by_symbol:
                self.logger.error("CRITICAL: bars_by_symbol is empty after processing!")
                self.logger.error(f"DataFrame shape: {df.shape}")
                self.logger.error(f"DataFrame head: {df.head()}")
            else:
                self.logger.info(f"SUCCESS: Processed {len(bars_by_symbol)} symbols")
                for symbol in bars_by_symbol.keys():
                    self.logger.info(f"  Symbol {symbol}: {len(bars_by_symbol[symbol])} bars")
            
            return bars_by_symbol

        except Exception as e:
            self.logger.error(f"Error loading market data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {}

    def _load_trade_snapshots_data(self, date: str, symbols: Optional[List[str]]) -> Dict[str, List[ReplayBar]]:
        """
        FALLBACK 2: Load data from trade_ohlc_snapshots in trading_data.db
        Some trades store full day bars in 'intraday_bars' JSON column.
        """
        try:
            conn = sqlite3.connect(self.trading_data_db)
            query = "SELECT symbol, intraday_bars FROM trade_ohlc_snapshots WHERE DATE(trading_date) = ?"
            params = [date]

            if symbols:
                placeholders = ','.join('?' * len(symbols))
                query += f" AND symbol IN ({placeholders})"
                params.extend(symbols)

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty:
                self.logger.warning(f"No data in trade_ohlc_snapshots for {date}")
                return {}

            self.logger.info(f"✅ Loaded snapshots for {len(df)} symbols from trade_ohlc_snapshots")
            
            bars_by_symbol = {}
            import json
            
            for _, row in df.iterrows():
                symbol = row['symbol']
                json_bars = row['intraday_bars']
                
                if not json_bars:
                    continue
                    
                try:
                    raw_bars = json.loads(json_bars)
                    bars = []
                    
                    # Sort by timestamp
                    raw_bars.sort(key=lambda x: x['timestamp'])
                    
                    # Calculate VWAP manually
                    cum_tp_vol = 0.0
                    cum_vol = 0.0
                    
                    for rb in raw_bars:
                        # Parse timestamp
                        # Check format: "2025-10-24T15:01:00-04:00"
                        ts = pd.to_datetime(rb['timestamp'])
                        
                        op = float(rb['open'])
                        hi = float(rb['high'])
                        lo = float(rb['low'])
                        cl = float(rb['close'])
                        vo = int(rb['volume'])
                        
                        # VWAP Calc
                        tp = (hi + lo + cl) / 3.0
                        cum_tp_vol += tp * vo
                        cum_vol += vo
                        vwap = cum_tp_vol / cum_vol if cum_vol > 0 else tp
                        
                        bar = ReplayBar(
                            symbol=symbol,
                            timestamp=ts,
                            open=op,
                            high=hi,
                            low=lo,
                            close=cl,
                            volume=vo,
                            rsi=None,
                            macd=None,
                            macd_signal=None,
                            vwap=vwap
                        )
                        bars.append(bar)
                    
                    bars_by_symbol[symbol] = bars
                    self.logger.info(f"   Parsed {len(bars)} bars for {symbol} from snapshot")
                    
                except Exception as e:
                     self.logger.error(f"Error parsing JSON bars for {symbol}: {e}")
                     continue

            return bars_by_symbol

        except Exception as e:
            self.logger.error(f"Error loading trade snapshots: {e}")
            return {}

    def _load_trade_intraday_data(self, date: str, symbols: Optional[List[str]]) -> Dict[str, List[ReplayBar]]:
        """
        FALLBACK: Carga datos desde trade_intraday_bars en trading_data.db
        
        Esto permite hacer replay de días donde solo tenemos datos de trades ejecutados,
        no datos de mercado generales.
        
        Returns:
            Dict[symbol -> List[ReplayBar]]
        """
        try:
            conn = sqlite3.connect(self.trading_data_db)
            
            # Query to get trade intraday bars joined with trades to get symbol
            query = """
                SELECT
                    t.symbol,
                    tib.bar_timestamp,
                    tib.open_price,
                    tib.high_price,
                    tib.low_price,
                    tib.close_price,
                    tib.volume
                FROM trade_intraday_bars tib
                JOIN trades t ON tib.trade_id = t.trade_id
                WHERE DATE(tib.bar_timestamp) = ?
            """
            
            params = [date]
            
            if symbols:
                placeholders = ','.join('?' * len(symbols))
                query += f" AND t.symbol IN ({placeholders})"
                params.extend(symbols)
            
            query += " ORDER BY t.symbol, tib.bar_timestamp"
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if df.empty:
                self.logger.warning(f"No data in trade_intraday_bars for {date} either")
                return {}
            
            self.logger.info(f"✅ Loaded {len(df)} bars from trade_intraday_bars (fallback)")
            
            # Convert to ReplayBar objects grouped by symbol
            bars_by_symbol = {}
            
            for symbol in df['symbol'].unique():
                symbol_df = df[df['symbol'] == symbol].copy()
                
                # Calculate VWAP from OHLCV data
                # Typical Price = (High + Low + Close) / 3
                symbol_df['typical_price'] = (symbol_df['high_price'] + symbol_df['low_price'] + symbol_df['close_price']) / 3
                
                # Cumulative (Typical Price * Volume)
                symbol_df['tp_volume'] = symbol_df['typical_price'] * symbol_df['volume']
                symbol_df['cum_tp_volume'] = symbol_df['tp_volume'].cumsum()
                symbol_df['cum_volume'] = symbol_df['volume'].cumsum()
                
                # VWAP = Cumulative (TP * Volume) / Cumulative Volume
                # Handle division by zero for bars with no volume
                symbol_df['vwap'] = symbol_df['cum_tp_volume'] / symbol_df['cum_volume'].replace(0, 1)
                
                bars = []
                for _, row in symbol_df.iterrows():
                    bar = ReplayBar(
                        symbol=row['symbol'],
                        timestamp=pd.to_datetime(row['bar_timestamp']),
                        open=float(row['open_price']),
                        high=float(row['high_price']),
                        low=float(row['low_price']),
                        close=float(row['close_price']),
                        volume=int(row['volume']),
                        rsi=None,
                        macd=None,
                        macd_signal=None,
                        vwap=float(row['vwap']) if pd.notna(row['vwap']) else None  # ✅ Calculated from OHLCV
                    )
                    bars.append(bar)
                
                bars_by_symbol[symbol] = bars
                self.logger.info(f"   Loaded {len(bars)} bars for {symbol} (from trades, VWAP calculated)")
            
            return bars_by_symbol
            
        except Exception as e:
            self.logger.error(f"Error loading trade intraday data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {}

    def _load_worker(self, worker_name: str) -> Optional[BaseWorkerLogic]:
        """
        Carga instancia REAL del worker (mismo código que en producción)

        Returns:
            Worker instance or None
        """
        try:
            # Create mock dependencies (execution_engine and risk_manager not needed for should_enter)
            class MockIB:
                async def reqHistoricalDataAsync(self, *args, **kwargs):
                    return []  # Return empty list to trigger "Insufficient daily history" safe path

            class MockBroker:
                def __init__(self):
                    self.ib = MockIB()
                    
                def get_account_value(self):
                    return 100000.0
                def get_buying_power(self):
                    return 400000.0
                async def get_short_data(self, symbol):
                    # Mock ETB (Easy To Borrow) - Assume always available for replay
                    return {
                        'symbol': symbol, 
                        'is_etb': True, 
                        'conviction': 'high',
                        'shortable_shares': 1000000, 
                        'short_status': 'Available'
                    }
                def get_position(self, symbol):
                    return None
            
            class MockExecutionEngine:
                def __init__(self, clock):
                    self.broker = MockBroker()
                    self.clock = clock
                    # Core components
                    from core.scanner_signal_recorder import ScannerSignalRecorder
                    self.market_hours = ExtendedHoursManager()
                    self.signal_recorder = ScannerSignalRecorder()
                    # Stats tracking
                    self.extended_hours_manager = ExtendedHoursManager(clock=clock)
            
            mock_execution = MockExecutionEngine(self.clock)
            mock_risk = None

            # Load REAL worker code (not mock)
            if worker_name == 'daily_plays':
                from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic

                # Load config.ini for daily_plays worker v2.0
                import configparser
                config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
                parser = configparser.ConfigParser()
                if os.path.exists(config_path):
                    parser.read(config_path)
                
                # Create a wrapper that supports BOTH attribute access (BaseWorkerLogic) AND get methods (DailyPlaysWorkerLogic)
                class ConfigWrapper:
                    def __init__(self, parser):
                        self.parser = parser
                        # Attributes for BaseWorkerLogic
                        self.no_entry_after = parser.getfloat('GLOBAL', 'no_entry_after', fallback=15.75)
                        self.market_open_time = parser.get('GLOBAL', 'market_open_time', fallback='09:30')
                        
                        # Strategy specific overrides
                        if parser.has_section('DAILY_PLAYS_STRATEGY'):
                            if parser.has_option('DAILY_PLAYS_STRATEGY', 'strategy_start_time'):
                                self.strategy_start_time = parser.get('DAILY_PLAYS_STRATEGY', 'strategy_start_time')
                            if parser.has_option('DAILY_PLAYS_STRATEGY', 'strategy_end_time'):
                                self.strategy_end_time = parser.get('DAILY_PLAYS_STRATEGY', 'strategy_end_time')

                    def getfloat(self, section, option, fallback=None):
                        return self.parser.getfloat(section, option, fallback=fallback)

                    def getint(self, section, option, fallback=None):
                        return self.parser.getint(section, option, fallback=fallback)
                    
                    def getboolean(self, section, option, fallback=None):
                        return self.parser.getboolean(section, option, fallback=fallback)

                    def get(self, section, option, fallback=None):
                        return self.parser.get(section, option, fallback=fallback)
                    
                    def has_option(self, section, option):
                        return self.parser.has_option(section, option)

                config = ConfigWrapper(parser)

                worker = DailyPlaysWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=config
                )
            elif worker_name == 'macdv':
                from strategies.workers.macdv_worker_logic import MacdvWorkerLogic
                worker = MacdvWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'vwap':
                from strategies.workers.vwap_worker_logic import VWAPWorkerLogic
                worker = VWAPWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'short_parabolic':
                from strategies.workers.short_parabolic_worker_logic import ShortParabolicWorkerLogic
                
                # Load config.ini for short_parabolic
                import configparser
                config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
                parser = configparser.ConfigParser()
                if os.path.exists(config_path):
                    parser.read(config_path)

                # Re-use ConfigWrapper if defined locally or duplicate it
                class ConfigWrapper:
                    def __init__(self, parser):
                        self.parser = parser
                    def getfloat(self, section, option, fallback=None):
                        return self.parser.getfloat(section, option, fallback=fallback)
                    def getint(self, section, option, fallback=None):
                        return self.parser.getint(section, option, fallback=fallback)
                    def getboolean(self, section, option, fallback=None):
                        return self.parser.getboolean(section, option, fallback=fallback)
                    def get(self, section, option, fallback=None):
                        return self.parser.get(section, option, fallback=fallback)
                    def has_option(self, section, option):
                        return self.parser.has_option(section, option)

                config = ConfigWrapper(parser)

                worker = ShortParabolicWorkerLogic(
                    worker_name='short_parabolic',
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=config
                )
            elif worker_name == 'generic_01':
                # Use mock for workers not yet implemented
                worker = MockWorker('generic_01')
            elif worker_name == 'vcp_smallcap':
                from strategies.workers.vcp_smallcap_worker_logic import VCPSmallcapWorkerLogic
                worker = VCPSmallcapWorkerLogic(
                    worker_name='vcp_smallcap',
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'holy_grail':
                from strategies.workers.holy_grail_worker_logic import HolyGrailWorkerLogic
                worker = HolyGrailWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'balance_day':
                from strategies.workers.balance_day_worker_logic import BalanceDayWorkerLogic
                worker = BalanceDayWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'volume_absorption':
                from strategies.workers.volume_absorption_worker_logic import VolumeAbsorptionWorkerLogic
                worker = VolumeAbsorptionWorkerLogic(
                    worker_name='volume_absorption',
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'buy_and_hold':
                from strategies.workers.buy_and_hold_worker_logic import BuyAndHoldWorkerLogic
                worker = BuyAndHoldWorkerLogic(
                    worker_name='buy_and_hold',
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
                )
            elif worker_name == 'buy_the_dip':
                from strategies.workers.buy_the_dip_worker_logic import BuyTheDipWorkerLogic
                # Load config.ini for buy_the_dip worker v2.0
                import configparser
                config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
                config = configparser.ConfigParser()
                if os.path.exists(config_path):
                    config.read(config_path)
                else:
                    config = None

                worker = BuyTheDipWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=config
                )
            elif worker_name == 'momentum_breakout':
                worker = MockWorker('momentum_breakout')
            elif worker_name == 'orb_breakout':
                from strategies.workers.orb_worker_logic import ORBWorkerLogic
                # Load config.ini for ORB worker
                import configparser
                config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.ini')
                config = configparser.ConfigParser()
                if os.path.exists(config_path):
                    config.read(config_path)
                else:
                    config = None

                worker = ORBWorkerLogic(
                    worker_name='orb_breakout',
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=config
                )
            else:
                self.logger.error(f"Unknown worker: {worker_name}")
                return None

            self.logger.info(f"✅ Loaded REAL worker: {worker_name}")
            return worker

        except Exception as e:
            self.logger.error(f"Error loading worker {worker_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _process_bar(self, worker: BaseWorkerLogic, bar: ReplayBar, event: ReplayEvent,
                    mock_metadata: Optional[Dict[str, Dict]] = None,
                    bars_history: Optional[List[ReplayBar]] = None) -> Optional[ReplayDecision]:
        """
        Procesa una barra individual con el worker para un evento específico

        Este es el equivalente a cuando el worker recibe una opportunity en real

        Returns:
            ReplayDecision if worker made a decision, None otherwise
        """
        # Default values (Synthetic)
        catalyst_type = 'NONE' # Default no catalyst
        quality_score = 6.0    # Default medium score
        gap_percent = 0.0
        
        symbol = bar.symbol

        
        # PERSISTENCE (PHASE 4): Try to load REAL recorded signal
        # This matches Replay exactly to what happened in Live
        try:
            date = pd.to_datetime(bar.timestamp)
            real_signal = self.signal_recorder.get_signal_for_replay(symbol, date.date())
            if real_signal:
                catalyst_type = real_signal.get('catalyst_type', 'NONE')
                quality_score = float(real_signal.get('quality_score', 6.0))
                # If we have the full dict, we could populate more fields if needed
                # For now, these are the critical ones impacting decision making
                # self.logger.debug(f"Loaded persisted signal for {symbol}: CAT={catalyst_type}, Q={quality_score}")
        except Exception as e:
            self.logger.warning(f"Error loading persisted signal for {symbol}: {e}")

        # If we have intraday data, calculate gap from daily bars if possible
        if self.daily_data is not None and symbol in self.daily_data:
            pass # This line was part of the original code, keeping it as is.
        try:
            symbol = bar.symbol

            # Check if we have an active position for this symbol
            has_position = symbol in self.active_positions

            # If we have position, check exit conditions
            if has_position:
                position = self.active_positions[symbol]

                # Check if worker should exit (async call but we run in sync context)
                import asyncio

                # Create temporary position dict for exit evaluation
                exit_decision = asyncio.run(self._check_exit_conditions(worker, bar, position, event))

                if exit_decision:
                    return exit_decision

                # No exit decision yet, continue monitoring
                return None

            # No position - check entry conditions
            else:
                # Check if ticker is locked by trade arbiter
                if symbol in self.locked_symbols:
                    self.logger.debug(f"   {symbol}: Locked by another worker")
                    return None

                # Check if ticker is in cooldown
                if symbol in self.cooldown_symbols:
                    unlock_time = self.cooldown_symbols[symbol]['unlock_time']

                    # Use simulation time, not wall clock time
                    current_time = pd.to_datetime(bar.timestamp)
                    if current_time.tzinfo is not None:
                        current_time = current_time.tz_localize(None)
                    if unlock_time.tzinfo is not None:
                        unlock_time = unlock_time.tz_localize(None)

                    if current_time < unlock_time:
                        remaining = (unlock_time - current_time).total_seconds() / 60
                        self.logger.debug(
                            f"   {symbol}: In cooldown ({remaining:.1f}min remaining)"
                        )
                        return None
                    else:
                        # Cooldown expired, remove it
                        del self.cooldown_symbols[symbol]

                # Convert ReplayBar to opportunity dict (same format as scanner)
                # print(f"DEBUG: _process_bar calling _bar_to_opportunity with mock_metadata: {list(mock_metadata.keys()) if mock_metadata else 'None'}")
                opportunity = self._bar_to_opportunity(bar, mock_metadata, bars_history)

                # Inject Scanner Adapter Data
                # If a scanner adapter is provided, check if we have a signal for this date/symbol
                if hasattr(self, 'scanner_adapter_data') and self.scanner_adapter_data:
                    date_str = pd.to_datetime(bar.timestamp).strftime('%Y-%m-%d')
                    scanner_hits = self.scanner_adapter_data.get(date_str, [])
                    for hit in scanner_hits:
                        if hit.get('symbol') == symbol:
                            # Merge scanner data into opportunity
                            opportunity.update(hit)
                            self.logger.debug(f"✨ Injected scanner data for {symbol} on {date_str}")
                            break

                # Evaluate with worker (async call)
                import asyncio
                entry_decision = asyncio.run(self._check_entry_conditions(worker, opportunity, event))

                return entry_decision

        except Exception as e:
            self.logger.error(f"Error processing bar for {bar.symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _simulate_entry(self, symbol: str, decision: ReplayDecision, event: ReplayEvent, worker=None):
        """
        Simula apertura de posición (NO ejecuta trade real)

        Args:
            symbol: Symbol
            decision: Decision object with entry details
            event: Event this entry belongs to
            worker: Worker instance (optional, for calling callbacks)
        """
        try:
            worker_name = decision.worker_name
            entry_price = decision.entry_price
            quantity = decision.quantity

            side = getattr(decision, 'side', 'LONG')

            # Lock ticker for this worker (only ONE worker can have position per event)
            self.locked_symbols[symbol] = {
                'worker': worker_name,
                'timestamp': decision.timestamp
            }

            # Calculate stop loss and take profit based on entry price
            # Using same logic as real system (example: 2% stop loss, 5% take profit)
            if side == 'SHORT':
                stop_loss_price = entry_price * 1.02  # 2% above entry (Loss if price goes UP)
                take_profit_price = entry_price * 0.95  # 5% below entry (Profit if price goes DOWN)
            else:
                stop_loss_price = entry_price * 0.98  # 2% below entry
                take_profit_price = entry_price * 1.05  # 5% above entry

            # Create simulated position
            position = {
                'symbol': symbol,
                'worker': worker_name,
                'side': side,
                'entry_price': entry_price,
                'entry_time': decision.timestamp,
                'quantity': quantity,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'trailing_stop_price': None,  # Updated as price moves up
                'highest_price': entry_price,
                'lowest_price': entry_price,  # Track lowest price for Short trailing stock
            }

            # Store active position
            self.active_positions[symbol] = position

            # Create simulated trade record (entry only, exit will be added later)
            simulated_trade = {
                'symbol': symbol,
                'worker': worker_name,
                'entry_time': decision.timestamp.isoformat(),
                'entry_price': entry_price,
                'quantity': quantity,
                'stop_loss': stop_loss_price,
                'take_profit': take_profit_price,
                'pattern_completion': decision.pattern_completion,
                'status': 'OPEN',
            }

            # Add to event's simulated trades
            event.simulated_trades.append(simulated_trade)

            # 🚫 Update worker's internal state for anti-overtrading
            # Mark symbol as traded today to prevent duplicate entries
            try:
                if worker and hasattr(worker, 'traded_symbols_today'):
                    worker.traded_symbols_today.add(symbol)
                    self.logger.debug(f"   📝 Marked {symbol} as traded today (anti-overtrading)")
            except Exception as e:
                self.logger.debug(f"   ⚠️ Error updating traded_symbols_today: {e}")

            self.logger.info(
                f"   🟢 SIMULATED ENTRY: {symbol} @ ${entry_price:.2f} "
                f"({worker_name}, qty={quantity})"
            )

        except Exception as e:
            self.logger.error(f"Error simulating entry for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _simulate_exit(self, symbol: str, decision: ReplayDecision, event: ReplayEvent):
        """
        Simula cierre de posición (NO ejecuta trade real)

        Args:
            symbol: Symbol
            decision: Decision object with exit details
            event: Event this exit belongs to
        """
        try:
            worker_name = decision.worker_name
            exit_price = decision.exit_price
            exit_reason = decision.exit_reason

            # Get active position
            if symbol not in self.active_positions:
                self.logger.warning(f"No active position for {symbol} to exit")
                return

            position = self.active_positions[symbol]
            entry_price = position['entry_price']
            quantity = position['quantity']

            side = position.get('side', 'LONG')
            
            # Calculate P&L
            if side == 'SHORT':
                pnl = (entry_price - exit_price) * quantity
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
            else:
                pnl = (exit_price - entry_price) * quantity
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100

            # Update simulated trade with exit info
            # Find the open trade for this symbol
            for trade in event.simulated_trades:
                if trade['symbol'] == symbol and trade['status'] == 'OPEN':
                    trade['exit_time'] = decision.timestamp.isoformat()
                    trade['exit_price'] = exit_price
                    trade['exit_reason'] = exit_reason
                    trade['pnl'] = pnl
                    trade['pnl_percent'] = pnl_percent
                    trade['pnl_pct'] = pnl_percent  # For test compatibility
                    trade['status'] = 'CLOSED'
                    break

            # Remove active position
            del self.active_positions[symbol]

            # Unlock ticker (with cooldown)
            del self.locked_symbols[symbol]

            # Apply cooldown based on exit reason
            cooldown_minutes = 0
            if 'STOP_LOSS' in exit_reason:
                cooldown_minutes = 30
            elif 'TRAILING_STOP' in exit_reason:
                cooldown_minutes = 15
            elif 'TAKE_PROFIT' in exit_reason:
                cooldown_minutes = 5

            if cooldown_minutes > 0:
                unlock_time = decision.timestamp + timedelta(minutes=cooldown_minutes)
                self.cooldown_symbols[symbol] = {
                    'worker': worker_name,
                    'reason': exit_reason,
                    'unlock_time': unlock_time
                }

            self.logger.info(
                f"   🔴 SIMULATED EXIT: {symbol} @ ${exit_price:.2f} "
                f"({exit_reason}, P&L={pnl_percent:+.1f}%, cooldown={cooldown_minutes}min)"
            )

        except Exception as e:
            self.logger.error(f"Error simulating exit for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _close_open_positions_eod(self, session: ReplaySession):
        """
        Cierra todas las posiciones abiertas al final del día con el último precio disponible

        Args:
            session: ReplaySession with potentially open positions
        """
        if not self.active_positions:
            return

        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"🔚 CLOSING OPEN POSITIONS AT END OF DAY")
        self.logger.info(f"{'='*80}\n")

        # Get last bar for each symbol to determine exit price
        for symbol, position in list(self.active_positions.items()):
            try:
                entry_price = position['entry_price']
                quantity = position['quantity']

                # Find the event for this symbol to get the last bar
                # Events are stored with symbol as key (not date_symbol)
                event = session.events.get(symbol)

                exit_price = None
                exit_time = None

                if event and hasattr(event, 'bars') and event.bars:
                    # Use last bar's close price
                    last_bar = event.bars[-1]
                    exit_price = last_bar.close
                    exit_time = last_bar.timestamp
                else:
                    # Fallback: look for entry price in position or use market close
                    exit_price = entry_price * 0.98  # Assume 2% loss if no data
                    exit_time = datetime.now()
                    self.logger.warning(f"No bars available for {symbol}, assuming 2% loss")

                # Calculate P&L
                pnl = (exit_price - entry_price) * quantity
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100

                # Find and update the open trade in session
                for event in session.events.values():
                    for trade in event.simulated_trades:
                        if trade['symbol'] == symbol and trade.get('status') == 'OPEN':
                            trade['exit_time'] = exit_time.isoformat()
                            trade['exit_price'] = exit_price
                            trade['exit_reason'] = 'EOD_CLOSE'
                            trade['pnl'] = pnl
                            trade['pnl_percent'] = pnl_percent
                            trade['pnl_pct'] = pnl_percent
                            trade['status'] = 'CLOSED'

                            self.logger.info(
                                f"   🔴 EOD CLOSE: {symbol} @ ${exit_price:.2f} "
                                f"(Entry: ${entry_price:.2f}, P&L={pnl_percent:+.1f}%)"
                            )
                            break

            except Exception as e:
                self.logger.error(f"Error closing EOD position for {symbol}: {e}")
                import traceback
                self.logger.error(traceback.format_exc())

        # Clear active positions
        self.active_positions.clear()
        self.logger.info(f"\n✅ All open positions closed at EOD\n")

    def _bar_to_opportunity(self, bar: ReplayBar, mock_metadata: Optional[Dict[str, Dict]] = None,
                           bars_history: Optional[List[ReplayBar]] = None) -> Dict[str, Any]:
        """
        Convierte ReplayBar a opportunity dict (formato scanner)

        Args:
            bar: ReplayBar with market data
            mock_metadata: Optional metadata overrides
            bars_history: Historical bars up to current bar (for pattern detection)

        Returns:
            Opportunity dict compatible with worker.should_enter()
        """
        opportunity = {
            'symbol': bar.symbol,
            'current_price': bar.close,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'timestamp': bar.timestamp,

            # Technical indicators
            'rsi': bar.rsi,
            'macd': bar.macd,
            'macd_signal': bar.macd_signal,
            'vwap': bar.vwap,

            # Metadata
            'volume_ratio': bar.volume_ratio,
            'gap_percentage': bar.gap_percentage,

            # Scanner defaults (replay doesn't have catalyst info)
            'catalyst_type': 'TECHNICAL',
            'quality_score': 75.0,  # Realistic score for replay testing (was 60.0, too low for VCP check)
            'catalyst_strength': 7,  # Strong catalyst strength for testing (min required is 7)
        }

        # TIMEZONE FIX: Ensure timestamp is US/Eastern for workers
        try:
            ts = opportunity['timestamp']
            import pytz
            eastern = pytz.timezone('US/Eastern')
            
            if ts.tzinfo is None:
                # Assume DB timestamps are ALREADY Eastern Time (naive)
                # This fixes the issue where 13:55 (ET) was treated as UTC -> 08:55 ET
                ts = eastern.localize(ts)
            else:
                # If already aware, convert to Eastern
                ts = ts.astimezone(eastern)
            
            opportunity['timestamp'] = ts
        except Exception:
            pass  # Keep original if conversion fails

        # Add bars history if available (convert ReplayBar to dict format)
        if bars_history:
            opportunity['bars_history'] = [
                {
                    'timestamp': b.timestamp,
                    'open': b.open,
                    'high': b.high,
                    'low': b.low,
                    'close': b.close,
                    'volume': b.volume,
                    'vwap': b.vwap
                }
                for b in bars_history
            ]

        # Apply mock metadata if available for this symbol
        if mock_metadata:
            # print(f"DEBUG: mock_metadata keys: {list(mock_metadata.keys())}, bar.symbol: {bar.symbol}")
            if bar.symbol in mock_metadata:
                overrides = mock_metadata[bar.symbol]
                # print(f"DEBUG: Applying overrides for {bar.symbol}: {overrides}")
                # Update opportunity with overrides
                for key, value in overrides.items():
                    opportunity[key] = value

        return opportunity

    def _calculate_position_size(self, symbol: str, price: float, worker: BaseWorkerLogic) -> int:
        """
        Calculate position size based on worker config (max_position_value)
        Mirrors TradingExecutionStage._calculate_position_size
        """
        try:
            # 1. Get max position value from worker config or global config
            # Try worker config first
            max_position_value = 0.0
            
            if worker.config:
                # Try to get from strategy section
                section = getattr(worker, 'config_section', worker.worker_name.upper() + '_STRATEGY')
                max_position_value = 0.0
                
                # Helper to get float from config safely
                def get_cfg(sec, key):
                    try:
                        val = worker.config.get(sec, key)
                        return float(val) if val else 0.0
                    except:
                        return 0.0
                
                max_position_value = get_cfg(section, 'max_position_value')
                
                # Fallback to GLOBAL if not in strategy
                if max_position_value <= 0:
                    max_position_value = get_cfg('GLOBAL', 'max_position_value')
            
            # Hard fallback if still 0
            if max_position_value <= 0:
                max_position_value = 2000.0  # Default reasonable value for replay
                
            # 2. Check for confidence sizing
            enable_confidence_sizing = False
            if worker.config:
                try:
                    val = worker.config.get('GLOBAL', 'enable_confidence_sizing')
                    enable_confidence_sizing = (str(val).lower() == 'true')
                except:
                    pass
            
            # 3. Calculate base quantity
            if price <= 0:
                return 0
                
            quantity = int(max_position_value / price)
            
            # 4. Limit checks
            min_quantity = 1
            if quantity < min_quantity:
                quantity = min_quantity
                
            return quantity
            
        except Exception as e:
            self.logger.error(f"Error calculating position size for {symbol}: {e}")
            return 100  # Safe fallback

    async def _check_entry_conditions(
        self,
        worker: BaseWorkerLogic,
        opportunity: Dict[str, Any],
        event: ReplayEvent
    ) -> Optional[ReplayDecision]:
        """
        Evalúa si el worker debe entrar en esta oportunidad

        Args:
            worker: Worker instance
            opportunity: Opportunity dict
            event: Current replay event

        Returns:
            ReplayDecision if worker wants to enter, None otherwise
        """
        symbol = opportunity['symbol']
        timestamp = opportunity['timestamp']

        try:
            # Call worker's should_enter method
            should_enter = await worker.should_enter(opportunity)
            
            if should_enter:
                # Calculate pattern completion
                result = await worker.calculate_pattern_completion(opportunity)

                if isinstance(result, tuple):
                    pattern_completion, support_level = result
                else:
                    pattern_completion = result
                    support_level = 0.0

                # Check if pattern completion meets minimum threshold (60% for VCP, 75% for others)
                # VCP pattern reaches 60% with 2 contractions (valid setup)
                min_threshold = 60.0 if worker.worker_name == 'vcp_smallcap' else 75.0
                if pattern_completion >= min_threshold:
                    # Entry approved
                    
                    # 1. Determine SIDE (Use explicit scaling_side if available, else infer from name)
                    side = 'LONG'  # Default
                    if hasattr(worker, 'scaling_side'):
                        side = worker.scaling_side
                    else:
                        # Legacy fallback: Name inference
                        worker_name_lower = worker.worker_name.lower()
                        if 'short_squeeze' in worker_name_lower:
                            side = 'LONG'
                        elif 'short' in worker_name_lower or 'bear' in worker_name_lower:
                            side = 'SHORT'
                    
                    # 2. Determine QUANTITY (Dynamic sizing)
                    quantity = self._calculate_position_size(symbol, opportunity['current_price'], worker)

                    decision = ReplayDecision(
                        timestamp=timestamp,
                        symbol=symbol,
                        worker_name=worker.worker_name,
                        decision_type='ENTRY',
                        should_enter=True,
                        entry_price=opportunity['current_price'],
                        side=side,
                        quantity=quantity,
                        pattern_completion=pattern_completion,
                        checks_passed={
                            'should_enter': True,
                            'pattern_completion': pattern_completion >= 75.0,
                        }
                    )

                    self.logger.debug(
                        f"   ✅ {symbol}: {worker.worker_name} ENTRY APPROVED "
                        f"(pattern={pattern_completion:.1f}%, price=${opportunity['current_price']:.2f})"
                    )

                    return decision

                else:
                    # Entry rejected - pattern not complete enough
                    decision = ReplayDecision(
                        timestamp=timestamp,
                        symbol=symbol,
                        worker_name=worker.worker_name,
                        decision_type='REJECTED',
                        should_enter=False,
                        pattern_completion=pattern_completion,
                        checks_failed={
                            'pattern_completion': f'{pattern_completion:.1f}% < 75%'
                        },
                        notes=f'Pattern incomplete ({pattern_completion:.1f}% < 75%)'
                    )

                    self.logger.debug(
                        f"   ⚪ {symbol}: {worker.worker_name} ENTRY REJECTED "
                        f"(pattern={pattern_completion:.1f}% < 75%)"
                    )

                    return decision

            else:
                # Worker's should_enter returned False
                decision = ReplayDecision(
                    timestamp=timestamp,
                    symbol=symbol,
                    worker_name=worker.worker_name,
                    decision_type='REJECTED',
                    should_enter=False,
                    notes='Worker strategy rejected entry'
                )

                self.logger.debug(
                    f"   ⚪ {symbol}: {worker.worker_name} ENTRY REJECTED (strategy criteria not met)"
                )

                return decision

        except Exception as e:
            self.logger.error(f"Error checking entry for {symbol} with {worker.worker_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    async def _check_exit_conditions(
        self,
        worker: BaseWorkerLogic,
        bar: ReplayBar,
        position: Dict,
        event: ReplayEvent
    ) -> Optional[ReplayDecision]:
        """
        Evalúa si el worker debe salir de la posición actual

        Args:
            worker: Worker instance
            bar: Current bar
            position: Active position dict
            event: Current replay event

        Returns:
            ReplayDecision if exit triggered, None otherwise
        """
        symbol = bar.symbol
        current_price = bar.close
        entry_price = position['entry_price']
        timestamp = bar.timestamp

        try:
            # Check worker's exit conditions
            exit_reason = None
            exit_price = None

            # DELEGATION: Use worker's stop manager if available (Source of Truth)
            if hasattr(worker, 'stop_manager') and worker.stop_manager:
                # Construct market data object for FOMO detection
                # Needs: close, volume, timestamp (at minimum)
                market_data = type('MarketData', (), {
                    'close': current_price,
                    'volume': bar.volume,
                    'high': bar.high,
                    'low': bar.low, 
                    'open': bar.open,
                    'timestamp': bar.timestamp
                })
                
                should_exit, reason = worker.stop_manager.check_exit(
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=entry_price,
                    market_data=market_data,  # Pass valid market data object
                    position_metadata=position.get('metadata')
                )
                
                if should_exit:
                    exit_reason = reason.split(' ')[0]  # Extract main reason (e.g., STOP_LOSS)
                    exit_price = current_price  # Assume execution at current close
            else:
                # Fallback: Manual checks (Legacy)
                # 1. Check stop loss
                stop_loss_price = position.get('stop_loss_price')
                side = position.get('side', 'LONG')
                
                if stop_loss_price:
                    if side == 'SHORT':
                        if current_price >= stop_loss_price:
                            exit_reason = 'STOP_LOSS'
                            exit_price = stop_loss_price
                    else:
                        if current_price <= stop_loss_price:
                            exit_reason = 'STOP_LOSS'
                            exit_price = stop_loss_price

                # 2. Check take profit
                take_profit_price = position.get('take_profit_price')
                if not exit_reason and take_profit_price:
                    if side == 'SHORT':
                        if current_price <= take_profit_price:
                            exit_reason = 'TAKE_PROFIT'
                            exit_price = take_profit_price
                    else:
                        if current_price >= take_profit_price:
                            exit_reason = 'TAKE_PROFIT'
                            exit_price = take_profit_price

                # 3. Check trailing stop
                trailing_stop_price = position.get('trailing_stop_price')
                if not exit_reason and trailing_stop_price:
                    if side == 'SHORT':
                        if current_price >= trailing_stop_price:
                            exit_reason = 'TRAILING_STOP'
                            exit_price = trailing_stop_price
                    else:
                        if current_price <= trailing_stop_price:
                            exit_reason = 'TRAILING_STOP'
                            exit_price = trailing_stop_price

                # 4. Check EOD exit (15:55 ET)
                if not exit_reason:
                    hour = timestamp.hour
                    minute = timestamp.minute
                    # Assuming bars are in ET timezone
                    if hour == 15 and minute >= 55:
                        exit_reason = 'EOD_EXIT'
                        exit_price = current_price

            # If any exit condition triggered
            if exit_reason:
                decision = ReplayDecision(
                    timestamp=timestamp,
                    symbol=symbol,
                    worker_name=worker.worker_name,
                    decision_type='EXIT',
                    should_exit=True,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    checks_passed={
                        'exit_triggered': True,
                        'exit_reason': exit_reason
                    }
                )

                self.logger.debug(
                    f"   🔴 {symbol}: {worker.worker_name} EXIT TRIGGERED "
                    f"({exit_reason}, price=${exit_price:.2f})"
                )

                return decision

            # No exit triggered
            return None

        except Exception as e:
            self.logger.error(f"Error checking exit for {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _load_real_trades_for_event(self, date: str, worker_name: Optional[str], symbol: str) -> List[Dict]:
        """
        Carga trades REALES de trading_data.db para un evento específico (symbol + date)

        Args:
            date: Date (YYYY-MM-DD)
            worker_name: Worker name (None = ANY worker)
            symbol: Symbol for this specific event

        Returns:
            List of real trades for this symbol on this date (from any/specific worker)
        """
        try:
            conn = sqlite3.connect(self.trading_data_db)

            if worker_name:
                # Specific worker
                query = """
                    SELECT *
                    FROM trades
                    WHERE DATE(entry_time) = ?
                    AND strategy = ?
                    AND symbol = ?
                    ORDER BY entry_time
                """
                df = pd.read_sql_query(query, conn, params=[date, worker_name, symbol])
            else:
                # ANY worker (para eventos con múltiples workers)
                query = """
                    SELECT *
                    FROM trades
                    WHERE DATE(entry_time) = ?
                    AND symbol = ?
                    ORDER BY entry_time
                """
                df = pd.read_sql_query(query, conn, params=[date, symbol])

            conn.close()

            trades = df.to_dict('records')

            if trades:
                workers = set([t.get('strategy', 'UNKNOWN') for t in trades])
                self.logger.debug(
                    f"   Loaded {len(trades)} real trades for {symbol} @ {date} "
                    f"(workers: {', '.join(workers)})"
                )

            return trades

        except Exception as e:
            self.logger.debug(f"Error loading real trades for {symbol}: {e}")
            return []

    def _compare_event_with_real(self, event: ReplayEvent) -> List[Dict]:
        """
        Compara un evento de replay vs trades reales de ese evento

        Args:
            event: ReplayEvent with simulated_trades and real_trades

        Returns:
            Lista de discrepancias encontradas para este evento específico
        """
        discrepancies = []

        try:
            symbol = event.symbol
            simulated_count = len(event.simulated_trades)
            real_count = len(event.real_trades)

            # 1. Check trade count discrepancy
            if simulated_count != real_count:
                discrepancies.append({
                    'type': 'TRADE_COUNT_MISMATCH',
                    'severity': 'MEDIUM',
                    'symbol': symbol,
                    'message': f'{symbol}: Replay had {simulated_count} trades but real system had {real_count}',
                    'replay_count': simulated_count,
                    'real_count': real_count
                })

            # 2. Compare individual trades (if counts match or are close)
            # Match trades by entry time (closest match within 5 minutes)
            for sim_trade in event.simulated_trades:
                sim_entry_time = pd.to_datetime(sim_trade['entry_time'])

                # Find matching real trade (same symbol, close entry time)
                best_match = None
                min_time_diff = timedelta(minutes=5)

                for real_trade in event.real_trades:
                    real_entry_time = pd.to_datetime(real_trade['entry_time'])
                    
                    # Ensure both are timezone-naive for comparison
                    if sim_entry_time.tzinfo is not None:
                        sim_entry_time = sim_entry_time.tz_localize(None)
                    if real_entry_time.tzinfo is not None:
                        real_entry_time = real_entry_time.tz_localize(None)
                        
                    time_diff = abs(sim_entry_time - real_entry_time)

                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        best_match = real_trade

                if best_match:
                    # Compare prices
                    sim_entry_price = sim_trade['entry_price']
                    real_entry_price = best_match.get('entry_price', 0)

                    price_diff_percent = abs(sim_entry_price - real_entry_price) / real_entry_price * 100

                    if price_diff_percent > 1.0:  # More than 1% difference
                        discrepancies.append({
                            'type': 'ENTRY_PRICE_MISMATCH',
                            'severity': 'HIGH',
                            'symbol': symbol,
                            'message': f'{symbol}: Entry price diff {price_diff_percent:.1f}% (replay=${sim_entry_price:.2f} vs real=${real_entry_price:.2f})',
                            'replay_price': sim_entry_price,
                            'real_price': real_entry_price,
                            'diff_percent': price_diff_percent
                        })

                    # Compare exit prices (if both trades are closed)
                    if sim_trade.get('status') == 'CLOSED' and best_match.get('exit_price'):
                        sim_exit_price = sim_trade['exit_price']
                        real_exit_price = best_match['exit_price']

                        exit_price_diff_percent = abs(sim_exit_price - real_exit_price) / real_exit_price * 100

                        if exit_price_diff_percent > 1.0:
                            discrepancies.append({
                                'type': 'EXIT_PRICE_MISMATCH',
                                'severity': 'MEDIUM',
                                'symbol': symbol,
                                'message': f'{symbol}: Exit price diff {exit_price_diff_percent:.1f}% (replay=${sim_exit_price:.2f} vs real=${real_exit_price:.2f})',
                                'replay_price': sim_exit_price,
                                'real_price': real_exit_price,
                                'diff_percent': exit_price_diff_percent
                            })

                    # Compare exit reasons
                    if sim_trade.get('exit_reason') and best_match.get('exit_reason'):
                        if sim_trade['exit_reason'] != best_match['exit_reason']:
                            discrepancies.append({
                                'type': 'EXIT_REASON_MISMATCH',
                                'severity': 'LOW',
                                'symbol': symbol,
                                'message': f'{symbol}: Exit reason mismatch (replay={sim_trade["exit_reason"]} vs real={best_match["exit_reason"]})',
                                'replay_reason': sim_trade['exit_reason'],
                                'real_reason': best_match['exit_reason']
                            })

                else:
                    # No matching real trade found
                    discrepancies.append({
                        'type': 'MISSING_REAL_TRADE',
                        'severity': 'HIGH',
                        'symbol': symbol,
                        'message': f'{symbol}: Replay entered @ {sim_entry_time.strftime("%H:%M")} but no matching real trade found',
                        'replay_trade': sim_trade
                    })

            # 3. Check for real trades that replay didn't capture
            for real_trade in event.real_trades:
                real_entry_time = pd.to_datetime(real_trade['entry_time'])

                # Find matching simulated trade
                found_match = False
                for sim_trade in event.simulated_trades:
                    sim_entry_time = pd.to_datetime(sim_trade['entry_time'])
                    
                    # Ensure both are timezone-naive
                    if sim_entry_time.tzinfo is not None:
                        sim_entry_time = sim_entry_time.tz_localize(None)
                    if real_entry_time.tzinfo is not None:
                        real_entry_time = real_entry_time.tz_localize(None)
                        
                    time_diff = abs(sim_entry_time - real_entry_time)

                    if time_diff < timedelta(minutes=5):
                        found_match = True
                        break

                if not found_match:
                    discrepancies.append({
                        'type': 'MISSING_REPLAY_TRADE',
                        'severity': 'HIGH',
                        'symbol': symbol,
                        'message': f'{symbol}: Real system entered @ {real_entry_time.strftime("%H:%M")} but replay did not',
                        'real_trade': real_trade
                    })

            return discrepancies

        except Exception as e:
            self.logger.error(f"Error comparing event {event.symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
