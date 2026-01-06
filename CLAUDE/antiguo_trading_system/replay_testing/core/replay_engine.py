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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Add parent directory to path para importar módulos del sistema real
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from strategies.workers.base_worker_logic import BaseWorkerLogic
from core.trade_arbiter import TradeArbiter, get_trade_arbiter


class MockWorker(BaseWorkerLogic):
    """Mock worker para replay testing - ACTUALIZADO para generar trades"""
    
    def __init__(self, worker_name: str):
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

        # Arbiter simulado
        self.arbiter = None

        self.logger.info("🔄 ReplayEngine initialized")
        self.logger.info(f"   Market data: {market_data_db_path}")
        self.logger.info(f"   Trading data: {trading_data_db_path}")

    def replay_day(self,
                   date: str,
                   worker_names: Optional[List[str]] = None,
                   symbols: Optional[List[str]] = None) -> ReplaySession:
        """
        Reproduce un día completo con uno o múltiples workers

        Args:
            date: Fecha en formato 'YYYY-MM-DD'
            worker_names: Lista de workers a evaluar (None = todos los workers disponibles)
            symbols: Lista de símbolos a analizar (None = todos)

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

        # 2. Load worker instances (REAL worker code)
        workers = {}
        for worker_name in worker_names:
            worker = self._load_worker(worker_name)
            if worker:
                workers[worker_name] = worker
            else:
                self.logger.warning(f"⚠️ Failed to load worker {worker_name}, skipping")

        if not workers:
            self.logger.error(f"❌ No workers loaded successfully")
            return session

        self.logger.info(f"✅ Loaded {len(workers)} workers: {', '.join(workers.keys())}\n")

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

            # Reset simulated state for this event (isolated from other events)
            self.active_positions = {}  # Fresh state per event
            self.locked_symbols = {}
            self.cooldown_symbols = {}

            # Process each bar for this event
            for bar in bars:
                session.total_bars_processed += 1

                # CADA WORKER evalúa este bar (como en el sistema real)
                for worker_name, worker in workers.items():
                    # Process this bar with this worker
                    decision = self._process_bar(worker, bar, event)

                    if decision:
                        # Add decision to event (separated by worker)
                        event.add_decision(worker_name, decision)
                        session.total_decisions += 1

                        if decision.decision_type == 'ENTRY':
                            if decision.should_enter:
                                session.entries_approved += 1
                                # Simulate opening position
                                self._simulate_entry(symbol, decision, event)
                            else:
                                session.entries_rejected += 1

                        elif decision.decision_type == 'EXIT':
                            session.exits_executed += 1
                            # Simulate closing position
                            self._simulate_exit(symbol, decision, event)

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

        session.end_time = datetime.now()
        elapsed = (session.end_time - session.start_time).total_seconds()

        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"✅ REPLAY COMPLETED in {elapsed:.1f}s")
        self.logger.info(f"{'='*80}")
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

        Returns:
            Dict[symbol -> List[ReplayBar]]
        """
        try:
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

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            if df.empty:
                self.logger.warning("DataFrame from SQL query is empty")
                return {}

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
            return {}

    def _load_worker(self, worker_name: str) -> Optional[BaseWorkerLogic]:
        """
        Carga instancia REAL del worker (mismo código que en producción)

        Returns:
            Worker instance or None
        """
        try:
            # Create mock dependencies (execution_engine and risk_manager not needed for should_enter)
            mock_execution = None
            mock_risk = None

            # Load REAL worker code (not mock)
            if worker_name == 'daily_plays':
                from strategies.workers.daily_plays_worker_logic import DailyPlaysWorkerLogic
                worker = DailyPlaysWorkerLogic(
                    execution_engine=mock_execution,
                    risk_manager=mock_risk,
                    config=None
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
            elif worker_name == 'generic_01':
                # Use mock for workers not yet implemented
                worker = MockWorker('generic_01')
            elif worker_name == 'vcp_smallcap':
                worker = MockWorker('vcp_smallcap')
            elif worker_name == 'volume_absorption':
                worker = MockWorker('volume_absorption')
            elif worker_name == 'momentum_breakout':
                worker = MockWorker('momentum_breakout')
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

    def _process_bar(self, worker: BaseWorkerLogic, bar: ReplayBar, event: ReplayEvent) -> Optional[ReplayDecision]:
        """
        Procesa una barra individual con el worker para un evento específico

        Este es el equivalente a cuando el worker recibe una opportunity en real

        Returns:
            ReplayDecision if worker made a decision, None otherwise
        """
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
                    if datetime.now() < unlock_time:
                        remaining = (unlock_time - datetime.now()).total_seconds() / 60
                        self.logger.debug(
                            f"   {symbol}: In cooldown ({remaining:.1f}min remaining)"
                        )
                        return None
                    else:
                        # Cooldown expired, remove it
                        del self.cooldown_symbols[symbol]

                # Convert ReplayBar to opportunity dict (same format as scanner)
                opportunity = self._bar_to_opportunity(bar)

                # Evaluate with worker (async call)
                import asyncio
                entry_decision = asyncio.run(self._check_entry_conditions(worker, opportunity, event))

                return entry_decision

        except Exception as e:
            self.logger.error(f"Error processing bar for {bar.symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def _simulate_entry(self, symbol: str, decision: ReplayDecision, event: ReplayEvent):
        """
        Simula apertura de posición (NO ejecuta trade real)

        Args:
            symbol: Symbol
            decision: Decision object with entry details
            event: Event this entry belongs to
        """
        try:
            worker_name = decision.worker_name
            entry_price = decision.entry_price
            quantity = decision.quantity

            # Lock ticker for this worker (only ONE worker can have position per event)
            self.locked_symbols[symbol] = {
                'worker': worker_name,
                'timestamp': decision.timestamp
            }

            # Calculate stop loss and take profit based on entry price
            # Using same logic as real system (example: 2% stop loss, 5% take profit)
            stop_loss_price = entry_price * 0.98  # 2% below entry
            take_profit_price = entry_price * 1.05  # 5% above entry

            # Create simulated position
            position = {
                'symbol': symbol,
                'worker': worker_name,
                'entry_price': entry_price,
                'entry_time': decision.timestamp,
                'quantity': quantity,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'trailing_stop_price': None,  # Updated as price moves up
                'highest_price': entry_price,
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

            # Calculate P&L
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

    def _bar_to_opportunity(self, bar: ReplayBar) -> Dict[str, Any]:
        """
        Convierte ReplayBar a opportunity dict (formato scanner)

        Args:
            bar: ReplayBar with market data

        Returns:
            Opportunity dict compatible with worker.should_enter()
        """
        return {
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
            'quality_score': 7.0,  # Neutral score
        }

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

                # Check if pattern completion meets minimum threshold (75%)
                if pattern_completion >= 75.0:
                    # Entry approved
                    decision = ReplayDecision(
                        timestamp=timestamp,
                        symbol=symbol,
                        worker_name=worker.worker_name,
                        decision_type='ENTRY',
                        should_enter=True,
                        entry_price=opportunity['current_price'],
                        quantity=100,  # TODO: Calculate based on risk manager
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
            # Workers use: stop_loss, take_profit, trailing_stop, EOD exit

            exit_reason = None
            exit_price = None

            # 1. Check stop loss
            stop_loss_price = position.get('stop_loss_price')
            if stop_loss_price and current_price <= stop_loss_price:
                exit_reason = 'STOP_LOSS'
                exit_price = stop_loss_price

            # 2. Check take profit
            take_profit_price = position.get('take_profit_price')
            if not exit_reason and take_profit_price and current_price >= take_profit_price:
                exit_reason = 'TAKE_PROFIT'
                exit_price = take_profit_price

            # 3. Check trailing stop
            trailing_stop_price = position.get('trailing_stop_price')
            if not exit_reason and trailing_stop_price and current_price <= trailing_stop_price:
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
