#!/usr/bin/env python3
"""
Polygon.io Data Downloader - Solo Datos de 1 Minuto
Versión simplificada que SOLO descarga datos intradía a 1 minuto
SIN datos diarios, SIN event_id, SIN contexto histórico
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


class PolygonDataDownloaderMinuteOnly:
    """
    Descargador simplificado que SOLO descarga datos intradía a 1 minuto
    SIN event_id, SIN contexto histórico, SIN datos diarios
    """

    def __init__(self, api_key: str, market_db_path: str = None,
                 trading_db_path: str = None, log_file: str = 'polygon_download_log_minute_only.json'):
        """
        Inicializar downloader simplificado

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

        # Inicializar cliente de Polygon
        self.client = RESTClient(api_key=self.api_key)

        # Logging
        self.logger = logging.getLogger('polygon_downloader_minute_only')
        self._setup_logging()

        # Cargar progreso previo
        self.processed_downloads = self._load_progress()

        # Inicializar base de datos simple
        self._init_database_minute_only()

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

    def _init_database_minute_only(self):
        """Inicializar market_data.db con estructura simple SOLO para datos de 1 minuto"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # Crear tabla simple para datos de 1 minuto (sin event_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intraday_bars_minute (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    bar_timestamp TIMESTAMP NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    vwap REAL,
                    transactions INTEGER,
                    source TEXT DEFAULT 'polygon',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, bar_timestamp)
                )
            """)

            # Crear índices para búsquedas eficientes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_symbol ON intraday_bars_minute(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_timestamp ON intraday_bars_minute(bar_timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_symbol_date ON intraday_bars_minute(symbol, DATE(bar_timestamp))")

            # Limpiar estructuras complejas del sistema anterior
            # Remover event_id de intraday_bars si existe
            cursor.execute("PRAGMA table_info(intraday_bars)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'event_id' in columns:
                self.logger.info("⚠️  Limpiando estructura compleja del sistema anterior...")
                try:
                    # Si existe event_id, lo removemos para simplificar
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS intraday_bars_minute_backup AS
                        SELECT id, symbol, bar_timestamp, open_price, high_price, low_price, 
                               close_price, volume, vwap, transactions, source, created_at
                        FROM intraday_bars
                    """)
                    cursor.execute("DROP TABLE IF EXISTS intraday_bars")
                    cursor.execute("ALTER TABLE intraday_bars_minute_backup RENAME TO intraday_bars")
                    self.logger.info("✅ Estructura simplificada - event_id removido")
                except Exception as e:
                    self.logger.warning(f"Could not clean old structure: {e}")

            # Eliminar tabla de contexto histórico
            cursor.execute("DROP TABLE IF EXISTS daily_ohlcv_history")
            self.logger.info("✅ Tabla de contexto histórico eliminada")

            conn.commit()
            conn.close()

            self.logger.info(f"Simple market database initialized: {self.market_db_path}")

        except Exception as e:
            self.logger.error(f"Error initializing simple market database: {e}")
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

    def download_symbol_date_minute_only(self, symbol: str, date: datetime) -> int:
        """
        Descargar SOLO datos de 1 minuto para un símbolo en una fecha específica

        Args:
            symbol: Ticker del símbolo
            date: Fecha para descargar

        Returns:
            Número de barras de 1 minuto descargadas
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            download_key = f"{symbol}_{date_str}"

            # Verificar si ya se procesó
            if download_key in self.processed_downloads:
                self.logger.info(f"Skipping {download_key} (already processed)")
                return 0

            self.logger.info(f"Downloading 1-minute data for {symbol} on {date_str}...")

            # Manejar rate limit
            self._handle_rate_limit()

            # Descargar datos REALES de 1 minuto desde Polygon
            try:
                aggs = []
                for agg in self.client.list_aggs(
                    ticker=symbol,
                    multiplier=1,
                    timespan='minute',  # SOLO datos de 1 minuto
                    from_=date_str,
                    to=date_str,
                    limit=50000  # Máximo permitido
                ):
                    aggs.append(agg)

                if not aggs:
                    self.logger.warning(f"No 1-minute data found for {symbol} on {date_str}")
                    self._save_progress(download_key)
                    return 0

                # Insertar barras de 1 minuto directamente
                inserted = self._insert_minute_bars(symbol, aggs)

                self.logger.info(f"✅ {symbol} {date_str}: {inserted} real 1-minute bars downloaded")

            except Exception as api_error:
                # Si falla la API, no usar datos de fallback (solo datos reales)
                self.logger.error(f"API error for {symbol} {date_str}: {api_error}")
                self._save_progress(download_key)
                return 0

            # Marcar como procesado
            self._save_progress(download_key)

            return inserted

        except Exception as e:
            self.logger.error(f"Error downloading {symbol} {date_str}: {e}")
            return 0

    def _insert_minute_bars(self, symbol: str, aggs: List) -> int:
        """
        Insertar barras de 1 minuto en market_data.db

        Args:
            symbol: Ticker del símbolo
            aggs: Lista de agregados de Polygon (datos reales de 1 minuto)

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
                            symbol, bar_timestamp,
                            open_price, high_price, low_price, close_price,
                            volume, vwap, transactions, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        bar_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        agg.open,
                        agg.high,
                        agg.low,
                        agg.close,
                        agg.volume,
                        getattr(agg, 'vwap', None),
                        getattr(agg, 'transactions', None),
                        'polygon_real'
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
            self.logger.error(f"Error in _insert_minute_bars: {e}")
            return 0

    def _validate_bar(self, agg) -> bool:
        """
        Validar datos de una barra
        """
        try:
            # Verificar que tenga datos mínimos
            if not hasattr(agg, 'open') or not hasattr(agg, 'close'):
                return False

            # Verificar precios positivos
            if agg.open < 0.01 or agg.high < 0.01 or agg.low < 0.01 or agg.close < 0.01:
                return False

            # Verificar OHLC coherente
            if agg.high < max(agg.open, agg.close):
                return False
            if agg.low > min(agg.open, agg.close):
                return False

            # Verificar volumen
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

    def download_scanner_opportunities_minute_only(self, limit: int = None) -> Dict[str, int]:
        """
        Descargar SOLO datos de 1 minuto para días específicos en que el scanner detectó oportunidades
        
        SIN event_id, SIN contexto histórico, SOLO datos reales de 1 minuto

        Args:
            limit: Límite de oportunidades a descargar (None = todas)

        Returns:
            Diccionario con estadísticas de descarga simplificadas
        """
        opportunities = self.get_scanner_opportunities()

        if not opportunities:
            self.logger.warning("No scanner opportunities found")
            return {
                'total_opportunities': 0,
                'downloaded': 0,
                'failed': 0,
                'total_minute_bars': 0
            }

        # Aplicar límite si se especifica
        if limit:
            opportunities = opportunities[:limit]

        self.logger.info(f"Downloading 1-minute data for {len(opportunities)} scanner opportunities...")

        stats = {
            'total_opportunities': len(opportunities),
            'downloaded': 0,
            'failed': 0,
            'total_minute_bars': 0
        }

        for i, opp in enumerate(opportunities, 1):
            symbol = opp['symbol']
            date_str = opp['date']
            strategy = opp['strategy']

            try:
                # Parsear fecha del evento
                event_date = datetime.strptime(date_str, "%Y-%m-%d")

                self.logger.info(
                    f"[{i}/{len(opportunities)}] {symbol} on {date_str} "
                    f"(Strategy: {strategy}) - 1-minute data only"
                )

                # Descargar SOLO datos de 1 minuto
                minute_bars = self.download_symbol_date_minute_only(symbol, event_date)

                if minute_bars > 0:
                    stats['downloaded'] += 1
                    stats['total_minute_bars'] += minute_bars
                    
                    self.logger.info(
                        f"✅ {symbol} {date_str}: {minute_bars} real 1-minute bars"
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
    print("🚀 Polygon Data Downloader - Solo 1 Minuto")
    print("=" * 60)
    print("📈 Sistema simplificado: SOLO datos de 1 minuto")
    print("❌ Sin datos diarios, sin event_id, sin contexto histórico")

    # Configuración
    API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_API_KEY_HERE')

    if API_KEY == 'YOUR_API_KEY_HERE':
        print("❌ ERROR: Configura POLYGON_API_KEY como variable de entorno")
        print("   export POLYGON_API_KEY='tu_api_key'")
        sys.exit(1)

    # Crear downloader simplificado
    downloader = PolygonDataDownloaderMinuteOnly(api_key=API_KEY)

    # Descargar datos para 3 oportunidades de prueba
    print("\n🎯 Descargando datos de 1 minuto para 3 oportunidades de prueba...")
    stats = downloader.download_scanner_opportunities_minute_only(limit=3)

    print("\n" + "=" * 60)
    print("✅ DESCARGA DE 1 MINUTO COMPLETADA")
    print("=" * 60)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades procesadas: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras de 1 minuto totales: {stats['total_minute_bars']:,}")

    print(f"\n🎯 Sistema simplificado listo:")
    print(f"   - SOLO datos de 1 minuto reales de Polygon")
    print(f"   - Sin event_id ni estructuras complejas")
    print(f"   - Base de datos limpia y simple")


if __name__ == "__main__":
    main()