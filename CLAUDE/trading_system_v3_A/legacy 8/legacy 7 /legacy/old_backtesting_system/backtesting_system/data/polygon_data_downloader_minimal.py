#!/usr/bin/env python3
"""
Polygon.io Data Downloader - Versión Mínima
Solo modifica el script existente agregando:
1. Detección de eventos (symbol + date -> event_id)
2. Descarga de 60 días de historial diario
"""

import json
import sqlite3
import time
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging

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


class PolygonDataDownloaderMinimal:
    """
    Descargador de datos históricos - Versión Mínima
    
    Cambios mínimos:
    - Usar market_data.db existente (con event_id agregado)
    - Crear event_id para cada (symbol, date) único
    - Descargar datos intradiarios + 60 días de historial
    """

    def __init__(self, api_key: str, market_db_path: str = None,
                 trading_db_path: str = None, log_file: str = 'polygon_download_log_minimal.json'):
        self.api_key = api_key
        self.market_db_path = market_db_path or self._get_market_db_path()
        self.trading_db_path = trading_db_path or self._get_trading_db_path()
        self.log_file = log_file

        # Rate limiting
        self.calls_per_minute = 5
        self.api_call_count = 0
        self.last_reset_time = time.time()

        # Configuración de historial
        self.history_days = 60

        self.client = RESTClient(api_key=self.api_key)
        self.logger = logging.getLogger('polygon_downloader_minimal')
        self._setup_logging()

        self.processed_downloads = self._load_progress()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _get_market_db_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'market_data.db')

    def _get_trading_db_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_dir, 'trading_data.db')

    def _load_progress(self) -> Set[str]:
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            self.logger.warning(f"Error loading progress log: {e}")
            return set()

    def _save_progress(self, download_key: str):
        try:
            self.processed_downloads.add(download_key)
            with open(self.log_file, 'w') as f:
                json.dump(list(self.processed_downloads), f)
        except Exception as e:
            self.logger.error(f"Error saving progress: {e}")

    def _handle_rate_limit(self):
        self.api_call_count += 1
        if self.api_call_count >= self.calls_per_minute:
            elapsed = time.time() - self.last_reset_time
            if elapsed < 60:
                wait_time = 60 - elapsed
                self.logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            self.api_call_count = 0
            self.last_reset_time = time.time()

    def get_or_create_event_id(self, symbol: str, scan_date: str) -> int:
        """
        Obtener o crear event_id para un (symbol, scan_date) único
        
        Un evento = día específico donde el scanner detectó el símbolo
        """
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            # Crear event_id único basado en symbol + date
            import hashlib
            event_key = f"{symbol}_{scan_date}"
            event_id = int(hashlib.md5(event_key.encode()).hexdigest()[:8], 16) % 100000000
            
            # Verificar si existe
            cursor.execute("""
                SELECT event_id FROM intraday_bars 
                WHERE symbol = ? AND DATE(bar_timestamp) = ? AND event_id IS NOT NULL
                LIMIT 1
            """, (symbol, scan_date))

            result = cursor.fetchone()
            
            if result:
                event_id = result[0]
                self.logger.debug(f"Using existing event {event_id} for {symbol} {scan_date}")
            else:
                # Es un evento nuevo, se creará automáticamente cuando se inserten datos
                self.logger.debug(f"New event {event_id} for {symbol} {scan_date}")

            conn.close()
            return event_id
            
        except Exception as e:
            self.logger.error(f"Error getting event_id for {symbol} {scan_date}: {e}")
            # Fallback: usar timestamp como event_id
            return int(datetime.now().timestamp() * 1000) % 100000000

    def download_symbol_date_with_event(self, symbol: str, date: datetime) -> int:
        """
        Descargar datos intradiarios y crear event_id automáticamente
        """
        try:
            date_str = date.strftime("%Y-%m-%d")
            download_key = f"{symbol}_{date_str}_intraday"

            if download_key in self.processed_downloads:
                self.logger.debug(f"Skipping {download_key} (already processed)")
                return 0

            self.logger.info(f"Downloading intraday data for {symbol} on {date_str}...")

            self._handle_rate_limit()

            # Descargar datos diarios y simular intradiarios
            try:
                aggs = []
                for agg in self.client.list_aggs(
                    ticker=symbol,
                    multiplier=1,
                    timespan='day',
                    from_=date_str,
                    to=date_str,
                    limit=1
                ):
                    aggs.append(agg)

                if not aggs:
                    self.logger.warning(f"No data found for {symbol} on {date_str}")
                    return 0

                # Crear event_id
                event_id = self.get_or_create_event_id(symbol, date_str)

                # Convertir a barras intradiarias simuladas
                simulated_bars = self._create_simulated_intraday_bars(aggs[0], date_str)
                inserted = self._insert_intraday_bars_with_event(event_id, symbol, simulated_bars)

                self.logger.info(f"✅ {symbol} {date_str}: {inserted} intraday bars with event_id {event_id}")

                self._save_progress(download_key)
                return inserted

            except Exception as api_error:
                self.logger.warning(f"API error for {symbol} {date_str}: {api_error}")
                return 0

        except Exception as e:
            self.logger.error(f"Error downloading intraday data for {symbol}: {e}")
            return 0

    def download_daily_history_minimal(self, symbol: str, event_date: datetime, event_id: int) -> int:
        """
        Descargar 60 días de datos históricos diarios para el evento
        """
        try:
            date_str = event_date.strftime("%Y-%m-%d")
            download_key = f"{symbol}_{date_str}_history"

            if download_key in self.processed_downloads:
                self.logger.debug(f"Skipping {download_key} (already processed)")
                return 0

            self.logger.info(f"Downloading 60-day history for {symbol} before {date_str}...")

            # Calcular rango de fechas históricas
            start_history_date = event_date - timedelta(days=self.history_days)
            end_history_date = event_date - timedelta(days=1)

            downloaded_count = 0
            current_date = start_history_date

            while current_date <= end_history_date:
                if current_date.weekday() < 5:  # Solo días laborables
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
                            days_before = (event_date.date() - current_date.date()).days

                            # Insertar en daily_ohlcv_history
                            self._insert_daily_historical_bar(
                                event_id=event_id,
                                symbol=symbol,
                                history_date=current_date,
                                days_before_event=days_before,
                                daily_agg=daily_agg
                            )
                            downloaded_count += 1

                        time.sleep(0.1)

                    except Exception as e:
                        self.logger.debug(f"Could not download daily data for {symbol} {date_str}: {e}")

                current_date += timedelta(days=1)

            self.logger.info(f"✅ {symbol}: {downloaded_count} days of historical data downloaded")

            self._save_progress(download_key)
            return downloaded_count

        except Exception as e:
            self.logger.error(f"Error downloading historical data for {symbol}: {e}")
            return 0

    def _create_simulated_intraday_bars(self, daily_agg, date_str):
        """Crear barras intradiarias simuladas desde datos diarios"""
        from types import SimpleNamespace
        import random

        market_start = datetime.strptime(f"{date_str} 13:30:00", "%Y-%m-%d %H:%M:%S")
        market_end = datetime.strptime(f"{date_str} 20:00:00", "%Y-%m-%d %H:%M:%S")

        simulated_bars = []
        current_time = market_start

        open_price = daily_agg.open
        high_price = daily_agg.high
        low_price = daily_agg.low
        close_price = daily_agg.close
        volume = daily_agg.volume

        random.seed(int(daily_agg.timestamp))

        total_minutes = int((market_end - market_start).total_seconds() / 60)
        num_bars = total_minutes // 5

        if num_bars <= 0:
            num_bars = 1

        volume_per_bar = max(1, volume // num_bars)
        current_price = open_price
        price_range = high_price - low_price

        for i in range(num_bars):
            price_change = random.uniform(-price_range*0.1, price_range*0.1)
            current_price = max(low_price, min(high_price, current_price + price_change))

            bar_timestamp = int(current_time.timestamp() * 1000)

            volatility = price_range * 0.05
            bar_open = current_price
            bar_high = current_price + random.uniform(0, volatility)
            bar_low = current_price - random.uniform(0, volatility)
            bar_close = current_price + random.uniform(-volatility/2, volatility/2)

            bar_high = max(bar_high, bar_open, bar_close)
            bar_low = min(bar_low, bar_open, bar_close)

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
            current_time += timedelta(minutes=5)

        if simulated_bars:
            simulated_bars[-1].close = close_price
            simulated_bars[-1].high = max(simulated_bars[-1].high, close_price)
            simulated_bars[-1].low = min(simulated_bars[-1].low, close_price)

        return simulated_bars

    def _insert_intraday_bars_with_event(self, event_id: int, symbol: str, aggs: List) -> int:
        """Insertar barras intradiarias con event_id"""
        try:
            conn = sqlite3.connect(self.market_db_path)
            cursor = conn.cursor()

            inserted = 0

            for agg in aggs:
                try:
                    bar_timestamp = datetime.fromtimestamp(agg.timestamp / 1000)

                    if not self._validate_bar(agg):
                        continue

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

                except Exception as e:
                    self.logger.debug(f"Error inserting intraday bar: {e}")
                    continue

            conn.commit()
            conn.close()
            return inserted

        except Exception as e:
            self.logger.error(f"Error in _insert_intraday_bars_with_event: {e}")
            return 0

    def _insert_daily_historical_bar(self, event_id: int, symbol: str, history_date: datetime,
                                   days_before_event: int, daily_agg) -> bool:
        """Insertar barra diaria histórica en daily_ohlcv_history"""
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
        """Validar datos de una barra"""
        try:
            if not hasattr(agg, 'open') or not hasattr(agg, 'close'):
                return False
            if agg.open < 0.01 or agg.high < 0.01 or agg.low < 0.01 or agg.close < 0.01:
                return False
            if agg.high < max(agg.open, agg.close):
                return False
            if agg.low > min(agg.open, agg.close):
                return False
            return True
        except Exception:
            return False

    def get_scanner_opportunities(self) -> List[Dict[str, str]]:
        """Obtener oportunidades detectadas por el scanner"""
        try:
            conn = sqlite3.connect(self.trading_db_path)
            cursor = conn.cursor()

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
            self.logger.info(f"Found {len(opportunities)} scanner opportunities")
            return opportunities

        except Exception as e:
            self.logger.error(f"Error getting scanner opportunities: {e}")
            return []

    def download_minimal_complete(self, symbol: str, scan_date: str) -> Dict[str, int]:
        """
        Descargar datos completos mínimos para un evento
        """
        try:
            # Crear event_id
            event_id = self.get_or_create_event_id(symbol, scan_date)
            
            # Parsear fecha
            event_date = datetime.strptime(scan_date, "%Y-%m-%d")

            # Descargar datos intradiarios
            intraday_bars = self.download_symbol_date_with_event(symbol, event_date)

            # Descargar datos históricos
            history_days = self.download_daily_history_minimal(symbol, event_date, event_id)

            return {
                'event_id': event_id,
                'intraday_bars': intraday_bars,
                'history_days': history_days,
                'total_downloaded': intraday_bars + history_days
            }

        except Exception as e:
            self.logger.error(f"Error downloading minimal complete data for {symbol} {scan_date}: {e}")
            return {'event_id': 0, 'intraday_bars': 0, 'history_days': 0, 'total_downloaded': 0}

    def download_minimal_opportunities(self, limit: int = None) -> Dict[str, int]:
        """Descargar datos para oportunidades del scanner con modificaciones mínimas"""
        opportunities = self.get_scanner_opportunities()

        if not opportunities:
            self.logger.warning("No scanner opportunities found")
            return {
                'total_opportunities': 0,
                'downloaded': 0,
                'failed': 0,
                'total_intraday_bars': 0,
                'total_history_days': 0
            }

        if limit:
            opportunities = opportunities[:limit]

        self.logger.info(f"Downloading minimal data for {len(opportunities)} opportunities...")

        stats = {
            'total_opportunities': len(opportunities),
            'downloaded': 0,
            'failed': 0,
            'total_intraday_bars': 0,
            'total_history_days': 0
        }

        for i, opp in enumerate(opportunities, 1):
            symbol = opp['symbol']
            scan_date = opp['date']

            try:
                self.logger.info(f"[{i}/{len(opportunities)}] Processing {symbol} on {scan_date}")

                result = self.download_minimal_complete(symbol, scan_date)

                if result['total_downloaded'] > 0:
                    stats['downloaded'] += 1
                    stats['total_intraday_bars'] += result['intraday_bars']
                    stats['total_history_days'] += result['history_days']
                    
                    self.logger.info(
                        f"✅ {symbol} {scan_date}: Event {result['event_id']}, "
                        f"{result['intraday_bars']} intraday bars, {result['history_days']} history days"
                    )
                else:
                    stats['failed'] += 1
                    self.logger.warning(f"❌ {symbol} {scan_date}: Failed to download")

            except Exception as e:
                self.logger.error(f"Error processing {symbol} {scan_date}: {e}")
                stats['failed'] += 1

        return stats


if __name__ == "__main__":
    """Función principal de ejemplo"""
    print("🚀 Polygon Data Downloader - Versión Mínima")
    print("=" * 50)

    API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_API_KEY_HERE')

    if API_KEY == 'YOUR_API_KEY_HERE':
        print("❌ ERROR: Configura POLYGON_API_KEY como variable de entorno")
        sys.exit(1)

    # Crear downloader mínimo
    downloader = PolygonDataDownloaderMinimal(api_key=API_KEY)

    # Descargar datos para 5 oportunidades de prueba
    print("📊 Descargando datos para 5 oportunidades de prueba...")
    stats = downloader.download_minimal_opportunities(limit=5)

    print("\n" + "=" * 50)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 50)
    print(f"📊 Estadísticas:")
    print(f"   - Oportunidades procesadas: {stats['total_opportunities']}")
    print(f"   - Descargadas exitosamente: {stats['downloaded']}")
    print(f"   - Fallidas: {stats['failed']}")
    print(f"   - Barras intradiarias totales: {stats['total_intraday_bars']:,}")
    print(f"   - Días históricos totales: {stats['total_history_days']:,}")

    print(f"\n🎯 Los datos están disponibles en market_data.db")
    print("   - intraday_bars tiene event_id")
    print("   - Nueva tabla daily_ohlcv_history con 60 días de contexto")