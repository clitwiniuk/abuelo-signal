#!/usr/bin/env python3
"""
Trade OHLC Recorder - Captura y almacena datos OHLC para forward testing
=========================================================================

Módulo que captura automáticamente todos los datos OHLC del día de trading
para cada trade ejecutado, permitiendo análisis posterior y forward testing.
"""

import sqlite3
import logging
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
from dataclasses import dataclass, asdict

from core.interfaces import MarketData, Signal, Position


@dataclass
class TradeOHLCSnapshot:
    """Snapshot de datos OHLC para un trade específico"""
    trade_id: str
    symbol: str
    trading_date: str

    # Datos del día completo
    day_open: float
    day_high: float
    day_low: float
    day_close: float
    day_volume: int

    # Datos específicos del trade
    entry_time: datetime
    entry_price: float
    entry_bar: Dict  # OHLC completo de la barra de entrada

    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_bar: Optional[Dict] = None  # OHLC completo de la barra de salida

    # Datos adicionales para análisis
    premarket_high: Optional[float] = None
    gap_percent: Optional[float] = None
    market_open_price: Optional[float] = None

    # Barras intraday completas (JSON)
    intraday_bars: Optional[str] = None  # JSON con todas las barras del día


class TradeOHLCRecorder:
    """
    Recorder que captura automáticamente datos OHLC para cada trade
    """

    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger("TradeOHLCRecorder")
        self._lock = threading.Lock()

        # Cache de datos OHLC por símbolo y fecha
        self._daily_data_cache: Dict[str, Dict[str, List[MarketData]]] = {}
        self._active_trades: Dict[str, TradeOHLCSnapshot] = {}

        self._init_database()

    def _init_database(self):
        """Inicializar tablas de base de datos en trading_data.db"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Tabla principal para snapshots de trades
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_ohlc_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        trading_date TEXT NOT NULL,

                        -- Datos del día
                        day_open REAL NOT NULL,
                        day_high REAL NOT NULL,
                        day_low REAL NOT NULL,
                        day_close REAL,
                        day_volume INTEGER,

                        -- Datos del trade
                        entry_time TIMESTAMP NOT NULL,
                        entry_price REAL NOT NULL,
                        entry_bar TEXT, -- JSON
                        exit_time TIMESTAMP,
                        exit_price REAL,
                        exit_bar TEXT, -- JSON

                        -- Datos adicionales
                        premarket_high REAL,
                        gap_percent REAL,
                        market_open_price REAL,

                        -- Barras completas del día
                        intraday_bars TEXT, -- JSON con todas las barras

                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Tabla detallada para barras individuales
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_intraday_bars (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT NOT NULL,
                        bar_timestamp TIMESTAMP NOT NULL,
                        timeframe TEXT DEFAULT '1min',
                        open_price REAL NOT NULL,
                        high_price REAL NOT NULL,
                        low_price REAL NOT NULL,
                        close_price REAL NOT NULL,
                        volume INTEGER NOT NULL,
                        bar_sequence INTEGER,
                        is_entry_bar BOOLEAN DEFAULT 0,
                        is_exit_bar BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trades(trade_id),
                        UNIQUE(trade_id, bar_timestamp)
                    )
                """)

                # Índices para performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_ohlc_symbol ON trade_ohlc_snapshots(symbol)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_ohlc_date ON trade_ohlc_snapshots(trading_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_bars_trade_id ON trade_intraday_bars(trade_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trade_bars_timestamp ON trade_intraday_bars(bar_timestamp)")

                conn.commit()
                self.logger.info("✅ Trade OHLC database initialized in trading_data.db")

        except Exception as e:
            self.logger.error(f"❌ Error initializing Trade OHLC database: {e}")

    def record_market_data(self, symbol: str, bar: MarketData):
        """
        Registrar datos de mercado para posible uso en trades

        Args:
            symbol: Símbolo del instrumento
            bar: Datos OHLC de la barra
        """
        with self._lock:
            trading_date = bar.timestamp.date().isoformat()

            # Inicializar cache si no existe
            if symbol not in self._daily_data_cache:
                self._daily_data_cache[symbol] = {}
            if trading_date not in self._daily_data_cache[symbol]:
                self._daily_data_cache[symbol][trading_date] = []

            # Agregar barra al cache
            self._daily_data_cache[symbol][trading_date].append(bar)

            # Limpiar cache de fechas antiguas (mantener solo últimos 3 días)
            cutoff_date = (datetime.now().date() - timedelta(days=3)).isoformat()
            for date_key in list(self._daily_data_cache[symbol].keys()):
                if date_key < cutoff_date:
                    del self._daily_data_cache[symbol][date_key]

    def start_trade_recording(self, signal: Signal) -> bool:
        """
        Iniciar grabación de datos OHLC para un nuevo trade

        Args:
            signal: Señal de entrada del trade

        Returns:
            bool: True si se inició correctamente
        """
        try:
            with self._lock:
                trade_id = signal.signal_id
                symbol = signal.symbol
                trading_date = signal.timestamp.date().isoformat()

                # Obtener datos del día hasta ahora
                daily_bars = self._daily_data_cache.get(symbol, {}).get(trading_date, [])

                if not daily_bars:
                    self.logger.warning(f"⚠️ No daily bars available for {symbol} on {trading_date}")
                    return False

                # Calcular datos del día
                day_open = daily_bars[0].open
                day_high = max(bar.high for bar in daily_bars)
                day_low = min(bar.low for bar in daily_bars)
                day_volume = sum(bar.volume for bar in daily_bars)

                # Encontrar barra de entrada más cercana
                entry_bar = self._find_closest_bar(daily_bars, signal.timestamp)

                # Calcular gap si es market open
                gap_percent = None
                market_open_price = None
                premarket_high = None

                if signal.timestamp.hour == 9 and signal.timestamp.minute <= 35:  # Market open period
                    market_open_price = day_open
                    # Estimar gap (simplificado)
                    if len(daily_bars) > 1:
                        prev_close = daily_bars[0].open  # Aproximación
                        gap_percent = ((day_open - prev_close) / prev_close) * 100 if prev_close > 0 else 0

                # Crear snapshot
                snapshot = TradeOHLCSnapshot(
                    trade_id=trade_id,
                    symbol=symbol,
                    trading_date=trading_date,
                    day_open=day_open,
                    day_high=day_high,
                    day_low=day_low,
                    day_close=daily_bars[-1].close,  # Último close disponible
                    day_volume=day_volume,
                    entry_time=signal.timestamp,
                    entry_price=signal.price,
                    entry_bar=self._bar_to_dict(entry_bar) if entry_bar else None,
                    premarket_high=premarket_high,
                    gap_percent=gap_percent,
                    market_open_price=market_open_price,
                    intraday_bars=json.dumps([self._bar_to_dict(bar) for bar in daily_bars])
                )

                # Almacenar en cache de trades activos
                self._active_trades[trade_id] = snapshot

                self.logger.info(f"📊 Started OHLC recording for trade {trade_id[:8]}... ({symbol})")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error starting trade recording for {signal.symbol}: {e}")
            return False

    def complete_trade_recording(self, trade_id: str, exit_signal: Signal) -> bool:
        """
        Completar grabación cuando el trade se cierra

        Args:
            trade_id: ID del trade
            exit_signal: Señal de salida

        Returns:
            bool: True si se completó correctamente
        """
        try:
            with self._lock:
                if trade_id not in self._active_trades:
                    self.logger.warning(f"⚠️ Trade {trade_id} not found in active recordings")
                    return False

                snapshot = self._active_trades[trade_id]
                symbol = snapshot.symbol
                trading_date = snapshot.trading_date

                # Actualizar datos del día (puede haber más barras)
                daily_bars = self._daily_data_cache.get(symbol, {}).get(trading_date, [])

                if daily_bars:
                    snapshot.day_high = max(snapshot.day_high, max(bar.high for bar in daily_bars))
                    snapshot.day_low = min(snapshot.day_low, min(bar.low for bar in daily_bars))
                    snapshot.day_close = daily_bars[-1].close
                    snapshot.day_volume = sum(bar.volume for bar in daily_bars)

                    # Actualizar barras intraday completas
                    snapshot.intraday_bars = json.dumps([self._bar_to_dict(bar) for bar in daily_bars])

                # Datos de salida
                snapshot.exit_time = exit_signal.timestamp
                snapshot.exit_price = exit_signal.price

                # Encontrar barra de salida
                if daily_bars:
                    exit_bar = self._find_closest_bar(daily_bars, exit_signal.timestamp)
                    snapshot.exit_bar = self._bar_to_dict(exit_bar) if exit_bar else None

                # Guardar en base de datos
                self._save_snapshot_to_db(snapshot)

                # Guardar barras detalladas
                if daily_bars:
                    self._save_intraday_bars_to_db(trade_id, daily_bars, snapshot)

                # Remover de trades activos
                del self._active_trades[trade_id]

                self.logger.info(f"✅ Completed OHLC recording for trade {trade_id[:8]}... ({symbol})")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error completing trade recording for {trade_id}: {e}")
            return False

    def _find_closest_bar(self, bars: List[MarketData], target_time: datetime) -> Optional[MarketData]:
        """Encontrar la barra más cercana al tiempo objetivo"""
        if not bars:
            return None

        closest_bar = None
        min_diff = float('inf')

        for bar in bars:
            diff = abs((bar.timestamp - target_time).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_bar = bar

        return closest_bar

    def _bar_to_dict(self, bar: MarketData) -> Dict:
        """Convertir MarketData a diccionario para JSON"""
        return {
            'timestamp': bar.timestamp.isoformat(),
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        }

    def _save_snapshot_to_db(self, snapshot: TradeOHLCSnapshot):
        """Guardar snapshot en base de datos"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trade_ohlc_snapshots (
                    trade_id, symbol, trading_date, day_open, day_high, day_low,
                    day_close, day_volume, entry_time, entry_price, entry_bar,
                    exit_time, exit_price, exit_bar, premarket_high, gap_percent,
                    market_open_price, intraday_bars, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                snapshot.trade_id, snapshot.symbol, snapshot.trading_date,
                snapshot.day_open, snapshot.day_high, snapshot.day_low,
                snapshot.day_close, snapshot.day_volume, snapshot.entry_time,
                snapshot.entry_price, json.dumps(snapshot.entry_bar) if snapshot.entry_bar else None,
                snapshot.exit_time, snapshot.exit_price,
                json.dumps(snapshot.exit_bar) if snapshot.exit_bar else None,
                snapshot.premarket_high, snapshot.gap_percent, snapshot.market_open_price,
                snapshot.intraday_bars
            ))
            conn.commit()

    def _save_intraday_bars_to_db(self, trade_id: str, bars: List[MarketData], snapshot: TradeOHLCSnapshot):
        """Guardar barras intraday detalladas"""
        with sqlite3.connect(self.db_path) as conn:
            for i, bar in enumerate(bars):
                is_entry = abs((bar.timestamp - snapshot.entry_time).total_seconds()) < 60  # 1 minuto
                is_exit = (snapshot.exit_time and
                          abs((bar.timestamp - snapshot.exit_time).total_seconds()) < 60)

                conn.execute("""
                    INSERT OR REPLACE INTO trade_intraday_bars (
                        trade_id, bar_timestamp, open_price, high_price, low_price,
                        close_price, volume, bar_sequence, is_entry_bar, is_exit_bar
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id, bar.timestamp, bar.open, bar.high, bar.low,
                    bar.close, bar.volume, i + 1, is_entry, is_exit
                ))
            conn.commit()

    def get_trade_ohlc_data(self, trade_id: str) -> Optional[Dict]:
        """
        Obtener datos OHLC completos para un trade específico

        Args:
            trade_id: ID del trade

        Returns:
            Dict con todos los datos OHLC del trade o None si no existe
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Obtener snapshot principal
                snapshot_row = conn.execute(
                    "SELECT * FROM trade_ohlc_snapshots WHERE trade_id = ?",
                    (trade_id,)
                ).fetchone()

                if not snapshot_row:
                    return None

                # Obtener barras detalladas
                bars_rows = conn.execute("""
                    SELECT * FROM trade_intraday_bars
                    WHERE trade_id = ?
                    ORDER BY bar_timestamp
                """, (trade_id,)).fetchall()

                return {
                    'snapshot': dict(snapshot_row),
                    'intraday_bars': [dict(row) for row in bars_rows]
                }

        except Exception as e:
            self.logger.error(f"❌ Error getting trade OHLC data for {trade_id}: {e}")
            return None

    def get_forward_testing_data(self, symbol: str, date_from: str, date_to: str) -> List[Dict]:
        """
        Obtener datos para forward testing de un símbolo en un rango de fechas

        Args:
            symbol: Símbolo a analizar
            date_from: Fecha inicio (YYYY-MM-DD)
            date_to: Fecha fin (YYYY-MM-DD)

        Returns:
            Lista de datos de trades con contexto OHLC completo
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                rows = conn.execute("""
                    SELECT tos.*, t.strategy, t.pnl, t.duration_minutes
                    FROM trade_ohlc_snapshots tos
                    LEFT JOIN trades t ON tos.trade_id = t.trade_id
                    WHERE tos.symbol = ? AND tos.trading_date BETWEEN ? AND ?
                    ORDER BY tos.entry_time
                """, (symbol, date_from, date_to)).fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"❌ Error getting forward testing data: {e}")
            return []

    def get_statistics(self) -> Dict:
        """Obtener estadísticas del recorder"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                snapshot_count = conn.execute("SELECT COUNT(*) FROM trade_ohlc_snapshots").fetchone()[0]
                bars_count = conn.execute("SELECT COUNT(*) FROM trade_intraday_bars").fetchone()[0]

                return {
                    'active_recordings': len(self._active_trades),
                    'total_snapshots': snapshot_count,
                    'total_bars_recorded': bars_count,
                    'cached_symbols': len(self._daily_data_cache),
                    'avg_bars_per_trade': bars_count / max(snapshot_count, 1)
                }

        except Exception as e:
            self.logger.error(f"❌ Error getting statistics: {e}")
            return {}


# Singleton global para acceso fácil
_trade_ohlc_recorder = None
_recorder_lock = threading.Lock()

def get_trade_ohlc_recorder(db_path: str = "trading_data.db") -> TradeOHLCRecorder:
    """Obtener instancia singleton del recorder"""
    global _trade_ohlc_recorder

    with _recorder_lock:
        if _trade_ohlc_recorder is None:
            _trade_ohlc_recorder = TradeOHLCRecorder(db_path)
        return _trade_ohlc_recorder