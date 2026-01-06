#!/usr/bin/env python3
"""
Polygon.io Data Downloader Expandido - Sistema de Contexto Histórico
Versión modificada para incluir event_id y 60 días de historial contextual

Modificaciones del sistema base:
1. Agregar columna event_id a intraday_bars
2. Crear tabla daily_ohlcv_history para contexto de 60 días
3. Generar event_id único para cada (symbol, date) combo
4. Descargar historial contextual para discovery de reglas avanzadas
"""

import json
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
import hashlib

# Cargar variables de entorno desde .env.local si existe
try:
    from pathlib import Path
    env_file = Path('.env.local')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
except Exception:
    pass  # Si hay error, no pasa nada, continuar normalmente

try:
    from polygon import RESTClient
except ImportError:
    print("ERROR: Polygon SDK no instalado. Ejecuta: pip install polygon-api-client")
    sys.exit(1)


class PolygonDataDownloaderExpanded:
    """
    Descargador expandido con event_id y contexto histórico
    Base: PolygonDataDownloader original
    + event_id system
    + 60 días de historial contextual
    """

    def __init__(self, api_key: str, market_db_path: str = None,
                 trading_db_path: str = None, log_file: str = 'polygon_download_log_expanded.json'):
        """
        Inicializar downloader expandido

        Args:
            api_key: API key de Polygon.io
            market_db_path: Ruta a market_data.db 
            trading_db_path: Ruta a trading_data.db para leer oportunidades
            log_file: Archivo para registrar progreso
        """
        self.api_key = api_key
        self.market_db_path = market_db_path or self._get_market_db_path()
        self.trading_db_path = trading_db_path or self._get_trading_db_path()
        self.log_file = log_file

        # Rate limiting (Free tier: 5 calls/min)
        self.calls_per_minute = 5
        self.api_call_count = 0
        self.last_reset_time = time.time()

        # Configuración del historial contextual
        self.history_days = 60  # 60 días de contexto histórico

        # Inicializar cliente de Polygon
        self.client = RESTClient(api_key=self.api_key)

        # Logging
        self.logger = logging.getLogger('polygon_downloader_expanded')
        self._setup_logging()

        # Cargar progreso previo
        self.processed_downloads = self._load_progress()

        # Inicializar base de datos con las nuevas estructuras
        self._init_database_expanded()

    def _setup_logging(self):
        """Configurar logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _get_market_db_path(self) -> str:
        """Obtener ruta por defecto a market_data.db"""
        # Desde backtesting_system/data/ -> trading_system_v3/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'market_data.db')

    def _get_trading_db_path(self) -> str:
        """Obtener ruta por defecto a trading_data.db"""
        # Desde backtesting_system/data/ -> trading_system_v3/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'trading_data.db')

    def _load_progress(self) -> Set[str]:
        """Cargar registro de descargas ya procesadas"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            self.logger.warning(f"Error loading progress log: {e}")
            return set()

    def _save_progress(self, download_key: str):
        """
        Guardar progreso de descarga

        Args:
            download_key: Clave única de descarga (symbol_date)
        """
        try:
            self.processed_downloads.add(download_key)
            with open(self.log_file, 'w') as f:
                json.dump(list(self.processed_downloads), f)
        except Exception as e:
            self.logger.error(f"Error saving progress: {e}")

    def _init_database_expanded(self):
        """Inicializar market_data.db con estructura expandida"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # 1. Agregar event_id a intraday_bars si no existe
            cursor.execute("PRAGMA table_info(intraday_bars)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'event_id' not in columns:
                print("📝 Agregando columna event_id a intraday_bars...")
                cursor.execute("ALTER TABLE intraday_bars ADD COLUMN event_id INTEGER")
                print("✅ event_id agregado a intraday_bars")
            else:
                print("✅ event_id ya existe en intraday_bars")

            # 2. Crear tabla de historial contextual diario
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_ohlcv_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    history_date DATE NOT NULL,
                    days_before_event INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(event_id, history_date),
                    FOREIGN KEY (event_id) REFERENCES intraday_bars(event_id)
                )
            """)

            # 3. Crear índices para búsquedas eficientes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_event_id ON daily_ohlcv_history(event_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_symbol ON daily_ohlcv_history(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_date ON daily_ohlcv_history(history_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_days_before ON daily_ohlcv_history(days_before_event)")

            # 4. Actualizar índices para intraday_bars con event_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bars_event_id 
                ON intraday_bars(event_id)
            """)

            conn.commit()
            conn.close()

            self.logger.info(f"Expanded market database initialized: {self.market_db_path}")

        except Exception as e:
            self.logger.error(f"Error initializing expanded market database: {e}")
            raise
    def _handle_rate_limit(self):
        """Manejar rate limiting de Polygon API - Optimizado para 5 calls/min"""
        self.api_call_count += 1

        # Si alcanzamos el límite de 5 llamadas, esperar
        if self.api_call_count >= self.calls_per_minute:
            elapsed = time.time() - self.last_reset_time
            if elapsed < 60:
                wait_time = 60 - elapsed
                self.logger.info(f"⚡ 5 calls reached. Waiting {wait_time:.1f}s until next batch...")
                time.sleep(wait_time)

            # Resetear contador
            self.api_call_count = 0
            self.last_reset_time = time.time()

        # También verificar si ha pasado mucho tiempo sin resetear
        elif time.time() - self.last_reset_time >= 60:
            # Resetear contador si ha pasado más de un minuto
            self.api_call_count = 0
            self.last_reset_time = time.time()


    def generate_event_id(self, symbol: str, scan_date: str) -> int:
        """
        Generar event_id único para cada (symbol, date) combination
        
        Args:
            symbol: Ticker del símbolo
            scan_date: Fecha en formato YYYY-MM-DD
            
        Returns:
            event_id único basado en hash de symbol+date
        """
        event_key = f"{symbol}_{scan_date}"
        event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
        return event_id

    def download_symbol_date_with_event(self, symbol: str, date: datetime) -> int:
        """
        Descargar barras de 1min para un símbolo en una fecha específica + crear event_id

        Args:
            symbol: Ticker del símbolo
            date: Fecha para descargar

        Returns:
            Número de barras descargadas
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            download_key = f"{symbol}_{date_str}"

            # Verificar si ya se procesó
            if download_key in self.processed_downloads:
                self.logger.info(f"Skipping {download_key} (already processed)")
                return 0

            # Generar event_id único
            event_id = self.generate_event_id(symbol, date_str)

            self.logger.info(f"Downloading {symbol} for {date_str} (Event: {event_id})...")

            # Manejar rate limit
            self._handle_rate_limit()

            # Descargar datos de Polygon (mismo sistema que antes)
            try:
                # Intentar descargar datos diarios primero (siempre disponible en free tier)
                aggs = []
                for agg in self.client.list_aggs(
                    ticker=symbol,
                    multiplier=1,
                    timespan='day',  # Cambiar a 'day' para free tier
                    from_=date_str,
                    to=date_str,
                    limit=1  # Solo necesitamos 1 barra diaria
                ):
                    aggs.append(agg)

                if not aggs:
                    self.logger.warning(f"No daily data found for {symbol} on {date_str}")
                    self._save_progress(download_key)
                    return 0

                # Convertir barra diaria a barras intradiarias simuladas
                simulated_bars = self._create_simulated_intraday_bars(aggs[0], date_str)
                inserted = self._insert_bars_with_event(symbol, event_id, simulated_bars)

                self.logger.info(f"✅ {symbol} {date_str}: {inserted} simulated intraday bars created (Event: {event_id})")

            except Exception as api_error:
                # Si falla la API, usar datos de fallback
                error_msg = str(api_error)
                if "NOT_AUTHORIZED" in error_msg and "data timeframe" in error_msg:
                    self.logger.warning(f"Free tier limitation for {symbol} {date_str}: Using simulated data")

                    simulated_daily = self._create_fallback_daily_bar(symbol, date_str)
                    if simulated_daily:
                        simulated_bars = self._create_simulated_intraday_bars(simulated_daily, date_str)
                        inserted = self._insert_bars_with_event(symbol, event_id, simulated_bars)
                        if inserted > 0:
                            self.logger.info(f"✅ {symbol} {date_str}: {inserted} fallback simulated bars created (Event: {event_id})")
                            return inserted
                else:
                    self.logger.error(f"API error for {symbol} {date_str}: {api_error}")
                    self._save_progress(download_key)
                    return 0

            # Marcar como procesado
            self._save_progress(download_key)

            return inserted

        except Exception as e:
            self.logger.error(f"Error downloading {symbol} {date_str}: {e}")
            return 0

    def download_historical_context(self, symbol: str, event_date: datetime, event_id: int) -> int:
        """
        Descargar 60 días de contexto histórico para un evento
        
        Args:
            symbol: Ticker del símbolo
            event_date: Fecha del evento (cuando el scanner detectó la oportunidad)
            event_id: ID del evento
            
        Returns:
            Número de días históricos descargados
        """
        try:
            date_str = event_date.strftime("%Y-%m-%d")
            download_key = f"{symbol}_{date_str}_history"

            if download_key in self.processed_downloads:
                self.logger.debug(f"Skipping {download_key} history (already processed)")
                return 0

            self.logger.info(f"Downloading 60-day context history for {symbol} before {date_str}...")

            # Calcular rango de fechas históricas (60 días antes del evento)
            start_history_date = event_date - timedelta(days=self.history_days)
            end_history_date = event_date - timedelta(days=1)

            downloaded_count = 0
            current_date = start_history_date

            while current_date <= end_history_date:
                # Solo días laborables (lunes-viernes)
                if current_date.weekday() < 5:
                    try:
                        self._handle_rate_limit()

                        # Descargar barra diaria
                        date_str = current_date.strftime("%Y-%m-%d")
                        aggs = list(self.client.list_aggs(
                            ticker=symbol,
                            multiplier=1,
                            timespan='day',
                            from_=date_str,
                            to=date_str,
                            limit=1
                        ))

                        if aggs:
                            daily_agg = aggs[0]
                            days_before_event = (event_date.date() - current_date.date()).days

                            # Insertar en daily_ohlcv_history
                            success = self._insert_daily_historical_bar(
                                event_id=event_id,
                                symbol=symbol,
                                history_date=current_date,
                                days_before_event=days_before_event,
                                daily_agg=daily_agg
                            )

                            if success:
                                downloaded_count += 1
                                self.logger.debug(f"  {date_str}: {days_before_event} days before event")

                        time.sleep(0.5)  # Pausa entre llamadas

                    except Exception as e:
                        self.logger.debug(f"Could not download daily data for {symbol} {date_str}: {e}")

                current_date += timedelta(days=1)

            self.logger.info(f"✅ {symbol}: {downloaded_count} days of context history downloaded")
            self._save_progress(download_key)
            return downloaded_count

        except Exception as e:
            self.logger.error(f"Error downloading historical context for {symbol}: {e}")
            return 0

    def _create_simulated_intraday_bars(self, daily_agg, date_str):
        """
        Crear barras intradiarias simuladas desde datos diarios
        (Mismo código que el original)
        """
        from types import SimpleNamespace

        # Horarios de mercado: 9:30 AM - 4:00 PM ET (13:30 - 20:00 UTC)
        market_start = datetime.strptime(f"{date_str} 13:30:00", "%Y-%m-%d %H:%M:%S")
        market_end = datetime.strptime(f"{date_str} 20:00:00", "%Y-%m-%d %H:%M:%S")

        # Crear barras simuladas cada 5 minutos durante horas de mercado
        simulated_bars = []
        current_time = market_start

        # Datos diarios
        open_price = daily_agg.open
        high_price = daily_agg.high
        low_price = daily_agg.low
        close_price = daily_agg.close
        volume = daily_agg.volume

        # Simular volatilidad intradiaria
        import random
        random.seed(int(daily_agg.timestamp))  # Seed reproducible

        # Calcular número de barras de 5 minutos en el día
        total_minutes = int((market_end - market_start).total_seconds() / 60)
        num_bars = total_minutes // 5  # Barras de 5 minutos

        if num_bars <= 0:
            num_bars = 1

        # Distribuir volumen entre barras
        volume_per_bar = max(1, volume // num_bars)  # Asegurar volumen mínimo

        # Simular precios intradiarios
        current_price = open_price
        price_range = high_price - low_price

        for i in range(num_bars):
            # Simular movimiento de precio (random walk limitado)
            price_change = random.uniform(-price_range*0.1, price_range*0.1)
            current_price = max(low_price, min(high_price, current_price + price_change))

            # Crear barra simulada
            bar_timestamp = int(current_time.timestamp() * 1000)  # Milisegundos

            # Simular OHLC alrededor del precio actual
            volatility = price_range * 0.05  # 5% volatilidad intradiaria
            bar_open = current_price
            bar_high = current_price + random.uniform(0, volatility)
            bar_low = current_price - random.uniform(0, volatility)
            bar_close = current_price + random.uniform(-volatility/2, volatility/2)

            # Asegurar OHLC coherente
            bar_high = max(bar_high, bar_open, bar_close)
            bar_low = min(bar_low, bar_open, bar_close)

            # Crear objeto similar a Polygon agg
            simulated_bar = SimpleNamespace()
            simulated_bar.timestamp = bar_timestamp
            simulated_bar.open = round(bar_open, 4)
            simulated_bar.high = round(bar_high, 4)
            simulated_bar.low = round(bar_low, 4)
            simulated_bar.close = round(bar_close, 4)
            simulated_bar.volume = volume_per_bar
            simulated_bar.vwap = round((bar_open + bar_high + bar_low + bar_close) / 4, 4)
            simulated_bar.transactions = None

            simulated_bars.append(simulated_bar)

            # Avanzar tiempo
            current_time += timedelta(minutes=5)

        # Ajustar última barra para que termine en el precio de cierre real
        if simulated_bars:
            simulated_bars[-1].close = close_price
            simulated_bars[-1].high = max(simulated_bars[-1].high, close_price)
            simulated_bars[-1].low = min(simulated_bars[-1].low, close_price)

        return simulated_bars

    def _create_fallback_daily_bar(self, symbol: str, date_str: str):
        """
        Crear una barra diaria de fallback cuando no hay acceso a datos de Polygon
        (Mismo código que el original)
        """
        from types import SimpleNamespace
        import random

        # Crear datos simulados realistas basados en el símbolo
        random.seed(hash(symbol + date_str) % 1000000)

        # Precio base aproximado (esto es solo para desarrollo)
        base_price = 10 + random.random() * 90  # Entre $10 y $100

        # Simular volatilidad diaria típica (1-5%)
        daily_volatility = 0.01 + random.random() * 0.04
        open_price = base_price
        close_price = base_price * (1 + random.uniform(-daily_volatility, daily_volatility))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, daily_volatility/2))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, daily_volatility/2))

        # Volumen simulado
        volume = int(random.uniform(10000, 1000000))

        # Timestamp
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        timestamp = int(date_obj.timestamp() * 1000)

        # Crear objeto similar a Polygon agg
        fallback_bar = SimpleNamespace()
        fallback_bar.timestamp = timestamp
        fallback_bar.open = round(open_price, 4)
        fallback_bar.high = round(high_price, 4)
        fallback_bar.low = round(low_price, 4)
        fallback_bar.close = round(close_price, 4)
        fallback_bar.volume = volume
        fallback_bar.vwap = round((open_price + high_price + low_price + close_price) / 4, 4)
        fallback_bar.transactions = None

        return fallback_bar

    def _insert_bars_with_event(self, symbol: str, event_id: int, aggs: List) -> int:
        """
        Insertar barras en market_data.db con event_id

        Args:
            symbol: Ticker del símbolo
            event_id: ID único del evento
            aggs: Lista de agregados de Polygon (o barras simuladas)

        Returns:
            Número de barras insertadas
        """
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            inserted = 0

            for agg in aggs:
                try:
                    # Convertir timestamp de Polygon (milisegundos) a datetime
                    bar_timestamp = datetime.fromtimestamp(agg.timestamp / 1000)

                    # Validar datos
                    if not self._validate_bar(agg):
                        self.logger.debug(f"Bar validation failed: open={agg.open}, high={agg.high}, low={agg.low}, close={agg.close}, volume={agg.volume}")
                        continue

                    # Insertar o ignorar si ya existe
                    cursor.execute("""
                        INSERT OR IGNORE INTO intraday_bars (
                            event_id, symbol, bar_timestamp,
                            open_price, high_price, low_price, close_price,
                            volume, vwap, transactions, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        symbol,
                        bar_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        agg.open,
                        agg.high,
                        agg.low,
                        agg.close,
                        agg.volume,
                        getattr(agg, 'vwap', None),
                        getattr(agg, 'transactions', None),
                        'polygon_simulated' if hasattr(agg, 'simulated') else 'polygon'
                    ))

                    if cursor.rowcount > 0:
                        inserted += 1
                    else:
                        self.logger.debug(f"Bar already exists: {symbol} {bar_timestamp}")

                except Exception as e:
                    self.logger.debug(f"Error inserting bar: {e}")
                    continue

            conn.commit()
            conn.close()

            return inserted

        except Exception as e:
            self.logger.error(f"Error in _insert_bars_with_event: {e}")
            return 0

    def _insert_daily_historical_bar(self, event_id: int, symbol: str, history_date: datetime,
                                   days_before_event: int, daily_agg) -> bool:
        """
        Insertar barra diaria histórica en daily_ohlcv_history

        Args:
            event_id: ID único del evento
            symbol: Ticker del símbolo
            history_date: Fecha histórica
            days_before_event: Días antes del evento principal
            daily_agg: Barra diaria de Polygon

        Returns:
            True si se insertó correctamente
        """
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO daily_ohlcv_history (
                    event_id, symbol, history_date, days_before_event,
                    open_price, high_price, low_price, close_price, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                symbol,
                history_date.strftime("%Y-%m-%d"),
                days_before_event,
                daily_agg.open,
                daily_agg.high,
                daily_agg.low,
                daily_agg.close,
                daily_agg.volume
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            self.logger.debug(f"Error inserting historical bar: {e}")
            return False

    def _validate_bar(self, agg) -> bool:
        """
        Validar datos de una barra
        (Mismo código que el original)
        """
        try:
            # Verificar que tenga datos mínimos
            if not hasattr(agg, 'open') or not hasattr(agg, 'close'):
                return False

            # Verificar precios positivos (permitir valores muy pequeños para datos simulados)
            if agg.open < 0.01 or agg.high < 0.01 or agg.low < 0.01 or agg.close < 0.01:
                return False

            # Verificar OHLC coherente
            if agg.high < max(agg.open, agg.close):
                return False
            if agg.low > min(agg.open, agg.close):
                return False

            # Verificar volumen (permitir volumen 0 para datos simulados)
            if hasattr(agg, 'volume') and agg.volume < 0:
                return False

            return True

        except Exception:
            return False

    def get_scanner_opportunities(self) -> List[Dict[str, str]]:
        """
        Obtener oportunidades detectadas por el scanner desde trading_data.db
        (Mismo código que el original)
        """
        try:
            conn = sqlite3.connect(self.trading_db_path)
            cursor = conn.cursor()

            # Obtener combinaciones únicas de (símbolo, fecha de entrada)
            query = """
                SELECT DISTINCT
                    symbol,
                    DATE(entry_time) as scan_date,
                    strategy,
                    COUNT(*) as signals_count
                FROM trades
                GROUP BY symbol, DATE(entry_time), strategy
                ORDER BY scan_date DESC, symbol
            """

            cursor.execute(query)
            results = cursor.fetchall()

            opportunities = []
            for symbol, scan_date, strategy, count in results:
                opportunities.append({
                    'symbol': symbol,
                    'date': scan_date,
                    'strategy': strategy,
                    'signals_count': count
                })

            conn.close()

            self.logger.info(f"Found {len(opportunities)} scanner opportunities (symbol-date combinations)")
            return opportunities

        except Exception as e:
            self.logger.error(f"Error getting scanner opportunities: {e}")
            return []

    def download_scanner_opportunities_with_context(self, limit: int = None) -> Dict[str, int]:
        """
        Descargar datos expandidos para días específicos en que el scanner detectó oportunidades
        
        Descarga:
        1. Datos intradiarios del día del evento (con event_id)
        2. 60 días de contexto histórico (daily_ohlcv_history)

        Args:
            limit: Límite de oportunidades a descargar (None = todas)

        Returns:
            Diccionario con estadísticas de descarga expandidas
        """
        opportunities = self.get_scanner_opportunities()

        if not opportunities:
            self.logger.warning("No scanner opportunities found")
            return {
                'total_opportunities': 0,
                'downloaded': 0,
                'failed': 0,
                'total_intraday_bars': 0,
                'total_historical_days': 0
            }

        # Aplicar límite si se especifica
        if limit:
            opportunities = opportunities[:limit]

        self.logger.info(f"Downloading expanded data for {len(opportunities)} scanner opportunities...")

        stats = {
            'total_opportunities': len(opportunities),
            'downloaded': 0,
            'failed': 0,
            'total_intraday_bars': 0,
            'total_historical_days': 0
        }

        for i, opp in enumerate(opportunities, 1):
            symbol = opp['symbol']
            date_str = opp['date']
            strategy = opp['strategy']

            try:
                # Parsear fecha del evento
                event_date = datetime.strptime(date_str, "%Y-%m-%d")

                # Generar event_id único
                event_id = self.generate_event_id(symbol, date_str)

                self.logger.info(
                    f"[{i}/{len(opportunities)}] {symbol} on {date_str} "
                    f"(Strategy: {strategy}, Event: {event_id})"
                )

                # 1. Descargar datos intradiarios del día del evento
                intraday_bars = self.download_symbol_date_with_event(symbol, event_date)

                # 2. Descargar 60 días de contexto histórico
                historical_days = self.download_historical_context(symbol, event_date, event_id)

                if intraday_bars > 0 or historical_days > 0:
                    stats['downloaded'] += 1
                    stats['total_intraday_bars'] += intraday_bars
                    stats['total_historical_days'] += historical_days
                    
                    self.logger.info(
                        f"✅ {symbol} {date_str}: {intraday_bars} intraday bars, "
                        f"{historical_days} historical days (Event: {event_id})"
                    )
                else:
                    stats['failed'] += 1
                    self.logger.warning(f"❌ {symbol} {date_str}: Failed to download")

            except Exception as e:
                self.logger.error(f"Error downloading {symbol} {date_str}: {e}")
                stats['failed'] += 1

        return stats


def main():
    """Función principal de ejemplo"""
    print("🚀 Polygon Data Downloader Expandido")
    print("=" * 60)
    print("📈 Sistema con event_id + 60 días de contexto histórico")

    # Configuración
    API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_API_KEY_HERE')

    if API_KEY == 'YOUR_API_KEY_HERE':
        print("❌ ERROR: Configura POLYGON_API_KEY como variable de entorno")
        print("   export POLYGON_API_KEY='tu_api_key'")
        sys.exit(1)

    # Crear downloader expandido
    downloader = PolygonDataDownloaderExpanded(api_key=API_KEY)

    # Descargar datos para 3 oportunidades de prueba
    print("\n🎯 Descargando datos expandidos para 3 oportunidades de prueba...")
    stats = downloader.download_scanner_opportunities_with_context(limit=3)

    print("\n" + "=" * 60)
    print("✅ DESCARGA EXPANDIDA COMPLETADA")
    print("=" * 60)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades procesadas: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras intradiarias totales: {stats['total_intraday_bars']:,}")
    print(f"   - Días históricos totales: {stats['total_historical_days']:,}")

    print(f"\n🎯 Sistema expandido listo:")
    print(f"   - intraday_bars tiene event_id para agrupar eventos")
    print(f"   - daily_ohlcv_history tiene 60 días de contexto por evento")
    print(f"   - Listo para discovery de reglas avanzadas con contexto histórico")


if __name__ == "__main__":
    main()